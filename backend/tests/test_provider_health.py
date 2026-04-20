"""
Tests for Provider Health Monitor

Validates health tracking, failover logic, and automatic restoration.
"""

import pytest
from datetime import datetime, timedelta

from app.services.provider_health import (
    ProviderHealthMetrics,
    ProviderHealthMonitor,
    ExponentialBackoffRetry,
)
from app.db.models import ProviderType


class TestProviderHealthMetrics:
    """Test health metrics tracking"""
    
    def test_initial_state(self):
        """Test initial metrics state"""
        metrics = ProviderHealthMetrics(ProviderType.CLAUDE)
        
        assert metrics.provider_type == ProviderType.CLAUDE
        assert metrics.total_calls == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.get_success_rate() == 1.0  # Assume healthy with no data
        assert not metrics.circuit_open
    
    def test_record_successful_call(self):
        """Test recording successful calls"""
        metrics = ProviderHealthMetrics(ProviderType.CLAUDE)
        
        metrics.record_call(success=True, response_time_ms=100.0)
        
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.get_success_rate() == 1.0
        assert metrics.get_avg_response_time_ms() == 100.0
        assert metrics.last_success is not None
    
    def test_record_failed_call(self):
        """Test recording failed calls"""
        metrics = ProviderHealthMetrics(ProviderType.CLAUDE)
        
        metrics.record_call(success=False, response_time_ms=50.0)
        
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 1
        assert metrics.get_success_rate() == 0.0
        assert metrics.last_failure is not None
    
    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        metrics = ProviderHealthMetrics(ProviderType.CLAUDE)
        
        # 7 successes, 3 failures = 70% success rate
        for _ in range(7):
            metrics.record_call(success=True, response_time_ms=100.0)
        for _ in range(3):
            metrics.record_call(success=False, response_time_ms=100.0)
        
        assert metrics.get_success_rate() == 0.7
        assert not metrics.is_healthy(threshold=0.95)  # Below 95% threshold
    
    def test_circuit_breaker_opens(self):
        """Test circuit breaker opens on high failure rate"""
        metrics = ProviderHealthMetrics(ProviderType.CLAUDE, window_size=20)
        
        # Generate 25% failure rate (5 failures, 15 successes)
        for _ in range(15):
            metrics.record_call(success=True, response_time_ms=100.0)
        for _ in range(5):
            metrics.record_call(success=False, response_time_ms=100.0)
        
        assert metrics.should_open_circuit(failure_threshold=0.20)
        
        metrics.open_circuit()
        assert metrics.circuit_open
        assert metrics.circuit_opened_at is not None
    
    def test_sliding_window(self):
        """Test sliding window behavior"""
        metrics = ProviderHealthMetrics(ProviderType.CLAUDE, window_size=10)
        
        # Fill window with failures
        for _ in range(10):
            metrics.record_call(success=False, response_time_ms=100.0)
        
        assert metrics.get_success_rate() == 0.0
        
        # Add successes - old failures should slide out
        for _ in range(10):
            metrics.record_call(success=True, response_time_ms=100.0)
        
        assert metrics.get_success_rate() == 1.0


class TestProviderHealthMonitor:
    """Test health monitor and failover logic"""
    
    def test_initialization(self):
        """Test monitor initialization"""
        monitor = ProviderHealthMonitor()
        
        # Should have metrics for all provider types
        assert len(monitor.metrics) == len(ProviderType)
        for provider_type in ProviderType:
            assert provider_type in monitor.metrics
    
    def test_set_primary_provider(self):
        """Test setting primary provider"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        assert monitor.primary_provider == ProviderType.CLAUDE
        assert monitor.current_provider == ProviderType.CLAUDE
    
    def test_record_call(self):
        """Test recording provider calls"""
        monitor = ProviderHealthMonitor()
        
        monitor.record_call(ProviderType.CLAUDE, success=True, response_time_ms=100.0)
        
        metrics = monitor.metrics[ProviderType.CLAUDE]
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1
    
    def test_get_health_status(self):
        """Test getting health status"""
        monitor = ProviderHealthMonitor()
        monitor.record_call(ProviderType.CLAUDE, success=True, response_time_ms=100.0)
        
        status = monitor.get_health_status(ProviderType.CLAUDE)
        
        assert status["provider"] == "claude"
        assert status["success_rate"] == 1.0
        assert status["avg_response_time_ms"] == 100.0
        assert status["is_healthy"] is True
        assert status["circuit_open"] is False
    
    def test_should_failover_low_success_rate(self):
        """Test failover trigger on low success rate"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        # Generate 90% success rate (below 95% threshold)
        for _ in range(90):
            monitor.record_call(ProviderType.CLAUDE, success=True, response_time_ms=100.0)
        for _ in range(10):
            monitor.record_call(ProviderType.CLAUDE, success=False, response_time_ms=100.0)
        
        assert monitor.should_failover()
    
    def test_should_failover_circuit_open(self):
        """Test failover trigger when circuit is open"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        # Open circuit
        metrics = monitor.metrics[ProviderType.CLAUDE]
        metrics.open_circuit()
        
        assert monitor.should_failover()
    
    def test_select_provider_primary_healthy(self):
        """Test provider selection when primary is healthy"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        # Record successful calls
        for _ in range(10):
            monitor.record_call(ProviderType.CLAUDE, success=True, response_time_ms=100.0)
        
        available = [ProviderType.CLAUDE, ProviderType.OPENAI]
        selected = monitor.select_provider(available)
        
        assert selected == ProviderType.CLAUDE
        assert not monitor.failover_active
    
    def test_select_provider_failover(self):
        """Test provider selection during failover"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        # Make primary unhealthy
        for _ in range(10):
            monitor.record_call(ProviderType.CLAUDE, success=False, response_time_ms=100.0)
        
        # Make OpenAI healthy
        for _ in range(10):
            monitor.record_call(ProviderType.OPENAI, success=True, response_time_ms=100.0)
        
        available = [ProviderType.CLAUDE, ProviderType.OPENAI]
        selected = monitor.select_provider(available)
        
        assert selected == ProviderType.OPENAI
        assert monitor.failover_active
    
    def test_should_restore_primary(self):
        """Test primary provider restoration logic"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        # Trigger failover
        for _ in range(10):
            monitor.record_call(ProviderType.CLAUDE, success=False, response_time_ms=100.0)
        
        available = [ProviderType.CLAUDE, ProviderType.OPENAI]
        monitor.select_provider(available)
        assert monitor.failover_active
        
        # Restore primary health
        for _ in range(100):
            monitor.record_call(ProviderType.CLAUDE, success=True, response_time_ms=100.0)
        
        assert monitor.should_restore_primary()
    
    def test_select_provider_skips_open_circuits(self):
        """Test that provider selection skips open circuits"""
        monitor = ProviderHealthMonitor()
        monitor.set_primary_provider(ProviderType.CLAUDE)
        
        # Open circuit on Claude
        metrics = monitor.metrics[ProviderType.CLAUDE]
        metrics.open_circuit()
        
        # Make OpenAI healthy
        for _ in range(10):
            monitor.record_call(ProviderType.OPENAI, success=True, response_time_ms=100.0)
        
        available = [ProviderType.CLAUDE, ProviderType.OPENAI]
        selected = monitor.select_provider(available)
        
        assert selected == ProviderType.OPENAI


class TestExponentialBackoffRetry:
    """Test exponential backoff retry logic"""
    
    def test_delay_calculation(self):
        """Test exponential backoff delay calculation"""
        retry = ExponentialBackoffRetry(base_delay_seconds=2.0, jitter=False)
        
        # Test exponential growth: 2s, 4s, 8s, 16s, 32s
        assert retry.get_delay(0) == 2.0
        assert retry.get_delay(1) == 4.0
        assert retry.get_delay(2) == 8.0
        assert retry.get_delay(3) == 16.0
        assert retry.get_delay(4) == 32.0
    
    def test_max_delay_cap(self):
        """Test maximum delay cap"""
        retry = ExponentialBackoffRetry(
            base_delay_seconds=2.0,
            max_delay_seconds=10.0,
            jitter=False,
        )
        
        # Should cap at 10 seconds
        assert retry.get_delay(10) == 10.0
    
    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness"""
        retry = ExponentialBackoffRetry(base_delay_seconds=2.0, jitter=True)
        
        delays = [retry.get_delay(0) for _ in range(10)]
        
        # All delays should be different due to jitter
        assert len(set(delays)) > 1
        
        # All delays should be around 2.0 ± 25%
        for delay in delays:
            assert 1.5 <= delay <= 2.5
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """Test successful execution without retry"""
        retry = ExponentialBackoffRetry(base_delay_seconds=0.1)
        
        call_count = 0
        
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        success, result = await retry.execute_with_retry(successful_func)
        
        assert success is True
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_eventual_success(self):
        """Test eventual success after retries"""
        retry = ExponentialBackoffRetry(base_delay_seconds=0.1, max_retries=3)
        
        call_count = 0
        
        async def eventually_successful_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        success, result = await retry.execute_with_retry(eventually_successful_func)
        
        assert success is True
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self):
        """Test retry exhaustion"""
        retry = ExponentialBackoffRetry(base_delay_seconds=0.1, max_retries=2)
        
        call_count = 0
        
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")
        
        success, result = await retry.execute_with_retry(always_fails)
        
        assert success is False
        assert isinstance(result, Exception)
        assert call_count == 3  # Initial + 2 retries
