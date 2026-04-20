"""
Background Health Monitor Task

Periodically checks provider health and persists metrics to database.
Handles automatic primary provider restoration.
"""

import asyncio
from datetime import datetime

import structlog

from app.services.provider_health import health_monitor
from app.services.redis_cache import redis_cache


logger = structlog.get_logger(__name__)


class HealthMonitorTask:
    """
    Background task for health monitoring and metric persistence.
    
    Responsibilities:
    - Update Redis cache every 30 seconds
    - Persist metrics to database every 5 minutes
    - Check for primary provider restoration
    """
    
    def __init__(
        self,
        cache_update_interval: int = 30,
        db_persist_interval: int = 300,
    ):
        self.cache_update_interval = cache_update_interval
        self.db_persist_interval = db_persist_interval
        self._running = False
        self._task: asyncio.Task = None
    
    async def start(self) -> None:
        """Start the background health monitoring task"""
        if self._running:
            logger.warning("health_monitor_task_already_running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(
            "health_monitor_task_started",
            cache_interval=self.cache_update_interval,
            db_interval=self.db_persist_interval,
        )
    
    async def stop(self) -> None:
        """Stop the background health monitoring task"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("health_monitor_task_stopped")
    
    async def _run(self) -> None:
        """Main task loop"""
        last_cache_update = datetime.utcnow()
        last_db_persist = datetime.utcnow()
        
        while self._running:
            try:
                now = datetime.utcnow()
                
                # Update cache every 30 seconds
                if (now - last_cache_update).total_seconds() >= self.cache_update_interval:
                    await self._update_cache()
                    last_cache_update = now
                
                # Persist to DB every 5 minutes
                if (now - last_db_persist).total_seconds() >= self.db_persist_interval:
                    await self._persist_metrics()
                    last_db_persist = now
                
                # Check for primary provider restoration
                await self._check_restoration()
                
                # Sleep for a short interval
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_monitor_task_error", error=str(e))
                await asyncio.sleep(5)
    
    async def _update_cache(self) -> None:
        """Update Redis cache with current health metrics"""
        try:
            await health_monitor.update_health_cache()
            logger.debug("health_cache_updated_by_task")
        except Exception as e:
            logger.error("health_cache_update_failed", error=str(e))
    
    async def _persist_metrics(self) -> None:
        """Persist health metrics to database"""
        try:
            await health_monitor.persist_health_metrics()
            logger.info("health_metrics_persisted_by_task")
        except Exception as e:
            logger.error("health_metrics_persist_failed", error=str(e))
    
    async def _check_restoration(self) -> None:
        """Check if primary provider should be restored"""
        try:
            if health_monitor.should_restore_primary():
                primary = health_monitor.primary_provider
                if primary:
                    # Close circuit if open
                    metrics = health_monitor.metrics[primary]
                    if metrics.circuit_open:
                        metrics.close_circuit()
                    
                    # Restore primary
                    health_monitor.current_provider = primary
                    health_monitor.failover_active = False
                    
                    logger.info(
                        "primary_provider_restored_by_task",
                        provider=primary.value,
                        success_rate=metrics.get_success_rate(),
                    )
                    
                    # Invalidate cache to force refresh
                    await redis_cache.invalidate_provider_health(primary.value)
        
        except Exception as e:
            logger.error("restoration_check_failed", error=str(e))


# Global health monitor task instance
health_monitor_task = HealthMonitorTask()
