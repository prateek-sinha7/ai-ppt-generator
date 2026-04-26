"""
Integration test for chart diversity functionality.

Tests the complete flow from storyboarding through validation to ensure
exactly 3 chart slides with different types (bar, line, pie).
"""

import pytest
from app.agents.storyboarding import StoryboardingAgent
from app.agents.prompt_engineering import PromptEngineeringAgent
from app.agents.validation import ValidationAgent
from app.db.models import ProviderType


class TestChartDiversityIntegration:
    """Integration tests for chart diversity across the pipeline."""

    @pytest.fixture
    def storyboarding_agent(self):
        return StoryboardingAgent()

    @pytest.fixture
    def prompt_agent(self):
        return PromptEngineeringAgent()

    @pytest.fixture
    def validation_agent(self):
        return ValidationAgent()

    @pytest.fixture
    def sample_research_findings(self):
        return {
            "context_summary": "Technology industry analysis",
            "sections": ["Market Analysis", "Competitive Landscape"],
            "risks": ["Market volatility", "Regulatory changes"],
            "opportunities": ["AI adoption", "Digital transformation"],
            "terminology": ["SaaS", "API", "Cloud", "ML", "IoT"]
        }

    def test_end_to_end_chart_diversity_flow(self, storyboarding_agent, prompt_agent, validation_agent, sample_research_findings):
        """Test complete flow ensures exactly 3 diverse chart types."""
        
        # Step 1: Storyboarding creates presentation plan with exactly 3 charts
        presentation_plan = storyboarding_agent.generate_presentation_plan(
            topic="AI Technology Transformation",
            industry="technology"
        )
        
        # Convert to dict for easier testing
        plan_dict = presentation_plan.model_dump()
        
        # Verify storyboarding limits to 3 charts
        chart_count = 0
        for section in plan_dict["sections"]:
            chart_count += section["slide_types"].count("chart")
        
        assert chart_count == 3, f"Storyboarding should create exactly 3 chart slides, got {chart_count}"
        
        # Step 2: Prompt engineering generates chart type assignments
        chart_assignments = prompt_agent._generate_chart_type_assignments(plan_dict)
        
        assert len(chart_assignments) == 3, f"Should have 3 chart assignments, got {len(chart_assignments)}"
        
        # Verify strategic chart types
        chart_types = list(chart_assignments.values())
        expected_types = ["bar", "line", "pie"]
        assert chart_types == expected_types, f"Expected {expected_types}, got {chart_types}"
        
        # Step 3: Generate prompt with chart guidance
        prompt = prompt_agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="AI Technology Transformation",
            industry="technology",
            research_findings=sample_research_findings,
            presentation_plan=plan_dict,
            execution_id="test-integration"
        )
        
        # Verify chart guidance is in prompt
        assert "CHART TYPE ASSIGNMENTS (MUST FOLLOW EXACTLY):" in prompt.user_prompt
        assert "chart_type = \"bar\"" in prompt.user_prompt
        assert "chart_type = \"line\"" in prompt.user_prompt
        assert "chart_type = \"pie\"" in prompt.user_prompt
        
        # Step 4: Simulate LLM output with extra charts (to test validation)
        mock_llm_output = {
            "slides": [
                {"type": "title", "title": "AI Transformation", "content": {}},
                {"type": "content", "title": "Agenda", "content": {"bullets": ["Overview", "Analysis", "Recommendations"]}},
                {"type": "chart", "title": "Market Analysis", "content": {"chart_data": [{"label": "Q1", "value": 100}], "chart_type": "bar"}},
                {"type": "chart", "title": "Growth Trends", "content": {"chart_data": [{"label": "Q2", "value": 150}], "chart_type": "line"}},
                {"type": "chart", "title": "Market Share", "content": {"chart_data": [{"label": "Us", "value": 30}], "chart_type": "pie"}},
                {"type": "content", "title": "Performance Rate Analysis", "content": {"chart_data": [{"label": "Q3", "value": 200}]}},  # Extra chart
                {"type": "content", "title": "Growth vs Competition", "content": {"bullets": ["Revenue: $100M", "Growth: 25%"]}},  # Would be chart by old logic
                {"type": "content", "title": "Recommendations", "content": {"bullets": ["Invest in AI", "Expand market"]}},
            ]
        }
        
        # Step 5: Validation agent enforces 3-chart limit
        corrected_data, corrections = validation_agent.infer_slide_types(mock_llm_output)
        
        # Count final chart slides
        final_chart_slides = [slide for slide in corrected_data["slides"] if slide["type"] == "chart"]
        assert len(final_chart_slides) == 3, f"Validation should enforce 3 chart limit, got {len(final_chart_slides)}"
        
        # Verify chart types are preserved
        chart_types_final = [slide["content"].get("chart_type") for slide in final_chart_slides]
        assert "bar" in chart_types_final, "Should have bar chart"
        assert "line" in chart_types_final, "Should have line chart"
        assert "pie" in chart_types_final, "Should have pie chart"
        
        # Verify excess chart data was removed
        slide_6 = corrected_data["slides"][5]  # 6th slide (0-indexed)
        assert slide_6["type"] == "content", "6th slide should remain content"
        assert "chart_data" not in slide_6["content"], "Excess chart_data should be removed"
        
        # Verify keyword-based conversion was disabled
        slide_7 = corrected_data["slides"][6]  # 7th slide
        assert slide_7["type"] == "content", "7th slide should remain content despite keywords"

    def test_storyboarding_chart_allocation_consistency(self, storyboarding_agent):
        """Test that storyboarding consistently allocates exactly 3 charts."""
        
        # Test multiple topics to ensure consistency
        test_topics = [
            ("Technology Transformation", "technology"),
            ("Market Analysis", "finance"),
            ("Product Strategy", "retail"),
            ("Digital Innovation", "technology"),
        ]
        
        for topic, industry in test_topics:
            presentation_plan = storyboarding_agent.generate_presentation_plan(
                topic=topic,
                industry=industry
            )
            
            plan_dict = presentation_plan.model_dump()
            
            chart_count = 0
            for section in plan_dict["sections"]:
                chart_count += section["slide_types"].count("chart")
            
            assert chart_count == 3, \
                f"For topic '{topic}', expected 3 charts, got {chart_count}"