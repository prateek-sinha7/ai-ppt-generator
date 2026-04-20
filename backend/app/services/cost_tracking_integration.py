"""
Cost Tracking Integration Example

This module demonstrates how to integrate cost tracking into the LLM provider service.
"""

import uuid
from typing import Optional, Any
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cost_tracker import CostTracker
from app.services.cost_controller import CostController, CostLimits
from app.services.provider_selector import ProviderSelector
from app.services.cost_alerts import CostAlertService
from app.services.llm_provider import provider_factory, ProviderType
from app.db.models import PipelineExecution, Presentation


logger = structlog.get_logger(__name__)


class CostAwareLLMService:
    """
    LLM service with integrated cost tracking and control.
    
    This service wraps the provider factory with cost tracking,
    enforcement, and alerting capabilities.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        cost_limits: Optional[CostLimits] = None,
    ):
        self.db = db
        self.cost_tracker = CostTracker(db)
        self.cost_controller = CostController(db, cost_limits)
        self.provider_selector = ProviderSelector(db)
        self.alert_service = CostAlertService(db)
    
    async def call_llm_with_cost_tracking(
        self,
        execution_id: uuid.UUID,
        provider_type: ProviderType,
        prompt: str,
        quality_scores: Optional[list[float]] = None,
        **kwargs,
    ) -> tuple[Any, bool]:
        """
        Call LLM with full cost tracking and enforcement.
        
        Args:
            execution_id: Pipeline execution ID
            provider_type: Provider to use
            prompt: Prompt to send
            quality_scores: Previous quality scores for feedback loop
            **kwargs: Additional arguments for LLM call
        
        Returns:
            Tuple of (response, should_continue)
            should_continue indicates if more calls are allowed
        """
        # Check if call is allowed
        can_proceed, reason = await self.cost_controller.check_and_enforce_limits(
            execution_id=execution_id,
            quality_scores=quality_scores,
        )
        
        if not can_proceed:
            logger.warning(
                "llm_call_blocked",
                execution_id=str(execution_id),
                reason=reason,
            )
            return None, False
        
        # Get LLM client
        client = provider_factory.get_client(
            execution_id=str(execution_id),
            preferred_provider=provider_type,
        )
        
        # Make LLM call
        try:
            response = await client.ainvoke(prompt, **kwargs)
            
            # Record usage and cost
            await self.cost_tracker.record_usage(
                execution_id=execution_id,
                provider_type=provider_type,
                response=response,
            )
            
            # Check if we should continue
            state = await self.cost_controller.get_execution_state(
                execution_id=execution_id,
                quality_scores=quality_scores,
            )
            
            can_continue, _ = self.cost_controller.should_allow_llm_call(state)
            
            logger.info(
                "llm_call_completed_with_cost_tracking",
                execution_id=str(execution_id),
                provider=provider_type.value,
                total_cost=state.total_cost_usd,
                call_count=state.llm_call_count,
                can_continue=can_continue,
            )
            
            return response, can_continue
            
        except Exception as e:
            logger.error(
                "llm_call_failed",
                execution_id=str(execution_id),
                provider=provider_type.value,
                error=str(e),
            )
            raise
    
    async def select_cost_optimal_provider(
        self,
        min_quality_threshold: float = 8.0,
    ) -> Optional[ProviderType]:
        """
        Select the most cost-effective provider that meets quality threshold.
        
        Args:
            min_quality_threshold: Minimum quality score (0-10)
        
        Returns:
            Selected provider type
        """
        return await self.provider_selector.select_cost_optimal_provider(
            min_quality_threshold=min_quality_threshold,
        )
    
    async def check_and_alert_tenant_costs(
        self,
        tenant_id: uuid.UUID,
        threshold: float,
    ) -> tuple[bool, float]:
        """
        Check tenant costs and send alerts if needed.
        
        Args:
            tenant_id: Tenant ID
            threshold: Daily cost threshold
        
        Returns:
            Tuple of (can_proceed, daily_cost)
        """
        # Get daily cost
        daily_cost = await self.cost_tracker.get_tenant_daily_cost(tenant_id)
        
        # Calculate percentage
        percent_used = (daily_cost / threshold * 100) if threshold > 0 else 0
        
        # Send alert if threshold reached
        if percent_used >= 80.0:
            await self.alert_service.send_threshold_alert(
                tenant_id=tenant_id,
                daily_cost=daily_cost,
                threshold=threshold,
                percent_used=percent_used,
            )
        
        # Check if can proceed
        can_proceed = daily_cost < threshold
        
        return can_proceed, daily_cost
    
    async def get_execution_cost_summary(
        self,
        execution_id: uuid.UUID,
    ) -> dict:
        """
        Get comprehensive cost summary for an execution.
        
        Args:
            execution_id: Pipeline execution ID
        
        Returns:
            Dict with cost metrics
        """
        return await self.cost_controller.get_cost_summary(execution_id)


# Example usage in pipeline
async def example_pipeline_with_cost_tracking(
    db: AsyncSession,
    presentation_id: uuid.UUID,
    execution_id: uuid.UUID,
    tenant_id: uuid.UUID,
):
    """
    Example of how to integrate cost tracking into the pipeline.
    """
    # Initialize cost-aware service
    cost_service = CostAwareLLMService(db)
    
    # Check tenant limits before starting
    can_proceed, daily_cost = await cost_service.check_and_alert_tenant_costs(
        tenant_id=tenant_id,
        threshold=10.0,  # $10 daily limit
    )
    
    if not can_proceed:
        logger.error(
            "tenant_daily_limit_exceeded",
            tenant_id=str(tenant_id),
            daily_cost=daily_cost,
        )
        return None
    
    # Select cost-optimal provider
    provider = await cost_service.select_cost_optimal_provider(
        min_quality_threshold=8.0,
    )
    
    if not provider:
        logger.error("no_suitable_provider_found")
        return None
    
    logger.info(
        "selected_provider",
        provider=provider.value,
        tenant_id=str(tenant_id),
    )
    
    # Quality feedback loop with cost control
    quality_scores = []
    max_iterations = 3
    
    for iteration in range(max_iterations):
        # Make LLM call with cost tracking
        response, can_continue = await cost_service.call_llm_with_cost_tracking(
            execution_id=execution_id,
            provider_type=provider,
            prompt="Generate presentation...",
            quality_scores=quality_scores,
        )
        
        if response is None:
            logger.warning(
                "llm_call_blocked_by_cost_control",
                iteration=iteration,
            )
            break
        
        # Evaluate quality (mock)
        quality_score = 8.5  # Would come from Quality_Scoring_Agent
        quality_scores.append(quality_score)
        
        logger.info(
            "iteration_completed",
            iteration=iteration,
            quality_score=quality_score,
            can_continue=can_continue,
        )
        
        # Check if we should continue
        if not can_continue:
            logger.info(
                "stopping_due_to_cost_limits",
                iteration=iteration,
            )
            break
        
        # Check for diminishing returns
        if len(quality_scores) >= 2:
            improvement = quality_scores[-1] - quality_scores[-2]
            if improvement < 0.5:
                logger.info(
                    "stopping_due_to_diminishing_returns",
                    iteration=iteration,
                    improvement=improvement,
                )
                break
    
    # Get final cost summary
    cost_summary = await cost_service.get_execution_cost_summary(execution_id)
    
    logger.info(
        "pipeline_completed",
        execution_id=str(execution_id),
        iterations=len(quality_scores),
        final_quality=quality_scores[-1] if quality_scores else None,
        cost_summary=cost_summary,
    )
    
    return {
        "quality_scores": quality_scores,
        "cost_summary": cost_summary,
    }
