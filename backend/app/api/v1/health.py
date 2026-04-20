"""
Health Check Endpoints (30.5)

GET /health        — basic liveness (always 200 if process is up)
GET /health/live   — liveness probe (same as /health, for k8s compatibility)
GET /health/ready  — readiness probe: checks DB, Redis, and primary LLM provider
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# Liveness — always 200 if the process is running
# ---------------------------------------------------------------------------

@router.get("/health", summary="Liveness check")
async def health() -> Dict[str, str]:
    """Basic liveness probe — returns 200 if the process is alive."""
    return {"status": "ok"}


@router.get("/health/live", summary="Liveness probe (k8s)")
async def liveness() -> Dict[str, str]:
    """Kubernetes-style liveness probe."""
    return {"status": "alive"}


# ---------------------------------------------------------------------------
# Readiness — checks DB, Redis, and primary LLM provider
# ---------------------------------------------------------------------------

@router.get("/health/ready", summary="Readiness probe")
async def readiness() -> JSONResponse:
    """
    Readiness probe.  Returns 200 only when all critical dependencies are
    reachable: PostgreSQL, Redis, and the configured primary LLM provider.

    Returns 503 with a JSON body describing which checks failed.
    """
    checks: Dict[str, Any] = {}
    all_ok = True

    # --- Database check ---
    db_ok, db_detail = await _check_database()
    checks["database"] = {"ok": db_ok, "detail": db_detail}
    if not db_ok:
        all_ok = False

    # --- Redis check ---
    redis_ok, redis_detail = await _check_redis()
    checks["redis"] = {"ok": redis_ok, "detail": redis_detail}
    if not redis_ok:
        all_ok = False

    # --- Primary LLM provider check ---
    provider_ok, provider_detail = await _check_provider()
    checks["llm_provider"] = {"ok": provider_ok, "detail": provider_detail}
    if not provider_ok:
        all_ok = False

    status_code = 200 if all_ok else 503
    body = {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
    }

    if not all_ok:
        logger.warning("readiness_check_failed", checks=checks)

    return JSONResponse(content=body, status_code=status_code)


# ---------------------------------------------------------------------------
# Individual dependency checks
# ---------------------------------------------------------------------------

async def _check_database() -> tuple[bool, str]:
    """Verify PostgreSQL is reachable with a lightweight query."""
    try:
        from sqlalchemy import text
        from app.db.session import async_session_maker

        async with async_session_maker() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=3.0)
        return True, "ok"
    except asyncio.TimeoutError:
        return False, "timeout after 3s"
    except Exception as exc:
        return False, str(exc)


async def _check_redis() -> tuple[bool, str]:
    """Verify Redis is reachable with a PING command."""
    try:
        from app.services.redis_cache import redis_cache

        if redis_cache._client is None:
            return False, "redis client not initialised"

        pong = await asyncio.wait_for(redis_cache._client.ping(), timeout=2.0)
        if pong:
            return True, "ok"
        return False, "ping returned falsy"
    except asyncio.TimeoutError:
        return False, "timeout after 2s"
    except Exception as exc:
        return False, str(exc)


async def _check_provider() -> tuple[bool, str]:
    """
    Verify the primary LLM provider is configured and its credentials are present.
    Does NOT make a live API call — checks configuration and cached health status.
    """
    try:
        from app.services.llm_provider import provider_factory
        from app.services.provider_health import health_monitor

        primary = provider_factory.primary_provider
        if primary is None:
            return False, "no primary provider configured"

        config = provider_factory.provider_configs.get(primary)
        if not config or not config.is_available:
            return False, f"provider '{primary.value}' credentials missing"

        # Check cached health status (non-blocking)
        metrics = health_monitor.metrics.get(primary)
        if metrics and metrics.circuit_open:
            return False, f"provider '{primary.value}' circuit breaker open"

        return True, f"provider '{primary.value}' configured"
    except Exception as exc:
        return False, str(exc)
