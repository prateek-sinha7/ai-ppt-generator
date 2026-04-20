"""
Tests for SlidePrettyPrinter (Req 26, Task 28).

Covers:
- 28.1: text, markdown, and JSON output formats
- 28.2: format_slide() producing structured outline per slide
- 28.3: formatting completes within 2 seconds for 50-slide presentations
"""

import json
import time
from typing import Any, Dict, List

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.agents.pretty_printer import SlidePrettyPrinter


# ---------------------------------------------------------------------------
# Helpers / Factories
# ---------------------------------------------------------------------------

def make_slide(
    slide_number: int = 1,
    slide_type: str = "content",
    title: str = "Test Slide",
    bullets: List[str] | None = None,
    chart_data: Dict | None = None,
    table_data: Dict | None = None,
    comparison_data: Dict | None = None,
    icon_name: str | None = None,
    highlight_text: str | None = None,
    visual_hint: str = "bullet-left",
) -> Dict[str, Any]:
    content: Dict[str, Any] = {}
    if bullets is not None:
        content["bullets"] = bullets
    if chart_data is not None:
        content["chart_data"] = chart_data
    if table_data is not None:
        content["table_data"] = table_data
    if comparison_data is not None:
        content["comparison_data"] = comparison_data
    if icon_name is not None:
        content["icon_name"] = icon_name
    if highlight_text is not None:
        content["highlight_text"] = highlight_text

    return {
        "slide_id": f"slide-{slide_number}",
        "slide_number": slide_number,
        "type": slide_type,
        "title": title,
        "content": content,
        "visual_hint": visual_hint,
        "metadata": {"quality_score": 8.5},
    }


def make_presentation(num_slides: int = 5) -> Dict[str, Any]:
    slides = []
    types = ["title", "content", "chart", "table", "comparison"]
    for i in range(1, num_slides + 1):
        slide_type = types[(i - 1) % len(types)]
        slide: Dict[str, Any] = {"slide_number": i, "type": slide_type, "title": f"Slide {i} Title", "content": {}, "visual_hint": "centered"}
        if slide_type == "content":
            slide["content"]["bullets"] = ["Point one", "Point two", "Point three"]
            slide["visual_hint"] = "bullet-left"
        elif slide_type == "chart":
            slide["content"]["chart_data"] = {"chart_type": "bar", "labels": ["A", "B"], "values": [10, 20]}
            slide["visual_hint"] = "split-chart-right"
        elif slide_type == "table":
            slide["content"]["table_data"] = {"headers": ["Col1", "Col2"], "rows": [["a", "b"], ["c", "d"]]}
            slide["visual_hint"] = "split-table-left"
        elif slide_type == "comparison":
            slide["content"]["comparison_data"] = {"left_title": "Option A", "right_title": "Option B", "left_points": [], "right_points": []}
            slide["visual_hint"] = "two-column"
        slides.append(slide)

    return {
        "schema_version": "1.0.0",
        "presentation_id": "pres-test-001",
        "total_slides": num_slides,
        "slides": slides,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def printer() -> SlidePrettyPrinter:
    return SlidePrettyPrinter()


@pytest.fixture
def simple_presentation() -> Dict[str, Any]:
    return make_presentation(5)


@pytest.fixture
def large_presentation() -> Dict[str, Any]:
    return make_presentation(50)


# ---------------------------------------------------------------------------
# 28.1 — Output format tests
# ---------------------------------------------------------------------------

class TestTextFormat:
    def test_returns_string(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="text")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_slide_numbers(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="text")
        for i in range(1, 6):
            assert f"[{i}]" in result

    def test_contains_slide_titles(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="text")
        for slide in simple_presentation["slides"]:
            assert slide["title"] in result

    def test_contains_presentation_metadata(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="text")
        assert "5 slides" in result
        assert "1.0.0" in result

    def test_default_format_is_text(self, printer, simple_presentation):
        result_default = printer.format(simple_presentation)
        result_text = printer.format(simple_presentation, output_format="text")
        assert result_default == result_text

    def test_bullets_rendered_with_bullet_char(self, printer):
        pres = make_presentation(1)
        pres["slides"][0]["content"]["bullets"] = ["Alpha", "Beta"]
        result = printer.format(pres, output_format="text")
        assert "• Alpha" in result
        assert "• Beta" in result

    def test_chart_annotation_present(self, printer):
        slide = make_slide(
            slide_type="chart",
            chart_data={"chart_type": "pie"},
            visual_hint="split-chart-right",
        )
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="text")
        assert "[CHART: pie]" in result

    def test_table_annotation_present(self, printer):
        slide = make_slide(
            slide_type="table",
            table_data={"headers": ["A"], "rows": [["x"], ["y"], ["z"]]},
            visual_hint="split-table-left",
        )
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="text")
        assert "[TABLE: 3 rows]" in result

    def test_comparison_annotation_present(self, printer):
        slide = make_slide(
            slide_type="comparison",
            comparison_data={"left_title": "Before", "right_title": "After"},
            visual_hint="two-column",
        )
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="text")
        assert "[COMPARISON: Before vs After]" in result

    def test_icon_annotation_present(self, printer):
        slide = make_slide(icon_name="trending-up")
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="text")
        assert "[ICON: trending-up]" in result

    def test_highlight_annotation_present(self, printer):
        slide = make_slide(highlight_text="$1B Revenue")
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="text")
        assert "[HIGHLIGHT: $1B Revenue]" in result


class TestMarkdownFormat:
    def test_returns_string(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="markdown")
        assert isinstance(result, str)

    def test_has_h1_header(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="markdown")
        assert "# Presentation Outline" in result

    def test_has_h2_per_slide(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="markdown")
        for slide in simple_presentation["slides"]:
            assert f"## Slide {slide['slide_number']}:" in result

    def test_bullets_as_markdown_list(self, printer):
        pres = make_presentation(1)
        pres["slides"][0]["content"]["bullets"] = ["Alpha", "Beta"]
        result = printer.format(pres, output_format="markdown")
        assert "- Alpha" in result
        assert "- Beta" in result

    def test_chart_blockquote_present(self, printer):
        slide = make_slide(
            slide_type="chart",
            chart_data={"chart_type": "line"},
            visual_hint="split-chart-right",
        )
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="markdown")
        assert "**Chart:**" in result
        assert "line" in result

    def test_table_blockquote_present(self, printer):
        slide = make_slide(
            slide_type="table",
            table_data={"headers": ["X"], "rows": [["1"], ["2"]]},
            visual_hint="split-table-left",
        )
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="markdown")
        assert "**Table:**" in result
        assert "2 rows" in result

    def test_metadata_in_header(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="markdown")
        assert "**Slides:** 5" in result
        assert "`1.0.0`" in result
        assert "`pres-test-001`" in result

    def test_visual_hint_shown(self, printer):
        slide = make_slide(visual_hint="highlight-metric")
        pres = {"schema_version": "1.0.0", "total_slides": 1, "slides": [slide]}
        result = printer.format(pres, output_format="markdown")
        assert "highlight-metric" in result


class TestJsonFormat:
    def test_returns_valid_json(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="json")
        parsed = json.loads(result)
        assert parsed["schema_version"] == "1.0.0"
        assert len(parsed["slides"]) == 5

    def test_json_is_indented(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="json")
        # Indented JSON has newlines
        assert "\n" in result

    def test_json_round_trip(self, printer, simple_presentation):
        result = printer.format(simple_presentation, output_format="json")
        parsed = json.loads(result)
        assert parsed == simple_presentation


class TestInvalidFormat:
    def test_raises_on_unknown_format(self, printer, simple_presentation):
        with pytest.raises(ValueError, match="Unsupported output_format"):
            printer.format(simple_presentation, output_format="xml")  # type: ignore


# ---------------------------------------------------------------------------
# 28.2 — format_slide() tests
# ---------------------------------------------------------------------------

class TestFormatSlide:
    def test_returns_string(self, printer):
        slide = make_slide()
        result = printer.format_slide(slide)
        assert isinstance(result, str)

    def test_header_line_format(self, printer):
        slide = make_slide(slide_number=3, slide_type="content", title="My Title")
        result = printer.format_slide(slide)
        first_line = result.split("\n")[0]
        assert first_line == "[3] CONTENT: My Title"

    def test_title_slide_type_uppercase(self, printer):
        slide = make_slide(slide_type="title", visual_hint="centered")
        result = printer.format_slide(slide)
        assert "TITLE" in result

    def test_bullets_indented(self, printer):
        slide = make_slide(bullets=["First point", "Second point"])
        result = printer.format_slide(slide)
        assert "  • First point" in result
        assert "  • Second point" in result

    def test_empty_content_no_crash(self, printer):
        slide = {"slide_number": 1, "type": "title", "title": "Hello", "content": {}}
        result = printer.format_slide(slide)
        assert "[1] TITLE: Hello" in result

    def test_missing_optional_fields_no_crash(self, printer):
        slide = {"slide_number": 2, "type": "content", "title": "Minimal"}
        result = printer.format_slide(slide)
        assert "[2] CONTENT: Minimal" in result

    def test_chart_data_shown(self, printer):
        slide = make_slide(chart_data={"chart_type": "bar"})
        result = printer.format_slide(slide)
        assert "[CHART: bar]" in result

    def test_table_data_row_count(self, printer):
        slide = make_slide(table_data={"rows": [["a"], ["b"], ["c"]]})
        result = printer.format_slide(slide)
        assert "[TABLE: 3 rows]" in result

    def test_comparison_data_shown(self, printer):
        slide = make_slide(
            comparison_data={"left_title": "Old", "right_title": "New"}
        )
        result = printer.format_slide(slide)
        assert "[COMPARISON: Old vs New]" in result

    def test_icon_shown(self, printer):
        slide = make_slide(icon_name="shield")
        result = printer.format_slide(slide)
        assert "[ICON: shield]" in result

    def test_highlight_shown(self, printer):
        slide = make_slide(highlight_text="Key Metric: 42%")
        result = printer.format_slide(slide)
        assert "[HIGHLIGHT: Key Metric: 42%]" in result

    def test_visual_hint_shown(self, printer):
        slide = make_slide(visual_hint="split-chart-right")
        result = printer.format_slide(slide)
        assert "visual_hint: split-chart-right" in result

    def test_all_slide_types(self, printer):
        for slide_type in ["title", "content", "chart", "table", "comparison"]:
            slide = make_slide(slide_type=slide_type)
            result = printer.format_slide(slide)
            assert slide_type.upper() in result

    def test_multiline_output(self, printer):
        slide = make_slide(bullets=["A", "B", "C"])
        result = printer.format_slide(slide)
        lines = result.split("\n")
        assert len(lines) >= 4  # header + 3 bullets + visual_hint


# ---------------------------------------------------------------------------
# 28.3 — Performance: 50 slides within 2 seconds
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_text_format_50_slides_under_2s(self, printer, large_presentation):
        start = time.perf_counter()
        result = printer.format(large_presentation, output_format="text")
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"text format took {elapsed:.3f}s (limit: 2s)"
        assert len(result) > 0

    def test_markdown_format_50_slides_under_2s(self, printer, large_presentation):
        start = time.perf_counter()
        result = printer.format(large_presentation, output_format="markdown")
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"markdown format took {elapsed:.3f}s (limit: 2s)"
        assert len(result) > 0

    def test_json_format_50_slides_under_2s(self, printer, large_presentation):
        start = time.perf_counter()
        result = printer.format(large_presentation, output_format="json")
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"json format took {elapsed:.3f}s (limit: 2s)"
        assert len(result) > 0

    def test_format_slide_50_times_under_2s(self, printer, large_presentation):
        slides = large_presentation["slides"]
        start = time.perf_counter()
        for slide in slides:
            printer.format_slide(slide)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"format_slide x50 took {elapsed:.3f}s (limit: 2s)"


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

slide_type_st = st.sampled_from(["title", "content", "chart", "table", "comparison"])
visual_hint_st = st.sampled_from(
    ["centered", "bullet-left", "split-chart-right", "split-table-left", "two-column", "highlight-metric"]
)
output_format_st = st.sampled_from(["text", "markdown", "json"])


@given(
    slide_number=st.integers(min_value=1, max_value=100),
    slide_type=slide_type_st,
    title=st.text(min_size=1, max_size=60, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
    visual_hint=visual_hint_st,
)
@settings(max_examples=50)
def test_format_slide_always_returns_string(slide_number, slide_type, title, visual_hint):
    printer = SlidePrettyPrinter()
    slide = {
        "slide_number": slide_number,
        "type": slide_type,
        "title": title,
        "content": {},
        "visual_hint": visual_hint,
    }
    result = printer.format_slide(slide)
    assert isinstance(result, str)
    assert len(result) > 0


@given(
    num_slides=st.integers(min_value=1, max_value=50),
    output_format=output_format_st,
)
@settings(max_examples=30)
def test_format_always_returns_string_for_any_size(num_slides, output_format):
    printer = SlidePrettyPrinter()
    pres = make_presentation(num_slides)
    result = printer.format(pres, output_format=output_format)
    assert isinstance(result, str)
    assert len(result) > 0


@given(output_format=output_format_st)
@settings(max_examples=10)
def test_format_empty_slides_list(output_format):
    printer = SlidePrettyPrinter()
    pres = {"schema_version": "1.0.0", "total_slides": 0, "slides": []}
    result = printer.format(pres, output_format=output_format)
    assert isinstance(result, str)


@given(
    bullets=st.lists(
        st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
        min_size=0,
        max_size=10,
    )
)
@settings(max_examples=50)
def test_format_slide_with_arbitrary_bullets(bullets):
    printer = SlidePrettyPrinter()
    slide = {
        "slide_number": 1,
        "type": "content",
        "title": "Test",
        "content": {"bullets": bullets},
        "visual_hint": "bullet-left",
    }
    result = printer.format_slide(slide)
    for bullet in bullets:
        assert bullet in result
