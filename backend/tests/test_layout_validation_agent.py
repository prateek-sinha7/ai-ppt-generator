"""
Tests for Layout Validation Agent.

Tests cover:
- Title length validation and correction
- Bullet count and length validation
- Chart data size validation
- Chart type validation
- Content overflow detection
- Layout correction application
"""

import pytest
from app.agents.layout_validation import (
    LayoutValidationAgent,
    LayoutIssue,
    LayoutIssueType,
    LayoutValidationResult
)


class TestLayoutValidationAgent:
    """Tests for LayoutValidationAgent."""

    @pytest.fixture
    def agent(self):
        """Create a LayoutValidationAgent instance."""
        return LayoutValidationAgent()

    def test_valid_slide_passes_validation(self, agent):
        """Test that a properly formatted slide passes validation."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "Short Title Here",  # 3 words, under limit
            "content": {
                "bullets": [
                    "First bullet point here",  # 4 words, under limit
                    "Second bullet point",      # 3 words, under limit
                    "Third bullet point"        # 3 words, under limit
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert result.is_valid
        assert len(result.issues) == 0
        assert result.corrections_applied == 0

    def test_title_too_long_detected(self, agent):
        """Test detection of titles that are too long."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "This is a very long title that exceeds the maximum word limit",  # 12 words
            "content": {}
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == LayoutIssueType.TITLE_TOO_LONG
        assert "12 words" in result.issues[0].description

    def test_title_too_long_corrected(self, agent):
        """Test automatic correction of titles that are too long."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "This is a very long title that exceeds the maximum word limit",
            "content": {}
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=True)
        
        assert result.corrections_applied == 1
        assert result.corrected_slides is not None
        corrected_title = result.corrected_slides[0]["title"]
        assert len(corrected_title.split()) == agent.MAX_TITLE_WORDS
        # Check that it's truncated to first 8 words
        expected_title = "This is a very long title that exceeds"
        assert corrected_title == expected_title

    def test_too_many_bullets_detected(self, agent):
        """Test detection of slides with too many bullets."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "Test Title",
            "content": {
                "bullets": [
                    "First bullet",
                    "Second bullet", 
                    "Third bullet",
                    "Fourth bullet",
                    "Fifth bullet",  # Exceeds limit of 4
                    "Sixth bullet"
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == LayoutIssueType.TOO_MANY_BULLETS
        assert "6 bullets" in result.issues[0].description

    def test_too_many_bullets_corrected(self, agent):
        """Test automatic correction of slides with too many bullets."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "Test Title",
            "content": {
                "bullets": [
                    "First bullet",
                    "Second bullet", 
                    "Third bullet",
                    "Fourth bullet",
                    "Fifth bullet",
                    "Sixth bullet"
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=True)
        
        assert result.corrections_applied == 1
        assert result.corrected_slides is not None
        corrected_bullets = result.corrected_slides[0]["content"]["bullets"]
        assert len(corrected_bullets) == agent.MAX_BULLETS_PER_SLIDE

    def test_bullet_too_long_detected(self, agent):
        """Test detection of bullets that are too long."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "Test Title",
            "content": {
                "bullets": [
                    "This is a very long bullet point that exceeds the maximum word limit for bullets"  # 15 words
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == LayoutIssueType.BULLET_TOO_LONG
        assert "15 words" in result.issues[0].description

    def test_bullet_too_long_corrected(self, agent):
        """Test automatic correction of bullets that are too long."""
        slides = [{
            "slide_number": 1,
            "type": "content", 
            "title": "Test Title",
            "content": {
                "bullets": [
                    "This is a very long bullet point that exceeds the maximum word limit for bullets"
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=True)
        
        assert result.corrections_applied == 1
        assert result.corrected_slides is not None
        corrected_bullet = result.corrected_slides[0]["content"]["bullets"][0]
        assert len(corrected_bullet.split()) == agent.MAX_WORDS_PER_BULLET
        # Check that it's truncated to first 8 words
        expected_bullet = "This is a very long bullet point that"
        assert corrected_bullet == expected_bullet

    def test_chart_data_overflow_detected(self, agent):
        """Test detection of charts with too many data points."""
        slides = [{
            "slide_number": 1,
            "type": "chart",
            "title": "Chart Title",
            "content": {
                "chart_type": "bar",
                "chart_data": [
                    {"label": f"Item {i}", "value": i * 10} 
                    for i in range(1, 12)  # 11 data points, exceeds limit of 8
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == LayoutIssueType.CHART_DATA_OVERFLOW
        assert "11 data points" in result.issues[0].description

    def test_chart_data_overflow_corrected(self, agent):
        """Test automatic correction of charts with too many data points."""
        slides = [{
            "slide_number": 1,
            "type": "chart",
            "title": "Chart Title",
            "content": {
                "chart_type": "bar",
                "chart_data": [
                    {"label": f"Item {i}", "value": i * 10} 
                    for i in range(1, 12)  # 11 data points
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=True)
        
        assert result.corrections_applied == 1
        assert result.corrected_slides is not None
        corrected_data = result.corrected_slides[0]["content"]["chart_data"]
        assert len(corrected_data) == agent.MAX_CHART_DATA_POINTS

    def test_invalid_chart_type_detected(self, agent):
        """Test detection of invalid chart types."""
        slides = [{
            "slide_number": 1,
            "type": "chart",
            "title": "Chart Title",
            "content": {
                "chart_type": "scatter",  # Not in valid types (bar, line, pie)
                "chart_data": [
                    {"label": "A", "value": 10},
                    {"label": "B", "value": 20},
                    {"label": "C", "value": 30}  # Add third data point to avoid min data issue
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == LayoutIssueType.INVALID_CHART_TYPE
        assert "scatter" in result.issues[0].description

    def test_invalid_chart_type_corrected(self, agent):
        """Test automatic correction of invalid chart types."""
        slides = [{
            "slide_number": 1,
            "type": "chart",
            "title": "Chart Title",
            "content": {
                "chart_type": "scatter",
                "chart_data": [
                    {"label": "A", "value": 10},
                    {"label": "B", "value": 20}
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=True)
        
        assert result.corrections_applied == 1
        assert result.corrected_slides is not None
        corrected_type = result.corrected_slides[0]["content"]["chart_type"]
        assert corrected_type == "bar"  # Default fallback

    def test_missing_chart_data_detected(self, agent):
        """Test detection of chart slides missing chart data."""
        slides = [{
            "slide_number": 1,
            "type": "chart",
            "title": "Chart Title",
            "content": {
                "chart_type": "bar"
                # Missing chart_data
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 2  # Missing chart_data + insufficient data points
        # Check that we have both missing content and data overflow issues
        issue_types = [issue.issue_type for issue in result.issues]
        assert LayoutIssueType.MISSING_REQUIRED_CONTENT in issue_types
        assert LayoutIssueType.CHART_DATA_OVERFLOW in issue_types

    def test_multiple_issues_detected(self, agent):
        """Test detection of multiple layout issues in one slide."""
        slides = [{
            "slide_number": 1,
            "type": "content",
            "title": "This is a very long title that exceeds the maximum word limit",  # Too long
            "content": {
                "bullets": [
                    "First bullet point here",
                    "Second bullet point here", 
                    "Third bullet point here",
                    "Fourth bullet point here",
                    "Fifth bullet point here",  # Too many bullets
                    "This is a very long bullet point that exceeds the maximum word limit"  # Too long
                ]
            }
        }]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 3  # Title too long, too many bullets, bullet too long

    def test_multiple_slides_validation(self, agent):
        """Test validation across multiple slides."""
        slides = [
            {
                "slide_number": 1,
                "type": "title",
                "title": "Valid Title",
                "content": {}
            },
            {
                "slide_number": 2,
                "type": "content",
                "title": "This title is way too long and exceeds limits",
                "content": {"bullets": ["Valid bullet"]}
            },
            {
                "slide_number": 3,
                "type": "chart",
                "title": "Chart Title",
                "content": {
                    "chart_type": "invalid_type",
                    "chart_data": [
                        {"label": "A", "value": 10},
                        {"label": "B", "value": 20},
                        {"label": "C", "value": 30}  # Add third data point to avoid min data issue
                    ]
                }
            }
        ]
        
        result = agent.validate_layout(slides, "test-exec", apply_corrections=False)
        
        assert not result.is_valid
        assert len(result.issues) == 2  # Title too long on slide 2, invalid chart type on slide 3
        
        # Check slide numbers are correct
        slide_numbers = [issue.slide_number for issue in result.issues]
        assert 2 in slide_numbers
        assert 3 in slide_numbers