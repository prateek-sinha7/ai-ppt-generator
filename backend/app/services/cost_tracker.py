"""
Cost Tracking Service

This module implements comprehensive cost tracking for LLM provider usage,
including token counting, cost calculation, and usage recording.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from langchain_core.outputs import LLMResult

from app.db.models import ProviderUsage, ProviderConfig, PipelineExecution, ProviderType


logger = structlog.get_logger(__name__)


class TokenUsageExtractor:
    """Extract token usage from LLM responses"""
    
    @staticmethod
    def extract_from_response(response: Any) -> Dict[str, int]:
        """
        Extract token usage from LLM response.
        
        Handles different response formats from various providers.
        
        Args:
            response: LLM response object (LLMResult or similar)
        
        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens
        """
        # Default values
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        
        try:
            # LangChain LLMResult format
            if isinstance(response, LLMResult):
                if hasattr(response, "llm_output") and response.llm_output:
                    token_usage = response.llm_output.get("token_usage", {})
                    usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                    usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                    usage["total_tokens"] = token_usage.get("total_tokens", 0)
            
            # Direct token_usage dict
            elif isinstance(response, dict):
                if "token_usage" in response:
                    token_usage = response["token_usage"]
                    usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                    usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                    usage["total_tokens"] = token_usage.get("total_tokens", 0)
                elif "usage" in response:
                    # OpenAI format
                    token_usage = response["usage"]
                    usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                    usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                    usage["total_tokens"] = token_usage.get("total_tokens", 0)
            
            # Fallback: calculate total if not provided
            if usage["total_tokens"] == 0 and (usage["prompt_tokens"] > 0 or usage["completion_tokens"] > 0):
                usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
            
        except Exception as e:
            logger.warning(
                "token_extraction_failed",
                error=str(e),
                response_type=type(response).__name__,
            )
        
        return usage


class CostCalculator:
    """Calculate costs based on token usage and provider pricing"""
    
    # Default cost per 1K tokens (USD) - can be overridden by provider_configs table
    DEFAULT_COSTS = {
        ProviderType.claude: {
            "prompt": 0.003,  # $3 per 1M input tokens
            "completion": 0.015,  # $15 per 1M output tokens
        },
        ProviderType.openai: {
            "prompt": 0.0025,  # $2.50 per 1M input tokens (GPT-4o)
            "completion": 0.010,  # $10 per 1M output tokens
        },
        ProviderType.groq: {
            "prompt": 0.0001,  # $0.10 per 1M tokens (very cheap)
            "completion": 0.0001,
        },
        ProviderType.local: {
            "prompt": 0.0,  # Free for local models
            "completion": 0.0,
        },
    }
    
    @classmethod
    def calculate_cost(
        cls,
        provider_type: ProviderType,
        prompt_tokens: int,
        completion_tokens: int,
        cost_per_1k_tokens: Optional[float] = None,
    ) -> float:
        """
        Calculate cost in USD for token usage.
        
        Args:
            provider_type: Type of LLM provider
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            cost_per_1k_tokens: Override cost (if None, uses default pricing)
        
        Returns:
            Cost in USD
        """
        if cost_per_1k_tokens is not None:
            # Simple pricing model: same cost for input and output
            total_tokens = prompt_tokens + completion_tokens
            return (total_tokens / 1000.0) * cost_per_1k_tokens
        
        # Use provider-specific pricing
        pricing = cls.DEFAULT_COSTS.get(provider_type, {"prompt": 0.0, "completion": 0.0})
        
        prompt_cost = (prompt_tokens / 1000.0) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000.0) * pricing["completion"]
        
        return prompt_cost + completion_cost


class CostTracker:
    """
    Track and record LLM provider costs.
    
    Implements:
    - Token usage extraction from LLM responses
    - Cost calculation based on provider pricing
    - Usage recording in provider_usage table
    - Execution-level cost accumulation
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_extractor = TokenUsageExtractor()
        self.cost_calculator = CostCalculator()
    
    async def get_provider_config(
        self,
        provider_type: ProviderType,
    ) -> Optional[ProviderConfig]:
        """Get provider configuration from database"""
        try:
            result = await self.db.execute(
                select(ProviderConfig).where(
                    ProviderConfig.provider_type == provider_type,
                    ProviderConfig.is_active == True,
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                "provider_config_fetch_failed",
                provider_type=provider_type.value,
                error=str(e),
            )
            return None
    
    async def record_usage(
        self,
        execution_id: uuid.UUID,
        provider_type: ProviderType,
        response: Any,
        provider_config_id: Optional[uuid.UUID] = None,
    ) -> ProviderUsage:
        """
        Record token usage and cost for an LLM call.
        
        Args:
            execution_id: Pipeline execution ID
            provider_type: Type of LLM provider used
            response: LLM response object
            provider_config_id: Optional provider config ID (fetched if not provided)
        
        Returns:
            Created ProviderUsage record
        """
        # Extract token usage
        usage = self.token_extractor.extract_from_response(response)
        
        # Get provider config for pricing
        if not provider_config_id:
            provider_config = await self.get_provider_config(provider_type)
            provider_config_id = provider_config.id if provider_config else None
            cost_per_1k = provider_config.cost_per_1k_tokens if provider_config else None
        else:
            cost_per_1k = None
        
        # Calculate cost
        cost_usd = self.cost_calculator.calculate_cost(
            provider_type=provider_type,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            cost_per_1k_tokens=cost_per_1k,
        )
        
        # Create usage record
        usage_record = ProviderUsage(
            execution_id=execution_id,
            provider_id=provider_config_id,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=cost_usd,
        )
        
        self.db.add(usage_record)
        await self.db.commit()
        await self.db.refresh(usage_record)
        
        logger.info(
            "usage_recorded",
            execution_id=str(execution_id),
            provider=provider_type.value,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=cost_usd,
        )
        
        return usage_record
    
    async def get_execution_cost(
        self,
        execution_id: uuid.UUID,
    ) -> float:
        """
        Get total cost for a pipeline execution.
        
        Args:
            execution_id: Pipeline execution ID
        
        Returns:
            Total cost in USD
        """
        result = await self.db.execute(
            select(func.sum(ProviderUsage.cost_usd)).where(
                ProviderUsage.execution_id == execution_id
            )
        )
        total_cost = result.scalar_one_or_none()
        return total_cost or 0.0
    
    async def get_execution_call_count(
        self,
        execution_id: uuid.UUID,
    ) -> int:
        """
        Get number of LLM calls for a pipeline execution.
        
        Args:
            execution_id: Pipeline execution ID
        
        Returns:
            Number of LLM calls
        """
        result = await self.db.execute(
            select(func.count(ProviderUsage.id)).where(
                ProviderUsage.execution_id == execution_id
            )
        )
        return result.scalar_one_or_none() or 0
    
    async def get_tenant_daily_cost(
        self,
        tenant_id: uuid.UUID,
        date: Optional[datetime] = None,
    ) -> float:
        """
        Get total cost for a tenant on a specific date.
        
        Args:
            tenant_id: Tenant ID
            date: Date to check (defaults to today)
        
        Returns:
            Total cost in USD
        """
        if date is None:
            date = datetime.utcnow()
        
        # Get start and end of day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Query usage through pipeline executions and presentations
        from app.db.models import Presentation
        
        result = await self.db.execute(
            select(func.sum(ProviderUsage.cost_usd))
            .join(PipelineExecution, ProviderUsage.execution_id == PipelineExecution.id)
            .join(Presentation, PipelineExecution.presentation_id == Presentation.presentation_id)
            .where(
                Presentation.tenant_id == tenant_id,
                ProviderUsage.created_at >= start_of_day,
                ProviderUsage.created_at <= end_of_day,
            )
        )
        
        total_cost = result.scalar_one_or_none()
        return total_cost or 0.0
    
    async def get_provider_usage_stats(
        self,
        provider_type: ProviderType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a provider.
        
        Args:
            provider_type: Type of LLM provider
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
        
        Returns:
            Dict with usage statistics
        """
        # Build query
        query = select(
            func.count(ProviderUsage.id).label("call_count"),
            func.sum(ProviderUsage.prompt_tokens).label("total_prompt_tokens"),
            func.sum(ProviderUsage.completion_tokens).label("total_completion_tokens"),
            func.sum(ProviderUsage.total_tokens).label("total_tokens"),
            func.sum(ProviderUsage.cost_usd).label("total_cost"),
            func.avg(ProviderUsage.cost_usd).label("avg_cost_per_call"),
        ).join(
            ProviderConfig, ProviderUsage.provider_id == ProviderConfig.id
        ).where(
            ProviderConfig.provider_type == provider_type
        )
        
        if start_date:
            query = query.where(ProviderUsage.created_at >= start_date)
        if end_date:
            query = query.where(ProviderUsage.created_at <= end_date)
        
        result = await self.db.execute(query)
        row = result.one_or_none()
        
        if not row:
            return {
                "call_count": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_cost_per_call": 0.0,
            }
        
        return {
            "call_count": row.call_count or 0,
            "total_prompt_tokens": row.total_prompt_tokens or 0,
            "total_completion_tokens": row.total_completion_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0.0),
            "avg_cost_per_call": float(row.avg_cost_per_call or 0.0),
        }
