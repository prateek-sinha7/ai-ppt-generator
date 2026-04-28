"""
Tests for the Caching Layer (Task 21).

Covers:
- 21.1  Composite cache key generation (sha256 determinism)
- 21.2  Research and enrichment cache get/set with TTL
- 21.3  Cache invalidation on prompt version, provider config, schema bump
- 21.4  Cache warming logic
- 21.5  Analytics: hit rate, storage bytes, cost savings
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.presentation_cache import (
    PresentationCacheService,
    _make_slide_json_key,
    _make_research_key,
    _make_enrichment_key,
    compute_provider_config_hash,
    PREFIX_SLIDE_JSON,
    PREFIX_RESEARCH,
    PREFIX_ENRICHMENT,
    SLIDE_JSON_TTL_SECONDS,
    RESEARCH_CACHE_TTL_SECONDS,
    ENRICHMENT_CACHE_TTL_SECONDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache_service() -> PresentationCacheService:
    return PresentationCacheService()


@pytest.fixture
def sample_slide_json() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "presentation_id": "test-123",
        "total_slides": 3,
        "slides": [
            {
                "slide_id": "s1",
                "slide_number": 1,
                "type": "title",
                "title": "Test Presentation",
                "content": {},
                "visual_hint": "centered",
            }
        ],
    }


@pytest.fixture
def sample_research() -> Dict[str, Any]:
    return {
        "topic": "AI in Healthcare",
        "industry": "healthcare",
        "sections": ["Overview", "Challenges", "Opportunities"],
        "risks": ["Data privacy", "Regulatory compliance"],
        "opportunities": ["Improved outcomes", "Cost reduction"],
        "terminology": ["EHR", "clinical pathways"],
        "context_summary": "AI is transforming healthcare.",
        "method": "llm",
    }


@pytest.fixture
def sample_enrichment() -> Dict[str, Any]:
    return {
        "topic": "AI in Healthcare",
        "industry": "healthcare",
        "seed": 12345,
        "topic_hash": "abc123",
        "charts": [],
        "tables": [],
        "key_metrics": {"patient_satisfaction": 85.0},
        "data_sources": ["Industry benchmarks"],
        "methodology_notes": "Seed-based generation.",
    }


# ---------------------------------------------------------------------------
# 21.1  Composite cache key tests
# ---------------------------------------------------------------------------

class TestCompositeKeyGeneration:
    """Verify the composite Slide_JSON cache key is deterministic and unique."""

    def test_key_is_deterministic(self):
        """Same inputs always produce the same key."""
        key1 = _make_slide_json_key("AI in Healthcare", "healthcare", "ocean-depths", "abc123", "1.0.0")
        key2 = _make_slide_json_key("AI in Healthcare", "healthcare", "ocean-depths", "abc123", "1.0.0")
        assert key1 == key2

    def test_key_starts_with_prefix(self):
        key = _make_slide_json_key("topic", "industry", "theme", "hash", "1.0.0")
        assert key.startswith(f"{PREFIX_SLIDE_JSON}:")

    def test_different_topics_produce_different_keys(self):
        key1 = _make_slide_json_key("Topic A", "healthcare", "ocean-depths", "abc", "1.0.0")
        key2 = _make_slide_json_key("Topic B", "healthcare", "ocean-depths", "abc", "1.0.0")
        assert key1 != key2

    def test_different_industries_produce_different_keys(self):
        key1 = _make_slide_json_key("topic", "healthcare", "ocean-depths", "abc", "1.0.0")
        key2 = _make_slide_json_key("topic", "finance", "ocean-depths", "abc", "1.0.0")
        assert key1 != key2

    def test_different_themes_produce_different_keys(self):
        key1 = _make_slide_json_key("topic", "healthcare", "ocean-depths", "abc", "1.0.0")
        key2 = _make_slide_json_key("topic", "healthcare", "modern-minimalist", "abc", "1.0.0")
        assert key1 != key2

    def test_different_provider_hashes_produce_different_keys(self):
        key1 = _make_slide_json_key("topic", "healthcare", "ocean-depths", "hash_claude", "1.0.0")
        key2 = _make_slide_json_key("topic", "healthcare", "ocean-depths", "hash_openai", "1.0.0")
        assert key1 != key2

    def test_different_prompt_versions_produce_different_keys(self):
        key1 = _make_slide_json_key("topic", "healthcare", "ocean-depths", "abc", "1.0.0")
        key2 = _make_slide_json_key("topic", "healthcare", "ocean-depths", "abc", "1.1.0")
        assert key1 != key2

    def test_topic_normalisation_case_insensitive(self):
        """Topic is normalised to lowercase before hashing."""
        key1 = _make_slide_json_key("AI in Healthcare", "healthcare", "ocean-depths", "abc", "1.0.0")
        key2 = _make_slide_json_key("ai in healthcare", "healthcare", "ocean-depths", "abc", "1.0.0")
        assert key1 == key2

    def test_topic_normalisation_strips_whitespace(self):
        key1 = _make_slide_json_key("  AI in Healthcare  ", "healthcare", "ocean-depths", "abc", "1.0.0")
        key2 = _make_slide_json_key("AI in Healthcare", "healthcare", "ocean-depths", "abc", "1.0.0")
        assert key1 == key2

    def test_key_contains_sha256_hex_digest(self):
        """The part after the prefix should be a 64-char hex string."""
        key = _make_slide_json_key("topic", "industry", "theme", "hash", "1.0.0")
        digest_part = key.split(":", 1)[1]
        assert len(digest_part) == 64
        assert all(c in "0123456789abcdef" for c in digest_part)

    def test_provider_config_hash_helper(self):
        h1 = compute_provider_config_hash("claude", "claude-3-5-sonnet")
        h2 = compute_provider_config_hash("claude", "claude-3-5-sonnet")
        assert h1 == h2
        assert len(h1) == 16  # truncated to 16 chars

    def test_provider_config_hash_differs_by_provider(self):
        h1 = compute_provider_config_hash("claude")
        h2 = compute_provider_config_hash("openai")
        assert h1 != h2


# ---------------------------------------------------------------------------
# 21.2  Research and enrichment cache tests
# ---------------------------------------------------------------------------

class TestResearchCache:
    """Verify research cache get/set with correct TTL."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache_service):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis._client = None

            result = await cache_service.get_research("topic", "healthcare")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_data(self, cache_service, sample_research):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=sample_research)
            mock_redis._client = None

            result = await cache_service.get_research("AI in Healthcare", "healthcare")
            assert result == sample_research

    @pytest.mark.asyncio
    async def test_set_research_uses_correct_ttl(self, cache_service, sample_research):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis._client = None

            await cache_service.set_research("topic", "healthcare", sample_research)

            mock_redis.set.assert_called_once()
            call_kwargs = mock_redis.set.call_args
            assert call_kwargs[1]["ttl_seconds"] == RESEARCH_CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_research_key_uses_topic_and_industry(self, cache_service, sample_research):
        """The cache key must inOcean Depths both topic and industry."""
        key1 = _make_research_key("topic A", "healthcare")
        key2 = _make_research_key("topic A", "finance")
        key3 = _make_research_key("topic B", "healthcare")

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    @pytest.mark.asyncio
    async def test_research_key_starts_with_prefix(self):
        key = _make_research_key("topic", "industry")
        assert key.startswith(f"{PREFIX_RESEARCH}:")


class TestEnrichmentCache:
    """Verify data enrichment cache get/set with correct TTL."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache_service):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis._client = None

            result = await cache_service.get_enrichment("topic", "healthcare")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_data(self, cache_service, sample_enrichment):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=sample_enrichment)
            mock_redis._client = None

            result = await cache_service.get_enrichment("topic", "healthcare")
            assert result == sample_enrichment

    @pytest.mark.asyncio
    async def test_set_enrichment_uses_correct_ttl(self, cache_service, sample_enrichment):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis._client = None

            await cache_service.set_enrichment("topic", "healthcare", sample_enrichment)

            mock_redis.set.assert_called_once()
            call_kwargs = mock_redis.set.call_args
            assert call_kwargs[1]["ttl_seconds"] == ENRICHMENT_CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_enrichment_key_starts_with_prefix(self):
        key = _make_enrichment_key("topic", "industry")
        assert key.startswith(f"{PREFIX_ENRICHMENT}:")


class TestSlideJsonCache:
    """Verify final Slide_JSON cache get/set."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache_service):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis._client = None

            result = await cache_service.get_slide_json(
                "topic", "healthcare", "ocean-depths", "hash", "1.0.0"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_data(self, cache_service, sample_slide_json):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=sample_slide_json)
            mock_redis._client = None

            result = await cache_service.get_slide_json(
                "topic", "healthcare", "ocean-depths", "hash", "1.0.0"
            )
            assert result == sample_slide_json

    @pytest.mark.asyncio
    async def test_set_slide_json_uses_correct_ttl(self, cache_service, sample_slide_json):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis._client = None

            await cache_service.set_slide_json(
                "topic", "healthcare", "ocean-depths", "hash", "1.0.0", sample_slide_json
            )

            mock_redis.set.assert_called_once()
            call_kwargs = mock_redis.set.call_args
            assert call_kwargs[1]["ttl_seconds"] == SLIDE_JSON_TTL_SECONDS


# ---------------------------------------------------------------------------
# 21.3  Cache invalidation tests
# ---------------------------------------------------------------------------

class TestCacheInvalidation:
    """Verify cache invalidation on prompt version, provider config, schema bump."""

    @pytest.mark.asyncio
    async def test_invalidate_on_prompt_version_deletes_slide_json_keys(self, cache_service):
        with patch.object(cache_service, "_delete_by_prefix", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = 5
            deleted = await cache_service.invalidate_on_prompt_version_update("1.1.0")
            mock_del.assert_called_once_with(PREFIX_SLIDE_JSON)
            assert deleted == 5

    @pytest.mark.asyncio
    async def test_invalidate_on_provider_config_deletes_slide_json_keys(self, cache_service):
        with patch.object(cache_service, "_delete_by_prefix", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = 3
            deleted = await cache_service.invalidate_on_provider_config_change()
            mock_del.assert_called_once_with(PREFIX_SLIDE_JSON)
            assert deleted == 3

    @pytest.mark.asyncio
    async def test_invalidate_on_schema_bump_deletes_all_prefixes(self, cache_service):
        """Schema bump must clear Slide_JSON + research + enrichment caches."""
        call_counts: Dict[str, int] = {}

        async def mock_delete(prefix: str) -> int:
            call_counts[prefix] = call_counts.get(prefix, 0) + 1
            return 2

        with patch.object(cache_service, "_delete_by_prefix", side_effect=mock_delete):
            deleted = await cache_service.invalidate_on_schema_version_bump()

        assert PREFIX_SLIDE_JSON in call_counts
        assert PREFIX_RESEARCH in call_counts
        assert PREFIX_ENRICHMENT in call_counts
        assert deleted == 6  # 2 per prefix × 3 prefixes

    @pytest.mark.asyncio
    async def test_delete_by_prefix_returns_zero_when_no_client(self, cache_service):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis._client = None
            result = await cache_service._delete_by_prefix(PREFIX_SLIDE_JSON)
            assert result == 0

    @pytest.mark.asyncio
    async def test_delete_by_prefix_deletes_matching_keys(self, cache_service):
        mock_client = AsyncMock()
        mock_client.scan_iter = MagicMock()

        async def fake_scan(match):
            for key in [f"{PREFIX_SLIDE_JSON}:abc", f"{PREFIX_SLIDE_JSON}:def"]:
                yield key

        mock_client.scan_iter.return_value = fake_scan(match=f"{PREFIX_SLIDE_JSON}:*")
        mock_client.delete = AsyncMock(return_value=2)

        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis._client = mock_client
            result = await cache_service._delete_by_prefix(PREFIX_SLIDE_JSON)

        assert result == 2
        mock_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# 21.5  Analytics tests
# ---------------------------------------------------------------------------

class TestCacheAnalytics:
    """Verify analytics tracking: hit rate, storage bytes, cost savings."""

    @pytest.mark.asyncio
    async def test_get_analytics_returns_expected_shape(self, cache_service):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis._client = None

            analytics = await cache_service.get_analytics()

        assert "hits" in analytics
        assert "misses" in analytics
        assert "total_requests" in analytics
        assert "hit_rate" in analytics
        assert "hit_rate_percent" in analytics
        assert "cost_saved_usd" in analytics
        assert "storage_bytes" in analytics
        assert "storage_mb" in analytics

    @pytest.mark.asyncio
    async def test_hit_rate_zero_when_no_requests(self, cache_service):
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis._client = None

            analytics = await cache_service.get_analytics()

        assert analytics["hit_rate"] == 0.0
        assert analytics["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_hit_increments_on_cache_hit(self, cache_service, sample_slide_json):
        """A cache hit should increment the hits counter."""
        increment_calls = []

        async def mock_increment(key: str, amount: float = 1.0) -> None:
            increment_calls.append((key, amount))

        with patch("app.services.presentation_cache.redis_cache") as mock_redis, \
             patch("app.services.presentation_cache._increment_analytics", side_effect=mock_increment):
            mock_redis.get = AsyncMock(return_value=sample_slide_json)
            mock_redis._client = None

            await cache_service.get_slide_json(
                "topic", "healthcare", "ocean-depths", "hash", "1.0.0"
            )

        hit_keys = [k for k, _ in increment_calls]
        from app.services.presentation_cache import PREFIX_ANALYTICS_HITS, PREFIX_ANALYTICS_COST_SAVED
        assert PREFIX_ANALYTICS_HITS in hit_keys
        assert PREFIX_ANALYTICS_COST_SAVED in hit_keys

    @pytest.mark.asyncio
    async def test_miss_increments_on_cache_miss(self, cache_service):
        """A cache miss should increment the misses counter."""
        increment_calls = []

        async def mock_increment(key: str, amount: float = 1.0) -> None:
            increment_calls.append((key, amount))

        with patch("app.services.presentation_cache.redis_cache") as mock_redis, \
             patch("app.services.presentation_cache._increment_analytics", side_effect=mock_increment):
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis._client = None

            await cache_service.get_slide_json(
                "topic", "healthcare", "ocean-depths", "hash", "1.0.0"
            )

        miss_keys = [k for k, _ in increment_calls]
        from app.services.presentation_cache import PREFIX_ANALYTICS_MISSES
        assert PREFIX_ANALYTICS_MISSES in miss_keys

    @pytest.mark.asyncio
    async def test_bytes_tracked_on_set(self, cache_service, sample_slide_json):
        """Setting a value should record the byte count in analytics."""
        increment_calls = []

        async def mock_increment(key: str, amount: float = 1.0) -> None:
            increment_calls.append((key, amount))

        with patch("app.services.presentation_cache.redis_cache") as mock_redis, \
             patch("app.services.presentation_cache._increment_analytics", side_effect=mock_increment):
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis._client = None

            await cache_service.set_slide_json(
                "topic", "healthcare", "ocean-depths", "hash", "1.0.0", sample_slide_json
            )

        from app.services.presentation_cache import PREFIX_ANALYTICS_BYTES
        byte_calls = [(k, v) for k, v in increment_calls if k == PREFIX_ANALYTICS_BYTES]
        assert len(byte_calls) == 1
        # Byte count should be positive
        assert byte_calls[0][1] > 0

    @pytest.mark.asyncio
    async def test_analytics_hit_rate_calculation(self, cache_service):
        """hit_rate = hits / (hits + misses)."""
        with patch("app.services.presentation_cache._get_analytics_value") as mock_get:
            # Simulate 3 hits, 1 miss
            async def fake_get(key: str) -> float:
                from app.services.presentation_cache import (
                    PREFIX_ANALYTICS_HITS,
                    PREFIX_ANALYTICS_MISSES,
                    PREFIX_ANALYTICS_COST_SAVED,
                    PREFIX_ANALYTICS_BYTES,
                )
                return {
                    PREFIX_ANALYTICS_HITS: 3.0,
                    PREFIX_ANALYTICS_MISSES: 1.0,
                    PREFIX_ANALYTICS_COST_SAVED: 0.15,
                    PREFIX_ANALYTICS_BYTES: 1024.0,
                }.get(key, 0.0)

            mock_get.side_effect = fake_get

            analytics = await cache_service.get_analytics()

        assert analytics["hits"] == 3
        assert analytics["misses"] == 1
        assert analytics["total_requests"] == 4
        assert analytics["hit_rate"] == pytest.approx(0.75, abs=0.001)
        assert analytics["hit_rate_percent"] == pytest.approx(75.0, abs=0.01)
        assert analytics["cost_saved_usd"] == pytest.approx(0.15, abs=0.001)


# ---------------------------------------------------------------------------
# 21.4  Cache warming tests
# ---------------------------------------------------------------------------

class TestCacheWarming:
    """Verify cache warming logic."""

    @pytest.mark.asyncio
    async def test_warm_skips_already_cached_topics(self, cache_service):
        """Topics already in cache should not be re-enqueued."""
        with patch("app.services.presentation_cache.redis_cache") as mock_redis:
            mock_redis.exists = AsyncMock(return_value=True)

            result = await cache_service.warm_cache_for_topics(
                topics_by_industry={"healthcare": ["AI in Healthcare"]},
                provider_type="claude",
                model_name="",
                prompt_version="1.0.0",
            )

        assert result["already_cached"] == 1
        assert result["enqueued"] == 0

    @pytest.mark.asyncio
    async def test_warm_enqueues_uncached_topics(self, cache_service):
        """Topics not in cache should be enqueued for generation."""
        with patch("app.services.presentation_cache.redis_cache") as mock_redis, \
             patch("app.worker.tasks.generate_presentation_task") as mock_task:
            mock_redis.exists = AsyncMock(return_value=False)
            mock_task.apply_async = MagicMock()

            result = await cache_service.warm_cache_for_topics(
                topics_by_industry={"healthcare": ["AI in Healthcare", "Digital Health"]},
                provider_type="claude",
                model_name="",
                prompt_version="1.0.0",
            )

        assert result["enqueued"] == 2
        assert result["already_cached"] == 0

    @pytest.mark.asyncio
    async def test_warm_handles_enqueue_failure_gracefully(self, cache_service):
        """Enqueue failures should not raise — just log and continue."""
        with patch("app.services.presentation_cache.redis_cache") as mock_redis, \
             patch("app.worker.tasks.generate_presentation_task") as mock_task:
            mock_redis.exists = AsyncMock(return_value=False)
            mock_task.apply_async = MagicMock(side_effect=Exception("Celery unavailable"))

            # Should not raise
            result = await cache_service.warm_cache_for_topics(
                topics_by_industry={"healthcare": ["AI in Healthcare"]},
                provider_type="claude",
                model_name="",
                prompt_version="1.0.0",
            )

        assert result["enqueued"] == 0
        assert result["already_cached"] == 0
