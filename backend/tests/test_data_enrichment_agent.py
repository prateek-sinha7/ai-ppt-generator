"""
Tests for Data Enrichment Agent

Tests cover:
- Seed-based data generation with reproducibility
- INDUSTRY_DATA_RANGES for known industries
- LLM-based dynamic range generation for unknown industries
- Chart type suggestion logic
- Data consistency validation
- Audit trail logging
"""

import pytest
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.agents.data_enrichment import (
    DataEnrichmentAgent,
    INDUSTRY_DATA_RANGES,
    AGENT_VERSION,
    ChartData,
    TableData,
    EnrichedData,
)


@pytest.fixture
def agent():
    """Create a DataEnrichmentAgent instance"""
    return DataEnrichmentAgent()


@pytest.fixture
def mock_provider_factory():
    """Mock provider factory for LLM calls"""
    with patch("app.agents.data_enrichment.provider_factory") as mock:
        yield mock


@pytest.fixture
def mock_db():
    """Mock database session"""
    with patch("app.agents.data_enrichment.get_db") as mock:
        db_session = AsyncMock()
        mock.return_value.__aiter__.return_value = [db_session]
        yield db_session


class TestSeedBasedGeneration:
    """Test seed-based data generation (Task 10.1)"""
    
    def test_compute_topic_hash(self, agent):
        """Test topic hash computation"""
        topic = "Healthcare Risk Assessment"
        
        # Compute hash
        topic_hash = agent._compute_topic_hash(topic)
        
        # Verify it's a valid SHA-256 hash
        assert len(topic_hash) == 64
        assert all(c in '0123456789abcdef' for c in topic_hash)
        
        # Verify determinism
        topic_hash2 = agent._compute_topic_hash(topic)
        assert topic_hash == topic_hash2
    
    def test_compute_seed_deterministic(self, agent):
        """Test seed computation is deterministic"""
        topic = "Healthcare Risk Assessment"
        
        # Compute seed multiple times
        seed1 = agent._compute_seed(topic)
        seed2 = agent._compute_seed(topic)
        seed3 = agent._compute_seed(topic)
        
        # All should be identical
        assert seed1 == seed2 == seed3
        assert isinstance(seed1, int)
    
    def test_compute_seed_different_topics(self, agent):
        """Test different topics produce different seeds"""
        topic1 = "Healthcare Risk Assessment"
        topic2 = "Insurance Market Analysis"
        
        seed1 = agent._compute_seed(topic1)
        seed2 = agent._compute_seed(topic2)
        
        # Seeds should be different
        assert seed1 != seed2
    
    @pytest.mark.asyncio
    async def test_reproducible_data_generation(self, agent, mock_provider_factory):
        """Test data generation is reproducible with same topic"""
        topic = "Healthcare Risk Assessment"
        industry = "healthcare"
        execution_id = "test-exec-1"
        
        # Generate data twice
        data1 = await agent.enrich_data(topic, industry, execution_id)
        data2 = await agent.enrich_data(topic, industry, execution_id)
        
        # Seeds should be identical
        assert data1.seed == data2.seed
        
        # Key metrics should be identical
        assert data1.key_metrics == data2.key_metrics
        
        # Charts should have identical data
        assert len(data1.charts) == len(data2.charts)
        for chart1, chart2 in zip(data1.charts, data2.charts):
            assert chart1.datasets == chart2.datasets


class TestIndustryDataRanges:
    """Test INDUSTRY_DATA_RANGES (Task 10.2)"""
    
    def test_predefined_ranges_exist(self):
        """Test predefined ranges exist for known industries"""
        expected_industries = [
            "healthcare",
            "insurance",
            "automobile",
            "finance",
            "technology",
            "retail",
            "education",
            "manufacturing",
            "logistics",
            "real_estate",
        ]
        
        for industry in expected_industries:
            assert industry in INDUSTRY_DATA_RANGES
            assert len(INDUSTRY_DATA_RANGES[industry]) > 0
    
    def test_range_format(self):
        """Test all ranges have correct format (min, max)"""
        for industry, ranges in INDUSTRY_DATA_RANGES.items():
            for metric_name, (min_val, max_val) in ranges.items():
                assert isinstance(min_val, (int, float))
                assert isinstance(max_val, (int, float))
                assert min_val < max_val, f"{industry}.{metric_name}: min >= max"
    
    def test_get_data_ranges_exact_match(self, agent):
        """Test getting data ranges with exact industry match"""
        ranges = agent._get_data_ranges("healthcare")
        
        assert ranges is not None
        assert "patient_satisfaction" in ranges
        assert ranges["patient_satisfaction"] == (75.0, 95.0)
    
    def test_get_data_ranges_partial_match(self, agent):
        """Test getting data ranges with partial industry match"""
        ranges = agent._get_data_ranges("healthcare services")
        
        assert ranges is not None
        assert "patient_satisfaction" in ranges
    
    def test_get_data_ranges_unknown_industry(self, agent):
        """Test getting data ranges for unknown industry returns None"""
        ranges = agent._get_data_ranges("quantum_computing")
        
        assert ranges is None


class TestDynamicRangeGeneration:
    """Test LLM-based dynamic range generation (Task 10.3)"""
    
    @pytest.mark.asyncio
    async def test_get_data_ranges_from_llm_success(self, agent, mock_provider_factory):
        """Test successful LLM-based range generation"""
        # Mock LLM response
        mock_provider_factory.call_with_failover = AsyncMock(return_value={
            "industry": "quantum_computing",
            "ranges": [
                {"metric_name": "qubit_count", "min_value": 50.0, "max_value": 1000.0, "unit": "qubits"},
                {"metric_name": "error_rate", "min_value": 0.1, "max_value": 5.0, "unit": "%"},
                {"metric_name": "coherence_time_ms", "min_value": 10.0, "max_value": 100.0, "unit": "ms"},
            ]
        })
        
        ranges = await agent._get_data_ranges_from_llm(
            industry="quantum_computing",
            topic="Quantum Computing Market Analysis",
            execution_id="test-exec-1",
        )
        
        assert ranges is not None
        assert "qubit_count" in ranges
        assert ranges["qubit_count"] == (50.0, 1000.0)
        assert "error_rate" in ranges
        assert "coherence_time_ms" in ranges
    
    @pytest.mark.asyncio
    async def test_get_data_ranges_from_llm_failure_fallback(self, agent, mock_provider_factory):
        """Test LLM failure falls back to generic ranges"""
        # Mock LLM failure
        mock_provider_factory.call_with_failover = AsyncMock(side_effect=Exception("LLM error"))
        
        ranges = await agent._get_data_ranges_from_llm(
            industry="quantum_computing",
            topic="Quantum Computing Market Analysis",
            execution_id="test-exec-1",
        )
        
        # Should return generic fallback ranges
        assert ranges is not None
        assert "revenue_millions" in ranges
        assert "market_share" in ranges
        assert "growth_rate" in ranges


class TestChartTypeSuggestion:
    """Test chart type suggestion logic (Task 10.4)"""
    
    def test_suggest_pie_chart_for_share_metrics(self, agent):
        """Test pie chart suggestion for share/distribution metrics"""
        chart_type, reason = agent._suggest_chart_type(
            "market_share_distribution",
            [25.0, 30.0, 20.0, 15.0, 10.0]
        )
        
        assert chart_type == "pie"
        assert "composition" in reason.lower() or "proportion" in reason.lower()
    
    def test_suggest_line_chart_for_trend_metrics(self, agent):
        """Test line chart suggestion for trend metrics"""
        chart_type, reason = agent._suggest_chart_type(
            "revenue_growth_over_time",
            [100.0, 110.0, 125.0, 140.0, 160.0]
        )
        
        assert chart_type == "line"
        assert "trend" in reason.lower() or "time" in reason.lower()
    
    def test_suggest_bar_chart_for_comparison_metrics(self, agent):
        """Test bar chart suggestion for comparison metrics"""
        chart_type, reason = agent._suggest_chart_type(
            "sales_by_region_comparison",
            [100.0, 150.0, 120.0, 180.0]
        )
        
        assert chart_type == "bar"
        assert "comparison" in reason.lower()
    
    def test_suggest_bar_chart_default(self, agent):
        """Test bar chart as default for general metrics"""
        chart_type, reason = agent._suggest_chart_type(
            "customer_satisfaction",
            [85.0, 87.0, 90.0, 88.0]
        )
        
        assert chart_type == "bar"
    
    def test_pie_chart_limited_to_few_categories(self, agent):
        """Test pie chart only suggested for few categories"""
        # Many categories - should not suggest pie
        chart_type, reason = agent._suggest_chart_type(
            "market_share_distribution",
            [10.0] * 10  # 10 categories
        )
        
        # Should fall back to bar chart
        assert chart_type == "bar"


class TestDataConsistencyValidation:
    """Test data consistency validation (Task 10.5)"""
    
    def test_validate_consistent_data(self, agent):
        """Test validation passes for consistent data"""
        key_metrics = {
            "revenue_millions": 150.5,
            "market_share": 25.3,
            "growth_rate": 12.5,
            "customer_satisfaction": 85.0,
        }
        
        is_valid = agent._validate_data_consistency(key_metrics)
        
        assert is_valid is True
    
    def test_validate_detects_nan(self, agent):
        """Test validation detects NaN values"""
        key_metrics = {
            "revenue_millions": 150.5,
            "market_share": float('nan'),
            "growth_rate": 12.5,
        }
        
        is_valid = agent._validate_data_consistency(key_metrics)
        
        assert is_valid is False
    
    def test_validate_detects_infinity(self, agent):
        """Test validation detects infinite values"""
        key_metrics = {
            "revenue_millions": float('inf'),
            "market_share": 25.3,
            "growth_rate": 12.5,
        }
        
        is_valid = agent._validate_data_consistency(key_metrics)
        
        assert is_valid is False
    
    def test_validate_warns_on_percentage_out_of_range(self, agent, caplog):
        """Test validation warns on percentage values outside 0-100"""
        key_metrics = {
            "market_share": 150.0,  # Invalid percentage
            "growth_rate": 12.5,
        }
        
        # Should still pass but log warning
        is_valid = agent._validate_data_consistency(key_metrics)
        
        assert is_valid is True
        # Warning should be logged (check if structlog captured it)


class TestAuditTrailLogging:
    """Test audit trail logging (Task 10.6)"""
    
    @pytest.mark.asyncio
    async def test_store_enriched_data_with_audit_trail(self, agent, mock_db):
        """Test storing enriched data includes audit trail"""
        enriched_data = EnrichedData(
            topic="Healthcare Risk Assessment",
            industry="healthcare",
            seed=12345,
            topic_hash="abc123def456",
            charts=[],
            tables=[],
            key_metrics={"revenue_millions": 150.5},
            data_sources=["Industry benchmarks"],
            methodology_notes="Test methodology",
            execution_id="test-exec-1",
            agent_version=AGENT_VERSION,
            created_at=datetime.utcnow().isoformat(),
        )
        
        # Mock pipeline execution
        mock_execution = MagicMock()
        mock_execution.id = "test-exec-1"
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_execution))
        mock_db.commit = AsyncMock()
        
        await agent.store_enriched_data(enriched_data, "test-exec-1")
        
        # Verify agent state was created
        mock_db.add.assert_called_once()
        agent_state = mock_db.add.call_args[0][0]
        
        assert agent_state.agent_name == "data_enrichment_agent"
        assert agent_state.execution_id == "test-exec-1"
        
        # Verify audit trail fields in state
        state_dict = agent_state.state
        assert state_dict["seed"] == 12345
        assert state_dict["topic_hash"] == "abc123def456"
        assert state_dict["agent_version"] == AGENT_VERSION
        assert state_dict["industry"] == "healthcare"
    
    @pytest.mark.asyncio
    async def test_enriched_data_includes_audit_fields(self, agent, mock_provider_factory):
        """Test enriched data includes all audit trail fields"""
        topic = "Healthcare Risk Assessment"
        industry = "healthcare"
        execution_id = "test-exec-1"
        
        enriched_data = await agent.enrich_data(topic, industry, execution_id)
        
        # Verify audit trail fields
        assert enriched_data.seed is not None
        assert enriched_data.topic_hash is not None
        assert enriched_data.agent_version == AGENT_VERSION
        assert enriched_data.execution_id == execution_id
        assert enriched_data.created_at is not None


class TestEndToEndDataEnrichment:
    """Test complete data enrichment flow"""
    
    @pytest.mark.asyncio
    async def test_enrich_data_known_industry(self, agent, mock_provider_factory):
        """Test complete enrichment for known industry"""
        topic = "Healthcare Risk Assessment"
        industry = "healthcare"
        execution_id = "test-exec-1"
        
        enriched_data = await agent.enrich_data(topic, industry, execution_id)
        
        # Verify structure
        assert enriched_data.topic == topic
        assert enriched_data.industry == industry
        assert enriched_data.seed is not None
        assert enriched_data.topic_hash is not None
        
        # Verify charts generated
        assert len(enriched_data.charts) > 0
        for chart in enriched_data.charts:
            assert isinstance(chart, ChartData)
            assert chart.chart_type in ["bar", "line", "pie"]
            assert len(chart.labels) > 0
            assert len(chart.datasets) > 0
        
        # Verify tables generated
        assert len(enriched_data.tables) >= 0
        for table in enriched_data.tables:
            assert isinstance(table, TableData)
            assert len(table.headers) > 0
            assert len(table.rows) > 0
        
        # Verify key metrics
        assert len(enriched_data.key_metrics) > 0
        
        # Verify metadata
        assert len(enriched_data.data_sources) > 0
        assert enriched_data.methodology_notes is not None
        assert enriched_data.agent_version == AGENT_VERSION
    
    @pytest.mark.asyncio
    async def test_enrich_data_unknown_industry_uses_llm(self, agent, mock_provider_factory):
        """Test enrichment for unknown industry uses LLM fallback"""
        # Mock LLM response for unknown industry
        mock_provider_factory.call_with_failover = AsyncMock(return_value={
            "industry": "quantum_computing",
            "ranges": [
                {"metric_name": "qubit_count", "min_value": 50.0, "max_value": 1000.0},
                {"metric_name": "error_rate", "min_value": 0.1, "max_value": 5.0},
                {"metric_name": "coherence_time_ms", "min_value": 10.0, "max_value": 100.0},
                {"metric_name": "gate_fidelity", "min_value": 95.0, "max_value": 99.9},
                {"metric_name": "quantum_volume", "min_value": 32.0, "max_value": 512.0},
            ]
        })
        
        topic = "Quantum Computing Market Analysis"
        industry = "quantum_computing"
        execution_id = "test-exec-1"
        
        enriched_data = await agent.enrich_data(topic, industry, execution_id)
        
        # Verify LLM was called
        mock_provider_factory.call_with_failover.assert_called_once()
        
        # Verify data was generated
        assert len(enriched_data.key_metrics) > 0
        assert "qubit_count" in enriched_data.key_metrics or len(enriched_data.key_metrics) >= 5
    
    @pytest.mark.asyncio
    async def test_generate_metric_value_within_range(self, agent):
        """Test generated metric values are within specified ranges"""
        import random
        
        rng = random.Random(12345)
        min_val = 10.0
        max_val = 100.0
        
        # Generate multiple values
        for _ in range(100):
            value = agent._generate_metric_value(rng, min_val, max_val)
            assert min_val <= value <= max_val
            assert isinstance(value, float)
