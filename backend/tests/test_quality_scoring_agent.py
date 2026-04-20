"""
Tests for Quality Scoring Agent.

Tests cover:
- 5-dimension scoring (content depth, visual appeal, structure coherence, data accuracy, clarity)
- Composite score calculation as weighted average
- Whitespace ratio and content density scoring
- Narrative coherence validation
- Improvement recommendations
- Feedback loop triggering
"""

import pytest
from app.agents.quality_scoring import (
    QualityScoringAgent,
    ScoreDimension,
    WEIGHT_CONTENT_DEPTH,
    WEIGHT_VISUAL_APPEAL,
    WEIGHT_STRUCTURE_COHERENCE,
    WEIGHT_DATA_ACCURACY,
    WEIGHT_CLARITY,
    QUALITY_THRESHOLD_FEEDBACK_LOOP,
    MAX_FEEDBACK_RETRIES,
)


@pytest.fixture
def agent():
    """Create quality scoring agent instance."""
    return QualityScoringAgent()


@pytest.fixture
def high_quality_slides():
    """High-quality presentation slides."""
    return [
        {
            "slide_id": "1",
            "type": "title",
            "title": "Healthcare Digital Transformation",
            "content": {},
            "visual_hint": "centered"
        },
        {
            "slide_id": "2",
            "type": "content",
            "title": "Agenda Overview",
            "content": {
                "bullets": [
                    "Current challenges",
                    "Market analysis",
                    "Strategic recommendations"
                ],
                "icon_name": "list"
            },
            "visual_hint": "bullet-left",
            "layout_constraints": {
                "max_content_density": 0.75,
                "min_whitespace_ratio": 0.25
            }
        },
        {
            "slide_id": "3",
            "type": "content",
            "title": "Problem Statement",
            "content": {
                "bullets": [
                    "Legacy systems limit growth",
                    "Patient data fragmented"
                ]
            },
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "4",
            "type": "chart",
            "title": "Market Analysis",
            "content": {
                "chart_data": {
                    "chart_type": "line",
                    "data": [{"year": 2021, "value": 100}]
                }
            },
            "visual_hint": "split-chart-right"
        },
        {
            "slide_id": "5",
            "type": "table",
            "title": "Evidence Data",
            "content": {
                "table_data": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Efficiency", "90%"]]
                }
            },
            "visual_hint": "split-table-left"
        },
        {
            "slide_id": "6",
            "type": "comparison",
            "title": "Recommendations",
            "content": {
                "comparison_data": {
                    "left": {"title": "Option A", "points": ["Fast"]},
                    "right": {"title": "Option B", "points": ["Comprehensive"]}
                }
            },
            "visual_hint": "two-column"
        },
        {
            "slide_id": "7",
            "type": "content",
            "title": "Conclusion",
            "content": {
                "bullets": ["Begin pilot", "Launch Q2"],
                "highlight_text": "ROI: 250%"
            },
            "visual_hint": "bullet-left"
        }
    ]


@pytest.fixture
def low_quality_slides():
    """Low-quality presentation slides."""
    return [
        {
            "slide_id": "1",
            "type": "content",  # Should be title
            "title": "This is a very long title that exceeds the maximum word count",
            "content": {
                "bullets": [
                    "This is a very long bullet point that exceeds the maximum",
                    "Another long bullet",
                    "Third bullet",
                    "Fourth bullet",
                    "Fifth bullet - too many!"
                ]
            },
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "2",
            "type": "content",
            "title": "More Content",
            "content": {"bullets": []},  # Empty
            "visual_hint": "bullet-left"
        },
        {
            "slide_id": "3",
            "type": "chart",
            "title": "Chart",
            "content": {},  # Missing chart_data
            "visual_hint": "split-chart-right"
        }
    ]


class TestContentDepthScoring:
    """Tests for content depth dimension (25% weight)."""
    
    def test_high_content_depth(self, agent, high_quality_slides):
        """Test scoring of high content depth."""
        score = agent.score_content_depth(high_quality_slides)
        
        assert score.dimension == ScoreDimension.CONTENT_DEPTH
        assert score.weight == WEIGHT_CONTENT_DEPTH
        assert score.score >= 8.0
        assert score.weighted_score == score.score * WEIGHT_CONTENT_DEPTH
    
    def test_low_content_depth(self, agent, low_quality_slides):
        """Test scoring of low content depth."""
        score = agent.score_content_depth(low_quality_slides)
        
        assert score.score < 8.0
        assert len(score.recommendations) > 0
        assert score.details["empty_content_slides"] > 0
    
    def test_content_ratio_penalty(self, agent):
        """Test penalty for low content slide ratio."""
        slides = [
            {"type": "title", "title": "Title", "content": {}},
            {"type": "title", "title": "Another", "content": {}},
        ]
        
        score = agent.score_content_depth(slides)
        assert score.score < 10.0
        assert any("content slides" in rec.lower() for rec in score.recommendations)


class TestVisualAppealScoring:
    """Tests for visual appeal dimension (20% weight)."""
    
    def test_high_visual_appeal(self, agent, high_quality_slides):
        """Test scoring of high visual appeal."""
        score = agent.score_visual_appeal(high_quality_slides)
        
        assert score.dimension == ScoreDimension.VISUAL_APPEAL
        assert score.weight == WEIGHT_VISUAL_APPEAL
        assert score.score >= 8.0
        assert score.details["unique_slide_types"] >= 4
    
    def test_low_visual_diversity(self, agent):
        """Test penalty for low visual diversity."""
        slides = [
            {"type": "content", "title": "Slide 1", "content": {"bullets": []}},
            {"type": "content", "title": "Slide 2", "content": {"bullets": []}},
            {"type": "content", "title": "Slide 3", "content": {"bullets": []}},
        ]
        
        score = agent.score_visual_appeal(slides)
        assert score.score < 10.0
        assert any("diversity" in rec.lower() for rec in score.recommendations)
    
    def test_consecutive_same_type_penalty(self, agent):
        """Test penalty for >2 consecutive same-type slides."""
        slides = [
            {"type": "content", "title": "1", "content": {"bullets": []}},
            {"type": "content", "title": "2", "content": {"bullets": []}},
            {"type": "content", "title": "3", "content": {"bullets": []}},
            {"type": "content", "title": "4", "content": {"bullets": []}},
        ]
        
        score = agent.score_visual_appeal(slides)
        assert score.details["max_consecutive_same_type"] > 2
        assert any("consecutive" in rec.lower() for rec in score.recommendations)
    
    def test_whitespace_density_scoring(self, agent):
        """Test whitespace and density scoring."""
        slides = [
            {
                "type": "content",
                "title": "Crowded",
                "content": {
                    "bullets": ["1", "2", "3", "4", "5"]  # Too many
                },
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                }
            }
        ]
        
        score = agent.score_visual_appeal(slides)
        assert score.details["density_violations"] > 0


class TestStructureCoherenceScoring:
    """Tests for structure coherence dimension (25% weight)."""
    
    def test_high_structure_coherence(self, agent, high_quality_slides):
        """Test scoring of high structure coherence."""
        score = agent.score_structure_coherence(high_quality_slides)
        
        assert score.dimension == ScoreDimension.STRUCTURE_COHERENCE
        assert score.weight == WEIGHT_STRUCTURE_COHERENCE
        assert score.score >= 7.0  # May not be perfect
    
    def test_missing_sections_penalty(self, agent):
        """Test penalty for missing required sections."""
        slides = [
            {"type": "title", "title": "Title", "content": {}},
            {"type": "content", "title": "Content", "content": {"bullets": []}}
        ]
        
        score = agent.score_structure_coherence(slides)
        assert len(score.details["missing_sections"]) > 0
        assert score.score < 10.0
        assert any("missing sections" in rec.lower() for rec in score.recommendations)
    
    def test_section_order_validation(self, agent):
        """Test validation of consulting storytelling structure order."""
        slides = [
            {"type": "title", "title": "Title", "content": {}},
            {"type": "content", "title": "Conclusion", "content": {"bullets": []}},
            {"type": "content", "title": "Problem", "content": {"bullets": []}},
        ]
        
        score = agent.score_structure_coherence(slides)
        # Conclusion before Problem is out of order
        assert score.details["order_violations"] > 0
    
    def test_first_slide_should_be_title(self, agent):
        """Test penalty if first slide is not title type."""
        slides = [
            {"type": "content", "title": "Not Title", "content": {"bullets": []}}
        ]
        
        score = agent.score_structure_coherence(slides)
        assert any("first slide" in rec.lower() for rec in score.recommendations)


class TestDataAccuracyScoring:
    """Tests for data accuracy dimension (15% weight)."""
    
    def test_high_data_accuracy(self, agent, high_quality_slides):
        """Test scoring of high data accuracy."""
        score = agent.score_data_accuracy(high_quality_slides)
        
        assert score.dimension == ScoreDimension.DATA_ACCURACY
        assert score.weight == WEIGHT_DATA_ACCURACY
        assert score.score >= 9.0
    
    def test_missing_chart_data_penalty(self, agent):
        """Test penalty for chart slides without chart_data."""
        slides = [
            {"type": "chart", "title": "Chart", "content": {}}  # Missing chart_data
        ]
        
        score = agent.score_data_accuracy(slides)
        assert score.details["charts_with_data"] == 0
        assert score.score < 10.0
        assert any("chart data" in rec.lower() for rec in score.recommendations)
    
    def test_missing_table_data_penalty(self, agent):
        """Test penalty for table slides without table_data."""
        slides = [
            {"type": "table", "title": "Table", "content": {}}  # Missing table_data
        ]
        
        score = agent.score_data_accuracy(slides)
        assert score.details["tables_with_data"] == 0
        assert score.score < 10.0
    
    def test_missing_comparison_data_penalty(self, agent):
        """Test penalty for comparison slides without comparison_data."""
        slides = [
            {"type": "comparison", "title": "Compare", "content": {}}
        ]
        
        score = agent.score_data_accuracy(slides)
        assert score.details["comparisons_with_data"] == 0
        assert score.score < 10.0


class TestClarityScoring:
    """Tests for clarity dimension (15% weight)."""
    
    def test_high_clarity(self, agent, high_quality_slides):
        """Test scoring of high clarity."""
        score = agent.score_clarity(high_quality_slides)
        
        assert score.dimension == ScoreDimension.CLARITY
        assert score.weight == WEIGHT_CLARITY
        assert score.score >= 8.0
    
    def test_long_title_penalty(self, agent):
        """Test penalty for titles exceeding max words."""
        slides = [
            {
                "type": "content",
                "title": "This is a very long title that exceeds the maximum word count",
                "content": {"bullets": []}
            }
        ]
        
        score = agent.score_clarity(slides)
        assert score.details["long_titles"] > 0
        assert any("shorten" in rec.lower() and "title" in rec.lower() 
                   for rec in score.recommendations)
    
    def test_too_many_bullets_penalty(self, agent):
        """Test penalty for slides with >4 bullets."""
        slides = [
            {
                "type": "content",
                "title": "Content",
                "content": {
                    "bullets": ["1", "2", "3", "4", "5", "6"]  # Too many
                }
            }
        ]
        
        score = agent.score_clarity(slides)
        assert score.details["slides_with_too_many_bullets"] > 0
        assert any("bullet count" in rec.lower() for rec in score.recommendations)
    
    def test_long_bullet_penalty(self, agent):
        """Test penalty for bullets exceeding max words."""
        slides = [
            {
                "type": "content",
                "title": "Content",
                "content": {
                    "bullets": [
                        "This is a very long bullet point that exceeds the maximum word count"
                    ]
                }
            }
        ]
        
        score = agent.score_clarity(slides)
        assert score.details["long_bullets"] > 0


class TestCompositeScoreCalculation:
    """Tests for composite score calculation."""
    
    def test_weighted_average_calculation(self, agent, high_quality_slides):
        """Test composite score is correct weighted average."""
        result = agent.score_presentation("pres-1", high_quality_slides)
        
        # Calculate expected composite
        expected = (
            result.content_depth * WEIGHT_CONTENT_DEPTH +
            result.visual_appeal * WEIGHT_VISUAL_APPEAL +
            result.structure_coherence * WEIGHT_STRUCTURE_COHERENCE +
            result.data_accuracy * WEIGHT_DATA_ACCURACY +
            result.clarity * WEIGHT_CLARITY
        )
        
        assert abs(result.composite_score - expected) < 0.01
    
    def test_composite_score_bounds(self, agent, high_quality_slides):
        """Test composite score stays within 1-10 bounds."""
        result = agent.score_presentation("pres-1", high_quality_slides)
        
        assert 1.0 <= result.composite_score <= 10.0
    
    def test_weights_sum_to_one(self, agent):
        """Test dimension weights sum to 1.0."""
        total_weight = sum(agent.dimension_weights.values())
        assert abs(total_weight - 1.0) < 0.001


class TestRecommendations:
    """Tests for improvement recommendations."""
    
    def test_recommendations_per_dimension(self, agent, low_quality_slides):
        """Test recommendations are generated per dimension."""
        result = agent.score_presentation("pres-1", low_quality_slides)
        
        assert len(result.recommendations) > 0
        
        # Check recommendations are keyed by dimension
        for dimension_key in result.recommendations.keys():
            assert dimension_key in [d.value for d in ScoreDimension]
    
    def test_no_recommendations_for_high_quality(self, agent, high_quality_slides):
        """Test minimal/no recommendations for high-quality presentations."""
        result = agent.score_presentation("pres-1", high_quality_slides)
        
        # High quality should have few or no recommendations
        total_recs = sum(len(recs) for recs in result.recommendations.values())
        assert total_recs <= 3  # Allow minor suggestions
    
    def test_actionable_recommendations(self, agent, low_quality_slides):
        """Test recommendations are actionable and specific."""
        result = agent.score_presentation("pres-1", low_quality_slides)
        
        for dimension, recs in result.recommendations.items():
            for rec in recs:
                # Recommendations should be non-empty strings
                assert isinstance(rec, str)
                assert len(rec) > 10  # Meaningful length


class TestFeedbackLoopTrigger:
    """Tests for feedback loop triggering."""
    
    def test_feedback_loop_triggered_below_threshold(self, agent, low_quality_slides):
        """Test feedback loop triggers when score < 8."""
        result = agent.score_presentation("pres-1", low_quality_slides, retry_count=0)
        
        if result.composite_score < QUALITY_THRESHOLD_FEEDBACK_LOOP:
            assert result.requires_feedback_loop is True
    
    def test_feedback_loop_not_triggered_above_threshold(self, agent, high_quality_slides):
        """Test feedback loop doesn't trigger when score >= 8."""
        result = agent.score_presentation("pres-1", high_quality_slides, retry_count=0)
        
        if result.composite_score >= QUALITY_THRESHOLD_FEEDBACK_LOOP:
            assert result.requires_feedback_loop is False
    
    def test_feedback_loop_max_retries(self, agent, low_quality_slides):
        """Test feedback loop stops after max retries."""
        # Retry count at max
        result = agent.score_presentation(
            "pres-1",
            low_quality_slides,
            retry_count=MAX_FEEDBACK_RETRIES
        )
        
        # Should not trigger even if score is low
        assert result.requires_feedback_loop is False
    
    def test_feedback_loop_retry_progression(self, agent, low_quality_slides):
        """Test feedback loop behavior across retries."""
        for retry in range(MAX_FEEDBACK_RETRIES + 1):
            result = agent.score_presentation(
                "pres-1",
                low_quality_slides,
                retry_count=retry
            )
            
            if retry < MAX_FEEDBACK_RETRIES and result.composite_score < QUALITY_THRESHOLD_FEEDBACK_LOOP:
                assert result.requires_feedback_loop is True
            elif retry >= MAX_FEEDBACK_RETRIES:
                assert result.requires_feedback_loop is False


class TestScoringDetails:
    """Tests for scoring details and metadata."""
    
    def test_scoring_details_structure(self, agent, high_quality_slides):
        """Test scoring details contain all required information."""
        result = agent.score_presentation("pres-1", high_quality_slides)
        
        assert "dimensions" in result.scoring_details
        assert "retry_count" in result.scoring_details
        assert "max_retries" in result.scoring_details
        assert "threshold" in result.scoring_details
        
        # Check each dimension has details
        for dimension in ScoreDimension:
            assert dimension.value in result.scoring_details["dimensions"]
            dim_details = result.scoring_details["dimensions"][dimension.value]
            assert "score" in dim_details
            assert "weight" in dim_details
            assert "weighted_score" in dim_details
            assert "details" in dim_details
    
    def test_result_to_dict(self, agent, high_quality_slides):
        """Test QualityScoreResult can be converted to dict."""
        result = agent.score_presentation("pres-1", high_quality_slides)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert "score_id" in result_dict
        assert "presentation_id" in result_dict
        assert "composite_score" in result_dict
        assert "recommendations" in result_dict
        assert "requires_feedback_loop" in result_dict


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_slides_list(self, agent):
        """Test handling of empty slides list."""
        result = agent.score_presentation("pres-1", [])
        
        # Should not crash, should return low scores
        assert 1.0 <= result.composite_score <= 10.0
    
    def test_single_slide_presentation(self, agent):
        """Test handling of single-slide presentation."""
        slides = [
            {"type": "title", "title": "Only Slide", "content": {}}
        ]
        
        result = agent.score_presentation("pres-1", slides)
        
        assert result.composite_score < 8.0  # Should be low quality
        assert result.requires_feedback_loop is True
    
    def test_missing_optional_fields(self, agent):
        """Test handling of slides with missing optional fields."""
        slides = [
            {
                "type": "content",
                "title": "Minimal Slide",
                "content": {}  # No bullets, no data
            }
        ]
        
        result = agent.score_presentation("pres-1", slides)
        
        # Should not crash
        assert isinstance(result.composite_score, float)
