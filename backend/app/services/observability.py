"""
Observability Service — LangSmith Tracing, Performance Logging, and Alerting

Implements:
- LangSmith tracing for all agent runs with provider, execution_id, industry tags (30.1)
- Per-agent performance logging: duration, token usage, success/failure, latency vs budget (30.2)
- Provider failover event tracing (30.3)
- Alerting thresholds: latency, error rate, quality score, cost (30.4)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from langsmith import Client as LangSmithClient
from langsmith.run_helpers import traceable

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Alert thresholds (30.4)
# ---------------------------------------------------------------------------

# Per-agent latency budgets (seconds) — mirrors pipeline_orchestrator.py
AGENT_LATENCY_BUDGETS: Dict[str, float] = {
    "industry_classifier": 15.0,
    "storyboarding": 10.0,
    "research": 30.0,
    "data_enrichment": 20.0,
    "prompt_engineering": 5.0,
    "llm_provider": 40.0,
    "validation": 5.0,
    "quality_scoring": 10.0,
}

# Provider error rate threshold for alert (5%)
PROVIDER_ERROR_RATE_ALERT_THRESHOLD = 0.05

# Quality score threshold — alert when score < 6 after retries
QUALITY_SCORE_ALERT_THRESHOLD = 6.0

# Cost ceiling alert threshold (USD)
COST_CEILING_ALERT_THRESHOLD = settings.COST_CEILING_USD


# ---------------------------------------------------------------------------
# Alert severity
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Agent run record
# ---------------------------------------------------------------------------

@dataclass
class AgentRunRecord:
    """Captures performance data for a single agent execution."""

    agent_name: str
    execution_id: str
    provider: Optional[str] = None
    industry: Optional[str] = None

    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None

    success: bool = False
    error: Optional[str] = None

    # Token usage (populated from LLM callback if available)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000.0

    @property
    def duration_s(self) -> float:
        return self.duration_ms / 1000.0

    @property
    def latency_budget_s(self) -> float:
        return AGENT_LATENCY_BUDGETS.get(self.agent_name, 0.0)

    @property
    def exceeded_budget(self) -> bool:
        budget = self.latency_budget_s
        return budget > 0 and self.duration_s > budget

    def finish(self, success: bool, error: Optional[str] = None) -> None:
        self.end_time = time.monotonic()
        self.success = success
        self.error = error


# ---------------------------------------------------------------------------
# Observability Service
# ---------------------------------------------------------------------------

class ObservabilityService:
    """
    Central observability hub for the multi-agent pipeline.

    Responsibilities:
    - Wrap agent runs with LangSmith traces (30.1)
    - Log per-agent performance metrics (30.2)
    - Trace provider failover events (30.3)
    - Fire alerts on threshold violations (30.4)
    """

    def __init__(self) -> None:
        self._langsmith: Optional[LangSmithClient] = None
        self._tracing_enabled = False
        self._initialize_langsmith()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _initialize_langsmith(self) -> None:
        if settings.LANGCHAIN_TRACING_V2 and settings.LANGSMITH_API_KEY:
            try:
                self._langsmith = LangSmithClient(api_key=settings.LANGSMITH_API_KEY)
                self._tracing_enabled = True
                logger.info(
                    "langsmith_tracing_enabled",
                    project=settings.LANGSMITH_PROJECT,
                )
            except Exception as exc:
                logger.warning("langsmith_init_failed", error=str(exc))
        else:
            logger.info("langsmith_tracing_disabled")

    # ------------------------------------------------------------------
    # 30.1 — Agent run tracing context manager
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def trace_agent(
        self,
        agent_name: str,
        execution_id: str,
        provider: Optional[str] = None,
        industry: Optional[str] = None,
        extra_tags: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[AgentRunRecord]:
        """
        Async context manager that wraps an agent run with LangSmith tracing
        and performance logging.

        Usage::

            async with observability.trace_agent("research", exec_id, provider="claude") as run:
                result = await research_agent.run(...)
                run.total_tokens = result.token_count
        """
        record = AgentRunRecord(
            agent_name=agent_name,
            execution_id=execution_id,
            provider=provider,
            industry=industry,
        )

        # Build LangSmith run metadata
        run_metadata: Dict[str, Any] = {
            "execution_id": execution_id,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if provider:
            run_metadata["provider"] = provider
        if industry:
            run_metadata["industry"] = industry
        if extra_tags:
            run_metadata.update(extra_tags)

        # Tags list for LangSmith
        tags: List[str] = [f"agent:{agent_name}"]
        if provider:
            tags.append(f"provider:{provider}")
        if industry:
            tags.append(f"industry:{industry}")
        tags.append(f"execution:{execution_id}")

        logger.info(
            "agent_trace_started",
            agent=agent_name,
            execution_id=execution_id,
            provider=provider,
            industry=industry,
        )

        try:
            yield record
            record.finish(success=True)
        except Exception as exc:
            record.finish(success=False, error=str(exc))
            raise
        finally:
            # 30.2 — Log performance metrics
            self._log_agent_performance(record)

            # 30.4 — Check latency alert threshold
            if record.exceeded_budget:
                self._fire_alert(
                    severity=AlertSeverity.WARNING,
                    event="agent_latency_exceeded_budget",
                    details={
                        "agent": agent_name,
                        "execution_id": execution_id,
                        "duration_s": round(record.duration_s, 3),
                        "budget_s": record.latency_budget_s,
                        "overage_s": round(record.duration_s - record.latency_budget_s, 3),
                    },
                )

            # Push run to LangSmith if enabled
            if self._tracing_enabled and self._langsmith:
                self._push_langsmith_run(record, run_metadata, tags)

    # ------------------------------------------------------------------
    # 30.2 — Per-agent performance logging
    # ------------------------------------------------------------------

    def _log_agent_performance(self, record: AgentRunRecord) -> None:
        """Emit structured log with full performance breakdown."""
        budget = record.latency_budget_s
        log_data: Dict[str, Any] = {
            "agent": record.agent_name,
            "execution_id": record.execution_id,
            "success": record.success,
            "duration_ms": round(record.duration_ms, 1),
            "latency_budget_s": budget,
            "exceeded_budget": record.exceeded_budget,
        }
        if record.provider:
            log_data["provider"] = record.provider
        if record.industry:
            log_data["industry"] = record.industry
        if record.total_tokens:
            log_data["prompt_tokens"] = record.prompt_tokens
            log_data["completion_tokens"] = record.completion_tokens
            log_data["total_tokens"] = record.total_tokens
        if record.cost_usd:
            log_data["cost_usd"] = round(record.cost_usd, 6)
        if record.error:
            log_data["error"] = record.error

        if record.success:
            logger.info("agent_performance", **log_data)
        else:
            logger.error("agent_performance_failure", **log_data)

    # ------------------------------------------------------------------
    # 30.3 — Provider failover event tracing
    # ------------------------------------------------------------------

    def trace_provider_failover(
        self,
        execution_id: str,
        from_provider: str,
        to_provider: str,
        failure_reason: str,
        agent_name: Optional[str] = None,
    ) -> None:
        """
        Record a provider failover event with full context.
        Emits a structured log and pushes a LangSmith feedback event if enabled.
        """
        event_data: Dict[str, Any] = {
            "failover_event": "provider_failover",
            "execution_id": execution_id,
            "from_provider": from_provider,
            "to_provider": to_provider,
            "failure_reason": failure_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if agent_name:
            event_data["agent"] = agent_name

        logger.warning("provider_failover_event", **event_data)

        # Push to LangSmith as a run event if tracing is enabled
        if self._tracing_enabled and self._langsmith:
            try:
                # LangSmith doesn't have a direct "event" API for non-run events,
                # so we create a lightweight run record for the failover event.
                self._langsmith.create_run(
                    name=f"provider_failover:{from_provider}->{to_provider}",
                    run_type="tool",
                    inputs={"from_provider": from_provider, "failure_reason": failure_reason},
                    outputs={"to_provider": to_provider},
                    tags=[
                        f"provider:{from_provider}",
                        f"failover_to:{to_provider}",
                        f"execution:{execution_id}",
                        "event:failover",
                    ],
                    extra={"metadata": event_data},
                    project_name=settings.LANGSMITH_PROJECT,
                )
            except Exception as exc:
                logger.debug("langsmith_failover_push_failed", error=str(exc))

    # ------------------------------------------------------------------
    # 30.4 — Alerting thresholds
    # ------------------------------------------------------------------

    def check_provider_error_rate(
        self,
        provider: str,
        error_rate: float,
        execution_id: Optional[str] = None,
    ) -> None:
        """
        Alert when provider error rate exceeds 5%.
        Called by the health monitor after each call batch.
        """
        if error_rate > PROVIDER_ERROR_RATE_ALERT_THRESHOLD:
            self._fire_alert(
                severity=AlertSeverity.ALERT,
                event="provider_error_rate_exceeded",
                details={
                    "provider": provider,
                    "error_rate": round(error_rate, 4),
                    "threshold": PROVIDER_ERROR_RATE_ALERT_THRESHOLD,
                    "execution_id": execution_id,
                },
            )

    def check_quality_score(
        self,
        quality_score: float,
        execution_id: str,
        retry_count: int,
        max_retries: int,
    ) -> None:
        """
        Alert when quality score is below threshold after all retries are exhausted.
        """
        if retry_count >= max_retries and quality_score < QUALITY_SCORE_ALERT_THRESHOLD:
            self._fire_alert(
                severity=AlertSeverity.ALERT,
                event="quality_score_below_threshold_after_retries",
                details={
                    "quality_score": quality_score,
                    "threshold": QUALITY_SCORE_ALERT_THRESHOLD,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                    "execution_id": execution_id,
                },
            )

    def check_cost_ceiling(
        self,
        cost_usd: float,
        ceiling_usd: float,
        execution_id: str,
        terminate: bool = False,
    ) -> None:
        """
        Alert (and optionally terminate) when cost exceeds ceiling.
        """
        if cost_usd >= ceiling_usd:
            self._fire_alert(
                severity=AlertSeverity.CRITICAL,
                event="cost_ceiling_exceeded",
                details={
                    "cost_usd": round(cost_usd, 6),
                    "ceiling_usd": ceiling_usd,
                    "execution_id": execution_id,
                    "terminate": terminate,
                },
            )

    def _fire_alert(
        self,
        severity: AlertSeverity,
        event: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Emit a structured alert log.  In production this can be wired to
        PagerDuty, Slack, or any webhook via the COST_ALERT_WEBHOOK_URL setting.
        """
        alert_payload = {
            "alert_severity": severity.value,
            "alert_event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }

        if severity == AlertSeverity.WARNING:
            logger.warning("observability_alert", **alert_payload)
        elif severity == AlertSeverity.ALERT:
            logger.error("observability_alert", **alert_payload)
        else:  # CRITICAL
            logger.critical("observability_alert", **alert_payload)

    # ------------------------------------------------------------------
    # LangSmith push helper
    # ------------------------------------------------------------------

    def _push_langsmith_run(
        self,
        record: AgentRunRecord,
        metadata: Dict[str, Any],
        tags: List[str],
    ) -> None:
        """Push a completed agent run to LangSmith."""
        if not self._langsmith:
            return
        try:
            run_id = self._langsmith.create_run(
                name=f"agent:{record.agent_name}",
                run_type="chain",
                inputs={"execution_id": record.execution_id, "agent": record.agent_name},
                outputs={
                    "success": record.success,
                    "duration_ms": round(record.duration_ms, 1),
                    "total_tokens": record.total_tokens,
                    "cost_usd": record.cost_usd,
                },
                error=record.error,
                tags=tags,
                extra={"metadata": metadata},
                project_name=settings.LANGSMITH_PROJECT,
            )
            logger.debug("langsmith_run_pushed", agent=record.agent_name, run_id=str(run_id))
        except Exception as exc:
            # LangSmith failures must never break the pipeline
            logger.debug("langsmith_push_failed", agent=record.agent_name, error=str(exc))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

observability = ObservabilityService()
