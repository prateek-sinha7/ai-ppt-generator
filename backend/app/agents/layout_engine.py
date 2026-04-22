"""
Layout Decision Engine and Content Adjustment.

Implements:
- Layout mapping rules: slide type → visual_hint
- Content density calculation and enforcement (max 0.75, min 0.25 whitespace)
- Dynamic font size adjustment within readability limits
- Design Intelligence Layer layout scoring algorithm
- layout_instructions generation in Slide_JSON using design token names
- LLM-powered visual hierarchy optimization (Phase 4)

References: Req 14, 15, 18, 62 | Design: Design Intelligence Layer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.agents.llm_helpers import LLMEnhancementHelper

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONTENT_DENSITY: float = 0.75
MIN_WHITESPACE_RATIO: float = 0.25

# Font size tokens in descending order (for dynamic adjustment)
FONT_SIZE_SCALE: list[str] = [
    "slide-title",    # largest — title slides
    "slide-subtitle", # headings
    "slide-body",     # default body text
    "slide-caption",  # smallest readable size
]

# Minimum readable font token (never go below this)
MIN_FONT_TOKEN: str = "slide-caption"
DEFAULT_BODY_TOKEN: str = "slide-body"
DEFAULT_TITLE_TOKEN: str = "slide-title"

# Spacing tokens used in layout_instructions
DEFAULT_PADDING_TOKEN: str = "6"   # 24px — 3 grid units
COMPACT_PADDING_TOKEN: str = "4"   # 16px — 2 grid units
DEFAULT_GAP_TOKEN: str = "4"       # 16px
COMPACT_GAP_TOKEN: str = "2"       # 8px


# ---------------------------------------------------------------------------
# LLM Output Models for Phase 4
# ---------------------------------------------------------------------------

class VisualHierarchyOptimization(BaseModel):
    """LLM-generated visual hierarchy optimization."""
    primary_element: str = Field(
        description="The most important content element (e.g., 'title', 'bullet_1', 'chart', 'highlight_text')"
    )
    secondary_elements: list[str] = Field(
        default_factory=list,
        description="Supporting elements in order of importance"
    )
    emphasis_recommendations: dict[str, str] = Field(
        default_factory=dict,
        description="Element-specific emphasis recommendations (e.g., {'title': 'increase_size', 'bullet_2': 'bold'})"
    )
    layout_adjustments: dict[str, str] = Field(
        default_factory=dict,
        description="Layout token adjustments (e.g., {'title_font_size': 'slide-title', 'padding': '8'})"
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SlideType(str, Enum):
    """Allowed slide types."""
    TITLE = "title"
    CONTENT = "content"
    CHART = "chart"
    TABLE = "table"
    COMPARISON = "comparison"
    METRIC = "metric"


class VisualHint(str, Enum):
    """Standardized visual hint enum values."""
    CENTERED = "centered"
    BULLET_LEFT = "bullet-left"
    SPLIT_CHART_RIGHT = "split-chart-right"
    SPLIT_TABLE_LEFT = "split-table-left"
    TWO_COLUMN = "two-column"
    HIGHLIGHT_METRIC = "highlight-metric"


# ---------------------------------------------------------------------------
# 23.1 — Layout Mapping Rules
# ---------------------------------------------------------------------------

# Canonical mapping: slide type → visual hint
LAYOUT_MAPPING: dict[SlideType, VisualHint] = {
    SlideType.TITLE:      VisualHint.CENTERED,
    SlideType.CONTENT:    VisualHint.BULLET_LEFT,
    SlideType.CHART:      VisualHint.SPLIT_CHART_RIGHT,
    SlideType.TABLE:      VisualHint.SPLIT_TABLE_LEFT,
    SlideType.COMPARISON: VisualHint.TWO_COLUMN,
    SlideType.METRIC:     VisualHint.HIGHLIGHT_METRIC,
}


def map_slide_type_to_visual_hint(slide_type: str) -> VisualHint:
    """
    Map a slide type string to the canonical VisualHint enum value.

    Falls back to BULLET_LEFT for unknown types.

    Args:
        slide_type: Slide type string (e.g. "title", "chart")

    Returns:
        Corresponding VisualHint enum value
    """
    try:
        st = SlideType(slide_type.lower())
        hint = LAYOUT_MAPPING[st]
        logger.debug("layout_mapped", slide_type=slide_type, visual_hint=hint.value)
        return hint
    except (ValueError, KeyError):
        logger.warning("unknown_slide_type_fallback", slide_type=slide_type)
        return VisualHint.BULLET_LEFT


# ---------------------------------------------------------------------------
# 23.2 — Content Density Calculation and Enforcement
# ---------------------------------------------------------------------------

@dataclass
class DensityResult:
    """Result of content density calculation."""
    density: float          # 0.0 – 1.0 content coverage
    whitespace_ratio: float # 1.0 - density
    exceeds_max: bool
    below_min_whitespace: bool
    bullet_count: int
    has_chart: bool
    has_table: bool
    has_comparison: bool


def calculate_content_density(slide: dict[str, Any]) -> DensityResult:
    """
    Calculate content density for a single slide.

    Density model:
    - Each bullet contributes 0.15 (max 4 bullets → 0.60)
    - Chart data contributes 0.40
    - Table data contributes 0.40
    - Comparison data contributes 0.35
    - Title always present (0.10 base)
    - Capped at 1.0

    Args:
        slide: Slide dictionary

    Returns:
        DensityResult with density metrics
    """
    content = slide.get("content", {})
    bullets: list = content.get("bullets") or []
    has_chart = bool(content.get("chart_data"))
    has_table = bool(content.get("table_data"))
    has_comparison = bool(content.get("comparison_data"))

    density = 0.10  # base for title
    density += min(len(bullets), 4) * 0.15
    if has_chart:
        density += 0.40
    if has_table:
        density += 0.40
    if has_comparison:
        density += 0.35

    density = min(density, 1.0)
    whitespace_ratio = 1.0 - density

    return DensityResult(
        density=round(density, 4),
        whitespace_ratio=round(whitespace_ratio, 4),
        exceeds_max=density > MAX_CONTENT_DENSITY,
        below_min_whitespace=whitespace_ratio < MIN_WHITESPACE_RATIO,
        bullet_count=len(bullets),
        has_chart=has_chart,
        has_table=has_table,
        has_comparison=has_comparison,
    )


def enforce_density_constraints(
    slide: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """
    Enforce density constraints on a slide, trimming bullets if needed.

    If density exceeds MAX_CONTENT_DENSITY, bullets are trimmed to bring
    density within bounds. Returns the (possibly modified) slide and a flag
    indicating whether a split is still recommended.

    Args:
        slide: Slide dictionary

    Returns:
        (adjusted_slide, needs_split) tuple
    """
    import copy
    result = calculate_content_density(slide)

    if not result.exceeds_max:
        return slide, False

    adjusted = copy.deepcopy(slide)
    content = adjusted.setdefault("content", {})
    bullets: list = list(content.get("bullets") or [])

    # Trim bullets until density is within bounds
    while bullets and calculate_content_density(adjusted).exceeds_max:
        bullets.pop()
        content["bullets"] = bullets

    still_exceeds = calculate_content_density(adjusted).exceeds_max
    logger.info(
        "density_enforced",
        slide_id=slide.get("slide_id"),
        original_bullets=result.bullet_count,
        adjusted_bullets=len(bullets),
        needs_split=still_exceeds,
    )
    return adjusted, still_exceeds


# ---------------------------------------------------------------------------
# 23.3 — Dynamic Font Size Adjustment
# ---------------------------------------------------------------------------

@dataclass
class FontAdjustmentResult:
    """Result of font size adjustment."""
    font_size_token: str
    adjusted: bool
    reason: str


def adjust_font_size(
    slide: dict[str, Any],
    current_token: str = DEFAULT_BODY_TOKEN,
) -> FontAdjustmentResult:
    """
    Dynamically adjust font size token when content exceeds layout bounds.

    Steps down the font scale (slide-body → slide-caption) when density
    is too high. Never goes below MIN_FONT_TOKEN.

    Args:
        slide: Slide dictionary
        current_token: Current font size token

    Returns:
        FontAdjustmentResult with the recommended token
    """
    result = calculate_content_density(slide)

    if not result.exceeds_max:
        return FontAdjustmentResult(
            font_size_token=current_token,
            adjusted=False,
            reason="density_within_bounds",
        )

    # Step down the font scale
    try:
        idx = FONT_SIZE_SCALE.index(current_token)
    except ValueError:
        idx = FONT_SIZE_SCALE.index(DEFAULT_BODY_TOKEN)

    # Move one step smaller
    next_idx = min(idx + 1, len(FONT_SIZE_SCALE) - 1)
    new_token = FONT_SIZE_SCALE[next_idx]

    if new_token == current_token:
        # Already at minimum
        logger.warning(
            "font_at_minimum",
            slide_id=slide.get("slide_id"),
            token=new_token,
        )
        return FontAdjustmentResult(
            font_size_token=new_token,
            adjusted=False,
            reason="already_at_minimum_font_size",
        )

    logger.info(
        "font_size_adjusted",
        slide_id=slide.get("slide_id"),
        from_token=current_token,
        to_token=new_token,
        density=result.density,
    )
    return FontAdjustmentResult(
        font_size_token=new_token,
        adjusted=True,
        reason=f"density_{result.density:.2f}_exceeds_max_{MAX_CONTENT_DENSITY}",
    )


# ---------------------------------------------------------------------------
# 23.4 — Design Intelligence Layer Layout Scoring
# ---------------------------------------------------------------------------

@dataclass
class LayoutScore:
    """Layout quality score for a single slide."""
    slide_id: str
    total_score: float          # 0.0 – 10.0
    type_hint_match: float      # 0–3 pts: visual_hint matches slide type
    density_score: float        # 0–3 pts: density within bounds
    diversity_score: float      # 0–2 pts: not same type as neighbours
    token_compliance: float     # 0–2 pts: layout_instructions use valid tokens
    recommendations: list[str] = field(default_factory=list)


def score_slide_layout(
    slide: dict[str, Any],
    prev_slide: dict[str, Any] | None = None,
    next_slide: dict[str, Any] | None = None,
) -> LayoutScore:
    """
    Score the layout quality of a single slide (0–10).

    Dimensions:
    - Type/hint match (3 pts): visual_hint matches the canonical mapping
    - Density (3 pts): content density within [0, 0.75]
    - Diversity (2 pts): not same type as both neighbours
    - Token compliance (2 pts): layout_instructions reference valid tokens

    Args:
        slide: Slide to score
        prev_slide: Previous slide (for diversity check)
        next_slide: Next slide (for diversity check)

    Returns:
        LayoutScore with breakdown
    """
    from app.agents.validation import (
        VALID_SPACING_TOKENS,
        VALID_TYPOGRAPHY_TOKENS,
        VALID_THEME_NAMES,
        SPACING_INSTRUCTION_KEYS,
        TYPOGRAPHY_INSTRUCTION_KEYS,
        THEME_INSTRUCTION_KEYS,
    )

    slide_id = slide.get("slide_id", "unknown")
    recommendations: list[str] = []

    # --- 1. Type / hint match (0–3 pts) ---
    slide_type = slide.get("type", "")
    visual_hint = slide.get("visual_hint", "")
    expected_hint = map_slide_type_to_visual_hint(slide_type).value
    if visual_hint == expected_hint:
        type_hint_score = 3.0
    else:
        type_hint_score = 0.0
        recommendations.append(
            f"visual_hint '{visual_hint}' should be '{expected_hint}' for type '{slide_type}'"
        )

    # --- 2. Density (0–3 pts) ---
    density_result = calculate_content_density(slide)
    if not density_result.exceeds_max and not density_result.below_min_whitespace:
        density_score = 3.0
    elif density_result.exceeds_max:
        density_score = 0.0
        recommendations.append(
            f"Content density {density_result.density:.2f} exceeds max {MAX_CONTENT_DENSITY}"
        )
    else:
        density_score = 1.5
        recommendations.append(
            f"Whitespace ratio {density_result.whitespace_ratio:.2f} below min {MIN_WHITESPACE_RATIO}"
        )

    # --- 3. Diversity (0–2 pts) ---
    current_type = slide.get("type")
    prev_type = prev_slide.get("type") if prev_slide else None
    next_type = next_slide.get("type") if next_slide else None

    same_as_prev = current_type == prev_type
    same_as_next = current_type == next_type

    if same_as_prev and same_as_next:
        diversity_score = 0.0
        recommendations.append(
            f"Slide type '{current_type}' repeated 3+ times consecutively"
        )
    elif same_as_prev or same_as_next:
        diversity_score = 1.0
    else:
        diversity_score = 2.0

    # --- 4. Token compliance (0–2 pts) ---
    instructions: dict[str, str] = slide.get("layout_instructions") or {}
    token_violations = 0
    for key, value in instructions.items():
        if not isinstance(value, str):
            token_violations += 1
            continue
        if key in SPACING_INSTRUCTION_KEYS and value not in VALID_SPACING_TOKENS:
            token_violations += 1
        elif key in TYPOGRAPHY_INSTRUCTION_KEYS and value not in VALID_TYPOGRAPHY_TOKENS:
            token_violations += 1
        elif key in THEME_INSTRUCTION_KEYS and value not in VALID_THEME_NAMES:
            token_violations += 1

    if token_violations == 0:
        token_score = 2.0
    elif token_violations == 1:
        token_score = 1.0
        recommendations.append("1 layout_instructions token violation found")
    else:
        token_score = 0.0
        recommendations.append(f"{token_violations} layout_instructions token violations found")

    total = type_hint_score + density_score + diversity_score + token_score

    return LayoutScore(
        slide_id=slide_id,
        total_score=round(total, 2),
        type_hint_match=type_hint_score,
        density_score=density_score,
        diversity_score=diversity_score,
        token_compliance=token_score,
        recommendations=recommendations,
    )


@dataclass
class PresentationLayoutScore:
    """Aggregate layout score for a full presentation."""
    presentation_id: str
    average_score: float
    slide_scores: list[LayoutScore]
    total_slides: int
    slides_needing_attention: list[str]  # slide_ids with score < 6


def score_presentation_layout(
    presentation_id: str,
    slides: list[dict[str, Any]],
) -> PresentationLayoutScore:
    """
    Score layout quality across all slides in a presentation.

    Args:
        presentation_id: Presentation identifier
        slides: List of slide dictionaries

    Returns:
        PresentationLayoutScore with per-slide and aggregate scores
    """
    slide_scores: list[LayoutScore] = []

    for i, slide in enumerate(slides):
        prev_slide = slides[i - 1] if i > 0 else None
        next_slide = slides[i + 1] if i < len(slides) - 1 else None
        score = score_slide_layout(slide, prev_slide, next_slide)
        slide_scores.append(score)

    avg = sum(s.total_score for s in slide_scores) / len(slide_scores) if slide_scores else 0.0
    needs_attention = [s.slide_id for s in slide_scores if s.total_score < 6.0]

    logger.info(
        "presentation_layout_scored",
        presentation_id=presentation_id,
        average_score=round(avg, 2),
        slides_needing_attention=len(needs_attention),
    )

    return PresentationLayoutScore(
        presentation_id=presentation_id,
        average_score=round(avg, 2),
        slide_scores=slide_scores,
        total_slides=len(slides),
        slides_needing_attention=needs_attention,
    )


# ---------------------------------------------------------------------------
# 23.5 — layout_instructions Generation Using Token Names
# ---------------------------------------------------------------------------

def generate_layout_instructions(
    slide: dict[str, Any],
    theme: str = "mckinsey",
) -> dict[str, str]:
    """
    Generate layout_instructions for a slide using design token names.

    Produces a mapping of layout keys → token names that the frontend
    uses to apply consistent spacing, typography, and theming.

    Token names reference frontend/src/styles/tokens.ts:
    - Spacing tokens: "0", "1", "2", "4", "6", "8", "10", "12", "16", "20", "24"
    - Typography tokens: "slide-title", "slide-subtitle", "slide-body", "slide-caption"
    - Theme tokens: "mckinsey", "deloitte", "dark-modern"

    Args:
        slide: Slide dictionary
        theme: Active presentation theme name

    Returns:
        layout_instructions dict with token name values
    """
    slide_type = slide.get("type", "content")
    density_result = calculate_content_density(slide)

    # Choose padding based on density
    padding_token = COMPACT_PADDING_TOKEN if density_result.exceeds_max else DEFAULT_PADDING_TOKEN
    gap_token = COMPACT_GAP_TOKEN if density_result.exceeds_max else DEFAULT_GAP_TOKEN

    # Choose font size — adjust down if density is high
    font_adj = adjust_font_size(slide)
    body_font_token = font_adj.font_size_token

    # Title font is always slide-title for title slides, slide-subtitle otherwise
    title_font_token = DEFAULT_TITLE_TOKEN if slide_type == "title" else "slide-subtitle"

    instructions: dict[str, str] = {
        "padding":        padding_token,
        "gap":            gap_token,
        "font_size":      body_font_token,
        "title_font_size": title_font_token,
        "theme":          theme,
    }

    # Type-specific additions
    if slide_type == "title":
        instructions["padding"] = "8"          # 32px — more breathing room
        instructions["font_size"] = "slide-body"
        instructions["title_font_size"] = "slide-title"

    elif slide_type in ("chart", "table"):
        # Split layouts need column gap
        instructions["column_gap"] = "4"       # 16px between text and visual

    elif slide_type == "comparison":
        instructions["column_gap"] = "6"       # 24px between columns

    elif slide_type == "metric":
        instructions["padding"] = "8"
        instructions["title_font_size"] = "slide-title"

    logger.debug(
        "layout_instructions_generated",
        slide_id=slide.get("slide_id"),
        slide_type=slide_type,
        instructions=instructions,
    )
    return instructions


def apply_layout_to_slide(
    slide: dict[str, Any],
    theme: str = "mckinsey",
) -> dict[str, Any]:
    """
    Apply full layout decisions to a slide in-place (returns new dict).

    Performs:
    1. Assign canonical visual_hint from slide type
    2. Enforce density constraints (trim bullets if needed)
    3. Adjust font size token if density is high
    4. Generate layout_instructions using token names
    5. Set layout_constraints

    Args:
        slide: Slide dictionary
        theme: Active presentation theme

    Returns:
        New slide dict with layout fields populated
    """
    import copy
    result = copy.deepcopy(slide)

    # 1. Canonical visual_hint
    result["visual_hint"] = map_slide_type_to_visual_hint(
        result.get("type", "content")
    ).value

    # 2. Enforce density
    result, _ = enforce_density_constraints(result)

    # 3. layout_instructions with token names
    result["layout_instructions"] = generate_layout_instructions(result, theme=theme)

    # 4. layout_constraints
    result["layout_constraints"] = {
        "max_content_density": MAX_CONTENT_DENSITY,
        "min_whitespace_ratio": MIN_WHITESPACE_RATIO,
    }

    return result


def apply_layout_to_presentation(
    slides: list[dict[str, Any]],
    theme: str = "mckinsey",
) -> list[dict[str, Any]]:
    """
    Apply layout decisions to all slides in a presentation.

    Args:
        slides: List of slide dictionaries
        theme: Active presentation theme

    Returns:
        New list of slides with layout fields populated
    """
    return [apply_layout_to_slide(slide, theme=theme) for slide in slides]


# ---------------------------------------------------------------------------
# 23.6 — LLM-Powered Visual Hierarchy Optimization (Phase 4)
# ---------------------------------------------------------------------------

class VisualHierarchyOptimizer(LLMEnhancementHelper):
    """
    Phase 4 Enhancement: Use LLM to optimize visual hierarchy.
    
    Determines which content elements deserve visual emphasis based on
    semantic importance, not just formula-based rules.
    """
    
    async def optimize_visual_hierarchy_with_llm(
        self,
        slide: dict[str, Any],
        execution_id: str,
    ) -> dict[str, Any]:
        """
        Use LLM to determine which content elements deserve visual emphasis.
        
        Phase 4 Enhancement: Goes beyond formula-based layout to understand
        semantic importance and adjust visual hierarchy accordingly.
        
        Args:
            slide: Slide dictionary
            execution_id: Execution ID for tracing
            
        Returns:
            Optimized layout_instructions dict with emphasis adjustments
        """
        logger.info(
            "visual_hierarchy_optimization_started",
            execution_id=execution_id,
            slide_id=slide.get("slide_id"),
        )
        
        # Extract slide content for LLM analysis
        title = slide.get("title", "")
        slide_type = slide.get("type", "content")
        content = slide.get("content", {})
        bullets = content.get("bullets", [])
        highlight_text = content.get("highlight_text", "")
        icon_name = content.get("icon_name", "")
        has_chart = bool(content.get("chart_data"))
        has_table = bool(content.get("table_data"))
        
        # Build content summary
        content_elements = [f"Title: {title}"]
        for i, bullet in enumerate(bullets, 1):
            content_elements.append(f"Bullet {i}: {bullet}")
        if highlight_text:
            content_elements.append(f"Highlight: {highlight_text}")
        if has_chart:
            chart_type = content.get("chart_type", "unknown")
            content_elements.append(f"Chart: {chart_type}")
        if has_table:
            content_elements.append("Table: present")
        if icon_name:
            content_elements.append(f"Icon: {icon_name}")
        
        system_prompt = """You are a visual design expert specializing in presentation hierarchy.
Your task is to determine which content elements deserve the most visual emphasis based on semantic importance.

Consider:
1. What is the key message of this slide?
2. Which elements support that message most directly?
3. What should the audience look at first, second, third?
4. How can layout tokens (font size, padding, spacing) create emphasis?

Available font size tokens (largest to smallest): slide-title, slide-subtitle, slide-body, slide-caption
Available spacing tokens: 0, 1, 2, 4, 6, 8, 10, 12, 16, 20, 24

Be strategic: not everything can be emphasized. Choose 1-2 primary elements."""

        user_prompt = f"""Analyze this slide and determine optimal visual hierarchy.

SLIDE TYPE: {slide_type}

CONTENT ELEMENTS:
{chr(10).join(content_elements)}

Determine:
1. primary_element: The single most important element
2. secondary_elements: Supporting elements in order of importance
3. emphasis_recommendations: How to emphasize each element (e.g., increase_size, bold, color)
4. layout_adjustments: Specific token adjustments (e.g., {{"title_font_size": "slide-title", "padding": "8"}})

Return JSON only."""

        try:
            result = await self.call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                pydantic_model=VisualHierarchyOptimization,
                execution_id=execution_id,
            )
            
            logger.info(
                "visual_hierarchy_optimization_success",
                execution_id=execution_id,
                slide_id=slide.get("slide_id"),
                primary_element=result.get("primary_element"),
                adjustment_count=len(result.get("layout_adjustments", {})),
            )
            
            # Apply layout adjustments to slide's layout_instructions
            current_instructions = slide.get("layout_instructions", {})
            optimized_instructions = {**current_instructions, **result.get("layout_adjustments", {})}
            
            return optimized_instructions
            
        except Exception as e:
            logger.warning(
                "visual_hierarchy_optimization_failed_graceful_degradation",
                execution_id=execution_id,
                slide_id=slide.get("slide_id"),
                error=str(e),
            )
            # Graceful degradation: return current instructions unchanged
            return slide.get("layout_instructions", {})


# Global optimizer instance
visual_hierarchy_optimizer = VisualHierarchyOptimizer()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class LayoutDecisionEngine:
    """
    Facade for the Layout Decision Engine.

    Provides a single entry point for all layout-related operations.
    """

    def map_visual_hint(self, slide_type: str) -> str:
        """Return canonical visual_hint string for a slide type."""
        return map_slide_type_to_visual_hint(slide_type).value

    def calculate_density(self, slide: dict[str, Any]) -> DensityResult:
        """Calculate content density for a slide."""
        return calculate_content_density(slide)

    def enforce_density(
        self, slide: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        """Enforce density constraints, returning adjusted slide and split flag."""
        return enforce_density_constraints(slide)

    def adjust_font(
        self, slide: dict[str, Any], current_token: str = DEFAULT_BODY_TOKEN
    ) -> FontAdjustmentResult:
        """Adjust font size token for a slide."""
        return adjust_font_size(slide, current_token)

    def score_layout(
        self,
        slide: dict[str, Any],
        prev_slide: dict[str, Any] | None = None,
        next_slide: dict[str, Any] | None = None,
    ) -> LayoutScore:
        """Score layout quality for a single slide."""
        return score_slide_layout(slide, prev_slide, next_slide)

    def score_presentation(
        self, presentation_id: str, slides: list[dict[str, Any]]
    ) -> PresentationLayoutScore:
        """Score layout quality for a full presentation."""
        return score_presentation_layout(presentation_id, slides)

    def generate_instructions(
        self, slide: dict[str, Any], theme: str = "mckinsey"
    ) -> dict[str, str]:
        """Generate layout_instructions using token names."""
        return generate_layout_instructions(slide, theme)

    def apply_to_slide(
        self, slide: dict[str, Any], theme: str = "mckinsey"
    ) -> dict[str, Any]:
        """Apply full layout decisions to a slide."""
        return apply_layout_to_slide(slide, theme)

    def apply_to_presentation(
        self, slides: list[dict[str, Any]], theme: str = "mckinsey"
    ) -> list[dict[str, Any]]:
        """Apply layout decisions to all slides."""
        return apply_layout_to_presentation(slides, theme)
    
    async def optimize_visual_hierarchy(
        self,
        slide: dict[str, Any],
        execution_id: str,
    ) -> dict[str, str]:
        """
        Phase 4: Optimize visual hierarchy using LLM.
        
        Args:
            slide: Slide dictionary
            execution_id: Execution ID for tracing
            
        Returns:
            Optimized layout_instructions dict
        """
        return await visual_hierarchy_optimizer.optimize_visual_hierarchy_with_llm(
            slide=slide,
            execution_id=execution_id,
        )


layout_engine = LayoutDecisionEngine()
