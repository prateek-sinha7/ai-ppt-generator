"""
Tests for Visual Refinement Agent.

Tests the LLM-enhanced visual polish functionality including:
- Icon selection (semantic matching)
- Highlight text generation (data-backed insights)
- Speaker notes generation (presenter-ready)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.visual_refinement import (
    VisualRefinementAgent,
    IconSelection,
    HighlightTextGeneration,
    SpeakerNotesGeneration,
)


@pytest.fixture
def visual_refinement_agent():
    """Create a Visual Refinement Agent instance."""
    return VisualRefinementAgent()


@pytest.fixture
def sample_slide():
    """Sample slide for testing."""
    return {
        "slide_id": "slide-1",
        "slide_number": 2,
        "type": "content",
        "title": "Market Consolidation Accelerates",
        "content": {
            "bullets": [
                "Top 3 players control 67% of revenue, up from 41% in 2022",
                "Mid-tier companies face margin pressure from scale disadvantages",
                "47 M&A transactions closed in 2025, up 89% year-over-year",
                "Digital-native players growing 3x faster than incumbents",
            ],
            "icon_name": "Users",  # Generic icon to be refined
        },
        "visual_hint": "bullet-left",
    }


@pytest.fixture
def sample_slides():
    """Sample presentation slides."""
    return [
        {
            "slide_id": "slide-1",
            "slide_number": 1,
            "type": "title",
            "title": "Healthcare Digital Transformation Strategy",
            "content": {"subtitle": "Q2 2026 Board Presentation"},
            "visual_hint": "centered",
        },
        {
            "slide_id": "slide-2",
            "slide_number": 2,
            "type": "content",
            "title": "Market Consolidation Accelerates",
            "content": {
                "bullets": [
                    "Top 3 players control 67% of revenue",
                    "Mid-tier companies face margin pressure",
                    "47 M&A transactions in 2025",
                ],
            },
            "visual_hint": "bullet-left",
        },
    ]


class TestIconSelection:
    """Test icon selection functionality."""
    
    @pytest.mark.asyncio
    async def test_select_optimal_icon_success(self, visual_refinement_agent, sample_slide):
        """Test successful icon selection."""
        # Mock LLM response
        mock_icon_result = {
            "icon_name": "Rocket",
            "reasoning": "Rocket represents growth and acceleration, matching the consolidation theme",
            "emotional_impact": "ambition and market momentum",
        }
        
        with patch.object(
            visual_refinement_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_icon_result),
        ):
            result = await visual_refinement_agent._select_optimal_icon(
                slide=sample_slide,
                industry="healthcare",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert result["icon_name"] == "Rocket"
        assert "growth" in result["reasoning"].lower()
        assert result["emotional_impact"] == "ambition and market momentum"
    
    @pytest.mark.asyncio
    async def test_select_optimal_icon_fallback_on_error(
        self, visual_refinement_agent, sample_slide
    ):
        """Test fallback when icon selection fails."""
        with patch.object(
            visual_refinement_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError("LLM timeout")),
        ):
            result = await visual_refinement_agent._select_optimal_icon(
                slide=sample_slide,
                industry="healthcare",
                execution_id="test-exec-123",
            )
        
        assert result is None  # Graceful fallback


class TestHighlightTextGeneration:
    """Test highlight text generation functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_highlight_text_success(
        self, visual_refinement_agent, sample_slide
    ):
        """Test successful highlight text generation."""
        mock_highlight_result = {
            "highlight_text": "Top 3 players control 67% of revenue — up from 41% in just 2 years",
            "key_metric": "67% market concentration",
            "impact": "Demonstrates rapid consolidation creating M&A opportunities",
        }
        
        with patch.object(
            visual_refinement_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_highlight_result),
        ):
            result = await visual_refinement_agent._generate_highlight_text(
                slide=sample_slide,
                industry="healthcare",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert "67%" in result["highlight_text"]
        assert len(result["highlight_text"]) <= 120  # Max length constraint
        assert result["key_metric"] == "67% market concentration"
    
    @pytest.mark.asyncio
    async def test_generate_highlight_text_no_bullets(self, visual_refinement_agent):
        """Test highlight text generation with no bullets."""
        slide_no_bullets = {
            "slide_id": "slide-1",
            "type": "content",
            "title": "Test Slide",
            "content": {},
        }
        
        result = await visual_refinement_agent._generate_highlight_text(
            slide=slide_no_bullets,
            industry="healthcare",
            execution_id="test-exec-123",
        )
        
        assert result is None  # Should return None for slides without bullets


class TestSpeakerNotesGeneration:
    """Test speaker notes generation functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_speaker_notes_success(
        self, visual_refinement_agent, sample_slide
    ):
        """Test successful speaker notes generation."""
        mock_notes_result = {
            "speaker_notes": "Emphasize the 67% market concentration — this is 26 points higher than 2022. Pause here to let the board absorb the consolidation speed. The key insight is that this creates a $2.4B M&A opportunity.",
            "emphasis_points": [
                "67% market concentration (up 26 points)",
                "$2.4B M&A opportunity",
            ],
            "transition_hint": "Transition to competitive implications on next slide",
        }
        
        with patch.object(
            visual_refinement_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(return_value=mock_notes_result),
        ):
            result = await visual_refinement_agent._generate_speaker_notes(
                slide=sample_slide,
                slide_index=1,
                total_slides=10,
                industry="healthcare",
                execution_id="test-exec-123",
            )
        
        assert result is not None
        assert "67%" in result["speaker_notes"]
        assert len(result["emphasis_points"]) >= 2
        assert "transition" in result["transition_hint"].lower()


class TestPresentationRefinement:
    """Test full presentation refinement."""
    
    @pytest.mark.asyncio
    async def test_refine_presentation_success(
        self, visual_refinement_agent, sample_slides
    ):
        """Test successful presentation refinement."""
        # Mock all LLM calls
        mock_icon = {"icon_name": "Rocket", "reasoning": "Growth theme", "emotional_impact": "ambition"}
        mock_highlight = {"highlight_text": "Top 3 players control 67% of revenue", "key_metric": "67%", "impact": "Consolidation"}
        mock_notes = {"speaker_notes": "Emphasize the key points.", "emphasis_points": ["Point 1"], "transition_hint": "Next slide"}
        
        with patch.object(
            visual_refinement_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(side_effect=[mock_icon, mock_highlight, mock_notes]),
        ):
            refined = await visual_refinement_agent.refine_presentation(
                slides=sample_slides,
                industry="healthcare",
                design_spec={"primary_color": "002F6C"},
                execution_id="test-exec-123",
            )
        
        assert len(refined) == len(sample_slides)
        # Title slide should be unchanged
        assert refined[0]["type"] == "title"
        # Content slide should be refined
        assert refined[1]["content"].get("icon_name") == "Rocket"
        assert refined[1]["content"].get("highlight_text") is not None
        assert refined[1]["content"].get("speaker_notes") is not None
    
    @pytest.mark.asyncio
    async def test_refine_presentation_partial_failure(
        self, visual_refinement_agent, sample_slides
    ):
        """Test presentation refinement with partial failures."""
        # Mock LLM calls with some failures
        with patch.object(
            visual_refinement_agent._llm_helper,
            "call_llm_with_retry",
            new=AsyncMock(side_effect=RuntimeError("LLM error")),
        ):
            refined = await visual_refinement_agent.refine_presentation(
                slides=sample_slides,
                industry="healthcare",
                design_spec=None,
                execution_id="test-exec-123",
            )
        
        # Should still return slides (graceful degradation)
        assert len(refined) == len(sample_slides)
        # Original slides should be preserved on error
        assert refined[0] == sample_slides[0]
        assert refined[1] == sample_slides[1]


class TestIconSemantics:
    """Test icon semantic mappings."""
    
    def test_icon_semantics_coverage(self, visual_refinement_agent):
        """Test that all common icons have semantic meanings."""
        required_icons = [
            "Shield", "Rocket", "Target", "Lightbulb", "TrendingUp",
            "Brain", "Fire", "Crown", "Zap", "Award", "Star",
        ]
        
        for icon in required_icons:
            assert icon in visual_refinement_agent.ICON_SEMANTICS
            assert len(visual_refinement_agent.ICON_SEMANTICS[icon]) > 20  # Meaningful description
    
    def test_icon_semantics_quality(self, visual_refinement_agent):
        """Test that icon semantics are descriptive."""
        for icon, meaning in visual_refinement_agent.ICON_SEMANTICS.items():
            # Should have multiple descriptive words
            words = meaning.split(",")
            assert len(words) >= 3, f"Icon {icon} needs more descriptive semantics"
            # Should not be empty
            assert all(word.strip() for word in words)
