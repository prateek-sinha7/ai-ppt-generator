"""
Slide_JSON Schema Registry and Migration Transformer (Task 31)

Implements:
- Schema registry supporting current version (1.0.0) and one previous version (0.9.0)
- Schema migration transformer converting v0.x responses to v1.0.0 format
- Schema validation rejection with detailed error messages for incompatible versions
- schema_version field enforcement (default "1.0.0") on all generated Slide_JSON

Design references: Req 35, 36 | Design: Interface Specifications
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import structlog
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = "1.0.0"
PREVIOUS_SCHEMA_VERSION = "0.9.0"

# Versions the registry can accept and migrate
SUPPORTED_VERSIONS = {CURRENT_SCHEMA_VERSION, PREVIOUS_SCHEMA_VERSION}

# Versions that are incompatible and must be rejected
INCOMPATIBLE_VERSION_PATTERN = re.compile(r"^0\.[0-8]\.")  # 0.0.x – 0.8.x


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

# v1.0.0 — current canonical schema (mirrors SLIDE_JSON_SCHEMA in validation.py)
SCHEMA_V1_0_0: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Slide_JSON v1.0.0",
    "type": "object",
    "required": ["schema_version", "presentation_id", "total_slides", "slides"],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0.0"},
        "presentation_id": {"type": "string"},
        "total_slides": {"type": "integer", "minimum": 1},
        "slides": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["slide_id", "slide_number", "type", "title", "content", "visual_hint"],
                "properties": {
                    "slide_id": {"type": "string"},
                    "slide_number": {"type": "integer", "minimum": 1},
                    "type": {
                        "type": "string",
                        "enum": ["title", "content", "chart", "table", "comparison"],
                    },
                    "title": {"type": "string"},
                    "content": {
                        "type": "object",
                        "properties": {
                            "bullets": {"type": "array", "items": {"type": "string"}},
                            "chart_data": {"type": "object"},
                            "table_data": {"type": "object"},
                            "comparison_data": {"type": "object"},
                            "icon_name": {"type": "string"},
                            "highlight_text": {"type": "string"},
                            "transition": {
                                "type": "string",
                                "enum": ["fade", "slide", "none"],
                            },
                        },
                    },
                    "visual_hint": {
                        "type": "string",
                        "enum": [
                            "centered",
                            "bullet-left",
                            "split-chart-right",
                            "split-table-left",
                            "two-column",
                            "highlight-metric",
                        ],
                    },
                    "layout_constraints": {
                        "type": "object",
                        "properties": {
                            "max_content_density": {"type": "number", "minimum": 0, "maximum": 1},
                            "min_whitespace_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "generated_at": {"type": "string"},
                            "provider_used": {"type": "string"},
                            "quality_score": {"type": "number", "minimum": 1, "maximum": 10},
                        },
                    },
                },
            },
        },
    },
}

# v0.9.0 — previous version schema (relaxed: no schema_version const, uses "layout" instead of "visual_hint")
SCHEMA_V0_9_0: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Slide_JSON v0.9.0",
    "type": "object",
    "required": ["presentation_id", "total_slides", "slides"],
    "properties": {
        "schema_version": {"type": "string"},
        "presentation_id": {"type": "string"},
        "total_slides": {"type": "integer", "minimum": 1},
        "slides": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["slide_id", "slide_number", "type", "title"],
                "properties": {
                    "slide_id": {"type": "string"},
                    "slide_number": {"type": "integer", "minimum": 1},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    # v0.9 used "layout" instead of "visual_hint"
                    "layout": {"type": "string"},
                    "visual_hint": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "content": {"type": "object"},
                    "metadata": {"type": "object"},
                },
            },
        },
    },
}

# Registry: version string → {schema, validator, deprecated, notes}
_SCHEMA_REGISTRY: Dict[str, Dict[str, Any]] = {
    CURRENT_SCHEMA_VERSION: {
        "schema": SCHEMA_V1_0_0,
        "validator": Draft7Validator(SCHEMA_V1_0_0),
        "deprecated": False,
        "notes": "Current stable version. All new presentations use this schema.",
        "released": "2025-01-01",
        "deprecated_date": None,
        "sunset_date": None,
    },
    PREVIOUS_SCHEMA_VERSION: {
        "schema": SCHEMA_V0_9_0,
        "validator": Draft7Validator(SCHEMA_V0_9_0),
        "deprecated": True,
        "notes": (
            "Deprecated. Migrate to v1.0.0. "
            "Key changes: schema_version field added, visual_hint replaces layout, "
            "content object wraps bullets."
        ),
        "released": "2024-06-01",
        "deprecated_date": "2025-01-01",
        "sunset_date": "2025-07-01",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SchemaVersionError(ValueError):
    """Raised when a Slide_JSON document has an incompatible or unknown schema version."""

    def __init__(self, message: str, version: Optional[str] = None, details: Optional[List[str]] = None):
        super().__init__(message)
        self.version = version
        self.details = details or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": "schema_version_incompatible",
            "message": str(self),
            "version": self.version,
            "supported_versions": sorted(SUPPORTED_VERSIONS),
            "current_version": CURRENT_SCHEMA_VERSION,
            "details": self.details,
            "migration_guide": (
                "Set schema_version to '1.0.0'. "
                "Wrap top-level bullets inside a content object. "
                "Rename 'layout' field to 'visual_hint'."
            ),
        }


def get_registry_info() -> Dict[str, Any]:
    """Return the full schema registry as a structured dict for the changelog endpoint."""
    versions = []
    for version, info in _SCHEMA_REGISTRY.items():
        versions.append(
            {
                "version": version,
                "deprecated": info["deprecated"],
                "notes": info["notes"],
                "released": info["released"],
                "deprecated_date": info.get("deprecated_date"),
                "sunset_date": info.get("sunset_date"),
            }
        )
    # Sort newest first
    versions.sort(key=lambda v: v["version"], reverse=True)
    return {
        "current_version": CURRENT_SCHEMA_VERSION,
        "supported_versions": sorted(SUPPORTED_VERSIONS, reverse=True),
        "versions": versions,
        "deprecation_policy": (
            "Schema versions are deprecated with at least 6 months notice. "
            "Deprecated versions are still accepted and automatically migrated to the current version. "
            "Incompatible versions (below 0.9.0) are rejected with HTTP 422."
        ),
        "changelog": _CHANGELOG,
    }


def detect_version(data: Dict[str, Any]) -> str:
    """
    Detect the schema version of a Slide_JSON document.

    Rules:
    - If schema_version field is present, use it.
    - If absent but document has v0.9-style structure (top-level bullets or layout field), infer 0.9.0.
    - Otherwise default to current version.
    """
    if "schema_version" in data:
        return str(data["schema_version"])

    # Heuristic: v0.9 documents often have top-level "layout" on slides or missing content wrapper
    slides = data.get("slides", [])
    if slides:
        first = slides[0]
        if "layout" in first or ("bullets" in first and "content" not in first):
            logger.info("schema_version_inferred", inferred=PREVIOUS_SCHEMA_VERSION)
            return PREVIOUS_SCHEMA_VERSION

    return CURRENT_SCHEMA_VERSION


def ensure_schema_version(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure schema_version is set to the current version (1.0.0).
    Mutates a copy of the data — does not modify the original.

    This is the 31.1 requirement: all generated Slide_JSON must carry schema_version "1.0.0".
    """
    result = deepcopy(data)
    if result.get("schema_version") != CURRENT_SCHEMA_VERSION:
        result["schema_version"] = CURRENT_SCHEMA_VERSION
        logger.info("schema_version_set", version=CURRENT_SCHEMA_VERSION)
    return result


def validate_version_compatibility(data: Dict[str, Any]) -> Tuple[bool, Optional[SchemaVersionError]]:
    """
    Check whether the document's schema version is compatible (supported or migratable).

    Returns:
        (True, None)                    — version is current or migratable
        (False, SchemaVersionError)     — version is incompatible and must be rejected

    Raises nothing — callers decide whether to raise or return the error.
    """
    version = detect_version(data)

    # Incompatible: below 0.9.0
    if INCOMPATIBLE_VERSION_PATTERN.match(version):
        err = SchemaVersionError(
            f"Schema version '{version}' is incompatible and cannot be migrated. "
            f"Minimum supported version is {PREVIOUS_SCHEMA_VERSION}.",
            version=version,
            details=[
                f"Received version: {version}",
                f"Minimum supported: {PREVIOUS_SCHEMA_VERSION}",
                f"Current version: {CURRENT_SCHEMA_VERSION}",
                "Documents below v0.9.0 cannot be automatically migrated.",
            ],
        )
        logger.warning("schema_version_incompatible", version=version)
        return False, err

    # Unknown version that is not in our registry and not a known pattern
    if version not in SUPPORTED_VERSIONS and not version.startswith("0."):
        err = SchemaVersionError(
            f"Unknown schema version '{version}'. Supported versions: {sorted(SUPPORTED_VERSIONS)}.",
            version=version,
            details=[
                f"Received version: {version}",
                f"Supported versions: {sorted(SUPPORTED_VERSIONS)}",
            ],
        )
        logger.warning("schema_version_unknown", version=version)
        return False, err

    return True, None


def migrate_to_current(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate a Slide_JSON document from any supported previous version to v1.0.0.

    Handles v0.9.0 → v1.0.0 migration:
    - Adds schema_version: "1.0.0"
    - Renames slide.layout → slide.visual_hint (with enum normalisation)
    - Wraps top-level slide.bullets into slide.content.bullets
    - Ensures slide.content object exists
    - Adds missing slide_id / slide_number defaults

    If the document is already v1.0.0, returns a copy unchanged.
    """
    version = detect_version(data)

    if version == CURRENT_SCHEMA_VERSION:
        result = deepcopy(data)
        result["schema_version"] = CURRENT_SCHEMA_VERSION
        return result

    if version == PREVIOUS_SCHEMA_VERSION or version.startswith("0.9"):
        return _migrate_v0_9_to_v1_0(data)

    # For any other 0.x version that passed compatibility check, attempt best-effort migration
    logger.warning("schema_migration_best_effort", from_version=version, to_version=CURRENT_SCHEMA_VERSION)
    return _migrate_v0_9_to_v1_0(data)


# ---------------------------------------------------------------------------
# Internal migration helpers
# ---------------------------------------------------------------------------

# Mapping from v0.9 layout strings to v1.0 visual_hint enum values
_LAYOUT_TO_VISUAL_HINT: Dict[str, str] = {
    "centered": "centered",
    "center": "centered",
    "title": "centered",
    "bullet-left": "bullet-left",
    "bullet_left": "bullet-left",
    "bullets": "bullet-left",
    "content": "bullet-left",
    "split-chart-right": "split-chart-right",
    "split_chart_right": "split-chart-right",
    "chart": "split-chart-right",
    "chart-right": "split-chart-right",
    "split-table-left": "split-table-left",
    "split_table_left": "split-table-left",
    "table": "split-table-left",
    "table-left": "split-table-left",
    "two-column": "two-column",
    "two_column": "two-column",
    "comparison": "two-column",
    "highlight-metric": "highlight-metric",
    "highlight_metric": "highlight-metric",
    "metric": "highlight-metric",
}

# Mapping from v0.9 slide type strings to v1.0 enum values
_SLIDE_TYPE_MAP: Dict[str, str] = {
    "title": "title",
    "title_slide": "title",
    "content": "content",
    "content_slide": "content",
    "chart": "chart",
    "chart_slide": "chart",
    "table": "table",
    "table_slide": "table",
    "comparison": "comparison",
    "comparison_slide": "comparison",
}


def _migrate_v0_9_to_v1_0(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a v0.9.0 Slide_JSON document to v1.0.0."""
    result = deepcopy(data)

    # 1. Set schema_version
    result["schema_version"] = CURRENT_SCHEMA_VERSION

    # 2. Ensure presentation_id
    if "presentation_id" not in result:
        result["presentation_id"] = str(uuid4())

    # 3. Migrate each slide
    migrated_slides = []
    for i, slide in enumerate(result.get("slides", [])):
        migrated = _migrate_slide_v0_9_to_v1_0(slide, index=i)
        migrated_slides.append(migrated)

    result["slides"] = migrated_slides

    # 4. Ensure total_slides is consistent
    result["total_slides"] = len(migrated_slides)

    logger.info(
        "schema_migration_completed",
        from_version=PREVIOUS_SCHEMA_VERSION,
        to_version=CURRENT_SCHEMA_VERSION,
        slide_count=len(migrated_slides),
    )
    return result


def _migrate_slide_v0_9_to_v1_0(slide: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Migrate a single slide from v0.9 to v1.0 format."""
    s = deepcopy(slide)

    # Ensure slide_id
    if "slide_id" not in s:
        s["slide_id"] = str(uuid4())

    # Ensure slide_number
    if "slide_number" not in s:
        s["slide_number"] = index + 1

    # Normalise slide type
    raw_type = s.get("type", "content")
    s["type"] = _SLIDE_TYPE_MAP.get(str(raw_type).lower(), "content")

    # Migrate layout → visual_hint
    if "layout" in s and "visual_hint" not in s:
        raw_layout = str(s.pop("layout")).lower()
        s["visual_hint"] = _LAYOUT_TO_VISUAL_HINT.get(raw_layout, "bullet-left")
    elif "visual_hint" not in s:
        # Infer visual_hint from slide type
        type_to_hint = {
            "title": "centered",
            "content": "bullet-left",
            "chart": "split-chart-right",
            "table": "split-table-left",
            "comparison": "two-column",
        }
        s["visual_hint"] = type_to_hint.get(s["type"], "bullet-left")

    # Migrate top-level bullets into content object
    if "content" not in s:
        s["content"] = {}

    if "bullets" in s and "bullets" not in s["content"]:
        s["content"]["bullets"] = s.pop("bullets")
    elif "bullets" in s:
        s.pop("bullets")  # already in content

    # Migrate top-level chart_data / table_data / comparison_data
    for field in ("chart_data", "table_data", "comparison_data", "icon_name", "highlight_text"):
        if field in s and field not in s["content"]:
            s["content"][field] = s.pop(field)
        elif field in s:
            s.pop(field)

    # Ensure layout_constraints
    if "layout_constraints" not in s:
        s["layout_constraints"] = {
            "max_content_density": 0.75,
            "min_whitespace_ratio": 0.25,
        }

    # Ensure metadata
    if "metadata" not in s:
        s["metadata"] = {
            "generated_at": datetime.utcnow().isoformat(),
            "provider_used": "unknown",
            "quality_score": 1.0,
        }

    return s


def validate_against_version(
    data: Dict[str, Any], version: str
) -> Tuple[bool, List[str]]:
    """
    Validate data against the schema for a specific version.

    Returns:
        (is_valid, error_messages)
    """
    info = _SCHEMA_REGISTRY.get(version)
    if info is None:
        return False, [f"No schema registered for version '{version}'."]

    validator: Draft7Validator = info["validator"]
    errors = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

_CHANGELOG: List[Dict[str, Any]] = [
    {
        "version": "1.0.0",
        "released": "2025-01-01",
        "breaking": False,
        "changes": [
            "Added required schema_version field (value: '1.0.0')",
            "visual_hint field replaces layout field with strict enum validation",
            "Slide content (bullets, chart_data, table_data, comparison_data) moved into content object",
            "Added layout_constraints object with max_content_density and min_whitespace_ratio",
            "Added metadata object with generated_at, provider_used, quality_score",
            "Added icon_name and highlight_text optional content fields",
            "Added transition enum field (fade | slide | none)",
        ],
        "migration": "Automatic migration from v0.9.0 is supported via the schema registry.",
    },
    {
        "version": "0.9.0",
        "released": "2024-06-01",
        "deprecated": "2025-01-01",
        "sunset": "2025-07-01",
        "breaking": False,
        "changes": [
            "Initial schema version",
            "Used layout field (free-text) instead of visual_hint enum",
            "Bullets stored at top level of slide object",
        ],
        "migration": "Migrate to v1.0.0. See migration_guide in error responses.",
    },
]
