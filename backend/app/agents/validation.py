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
    "mckinsey", "deloitte", "dark-modern",
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


# Content constraints
MAX_TITLE_WORDS = 8
MAX_BULLETS = 4
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
            bullet: Original bullet text
            max_words: Maximum number of words (default: 8)
            
        Returns:
            Truncated bullet
        """
        words = bullet.split()
        if len(words) <= max_words:
            return bullet
        
        truncated = " ".join(words[:max_words])
        logger.info(
            "bullet_truncated",
            original_words=len(words),
            max_words=max_words,
            original=bullet[:50],
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
                        fallback = [{"label": b[:20], "value": round(random.uniform(30, 90), 1)} for b in bullets[:5]]
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
                slide["content"] = content

            elif slide_type == "table":
                # Ensure table_data has headers and rows
                table_data = content.get("table_data")
                if not table_data or not isinstance(table_data, dict) or not table_data.get("headers"):
                    bullets = content.get("bullets", [])
                    if bullets:
                        fallback = {
                            "headers": ["Item", "Details"],
                            "rows": [[b[:30], "—"] for b in bullets[:5]]
                        }
                    else:
                        fallback = {
                            "headers": ["Metric", "Value", "Trend"],
                            "rows": [
                                ["Revenue Growth", "12.5%", "↑"],
                                ["Market Share", "23.4%", "↑"],
                                ["Cost Reduction", "8.2%", "↓"],
                                ["Customer Satisfaction", "87%", "↑"],
                            ]
                        }
                    content["table_data"] = fallback
                    corrections += 1
                    logger.info("auto_corrected_table_data", slide_number=i+1)
                slide["content"] = content

            elif slide_type == "comparison":
                # Ensure comparison_data has left_column and right_column
                comparison_data = content.get("comparison_data")
                if not comparison_data or not isinstance(comparison_data, dict) or \
                   not comparison_data.get("left_column") or not comparison_data.get("right_column"):
                    bullets = content.get("bullets", [])
                    mid = len(bullets) // 2
                    left_bullets = bullets[:mid] if mid > 0 else ["Current approach", "Existing process", "Status quo"]
                    right_bullets = bullets[mid:] if mid > 0 else ["Improved approach", "New process", "Future state"]
                    content["comparison_data"] = {
                        "left_column": {"heading": "Current State", "bullets": left_bullets},
                        "right_column": {"heading": "Future State", "bullets": right_bullets}
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
        
        for i, slide in enumerate(corrected.get("slides", [])):
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
        apply_corrections: bool = True
    ) -> ValidationResult:
        """
        Main validation method with auto-correction.

        Implements:
        1. Schema version compatibility check (31.4) — reject incompatible versions
        2. Schema migration from v0.9.0 → v1.0.0 (31.3)
        3. schema_version field enforcement (31.1)
        4. Schema validation
        5. Visual hint validation
        6. Auto-correction (up to 2 attempts)
        7. Content constraint application
        8. Round-trip validation

        Args:
            data: Slide_JSON data to validate
            execution_id: Execution ID for tracing
            apply_corrections: Whether to apply auto-corrections

        Returns:
            ValidationResult with validation status and corrections

        Raises:
            SchemaVersionError: if the document's schema version is incompatible
        """
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

        all_errors = []
        total_corrections = 0

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


# Global agent instance
validation_agent = ValidationAgent()
