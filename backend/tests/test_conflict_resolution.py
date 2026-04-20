"""
Unit tests for Conflict Resolution Engine.

Tests cover:
- Slide count enforcement
- Slide type enforcement
- Visual hint enforcement
- Section structure enforcement
- Narrative flow enforcement
- Conflict logging and reporting
"""

import pytest

from app.agents.conflict_resolution import (
    ConflictResolutionEngine,
    ConflictType,
    ConflictResolution
)


class TestConflictResolutionEngine:
    """Test suite for Conflict Resolution Engine."""

    @pytest.fixture
    def engine(self):
        """Create a Conflict Resolution Engine instance."""
        return ConflictResolutionEngine()

    @pytest.fixture
    def sample_plan(self):
        """Create a sample presentation plan."""
        return {
            "plan_id": "test-plan",
            "topic": "Test Topic",
            "industry": "test",
            "total_slides": 3,
            "sections": [
                {
                    "name": "Title",
                    "slide_count": 1,
                    "slide_types": ["title"]
                },
                {
                    "name": "Content",
                    "slide_count": 2,
                    "slide_types": ["content", "chart"]
                }
            ]
        }

    def test_enforce_slide_count_match(self, engine, sample_plan):
        """Test no conflict when slide count matches."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "title"},
                {"slide_id": "2", "type": "content"},
                {"slide_id": "3", "type": "chart"}
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        assert len(corrected["slides"]) == 3
        # Should have no slide count conflicts
        count_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SLIDE_COUNT_MISMATCH]
        assert len(count_conflicts) == 0

    def test_enforce_slide_count_too_many(self, engine, sample_plan):
        """Test enforcement when LLM generates too many slides."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "title"},
                {"slide_id": "2", "type": "content"},
                {"slide_id": "3", "type": "chart"},
                {"slide_id": "4", "type": "content"}  # Extra slide
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should truncate to 3 slides
        assert len(corrected["slides"]) == 3
        
        # Should log conflict
        count_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SLIDE_COUNT_MISMATCH]
        assert len(count_conflicts) == 1
        assert count_conflicts[0].storyboard_value == 3
        assert count_conflicts[0].llm_value == 4

    def test_enforce_slide_count_too_few(self, engine, sample_plan):
        """Test enforcement when LLM generates too few slides."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "title"},
                {"slide_id": "2", "type": "content"}
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should pad to 3 slides
        assert len(corrected["slides"]) == 3
        
        # Should log conflict
        count_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SLIDE_COUNT_MISMATCH]
        assert len(count_conflicts) == 1

    def test_enforce_slide_types(self, engine, sample_plan):
        """Test enforcement of slide types."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "title"},
                {"slide_id": "2", "type": "table"},  # Wrong type (should be content)
                {"slide_id": "3", "type": "chart"}
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should correct type
        assert corrected["slides"][1]["type"] == "content"
        
        # Should log conflict
        type_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SLIDE_TYPE_MISMATCH]
        assert len(type_conflicts) == 1
        assert type_conflicts[0].slide_index == 1

    def test_enforce_visual_hints(self, engine, sample_plan):
        """Test enforcement of visual hints based on slide types."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "title", "visual_hint": "bullet-left"},  # Wrong hint
                {"slide_id": "2", "type": "content", "visual_hint": "centered"},  # Wrong hint
                {"slide_id": "3", "type": "chart", "visual_hint": "two-column"}  # Wrong hint
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should correct visual hints
        assert corrected["slides"][0]["visual_hint"] == "centered"
        assert corrected["slides"][1]["visual_hint"] == "bullet-left"
        assert corrected["slides"][2]["visual_hint"] == "split-chart-right"
        
        # Should log conflicts
        hint_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.VISUAL_HINT_OVERRIDE]
        assert len(hint_conflicts) == 3

    def test_enforce_section_structure(self, engine, sample_plan):
        """Test enforcement of section structure."""
        llm_output = {
            "slides": [
                {
                    "slide_id": "1",
                    "type": "title",
                    "metadata": {"section": "WrongSection"}
                },
                {
                    "slide_id": "2",
                    "type": "content",
                    "metadata": {"section": "AnotherWrong"}
                },
                {
                    "slide_id": "3",
                    "type": "chart",
                    "metadata": {}
                }
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should correct sections
        assert corrected["slides"][0]["metadata"]["section"] == "Title"
        assert corrected["slides"][1]["metadata"]["section"] == "Content"
        assert corrected["slides"][2]["metadata"]["section"] == "Content"
        
        # Should log conflicts
        section_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SECTION_STRUCTURE_VIOLATION]
        assert len(section_conflicts) == 2

    def test_enforce_narrative_flow(self, engine, sample_plan):
        """Test enforcement of narrative flow (slide numbering)."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "title", "slide_number": 5},  # Wrong number
                {"slide_id": "2", "type": "content", "slide_number": 1},  # Wrong number
                {"slide_id": "3", "type": "chart", "slide_number": 3}  # Correct
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should correct slide numbers
        assert corrected["slides"][0]["slide_number"] == 1
        assert corrected["slides"][1]["slide_number"] == 2
        assert corrected["slides"][2]["slide_number"] == 3
        
        # Should log conflicts
        flow_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.NARRATIVE_FLOW_VIOLATION]
        assert len(flow_conflicts) == 2

    def test_no_conflicts_when_correct(self, engine, sample_plan):
        """Test no conflicts when LLM output is correct."""
        llm_output = {
            "slides": [
                {
                    "slide_id": "1",
                    "slide_number": 1,
                    "type": "title",
                    "visual_hint": "centered",
                    "metadata": {"section": "Title"}
                },
                {
                    "slide_id": "2",
                    "slide_number": 2,
                    "type": "content",
                    "visual_hint": "bullet-left",
                    "metadata": {"section": "Content"}
                },
                {
                    "slide_id": "3",
                    "slide_number": 3,
                    "type": "chart",
                    "visual_hint": "split-chart-right",
                    "metadata": {"section": "Content"}
                }
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        assert len(conflicts) == 0
        assert engine.has_conflicts() is False

    def test_conflict_summary(self, engine, sample_plan):
        """Test conflict summary generation."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "content", "visual_hint": "centered"},  # Type + hint wrong
                {"slide_id": "2", "type": "content", "visual_hint": "bullet-left"},
                {"slide_id": "3", "type": "chart", "visual_hint": "split-chart-right"}
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        summary = engine.get_conflict_summary()
        
        assert summary["total_conflicts"] > 0
        assert "conflicts_by_type" in summary
        assert "all_conflicts" in summary
        assert len(summary["all_conflicts"]) == len(conflicts)

    def test_has_conflicts_method(self, engine, sample_plan):
        """Test has_conflicts method."""
        # No conflicts
        llm_output_correct = {
            "slides": [
                {"slide_id": "1", "type": "title", "visual_hint": "centered"},
                {"slide_id": "2", "type": "content", "visual_hint": "bullet-left"},
                {"slide_id": "3", "type": "chart", "visual_hint": "split-chart-right"}
            ]
        }
        
        engine_no_conflict = ConflictResolutionEngine()
        engine_no_conflict.validate_and_resolve(sample_plan, llm_output_correct)
        assert engine_no_conflict.has_conflicts() is False
        
        # With conflicts
        llm_output_wrong = {
            "slides": [
                {"slide_id": "1", "type": "content"},  # Wrong type
                {"slide_id": "2", "type": "content"},
                {"slide_id": "3", "type": "chart"}
            ]
        }
        
        engine_with_conflict = ConflictResolutionEngine()
        engine_with_conflict.validate_and_resolve(sample_plan, llm_output_wrong)
        assert engine_with_conflict.has_conflicts() is True

    def test_multiple_conflict_types_same_slide(self, engine, sample_plan):
        """Test handling multiple conflict types on same slide."""
        llm_output = {
            "slides": [
                {
                    "slide_id": "1",
                    "slide_number": 5,  # Wrong number
                    "type": "content",  # Wrong type (should be title)
                    "visual_hint": "bullet-left",  # Wrong hint (should be centered)
                    "metadata": {"section": "Wrong"}  # Wrong section
                },
                {"slide_id": "2", "type": "content"},
                {"slide_id": "3", "type": "chart"}
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # Should have multiple conflicts for slide 0
        slide_0_conflicts = [c for c in conflicts if c.slide_index == 0]
        assert len(slide_0_conflicts) >= 3  # Type, hint, section

    def test_conflict_resolution_enum(self, engine, sample_plan):
        """Test that all conflicts use ENFORCE_STORYBOARD resolution."""
        llm_output = {
            "slides": [
                {"slide_id": "1", "type": "content"},  # Wrong
                {"slide_id": "2", "type": "table"},  # Wrong
                {"slide_id": "3", "type": "comparison"}  # Wrong
            ]
        }
        
        corrected, conflicts = engine.validate_and_resolve(sample_plan, llm_output)
        
        # All conflicts should use ENFORCE_STORYBOARD resolution
        for conflict in conflicts:
            assert conflict.resolution == ConflictResolution.ENFORCE_STORYBOARD
