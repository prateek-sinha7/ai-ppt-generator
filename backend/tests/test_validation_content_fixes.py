"""
Tests for validation agent content fixes (minimum bullets and content density).

Tests the fixes for:
1. Single-bullet slides (should have minimum 2 bullets)
2. Content overflow (should enforce content density limits)
"""

import pytest
from app.agents.validation import validation_agent, MIN_BULLETS, MAX_CONTENT_DENSITY


class TestMinimumBulletValidation:
    """Test minimum bullet count enforcement."""
    
    def test_single_bullet_gets_expanded(self):
        """Content slide with 1 bullet should be expanded to MIN_BULLETS."""
        data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 2,
            "slides": [
                {
                    "slide_id": "slide-0",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Presentation Title",
                    "content": {
                        "subtitle": "Test Presentation"
                    },
                    "visual_hint": "centered"
                },
                {
                    "slide_id": "slide-1",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Test Slide",
                    "content": {
                        "bullets": ["Only one bullet point"]
                    },
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = validation_agent.validate(data, execution_id="test-min-bullets", apply_corrections=True)
        
        assert result.is_valid
        assert result.corrections_applied > 0
        
        # Check that bullets were expanded (slide 1 is the content slide, not slide 0 which is title)
        corrected_slide = result.corrected_data["slides"][1]
        bullets = corrected_slide["content"]["bullets"]
        assert len(bullets) >= MIN_BULLETS, f"Expected at least {MIN_BULLETS} bullets, got {len(bullets)}"
    
    def test_zero_bullets_gets_generated(self):
        """Content slide with no bullets should get generated bullets."""
        data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 2,
            "slides": [
                {
                    "slide_id": "slide-0",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Presentation Title",
                    "content": {
                        "subtitle": "Test Presentation"
                    },
                    "visual_hint": "centered"
                },
                {
                    "slide_id": "slide-1",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Test Slide",
                    "content": {},
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = validation_agent.validate(data, execution_id="test-zero-bullets", apply_corrections=True)
        
        assert result.is_valid
        assert result.corrections_applied > 0
        
        # Check that bullets were generated (slide 1 is the content slide)
        corrected_slide = result.corrected_data["slides"][1]
        bullets = corrected_slide["content"]["bullets"]
        assert len(bullets) >= MIN_BULLETS, f"Expected at least {MIN_BULLETS} bullets, got {len(bullets)}"
    
    def test_sufficient_bullets_unchanged(self):
        """Content slide with sufficient bullets should not be modified."""
        data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "content",
                    "title": "Test Slide",
                    "content": {
                        "bullets": [
                            "First bullet point",
                            "Second bullet point",
                            "Third bullet point"
                        ]
                    },
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = validation_agent.validate(data, execution_id="test-sufficient-bullets", apply_corrections=True)
        
        assert result.is_valid
        
        # Check that bullets were not modified (still 3)
        corrected_slide = result.corrected_data["slides"][0]
        bullets = corrected_slide["content"]["bullets"]
        assert len(bullets) == 3


class TestContentDensityValidation:
    """Test content density enforcement to prevent overflow."""
    
    def test_excessive_content_gets_truncated(self):
        """Slide with excessive content should be truncated."""
        # Create a slide with way too much content
        long_bullets = [
            "This is an extremely long bullet point with way too many words that will definitely exceed the maximum word count limit and cause overflow issues on the slide layout" * 2
            for _ in range(10)
        ]
        
        data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "content",
                    "title": "This is an extremely long title with way too many words that should be truncated",
                    "content": {
                        "bullets": long_bullets,
                        "highlight_text": "This is an extremely long highlight text with way too many words that will definitely exceed the maximum length and should be truncated to prevent overflow"
                    },
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = validation_agent.validate(data, execution_id="test-density", apply_corrections=True)
        
        assert result.is_valid
        
        corrected_slide = result.corrected_data["slides"][0]
        
        # Check that title was truncated
        title_words = corrected_slide["title"].split()
        assert len(title_words) <= 8, f"Title should be max 8 words, got {len(title_words)}"
        
        # Check that bullets were limited
        bullets = corrected_slide["content"]["bullets"]
        assert len(bullets) <= 4, f"Should have max 4 bullets, got {len(bullets)}"
        
        # Check that each bullet was truncated
        for bullet in bullets:
            bullet_words = bullet.split()
            assert len(bullet_words) <= 8, f"Bullet should be max 8 words, got {len(bullet_words)}"
        
        # Check that highlight text was truncated
        highlight = corrected_slide["content"].get("highlight_text", "")
        if highlight:
            highlight_words = highlight.split()
            assert len(highlight_words) <= 15, f"Highlight should be max 15 words, got {len(highlight_words)}"
    
    def test_content_density_calculation(self):
        """Test that content density is calculated correctly."""
        slide = {
            "slide_id": "slide-1",
            "slide_number": 1,
            "type": "content",
            "title": "Short Title",
            "content": {
                "bullets": [
                    "Short bullet",
                    "Another short bullet"
                ]
            },
            "visual_hint": "bullet-left"
        }
        
        density = validation_agent.calculate_content_density(slide)
        
        # Low content should have low density
        assert 0.0 <= density <= 1.0
        assert density < 0.5, f"Expected low density for minimal content, got {density}"
    
    def test_high_density_slide_gets_reduced(self):
        """Test that high-density slides are automatically reduced."""
        # Create a slide with high density
        slide = {
            "slide_id": "slide-1",
            "slide_number": 1,
            "type": "content",
            "title": "Very Long Title With Many Words That Exceeds Limits",
            "content": {
                "bullets": [
                    "Very long bullet point with excessive words that should be truncated" * 3
                    for _ in range(8)
                ]
            },
            "visual_hint": "bullet-left"
        }
        
        corrected_slide, was_modified = validation_agent.enforce_content_density(slide)
        
        # Should have been modified
        assert was_modified, "High-density slide should be modified"
        
        # Check that content was reduced
        new_density = validation_agent.calculate_content_density(corrected_slide)
        assert new_density <= MAX_CONTENT_DENSITY, f"Density {new_density} should be <= {MAX_CONTENT_DENSITY}"


class TestMultipleContentIssues:
    """Test slides with multiple content issues."""
    
    def test_single_bullet_and_overflow_both_fixed(self):
        """Slide with both single bullet and overflow should be fixed."""
        data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 2,
            "slides": [
                {
                    "slide_id": "slide-0",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Presentation Title",
                    "content": {
                        "subtitle": "Test Presentation"
                    },
                    "visual_hint": "centered"
                },
                {
                    "slide_id": "slide-1",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Very Long Title With Many Words That Exceeds The Maximum Allowed Limit",
                    "content": {
                        "bullets": [
                            "Only one extremely long bullet point with way too many words that will definitely exceed the maximum word count limit and cause overflow issues on the slide layout and should be truncated"
                        ]
                    },
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = validation_agent.validate(data, execution_id="test-multiple-issues", apply_corrections=True)
        
        assert result.is_valid
        assert result.corrections_applied > 0
        
        # Get the content slide (slide 1, not slide 0 which is title)
        corrected_slide = result.corrected_data["slides"][1]
        
        # Check minimum bullets enforced
        bullets = corrected_slide["content"]["bullets"]
        assert len(bullets) >= MIN_BULLETS, f"Expected at least {MIN_BULLETS} bullets"
        
        # Check title truncated
        title_words = corrected_slide["title"].split()
        assert len(title_words) <= 8, f"Title should be max 8 words"
        
        # Check bullets truncated
        for bullet in bullets:
            bullet_words = bullet.split()
            assert len(bullet_words) <= 8, f"Bullet should be max 8 words"
    
    def test_multiple_slides_all_fixed(self):
        """Multiple slides with various issues should all be fixed."""
        data = {
            "schema_version": "1.0.0",
            "presentation_id": "test-123",
            "total_slides": 3,
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "content",
                    "title": "Slide 1",
                    "content": {
                        "bullets": ["Only one bullet"]
                    },
                    "visual_hint": "bullet-left"
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Very Long Title With Too Many Words That Should Be Truncated",
                    "content": {
                        "bullets": [
                            "Long bullet " * 20,
                            "Another long bullet " * 20,
                            "Yet another long bullet " * 20,
                            "And one more long bullet " * 20,
                            "Plus an extra bullet " * 20,
                        ]
                    },
                    "visual_hint": "bullet-left"
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "content",
                    "title": "Slide 3",
                    "content": {},
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = validation_agent.validate(data, execution_id="test-multiple-slides", apply_corrections=True)
        
        assert result.is_valid
        
        # Check all slides were fixed
        for slide in result.corrected_data["slides"]:
            if slide["type"] == "content":
                bullets = slide["content"]["bullets"]
                assert len(bullets) >= MIN_BULLETS, f"Slide {slide['slide_number']} should have min bullets"
                assert len(bullets) <= 4, f"Slide {slide['slide_number']} should have max 4 bullets"
                
                for bullet in bullets:
                    bullet_words = bullet.split()
                    assert len(bullet_words) <= 8, f"Bullet in slide {slide['slide_number']} should be max 8 words"
