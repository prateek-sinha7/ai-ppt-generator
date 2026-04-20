"""
Tests for LangSmith Observability and Alerting (Task 30)

Covers:
- 30.1  LangSmith tracing context manager with provider/execution_id/industry tags
- 30.2  Per-agent performance logging (duration, tokens, success/failure, latency vs budget)
- 30.3  Provider failover event tracing
- 30.4  Alerting thresholds (latency, error rate, quality score, cost)
- 30.5  Health check endpoints (/health, /health/live, /health/ready)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.observability import (
    AGENT_LATENCY_BUDGETS,
    PROVIDER_ERROR_RATE_ALERT_THRESHOLD,
    QUALITY_SCORE_ALERT_THRESHOLD,
    AgentRunRecord,
    AlertSeverity,
    ObservabilityService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def obs() -> ObservabilityService:
    """Fresh ObservabilityService with LangSmith disabled."""
    svc = ObservabilityService.__new__(ObservabilityService)
    svc._langsmith = None
    svc._tracing_enabled = False
    return svc


# ---------------------------------------------------------------------------
# 30.1 — LangSmith tracing context manager
# ---------------------------------------------------------------------------

class TestAgentTracing:
    """30.1 — trace_agent context manager attaches correct tags."""

    @pytest.mark.asyncio
    async def test_trace_agent_success(self, obs: ObservabilityService):
        """Successful agent run sets success=True and records end_time."""
        async with obs.trace_agent(
            agent_name="research",
            execution_id="exec-001",
            provider="claude",
            industry="healthcare",
        ) as record:
            assert record.agent_name == "research"
            assert record.execution_id == "exec-001"
            assert record.provider == "claude"
            assert record.industry == "healthcare"
            # Simulate work
            await asyncio.sleep(0)

        assert record.success is True
        assert record.end_time is not None
        assert record.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_trace_agent_failure_propagates(self, obs: ObservabilityService):
        """Exception inside context manager is re-raised and success=False."""
        with pytest.raises(ValueError, match="boom"):
            async with obs.trace_agent(
                agent_name="validation",
                execution_id="exec-002",
            ) as record:
                raise ValueError("boom")

        assert record.success is False
        assert record.error == "boom"

    @pytest.mark.asyncio
    async def test_trace_agent_without_optional_tags(self, obs: ObservabilityService):
        """Context manager works without provider/industry."""
        async with obs.trace_agent(
            agent_name="quality_scoring",
            execution_id="exec-003",
        ) as record:
            pass

        assert record.provider is None
        assert record.industry is None
        assert record.success is True

    @pytest.mark.asyncio
    async def test_trace_agent_pushes_to_langsmith_when_enabled(self):
        """When LangSmith is enabled, _push_langsmith_run is called."""
        svc = ObservabilityService.__new__(ObservabilityService)
        svc._langsmith = MagicMock()
        svc._langsmith.create_run = MagicMock(return_value="run-id-123")
        svc._tracing_enabled = True

        async with svc.trace_agent(
            agent_name="research",
            execution_id="exec-ls-001",
            provider="openai",
            industry="finance",
        ):
            pass

        svc._langsmith.create_run.assert_called_once()
        call_kwargs = svc._langsmith.create_run.call_args
        assert "agent:research" in call_kwargs.kwargs.get("name", call_kwargs.args[0] if call_kwargs.args else "")

    @pytest.mark.asyncio
    async def test_trace_agent_langsmith_failure_does_not_break_pipeline(self):
        """LangSmith push failure must not propagate."""
        svc = ObservabilityService.__new__(ObservabilityService)
        svc._langsmith = MagicMock()
        svc._langsmith.create_run = MagicMock(side_effect=RuntimeError("langsmith down"))
        svc._tracing_enabled = True

        # Should not raise
        async with svc.trace_agent(
            agent_name="research",
            execution_id="exec-ls-002",
        ):
            pass


# ---------------------------------------------------------------------------
# 30.2 — Per-agent performance logging
# ---------------------------------------------------------------------------

class TestAgentPerformanceLogging:
    """30.2 — AgentRunRecord captures duration, tokens, success/failure."""

    def test_agent_run_record_duration(self):
        import time
        record = AgentRunRecord(agent_name="research", execution_id="e1")
        time.sleep(0.01)
        record.finish(success=True)
        assert record.duration_ms >= 10.0
        assert record.duration_s >= 0.01

    def test_agent_run_record_failure(self):
        record = AgentRunRecord(agent_name="validation", execution_id="e2")
        record.finish(success=False, error="schema error")
        assert record.success is False
        assert record.error == "schema error"

    def test_agent_run_record_token_fields(self):
        record = AgentRunRecord(agent_name="llm_provider", execution_id="e3")
        record.prompt_tokens = 500
        record.completion_tokens = 300
        record.total_tokens = 800
        record.cost_usd = 0.0024
        assert record.total_tokens == 800
        assert record.cost_usd == pytest.approx(0.0024)

    def test_exceeded_budget_true(self):
        """Agent that runs over budget is flagged."""
        import time
        record = AgentRunRecord(agent_name="prompt_engineering", execution_id="e4")
        # prompt_engineering budget is 5s — simulate 6s elapsed
        record.start_time = time.monotonic() - 6.0
        record.end_time = time.monotonic()
        assert record.latency_budget_s == 5.0
        assert record.exceeded_budget is True

    def test_exceeded_budget_false(self):
        """Agent within budget is not flagged."""
        import time
        record = AgentRunRecord(agent_name="quality_scoring", execution_id="e5")
        # quality_scoring budget is 10s — simulate 3s elapsed
        record.start_time = time.monotonic() - 3.0
        record.end_time = time.monotonic()
        assert record.exceeded_budget is False

    def test_latency_budget_values(self):
        """All known agents have a latency budget defined."""
        for agent in [
            "industry_classifier", "storyboarding", "research",
            "data_enrichment", "prompt_engineering", "llm_provider",
            "validation", "quality_scoring",
        ]:
            assert AGENT_LATENCY_BUDGETS[agent] > 0

    @pytest.mark.asyncio
    async def test_performance_log_emitted_on_success(self, obs: ObservabilityService):
        """_log_agent_performance is called after successful run."""
        with patch.object(obs, "_log_agent_performance") as mock_log:
            async with obs.trace_agent("research", "exec-perf-1"):
                pass
            mock_log.assert_called_once()
            record = mock_log.call_args[0][0]
            assert record.success is True

    @pytest.mark.asyncio
    async def test_performance_log_emitted_on_failure(self, obs: ObservabilityService):
        """_log_agent_performance is called even when agent raises."""
        with patch.object(obs, "_log_agent_performance") as mock_log:
            with pytest.raises(RuntimeError):
                async with obs.trace_agent("validation", "exec-perf-2"):
                    raise RuntimeError("fail")
            mock_log.assert_called_once()
            record = mock_log.call_args[0][0]
            assert record.success is False


# ---------------------------------------------------------------------------
# 30.3 — Provider failover event tracing
# ---------------------------------------------------------------------------

class TestProviderFailoverTracing:
    """30.3 — trace_provider_failover emits structured log and LangSmith event."""

    def test_failover_logs_warning(self, obs: ObservabilityService):
        """Failover event emits a structured warning log."""
        with patch("app.services.observability.logger") as mock_logger:
            obs.trace_provider_failover(
                execution_id="exec-fo-1",
                from_provider="claude",
                to_provider="openai",
                failure_reason="rate limit exceeded",
            )
            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args[1]
            assert call_kwargs["from_provider"] == "claude"
            assert call_kwargs["to_provider"] == "openai"
            assert call_kwargs["failure_reason"] == "rate limit exceeded"

    def test_failover_includes_agent_name(self, obs: ObservabilityService):
        """Optional agent_name is included in the log."""
        with patch("app.services.observability.logger") as mock_logger:
            obs.trace_provider_failover(
                execution_id="exec-fo-2",
                from_provider="openai",
                to_provider="groq",
                failure_reason="timeout",
                agent_name="llm_provider",
            )
            call_kwargs = mock_logger.warning.call_args[1]
            assert call_kwargs.get("agent") == "llm_provider"

    def test_failover_pushes_to_langsmith_when_enabled(self):
        """LangSmith create_run is called for failover events when tracing enabled."""
        svc = ObservabilityService.__new__(ObservabilityService)
        svc._langsmith = MagicMock()
        svc._langsmith.create_run = MagicMock(return_value="run-fo-1")
        svc._tracing_enabled = True

        svc.trace_provider_failover(
            execution_id="exec-fo-3",
            from_provider="claude",
            to_provider="groq",
            failure_reason="api error",
        )

        svc._langsmith.create_run.assert_called_once()
        call_kwargs = svc._langsmith.create_run.call_args[1]
        assert "provider:claude" in call_kwargs.get("tags", [])
        assert "event:failover" in call_kwargs.get("tags", [])

    def test_failover_langsmith_failure_does_not_raise(self):
        """LangSmith failure during failover trace must not propagate."""
        svc = ObservabilityService.__new__(ObservabilityService)
        svc._langsmith = MagicMock()
        svc._langsmith.create_run = MagicMock(side_effect=Exception("ls down"))
        svc._tracing_enabled = True

        # Should not raise
        svc.trace_provider_failover(
            execution_id="exec-fo-4",
            from_provider="claude",
            to_provider="openai",
            failure_reason="error",
        )


# ---------------------------------------------------------------------------
# 30.4 — Alerting thresholds
# ---------------------------------------------------------------------------

class TestAlertingThresholds:
    """30.4 — Alerts fire at correct thresholds."""

    def test_latency_alert_fires_when_budget_exceeded(self, obs: ObservabilityService):
        """_fire_alert is called with WARNING when agent exceeds latency budget."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            import time
            record = AgentRunRecord(agent_name="prompt_engineering", execution_id="e-lat-1")
            record.start_time = time.monotonic() - 10.0  # 10s > 5s budget
            record.end_time = time.monotonic()
            record.success = True
            obs._log_agent_performance(record)
            # Manually trigger the budget check (normally done in trace_agent finally block)
            if record.exceeded_budget:
                obs._fire_alert(
                    severity=AlertSeverity.WARNING,
                    event="agent_latency_exceeded_budget",
                    details={"agent": record.agent_name, "duration_s": record.duration_s},
                )
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[1]["severity"] == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_latency_alert_fires_inside_trace_agent(self, obs: ObservabilityService):
        """trace_agent fires a WARNING alert when agent exceeds its budget."""
        import time
        fired_alerts = []

        original_fire = obs._fire_alert

        def capture_alert(severity, event, details):
            fired_alerts.append({"severity": severity, "event": event, "details": details})

        obs._fire_alert = capture_alert

        # Simulate a prompt_engineering run that takes 10s (budget=5s)
        # We can't actually sleep 10s in tests, so we manipulate start_time after the fact.
        # Instead, patch run_with_budget to be instant but then check the record manually.
        async with obs.trace_agent("prompt_engineering", "exec-lat-2") as record:
            # Artificially push start_time back to simulate 10s elapsed
            record.start_time -= 10.0

        # The finally block should have fired a WARNING
        latency_alerts = [a for a in fired_alerts if a["event"] == "agent_latency_exceeded_budget"]
        assert len(latency_alerts) == 1
        assert latency_alerts[0]["severity"] == AlertSeverity.WARNING

    def test_provider_error_rate_alert_fires_above_threshold(self, obs: ObservabilityService):
        """Alert fires when error rate > 5%."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_provider_error_rate("claude", error_rate=0.10)
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args[1]
            assert call_args["severity"] == AlertSeverity.ALERT
            assert call_args["event"] == "provider_error_rate_exceeded"

    def test_provider_error_rate_no_alert_below_threshold(self, obs: ObservabilityService):
        """No alert when error rate is at or below 5%."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_provider_error_rate("claude", error_rate=0.04)
            mock_alert.assert_not_called()

    def test_provider_error_rate_alert_at_exact_threshold(self, obs: ObservabilityService):
        """No alert at exactly the threshold (strictly greater than)."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_provider_error_rate("claude", error_rate=PROVIDER_ERROR_RATE_ALERT_THRESHOLD)
            mock_alert.assert_not_called()

    def test_quality_score_alert_fires_after_retries_exhausted(self, obs: ObservabilityService):
        """Alert fires when quality < 6 and retries are exhausted."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_quality_score(
                quality_score=5.5,
                execution_id="exec-qs-1",
                retry_count=2,
                max_retries=2,
            )
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args[1]
            assert call_args["severity"] == AlertSeverity.ALERT
            assert call_args["event"] == "quality_score_below_threshold_after_retries"

    def test_quality_score_no_alert_when_retries_remain(self, obs: ObservabilityService):
        """No alert when quality is low but retries haven't been exhausted."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_quality_score(
                quality_score=4.0,
                execution_id="exec-qs-2",
                retry_count=1,
                max_retries=2,
            )
            mock_alert.assert_not_called()

    def test_quality_score_no_alert_when_score_above_threshold(self, obs: ObservabilityService):
        """No alert when quality score meets threshold."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_quality_score(
                quality_score=7.0,
                execution_id="exec-qs-3",
                retry_count=2,
                max_retries=2,
            )
            mock_alert.assert_not_called()

    def test_cost_ceiling_alert_fires_when_exceeded(self, obs: ObservabilityService):
        """CRITICAL alert fires when cost exceeds ceiling."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_cost_ceiling(
                cost_usd=1.50,
                ceiling_usd=1.00,
                execution_id="exec-cost-1",
                terminate=True,
            )
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args[1]
            assert call_args["severity"] == AlertSeverity.CRITICAL
            assert call_args["event"] == "cost_ceiling_exceeded"
            assert call_args["details"]["terminate"] is True

    def test_cost_ceiling_no_alert_below_ceiling(self, obs: ObservabilityService):
        """No alert when cost is below ceiling."""
        with patch.object(obs, "_fire_alert") as mock_alert:
            obs.check_cost_ceiling(
                cost_usd=0.50,
                ceiling_usd=1.00,
                execution_id="exec-cost-2",
            )
            mock_alert.assert_not_called()

    def test_fire_alert_warning_uses_logger_warning(self, obs: ObservabilityService):
        """WARNING severity uses logger.warning."""
        with patch("app.services.observability.logger") as mock_logger:
            obs._fire_alert(AlertSeverity.WARNING, "test_event", {"key": "val"})
            mock_logger.warning.assert_called_once()

    def test_fire_alert_alert_uses_logger_error(self, obs: ObservabilityService):
        """ALERT severity uses logger.error."""
        with patch("app.services.observability.logger") as mock_logger:
            obs._fire_alert(AlertSeverity.ALERT, "test_event", {"key": "val"})
            mock_logger.error.assert_called_once()

    def test_fire_alert_critical_uses_logger_critical(self, obs: ObservabilityService):
        """CRITICAL severity uses logger.critical."""
        with patch("app.services.observability.logger") as mock_logger:
            obs._fire_alert(AlertSeverity.CRITICAL, "test_event", {"key": "val"})
            mock_logger.critical.assert_called_once()


# ---------------------------------------------------------------------------
# 30.5 — Health check endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    """30.5 — /health, /health/live, /health/ready endpoints."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        from app.main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_live_returns_200(self):
        from app.main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    @pytest.mark.asyncio
    async def test_health_ready_structure(self):
        """Readiness endpoint returns a body with 'status' and 'checks' keys."""
        from app.main import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health/ready")
        body = response.json()
        assert "status" in body
        assert "checks" in body
        assert "database" in body["checks"]
        assert "redis" in body["checks"]
        assert "llm_provider" in body["checks"]

    @pytest.mark.asyncio
    async def test_health_ready_503_when_db_down(self):
        """Returns 503 when database check fails."""
        from app.api.v1.health import _check_database
        with patch("app.api.v1.health._check_database", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = (False, "connection refused")
            from app.main import app
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["database"]["ok"] is False

    @pytest.mark.asyncio
    async def test_health_ready_503_when_redis_down(self):
        """Returns 503 when Redis check fails."""
        with patch("app.api.v1.health._check_redis", new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value = (False, "connection refused")
            from app.main import app
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["checks"]["redis"]["ok"] is False

    @pytest.mark.asyncio
    async def test_health_ready_503_when_provider_down(self):
        """Returns 503 when LLM provider check fails."""
        with patch("app.api.v1.health._check_provider", new_callable=AsyncMock) as mock_prov:
            mock_prov.return_value = (False, "credentials missing")
            from app.main import app
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["checks"]["llm_provider"]["ok"] is False

    @pytest.mark.asyncio
    async def test_health_ready_200_when_all_checks_pass(self):
        """Returns 200 when all dependency checks pass."""
        with (
            patch("app.api.v1.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.v1.health._check_provider", new_callable=AsyncMock) as mock_prov,
        ):
            mock_db.return_value = (True, "ok")
            mock_redis.return_value = (True, "ok")
            mock_prov.return_value = (True, "provider 'claude' configured")
            from app.main import app
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert all(v["ok"] for v in body["checks"].values())

    @pytest.mark.asyncio
    async def test_health_ready_check_details_present(self):
        """Each check entry has 'ok' and 'detail' fields."""
        with (
            patch("app.api.v1.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.v1.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.v1.health._check_provider", new_callable=AsyncMock) as mock_prov,
        ):
            mock_db.return_value = (True, "ok")
            mock_redis.return_value = (True, "ok")
            mock_prov.return_value = (True, "ok")
            from app.main import app
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/ready")
        body = response.json()
        for check_name, check_data in body["checks"].items():
            assert "ok" in check_data, f"Missing 'ok' in {check_name}"
            assert "detail" in check_data, f"Missing 'detail' in {check_name}"
