"""
Tests for Slide_JSON Schema Versioning and Backward Compatibility (Task 31)

Covers:
- 31.1: schema_version field enforcement (default "1.0.0")
- 31.2: schema registry supporting current and previous version
- 31.3: migration transformer v0.9.0 → v1.0.0
- 31.4: schema validation rejection with detailed error messages
- 31.5: API versioning changelog endpoint
"""
from __future__ import annotations

import pytest
from copy import deepcopy
from typing import Any, Dict

from app.services.schema_registry import (
    CURRENT_SCHEMA_VERSION,
    PREVIOUS_SCHEMA_VERSION,
    SUPPORTED_VERSIONS,
    SchemaVersionError,
    _migrate_slide_v0_9_to_v1_0,
    _migrate_v0_9_to_v1_0,
    detect_version,
    ensure_schema_version,
    get_registry_info,
    migrate_to_current,
    validate_against_version,
    validate_version_compatibility,
)
from app.agents.validation import ValidationAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_v1_slide_json(**overrides) -> Dict[str, Any]:
    """Minimal valid v1.0.0 Slide_JSON."""
    doc = {
        "schema_version": "1.0.0",
        "presentation_id": "550e8400-e29b-41d4-a716-446655440000",
        "total_slides": 1,
        "slides": [
            {
                "slide_id": "slide-001",
                "slide_number": 1,
                "type": "content",
                "title": "Test Slide",
                "content": {"bullets": ["Point one", "Point two"]},
                "visual_hint": "bullet-left",
                "layout_constraints": {
                    "max_content_density": 0.75,
                    "min_whitespace_ratio": 0.25,
                },
                "metadata": {
                    "generated_at": "2025-01-01T00:00:00",
                    "provider_used": "claude",
                    "quality_score": 8.5,
                },
            }
        ],
    }
    doc.update(overrides)
    return doc


def make_v0_9_slide_json(**overrides) -> Dict[str, Any]:
    """Minimal v0.9.0-style Slide_JSON (no schema_version, uses layout, top-level bullets)."""
    doc = {
        "presentation_id": "550e8400-e29b-41d4-a716-446655440000",
        "total_slides": 1,
        "slides": [
            {
                "slide_id": "slide-001",
                "slide_number": 1,
                "type": "content",
                "title": "Test Slide",
                "bullets": ["Point one", "Point two"],
                "layout": "bullet-left",
            }
        ],
    }
    doc.update(overrides)
    return doc


# ---------------------------------------------------------------------------
# 31.1 — schema_version field enforcement
# ---------------------------------------------------------------------------


class TestEnsureSchemaVersion:
    def test_sets_version_when_missing(self):
        doc = {"presentation_id": "abc", "total_slides": 1, "slides": []}
        result = ensure_schema_version(doc)
        assert result["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_keeps_current_version_unchanged(self):
        doc = make_v1_slide_json()
        result = ensure_schema_version(doc)
        assert result["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_overwrites_old_version(self):
        doc = make_v1_slide_json(schema_version="0.9.0")
        result = ensure_schema_version(doc)
        assert result["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_does_not_mutate_original(self):
        doc = {"presentation_id": "abc", "total_slides": 1, "slides": []}
        original_keys = set(doc.keys())
        ensure_schema_version(doc)
        assert set(doc.keys()) == original_keys
        assert "schema_version" not in doc

    def test_current_version_is_1_0_0(self):
        assert CURRENT_SCHEMA_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# 31.2 — schema registry
# ---------------------------------------------------------------------------


class TestSchemaRegistry:
    def test_supported_versions_contains_current(self):
        assert CURRENT_SCHEMA_VERSION in SUPPORTED_VERSIONS

    def test_supported_versions_contains_previous(self):
        assert PREVIOUS_SCHEMA_VERSION in SUPPORTED_VERSIONS

    def test_previous_version_is_0_9_0(self):
        assert PREVIOUS_SCHEMA_VERSION == "0.9.0"

    def test_get_registry_info_returns_both_versions(self):
        info = get_registry_info()
        versions = [v["version"] for v in info["versions"]]
        assert CURRENT_SCHEMA_VERSION in versions
        assert PREVIOUS_SCHEMA_VERSION in versions

    def test_registry_info_has_deprecation_policy(self):
        info = get_registry_info()
        assert "deprecation_policy" in info
        assert len(info["deprecation_policy"]) > 0

    def test_registry_info_has_changelog(self):
        info = get_registry_info()
        assert "changelog" in info
        assert len(info["changelog"]) >= 2

    def test_previous_version_marked_deprecated(self):
        info = get_registry_info()
        prev = next(v for v in info["versions"] if v["version"] == PREVIOUS_SCHEMA_VERSION)
        assert prev["deprecated"] is True

    def test_current_version_not_deprecated(self):
        info = get_registry_info()
        curr = next(v for v in info["versions"] if v["version"] == CURRENT_SCHEMA_VERSION)
        assert curr["deprecated"] is False

    def test_validate_against_current_version_valid(self):
        doc = make_v1_slide_json()
        is_valid, errors = validate_against_version(doc, CURRENT_SCHEMA_VERSION)
        assert is_valid
        assert errors == []

    def test_validate_against_current_version_invalid(self):
        doc = {"schema_version": "1.0.0"}  # missing required fields
        is_valid, errors = validate_against_version(doc, CURRENT_SCHEMA_VERSION)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_against_previous_version_valid(self):
        doc = make_v0_9_slide_json()
        is_valid, errors = validate_against_version(doc, PREVIOUS_SCHEMA_VERSION)
        assert is_valid

    def test_validate_against_unknown_version_returns_error(self):
        doc = make_v1_slide_json()
        is_valid, errors = validate_against_version(doc, "99.0.0")
        assert not is_valid
        assert any("No schema registered" in e for e in errors)


# ---------------------------------------------------------------------------
# 31.3 — migration transformer v0.9.0 → v1.0.0
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    def test_migrate_adds_schema_version(self):
        doc = make_v0_9_slide_json()
        result = migrate_to_current(doc)
        assert result["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_migrate_converts_layout_to_visual_hint(self):
        doc = make_v0_9_slide_json()
        result = migrate_to_current(doc)
        slide = result["slides"][0]
        assert "visual_hint" in slide
        assert slide["visual_hint"] == "bullet-left"
        assert "layout" not in slide

    def test_migrate_wraps_bullets_in_content(self):
        doc = make_v0_9_slide_json()
        result = migrate_to_current(doc)
        slide = result["slides"][0]
        assert "content" in slide
        assert "bullets" in slide["content"]
        assert slide["content"]["bullets"] == ["Point one", "Point two"]
        assert "bullets" not in slide  # top-level bullets removed

    def test_migrate_adds_layout_constraints(self):
        doc = make_v0_9_slide_json()
        result = migrate_to_current(doc)
        slide = result["slides"][0]
        assert "layout_constraints" in slide
        assert slide["layout_constraints"]["max_content_density"] == 0.75
        assert slide["layout_constraints"]["min_whitespace_ratio"] == 0.25

    def test_migrate_adds_metadata(self):
        doc = make_v0_9_slide_json()
        result = migrate_to_current(doc)
        slide = result["slides"][0]
        assert "metadata" in slide
        assert "generated_at" in slide["metadata"]

    def test_migrate_updates_total_slides(self):
        doc = make_v0_9_slide_json()
        doc["total_slides"] = 99  # wrong value
        result = migrate_to_current(doc)
        assert result["total_slides"] == len(result["slides"])

    def test_migrate_v1_document_unchanged(self):
        doc = make_v1_slide_json()
        result = migrate_to_current(doc)
        assert result["schema_version"] == CURRENT_SCHEMA_VERSION
        assert result["slides"][0]["visual_hint"] == "bullet-left"

    def test_migrate_does_not_mutate_original(self):
        doc = make_v0_9_slide_json()
        original_slide = deepcopy(doc["slides"][0])
        migrate_to_current(doc)
        assert doc["slides"][0] == original_slide

    def test_migrate_layout_centered(self):
        doc = make_v0_9_slide_json()
        doc["slides"][0]["layout"] = "centered"
        result = migrate_to_current(doc)
        assert result["slides"][0]["visual_hint"] == "centered"

    def test_migrate_layout_chart(self):
        doc = make_v0_9_slide_json()
        doc["slides"][0]["layout"] = "chart"
        result = migrate_to_current(doc)
        assert result["slides"][0]["visual_hint"] == "split-chart-right"

    def test_migrate_layout_table(self):
        doc = make_v0_9_slide_json()
        doc["slides"][0]["layout"] = "table"
        result = migrate_to_current(doc)
        assert result["slides"][0]["visual_hint"] == "split-table-left"

    def test_migrate_layout_comparison(self):
        doc = make_v0_9_slide_json()
        doc["slides"][0]["layout"] = "comparison"
        result = migrate_to_current(doc)
        assert result["slides"][0]["visual_hint"] == "two-column"

    def test_migrate_layout_metric(self):
        doc = make_v0_9_slide_json()
        doc["slides"][0]["layout"] = "metric"
        result = migrate_to_current(doc)
        assert result["slides"][0]["visual_hint"] == "highlight-metric"

    def test_migrate_infers_visual_hint_from_type_when_no_layout(self):
        doc = make_v0_9_slide_json()
        del doc["slides"][0]["layout"]
        doc["slides"][0]["type"] = "chart"
        result = migrate_to_current(doc)
        assert result["slides"][0]["visual_hint"] == "split-chart-right"

    def test_migrate_moves_chart_data_into_content(self):
        doc = make_v0_9_slide_json()
        doc["slides"][0]["chart_data"] = {"labels": ["A", "B"], "values": [1, 2]}
        result = migrate_to_current(doc)
        slide = result["slides"][0]
        assert "chart_data" in slide["content"]
        assert "chart_data" not in slide

    def test_migrate_multiple_slides(self):
        doc = {
            "presentation_id": "abc",
            "total_slides": 2,
            "slides": [
                {
                    "slide_id": "s1",
                    "slide_number": 1,
                    "type": "title",
                    "title": "Title",
                    "layout": "centered",
                },
                {
                    "slide_id": "s2",
                    "slide_number": 2,
                    "type": "content",
                    "title": "Content",
                    "bullets": ["A", "B"],
                    "layout": "bullet-left",
                },
            ],
        }
        result = migrate_to_current(doc)
        assert len(result["slides"]) == 2
        assert result["slides"][0]["visual_hint"] == "centered"
        assert result["slides"][1]["visual_hint"] == "bullet-left"
        assert result["slides"][1]["content"]["bullets"] == ["A", "B"]

    def test_migrate_adds_missing_slide_id(self):
        doc = make_v0_9_slide_json()
        del doc["slides"][0]["slide_id"]
        result = migrate_to_current(doc)
        assert "slide_id" in result["slides"][0]
        assert len(result["slides"][0]["slide_id"]) > 0

    def test_migrate_adds_missing_slide_number(self):
        doc = make_v0_9_slide_json()
        del doc["slides"][0]["slide_number"]
        result = migrate_to_current(doc)
        assert result["slides"][0]["slide_number"] == 1

    def test_migrated_document_passes_v1_validation(self):
        doc = make_v0_9_slide_json()
        migrated = migrate_to_current(doc)
        is_valid, errors = validate_against_version(migrated, CURRENT_SCHEMA_VERSION)
        assert is_valid, f"Migration produced invalid v1.0.0 document: {errors}"


# ---------------------------------------------------------------------------
# 31.4 — schema validation rejection with detailed error messages
# ---------------------------------------------------------------------------


class TestVersionCompatibilityValidation:
    def test_current_version_is_compatible(self):
        doc = make_v1_slide_json()
        is_compatible, err = validate_version_compatibility(doc)
        assert is_compatible
        assert err is None

    def test_previous_version_is_compatible(self):
        doc = make_v0_9_slide_json()
        doc["schema_version"] = "0.9.0"
        is_compatible, err = validate_version_compatibility(doc)
        assert is_compatible
        assert err is None

    def test_incompatible_version_0_8_rejected(self):
        doc = make_v1_slide_json(schema_version="0.8.0")
        is_compatible, err = validate_version_compatibility(doc)
        assert not is_compatible
        assert err is not None
        assert err.version == "0.8.0"

    def test_incompatible_version_0_1_rejected(self):
        doc = make_v1_slide_json(schema_version="0.1.0")
        is_compatible, err = validate_version_compatibility(doc)
        assert not is_compatible
        assert err is not None

    def test_incompatible_version_0_0_1_rejected(self):
        doc = make_v1_slide_json(schema_version="0.0.1")
        is_compatible, err = validate_version_compatibility(doc)
        assert not is_compatible

    def test_error_has_detailed_messages(self):
        doc = make_v1_slide_json(schema_version="0.5.0")
        _, err = validate_version_compatibility(doc)
        assert err is not None
        assert len(err.details) > 0
        assert any("0.5.0" in d for d in err.details)

    def test_error_to_dict_has_required_fields(self):
        doc = make_v1_slide_json(schema_version="0.5.0")
        _, err = validate_version_compatibility(doc)
        d = err.to_dict()
        assert "error" in d
        assert "message" in d
        assert "version" in d
        assert "supported_versions" in d
        assert "current_version" in d
        assert "details" in d
        assert "migration_guide" in d

    def test_schema_version_error_is_value_error(self):
        err = SchemaVersionError("test", version="0.5.0", details=["detail"])
        assert isinstance(err, ValueError)

    def test_unknown_non_semver_version_rejected(self):
        doc = make_v1_slide_json(schema_version="banana")
        is_compatible, err = validate_version_compatibility(doc)
        assert not is_compatible
        assert err is not None


class TestDetectVersion:
    def test_detects_explicit_version(self):
        doc = make_v1_slide_json()
        assert detect_version(doc) == "1.0.0"

    def test_detects_previous_version(self):
        doc = make_v0_9_slide_json()
        doc["schema_version"] = "0.9.0"
        assert detect_version(doc) == "0.9.0"

    def test_infers_v0_9_from_layout_field(self):
        doc = make_v0_9_slide_json()  # no schema_version, has layout
        version = detect_version(doc)
        assert version == PREVIOUS_SCHEMA_VERSION

    def test_infers_v0_9_from_top_level_bullets(self):
        doc = {
            "presentation_id": "abc",
            "total_slides": 1,
            "slides": [{"slide_id": "s1", "type": "content", "title": "T", "bullets": ["A"]}],
        }
        version = detect_version(doc)
        assert version == PREVIOUS_SCHEMA_VERSION

    def test_defaults_to_current_when_no_signals(self):
        doc = {"presentation_id": "abc", "total_slides": 0, "slides": []}
        version = detect_version(doc)
        assert version == CURRENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# ValidationAgent integration — schema versioning hooks
# ---------------------------------------------------------------------------


class TestValidationAgentSchemaVersioning:
    def setup_method(self):
        self.agent = ValidationAgent()

    def test_validate_v1_document_succeeds(self):
        doc = make_v1_slide_json()
        result = self.agent.validate(doc, execution_id="test-exec-1")
        assert result.is_valid

    def test_validate_v0_9_document_migrates_and_succeeds(self):
        doc = make_v0_9_slide_json()
        result = self.agent.validate(doc, execution_id="test-exec-2")
        # After migration the document should be valid
        assert result.corrected_data is not None
        assert result.corrected_data["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_validate_incompatible_version_raises(self):
        doc = make_v1_slide_json(schema_version="0.5.0")
        with pytest.raises(SchemaVersionError) as exc_info:
            self.agent.validate(doc, execution_id="test-exec-3")
        assert exc_info.value.version == "0.5.0"

    def test_validate_missing_schema_version_defaults_to_current(self):
        doc = make_v1_slide_json()
        del doc["schema_version"]
        # No layout or top-level bullets → defaults to current → valid
        result = self.agent.validate(doc, execution_id="test-exec-4")
        assert result.corrected_data["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_validate_v0_9_with_explicit_version_field(self):
        doc = make_v0_9_slide_json()
        doc["schema_version"] = "0.9.0"
        result = self.agent.validate(doc, execution_id="test-exec-5")
        assert result.corrected_data["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_validate_incompatible_error_has_details(self):
        doc = make_v1_slide_json(schema_version="0.3.0")
        with pytest.raises(SchemaVersionError) as exc_info:
            self.agent.validate(doc, execution_id="test-exec-6")
        err = exc_info.value
        assert len(err.details) > 0
        d = err.to_dict()
        assert d["current_version"] == CURRENT_SCHEMA_VERSION
