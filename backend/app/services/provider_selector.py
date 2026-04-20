"""
Provider Selection Service

This module implements intelligent provider selection based on cost,
quality, and health metrics.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import ProviderConfig, ProviderType
from app.services.provider_health import health_monitor
from app.services.cost_tracker import CostCalculator


logger = structlog.get_logger(__name__)


@dataclass
class ProviderScore:
    """Score for a provider based on multiple factors"""
    provider_type: ProviderType
    health_score: float  # 0-1, based on success rate
    cost_score: float  # 0-1, lower cost = higher score
    quality_score: float  # 0-1, historical quality performance
    composite_score: float  # Weighted combination
    cost_per_1k_tokens: float
    is_available: bool


class ProviderSelector:
    """
    Intelligent provider selection based on cost, quality, and health.
    
    Implements:
    - Cost-based selection when multiple providers meet quality threshold
    - Health-aware provider ranking
    - Quality-cost tradeoff optimization
    - Provider efficiency tracking
    
    References: Requirement 11.3, Design: Cost Control Design
    """
    
    # Scoring weights
    HEALTH_WEIGHT = 0.4
    COST_WEIGHT = 0.4
    QUALITY_WEIGHT = 0.2
    
    # Quality threshold for cost-based selection
    MIN_QUALITY_THRESHOLD = 8.0
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cost_calculator = CostCalculator()
    
    async def get_available_providers(self) -> List[ProviderConfig]:
        """Get all active provider configurations"""
        result = await self.db.execute(
            select(ProviderConfig).where(
                ProviderConfig.is_active == True
            ).order_by(
                ProviderConfig.priority.asc()
            )
        )
        return list(result.scalars().all())
    
    def calculate_health_score(self, provider_type: ProviderType) -> float:
        """
        Calculate health score for a provider (0-1).
        
        Based on success rate and circuit breaker status.
        """
        metrics = health_monitor.metrics.get(provider_type)
        if not metrics:
            return 0.5  # Neutral score for unknown providers
        
        # Circuit open = very low score
        if metrics.circuit_open:
            return 0.1
        
        # Use success rate as primary health indicator
        return metrics.success_rate
    
    def calculate_cost_score(
        self,
        provider_type: ProviderType,
        cost_per_1k_tokens: float,
    ) -> float:
        """
        Calculate cost score for a provider (0-1).
        
        Lower cost = higher score.
        Normalized against all provider costs.
        """
        # Get default costs for normalization
        default_costs = self.cost_calculator.DEFAULT_COSTS
        
        # Calculate average cost across providers
        all_costs = []
        for ptype, pricing in default_costs.items():
            avg_cost = (pricing["prompt"] + pricing["completion"]) / 2
            all_costs.append(avg_cost)
        
        if not all_costs:
            return 0.5
        
        max_cost = max(all_costs)
        min_cost = min(all_costs)
        
        # Normalize: lower cost = higher score
        if max_cost == min_cost:
            return 0.5
        
        # Use configured cost or default
        if cost_per_1k_tokens > 0:
            provider_cost = cost_per_1k_tokens
        else:
            pricing = default_costs.get(provider_type, {"prompt": 0, "completion": 0})
            provider_cost = (pricing["prompt"] + pricing["completion"]) / 2
        
        # Invert: lower cost = higher score
        normalized = 1.0 - ((provider_cost - min_cost) / (max_cost - min_cost))
        return max(0.0, min(1.0, normalized))
    
    def calculate_quality_score(
        self,
        provider_type: ProviderType,
    ) -> float:
        """
        Calculate quality score for a provider (0-1).
        
        Based on historical quality performance.
        Currently returns neutral score - can be enhanced with historical data.
        """
        # TODO: Implement historical quality tracking
        # For now, return provider-specific defaults based on known capabilities
        quality_defaults = {
            ProviderType.claude: 0.9,  # Claude known for high quality
            ProviderType.openai: 0.85,  # GPT-4o also high quality
            ProviderType.groq: 0.75,  # Fast but slightly lower quality
            ProviderType.local: 0.6,  # Local models vary
        }
        return quality_defaults.get(provider_type, 0.7)
    
    async def score_provider(
        self,
        provider_config: ProviderConfig,
    ) -> ProviderScore:
        """
        Calculate composite score for a provider.
        
        Args:
            provider_config: Provider configuration
        
        Returns:
            ProviderScore with all metrics
        """
        provider_type = provider_config.provider_type
        
        # Calculate individual scores
        health_score = self.calculate_health_score(provider_type)
        cost_score = self.calculate_cost_score(
            provider_type,
            provider_config.cost_per_1k_tokens,
        )
        quality_score = self.calculate_quality_score(provider_type)
        
        # Calculate composite score
        composite_score = (
            self.HEALTH_WEIGHT * health_score +
            self.COST_WEIGHT * cost_score +
            self.QUALITY_WEIGHT * quality_score
        )
        
        # Check availability
        is_available = health_score > 0.2 and not health_monitor.metrics.get(provider_type, None) or not health_monitor.metrics[provider_type].circuit_open
        
        return ProviderScore(
            provider_type=provider_type,
            health_score=health_score,
            cost_score=cost_score,
            quality_score=quality_score,
            composite_score=composite_score,
            cost_per_1k_tokens=provider_config.cost_per_1k_tokens,
            is_available=is_available,
        )
    
    async def select_best_provider(
        self,
        quality_threshold: Optional[float] = None,
        prefer_cost_optimization: bool = False,
    ) -> Optional[ProviderType]:
        """
        Select the best provider based on current conditions.
        
        Args:
            quality_threshold: Minimum quality score required (0-10 scale)
            prefer_cost_optimization: If True, prioritize cost over other factors
        
        Returns:
            Selected provider type, or None if no suitable provider found
        """
        # Get all available providers
        providers = await self.get_available_providers()
        if not providers:
            logger.error("no_providers_configured")
            return None
        
        # Score all providers
        scored_providers: List[ProviderScore] = []
        for provider in providers:
            score = await self.score_provider(provider)
            if score.is_available:
                scored_providers.append(score)
        
        if not scored_providers:
            logger.error("no_available_providers")
            return None
        
        # Filter by quality threshold if specified
        if quality_threshold is not None:
            # Convert 0-10 scale to 0-1 scale
            min_quality = quality_threshold / 10.0
            scored_providers = [
                p for p in scored_providers
                if p.quality_score >= min_quality
            ]
        
        if not scored_providers:
            logger.warning(
                "no_providers_meet_quality_threshold",
                threshold=quality_threshold,
            )
            return None
        
        # Select based on preference
        if prefer_cost_optimization:
            # Sort by cost score (higher = cheaper)
            scored_providers.sort(key=lambda p: p.cost_score, reverse=True)
            selected = scored_providers[0]
            
            logger.info(
                "provider_selected_cost_optimized",
                provider=selected.provider_type.value,
                cost_score=selected.cost_score,
                health_score=selected.health_score,
                quality_score=selected.quality_score,
            )
        else:
            # Sort by composite score
            scored_providers.sort(key=lambda p: p.composite_score, reverse=True)
            selected = scored_providers[0]
            
            logger.info(
                "provider_selected_balanced",
                provider=selected.provider_type.value,
                composite_score=selected.composite_score,
                health_score=selected.health_score,
                cost_score=selected.cost_score,
                quality_score=selected.quality_score,
            )
        
        return selected.provider_type
    
    async def select_cost_optimal_provider(
        self,
        min_quality_threshold: float = MIN_QUALITY_THRESHOLD,
    ) -> Optional[ProviderType]:
        """
        Select the most cost-effective provider that meets quality threshold.
        
        This is the primary method for cost-based provider selection.
        
        Args:
            min_quality_threshold: Minimum quality score (0-10 scale)
        
        Returns:
            Most cost-effective provider, or None if none meet threshold
        """
        return await self.select_best_provider(
            quality_threshold=min_quality_threshold,
            prefer_cost_optimization=True,
        )
    
    async def get_provider_rankings(self) -> List[Dict[str, Any]]:
        """
        Get ranked list of all providers with scores.
        
        Useful for debugging and monitoring.
        
        Returns:
            List of provider rankings with detailed scores
        """
        providers = await self.get_available_providers()
        
        rankings = []
        for provider in providers:
            score = await self.score_provider(provider)
            rankings.append({
                "provider": score.provider_type.value,
                "composite_score": score.composite_score,
                "health_score": score.health_score,
                "cost_score": score.cost_score,
                "quality_score": score.quality_score,
                "cost_per_1k_tokens": score.cost_per_1k_tokens,
                "is_available": score.is_available,
            })
        
        # Sort by composite score
        rankings.sort(key=lambda x: x["composite_score"], reverse=True)
        
        return rankings
    
    async def compare_providers(
        self,
        provider_a: ProviderType,
        provider_b: ProviderType,
    ) -> Dict[str, Any]:
        """
        Compare two providers across all metrics.
        
        Args:
            provider_a: First provider to compare
            provider_b: Second provider to compare
        
        Returns:
            Comparison results
        """
        # Get configs
        result_a = await self.db.execute(
            select(ProviderConfig).where(
                ProviderConfig.provider_type == provider_a,
                ProviderConfig.is_active == True,
            )
        )
        config_a = result_a.scalar_one_or_none()
        
        result_b = await self.db.execute(
            select(ProviderConfig).where(
                ProviderConfig.provider_type == provider_b,
                ProviderConfig.is_active == True,
            )
        )
        config_b = result_b.scalar_one_or_none()
        
        if not config_a or not config_b:
            return {"error": "One or both providers not found"}
        
        # Score both
        score_a = await self.score_provider(config_a)
        score_b = await self.score_provider(config_b)
        
        # Determine winner for each category
        return {
            "provider_a": provider_a.value,
            "provider_b": provider_b.value,
            "health": {
                "a": score_a.health_score,
                "b": score_b.health_score,
                "winner": provider_a.value if score_a.health_score > score_b.health_score else provider_b.value,
            },
            "cost": {
                "a": score_a.cost_score,
                "b": score_b.cost_score,
                "winner": provider_a.value if score_a.cost_score > score_b.cost_score else provider_b.value,
            },
            "quality": {
                "a": score_a.quality_score,
                "b": score_b.quality_score,
                "winner": provider_a.value if score_a.quality_score > score_b.quality_score else provider_b.value,
            },
            "composite": {
                "a": score_a.composite_score,
                "b": score_b.composite_score,
                "winner": provider_a.value if score_a.composite_score > score_b.composite_score else provider_b.value,
            },
        }
