"""
Presentation Cache Service

Implements the caching layer for the AI Presentation Intelligence Platform:

- 21.1  Composite cache key for final Slide_JSON:
        sha256(topic + industry + theme + provider_config_hash + prompt_version)
- 21.2  Research cache (TTL=6h) and data enrichment cache (TTL=6h)
        with topic+industry keys
- 21.3  Cache invalidation on prompt version update, provider config change,
        and schema version bump
- 21.4  Cache warming background task for top topics per industry
- 21.5  Cache analytics tracking hit rate, storage bytes, and cost savings
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Optional

import structlog

from app.services.redis_cache import redis_cache

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# TTL constants
# ---------------------------------------------------------------------------

SLIDE_JSON_TTL_SECONDS = 21600       # 6 hours — final Slide_JSON
RESEARCH_CACHE_TTL_SECONDS = 21600   # 6 hours — research findings
ENRICHMENT_CACHE_TTL_SECONDS = 21600 # 6 hours — data enrichment
ANALYTICS_TTL_SECONDS = 86400        # 24 hours — analytics counters

# ---------------------------------------------------------------------------
# Key prefixes
# ---------------------------------------------------------------------------

PREFIX_SLIDE_JSON = "slide_json"
PREFIX_RESEARCH = "research"
PREFIX_ENRICHMENT = "enrichment"
PREFIX_ANALYTICS_HITS = "cache_analytics:hits"
PREFIX_ANALYTICS_MISSES = "cache_analytics:misses"
PREFIX_ANALYTICS_COST_SAVED = "cache_analytics:cost_saved"
PREFIX_ANALYTICS_BYTES = "cache_analytics:bytes"

# Estimated cost saved per cache hit (USD) — based on average LLM call cost
ESTIMATED_COST_PER_GENERATION_USD = 0.05


# ---------------------------------------------------------------------------
# 21.1  Composite cache key helpers
# ---------------------------------------------------------------------------

def _make_slide_json_key(
    topic: str,
    industry: str,
    theme: str,
    provider_config_hash: str,
    prompt_version: str,
) -> str:
    """
    Build a composite SHA-256 cache key for final Slide_JSON.

    Key components:
      - topic            : normalised (stripped, lower-cased)
      - industry         : normalised
      - theme            : mckinsey | deloitte | dark_modern
      - provider_config_hash : sha256 of provider type + model name
      - prompt_version   : e.g. "1.0.0"
    """
    raw = "|".join([
        topic.strip().lower(),
        industry.strip().lower(),
        theme.strip().lower(),
        provider_config_hash,
        prompt_version,
    ])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{PREFIX_SLIDE_JSON}:{digest}"


def _make_research_key(topic: str, industry: str) -> str:
    """Cache key for research findings: sha256(topic + industry)."""
    raw = f"{topic.strip().lower()}|{industry.strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{PREFIX_RESEARCH}:{digest}"


def _make_enrichment_key(topic: str, industry: str) -> str:
    """Cache key for data enrichment: sha256(topic + industry)."""
    raw = f"{topic.strip().lower()}|{industry.strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{PREFIX_ENRICHMENT}:{digest}"


def compute_provider_config_hash(provider_type: str, model_name: str = "") -> str:
    """
    Compute a short hash representing the active provider configuration.

    Used as part of the composite Slide_JSON cache key so that changing
    the provider or model automatically busts the cache.
    """
    raw = f"{provider_type.strip().lower()}|{model_name.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 21.5  Analytics helpers
# ---------------------------------------------------------------------------

async def _increment_analytics(key: str, amount: float = 1.0) -> None:
    """Increment a float analytics counter in Redis."""
    try:
        client = redis_cache._client
        if client:
            await client.incrbyfloat(key, amount)
            # Set TTL only on first creation (TTL = -1 means no expiry set yet)
            ttl = await client.ttl(key)
            if ttl == -1:
                await client.expire(key, ANALYTICS_TTL_SECONDS)
    except Exception as exc:
        logger.debug("analytics_increment_failed", key=key, error=str(exc))


async def _get_analytics_value(key: str) -> float:
    """Read a float analytics counter from Redis."""
    try:
        raw = await redis_cache.get(key)
        if raw is None:
            return 0.0
        return float(raw)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Main cache service
# ---------------------------------------------------------------------------

class PresentationCacheService:
    """
    Caching layer for the presentation pipeline.

    Provides:
    - get/set for final Slide_JSON with composite key (21.1)
    - get/set for research and enrichment intermediate results (21.2)
    - invalidation helpers for prompt/provider/schema changes (21.3)
    - cache warming for top topics (21.4)
    - analytics: hit rate, bytes stored, cost savings (21.5)
    """

    # ------------------------------------------------------------------ #
    # 21.1  Final Slide_JSON cache                                         #
    # ------------------------------------------------------------------ #

    async def get_slide_json(
        self,
        topic: str,
        industry: str,
        theme: str,
        provider_config_hash: str,
        prompt_version: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached Slide_JSON.

        Returns the cached dict on hit, None on miss.
        Updates analytics counters.
        """
        key = _make_slide_json_key(topic, industry, theme, provider_config_hash, prompt_version)
        result = await redis_cache.get(key)

        if result is not None:
            logger.info(
                "slide_json_cache_hit",
                topic=topic[:60],
                industry=industry,
                theme=theme,
            )
            await _increment_analytics(PREFIX_ANALYTICS_HITS)
            await _increment_analytics(PREFIX_ANALYTICS_COST_SAVED, ESTIMATED_COST_PER_GENERATION_USD)
            return result

        logger.info(
            "slide_json_cache_miss",
            topic=topic[:60],
            industry=industry,
            theme=theme,
        )
        await _increment_analytics(PREFIX_ANALYTICS_MISSES)
        return None

    async def set_slide_json(
        self,
        topic: str,
        industry: str,
        theme: str,
        provider_config_hash: str,
        prompt_version: str,
        slide_json: Dict[str, Any],
    ) -> bool:
        """
        Store Slide_JSON in cache with 6-hour TTL.

        Also records approximate storage bytes in analytics.
        """
        key = _make_slide_json_key(topic, industry, theme, provider_config_hash, prompt_version)
        serialized = json.dumps(slide_json)
        byte_count = len(serialized.encode("utf-8"))

        success = await redis_cache.set(key, slide_json, ttl_seconds=SLIDE_JSON_TTL_SECONDS)

        if success:
            await _increment_analytics(PREFIX_ANALYTICS_BYTES, float(byte_count))
            logger.info(
                "slide_json_cached",
                topic=topic[:60],
                industry=industry,
                theme=theme,
                bytes=byte_count,
                ttl=SLIDE_JSON_TTL_SECONDS,
            )

        return success

    # ------------------------------------------------------------------ #
    # 21.2  Research cache (TTL=6h)                                        #
    # ------------------------------------------------------------------ #

    async def get_research(
        self,
        topic: str,
        industry: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached research findings for topic+industry."""
        key = _make_research_key(topic, industry)
        result = await redis_cache.get(key)

        if result is not None:
            logger.info("research_cache_hit", topic=topic[:60], industry=industry)
            await _increment_analytics(PREFIX_ANALYTICS_HITS)
            return result

        logger.info("research_cache_miss", topic=topic[:60], industry=industry)
        await _increment_analytics(PREFIX_ANALYTICS_MISSES)
        return None

    async def set_research(
        self,
        topic: str,
        industry: str,
        findings: Dict[str, Any],
    ) -> bool:
        """Store research findings with 6-hour TTL."""
        key = _make_research_key(topic, industry)
        success = await redis_cache.set(key, findings, ttl_seconds=RESEARCH_CACHE_TTL_SECONDS)

        if success:
            byte_count = len(json.dumps(findings).encode("utf-8"))
            await _increment_analytics(PREFIX_ANALYTICS_BYTES, float(byte_count))
            logger.info(
                "research_cached",
                topic=topic[:60],
                industry=industry,
                ttl=RESEARCH_CACHE_TTL_SECONDS,
            )

        return success

    # ------------------------------------------------------------------ #
    # 21.2  Data enrichment cache (TTL=6h)                                 #
    # ------------------------------------------------------------------ #

    async def get_enrichment(
        self,
        topic: str,
        industry: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached data enrichment for topic+industry."""
        key = _make_enrichment_key(topic, industry)
        result = await redis_cache.get(key)

        if result is not None:
            logger.info("enrichment_cache_hit", topic=topic[:60], industry=industry)
            await _increment_analytics(PREFIX_ANALYTICS_HITS)
            return result

        logger.info("enrichment_cache_miss", topic=topic[:60], industry=industry)
        await _increment_analytics(PREFIX_ANALYTICS_MISSES)
        return None

    async def set_enrichment(
        self,
        topic: str,
        industry: str,
        enriched_data: Dict[str, Any],
    ) -> bool:
        """Store data enrichment with 6-hour TTL."""
        key = _make_enrichment_key(topic, industry)
        success = await redis_cache.set(key, enriched_data, ttl_seconds=ENRICHMENT_CACHE_TTL_SECONDS)

        if success:
            byte_count = len(json.dumps(enriched_data).encode("utf-8"))
            await _increment_analytics(PREFIX_ANALYTICS_BYTES, float(byte_count))
            logger.info(
                "enrichment_cached",
                topic=topic[:60],
                industry=industry,
                ttl=ENRICHMENT_CACHE_TTL_SECONDS,
            )

        return success

    # ------------------------------------------------------------------ #
    # 21.3  Cache invalidation                                             #
    # ------------------------------------------------------------------ #

    async def invalidate_on_prompt_version_update(
        self,
        new_prompt_version: str,
    ) -> int:
        """
        Invalidate all Slide_JSON cache entries when the prompt version changes.

        Because the prompt version is baked into the composite key, simply
        scanning for the old prefix and deleting is sufficient.  All keys
        with the old version will no longer be reachable via the new key.

        Returns the number of keys deleted.
        """
        return await self._delete_by_prefix(PREFIX_SLIDE_JSON)

    async def invalidate_on_provider_config_change(self) -> int:
        """
        Invalidate all Slide_JSON cache entries when the provider config changes.

        The provider_config_hash component of the key changes automatically,
        so old entries become unreachable.  This method proactively removes
        stale entries to free memory.

        Returns the number of keys deleted.
        """
        return await self._delete_by_prefix(PREFIX_SLIDE_JSON)

    async def invalidate_on_schema_version_bump(self) -> int:
        """
        Invalidate ALL cache entries (Slide_JSON + research + enrichment)
        when the Slide_JSON schema version is bumped.

        A schema change means cached data may be structurally incompatible.

        Returns the total number of keys deleted.
        """
        deleted = 0
        deleted += await self._delete_by_prefix(PREFIX_SLIDE_JSON)
        deleted += await self._delete_by_prefix(PREFIX_RESEARCH)
        deleted += await self._delete_by_prefix(PREFIX_ENRICHMENT)
        logger.info("cache_invalidated_schema_bump", deleted_keys=deleted)
        return deleted

    async def invalidate_presentation(self, presentation_id: str) -> int:
        """
        Invalidate all cache entries associated with a specific presentation.

        Scans for keys that contain the presentation_id in their value
        (stored as metadata) — or simply clears all slide_json keys as a
        conservative approach when the presentation_id is not embedded in
        the key itself.

        For targeted invalidation, callers should use the topic/industry/theme
        parameters directly via the delete_slide_json helper.
        """
        # Scan for any key whose stored JSON contains this presentation_id
        client = redis_cache._client
        if not client:
            return 0

        deleted = 0
        try:
            async for key in client.scan_iter(match=f"{PREFIX_SLIDE_JSON}:*"):
                try:
                    raw = await client.get(key)
                    if raw and presentation_id in raw:
                        await client.delete(key)
                        deleted += 1
                except Exception:
                    pass
        except Exception as exc:
            logger.error("invalidate_presentation_failed", error=str(exc))

        logger.info(
            "presentation_cache_invalidated",
            presentation_id=presentation_id,
            deleted_keys=deleted,
        )
        return deleted

    async def _delete_by_prefix(self, prefix: str) -> int:
        """Delete all Redis keys matching prefix:*. Returns count deleted."""
        client = redis_cache._client
        if not client:
            return 0

        keys: List[str] = []
        try:
            async for key in client.scan_iter(match=f"{prefix}:*"):
                keys.append(key)

            if keys:
                await client.delete(*keys)

            logger.info("cache_prefix_deleted", prefix=prefix, count=len(keys))
            return len(keys)

        except Exception as exc:
            logger.error("cache_delete_by_prefix_failed", prefix=prefix, error=str(exc))
            return 0

    # ------------------------------------------------------------------ #
    # 21.4  Cache warming                                                  #
    # ------------------------------------------------------------------ #

    async def warm_cache_for_topics(
        self,
        topics_by_industry: Dict[str, List[str]],
        provider_type: str,
        model_name: str,
        prompt_version: str,
        theme: str = "mckinsey",
    ) -> Dict[str, int]:
        """
        Warm the cache for a set of top topics per industry.

        For each topic, checks whether a Slide_JSON cache entry already
        exists.  If not, it enqueues a generation job via Celery so the
        result will be cached after the pipeline completes.

        Args:
            topics_by_industry: Mapping of industry → list of topics to warm
            provider_type:      Active LLM provider type string
            model_name:         Active model name
            prompt_version:     Current prompt version
            theme:              Default theme to use for warming

        Returns:
            Dict with "already_cached" and "enqueued" counts.
        """
        provider_config_hash = compute_provider_config_hash(provider_type, model_name)
        already_cached = 0
        enqueued = 0

        for industry, topics in topics_by_industry.items():
            for topic in topics:
                key = _make_slide_json_key(
                    topic, industry, theme, provider_config_hash, prompt_version
                )
                exists = await redis_cache.exists(key)

                if exists:
                    already_cached += 1
                    logger.debug(
                        "cache_warm_already_cached",
                        topic=topic[:60],
                        industry=industry,
                    )
                    continue

                # Enqueue a generation job to populate the cache
                try:
                    from app.worker.tasks import generate_presentation_task
                    import uuid as _uuid

                    # Use a synthetic presentation_id for warming jobs
                    warm_presentation_id = str(_uuid.uuid4())

                    generate_presentation_task.apply_async(
                        kwargs={
                            "presentation_id": warm_presentation_id,
                            "topic": topic,
                            "tenant_id": "system",
                            "idempotency_key": f"warm:{industry}:{hashlib.sha256(topic.encode()).hexdigest()[:8]}",
                        },
                        queue="default",
                    )
                    enqueued += 1
                    logger.info(
                        "cache_warm_enqueued",
                        topic=topic[:60],
                        industry=industry,
                    )

                except Exception as exc:
                    logger.warning(
                        "cache_warm_enqueue_failed",
                        topic=topic[:60],
                        industry=industry,
                        error=str(exc),
                    )

        logger.info(
            "cache_warming_complete",
            already_cached=already_cached,
            enqueued=enqueued,
        )
        return {"already_cached": already_cached, "enqueued": enqueued}

    # ------------------------------------------------------------------ #
    # 21.5  Cache analytics                                                #
    # ------------------------------------------------------------------ #

    async def get_analytics(self) -> Dict[str, Any]:
        """
        Return cache analytics: hit rate, storage bytes, and cost savings.

        Counters are stored in Redis and reset every 24 hours.
        """
        hits = await _get_analytics_value(PREFIX_ANALYTICS_HITS)
        misses = await _get_analytics_value(PREFIX_ANALYTICS_MISSES)
        cost_saved = await _get_analytics_value(PREFIX_ANALYTICS_COST_SAVED)
        bytes_stored = await _get_analytics_value(PREFIX_ANALYTICS_BYTES)

        total = hits + misses
        hit_rate = (hits / total) if total > 0 else 0.0

        return {
            "hits": int(hits),
            "misses": int(misses),
            "total_requests": int(total),
            "hit_rate": round(hit_rate, 4),
            "hit_rate_percent": round(hit_rate * 100, 2),
            "cost_saved_usd": round(cost_saved, 4),
            "storage_bytes": int(bytes_stored),
            "storage_mb": round(bytes_stored / (1024 * 1024), 3),
        }

    async def reset_analytics(self) -> None:
        """Reset all analytics counters (e.g. at start of a new day)."""
        client = redis_cache._client
        if not client:
            return
        try:
            for key in [
                PREFIX_ANALYTICS_HITS,
                PREFIX_ANALYTICS_MISSES,
                PREFIX_ANALYTICS_COST_SAVED,
                PREFIX_ANALYTICS_BYTES,
            ]:
                await client.delete(key)
            logger.info("cache_analytics_reset")
        except Exception as exc:
            logger.error("cache_analytics_reset_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

presentation_cache = PresentationCacheService()
