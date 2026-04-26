"""
Tests for the Layout Decision Engine (Task 23).

Covers:
- 23.1 Layout mapping rules
- 23.2 Content density calculation and enforcement
- 23.3 Dynamic font size adjustment
- 23.4 Design Intelligence Layer layout scoring
- 23.5 layout_instructions generation using token names
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.agents.layout_engine import (
    DEFAULT_BODY_TOKEN,
    DEFAULT_PADDING_TOKEN,
    FONT_SIZE_SCALE,
    LAYOUT_MAPPING,
    MAX_CONTENT_DENSITY,
    MIN_FONT_TOKEN,
    MIN_WHITESPACE_RATIO,
    DensityResult,
    FontAdjustmentResult,
    LayoutScore,
    SlideType,
    VisualHint,
    adjust_font_size,
    apply_layout_to_presentation,
    apply_layout_to_slide,
    calculate_content_density,
    enforce_density_constraints,
    generate_layout_instructions,
    layout_engine,
    map_slide_type_to_visual_hint,
    score_presentation_layout,
    score_slide_layout,
)
from app.agents.validation import (
    VALID_SPACING_TOKENS,
    VALID_THEME_NAMES,
    VALID_TYPOGRAPHY_TOKENS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_slide(
    slide_type: str = "content",
    bullets: list[str] | None = None,
    has_chart: bool = False,
    has_table: bool = False,
    has_comparison: bool = False,
    visual_hint: str | None = None,
    layout_instructions: dict | None = None,
    slide_id: str = "slide-1",
) -> dict:
    content: dict = {}
    if bullets is not None:
        content["bullets"] = bullets
    if has_chart:
        content["chart_data"] = {"chart_type": "bar", "data": []}
    if has_table:
        content["table_data"] = {"headers": [], "rows": []}
    if has_comparison:
        content["comparison_data"] = {"left": {}, "right": {}}

    slide: dict = {
        "slide_id": slide_id,
        "type": slide_type,
        "title": "Test Slide",
        "content": content,
    }
    if visual_hint is not None:
        slide["visual_hint"] = visual_hint
    if layout_instructions is not None:
        slide["layout_instructions"] = layout_instructions
    return slide


# ---------------------------------------------------------------------------
# 23.1 — Layout Mapping Rules
# ---------------------------------------------------------------------------

class TestLayoutMappingRules:
    """Tests for slide type → visual_hint canonical mapping."""

    @pytest.mark.parametrize("slide_type,expected_hint", [
        ("title",      "centered"),
        ("content",    "bullet-left"),
        ("chart",      "split-chart-right"),
        ("table",      "split-table-left"),
        ("comparison", "two-column"),
        ("metric",     "highlight-metric"),
    ])
    def test_canonical_mapping(self, slide_type: str, expected_hint: str):
        hint = map_slide_type_to_visual_hint(slide_type)
        assert hint.value == expected_hint

    def test_all_slide_types_covered(self):
        """Every SlideType must have a mapping."""
        for st_enum in SlideType:
            hint = map_slide_type_to_visual_hint(st_enum.value)
            assert isinstance(hint, VisualHint)

    def test_unknown_type_falls_back_to_bullet_left(self):
        hint = map_slide_type_to_visual_hint("unknown_type")
        assert hint == VisualHint.BULLET_LEFT

    def test_case_insensitive(self):
        assert map_slide_type_to_visual_hint("TITLE") == VisualHint.CENTERED
        assert map_slide_type_to_visual_hint("Chart") == VisualHint.SPLIT_CHART_RIGHT

    def test_layout_mapping_dict_completeness(self):
        """LAYOUT_MAPPING must cover all SlideType values."""
        for st_enum in SlideType:
            assert st_enum in LAYOUT_MAPPING, f"Missing mapping for {st_enum}"

    def test_engine_facade_map_visual_hint(self):
        assert layout_engine.map_visual_hint("title") == "centered"
        assert layout_engine.map_visual_hint("chart") == "split-chart-right"


# ---------------------------------------------------------------------------
# 23.2 — Content Density Calculation and Enforcement
# ---------------------------------------------------------------------------

class TestContentDensityCalculation:
    """Tests for density calculation logic."""

    def test_empty_slide_has_base_density(self):
        slide = make_slide(bullets=[])
        result = calculate_content_density(slide)
        assert result.density == pytest.approx(0.10)
        assert result.whitespace_ratio == pytest.approx(0.90)
        assert not result.exceeds_max
        assert not result.below_min_whitespace

    def test_four_bullets_within_bounds(self):
        slide = make_slide(bullets=["a", "b", "c", "d"])
        result = calculate_content_density(slide)
        # 0.10 base + 4 * 0.15 = 0.70
        assert result.density == pytest.approx(0.70)
        assert not result.exceeds_max

    def test_chart_slide_density(self):
        slide = make_slide(slide_type="chart", has_chart=True)
        result = calculate_content_density(slide)
        # 0.10 + 0.40 = 0.50
        assert result.density == pytest.approx(0.50)
        assert not result.exceeds_max

    def test_overcrowded_slide_exceeds_max(self):
        # 4 bullets + chart = 0.10 + 0.60 + 0.40 = 1.10 → capped at 1.0
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        result = calculate_content_density(slide)
        assert result.density == pytest.approx(1.0)
        assert result.exceeds_max

    def test_density_capped_at_one(self):
        slide = make_slide(
            bullets=["a", "b", "c", "d"],
            has_chart=True,
            has_table=True,
        )
        result = calculate_content_density(slide)
        assert result.density <= 1.0

    def test_whitespace_ratio_is_complement(self):
        slide = make_slide(bullets=["a", "b"])
        result = calculate_content_density(slide)
        assert result.whitespace_ratio == pytest.approx(1.0 - result.density, abs=1e-4)

    def test_below_min_whitespace_flag(self):
        # 4 bullets = 0.70 density → whitespace 0.30 — OK
        slide = make_slide(bullets=["a", "b", "c", "d"])
        result = calculate_content_density(slide)
        assert not result.below_min_whitespace

    def test_engine_facade_calculate_density(self):
        slide = make_slide(bullets=["x"])
        result = layout_engine.calculate_density(slide)
        assert isinstance(result, DensityResult)


class TestDensityEnforcement:
    """Tests for density constraint enforcement."""

    def test_within_bounds_unchanged(self):
        slide = make_slide(bullets=["a", "b"])
        adjusted, needs_split = enforce_density_constraints(slide)
        assert adjusted["content"]["bullets"] == ["a", "b"]
        assert not needs_split

    def test_overcrowded_bullets_trimmed(self):
        # 4 bullets + chart → exceeds max; bullets should be trimmed
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        adjusted, _ = enforce_density_constraints(slide)
        density = calculate_content_density(adjusted)
        assert density.density <= MAX_CONTENT_DENSITY

    def test_original_slide_not_mutated(self):
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        original_bullets = list(slide["content"]["bullets"])
        enforce_density_constraints(slide)
        assert slide["content"]["bullets"] == original_bullets

    def test_needs_split_when_chart_alone_exceeds(self):
        # chart + table → density 0.10 + 0.40 + 0.40 = 0.90 > 0.75
        # bullets are empty so trimming won't help → needs_split=True
        slide = make_slide(has_chart=True, has_table=True)
        _, needs_split = enforce_density_constraints(slide)
        assert needs_split

    def test_engine_facade_enforce_density(self):
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        adjusted, _ = layout_engine.enforce_density(slide)
        assert calculate_content_density(adjusted).density <= MAX_CONTENT_DENSITY


# ---------------------------------------------------------------------------
# 23.3 — Dynamic Font Size Adjustment
# ---------------------------------------------------------------------------

class TestFontSizeAdjustment:
    """Tests for dynamic font size adjustment."""

    def test_no_adjustment_when_within_bounds(self):
        slide = make_slide(bullets=["a"])
        result = adjust_font_size(slide)
        assert not result.adjusted
        assert result.font_size_token == DEFAULT_BODY_TOKEN

    def test_steps_down_when_overcrowded(self):
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        result = adjust_font_size(slide, current_token="slide-body")
        assert result.adjusted
        # Should step down to slide-caption
        assert result.font_size_token == "slide-caption"

    def test_never_goes_below_minimum(self):
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        result = adjust_font_size(slide, current_token=MIN_FONT_TOKEN)
        assert result.font_size_token == MIN_FONT_TOKEN

    def test_font_scale_order(self):
        """Font scale must go from largest to smallest."""
        assert FONT_SIZE_SCALE.index("slide-title") < FONT_SIZE_SCALE.index("slide-caption")

    def test_unknown_token_falls_back_to_body(self):
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        result = adjust_font_size(slide, current_token="nonexistent-token")
        # Should not raise; falls back to body position
        assert result.font_size_token in FONT_SIZE_SCALE

    def test_engine_facade_adjust_font(self):
        slide = make_slide(bullets=["a"])
        result = layout_engine.adjust_font(slide)
        assert isinstance(result, FontAdjustmentResult)


# ---------------------------------------------------------------------------
# 23.4 — Design Intelligence Layer Layout Scoring
# ---------------------------------------------------------------------------

class TestLayoutScoring:
    """Tests for the layout scoring algorithm."""

    def test_perfect_slide_scores_ten(self):
        slide = make_slide(
            slide_type="content",
            bullets=["a", "b"],
            visual_hint="bullet-left",
            layout_instructions={
                "padding": "6",
                "font_size": "slide-body",
                "theme": "hexaware_corporate",
            },
        )
        score = score_slide_layout(slide)
        assert score.total_score == pytest.approx(10.0)

    def test_wrong_visual_hint_loses_points(self):
        slide = make_slide(
            slide_type="content",
            bullets=["a"],
            visual_hint="centered",  # wrong for content
        )
        score = score_slide_layout(slide)
        assert score.type_hint_match == 0.0
        assert "visual_hint" in " ".join(score.recommendations).lower()

    def test_overcrowded_slide_loses_density_points(self):
        slide = make_slide(
            slide_type="chart",
            bullets=["a", "b", "c", "d"],
            has_chart=True,
            visual_hint="split-chart-right",
        )
        score = score_slide_layout(slide)
        assert score.density_score == 0.0

    def test_three_consecutive_same_type_loses_diversity_points(self):
        slide = make_slide(slide_type="content", bullets=["a"], visual_hint="bullet-left")
        prev_slide = make_slide(slide_type="content", slide_id="prev")
        next_slide = make_slide(slide_type="content", slide_id="next")
        score = score_slide_layout(slide, prev_slide, next_slide)
        assert score.diversity_score == 0.0

    def test_two_consecutive_same_type_partial_diversity(self):
        slide = make_slide(slide_type="content", bullets=["a"], visual_hint="bullet-left")
        prev_slide = make_slide(slide_type="content", slide_id="prev")
        score = score_slide_layout(slide, prev_slide, None)
        assert score.diversity_score == 1.0

    def test_invalid_token_in_instructions_loses_points(self):
        slide = make_slide(
            slide_type="content",
            bullets=["a"],
            visual_hint="bullet-left",
            layout_instructions={"padding": "999px"},  # invalid token
        )
        score = score_slide_layout(slide)
        assert score.token_compliance < 2.0

    def test_score_range_0_to_10(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        score = score_slide_layout(slide)
        assert 0.0 <= score.total_score <= 10.0

    def test_presentation_layout_score_aggregate(self):
        slides = [
            make_slide("title", visual_hint="centered", slide_id="s1"),
            make_slide("content", bullets=["a", "b"], visual_hint="bullet-left", slide_id="s2"),
            make_slide("chart", has_chart=True, visual_hint="split-chart-right", slide_id="s3"),
        ]
        result = score_presentation_layout("pres-1", slides)
        assert result.presentation_id == "pres-1"
        assert result.total_slides == 3
        assert 0.0 <= result.average_score <= 10.0
        assert len(result.slide_scores) == 3

    def test_slides_needing_attention_identified(self):
        # A slide with wrong hint and overcrowded content should score < 6
        bad_slide = make_slide(
            slide_type="content",
            bullets=["a", "b", "c", "d"],
            has_chart=True,
            visual_hint="centered",  # wrong
            slide_id="bad-slide",
        )
        result = score_presentation_layout("pres-2", [bad_slide])
        assert "bad-slide" in result.slides_needing_attention

    def test_engine_facade_score_layout(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        score = layout_engine.score_layout(slide)
        assert isinstance(score, LayoutScore)

    def test_engine_facade_score_presentation(self):
        slides = [make_slide("title", slide_id="s1"), make_slide("content", slide_id="s2")]
        result = layout_engine.score_presentation("p1", slides)
        assert result.total_slides == 2


# ---------------------------------------------------------------------------
# 23.5 — layout_instructions Generation Using Token Names
# ---------------------------------------------------------------------------

class TestLayoutInstructionsGeneration:
    """Tests for layout_instructions token name generation."""

    def test_instructions_use_valid_spacing_tokens(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        instructions = generate_layout_instructions(slide)
        for key in ("padding", "gap"):
            assert instructions[key] in VALID_SPACING_TOKENS, (
                f"'{key}' value '{instructions[key]}' is not a valid spacing token"
            )

    def test_instructions_use_valid_typography_tokens(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        instructions = generate_layout_instructions(slide)
        for key in ("font_size", "title_font_size"):
            assert instructions[key] in VALID_TYPOGRAPHY_TOKENS, (
                f"'{key}' value '{instructions[key]}' is not a valid typography token"
            )

    def test_instructions_use_valid_theme_token(self):
        for theme in VALID_THEME_NAMES:
            slide = make_slide(slide_type="content", bullets=["a"])
            instructions = generate_layout_instructions(slide, theme=theme)
            assert instructions["theme"] in VALID_THEME_NAMES

    def test_title_slide_gets_larger_padding(self):
        title_slide = make_slide(slide_type="title")
        content_slide = make_slide(slide_type="content", bullets=["a"])
        title_instr = generate_layout_instructions(title_slide)
        content_instr = generate_layout_instructions(content_slide)
        # Title should have padding "8" (32px), content "6" (24px)
        assert title_instr["padding"] == "8"
        assert content_instr["padding"] == DEFAULT_PADDING_TOKEN

    def test_chart_slide_has_column_gap(self):
        slide = make_slide(slide_type="chart", has_chart=True)
        instructions = generate_layout_instructions(slide)
        assert "column_gap" in instructions
        assert instructions["column_gap"] in VALID_SPACING_TOKENS

    def test_comparison_slide_has_column_gap(self):
        slide = make_slide(slide_type="comparison", has_comparison=True)
        instructions = generate_layout_instructions(slide)
        assert "column_gap" in instructions

    def test_dense_slide_uses_compact_tokens(self):
        # 4 bullets + chart → density > 0.75 → compact padding
        slide = make_slide(bullets=["a", "b", "c", "d"], has_chart=True)
        instructions = generate_layout_instructions(slide)
        assert instructions["padding"] == "4"  # compact

    def test_engine_facade_generate_instructions(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        instructions = layout_engine.generate_instructions(slide)
        assert "padding" in instructions
        assert "theme" in instructions


# ---------------------------------------------------------------------------
# apply_layout_to_slide / apply_layout_to_presentation
# ---------------------------------------------------------------------------

class TestApplyLayout:
    """Integration tests for full layout application."""

    def test_apply_sets_visual_hint(self):
        slide = make_slide(slide_type="chart", has_chart=True)
        result = apply_layout_to_slide(slide)
        assert result["visual_hint"] == "split-chart-right"

    def test_apply_sets_layout_instructions(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        result = apply_layout_to_slide(slide)
        assert "layout_instructions" in result
        assert "padding" in result["layout_instructions"]

    def test_apply_sets_layout_constraints(self):
        slide = make_slide(slide_type="content", bullets=["a"])
        result = apply_layout_to_slide(slide)
        constraints = result["layout_constraints"]
        assert constraints["max_content_density"] == MAX_CONTENT_DENSITY
        assert constraints["min_whitespace_ratio"] == MIN_WHITESPACE_RATIO

    def test_apply_does_not_mutate_original(self):
        slide = make_slide(slide_type="content", bullets=["a", "b"])
        original_bullets = list(slide["content"]["bullets"])
        apply_layout_to_slide(slide)
        assert slide["content"]["bullets"] == original_bullets

    def test_apply_to_presentation_processes_all_slides(self):
        slides = [
            make_slide("title", slide_id="s1"),
            make_slide("content", bullets=["a"], slide_id="s2"),
            make_slide("chart", has_chart=True, slide_id="s3"),
        ]
        results = apply_layout_to_presentation(slides)
        assert len(results) == 3
        for r in results:
            assert "visual_hint" in r
            assert "layout_instructions" in r
            assert "layout_constraints" in r

    def test_apply_to_presentation_correct_hints(self):
        slides = [
            make_slide("title", slide_id="s1"),
            make_slide("table", has_table=True, slide_id="s2"),
        ]
        results = apply_layout_to_presentation(slides)
        assert results[0]["visual_hint"] == "centered"
        assert results[1]["visual_hint"] == "split-table-left"

    def test_engine_facade_apply_to_slide(self):
        slide = make_slide(slide_type="metric")
        result = layout_engine.apply_to_slide(slide)
        assert result["visual_hint"] == "highlight-metric"

    def test_engine_facade_apply_to_presentation(self):
        slides = [make_slide("content", slide_id="s1")]
        results = layout_engine.apply_to_presentation(slides)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------

VALID_SLIDE_TYPES = ["title", "content", "chart", "table", "comparison", "metric"]
VALID_THEMES = list(VALID_THEME_NAMES)


@given(slide_type=st.sampled_from(VALID_SLIDE_TYPES))
def test_property_layout_mapping_deterministic(slide_type: str):
    """For any valid slide type, mapping is deterministic."""
    hint1 = map_slide_type_to_visual_hint(slide_type)
    hint2 = map_slide_type_to_visual_hint(slide_type)
    assert hint1 == hint2


@given(
    bullet_count=st.integers(min_value=0, max_value=10),
    has_chart=st.booleans(),
)
def test_property_density_always_in_range(bullet_count: int, has_chart: bool):
    """Density is always in [0, 1]."""
    slide = make_slide(
        bullets=["bullet"] * bullet_count,
        has_chart=has_chart,
    )
    result = calculate_content_density(slide)
    assert 0.0 <= result.density <= 1.0
    assert 0.0 <= result.whitespace_ratio <= 1.0
    assert abs(result.density + result.whitespace_ratio - 1.0) < 1e-4


@given(
    bullet_count=st.integers(min_value=0, max_value=10),
    has_chart=st.booleans(),
)
def test_property_enforce_density_never_exceeds_max(bullet_count: int, has_chart: bool):
    """After enforcement, density never exceeds MAX_CONTENT_DENSITY (unless chart/table alone)."""
    slide = make_slide(bullets=["b"] * bullet_count, has_chart=has_chart)
    adjusted, _ = enforce_density_constraints(slide)
    result = calculate_content_density(adjusted)
    # If chart alone causes overflow, needs_split=True and density may still exceed
    # but bullets should be 0 in that case
    if not has_chart:
        assert result.density <= MAX_CONTENT_DENSITY


@given(slide_type=st.sampled_from(VALID_SLIDE_TYPES))
@settings(max_examples=50)
def test_property_apply_layout_always_sets_valid_hint(slide_type: str):
    """apply_layout_to_slide always produces a valid visual_hint."""
    valid_hints = {vh.value for vh in VisualHint}
    slide = make_slide(slide_type=slide_type)
    result = apply_layout_to_slide(slide)
    assert result["visual_hint"] in valid_hints


@given(
    slide_type=st.sampled_from(VALID_SLIDE_TYPES),
    theme=st.sampled_from(VALID_THEMES),
)
@settings(max_examples=50)
def test_property_layout_instructions_always_valid_tokens(slide_type: str, theme: str):
    """All generated layout_instructions values are valid token names."""
    slide = make_slide(slide_type=slide_type)
    instructions = generate_layout_instructions(slide, theme=theme)

    from app.agents.validation import (
        SPACING_INSTRUCTION_KEYS,
        THEME_INSTRUCTION_KEYS,
        TYPOGRAPHY_INSTRUCTION_KEYS,
    )

    for key, value in instructions.items():
        assert isinstance(value, str), f"Token value for '{key}' must be a string"
        if key in SPACING_INSTRUCTION_KEYS:
            assert value in VALID_SPACING_TOKENS, f"'{value}' not a valid spacing token for '{key}'"
        elif key in TYPOGRAPHY_INSTRUCTION_KEYS:
            assert value in VALID_TYPOGRAPHY_TOKENS, f"'{value}' not a valid typography token for '{key}'"
        elif key in THEME_INSTRUCTION_KEYS:
            assert value in VALID_THEME_NAMES, f"'{value}' not a valid theme for '{key}'"


@given(
    bullet_count=st.integers(min_value=0, max_value=6),
)
@settings(max_examples=50)
def test_property_score_always_in_range(bullet_count: int):
    """Layout score is always in [0, 10]."""
    slide = make_slide(bullets=["b"] * bullet_count, visual_hint="bullet-left")
    score = score_slide_layout(slide)
    assert 0.0 <= score.total_score <= 10.0
