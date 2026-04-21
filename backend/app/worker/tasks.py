"""
Celery task definitions for the AI Presentation Intelligence Platform.

Implements:
- 15.2  generate_presentation_task  — full pipeline wrapper
- 15.3  regenerate_slide_task       — single slide regeneration
- 15.4  export_pptx_task            — background PPTX export + S3 upload
- 15.5  Job status lifecycle        — queued→processing→completed/failed/cancelled
- 15.6  Idempotency key checking    — prevent duplicate job execution
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import structlog
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import Task
from celery.exceptions import Ignore
from sqlalchemy import select, update

from app.db.models import Presentation, PresentationStatus
from app.db.session import async_session_maker
from app.worker.celery_app import celery_app

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Idempotency helpers (15.6)
# ---------------------------------------------------------------------------

IDEMPOTENCY_TTL_SECONDS = 86400  # 24 hours


def _idempotency_redis_key(idempotency_key: str) -> str:
    return f"idempotency:{idempotency_key}"


def _check_and_set_idempotency(redis_client: Any, key: str, job_id: str) -> Optional[str]:
    """
    Atomically check if key exists; if not, set it and return None.
    If it already exists, return the existing job_id (duplicate detected).
    Uses Redis SET NX (set-if-not-exists) for atomicity.
    """
    redis_key = _idempotency_redis_key(key)
    was_set = redis_client.set(redis_key, job_id, nx=True, ex=IDEMPOTENCY_TTL_SECONDS)
    if was_set:
        return None  # new job — proceed
    existing = redis_client.get(redis_key)
    return existing.decode() if isinstance(existing, bytes) else existing


def _get_redis_client():
    """Return a synchronous Redis client for idempotency checks."""
    import redis as redis_lib
    from app.core.config import settings
    return redis_lib.from_url(settings.CELERY_BROKER_URL, decode_responses=False)


# ---------------------------------------------------------------------------
# DB helpers (15.5)
# ---------------------------------------------------------------------------

_worker_event_loop = None


def _get_or_create_event_loop():
    """Get or create a persistent event loop for the worker process."""
    global _worker_event_loop
    if _worker_event_loop is None or _worker_event_loop.is_closed():
        _worker_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_event_loop)
    return _worker_event_loop


def _run_async(coro):
    """Run an async coroutine from a sync Celery task using a persistent event loop."""
    loop = _get_or_create_event_loop()
    return loop.run_until_complete(coro)


async def _update_presentation_status(
    presentation_id: str,
    status: PresentationStatus,
    error_message: Optional[str] = None,
) -> None:
    """Atomically update presentation status in DB."""
    values: Dict[str, Any] = {"status": status}
    if error_message is not None:
        # Store error in pipeline_executions via orchestrator; just update status here
        pass
    async with async_session_maker() as db:
        await db.execute(
            update(Presentation)
            .where(Presentation.presentation_id == presentation_id)
            .values(**values)
        )
        await db.commit()


async def _get_presentation(presentation_id: str) -> Optional[Presentation]:
    async with async_session_maker() as db:
        result = await db.execute(
            select(Presentation).where(
                Presentation.presentation_id == presentation_id
            )
        )
        return result.scalars().first()


# ---------------------------------------------------------------------------
# Base task class with common retry / error handling
# ---------------------------------------------------------------------------

class BaseTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        presentation_id = kwargs.get("presentation_id") or (args[0] if args else None)
        if presentation_id:
            try:
                _run_async(
                    _update_presentation_status(
                        presentation_id, PresentationStatus.failed
                    )
                )
            except Exception:
                logger.exception("Failed to update status on task failure")
        super().on_failure(exc, task_id, args, kwargs, einfo)


# ---------------------------------------------------------------------------
# 15.2  generate_presentation_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="generate_presentation",
    queue="high-priority",
    bind=True,
    base=BaseTask,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def generate_presentation_task(
    self: Task,
    presentation_id: str,
    topic: str,
    tenant_id: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Wrap the full multi-agent pipeline in a Celery task.

    Status lifecycle (15.5):
      queued → processing → completed | failed

    Idempotency (15.6):
      If idempotency_key is provided and a job already ran for that key,
      the task is ignored and the existing job_id is returned.
    """
    job_id = self.request.id

    # --- Idempotency check (15.6) ---
    if idempotency_key:
        redis_client = _get_redis_client()
        existing_job_id = _check_and_set_idempotency(redis_client, idempotency_key, job_id)
        if existing_job_id and existing_job_id != job_id:
            logger.info(
                "duplicate_job_ignored",
                idempotency_key=idempotency_key,
                existing_job_id=existing_job_id,
                new_job_id=job_id,
            )
            raise Ignore()

    # --- Status: processing (15.5) ---
    _run_async(_update_presentation_status(presentation_id, PresentationStatus.processing))

    try:
        from app.agents.pipeline_orchestrator import pipeline_orchestrator

        ctx = _run_async(
            pipeline_orchestrator.run(
                presentation_id=presentation_id,
                topic=topic,
                resume_from_checkpoint=True,
                job_id=job_id,
            )
        )

        all_done = len(ctx.completed_agents) == len(
            __import__(
                "app.agents.pipeline_orchestrator",
                fromlist=["PIPELINE_SEQUENCE"],
            ).PIPELINE_SEQUENCE
        )

        final_status = (
            PresentationStatus.completed if all_done else PresentationStatus.failed
        )
        # _finalize() inside orchestrator already updates the DB; this is a safety net
        _run_async(_update_presentation_status(presentation_id, final_status))

        return {
            "job_id": job_id,
            "presentation_id": presentation_id,
            "status": final_status.value,
            "completed_agents": [a.value for a in ctx.completed_agents],
            "quality_score": (ctx.quality_result or {}).get("composite_score"),
        }

    except Exception as exc:
        logger.exception(
            "generate_presentation_task_failed",
            presentation_id=presentation_id,
            exc=str(exc),
        )
        _run_async(_update_presentation_status(presentation_id, PresentationStatus.failed))
        raise self.retry(exc=exc) from exc


# ---------------------------------------------------------------------------
# 15.3  regenerate_slide_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="regenerate_slide",
    queue="default",
    bind=True,
    base=BaseTask,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def regenerate_slide_task(
    self: Task,
    presentation_id: str,
    slide_id: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Regenerate a single slide within an existing presentation.

    Fetches the presentation topic and existing slides, runs a targeted
    pipeline pass for the specific slide, and updates the slide in-place.
    """
    job_id = self.request.id

    # --- Idempotency check (15.6) ---
    if idempotency_key:
        redis_client = _get_redis_client()
        existing_job_id = _check_and_set_idempotency(redis_client, idempotency_key, job_id)
        if existing_job_id and existing_job_id != job_id:
            logger.info(
                "duplicate_slide_regen_ignored",
                idempotency_key=idempotency_key,
                existing_job_id=existing_job_id,
            )
            raise Ignore()

    try:
        presentation = _run_async(_get_presentation(presentation_id))
        if presentation is None:
            raise ValueError(f"Presentation {presentation_id} not found")

        topic = presentation.topic
        existing_slides = presentation.slides or {}

        # Find the target slide
        slides_list = existing_slides.get("slides", [])
        target_slide = next(
            (s for s in slides_list if s.get("slide_id") == slide_id), None
        )
        if target_slide is None:
            raise ValueError(f"Slide {slide_id} not found in presentation {presentation_id}")

        slide_type = target_slide.get("type", "content")
        slide_number = target_slide.get("slide_number", 1)

        # Run a focused regeneration via the prompt engineering + LLM path
        regenerated_slide = _run_async(
            _regenerate_single_slide(
                presentation_id=presentation_id,
                topic=topic,
                slide_id=slide_id,
                slide_type=slide_type,
                slide_number=slide_number,
                existing_slides=existing_slides,
            )
        )

        # Patch the slide in the existing slides structure
        updated_slides = _patch_slide(existing_slides, slide_id, regenerated_slide)

        _run_async(
            _persist_updated_slides(presentation_id, updated_slides)
        )

        return {
            "job_id": job_id,
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "status": "completed",
        }

    except Exception as exc:
        logger.exception(
            "regenerate_slide_task_failed",
            presentation_id=presentation_id,
            slide_id=slide_id,
            exc=str(exc),
        )
        raise self.retry(exc=exc) from exc


async def _regenerate_single_slide(
    presentation_id: str,
    topic: str,
    slide_id: str,
    slide_type: str,
    slide_number: int,
    existing_slides: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Use the prompt engineering + LLM provider to regenerate one slide.
    Falls back to a minimal placeholder on any failure.
    """
    try:
        from app.agents.prompt_engineering import prompt_engineering_agent
        from app.services.llm_provider import provider_factory
        from app.core.config import settings

        provider_type = settings.LLM_PRIMARY_PROVIDER
        provider = provider_factory.get_provider(provider_type)

        # Build a targeted prompt for single-slide regeneration
        prompt_context = {
            "topic": topic,
            "slide_type": slide_type,
            "slide_number": slide_number,
            "slide_id": slide_id,
            "total_slides": existing_slides.get("total_slides", 1),
            "regenerate_single": True,
        }

        optimized = await prompt_engineering_agent.optimize(
            context=prompt_context,
            provider_type=provider_type,
        )

        response = await provider.generate(optimized.get("system_prompt", ""), optimized.get("user_prompt", ""))
        raw_content = response.get("content", "{}")

        # Parse and validate the regenerated slide
        import json as _json
        try:
            slide_data = _json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        except Exception:
            slide_data = {}

        # Ensure required fields
        slide_data.setdefault("slide_id", slide_id)
        slide_data.setdefault("slide_number", slide_number)
        slide_data.setdefault("type", slide_type)
        slide_data.setdefault("title", f"Slide {slide_number}")
        slide_data.setdefault("content", {"bullets": []})
        slide_data.setdefault("visual_hint", "bullet-left")
        slide_data.setdefault(
            "layout_constraints",
            {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
        )
        slide_data.setdefault(
            "metadata",
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider_used": provider_type,
                "quality_score": None,
            },
        )
        return slide_data

    except Exception as exc:
        logger.warning("single_slide_regen_failed_using_placeholder", exc=str(exc))
        return {
            "slide_id": slide_id,
            "slide_number": slide_number,
            "type": slide_type,
            "title": f"Slide {slide_number}",
            "content": {"bullets": ["Content regeneration failed — please retry"]},
            "visual_hint": "bullet-left",
            "layout_constraints": {
                "max_content_density": 0.75,
                "min_whitespace_ratio": 0.25,
            },
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider_used": "fallback",
                "quality_score": None,
            },
        }


def _patch_slide(
    existing_slides: Dict[str, Any],
    slide_id: str,
    new_slide: Dict[str, Any],
) -> Dict[str, Any]:
    """Replace the slide with matching slide_id in the slides structure."""
    import copy
    updated = copy.deepcopy(existing_slides)
    slides_list = updated.get("slides", [])
    for i, slide in enumerate(slides_list):
        if slide.get("slide_id") == slide_id:
            slides_list[i] = new_slide
            break
    updated["slides"] = slides_list
    return updated


async def _persist_updated_slides(
    presentation_id: str, updated_slides: Dict[str, Any]
) -> None:
    async with async_session_maker() as db:
        await db.execute(
            update(Presentation)
            .where(Presentation.presentation_id == presentation_id)
            .values(slides=updated_slides.get("slides"))
        )
        await db.commit()


# ---------------------------------------------------------------------------
# 15.4  export_pptx_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="export_pptx",
    queue="export",
    bind=True,
    base=BaseTask,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
    time_limit=60,  # hard limit: 60s (spec: 30s for ≤50 slides)
    soft_time_limit=45,
)
def export_pptx_task(
    self: Task,
    presentation_id: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a PPTX file from a completed presentation and upload to S3/MinIO.

    Returns a signed download URL valid for 1 hour.
    """
    job_id = self.request.id

    # --- Idempotency check (15.6) ---
    if idempotency_key:
        redis_client = _get_redis_client()
        existing_job_id = _check_and_set_idempotency(redis_client, idempotency_key, job_id)
        if existing_job_id and existing_job_id != job_id:
            logger.info(
                "duplicate_export_ignored",
                idempotency_key=idempotency_key,
                existing_job_id=existing_job_id,
            )
            raise Ignore()

    try:
        presentation = _run_async(_get_presentation(presentation_id))
        if presentation is None:
            raise ValueError(f"Presentation {presentation_id} not found")

        if presentation.status != PresentationStatus.completed:
            raise ValueError(
                f"Cannot export presentation {presentation_id} with status {presentation.status}"
            )

        slides_data = presentation.slides or []
        theme = presentation.selected_theme or "dark_modern"
        design_spec = presentation.design_spec or {}

        # Build PPTX via Node.js pptx-service (Claude-quality rendering)
        pptx_bytes = _build_pptx(slides_data, theme, design_spec)

        # Upload to S3/MinIO and get signed URL
        object_key = f"exports/{presentation_id}/{job_id}.pptx"
        signed_url = _run_async(_upload_to_s3(object_key, pptx_bytes))

        return {
            "job_id": job_id,
            "presentation_id": presentation_id,
            "status": "completed",
            "download_url": signed_url,
            "object_key": object_key,
        }

    except Exception as exc:
        logger.exception(
            "export_pptx_task_failed",
            presentation_id=presentation_id,
            exc=str(exc),
        )
        raise self.retry(exc=exc) from exc


def _build_pptx(slides_data: Any, theme: str, design_spec: Optional[Dict[str, Any]] = None) -> bytes:
    """
    Build a PPTX file by calling the pptx-service Node.js microservice.

    The pptx-service implements the full Claude-style design system using pptxgenjs:
    - Topic-specific color palettes from design_spec (DesignAgent output)
    - Visual motif carried across all slides
    - Varied layouts with icons, charts, callouts
    - Modern chart styling with dark themes
    - Numbered bullet cards, KPI badges, comparison columns
    - No fallback - always uses pptx-service for consistent Claude-style output

    Args:
        slides_data: List of slide dictionaries from Slide_JSON
        theme: Theme name (mckinsey, deloitte, dark_modern)
        design_spec: DesignAgent output dict with palette, fonts, motif

    Returns:
        PPTX file as bytes

    Raises:
        Exception: If pptx-service is unavailable or fails
    """
    import httpx
    from app.core.config import settings

    # slides_data may be a list directly or a dict with a "slides" key
    if isinstance(slides_data, dict):
        slides_list = slides_data.get("slides", [])
    elif isinstance(slides_data, list):
        slides_list = slides_data
    else:
        slides_list = []

    pptx_service_url = getattr(settings, "PPTX_SERVICE_URL", "http://pptx-service:3001")
    
    logger.info(
        "attempting_pptx_service_build",
        url=pptx_service_url,
        slide_count=len(slides_list),
        theme=theme,
        has_design_spec=bool(design_spec),
    )

    try:
        response = httpx.post(
            f"{pptx_service_url}/build",
            json={
                "slides": slides_list,
                "design_spec": design_spec or {},
                "theme": theme,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        logger.info(
            "pptx_service_build_success",
            slide_count=len(slides_list),
            size_bytes=len(response.content),
            theme=theme,
        )
        return response.content

    except httpx.TimeoutException as exc:
        logger.error(
            "pptx_service_timeout",
            error=str(exc),
            slide_count=len(slides_list),
            timeout=60.0,
        )
        raise Exception(f"PPTX service timeout after 60 seconds: {str(exc)}")
    except httpx.HTTPStatusError as exc:
        logger.error(
            "pptx_service_http_error",
            error=str(exc),
            status_code=exc.response.status_code,
            response_text=exc.response.text[:500],
            slide_count=len(slides_list),
        )
        raise Exception(f"PPTX service HTTP error {exc.response.status_code}: {exc.response.text[:200]}")
    except Exception as exc:
        logger.error(
            "pptx_service_error",
            error=str(exc),
            error_type=type(exc).__name__,
            slide_count=len(slides_list),
        )
        raise Exception(f"PPTX service error ({type(exc).__name__}): {str(exc)}")


async def _upload_to_s3(object_key: str, data: bytes) -> str:
    """Upload bytes to MinIO/S3 and return a 1-hour signed URL."""
    import boto3
    from botocore.client import Config
    from app.core.config import settings

    s3_client = boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=settings.MINIO_BUCKET)
    except Exception:
        s3_client.create_bucket(Bucket=settings.MINIO_BUCKET)

    s3_client.put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=object_key,
        Body=data,
        ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

    signed_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": object_key},
        ExpiresIn=3600,  # 1 hour TTL
    )
    return signed_url
