"""
Tests for Cost Tracking System

Tests cover:
- Token usage extraction and cost calculation
- Cost controller limits enforcement
- Provider selection based on cost
- Cost alert webhooks
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cost_tracker import (
    TokenUsageExtractor,
    CostCalculator,
    CostTracker,
)
from app.services.cost_controller import (
    CostController,
    CostLimits,
    ExecutionCostState,
    TenantCostController,
)
from app.services.provider_selector import ProviderSelector, ProviderScore
from app.services.cost_alerts import CostAlertService, AlertType, AlertLevel
from app.db.models import ProviderType, ProviderConfig, ProviderUsage


class TestTokenUsageExtractor:
    """Test token usage extraction from LLM responses"""
    
    def test_extract_from_langchain_response(self):
        """Test extraction from LangChain LLMResult format"""
        extractor = TokenUsageExtractor()
        
        # Mock LLMResult
        response = MagicMock()
        response.llm_output = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }
        
        usage = extractor.extract_from_response(response)
        
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150
    
    def test_extract_from_dict_response(self):
        """Test extraction from dict format"""
        extractor = TokenUsageExtractor()
        
        response = {
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "total_tokens": 300,
            }
        }
        
        usage = extractor.extract_from_response(response)
        
        assert usage["prompt_tokens"] == 200
        assert usage["completion_tokens"] == 100
        assert usage["total_tokens"] == 300
    
    def test_extract_calculates_total_if_missing(self):
        """Test total calculation when not provided"""
        extractor = TokenUsageExtractor()
        
        response = {
            "token_usage": {
                "prompt_tokens": 150,
                "completion_tokens": 75,
            }
        }
        
        usage = extractor.extract_from_response(response)
        
        assert usage["total_tokens"] == 225


class TestCostCalculator:
    """Test cost calculation logic"""
    
    def test_calculate_cost_claude(self):
        """Test cost calculation for Claude"""
        calculator = CostCalculator()
        
        cost = calculator.calculate_cost(
            provider_type=ProviderType.claude,
            prompt_tokens=1000,
            completion_tokens=500,
        )
        
        # Claude: $3/1M input, $15/1M output
        # (1000 * 0.003) + (500 * 0.015) = 3 + 7.5 = 10.5 cents = $0.105
        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
        assert abs(cost - expected) < 0.0001
    
    def test_calculate_cost_openai(self):
        """Test cost calculation for OpenAI"""
        calculator = CostCalculator()
        
        cost = calculator.calculate_cost(
            provider_type=ProviderType.openai,
            prompt_tokens=2000,
            completion_tokens=1000,
        )
        
        # OpenAI: $2.50/1M input, $10/1M output
        expected = (2000 / 1000 * 0.0025) + (1000 / 1000 * 0.010)
        assert abs(cost - expected) < 0.0001
    
    def test_calculate_cost_groq(self):
        """Test cost calculation for Groq (cheap)"""
        calculator = CostCalculator()
        
        cost = calculator.calculate_cost(
            provider_type=ProviderType.groq,
            prompt_tokens=5000,
            completion_tokens=2000,
        )
        
        # Groq: $0.10/1M tokens
        expected = (5000 / 1000 * 0.0001) + (2000 / 1000 * 0.0001)
        assert abs(cost - expected) < 0.0001
    
    def test_calculate_cost_local_is_free(self):
        """Test that local LLM has zero cost"""
        calculator = CostCalculator()
        
        cost = calculator.calculate_cost(
            provider_type=ProviderType.local,
            prompt_tokens=10000,
            completion_tokens=5000,
        )
        
        assert cost == 0.0
    
    def test_calculate_cost_with_override(self):
        """Test cost calculation with custom pricing"""
        calculator = CostCalculator()
        
        cost = calculator.calculate_cost(
            provider_type=ProviderType.claude,
            prompt_tokens=1000,
            completion_tokens=500,
            cost_per_1k_tokens=0.01,  # Custom pricing
        )
        
        # Total tokens: 1500, cost: 1.5 * 0.01 = $0.015
        expected = 1500 / 1000 * 0.01
        assert abs(cost - expected) < 0.0001


class TestCostController:
    """Test cost controller enforcement"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def cost_controller(self, mock_db):
        """Create cost controller with default limits"""
        return CostController(mock_db)
    
    def test_should_allow_llm_call_within_limits(self, cost_controller):
        """Test that calls are allowed within limits"""
        state = ExecutionCostState(
            execution_id=uuid.uuid4(),
            llm_call_count=2,
            total_cost_usd=0.25,
            quality_scores=[],
            cost_ceiling_usd=0.50,
            max_llm_calls=4,
        )
        
        allowed, reason = cost_controller.should_allow_llm_call(state)
        
        assert allowed is True
        assert reason is None
    
    def test_should_block_llm_call_at_max_calls(self, cost_controller):
        """Test that calls are blocked at max limit"""
        state = ExecutionCostState(
            execution_id=uuid.uuid4(),
            llm_call_count=4,
            total_cost_usd=0.30,
            quality_scores=[],
            cost_ceiling_usd=0.50,
            max_llm_calls=4,
        )
        
        allowed, reason = cost_controller.should_allow_llm_call(state)
        
        assert allowed is False
        assert "Maximum LLM calls reached" in reason
    
    def test_should_block_llm_call_at_cost_ceiling(self, cost_controller):
        """Test that calls are blocked at cost ceiling"""
        state = ExecutionCostState(
            execution_id=uuid.uuid4(),
            llm_call_count=3,
            total_cost_usd=0.50,
            quality_scores=[],
            cost_ceiling_usd=0.50,
            max_llm_calls=4,
        )
        
        allowed, reason = cost_controller.should_allow_llm_call(state)
        
        assert allowed is False
        assert "Cost ceiling reached" in reason
    
    def test_should_continue_feedback_loop_with_improvement(self, cost_controller):
        """Test feedback loop continues with good improvement"""
        state = ExecutionCostState(
            execution_id=uuid.uuid4(),
            llm_call_count=2,
            total_cost_usd=0.25,
            quality_scores=[7.0, 8.0],  # Improvement of 1.0
            cost_ceiling_usd=0.50,
            max_llm_calls=4,
        )
        
        should_continue, reason = cost_controller.should_continue_feedback_loop(state)
        
        assert should_continue is True
        assert reason is None
    
    def test_should_stop_feedback_loop_with_diminishing_returns(self, cost_controller):
        """Test feedback loop stops with small improvement"""
        state = ExecutionCostState(
            execution_id=uuid.uuid4(),
            llm_call_count=2,
            total_cost_usd=0.25,
            quality_scores=[8.0, 8.3],  # Improvement of 0.3 < 0.5 threshold
            cost_ceiling_usd=0.50,
            max_llm_calls=4,
        )
        
        should_continue, reason = cost_controller.should_continue_feedback_loop(state)
        
        assert should_continue is False
        assert "Diminishing returns" in reason
    
    def test_calculate_cost_per_quality_point(self, cost_controller):
        """Test cost efficiency calculation"""
        cost_per_point = cost_controller.calculate_cost_per_quality_point(
            total_cost_usd=0.40,
            quality_score=8.0,
        )
        
        assert cost_per_point == 0.05  # $0.40 / 8 = $0.05 per point
    
    def test_calculate_cost_per_quality_point_zero_quality(self, cost_controller):
        """Test cost efficiency with zero quality returns infinity"""
        cost_per_point = cost_controller.calculate_cost_per_quality_point(
            total_cost_usd=0.40,
            quality_score=0.0,
        )
        
        assert cost_per_point == float('inf')


class TestTenantCostController:
    """Test tenant-level cost controls"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def tenant_controller(self, mock_db):
        """Create tenant cost controller"""
        return TenantCostController(mock_db, daily_threshold_usd=10.0)
    
    @pytest.mark.asyncio
    async def test_check_tenant_limits_within_budget(self, tenant_controller):
        """Test tenant check passes within budget"""
        tenant_id = uuid.uuid4()
        
        # Mock cost tracker
        tenant_controller.cost_tracker.get_tenant_daily_cost = AsyncMock(return_value=5.0)
        
        can_proceed, reason, daily_cost = await tenant_controller.check_tenant_limits(tenant_id)
        
        assert can_proceed is True
        assert reason is None
        assert daily_cost == 5.0
    
    @pytest.mark.asyncio
    async def test_check_tenant_limits_at_threshold(self, tenant_controller):
        """Test tenant check fails at threshold"""
        tenant_id = uuid.uuid4()
        
        # Mock cost tracker
        tenant_controller.cost_tracker.get_tenant_daily_cost = AsyncMock(return_value=10.0)
        
        can_proceed, reason, daily_cost = await tenant_controller.check_tenant_limits(tenant_id)
        
        assert can_proceed is False
        assert "Daily cost limit reached" in reason
        assert daily_cost == 10.0


class TestProviderSelector:
    """Test cost-based provider selection"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def provider_selector(self, mock_db):
        """Create provider selector"""
        return ProviderSelector(mock_db)
    
    def test_calculate_cost_score_groq_highest(self, provider_selector):
        """Test that Groq gets highest cost score (cheapest)"""
        groq_score = provider_selector.calculate_cost_score(
            ProviderType.groq,
            0.0001,
        )
        
        claude_score = provider_selector.calculate_cost_score(
            ProviderType.claude,
            0.003,
        )
        
        # Groq should have higher cost score (cheaper)
        assert groq_score > claude_score
    
    def test_calculate_health_score_circuit_open(self, provider_selector):
        """Test health score is low when circuit is open"""
        # Mock health monitor
        with patch('app.services.provider_selector.health_monitor') as mock_monitor:
            mock_metrics = MagicMock()
            mock_metrics.circuit_open = True
            mock_metrics.success_rate = 0.5
            mock_monitor.metrics = {ProviderType.claude: mock_metrics}
            
            score = provider_selector.calculate_health_score(ProviderType.claude)
            
            assert score == 0.1  # Very low score for open circuit


class TestCostAlertService:
    """Test cost alert webhooks"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def alert_service(self, mock_db):
        """Create alert service"""
        return CostAlertService(mock_db)
    
    @pytest.mark.asyncio
    async def test_send_threshold_alert_80_percent(self, alert_service):
        """Test 80% threshold alert"""
        tenant_id = uuid.uuid4()
        
        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.slug = "test-tenant"
        alert_service.get_tenant = AsyncMock(return_value=mock_tenant)
        
        # Mock webhook
        with patch.object(alert_service, '_send_webhook', return_value=True) as mock_webhook:
            success = await alert_service.send_threshold_alert(
                tenant_id=tenant_id,
                daily_cost=8.0,
                threshold=10.0,
                percent_used=80.0,
                webhook_url="https://example.com/webhook",
            )
            
            assert success is True
            mock_webhook.assert_called_once()
            
            # Check payload
            call_args = mock_webhook.call_args
            payload = call_args[0][1]
            assert payload["alert_type"] == AlertType.THRESHOLD_80.value
            assert payload["alert_level"] == AlertLevel.WARNING.value
            assert payload["cost_metrics"]["daily_cost_usd"] == 8.0
    
    @pytest.mark.asyncio
    async def test_send_threshold_alert_100_percent(self, alert_service):
        """Test 100% threshold alert"""
        tenant_id = uuid.uuid4()
        
        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.slug = "test-tenant"
        alert_service.get_tenant = AsyncMock(return_value=mock_tenant)
        
        # Mock webhook
        with patch.object(alert_service, '_send_webhook', return_value=True) as mock_webhook:
            success = await alert_service.send_threshold_alert(
                tenant_id=tenant_id,
                daily_cost=10.0,
                threshold=10.0,
                percent_used=100.0,
                webhook_url="https://example.com/webhook",
            )
            
            assert success is True
            
            # Check payload
            call_args = mock_webhook.call_args
            payload = call_args[0][1]
            assert payload["alert_type"] == AlertType.THRESHOLD_100.value
            assert payload["alert_level"] == AlertLevel.CRITICAL.value
    
    @pytest.mark.asyncio
    async def test_alert_deduplication(self, alert_service):
        """Test that alerts are not sent twice in same day"""
        tenant_id = uuid.uuid4()
        
        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.slug = "test-tenant"
        alert_service.get_tenant = AsyncMock(return_value=mock_tenant)
        
        # Mock webhook
        with patch.object(alert_service, '_send_webhook', return_value=True) as mock_webhook:
            # Send first alert
            await alert_service.send_threshold_alert(
                tenant_id=tenant_id,
                daily_cost=8.0,
                threshold=10.0,
                percent_used=80.0,
                webhook_url="https://example.com/webhook",
            )
            
            # Try to send again
            await alert_service.send_threshold_alert(
                tenant_id=tenant_id,
                daily_cost=8.5,
                threshold=10.0,
                percent_used=85.0,
                webhook_url="https://example.com/webhook",
            )
            
            # Should only be called once due to deduplication
            assert mock_webhook.call_count == 1
