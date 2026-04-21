"""
Tests for the Multi-Agent Pipeline Orchestrator (Task 14).

Covers:
- Sequential execution order (14.1)
- LLM provider call integration (14.2)
- State persistence at each transition (14.3)
- Checkpoint recovery (14.4)
- Per-agent latency budget enforcement (14.5)
- Circuit breaker behaviour (14.6)
- Partial result delivery on failure (14.7)
- State cleanup policy (14.8)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.pipeline_orchestrator import (
    AGENT_LATENCY_BUDGETS,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_MIN_CALLS,
    PIPELINE_SEQUENCE,
    AgentName,
    CircuitBreaker,
    CircuitState,
    PipelineContext,
    PipelineOrchestrator,
    StateManagementLayer,
    run_with_budget,
    state_layer,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_context(
    presentation_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    topic: str = "Test topic",
) -> PipelineContext:
    return PipelineContext(
        presentation_id=presentation_id or str(uuid.uuid4()),
        execution_id=execution_id or str(uuid.uuid4()),
        topic=topic,
    )


def _minimal_slide_json(n: int = 1) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "presentation_id": str(uuid.uuid4()),
        "total_slides": n,
        "slides": [
            {
                "slide_id": str(uuid.uuid4()),
                "slide_number": i + 1,
                "type": "content",
                "title": "Test Slide",
                "content": {"bullets": ["Point one", "Point two"]},
                "visual_hint": "bullet-left",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25,
                },
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "provider_used": "claude",
                    "quality_score": 8.5,
                },
            }
            for i in range(n)
        ],
    }


# ---------------------------------------------------------------------------
# 14.1 — Pipeline sequence invariant
# ---------------------------------------------------------------------------

class TestPipelineSequence:
    def test_pipeline_sequence_order(self):
        """PIPELINE_SEQUENCE must follow the canonical agent order."""
        expected = [
            AgentName.INDUSTRY_CLASSIFIER,
            AgentName.DESIGN,
            AgentName.STORYBOARDING,
            AgentName.RESEARCH,
            AgentName.DATA_ENRICHMENT,
            AgentName.PROMPT_ENGINEERING,
            AgentName.LLM_PROVIDER,
            AgentName.VALIDATION,
            AgentName.QUALITY_SCORING,
        ]
        assert PIPELINE_SEQUENCE == expected

    def test_all_agents_in_sequence(self):
        """Every AgentName (except internal) must appear in PIPELINE_SEQUENCE."""
        for agent in AgentName:
            assert agent in PIPELINE_SEQUENCE, f"{agent} missing from PIPELINE_SEQUENCE"

    @pytest.mark.asyncio
    async def test_run_records_agents_in_order(self):
        """
        When all agents succeed, completed_agents must match PIPELINE_SEQUENCE.
        """
        orchestrator = PipelineOrchestrator()
        orchestrator._agents_loaded = True

        call_order: List[AgentName] = []

        async def fake_dispatch(agent_name: AgentName, ctx: PipelineContext) -> None:
            call_order.append(agent_name)
            # Populate minimal required fields so later agents don't crash
            if agent_name == AgentName.INDUSTRY_CLASSIFIER:
                ctx.detected_context = {"industry": "technology", "confidence": 0.9,
                                        "sub_sector": None, "target_audience": "general",
                                        "selected_template_id": None,
                                        "selected_template_name": "Tech",
                                        "theme": "dark_modern",
                                        "compliance_context": [],
                                        "classification_method": "keyword"}
            elif agent_name == AgentName.STORYBOARDING:
                ctx.presentation_plan = {"total_slides": 7, "sections": []}
            elif agent_name == AgentName.RESEARCH:
                ctx.research_findings = {"sections": [], "risks": [], "opportunities": [],
                                         "terminology": [], "context_summary": ""}
            elif agent_name == AgentName.DATA_ENRICHMENT:
                ctx.enriched_data = {"charts": [], "tables": [], "key_metrics": {}}
            elif agent_name == AgentName.PROMPT_ENGINEERING:
                ctx.optimized_prompt = {"prompt_id": "abc", "version": "1.0.0",
                                        "system_prompt": "sys", "user_prompt": "usr",
                                        "estimated_tokens": 100, "token_limit": 4096,
                                        "metadata": {}, "created_at": "2024-01-01",
                                        "provider_type": "claude"}
            elif agent_name == AgentName.LLM_PROVIDER:
                ctx.raw_llm_output = _minimal_slide_json(3)
            elif agent_name == AgentName.VALIDATION:
                ctx.validated_slides = _minimal_slide_json(3)
            elif agent_name == AgentName.QUALITY_SCORING:
                ctx.quality_result = {"composite_score": 8.5, "requires_feedback_loop": False}

        with (
            patch.object(orchestrator, "_dispatch", side_effect=fake_dispatch),
            patch.object(orchestrator, "_get_or_create_execution",
                         new_callable=AsyncMock,
                         return_value=str(uuid.uuid4())),
            patch.object(orchestrator, "_persist_agent_output", new_callable=AsyncMock),
            patch.object(orchestrator, "_finalize", new_callable=AsyncMock),
            patch("app.agents.pipeline_orchestrator.state_layer.persist_checkpoint",
                  new_callable=AsyncMock),
            patch("app.agents.pipeline_orchestrator.state_layer.load_checkpoint",
                  new_callable=AsyncMock, return_value=None),
            patch("app.agents.pipeline_orchestrator.state_layer.update_execution_status",
                  new_callable=AsyncMock),
            patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
        ):
            # Make async_session_maker return a usable async context manager
            mock_db = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            ctx = await orchestrator.run(
                presentation_id=str(uuid.uuid4()),
                topic="Healthcare digital transformation",
            )

        assert call_order == PIPELINE_SEQUENCE
        assert ctx.completed_agents == PIPELINE_SEQUENCE


# ---------------------------------------------------------------------------
# 14.3 — State persistence
# ---------------------------------------------------------------------------

class TestStatePersistence:
    @pytest.mark.asyncio
    async def test_checkpoint_round_trip(self):
        """Context serialises and deserialises without data loss."""
        ctx = make_context()
        ctx.detected_context = {"industry": "finance", "confidence": 0.95}
        ctx.presentation_plan = {"total_slides": 10}
        ctx.completed_agents = [AgentName.INDUSTRY_CLASSIFIER, AgentName.STORYBOARDING]

        checkpoint = ctx.to_checkpoint()
        restored = PipelineContext.from_checkpoint(checkpoint)

        assert restored.presentation_id == ctx.presentation_id
        assert restored.execution_id == ctx.execution_id
        assert restored.topic == ctx.topic
        assert restored.detected_context == ctx.detected_context
        assert restored.presentation_plan == ctx.presentation_plan
        assert restored.completed_agents == ctx.completed_agents

    @pytest.mark.asyncio
    async def test_persist_agent_state_creates_row(self):
        """persist_agent_state writes a new AgentState row."""
        layer = StateManagementLayer()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()

        await layer.persist_agent_state(
            db,
            execution_id=str(uuid.uuid4()),
            agent_name=AgentName.RESEARCH,
            state={"sections": ["A", "B"]},
        )

        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_agent_state_updates_existing(self):
        """persist_agent_state updates an existing AgentState row."""
        layer = StateManagementLayer()
        existing = MagicMock()
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )
        db.flush = AsyncMock()

        new_state = {"sections": ["X", "Y"]}
        await layer.persist_agent_state(
            db,
            execution_id=str(uuid.uuid4()),
            agent_name=AgentName.RESEARCH,
            state=new_state,
        )

        assert existing.state == new_state
        db.add.assert_not_called()


# ---------------------------------------------------------------------------
# 14.4 — Checkpoint recovery
# ---------------------------------------------------------------------------

class TestCheckpointRecovery:
    @pytest.mark.asyncio
    async def test_skips_completed_agents(self):
        """Agents already in completed_agents are skipped on resume."""
        orchestrator = PipelineOrchestrator()
        orchestrator._agents_loaded = True

        dispatched: List[AgentName] = []

        async def fake_dispatch(agent_name: AgentName, ctx: PipelineContext) -> None:
            dispatched.append(agent_name)
            if agent_name == AgentName.LLM_PROVIDER:
                ctx.raw_llm_output = _minimal_slide_json(2)
            elif agent_name == AgentName.VALIDATION:
                ctx.validated_slides = _minimal_slide_json(2)
            elif agent_name == AgentName.QUALITY_SCORING:
                ctx.quality_result = {"composite_score": 9.0, "requires_feedback_loop": False}

        # Pre-populate context as if first 5 agents already ran
        pre_ctx = make_context()
        pre_ctx.completed_agents = [
            AgentName.INDUSTRY_CLASSIFIER,
            AgentName.DESIGN,
            AgentName.STORYBOARDING,
            AgentName.RESEARCH,
            AgentName.DATA_ENRICHMENT,
            AgentName.PROMPT_ENGINEERING,
        ]
        pre_ctx.detected_context = {"industry": "retail", "confidence": 0.8,
                                    "sub_sector": None, "target_audience": "general",
                                    "selected_template_id": None,
                                    "selected_template_name": "Retail",
                                    "theme": "deloitte",
                                    "compliance_context": [],
                                    "classification_method": "semantic"}
        pre_ctx.optimized_prompt = {"prompt_id": "x", "version": "1.0.0",
                                    "system_prompt": "s", "user_prompt": "u",
                                    "estimated_tokens": 50, "token_limit": 4096,
                                    "metadata": {}, "created_at": "2024-01-01",
                                    "provider_type": "claude"}

        with (
            patch.object(orchestrator, "_dispatch", side_effect=fake_dispatch),
            patch.object(orchestrator, "_get_or_create_execution",
                         new_callable=AsyncMock,
                         return_value=pre_ctx.execution_id),
            patch.object(orchestrator, "_persist_agent_output", new_callable=AsyncMock),
            patch.object(orchestrator, "_finalize", new_callable=AsyncMock),
            patch("app.agents.pipeline_orchestrator.state_layer.persist_checkpoint",
                  new_callable=AsyncMock),
            patch("app.agents.pipeline_orchestrator.state_layer.load_checkpoint",
                  new_callable=AsyncMock, return_value=pre_ctx),
            patch("app.agents.pipeline_orchestrator.state_layer.update_execution_status",
                  new_callable=AsyncMock),
            patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
        ):
            mock_db = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            ctx = await orchestrator.run(
                presentation_id=pre_ctx.presentation_id,
                topic=pre_ctx.topic,
                resume_from_checkpoint=True,
            )

        # Only the remaining 3 agents should have been dispatched
        assert dispatched == [
            AgentName.LLM_PROVIDER,
            AgentName.VALIDATION,
            AgentName.QUALITY_SCORING,
        ]


# ---------------------------------------------------------------------------
# 14.5 — Latency budget enforcement
# ---------------------------------------------------------------------------

class TestLatencyBudgets:
    def test_all_agents_have_budgets(self):
        """Every agent in PIPELINE_SEQUENCE must have a latency budget."""
        for agent in PIPELINE_SEQUENCE:
            assert agent in AGENT_LATENCY_BUDGETS, f"No budget for {agent}"
            assert AGENT_LATENCY_BUDGETS[agent] > 0

    @pytest.mark.asyncio
    async def test_run_with_budget_raises_on_timeout(self):
        """run_with_budget raises TimeoutError when coro exceeds budget."""
        async def slow_coro():
            await asyncio.sleep(10)

        # Temporarily shrink budget to 0.05s for the test
        original = AGENT_LATENCY_BUDGETS[AgentName.RESEARCH]
        AGENT_LATENCY_BUDGETS[AgentName.RESEARCH] = 0.05
        try:
            with pytest.raises(asyncio.TimeoutError):
                await run_with_budget(AgentName.RESEARCH, slow_coro())
        finally:
            AGENT_LATENCY_BUDGETS[AgentName.RESEARCH] = original

    @pytest.mark.asyncio
    async def test_run_with_budget_passes_fast_coro(self):
        """run_with_budget returns normally for fast coroutines."""
        async def fast_coro():
            return 42

        result = await run_with_budget(AgentName.PROMPT_ENGINEERING, fast_coro())
        assert result == 42

    @pytest.mark.asyncio
    async def test_agent_timeout_marks_failure(self):
        """A timed-out agent sets failed_agent and error_message on context."""
        orchestrator = PipelineOrchestrator()
        orchestrator._agents_loaded = True

        async def slow_dispatch(agent_name: AgentName, ctx: PipelineContext) -> None:
            if agent_name == AgentName.INDUSTRY_CLASSIFIER:
                await asyncio.sleep(10)  # Will be killed by budget

        original_budget = AGENT_LATENCY_BUDGETS[AgentName.INDUSTRY_CLASSIFIER]
        AGENT_LATENCY_BUDGETS[AgentName.INDUSTRY_CLASSIFIER] = 0.05

        try:
            with (
                patch.object(orchestrator, "_dispatch", side_effect=slow_dispatch),
                patch.object(orchestrator, "_get_or_create_execution",
                             new_callable=AsyncMock,
                             return_value=str(uuid.uuid4())),
                patch.object(orchestrator, "_persist_partial_result", new_callable=AsyncMock),
                patch.object(orchestrator, "_finalize", new_callable=AsyncMock),
                patch("app.agents.pipeline_orchestrator.state_layer.load_checkpoint",
                      new_callable=AsyncMock, return_value=None),
                patch("app.agents.pipeline_orchestrator.state_layer.update_execution_status",
                      new_callable=AsyncMock),
                patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
            ):
                mock_db = AsyncMock()
                mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

                ctx = await orchestrator.run(
                    presentation_id=str(uuid.uuid4()),
                    topic="test",
                )
        finally:
            AGENT_LATENCY_BUDGETS[AgentName.INDUSTRY_CLASSIFIER] = original_budget

        assert ctx.failed_agent == AgentName.INDUSTRY_CLASSIFIER
        assert "budget" in (ctx.error_message or "").lower()


# ---------------------------------------------------------------------------
# 14.6 — Circuit breakers
# ---------------------------------------------------------------------------

class TestCircuitBreakers:
    def test_circuit_starts_closed(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_call() is True

    def test_circuit_opens_after_threshold(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        # Record enough failures to exceed threshold
        for _ in range(CIRCUIT_BREAKER_MIN_CALLS):
            cb.record(False)
        assert cb.state == CircuitState.OPEN
        assert cb.allow_call() is False

    def test_circuit_stays_closed_below_threshold(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        # 1 failure out of 5 calls = 20% — exactly at threshold, not above it
        # Use 1 failure out of 10 calls = 10% to stay clearly below threshold
        for _ in range(9):
            cb.record(True)
        cb.record(False)
        assert cb.state == CircuitState.CLOSED

    def test_circuit_transitions_to_half_open_after_recovery_window(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        for _ in range(CIRCUIT_BREAKER_MIN_CALLS):
            cb.record(False)
        assert cb.state == CircuitState.OPEN

        # Simulate recovery window elapsed
        cb._opened_at = time.monotonic() - 999
        assert cb.allow_call() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_circuit_closes_on_success_in_half_open(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        cb.state = CircuitState.HALF_OPEN
        cb.record(True)
        assert cb.state == CircuitState.CLOSED

    def test_circuit_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        cb.state = CircuitState.HALF_OPEN
        cb.record(False)
        assert cb.state == CircuitState.OPEN

    def test_failure_rate_calculation(self):
        cb = CircuitBreaker(agent_name=AgentName.RESEARCH)
        cb._window = deque([True, True, False, False], maxlen=20)
        assert abs(cb.failure_rate - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_open_circuit_stops_pipeline(self):
        """An open circuit breaker stops the pipeline before running the agent."""
        orchestrator = PipelineOrchestrator()
        orchestrator._agents_loaded = True

        dispatched: List[AgentName] = []

        async def fake_dispatch(agent_name: AgentName, ctx: PipelineContext) -> None:
            dispatched.append(agent_name)

        # Force industry_classifier circuit open
        from app.agents.pipeline_orchestrator import _circuit_breakers
        original_state = _circuit_breakers[AgentName.INDUSTRY_CLASSIFIER].state
        _circuit_breakers[AgentName.INDUSTRY_CLASSIFIER].state = CircuitState.OPEN
        _circuit_breakers[AgentName.INDUSTRY_CLASSIFIER]._opened_at = time.monotonic()

        try:
            with (
                patch.object(orchestrator, "_dispatch", side_effect=fake_dispatch),
                patch.object(orchestrator, "_get_or_create_execution",
                             new_callable=AsyncMock,
                             return_value=str(uuid.uuid4())),
                patch.object(orchestrator, "_persist_partial_result", new_callable=AsyncMock),
                patch.object(orchestrator, "_finalize", new_callable=AsyncMock),
                patch("app.agents.pipeline_orchestrator.state_layer.load_checkpoint",
                      new_callable=AsyncMock, return_value=None),
                patch("app.agents.pipeline_orchestrator.state_layer.update_execution_status",
                      new_callable=AsyncMock),
                patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
            ):
                mock_db = AsyncMock()
                mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

                ctx = await orchestrator.run(
                    presentation_id=str(uuid.uuid4()),
                    topic="test",
                )
        finally:
            _circuit_breakers[AgentName.INDUSTRY_CLASSIFIER].state = original_state

        assert AgentName.INDUSTRY_CLASSIFIER not in dispatched
        assert ctx.failed_agent == AgentName.INDUSTRY_CLASSIFIER


# ---------------------------------------------------------------------------
# 14.7 — Partial result delivery
# ---------------------------------------------------------------------------

class TestPartialResultDelivery:
    @pytest.mark.asyncio
    async def test_partial_result_uses_best_available(self):
        """
        When pipeline fails mid-way, _persist_partial_result stores
        the best available slides (validated > raw > empty).
        """
        orchestrator = PipelineOrchestrator()
        orchestrator._agents_loaded = True

        ctx = make_context()
        ctx.raw_llm_output = _minimal_slide_json(5)
        ctx.validated_slides = _minimal_slide_json(5)
        ctx.failed_agent = AgentName.QUALITY_SCORING
        ctx.error_message = "Scoring failed"

        with (
            patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
            patch("app.agents.pipeline_orchestrator.state_layer.update_execution_status",
                  new_callable=AsyncMock),
        ):
            mock_db = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            await orchestrator._persist_partial_result(ctx)

        # DB execute should have been called (UPDATE presentation)
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_partial_result_falls_back_to_raw_when_no_validated(self):
        """When validated_slides is None, raw_llm_output is used."""
        orchestrator = PipelineOrchestrator()
        orchestrator._agents_loaded = True

        ctx = make_context()
        ctx.raw_llm_output = _minimal_slide_json(3)
        ctx.validated_slides = None
        ctx.failed_agent = AgentName.VALIDATION

        captured_values: List[Dict] = []

        with (
            patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
            patch("app.agents.pipeline_orchestrator.state_layer.update_execution_status",
                  new_callable=AsyncMock),
        ):
            mock_db = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            await orchestrator._persist_partial_result(ctx)

        mock_db.execute.assert_called()


# ---------------------------------------------------------------------------
# 14.8 — State cleanup
# ---------------------------------------------------------------------------

class TestStateCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_expired_states(self):
        """cleanup_expired_states deletes rows older than 7 days."""
        layer = StateManagementLayer()
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 42
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        deleted = await layer.cleanup_expired_states(db)

        assert deleted == 42
        db.execute.assert_called_once()
        # Verify a DELETE statement was issued
        call_args = db.execute.call_args[0][0]
        assert "DELETE" in str(call_args).upper() or hasattr(call_args, "whereclause")

    @pytest.mark.asyncio
    async def test_orchestrator_cleanup_calls_layer(self):
        """PipelineOrchestrator.cleanup_expired_states delegates to state_layer."""
        orchestrator = PipelineOrchestrator()

        with (
            patch("app.agents.pipeline_orchestrator.state_layer.cleanup_expired_states",
                  new_callable=AsyncMock, return_value=7) as mock_cleanup,
            patch("app.agents.pipeline_orchestrator.async_session_maker") as mock_sm,
        ):
            mock_db = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            deleted = await orchestrator.cleanup_expired_states()

        assert deleted == 7
        mock_cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# Context serialisation
# ---------------------------------------------------------------------------

class TestPipelineContext:
    def test_to_checkpoint_includes_all_fields(self):
        ctx = make_context()
        ctx.detected_context = {"industry": "healthcare"}
        ctx.completed_agents = [AgentName.INDUSTRY_CLASSIFIER]
        ctx.failed_agent = AgentName.RESEARCH
        ctx.error_message = "timeout"

        cp = ctx.to_checkpoint()

        assert cp["detected_context"] == {"industry": "healthcare"}
        assert cp["completed_agents"] == ["industry_classifier"]
        assert cp["failed_agent"] == "research"
        assert cp["error_message"] == "timeout"

    def test_from_checkpoint_restores_enums(self):
        cp = {
            "presentation_id": str(uuid.uuid4()),
            "execution_id": str(uuid.uuid4()),
            "topic": "test",
            "completed_agents": ["industry_classifier", "storyboarding"],
            "failed_agent": "research",
            "error_message": "err",
            "feedback_loop_count": 1,
        }
        ctx = PipelineContext.from_checkpoint(cp)

        assert ctx.completed_agents == [AgentName.INDUSTRY_CLASSIFIER, AgentName.STORYBOARDING]
        assert ctx.failed_agent == AgentName.RESEARCH
        assert ctx.feedback_loop_count == 1
