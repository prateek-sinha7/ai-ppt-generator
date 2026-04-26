"""
Tests for chart type diversity functionality.

Ensures that presentations have varied chart types instead of all bar charts.
"""

import pytest
from app.agents.prompt_engineering import PromptEngineeringAgent
from app.db.models import ProviderType


class TestChartTypeDiversity:
    """Test chart type diversity functionality."""

    @pytest.fixture
    def agent(self):
        """Create a PromptEngineeringAgent instance."""
        return PromptEngineeringAgent()

    @pytest.fixture
    def sample_presentation_plan_with_charts(self):
        """Sample presentation plan with multiple chart slides."""
        return {
            "total_slides": 10,
            "sections": [
                {
                    "name": "Title",
                    "slide_count": 1,
                    "slide_types": ["title"]
                },
                {
                    "name": "Analysis", 
                    "slide_count": 6,
                    "slide_types": ["content", "chart", "chart", "chart", "table", "chart"]
                },
                {
                    "name": "Conclusion",
                    "slide_count": 3,
                    "slide_types": ["chart", "comparison", "content"]
                }
            ]
        }

    @pytest.fixture
    def sample_research_findings(self):
        """Sample research findings."""
        return {
            "context_summary": "Technology industry analysis",
            "sections": ["Market Analysis", "Competitive Landscape"],
            "risks": ["Market volatility", "Regulatory changes"],
            "opportunities": ["AI adoption", "Digital transformation"],
            "terminology": ["SaaS", "API", "Cloud", "ML", "IoT"]
        }

    def test_chart_type_assignments_generation(self, agent, sample_presentation_plan_with_charts):
        """Test that chart type assignments are generated correctly for exactly 3 charts."""
        chart_assignments = agent._generate_chart_type_assignments(sample_presentation_plan_with_charts)
        
        # Should have exactly 3 chart slides with strategic types
        expected_chart_slides = [3, 4, 5]  # First 3 chart slides
        expected_chart_types = ["bar", "line", "pie"]  # Strategic assignment
        
        assert len(chart_assignments) == 3, f"Expected exactly 3 chart slides, got {len(chart_assignments)}"
        
        for i, slide_num in enumerate(expected_chart_slides):
            assert slide_num in chart_assignments, f"Slide {slide_num} should have chart type assignment"
            assert chart_assignments[slide_num] == expected_chart_types[i], \
                f"Slide {slide_num} should be {expected_chart_types[i]}, got {chart_assignments[slide_num]}"

    def test_chart_type_rotation_cycles(self, agent):
        """Test that chart types are limited to exactly 3 strategic types."""
        # Create a plan with many chart slides to test limiting
        presentation_plan = {
            "total_slides": 15,
            "sections": [
                {
                    "name": "Title",
                    "slide_count": 1,
                    "slide_types": ["title"]
                },
                {
                    "name": "Charts", 
                    "slide_count": 14,
                    "slide_types": ["chart"] * 14  # 14 chart slides requested
                }
            ]
        }
        
        chart_assignments = agent._generate_chart_type_assignments(presentation_plan)
        
        # Should have exactly 3 chart slides, not 14
        assert len(chart_assignments) == 3, f"Should limit to 3 charts, got {len(chart_assignments)}"
        
        # Should be the strategic types
        expected_types = ["bar", "line", "pie"]
        for i in range(3):
            slide_num = i + 2  # Charts start at slide 2
            assert chart_assignments[slide_num] == expected_types[i]

    def test_chart_type_guidance_formatting(self, agent, sample_presentation_plan_with_charts):
        """Test that chart type guidance is formatted correctly."""
        chart_assignments = agent._generate_chart_type_assignments(sample_presentation_plan_with_charts)
        guidance = agent._format_chart_type_guidance(chart_assignments)
        
        # Should contain header
        assert "CHART TYPE ASSIGNMENTS (MUST FOLLOW EXACTLY):" in guidance
        
        # Should contain specific assignments for exactly 3 charts
        assert "Slide 3: chart_type = \"bar\"" in guidance
        assert "Slide 4: chart_type = \"line\"" in guidance
        assert "Slide 5: chart_type = \"pie\"" in guidance
        
        # Should contain strategic rationale
        assert "STRATEGIC CHART TYPE RATIONALE:" in guidance
        assert "bar: Use for market comparisons" in guidance
        assert "line: Use for trends over time" in guidance
        assert "pie: Use for market share" in guidance
        assert "EXACTLY these chart types" in guidance

    def test_empty_chart_assignments_guidance(self, agent):
        """Test guidance when there are no chart slides."""
        empty_assignments = {}
        guidance = agent._format_chart_type_guidance(empty_assignments)
        
        assert guidance == "No chart slides in this presentation."

    def test_prompt_includes_chart_guidance(self, agent, sample_presentation_plan_with_charts, sample_research_findings):
        """Test that generated prompts include chart type guidance."""
        prompt = agent.generate_prompt(
            provider_type=ProviderType.claude,
            topic="Technology Transformation Strategy",
            industry="technology",
            research_findings=sample_research_findings,
            presentation_plan=sample_presentation_plan_with_charts,
            execution_id="test-chart-diversity"
        )
        
        # Verify chart type assignments are in the prompt
        assert "CHART TYPE ASSIGNMENTS (MUST FOLLOW EXACTLY):" in prompt.user_prompt
        assert "Slide 3: chart_type = \"bar\"" in prompt.user_prompt
        assert "Slide 4: chart_type = \"line\"" in prompt.user_prompt
        assert "Slide 5: chart_type = \"pie\"" in prompt.user_prompt
        assert "STRATEGIC CHART TYPE RATIONALE:" in prompt.user_prompt

    def test_all_provider_templates_support_chart_diversity(self, agent, sample_presentation_plan_with_charts, sample_research_findings):
        """Test that all LLM provider templates include chart diversity guidance."""
        providers = [ProviderType.claude, ProviderType.openai, ProviderType.groq, ProviderType.local]
        
        for provider in providers:
            prompt = agent.generate_prompt(
                provider_type=provider,
                topic="Test Topic",
                industry="technology",
                research_findings=sample_research_findings,
                presentation_plan=sample_presentation_plan_with_charts,
                execution_id=f"test-{provider.value}"
            )
            
            # All providers should get chart type assignments
            assert "CHART TYPE ASSIGNMENTS" in prompt.user_prompt, f"Provider {provider.value} missing chart assignments"

    def test_no_chart_slides_no_assignments(self, agent):
        """Test that presentations with no chart slides get no chart assignments."""
        presentation_plan = {
            "total_slides": 5,
            "sections": [
                {
                    "name": "Title",
                    "slide_count": 1,
                    "slide_types": ["title"]
                },
                {
                    "name": "Content", 
                    "slide_count": 4,
                    "slide_types": ["content", "table", "comparison", "metric"]
                }
            ]
        }
        
        chart_assignments = agent._generate_chart_type_assignments(presentation_plan)
        assert len(chart_assignments) == 0, "Should have no chart assignments when no chart slides"

    def test_chart_type_constants(self, agent):
        """Test that chart types are limited to strategic 3."""
        # Test the strategic chart types used in _generate_chart_type_assignments
        presentation_plan = {
            "total_slides": 5,
            "sections": [
                {
                    "name": "Title",
                    "slide_count": 1,
                    "slide_types": ["title"]
                },
                {
                    "name": "Analysis", 
                    "slide_count": 4,
                    "slide_types": ["chart", "chart", "chart", "content"]
                }
            ]
        }
        
        chart_assignments = agent._generate_chart_type_assignments(presentation_plan)
        expected_types = ["bar", "line", "pie"]  # Strategic 3-chart approach
        
        # Verify the strategic types are used
        actual_types = list(chart_assignments.values())
        assert actual_types == expected_types, f"Chart types mismatch: {actual_types}"