"""
Cost Controller

This module implements cost control mechanisms for LLM operations,
including call limits, cost ceilings, and early stopping logic.
"""

from typing import Optional, List
from dataclasses import dataclass
import uuid
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cost_tracker import CostTracker


logger = structlog.get_logger(__name__)


@dataclass
class CostLimits:
    """Cost limit configuration"""
    max_llm_calls: int = 4
    cost_ceiling_usd: float = 0.50
    diminishing_return_delta: float = 0.5


@dataclass
class ExecutionCostState:
    """Current cost state for a pipeline execution"""
    execution_id: uuid.UUID
    llm_call_count: int
    total_cost_usd: float
    quality_scores: List[float]
    cost_ceiling_usd: float
    max_llm_calls: int


class CostController:
    """
    Enforce cost controls on LLM operations.
    
    Implements:
    - Maximum LLM calls per request (default: 4)
    - Configurable cost ceiling per execution
    - Early stopping based on diminishing returns
    - Cost-based decision making
    
    References: Requirement 47, Design: Cost Control Design
    """
    
    # Default limits
    MAX_LLM_CALLS_PER_REQUEST = 4
    DEFAULT_COST_CEILING_USD = 0.50
    DIMINISHING_RETURN_DELTA = 0.5
    
    def __init__(
        self,
        db: AsyncSession,
        cost_limits: Optional[CostLimits] = None,
    ):
        self.db = db
        self.cost_tracker = CostTracker(db)
        self.limits = cost_limits or CostLimits()
    
    async def get_execution_state(
        self,
        execution_id: uuid.UUID,
        quality_scores: Optional[List[float]] = None,
    ) -> ExecutionCostState:
        """
        Get current cost state for an execution.
        
        Args:
            execution_id: Pipeline execution ID
            quality_scores: List of quality scores from previous iterations
        
        Returns:
            ExecutionCostState with current metrics
        """
        # Get current call count and cost
        call_count = await self.cost_tracker.get_execution_call_count(execution_id)
        total_cost = await self.cost_tracker.get_execution_cost(execution_id)
        
        return ExecutionCostState(
            execution_id=execution_id,
            llm_call_count=call_count,
            total_cost_usd=total_cost,
            quality_scores=quality_scores or [],
            cost_ceiling_usd=self.limits.cost_ceiling_usd,
            max_llm_calls=self.limits.max_llm_calls,
        )
    
    def should_allow_llm_call(
        self,
        state: ExecutionCostState,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if another LLM call should be allowed.
        
        Args:
            state: Current execution cost state
        
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
            If not allowed, reason explains why
        """
        # Check call count limit
        if state.llm_call_count >= state.max_llm_calls:
            reason = (
                f"Maximum LLM calls reached ({state.llm_call_count}/{state.max_llm_calls}). "
                f"Delivering best result."
            )
            logger.warning(
                "llm_call_limit_reached",
                execution_id=str(state.execution_id),
                call_count=state.llm_call_count,
                max_calls=state.max_llm_calls,
            )
            return False, reason
        
        # Check cost ceiling
        if state.total_cost_usd >= state.cost_ceiling_usd:
            reason = (
                f"Cost ceiling reached (${state.total_cost_usd:.4f}/${state.cost_ceiling_usd:.2f}). "
                f"Delivering best result."
            )
            logger.warning(
                "cost_ceiling_reached",
                execution_id=str(state.execution_id),
                total_cost=state.total_cost_usd,
                ceiling=state.cost_ceiling_usd,
            )
            return False, reason
        
        # All checks passed
        return True, None
    
    def should_continue_feedback_loop(
        self,
        state: ExecutionCostState,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if feedback loop should continue based on quality improvement.
        
        Implements early stopping when quality improvements show diminishing returns.
        
        Args:
            state: Current execution cost state
        
        Returns:
            Tuple of (should_continue: bool, reason: Optional[str])
        """
        # Need at least 2 scores to compare
        if len(state.quality_scores) < 2:
            return True, None
        
        # Calculate improvement from last iteration
        improvement = state.quality_scores[-1] - state.quality_scores[-2]
        
        # Check if improvement is below threshold
        if improvement < self.limits.diminishing_return_delta:
            reason = (
                f"Diminishing returns detected (improvement: {improvement:.2f} < "
                f"threshold: {self.limits.diminishing_return_delta}). Stopping feedback loop."
            )
            logger.info(
                "early_stopping_triggered",
                execution_id=str(state.execution_id),
                improvement=improvement,
                threshold=self.limits.diminishing_return_delta,
                scores=state.quality_scores,
            )
            return False, reason
        
        logger.info(
            "feedback_loop_continuing",
            execution_id=str(state.execution_id),
            improvement=improvement,
            current_score=state.quality_scores[-1],
        )
        
        return True, None
    
    def calculate_cost_per_quality_point(
        self,
        total_cost_usd: float,
        quality_score: float,
    ) -> float:
        """
        Calculate cost efficiency metric.
        
        Args:
            total_cost_usd: Total cost spent
            quality_score: Quality score achieved (1-10)
        
        Returns:
            Cost per quality point (lower is better)
        """
        if quality_score <= 0:
            return float('inf')
        
        return total_cost_usd / quality_score
    
    async def check_and_enforce_limits(
        self,
        execution_id: uuid.UUID,
        quality_scores: Optional[List[float]] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check all cost limits and return whether to proceed.
        
        Convenience method that combines all checks.
        
        Args:
            execution_id: Pipeline execution ID
            quality_scores: List of quality scores from previous iterations
        
        Returns:
            Tuple of (can_proceed: bool, reason: Optional[str])
        """
        # Get current state
        state = await self.get_execution_state(execution_id, quality_scores)
        
        # Check if LLM call is allowed
        allowed, reason = self.should_allow_llm_call(state)
        if not allowed:
            return False, reason
        
        # If we have quality scores, check feedback loop
        if quality_scores and len(quality_scores) >= 2:
            should_continue, reason = self.should_continue_feedback_loop(state)
            if not should_continue:
                return False, reason
        
        return True, None
    
    async def get_cost_summary(
        self,
        execution_id: uuid.UUID,
    ) -> dict:
        """
        Get cost summary for an execution.
        
        Args:
            execution_id: Pipeline execution ID
        
        Returns:
            Dict with cost metrics
        """
        call_count = await self.cost_tracker.get_execution_call_count(execution_id)
        total_cost = await self.cost_tracker.get_execution_cost(execution_id)
        
        return {
            "execution_id": str(execution_id),
            "llm_call_count": call_count,
            "total_cost_usd": total_cost,
            "cost_ceiling_usd": self.limits.cost_ceiling_usd,
            "max_llm_calls": self.limits.max_llm_calls,
            "remaining_calls": max(0, self.limits.max_llm_calls - call_count),
            "remaining_budget_usd": max(0.0, self.limits.cost_ceiling_usd - total_cost),
            "budget_used_percent": (total_cost / self.limits.cost_ceiling_usd * 100) if self.limits.cost_ceiling_usd > 0 else 0,
        }


class TenantCostController:
    """
    Enforce tenant-level cost controls.
    
    Implements:
    - Daily cost thresholds per tenant
    - Cost alerts at 80% threshold
    - Hard stop at 100% threshold
    """
    
    # Default tenant limits
    DEFAULT_DAILY_THRESHOLD_USD = 10.0
    ALERT_THRESHOLD_PERCENT = 80.0
    
    def __init__(
        self,
        db: AsyncSession,
        daily_threshold_usd: float = DEFAULT_DAILY_THRESHOLD_USD,
    ):
        self.db = db
        self.cost_tracker = CostTracker(db)
        self.daily_threshold_usd = daily_threshold_usd
    
    async def check_tenant_limits(
        self,
        tenant_id: uuid.UUID,
    ) -> tuple[bool, Optional[str], float]:
        """
        Check if tenant has exceeded daily cost limits.
        
        Args:
            tenant_id: Tenant ID
        
        Returns:
            Tuple of (can_proceed: bool, reason: Optional[str], current_cost: float)
        """
        # Get today's cost
        daily_cost = await self.cost_tracker.get_tenant_daily_cost(tenant_id)
        
        # Calculate percentage
        percent_used = (daily_cost / self.daily_threshold_usd * 100) if self.daily_threshold_usd > 0 else 0
        
        # Check hard limit
        if daily_cost >= self.daily_threshold_usd:
            reason = (
                f"Daily cost limit reached (${daily_cost:.2f}/${self.daily_threshold_usd:.2f}). "
                f"New requests will be queued until next billing period."
            )
            logger.warning(
                "tenant_daily_limit_reached",
                tenant_id=str(tenant_id),
                daily_cost=daily_cost,
                threshold=self.daily_threshold_usd,
            )
            return False, reason, daily_cost
        
        # Check alert threshold
        if percent_used >= self.ALERT_THRESHOLD_PERCENT:
            logger.warning(
                "tenant_approaching_daily_limit",
                tenant_id=str(tenant_id),
                daily_cost=daily_cost,
                threshold=self.daily_threshold_usd,
                percent_used=percent_used,
            )
        
        return True, None, daily_cost
    
    async def get_tenant_cost_summary(
        self,
        tenant_id: uuid.UUID,
    ) -> dict:
        """
        Get cost summary for a tenant.
        
        Args:
            tenant_id: Tenant ID
        
        Returns:
            Dict with cost metrics
        """
        daily_cost = await self.cost_tracker.get_tenant_daily_cost(tenant_id)
        percent_used = (daily_cost / self.daily_threshold_usd * 100) if self.daily_threshold_usd > 0 else 0
        
        return {
            "tenant_id": str(tenant_id),
            "daily_cost_usd": daily_cost,
            "daily_threshold_usd": self.daily_threshold_usd,
            "remaining_budget_usd": max(0.0, self.daily_threshold_usd - daily_cost),
            "budget_used_percent": percent_used,
            "alert_triggered": percent_used >= self.ALERT_THRESHOLD_PERCENT,
            "limit_reached": daily_cost >= self.daily_threshold_usd,
        }
