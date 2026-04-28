"""
Multi-Agent Pipeline Orchestrator

Implements the full sequential pipeline:
  Industry_Classifier → Storyboarding → Research → DataEnrichment →
  PromptEngineering → LLM → Validation → QualityScoring

Key features:
- Atomic state persistence at each agent transition (14.3)
- Checkpoint recovery from any agent (14.4)
- Per-agent latency budget enforcement (14.5)
- Circuit breakers per agent (14.6)
- Partial result delivery on failure (14.7)
- State cleanup after 7 days (14.8)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.generation_mode import GenerationMode, PROVIDER_DEFAULT_MODES
from app.db.models import (
    AgentState,
    Presentation,
    PipelineExecution,
    PresentationStatus,
    QualityScore,
)
from app.db.session import async_session_maker

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Agent names (canonical)
# ---------------------------------------------------------------------------

class AgentName(str, Enum):
    INDUSTRY_CLASSIFIER = "industry_classifier"
    DESIGN = "design"
    STORYBOARDING = "storyboarding"
    RESEARCH = "research"
    DATA_ENRICHMENT = "data_enrichment"
    PROMPT_ENGINEERING = "prompt_engineering"
    LLM_PROVIDER = "llm_provider"
    VALIDATION = "validation"
    VISUAL_REFINEMENT = "visual_refinement"  # NEW - Post-validation visual polish
    QUALITY_SCORING = "quality_scoring"
    VISUAL_QA = "visual_qa"


# Pipeline execution order
PIPELINE_SEQUENCE: List[AgentName] = [
    AgentName.INDUSTRY_CLASSIFIER,
    AgentName.DESIGN,
    AgentName.STORYBOARDING,
    AgentName.RESEARCH,
    AgentName.DATA_ENRICHMENT,
    AgentName.PROMPT_ENGINEERING,
    AgentName.LLM_PROVIDER,
    AgentName.VALIDATION,
    AgentName.VISUAL_REFINEMENT,  # NEW - Runs after validation
    AgentName.QUALITY_SCORING,
    AgentName.VISUAL_QA,
]


# ---------------------------------------------------------------------------
# Per-agent latency budgets (seconds) — Req 14.5
# ---------------------------------------------------------------------------

AGENT_LATENCY_BUDGETS: Dict[AgentName, float] = {
    AgentName.INDUSTRY_CLASSIFIER: 15.0,
    AgentName.DESIGN: 20.0,  # LLM call for design spec
    AgentName.STORYBOARDING: 10.0,
    AgentName.RESEARCH: 60.0,  # Increased from 30s - LLM call can be slow for complex topics
    AgentName.DATA_ENRICHMENT: 20.0,
    AgentName.PROMPT_ENGINEERING: 5.0,
    AgentName.LLM_PROVIDER: 300.0,  # Increased to 5 minutes to handle large presentation generation with Claude
    AgentName.VALIDATION: 5.0,
    AgentName.VISUAL_REFINEMENT: 90.0,  # Increased for Phase 5 batch processing (3 LLM calls per batch)
    AgentName.QUALITY_SCORING: 10.0,
    AgentName.VISUAL_QA: 60.0,
}

# Total pipeline budget
PIPELINE_TOTAL_BUDGET_SECONDS = 630.0  # Increased for research agent + Phase 5 visual refinement + longer LLM generation time + visual QA

# Circuit breaker threshold — open when failure rate > 20%
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 0.20
# Minimum calls before circuit can open
CIRCUIT_BREAKER_MIN_CALLS = 5
# How long circuit stays open before half-open probe (seconds)
CIRCUIT_BREAKER_RECOVERY_SECONDS = 60.0
# Rolling window size for failure rate calculation
CIRCUIT_BREAKER_WINDOW_SIZE = 20

# State cleanup: remove agent states older than 7 days, keep audit logs
STATE_CLEANUP_DAYS = 7


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing — reject calls
    HALF_OPEN = "half_open"  # Probe to see if recovered


@dataclass
class CircuitBreaker:
    """Per-agent circuit breaker tracking failure rate over a rolling window."""

    agent_name: AgentName
    state: CircuitState = CircuitState.CLOSED
    _window: Deque[bool] = field(default_factory=lambda: deque(maxlen=CIRCUIT_BREAKER_WINDOW_SIZE))
    _opened_at: Optional[float] = None  # monotonic time

    def record(self, success: bool) -> None:
        self._window.append(success)
        if self.state == CircuitState.HALF_OPEN:
            if success:
                self._close()
            else:
                self._open()
        elif self.state == CircuitState.CLOSED:
            if self._should_open():
                self._open()

    def _should_open(self) -> bool:
        if len(self._window) < CIRCUIT_BREAKER_MIN_CALLS:
            return False
        failures = sum(1 for ok in self._window if not ok)
        rate = failures / len(self._window)
        return rate > CIRCUIT_BREAKER_FAILURE_THRESHOLD

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.warning("circuit_breaker_opened", agent=self.agent_name.value)

    def _close(self) -> None:
        self.state = CircuitState.CLOSED
        self._opened_at = None
        logger.info("circuit_breaker_closed", agent=self.agent_name.value)

    def allow_call(self) -> bool:
        """Return True if the call should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._opened_at or 0)
            if elapsed >= CIRCUIT_BREAKER_RECOVERY_SECONDS:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open", agent=self.agent_name.value)
                return True
            return False
        # HALF_OPEN — allow one probe
        return True

    @property
    def failure_rate(self) -> float:
        if not self._window:
            return 0.0
        failures = sum(1 for ok in self._window if not ok)
        return failures / len(self._window)


# Global circuit breakers — one per agent
_circuit_breakers: Dict[AgentName, CircuitBreaker] = {
    name: CircuitBreaker(agent_name=name) for name in AgentName
}


def get_circuit_breaker(agent: AgentName) -> CircuitBreaker:
    return _circuit_breakers[agent]


# ---------------------------------------------------------------------------
# Code Failure Tracker — per-provider code generation failure tracking (6.4)
# ---------------------------------------------------------------------------

@dataclass
class CodeFailureTracker:
    """Track code generation success/failure per provider over a rolling window.

    When the failure rate exceeds 30% over the last 10 requests for a provider,
    the tracker recommends downgrading that provider's generation mode.
    """

    _results: Dict[str, Deque[bool]] = field(default_factory=dict)

    def record(self, provider: str, success: bool) -> None:
        """Record a code generation result for *provider*."""
        if provider not in self._results:
            self._results[provider] = deque(maxlen=10)
        self._results[provider].append(success)

    def failure_rate(self, provider: str) -> float:
        window = self._results.get(provider)
        if not window:
            return 0.0
        failures = sum(1 for ok in window if not ok)
        return failures / len(window)

    def should_downgrade(self, provider: str) -> bool:
        return self.failure_rate(provider) > 0.30

    def downgraded_mode(self, current_mode: GenerationMode) -> GenerationMode:
        """Return the next lower mode: artisan → studio → craft → express."""
        if current_mode == GenerationMode.ARTISAN:
            return GenerationMode.STUDIO
        if current_mode == GenerationMode.STUDIO:
            return GenerationMode.CRAFT
        return GenerationMode.EXPRESS


# Global code failure tracker instance
_code_failure_tracker = CodeFailureTracker()


def get_code_failure_tracker() -> CodeFailureTracker:
    return _code_failure_tracker


# ---------------------------------------------------------------------------
# Pipeline context — carries state between agents
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Mutable context passed through the pipeline."""

    presentation_id: str
    execution_id: str
    topic: str
    user_selected_theme: Optional[str] = None
    generation_mode: Optional[GenerationMode] = None

    # Populated by each agent
    detected_context: Optional[Dict[str, Any]] = None
    design_spec: Optional[Dict[str, Any]] = None  # DesignAgent output
    presentation_plan: Optional[Dict[str, Any]] = None
    research_findings: Optional[Dict[str, Any]] = None
    enriched_data: Optional[Dict[str, Any]] = None
    optimized_prompt: Optional[Dict[str, Any]] = None
    raw_llm_output: Optional[Dict[str, Any]] = None
    validated_slides: Optional[Dict[str, Any]] = None
    quality_result: Optional[Dict[str, Any]] = None
    visual_qa_result: Optional[Dict[str, Any]] = None

    # Tracking
    completed_agents: List[AgentName] = field(default_factory=list)
    failed_agent: Optional[AgentName] = None
    error_message: Optional[str] = None
    feedback_loop_count: int = 0

    def to_checkpoint(self) -> Dict[str, Any]:
        """Serialise to a checkpoint dict for DB storage."""
        return {
            "presentation_id": self.presentation_id,
            "execution_id": self.execution_id,
            "topic": self.topic,
            "user_selected_theme": self.user_selected_theme,
            "generation_mode": self.generation_mode.value if self.generation_mode else None,
            "detected_context": self.detected_context,
            "design_spec": self.design_spec,
            "presentation_plan": self.presentation_plan,
            "research_findings": self.research_findings,
            "enriched_data": self.enriched_data,
            "optimized_prompt": self.optimized_prompt,
            "raw_llm_output": self.raw_llm_output,
            "validated_slides": self.validated_slides,
            "quality_result": self.quality_result,
            "visual_qa_result": self.visual_qa_result,
            "completed_agents": [a.value for a in self.completed_agents],
            "failed_agent": self.failed_agent.value if self.failed_agent else None,
            "error_message": self.error_message,
            "feedback_loop_count": self.feedback_loop_count,
        }

    @classmethod
    def from_checkpoint(cls, data: Dict[str, Any]) -> "PipelineContext":
        ctx = cls(
            presentation_id=data["presentation_id"],
            execution_id=data["execution_id"],
            topic=data["topic"],
            user_selected_theme=data.get("user_selected_theme"),
        )
        gm = data.get("generation_mode")
        ctx.generation_mode = GenerationMode(gm) if gm else None
        ctx.detected_context = data.get("detected_context")
        ctx.design_spec = data.get("design_spec")
        ctx.presentation_plan = data.get("presentation_plan")
        ctx.research_findings = data.get("research_findings")
        ctx.enriched_data = data.get("enriched_data")
        ctx.optimized_prompt = data.get("optimized_prompt")
        ctx.raw_llm_output = data.get("raw_llm_output")
        ctx.validated_slides = data.get("validated_slides")
        ctx.quality_result = data.get("quality_result")
        ctx.visual_qa_result = data.get("visual_qa_result")
        ctx.completed_agents = [AgentName(a) for a in data.get("completed_agents", [])]
        failed = data.get("failed_agent")
        ctx.failed_agent = AgentName(failed) if failed else None
        ctx.error_message = data.get("error_message")
        ctx.feedback_loop_count = data.get("feedback_loop_count", 0)
        return ctx


# ---------------------------------------------------------------------------
# State Management Layer (14.3)
# ---------------------------------------------------------------------------

class StateManagementLayer:
    """
    Persists agent state atomically at each pipeline transition.

    Each agent's output is written to agent_states as a JSONB blob keyed by
    (execution_id, agent_name).  The pipeline_executions row is updated with
    current_agent and status on every transition.
    """

    async def persist_agent_state(
        self,
        db: AsyncSession,
        execution_id: str,
        agent_name: AgentName,
        state: Dict[str, Any],
    ) -> None:
        """Upsert agent state atomically."""
        # Check if state already exists
        stmt = select(AgentState).where(
            AgentState.execution_id == execution_id,
            AgentState.agent_name == agent_name.value,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.state = state
        else:
            db.add(
                AgentState(
                    execution_id=execution_id,
                    agent_name=agent_name.value,
                    state=state,
                )
            )
        await db.flush()

    async def update_execution_status(
        self,
        db: AsyncSession,
        execution_id: str,
        current_agent: AgentName,
        status: str = "processing",
        error_message: Optional[str] = None,
    ) -> None:
        """Update pipeline execution row with current agent and status."""
        stmt = (
            update(PipelineExecution)
            .where(PipelineExecution.id == execution_id)
            .values(
                current_agent=current_agent.value,
                status=status,
                error_message=error_message,
            )
        )
        await db.execute(stmt)
        await db.flush()

    async def persist_checkpoint(
        self,
        db: AsyncSession,
        execution_id: str,
        context: PipelineContext,
    ) -> None:
        """Persist full pipeline context as a checkpoint."""
        # Store checkpoint directly without using AgentName enum
        stmt = select(AgentState).where(
            AgentState.execution_id == execution_id,
            AgentState.agent_name == "_checkpoint",
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.state = context.to_checkpoint()
        else:
            db.add(
                AgentState(
                    execution_id=execution_id,
                    agent_name="_checkpoint",
                    state=context.to_checkpoint(),
                )
            )
        await db.flush()

    async def load_checkpoint(
        self,
        db: AsyncSession,
        execution_id: str,
    ) -> Optional[PipelineContext]:
        """Load pipeline context from checkpoint if it exists."""
        stmt = select(AgentState).where(
            AgentState.execution_id == execution_id,
            AgentState.agent_name == "_checkpoint",
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return PipelineContext.from_checkpoint(row.state)
        return None

    async def load_agent_state(
        self,
        db: AsyncSession,
        execution_id: str,
        agent_name: AgentName,
    ) -> Optional[Dict[str, Any]]:
        """Load a specific agent's persisted state."""
        stmt = select(AgentState).where(
            AgentState.execution_id == execution_id,
            AgentState.agent_name == agent_name.value,
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return row.state if row else None

    async def cleanup_expired_states(self, db: AsyncSession) -> int:
        """
        Remove agent_states older than STATE_CLEANUP_DAYS days.
        Audit logs (audit_logs table) are NOT touched — only agent_states.
        Returns count of deleted rows.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=STATE_CLEANUP_DAYS)
        stmt = delete(AgentState).where(AgentState.created_at < cutoff)
        result = await db.execute(stmt)
        deleted = result.rowcount
        await db.flush()
        logger.info("agent_state_cleanup_completed", deleted_rows=deleted, cutoff=cutoff.isoformat())
        return deleted


state_layer = StateManagementLayer()


# ---------------------------------------------------------------------------
# Latency-bounded agent runner (14.5)
# ---------------------------------------------------------------------------

async def run_with_budget(
    agent_name: AgentName,
    coro: Any,
) -> Any:
    """
    Run an agent coroutine within its latency budget.
    Raises asyncio.TimeoutError if the budget is exceeded.
    """
    budget = AGENT_LATENCY_BUDGETS[agent_name]
    try:
        return await asyncio.wait_for(coro, timeout=budget)
    except asyncio.TimeoutError:
        logger.warning(
            "agent_latency_budget_exceeded",
            agent=agent_name.value,
            budget_seconds=budget,
        )
        raise


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

class PipelineOrchestrator:
    """
    Orchestrates the full multi-agent pipeline with:
    - Sequential execution (14.1)
    - LLM provider call (14.2)
    - Atomic state persistence (14.3)
    - Checkpoint recovery (14.4)
    - Per-agent latency budgets (14.5)
    - Circuit breakers (14.6)
    - Partial result delivery (14.7)
    - State cleanup (14.8)
    """

    def __init__(self) -> None:
        # Lazy imports to avoid circular dependencies at module load time
        self._agents_loaded = False

    def _load_agents(self) -> None:
        if self._agents_loaded:
            return
        from app.agents.industry_classifier import industry_classifier
        from app.agents.design_agent import design_agent
        from app.agents.storyboarding import StoryboardingAgent
        from app.agents.research import research_agent
        from app.agents.data_enrichment import data_enrichment_agent
        from app.agents.prompt_engineering import prompt_engineering_agent
        from app.agents.validation import validation_agent
        from app.agents.quality_scoring import quality_scoring_agent
        from app.services.llm_provider import provider_factory
        from app.db.models import ProviderType as DBProviderType

        self._industry_classifier = industry_classifier
        self._design_agent = design_agent
        self._storyboarding = StoryboardingAgent()
        self._research = research_agent
        self._data_enrichment = data_enrichment_agent
        self._prompt_engineering = prompt_engineering_agent
        self._validation = validation_agent
        self._quality_scoring = quality_scoring_agent
        self._provider_factory = provider_factory
        self._DBProviderType = DBProviderType
        self._agents_loaded = True

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        presentation_id: str,
        topic: str,
        resume_from_checkpoint: bool = True,
        job_id: Optional[str] = None,
        user_selected_theme: Optional[str] = None,
        generation_mode: Optional[str] = None,
    ) -> PipelineContext:
        """
        Execute the full pipeline for a presentation.

        If resume_from_checkpoint=True and a checkpoint exists for this
        presentation, the pipeline resumes from the last completed agent.

        job_id is the Celery task ID; if provided, the orchestrator polls
        the Redis cancellation flag between agents (16.5).

        Returns the final PipelineContext (may be partial on failure).
        """
        self._load_agents()

        async with async_session_maker() as db:
            # Find or create pipeline execution
            execution_id = await self._get_or_create_execution(db, presentation_id)
            await db.commit()

        # Build or restore context
        async with async_session_maker() as db:
            ctx: Optional[PipelineContext] = None
            if resume_from_checkpoint:
                ctx = await state_layer.load_checkpoint(db, execution_id)

        if ctx is None:
            ctx = PipelineContext(
                presentation_id=presentation_id,
                execution_id=execution_id,
                topic=topic,
                user_selected_theme=user_selected_theme,
            )

        # Resolve generation_mode: user override > checkpoint > provider default
        if generation_mode:
            try:
                ctx.generation_mode = GenerationMode(generation_mode)
            except ValueError:
                logger.warning("invalid_generation_mode_ignored", mode=generation_mode)
        if ctx.generation_mode is None:
            # Derive from primary provider
            try:
                from app.db.models import ProviderType as _PT
                primary = self._provider_factory.primary_provider
                db_provider = _PT(primary.value)
                ctx.generation_mode = PROVIDER_DEFAULT_MODES.get(db_provider, GenerationMode.EXPRESS)
            except Exception:
                ctx.generation_mode = GenerationMode.EXPRESS

        logger.info(
            "generation_mode_resolved",
            presentation_id=presentation_id,
            generation_mode=ctx.generation_mode.value,
            user_override=generation_mode,
        )

        # Check final Slide_JSON cache before running the full pipeline (21.1)
        try:
            from app.services.presentation_cache import presentation_cache, compute_provider_config_hash
            from app.agents.prompt_engineering import PromptEngineeringAgent

            # We need industry + theme to build the key; these are only known after
            # Industry_Classifier runs.  If we have a checkpoint with detected_context
            # we can attempt a cache lookup immediately.
            if ctx.detected_context:
                _industry = ctx.detected_context.get("industry", "general")
                _theme = ctx.detected_context.get("theme", "ocean-depths")
                _provider = self._provider_factory.primary_provider.value if self._agents_loaded else "claude"
                _phash = compute_provider_config_hash(_provider)
                _pv = PromptEngineeringAgent.PROMPT_VERSION
                cached_slides = await presentation_cache.get_slide_json(
                    topic, _industry, _theme, _phash, _pv
                )
                if cached_slides is not None:
                    ctx.validated_slides = cached_slides
                    ctx.completed_agents = list(PIPELINE_SEQUENCE)
                    logger.info(
                        "pipeline_served_from_cache",
                        presentation_id=presentation_id,
                        industry=_industry,
                    )
                    await self._finalize(ctx)
                    return ctx
        except Exception as exc:
            logger.warning("slide_json_cache_lookup_failed", error=str(exc))

        pipeline_start = time.monotonic()

        # Keep iterating until all agents complete or we hit a failure
        # This allows feedback loops to re-run agents
        max_iterations = 20  # Safety limit to prevent infinite loops
        iteration = 0
        
        while set(ctx.completed_agents) != set(PIPELINE_SEQUENCE) and iteration < max_iterations:
            iteration += 1
            made_progress = False
            
            for agent_name in PIPELINE_SEQUENCE:
                # Skip already-completed agents (checkpoint recovery)
                if agent_name in ctx.completed_agents:
                    continue

                made_progress = True

                # Check total pipeline budget
                elapsed = time.monotonic() - pipeline_start
                remaining = PIPELINE_TOTAL_BUDGET_SECONDS - elapsed
                if remaining <= 0:
                    logger.warning("pipeline_total_budget_exceeded", elapsed=elapsed)
                    ctx.error_message = "Pipeline total time budget exceeded"
                    break

                # Cancellation check (16.5) — poll between agents
                if job_id:
                    try:
                        from app.services.streaming import streaming_service
                        if await streaming_service.is_cancelled(job_id):
                            logger.info(
                                "pipeline_cancelled_by_user",
                                job_id=job_id,
                                presentation_id=presentation_id,
                            )
                            ctx.error_message = "Job cancelled by user"
                            ctx.failed_agent = agent_name
                            await streaming_service.clear_cancellation_flag(job_id)
                            break
                    except Exception:
                        pass  # cancellation check failures must not break the pipeline

                # Circuit breaker check (14.6)
                cb = get_circuit_breaker(agent_name)
                if not cb.allow_call():
                    logger.warning(
                        "circuit_breaker_blocking_agent",
                        agent=agent_name.value,
                        failure_rate=cb.failure_rate,
                    )
                    ctx.error_message = f"Circuit breaker open for agent {agent_name.value}"
                    ctx.failed_agent = agent_name
                    break

                # Run agent
                success = await self._run_agent(agent_name, ctx)
                cb.record(success)

                if not success:
                    # Partial result delivery (14.7): persist what we have and stop
                    await self._persist_partial_result(ctx)
                    break
            
            # If we didn't make progress and still have incomplete agents, break to avoid infinite loop
            if not made_progress and set(ctx.completed_agents) != set(PIPELINE_SEQUENCE):
                logger.warning(
                    "pipeline_stalled",
                    completed=len(ctx.completed_agents),
                    total=len(PIPELINE_SEQUENCE),
                    iteration=iteration
                )
                break
            
            # If we hit an error, break
            if ctx.error_message or ctx.failed_agent:
                break

        # Final DB update
        await self._finalize(ctx)
        return ctx

    # ------------------------------------------------------------------
    # Agent dispatch
    # ------------------------------------------------------------------

    async def _run_agent(self, agent_name: AgentName, ctx: PipelineContext) -> bool:
        """
        Run a single agent, persist its state, and return success flag.
        Publishes agent_start / agent_complete / error streaming events (16.2).
        Wraps execution with LangSmith observability tracing (30.1, 30.2).
        """
        logger.info("agent_started", agent=agent_name.value, execution_id=ctx.execution_id)
        agent_start = time.monotonic()

        # Resolve provider and industry for observability tags (30.1)
        provider_name: Optional[str] = None
        industry: Optional[str] = None
        try:
            if self._agents_loaded and self._provider_factory.primary_provider:
                provider_name = self._provider_factory.primary_provider.value
            if ctx.detected_context:
                industry = ctx.detected_context.get("industry")
        except Exception:
            pass

        async with async_session_maker() as db:
            await state_layer.update_execution_status(db, ctx.execution_id, agent_name)
            await db.commit()

        # Publish agent_start event (16.2)
        try:
            from app.services.streaming import streaming_service
            await streaming_service.publish_agent_start(
                ctx.presentation_id, agent_name.value, ctx.execution_id,
                generation_mode=ctx.generation_mode.value if ctx.generation_mode else None,
            )
        except Exception:
            pass  # streaming failures must never break the pipeline

        # Import observability service (lazy to avoid circular imports)
        try:
            from app.services.observability import observability as obs_service
            _obs = obs_service
        except Exception:
            _obs = None

        try:
            if _obs is not None:
                async with _obs.trace_agent(
                    agent_name=agent_name.value,
                    execution_id=ctx.execution_id,
                    provider=provider_name,
                    industry=industry,
                ) as run_record:
                    coro = self._dispatch(agent_name, ctx)
                    await run_with_budget(agent_name, coro)
                    elapsed_ms = (time.monotonic() - agent_start) * 1000
                    run_record.end_time = time.monotonic()
                    run_record.success = True
            else:
                coro = self._dispatch(agent_name, ctx)
                await run_with_budget(agent_name, coro)
                elapsed_ms = (time.monotonic() - agent_start) * 1000

            logger.info(
                "agent_completed",
                agent=agent_name.value,
                elapsed_ms=round(elapsed_ms, 1),
            )

            ctx.completed_agents.append(agent_name)

            # Persist state after each agent (14.3)
            async with async_session_maker() as db:
                await self._persist_agent_output(db, agent_name, ctx)
                await state_layer.persist_checkpoint(db, ctx.execution_id, ctx)
                await db.commit()

            # Publish agent_complete event (16.2)
            try:
                from app.services.streaming import streaming_service
                logger.info(
                    "publishing_agent_complete_event",
                    agent=agent_name.value,
                    presentation_id=ctx.presentation_id,
                    execution_id=ctx.execution_id,
                    elapsed_ms=round(elapsed_ms, 1)
                )
                await streaming_service.publish_agent_complete(
                    ctx.presentation_id, agent_name.value, ctx.execution_id, elapsed_ms
                )
                logger.info(
                    "agent_complete_event_published",
                    agent=agent_name.value,
                    presentation_id=ctx.presentation_id
                )
                # After validation, emit slide_ready events for progressive rendering (16.3)
                if agent_name == AgentName.VALIDATION and ctx.validated_slides:
                    logger.info(
                        "publishing_slide_ready_events",
                        presentation_id=ctx.presentation_id,
                        slide_count=len(ctx.validated_slides.get("slides", []))
                    )
                    await self._publish_slide_ready_events(ctx)
                    logger.info(
                        "slide_ready_events_published",
                        presentation_id=ctx.presentation_id
                    )
                # After quality scoring, emit quality_score event (16.2)
                if agent_name == AgentName.QUALITY_SCORING and ctx.quality_result:
                    qr = ctx.quality_result
                    await streaming_service.publish_quality_score(
                        ctx.presentation_id,
                        composite_score=qr.get("composite_score", 0.0),
                        dimensions={
                            "content_depth": qr.get("content_depth", 0.0),
                            "visual_appeal": qr.get("visual_appeal", 0.0),
                            "structure_coherence": qr.get("structure_coherence", 0.0),
                            "data_accuracy": qr.get("data_accuracy", 0.0),
                            "clarity": qr.get("clarity", 0.0),
                        },
                    )
                    # 30.4 — Check quality score alert after retries exhausted
                    if _obs is not None:
                        _obs.check_quality_score(
                            quality_score=qr.get("composite_score", 0.0),
                            execution_id=ctx.execution_id,
                            retry_count=ctx.feedback_loop_count,
                            max_retries=2,
                        )
            except Exception:
                pass  # streaming failures must never break the pipeline

            return True

        except asyncio.TimeoutError:
            ctx.failed_agent = agent_name
            ctx.error_message = (
                f"Agent {agent_name.value} exceeded latency budget "
                f"({AGENT_LATENCY_BUDGETS[agent_name]}s)"
            )
            logger.error("agent_timeout", agent=agent_name.value)
            try:
                from app.services.streaming import streaming_service
                await streaming_service.publish_error(
                    ctx.presentation_id, ctx.execution_id,
                    ctx.error_message, agent_name.value
                )
            except Exception:
                pass
            return False

        except Exception as exc:
            ctx.failed_agent = agent_name
            ctx.error_message = str(exc)
            logger.error("agent_failed", agent=agent_name.value, error=str(exc), exc_info=True)
            try:
                from app.services.streaming import streaming_service
                await streaming_service.publish_error(
                    ctx.presentation_id, ctx.execution_id,
                    ctx.error_message, agent_name.value
                )
            except Exception:
                pass
            return False

    async def _publish_slide_ready_events(self, ctx: PipelineContext) -> None:
        """Emit a slide_ready event for each validated slide (16.3)."""
        try:
            from app.services.streaming import streaming_service
            slides_data = ctx.validated_slides or {}
            slides = slides_data.get("slides", [])
            total = len(slides)
            
            _type_mapping = {
                "title": "title", "title_slide": "title",
                "content": "content", "content_slide": "content",
                "chart": "chart", "chart_slide": "chart",
                "table": "table", "table_slide": "table",
                "comparison": "comparison", "comparison_slide": "comparison",
                "metric": "metric", "metric_slide": "metric",
            }
            _hint_to_type = {
                "centered": "title",
                "split-chart-right": "chart",
                "split-table-left": "table",
                "two-column": "comparison",
                "bullet-left": "content",
                "highlight-metric": "metric",
            }
            
            for slide in slides:
                # Normalize type: prefer slide_type over type
                slide_copy = dict(slide)
                slide_type_raw = slide_copy.get("slide_type") or slide_copy.get("type", "content")
                correct_type = _type_mapping.get(str(slide_type_raw).lower(), "content")
                if correct_type == "content" and slide_copy.get("visual_hint"):
                    # Try to infer from visual_hint
                    correct_type = _hint_to_type.get(slide_copy["visual_hint"], "content")
                slide_copy["type"] = correct_type
                
                await streaming_service.publish_slide_ready(
                    ctx.presentation_id,
                    slide=slide_copy,
                    slide_number=slide_copy.get("slide_number", 0),
                    total_slides=total,
                )
        except Exception as exc:
            logger.warning("slide_ready_publish_failed", error=str(exc))

    async def _dispatch(self, agent_name: AgentName, ctx: PipelineContext) -> None:
        """Route to the correct agent implementation."""
        if agent_name == AgentName.INDUSTRY_CLASSIFIER:
            await self._run_industry_classifier(ctx)
        elif agent_name == AgentName.DESIGN:
            await self._run_design_agent(ctx)
        elif agent_name == AgentName.STORYBOARDING:
            await self._run_storyboarding(ctx)
        elif agent_name == AgentName.RESEARCH:
            await self._run_research(ctx)
        elif agent_name == AgentName.DATA_ENRICHMENT:
            await self._run_data_enrichment(ctx)
        elif agent_name == AgentName.PROMPT_ENGINEERING:
            await self._run_prompt_engineering(ctx)
        elif agent_name == AgentName.LLM_PROVIDER:
            await self._run_llm_provider(ctx)
        elif agent_name == AgentName.VALIDATION:
            await self._run_validation(ctx)
        elif agent_name == AgentName.VISUAL_REFINEMENT:
            await self._run_visual_refinement(ctx)
        elif agent_name == AgentName.QUALITY_SCORING:
            await self._run_quality_scoring(ctx)
        elif agent_name == AgentName.VISUAL_QA:
            await self._run_visual_qa(ctx)

    # ------------------------------------------------------------------
    # Individual agent runners
    # ------------------------------------------------------------------

    async def _run_industry_classifier(self, ctx: PipelineContext) -> None:
        logger.info(
            "industry_classifier_input",
            execution_id=ctx.execution_id,
            topic=ctx.topic[:100],
            topic_length=len(ctx.topic)
        )
        
        result = await self._industry_classifier.classify(
            topic=ctx.topic,
            execution_id=ctx.execution_id,
        )

        # Override theme if user explicitly selected one
        theme = result.theme
        if ctx.user_selected_theme:
            theme = ctx.user_selected_theme
            logger.info(
                "user_theme_override",
                auto_theme=result.theme,
                user_theme=theme,
                execution_id=ctx.execution_id,
            )

        ctx.detected_context = {
            "industry": result.industry,
            "confidence": result.confidence,
            "sub_sector": result.sub_sector,
            "target_audience": result.target_audience,
            "selected_template_id": result.selected_template_id,
            "selected_template_name": result.selected_template_name,
            "theme": theme,
            "compliance_context": result.compliance_context,
            "classification_method": result.classification_method,
        }
        
        logger.info(
            "industry_classifier_output",
            execution_id=ctx.execution_id,
            industry=result.industry,
            confidence=result.confidence,
            sub_sector=result.sub_sector,
            target_audience=result.target_audience,
            template_name=result.selected_template_name,
            theme=theme,
            method=result.classification_method
        )

    async def _run_design_agent(self, ctx: PipelineContext) -> None:
        """Run the DesignAgent to produce a topic-specific DesignSpec."""
        detected = ctx.detected_context or {}
        industry = detected.get("industry", "general")
        theme = detected.get("theme", "ocean-depths")

        logger.info(
            "design_agent_input",
            execution_id=ctx.execution_id,
            topic=ctx.topic[:80],
            industry=industry,
            theme=theme,
        )

        spec = await self._design_agent.generate_design_spec(
            topic=ctx.topic,
            industry=industry,
            theme=theme,
            execution_id=ctx.execution_id,
        )
        ctx.design_spec = spec.to_dict()

        logger.info(
            "design_agent_output",
            execution_id=ctx.execution_id,
            palette=spec.palette_name,
            primary=spec.primary_color,
            accent=spec.accent_color,
            motif=spec.motif,
            font_header=spec.font_header,
        )

    async def _run_storyboarding(self, ctx: PipelineContext) -> None:
        detected = ctx.detected_context or {}
        industry = detected.get("industry", "general")
        template_name = detected.get("selected_template_name", "")
        
        logger.info(
            "storyboarding_input",
            execution_id=ctx.execution_id,
            industry=industry,
            template_name=template_name,
            topic=ctx.topic[:100]
        )

        # 29.3 — Load template slide_structure and pass as Storyboarding constraint
        template_structure: list[dict] | None = None
        template_slide_count: int | None = None
        resolved_template_id: str | None = None

        try:
            from app.services.template_service import (
                resolve_template_for_industry,
                extract_storyboarding_constraints,
            )
            async with async_session_maker() as db:
                template = await resolve_template_for_industry(
                    db=db,
                    industry=industry,
                    template_name=template_name,
                )
                if template:
                    constraints = extract_storyboarding_constraints(template)
                    template_structure = constraints["slide_structure"]
                    template_slide_count = constraints["slide_count"] or None
                    resolved_template_id = constraints["template_id"]
                    logger.info(
                        "storyboarding_template_applied",
                        template_id=resolved_template_id,
                        template_name=constraints["template_name"],
                        slide_count=template_slide_count,
                    )
        except Exception as exc:
            logger.warning("template_load_failed_using_defaults", error=str(exc))

        plan = self._storyboarding.generate_presentation_plan(
            topic=ctx.topic,
            industry=industry,
            template_structure=template_structure,
            template_slide_count=template_slide_count,
        )
        ctx.presentation_plan = plan.model_dump()

        # Store resolved template_id so _finalize can update the presentation row
        # and increment usage_count (29.5)
        if resolved_template_id:
            ctx.detected_context = {**detected, "resolved_template_id": resolved_template_id}
        
        logger.info(
            "storyboarding_output",
            execution_id=ctx.execution_id,
            slide_count=len(plan.sections),
            sections=len(plan.sections),
            has_template=resolved_template_id is not None
        )

    async def _run_research(self, ctx: PipelineContext) -> None:
        detected = ctx.detected_context or {}
        industry = detected.get("industry", "general")
        
        logger.info(
            "research_input",
            execution_id=ctx.execution_id,
            topic=ctx.topic[:100],
            industry=industry,
            sub_sector=detected.get("sub_sector"),
            target_audience=detected.get("target_audience", "general")
        )

        # Check research cache first (21.2)
        try:
            from app.services.presentation_cache import presentation_cache
            cached = await presentation_cache.get_research(ctx.topic, industry)
            if cached is not None:
                logger.info(
                    "research_served_from_cache",
                    topic=ctx.topic[:60],
                    industry=industry,
                )
                ctx.research_findings = cached
                return
        except Exception as exc:
            logger.warning("research_cache_lookup_failed", error=str(exc))

        findings = await self._research.analyze_topic(
            topic=ctx.topic,
            industry=industry,
            execution_id=ctx.execution_id,
            sub_sector=detected.get("sub_sector"),
            target_audience=detected.get("target_audience", "general"),
        )
        ctx.research_findings = findings.to_dict()
        
        logger.info(
            "research_output",
            execution_id=ctx.execution_id,
            has_sections=bool(findings.sections),
            sections_count=len(findings.sections) if findings.sections else 0,
            has_risks=bool(findings.risks),
            risks_count=len(findings.risks) if findings.risks else 0,
            has_opportunities=bool(findings.opportunities),
            opportunities_count=len(findings.opportunities) if findings.opportunities else 0,
            has_terminology=bool(findings.terminology),
            terminology_count=len(findings.terminology) if findings.terminology else 0,
            method=findings.method
        )

        # Populate research cache (21.2)
        try:
            from app.services.presentation_cache import presentation_cache
            await presentation_cache.set_research(ctx.topic, industry, ctx.research_findings)
        except Exception as exc:
            logger.warning("research_cache_store_failed", error=str(exc))

    async def _run_data_enrichment(self, ctx: PipelineContext) -> None:
        detected = ctx.detected_context or {}
        industry = detected.get("industry", "general")
        
        logger.info(
            "data_enrichment_input",
            execution_id=ctx.execution_id,
            topic=ctx.topic[:100],
            industry=industry,
            has_research_findings=bool(ctx.research_findings)
        )

        # Check enrichment cache first (21.2)
        try:
            from app.services.presentation_cache import presentation_cache
            cached = await presentation_cache.get_enrichment(ctx.topic, industry)
            if cached is not None:
                logger.info(
                    "enrichment_served_from_cache",
                    topic=ctx.topic[:60],
                    industry=industry,
                )
                ctx.enriched_data = cached
                return
        except Exception as exc:
            logger.warning("enrichment_cache_lookup_failed", error=str(exc))

        enriched = await self._data_enrichment.enrich_data(
            topic=ctx.topic,
            industry=industry,
            execution_id=ctx.execution_id,
            research_findings=ctx.research_findings,
        )
        ctx.enriched_data = enriched.to_dict()
        
        logger.info(
            "data_enrichment_output",
            execution_id=ctx.execution_id,
            has_charts=bool(enriched.charts),
            charts_count=len(enriched.charts) if enriched.charts else 0,
            has_tables=bool(enriched.tables),
            tables_count=len(enriched.tables) if enriched.tables else 0,
            has_key_metrics=bool(enriched.key_metrics),
            key_metrics_count=len(enriched.key_metrics) if enriched.key_metrics else 0
        )

        # Populate enrichment cache (21.2)
        try:
            from app.services.presentation_cache import presentation_cache
            await presentation_cache.set_enrichment(ctx.topic, industry, ctx.enriched_data)
        except Exception as exc:
            logger.warning("enrichment_cache_store_failed", error=str(exc))

    async def _run_prompt_engineering(self, ctx: PipelineContext) -> None:
        from app.db.models import ProviderType as DBProviderType

        # Map provider factory type to DB ProviderType
        primary = self._provider_factory.primary_provider
        try:
            db_provider = DBProviderType(primary.value)
        except ValueError:
            db_provider = DBProviderType.claude
        
        logger.info(
            "prompt_engineering_input",
            execution_id=ctx.execution_id,
            provider=db_provider.value,
            industry=(ctx.detected_context or {}).get("industry", "general"),
            has_research=bool(ctx.research_findings),
            has_plan=bool(ctx.presentation_plan),
            has_enrichment=bool(ctx.enriched_data)
        )

        prompt = self._prompt_engineering.generate_prompt(
            provider_type=db_provider,
            topic=ctx.topic,
            industry=(ctx.detected_context or {}).get("industry", "general"),
            research_findings=ctx.research_findings or {},
            presentation_plan=ctx.presentation_plan or {},
            data_enrichment=ctx.enriched_data,
            design_spec=ctx.design_spec,
            execution_id=ctx.execution_id,
            generation_mode=ctx.generation_mode,
        )
        ctx.optimized_prompt = prompt.to_dict()
        
        logger.info(
            "prompt_engineering_output",
            execution_id=ctx.execution_id,
            prompt_id=prompt.prompt_id,
            version=prompt.version,
            system_prompt_length=len(prompt.system_prompt),
            user_prompt_length=len(prompt.user_prompt),
            estimated_tokens=prompt.estimated_tokens
        )

        # Persist prompt metadata to pipeline execution
        async with async_session_maker() as db:
            stmt = (
                update(PipelineExecution)
                .where(PipelineExecution.id == ctx.execution_id)
                .values(
                    prompt_id=prompt.prompt_id,
                    prompt_version=prompt.version,
                    prompt_metadata=prompt.metadata,
                )
            )
            await db.execute(stmt)
            await db.commit()

    async def _run_llm_provider(self, ctx: PipelineContext) -> None:
        """
        Invoke the configured primary LLM provider with optimised prompts
        and receive structured Slide_JSON (14.2).

        After the call, if a failover occurred (the provider that actually
        served the request differs from the primary), remap generation_mode
        to the new provider's default (Req 1.5).
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt_data = ctx.optimized_prompt or {}
        system_prompt = prompt_data.get("system_prompt", "")
        user_prompt = prompt_data.get("user_prompt", "")

        # Record the primary provider *before* the call so we can detect failover
        pre_call_provider = self._provider_factory.primary_provider
        
        logger.info(
            "llm_provider_input",
            execution_id=ctx.execution_id,
            system_prompt_length=len(system_prompt),
            user_prompt_length=len(user_prompt),
            provider=pre_call_provider.value if pre_call_provider else "unknown",
            generation_mode=ctx.generation_mode.value if ctx.generation_mode else None,
        )

        # Track which provider actually served the request
        _used_provider = [pre_call_provider]  # mutable container for closure

        async def call_llm(client, *args, **kwargs):
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = await client.ainvoke(messages)
            return response.content

        raw_content = await self._provider_factory.call_with_failover(
            call_llm,
            execution_id=ctx.execution_id,
            industry=(ctx.detected_context or {}).get("industry"),
        )

        # Detect provider failover and remap generation_mode (Req 1.5)
        try:
            from app.db.models import ProviderType as _PT
            # After failover, the health monitor may have changed the effective provider.
            # We check the fallback sequence — if primary failed, the next healthy one was used.
            fallback_seq = self._provider_factory.get_fallback_sequence()
            from app.services.provider_health import health_monitor
            effective_provider = health_monitor.select_provider(fallback_seq)
            if effective_provider and effective_provider != pre_call_provider:
                old_mode = ctx.generation_mode
                db_provider = _PT(effective_provider.value)
                ctx.generation_mode = PROVIDER_DEFAULT_MODES.get(db_provider, GenerationMode.EXPRESS)
                logger.info(
                    "generation_mode_remapped_after_failover",
                    from_provider=pre_call_provider.value if pre_call_provider else "unknown",
                    to_provider=effective_provider.value,
                    old_mode=old_mode.value if old_mode else None,
                    new_mode=ctx.generation_mode.value,
                )
        except Exception as exc:
            logger.warning("failover_mode_remap_check_failed", error=str(exc))
        
        logger.info(
            "llm_provider_raw_response",
            execution_id=ctx.execution_id,
            response_length=len(raw_content),
            response_preview=raw_content[:200]
        )

        # Parse JSON from LLM response
        import json, re
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json|javascript)?\s*", "", raw_content).strip().rstrip("`").strip()

        # --- Artisan mode: the LLM returns { "artisan_code": "..." } or a
        # raw script.  Skip the slides-oriented normalisation path. ---
        if ctx.generation_mode == GenerationMode.ARTISAN:
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                # Try to extract a JSON object
                match = re.search(r"\{.*\}", cleaned, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group())
                    except json.JSONDecodeError:
                        # Treat the whole response as a raw script
                        parsed = {"artisan_code": cleaned}
                else:
                    # Treat the whole response as a raw script
                    parsed = {"artisan_code": cleaned}

            # If parsed dict doesn't have artisan_code, try to find it
            if isinstance(parsed, dict) and "artisan_code" not in parsed:
                for val in parsed.values():
                    if isinstance(val, str) and "pres.addSlide()" in val:
                        parsed = {"artisan_code": val}
                        break
                else:
                    # Wrap the whole cleaned content as artisan_code
                    parsed = {"artisan_code": cleaned}

            ctx.raw_llm_output = parsed
            logger.info(
                "llm_provider_output_artisan",
                execution_id=ctx.execution_id,
                artisan_code_length=len(parsed.get("artisan_code", "")),
            )
            return

        try:
            slide_json = json.loads(cleaned)
            logger.info(
                "llm_provider_json_parsed",
                execution_id=ctx.execution_id,
                slide_count=len(slide_json.get("slides", [])) if isinstance(slide_json, dict) else 0
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "json_parse_failed_attempting_extraction",
                error=str(e),
                content_length=len(cleaned),
                content_preview=cleaned[:500],
                char_position=e.pos if hasattr(e, 'pos') else None,
            )
            # Attempt to extract JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                extracted = match.group()
                try:
                    slide_json = json.loads(extracted)
                    logger.info(
                        "llm_provider_json_extracted",
                        execution_id=ctx.execution_id,
                        slide_count=len(slide_json.get("slides", [])) if isinstance(slide_json, dict) else 0
                    )
                except json.JSONDecodeError as e2:
                    # Try to repair truncated JSON by closing open structures
                    logger.warning("attempting_json_repair_for_truncation", error=str(e2))
                    repaired = extracted.rstrip()
                    # Count open/close brackets and braces
                    open_braces = repaired.count('{') - repaired.count('}')
                    open_brackets = repaired.count('[') - repaired.count(']')
                    # Close them
                    repaired += ']' * open_brackets + '}' * open_braces
                    try:
                        slide_json = json.loads(repaired)
                        logger.info("json_repaired_successfully", slides_added=open_braces + open_brackets)
                    except json.JSONDecodeError:
                        logger.error(
                            "json_repair_failed",
                            error=str(e2),
                            char_position=e2.pos if hasattr(e2, 'pos') else None,
                            content_length=len(extracted),
                        )
                        raise ValueError(f"LLM response truncated at char {e2.pos if hasattr(e2, 'pos') else '?'}. Increase max_tokens.")
            else:
                raise ValueError(f"LLM did not return valid JSON: {cleaned[:200]}")

        # Normalize: handle cases where LLM wraps slides under a nested key
        # e.g. {"presentation": {"slides": [...]}} or just a list
        if isinstance(slide_json, list):
            # LLM returned a bare array — wrap it
            slide_json = {"schema_version": "1.0.0", "slides": slide_json, "total_slides": len(slide_json)}
        elif isinstance(slide_json, dict):
            if "slides" not in slide_json:
                # Search one level deep for a slides array
                for key, val in slide_json.items():
                    if isinstance(val, dict) and "slides" in val:
                        logger.warning("llm_output_slides_nested", outer_key=key)
                        slide_json = val
                        break
                    elif isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and "type" in val[0]:
                        logger.warning("llm_output_slides_as_value", key=key)
                        slide_json = {"schema_version": "1.0.0", "slides": val, "total_slides": len(val)}
                        break
            # Ensure required top-level fields
            if "slides" not in slide_json:
                slide_json["slides"] = []
            if "schema_version" not in slide_json:
                slide_json["schema_version"] = "1.0.0"
            if "total_slides" not in slide_json:
                slide_json["total_slides"] = len(slide_json.get("slides", []))

        ctx.raw_llm_output = slide_json
        
        logger.info(
            "llm_provider_output",
            execution_id=ctx.execution_id,
            total_slides=slide_json.get("total_slides", 0) if isinstance(slide_json, dict) else 0,
            slides_array_length=len(slide_json.get("slides", [])) if isinstance(slide_json, dict) else 0
        )

    async def _run_validation(self, ctx: PipelineContext) -> None:
        raw = ctx.raw_llm_output or {}
        
        logger.info(
            "validation_input",
            execution_id=ctx.execution_id,
            has_slides=bool(raw.get("slides")),
            slide_count=len(raw.get("slides", [])),
            has_schema_version=bool(raw.get("schema_version")),
            generation_mode=ctx.generation_mode.value if ctx.generation_mode else None,
        )
        
        validation_start = time.monotonic()
        result = self._validation.validate(
            data=raw,
            execution_id=ctx.execution_id,
            apply_corrections=True,
            generation_mode=ctx.generation_mode,
        )
        validation_elapsed = (time.monotonic() - validation_start) * 1000
        ctx.validated_slides = result.corrected_data or raw
        
        logger.info(
            "validation_output",
            execution_id=ctx.execution_id,
            is_valid=result.is_valid,
            errors_count=len(result.errors),
            corrections_applied=result.corrections_applied,
            final_slide_count=len(ctx.validated_slides.get("slides", [])),
            elapsed_ms=round(validation_elapsed, 1),
        )

        # --- Artisan retry logic (Req 6.1, 6.2, 6.3) ---
        # On validation failure: retry LLM once with same prompt.
        # On runtime error: retry once with error message appended.
        # After both retries fail: fall back to STUDIO mode and re-run
        # from PROMPT_ENGINEERING.
        if ctx.generation_mode == GenerationMode.ARTISAN and not result.is_valid:
            artisan_retried = await self._artisan_retry(ctx, result)
            if artisan_retried:
                # Retry succeeded — ctx.validated_slides already updated
                return

        # Track code generation success/failure for mode downgrade (Req 6.4)
        if ctx.generation_mode in (GenerationMode.STUDIO, GenerationMode.CRAFT, GenerationMode.ARTISAN):
            try:
                provider_name = self._provider_factory.primary_provider.value
                tracker = get_code_failure_tracker()
                code_success = result.is_valid and len(result.errors) == 0
                tracker.record(provider_name, code_success)

                if tracker.should_downgrade(provider_name):
                    old_mode = ctx.generation_mode
                    ctx.generation_mode = tracker.downgraded_mode(old_mode)
                    logger.warning(
                        "generation_mode_downgraded",
                        provider=provider_name,
                        failure_rate=round(tracker.failure_rate(provider_name), 2),
                        old_mode=old_mode.value,
                        new_mode=ctx.generation_mode.value,
                    )
            except Exception as exc:
                logger.warning("code_failure_tracking_error", error=str(exc))

    async def _artisan_retry(
        self,
        ctx: PipelineContext,
        initial_result: Any,
    ) -> bool:
        """Artisan-mode retry logic (Req 6.1, 6.2, 6.3).

        1. Retry the LLM call once with the same prompt (validation failure).
        2. If the first retry also fails, retry once more with the error
           message appended to the prompt (runtime error context).
        3. If both retries fail, fall back to STUDIO mode and schedule a
           re-run from PROMPT_ENGINEERING.

        Returns True if a retry succeeded and ctx.validated_slides is updated.
        Returns False if all retries failed (fallback to STUDIO was triggered).
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt_data = ctx.optimized_prompt or {}
        system_prompt = prompt_data.get("system_prompt", "")
        user_prompt = prompt_data.get("user_prompt", "")

        error_messages = [e.message for e in initial_result.errors if hasattr(e, "message")]
        error_summary = "; ".join(error_messages) if error_messages else "Validation failed"

        # --- Retry 1: same prompt ---
        logger.info(
            "artisan_retry_attempt",
            execution_id=ctx.execution_id,
            attempt=1,
            reason=error_summary[:200],
        )
        retry_result = await self._artisan_llm_retry(
            ctx, system_prompt, user_prompt,
        )
        if retry_result is not None:
            ctx.validated_slides = retry_result
            logger.info("artisan_retry_succeeded", execution_id=ctx.execution_id, attempt=1)
            return True

        # --- Retry 2: append error context ---
        augmented_prompt = (
            f"{user_prompt}\n\n"
            f"IMPORTANT: Your previous attempt failed with the following errors. "
            f"Please fix these issues:\n{error_summary}"
        )
        logger.info(
            "artisan_retry_attempt",
            execution_id=ctx.execution_id,
            attempt=2,
            reason="retry_with_error_context",
        )
        retry_result = await self._artisan_llm_retry(
            ctx, system_prompt, augmented_prompt,
        )
        if retry_result is not None:
            ctx.validated_slides = retry_result
            logger.info("artisan_retry_succeeded", execution_id=ctx.execution_id, attempt=2)
            return True

        # --- Both retries failed: fall back to STUDIO mode (Req 6.3) ---
        logger.warning(
            "artisan_fallback_to_studio",
            execution_id=ctx.execution_id,
            error=error_summary[:200],
        )
        ctx.generation_mode = GenerationMode.STUDIO

        # Record the failure for CodeFailureTracker
        try:
            provider_name = self._provider_factory.primary_provider.value
            tracker = get_code_failure_tracker()
            tracker.record(provider_name, False)
        except Exception:
            pass

        # Remove downstream agents so the pipeline re-runs from PROMPT_ENGINEERING
        for agent in [
            AgentName.PROMPT_ENGINEERING,
            AgentName.LLM_PROVIDER,
            AgentName.VALIDATION,
            AgentName.VISUAL_REFINEMENT,
            AgentName.QUALITY_SCORING,
            AgentName.VISUAL_QA,
        ]:
            if agent in ctx.completed_agents:
                ctx.completed_agents.remove(agent)

        return False

    async def _artisan_llm_retry(
        self,
        ctx: PipelineContext,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Call the LLM and validate the response for artisan mode.

        Returns the validated corrected_data dict on success, or None on
        failure.
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        import json
        import re

        try:
            async def call_llm(client, *args, **kwargs):
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
                response = await client.ainvoke(messages)
                return response.content

            raw_content = await self._provider_factory.call_with_failover(
                call_llm,
                execution_id=ctx.execution_id,
                industry=(ctx.detected_context or {}).get("industry"),
            )

            # Parse the LLM response — artisan mode returns { "artisan_code": "..." }
            cleaned = re.sub(r"```(?:json|javascript)?\s*", "", raw_content).strip().rstrip("`").strip()
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                # Try to extract JSON object
                match = re.search(r"\{.*\}", cleaned, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group())
                    except json.JSONDecodeError:
                        return None
                else:
                    # Might be raw script without JSON wrapper
                    parsed = {"artisan_code": cleaned}

            # If parsed is not a dict with artisan_code, wrap it
            if isinstance(parsed, dict) and "artisan_code" not in parsed:
                # Check if any value looks like artisan code
                for val in parsed.values():
                    if isinstance(val, str) and "pres.addSlide()" in val:
                        parsed = {"artisan_code": val}
                        break

            ctx.raw_llm_output = parsed

            # Validate
            result = self._validation.validate(
                data=parsed,
                execution_id=ctx.execution_id,
                apply_corrections=True,
                generation_mode=GenerationMode.ARTISAN,
            )

            if result.is_valid:
                return result.corrected_data or parsed
            return None

        except Exception as exc:
            logger.warning(
                "artisan_retry_llm_call_failed",
                execution_id=ctx.execution_id,
                error=str(exc),
            )
            return None

    async def _run_visual_refinement(self, ctx: PipelineContext) -> None:
        """
        Run Visual Refinement Agent to polish icons, highlight text, and speaker notes.
        
        Phase 5 Optimization: Uses optimized visual refinement with caching, batch processing,
        and selective enhancement to reduce costs by 50-70%.
        
        This is the highest ROI enhancement: +0.70 quality points for $0.0076 per presentation
        (or $0.0023-$0.0038 with optimizations enabled).

        Skipped for artisan mode — the LLM script handles all visual styling directly.
        """
        # Artisan mode: the LLM generates the complete script with all visual
        # styling baked in; visual refinement operates on slide JSON dicts and
        # is not applicable.
        if ctx.generation_mode == GenerationMode.ARTISAN:
            logger.info(
                "visual_refinement_skipped_artisan_mode",
                execution_id=ctx.execution_id,
            )
            return

        from app.services.optimized_visual_refinement import optimized_visual_refinement
        from app.core.config import settings
        
        slides_data = ctx.validated_slides or {}
        slides = slides_data.get("slides", [])
        detected = ctx.detected_context or {}
        industry = detected.get("industry", "general")
        design_spec = ctx.design_spec
        
        # Check if optimizations are enabled (default: True)
        use_optimizations = getattr(settings, "ENABLE_PHASE5_OPTIMIZATIONS", True)
        use_caching = getattr(settings, "ENABLE_LLM_CACHING", True)
        use_batch_processing = getattr(settings, "ENABLE_BATCH_PROCESSING", True)
        use_selective_enhancement = getattr(settings, "ENABLE_SELECTIVE_ENHANCEMENT", True)
        
        logger.info(
            "visual_refinement_input",
            execution_id=ctx.execution_id,
            slide_count=len(slides),
            industry=industry,
            has_design_spec=bool(design_spec),
            optimizations_enabled=use_optimizations,
            caching_enabled=use_caching,
            batch_processing_enabled=use_batch_processing,
            selective_enhancement_enabled=use_selective_enhancement,
        )
        
        if use_optimizations:
            # Use optimized visual refinement (Phase 5)
            refined_slides = await optimized_visual_refinement.refine_presentation_optimized(
                slides=slides,
                execution_id=ctx.execution_id,
                use_batch_processing=use_batch_processing,
                use_selective_enhancement=use_selective_enhancement,
            )
            
            # Get optimization statistics
            stats = optimized_visual_refinement.get_optimization_stats(slides)
            
            logger.info(
                "visual_refinement_output_optimized",
                execution_id=ctx.execution_id,
                refined_slide_count=len(refined_slides),
                icons_refined=sum(1 for s in refined_slides if s.get("content", {}).get("icon_name")),
                highlights_refined=sum(1 for s in refined_slides if s.get("content", {}).get("highlight_text")),
                notes_refined=sum(1 for s in refined_slides if s.get("content", {}).get("speaker_notes")),
                optimization_stats=stats,
            )
        else:
            # Use original visual refinement (no optimizations)
            from app.agents.visual_refinement import visual_refinement_agent
            
            refined_slides = await visual_refinement_agent.refine_presentation(
                slides=slides,
                industry=industry,
                design_spec=design_spec,
                execution_id=ctx.execution_id,
            )
            
            logger.info(
                "visual_refinement_output",
                execution_id=ctx.execution_id,
                refined_slide_count=len(refined_slides),
                icons_refined=sum(1 for s in refined_slides if s.get("content", {}).get("icon_name")),
                highlights_refined=sum(1 for s in refined_slides if s.get("content", {}).get("highlight_text")),
                notes_refined=sum(1 for s in refined_slides if s.get("content", {}).get("speaker_notes"))
            )
        
        # Update context with refined slides
        ctx.validated_slides["slides"] = refined_slides

    async def _run_quality_scoring(self, ctx: PipelineContext) -> None:
        slides_data = ctx.validated_slides or {}
        slides = slides_data.get("slides", [])
        
        logger.info(
            "quality_scoring_input",
            execution_id=ctx.execution_id,
            slide_count=len(slides),
            retry_count=ctx.feedback_loop_count
        )

        result = self._quality_scoring.score_presentation(
            presentation_id=ctx.presentation_id,
            slides=slides,
            execution_id=ctx.execution_id,
            retry_count=ctx.feedback_loop_count,
        )
        ctx.quality_result = result.to_dict()
        
        logger.info(
            "quality_scoring_output",
            execution_id=ctx.execution_id,
            composite_score=result.composite_score,
            content_depth=result.content_depth,
            visual_appeal=result.visual_appeal,
            structure_coherence=result.structure_coherence,
            data_accuracy=result.data_accuracy,
            clarity=result.clarity,
            requires_feedback_loop=result.requires_feedback_loop,
            recommendations_count=len(result.recommendations)
        )

        # Persist quality score to DB
        async with async_session_maker() as db:
            db.add(
                QualityScore(
                    presentation_id=ctx.presentation_id,
                    execution_id=ctx.execution_id,
                    content_depth=result.content_depth,
                    visual_appeal=result.visual_appeal,
                    structure_coherence=result.structure_coherence,
                    data_accuracy=result.data_accuracy,
                    clarity=result.clarity,
                    composite_score=result.composite_score,
                    recommendations=result.recommendations,
                )
            )
            await db.commit()

        # Feedback loop: if score < 8 and retries remain, re-run from LLM
        if result.requires_feedback_loop and ctx.feedback_loop_count < 2:
            logger.info(
                "feedback_loop_triggered",
                score=result.composite_score,
                retry=ctx.feedback_loop_count + 1,
            )
            ctx.feedback_loop_count += 1
            # Remove LLM, Validation, QualityScoring from completed so they re-run
            for agent in [AgentName.LLM_PROVIDER, AgentName.VALIDATION, AgentName.QUALITY_SCORING]:
                if agent in ctx.completed_agents:
                    ctx.completed_agents.remove(agent)
                    logger.info(
                        "feedback_loop_agent_removed",
                        agent=agent.value,
                        retry=ctx.feedback_loop_count
                    )

    async def _run_visual_qa(self, ctx: PipelineContext) -> None:
        """
        Run Visual QA Agent to inspect rendered slides for visual defects
        and apply automatic fixes (trim titles, reduce bullets, change layout).

        Routes to /preview-code when generation_mode is studio or craft,
        and to /preview-artisan when generation_mode is artisan (Req 9.1).
        """
        from app.agents.visual_qa import visual_qa_agent

        slides_data = ctx.validated_slides or {}
        detected = ctx.detected_context or {}
        theme = detected.get("theme", "ocean-depths")
        design_spec = ctx.design_spec

        # For artisan mode, the validated data contains artisan_code, not slides
        if ctx.generation_mode == GenerationMode.ARTISAN:
            slides = []  # Visual QA will use artisan_code via the agent
        else:
            slides = slides_data.get("slides", [])

        logger.info(
            "visual_qa_input",
            execution_id=ctx.execution_id,
            slide_count=len(slides),
            theme=theme,
            has_design_spec=bool(design_spec),
            generation_mode=ctx.generation_mode.value if ctx.generation_mode else None,
        )

        result = await visual_qa_agent.run(
            slides=slides,
            presentation_id=ctx.presentation_id,
            execution_id=ctx.execution_id,
            design_spec=design_spec,
            theme=theme,
            generation_mode=ctx.generation_mode,
            artisan_code=slides_data.get("artisan_code") if ctx.generation_mode == GenerationMode.ARTISAN else None,
        )

        # Store result in pipeline context
        ctx.visual_qa_result = result.to_dict()

        # Update validated_slides with any fixes applied by the QA agent
        if ctx.generation_mode != GenerationMode.ARTISAN:
            ctx.validated_slides["slides"] = slides

        logger.info(
            "visual_qa_output",
            execution_id=ctx.execution_id,
            approved=result.approved,
            iterations=result.iterations_run,
            total_found=result.total_issues_found,
            fixed=result.issues_fixed,
            remaining=result.remaining_issues,
            elapsed_ms=round(result.elapsed_ms, 1),
        )

    # ------------------------------------------------------------------
    # State persistence helpers
    # ------------------------------------------------------------------

    async def _persist_agent_output(
        self,
        db: AsyncSession,
        agent_name: AgentName,
        ctx: PipelineContext,
    ) -> None:
        """Write the agent's output slice to agent_states."""
        output_map: Dict[AgentName, Optional[Dict[str, Any]]] = {
            AgentName.INDUSTRY_CLASSIFIER: ctx.detected_context,
            AgentName.DESIGN: ctx.design_spec,
            AgentName.STORYBOARDING: ctx.presentation_plan,
            AgentName.RESEARCH: ctx.research_findings,
            AgentName.DATA_ENRICHMENT: ctx.enriched_data,
            AgentName.PROMPT_ENGINEERING: ctx.optimized_prompt,
            AgentName.LLM_PROVIDER: ctx.raw_llm_output,
            AgentName.VALIDATION: ctx.validated_slides,
            AgentName.QUALITY_SCORING: ctx.quality_result,
            AgentName.VISUAL_QA: ctx.visual_qa_result,
        }
        state = output_map.get(agent_name) or {}
        await state_layer.persist_agent_state(db, ctx.execution_id, agent_name, state)

    async def _persist_partial_result(self, ctx: PipelineContext) -> None:
        """Store best available result when pipeline fails mid-way (14.7)."""
        best_slides = (
            ctx.validated_slides
            or ctx.raw_llm_output
            or {}
        )
        async with async_session_maker() as db:
            stmt = (
                update(Presentation)
                .where(Presentation.presentation_id == ctx.presentation_id)
                .values(
                    slides=best_slides.get("slides"),
                    total_slides=best_slides.get("total_slides"),
                    status=PresentationStatus.failed,
                    quality_score=(ctx.quality_result or {}).get("composite_score"),
                )
            )
            await db.execute(stmt)
            await state_layer.update_execution_status(
                db,
                ctx.execution_id,
                ctx.failed_agent or AgentName.QUALITY_SCORING,
                status="failed",
                error_message=ctx.error_message,
            )
            await db.commit()
        logger.info(
            "partial_result_persisted",
            presentation_id=ctx.presentation_id,
            completed_agents=[a.value for a in ctx.completed_agents],
        )

    async def _finalize(self, ctx: PipelineContext) -> None:
        """Update presentation and execution rows on pipeline completion."""
        all_done = set(ctx.completed_agents) == set(PIPELINE_SEQUENCE)
        status = PresentationStatus.completed if all_done else PresentationStatus.failed
        exec_status = "completed" if all_done else "failed"

        slides_data = ctx.validated_slides or ctx.raw_llm_output or {}
        detected = ctx.detected_context or {}

        # Resolve template_id — may have been set by _run_storyboarding (29.3)
        resolved_template_id = detected.get("resolved_template_id")

        # For artisan mode, slides_data is {"artisan_code": "..."} rather than
        # {"slides": [...]}. Store the whole dict so the export worker can
        # route to /build-artisan with the artisan_code payload.
        if ctx.generation_mode == GenerationMode.ARTISAN:
            slides_value = slides_data  # store entire dict including artisan_code
            total_slides_value = None
        else:
            slides_value = slides_data.get("slides")
            total_slides_value = slides_data.get("total_slides") or len(slides_data.get("slides") or [])

        async with async_session_maker() as db:
            update_values: dict = dict(
                slides=slides_value,
                total_slides=total_slides_value,
                status=status,
                quality_score=(ctx.quality_result or {}).get("composite_score"),
                detected_industry=detected.get("industry"),
                detection_confidence=detected.get("confidence"),
                detected_sub_sector=detected.get("sub_sector"),
                inferred_audience=detected.get("target_audience"),
                selected_theme=detected.get("theme"),
                compliance_context=detected.get("compliance_context"),
                design_spec=ctx.design_spec,
            )
            if resolved_template_id:
                import uuid as _uuid
                try:
                    update_values["selected_template_id"] = _uuid.UUID(resolved_template_id)
                except ValueError:
                    pass

            stmt = (
                update(Presentation)
                .where(Presentation.presentation_id == ctx.presentation_id)
                .values(**update_values)
            )
            await db.execute(stmt)

            # 29.5 — Increment template usage_count on successful completion
            if all_done and resolved_template_id:
                try:
                    from app.services.template_service import increment_template_usage
                    import uuid as _uuid2
                    await increment_template_usage(db, _uuid2.UUID(resolved_template_id))
                except Exception as exc:
                    logger.warning("template_usage_increment_failed", error=str(exc))

            exec_stmt = (
                update(PipelineExecution)
                .where(PipelineExecution.id == ctx.execution_id)
                .values(
                    status=exec_status,
                    completed_at=datetime.now(timezone.utc),
                    error_message=ctx.error_message,
                )
            )
            await db.execute(exec_stmt)
            await db.commit()

        logger.info(
            "pipeline_finalized",
            presentation_id=ctx.presentation_id,
            status=exec_status,
            completed_agents=[a.value for a in ctx.completed_agents],
        )

        # Populate final Slide_JSON cache on successful completion (21.1)
        if all_done and slides_data:
            try:
                from app.services.presentation_cache import presentation_cache, compute_provider_config_hash
                from app.agents.prompt_engineering import PromptEngineeringAgent

                _industry = detected.get("industry", "general")
                _theme = detected.get("theme", "ocean-depths")
                _provider = self._provider_factory.primary_provider.value if self._agents_loaded else "claude"
                _phash = compute_provider_config_hash(_provider)
                _pv = PromptEngineeringAgent.PROMPT_VERSION

                await presentation_cache.set_slide_json(
                    ctx.topic, _industry, _theme, _phash, _pv, slides_data
                )
            except Exception as exc:
                logger.warning("slide_json_cache_store_failed", error=str(exc))

        # Publish terminal streaming event (16.2)
        try:
            from app.services.streaming import streaming_service
            quality_score = (ctx.quality_result or {}).get("composite_score")
            if all_done:
                await streaming_service.publish_complete(
                    ctx.presentation_id, ctx.execution_id, quality_score
                )
            else:
                await streaming_service.publish_error(
                    ctx.presentation_id,
                    ctx.execution_id,
                    ctx.error_message or "Pipeline failed",
                    ctx.failed_agent.value if ctx.failed_agent else None,
                )
        except Exception:
            pass  # streaming failures must never break finalization

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_or_create_execution(
        self, db: AsyncSession, presentation_id: str
    ) -> str:
        """Return existing execution_id or create a new PipelineExecution row."""
        stmt = (
            select(PipelineExecution)
            .where(PipelineExecution.presentation_id == presentation_id)
            .order_by(PipelineExecution.started_at.desc())
        )
        result = await db.execute(stmt)
        existing = result.scalars().first()
        if existing and existing.status in ("queued", "processing"):
            return str(existing.id)

        execution = PipelineExecution(
            presentation_id=presentation_id,
            status="processing",
            started_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        await db.flush()
        return str(execution.id)

    # ------------------------------------------------------------------
    # State cleanup (14.8)
    # ------------------------------------------------------------------

    async def cleanup_expired_states(self) -> int:
        """
        Remove agent_states older than 7 days while preserving audit_logs.
        Intended to be called from a periodic background task.
        """
        async with async_session_maker() as db:
            deleted = await state_layer.cleanup_expired_states(db)
            await db.commit()
        return deleted

    # ------------------------------------------------------------------
    # Checkpoint recovery (14.4) — public helper
    # ------------------------------------------------------------------

    async def resume(self, presentation_id: str, topic: str) -> PipelineContext:
        """Resume a pipeline from its last checkpoint."""
        return await self.run(
            presentation_id=presentation_id,
            topic=topic,
            resume_from_checkpoint=True,
        )


# Global orchestrator instance
pipeline_orchestrator = PipelineOrchestrator()
