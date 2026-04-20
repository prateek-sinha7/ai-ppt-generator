"""
Unit tests for Storyboarding Agent.

Tests cover:
- Topic complexity analysis
- Slide count determination
- Section allocation
- Visual diversity enforcement
- Presentation plan generation
- Final presentation validation
"""

import pytest

from app.agents.storyboarding import (
    StoryboardingAgent,
    TopicComplexity,
    SlideType,
    VisualHint,
    PresentationPlanJSON,
    SectionPlan
)


class TestStoryboardingAgent:
    """Test suite for Storyboarding Agent."""

    @pytest.fixture
    def agent(self):
        """Create a Storyboarding Agent instance."""
        return StoryboardingAgent()

    def test_analyze_simple_topic_complexity(self, agent):
        """Test complexity analysis for simple topics."""
        topic = "Sales Report"
        industry = "retail"
        
        complexity = agent.analyze_topic_complexity(topic, industry)
        
        assert complexity == TopicComplexity.SIMPLE

    def test_analyze_moderate_topic_complexity(self, agent):
        """Test complexity analysis for moderate topics."""
        topic = "Q4 Sales Performance Analysis and Market Trends"
        industry = "retail"
        
        complexity = agent.analyze_topic_complexity(topic, industry)
        
        assert complexity == TopicComplexity.MODERATE

    def test_analyze_complex_topic_complexity(self, agent):
        """Test complexity analysis for complex topics."""
        topic = "Comprehensive Digital Transformation Strategy and Roadmap for Enterprise Cloud Migration"
        industry = "technology"
        
        complexity = agent.analyze_topic_complexity(topic, industry)
        
        assert complexity == TopicComplexity.COMPLEX

    def test_determine_optimal_slide_count_simple(self, agent):
        """Test slide count determination for simple topics."""
        count = agent.determine_optimal_slide_count(TopicComplexity.SIMPLE)
        
        assert 5 <= count <= 8

    def test_determine_optimal_slide_count_moderate(self, agent):
        """Test slide count determination for moderate topics."""
        count = agent.determine_optimal_slide_count(TopicComplexity.MODERATE)
        
        assert 9 <= count <= 15

    def test_determine_optimal_slide_count_complex(self, agent):
        """Test slide count determination for complex topics."""
        count = agent.determine_optimal_slide_count(TopicComplexity.COMPLEX)
        
        assert 16 <= count <= 25

    def test_determine_optimal_slide_count_with_template(self, agent):
        """Test slide count determination with template override."""
        count = agent.determine_optimal_slide_count(
            TopicComplexity.SIMPLE,
            template_slide_count=10
        )
        
        assert count == 10

    def test_allocate_slides_to_sections(self, agent):
        """Test slide allocation to consulting sections."""
        sections = agent.allocate_slides_to_sections(12)
        
        # Check required sections present
        section_names = [s.name for s in sections]
        assert "Title" in section_names
        assert "Agenda" in section_names
        assert "Problem" in section_names
        assert "Analysis" in section_names
        assert "Evidence" in section_names
        assert "Recommendations" in section_names
        assert "Conclusion" in section_names
        
        # Check total slide count
        total = sum(s.slide_count for s in sections)
        assert total == 12

    def test_allocate_slides_respects_bounds(self, agent):
        """Test slide allocation respects min/max bounds."""
        # Minimum
        sections_min = agent.allocate_slides_to_sections(5)
        total_min = sum(s.slide_count for s in sections_min)
        assert total_min == 5
        
        # Maximum
        sections_max = agent.allocate_slides_to_sections(25)
        total_max = sum(s.slide_count for s in sections_max)
        assert total_max == 25

    def test_visual_diversity_enforcement(self, agent):
        """Test visual diversity enforcement."""
        # Create sections with diversity violations
        sections = [
            SectionPlan(
                name="Test",
                slide_count=5,
                slide_types=[SlideType.CONTENT] * 5  # 5 consecutive same type
            )
        ]
        
        enforced = agent.enforce_visual_diversity(sections)
        
        # Check no more than 2 consecutive of same type
        all_types = []
        for section in enforced:
            all_types.extend(section.slide_types)
        
        for i in range(len(all_types) - 2):
            # Should not have 3 consecutive of same type
            assert not (all_types[i] == all_types[i+1] == all_types[i+2])

    def test_generate_presentation_plan(self, agent):
        """Test complete presentation plan generation."""
        topic = "Healthcare Market Analysis"
        industry = "healthcare"
        
        plan = agent.generate_presentation_plan(topic, industry)
        
        # Validate plan structure
        assert isinstance(plan, PresentationPlanJSON)
        assert plan.topic == topic
        assert plan.industry == industry
        assert 5 <= plan.total_slides <= 25
        assert len(plan.sections) > 0
        assert plan.visual_diversity_check is True
        
        # Validate total matches sections
        section_total = sum(s.slide_count for s in plan.sections)
        assert plan.total_slides == section_total

    def test_generate_presentation_plan_with_template(self, agent):
        """Test presentation plan generation with template."""
        topic = "Product Launch"
        industry = "technology"
        template_structure = [
            {"type": "title", "section": "Title"},
            {"type": "content", "section": "Overview"},
            {"type": "chart", "section": "Market"},
            {"type": "content", "section": "Strategy"},
        ]
        
        plan = agent.generate_presentation_plan(
            topic,
            industry,
            template_structure=template_structure
        )
        
        assert plan.total_slides == 4

    def test_validate_final_presentation_success(self, agent):
        """Test validation of matching presentation."""
        plan = PresentationPlanJSON(
            topic="Test",
            industry="test",
            total_slides=3,
            sections=[
                SectionPlan(
                    name="Title",
                    slide_count=1,
                    slide_types=[SlideType.TITLE]
                ),
                SectionPlan(
                    name="Content",
                    slide_count=2,
                    slide_types=[SlideType.CONTENT, SlideType.CHART]
                )
            ]
        )
        
        generated_slides = [
            {"type": "title", "slide_number": 1},
            {"type": "content", "slide_number": 2},
            {"type": "chart", "slide_number": 3}
        ]
        
        is_valid, errors = agent.validate_final_presentation(plan, generated_slides)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_final_presentation_count_mismatch(self, agent):
        """Test validation detects slide count mismatch."""
        plan = PresentationPlanJSON(
            topic="Test",
            industry="test",
            total_slides=3,
            sections=[
                SectionPlan(
                    name="Title",
                    slide_count=3,
                    slide_types=[SlideType.CONTENT] * 3
                )
            ]
        )
        
        generated_slides = [
            {"type": "content", "slide_number": 1},
            {"type": "content", "slide_number": 2}
        ]
        
        is_valid, errors = agent.validate_final_presentation(plan, generated_slides)
        
        assert is_valid is False
        assert any("count mismatch" in e.lower() for e in errors)

    def test_validate_final_presentation_type_mismatch(self, agent):
        """Test validation detects slide type mismatch."""
        plan = PresentationPlanJSON(
            topic="Test",
            industry="test",
            total_slides=2,
            sections=[
                SectionPlan(
                    name="Test",
                    slide_count=2,
                    slide_types=[SlideType.CONTENT, SlideType.CHART]
                )
            ]
        )
        
        generated_slides = [
            {"type": "content", "slide_number": 1},
            {"type": "table", "slide_number": 2}  # Wrong type
        ]
        
        is_valid, errors = agent.validate_final_presentation(plan, generated_slides)
        
        assert is_valid is False
        assert any("type mismatch" in e.lower() for e in errors)

    def test_validate_final_presentation_diversity_violation(self, agent):
        """Test validation detects visual diversity violations."""
        plan = PresentationPlanJSON(
            topic="Test",
            industry="test",
            total_slides=4,
            sections=[
                SectionPlan(
                    name="Test",
                    slide_count=4,
                    slide_types=[SlideType.CONTENT] * 4
                )
            ]
        )
        
        generated_slides = [
            {"type": "content", "slide_number": 1},
            {"type": "content", "slide_number": 2},
            {"type": "content", "slide_number": 3},
            {"type": "content", "slide_number": 4}
        ]
        
        is_valid, errors = agent.validate_final_presentation(plan, generated_slides)
        
        assert is_valid is False
        assert any("diversity violation" in e.lower() for e in errors)

    def test_required_sections_present(self, agent):
        """Test that all required consulting sections are present."""
        plan = agent.generate_presentation_plan("Test Topic", "general")
        
        section_names = [s.name for s in plan.sections]
        
        for required in agent.REQUIRED_SECTIONS:
            assert required in section_names

    def test_slide_type_to_visual_hint_mapping(self, agent):
        """Test slide type to visual hint mapping."""
        assert agent.TYPE_TO_VISUAL_HINT[SlideType.TITLE] == VisualHint.CENTERED
        assert agent.TYPE_TO_VISUAL_HINT[SlideType.CONTENT] == VisualHint.BULLET_LEFT
        assert agent.TYPE_TO_VISUAL_HINT[SlideType.CHART] == VisualHint.SPLIT_CHART_RIGHT
        assert agent.TYPE_TO_VISUAL_HINT[SlideType.TABLE] == VisualHint.SPLIT_TABLE_LEFT
        assert agent.TYPE_TO_VISUAL_HINT[SlideType.COMPARISON] == VisualHint.TWO_COLUMN
