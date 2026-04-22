"""
Tests for Storyboarding Agent LLM enhancements (Phase 3).

Tests the LLM-enhanced narrative optimization functionality including:
- Narrative arc optimization (problem → tension → resolution)
- Slide distribution optimization (more slides at tension peaks)
- Executive attention management
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.storyboarding import (
    StoryboardingAgent,
    PresentationPlanJSON,
    SectionPlan,
    SlideType,
    NarrativeOptimization,
)


@pytest.fixture
def storyboarding_agent():
    """Create a Storyboarding Agent instance."""
    return StoryboardingAgent()


@pytest.fixture
def initial_plan():
    """Sample initial presentation plan."""
    return PresentationPlanJSON(
        topic="Insurance Digital Transformation Strategy",
        industry="insurance",
        total_slides=12,
        sections=[
            SectionPlan(name="Title", slide_count=1, slide_types=[SlideType.TITLE]),
            SectionPlan(name="Agenda", slide_count=1, slide_types=[SlideType.CONTENT]),
            SectionPlan(name="Problem", slide_count=2, slide_types=[SlideType.CONTENT, SlideType.CHART]),
            SectionPlan(name="Analysis", slide_count=3, slide_types=[SlideType.CONTENT, SlideType.CHART, SlideType.TABLE]),
            SectionPlan(name="Evidence", slide_count=3, slide_types=[SlideType.CHART, SlideType.COMPARISON, SlideType.METRIC]),
            SectionPlan(name="Recommendations", slide_count=1, slide_types=[SlideType.CONTENT]),
            SectionPlan(name="Conclusion", slide_count=1, slide_types=[SlideType.CONTENT]),
        ]
    )


class TestNarrativeOptimization:
    """Test narrative optimization functionality."""
    
    @pytest.mark.asyncio
    async def test_optimize_narrative_success(
        self, storyboarding_agent, initial_plan
    ):
        """Test successful narrative optimization."""
        mock_optimization_result = {
            "optimized_sections": [
                {"name": "Title", "slide_count": 1, "types": ["title"]},
                {"name": "Agenda", "slide_count": 1, "types": ["content"]},
                {"name": "Problem", "slide_count": 1, "types": ["content"]},  # Compressed
                {"name": "Analysis", "slide_count": 4, "types": ["content", "chart", "table", "metric"]},  # Expanded
                {"name": "Evidence", "slide_count": 4, "types": ["chart", "comparison", "metric", "table"]},  # Expanded
                {"name": "Recommendations", "slide_count": 2, "types": ["content", "comparison"]},  # Expanded
                {"name": "Conclusion", "slide_count": 1, "types": ["content"]},
            ],
            "narrative_arc": "Problem (compressed) → Tension (Analysis + Evidence expanded) → Resolution (clear recommendations)",
            "attention_peaks": [5, 8, 11],
            "reasoning": "Executives already understand the problem. Focus on analysis and evidence to build case, then drive to action.",
        }
        
        with patch.object(
            storyboarding_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_optimization_result),
        ):
            result = await storyboarding_agent.optimize_narrative_with_llm(
                topic="Insurance Digital Transformation Strategy",
                industry="insurance",
                initial_plan=initial_plan,
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert result.total_slides == 14  # Optimized from 12
        assert len(result.sections) == 7
        
        # Check that Analysis and Evidence were expanded
        analysis_section = next(s for s in result.sections if s.name == "Analysis")
        assert analysis_section.slide_count == 4  # Expanded from 3
        
        evidence_section = next(s for s in result.sections if s.name == "Evidence")
        assert evidence_section.slide_count == 4  # Expanded from 3
        
        # Check that Problem was compressed
        problem_section = next(s for s in result.sections if s.name == "Problem")
        assert problem_section.slide_count == 1  # Compressed from 2
    
    @pytest.mark.asyncio
    async def test_optimize_narrative_maintains_bounds(
        self, storyboarding_agent, initial_plan
    ):
        """Test that optimization maintains slide count bounds (5-25)."""
        mock_optimization_result = {
            "optimized_sections": [
                {"name": "Title", "slide_count": 1, "types": ["title"]},
                {"name": "Agenda", "slide_count": 1, "types": ["content"]},
                {"name": "Problem", "slide_count": 2, "types": ["content", "chart"]},
                {"name": "Analysis", "slide_count": 5, "types": ["content", "chart", "table", "metric", "comparison"]},
                {"name": "Evidence", "slide_count": 4, "types": ["chart", "comparison", "metric", "table"]},
                {"name": "Recommendations", "slide_count": 2, "types": ["content", "comparison"]},
                {"name": "Conclusion", "slide_count": 1, "types": ["content"]},
            ],
            "narrative_arc": "Problem → Tension → Resolution",
            "attention_peaks": [6, 10, 14],
            "reasoning": "Balanced narrative with emphasis on analysis.",
        }
        
        with patch.object(
            storyboarding_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_optimization_result),
        ):
            result = await storyboarding_agent.optimize_narrative_with_llm(
                topic="Test Topic",
                industry="healthcare",
                initial_plan=initial_plan,
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert 5 <= result.total_slides <= 25
    
    @pytest.mark.asyncio
    async def test_optimize_narrative_fallback_on_error(
        self, storyboarding_agent, initial_plan
    ):
        """Test fallback when narrative optimization fails."""
        with patch.object(
            storyboarding_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError("LLM timeout")),
        ):
            result = await storyboarding_agent.optimize_narrative_with_llm(
                topic="Test Topic",
                industry="healthcare",
                initial_plan=initial_plan,
                execution_id="test-exec-123",
            )
        
        assert result is None  # Graceful fallback (caller uses initial_plan)
    
    @pytest.mark.asyncio
    async def test_optimize_narrative_enforces_visual_diversity(
        self, storyboarding_agent, initial_plan
    ):
        """Test that optimization enforces visual diversity."""
        # Mock result with potential diversity violations
        mock_optimization_result = {
            "optimized_sections": [
                {"name": "Title", "slide_count": 1, "types": ["title"]},
                {"name": "Agenda", "slide_count": 1, "types": ["content"]},
                {"name": "Analysis", "slide_count": 5, "types": ["chart", "chart", "chart", "chart", "chart"]},  # Violation
                {"name": "Recommendations", "slide_count": 1, "types": ["content"]},
                {"name": "Conclusion", "slide_count": 1, "types": ["content"]},
            ],
            "narrative_arc": "Problem → Tension → Resolution",
            "attention_peaks": [3, 5, 7],
            "reasoning": "Chart-heavy analysis.",
        }
        
        with patch.object(
            storyboarding_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_optimization_result),
        ):
            result = await storyboarding_agent.optimize_narrative_with_llm(
                topic="Test Topic",
                industry="finance",
                initial_plan=initial_plan,
                execution_id="test-exec-123",
            )
        
        assert result is not None
        
        # Check that visual diversity is enforced (no more than 2 consecutive same types)
        all_types = []
        for section in result.sections:
            all_types.extend(section.slide_types)
        
        consecutive_count = 1
        last_type = all_types[0] if all_types else None
        
        for i in range(1, len(all_types)):
            if all_types[i] == last_type:
                consecutive_count += 1
                assert consecutive_count <= 2, f"Found {consecutive_count} consecutive {last_type} slides"
            else:
                consecutive_count = 1
                last_type = all_types[i]


class TestNarrativeArc:
    """Test narrative arc optimization."""
    
    @pytest.mark.asyncio
    async def test_narrative_arc_problem_tension_resolution(
        self, storyboarding_agent, initial_plan
    ):
        """Test that narrative follows problem → tension → resolution arc."""
        mock_optimization_result = {
            "optimized_sections": [
                {"name": "Title", "slide_count": 1, "types": ["title"]},
                {"name": "Agenda", "slide_count": 1, "types": ["content"]},
                {"name": "Problem", "slide_count": 1, "types": ["content"]},
                {"name": "Analysis", "slide_count": 4, "types": ["content", "chart", "table", "metric"]},
                {"name": "Evidence", "slide_count": 3, "types": ["chart", "comparison", "metric"]},
                {"name": "Recommendations", "slide_count": 2, "types": ["content", "comparison"]},
                {"name": "Conclusion", "slide_count": 1, "types": ["content"]},
            ],
            "narrative_arc": "Problem (1 slide) → Tension (Analysis 4 + Evidence 3) → Resolution (Recommendations 2 + Conclusion 1)",
            "attention_peaks": [5, 8, 11],
            "reasoning": "Build tension with data, resolve with clear actions.",
        }
        
        with patch.object(
            storyboarding_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_optimization_result),
        ):
            result = await storyboarding_agent.optimize_narrative_with_llm(
                topic="Test Topic",
                industry="technology",
                initial_plan=initial_plan,
                execution_id="test-exec-123",
            )
        
        assert result is not None
        
        # Verify narrative arc structure
        section_names = [s.name for s in result.sections]
        
        # Problem should come early
        problem_index = section_names.index("Problem")
        assert problem_index <= 2
        
        # Analysis and Evidence should be in the middle (tension)
        analysis_index = section_names.index("Analysis")
        evidence_index = section_names.index("Evidence")
        assert analysis_index > problem_index
        assert evidence_index > problem_index
        
        # Recommendations and Conclusion should come last (resolution)
        recommendations_index = section_names.index("Recommendations")
        conclusion_index = section_names.index("Conclusion")
        assert recommendations_index > analysis_index
        assert recommendations_index > evidence_index
        assert conclusion_index == len(section_names) - 1


class TestAttentionManagement:
    """Test executive attention management."""
    
    @pytest.mark.asyncio
    async def test_attention_peaks_identified(
        self, storyboarding_agent, initial_plan
    ):
        """Test that attention peaks are identified."""
        mock_optimization_result = {
            "optimized_sections": [
                {"name": "Title", "slide_count": 1, "types": ["title"]},
                {"name": "Agenda", "slide_count": 1, "types": ["content"]},
                {"name": "Problem", "slide_count": 1, "types": ["content"]},
                {"name": "Analysis", "slide_count": 4, "types": ["content", "chart", "table", "metric"]},
                {"name": "Evidence", "slide_count": 3, "types": ["chart", "comparison", "metric"]},
                {"name": "Recommendations", "slide_count": 2, "types": ["content", "comparison"]},
                {"name": "Conclusion", "slide_count": 1, "types": ["content"]},
            ],
            "narrative_arc": "Problem → Tension → Resolution",
            "attention_peaks": [3, 6, 10],  # Key moments
            "reasoning": "Peak attention at problem statement, mid-analysis, and recommendations.",
        }
        
        with patch.object(
            storyboarding_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_optimization_result),
        ):
            result = await storyboarding_agent.optimize_narrative_with_llm(
                topic="Test Topic",
                industry="retail",
                initial_plan=initial_plan,
                execution_id="test-exec-123",
            )
        
        assert result is not None
        # Attention peaks are logged but not stored in plan
        # This test verifies the optimization runs successfully
