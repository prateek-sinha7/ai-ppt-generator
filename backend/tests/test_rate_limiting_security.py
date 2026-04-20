"""
Tests for Task 20: Rate Limiting and Security Middleware

Covers:
  20.1 Multi-tier rate limiting (per-provider, per-user, system-wide)
  20.2 Priority request queuing
  20.3 Security headers (CSP, HSTS, X-Frame-Options, etc.)
  20.4 Audit logging middleware
  20.5 API versioning with deprecation support
"""
from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# 20.1 Rate Limiter Tests
# ---------------------------------------------------------------------------


class TestProviderRateLimiter:
    """Tests for per-provider rate limiting."""

    @pytest.mark.asyncio
    async def test_provider_rate_limit_allows_within_limit(self):
        """Requests within the provider limit should be allowed."""
        from app.services.rate_limiter import check_provider_rate_limit, PROVIDER_RATE_LIMITS

        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=1)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=55)

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await check_provider_rate_limit("claude")

        assert result.allowed is True
        assert result.limit == PROVIDER_RATE_LIMITS["claude"]
        assert result.remaining == PROVIDER_RATE_LIMITS["claude"] - 1

    @pytest.mark.asyncio
    async def test_provider_rate_limit_blocks_over_limit(self):
        """Requests exceeding the provider limit should be blocked."""
        from app.services.rate_limiter import check_provider_rate_limit, PROVIDER_RATE_LIMITS

        limit = PROVIDER_RATE_LIMITS["claude"]
        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=limit + 1)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=30)

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await check_provider_rate_limit("claude")

        assert result.allowed is False
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_provider_rate_limits_differ_by_provider(self):
        """Different providers have different rate limits."""
        from app.services.rate_limiter import PROVIDER_RATE_LIMITS

        assert PROVIDER_RATE_LIMITS["claude"] == 100
        assert PROVIDER_RATE_LIMITS["openai"] == 150
        assert PROVIDER_RATE_LIMITS["groq"] == 200

    @pytest.mark.asyncio
    async def test_provider_rate_limit_fails_open_on_redis_error(self):
        """Rate limiter should fail open (allow) when Redis is unavailable."""
        from app.services.rate_limiter import check_provider_rate_limit

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = None
            mock_cache.connect = AsyncMock(side_effect=ConnectionError("Redis down"))
            result = await check_provider_rate_limit("claude")

        assert result.allowed is True


class TestUserRateLimiter:
    """Tests for per-user rate limiting."""

    @pytest.mark.asyncio
    async def test_free_user_limit(self):
        """Free (member) users have 10 req/hr limit."""
        from app.services.rate_limiter import USER_RATE_LIMITS

        assert USER_RATE_LIMITS["member"] == 10
        assert USER_RATE_LIMITS["viewer"] == 10

    @pytest.mark.asyncio
    async def test_premium_user_limit(self):
        """Premium (admin) users have 100 req/hr limit."""
        from app.services.rate_limiter import USER_RATE_LIMITS

        assert USER_RATE_LIMITS["admin"] == 100

    @pytest.mark.asyncio
    async def test_user_rate_limit_allows_within_limit(self):
        """User requests within limit should be allowed."""
        from app.services.rate_limiter import check_user_rate_limit

        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=5)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=3000)

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await check_user_rate_limit("user-123", "member")

        assert result.allowed is True
        assert result.limit == 10
        assert result.remaining == 5

    @pytest.mark.asyncio
    async def test_user_rate_limit_blocks_over_limit(self):
        """User requests over limit should be blocked."""
        from app.services.rate_limiter import check_user_rate_limit

        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=11)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=1800)

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await check_user_rate_limit("user-123", "member")

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0


class TestSystemConcurrentLimit:
    """Tests for system-wide concurrent request limiting."""

    @pytest.mark.asyncio
    async def test_acquire_slot_within_limit(self):
        """Should acquire slot when under the concurrent limit."""
        from app.services.rate_limiter import acquire_concurrent_slot, SYSTEM_CONCURRENT_LIMIT

        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=500)
        mock_client.ttl = AsyncMock(return_value=60)
        mock_client.expire = AsyncMock()

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await acquire_concurrent_slot()

        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_slot_at_limit(self):
        """Should reject slot when at the concurrent limit."""
        from app.services.rate_limiter import acquire_concurrent_slot, SYSTEM_CONCURRENT_LIMIT

        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=SYSTEM_CONCURRENT_LIMIT + 1)
        mock_client.ttl = AsyncMock(return_value=60)
        mock_client.expire = AsyncMock()
        mock_client.decr = AsyncMock(return_value=SYSTEM_CONCURRENT_LIMIT)

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await acquire_concurrent_slot()

        assert result is False
        mock_client.decr.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_slot_decrements_counter(self):
        """Releasing a slot should decrement the counter."""
        from app.services.rate_limiter import release_concurrent_slot

        mock_client = AsyncMock()
        mock_client.decr = AsyncMock(return_value=499)

        with patch("app.services.rate_limiter.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            await release_concurrent_slot()

        mock_client.decr.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_concurrent_limit_value(self):
        """System concurrent limit should be 1000."""
        from app.services.rate_limiter import SYSTEM_CONCURRENT_LIMIT

        assert SYSTEM_CONCURRENT_LIMIT == 1000


# ---------------------------------------------------------------------------
# 20.2 Priority Queue Tests
# ---------------------------------------------------------------------------


class TestPriorityQueue:
    """Tests for priority request queuing."""

    def test_priority_computation_premium(self):
        """Admin users get highest priority."""
        from app.services.priority_queue import _compute_priority, PRIORITY_PREMIUM

        assert _compute_priority("admin", False) == PRIORITY_PREMIUM
        assert _compute_priority("admin", True) == PRIORITY_PREMIUM

    def test_priority_computation_retry(self):
        """Retry requests get medium priority."""
        from app.services.priority_queue import _compute_priority, PRIORITY_RETRY

        assert _compute_priority("member", True) == PRIORITY_RETRY

    def test_priority_computation_new(self):
        """New free requests get lowest priority."""
        from app.services.priority_queue import _compute_priority, PRIORITY_NEW

        assert _compute_priority("member", False) == PRIORITY_NEW
        assert _compute_priority("viewer", False) == PRIORITY_NEW

    def test_priority_order(self):
        """Premium > retry > new."""
        from app.services.priority_queue import PRIORITY_PREMIUM, PRIORITY_RETRY, PRIORITY_NEW

        assert PRIORITY_PREMIUM > PRIORITY_RETRY > PRIORITY_NEW

    def test_queue_score_higher_priority_lower_score(self):
        """Higher priority should produce a lower (more negative) score for ZPOPMIN."""
        from app.services.priority_queue import _queue_score, PRIORITY_PREMIUM, PRIORITY_NEW

        ts = time.time()
        premium_score = _queue_score(PRIORITY_PREMIUM, ts)
        new_score = _queue_score(PRIORITY_NEW, ts)

        # ZPOPMIN returns lowest score first — premium should have lower score
        assert premium_score < new_score

    def test_fifo_within_same_priority(self):
        """Earlier requests should have lower score within the same priority."""
        from app.services.priority_queue import _queue_score, PRIORITY_NEW

        earlier = _queue_score(PRIORITY_NEW, 1000.0)
        later = _queue_score(PRIORITY_NEW, 2000.0)

        assert earlier < later

    @pytest.mark.asyncio
    async def test_enqueue_request(self):
        """Enqueuing a request should store it in Redis."""
        from app.services.priority_queue import enqueue_request

        mock_client = AsyncMock()
        mock_client.hset = AsyncMock()
        mock_client.zadd = AsyncMock()

        with patch("app.services.priority_queue.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            req = await enqueue_request(
                user_id="user-1",
                role="admin",
                payload={"topic": "test"},
            )

        assert req.user_id == "user-1"
        assert req.role == "admin"
        assert req.request_id is not None
        mock_client.hset.assert_called_once()
        mock_client.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_returns_highest_priority(self):
        """Dequeue should return the highest-priority request."""
        import json
        from app.services.priority_queue import dequeue_next_request

        payload_data = {
            "request_id": "req-1",
            "user_id": "user-1",
            "role": "admin",
            "is_retry": False,
            "payload": {"topic": "test"},
            "queued_at": time.time(),
            "priority": 10,
        }

        mock_client = AsyncMock()
        mock_client.zpopmin = AsyncMock(return_value=[("req-1", -10e12)])
        mock_client.hget = AsyncMock(return_value=json.dumps(payload_data))
        mock_client.hdel = AsyncMock()

        with patch("app.services.priority_queue.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            req = await dequeue_next_request()

        assert req is not None
        assert req.request_id == "req-1"
        assert req.role == "admin"

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue_returns_none(self):
        """Dequeue on empty queue should return None."""
        from app.services.priority_queue import dequeue_next_request

        mock_client = AsyncMock()
        mock_client.zpopmin = AsyncMock(return_value=[])

        with patch("app.services.priority_queue.redis_cache") as mock_cache:
            mock_cache._client = mock_client
            result = await dequeue_next_request()

        assert result is None


# ---------------------------------------------------------------------------
# 20.3 Security Headers Tests
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def test_csp_header_present(self):
        """CSP header should be present on all responses."""
        from app.middleware.security_headers import _CSP_HEADER

        assert "default-src" in _CSP_HEADER
        assert "script-src" in _CSP_HEADER
        assert "frame-ancestors" in _CSP_HEADER
        assert "'none'" in _CSP_HEADER  # frame-ancestors: 'none'

    def test_csp_blocks_object_src(self):
        """CSP should block object-src."""
        from app.middleware.security_headers import _CSP_HEADER

        assert "object-src 'none'" in _CSP_HEADER

    def test_hsts_header_format(self):
        """HSTS header should include max-age, includeSubDomains, preload."""
        from app.middleware.security_headers import _HSTS_HEADER

        assert "max-age=" in _HSTS_HEADER
        assert "includeSubDomains" in _HSTS_HEADER
        assert "preload" in _HSTS_HEADER

    def test_hsts_max_age_one_year(self):
        """HSTS max-age should be at least 1 year (31536000 seconds)."""
        from app.middleware.security_headers import _HSTS_HEADER

        import re
        match = re.search(r"max-age=(\d+)", _HSTS_HEADER)
        assert match is not None
        assert int(match.group(1)) >= 31536000

    @pytest.mark.asyncio
    async def test_security_headers_added_to_response(self):
        """Security headers should be added to every response."""
        from app.middleware.security_headers import SecurityHeadersMiddleware
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def homepage(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_no_server_header_leaked(self):
        """Server identification headers should be removed."""
        from app.middleware.security_headers import SecurityHeadersMiddleware
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def homepage(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)
        response = client.get("/")

        assert "X-Powered-By" not in response.headers


# ---------------------------------------------------------------------------
# 20.4 Audit Logging Tests
# ---------------------------------------------------------------------------


class TestAuditLogger:
    """Tests for the audit logger service."""

    @pytest.mark.asyncio
    async def test_audit_log_writes_entry(self):
        """Audit logger should write an AuditLog entry to the DB."""
        from app.services.audit_logger import audit_logger

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        await audit_logger.log(
            db=mock_db,
            action="presentation.create",
            resource_type="presentation",
            resource_id="pres-123",
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            metadata={"topic": "AI trends"},
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_log_does_not_raise_on_db_error(self):
        """Audit logger should swallow DB errors and not propagate them."""
        from app.services.audit_logger import audit_logger

        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=Exception("DB error"))
        mock_db.flush = AsyncMock()

        # Should not raise
        await audit_logger.log(
            db=mock_db,
            action="presentation.create",
            resource_type="presentation",
            resource_id="pres-123",
        )

    @pytest.mark.asyncio
    async def test_audit_log_mutation_captures_before_after(self):
        """log_mutation should include before/after state in metadata."""
        from app.services.audit_logger import audit_logger
        from app.db.models import AuditLog

        captured_entry = None

        mock_db = AsyncMock()

        def capture_add(entry):
            nonlocal captured_entry
            captured_entry = entry

        mock_db.add = MagicMock(side_effect=capture_add)
        mock_db.flush = AsyncMock()

        before = {"status": "queued"}
        after = {"status": "completed"}

        await audit_logger.log_mutation(
            db=mock_db,
            action="presentation.update",
            resource_type="presentation",
            resource_id="pres-123",
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            before=before,
            after=after,
        )

        assert captured_entry is not None
        assert captured_entry.extra_metadata["before"] == before
        assert captured_entry.extra_metadata["after"] == after

    def test_audit_action_constants_defined(self):
        """All canonical action constants should be defined."""
        from app.services import audit_logger as al

        assert al.ACTION_PRESENTATION_CREATE == "presentation.create"
        assert al.ACTION_PRESENTATION_READ == "presentation.read"
        assert al.ACTION_SLIDE_UPDATE == "slide.update"
        assert al.ACTION_USER_LOGIN == "user.login"


class TestAuditMiddleware:
    """Tests for the audit middleware path parsing."""

    def test_resource_from_path_presentation(self):
        """Should extract presentation resource from path."""
        from app.middleware.audit import _resource_from_path

        resource_type, resource_id = _resource_from_path("/api/v1/presentations/abc-123")
        assert resource_type == "presentation"
        assert resource_id == "abc-123"

    def test_resource_from_path_slide(self):
        """Should extract slide resource from nested path."""
        from app.middleware.audit import _resource_from_path

        resource_type, resource_id = _resource_from_path(
            "/api/v1/presentations/pres-1/slides/slide-2"
        )
        assert resource_type == "slide"
        assert resource_id == "slide-2"

    def test_resource_from_path_template(self):
        """Should extract template resource."""
        from app.middleware.audit import _resource_from_path

        resource_type, resource_id = _resource_from_path("/api/v1/templates")
        assert resource_type == "template"
        assert resource_id is None

    def test_should_audit_post(self):
        """POST requests should always be audited."""
        from app.middleware.audit import _should_audit

        assert _should_audit("POST", "/api/v1/presentations") is True

    def test_should_audit_delete(self):
        """DELETE requests should always be audited."""
        from app.middleware.audit import _should_audit

        assert _should_audit("DELETE", "/api/v1/jobs/job-1") is True

    def test_should_not_audit_health(self):
        """Health check endpoints should not be audited."""
        from app.middleware.audit import _should_audit

        assert _should_audit("GET", "/health") is False
        assert _should_audit("GET", "/health/ready") is False

    def test_should_not_audit_docs(self):
        """API docs should not be audited."""
        from app.middleware.audit import _should_audit

        assert _should_audit("GET", "/api/docs") is False


# ---------------------------------------------------------------------------
# 20.5 API Versioning Tests
# ---------------------------------------------------------------------------


class TestAPIVersioning:
    """Tests for API versioning middleware."""

    def test_current_version_is_v1(self):
        """Current API version should be 1.0.0."""
        from app.middleware.api_versioning import CURRENT_VERSION

        assert CURRENT_VERSION == "1.0.0"

    def test_version_registry_has_v1(self):
        """Version registry should contain v1 as active."""
        from app.middleware.api_versioning import VERSION_REGISTRY

        assert "v1" in VERSION_REGISTRY
        assert VERSION_REGISTRY["v1"]["status"] == "active"

    def test_extract_version_prefix_v1(self):
        """Should extract v1 from /api/v1/presentations."""
        from app.middleware.api_versioning import _extract_version_prefix

        assert _extract_version_prefix("/api/v1/presentations") == "v1"
        assert _extract_version_prefix("/api/v1/auth/login") == "v1"

    def test_extract_version_prefix_none_for_non_versioned(self):
        """Should return None for non-versioned paths."""
        from app.middleware.api_versioning import _extract_version_prefix

        assert _extract_version_prefix("/health") is None
        assert _extract_version_prefix("/internal/providers") is None

    def test_get_api_versions_response_structure(self):
        """API versions response should have required fields."""
        from app.middleware.api_versioning import get_api_versions_response

        response = get_api_versions_response()

        assert "current_version" in response
        assert "versions" in response
        assert "deprecation_policy" in response
        assert len(response["versions"]) >= 1

        v1 = next(v for v in response["versions"] if v["prefix"] == "v1")
        assert v1["status"] == "active"
        assert v1["base_url"] == "/api/v1/"

    @pytest.mark.asyncio
    async def test_api_version_header_injected(self):
        """API-Version header should be present on versioned responses."""
        from app.middleware.api_versioning import APIVersioningMiddleware, CURRENT_VERSION
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def endpoint(request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/v1/test", endpoint)])
        app.add_middleware(APIVersioningMiddleware)

        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert "API-Version" in response.headers
        assert response.headers["API-Version"] == CURRENT_VERSION

    @pytest.mark.asyncio
    async def test_unknown_version_returns_404(self):
        """Unknown API version should return 404."""
        from app.middleware.api_versioning import APIVersioningMiddleware
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def endpoint(request):
            return JSONResponse({"ok": True})

        app = Starlette(routes=[Route("/api/v99/test", endpoint)])
        app.add_middleware(APIVersioningMiddleware)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v99/test")

        assert response.status_code == 404
        data = response.json()
        assert "supported_versions" in data

    def test_deprecation_policy_mentions_six_months(self):
        """Deprecation policy should mention 6 months notice."""
        from app.middleware.api_versioning import get_api_versions_response

        response = get_api_versions_response()
        assert "6 months" in response["deprecation_policy"]

    def test_sunsetted_version_returns_410(self):
        """Sunsetted API version should return 410 Gone."""
        from app.middleware.api_versioning import APIVersioningMiddleware, VERSION_REGISTRY
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        # Temporarily add a sunsetted version
        VERSION_REGISTRY["v0"] = {
            "version": "0.9.0",
            "status": "sunset",
            "deprecated_date": "2024-01-01",
            "sunset_date": "2024-07-01",
            "notes": "Use v1.",
        }

        try:
            async def endpoint(request):
                return JSONResponse({"ok": True})

            app = Starlette(routes=[Route("/api/v0/test", endpoint)])
            app.add_middleware(APIVersioningMiddleware)

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v0/test")

            assert response.status_code == 410
            data = response.json()
            assert "sunset" in data["detail"].lower()
        finally:
            del VERSION_REGISTRY["v0"]
