"""
Cache Warming Background Task (21.4)

Periodically warms the presentation cache for the most-requested topics
per industry.  Runs as an asyncio background task alongside the FastAPI app.

Top topics are determined by scanning the presentations table for the most
frequently generated topics per industry over the last 7 days.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import structlog
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import async_session_maker

logger = structlog.get_logger(__name__)

# How often to run the warming cycle (seconds)
WARMING_INTERVAL_SECONDS = 3600  # every hour

# How many top topics to warm per industry
TOP_TOPICS_PER_INDUSTRY = 5

# Look-back window for determining "top" topics
LOOKBACK_DAYS = 7


class CacheWarmingTask:
    """
    Background task that warms the presentation cache for popular topics.

    Lifecycle:
      await cache_warming_task.start()   # called from app lifespan
      await cache_warming_task.stop()    # called on shutdown
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background warming loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="cache_warming")
        logger.info("cache_warming_task_started", interval_seconds=WARMING_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Stop the background warming loop gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("cache_warming_task_stopped")

    async def _loop(self) -> None:
        """Main warming loop — runs every WARMING_INTERVAL_SECONDS."""
        while self._running:
            try:
                await self._run_warming_cycle()
            except Exception as exc:
                logger.error("cache_warming_cycle_failed", error=str(exc))

            # Wait for next cycle (interruptible)
            try:
                await asyncio.sleep(WARMING_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

    async def _run_warming_cycle(self) -> None:
        """
        Fetch top topics per industry from the DB and warm the cache.
        """
        logger.info("cache_warming_cycle_started")

        topics_by_industry = await self._fetch_top_topics()

        if not topics_by_industry:
            logger.info("cache_warming_no_topics_found")
            return

        from app.services.presentation_cache import presentation_cache
        from app.agents.prompt_engineering import PromptEngineeringAgent

        provider_type = settings.LLM_PRIMARY_PROVIDER
        prompt_version = PromptEngineeringAgent.PROMPT_VERSION

        result = await presentation_cache.warm_cache_for_topics(
            topics_by_industry=topics_by_industry,
            provider_type=provider_type,
            model_name="",  # model name not tracked in settings; hash on type only
            prompt_version=prompt_version,
            theme="mckinsey",  # warm with the default theme
        )

        logger.info(
            "cache_warming_cycle_completed",
            industries=list(topics_by_industry.keys()),
            already_cached=result["already_cached"],
            enqueued=result["enqueued"],
        )

    async def _fetch_top_topics(self) -> Dict[str, List[str]]:
        """
        Query the presentations table for the most-generated topics per industry
        over the last LOOKBACK_DAYS days.

        Returns a dict mapping industry → list of top topic strings.
        """
        from app.db.models import Presentation, PresentationStatus

        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

        try:
            async with async_session_maker() as db:
                # Count how many times each (industry, topic) pair was generated
                stmt = (
                    select(
                        Presentation.detected_industry,
                        Presentation.topic,
                        func.count(Presentation.presentation_id).label("gen_count"),
                    )
                    .where(
                        Presentation.status == PresentationStatus.completed,
                        Presentation.detected_industry.isnot(None),
                        Presentation.created_at >= cutoff,
                    )
                    .group_by(Presentation.detected_industry, Presentation.topic)
                    .order_by(
                        Presentation.detected_industry,
                        func.count(Presentation.presentation_id).desc(),
                    )
                )
                result = await db.execute(stmt)
                rows = result.all()

        except Exception as exc:
            logger.error("cache_warming_db_query_failed", error=str(exc))
            return {}

        # Group by industry, keep top N topics
        topics_by_industry: Dict[str, List[str]] = {}
        for row in rows:
            industry = row.detected_industry
            topic = row.topic
            if industry not in topics_by_industry:
                topics_by_industry[industry] = []
            if len(topics_by_industry[industry]) < TOP_TOPICS_PER_INDUSTRY:
                topics_by_industry[industry].append(topic)

        logger.info(
            "cache_warming_top_topics_fetched",
            industries=len(topics_by_industry),
            total_topics=sum(len(v) for v in topics_by_industry.values()),
        )
        return topics_by_industry

    async def run_once(self) -> Dict[str, int]:
        """
        Manually trigger a single warming cycle (useful for admin endpoints).

        Returns the warming result dict.
        """
        topics_by_industry = await self._fetch_top_topics()

        if not topics_by_industry:
            return {"already_cached": 0, "enqueued": 0}

        from app.services.presentation_cache import presentation_cache
        from app.agents.prompt_engineering import PromptEngineeringAgent

        return await presentation_cache.warm_cache_for_topics(
            topics_by_industry=topics_by_industry,
            provider_type=settings.LLM_PRIMARY_PROVIDER,
            model_name="",
            prompt_version=PromptEngineeringAgent.PROMPT_VERSION,
            theme="mckinsey",
        )


# Global singleton
cache_warming_task = CacheWarmingTask()
