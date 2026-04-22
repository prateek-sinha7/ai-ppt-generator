"""
Tests for Data Enrichment Agent LLM enhancements (Phase 2).

Tests the LLM-enhanced data richness functionality including:
- Realistic chart label generation (industry-specific)
- Rich comparative table generation (benchmarking)
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.data_enrichment import (
    DataEnrichmentAgent,
    RealisticChartLabels,
    RichTableData,
    RichTableRow,
)


@pytest.fixture
def data_enrichment_agent():
    """Create a Data Enrichment Agent instance."""
    return DataEnrichmentAgent()


class TestRealisticChartLabels:
    """Test realistic chart label generation."""
    
    @pytest.mark.asyncio
    async def test_generate_realistic_chart_labels_healthcare(
        self, data_enrichment_agent
    ):
        """Test realistic chart labels for healthcare industry."""
        mock_labels_result = {
            "labels": ["Primary Care", "Specialty", "Hospital", "Pharma", "MedTech", "Telehealth"],
            "reasoning": "These are the major revenue segments in healthcare industry",
        }
        
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_labels_result),
        ):
            result = await data_enrichment_agent.generate_realistic_chart_labels(
                metric_name="revenue_by_segment",
                industry="healthcare",
                chart_type="bar",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert len(result) == 6
        assert "Primary Care" in result
        assert "Specialty" in result
        assert "Hospital" in result
        # Should NOT contain generic labels
        assert "Category 1" not in result
        assert "Segment A" not in result
    
    @pytest.mark.asyncio
    async def test_generate_realistic_chart_labels_finance(
        self, data_enrichment_agent
    ):
        """Test realistic chart labels for finance industry."""
        mock_labels_result = {
            "labels": ["Retail Banking", "Investment", "Insurance", "Wealth Mgmt", "Fintech"],
            "reasoning": "Core segments of financial services industry",
        }
        
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_labels_result),
        ):
            result = await data_enrichment_agent.generate_realistic_chart_labels(
                metric_name="market_share",
                industry="finance",
                chart_type="pie",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert len(result) == 5
        assert "Retail Banking" in result
        assert "Investment" in result
    
    @pytest.mark.asyncio
    async def test_generate_realistic_chart_labels_fallback_on_error(
        self, data_enrichment_agent
    ):
        """Test fallback when chart label generation fails."""
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError("LLM timeout")),
        ):
            result = await data_enrichment_agent.generate_realistic_chart_labels(
                metric_name="revenue",
                industry="healthcare",
                chart_type="bar",
                execution_id="test-exec-123",
            )
        
        assert result is None  # Graceful fallback


class TestRichTableData:
    """Test rich comparative table generation."""
    
    @pytest.mark.asyncio
    async def test_generate_rich_table_data_insurance(
        self, data_enrichment_agent
    ):
        """Test rich table data for insurance industry."""
        mock_table_result = {
            "title": "Competitive Benchmarking - Insurance Metrics",
            "headers": ["Metric", "Our Position", "Market Leader", "Industry Avg", "Gap"],
            "rows": [
                {
                    "metric": "Combined Ratio",
                    "our_value": "94.2%",
                    "market_leader": "88.7%",
                    "industry_avg": "97.1%",
                    "gap": "-5.5pp",
                },
                {
                    "metric": "Claims Processing",
                    "our_value": "12.4 days",
                    "market_leader": "4.8 days",
                    "industry_avg": "15.2 days",
                    "gap": "+7.6 days",
                },
                {
                    "metric": "Customer NPS",
                    "our_value": "34",
                    "market_leader": "67",
                    "industry_avg": "28",
                    "gap": "-33 pts",
                },
            ],
            "insights": "We outperform industry average on combined ratio but lag market leader significantly on claims processing speed and customer satisfaction.",
        }
        
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_table_result),
        ):
            result = await data_enrichment_agent.generate_rich_table_data(
                topic="Insurance Digital Transformation Strategy",
                industry="insurance",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert result["title"] == "Competitive Benchmarking - Insurance Metrics"
        assert len(result["headers"]) == 5
        assert len(result["rows"]) == 3
        
        # Check first row
        first_row = result["rows"][0]
        assert first_row[0] == "Combined Ratio"
        assert first_row[1] == "94.2%"
        assert first_row[2] == "88.7%"
        assert first_row[3] == "97.1%"
        assert first_row[4] == "-5.5pp"
        
        # Should have insights
        assert len(result["insights"]) > 50
        assert "combined ratio" in result["insights"].lower()
    
    @pytest.mark.asyncio
    async def test_generate_rich_table_data_healthcare(
        self, data_enrichment_agent
    ):
        """Test rich table data for healthcare industry."""
        mock_table_result = {
            "title": "Healthcare Performance Benchmarking",
            "headers": ["Metric", "Our Position", "Market Leader", "Industry Avg", "Gap"],
            "rows": [
                {
                    "metric": "Patient Satisfaction",
                    "our_value": "82%",
                    "market_leader": "91%",
                    "industry_avg": "78%",
                    "gap": "-9pp",
                },
                {
                    "metric": "Readmission Rate",
                    "our_value": "8.2%",
                    "market_leader": "5.1%",
                    "industry_avg": "11.4%",
                    "gap": "+3.1pp",
                },
            ],
            "insights": "Strong performance on readmission rates but opportunity to improve patient satisfaction.",
        }
        
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_table_result),
        ):
            result = await data_enrichment_agent.generate_rich_table_data(
                topic="Healthcare Quality Improvement",
                industry="healthcare",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert "Healthcare" in result["title"]
        assert len(result["rows"]) == 2
    
    @pytest.mark.asyncio
    async def test_generate_rich_table_data_fallback_on_error(
        self, data_enrichment_agent
    ):
        """Test fallback when table generation fails."""
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError("LLM timeout")),
        ):
            result = await data_enrichment_agent.generate_rich_table_data(
                topic="Test Topic",
                industry="healthcare",
                execution_id="test-exec-123",
            )
        
        assert result is None  # Graceful fallback


class TestDataQuality:
    """Test data quality improvements."""
    
    @pytest.mark.asyncio
    async def test_realistic_labels_no_generic_categories(
        self, data_enrichment_agent
    ):
        """Test that realistic labels don't contain generic categories."""
        mock_labels_result = {
            "labels": ["Cloud Services", "AI/ML", "Cybersecurity", "SaaS", "IoT"],
            "reasoning": "Core technology segments",
        }
        
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_labels_result),
        ):
            result = await data_enrichment_agent.generate_realistic_chart_labels(
                metric_name="revenue_by_product",
                industry="technology",
                chart_type="bar",
                execution_id="test-exec-123",
            )
        
        # Verify NO generic labels
        generic_patterns = ["Category", "Segment", "Group", "Type"]
        for label in result:
            for pattern in generic_patterns:
                assert pattern not in label, f"Found generic pattern '{pattern}' in label '{label}'"
    
    @pytest.mark.asyncio
    async def test_rich_table_has_comparative_data(
        self, data_enrichment_agent
    ):
        """Test that rich tables include comparative benchmarking."""
        mock_table_result = {
            "title": "Competitive Analysis",
            "headers": ["Metric", "Our Position", "Market Leader", "Industry Avg", "Gap"],
            "rows": [
                {
                    "metric": "Revenue Growth",
                    "our_value": "12.5%",
                    "market_leader": "18.3%",
                    "industry_avg": "9.7%",
                    "gap": "-5.8pp",
                },
            ],
            "insights": "Above industry average but below market leader.",
        }
        
        with patch.object(
            data_enrichment_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_table_result),
        ):
            result = await data_enrichment_agent.generate_rich_table_data(
                topic="Test Topic",
                industry="retail",
                execution_id="test-exec-123",
            )
        
        # Verify comparative structure
        assert len(result["headers"]) >= 4  # At least: Metric, Our, Leader, Avg
        assert len(result["rows"]) > 0
        
        # Each row should have multiple comparison points
        for row in result["rows"]:
            assert len(row) >= 4  # At least 4 columns
