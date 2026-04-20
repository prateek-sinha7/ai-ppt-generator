"""
Priority Request Queue Service (Task 20.2)

Implements priority-based request queuing using Redis sorted sets.
Priority order (highest first):
  1. Premium users (admin role)   — priority 10
  2. Retry requests               — priority 5
  3. New requests (free/member)   — priority 1

Requests that exceed the system concurrent limit are queued here
and dequeued in priority order when capacity becomes available.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.services.redis_cache import redis_cache

logger = structlog.get_logger(__name__)

# Redis key for the priority queue (sorted set — score = priority * 1e12 - timestamp)
PRIORITY_QUEUE_KEY = "queue:requests:priority"
# TTL for queued requests — auto-expire stale entries
QUEUE_ENTRY_TTL = 300  # 5 minutes
# Hash storing request payloads keyed by request_id
QUEUE_PAYLOAD_KEY = "queue:requests:payloads"

# Priority scores (higher = processed first in sorted set via negative score trick)
PRIORITY_PREMIUM = 10
PRIORITY_RETRY = 5
PRIORITY_NEW = 1


@dataclass
class QueuedRequest:
    request_id: str
    user_id: str
    role: str
    is_retry: bool
    payload: dict
    queued_at: float = field(default_factory=time.time)
    priority: int = field(init=False)

    def __post_init__(self) -> None:
        self.priority = _compute_priority(self.role, self.is_retry)


def _compute_priority(role: str, is_retry: bool) -> int:
    """
    Determine queue priority.

    Premium (admin) > retry > new free request.
    When role is admin AND it's a retry, still use PRIORITY_PREMIUM
    since premium users always get highest priority.
    """
    if role == "admin":
        return PRIORITY_PREMIUM
    if is_retry:
        return PRIORITY_RETRY
    return PRIORITY_NEW


def _queue_score(priority: int, queued_at: float) -> float:
    """
    Compute Redis sorted-set score.

    We want higher priority processed first, and within the same priority,
    earlier requests processed first (FIFO). Redis sorted sets return members
    with the LOWEST score first (ZPOPMIN), so we negate priority and add
    a fractional timestamp component.

    score = -priority * 1e12 + queued_at
    """
    return -priority * 1e12 + queued_at


async def enqueue_request(
    user_id: str,
    role: str,
    payload: dict,
    is_retry: bool = False,
    request_id: Optional[str] = None,
) -> QueuedRequest:
    """
    Add a request to the priority queue.

    Returns the QueuedRequest with its assigned request_id and priority.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    req = QueuedRequest(
        request_id=request_id,
        user_id=user_id,
        role=role,
        is_retry=is_retry,
        payload=payload,
    )

    score = _queue_score(req.priority, req.queued_at)

    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        # Store payload in hash
        await client.hset(
            QUEUE_PAYLOAD_KEY,
            request_id,
            json.dumps({
                "request_id": request_id,
                "user_id": user_id,
                "role": role,
                "is_retry": is_retry,
                "payload": payload,
                "queued_at": req.queued_at,
                "priority": req.priority,
            }),
        )
        # Add to sorted set with computed score
        await client.zadd(PRIORITY_QUEUE_KEY, {request_id: score})

        logger.info(
            "request_enqueued",
            request_id=request_id,
            user_id=user_id,
            role=role,
            priority=req.priority,
            is_retry=is_retry,
        )

    except Exception as e:
        logger.error("enqueue_request_failed", request_id=request_id, error=str(e))

    return req


async def dequeue_next_request() -> Optional[QueuedRequest]:
    """
    Dequeue the highest-priority request (lowest score in sorted set).

    Returns None if the queue is empty.
    """
    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        # Atomically pop the lowest-score member
        result = await client.zpopmin(PRIORITY_QUEUE_KEY, count=1)
        if not result:
            return None

        request_id = result[0][0]

        # Retrieve payload
        raw = await client.hget(QUEUE_PAYLOAD_KEY, request_id)
        if not raw:
            logger.warning("queue_payload_missing", request_id=request_id)
            return None

        await client.hdel(QUEUE_PAYLOAD_KEY, request_id)

        data = json.loads(raw)
        req = QueuedRequest(
            request_id=data["request_id"],
            user_id=data["user_id"],
            role=data["role"],
            is_retry=data["is_retry"],
            payload=data["payload"],
            queued_at=data["queued_at"],
        )

        logger.info(
            "request_dequeued",
            request_id=req.request_id,
            user_id=req.user_id,
            priority=req.priority,
        )
        return req

    except Exception as e:
        logger.error("dequeue_request_failed", error=str(e))
        return None


async def get_queue_depth() -> dict[str, int]:
    """
    Return queue depth broken down by priority tier.
    """
    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        total = await client.zcard(PRIORITY_QUEUE_KEY)

        # Count by priority band using score ranges
        # score = -priority * 1e12 + timestamp
        # premium: score in (-10e12, -10e12 + 1e12) → (-10e12, -9e12)
        # retry:   score in (-5e12, -5e12 + 1e12)   → (-5e12, -4e12)
        # new:     score in (-1e12, -1e12 + 1e12)    → (-1e12, 0)

        premium_count = await client.zcount(
            PRIORITY_QUEUE_KEY,
            -PRIORITY_PREMIUM * 1e12,
            -(PRIORITY_PREMIUM - 1) * 1e12,
        )
        retry_count = await client.zcount(
            PRIORITY_QUEUE_KEY,
            -PRIORITY_RETRY * 1e12,
            -(PRIORITY_RETRY - 1) * 1e12,
        )
        new_count = await client.zcount(
            PRIORITY_QUEUE_KEY,
            -PRIORITY_NEW * 1e12,
            0,
        )

        return {
            "total": total,
            "premium": premium_count,
            "retry": retry_count,
            "new": new_count,
        }

    except Exception as e:
        logger.error("get_queue_depth_failed", error=str(e))
        return {"total": 0, "premium": 0, "retry": 0, "new": 0}


async def remove_request(request_id: str) -> bool:
    """Remove a specific request from the queue (e.g. on cancellation)."""
    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        await client.zrem(PRIORITY_QUEUE_KEY, request_id)
        await client.hdel(QUEUE_PAYLOAD_KEY, request_id)
        return True

    except Exception as e:
        logger.error("remove_request_failed", request_id=request_id, error=str(e))
        return False


async def get_queue_position(request_id: str) -> Optional[int]:
    """
    Return the 0-based position of a request in the queue.
    Returns None if the request is not in the queue.
    """
    try:
        client = redis_cache._client
        if client is None:
            await redis_cache.connect()
            client = redis_cache._client

        rank = await client.zrank(PRIORITY_QUEUE_KEY, request_id)
        return rank  # None if not found

    except Exception as e:
        logger.error("get_queue_position_failed", request_id=request_id, error=str(e))
        return None
