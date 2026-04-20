"""
Provider Health Monitor

Tracks response times, error rates, and availability for all LLM providers.
Implements automatic failover when primary provider health degrades.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
import random

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProviderConfig, ProviderHealthLog, ProviderType
from app.db.session import async_session_maker
from app.services.redis_cache import redis_cache


logger = structlog.get_logger(__name__)


class ProviderHealthMetrics:
    """Real-time health metrics for a single provider"""
    
    def __init__(self, provider_type: ProviderType, window_size: int = 100):
        self.provider_type = provider_type
        self.window_size = window_size
        
        # Sliding window of recent call results
        self.recent_calls: deque = deque(maxlen=window_size)
        
        # Metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_response_time_ms = 0.0
        
        # Timestamps
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
        self.last_health_check: Optional[datetime] = None
        
        # Circuit breaker state
        self.circuit_open = False
        self.circuit_opened_at: Optional[datetime] = None
    
    def record_call(self, success: bool, response_time_ms: float) -> None:
        """Record a provider call result"""
        self.total_calls += 1
        self.recent_calls.append((success, response_time_ms, datetime.utcnow()))
        
        if success:
            self.successful_calls += 1
            self.last_success = datetime.utcnow()
        else:
            self.failed_calls += 1
            self.last_failure = datetime.utcnow()
        
        self.total_response_time_ms += response_time_ms
    
    def get_success_rate(self) -> float:
        """Calculate success rate from recent calls"""
        if not self.recent_calls:
            return 1.0  # Assume healthy if no data
        
        successful = sum(1 for success, _, _ in self.recent_calls if success)
        return successful / len(self.recent_calls)
    
    def get_avg_response_time_ms(self) -> float:
        """Calculate average response time from recent calls"""
        if not self.recent_calls:
            return 0.0
        
        total_time = sum(time_ms for _, time_ms, _ in self.recent_calls)
        return total_time / len(self.recent_calls)
    
    def get_error_count(self) -> int:
        """Get error count from recent calls"""
        return sum(1 for success, _, _ in self.recent_calls if not success)
    
    def is_healthy(self, threshold: float = 0.95) -> bool:
        """Check if provider is healthy based on success rate threshold"""
        return self.get_success_rate() >= threshold
    
    def should_open_circuit(self, failure_threshold: float = 0.20) -> bool:
        """Check if circuit breaker should open (>20% failure rate)"""
        if len(self.recent_calls) < 10:  # Need minimum data
            return False
        
        failure_rate = 1.0 - self.get_success_rate()
        return failure_rate > failure_threshold
    
    def open_circuit(self) -> None:
        """Open circuit breaker"""
        self.circuit_open = True
        self.circuit_opened_at = datetime.utcnow()
        logger.warning(
            "circuit_breaker_opened",
            provider=self.provider_type.value,
            failure_rate=1.0 - self.get_success_rate(),
        )
    
    def close_circuit(self) -> None:
        """Close circuit breaker"""
        self.circuit_open = False
        self.circuit_opened_at = None
        logger.info(
            "circuit_breaker_closed",
            provider=self.provider_type.value,
        )
    
    def can_attempt_recovery(self, recovery_timeout_seconds: int = 60) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if not self.circuit_open or not self.circuit_opened_at:
            return True
        
        elapsed = (datetime.utcnow() - self.circuit_opened_at).total_seconds()
        return elapsed >= recovery_timeout_seconds


class ProviderHealthMonitor:
    """
    Monitors health of all LLM providers and manages failover decisions.
    
    Tracks:
    - Response times per provider
    - Error rates per provider
    - Availability status
    
    Implements:
    - Automatic failover when primary provider success rate < 95%
    - Circuit breaker pattern (>20% failure rate)
    - Automatic primary provider restoration
    """
    
    def __init__(self):
        self.metrics: Dict[ProviderType, ProviderHealthMetrics] = {}
        self.primary_provider: Optional[ProviderType] = None
        self.current_provider: Optional[ProviderType] = None
        self.failover_active = False
        
        # Initialize metrics for all provider types
        for provider_type in ProviderType:
            self.metrics[provider_type] = ProviderHealthMetrics(provider_type)
    
    def set_primary_provider(self, provider: ProviderType) -> None:
        """Set the primary provider"""
        self.primary_provider = provider
        self.current_provider = provider
        logger.info(
            "primary_provider_set",
            provider=provider.value,
        )
    
    def record_call(
        self,
        provider: ProviderType,
        success: bool,
        response_time_ms: float,
    ) -> None:
        """
        Record a provider call result and update health metrics.
        
        Args:
            provider: Provider that was called
            success: Whether the call succeeded
            response_time_ms: Response time in milliseconds
        """
        metrics = self.metrics[provider]
        metrics.record_call(success, response_time_ms)
        
        # Check if circuit breaker should open
        if metrics.should_open_circuit() and not metrics.circuit_open:
            metrics.open_circuit()
        
        logger.info(
            "provider_call_recorded",
            provider=provider.value,
            success=success,
            response_time_ms=response_time_ms,
            success_rate=metrics.get_success_rate(),
            circuit_open=metrics.circuit_open,
        )
        
        # 30.4 — Alert when provider error rate exceeds 5%
        try:
            from app.services.observability import observability as obs
            error_rate = 1.0 - metrics.get_success_rate()
            obs.check_provider_error_rate(provider.value, error_rate)
        except Exception:
            pass
    
    def get_health_status(self, provider: ProviderType) -> Dict:
        """Get current health status for a provider"""
        metrics = self.metrics[provider]
        
        return {
            "provider": provider.value,
            "success_rate": metrics.get_success_rate(),
            "avg_response_time_ms": metrics.get_avg_response_time_ms(),
            "error_count": metrics.get_error_count(),
            "total_calls": metrics.total_calls,
            "is_healthy": metrics.is_healthy(),
            "circuit_open": metrics.circuit_open,
            "last_success": metrics.last_success.isoformat() if metrics.last_success else None,
            "last_failure": metrics.last_failure.isoformat() if metrics.last_failure else None,
        }
    
    async def get_cached_health_status(self, provider: ProviderType) -> Optional[Dict]:
        """
        Get health status from cache (30-second TTL).
        Falls back to real-time metrics if cache miss.
        
        Args:
            provider: Provider to check
        
        Returns:
            Health status dictionary
        """
        # Try cache first
        cached = await redis_cache.get_provider_health(provider.value)
        if cached:
            logger.debug("health_status_cache_hit", provider=provider.value)
            return cached
        
        # Cache miss - get real-time metrics and cache them
        logger.debug("health_status_cache_miss", provider=provider.value)
        status = self.get_health_status(provider)
        await redis_cache.set_provider_health(provider.value, status, ttl_seconds=30)
        
        return status
    
    async def update_health_cache(self) -> None:
        """Update Redis cache with current health metrics for all providers"""
        for provider_type in ProviderType:
            status = self.get_health_status(provider_type)
            await redis_cache.set_provider_health(provider_type.value, status, ttl_seconds=30)
        
        logger.debug("health_cache_updated")
    
    def should_failover(self) -> bool:
        """
        Check if failover should occur.
        
        Returns True if:
        - Primary provider success rate < 95%
        - Primary provider circuit is open
        """
        if not self.primary_provider:
            return False
        
        primary_metrics = self.metrics[self.primary_provider]
        
        # Check success rate threshold
        if not primary_metrics.is_healthy(threshold=0.95):
            logger.warning(
                "primary_provider_unhealthy",
                provider=self.primary_provider.value,
                success_rate=primary_metrics.get_success_rate(),
            )
            return True
        
        # Check circuit breaker
        if primary_metrics.circuit_open:
            logger.warning(
                "primary_provider_circuit_open",
                provider=self.primary_provider.value,
            )
            return True
        
        return False
    
    def should_restore_primary(self) -> bool:
        """
        Check if primary provider should be restored.
        
        Returns True if:
        - Currently in failover mode
        - Primary provider is healthy again
        - Circuit breaker is closed or can attempt recovery
        """
        if not self.failover_active or not self.primary_provider:
            return False
        
        primary_metrics = self.metrics[self.primary_provider]
        
        # Check if circuit can be recovered
        if primary_metrics.circuit_open:
            if not primary_metrics.can_attempt_recovery():
                return False
        
        # Check if primary is healthy
        if primary_metrics.is_healthy(threshold=0.95):
            logger.info(
                "primary_provider_recovered",
                provider=self.primary_provider.value,
                success_rate=primary_metrics.get_success_rate(),
            )
            return True
        
        return False
    
    def select_provider(self, available_providers: List[ProviderType]) -> Optional[ProviderType]:
        """
        Select best available provider based on health metrics.
        
        Selection logic:
        1. If primary is healthy, use primary
        2. If failover needed, select healthiest available provider
        3. Skip providers with open circuit breakers (unless recovery timeout passed)
        
        Args:
            available_providers: List of configured providers
        
        Returns:
            Selected provider or None if all unavailable
        """
        if not available_providers:
            return None
        
        # Check if we should restore primary
        if self.should_restore_primary():
            primary_metrics = self.metrics[self.primary_provider]
            if primary_metrics.circuit_open:
                primary_metrics.close_circuit()
            self.current_provider = self.primary_provider
            self.failover_active = False
            logger.info(
                "primary_provider_restored",
                provider=self.primary_provider.value,
            )
            return self.primary_provider
        
        # Check if we should failover from primary
        if not self.failover_active and self.should_failover():
            self.failover_active = True
            logger.warning(
                "failover_activated",
                from_provider=self.primary_provider.value if self.primary_provider else None,
            )
        
        # If not in failover and primary is available, use primary
        if not self.failover_active and self.primary_provider in available_providers:
            return self.primary_provider
        
        # Select best available provider (excluding those with open circuits)
        candidates = []
        for provider in available_providers:
            metrics = self.metrics[provider]
            
            # Skip if circuit is open and can't recover yet
            if metrics.circuit_open and not metrics.can_attempt_recovery():
                continue
            
            candidates.append((provider, metrics.get_success_rate(), metrics.get_avg_response_time_ms()))
        
        if not candidates:
            # All circuits open, try primary anyway as last resort
            logger.error("all_providers_unavailable")
            return self.primary_provider if self.primary_provider in available_providers else available_providers[0]
        
        # Sort by success rate (desc), then by response time (asc)
        candidates.sort(key=lambda x: (-x[1], x[2]))
        selected = candidates[0][0]
        
        self.current_provider = selected
        logger.info(
            "provider_selected",
            provider=selected.value,
            success_rate=candidates[0][1],
            avg_response_time_ms=candidates[0][2],
        )
        
        return selected
    
    async def persist_health_metrics(self) -> None:
        """Persist current health metrics to database"""
        async with async_session_maker() as session:
            try:
                # Get all provider configs
                result = await session.execute(select(ProviderConfig))
                provider_configs = result.scalars().all()
                
                # Create health log entries
                for config in provider_configs:
                    metrics = self.metrics.get(config.provider_type)
                    if not metrics:
                        continue
                    
                    health_log = ProviderHealthLog(
                        provider_id=config.id,
                        success_rate=metrics.get_success_rate(),
                        avg_response_ms=metrics.get_avg_response_time_ms(),
                        error_count=metrics.get_error_count(),
                        checked_at=datetime.utcnow(),
                    )
                    session.add(health_log)
                
                await session.commit()
                logger.info("health_metrics_persisted")
                
            except Exception as e:
                logger.error("health_metrics_persist_failed", error=str(e))
                await session.rollback()


class ExponentialBackoffRetry:
    """
    Implements exponential backoff retry with jitter for provider failures.
    
    Retry delays: 2s, 4s, 8s, 16s, 32s (with jitter)
    """
    
    def __init__(
        self,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 32.0,
        max_retries: int = 5,
        jitter: bool = True,
    ):
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.max_retries = max_retries
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Retry attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        if attempt >= self.max_retries:
            return 0.0
        
        # Exponential backoff: base * 2^attempt
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            jitter_amount = delay * 0.25  # ±25% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0.0, delay)
    
    async def execute_with_retry(
        self,
        func,
        *args,
        on_retry=None,
        **kwargs,
    ) -> Tuple[bool, any]:
        """
        Execute function with exponential backoff retry.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            on_retry: Optional callback called on each retry
            **kwargs: Keyword arguments for func
        
        Returns:
            Tuple of (success, result)
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                return True, result
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    
                    logger.warning(
                        "retry_attempt",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        delay_seconds=delay,
                        error=str(e),
                    )
                    
                    if on_retry:
                        await on_retry(attempt, e)
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "retry_exhausted",
                        attempts=attempt + 1,
                        error=str(e),
                    )
        
        return False, last_error


# Global health monitor instance
health_monitor = ProviderHealthMonitor()
