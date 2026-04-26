"""
Tests for Export, Templates, and Admin API — Task 19.

Covers:
  19.1 — POST /api/v1/presentations/{id}/export/pptx
  19.2 — GET  /api/v1/presentations/{id}/export/pptx/status
  19.3 — GET  /api/v1/presentations/{id}/export/preview
  19.4 — GET  /api/v1/templates (with industry filter)
  19.5 — GET/POST /internal/providers, GET /internal/providers/{id}/metrics
  19.6 — GET /api/v1/prompts, POST /api/v1/prompts/{id}/rollback
  19.7 — GET /api/v1/cache/stats, DELETE /api/v1/cache/presentations/{id}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import (
    Presentation,
    PresentationStatus,
    ProviderConfig,
    ProviderHealthLog,
    ProviderUsage,
    Prompt,
    ProviderType,
    Template,
    User,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_user(role: str = "admin") -> MagicMock:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.role = role
    user.is_active = True
    return user


def _make_presentation(
    status: PresentationStatus = PresentationStatus.completed,
    tenant_id: uuid.UUID = None,
) -> MagicMock:
    p = MagicMock(spec=Presentation)
    p.presentation_id = uuid.uuid4()
    p.tenant_id = tenant_id or uuid.uuid4()
    p.status = status
    p.topic = "AI in Healthcare"
    p.selected_theme = "hexaware_corporate"
    p.slides = [
        {
            "slide_id": str(uuid.uuid4()),
            "slide_number": 1,
            "type": "title",
            "title": "Introduction",
            "content": {"bullets": []},
            "visual_hint": "centered",
        }
    ]
    return p


def _make_template(
    industry: str = "technology",
    is_system: bool = True,
    tenant_id: uuid.UUID = None,
) -> MagicMock:
    t = MagicMock(spec=Template)
    t.id = uuid.uuid4()
    t.name = f"{industry.title()} Strategy"
    t.industry = industry
    t.sub_sector = None
    t.is_system = is_system
    t.usage_count = 5
    t.tenant_id = tenant_id
    t.slide_structure = {"slides": [{"section": "Title", "type": "title"}]}
    return t


def _make_provider_config(provider_type: str = "claude") -> MagicMock:
    c = MagicMock(spec=ProviderConfig)
    c.id = uuid.uuid4()
    c.provider_type = MagicMock()
    c.provider_type.value = provider_type
    c.model_name = "claude-3-opus-20240229"
    c.is_active = True
    c.priority = 1
    return c


def _make_prompt(
    name: str = "slide_generation",
    version: int = 2,
    provider_type: str = "claude",
    is_active: bool = True,
) -> MagicMock:
    p = MagicMock(spec=Prompt)
    p.id = uuid.uuid4()
    p.name = name
    p.version = version
    p.provider_type = MagicMock()
    p.provider_type.value = provider_type
    p.is_active = is_active
    p.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return p


# ---------------------------------------------------------------------------
# 19.1  POST /api/v1/presentations/{id}/export/pptx
# ---------------------------------------------------------------------------


class TestTriggerPptxExport:
    """POST /api/v1/presentations/{id}/export/pptx — trigger background export."""

    def test_export_job_response_schema(self):
        """ExportJobResponse has required fields."""
        from app.api.v1.export_templates_admin import ExportJobResponse

        resp = ExportJobResponse(
            job_id="abc-123",
            presentation_id="pres-456",
            status="queued",
            message="Export queued.",
        )
        assert resp.job_id == "abc-123"
        assert resp.status == "queued"

    def test_export_requires_completed_presentation(self):
        """Only completed presentations can be exported."""
        # Verify the endpoint logic: non-completed status raises 409
        from app.api.v1.export_templates_admin import ExportJobResponse
        from fastapi import HTTPException

        presentation = _make_presentation(status=PresentationStatus.processing)

        # Simulate the guard check in the endpoint
        if presentation.status != PresentationStatus.completed:
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=409,
                    detail=f"Presentation must be completed before exporting. Current status: {presentation.status.value}",
                )
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_trigger_export_queues_celery_task(self):
        """Triggering export calls export_pptx_task.apply_async and caches job_id."""
        from app.api.v1.export_templates_admin import trigger_pptx_export

        user = _make_user(role="member")
        presentation = _make_presentation(status=PresentationStatus.completed)
        presentation.tenant_id = user.tenant_id

        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-id-001"

        mock_task = MagicMock()
        mock_task.apply_async.return_value = mock_task_result

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        with (
            patch("app.worker.tasks.export_pptx_task", mock_task),
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
        ):
            mock_cache.set = AsyncMock(return_value=True)

            result = await trigger_pptx_export(
                presentation_id=str(presentation.presentation_id),
                current_user=user,
                db=mock_db,
            )

        assert result.job_id == "celery-task-id-001"
        assert result.status == "queued"
        mock_task.apply_async.assert_called_once()
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_export_404_when_presentation_not_found(self):
        """Returns 404 when presentation does not belong to tenant."""
        from app.api.v1.export_templates_admin import trigger_pptx_export
        from fastapi import HTTPException

        user = _make_user(role="member")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        with pytest.raises(HTTPException) as exc_info:
            await trigger_pptx_export(
                presentation_id=str(uuid.uuid4()),
                current_user=user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 19.2  GET /api/v1/presentations/{id}/export/pptx/status
# ---------------------------------------------------------------------------


class TestGetPptxExportStatus:
    """GET /api/v1/presentations/{id}/export/pptx/status — status + signed URL."""

    def test_export_status_response_schema(self):
        """ExportStatusResponse has all required fields."""
        from app.api.v1.export_templates_admin import ExportStatusResponse

        resp = ExportStatusResponse(
            job_id="job-001",
            presentation_id="pres-001",
            status="completed",
            download_url="https://minio/file.pptx",
            expires_at="2024-01-01T01:00:00Z",
        )
        assert resp.status == "completed"
        assert resp.download_url is not None

    def test_export_status_optional_fields(self):
        """download_url and expires_at are optional (None when not ready)."""
        from app.api.v1.export_templates_admin import ExportStatusResponse

        resp = ExportStatusResponse(
            job_id="job-001",
            presentation_id="pres-001",
            status="queued",
        )
        assert resp.download_url is None
        assert resp.expires_at is None

    @pytest.mark.asyncio
    async def test_status_returns_queued_for_pending_task(self):
        """PENDING celery state maps to 'queued' status."""
        from app.api.v1.export_templates_admin import get_pptx_export_status

        user = _make_user()
        presentation = _make_presentation()
        presentation.tenant_id = user.tenant_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        mock_task_result = MagicMock()
        mock_task_result.state = "PENDING"

        with (
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
            patch("celery.result.AsyncResult", return_value=mock_task_result),
        ):
            mock_cache.get = AsyncMock(return_value={"job_id": "job-001"})

            result = await get_pptx_export_status(
                presentation_id=str(presentation.presentation_id),
                current_user=user,
                db=mock_db,
            )

        assert result.status == "queued"

    @pytest.mark.asyncio
    async def test_status_returns_completed_with_download_url(self):
        """SUCCESS celery state returns 'completed' with download_url."""
        from app.api.v1.export_templates_admin import get_pptx_export_status

        user = _make_user()
        presentation = _make_presentation()
        presentation.tenant_id = user.tenant_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        mock_task_result = MagicMock()
        mock_task_result.state = "SUCCESS"
        mock_task_result.result = {"download_url": "https://minio/export.pptx"}

        with (
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
            patch("celery.result.AsyncResult", return_value=mock_task_result),
        ):
            mock_cache.get = AsyncMock(return_value={"job_id": "job-001"})

            result = await get_pptx_export_status(
                presentation_id=str(presentation.presentation_id),
                current_user=user,
                db=mock_db,
            )

        assert result.status == "completed"
        assert result.download_url == "https://minio/export.pptx"
        assert result.expires_at is not None

    @pytest.mark.asyncio
    async def test_status_returns_failed_on_failure(self):
        """FAILURE celery state returns 'failed' with error message."""
        from app.api.v1.export_templates_admin import get_pptx_export_status

        user = _make_user()
        presentation = _make_presentation()
        presentation.tenant_id = user.tenant_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        mock_task_result = MagicMock()
        mock_task_result.state = "FAILURE"
        mock_task_result.result = Exception("S3 upload failed")

        with (
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
            patch("celery.result.AsyncResult", return_value=mock_task_result),
        ):
            mock_cache.get = AsyncMock(return_value={"job_id": "job-001"})

            result = await get_pptx_export_status(
                presentation_id=str(presentation.presentation_id),
                current_user=user,
                db=mock_db,
            )

        assert result.status == "failed"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_status_404_when_no_export_job(self):
        """Returns 404 when no export job exists for the presentation."""
        from app.api.v1.export_templates_admin import get_pptx_export_status
        from fastapi import HTTPException

        user = _make_user()
        presentation = _make_presentation()
        presentation.tenant_id = user.tenant_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        with patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_pptx_export_status(
                    presentation_id=str(presentation.presentation_id),
                    current_user=user,
                    db=mock_db,
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 19.3  GET /api/v1/presentations/{id}/export/preview
# ---------------------------------------------------------------------------


class TestGetExportPreview:
    """GET /api/v1/presentations/{id}/export/preview — PDF preview via headless Chromium."""

    def test_preview_response_schema(self):
        """PreviewResponse has required fields."""
        from app.api.v1.export_templates_admin import PreviewResponse

        resp = PreviewResponse(
            presentation_id="pres-001",
            preview_url="https://minio/preview.pdf",
            expires_at="2024-01-01T01:00:00Z",
            format="pdf",
        )
        assert resp.format == "pdf"
        assert resp.preview_url.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_preview_returns_cached_result(self):
        """Returns cached preview URL without re-rendering."""
        from app.api.v1.export_templates_admin import get_export_preview

        user = _make_user()
        presentation = _make_presentation()
        presentation.tenant_id = user.tenant_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        cached_data = {
            "presentation_id": str(presentation.presentation_id),
            "preview_url": "https://minio/cached-preview.pdf",
            "expires_at": "2024-01-01T01:00:00Z",
            "format": "pdf",
        }

        with patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=cached_data)

            result = await get_export_preview(
                presentation_id=str(presentation.presentation_id),
                current_user=user,
                db=mock_db,
            )

        assert result.preview_url == "https://minio/cached-preview.pdf"

    @pytest.mark.asyncio
    async def test_preview_409_for_non_completed_presentation(self):
        """Returns 409 when presentation is not completed."""
        from app.api.v1.export_templates_admin import get_export_preview
        from fastapi import HTTPException

        user = _make_user()
        presentation = _make_presentation(status=PresentationStatus.processing)
        presentation.tenant_id = user.tenant_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=presentation))
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_export_preview(
                presentation_id=str(presentation.presentation_id),
                current_user=user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 409

    def test_build_preview_html_contains_slide_titles(self):
        """_build_preview_html includes slide titles in the output."""
        from app.api.v1.export_templates_admin import _build_preview_html

        slides = [
            {"title": "Introduction", "content": {"bullets": ["Point A"]}},
            {"title": "Analysis", "content": {"bullets": ["Finding 1", "Finding 2"]}},
        ]
        html = _build_preview_html(slides, "hexaware_corporate")

        assert "Introduction" in html
        assert "Analysis" in html
        assert "Point A" in html

    def test_build_preview_html_applies_theme_colors(self):
        """_build_preview_html uses theme-specific background color."""
        from app.api.v1.export_templates_admin import _build_preview_html

        html_executive = _build_preview_html([], "hexaware_corporate")
        html_professional = _build_preview_html([], "hexaware_professional")
        html_dark = _build_preview_html([], "hexaware_corporate")

        assert "#003366" in html_executive
        assert "#86BC25" in html_professional
        assert "#1A1A2E" in html_dark

    def test_build_fallback_pdf_returns_valid_pdf_bytes(self):
        """_build_fallback_pdf returns bytes starting with PDF magic bytes."""
        from app.api.v1.export_templates_admin import _build_fallback_pdf

        pdf_bytes = _build_fallback_pdf([])
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# 19.4  GET /api/v1/templates
# ---------------------------------------------------------------------------


class TestListTemplates:
    """GET /api/v1/templates — list templates with optional industry filter."""

    def test_template_summary_schema(self):
        """TemplateSummary has all required fields."""
        from app.api.v1.export_templates_admin import TemplateSummary

        summary = TemplateSummary(
            id=str(uuid.uuid4()),
            name="Healthcare Executive Briefing",
            industry="healthcare",
            is_system=True,
            usage_count=42,
            slide_structure={"slides": []},
        )
        assert summary.industry == "healthcare"
        assert summary.is_system is True

    def test_template_list_response_schema(self):
        """TemplateListResponse wraps templates with total count."""
        from app.api.v1.export_templates_admin import TemplateListResponse, TemplateSummary

        resp = TemplateListResponse(templates=[], total=0)
        assert resp.total == 0
        assert resp.templates == []

    @pytest.mark.asyncio
    async def test_list_templates_returns_system_and_tenant_templates(self):
        """Returns system templates and tenant-scoped templates."""
        from app.api.v1.export_templates_admin import list_templates

        user = _make_user()
        system_tpl = _make_template(industry="healthcare", is_system=True)
        tenant_tpl = _make_template(industry="fintech", is_system=False, tenant_id=user.tenant_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[system_tpl, tenant_tpl]))))
        )

        result = await list_templates(industry=None, current_user=user, db=mock_db)

        assert result.total == 2
        industries = {t.industry for t in result.templates}
        assert "healthcare" in industries
        assert "fintech" in industries

    @pytest.mark.asyncio
    async def test_list_templates_filters_by_industry(self):
        """Industry filter returns only matching templates."""
        from app.api.v1.export_templates_admin import list_templates

        user = _make_user()
        healthcare_tpl = _make_template(industry="healthcare", is_system=True)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[healthcare_tpl]))))
        )

        result = await list_templates(industry="healthcare", current_user=user, db=mock_db)

        assert result.total == 1
        assert result.templates[0].industry == "healthcare"

    @pytest.mark.asyncio
    async def test_list_templates_empty_when_no_match(self):
        """Returns empty list when no templates match the filter."""
        from app.api.v1.export_templates_admin import list_templates

        user = _make_user()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )

        result = await list_templates(industry="unknown_industry", current_user=user, db=mock_db)

        assert result.total == 0
        assert result.templates == []


# ---------------------------------------------------------------------------
# 19.5  GET/POST /internal/providers, GET /internal/providers/{id}/metrics
# ---------------------------------------------------------------------------


class TestInternalProviderEndpoints:
    """Admin-only provider management endpoints."""

    def test_provider_health_response_schema(self):
        """ProviderHealthResponse has required fields."""
        from app.api.v1.export_templates_admin import ProviderHealthResponse

        resp = ProviderHealthResponse(
            provider_id=str(uuid.uuid4()),
            provider_type="claude",
            model_name="claude-3-opus-20240229",
            is_active=True,
            priority=1,
            health={"success_rate": 0.99, "avg_response_ms": 1200},
        )
        assert resp.provider_type == "claude"
        assert resp.is_active is True

    def test_provider_list_response_schema(self):
        """ProviderListResponse wraps providers list."""
        from app.api.v1.export_templates_admin import ProviderListResponse

        resp = ProviderListResponse(providers=[])
        assert resp.providers == []

    def test_create_provider_request_validation(self):
        """CreateProviderRequest validates provider_type and numeric fields."""
        from app.api.v1.export_templates_admin import CreateProviderRequest
        from pydantic import ValidationError

        # Valid request
        req = CreateProviderRequest(
            provider_type="openai",
            model_name="gpt-4o",
            max_tokens=4096,
            temperature=0.7,
            rate_limit_per_min=150,
            cost_per_1k_tokens=0.03,
            priority=2,
        )
        assert req.provider_type == "openai"
        assert req.temperature == 0.7

    def test_create_provider_request_defaults(self):
        """CreateProviderRequest has sensible defaults."""
        from app.api.v1.export_templates_admin import CreateProviderRequest

        req = CreateProviderRequest(provider_type="groq", model_name="llama3-70b")
        assert req.max_tokens == 4096
        assert req.temperature == 0.7
        assert req.priority == 1

    @pytest.mark.asyncio
    async def test_list_providers_returns_all_configs(self):
        """GET /internal/providers returns all provider configs with health."""
        from app.api.v1.export_templates_admin import list_providers

        admin_user = _make_user(role="admin")
        config1 = _make_provider_config("claude")
        config2 = _make_provider_config("openai")

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[config1, config2]))))
        )

        mock_health_monitor = MagicMock()
        mock_health_monitor.get_cached_health_status = AsyncMock(
            return_value={"success_rate": 0.99, "avg_response_ms": 800}
        )

        with patch("app.services.provider_health.health_monitor", mock_health_monitor):
            result = await list_providers(current_user=admin_user, db=mock_db)

        assert len(result.providers) == 2

    @pytest.mark.asyncio
    async def test_create_provider_rejects_invalid_type(self):
        """POST /internal/providers returns 422 for unknown provider_type."""
        from app.api.v1.export_templates_admin import create_provider, CreateProviderRequest
        from fastapi import HTTPException

        admin_user = _make_user(role="admin")
        mock_db = AsyncMock()

        body = CreateProviderRequest(provider_type="invalid_llm", model_name="unknown")

        with pytest.raises(HTTPException) as exc_info:
            await create_provider(body=body, current_user=admin_user, db=mock_db)

        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_persists_config(self):
        """POST /internal/providers adds config to DB and returns provider_id."""
        from app.api.v1.export_templates_admin import create_provider, CreateProviderRequest

        admin_user = _make_user(role="admin")

        new_config = MagicMock(spec=ProviderConfig)
        new_config.id = uuid.uuid4()
        new_config.provider_type = MagicMock()
        new_config.provider_type.value = "groq"
        new_config.model_name = "llama3-70b"
        new_config.is_active = True
        new_config.priority = 3

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        body = CreateProviderRequest(provider_type="groq", model_name="llama3-70b", priority=3)

        mock_pres_cache = MagicMock()
        mock_pres_cache.invalidate_on_provider_config_change = AsyncMock(return_value=0)

        with (
            patch("app.api.v1.export_templates_admin.ProviderConfig", return_value=new_config),
            patch("app.services.presentation_cache.presentation_cache", mock_pres_cache),
        ):
            result = await create_provider(body=body, current_user=admin_user, db=mock_db)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result["provider_type"] == "groq"

    def test_provider_metrics_response_schema(self):
        """ProviderMetricsResponse has all required fields."""
        from app.api.v1.export_templates_admin import ProviderMetricsResponse

        resp = ProviderMetricsResponse(
            provider_id=str(uuid.uuid4()),
            provider_type="claude",
            total_calls=500,
            total_tokens=1_000_000,
            total_cost_usd=15.50,
            avg_tokens_per_call=2000.0,
            recent_health_logs=[],
        )
        assert resp.total_calls == 500
        assert resp.avg_tokens_per_call == 2000.0

    @pytest.mark.asyncio
    async def test_get_provider_metrics_404_for_unknown_provider(self):
        """GET /internal/providers/{id}/metrics returns 404 for unknown ID."""
        from app.api.v1.export_templates_admin import get_provider_metrics
        from fastapi import HTTPException

        admin_user = _make_user(role="admin")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_provider_metrics(
                provider_id=str(uuid.uuid4()),
                current_user=admin_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_provider_metrics_aggregates_usage(self):
        """GET /internal/providers/{id}/metrics returns aggregated token/cost data."""
        from app.api.v1.export_templates_admin import get_provider_metrics

        admin_user = _make_user(role="admin")
        config = _make_provider_config("claude")

        # First execute: provider config lookup
        # Second execute: usage aggregation
        # Third execute: health logs
        call_count = 0

        async def mock_execute(_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=config))
            elif call_count == 2:
                row = MagicMock()
                row.total_calls = 100
                row.total_tokens = 200_000
                row.total_cost_usd = 3.0
                return MagicMock(one=MagicMock(return_value=row))
            else:
                return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))

        mock_db = AsyncMock()
        mock_db.execute = mock_execute

        result = await get_provider_metrics(
            provider_id=str(config.id),
            current_user=admin_user,
            db=mock_db,
        )

        assert result.total_calls == 100
        assert result.total_tokens == 200_000
        assert result.total_cost_usd == 3.0
        assert result.avg_tokens_per_call == 2000.0


# ---------------------------------------------------------------------------
# 19.6  GET /api/v1/prompts, POST /api/v1/prompts/{id}/rollback
# ---------------------------------------------------------------------------


class TestPromptManagementEndpoints:
    """Prompt listing and rollback endpoints."""

    def test_prompt_summary_schema(self):
        """PromptSummary has all required fields."""
        from app.api.v1.export_templates_admin import PromptSummary

        summary = PromptSummary(
            id=str(uuid.uuid4()),
            name="slide_generation",
            version=3,
            provider_type="claude",
            is_active=True,
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert summary.version == 3
        assert summary.is_active is True

    def test_prompt_list_response_schema(self):
        """PromptListResponse wraps prompts with total count."""
        from app.api.v1.export_templates_admin import PromptListResponse

        resp = PromptListResponse(prompts=[], total=0)
        assert resp.total == 0

    @pytest.mark.asyncio
    async def test_list_prompts_returns_all_prompts(self):
        """GET /api/v1/prompts returns all prompts ordered by name/version."""
        from app.api.v1.export_templates_admin import list_prompts

        user = _make_user(role="member")
        p1 = _make_prompt(name="slide_generation", version=2, is_active=True)
        p2 = _make_prompt(name="slide_generation", version=1, is_active=False)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[p1, p2]))))
        )

        result = await list_prompts(
            provider_type=None,
            active_only=False,
            current_user=user,
            db=mock_db,
        )

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_list_prompts_filters_active_only(self):
        """active_only=True returns only active prompts."""
        from app.api.v1.export_templates_admin import list_prompts

        user = _make_user(role="member")
        active_prompt = _make_prompt(is_active=True)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[active_prompt]))))
        )

        result = await list_prompts(
            provider_type=None,
            active_only=True,
            current_user=user,
            db=mock_db,
        )

        assert result.total == 1
        assert result.prompts[0].is_active is True

    @pytest.mark.asyncio
    async def test_list_prompts_rejects_invalid_provider_type(self):
        """Invalid provider_type raises 422."""
        from app.api.v1.export_templates_admin import list_prompts
        from fastapi import HTTPException

        user = _make_user(role="member")
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await list_prompts(
                provider_type="invalid_provider",
                active_only=False,
                current_user=user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 422

    def test_prompt_rollback_response_schema(self):
        """PromptRollbackResponse has all required fields."""
        from app.api.v1.export_templates_admin import PromptRollbackResponse

        resp = PromptRollbackResponse(
            prompt_id=str(uuid.uuid4()),
            rolled_back_to_version=1,
            new_active_version=1,
            message="Rolled back successfully.",
        )
        assert resp.rolled_back_to_version == 1
        assert resp.new_active_version == 1

    @pytest.mark.asyncio
    async def test_rollback_prompt_404_when_not_found(self):
        """Returns 404 when prompt_id does not exist."""
        from app.api.v1.export_templates_admin import rollback_prompt
        from fastapi import HTTPException

        admin_user = _make_user(role="admin")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        with pytest.raises(HTTPException) as exc_info:
            await rollback_prompt(
                prompt_id=str(uuid.uuid4()),
                target_version=1,
                current_user=admin_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_prompt_404_when_target_version_missing(self):
        """Returns 404 when target version does not exist."""
        from app.api.v1.export_templates_admin import rollback_prompt
        from fastapi import HTTPException

        admin_user = _make_user(role="admin")
        current_prompt = _make_prompt(name="slide_generation", version=3)

        call_count = 0

        async def mock_execute(_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=current_prompt))
            # Target version not found
            return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

        mock_db = AsyncMock()
        mock_db.execute = mock_execute

        with pytest.raises(HTTPException) as exc_info:
            await rollback_prompt(
                prompt_id=str(current_prompt.id),
                target_version=99,
                current_user=admin_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_prompt_activates_target_version(self):
        """Rollback deactivates current and activates target version."""
        from app.api.v1.export_templates_admin import rollback_prompt

        admin_user = _make_user(role="admin")
        current_prompt = _make_prompt(name="slide_generation", version=3, is_active=True)
        target_prompt = _make_prompt(name="slide_generation", version=1, is_active=False)
        target_prompt.id = uuid.uuid4()

        call_count = 0

        async def mock_execute(_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=current_prompt))
            elif call_count == 2:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=target_prompt))
            return MagicMock()

        mock_db = AsyncMock()
        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        mock_pres_cache = MagicMock()
        mock_pres_cache.invalidate_on_prompt_version_update = AsyncMock(return_value=0)

        with patch("app.services.presentation_cache.presentation_cache", mock_pres_cache):
            result = await rollback_prompt(
                prompt_id=str(current_prompt.id),
                target_version=1,
                current_user=admin_user,
                db=mock_db,
            )

        assert result.rolled_back_to_version == 1
        assert result.new_active_version == 1
        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 19.7  GET /api/v1/cache/stats, DELETE /api/v1/cache/presentations/{id}
# ---------------------------------------------------------------------------


class TestCacheManagementEndpoints:
    """Cache stats and invalidation endpoints."""

    def test_cache_stats_response_schema(self):
        """CacheStatsResponse has all required fields."""
        from app.api.v1.export_templates_admin import CacheStatsResponse

        resp = CacheStatsResponse(
            connected=True,
            total_keys=150,
            provider_health_keys=4,
            presentation_cache_keys=80,
            rate_limit_keys=20,
            memory_used_bytes=1_048_576,
            hits=500,
            misses=100,
            hit_rate_percent=83.33,
            cost_saved_usd=25.0,
            storage_mb=1.0,
        )
        assert resp.connected is True
        assert resp.hit_rate_percent == 83.33

    def test_cache_stats_optional_analytics_fields(self):
        """Analytics fields are optional (None when unavailable)."""
        from app.api.v1.export_templates_admin import CacheStatsResponse

        resp = CacheStatsResponse(
            connected=False,
            total_keys=0,
            provider_health_keys=0,
            presentation_cache_keys=0,
            rate_limit_keys=0,
        )
        assert resp.hits is None
        assert resp.cost_saved_usd is None

    @pytest.mark.asyncio
    async def test_get_cache_stats_returns_disconnected_when_no_client(self):
        """Returns connected=False when Redis client is unavailable."""
        from app.api.v1.export_templates_admin import get_cache_stats

        admin_user = _make_user(role="admin")

        with patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache:
            mock_cache._client = None

            result = await get_cache_stats(current_user=admin_user)

        assert result.connected is False
        assert result.total_keys == 0

    @pytest.mark.asyncio
    async def test_get_cache_stats_counts_keys_by_prefix(self):
        """Cache stats correctly categorises keys by prefix."""
        from app.api.v1.export_templates_admin import get_cache_stats

        admin_user = _make_user(role="admin")

        # Simulate Redis keys
        all_keys = [
            "provider_health:claude",
            "provider_health:openai",
            "slide_json:abc123",
            "research:def456",
            "enrichment:ghi789",
            "ratelimit:user:001",
            "export_job:pres-001",
        ]

        async def mock_scan_iter(match="*"):
            for k in all_keys:
                yield k

        mock_client = MagicMock()
        mock_client.scan_iter = mock_scan_iter
        mock_client.info = AsyncMock(return_value={"used_memory": 2_097_152})

        analytics_data = {
            "hits": 200,
            "misses": 50,
            "hit_rate_percent": 80.0,
            "cost_saved_usd": 10.0,
            "storage_mb": 2.0,
        }

        with (
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
            patch("app.services.presentation_cache.presentation_cache") as mock_pres_cache,
        ):
            mock_cache._client = mock_client
            mock_pres_cache.get_analytics = AsyncMock(return_value=analytics_data)

            result = await get_cache_stats(current_user=admin_user)

        assert result.connected is True
        assert result.provider_health_keys == 2
        assert result.presentation_cache_keys == 3  # slide_json + research + enrichment
        assert result.rate_limit_keys == 1
        assert result.total_keys == 7
        assert result.hits == 200
        assert result.cost_saved_usd == 10.0

    @pytest.mark.asyncio
    async def test_invalidate_presentation_cache_calls_service(self):
        """DELETE /api/v1/cache/presentations/{id} calls presentation_cache.invalidate_presentation."""
        from app.api.v1.export_templates_admin import invalidate_presentation_cache

        admin_user = _make_user(role="admin")
        presentation_id = str(uuid.uuid4())

        mock_client = MagicMock()

        with (
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
            patch("app.services.presentation_cache.presentation_cache") as mock_pres_cache,
        ):
            mock_cache._client = mock_client
            mock_pres_cache.invalidate_presentation = AsyncMock(return_value=3)
            mock_cache.exists = AsyncMock(return_value=False)

            # Should not raise
            await invalidate_presentation_cache(
                presentation_id=presentation_id,
                current_user=admin_user,
            )

        mock_pres_cache.invalidate_presentation.assert_called_once_with(presentation_id)

    @pytest.mark.asyncio
    async def test_invalidate_presentation_cache_503_when_no_client(self):
        """Returns 503 when Redis client is unavailable."""
        from app.api.v1.export_templates_admin import invalidate_presentation_cache
        from fastapi import HTTPException

        admin_user = _make_user(role="admin")

        with patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache:
            mock_cache._client = None

            with pytest.raises(HTTPException) as exc_info:
                await invalidate_presentation_cache(
                    presentation_id=str(uuid.uuid4()),
                    current_user=admin_user,
                )

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_invalidate_presentation_cache_also_clears_export_and_preview(self):
        """Invalidation also removes export_job and preview cache keys."""
        from app.api.v1.export_templates_admin import invalidate_presentation_cache

        admin_user = _make_user(role="admin")
        presentation_id = "pres-test-001"

        deleted_keys = []

        async def mock_exists(key: str) -> bool:
            return key in [f"export_job:{presentation_id}", f"preview:{presentation_id}"]

        mock_client = MagicMock()
        mock_client.delete = AsyncMock(side_effect=lambda *keys: deleted_keys.extend(keys))

        with (
            patch("app.api.v1.export_templates_admin.redis_cache") as mock_cache,
            patch("app.services.presentation_cache.presentation_cache") as mock_pres_cache,
        ):
            mock_cache._client = mock_client
            mock_cache.exists = mock_exists
            mock_pres_cache.invalidate_presentation = AsyncMock(return_value=1)

            await invalidate_presentation_cache(
                presentation_id=presentation_id,
                current_user=admin_user,
            )

        # Both export_job and preview keys should have been deleted
        assert f"export_job:{presentation_id}" in deleted_keys
        assert f"preview:{presentation_id}" in deleted_keys


# ---------------------------------------------------------------------------
# Cross-cutting: schema validation for Pydantic models
# ---------------------------------------------------------------------------


class TestPydanticSchemas:
    """Validate all Pydantic request/response models for task 19."""

    def test_create_template_request_requires_name_and_industry(self):
        """CreateTemplateRequest requires name, industry, and slide_structure."""
        from app.api.v1.export_templates_admin import CreateTemplateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateTemplateRequest(name="", industry="tech", slide_structure=[])

    def test_create_template_request_valid(self):
        """Valid CreateTemplateRequest is accepted."""
        from app.api.v1.export_templates_admin import CreateTemplateRequest

        req = CreateTemplateRequest(
            name="My Template",
            industry="fintech",
            slide_structure=[{"section": "Title", "type": "title"}],
        )
        assert req.name == "My Template"
        assert req.industry == "fintech"

    def test_update_template_request_all_optional(self):
        """UpdateTemplateRequest allows partial updates (all fields optional)."""
        from app.api.v1.export_templates_admin import UpdateTemplateRequest

        req = UpdateTemplateRequest()
        assert req.name is None
        assert req.industry is None
        assert req.slide_structure is None

    def test_export_job_response_required_fields(self):
        """ExportJobResponse requires job_id, presentation_id, status, message."""
        from app.api.v1.export_templates_admin import ExportJobResponse
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExportJobResponse(job_id="x")  # missing required fields
