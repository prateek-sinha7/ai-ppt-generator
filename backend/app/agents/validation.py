"""
Validation Agent - JSON structure validation and automatic error correction.

This agent validates and corrects LLM-generated Slide_JSON including:
- SlideContentParser with title truncation (max 8 words) and bullet splitting (max 4 bullets, max 8 words each)
- Automatic slide splitting when content exceeds layout bounds
- JSON schema validation against Slide_JSON v1.0.0 with strict type checking
- visual_hint enum validation
- Auto-correction for common JSON errors with 2 retry attempts
- Round-trip property: parse(format(parse(x))) == parse(x)

The agent implements comprehensive validation and correction logic to ensure
all generated content conforms to the Slide_JSON schema and content constraints.
"""

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import structlog
from jsonschema import Draft7Validator, validate
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, Field, field_validator

from app.core.generation_mode import GenerationMode
from app.services.schema_registry import (
    CURRENT_SCHEMA_VERSION,
    SchemaVersionError,
    ensure_schema_version,
    migrate_to_current,
    validate_version_compatibility,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums and Constants
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


class TransitionType(str, Enum):
    """Allowed transition types."""
    FADE = "fade"
    SLIDE = "slide"
    NONE = "none"


# ---------------------------------------------------------------------------
# Design Token Registry (mirrors frontend/src/styles/tokens.ts)
# ---------------------------------------------------------------------------

# Valid spacing token names — must stay in sync with tokens.ts spacing object
VALID_SPACING_TOKENS: frozenset = frozenset({
    "0", "1", "2", "4", "6", "8", "10", "12", "16", "20", "24",
})

# Valid typography token names — must stay in sync with tokens.ts fontSize object
VALID_TYPOGRAPHY_TOKENS: frozenset = frozenset({
    "slide-title", "slide-subtitle", "slide-body", "slide-caption",
})

# Valid theme names — must stay in sync with tokens.ts themes object
VALID_THEME_NAMES: frozenset = frozenset({
    "ocean-depths", "sunset-boulevard", "forest-canopy", "modern-minimalist",
    "golden-hour", "arctic-frost", "desert-rose", "tech-innovation",
    "botanical-garden", "midnight-galaxy",
})

# layout_instructions keys that reference spacing tokens
SPACING_INSTRUCTION_KEYS: frozenset = frozenset({
    "padding", "margin", "gap", "padding_top", "padding_bottom",
    "padding_left", "padding_right", "margin_top", "margin_bottom",
    "margin_left", "margin_right", "row_gap", "column_gap",
})

# layout_instructions keys that reference typography tokens
TYPOGRAPHY_INSTRUCTION_KEYS: frozenset = frozenset({
    "font_size", "title_font_size", "body_font_size", "caption_font_size",
    "subtitle_font_size",
})

# layout_instructions keys that reference theme names
THEME_INSTRUCTION_KEYS: frozenset = frozenset({
    "theme",
})

# Layout variant validation
CONTENT_LAYOUT_VARIANTS: frozenset = frozenset({
    "numbered-cards", "icon-grid", "two-column-text",
    "stat-callouts", "timeline", "quote-highlight",
})
CHART_LAYOUT_VARIANTS: frozenset = frozenset({
    "chart-right", "chart-full", "chart-top", "chart-with-kpi",
})
TABLE_LAYOUT_VARIANTS: frozenset = frozenset({
    "table-full", "table-with-insights", "table-highlight",
})
COMPARISON_LAYOUT_VARIANTS: frozenset = frozenset({
    "two-column", "pros-cons", "before-after", "icon-rows",
})

DEFAULT_LAYOUT_VARIANTS: dict = {
    "content": "numbered-cards",
    "chart": "chart-right",
    "table": "table-full",
    "comparison": "two-column",
}

LAYOUT_VARIANTS_BY_TYPE: dict = {
    "content": CONTENT_LAYOUT_VARIANTS,
    "chart": CHART_LAYOUT_VARIANTS,
    "table": TABLE_LAYOUT_VARIANTS,
    "comparison": COMPARISON_LAYOUT_VARIANTS,
}


# Code-mode constants
PPTXGENJS_API_PATTERN = re.compile(
    r'slide\.(addText|addShape|addChart|addImage|addTable|background)'
)
MAX_RENDER_CODE_LENGTH = 50_000
CODE_SLIDE_REQUIRED_FIELDS = ("slide_id", "slide_number", "type", "title", "speaker_notes", "render_code")

# Artisan-mode constants
ARTISAN_API_PATTERN = re.compile(r'pres\.addSlide\(\)')
MAX_ARTISAN_CODE_LENGTH = 500_000

# Content constraints
MAX_TITLE_WORDS = 8
MAX_BULLETS = 4
MIN_BULLETS = 2  # Minimum bullets per content slide
MAX_WORDS_PER_BULLET = 8
MAX_CONTENT_DENSITY = 0.75
MIN_WHITESPACE_RATIO = 0.25


# ---------------------------------------------------------------------------
# JSON Schema Definition (Slide_JSON v1.0.0)
# ---------------------------------------------------------------------------

SLIDE_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["schema_version", "presentation_id", "total_slides", "slides"],
    "properties": {
        "schema_version": {
            "type": "string",
            "const": "1.0.0"
        },
        "presentation_id": {
            "type": "string",
            "format": "uuid"
        },
        "total_slides": {
            "type": "integer",
            "minimum": 1
        },
        "slides": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["slide_id", "slide_number", "type", "title", "content", "visual_hint"],
                "properties": {
                    "slide_id": {
                        "type": "string"
                    },
                    "slide_number": {
                        "type": "integer",
                        "minimum": 1
                    },
                    "type": {
                        "type": "string",
                        "enum": ["title", "content", "chart", "table", "comparison"]
                    },
                    "title": {
                        "type": "string"
                    },
                    "content": {
                        "type": "object",
                        "properties": {
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "chart_data": {
                                "type": "object"
                            },
                            "table_data": {
                                "type": "object"
                            },
                            "comparison_data": {
                                "type": "object"
                            },
                            "icon_name": {
                                "type": "string"
                            },
                            "highlight_text": {
                                "type": "string"
                            },
                            "transition": {
                                "type": "string",
                                "enum": ["fade", "slide", "none"]
                            }
                        }
                    },
                    "visual_hint": {
                        "type": "string",
                        "enum": [
                            "centered",
                            "bullet-left",
                            "split-chart-right",
                            "split-table-left",
                            "two-column",
                            "highlight-metric"
                        ]
                    },
                    "layout_variant": {
                        "type": "string"
                    },
                    "layout_constraints": {
                        "type": "object",
                        "properties": {
                            "max_content_density": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "min_whitespace_ratio": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "generated_at": {
                                "type": "string",
                                "format": "date-time"
                            },
                            "provider_used": {
                                "type": "string"
                            },
                            "quality_score": {
                                "type": "number",
                                "minimum": 1,
                                "maximum": 10
                            }
                        }
                    }
                }
            }
        }
    }
}


# ---------------------------------------------------------------------------
# Validation Result Models
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    """Validation error details."""
    field: str
    message: str
    severity: str  # "error" or "warning"
    auto_corrected: bool = False


@dataclass
class ValidationResult:
    """Result of validation process."""
    is_valid: bool
    errors: List[ValidationError]
    corrected_data: Optional[Dict[str, Any]] = None
    corrections_applied: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": [
                {
                    "field": e.field,
                    "message": e.message,
                    "severity": e.severity,
                    "auto_corrected": e.auto_corrected
                }
                for e in self.errors
            ],
            "corrections_applied": self.corrections_applied
        }


# ---------------------------------------------------------------------------
# Slide Content Parser
# ---------------------------------------------------------------------------

class SlideContentParser:
    """
    Parser for slide content with automatic truncation and splitting.
    
    Implements:
    - Title truncation (max 8 words)
    - Bullet splitting (max 4 bullets, max 8 words each)
    - Automatic slide splitting when content exceeds bounds
    """
    
    @staticmethod
    def truncate_title(title: str, max_words: int = MAX_TITLE_WORDS) -> str:
        """
        Truncate title to maximum word count.
        
        Args:
            title: Original title
            max_words: Maximum number of words (default: 8)
            
        Returns:
            Truncated title
        """
        words = title.split()
        if len(words) <= max_words:
            return title
        
        truncated = " ".join(words[:max_words])
        logger.info(
            "title_truncated",
            original_words=len(words),
            max_words=max_words,
            original=title[:50],
            truncated=truncated
        )
        return truncated
    
    @staticmethod
    def truncate_bullet(bullet: str, max_words: int = MAX_WORDS_PER_BULLET) -> str:
        """
        Truncate bullet point to maximum word count.
        
        Args:
            bullet: Original bullet text (string or dict with 'text' key)
            max_words: Maximum number of words (default: 8)
            
        Returns:
            Truncated bullet
        """
        # Handle both string bullets and dict bullets with 'text' key
        if isinstance(bullet, dict):
            bullet_text = bullet.get("text", str(bullet))
        else:
            bullet_text = str(bullet)
        
        words = bullet_text.split()
        if len(words) <= max_words:
            return bullet_text
        
        truncated = " ".join(words[:max_words])
        logger.info(
            "bullet_truncated",
            original_words=len(words),
            max_words=max_words,
            original=bullet_text[:50],
            truncated=truncated
        )
        return truncated
    
    @staticmethod
    def split_bullets(
        bullets: List[str],
        max_bullets: int = MAX_BULLETS,
        max_words_per_bullet: int = MAX_WORDS_PER_BULLET
    ) -> Tuple[List[str], List[str]]:
        """
        Split bullets into current slide and overflow.
        
        Truncates each bullet to max words and splits into groups of max bullets.
        
        Args:
            bullets: List of bullet points
            max_bullets: Maximum bullets per slide (default: 4)
            max_words_per_bullet: Maximum words per bullet (default: 8)
            
        Returns:
            Tuple of (current_slide_bullets, overflow_bullets)
        """
        # Truncate all bullets first
        truncated_bullets = [
            SlideContentParser.truncate_bullet(b, max_words_per_bullet)
            for b in bullets
        ]
        
        # Split into current and overflow
        current = truncated_bullets[:max_bullets]
        overflow = truncated_bullets[max_bullets:]
        
        if overflow:
            logger.info(
                "bullets_split",
                total_bullets=len(bullets),
                current_bullets=len(current),
                overflow_bullets=len(overflow)
            )
        
        return current, overflow
    
    @staticmethod
    def parse_slide_content(slide: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and correct slide content.
        
        Applies:
        - Title truncation
        - Bullet splitting and truncation
        
        Args:
            slide: Slide dictionary
            
        Returns:
            Corrected slide dictionary
        """
        corrected = deepcopy(slide)
        
        # Truncate title
        if "title" in corrected:
            corrected["title"] = SlideContentParser.truncate_title(corrected["title"])
        
        # Process bullets if present
        if "content" in corrected and "bullets" in corrected["content"]:
            bullets = corrected["content"]["bullets"]
            if bullets:
                current, overflow = SlideContentParser.split_bullets(bullets)
                corrected["content"]["bullets"] = current
                
                # Store overflow for potential new slide creation
                if overflow:
                    corrected["_overflow_bullets"] = overflow
        
        return corrected


# ---------------------------------------------------------------------------
# Validation Agent
# ---------------------------------------------------------------------------

class ValidationAgent:
    """
    Validation Agent - JSON structure validation and automatic error correction.
    
    Key responsibilities:
    1. Parse and validate Slide_JSON against v1.0.0 schema
    2. Truncate titles and bullets to content constraints
    3. Split slides when content exceeds layout bounds
    4. Validate visual_hint enum values
    5. Auto-correct common JSON errors (2 retry attempts)
    6. Ensure round-trip property: parse(format(parse(x))) == parse(x)
    """
    
    MAX_CORRECTION_ATTEMPTS = 2
    
    def __init__(self):
        """Initialize the Validation Agent."""
        self.schema_validator = Draft7Validator(SLIDE_JSON_SCHEMA)

    def normalise_slide_fields(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Normalise LLM output by migrating root-level fields into content{}.

        The LLM frequently places fields at the slide root instead of inside content:
        - bullets, highlight_text, icon_name, chart_type, subtitle, speaker_notes
        - chart_data, table_data, comparison_data
        - kpi_badges, left_panel_bullets
        - metric_value, metric_label, metric_trend

        This method runs FIRST before any other validation to ensure consistent structure.

        Args:
            data: Raw LLM-generated Slide_JSON

        Returns:
            Tuple of (normalised_data, corrections_count)
        """
        corrected = deepcopy(data)
        corrections = 0

        for i, slide in enumerate(corrected.get("slides", [])):
            content = slide.setdefault("content", {})

            # ── Migrate simple root-level fields into content ──────────────
            root_fields = [
                "bullets", "highlight_text", "icon_name", "chart_type",
                "subtitle", "speaker_notes", "transition",
                "metric_value", "metric_label", "metric_trend",
            ]
            for field in root_fields:
                if field in slide and field not in content:
                    content[field] = slide.pop(field)
                    corrections += 1
                    logger.debug("migrated_field_to_content", field=field, slide_number=i+1)

            # ── Migrate chart_data (multiple formats) ──────────────────────
            root_cd = slide.pop("chart_data", None)
            if root_cd is not None and not content.get("chart_data"):
                content["chart_data"] = root_cd
                corrections += 1
                logger.debug("migrated_chart_data_to_content", slide_number=i+1)

            # Migrate root-level "chart" object → content.chart_data
            root_chart = slide.pop("chart", None)
            if root_chart and isinstance(root_chart, dict) and not content.get("chart_data"):
                # Convert {labels: [...], datasets: [{data: [...]}]} → [{label, value}]
                labels = root_chart.get("labels", [])
                datasets = root_chart.get("datasets", [])
                values = datasets[0].get("data", []) if datasets else []
                if labels and values:
                    content["chart_data"] = [
                        {"label": str(lbl), "value": float(val)}
                        for lbl, val in zip(labels, values)
                    ]
                    corrections += 1
                    logger.info("migrated_root_chart_to_content", slide_number=i+1)
                if not content.get("chart_type") and root_chart.get("chart_type"):
                    content["chart_type"] = root_chart["chart_type"]
                    corrections += 1

            # ── Migrate table_data ──────────────────────────────────────────
            root_td = slide.pop("table_data", None)
            if root_td is not None and not content.get("table_data"):
                # Validate that table_data has proper structure
                if isinstance(root_td, dict) and root_td.get("headers") and root_td.get("rows"):
                    content["table_data"] = root_td
                    corrections += 1
                    logger.info(
                        "migrated_table_data_to_content",
                        slide_number=i+1,
                        headers_count=len(root_td.get("headers", [])),
                        rows_count=len(root_td.get("rows", []))
                    )
                else:
                    logger.warning(
                        "invalid_table_data_structure_ignored",
                        slide_number=i+1,
                        type=type(root_td).__name__,
                        has_headers=bool(root_td.get("headers") if isinstance(root_td, dict) else False),
                        has_rows=bool(root_td.get("rows") if isinstance(root_td, dict) else False)
                    )

            # Migrate root-level "table" object → content.table_data
            root_table = slide.pop("table", None)
            if root_table and isinstance(root_table, dict) and not content.get("table_data"):
                if root_table.get("headers"):
                    content["table_data"] = {
                        "headers": root_table.get("headers", []),
                        "rows": root_table.get("rows", []),
                    }
                    corrections += 1
                    logger.info("migrated_root_table_to_content", slide_number=i+1)

            # ── Migrate comparison_data ─────────────────────────────────────
            root_comp = slide.pop("comparison_data", None) or slide.pop("comparison", None)
            if root_comp and isinstance(root_comp, dict) and not content.get("comparison_data"):
                # Validate that comparison_data has proper structure
                has_left = root_comp.get("left_column") or root_comp.get("left")
                has_right = root_comp.get("right_column") or root_comp.get("right")
                if has_left and has_right:
                    content["comparison_data"] = root_comp
                    corrections += 1
                    logger.info(
                        "migrated_root_comparison_to_content",
                        slide_number=i+1,
                        has_left_column=bool(root_comp.get("left_column")),
                        has_right_column=bool(root_comp.get("right_column"))
                    )
                else:
                    logger.warning(
                        "invalid_comparison_data_structure_ignored",
                        slide_number=i+1,
                        has_left=bool(has_left),
                        has_right=bool(has_right)
                    )

            # ── Special case: kpi_badges → bullets (title slides) ──────────
            kpi = slide.pop("kpi_badges", None)
            if kpi and isinstance(kpi, list) and not content.get("bullets"):
                content["bullets"] = [
                    (b.get("label", "") + (f" — {b['description']}" if b.get("description") else ""))
                    if isinstance(b, dict) else str(b)
                    for b in kpi
                ]
                corrections += 1
                logger.info("migrated_kpi_badges_to_bullets", slide_number=i+1)

            # ── Special case: left_panel_bullets → bullets (chart slides) ──
            lpb = slide.pop("left_panel_bullets", None)
            if lpb and not content.get("bullets"):
                content["bullets"] = lpb
                corrections += 1
                logger.info("migrated_left_panel_bullets_to_bullets", slide_number=i+1)

            # ── Clean up other LLM-specific fields ─────────────────────────
            slide.pop("footer", None)
            slide.pop("layout_hint", None)
            slide.pop("slide_type", None)  # We use "type" not "slide_type"

            slide["content"] = content

        # Enforce layout variant diversity — no consecutive same-type slides with same variant
        for i in range(1, len(corrected.get("slides", []))):
            prev_slide = corrected["slides"][i - 1]
            curr_slide = corrected["slides"][i]
            prev_type = prev_slide.get("type", "content")
            curr_type = curr_slide.get("type", "content")
            if prev_type == curr_type:
                prev_variant = prev_slide.get("content", {}).get("layout_variant") or prev_slide.get("layout_variant")
                curr_variant = curr_slide.get("content", {}).get("layout_variant") or curr_slide.get("layout_variant")
                if prev_variant and curr_variant and prev_variant == curr_variant:
                    # Rotate to next available variant
                    valid_variants = LAYOUT_VARIANTS_BY_TYPE.get(curr_type, set())
                    if valid_variants:
                        alternatives = [v for v in valid_variants if v != curr_variant]
                        if alternatives:
                            new_variant = alternatives[0]
                            if "layout_variant" in curr_slide.get("content", {}):
                                curr_slide["content"]["layout_variant"] = new_variant
                            else:
                                curr_slide["layout_variant"] = new_variant
                            corrections += 1

        return corrected, corrections
    
    def validate_schema(self, data: Dict[str, Any]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate data against Slide_JSON schema.
        
        Args:
            data: Slide_JSON data to validate
            
        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        errors = []
        
        try:
            # Validate against schema
            validate(instance=data, schema=SLIDE_JSON_SCHEMA)
            return True, []
            
        except JsonSchemaValidationError as e:
            # Collect all validation errors
            for error in self.schema_validator.iter_errors(data):
                field_path = ".".join(str(p) for p in error.path) if error.path else "root"
                errors.append(
                    ValidationError(
                        field=field_path,
                        message=error.message,
                        severity="error",
                        auto_corrected=False
                    )
                )
            
            return False, errors
    
    def validate_visual_hints(self, data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate visual_hint enum values.
        
        Args:
            data: Slide_JSON data
            
        Returns:
            List of validation errors
        """
        errors = []
        valid_hints = {vh.value for vh in VisualHint}
        
        for i, slide in enumerate(data.get("slides", [])):
            visual_hint = slide.get("visual_hint")
            if visual_hint and visual_hint not in valid_hints:
                errors.append(
                    ValidationError(
                        field=f"slides[{i}].visual_hint",
                        message=f"Invalid visual_hint '{visual_hint}'. Must be one of: {', '.join(valid_hints)}",
                        severity="error",
                        auto_corrected=False
                    )
                )
        
        return errors
    
    def auto_correct_missing_fields(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Auto-correct missing required fields.
        
        Args:
            data: Slide_JSON data
            
        Returns:
            Tuple of (corrected_data, corrections_count)
        """
        corrected = deepcopy(data)
        corrections = 0
        
        # Ensure schema_version
        if "schema_version" not in corrected:
            corrected["schema_version"] = "1.0.0"
            corrections += 1
            logger.info("auto_corrected_schema_version")
        
        # Ensure presentation_id
        if "presentation_id" not in corrected:
            corrected["presentation_id"] = str(uuid4())
            corrections += 1
            logger.info("auto_corrected_presentation_id")
        
        # Ensure total_slides matches slides array
        if "slides" in corrected:
            actual_count = len(corrected["slides"])
            if "total_slides" not in corrected or corrected["total_slides"] != actual_count:
                corrected["total_slides"] = actual_count
                corrections += 1
                logger.info("auto_corrected_total_slides", count=actual_count)
        
        # Correct each slide
        for i, slide in enumerate(corrected.get("slides", [])):
            # Ensure slide_id
            if "slide_id" not in slide:
                slide["slide_id"] = str(uuid4())
                corrections += 1
            
            # Ensure slide_number
            if "slide_number" not in slide:
                slide["slide_number"] = i + 1
                corrections += 1
            
            # Ensure type — also check slide_type (LLM sometimes uses this field name)
            if "type" not in slide or slide["type"] not in [t.value for t in SlideType]:
                # Try slide_type first (Claude often returns this)
                slide_type_val = slide.get("slide_type", "")
                type_mapping = {
                    "title": "title", "title_slide": "title",
                    "content": "content", "content_slide": "content",
                    "chart": "chart", "chart_slide": "chart",
                    "table": "table", "table_slide": "table",
                    "comparison": "comparison", "comparison_slide": "comparison",
                    "metric": "metric", "metric_slide": "metric",
                }
                mapped = type_mapping.get(str(slide_type_val).lower(), "content")
                slide["type"] = mapped
                corrections += 1
            
            # Ensure title
            if "title" not in slide or slide["title"] == f"Slide {i + 1}":
                # Check if title is inside content (LLM sometimes puts it there)
                content_obj = slide.get("content", {})
                if isinstance(content_obj, dict) and content_obj.get("title"):
                    slide["title"] = content_obj.pop("title")
                    corrections += 1
                elif "title" not in slide:
                    slide["title"] = f"Slide {i + 1}"
                    corrections += 1

            # Extract subtitle from content if missing at root
            if "subtitle" not in slide:
                content_obj = slide.get("content", {})
                if isinstance(content_obj, dict) and content_obj.get("subtitle"):
                    slide["subtitle"] = content_obj.pop("subtitle")
                    corrections += 1
            
            # Ensure content object
            if "content" not in slide:
                slide["content"] = {}
                corrections += 1

            # ── Migrate root-level LLM fields into content ──────────────────
            # Claude often returns chart/table data at the slide root level
            # (e.g. slide["chart"], slide["table"]) instead of inside content.
            # Move them into content so the rest of the pipeline can find them.
            content = slide.setdefault("content", {})

            # Migrate root-level "chart" → content["chart_data"] + content["chart_type"]
            root_chart = slide.pop("chart", None)
            if root_chart and isinstance(root_chart, dict):
                if not content.get("chart_data"):
                    labels = root_chart.get("labels", [])
                    datasets = root_chart.get("datasets", [])
                    values = datasets[0].get("data", []) if datasets else []
                    if labels and values:
                        content["chart_data"] = [
                            {"label": lbl, "value": val}
                            for lbl, val in zip(labels, values)
                        ]
                        corrections += 1
                        logger.info("migrated_root_chart_to_content", slide_number=i+1)
                if not content.get("chart_type") and root_chart.get("chart_type"):
                    content["chart_type"] = root_chart["chart_type"]

            # Migrate root-level "table" → content["table_data"]
            root_table = slide.pop("table", None)
            if root_table and isinstance(root_table, dict) and root_table.get("headers"):
                if not content.get("table_data"):
                    content["table_data"] = {
                        "headers": root_table.get("headers", []),
                        "rows": root_table.get("rows", []),
                    }
                    corrections += 1
                    logger.info("migrated_root_table_to_content", slide_number=i+1)

            # Migrate root-level "comparison_data" or "comparison" → content["comparison_data"]
            root_comp = slide.pop("comparison_data", None) or slide.pop("comparison", None)
            if root_comp and isinstance(root_comp, dict):
                if not content.get("comparison_data"):
                    content["comparison_data"] = root_comp
                    corrections += 1
                    logger.info("migrated_root_comparison_to_content", slide_number=i+1)

            # Also handle comparison stored as a table (Claude sometimes does this)
            slide_type_raw = slide.get("slide_type", slide.get("type", ""))
            if str(slide_type_raw).lower() == "comparison" and root_table and isinstance(root_table, dict):
                if not content.get("comparison_data") and root_table.get("headers") and root_table.get("rows"):
                    # Convert table format to comparison_data format
                    headers = root_table.get("headers", [])
                    rows = root_table.get("rows", [])
                    if len(headers) >= 3 and rows:
                        left_bullets = [str(r[1]) for r in rows if len(r) > 1]
                        right_bullets = [str(r[2]) for r in rows if len(r) > 2]
                        content["comparison_data"] = {
                            "left_column": {"heading": headers[1] if len(headers) > 1 else "Option A", "bullets": left_bullets},
                            "right_column": {"heading": headers[2] if len(headers) > 2 else "Option B", "bullets": right_bullets},
                        }
                        corrections += 1
                        logger.info("migrated_table_to_comparison_data", slide_number=i+1)

            # Remove other root-level LLM-specific fields that don't belong in the schema
            slide.pop("footer", None)
            slide.pop("layout_hint", None)  # already handled above via visual_hint

            # ── Migrate root-level content fields into content dict ──────────
            # The LLM frequently places bullets, highlight_text, icon_name,
            # chart_type, left_panel_bullets, kpi_badges, subtitle at the slide
            # root instead of inside content{}. Migrate them now.
            content = slide.setdefault("content", {})

            for field in ("bullets", "highlight_text", "icon_name", "chart_type",
                          "subtitle", "speaker_notes",
                          "metric_value", "metric_label", "metric_trend"):
                if field in slide and field not in content:
                    content[field] = slide.pop(field)
                    corrections += 1

            # left_panel_bullets → content.bullets (chart slides)
            lpb = slide.pop("left_panel_bullets", None)
            if lpb and not content.get("bullets"):
                content["bullets"] = lpb
                corrections += 1

            # kpi_badges → content.bullets (title slides)
            kpi = slide.pop("kpi_badges", None)
            if kpi and isinstance(kpi, list) and not content.get("bullets"):
                content["bullets"] = [
                    (b.get("label", "") + (f" — {b['description']}" if b.get("description") else ""))
                    if isinstance(b, dict) else str(b)
                    for b in kpi
                ]
                corrections += 1

            # chart_data at root → content.chart_data
            root_cd = slide.pop("chart_data", None)
            if root_cd is not None and not content.get("chart_data"):
                content["chart_data"] = root_cd
                corrections += 1

            # table_data at root → content.table_data
            root_td = slide.pop("table_data", None)
            if root_td is not None and not content.get("table_data"):
                # Validate structure before migrating
                if isinstance(root_td, dict) and root_td.get("headers") and root_td.get("rows"):
                    content["table_data"] = root_td
                    corrections += 1
                    logger.debug(
                        "migrated_table_data_in_auto_correct",
                        slide_number=i+1,
                        headers=len(root_td.get("headers", [])),
                        rows=len(root_td.get("rows", []))
                    )
                else:
                    logger.warning(
                        "skipped_invalid_table_data_in_auto_correct",
                        slide_number=i+1
                    )

            slide["content"] = content
            
            # Ensure visual_hint
            if "visual_hint" not in slide:
                # Default visual hint based on slide type (use slide_type_raw for accuracy)
                st = str(slide.get("slide_type", slide.get("type", "content"))).lower()
                if st in ("title", "title_slide"):
                    slide["visual_hint"] = "centered"
                elif st in ("chart", "chart_slide"):
                    slide["visual_hint"] = "split-chart-right"
                elif st in ("table", "table_slide"):
                    slide["visual_hint"] = "split-table-left"
                elif st in ("comparison", "comparison_slide"):
                    slide["visual_hint"] = "two-column"
                else:
                    slide["visual_hint"] = "bullet-left"
                corrections += 1
                logger.info("auto_corrected_visual_hint", slide_number=i+1, visual_hint=slide["visual_hint"])
            
            # Ensure content has required data for visual slide types
            content = slide.get("content", {})
            slide_type = str(slide.get("slide_type", slide.get("type", "content"))).lower()
            # Normalize slide_type for comparison
            _type_norm = {
                "title_slide": "title", "content_slide": "content",
                "chart_slide": "chart", "table_slide": "table",
                "comparison_slide": "comparison",
            }
            slide_type = _type_norm.get(slide_type, slide_type)

            if slide_type == "chart":
                # Ensure chart_data is a non-empty list of {label, value} objects
                chart_data = content.get("chart_data")
                if not chart_data or not isinstance(chart_data, list) or len(chart_data) == 0:
                    # Generate fallback chart data from bullets or defaults
                    bullets = content.get("bullets", [])
                    if bullets:
                        import random
                        fallback = []
                        for b in bullets[:5]:
                            # Handle both string bullets and dict bullets with 'text' key
                            bullet_text = b.get("text", str(b)) if isinstance(b, dict) else str(b)
                            fallback.append({"label": bullet_text[:20], "value": round(random.uniform(30, 90), 1)})
                    else:
                        fallback = [
                            {"label": "Category A", "value": 42.5},
                            {"label": "Category B", "value": 67.3},
                            {"label": "Category C", "value": 55.1},
                            {"label": "Category D", "value": 78.9},
                            {"label": "Category E", "value": 61.2},
                        ]
                    content["chart_data"] = fallback
                    corrections += 1
                    logger.info("auto_corrected_chart_data", slide_number=i+1)
                # Ensure chart_type
                if not content.get("chart_type"):
                    content["chart_type"] = "bar"
                    corrections += 1
                # If chart slide has no chart_data at all, convert to content slide
                if not content.get("chart_data"):
                    slide["type"] = "content"
                    slide["visual_hint"] = "bullet-left"
                    corrections += 1
                    logger.info("converted_empty_chart_to_content", slide_number=i+1)
                slide["content"] = content

            elif slide_type == "table":
                # If table slide has no table_data, convert to content slide
                table_data = content.get("table_data")
                if not table_data or not isinstance(table_data, dict) or not table_data.get("headers"):
                    if content.get("bullets"):
                        # Has bullets but no table — just make it a content slide
                        slide["type"] = "content"
                        slide["visual_hint"] = "bullet-left"
                        corrections += 1
                        logger.info("converted_empty_table_to_content", slide_number=i+1)
                    else:
                        # No bullets and no table — generate minimal fallback
                        fallback = {
                            "headers": ["Metric", "Value", "Trend"],
                            "rows": [
                                ["Revenue Growth", "12.5%", "↑"],
                                ["Market Share", "23.4%", "↑"],
                                ["Cost Reduction", "8.2%", "↓"],
                            ]
                        }
                        content["table_data"] = fallback
                        corrections += 1
                        logger.info("auto_corrected_table_data", slide_number=i+1)
                slide["content"] = content

            elif slide_type == "comparison":
                # If comparison slide has no comparison_data, convert to content slide
                comparison_data = content.get("comparison_data")
                if not comparison_data or not isinstance(comparison_data, dict) or \
                   not comparison_data.get("left_column") or not comparison_data.get("right_column"):
                    if content.get("bullets"):
                        # Has bullets but no comparison — just make it a content slide
                        slide["type"] = "content"
                        slide["visual_hint"] = "bullet-left"
                        corrections += 1
                        logger.info("converted_empty_comparison_to_content", slide_number=i+1)
                    else:
                        # No bullets and no comparison — generate minimal fallback
                        content["comparison_data"] = {
                            "left_column": {"heading": "Current State", "bullets": ["Current approach", "Existing process"]},
                            "right_column": {"heading": "Future State", "bullets": ["Improved approach", "New process"]}
                        }
                        corrections += 1
                        logger.info("auto_corrected_comparison_data", slide_number=i+1)
                slide["content"] = content
            
            # Ensure layout_constraints
            if "layout_constraints" not in slide:
                slide["layout_constraints"] = {
                    "max_content_density": MAX_CONTENT_DENSITY,
                    "min_whitespace_ratio": MIN_WHITESPACE_RATIO
                }
                corrections += 1
            
            # Ensure metadata
            if "metadata" not in slide:
                slide["metadata"] = {
                    "generated_at": datetime.utcnow().isoformat(),
                    "provider_used": "unknown",
                    "quality_score": 1.0
                }
                corrections += 1
        
        return corrected, corrections
    
    def validate_content_completeness(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Validate that every slide has the content its type requires.

        Runs AFTER normalise_slide_fields() and auto_correct_missing_fields() so
        all root-level fields have already been migrated into content{}.

        For each slide type, checks:
        - content: has bullets (generates from title if missing)
        - chart: has valid chart_data (list or {categories, series}), has chart_type
        - table: has table_data with headers and rows
        - comparison: has comparison_data with left_column and right_column
        - metric: has metric_value
        - title: has subtitle or bullets

        Also validates:
        - chart_data format consistency
        - table_data row/column alignment
        - comparison_data column structure
        - visual_hint matches slide type

        Args:
            data: Slide_JSON data (already normalised)

        Returns:
            Tuple of (validated_data, corrections_count)
        """
        import random
        corrected = deepcopy(data)
        corrections = 0

        # Type → expected visual_hint
        TYPE_TO_HINT = {
            "title": "centered",
            "content": "bullet-left",
            "chart": "split-chart-right",
            "table": "split-table-left",
            "comparison": "two-column",
            "metric": "highlight-metric",
        }

        for i, slide in enumerate(corrected.get("slides", [])):
            slide_type = slide.get("type", "content")
            content = slide.setdefault("content", {})
            slide_num = slide.get("slide_number", i + 1)

            # ── Enforce visual_hint matches type ──────────────────────────
            expected_hint = TYPE_TO_HINT.get(slide_type)
            if expected_hint and slide.get("visual_hint") != expected_hint:
                slide["visual_hint"] = expected_hint
                corrections += 1
                logger.info("corrected_visual_hint_mismatch",
                            slide_number=slide_num, slide_type=slide_type,
                            corrected_hint=expected_hint)

            # ── Validate transition ────────────────────────────────────────
            transition = content.get("transition", "fade")
            if transition not in ("fade", "slide", "none"):
                content["transition"] = "fade"
                corrections += 1

            # ── Per-type content validation ────────────────────────────────

            if slide_type == "title":
                # Title slides need subtitle or bullets for KPI badges
                if not content.get("subtitle") and not content.get("bullets"):
                    content["subtitle"] = "Strategic Analysis for Senior Leadership"
                    corrections += 1
                    logger.info("generated_title_subtitle", slide_number=slide_num)
                
                # Limit title slide bullets to prevent overlap (max 4 KPI badges)
                bullets = content.get("bullets", [])
                if len(bullets) > 4:
                    content["bullets"] = bullets[:4]
                    corrections += 1
                    logger.warning(
                        "truncated_title_slide_bullets",
                        slide_number=slide_num,
                        original_count=len(bullets),
                        truncated_to=4
                    )
                
                # Ensure subtitle is not too long (max 60 characters)
                subtitle = content.get("subtitle", "")
                if len(subtitle) > 60:
                    content["subtitle"] = subtitle[:57] + "..."
                    corrections += 1
                    logger.warning(
                        "truncated_title_subtitle",
                        slide_number=slide_num,
                        original_length=len(subtitle)
                    )

            elif slide_type == "content":
                # Content slides must have bullets
                bullets = content.get("bullets")
                if not bullets or not isinstance(bullets, list) or len(bullets) == 0:
                    # Generate from title words as placeholder
                    title = slide.get("title", "")
                    content["bullets"] = [
                        f"Key insight: {title}",
                        "Supporting evidence and data points",
                        "Strategic implications for stakeholders",
                        "Recommended next steps and actions",
                    ]
                    corrections += 1
                    logger.info("generated_content_bullets", slide_number=slide_num)
                # Ensure bullets is a list of strings
                if isinstance(content.get("bullets"), list):
                    content["bullets"] = [str(b) for b in content["bullets"] if b]
                
                # CRITICAL: Enforce minimum bullet count (MIN_BULLETS = 2)
                bullets = content.get("bullets", [])
                original_count = len(bullets)
                if original_count < MIN_BULLETS:
                    title = slide.get("title", "")
                    # Generate contextual bullets based on title
                    title_words = title.split()
                    
                    # Generate additional bullets to meet minimum
                    while len(bullets) < MIN_BULLETS:
                        if len(bullets) == 0:
                            # First bullet: extract key concept from title
                            if len(title_words) >= 3:
                                bullets.append(f"{' '.join(title_words[:3])} drives strategic value")
                            else:
                                bullets.append(f"Key insight: {title}")
                        elif len(bullets) == 1:
                            # Second bullet: add supporting context
                            if len(title_words) >= 2:
                                bullets.append(f"Analysis shows {' '.join(title_words[-2:])} impact")
                            else:
                                bullets.append("Supporting evidence and data analysis")
                        else:
                            # Additional bullets if needed
                            bullets.append(f"Strategic implication {len(bullets)}")
                    
                    content["bullets"] = bullets
                    corrections += 1
                    logger.warning(
                        "enforced_minimum_bullets",
                        slide_number=slide_num,
                        slide_title=title[:50],
                        original_count=original_count,
                        enforced_count=len(bullets),
                        min_required=MIN_BULLETS
                    )

            elif slide_type == "chart":
                # Chart slides must have valid chart_data
                chart_data = content.get("chart_data")
                chart_type = content.get("chart_type", "bar")

                # Normalise [{label, value}] format — already a list, good
                # Normalise {categories, series} format — also good
                # Handle edge cases:
                if chart_data is None or chart_data == {} or chart_data == []:
                    # Generate fallback from bullets if available
                    bullets = content.get("bullets", [])
                    if bullets:
                        seed = hash(slide.get("title", "")) % 1000
                        rng = random.Random(seed)
                        chart_data = []
                        for b in bullets[:6]:
                            # Handle both string bullets and dict bullets with 'text' key
                            bullet_text = b.get("text", str(b)) if isinstance(b, dict) else str(b)
                            label = bullet_text.split(":")[0][:25].strip()
                            chart_data.append({"label": label, "value": round(rng.uniform(20, 90), 1)})
                    else:
                        chart_data = [
                            {"label": "Category A", "value": 42.5},
                            {"label": "Category B", "value": 67.3},
                            {"label": "Category C", "value": 55.1},
                            {"label": "Category D", "value": 78.9},
                            {"label": "Category E", "value": 61.2},
                        ]
                    content["chart_data"] = chart_data
                    corrections += 1
                    logger.info("generated_chart_data_fallback", slide_number=slide_num)

                # Validate list format: [{label, value}]
                if isinstance(chart_data, list):
                    valid_items = []
                    for item in chart_data:
                        if isinstance(item, dict):
                            label = str(item.get("label", item.get("name", item.get("x", "Item"))))
                            value = item.get("value", item.get("y", item.get("count", 0)))
                            try:
                                value = float(value)
                            except (TypeError, ValueError):
                                value = 0.0
                            valid_items.append({"label": label, "value": value})
                        elif isinstance(item, (int, float)):
                            valid_items.append({"label": f"Item {len(valid_items)+1}", "value": float(item)})
                    if valid_items:
                        content["chart_data"] = valid_items
                    else:
                        content["chart_data"] = [{"label": "Data", "value": 50.0}]
                    corrections += 1

                # Validate dict format: {categories, series}
                elif isinstance(chart_data, dict):
                    categories = chart_data.get("categories", [])
                    series = chart_data.get("series", [])
                    if not categories or not series:
                        # Convert to label/value list if possible
                        if categories and not series:
                            seed = hash(slide.get("title", "")) % 1000
                            rng = random.Random(seed)
                            content["chart_data"] = [
                                {"label": str(c), "value": round(rng.uniform(20, 90), 1)}
                                for c in categories[:8]
                            ]
                            corrections += 1
                    else:
                        # Ensure series values are numeric
                        for s in series:
                            if "values" in s:
                                s["values"] = [
                                    float(v) if v is not None else 0.0
                                    for v in s["values"]
                                ]

                # Ensure chart_type is valid
                valid_chart_types = {"bar", "line", "pie", "area", "stacked_bar", "donut", "scatter",
                                     "column", "bar_horizontal", "line_smooth", "stacked_area"}
                if chart_type not in valid_chart_types:
                    content["chart_type"] = "bar"
                    corrections += 1
                else:
                    content["chart_type"] = chart_type

                # Ensure bullets exist for left panel
                if not content.get("bullets"):
                    content["bullets"] = [
                        "Key trend visible in the data above",
                        "Year-over-year growth accelerating",
                        "Market leader position strengthening",
                    ]
                    corrections += 1

            elif slide_type == "table":
                # Table slides must have table_data with headers and rows
                table_data = content.get("table_data")

                if not table_data or not isinstance(table_data, dict):
                    table_data = {}

                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])

                if not headers:
                    # Generate from bullets if available
                    bullets = content.get("bullets", [])
                    if bullets:
                        headers = ["Item", "Details", "Impact"]
                        rows = [
                            [
                                (b.get("text", str(b)) if isinstance(b, dict) else str(b))[:40],
                                "—",
                                "High"
                            ]
                            for b in bullets[:6]
                        ]
                    else:
                        headers = ["Metric", "Current", "Target", "Gap"]
                        rows = [
                            ["Revenue Growth", "12.5%", "18.0%", "-5.5pp"],
                            ["Market Share", "23.4%", "30.0%", "-6.6pp"],
                            ["Cost Efficiency", "68%", "75%", "-7pp"],
                            ["Customer NPS", "34", "55", "-21 pts"],
                        ]
                    content["table_data"] = {"headers": headers, "rows": rows}
                    corrections += 1
                    logger.warning(
                        "generated_table_data_fallback",
                        slide_number=slide_num,
                        slide_title=slide.get("title", "")[:50],
                        headers_count=len(headers),
                        rows_count=len(rows)
                    )
                else:
                    # Validate row/column alignment
                    num_cols = len(headers)
                    fixed_rows = []
                    for row in rows:
                        if isinstance(row, list):
                            # Pad or trim to match header count
                            if len(row) < num_cols:
                                row = row + ["—"] * (num_cols - len(row))
                            elif len(row) > num_cols:
                                row = row[:num_cols]
                            fixed_rows.append([str(cell) for cell in row])
                        elif isinstance(row, dict):
                            # Convert dict row to list
                            fixed_rows.append([str(row.get(h, "—")) for h in headers])
                    if fixed_rows != rows:
                        content["table_data"] = {"headers": [str(h) for h in headers], "rows": fixed_rows}
                        corrections += 1
                
                # CRITICAL: Ensure bullets exist as fallback for rendering
                if not content.get("bullets"):
                    content["bullets"] = [
                        "Key data points shown in table above",
                        "Comparative analysis across metrics",
                    ]
                    corrections += 1
                    logger.info("added_fallback_bullets_to_table", slide_number=slide_num)

            elif slide_type == "comparison":
                # Comparison slides must have comparison_data with left_column and right_column
                comparison_data = content.get("comparison_data")

                if not comparison_data or not isinstance(comparison_data, dict):
                    comparison_data = {}

                # Support both formats and normalise to {left_column, right_column}
                has_new_format = "left_column" in comparison_data and "right_column" in comparison_data
                has_old_format = "left" in comparison_data or "right" in comparison_data

                if not has_new_format and not has_old_format:
                    # Generate from bullets
                    bullets = content.get("bullets", [])
                    mid = max(1, len(bullets) // 2)
                    content["comparison_data"] = {
                        "left_column": {
                            "heading": "Current State",
                            "bullets": bullets[:mid] if bullets else [
                                "Existing manual processes",
                                "High operational costs",
                                "Limited scalability",
                            ]
                        },
                        "right_column": {
                            "heading": "Future State",
                            "bullets": bullets[mid:] if len(bullets) > mid else [
                                "Automated AI-driven workflows",
                                "40% cost reduction achieved",
                                "Unlimited cloud scalability",
                            ]
                        }
                    }
                    corrections += 1
                    logger.warning(
                        "generated_comparison_data_fallback",
                        slide_number=slide_num,
                        slide_title=slide.get("title", "")[:50],
                        left_bullets=len(content["comparison_data"]["left_column"]["bullets"]),
                        right_bullets=len(content["comparison_data"]["right_column"]["bullets"])
                    )
                elif has_new_format:
                    # Validate left_column and right_column structure
                    for col_key in ("left_column", "right_column"):
                        col = comparison_data.get(col_key, {})
                        if not isinstance(col, dict):
                            comparison_data[col_key] = {"heading": col_key.replace("_", " ").title(), "bullets": [str(col)]}
                            corrections += 1
                        elif col.get("items") and isinstance(col["items"], list):
                            # Rich item format: [{ icon, title, description }] — preserve as-is
                            # Also generate bullets fallback for backward compatibility
                            if not col.get("bullets"):
                                col["bullets"] = [
                                    item.get("title", str(item)) if isinstance(item, dict) else str(item)
                                    for item in col["items"]
                                ]
                        elif not col.get("bullets"):
                            col["bullets"] = ["Key point 1", "Key point 2", "Key point 3"]
                            corrections += 1
                        elif not isinstance(col["bullets"], list):
                            col["bullets"] = [str(col["bullets"])]
                            corrections += 1
                    content["comparison_data"] = comparison_data
                elif has_old_format:
                    # Convert old format to new format
                    content["comparison_data"] = {
                        "left_column": {
                            "heading": comparison_data.get("left_title", "Option A"),
                            "bullets": comparison_data.get("left", ["Point 1", "Point 2"])
                        },
                        "right_column": {
                            "heading": comparison_data.get("right_title", "Option B"),
                            "bullets": comparison_data.get("right", ["Point 1", "Point 2"])
                        }
                    }
                    corrections += 1
                    logger.info("normalised_comparison_old_to_new_format", slide_number=slide_num)
                
                # CRITICAL: Ensure bullets exist as fallback for rendering
                if not content.get("bullets"):
                    content["bullets"] = [
                        "Comparative analysis shown above",
                        "Key differences highlighted",
                    ]
                    corrections += 1
                    logger.info("added_fallback_bullets_to_comparison", slide_number=slide_num)

            elif slide_type == "metric":
                # Metric slides must have metric_value
                if not content.get("metric_value"):
                    # Try to extract from title or bullets
                    title = slide.get("title", "")
                    # Look for numbers in title
                    import re as _re
                    numbers = _re.findall(r'[\$€£]?[\d,]+\.?\d*[%BMK]?', title)
                    if numbers:
                        content["metric_value"] = numbers[0]
                    else:
                        content["metric_value"] = "N/A"
                    corrections += 1
                    logger.info("generated_metric_value", slide_number=slide_num)

                if not content.get("metric_label"):
                    content["metric_label"] = slide.get("title", "Key Performance Indicator")[:50]
                    corrections += 1

                if not content.get("metric_trend"):
                    content["metric_trend"] = "See analysis below"
                    corrections += 1

                if not content.get("bullets"):
                    content["bullets"] = [
                        "Performance tracking against strategic targets",
                        "Year-over-year comparison and trend analysis",
                        "Industry benchmark positioning",
                    ]
                    corrections += 1

            # ── Ensure highlight_text on all non-title slides ──────────────
            if slide_type != "title" and not content.get("highlight_text"):
                title = slide.get("title", "")
                content["highlight_text"] = f"Key insight: {title[:80]}" if title else "See detailed analysis above"
                corrections += 1

            slide["content"] = content

        if corrections > 0:
            logger.info("content_completeness_corrections", total=corrections,
                        slide_count=len(corrected.get("slides", [])))

        return corrected, corrections

    def auto_correct_wrong_types(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Auto-correct wrong field types.
        
        Args:
            data: Slide_JSON data
            
        Returns:
            Tuple of (corrected_data, corrections_count)
        """
        corrected = deepcopy(data)
        corrections = 0
        
        # Correct total_slides type
        if "total_slides" in corrected and not isinstance(corrected["total_slides"], int):
            try:
                corrected["total_slides"] = int(corrected["total_slides"])
                corrections += 1
                logger.info("auto_corrected_total_slides_type")
            except (ValueError, TypeError):
                pass
        
        # Correct slide types
        for i, slide in enumerate(corrected.get("slides", [])):
            # Correct slide_number type
            if "slide_number" in slide and not isinstance(slide["slide_number"], int):
                try:
                    slide["slide_number"] = int(slide["slide_number"])
                    corrections += 1
                except (ValueError, TypeError):
                    slide["slide_number"] = i + 1
                    corrections += 1
            
            # Correct type enum
            if "type" in slide and slide["type"] not in [t.value for t in SlideType]:
                # Try to map common variations
                type_mapping = {
                    "title_slide": "title",
                    "content_slide": "content",
                    "chart_slide": "chart",
                    "table_slide": "table",
                    "comparison_slide": "comparison"
                }
                mapped_type = type_mapping.get(slide["type"].lower(), "content")
                slide["type"] = mapped_type
                corrections += 1
                logger.info("auto_corrected_slide_type", original=slide["type"], corrected=mapped_type)
            
            # Correct visual_hint enum
            if "visual_hint" in slide and slide["visual_hint"] not in [vh.value for vh in VisualHint]:
                # Try to map common variations
                hint_mapping = {
                    "center": "centered",
                    "bullets": "bullet-left",
                    "chart": "split-chart-right",
                    "table": "split-table-left",
                    "comparison": "two-column",
                    "metric": "highlight-metric"
                }
                mapped_hint = hint_mapping.get(slide["visual_hint"].lower(), "bullet-left")
                slide["visual_hint"] = mapped_hint
                corrections += 1
                logger.info("auto_corrected_visual_hint", original=slide["visual_hint"], corrected=mapped_hint)
            
            # Correct content field if it's a list instead of a dict
            if "content" in slide:
                content = slide["content"]
                if isinstance(content, list):
                    # LLM returned content as a list directly, convert to {"bullets": list}
                    slide["content"] = {"bullets": content}
                    corrections += 1
                    logger.info("auto_corrected_content_list_to_dict", slide_number=slide.get("slide_number", i+1))
                elif not isinstance(content, dict):
                    # Content is neither list nor dict, create empty dict
                    slide["content"] = {}
                    corrections += 1
                    logger.info("auto_corrected_content_invalid_type", slide_number=slide.get("slide_number", i+1), type=type(content).__name__)
        
        return corrected, corrections
    
    def infer_slide_types(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Intelligently infer slide types based on content.
        
        This fixes the issue where LLMs generate all slides as "content" type.
        Infers the correct type based on:
        - First slide → "title"
        - Has chart_data → "chart"
        - Has table_data → "table"
        - Has comparison_data → "comparison"
        - Has metric_value → "metric"
        - Otherwise → "content"
        
        Args:
            data: Slide_JSON data
            
        Returns:
            Tuple of (corrected_data, corrections_count)
        """
        corrected = deepcopy(data)
        corrections = 0
        
        slides = corrected.get("slides", [])
        if not slides:
            return corrected, corrections
        
        for i, slide in enumerate(slides):
            original_type = slide.get("type", "content")
            inferred_type = original_type
            content = slide.get("content", {})
            
            # Rule 1: First slide MUST ALWAYS be "title" - remove any data viz fields
            if i == 0:
                inferred_type = "title"
                # Remove chart/table/comparison data from first slide - it should only have bullets/subtitle
                if content.get("chart_data"):
                    content.pop("chart_data", None)
                    logger.info("removed_chart_data_from_title_slide", slide_number=1)
                if content.get("table_data"):
                    content.pop("table_data", None)
                    logger.info("removed_table_data_from_title_slide", slide_number=1)
                if content.get("comparison_data"):
                    content.pop("comparison_data", None)
                    logger.info("removed_comparison_data_from_title_slide", slide_number=1)
            
            # Rules 2-5: Only apply to non-first slides
            if i > 0:
                # Rule 2: Has chart_data → "chart"
                if content.get("chart_data") and original_type == "content":
                    inferred_type = "chart"
                
                # Rule 3: Has table_data → "table"
                if content.get("table_data") and original_type == "content":
                    inferred_type = "table"
                
                # Rule 4: Has comparison_data → "comparison"
                if content.get("comparison_data") and original_type == "content":
                    inferred_type = "comparison"
                
                # Rule 5: Has metric_value → "metric"
                if content.get("metric_value") and original_type == "content":
                    inferred_type = "metric"
            
            # Rule 6: Title contains keywords suggesting chart/table
            # Only applies to slides after the first
            title_lower = slide.get("title", "").lower()
            if i > 0 and original_type == "content" and not content.get("chart_data"):
                if any(keyword in title_lower for keyword in ["chart", "graph", "trend", "growth", "rate", "comparison", "vs", "versus"]):
                    # Check if there's numeric data in bullets that could be charted
                    bullets = content.get("bullets", [])
                    if bullets and any(any(char.isdigit() for char in str(b)) for b in bullets):
                        inferred_type = "chart"
            
            if i > 0 and original_type == "content" and not content.get("table_data"):
                if any(keyword in title_lower for keyword in ["table", "matrix", "breakdown", "kpi", "metrics", "performance indicators"]):
                    inferred_type = "table"
            
            # Apply the inferred type
            if inferred_type != original_type:
                slide["type"] = inferred_type
                corrections += 1
                logger.info(
                    "inferred_slide_type",
                    slide_number=i + 1,
                    original=original_type,
                    inferred=inferred_type,
                    title=slide.get("title", "")[:50]
                )
        
        return corrected, corrections
    
    def calculate_content_density(self, slide: Dict[str, Any]) -> float:
        """
        Calculate content density for a slide (0.0 to 1.0).
        
        Estimates how much of the slide is filled with text content.
        Higher values = more crowded, lower values = more whitespace.
        
        Args:
            slide: Slide dictionary
            
        Returns:
            Content density ratio (0.0 to 1.0)
        """
        content = slide.get("content", {})
        slide_type = slide.get("type", "content")
        
        # Base density calculation on text content
        total_chars = 0
        
        # Title contributes to density
        title = slide.get("title", "")
        total_chars += len(title)
        
        # Bullets contribute most to density
        bullets = content.get("bullets", [])
        for bullet in bullets:
            total_chars += len(str(bullet))
        
        # Subtitle/highlight text
        subtitle = content.get("subtitle", "")
        highlight = content.get("highlight_text", "")
        total_chars += len(subtitle) + len(highlight)
        
        # Chart/table/comparison data adds moderate density
        if slide_type == "chart" and content.get("chart_data"):
            total_chars += 100  # Fixed penalty for chart
        elif slide_type == "table" and content.get("table_data"):
            table_data = content["table_data"]
            headers = table_data.get("headers", [])
            rows = table_data.get("rows", [])
            total_chars += len(" ".join(str(h) for h in headers))
            for row in rows:
                total_chars += len(" ".join(str(cell) for cell in row))
        elif slide_type == "comparison" and content.get("comparison_data"):
            comp = content["comparison_data"]
            left = comp.get("left_column", {})
            right = comp.get("right_column", {})
            total_chars += len(left.get("heading", "")) + len(right.get("heading", ""))
            total_chars += sum(len(str(b)) for b in left.get("bullets", []))
            total_chars += sum(len(str(b)) for b in right.get("bullets", []))
        
        # Estimate density based on character count
        # Typical slide can comfortably hold ~400-500 chars
        # MAX_CONTENT_DENSITY = 0.75 means we allow up to ~600 chars
        MAX_COMFORTABLE_CHARS = 500
        density = min(1.0, total_chars / MAX_COMFORTABLE_CHARS)
        
        return density
    
    def enforce_content_density(self, slide: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Enforce content density limits to prevent overflow.
        
        If content density exceeds MAX_CONTENT_DENSITY (0.75), reduces content:
        - Truncates bullets to MAX_BULLETS (4)
        - Truncates each bullet to MAX_WORDS_PER_BULLET (8)
        - Truncates title to MAX_TITLE_WORDS (8)
        
        Args:
            slide: Slide dictionary
            
        Returns:
            Tuple of (corrected_slide, was_modified)
        """
        density = self.calculate_content_density(slide)
        
        if density <= MAX_CONTENT_DENSITY:
            return slide, False
        
        # Content is too dense, apply reductions
        corrected = deepcopy(slide)
        content = corrected.get("content", {})
        
        # 1. Truncate title
        title = corrected.get("title", "")
        truncated_title = SlideContentParser.truncate_title(title, MAX_TITLE_WORDS)
        if truncated_title != title:
            corrected["title"] = truncated_title
        
        # 2. Truncate bullets
        bullets = content.get("bullets", [])
        if bullets:
            # First, truncate each bullet to max words
            truncated_bullets = [
                SlideContentParser.truncate_bullet(b, MAX_WORDS_PER_BULLET)
                for b in bullets
            ]
            # Then, limit to max bullet count
            if len(truncated_bullets) > MAX_BULLETS:
                truncated_bullets = truncated_bullets[:MAX_BULLETS]
            
            content["bullets"] = truncated_bullets
            corrected["content"] = content
        
        # 3. Truncate highlight text if present
        highlight = content.get("highlight_text", "")
        if highlight:
            words = highlight.split()
            if len(words) > 15:  # Max 15 words for highlight
                content["highlight_text"] = " ".join(words[:15])
                corrected["content"] = content
        
        # Recalculate density
        new_density = self.calculate_content_density(corrected)
        
        logger.warning(
            "content_density_enforced",
            slide_number=slide.get("slide_number", 0),
            original_density=round(density, 2),
            new_density=round(new_density, 2),
            max_allowed=MAX_CONTENT_DENSITY
        )
        
        return corrected, True
    
    def apply_content_constraints(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Apply content constraints and split slides if needed.
        
        Args:
            data: Slide_JSON data
            
        Returns:
            Tuple of (corrected_data, overflow_slides)
        """
        corrected = deepcopy(data)
        overflow_slides = []

        # Guard: if slides key is missing, return as-is
        if "slides" not in corrected:
            return corrected, overflow_slides
        
        for i, slide in enumerate(corrected.get("slides", [])):
            # First, enforce content density to prevent overflow
            slide, was_modified = self.enforce_content_density(slide)
            if was_modified:
                logger.info(
                    "slide_content_reduced_for_density",
                    slide_number=i + 1,
                    title=slide.get("title", "")[:50]
                )
            
            # Parse and correct slide content
            parsed_slide = SlideContentParser.parse_slide_content(slide)
            
            # Check for overflow bullets
            if "_overflow_bullets" in parsed_slide:
                overflow_bullets = parsed_slide.pop("_overflow_bullets")
                
                # Create new slide for overflow
                overflow_slide = {
                    "slide_id": str(uuid4()),
                    "slide_number": i + 2,  # Will be renumbered later
                    "type": slide["type"],
                    "title": f"{slide['title']} (continued)",
                    "content": {
                        "bullets": overflow_bullets
                    },
                    "visual_hint": slide["visual_hint"],
                    "layout_constraints": slide.get("layout_constraints", {
                        "max_content_density": MAX_CONTENT_DENSITY,
                        "min_whitespace_ratio": MIN_WHITESPACE_RATIO
                    }),
                    "metadata": slide.get("metadata", {
                        "generated_at": datetime.utcnow().isoformat(),
                        "provider_used": "unknown",
                        "quality_score": 1.0
                    })
                }
                
                overflow_slides.append((i + 1, overflow_slide))
                logger.info("slide_split_created", original_slide=i+1, overflow_bullets=len(overflow_bullets))
            
            # Update slide with parsed content
            corrected["slides"][i] = parsed_slide
        
        # Insert overflow slides
        for insert_index, overflow_slide in reversed(overflow_slides):
            corrected["slides"].insert(insert_index, overflow_slide)
        
        # Renumber all slides
        for i, slide in enumerate(corrected["slides"]):
            slide["slide_number"] = i + 1
        
        # Add beautiful "Thank You" slide at the end
        thank_you_slide = {
            "slide_id": str(uuid4()),
            "slide_number": len(corrected["slides"]) + 1,
            "type": "title",  # Use title type for beautiful dark background
            "title": "Thank You",
            "content": {
                "subtitle": "Questions & Discussion",
                "bullets": [],
                "icon_name": "check-circle",
            },
            "visual_hint": "centered",
            "layout_constraints": {
                "max_content_density": MAX_CONTENT_DENSITY,
                "min_whitespace_ratio": MIN_WHITESPACE_RATIO
            },
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "provider_used": "system",
                "quality_score": 10.0
            }
        }
        corrected["slides"].append(thank_you_slide)
        logger.info("thank_you_slide_added", slide_number=len(corrected["slides"]))
        
        # Update total_slides
        corrected["total_slides"] = len(corrected["slides"])
        
        return corrected, overflow_slides
    
    def validate_layout_instructions(self, data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate that layout_instructions in each slide reference valid design token names.

        Checks:
        - Spacing instruction values must be valid spacing token names
        - Typography instruction values must be valid typography token names
        - Theme instruction values must be valid theme names

        Args:
            data: Slide_JSON data

        Returns:
            List of validation errors (severity="warning" — non-blocking)
        """
        errors = []

        for i, slide in enumerate(data.get("slides", [])):
            instructions: Dict[str, str] = slide.get("layout_instructions") or {}
            if not isinstance(instructions, dict):
                errors.append(
                    ValidationError(
                        field=f"slides[{i}].layout_instructions",
                        message="layout_instructions must be an object mapping string keys to string token names",
                        severity="warning",
                        auto_corrected=False,
                    )
                )
                continue

            for key, value in instructions.items():
                if not isinstance(value, str):
                    errors.append(
                        ValidationError(
                            field=f"slides[{i}].layout_instructions.{key}",
                            message=f"Token value must be a string, got {type(value).__name__}",
                            severity="warning",
                            auto_corrected=False,
                        )
                    )
                    continue

                if key in SPACING_INSTRUCTION_KEYS:
                    if value not in VALID_SPACING_TOKENS:
                        errors.append(
                            ValidationError(
                                field=f"slides[{i}].layout_instructions.{key}",
                                message=(
                                    f"'{value}' is not a valid spacing token. "
                                    f"Valid tokens: {sorted(VALID_SPACING_TOKENS)}"
                                ),
                                severity="warning",
                                auto_corrected=False,
                            )
                        )
                elif key in TYPOGRAPHY_INSTRUCTION_KEYS:
                    if value not in VALID_TYPOGRAPHY_TOKENS:
                        errors.append(
                            ValidationError(
                                field=f"slides[{i}].layout_instructions.{key}",
                                message=(
                                    f"'{value}' is not a valid typography token. "
                                    f"Valid tokens: {sorted(VALID_TYPOGRAPHY_TOKENS)}"
                                ),
                                severity="warning",
                                auto_corrected=False,
                            )
                        )
                elif key in THEME_INSTRUCTION_KEYS:
                    if value not in VALID_THEME_NAMES:
                        errors.append(
                            ValidationError(
                                field=f"slides[{i}].layout_instructions.{key}",
                                message=(
                                    f"'{value}' is not a valid theme name. "
                                    f"Valid themes: {sorted(VALID_THEME_NAMES)}"
                                ),
                                severity="warning",
                                auto_corrected=False,
                            )
                        )

        if errors:
            logger.warning(
                "layout_instruction_token_errors",
                count=len(errors),
                fields=[e.field for e in errors],
            )

        return errors

    # ------------------------------------------------------------------
    # Code-mode and Hybrid-mode validation
    # ------------------------------------------------------------------

    @staticmethod
    def strip_code_fences(raw: str) -> str:
        """
        Strip markdown code fences from raw LLM response text.

        Removes ```json, ```javascript, ``` wrappers that LLMs commonly
        add around their output.

        Args:
            raw: Raw LLM response string

        Returns:
            Cleaned string with code fences removed
        """
        stripped = raw.strip()
        # Remove opening fence (```json, ```javascript, ```js, ```)
        stripped = re.sub(r'^```(?:json|javascript|js)?\s*\n?', '', stripped)
        # Remove closing fence
        stripped = re.sub(r'\n?```\s*$', '', stripped)
        return stripped.strip()

    def validate_code_slide(self, slide: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate a single code-mode slide.

        Checks:
        - Required fields: slide_id, slide_number, type, title, speaker_notes, render_code
        - render_code is a non-empty string
        - render_code length <= 50,000 characters
        - render_code contains at least one pptxgenjs API call pattern

        Args:
            slide: A single slide dictionary

        Returns:
            List of validation errors for this slide
        """
        errors: List[ValidationError] = []
        slide_id = slide.get("slide_id", "unknown")

        # Check required fields
        for field in CODE_SLIDE_REQUIRED_FIELDS:
            if field not in slide:
                errors.append(
                    ValidationError(
                        field=f"slide[{slide_id}].{field}",
                        message=f"Missing required field '{field}' for code-mode slide",
                        severity="error",
                        auto_corrected=False,
                    )
                )

        render_code = slide.get("render_code")

        # Check render_code is a non-empty string
        if render_code is not None:
            if not isinstance(render_code, str) or len(render_code.strip()) == 0:
                errors.append(
                    ValidationError(
                        field=f"slide[{slide_id}].render_code",
                        message="render_code must be a non-empty string",
                        severity="error",
                        auto_corrected=False,
                    )
                )
            else:
                # Check length limit
                if len(render_code) > MAX_RENDER_CODE_LENGTH:
                    errors.append(
                        ValidationError(
                            field=f"slide[{slide_id}].render_code",
                            message=f"render_code exceeds {MAX_RENDER_CODE_LENGTH} character limit "
                                    f"(actual: {len(render_code)})",
                            severity="error",
                            auto_corrected=False,
                        )
                    )

                # Check for at least one pptxgenjs API call
                if not PPTXGENJS_API_PATTERN.search(render_code):
                    errors.append(
                        ValidationError(
                            field=f"slide[{slide_id}].render_code",
                            message="render_code must contain at least one pptxgenjs API call "
                                    "(slide.addText, slide.addShape, slide.addChart, "
                                    "slide.addImage, slide.addTable, or slide.background)",
                            severity="error",
                            auto_corrected=False,
                        )
                    )

        return errors

    @staticmethod
    def _repair_json(raw: str, max_retries: int = 2) -> Optional[Any]:
        """
        Attempt to parse *raw* as JSON, applying incremental repairs on failure.

        Repair strategies (applied cumulatively across retries):
        1. Strip trailing commas before ``]`` or ``}``.
        2. Close unbalanced brackets / braces.

        Args:
            raw: Raw string that should contain JSON.
            max_retries: Maximum repair attempts (default 2).

        Returns:
            Parsed Python object on success, or ``None`` after all retries fail.
        """
        text = raw.strip()

        # Attempt 0 — parse as-is
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        for attempt in range(1, max_retries + 1):
            # Repair step 1: strip trailing commas  (,] or ,})
            text = re.sub(r',\s*([}\]])', r'\1', text)

            # Repair step 2: close unbalanced brackets / braces
            # We must close in the reverse order they were opened to produce
            # valid JSON.  Walk the string and record unclosed openers.
            stack: list[str] = []
            in_string = False
            escape_next = False
            for ch in text:
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch in ('{', '['):
                    stack.append(ch)
                elif ch == '}' and stack and stack[-1] == '{':
                    stack.pop()
                elif ch == ']' and stack and stack[-1] == '[':
                    stack.pop()

            # Close in reverse order
            closers = {'[': ']', '{': '}'}
            suffix = ''.join(closers[opener] for opener in reversed(stack))
            text = text.rstrip() + suffix

            try:
                parsed = json.loads(text)
                logger.info(
                    "json_repair_succeeded",
                    attempt=attempt,
                    closers_appended=suffix,
                )
                return parsed
            except json.JSONDecodeError:
                logger.debug("json_repair_attempt_failed", attempt=attempt)

        return None

    def auto_correct_render_code(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Auto-correct common issues in code-mode LLM output.

        Corrections applied per ``render_code`` field:
        1. Strip markdown code fences (```javascript … ```)
        2. Fix double-escaped newlines (\\\\n → \\n)
        3. Fix double-escaped quotes (\\\\" → \\")

        Args:
            data: Parsed slide data dictionary (with a "slides" array)

        Returns:
            Tuple of (corrected_data, count_of_corrections)
        """
        corrected = deepcopy(data)
        corrections = 0

        for slide in corrected.get("slides", []):
            render_code = slide.get("render_code")
            if not isinstance(render_code, str):
                continue

            original = render_code

            # Strip markdown code fences wrapping the render_code value
            render_code = self.strip_code_fences(render_code)

            # Fix double-escaped newlines: \\n → \n
            render_code = render_code.replace("\\\\n", "\\n")
            # Fix double-escaped quotes: \\" → \"
            render_code = render_code.replace('\\\\"', '\\"')

            if render_code != original:
                slide["render_code"] = render_code
                corrections += 1
                logger.info(
                    "auto_corrected_render_code_escaping",
                    slide_id=slide.get("slide_id", "unknown"),
                )

        return corrected, corrections

    def validate_code_mode(
        self,
        data: Dict[str, Any],
        execution_id: str,
    ) -> ValidationResult:
        """
        Full code-mode validation pipeline.

        Steps:
        1. Apply auto_correct_render_code (strip fences, fix escaping)
        2. Validate each slide with validate_code_slide
        3. Validate round-trip property

        Args:
            data: Parsed LLM output with slides array
            execution_id: Execution ID for tracing

        Returns:
            ValidationResult
        """
        logger.info("code_mode_validation_started", execution_id=execution_id)

        corrected_data = deepcopy(data)
        all_errors: List[ValidationError] = []
        total_corrections = 0

        # Step 1: Auto-correct render_code (strip fences + fix escaping)
        corrected_data, corrections = self.auto_correct_render_code(corrected_data)
        total_corrections += corrections

        # Step 2: Validate each slide
        for slide in corrected_data.get("slides", []):
            slide_errors = self.validate_code_slide(slide)
            all_errors.extend(slide_errors)

        # Step 3: Round-trip validation
        round_trip_valid = self.validate_round_trip(corrected_data)
        if not round_trip_valid:
            all_errors.append(
                ValidationError(
                    field="root",
                    message="Round-trip validation failed: parse(format(parse(x))) != parse(x)",
                    severity="warning",
                    auto_corrected=False,
                )
            )

        has_errors = any(e.severity == "error" for e in all_errors)
        is_valid = not has_errors and round_trip_valid

        result = ValidationResult(
            is_valid=is_valid,
            errors=all_errors,
            corrected_data=corrected_data,
            corrections_applied=total_corrections,
        )

        logger.info(
            "code_mode_validation_completed",
            execution_id=execution_id,
            is_valid=result.is_valid,
            errors_count=len(result.errors),
            corrections_applied=result.corrections_applied,
        )

        return result

    def validate_hybrid_mode(
        self,
        data: Dict[str, Any],
        execution_id: str,
    ) -> ValidationResult:
        """
        Hybrid-mode validation pipeline.

        For slides WITH render_code: validate using code-mode rules.
        For slides WITHOUT render_code: validate using existing JSON schema rules.

        Args:
            data: Parsed LLM output with slides array
            execution_id: Execution ID for tracing

        Returns:
            ValidationResult
        """
        logger.info("hybrid_mode_validation_started", execution_id=execution_id)

        corrected_data = deepcopy(data)
        all_errors: List[ValidationError] = []
        total_corrections = 0

        # Auto-correct render_code escaping on slides that have it
        corrected_data, corrections = self.auto_correct_render_code(corrected_data)
        total_corrections += corrections

        code_slides: List[Dict[str, Any]] = []
        json_slides: List[Dict[str, Any]] = []

        for slide in corrected_data.get("slides", []):
            if slide.get("render_code"):
                code_slides.append(slide)
            else:
                json_slides.append(slide)

        # Validate code slides with code-mode rules
        for slide in code_slides:
            slide_errors = self.validate_code_slide(slide)
            all_errors.extend(slide_errors)

        # Validate JSON slides with existing schema rules
        if json_slides:
            # Build a temporary data structure for JSON-only slides
            json_data = deepcopy(corrected_data)
            json_data["slides"] = json_slides
            json_data["total_slides"] = len(json_slides)

            # Run existing JSON validation pipeline on JSON slides
            json_data = ensure_schema_version(json_data)
            json_data, norm_corrections = self.normalise_slide_fields(json_data)
            total_corrections += norm_corrections

            json_data, type_corrections = self.infer_slide_types(json_data)
            total_corrections += type_corrections

            is_valid_json, schema_errors = self.validate_schema(json_data)
            all_errors.extend(schema_errors)

            visual_hint_errors = self.validate_visual_hints(json_data)
            all_errors.extend(visual_hint_errors)

            if not is_valid_json:
                json_data, corrections = self.auto_correct_missing_fields(json_data)
                total_corrections += corrections
                json_data, corrections = self.auto_correct_wrong_types(json_data)
                total_corrections += corrections

            # Merge corrected JSON slides back
            json_slide_map = {s.get("slide_id"): s for s in json_data.get("slides", [])}
            for i, slide in enumerate(corrected_data.get("slides", [])):
                if not slide.get("render_code") and slide.get("slide_id") in json_slide_map:
                    corrected_data["slides"][i] = json_slide_map[slide["slide_id"]]

        # Round-trip validation
        round_trip_valid = self.validate_round_trip(corrected_data)
        if not round_trip_valid:
            all_errors.append(
                ValidationError(
                    field="root",
                    message="Round-trip validation failed: parse(format(parse(x))) != parse(x)",
                    severity="warning",
                    auto_corrected=False,
                )
            )

        has_errors = any(e.severity == "error" for e in all_errors)
        is_valid = not has_errors and round_trip_valid

        result = ValidationResult(
            is_valid=is_valid,
            errors=all_errors,
            corrected_data=corrected_data,
            corrections_applied=total_corrections,
        )

        logger.info(
            "hybrid_mode_validation_completed",
            execution_id=execution_id,
            is_valid=result.is_valid,
            errors_count=len(result.errors),
            corrections_applied=result.corrections_applied,
            code_slides=len(code_slides),
            json_slides=len(json_slides),
        )

        return result

    def validate_artisan_mode(
        self,
        data: Dict[str, Any],
        execution_id: str,
    ) -> ValidationResult:
        """
        Artisan-mode validation pipeline.

        Handles both pre-parsed dicts (from ``parse_raw_llm_output``) and
        dicts that may still contain raw LLM formatting artefacts.

        Steps:
        1. Strip markdown code fences from the ``artisan_code`` value
        2. Handle unwrapped script (no JSON wrapper) by auto-wrapping in
           ``{"artisan_code": "<script>"}``
        3. JSON repair (trailing commas, missing brackets) with up to 2
           retries using ``_repair_json()``
        4. Verify ``artisan_code`` field is a non-empty string
        5. Verify ``artisan_code`` contains ``pres.addSlide()``
        6. Enforce 500,000 character limit
        7. Round-trip validation

        Args:
            data: Parsed LLM output — expected to have an ``artisan_code``
                  key, but the method will attempt recovery if it doesn't.
            execution_id: Execution ID for tracing

        Returns:
            ValidationResult
        """
        logger.info("artisan_mode_validation_started", execution_id=execution_id)

        corrected_data = deepcopy(data)
        all_errors: List[ValidationError] = []
        total_corrections = 0

        # ------------------------------------------------------------------
        # Step 1: Strip markdown code fences from artisan_code value
        # ------------------------------------------------------------------
        artisan_code = corrected_data.get("artisan_code")
        if isinstance(artisan_code, str):
            stripped = self.strip_code_fences(artisan_code)
            if stripped != artisan_code:
                corrected_data["artisan_code"] = stripped
                artisan_code = stripped
                total_corrections += 1
                logger.info(
                    "artisan_code_fences_stripped",
                    execution_id=execution_id,
                )

        # ------------------------------------------------------------------
        # Step 2: Handle unwrapped script — if artisan_code is missing but
        # the data dict itself looks like it might contain a raw script
        # stashed under a different key, or if the caller accidentally
        # passed a dict without the wrapper, try to recover.
        # ------------------------------------------------------------------
        if artisan_code is None:
            # Check if any string value in the dict contains pres.addSlide()
            for key, value in corrected_data.items():
                if isinstance(value, str) and ARTISAN_API_PATTERN.search(value):
                    artisan_code = self.strip_code_fences(value)
                    corrected_data = {"artisan_code": artisan_code}
                    total_corrections += 1
                    logger.info(
                        "artisan_code_recovered_from_key",
                        execution_id=execution_id,
                        source_key=key,
                    )
                    break

        # ------------------------------------------------------------------
        # Step 3: If artisan_code looks like a JSON string (e.g. the LLM
        # returned a double-encoded value), attempt JSON repair to extract
        # the actual script.
        # ------------------------------------------------------------------
        if isinstance(artisan_code, str) and artisan_code.lstrip().startswith('{'):
            repaired = self._repair_json(artisan_code, max_retries=2)
            if isinstance(repaired, dict) and "artisan_code" in repaired:
                inner = repaired["artisan_code"]
                if isinstance(inner, str) and len(inner.strip()) > 0:
                    artisan_code = self.strip_code_fences(inner)
                    corrected_data["artisan_code"] = artisan_code
                    total_corrections += 1
                    logger.info(
                        "artisan_code_unwrapped_from_double_encoding",
                        execution_id=execution_id,
                    )

        # ------------------------------------------------------------------
        # Step 4: Verify artisan_code field is a non-empty string
        # ------------------------------------------------------------------
        if artisan_code is None:
            all_errors.append(
                ValidationError(
                    field="artisan_code",
                    message="Missing required field 'artisan_code'",
                    severity="error",
                    auto_corrected=False,
                )
            )
        elif not isinstance(artisan_code, str) or len(artisan_code.strip()) == 0:
            all_errors.append(
                ValidationError(
                    field="artisan_code",
                    message="artisan_code must be a non-empty string",
                    severity="error",
                    auto_corrected=False,
                )
            )
        else:
            # ----------------------------------------------------------
            # Step 5: Verify artisan_code contains pres.addSlide()
            # ----------------------------------------------------------
            if not ARTISAN_API_PATTERN.search(artisan_code):
                all_errors.append(
                    ValidationError(
                        field="artisan_code",
                        message="artisan_code must contain at least one pres.addSlide() call",
                        severity="error",
                        auto_corrected=False,
                    )
                )

            # ----------------------------------------------------------
            # Step 6: Enforce 500,000 character limit
            # ----------------------------------------------------------
            if len(artisan_code) > MAX_ARTISAN_CODE_LENGTH:
                all_errors.append(
                    ValidationError(
                        field="artisan_code",
                        message=f"artisan_code exceeds {MAX_ARTISAN_CODE_LENGTH} character limit "
                                f"(actual: {len(artisan_code)})",
                        severity="error",
                        auto_corrected=False,
                    )
                )

        # ------------------------------------------------------------------
        # Step 7: Round-trip validation
        # ------------------------------------------------------------------
        round_trip_valid = self.validate_round_trip(corrected_data)
        if not round_trip_valid:
            all_errors.append(
                ValidationError(
                    field="root",
                    message="Round-trip validation failed: parse(format(parse(x))) != parse(x)",
                    severity="warning",
                    auto_corrected=False,
                )
            )

        has_errors = any(e.severity == "error" for e in all_errors)
        is_valid = not has_errors and round_trip_valid

        result = ValidationResult(
            is_valid=is_valid,
            errors=all_errors,
            corrected_data=corrected_data,
            corrections_applied=total_corrections,
        )

        logger.info(
            "artisan_mode_validation_completed",
            execution_id=execution_id,
            is_valid=result.is_valid,
            errors_count=len(result.errors),
            corrections_applied=result.corrections_applied,
        )

        return result

    def validate_round_trip(self, original: Dict[str, Any]) -> bool:
        """
        Validate round-trip property: parse(format(parse(x))) == parse(x)
        
        Args:
            original: Original Slide_JSON data
            
        Returns:
            True if round-trip is consistent
        """
        try:
            # Format to JSON string
            formatted = json.dumps(original, sort_keys=True)
            
            # Parse back
            parsed = json.loads(formatted)
            
            # Format again
            reformatted = json.dumps(parsed, sort_keys=True)
            
            # Check equality
            is_consistent = formatted == reformatted
            
            if not is_consistent:
                logger.warning("round_trip_inconsistency_detected")
            
            return is_consistent
            
        except Exception as e:
            logger.error("round_trip_validation_failed", error=str(e))
            return False
    
    def validate(
        self,
        data: Dict[str, Any],
        execution_id: str,
        apply_corrections: bool = True,
        generation_mode: Optional[GenerationMode] = None,
    ) -> ValidationResult:
        """
        Main validation method with auto-correction.

        Implements:
        1. Generation mode routing (artisan/studio/craft/express)
        2. Schema version compatibility check (31.4) — reject incompatible versions
        3. Schema migration from v0.9.0 → v1.0.0 (31.3)
        4. schema_version field enforcement (31.1)
        5. Schema validation
        6. Visual hint validation
        7. Auto-correction (up to 2 attempts)
        8. Content constraint application
        9. Round-trip validation

        Args:
            data: Slide_JSON data to validate
            execution_id: Execution ID for tracing
            apply_corrections: Whether to apply auto-corrections
            generation_mode: Generation mode (artisan, studio, craft, express, or None for express)

        Returns:
            ValidationResult with validation status and corrections

        Raises:
            SchemaVersionError: if the document's schema version is incompatible
        """
        # --- Route by generation mode ---
        if generation_mode == GenerationMode.ARTISAN:
            return self.validate_artisan_mode(data, execution_id)
        if generation_mode == GenerationMode.STUDIO:
            return self.validate_code_mode(data, execution_id)
        if generation_mode == GenerationMode.CRAFT:
            return self.validate_hybrid_mode(data, execution_id)

        # --- JSON mode (default / existing logic) ---
        logger.info("validation_started", execution_id=execution_id)

        # --- Step 1: Version compatibility check (31.4) ---
        is_compatible, version_error = validate_version_compatibility(data)
        if not is_compatible:
            # Incompatible version — reject with detailed error message
            logger.error(
                "schema_version_rejected",
                execution_id=execution_id,
                version=version_error.version if version_error else "unknown",
            )
            raise version_error  # type: ignore[misc]

        # --- Step 2: Migrate from previous version if needed (31.3) ---
        corrected_data = migrate_to_current(data)
        if corrected_data.get("schema_version") != data.get("schema_version"):
            logger.info(
                "schema_migrated",
                execution_id=execution_id,
                from_version=data.get("schema_version"),
                to_version=CURRENT_SCHEMA_VERSION,
            )

        # --- Step 3: Ensure schema_version is always set to current (31.1) ---
        corrected_data = ensure_schema_version(corrected_data)

        # --- Step 3a: NORMALISE root-level LLM fields into content{} FIRST ---
        # This runs unconditionally before any other validation so that all
        # subsequent passes see a consistent structure.
        corrected_data, norm_corrections = self.normalise_slide_fields(corrected_data)
        if norm_corrections > 0:
            logger.info(
                "normalise_slide_fields_applied",
                execution_id=execution_id,
                corrections=norm_corrections,
            )

        all_errors = []
        total_corrections = norm_corrections

        # --- Step 3b: ALWAYS enforce first slide = title and infer types ---
        # This runs unconditionally regardless of schema validity, because the
        # LLM may return a valid schema but with wrong slide types (e.g. type="chart"
        # on slide 1). We must fix this before any further processing.
        corrected_data, type_corrections = self.infer_slide_types(corrected_data)
        total_corrections += type_corrections
        if type_corrections > 0:
            logger.info(
                "slide_type_inference_applied",
                execution_id=execution_id,
                corrections=type_corrections,
            )

        # Attempt 1: Initial validation
        is_valid, schema_errors = self.validate_schema(corrected_data)
        all_errors.extend(schema_errors)
        
        visual_hint_errors = self.validate_visual_hints(corrected_data)
        all_errors.extend(visual_hint_errors)

        # Validate design token names in layout_instructions (non-blocking warnings)
        token_errors = self.validate_layout_instructions(corrected_data)
        all_errors.extend(token_errors)

        if not is_valid and apply_corrections:
            # Attempt 2: Auto-correct missing fields
            logger.info("applying_auto_corrections_attempt_1", execution_id=execution_id)
            corrected_data, corrections = self.auto_correct_missing_fields(corrected_data)
            total_corrections += corrections
            
            # Attempt 3: Auto-correct wrong types
            logger.info("applying_auto_corrections_attempt_2", execution_id=execution_id)
            corrected_data, corrections = self.auto_correct_wrong_types(corrected_data)
            total_corrections += corrections
            
            # Re-validate after corrections
            is_valid, schema_errors = self.validate_schema(corrected_data)
            
            # Mark corrected errors
            for error in all_errors:
                if error.field not in [e.field for e in schema_errors]:
                    error.auto_corrected = True
            
            # Update error list
            all_errors = [e for e in all_errors if not e.auto_corrected] + schema_errors

        # --- Step 4: Content completeness validation (always runs) ---
        # Ensures every slide has the data its type requires.
        # Runs after field normalisation and missing-field correction so all
        # root-level fields are already inside content{}.
        corrected_data, completeness_corrections = self.validate_content_completeness(corrected_data)
        total_corrections += completeness_corrections
        if completeness_corrections > 0:
            logger.info(
                "content_completeness_applied",
                execution_id=execution_id,
                corrections=completeness_corrections,
            )
        
        # Apply content constraints (always)
        corrected_data, overflow_slides = self.apply_content_constraints(corrected_data)
        if overflow_slides:
            total_corrections += len(overflow_slides)
        
        # Validate round-trip property
        round_trip_valid = self.validate_round_trip(corrected_data)
        if not round_trip_valid:
            all_errors.append(
                ValidationError(
                    field="root",
                    message="Round-trip validation failed: parse(format(parse(x))) != parse(x)",
                    severity="warning",
                    auto_corrected=False
                )
            )
        
        # Final validation
        final_valid, final_errors = self.validate_schema(corrected_data)
        
        result = ValidationResult(
            is_valid=final_valid and round_trip_valid,
            errors=all_errors if not final_valid else [e for e in all_errors if e.severity == "warning"],
            corrected_data=corrected_data if apply_corrections else None,
            corrections_applied=total_corrections
        )
        
        logger.info(
            "validation_completed",
            execution_id=execution_id,
            is_valid=result.is_valid,
            errors_count=len(result.errors),
            corrections_applied=result.corrections_applied
        )
        
        return result

    def parse_raw_llm_output(
        self,
        raw_text: str,
        generation_mode: Optional[GenerationMode] = None,
    ) -> Dict[str, Any]:
        """
        Parse raw LLM response text into a structured dict, with auto-repair.

        For all modes:
        1. Strip markdown code fences (```json, ```javascript, ```)
        2. Attempt JSON parse
        3. On failure, apply JSON repair (trailing commas, unbalanced brackets)
           with up to 2 retries
        4. Normalise bare arrays into ``{"slides": [...]}``

        For artisan mode specifically:
        5. If the parsed result lacks an ``artisan_code`` key but looks like
           a raw script (contains ``pres.addSlide()``), auto-wrap it into
           ``{"artisan_code": "<script>"}``

        This method is intended to be called *before* ``validate()`` when the
        caller has a raw string rather than an already-parsed dict.

        Args:
            raw_text: Raw LLM response string
            generation_mode: Active generation mode (for logging)

        Returns:
            Parsed dict ready for ``validate()``

        Raises:
            ValueError: If the text cannot be parsed after all repair attempts
        """
        # Step 1: strip code fences
        cleaned = self.strip_code_fences(raw_text)

        # --- Artisan mode handling ---
        if generation_mode == GenerationMode.ARTISAN:
            return self._parse_artisan_output(cleaned)

        # Step 2: try to extract JSON from the cleaned text
        # The LLM may include preamble text before the JSON array/object
        json_start = None
        for i, ch in enumerate(cleaned):
            if ch in ('[', '{'):
                json_start = i
                break

        if json_start is not None:
            candidate = cleaned[json_start:]
        else:
            candidate = cleaned

        # Step 3: parse with repair
        parsed = self._repair_json(candidate, max_retries=2)
        if parsed is None:
            raise ValueError(
                f"Failed to parse LLM output as JSON after 2 repair attempts. "
                f"First 200 chars: {cleaned[:200]}"
            )

        # Step 4: normalise
        if isinstance(parsed, list):
            parsed = {
                "slides": parsed,
                "total_slides": len(parsed),
            }
        elif isinstance(parsed, dict) and "slides" not in parsed:
            # Search one level deep for a slides array
            for key, val in parsed.items():
                if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                    parsed = {"slides": val, "total_slides": len(val)}
                    break

        logger.info(
            "raw_llm_output_parsed",
            generation_mode=generation_mode.value if generation_mode else "unknown",
            slide_count=len(parsed.get("slides", [])) if isinstance(parsed, dict) else 0,
        )

        return parsed

    def _parse_artisan_output(self, cleaned: str) -> Dict[str, Any]:
        """
        Parse artisan-mode LLM output.

        Handles three cases:
        1. Valid JSON with ``artisan_code`` key → return as-is
        2. JSON-like text that needs repair → repair then return
        3. Raw script (no JSON wrapper) containing ``pres.addSlide()``
           → auto-wrap into ``{"artisan_code": "<script>"}``

        Args:
            cleaned: Code-fence-stripped LLM response

        Returns:
            Dict with ``artisan_code`` key

        Raises:
            ValueError: If the text cannot be parsed or wrapped
        """
        # Try to find JSON object start
        json_start = None
        for i, ch in enumerate(cleaned):
            if ch == '{':
                json_start = i
                break

        if json_start is not None:
            candidate = cleaned[json_start:]
            parsed = self._repair_json(candidate, max_retries=2)
            if isinstance(parsed, dict) and "artisan_code" in parsed:
                logger.info(
                    "artisan_output_parsed_as_json",
                    code_length=len(parsed["artisan_code"]) if isinstance(parsed.get("artisan_code"), str) else 0,
                )
                return parsed

        # If JSON parsing failed or result lacks artisan_code,
        # check if the cleaned text is a raw script
        if ARTISAN_API_PATTERN.search(cleaned):
            logger.info(
                "artisan_output_auto_wrapped",
                code_length=len(cleaned),
            )
            return {"artisan_code": cleaned}

        raise ValueError(
            f"Failed to parse artisan LLM output: no valid JSON with 'artisan_code' key "
            f"and no raw script with pres.addSlide() found. "
            f"First 200 chars: {cleaned[:200]}"
        )


# Global agent instance
validation_agent = ValidationAgent()
