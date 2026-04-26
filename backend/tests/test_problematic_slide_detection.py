"""
Test Problematic Slide Detection - Ensures slides with layout/content fit issues are removed.

This test verifies that the validation agent correctly identifies and removes:
- Slides with empty or missing critical content
- Slides with aggressively truncated content
- Slides at batch processing boundaries (7, 11, 15, 19, 23)
"""

import pytest
from app.agents.validation import ValidationAgent


class TestProblematicSlideDetection:
    """Test that problematic slides are correctly detected and removed."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ValidationAgent()

    def test_detect_content_slide_with_no_bullets(self):
        """Test detection of content slide with no bullets."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test Presentation",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Content Slide",
                    "content": {"bullets": []},  # Empty bullets - problematic
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "content",
                    "title": "Good Content",
                    "content": {"bullets": ["Point 1", "Point 2", "Point 3"]},
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-1"
        )

        # Slide 2 should be removed
        assert len(removed) == 1
        assert 2 in removed
        assert len(corrected["slides"]) == 2
        assert corrected["slides"][1]["slide_number"] == 2  # Renumbered

    def test_detect_chart_slide_with_insufficient_data(self):
        """Test detection of chart slide with insufficient data."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "chart",
                    "title": "Chart Slide",
                    "content": {"chart_data": []},  # Empty chart data - problematic
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "chart",
                    "title": "Good Chart",
                    "content": {
                        "chart_data": [
                            {"label": "A", "value": 10},
                            {"label": "B", "value": 20},
                            {"label": "C", "value": 30},
                        ]
                    },
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-2"
        )

        assert len(removed) == 1
        assert 2 in removed
        assert len(corrected["slides"]) == 2

    def test_detect_table_slide_with_invalid_data(self):
        """Test detection of table slide with invalid data."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "table",
                    "title": "Table Slide",
                    "content": {"table_data": {}},  # Empty table data - problematic
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "table",
                    "title": "Good Table",
                    "content": {
                        "table_data": {
                            "headers": ["Col1", "Col2"],
                            "rows": [["A", "B"], ["C", "D"]],
                        }
                    },
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-3"
        )

        assert len(removed) == 1
        assert 2 in removed
        assert len(corrected["slides"]) == 2

    def test_detect_batch_boundary_slides(self):
        """Test detection of problematic slides at batch boundaries (7, 11, 15, 19, 23)."""
        # Create a presentation with slides at batch boundaries
        slides = [
            {
                "slide_id": f"slide-{i+1}",
                "slide_number": i + 1,
                "type": "title" if i == 0 else "content",
                "title": f"Slide {i+1}",
                "content": {
                    "subtitle": "Test" if i == 0 else None,
                    "bullets": [] if i == 6 else ["Point 1", "Point 2"],  # Slide 7 has no bullets
                },
            }
            for i in range(12)
        ]

        data = {"schema_version": "1.0.0", "slides": slides}

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-4"
        )

        # Slide 7 (index 6) should be removed due to batch boundary + no bullets
        assert 7 in removed
        assert len(corrected["slides"]) == 11

    def test_detect_title_too_short(self):
        """Test detection of slides with titles that are too short (likely truncated)."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "A",  # Single word - likely truncated
                    "content": {"bullets": ["Point 1"]},
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "content",
                    "title": "Good Title Here",
                    "content": {"bullets": ["Point 1", "Point 2"]},
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-6"
        )

        # Slide 2 should be removed (title too short)
        assert 2 in removed
        assert len(corrected["slides"]) == 2

    def test_no_problematic_slides(self):
        """Test that no slides are removed when all are valid."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test Presentation",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Good Content Slide",
                    "content": {
                        "bullets": ["Point 1", "Point 2", "Point 3"],
                    },
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "chart",
                    "title": "Good Chart Slide",
                    "content": {
                        "chart_data": [
                            {"label": "A", "value": 10},
                            {"label": "B", "value": 20},
                        ],
                    },
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-7"
        )

        # No slides should be removed
        assert len(removed) == 0
        assert len(corrected["slides"]) == 3

    def test_slide_renumbering_after_removal(self):
        """Test that slides are correctly renumbered after removal."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Bad Slide",
                    "content": {"bullets": []},  # Will be removed
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "content",
                    "title": "Good Slide",
                    "content": {"bullets": ["Point 1", "Point 2"]},
                },
                {
                    "slide_id": "slide-4",
                    "slide_number": 4,
                    "type": "content",
                    "title": "Another Good Slide",
                    "content": {"bullets": ["Point 1", "Point 2"]},
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-8"
        )

        # Verify renumbering
        assert len(corrected["slides"]) == 3
        assert corrected["slides"][0]["slide_number"] == 1
        assert corrected["slides"][1]["slide_number"] == 2
        assert corrected["slides"][2]["slide_number"] == 3

    def test_multiple_problematic_slides_removed(self):
        """Test removal of multiple problematic slides."""
        data = {
            "schema_version": "1.0.0",
            "slides": [
                {
                    "slide_id": "slide-1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Test",
                    "content": {"subtitle": "Test"},
                },
                {
                    "slide_id": "slide-2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Bad Slide One",
                    "content": {"bullets": []},  # Will be removed
                },
                {
                    "slide_id": "slide-3",
                    "slide_number": 3,
                    "type": "content",
                    "title": "Good Slide",
                    "content": {"bullets": ["Point 1", "Point 2"]},
                },
                {
                    "slide_id": "slide-4",
                    "slide_number": 4,
                    "type": "chart",
                    "title": "Bad Slide Two",
                    "content": {"chart_data": []},  # Will be removed
                },
                {
                    "slide_id": "slide-5",
                    "slide_number": 5,
                    "type": "content",
                    "title": "Good Slide Two",
                    "content": {"bullets": ["Point 1", "Point 2"]},
                },
            ]
        }

        corrected, removed = self.validator.detect_and_remove_problematic_slides(
            data, "test-exec-9"
        )

        # Two slides should be removed
        assert len(removed) == 2
        assert 2 in removed
        assert 4 in removed
        assert len(corrected["slides"]) == 3
