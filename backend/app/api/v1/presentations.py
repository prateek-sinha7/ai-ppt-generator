"""
Presentations API — Generation, Status, Retrieval, Regeneration, and Streaming.

Endpoints:
  POST   /api/v1/presentations                          — 17.1 Create & enqueue
  GET    /api/v1/presentations/{id}/status              — 17.2 Poll progress
  GET    /api/v1/presentations/{id}                     — 17.3 Full Slide_JSON
  POST   /api/v1/presentations/{id}/regenerate          — 17.4 Regenerate
  GET    /api/v1/presentations/{id}/stream              — 16.1 SSE stream
  DELETE /api/v1/jobs/{job_id}                          — 16.5 Cancel job

Rate-limit headers (17.5) are injected on every response via the
RateLimitHeaderMiddleware applied in this module.
"""
from __future__ import annotations

import math
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_sse, require_min_role
from app.db.models import (
    Presentation,
    PipelineExecution,
    PresentationStatus,
    User,
)
from app.db.session import get_db
from app.services.redis_cache import redis_cache
from app.services.streaming import streaming_service
from app.worker.tasks import generate_presentation_task

router = APIRouter(tags=["presentations"])

# ---------------------------------------------------------------------------
# Rate-limit constants (17.5)
# Free tier: 10/hr, Premium: 100/hr  — role "member" = free, "admin" = premium
# ---------------------------------------------------------------------------

_RATE_LIMIT_FREE = 10
_RATE_LIMIT_PREMIUM = 100
_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


def _rate_limit_for_role(role: str) -> int:
    return _RATE_LIMIT_PREMIUM if role == "admin" else _RATE_LIMIT_FREE


async def _get_rate_limit_info(user: User) -> Dict[str, int]:
    """
    Return current rate-limit counters for the user.
    Uses Redis key  ratelimit:{user_id}  with 1-hour sliding window.
    """
    limit = _rate_limit_for_role(user.role)
    key = f"ratelimit:{user.id}"

    try:
        raw = await redis_cache.get(key)
        count = raw if isinstance(raw, int) else 0
    except Exception:
        count = 0

    remaining = max(0, limit - count)

    # Compute reset timestamp (end of current window)
    try:
        client = redis_cache._client
        if client:
            ttl = await client.ttl(key)
            reset_at = int(time.time()) + (ttl if ttl > 0 else _RATE_LIMIT_WINDOW_SECONDS)
        else:
            reset_at = int(time.time()) + _RATE_LIMIT_WINDOW_SECONDS
    except Exception:
        reset_at = int(time.time()) + _RATE_LIMIT_WINDOW_SECONDS

    return {"limit": limit, "remaining": remaining, "reset": reset_at}


async def _increment_rate_limit(user: User) -> None:
    """Increment the user's request counter; set TTL on first use."""
    key = f"ratelimit:{user.id}"
    try:
        client = redis_cache._client
        if client:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, _RATE_LIMIT_WINDOW_SECONDS)
    except Exception:
        pass  # non-fatal — don't block the request


def _add_rate_limit_headers(response: Response, info: Dict[str, int]) -> None:
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CreatePresentationRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=5000, description="Presentation topic or pasted content")
    theme: Optional[str] = Field(None, description="Optional theme: hexaware_corporate or hexaware_professional")

    @field_validator("topic")
    @classmethod
    def topic_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must not be blank")
        return v.strip()

    @field_validator("theme")
    @classmethod
    def theme_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = {"hexaware_corporate", "hexaware_professional"}
        normalised = v.strip().lower()
        if normalised not in valid:
            raise ValueError("theme must be one of: hexaware_corporate, hexaware_professional")
        return normalised


class CreatePresentationResponse(BaseModel):
    job_id: str
    presentation_id: str
    status: str
    message: str


class DetectedContextSchema(BaseModel):
    detected_industry: Optional[str] = None
    confidence_score: Optional[float] = None
    sub_sector: Optional[str] = None
    target_audience: Optional[str] = None
    selected_template_id: Optional[str] = None
    theme: Optional[str] = None
    compliance_context: Optional[List[str]] = None


class PresentationStatusResponse(BaseModel):
    presentation_id: str
    status: str
    progress: int  # 0-100
    current_agent: Optional[str] = None
    detected_context: Optional[DetectedContextSchema] = None
    quality_score: Optional[float] = None
    error_message: Optional[str] = None


class RegenerateRequest(BaseModel):
    """No provider field — backend selects from .env (Req 13)."""
    pass


class RegenerateResponse(BaseModel):
    job_id: str
    presentation_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Progress calculation helper
# ---------------------------------------------------------------------------

_AGENT_PROGRESS: Dict[str, int] = {
    "industry_classifier": 8,
    "design": 16,
    "storyboarding": 24,
    "research": 36,
    "data_enrichment": 48,
    "prompt_engineering": 56,
    "llm_provider": 70,
    "validation": 80,
    "visual_refinement": 88,
    "quality_scoring": 95,
}

_STATUS_PROGRESS: Dict[str, int] = {
    "queued": 0,
    "processing": 5,
    "completed": 100,
    "failed": 0,
    "cancelled": 0,
}


def _compute_progress(exec_status: str, current_agent: Optional[str]) -> int:
    if exec_status == "completed":
        return 100
    if current_agent and current_agent in _AGENT_PROGRESS:
        return _AGENT_PROGRESS[current_agent]
    return _STATUS_PROGRESS.get(exec_status, 0)


def _flatten_slide_for_frontend(slide: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform backend slide structure to frontend-expected structure.
    
    Backend stores: { "content": { "bullets": [...], "chart_data": {...}, ... } }
    Frontend expects: { "bullets": [...], "chart_data": {...], ... }
    
    Also normalizes field names from Claude's output format to frontend format.
    """
    flattened = {**slide}
    
    # Resolve the correct slide type.
    # The DB stores both "type" (set by validation agent, often wrong "content")
    # and "slide_type" (set by LLM, the correct value).
    # Always prefer slide_type when present, then fall back to type.
    slide_type_raw = flattened.pop("slide_type", None)
    type_mapping = {
        "title": "title", "title_slide": "title",
        "content": "content", "content_slide": "content",
        "chart": "chart", "chart_slide": "chart",
        "table": "table", "table_slide": "table",
        "comparison": "comparison", "comparison_slide": "comparison",
        "metric": "metric", "metric_slide": "metric",
    }
    if slide_type_raw:
        flattened["type"] = type_mapping.get(str(slide_type_raw).lower(), "content")
    elif "type" not in flattened:
        # Infer from visual_hint as last resort
        hint_to_type = {
            "centered": "title",
            "split-chart-right": "chart",
            "split-table-left": "table",
            "two-column": "comparison",
            "bullet-left": "content",
            "highlight-metric": "metric",
        }
        flattened["type"] = hint_to_type.get(flattened.get("visual_hint", ""), "content")

    if "layout_hint" in flattened and "visual_hint" not in flattened:
        flattened["visual_hint"] = flattened.pop("layout_hint")
    elif "layout_hint" in flattened:
        flattened.pop("layout_hint")

    # slide_number → keep as-is but also ensure id exists
    if "slide_number" in flattened and "id" not in flattened:
        flattened["id"] = str(flattened["slide_number"])

    # Extract content fields and flatten them
    content = flattened.pop("content", {})
    if isinstance(content, dict):
        # Merge content fields into root
        if "bullets" in content:
            flattened["bullets"] = content["bullets"]
        if "chart_data" in content:
            chart_data = content["chart_data"]
            # Ensure chart_data is a list of {label, value} objects
            if isinstance(chart_data, list):
                flattened["chart_data"] = chart_data
            elif isinstance(chart_data, dict) and "labels" in chart_data and "datasets" in chart_data:
                # Convert enrichment format to frontend format
                labels = chart_data.get("labels", [])
                datasets = chart_data.get("datasets", [])
                values = datasets[0].get("data", []) if datasets else []
                flattened["chart_data"] = [
                    {"label": lbl, "value": val}
                    for lbl, val in zip(labels, values)
                ]
            else:
                flattened["chart_data"] = chart_data
        if "chart_type" in content:
            flattened["chart_type"] = content["chart_type"]
        if "table_data" in content:
            table_data = content["table_data"]
            if isinstance(table_data, dict):
                headers = table_data.get("headers", [])
                raw_rows = table_data.get("rows", [])
                flattened["table_headers"] = headers
                # Convert array rows to dict rows keyed by header (frontend expects dicts)
                converted_rows = []
                for row in raw_rows:
                    if isinstance(row, list):
                        row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                        converted_rows.append(row_dict)
                    elif isinstance(row, dict):
                        converted_rows.append(row)
                flattened["table_rows"] = converted_rows
        if "comparison_data" in content:
            comparison_data = content["comparison_data"]
            if isinstance(comparison_data, dict):
                flattened["left_column"] = comparison_data.get("left_column")
                flattened["right_column"] = comparison_data.get("right_column")
        if "icon_name" in content:
            flattened["icon_name"] = content["icon_name"]
        if "highlight_text" in content:
            flattened["highlight_text"] = content["highlight_text"]
        if "transition" in content:
            flattened["transition"] = content["transition"]
        if "metric_value" in content:
            flattened["metric_value"] = content["metric_value"]
        if "metric_label" in content:
            flattened["metric_label"] = content["metric_label"]
        if "metric_trend" in content:
            flattened["metric_trend"] = content["metric_trend"]
        if "speaker_notes" in content:
            flattened["speaker_notes"] = content["speaker_notes"]
    elif isinstance(content, list):
        # content is directly a list of bullets
        flattened["bullets"] = content

    # Also check top-level bullets if not already set (Claude sometimes puts them at root)
    # bullets already at root level — keep as-is

    # Map backend field names to frontend expectations
    if "slide_id" in flattened:
        flattened["id"] = flattened.pop("slide_id")

    # Remove backend-only fields
    flattened.pop("layout_constraints", None)
    flattened.pop("metadata", None)
    flattened.pop("image", None)
    flattened.pop("section", None)  # Remove section field not needed by frontend
    
    return flattened


# ---------------------------------------------------------------------------
# 17.1  POST /api/v1/presentations
# ---------------------------------------------------------------------------


@router.post(
    "/presentations",
    response_model=CreatePresentationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_presentation(
    body: CreatePresentationRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> CreatePresentationResponse:
    """
    Accept a topic and immediately enqueue a generation job.

    Returns job_id and presentation_id — clients poll /status or connect to /stream.
    Only { topic } is accepted; all other decisions are made by the backend pipeline.
    """
    # Rate-limit check
    rl_info = await _get_rate_limit_info(current_user)
    _add_rate_limit_headers(response, rl_info)

    if rl_info["remaining"] == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again after the reset time.",
            headers={
                "X-RateLimit-Limit": str(rl_info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rl_info["reset"]),
                "Retry-After": str(rl_info["reset"] - int(time.time())),
            },
        )

    # Create presentation record (status=queued)
    presentation = Presentation(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        topic=body.topic,
        status=PresentationStatus.queued,
        schema_version="1.0.0",
    )
    db.add(presentation)
    await db.flush()  # get the generated presentation_id

    presentation_id = str(presentation.presentation_id)

    # Create pipeline execution record
    execution = PipelineExecution(
        presentation_id=presentation.presentation_id,
        status="queued",
    )
    db.add(execution)
    await db.flush()

    await db.commit()

    # Enqueue Celery task
    idempotency_key = f"gen:{presentation_id}"
    task_result = generate_presentation_task.apply_async(
        kwargs={
            "presentation_id": presentation_id,
            "topic": body.topic,
            "tenant_id": str(current_user.tenant_id),
            "idempotency_key": idempotency_key,
            "user_selected_theme": body.theme,
        },
        task_id=str(execution.id),
    )

    job_id = task_result.id

    # Increment rate-limit counter
    await _increment_rate_limit(current_user)

    return CreatePresentationResponse(
        job_id=job_id,
        presentation_id=presentation_id,
        status="queued",
        message="Presentation generation queued. Connect to /stream or poll /status for updates.",
    )


# ---------------------------------------------------------------------------
# 17.2  GET /api/v1/presentations/{id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/status",
    response_model=PresentationStatusResponse,
)
async def get_presentation_status(
    presentation_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PresentationStatusResponse:
    """
    Return generation progress, current agent, and auto-detected context.
    """
    rl_info = await _get_rate_limit_info(current_user)
    _add_rate_limit_headers(response, rl_info)

    # Fetch presentation (tenant-scoped)
    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    # Fetch latest pipeline execution
    exec_result = await db.execute(
        select(PipelineExecution)
        .where(PipelineExecution.presentation_id == presentation.presentation_id)
        .order_by(PipelineExecution.started_at.desc().nullslast())
        .limit(1)
    )
    execution = exec_result.scalar_one_or_none()

    exec_status = execution.status if execution else presentation.status.value
    current_agent = execution.current_agent if execution else None
    error_message = execution.error_message if execution else None

    progress = _compute_progress(exec_status, current_agent)

    # Build detected_context from presentation fields
    detected_context = None
    if presentation.detected_industry:
        detected_context = DetectedContextSchema(
            detected_industry=presentation.detected_industry,
            confidence_score=presentation.detection_confidence,
            sub_sector=presentation.detected_sub_sector,
            target_audience=presentation.inferred_audience,
            selected_template_id=(
                str(presentation.selected_template_id)
                if presentation.selected_template_id
                else None
            ),
            theme=presentation.selected_theme,
            compliance_context=presentation.compliance_context or [],
        )

    return PresentationStatusResponse(
        presentation_id=presentation_id,
        status=exec_status,
        progress=progress,
        current_agent=current_agent,
        detected_context=detected_context,
        quality_score=presentation.quality_score,
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# 17.3  GET /api/v1/presentations/{id}
# ---------------------------------------------------------------------------


@router.get("/presentations/{presentation_id}")
async def get_presentation(
    presentation_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return the complete Slide_JSON with metadata once generation is complete.
    """
    rl_info = await _get_rate_limit_info(current_user)
    _add_rate_limit_headers(response, rl_info)

    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    if presentation.status == PresentationStatus.queued:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Presentation is still queued for generation.",
        )
    if presentation.status == PresentationStatus.processing:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Presentation is still being generated.",
        )
    if presentation.status == PresentationStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Presentation generation failed.",
        )

    slides = presentation.slides or []
    if isinstance(slides, dict):
        slides = slides.get("slides", [])
    
    # Flatten slides for frontend consumption
    flattened_slides = [_flatten_slide_for_frontend(slide) for slide in slides]

    return {
        "schema_version": presentation.schema_version or "1.0.0",
        "presentation_id": presentation_id,
        "topic": presentation.topic,
        "total_slides": presentation.total_slides or len(slides),
        "status": presentation.status.value,
        "quality_score": presentation.quality_score,
        "slides": flattened_slides,
        "detected_context": {
            "detected_industry": presentation.detected_industry,
            "confidence_score": presentation.detection_confidence,
            "sub_sector": presentation.detected_sub_sector,
            "target_audience": presentation.inferred_audience,
            "selected_template_id": (
                str(presentation.selected_template_id)
                if presentation.selected_template_id
                else None
            ),
            "theme": presentation.selected_theme,
            "compliance_context": presentation.compliance_context or [],
        },
        "metadata": {
            "created_at": presentation.created_at.isoformat(),
            "updated_at": presentation.updated_at.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# 17.4  POST /api/v1/presentations/{id}/regenerate
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/regenerate",
    response_model=RegenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_presentation(
    presentation_id: str,
    response: Response,
    body: RegenerateRequest = RegenerateRequest(),
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> RegenerateResponse:
    """
    Re-run the full pipeline for an existing presentation.

    No provider field is accepted — the backend selects the provider from .env.
    """
    rl_info = await _get_rate_limit_info(current_user)
    _add_rate_limit_headers(response, rl_info)

    if rl_info["remaining"] == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
            headers={
                "X-RateLimit-Limit": str(rl_info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rl_info["reset"]),
            },
        )

    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    if presentation.status == PresentationStatus.processing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation is currently being generated.",
        )

    # Reset status to queued
    await db.execute(
        update(Presentation)
        .where(Presentation.presentation_id == presentation_id)
        .values(status=PresentationStatus.queued)
    )

    # New pipeline execution record
    execution = PipelineExecution(
        presentation_id=presentation.presentation_id,
        status="queued",
    )
    db.add(execution)
    await db.flush()
    await db.commit()

    # Enqueue with a fresh idempotency key (timestamp-based to allow re-runs)
    idempotency_key = f"regen:{presentation_id}:{int(time.time())}"
    task_result = generate_presentation_task.apply_async(
        kwargs={
            "presentation_id": presentation_id,
            "topic": presentation.topic,
            "tenant_id": str(current_user.tenant_id),
            "idempotency_key": idempotency_key,
        },
        task_id=str(execution.id),
    )

    await _increment_rate_limit(current_user)

    return RegenerateResponse(
        job_id=task_result.id,
        presentation_id=presentation_id,
        status="queued",
        message="Regeneration queued. Connect to /stream or poll /status for updates.",
    )


# ---------------------------------------------------------------------------
# 16.1  GET /api/v1/presentations/{id}/stream  (SSE)
# ---------------------------------------------------------------------------


@router.get("/presentations/{presentation_id}/stream")
async def stream_presentation(
    presentation_id: str,
    request: Request,
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    current_user: User = Depends(get_current_user_sse),  # Use SSE-specific auth
    db: AsyncSession = Depends(get_db),
):
    """
    Server-Sent Events stream for a presentation generation job.

    Events: agent_start, agent_complete, slide_ready, quality_score, complete, error.
    Reconnection: send Last-Event-ID header to replay missed events (5-min window).
    
    Note: Accepts token as query parameter since EventSource doesn't support custom headers.
    """
    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    async def event_generator():
        async for chunk in streaming_service.stream_events(
            presentation_id=presentation_id,
            last_event_id=last_event_id,
        ):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# POST /api/v1/presentations/{id}/export  — enqueue PPTX export
# GET  /api/v1/presentations/{id}/export/status — poll export job
# ---------------------------------------------------------------------------

class ExportResponse(BaseModel):
    job_id: str
    presentation_id: str
    status: str
    message: str


class ExportStatusResponse(BaseModel):
    job_id: str
    status: str
    download_url: Optional[str] = None
    message: str


@router.post(
    "/presentations/{presentation_id}/export",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def export_presentation(
    presentation_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """Enqueue a PPTX export job for a completed presentation."""
    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    if presentation.status != PresentationStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Presentation must be completed before exporting.",
        )

    from app.worker.tasks import export_pptx_task
    idempotency_key = f"export:{presentation_id}:{int(time.time())}"
    task = export_pptx_task.apply_async(
        kwargs={"presentation_id": presentation_id, "idempotency_key": idempotency_key}
    )

    return ExportResponse(
        job_id=task.id,
        presentation_id=presentation_id,
        status="queued",
        message="PPTX export queued. Poll /export/status for the download URL.",
    )


@router.get(
    "/presentations/{presentation_id}/export/status",
    response_model=ExportStatusResponse,
)
async def get_export_status(
    presentation_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportStatusResponse:
    """Poll the status of a PPTX export job."""
    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Presentation not found")

    from celery.result import AsyncResult
    task_result = AsyncResult(job_id)

    if task_result.state == "SUCCESS":
        result_data = task_result.result or {}
        return ExportStatusResponse(
            job_id=job_id,
            status="completed",
            download_url=result_data.get("download_url"),
            message="Export complete. Download URL is ready.",
        )
    elif task_result.state == "FAILURE":
        return ExportStatusResponse(
            job_id=job_id,
            status="failed",
            message=f"Export failed: {str(task_result.result)}",
        )
    else:
        return ExportStatusResponse(
            job_id=job_id,
            status=task_result.state.lower(),
            message="Export in progress...",
        )


# ---------------------------------------------------------------------------
# 16.5  DELETE /api/v1/jobs/{job_id}
# ---------------------------------------------------------------------------


@router.delete("/jobs/{job_id}", status_code=status.HTTP_202_ACCEPTED)
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a running presentation generation job.
    Partial results are preserved; cancellation is asynchronous.
    """
    exec_result = await db.execute(
        select(PipelineExecution).where(PipelineExecution.id == job_id)
    )
    execution = exec_result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Job not found")

    pres_result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == str(execution.presentation_id),
            Presentation.tenant_id == current_user.tenant_id,
        )
    )
    presentation = pres_result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=403, detail="Not authorised to cancel this job")

    if execution.status not in ("queued", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Job is already in terminal state: {execution.status}",
        )

    await streaming_service.set_cancellation_flag(job_id)
    await streaming_service.cancel_stream(str(execution.presentation_id), job_id)

    await db.execute(
        update(PipelineExecution)
        .where(PipelineExecution.id == job_id)
        .values(status="cancelled")
    )
    await db.execute(
        update(Presentation)
        .where(Presentation.presentation_id == str(execution.presentation_id))
        .values(status=PresentationStatus.cancelled)
    )
    await db.commit()

    return {
        "job_id": job_id,
        "presentation_id": str(execution.presentation_id),
        "status": "cancellation_requested",
        "message": "Cancellation requested. Any slides generated so far are preserved.",
    }
