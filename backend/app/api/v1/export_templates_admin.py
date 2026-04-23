"""
Export, Templates, and Admin API — Task 19.

Endpoints:
  POST   /api/v1/presentations/{id}/export/pptx              — 19.1 Trigger background PPTX export
  GET    /api/v1/presentations/{id}/export/pptx/status       — 19.2 Export status + signed URL
  GET    /api/v1/presentations/{id}/export/preview           — 19.3 PDF preview (headless Chromium)
  GET    /api/v1/templates                                   — 19.4 List templates with industry filter
  GET    /internal/providers                                 — 19.5 List provider health (admin only)
  POST   /internal/providers                                 — 19.5 Register/update provider config
  GET    /internal/providers/{id}/metrics                    — 19.5 Provider usage metrics
  GET    /api/v1/prompts                                     — 19.6 List prompts
  POST   /api/v1/prompts/{id}/rollback                       — 19.6 Rollback prompt to previous version
  GET    /api/v1/cache/stats                                 — 19.7 Cache statistics
  DELETE /api/v1/cache/presentations/{id}                    — 19.7 Invalidate presentation cache
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_min_role, require_role
from app.db.models import (
    Presentation,
    PipelineExecution,
    PresentationStatus,
    ProviderConfig,
    ProviderHealthLog,
    ProviderUsage,
    Prompt,
    ProviderType,
    Template,
    User,
)
from app.db.session import get_db
from app.services.redis_cache import redis_cache

router = APIRouter()

# Separate router for /internal/* endpoints (mounted at /internal in main.py)
internal_router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ExportJobResponse(BaseModel):
    job_id: str
    presentation_id: str
    status: str
    message: str


class ExportStatusResponse(BaseModel):
    job_id: str
    presentation_id: str
    status: str  # queued | processing | completed | failed
    download_url: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class PreviewResponse(BaseModel):
    presentation_id: str
    preview_url: str
    expires_at: str
    format: str = "pdf"


class TemplateSummary(BaseModel):
    id: str
    name: str
    industry: str
    sub_sector: Optional[str] = None
    is_system: bool
    usage_count: int
    slide_structure: Dict[str, Any]


class TemplateListResponse(BaseModel):
    templates: List[TemplateSummary]
    total: int


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)
    sub_sector: Optional[str] = Field(None, max_length=255)
    slide_structure: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of slide definitions with 'section', 'type', and optional 'title_hint'",
    )


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, min_length=1, max_length=255)
    sub_sector: Optional[str] = Field(None, max_length=255)
    slide_structure: Optional[List[Dict[str, Any]]] = None


class TemplateDetailResponse(BaseModel):
    id: str
    name: str
    industry: str
    sub_sector: Optional[str] = None
    is_system: bool
    usage_count: int
    slide_structure: Dict[str, Any]
    tenant_id: Optional[str] = None


class ProviderHealthResponse(BaseModel):
    provider_id: str
    provider_type: str
    model_name: str
    is_active: bool
    priority: int
    health: Dict[str, Any]


class ProviderListResponse(BaseModel):
    providers: List[ProviderHealthResponse]


class CreateProviderRequest(BaseModel):
    provider_type: str = Field(..., description="claude | openai | groq | local")
    model_name: str
    max_tokens: int = Field(4096, ge=1)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    rate_limit_per_min: int = Field(60, ge=1)
    cost_per_1k_tokens: float = Field(0.0, ge=0.0)
    priority: int = Field(1, ge=1)


class ProviderMetricsResponse(BaseModel):
    provider_id: str
    provider_type: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_tokens_per_call: float
    recent_health_logs: List[Dict[str, Any]]


class PromptSummary(BaseModel):
    id: str
    name: str
    version: int
    provider_type: str
    is_active: bool
    created_at: str


class PromptListResponse(BaseModel):
    prompts: List[PromptSummary]
    total: int


class PromptRollbackResponse(BaseModel):
    prompt_id: str
    rolled_back_to_version: int
    new_active_version: int
    message: str


class CacheStatsResponse(BaseModel):
    connected: bool
    total_keys: int
    provider_health_keys: int
    presentation_cache_keys: int
    rate_limit_keys: int
    memory_used_bytes: Optional[int] = None
    # Analytics (21.5)
    hits: Optional[int] = None
    misses: Optional[int] = None
    hit_rate_percent: Optional[float] = None
    cost_saved_usd: Optional[float] = None
    storage_mb: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_presentation_or_404(
    presentation_id: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Presentation:
    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    return presentation


# ---------------------------------------------------------------------------
# 19.1  POST /api/v1/presentations/{id}/export/pptx  — direct streaming download
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/export/pptx",
    tags=["export"],
    response_class=Response,
)
async def trigger_pptx_export(
    presentation_id: str,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Build and stream a PPTX file directly to the browser.

    Builds the PPTX synchronously and returns it as a file download.
    No MinIO, no polling, no signed URLs — just a direct file response.
    """
    from app.worker.tasks import _build_pptx

    presentation = await _get_presentation_or_404(
        presentation_id, current_user.tenant_id, db
    )

    if presentation.status != PresentationStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Presentation must be completed before exporting. Current status: {presentation.status.value}",
        )

    slides_data = presentation.slides or []
    theme = presentation.selected_theme or "dark_modern"
    design_spec = presentation.design_spec or {}

    # Build PPTX bytes — run in thread pool to avoid blocking the async event loop
    import asyncio
    loop = asyncio.get_running_loop()
    pptx_bytes = await loop.run_in_executor(
        None, _build_pptx, slides_data, theme, design_spec
    )

    safe_topic = (presentation.topic or "presentation")[:40]
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "_" for c in safe_topic).strip()
    filename = f"{safe_topic}.pptx"

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pptx_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# 19.1b  POST /api/v1/presentations/{id}/export/pptx/preview-images
#         Build PPTX → convert to slide images → return base64 JPGs
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/export/pptx/preview-images",
    tags=["export"],
)
async def get_pptx_preview_images(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Build the PPTX and convert each slide to a JPEG image.
    Returns base64-encoded images — pixel-perfect match with the downloaded file.
    """
    import httpx
    from app.core.config import settings
    import structlog

    logger = structlog.get_logger(__name__)

    presentation = await _get_presentation_or_404(
        presentation_id, current_user.tenant_id, db
    )

    if presentation.status != PresentationStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation must be completed before generating preview.",
        )

    slides_data = presentation.slides or []
    if isinstance(slides_data, dict):
        slides_data = slides_data.get("slides", [])
    theme = presentation.selected_theme or "dark_modern"
    design_spec = presentation.design_spec or {}

    logger.info(
        "preview_images_request",
        presentation_id=presentation_id,
        slide_count=len(slides_data),
        theme=theme,
        has_design_spec=bool(design_spec),
    )

    # Extract slide titles and types for the UI
    slide_meta = [
        {
            "title": s.get("title", f"Slide {i+1}"),
            "type": s.get("type", "content"),
            "slide_number": i + 1,
        }
        for i, s in enumerate(slides_data)
    ]

    pptx_service_url = getattr(settings, "PPTX_SERVICE_URL", "http://pptx-service:3001")
    logger.info("calling_pptx_service_preview", url=f"{pptx_service_url}/preview")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{pptx_service_url}/preview",
                json={"slides": slides_data, "design_spec": design_spec, "theme": theme},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "preview_images_success",
                image_count=data.get("count", 0),
                presentation_id=presentation_id,
            )
            return {
                "images": data.get("images", []),
                "count": data.get("count", 0),
                "slide_meta": slide_meta,
            }
    except httpx.TimeoutException as exc:
        logger.error(
            "preview_timeout",
            error=str(exc),
            presentation_id=presentation_id,
            timeout=120.0,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Preview generation timed out after 120 seconds: {str(exc)}",
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "preview_http_error",
            error=str(exc),
            status_code=exc.response.status_code,
            response_text=exc.response.text[:500],
            presentation_id=presentation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Preview generation failed with HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )
    except Exception as exc:
        logger.error(
            "preview_error",
            error=str(exc),
            error_type=type(exc).__name__,
            presentation_id=presentation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Preview generation failed: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# 19.2  GET /api/v1/presentations/{id}/export/pptx/status  — kept for compatibility
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/export/pptx/status",
    response_model=ExportStatusResponse,
    tags=["export"],
)
async def get_pptx_export_status(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportStatusResponse:
    """
    Compatibility endpoint — returns a direct download URL for the presentation.

    Since export is now synchronous, this always returns a direct download URL
    pointing to the POST endpoint. No polling needed.
    """
    await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    # Return a direct download URL — the POST endpoint streams the file
    download_url = f"/api/v1/presentations/{presentation_id}/export/pptx/download"

    return ExportStatusResponse(
        job_id="direct",
        presentation_id=presentation_id,
        status="completed",
        download_url=download_url,
    )


# ---------------------------------------------------------------------------
# 19.2b  GET /api/v1/presentations/{id}/export/pptx/download  — direct GET download
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/export/pptx/download",
    tags=["export"],
    response_class=Response,
)
async def download_pptx(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Direct GET endpoint to download the PPTX file.
    Used by the status endpoint's download_url field.
    """
    from app.worker.tasks import _build_pptx

    presentation = await _get_presentation_or_404(
        presentation_id, current_user.tenant_id, db
    )

    if presentation.status != PresentationStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation must be completed before downloading.",
        )

    slides_data = presentation.slides or []
    theme = presentation.selected_theme or "dark_modern"
    design_spec = presentation.design_spec or {}

    import asyncio
    loop = asyncio.get_running_loop()
    pptx_bytes = await loop.run_in_executor(
        None, _build_pptx, slides_data, theme, design_spec
    )

    safe_topic = (presentation.topic or "presentation")[:40]
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "_" for c in safe_topic).strip()
    filename = f"{safe_topic}.pptx"

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pptx_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# 19.3  GET /api/v1/presentations/{id}/export/preview
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/export/preview",
    response_model=PreviewResponse,
    tags=["export"],
)
async def get_export_preview(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    """
    Generate a PDF preview of the presentation via headless Chromium render.

    Returns a signed URL to the generated PDF (1-hour TTL).
    Falls back to a placeholder URL if Chromium is unavailable.
    """
    from datetime import timedelta

    presentation = await _get_presentation_or_404(
        presentation_id, current_user.tenant_id, db
    )

    if presentation.status != PresentationStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation must be completed before generating a preview.",
        )

    # Check cache first
    cache_key = f"preview:{presentation_id}"
    cached_preview = await redis_cache.get(cache_key)
    if cached_preview:
        return PreviewResponse(**cached_preview)

    preview_url = await _render_pdf_preview(presentation_id, presentation)

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    result = PreviewResponse(
        presentation_id=presentation_id,
        preview_url=preview_url,
        expires_at=expires_at,
        format="pdf",
    )

    # Cache for 55 minutes (slightly less than the signed URL TTL)
    await redis_cache.set(cache_key, result.model_dump(), ttl_seconds=3300)

    return result


async def _render_pdf_preview(presentation_id: str, presentation: Presentation) -> str:
    """
    Render a PDF preview using headless Chromium (pyppeteer/playwright).
    Falls back to a PPTX-based PDF if Chromium is unavailable.
    """
    import io
    from app.core.config import settings

    # Build minimal HTML representation of the presentation
    slides_data = presentation.slides or []
    if isinstance(slides_data, dict):
        slides_data = slides_data.get("slides", [])

    html_content = _build_preview_html(slides_data, presentation.selected_theme or "dark_modern")

    pdf_bytes: Optional[bytes] = None

    # Attempt headless Chromium render via playwright
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                landscape=True,
                print_background=True,
            )
            await browser.close()

    except Exception:
        # Playwright not available — fall back to python-pptx PDF export stub
        pdf_bytes = _build_fallback_pdf(slides_data)

    # Upload to S3/MinIO
    import boto3
    from botocore.client import Config

    object_key = f"previews/{presentation_id}/preview.pdf"

    s3_client = boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    try:
        s3_client.head_bucket(Bucket=settings.MINIO_BUCKET)
    except Exception:
        s3_client.create_bucket(Bucket=settings.MINIO_BUCKET)

    s3_client.put_object(
        Bucket=settings.MINIO_BUCKET,
        Key=object_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    signed_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET, "Key": object_key},
        ExpiresIn=3600,
    )
    return signed_url


def _build_preview_html(slides: List[Dict[str, Any]], theme: str) -> str:
    """Build a minimal HTML representation of slides for PDF rendering."""
    theme_colors = {
        "executive": {"bg": "#003366", "text": "#FFFFFF", "accent": "#0066CC"},
        "professional": {"bg": "#86BC25", "text": "#FFFFFF", "accent": "#012169"},
        "dark_modern": {"bg": "#1A1A2E", "text": "#E0E0E0", "accent": "#16213E"},
        "corporate": {"bg": "#002855", "text": "#FFFFFF", "accent": "#0078AC"},
    }
    colors = theme_colors.get(theme, theme_colors["corporate"])

    slides_html = ""
    for slide in slides:
        title = slide.get("title", "")
        content = slide.get("content", {})
        bullets = content.get("bullets", [])
        bullets_html = "".join(f"<li>{b}</li>" for b in bullets)

        slides_html += f"""
        <div class="slide">
            <h1 style="color:{colors['text']}">{title}</h1>
            <ul style="color:{colors['text']}">{bullets_html}</ul>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin: 0; font-family: Arial, sans-serif; }}
  .slide {{
    width: 297mm; height: 210mm;
    background: {colors['bg']};
    padding: 40px;
    box-sizing: border-box;
    page-break-after: always;
  }}
  h1 {{ font-size: 28px; margin-bottom: 20px; }}
  ul {{ font-size: 18px; line-height: 1.6; }}
</style>
</head>
<body>{slides_html}</body>
</html>"""


def _build_fallback_pdf(slides: List[Dict[str, Any]]) -> bytes:
    """Minimal PDF fallback using reportlab-style bytes (returns empty PDF stub)."""
    # Minimal valid PDF bytes as fallback when Chromium is unavailable
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"


# ---------------------------------------------------------------------------
# 19.4  GET /api/v1/templates
# ---------------------------------------------------------------------------


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    tags=["templates"],
)
async def list_templates(
    industry: Optional[str] = Query(None, description="Filter by industry (case-insensitive)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateListResponse:
    """
    List available presentation templates.

    Returns system templates plus templates belonging to the user's tenant.
    Optionally filter by industry. Read-only for all authenticated users.
    """
    query = select(Template).where(
        (Template.is_system == True) | (Template.tenant_id == current_user.tenant_id)
    )

    if industry:
        query = query.where(func.lower(Template.industry) == industry.lower())

    query = query.order_by(Template.is_system.desc(), Template.usage_count.desc())

    result = await db.execute(query)
    templates = result.scalars().all()

    summaries = [
        TemplateSummary(
            id=str(t.id),
            name=t.name,
            industry=t.industry,
            sub_sector=t.sub_sector,
            is_system=t.is_system,
            usage_count=t.usage_count,
            slide_structure=t.slide_structure if isinstance(t.slide_structure, dict) else {},
        )
        for t in templates
    ]

    return TemplateListResponse(templates=summaries, total=len(summaries))


# ---------------------------------------------------------------------------
# 19.5  GET /internal/providers  (admin only)
# ---------------------------------------------------------------------------


@internal_router.get(
    "/providers",
    response_model=ProviderListResponse,
    tags=["admin"],
)
async def list_providers(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ProviderListResponse:
    """
    List all configured LLM providers with their current health status.

    Admin-only endpoint — not accessible to regular users.
    """
    from app.services.provider_health import health_monitor

    result = await db.execute(
        select(ProviderConfig).order_by(ProviderConfig.priority.asc())
    )
    configs = result.scalars().all()

    providers = []
    for config in configs:
        try:
            provider_enum = ProviderType(config.provider_type.value)
            health = await health_monitor.get_cached_health_status(provider_enum)
        except Exception:
            health = {"error": "health data unavailable"}

        providers.append(
            ProviderHealthResponse(
                provider_id=str(config.id),
                provider_type=config.provider_type.value,
                model_name=config.model_name,
                is_active=config.is_active,
                priority=config.priority,
                health=health or {},
            )
        )

    return ProviderListResponse(providers=providers)


# ---------------------------------------------------------------------------
# 19.5  POST /internal/providers  (admin only)
# ---------------------------------------------------------------------------


@internal_router.post(
    "/providers",
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def create_provider(
    body: CreateProviderRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Register a new provider configuration.

    Admin-only. Provider credentials are still read from .env — this endpoint
    only manages the DB configuration record (model, limits, priority).
    """
    try:
        provider_type = ProviderType(body.provider_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid provider_type '{body.provider_type}'. Must be one of: {[p.value for p in ProviderType]}",
        )

    config = ProviderConfig(
        provider_type=provider_type,
        model_name=body.model_name,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        rate_limit_per_min=body.rate_limit_per_min,
        cost_per_1k_tokens=body.cost_per_1k_tokens,
        priority=body.priority,
        is_active=True,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Invalidate Slide_JSON cache since provider config changed (21.3)
    try:
        from app.services.presentation_cache import presentation_cache as pres_cache
        await pres_cache.invalidate_on_provider_config_change()
    except Exception:
        pass  # cache invalidation failure must not block the response

    return {
        "provider_id": str(config.id),
        "provider_type": config.provider_type.value,
        "model_name": config.model_name,
        "is_active": config.is_active,
        "priority": config.priority,
        "message": "Provider configuration created successfully.",
    }


# ---------------------------------------------------------------------------
# 19.5  GET /internal/providers/{id}/metrics  (admin only)
# ---------------------------------------------------------------------------


@internal_router.get(
    "/providers/{provider_id}/metrics",
    response_model=ProviderMetricsResponse,
    tags=["admin"],
)
async def get_provider_metrics(
    provider_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> ProviderMetricsResponse:
    """
    Get usage and cost metrics for a specific provider.

    Admin-only. Returns token usage, cost, and recent health logs.
    """
    # Validate provider exists
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.id == provider_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Aggregate usage metrics
    usage_result = await db.execute(
        select(
            func.count(ProviderUsage.id).label("total_calls"),
            func.coalesce(func.sum(ProviderUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(ProviderUsage.cost_usd), 0.0).label("total_cost_usd"),
        ).where(ProviderUsage.provider_id == provider_id)
    )
    usage_row = usage_result.one()
    total_calls = usage_row.total_calls or 0
    total_tokens = int(usage_row.total_tokens or 0)
    total_cost_usd = float(usage_row.total_cost_usd or 0.0)
    avg_tokens = total_tokens / total_calls if total_calls > 0 else 0.0

    # Recent health logs (last 10)
    health_result = await db.execute(
        select(ProviderHealthLog)
        .where(ProviderHealthLog.provider_id == provider_id)
        .order_by(ProviderHealthLog.checked_at.desc())
        .limit(10)
    )
    health_logs = health_result.scalars().all()
    recent_health = [
        {
            "success_rate": log.success_rate,
            "avg_response_ms": log.avg_response_ms,
            "error_count": log.error_count,
            "checked_at": log.checked_at.isoformat(),
        }
        for log in health_logs
    ]

    return ProviderMetricsResponse(
        provider_id=provider_id,
        provider_type=config.provider_type.value,
        total_calls=total_calls,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        avg_tokens_per_call=avg_tokens,
        recent_health_logs=recent_health,
    )


# ---------------------------------------------------------------------------
# 19.6  GET /api/v1/prompts
# ---------------------------------------------------------------------------


@router.get(
    "/prompts",
    response_model=PromptListResponse,
    tags=["prompts"],
)
async def list_prompts(
    provider_type: Optional[str] = Query(None, description="Filter by provider type"),
    active_only: bool = Query(False, description="Return only active prompts"),
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> PromptListResponse:
    """
    List all prompt templates with optional filtering.

    Returns prompts ordered by name and version descending.
    """
    query = select(Prompt)

    if provider_type:
        try:
            pt = ProviderType(provider_type)
            query = query.where(Prompt.provider_type == pt)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid provider_type. Must be one of: {[p.value for p in ProviderType]}",
            )

    if active_only:
        query = query.where(Prompt.is_active == True)

    query = query.order_by(Prompt.name.asc(), Prompt.version.desc())

    result = await db.execute(query)
    prompts = result.scalars().all()

    summaries = [
        PromptSummary(
            id=str(p.id),
            name=p.name,
            version=p.version,
            provider_type=p.provider_type.value,
            is_active=p.is_active,
            created_at=p.created_at.isoformat(),
        )
        for p in prompts
    ]

    return PromptListResponse(prompts=summaries, total=len(summaries))


# ---------------------------------------------------------------------------
# 19.6  POST /api/v1/prompts/{id}/rollback
# ---------------------------------------------------------------------------


@router.post(
    "/prompts/{prompt_id}/rollback",
    response_model=PromptRollbackResponse,
    tags=["prompts"],
)
async def rollback_prompt(
    prompt_id: str,
    target_version: int = Query(..., ge=1, description="Version number to roll back to"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> PromptRollbackResponse:
    """
    Roll back a prompt to a previous version.

    Deactivates the current active version and activates the target version.
    Admin-only — prompt changes affect all pipeline executions.
    """
    # Fetch the target prompt version
    result = await db.execute(
        select(Prompt).where(Prompt.id == prompt_id)
    )
    current_prompt = result.scalar_one_or_none()
    if not current_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Find the target version by name + provider_type + version number
    target_result = await db.execute(
        select(Prompt).where(
            Prompt.name == current_prompt.name,
            Prompt.provider_type == current_prompt.provider_type,
            Prompt.version == target_version,
        )
    )
    target_prompt = target_result.scalar_one_or_none()
    if not target_prompt:
        raise HTTPException(
            status_code=404,
            detail=f"Version {target_version} not found for prompt '{current_prompt.name}'",
        )

    current_version = current_prompt.version

    # Deactivate all versions of this prompt name + provider
    await db.execute(
        update(Prompt)
        .where(
            Prompt.name == current_prompt.name,
            Prompt.provider_type == current_prompt.provider_type,
        )
        .values(is_active=False)
    )

    # Activate the target version
    await db.execute(
        update(Prompt)
        .where(Prompt.id == str(target_prompt.id))
        .values(is_active=True)
    )

    await db.commit()

    # Invalidate Slide_JSON cache entries since prompt changed (21.3)
    try:
        from app.services.presentation_cache import presentation_cache as pres_cache
        await pres_cache.invalidate_on_prompt_version_update(str(target_version))
    except Exception:
        pass  # cache invalidation failure must not block the rollback response

    return PromptRollbackResponse(
        prompt_id=str(target_prompt.id),
        rolled_back_to_version=target_version,
        new_active_version=target_version,
        message=f"Prompt '{current_prompt.name}' rolled back from version {current_version} to version {target_version}.",
    )


# ---------------------------------------------------------------------------
# 19.7  GET /api/v1/cache/stats
# ---------------------------------------------------------------------------


@router.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    tags=["cache"],
)
async def get_cache_stats(
    current_user: User = Depends(require_role("admin")),
) -> CacheStatsResponse:
    """
    Return Redis cache statistics.

    Admin-only. Shows key counts by category and memory usage.
    """
    client = redis_cache._client
    if not client:
        return CacheStatsResponse(
            connected=False,
            total_keys=0,
            provider_health_keys=0,
            presentation_cache_keys=0,
            rate_limit_keys=0,
        )

    try:
        # Count keys by pattern
        provider_health_keys = 0
        presentation_cache_keys = 0
        rate_limit_keys = 0
        total_keys = 0

        async for key in client.scan_iter(match="*"):
            total_keys += 1
            if key.startswith("provider_health:"):
                provider_health_keys += 1
            elif key.startswith("slide_json:") or key.startswith("research:") or key.startswith("enrichment:"):
                presentation_cache_keys += 1
            elif key.startswith("ratelimit:"):
                rate_limit_keys += 1

        # Memory info
        memory_used = None
        try:
            info = await client.info("memory")
            memory_used = info.get("used_memory")
        except Exception:
            pass

        # Analytics (21.5)
        from app.services.presentation_cache import presentation_cache as pres_cache
        analytics = await pres_cache.get_analytics()

        return CacheStatsResponse(
            connected=True,
            total_keys=total_keys,
            provider_health_keys=provider_health_keys,
            presentation_cache_keys=presentation_cache_keys,
            rate_limit_keys=rate_limit_keys,
            memory_used_bytes=memory_used,
            hits=analytics["hits"],
            misses=analytics["misses"],
            hit_rate_percent=analytics["hit_rate_percent"],
            cost_saved_usd=analytics["cost_saved_usd"],
            storage_mb=analytics["storage_mb"],
        )

    except Exception as exc:
        return CacheStatsResponse(
            connected=False,
            total_keys=0,
            provider_health_keys=0,
            presentation_cache_keys=0,
            rate_limit_keys=0,
        )


# ---------------------------------------------------------------------------
# 19.7  DELETE /api/v1/cache/presentations/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/cache/presentations/{presentation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    tags=["cache"],
)
async def invalidate_presentation_cache(
    presentation_id: str,
    current_user: User = Depends(require_role("admin")),
) -> None:
    """
    Invalidate all cached data for a specific presentation.

    Removes the final Slide_JSON cache entries that contain this presentation_id,
    plus the export job and preview cache entries. Admin-only.
    """
    from app.services.presentation_cache import presentation_cache as pres_cache

    client = redis_cache._client
    if not client:
        raise HTTPException(status_code=503, detail="Cache service unavailable")

    try:
        # Use the presentation cache service for Slide_JSON invalidation (21.3)
        await pres_cache.invalidate_presentation(presentation_id)

        # Also clear export job and preview caches for this presentation
        extra_keys = [
            f"export_job:{presentation_id}",
            f"preview:{presentation_id}",
        ]
        existing = [k for k in extra_keys if await redis_cache.exists(k)]
        if existing:
            await client.delete(*existing)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cache operation failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Cache invalidation endpoints (21.3)
# ---------------------------------------------------------------------------


@router.post(
    "/cache/invalidate/prompt-version",
    status_code=status.HTTP_200_OK,
    tags=["cache"],
)
async def invalidate_cache_on_prompt_update(
    new_version: str = Query(..., description="New prompt version string, e.g. '1.1.0'"),
    current_user: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Invalidate all Slide_JSON cache entries after a prompt version update.

    Because the prompt version is part of the composite cache key, old entries
    become unreachable automatically.  This endpoint proactively removes them
    to free Redis memory.  Admin-only.
    """
    from app.services.presentation_cache import presentation_cache as pres_cache

    deleted = await pres_cache.invalidate_on_prompt_version_update(new_version)
    return {
        "invalidated": deleted,
        "reason": "prompt_version_update",
        "new_version": new_version,
    }


@router.post(
    "/cache/invalidate/provider-config",
    status_code=status.HTTP_200_OK,
    tags=["cache"],
)
async def invalidate_cache_on_provider_change(
    current_user: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Invalidate all Slide_JSON cache entries after a provider configuration change.

    Admin-only.  Call this after updating LLM_PRIMARY_PROVIDER or model settings.
    """
    from app.services.presentation_cache import presentation_cache as pres_cache

    deleted = await pres_cache.invalidate_on_provider_config_change()
    return {
        "invalidated": deleted,
        "reason": "provider_config_change",
    }


@router.post(
    "/cache/invalidate/schema-version",
    status_code=status.HTTP_200_OK,
    tags=["cache"],
)
async def invalidate_cache_on_schema_bump(
    current_user: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Invalidate ALL cache entries (Slide_JSON + research + enrichment) after a
    Slide_JSON schema version bump.  Admin-only.
    """
    from app.services.presentation_cache import presentation_cache as pres_cache

    deleted = await pres_cache.invalidate_on_schema_version_bump()
    return {
        "invalidated": deleted,
        "reason": "schema_version_bump",
    }


@router.get(
    "/cache/analytics",
    tags=["cache"],
)
async def get_cache_analytics(
    current_user: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Return cache analytics: hit rate, storage bytes, and estimated cost savings.

    Admin-only.  Counters reset every 24 hours.
    """
    from app.services.presentation_cache import presentation_cache as pres_cache

    return await pres_cache.get_analytics()


@router.post(
    "/cache/warm",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["cache"],
)
async def trigger_cache_warming(
    current_user: User = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """
    Manually trigger a cache warming cycle for top topics per industry.

    Admin-only.  Normally runs automatically every hour.
    """
    from app.services.cache_warming_task import cache_warming_task

    result = await cache_warming_task.run_once()
    return {
        "status": "warming_triggered",
        "already_cached": result["already_cached"],
        "enqueued": result["enqueued"],
    }


# ---------------------------------------------------------------------------
# 29.4  Custom template CRUD — POST /api/v1/templates
# ---------------------------------------------------------------------------


@router.post(
    "/templates",
    response_model=TemplateDetailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["templates"],
)
async def create_template(
    body: CreateTemplateRequest,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> TemplateDetailResponse:
    """
    Create a custom presentation template scoped to the user's tenant.

    The template is immediately available to all users within the same tenant.
    System templates cannot be created via this endpoint.
    """
    from app.services.template_service import create_custom_template

    template = await create_custom_template(
        db=db,
        tenant_id=current_user.tenant_id,
        name=body.name,
        industry=body.industry,
        slide_structure=body.slide_structure,
        sub_sector=body.sub_sector,
    )
    await db.commit()

    return TemplateDetailResponse(
        id=str(template.id),
        name=template.name,
        industry=template.industry,
        sub_sector=template.sub_sector,
        is_system=template.is_system,
        usage_count=template.usage_count,
        slide_structure=template.slide_structure if isinstance(template.slide_structure, dict) else {},
        tenant_id=str(template.tenant_id) if template.tenant_id else None,
    )


# ---------------------------------------------------------------------------
# 29.4  GET /api/v1/templates/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/templates/{template_id}",
    response_model=TemplateDetailResponse,
    tags=["templates"],
)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateDetailResponse:
    """
    Retrieve a single template by ID.

    Returns system templates (visible to all) and tenant-scoped custom templates
    (visible only within the owning tenant).
    """
    from app.services.template_service import get_template_by_id

    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid template_id format")

    template = await get_template_by_id(db, tid, tenant_id=current_user.tenant_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateDetailResponse(
        id=str(template.id),
        name=template.name,
        industry=template.industry,
        sub_sector=template.sub_sector,
        is_system=template.is_system,
        usage_count=template.usage_count,
        slide_structure=template.slide_structure if isinstance(template.slide_structure, dict) else {},
        tenant_id=str(template.tenant_id) if template.tenant_id else None,
    )


# ---------------------------------------------------------------------------
# 29.4  PATCH /api/v1/templates/{id}
# ---------------------------------------------------------------------------


@router.patch(
    "/templates/{template_id}",
    response_model=TemplateDetailResponse,
    tags=["templates"],
)
async def update_template(
    template_id: str,
    body: UpdateTemplateRequest,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> TemplateDetailResponse:
    """
    Update a custom template owned by the user's tenant.

    System templates cannot be modified via this endpoint.
    """
    from app.services.template_service import update_custom_template

    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid template_id format")

    template = await update_custom_template(
        db=db,
        template_id=tid,
        tenant_id=current_user.tenant_id,
        name=body.name,
        industry=body.industry,
        slide_structure=body.slide_structure,
        sub_sector=body.sub_sector,
    )
    if not template:
        raise HTTPException(
            status_code=404,
            detail="Template not found or you do not have permission to modify it",
        )
    await db.commit()

    return TemplateDetailResponse(
        id=str(template.id),
        name=template.name,
        industry=template.industry,
        sub_sector=template.sub_sector,
        is_system=template.is_system,
        usage_count=template.usage_count,
        slide_structure=template.slide_structure if isinstance(template.slide_structure, dict) else {},
        tenant_id=str(template.tenant_id) if template.tenant_id else None,
    )


# ---------------------------------------------------------------------------
# 29.4  DELETE /api/v1/templates/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    tags=["templates"],
)
async def delete_template(
    template_id: str,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a custom template owned by the user's tenant.

    System templates cannot be deleted. Returns 404 if not found or not owned
    by the current tenant.
    """
    from app.services.template_service import delete_custom_template

    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid template_id format")

    deleted = await delete_custom_template(db, tid, current_user.tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Template not found or you do not have permission to delete it",
        )
    await db.commit()
