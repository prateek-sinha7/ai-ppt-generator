"""
Streaming Engine — Redis pub/sub + Redis Streams for SSE delivery.

Architecture:
- Events are published to a Redis Stream (XADD) keyed by presentation_id.
  This gives us persistent, replayable event history (5-minute window).
- The SSE endpoint subscribes via XREAD with BLOCK, yielding events as
  server-sent events to the client.
- Last-Event-ID reconnection: client sends the last received stream entry
  ID; we resume from that position.

Event types (16.2):
  agent_start      — an agent has begun processing
  agent_complete   — an agent finished successfully
  slide_ready      — a single slide is available (progressive rendering)
  quality_score    — quality scoring result
  complete         — pipeline finished; full Slide_JSON available
  error            — pipeline failed with an error message

Stream key:  stream:presentation:{presentation_id}
TTL:         5 minutes (300 seconds) — events are replayed within this window
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, Optional

import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STREAM_TTL_SECONDS = 300          # 5-minute event replay window (16.4)
STREAM_KEY_PREFIX = "stream:presentation:"
STREAM_MAX_LEN = 500              # cap entries per stream to avoid unbounded growth
SSE_KEEPALIVE_INTERVAL = 15       # seconds between keepalive comments
XREAD_BLOCK_MS = 5_000            # block up to 5 s waiting for new events


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def _stream_key(presentation_id: str) -> str:
    return f"{STREAM_KEY_PREFIX}{presentation_id}"


def _build_sse_line(event_type: str, data: Dict[str, Any], event_id: str) -> str:
    """Format a single SSE message."""
    payload = json.dumps(data)
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# StreamingService
# ---------------------------------------------------------------------------

class StreamingService:
    """
    Manages pipeline event publishing and SSE delivery.

    One instance is shared across the application (singleton pattern).
    Each method creates its own short-lived Redis connection to avoid
    blocking the shared async connection pool.
    """

    def __init__(self) -> None:
        self._redis_url = settings.REDIS_URL

    def _get_client(self) -> aioredis.Redis:
        """Create a new async Redis client."""
        return aioredis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    # ------------------------------------------------------------------
    # Publishing (16.2)
    # ------------------------------------------------------------------

    async def publish_event(
        self,
        presentation_id: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> str:
        """
        Publish a pipeline event to the Redis Stream for this presentation.

        Returns the stream entry ID (e.g. "1700000000000-0").
        The stream is capped at STREAM_MAX_LEN entries and expires after
        STREAM_TTL_SECONDS so memory is bounded.
        """
        client = self._get_client()
        try:
            key = _stream_key(presentation_id)
            entry = {
                "event_type": event_type,
                "data": json.dumps(data),
                "ts": str(int(time.time() * 1000)),
            }
            entry_id: str = await client.xadd(
                key,
                entry,
                maxlen=STREAM_MAX_LEN,
                approximate=True,
            )
            # Refresh TTL on every write so the window slides forward
            await client.expire(key, STREAM_TTL_SECONDS)
            logger.debug(
                "stream_event_published",
                presentation_id=presentation_id,
                event_type=event_type,
                entry_id=entry_id,
            )
            return entry_id
        finally:
            await client.aclose()

    # ------------------------------------------------------------------
    # Convenience publish methods (16.2)
    # ------------------------------------------------------------------

    async def publish_agent_start(
        self, presentation_id: str, agent_name: str, execution_id: str,
        generation_mode: Optional[str] = None,
    ) -> str:
        data: Dict[str, Any] = {"agent": agent_name, "execution_id": execution_id}
        if generation_mode:
            data["generation_mode"] = generation_mode
        return await self.publish_event(
            presentation_id,
            "agent_start",
            data,
        )

    async def publish_agent_complete(
        self,
        presentation_id: str,
        agent_name: str,
        execution_id: str,
        elapsed_ms: float,
    ) -> str:
        return await self.publish_event(
            presentation_id,
            "agent_complete",
            {
                "agent": agent_name,
                "execution_id": execution_id,
                "elapsed_ms": round(elapsed_ms, 1),
            },
        )

    async def publish_slide_ready(
        self,
        presentation_id: str,
        slide: Dict[str, Any],
        slide_number: int,
        total_slides: int,
    ) -> str:
        """Emit a slide_ready event for progressive rendering (16.3)."""
        return await self.publish_event(
            presentation_id,
            "slide_ready",
            {
                "slide_number": slide_number,
                "total_slides": total_slides,
                "slide": slide,
            },
        )

    async def publish_quality_score(
        self,
        presentation_id: str,
        composite_score: float,
        dimensions: Dict[str, float],
    ) -> str:
        return await self.publish_event(
            presentation_id,
            "quality_score",
            {
                "composite_score": composite_score,
                "dimensions": dimensions,
            },
        )

    async def publish_complete(
        self,
        presentation_id: str,
        execution_id: str,
        quality_score: Optional[float] = None,
    ) -> str:
        return await self.publish_event(
            presentation_id,
            "complete",
            {
                "execution_id": execution_id,
                "quality_score": quality_score,
                "presentation_id": presentation_id,
            },
        )

    async def publish_error(
        self,
        presentation_id: str,
        execution_id: str,
        error_message: str,
        failed_agent: Optional[str] = None,
    ) -> str:
        return await self.publish_event(
            presentation_id,
            "error",
            {
                "execution_id": execution_id,
                "error": error_message,
                "failed_agent": failed_agent,
            },
        )

    # ------------------------------------------------------------------
    # SSE streaming (16.1, 16.4)
    # ------------------------------------------------------------------

    async def stream_events(
        self,
        presentation_id: str,
        last_event_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator that yields SSE-formatted strings.

        Reconnection (16.4):
          If last_event_id is provided (from the Last-Event-ID header),
          we start reading from that position in the stream so the client
          receives any events it missed during a disconnect.

        Keepalive:
          A SSE comment (": keepalive") is emitted every
          SSE_KEEPALIVE_INTERVAL seconds to prevent proxy timeouts.

        Termination:
          The generator exits when a "complete" or "error" event is
          consumed, or when the stream key expires (no more events within
          the TTL window).
        """
        key = _stream_key(presentation_id)
        # "0" means "from the beginning"; "$" means "only new events"
        start_id = last_event_id if last_event_id else "0"

        client = self._get_client()
        try:
            last_keepalive = time.monotonic()

            while True:
                # Keepalive comment to prevent proxy/browser timeouts
                now = time.monotonic()
                if now - last_keepalive >= SSE_KEEPALIVE_INTERVAL:
                    yield ": keepalive\n\n"
                    last_keepalive = now

                # XREAD with blocking — waits up to XREAD_BLOCK_MS for new entries
                results = await client.xread(
                    {key: start_id},
                    block=XREAD_BLOCK_MS,
                    count=50,
                )

                if not results:
                    # No new events; check if stream still exists
                    exists = await client.exists(key)
                    if not exists:
                        # Stream expired — nothing more to deliver
                        logger.info(
                            "stream_expired",
                            presentation_id=presentation_id,
                        )
                        return
                    continue

                # results is [(stream_key, [(entry_id, fields), ...])]
                for _stream_name, entries in results:
                    for entry_id, fields in entries:
                        start_id = entry_id  # advance cursor

                        event_type = fields.get("event_type", "unknown")
                        raw_data = fields.get("data", "{}")
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            data = {"raw": raw_data}

                        yield _build_sse_line(event_type, data, entry_id)

                        # Stop streaming after terminal events
                        if event_type in ("complete", "error"):
                            logger.info(
                                "stream_terminal_event",
                                presentation_id=presentation_id,
                                event_type=event_type,
                            )
                            return

        except asyncio.CancelledError:
            # Client disconnected — clean exit
            logger.info("stream_client_disconnected", presentation_id=presentation_id)
            return
        except Exception as exc:
            logger.error(
                "stream_error",
                presentation_id=presentation_id,
                error=str(exc),
            )
            yield _build_sse_line(
                "error",
                {"error": "Internal streaming error"},
                "0-0",
            )
            return
        finally:
            await client.aclose()

    # ------------------------------------------------------------------
    # Cancellation support (16.5)
    # ------------------------------------------------------------------

    async def cancel_stream(self, presentation_id: str, execution_id: str) -> None:
        """
        Publish a cancellation event so connected SSE clients receive it
        and the pipeline worker can detect the cancellation flag.
        """
        await self.publish_event(
            presentation_id,
            "error",
            {
                "execution_id": execution_id,
                "error": "Job cancelled by user",
                "cancelled": True,
            },
        )

    async def set_cancellation_flag(self, job_id: str) -> None:
        """
        Set a Redis key that the Celery worker polls to detect cancellation.
        TTL matches the stream window so it auto-expires.
        """
        client = self._get_client()
        try:
            key = f"cancel:job:{job_id}"
            await client.set(key, "1", ex=STREAM_TTL_SECONDS)
            logger.info("cancellation_flag_set", job_id=job_id)
        finally:
            await client.aclose()

    async def is_cancelled(self, job_id: str) -> bool:
        """Check whether a cancellation flag has been set for this job."""
        client = self._get_client()
        try:
            key = f"cancel:job:{job_id}"
            return await client.exists(key) > 0
        finally:
            await client.aclose()

    async def clear_cancellation_flag(self, job_id: str) -> None:
        """Remove the cancellation flag (called after worker acknowledges)."""
        client = self._get_client()
        try:
            await client.delete(f"cancel:job:{job_id}")
        finally:
            await client.aclose()


# Singleton instance
streaming_service = StreamingService()
