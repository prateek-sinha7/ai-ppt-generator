"""
Test validation agent's 3-chart limit enforcement.
"""

import pytest
from app.agents.validation import ValidationAgent


class TestValidationChartLimit:
    """Test that validation agent enforces 3-chart limit."""

    @pytest.fixture
    def agent(self):
        """Create a ValidationAgent instance."""
        return ValidationAgent()

    def test_infer_slide_types_respects_chart_limit(self, agent):
        """Test that slide type inference respects 3-chart limit."""
        # Create test data with 5 potential chart slides
        test_data = {
            "slides": [
                {"type": "title", "title": "Title Slide", "content": {}},
                {"type": "chart", "title": "Chart 1", "content": {"chart_data": [{"label": "A", "value": 10}]}},
                {"type": "chart", "title": "Chart 2", "content": {"chart_data": [{"label": "B", "value": 20}]}},
                {"type": "chart", "title": "Chart 3", "content": {"chart_data": [{"label": "C", "value": 30}]}},
                {"type": "content", "title": "Growth Trends Analysis", "content": {"chart_data": [{"label": "D", "value": 40}]}},  # Would be converted to chart
                {"type": "content", "title": "Market Rate Comparison", "content": {"bullets": ["Revenue: $100M", "Growth: 25%"]}},  # Would be converted to chart by old logic
            ]
        }
        
        corrected_data, corrections = agent.infer_slide_types(test_data)
        
        # Count chart slides in result
        chart_slides = [slide for slide in corrected_data["slides"] if slide["type"] == "chart"]
        
        # Should have exactly 3 chart slides (the first 3 that had chart_data)
        assert len(chart_slides) == 3, f"Expected exactly 3 chart slides, got {len(chart_slides)}"
        
        # The 4th slide should have had its chart_data removed and stayed as content
        slide_4 = corrected_data["slides"][4]
        assert slide_4["type"] == "content", "4th slide should remain content type"
        assert "chart_data" not in slide_4["content"], "4th slide should have chart_data removed"
        
        # The 5th slide should remain content (keyword-based conversion disabled)
        slide_5 = corrected_data["slides"][5]
        assert slide_5["type"] == "content", "5th slide should remain content type"

    def test_keyword_based_chart_inference_disabled(self, agent):
        """Test that keyword-based chart inference is disabled."""
        test_data = {
            "slides": [
                {"type": "title", "title": "Title", "content": {}},
                {"type": "content", "title": "Growth Trends Analysis", "content": {"bullets": ["Revenue: $100M", "Growth: 25%"]}},
                {"type": "content", "title": "Market Rate Comparison vs Competition", "content": {"bullets": ["Market share: 15%", "Competitor A: 20%"]}},
                {"type": "content", "title": "Performance Chart Overview", "content": {"bullets": ["Q1: 10%", "Q2: 15%", "Q3: 20%"]}},
            ]
        }
        
        corrected_data, corrections = agent.infer_slide_types(test_data)
        
        # All content slides should remain content (no keyword-based conversion)
        for i in range(1, 4):
            slide = corrected_data["slides"][i]
            assert slide["type"] == "content", f"Slide {i+1} should remain content type despite keywords"

    def test_existing_chart_data_still_creates_charts(self, agent):
        """Test that slides with actual chart_data still become chart type."""
        test_data = {
            "slides": [
                {"type": "title", "title": "Title", "content": {}},
                {"type": "content", "title": "Revenue Analysis", "content": {"chart_data": [{"label": "Q1", "value": 100}]}},
                {"type": "content", "title": "Growth Metrics", "content": {"chart_data": [{"label": "Q2", "value": 150}]}},
            ]
        }
        
        corrected_data, corrections = agent.infer_slide_types(test_data)
        
        # Both slides with chart_data should become chart type
        assert corrected_data["slides"][1]["type"] == "chart"
        assert corrected_data["slides"][2]["type"] == "chart"
        assert corrections == 2  # Two corrections made