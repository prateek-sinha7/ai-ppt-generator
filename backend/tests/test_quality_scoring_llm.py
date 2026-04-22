"""
Tests for Phase 4: Quality Scoring Agent LLM Recommendations.

Tests the LLM-powered specific, actionable recommendations feature.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.quality_scoring import (
    quality_scoring_agent,
    QualityScoreResult,
    LLMRecommendations,
)


@pytest.fixture
def sample_slides():
    """Sample slides for testing."""
    return [
        {
            "slide_id": "slide-1",
            "type": "title",
            "title": "Market Analysis",
            "content": {},
        },
        {
            "slide_id": "slide-2",
            "type": "content",
            "title": "Key Findings",
            "content": {
                "bullets": [
                    "Market growing",
                    "Competition increasing",
                ],
                "icon_name": "TrendingUp",
            },
        },
        {
            "slide_id": "slide-3",
            "type": "chart",
            "title": "Revenue Trends",
            "content": {
                "chart_type": "line",
                "chart_data": {
                    "labels": ["Category 1", "Category 2", "Category 3"],
                    "values": [100, 200, 150],
                },
            },
        },
    ]


@pytest.fixture
def mock_llm_recommendations():
    """Mock LLM recommendations response."""
    return {
        "content_improvements": [
            "Slide 2: Add specific market growth percentage (e.g., '23% YoY')",
            "Slide 2: Quantify 'competition increasing' with number of new entrants",
        ],
        "visual_improvements": [
            "Slide 2: Icon 'TrendingUp' is good but consider 'BarChart' for data focus",
        ],
        "data_improvements": [
            "Slide 3: Replace generic labels 'Category 1, 2, 3' with real segment names",
        ],
        "priority_fixes": [
            "1. Slide 3: Fix generic chart labels (critical for credibility)",
            "2. Slide 2: Add specific growth percentage (missing key data)",
            "3. Slide 2: Quantify competition claim (vague statement)",
        ],
    }


class TestLLMRecommendations:
    """Test LLM-powered recommendations generation."""
    
    @pytest.mark.asyncio
    async def test_generate_llm_recommendations_success(
        self, sample_slides, mock_llm_recommendations
    ):
        """Test successful LLM recommendations generation."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_llm_recommendations,
        ):
            # Generate dimension scores first
            dimension_scores = [
                quality_scoring_agent.score_content_depth(sample_slides),
                quality_scoring_agent.score_visual_appeal(sample_slides),
                quality_scoring_agent.score_structure_coherence(sample_slides),
                quality_scoring_agent.score_data_accuracy(sample_slides),
                quality_scoring_agent.score_clarity(sample_slides),
            ]
            
            result = await quality_scoring_agent.generate_llm_recommendations(
                slides=sample_slides,
                dimension_scores=dimension_scores,
                execution_id="test-exec-123",
            )
            
            assert "content_improvements" in result
            assert "visual_improvements" in result
            assert "data_improvements" in result
            assert "priority_fixes" in result
            
            assert len(result["content_improvements"]) == 2
            assert len(result["data_improvements"]) == 1
            assert len(result["priority_fixes"]) == 3
            
            # Verify slide numbers are referenced
            assert "Slide 2:" in result["content_improvements"][0]
            assert "Slide 3:" in result["data_improvements"][0]
    
    @pytest.mark.asyncio
    async def test_generate_llm_recommendations_graceful_degradation(
        self, sample_slides
    ):
        """Test graceful degradation when LLM fails."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ):
            dimension_scores = [
                quality_scoring_agent.score_content_depth(sample_slides),
            ]
            
            result = await quality_scoring_agent.generate_llm_recommendations(
                slides=sample_slides,
                dimension_scores=dimension_scores,
                execution_id="test-exec-123",
            )
            
            # Should return empty lists with fallback message
            assert result["content_improvements"] == []
            assert result["visual_improvements"] == []
            assert result["data_improvements"] == []
            assert "LLM recommendations unavailable" in result["priority_fixes"][0]
    
    @pytest.mark.asyncio
    async def test_generate_llm_recommendations_slide_summary(
        self, sample_slides, mock_llm_recommendations
    ):
        """Test that slide summary is correctly built for LLM."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_llm_recommendations,
        ) as mock_call:
            dimension_scores = [
                quality_scoring_agent.score_content_depth(sample_slides),
            ]
            
            await quality_scoring_agent.generate_llm_recommendations(
                slides=sample_slides,
                dimension_scores=dimension_scores,
                execution_id="test-exec-123",
            )
            
            # Verify the user prompt contains slide summaries
            call_args = mock_call.call_args
            user_prompt = call_args.kwargs["user_prompt"]
            
            assert "Slide 1 (title): 'Market Analysis'" in user_prompt
            assert "Slide 2 (content): 'Key Findings'" in user_prompt
            assert "2 bullets" in user_prompt
            assert "Icon: TrendingUp" in user_prompt
            assert "Slide 3 (chart): 'Revenue Trends'" in user_prompt
            assert "Chart: line" in user_prompt


class TestQualityScoringWithLLM:
    """Test quality scoring integration with LLM recommendations."""
    
    def test_score_presentation_with_llm_recommendations(
        self, sample_slides, mock_llm_recommendations
    ):
        """Test that score_presentation includes LLM recommendations."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_llm_recommendations,
        ):
            result = quality_scoring_agent.score_presentation(
                presentation_id="pres-123",
                slides=sample_slides,
                execution_id="exec-123",
                use_llm_recommendations=True,
            )
            
            assert isinstance(result, QualityScoreResult)
            assert result.composite_score > 0
            
            # Check that LLM recommendations are included
            assert "llm_content_improvements" in result.recommendations
            assert "llm_visual_improvements" in result.recommendations
            assert "llm_data_improvements" in result.recommendations
            assert "llm_priority_fixes" in result.recommendations
            
            assert len(result.recommendations["llm_content_improvements"]) == 2
            assert len(result.recommendations["llm_priority_fixes"]) == 3
    
    def test_score_presentation_without_llm_recommendations(self, sample_slides):
        """Test that score_presentation works without LLM recommendations."""
        result = quality_scoring_agent.score_presentation(
            presentation_id="pres-123",
            slides=sample_slides,
            execution_id="exec-123",
            use_llm_recommendations=False,
        )
        
        assert isinstance(result, QualityScoreResult)
        assert result.composite_score > 0
        
        # Check that LLM recommendations are NOT included
        assert "llm_content_improvements" not in result.recommendations
        assert "llm_visual_improvements" not in result.recommendations
        
        # But formula-based recommendations should still be there
        assert len(result.recommendations) > 0
    
    def test_score_presentation_without_execution_id(self, sample_slides):
        """Test that LLM recommendations are skipped without execution_id."""
        result = quality_scoring_agent.score_presentation(
            presentation_id="pres-123",
            slides=sample_slides,
            execution_id=None,
            use_llm_recommendations=True,
        )
        
        assert isinstance(result, QualityScoreResult)
        
        # LLM recommendations should be skipped
        assert "llm_content_improvements" not in result.recommendations
    
    def test_score_presentation_llm_failure_doesnt_break_scoring(
        self, sample_slides
    ):
        """Test that LLM failure doesn't break overall scoring."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM failed"),
        ):
            result = quality_scoring_agent.score_presentation(
                presentation_id="pres-123",
                slides=sample_slides,
                execution_id="exec-123",
                use_llm_recommendations=True,
            )
            
            # Scoring should still complete
            assert isinstance(result, QualityScoreResult)
            assert result.composite_score > 0
            
            # Formula-based recommendations should still be present
            assert len(result.recommendations) > 0


class TestLLMRecommendationQuality:
    """Test the quality and specificity of LLM recommendations."""
    
    @pytest.mark.asyncio
    async def test_recommendations_are_specific(
        self, sample_slides, mock_llm_recommendations
    ):
        """Test that recommendations reference specific slides."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_llm_recommendations,
        ):
            dimension_scores = [
                quality_scoring_agent.score_content_depth(sample_slides),
            ]
            
            result = await quality_scoring_agent.generate_llm_recommendations(
                slides=sample_slides,
                dimension_scores=dimension_scores,
                execution_id="test-exec-123",
            )
            
            # All recommendations should reference slide numbers
            all_recs = (
                result["content_improvements"]
                + result["visual_improvements"]
                + result["data_improvements"]
            )
            
            for rec in all_recs:
                assert "Slide" in rec, f"Recommendation missing slide reference: {rec}"
    
    @pytest.mark.asyncio
    async def test_priority_fixes_are_ranked(
        self, sample_slides, mock_llm_recommendations
    ):
        """Test that priority fixes are ranked."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_llm_recommendations,
        ):
            dimension_scores = [
                quality_scoring_agent.score_content_depth(sample_slides),
            ]
            
            result = await quality_scoring_agent.generate_llm_recommendations(
                slides=sample_slides,
                dimension_scores=dimension_scores,
                execution_id="test-exec-123",
            )
            
            priority_fixes = result["priority_fixes"]
            
            # Should have rankings
            assert priority_fixes[0].startswith("1.")
            assert priority_fixes[1].startswith("2.")
            assert priority_fixes[2].startswith("3.")


class TestCostTracking:
    """Test cost tracking for LLM recommendations."""
    
    def test_scoring_details_tracks_llm_usage(
        self, sample_slides, mock_llm_recommendations
    ):
        """Test that scoring details track whether LLM was used."""
        with patch.object(
            quality_scoring_agent,
            "call_llm_with_retry",
            new_callable=AsyncMock,
            return_value=mock_llm_recommendations,
        ):
            result = quality_scoring_agent.score_presentation(
                presentation_id="pres-123",
                slides=sample_slides,
                execution_id="exec-123",
                use_llm_recommendations=True,
            )
            
            assert result.scoring_details["llm_recommendations_used"] is True
    
    def test_scoring_details_tracks_no_llm_usage(self, sample_slides):
        """Test that scoring details track when LLM was not used."""
        result = quality_scoring_agent.score_presentation(
            presentation_id="pres-123",
            slides=sample_slides,
            execution_id="exec-123",
            use_llm_recommendations=False,
        )
        
        assert result.scoring_details["llm_recommendations_used"] is False
