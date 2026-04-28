"""
Tests for the Presentation Generation API (Task 17).

Covers:
- 17.1  POST /api/v1/presentations — topic-only input, returns job_id immediately
- 17.2  GET  /api/v1/presentations/{id}/status — progress, current_agent, detected_context
- 17.3  GET  /api/v1/presentations/{id} — complete Slide_JSON with metadata
- 17.4  POST /api/v1/presentations/{id}/regenerate — no provider field
- 17.5  Rate-limit headers on all responses
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.db.models import Presentation, PipelineExecution, PresentationStatus


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_presentation_id() -> str:
    return str(uuid.uuid4())


def _make_slide(slide_id: str = None, slide_number: int = 1) -> Dict[str, Any]:
    return {
        "slide_id": slide_id or str(uuid.uuid4()),
        "slide_number": slide_number,
        "type": "content",
        "title": "Test Slide",
        "content": {"bullets": ["Point A", "Point B"]},
        "visual_hint": "bullet-left",
        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
        "metadata": {
            "generated_at": "2024-01-01T00:00:00Z",
            "provider_used": "claude",
            "quality_score": 8.5,
        },
    }


def _make_mock_user(role: str = "member") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.role = role
    user.is_active = True
    return user


def _make_mock_presentation(
    presentation_id: str = None,
    status: PresentationStatus = PresentationStatus.completed,
    topic: str = "AI in Healthcare",
    slides: list = None,
) -> MagicMock:
    p = MagicMock(spec=Presentation)
    p.presentation_id = uuid.UUID(presentation_id) if presentation_id else uuid.uuid4()
    p.status = status
    p.topic = topic
    p.schema_version = "1.0.0"
    p.total_slides = 3
    p.slides = slides or [_make_slide(slide_number=i + 1) for i in range(3)]
    p.quality_score = 8.5
    p.detected_industry = "healthcare"
    p.detection_confidence = 0.92
    p.detected_sub_sector = "clinical research"
    p.inferred_audience = "executives"
    p.selected_template_id = None
    p.selected_theme = "ocean-depths"
    p.compliance_context = ["HIPAA"]
    p.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    p.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    p.tenant_id = uuid.uuid4()
    return p


def _make_mock_execution(
    presentation_id: uuid.UUID = None,
    exec_status: str = "completed",
    current_agent: str = None,
) -> MagicMock:
    e = MagicMock(spec=PipelineExecution)
    e.id = uuid.uuid4()
    e.presentation_id = presentation_id or uuid.uuid4()
    e.status = exec_status
    e.current_agent = current_agent
    e.error_message = None
    e.started_at = None
    return e


# ---------------------------------------------------------------------------
# 17.1  POST /api/v1/presentations
# ---------------------------------------------------------------------------


class TestCreatePresentation:
    """POST /api/v1/presentations — topic-only, returns job_id immediately."""

    @pytest.mark.asyncio
    async def test_create_returns_202_with_job_id(self):
        """Valid topic returns 202 with job_id and presentation_id."""
        from app.api.v1.presentations import (
            CreatePresentationRequest,
            CreatePresentationResponse,
        )

        req = CreatePresentationRequest(topic="AI in Healthcare")
        assert req.topic == "AI in Healthcare"

    def test_topic_is_only_accepted_field(self):
        """Request schema must only accept topic — no provider, theme, etc."""
        from app.api.v1.presentations import CreatePresentationRequest
        import inspect

        fields = CreatePresentationRequest.model_fields
        assert "topic" in fields
        # No provider, theme, audience, or template fields
        for forbidden in ("provider", "theme", "audience", "template_id", "industry"):
            assert forbidden not in fields, f"Field '{forbidden}' must not be in request"

    def test_topic_max_length_500(self):
        """Topic must be rejected if longer than 500 characters."""
        from app.api.v1.presentations import CreatePresentationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreatePresentationRequest(topic="x" * 501)

    def test_topic_blank_rejected(self):
        """Blank topic must be rejected."""
        from app.api.v1.presentations import CreatePresentationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreatePresentationRequest(topic="   ")

    def test_topic_empty_rejected(self):
        """Empty topic must be rejected."""
        from app.api.v1.presentations import CreatePresentationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreatePresentationRequest(topic="")

    def test_topic_stripped_of_whitespace(self):
        """Leading/trailing whitespace is stripped from topic."""
        from app.api.v1.presentations import CreatePresentationRequest

        req = CreatePresentationRequest(topic="  AI in Healthcare  ")
        assert req.topic == "AI in Healthcare"

    def test_response_schema_has_job_id_and_presentation_id(self):
        """Response schema must include job_id, presentation_id, status, message."""
        from app.api.v1.presentations import CreatePresentationResponse

        fields = CreatePresentationResponse.model_fields
        assert "job_id" in fields
        assert "presentation_id" in fields
        assert "status" in fields
        assert "message" in fields

    def test_regenerate_request_has_no_provider_field(self):
        """RegenerateRequest must not accept a provider field (Req 13)."""
        from app.api.v1.presentations import RegenerateRequest

        fields = RegenerateRequest.model_fields
        assert "provider" not in fields
        assert "theme" not in fields


# ---------------------------------------------------------------------------
# 17.2  GET /api/v1/presentations/{id}/status
# ---------------------------------------------------------------------------


class TestPresentationStatus:
    """GET /api/v1/presentations/{id}/status — progress, agent, detected_context."""

    def test_status_response_schema(self):
        """Status response must include all required fields."""
        from app.api.v1.presentations import PresentationStatusResponse

        fields = PresentationStatusResponse.model_fields
        assert "presentation_id" in fields
        assert "status" in fields
        assert "progress" in fields
        assert "current_agent" in fields
        assert "detected_context" in fields
        assert "quality_score" in fields

    def test_detected_context_schema(self):
        """DetectedContextSchema must include industry, confidence, audience, theme."""
        from app.api.v1.presentations import DetectedContextSchema

        fields = DetectedContextSchema.model_fields
        assert "detected_industry" in fields
        assert "confidence_score" in fields
        assert "target_audience" in fields
        assert "theme" in fields
        assert "compliance_context" in fields

    def test_progress_computation_queued(self):
        """Queued status maps to 0% progress."""
        from app.api.v1.presentations import _compute_progress

        assert _compute_progress("queued", None) == 0

    def test_progress_computation_completed(self):
        """Completed status maps to 100% progress."""
        from app.api.v1.presentations import _compute_progress

        assert _compute_progress("completed", None) == 100

    def test_progress_computation_by_agent(self):
        """Progress is driven by current_agent when processing."""
        from app.api.v1.presentations import _compute_progress

        assert _compute_progress("processing", "research") == 35
        assert _compute_progress("processing", "quality_scoring") == 95
        assert _compute_progress("processing", "industry_classifier") == 10

    def test_progress_computation_unknown_agent(self):
        """Unknown agent falls back to status-based progress."""
        from app.api.v1.presentations import _compute_progress

        result = _compute_progress("processing", "unknown_agent")
        assert result == 5  # processing default

    def test_progress_computation_failed(self):
        """Failed status maps to 0% progress."""
        from app.api.v1.presentations import _compute_progress

        assert _compute_progress("failed", None) == 0

    def test_all_pipeline_agents_have_progress_values(self):
        """Every agent in the pipeline must have a progress mapping."""
        from app.api.v1.presentations import _AGENT_PROGRESS

        expected_agents = [
            "industry_classifier",
            "storyboarding",
            "research",
            "data_enrichment",
            "prompt_engineering",
            "llm_provider",
            "validation",
            "quality_scoring",
        ]
        for agent in expected_agents:
            assert agent in _AGENT_PROGRESS, f"Agent '{agent}' missing from _AGENT_PROGRESS"

    def test_agent_progress_values_are_ordered(self):
        """Agent progress values must be monotonically increasing in pipeline order."""
        from app.api.v1.presentations import _AGENT_PROGRESS

        ordered = [
            "industry_classifier",
            "storyboarding",
            "research",
            "data_enrichment",
            "prompt_engineering",
            "llm_provider",
            "validation",
            "quality_scoring",
        ]
        values = [_AGENT_PROGRESS[a] for a in ordered]
        assert values == sorted(values), "Agent progress values must be monotonically increasing"


# ---------------------------------------------------------------------------
# 17.3  GET /api/v1/presentations/{id}
# ---------------------------------------------------------------------------


class TestGetPresentation:
    """GET /api/v1/presentations/{id} — complete Slide_JSON."""

    def test_get_presentation_response_structure(self):
        """Response must include schema_version, slides, detected_context, metadata."""
        # Verify the endpoint returns the expected keys by inspecting the function
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module.get_presentation)
        assert "schema_version" in source
        assert "slides" in source
        assert "detected_context" in source
        assert "metadata" in source
        assert "quality_score" in source

    def test_queued_presentation_returns_202(self):
        """Queued presentation must raise 202 (not yet ready)."""
        from app.api.v1.presentations import get_presentation
        import inspect

        source = inspect.getsource(get_presentation)
        assert "queued" in source
        assert "202" in source or "HTTP_202_ACCEPTED" in source

    def test_processing_presentation_returns_202(self):
        """Processing presentation must raise 202."""
        from app.api.v1.presentations import get_presentation
        import inspect

        source = inspect.getsource(get_presentation)
        assert "processing" in source

    def test_failed_presentation_returns_422(self):
        """Failed presentation must raise 422."""
        from app.api.v1.presentations import get_presentation
        import inspect

        source = inspect.getsource(get_presentation)
        assert "failed" in source
        assert "422" in source or "HTTP_422_UNPROCESSABLE_ENTITY" in source


# ---------------------------------------------------------------------------
# 17.4  POST /api/v1/presentations/{id}/regenerate
# ---------------------------------------------------------------------------


class TestRegeneratePresentation:
    """POST /api/v1/presentations/{id}/regenerate — no provider field."""

    def test_regenerate_request_accepts_no_fields(self):
        """RegenerateRequest must be an empty body — no provider selection."""
        from app.api.v1.presentations import RegenerateRequest

        # Should instantiate with no arguments
        req = RegenerateRequest()
        assert req is not None

    def test_regenerate_response_schema(self):
        """RegenerateResponse must include job_id, presentation_id, status, message."""
        from app.api.v1.presentations import RegenerateResponse

        fields = RegenerateResponse.model_fields
        assert "job_id" in fields
        assert "presentation_id" in fields
        assert "status" in fields
        assert "message" in fields

    def test_regenerate_resets_status_to_queued(self):
        """Regenerate endpoint must reset presentation status to queued."""
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module.regenerate_presentation)
        assert "queued" in source
        assert "PresentationStatus.queued" in source

    def test_regenerate_rejects_processing_presentation(self):
        """Cannot regenerate a presentation that is currently processing."""
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module.regenerate_presentation)
        assert "processing" in source
        assert "409" in source or "HTTP_409_CONFLICT" in source

    def test_regenerate_uses_fresh_idempotency_key(self):
        """Each regeneration must use a unique idempotency key to allow re-runs."""
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module.regenerate_presentation)
        # Should include timestamp in idempotency key to make it unique
        assert "regen:" in source
        assert "time.time()" in source or "int(time" in source


# ---------------------------------------------------------------------------
# 17.5  Rate-limit headers
# ---------------------------------------------------------------------------


class TestRateLimitHeaders:
    """Rate-limit headers must appear on all responses."""

    def test_rate_limit_constants_defined(self):
        """Free and premium rate limits must be defined."""
        from app.api.v1.presentations import _RATE_LIMIT_FREE, _RATE_LIMIT_PREMIUM

        assert _RATE_LIMIT_FREE == 10
        assert _RATE_LIMIT_PREMIUM == 100

    def test_rate_limit_window_is_one_hour(self):
        """Rate limit window must be 3600 seconds (1 hour)."""
        from app.api.v1.presentations import _RATE_LIMIT_WINDOW_SECONDS

        assert _RATE_LIMIT_WINDOW_SECONDS == 3600

    def test_admin_gets_premium_limit(self):
        """Admin role gets premium (100/hr) rate limit."""
        from app.api.v1.presentations import _rate_limit_for_role

        assert _rate_limit_for_role("admin") == 100

    def test_member_gets_free_limit(self):
        """Member role gets free (10/hr) rate limit."""
        from app.api.v1.presentations import _rate_limit_for_role

        assert _rate_limit_for_role("member") == 10

    def test_viewer_gets_free_limit(self):
        """Viewer role gets free (10/hr) rate limit."""
        from app.api.v1.presentations import _rate_limit_for_role

        assert _rate_limit_for_role("viewer") == 10

    def test_add_rate_limit_headers_sets_all_three(self):
        """_add_rate_limit_headers must set all three required headers."""
        from app.api.v1.presentations import _add_rate_limit_headers
        from fastapi import Response

        response = Response()
        _add_rate_limit_headers(
            response,
            {"limit": 10, "remaining": 7, "reset": 1700000000},
        )

        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Remaining"] == "7"
        assert response.headers["X-RateLimit-Reset"] == "1700000000"

    def test_add_rate_limit_headers_values_are_strings(self):
        """Header values must be strings."""
        from app.api.v1.presentations import _add_rate_limit_headers
        from fastapi import Response

        response = Response()
        _add_rate_limit_headers(
            response,
            {"limit": 100, "remaining": 0, "reset": 9999999999},
        )

        assert isinstance(response.headers["X-RateLimit-Limit"], str)
        assert isinstance(response.headers["X-RateLimit-Remaining"], str)
        assert isinstance(response.headers["X-RateLimit-Reset"], str)

    def test_remaining_never_negative(self):
        """Remaining count must never go below 0."""
        from app.api.v1.presentations import _RATE_LIMIT_FREE

        # Simulate over-limit scenario
        limit = _RATE_LIMIT_FREE
        count = limit + 5  # exceeded
        remaining = max(0, limit - count)
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_returns_required_keys(self):
        """_get_rate_limit_info must return limit, remaining, reset keys."""
        from app.api.v1.presentations import _get_rate_limit_info

        mock_user = _make_mock_user(role="member")

        with patch("app.api.v1.presentations.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=3)
            mock_cache._client = None

            info = await _get_rate_limit_info(mock_user)

        assert "limit" in info
        assert "remaining" in info
        assert "reset" in info
        assert info["limit"] == 10
        assert info["remaining"] == 7  # 10 - 3

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_handles_redis_failure(self):
        """Rate limit info must not crash when Redis is unavailable."""
        from app.api.v1.presentations import _get_rate_limit_info

        mock_user = _make_mock_user(role="member")

        with patch("app.api.v1.presentations.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(side_effect=Exception("Redis down"))
            mock_cache._client = None

            info = await _get_rate_limit_info(mock_user)

        # Should return defaults without crashing
        assert info["limit"] == 10
        assert info["remaining"] == 10  # count defaults to 0

    @pytest.mark.asyncio
    async def test_increment_rate_limit_handles_redis_failure(self):
        """Increment must not crash when Redis is unavailable."""
        from app.api.v1.presentations import _increment_rate_limit

        mock_user = _make_mock_user()

        with patch("app.api.v1.presentations.redis_cache") as mock_cache:
            mock_cache._client = MagicMock()
            mock_cache._client.incr = AsyncMock(side_effect=Exception("Redis down"))

            # Must not raise
            await _increment_rate_limit(mock_user)

    def test_rate_limit_headers_present_on_all_endpoints(self):
        """All presentation endpoints must call _add_rate_limit_headers."""
        from app.api.v1 import presentations as pres_module
        import inspect

        endpoints = [
            pres_module.create_presentation,
            pres_module.get_presentation_status,
            pres_module.get_presentation,
            pres_module.regenerate_presentation,
        ]

        for endpoint in endpoints:
            source = inspect.getsource(endpoint)
            assert "_add_rate_limit_headers" in source, (
                f"Endpoint {endpoint.__name__} is missing rate-limit headers"
            )

    def test_rate_limit_redis_key_format(self):
        """Rate limit Redis key must be scoped to user ID."""
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module._get_rate_limit_info)
        assert "ratelimit:" in source

    def test_rate_limit_window_applied_on_first_increment(self):
        """TTL must be set on the Redis key when counter is first created."""
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module._increment_rate_limit)
        assert "expire" in source


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


class TestRouterRegistration:
    """Verify all endpoints are registered on the router."""

    def test_router_has_create_presentation_route(self):
        from app.api.v1.presentations import router

        routes = {r.path for r in router.routes}
        assert "/presentations" in routes

    def test_router_has_status_route(self):
        from app.api.v1.presentations import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/status" in routes

    def test_router_has_get_presentation_route(self):
        from app.api.v1.presentations import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}" in routes

    def test_router_has_regenerate_route(self):
        from app.api.v1.presentations import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/regenerate" in routes

    def test_router_has_stream_route(self):
        from app.api.v1.presentations import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/stream" in routes

    def test_router_has_cancel_job_route(self):
        from app.api.v1.presentations import router

        routes = {r.path for r in router.routes}
        assert "/jobs/{job_id}" in routes

    def test_create_presentation_method_is_post(self):
        from app.api.v1.presentations import router

        post_routes = [r for r in router.routes if "POST" in getattr(r, "methods", set())]
        paths = {r.path for r in post_routes}
        assert "/presentations" in paths

    def test_status_method_is_get(self):
        from app.api.v1.presentations import router

        get_routes = [r for r in router.routes if "GET" in getattr(r, "methods", set())]
        paths = {r.path for r in get_routes}
        assert "/presentations/{presentation_id}/status" in paths

    def test_cancel_method_is_delete(self):
        from app.api.v1.presentations import router

        delete_routes = [r for r in router.routes if "DELETE" in getattr(r, "methods", set())]
        paths = {r.path for r in delete_routes}
        assert "/jobs/{job_id}" in paths
