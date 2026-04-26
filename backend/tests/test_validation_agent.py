"""
Tests for Validation Agent.

Tests cover:
- SlideContentParser functionality
- Title truncation
- Bullet splitting and truncation
- Automatic slide splitting
- JSON schema validation
- Visual hint enum validation
- Auto-correction for missing fields and wrong types
- Round-trip property validation
"""

import json
from copy import deepcopy
from uuid import uuid4

import pytest

from app.agents.validation import (
    SlideContentParser,
    ValidationAgent,
    ValidationError,
    SlideType,
    VisualHint,
    MAX_TITLE_WORDS,
    MAX_BULLETS,
    MAX_WORDS_PER_BULLET,
    VALID_SPACING_TOKENS,
    VALID_TYPOGRAPHY_TOKENS,
    VALID_THEME_NAMES,
    SPACING_INSTRUCTION_KEYS,
    TYPOGRAPHY_INSTRUCTION_KEYS,
    THEME_INSTRUCTION_KEYS,
)


# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

def create_valid_slide_json():
    """Create a valid Slide_JSON for testing."""
    return {
        "schema_version": "1.0.0",
        "presentation_id": str(uuid4()),
        "total_slides": 2,
        "slides": [
            {
                "slide_id": str(uuid4()),
                "slide_number": 1,
                "type": "title",
                "title": "Test Presentation Title",
                "content": {},
                "visual_hint": "centered",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "test",
                    "quality_score": 8.5
                }
            },
            {
                "slide_id": str(uuid4()),
                "slide_number": 2,
                "type": "content",
                "title": "Content Slide",
                "content": {
                    "bullets": [
                        "First bullet point",
                        "Second bullet point",
                        "Third bullet point"
                    ]
                },
                "visual_hint": "bullet-left",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25
                },
                "metadata": {
                    "generated_at": "2024-01-01T00:00:00",
                    "provider_used": "test",
                    "quality_score": 8.5
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# SlideContentParser Tests
# ---------------------------------------------------------------------------

class TestSlideContentParser:
    """Tests for SlideContentParser."""
    
    def test_truncate_title_within_limit(self):
        """Test title truncation when within word limit."""
        title = "Short Title"
        result = SlideContentParser.truncate_title(title)
        assert result == title
    
    def test_truncate_title_exceeds_limit(self):
        """Test title truncation when exceeding word limit."""
        title = "This is a very long title that exceeds the maximum word count limit"
        result = SlideContentParser.truncate_title(title, max_words=8)
        words = result.split()
        assert len(words) == 8
        assert result == "This is a very long title that exceeds"
    
    def test_truncate_bullet_within_limit(self):
        """Test bullet truncation when within word limit."""
        bullet = "Short bullet"
        result = SlideContentParser.truncate_bullet(bullet)
        assert result == bullet
    
    def test_truncate_bullet_exceeds_limit(self):
        """Test bullet truncation when exceeding word limit."""
        bullet = "This is a very long bullet point that exceeds the maximum word count"
        result = SlideContentParser.truncate_bullet(bullet, max_words=8)
        words = result.split()
        assert len(words) == 8
        assert result == "This is a very long bullet point that"
    
    def test_split_bullets_within_limit(self):
        """Test bullet splitting when within limit."""
        bullets = ["Bullet 1", "Bullet 2", "Bullet 3"]
        current, overflow = SlideContentParser.split_bullets(bullets, max_bullets=4)
        assert len(current) == 3
        assert len(overflow) == 0
        assert current == bullets
    
    def test_split_bullets_exceeds_limit(self):
        """Test bullet splitting when exceeding limit."""
        bullets = ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5", "Bullet 6"]
        current, overflow = SlideContentParser.split_bullets(bullets, max_bullets=4)
        assert len(current) == 4
        assert len(overflow) == 2
        assert current == bullets[:4]
        assert overflow == bullets[4:]
    
    def test_split_bullets_with_truncation(self):
        """Test bullet splitting with word truncation."""
        bullets = [
            "This is a very long bullet point that exceeds the maximum",
            "Another long bullet point with too many words",
            "Short bullet",
            "Yet another extremely long bullet point that needs truncation"
        ]
        current, overflow = SlideContentParser.split_bullets(bullets, max_bullets=4, max_words_per_bullet=8)
        
        # All bullets should be truncated to 8 words
        for bullet in current:
            assert len(bullet.split()) <= 8
        
        # Should have all 4 bullets (no overflow since max_bullets=4)
        assert len(current) == 4
        assert len(overflow) == 0
    
    def test_parse_slide_content_title_truncation(self):
        """Test slide content parsing with title truncation."""
        slide = {
            "title": "This is a very long title that exceeds the maximum word count limit",
            "content": {}
        }
        result = SlideContentParser.parse_slide_content(slide)
        assert len(result["title"].split()) <= MAX_TITLE_WORDS
    
    def test_parse_slide_content_bullet_splitting(self):
        """Test slide content parsing with bullet splitting."""
        slide = {
            "title": "Test Slide",
            "content": {
                "bullets": [
                    "Bullet 1", "Bullet 2", "Bullet 3",
                    "Bullet 4", "Bullet 5", "Bullet 6"
                ]
            }
        }
        result = SlideContentParser.parse_slide_content(slide)
        
        # Should have max 4 bullets
        assert len(result["content"]["bullets"]) <= MAX_BULLETS
        
        # Should have overflow
        assert "_overflow_bullets" in result
        assert len(result["_overflow_bullets"]) == 2


# ---------------------------------------------------------------------------
# ValidationAgent Tests
# ---------------------------------------------------------------------------

class TestValidationAgent:
    """Tests for ValidationAgent."""
    
    def test_validate_schema_valid_data(self):
        """Test schema validation with valid data."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        
        is_valid, errors = agent.validate_schema(data)
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_schema_missing_required_field(self):
        """Test schema validation with missing required field."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        del data["schema_version"]
        
        is_valid, errors = agent.validate_schema(data)
        assert not is_valid
        assert len(errors) > 0
        assert any("schema_version" in e.field or "required" in e.message.lower() for e in errors)
    
    def test_validate_schema_wrong_type(self):
        """Test schema validation with wrong field type."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["total_slides"] = "not_a_number"
        
        is_valid, errors = agent.validate_schema(data)
        assert not is_valid
        assert len(errors) > 0
    
    def test_validate_visual_hints_valid(self):
        """Test visual hint validation with valid hints."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        
        errors = agent.validate_visual_hints(data)
        assert len(errors) == 0
    
    def test_validate_visual_hints_invalid(self):
        """Test visual hint validation with invalid hints."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["slides"][0]["visual_hint"] = "invalid-hint"
        
        errors = agent.validate_visual_hints(data)
        assert len(errors) > 0
        assert any("visual_hint" in e.field for e in errors)
    
    def test_auto_correct_missing_fields(self):
        """Test auto-correction of missing fields."""
        agent = ValidationAgent()
        data = {
            "slides": [
                {
                    "type": "title",
                    "title": "Test",
                    "content": {},
                    "visual_hint": "centered"
                }
            ]
        }
        
        corrected, corrections = agent.auto_correct_missing_fields(data)
        
        assert corrections > 0
        assert "schema_version" in corrected
        assert "presentation_id" in corrected
        assert "total_slides" in corrected
        assert corrected["total_slides"] == 1
        assert "slide_id" in corrected["slides"][0]
        assert "slide_number" in corrected["slides"][0]
    
    def test_auto_correct_missing_visual_hint(self):
        """Test auto-correction of missing visual_hint field."""
        agent = ValidationAgent()
        data = {
            "slides": [
                {
                    "type": "title",
                    "title": "Test Title",
                    "content": {}
                }
            ]
        }
        
        corrected, corrections = agent.auto_correct_missing_fields(data)
        
        assert corrections > 0
        assert "visual_hint" in corrected["slides"][0]
        # Title slide should get "centered" visual hint
        assert corrected["slides"][0]["visual_hint"] == "centered"
    
    def test_auto_correct_missing_visual_hint_content_slide(self):
        """Test auto-correction of missing visual_hint for content slide."""
        agent = ValidationAgent()
        data = {
            "slides": [
                {
                    "type": "content",
                    "title": "Test Content",
                    "content": {"bullets": ["Point 1"]}
                }
            ]
        }
        
        corrected, corrections = agent.auto_correct_missing_fields(data)
        
        assert corrections > 0
        assert "visual_hint" in corrected["slides"][0]
        # Content slide should get "bullet-left" visual hint
        assert corrected["slides"][0]["visual_hint"] == "bullet-left"
    
    def test_auto_correct_wrong_types(self):
        """Test auto-correction of wrong types."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["total_slides"] = "2"  # String instead of int
        data["slides"][0]["slide_number"] = "1"  # String instead of int
        
        corrected, corrections = agent.auto_correct_wrong_types(data)
        
        assert corrections > 0
        assert isinstance(corrected["total_slides"], int)
        assert isinstance(corrected["slides"][0]["slide_number"], int)
    
    def test_auto_correct_slide_type_mapping(self):
        """Test auto-correction of slide type variations."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["slides"][0]["type"] = "title_slide"
        
        corrected, corrections = agent.auto_correct_wrong_types(data)
        
        assert corrections > 0
        assert corrected["slides"][0]["type"] == "title"
    
    def test_auto_correct_visual_hint_mapping(self):
        """Test auto-correction of visual hint variations."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["slides"][0]["visual_hint"] = "center"
        
        corrected, corrections = agent.auto_correct_wrong_types(data)
        
        assert corrections > 0
        assert corrected["slides"][0]["visual_hint"] == "centered"
    
    def test_auto_correct_content_list_to_dict(self):
        """Test auto-correction of content field when it's a list instead of dict."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        # LLM sometimes returns content as a list directly
        data["slides"][0]["content"] = ["Bullet 1", "Bullet 2", "Bullet 3"]
        
        corrected, corrections = agent.auto_correct_wrong_types(data)
        
        assert corrections > 0
        assert isinstance(corrected["slides"][0]["content"], dict)
        assert "bullets" in corrected["slides"][0]["content"]
        assert corrected["slides"][0]["content"]["bullets"] == ["Bullet 1", "Bullet 2", "Bullet 3"]
    
    def test_auto_correct_content_invalid_type(self):
        """Test auto-correction of content field when it's an invalid type."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        # Content is a string (invalid)
        data["slides"][0]["content"] = "Invalid content"
        
        corrected, corrections = agent.auto_correct_wrong_types(data)
        
        assert corrections > 0
        assert isinstance(corrected["slides"][0]["content"], dict)
        assert corrected["slides"][0]["content"] == {}
    
    def test_apply_content_constraints_no_overflow(self):
        """Test content constraints with no overflow."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        
        corrected, overflow_slides = agent.apply_content_constraints(data)
        
        assert len(overflow_slides) == 0
        assert corrected["total_slides"] == data["total_slides"]
    
    def test_apply_content_constraints_with_overflow(self):
        """Test content constraints with bullet overflow."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["slides"][1]["content"]["bullets"] = [
            "Bullet 1", "Bullet 2", "Bullet 3",
            "Bullet 4", "Bullet 5", "Bullet 6"
        ]
        
        corrected, overflow_slides = agent.apply_content_constraints(data)
        
        # Should create overflow slide
        assert len(overflow_slides) > 0
        assert corrected["total_slides"] > data["total_slides"]
        
        # Original slide should have max 4 bullets
        assert len(corrected["slides"][1]["content"]["bullets"]) <= MAX_BULLETS
        
        # Overflow slide should exist
        assert len(corrected["slides"]) == 3
    
    def test_validate_round_trip_consistent(self):
        """Test round-trip validation with consistent data."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        
        is_consistent = agent.validate_round_trip(data)
        assert is_consistent
    
    def test_validate_full_process_valid_data(self):
        """Test full validation process with valid data."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        
        result = agent.validate(data, execution_id="test-exec-1")
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.corrected_data is not None
    
    def test_validate_full_process_with_corrections(self):
        """Test full validation process with auto-corrections."""
        agent = ValidationAgent()
        data = {
            "slides": [
                {
                    "type": "content",
                    "title": "This is a very long title that exceeds the maximum word count",
                    "content": {
                        "bullets": [
                            "Bullet 1", "Bullet 2", "Bullet 3",
                            "Bullet 4", "Bullet 5", "Bullet 6"
                        ]
                    },
                    "visual_hint": "bullets"
                }
            ]
        }
        
        result = agent.validate(data, execution_id="test-exec-2", apply_corrections=True)
        
        assert result.corrections_applied > 0
        assert result.corrected_data is not None
        
        # Check title truncation
        title_words = len(result.corrected_data["slides"][0]["title"].split())
        assert title_words <= MAX_TITLE_WORDS
        
        # Check visual hint correction
        assert result.corrected_data["slides"][0]["visual_hint"] == "bullet-left"
    
    def test_validate_without_corrections(self):
        """Test validation without applying corrections."""
        agent = ValidationAgent()
        data = {
            "slides": [
                {
                    "type": "content",
                    "title": "Test",
                    "content": {},
                    "visual_hint": "bullet-left"
                }
            ]
        }
        
        result = agent.validate(data, execution_id="test-exec-3", apply_corrections=False)
        
        assert not result.is_valid
        assert result.corrected_data is None
    
    def test_validate_all_visual_hint_enums(self):
        """Test validation with all valid visual hint enums."""
        agent = ValidationAgent()
        
        for hint in VisualHint:
            data = create_valid_slide_json()
            data["slides"][0]["visual_hint"] = hint.value
            
            errors = agent.validate_visual_hints(data)
            assert len(errors) == 0
    
    def test_validate_all_slide_type_enums(self):
        """Test validation with all valid slide type enums."""
        agent = ValidationAgent()
        
        for slide_type in SlideType:
            data = create_valid_slide_json()
            data["slides"][0]["type"] = slide_type.value
            
            is_valid, errors = agent.validate_schema(data)
            assert is_valid


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestValidationAgentIntegration:
    """Integration tests for ValidationAgent."""
    
    def test_end_to_end_validation_and_correction(self):
        """Test end-to-end validation and correction flow."""
        agent = ValidationAgent()
        
        # Create problematic data
        data = {
            "slides": [
                {
                    "type": "title_slide",  # Wrong format
                    "title": "This is a very long title that exceeds the maximum word count limit",
                    "content": {},
                    "visual_hint": "center"  # Wrong format
                },
                {
                    "type": "content",
                    "title": "Content Slide",
                    "content": {
                        "bullets": [
                            "This is a very long bullet point that exceeds the maximum word count",
                            "Another long bullet point with too many words in it",
                            "Bullet 3",
                            "Bullet 4",
                            "Bullet 5",
                            "Bullet 6"
                        ]
                    },
                    "visual_hint": "bullets"  # Wrong format
                }
            ]
        }
        
        # Validate and correct
        result = agent.validate(data, execution_id="test-integration-1", apply_corrections=True)
        
        # Should have corrections
        assert result.corrections_applied > 0
        assert result.corrected_data is not None
        
        corrected = result.corrected_data
        
        # Check schema fields added
        assert "schema_version" in corrected
        assert "presentation_id" in corrected
        assert "total_slides" in corrected
        
        # Check slide type correction
        assert corrected["slides"][0]["type"] == "title"
        
        # Check visual hint corrections
        assert corrected["slides"][0]["visual_hint"] == "centered"
        assert corrected["slides"][1]["visual_hint"] == "bullet-left"
        
        # Check title truncation
        assert len(corrected["slides"][0]["title"].split()) <= MAX_TITLE_WORDS
        
        # Check bullet splitting (should create overflow slide)
        assert corrected["total_slides"] > 2
        
        # Check bullet truncation
        for bullet in corrected["slides"][1]["content"]["bullets"]:
            assert len(bullet.split()) <= MAX_WORDS_PER_BULLET
        
        # Final validation should pass
        final_valid, final_errors = agent.validate_schema(corrected)
        assert final_valid
    
    def test_validation_preserves_valid_data(self):
        """Test that validation preserves already valid data."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        original_json = json.dumps(data, sort_keys=True)
        
        result = agent.validate(data, execution_id="test-integration-2", apply_corrections=True)
        
        assert result.is_valid
        
        # Content should be preserved (except for potential slide number adjustments)
        assert result.corrected_data["schema_version"] == data["schema_version"]
        assert result.corrected_data["presentation_id"] == data["presentation_id"]
        assert len(result.corrected_data["slides"]) == len(data["slides"])


# ---------------------------------------------------------------------------
# Design Token Validation Tests
# ---------------------------------------------------------------------------

class TestLayoutInstructionTokenValidation:
    """Tests for validate_layout_instructions — design token name enforcement."""

    def _slide_with_instructions(self, instructions: dict) -> dict:
        """Build a minimal valid Slide_JSON with layout_instructions on slide 0."""
        data = create_valid_slide_json()
        data["slides"][0]["layout_instructions"] = instructions
        return data

    def test_valid_spacing_tokens_produce_no_errors(self):
        agent = ValidationAgent()
        for token in VALID_SPACING_TOKENS:
            data = self._slide_with_instructions({"padding": token})
            errors = agent.validate_layout_instructions(data)
            assert errors == [], f"Expected no errors for spacing token '{token}'"

    def test_invalid_spacing_token_produces_warning(self):
        agent = ValidationAgent()
        data = self._slide_with_instructions({"padding": "99"})
        errors = agent.validate_layout_instructions(data)
        assert len(errors) == 1
        assert errors[0].severity == "warning"
        assert "padding" in errors[0].field
        assert "99" in errors[0].message

    def test_valid_typography_tokens_produce_no_errors(self):
        agent = ValidationAgent()
        for token in VALID_TYPOGRAPHY_TOKENS:
            data = self._slide_with_instructions({"font_size": token})
            errors = agent.validate_layout_instructions(data)
            assert errors == [], f"Expected no errors for typography token '{token}'"

    def test_invalid_typography_token_produces_warning(self):
        agent = ValidationAgent()
        data = self._slide_with_instructions({"font_size": "huge"})
        errors = agent.validate_layout_instructions(data)
        assert len(errors) == 1
        assert errors[0].severity == "warning"
        assert "font_size" in errors[0].field

    def test_valid_theme_names_produce_no_errors(self):
        agent = ValidationAgent()
        for theme in VALID_THEME_NAMES:
            data = self._slide_with_instructions({"theme": theme})
            errors = agent.validate_layout_instructions(data)
            assert errors == [], f"Expected no errors for theme '{theme}'"

    def test_invalid_theme_name_produces_warning(self):
        agent = ValidationAgent()
        data = self._slide_with_instructions({"theme": "corporate-blue"})
        errors = agent.validate_layout_instructions(data)
        assert len(errors) == 1
        assert errors[0].severity == "warning"
        assert "theme" in errors[0].field

    def test_unknown_instruction_key_is_ignored(self):
        """Keys not in any known category should not produce errors."""
        agent = ValidationAgent()
        data = self._slide_with_instructions({"custom_key": "anything"})
        errors = agent.validate_layout_instructions(data)
        assert errors == []

    def test_non_string_value_produces_warning(self):
        agent = ValidationAgent()
        data = self._slide_with_instructions({"padding": 16})  # type: ignore
        errors = agent.validate_layout_instructions(data)
        assert len(errors) == 1
        assert "string" in errors[0].message

    def test_non_dict_layout_instructions_produces_warning(self):
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["slides"][0]["layout_instructions"] = "invalid"  # type: ignore
        errors = agent.validate_layout_instructions(data)
        assert len(errors) == 1
        assert "object" in errors[0].message

    def test_missing_layout_instructions_produces_no_errors(self):
        """Slides without layout_instructions are valid — field is optional."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        # Ensure no layout_instructions key
        data["slides"][0].pop("layout_instructions", None)
        errors = agent.validate_layout_instructions(data)
        assert errors == []

    def test_multiple_invalid_tokens_all_reported(self):
        agent = ValidationAgent()
        data = self._slide_with_instructions({
            "padding": "bad-spacing",
            "font_size": "bad-font",
            "theme": "bad-theme",
        })
        errors = agent.validate_layout_instructions(data)
        assert len(errors) == 3

    def test_token_errors_are_warnings_not_blocking(self):
        """Token validation errors should be warnings and not block overall validation."""
        agent = ValidationAgent()
        data = create_valid_slide_json()
        data["slides"][0]["layout_instructions"] = {"padding": "invalid-token"}
        result = agent.validate(data, execution_id="token-test", apply_corrections=True)
        # Overall validation still passes — token warnings are non-blocking
        assert result.is_valid
        warning_errors = [e for e in result.errors if e.severity == "warning"]
        assert any("padding" in e.field for e in warning_errors)

    def test_valid_token_set_constants(self):
        """Verify the token constant sets contain expected values."""
        assert "2" in VALID_SPACING_TOKENS   # 8px
        assert "4" in VALID_SPACING_TOKENS   # 16px
        assert "8" in VALID_SPACING_TOKENS   # 32px
        assert "slide-title" in VALID_TYPOGRAPHY_TOKENS
        assert "slide-caption" in VALID_TYPOGRAPHY_TOKENS
        assert "hexaware_corporate" in VALID_THEME_NAMES
        assert "hexaware_professional" in VALID_THEME_NAMES

    def test_spacing_instruction_keys_set(self):
        assert "padding" in SPACING_INSTRUCTION_KEYS
        assert "margin" in SPACING_INSTRUCTION_KEYS
        assert "gap" in SPACING_INSTRUCTION_KEYS

    def test_typography_instruction_keys_set(self):
        assert "font_size" in TYPOGRAPHY_INSTRUCTION_KEYS
        assert "title_font_size" in TYPOGRAPHY_INSTRUCTION_KEYS

    def test_theme_instruction_keys_set(self):
        assert "theme" in THEME_INSTRUCTION_KEYS
