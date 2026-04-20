"""
Multi-tier Rate Limiting Service (Task 20.1)

Implements three tiers of rate limiting using Redis:
  1. Per-provider limits  — Claude 100/min, OpenAI 150/min, Groq 200/min
  2. Per-user limits      — 10/hr (free/member), 100/hr (premium/admin)
  3. System-wide limit    — 1000 concurrent requests

All counters are stored in Redis with appropriate TTLs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import structlog

from app.services.redis_cache import redis_cache

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Per-provider limits (requests per minute)
PROVIDER_RATE_LIMITS: dict[str, int] = {
    "claude": 100,
    "openai": 150,
    "groq": 200,
    "local": 500,  # local has no external constraint
}
PROVIDER_WINDOW_SECONDS = 60  # 1 minute

# Per-user limits (requests per hour)
USER_RATE_LIMITS: dict[str, int] = {
    "member": 10,    # free tier
    "viewer": 10,    # free tier
    "admin": 100,    # premium tier
}
USER_WINDOW_SECONDS = 3600  # 1 hour

# System-wide concurrent request limit
SYSTEM_CONCURRENT_LIMIT = 1000
SYSTEM_CONCURRENT_KEY = "ratelimit:system:concurrent"
# TTL for concurrent slot — auto-expires if request never decrements (e.g. crash)
SYSTEM_CONCURRENT_TTL = 300  # 5 minutes


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int          # Unix timestamp when window resets
    retry_after: int = 0   # seconds to wait if not allowed


# ---------------------------------------------------------------------------
# Provider rate limiting
# ---------------------------------------------------------------------------


async def check_provider_rate_limit(provider: str) -> RateLimitResult:
    """
    Check and increment the per-provider rate limit counter.

    Uses a fixed 1-minute window keyed by provider name.
    Returns RateLimitResult indicating whether the call is allowed.
    """
    limit = PROVIDER_RATE_LIMITS.get(provider, 100)
    key = f"ratelimit:provider:{provider}"

    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        count = await client.incr(key)
        if count == 1:
            await client.expire(key, PROVIDER_WINDOW_SECONDS)

        ttl = await client.ttl(key)
        reset_at = int(time.time()) + (ttl if ttl > 0 else PROVIDER_WINDOW_SECONDS)
        remaining = max(0, limit - count)
        allowed = count <= limit

        if not allowed:
            logger.warning(
                "provider_rate_limit_exceeded",
                provider=provider,
                count=count,
                limit=limit,
            )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=ttl if not allowed else 0,
        )

    except Exception as e:
        logger.error("provider_rate_limit_check_failed", provider=provider, error=str(e))
        # Fail open — don't block requests if Redis is unavailable
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_at=int(time.time()) + PROVIDER_WINDOW_SECONDS)


async def get_provider_rate_limit_info(provider: str) -> RateLimitResult:
    """
    Read current provider rate limit state without incrementing.
    """
    limit = PROVIDER_RATE_LIMITS.get(provider, 100)
    key = f"ratelimit:provider:{provider}"

    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        raw = await client.get(key)
        count = int(raw) if raw else 0
        ttl = await client.ttl(key)
        reset_at = int(time.time()) + (ttl if ttl > 0 else PROVIDER_WINDOW_SECONDS)
        remaining = max(0, limit - count)

        return RateLimitResult(
            allowed=count < limit,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    except Exception as e:
        logger.error("provider_rate_limit_info_failed", provider=provider, error=str(e))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_at=int(time.time()) + PROVIDER_WINDOW_SECONDS)


# ---------------------------------------------------------------------------
# Per-user rate limiting
# ---------------------------------------------------------------------------


async def check_user_rate_limit(user_id: str, role: str) -> RateLimitResult:
    """
    Check and increment the per-user hourly rate limit.

    member/viewer = 10 req/hr (free tier)
    admin         = 100 req/hr (premium tier)
    """
    limit = USER_RATE_LIMITS.get(role, USER_RATE_LIMITS["member"])
    key = f"ratelimit:user:{user_id}"

    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        count = await client.incr(key)
        if count == 1:
            await client.expire(key, USER_WINDOW_SECONDS)

        ttl = await client.ttl(key)
        reset_at = int(time.time()) + (ttl if ttl > 0 else USER_WINDOW_SECONDS)
        remaining = max(0, limit - count)
        allowed = count <= limit

        if not allowed:
            logger.warning(
                "user_rate_limit_exceeded",
                user_id=user_id,
                role=role,
                count=count,
                limit=limit,
            )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=ttl if not allowed else 0,
        )

    except Exception as e:
        logger.error("user_rate_limit_check_failed", user_id=user_id, error=str(e))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_at=int(time.time()) + USER_WINDOW_SECONDS)


async def get_user_rate_limit_info(user_id: str, role: str) -> RateLimitResult:
    """
    Read current user rate limit state without incrementing.
    """
    limit = USER_RATE_LIMITS.get(role, USER_RATE_LIMITS["member"])
    key = f"ratelimit:user:{user_id}"

    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        raw = await client.get(key)
        count = int(raw) if raw else 0
        ttl = await client.ttl(key)
        reset_at = int(time.time()) + (ttl if ttl > 0 else USER_WINDOW_SECONDS)
        remaining = max(0, limit - count)

        return RateLimitResult(
            allowed=count < limit,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    except Exception as e:
        logger.error("user_rate_limit_info_failed", user_id=user_id, error=str(e))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_at=int(time.time()) + USER_WINDOW_SECONDS)


# ---------------------------------------------------------------------------
# System-wide concurrent request limiting
# ---------------------------------------------------------------------------


async def acquire_concurrent_slot() -> bool:
    """
    Attempt to acquire a system-wide concurrent request slot.

    Uses Redis INCR + compare to enforce max 1000 concurrent requests.
    Returns True if slot acquired, False if limit reached.
    """
    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        count = await client.incr(SYSTEM_CONCURRENT_KEY)
        # Ensure the key has a TTL as a safety net
        ttl = await client.ttl(SYSTEM_CONCURRENT_KEY)
        if ttl < 0:
            await client.expire(SYSTEM_CONCURRENT_KEY, SYSTEM_CONCURRENT_TTL)

        if count > SYSTEM_CONCURRENT_LIMIT:
            # Immediately decrement — we're not actually processing
            await client.decr(SYSTEM_CONCURRENT_KEY)
            logger.warning(
                "system_concurrent_limit_exceeded",
                count=count,
                limit=SYSTEM_CONCURRENT_LIMIT,
            )
            return False

        return True

    except Exception as e:
        logger.error("acquire_concurrent_slot_failed", error=str(e))
        return True  # Fail open


async def release_concurrent_slot() -> None:
    """Release a previously acquired concurrent request slot."""
    try:
        client = redis_cache._client
        if client is None:
            return

        count = await client.decr(SYSTEM_CONCURRENT_KEY)
        # Prevent negative values from accumulating
        if count < 0:
            await client.set(SYSTEM_CONCURRENT_KEY, 0)

    except Exception as e:
        logger.error("release_concurrent_slot_failed", error=str(e))


async def get_concurrent_count() -> int:
    """Return the current number of concurrent requests."""
    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        raw = await client.get(SYSTEM_CONCURRENT_KEY)
        return max(0, int(raw)) if raw else 0

    except Exception as e:
        logger.error("get_concurrent_count_failed", error=str(e))
        return 0
