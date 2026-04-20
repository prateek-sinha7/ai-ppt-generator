"""
Tests for the Slide Editing and Versioning API (Task 18).

Covers:
- 18.1  PATCH /api/v1/presentations/{id}/slides/{slide_id}
- 18.2  POST  /api/v1/presentations/{id}/slides/{slide_id}/regenerate
- 18.3  POST/DELETE /api/v1/presentations/{id}/slides/{slide_id}/lock
- 18.4  PATCH /api/v1/presentations/{id}/slides/reorder
- 18.5  GET   /api/v1/presentations/{id}/versions[/{version}]
- 18.6  POST  /api/v1/presentations/{id}/rollback
- 18.6  GET   /api/v1/presentations/{id}/diff
- 18.7  POST  /api/v1/presentations/{id}/merge
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_slide(
    slide_id: str = None,
    slide_number: int = 1,
    slide_type: str = "content",
    title: str = "Test Slide",
) -> Dict[str, Any]:
    return {
        "slide_id": slide_id or str(uuid.uuid4()),
        "slide_number": slide_number,
        "type": slide_type,
        "title": title,
        "content": {"bullets": ["Point A", "Point B"]},
        "visual_hint": "bullet-left",
        "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
        "metadata": {"generated_at": "2024-01-01T00:00:00Z", "provider_used": "claude"},
    }


def _make_slides_list(count: int = 5) -> List[Dict[str, Any]]:
    types = ["title", "content", "chart", "content", "content"]
    titles = ["Title", "Agenda", "Problem", "Analysis", "Conclusion"]
    slides = []
    for i in range(count):
        t = types[i] if i < len(types) else "content"
        title = titles[i] if i < len(titles) else f"Slide {i + 1}"
        slides.append(_make_slide(slide_number=i + 1, slide_type=t, title=title))
    return slides


# ---------------------------------------------------------------------------
# 18.1  SlideContentUpdate schema
# ---------------------------------------------------------------------------


class TestSlideContentUpdate:
    """Pydantic schema validation for slide content updates."""

    def test_title_max_8_words_accepted(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        req = SlideContentUpdate(title="This is a valid title here")
        assert req.title == "This is a valid title here"

    def test_title_9_words_rejected(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        with pytest.raises(ValidationError):
            SlideContentUpdate(title="one two three four five six seven eight nine")

    def test_bullets_max_4_accepted(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        req = SlideContentUpdate(bullets=["A", "B", "C", "D"])
        assert len(req.bullets) == 4

    def test_bullets_5_rejected(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        with pytest.raises(ValidationError):
            SlideContentUpdate(bullets=["A", "B", "C", "D", "E"])

    def test_bullet_max_8_words_accepted(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        req = SlideContentUpdate(bullets=["one two three four five six seven eight"])
        assert req.bullets[0] == "one two three four five six seven eight"

    def test_bullet_9_words_rejected(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        with pytest.raises(ValidationError):
            SlideContentUpdate(bullets=["one two three four five six seven eight nine"])

    def test_valid_visual_hint_accepted(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        for hint in ("centered", "bullet-left", "split-chart-right",
                     "split-table-left", "two-column", "highlight-metric"):
            req = SlideContentUpdate(visual_hint=hint)
            assert req.visual_hint == hint

    def test_invalid_visual_hint_rejected(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        with pytest.raises(ValidationError):
            SlideContentUpdate(visual_hint="free-text-layout")

    def test_valid_transition_accepted(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        for t in ("fade", "slide", "none"):
            req = SlideContentUpdate(transition=t)
            assert req.transition == t

    def test_invalid_transition_rejected(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        with pytest.raises(ValidationError):
            SlideContentUpdate(transition="zoom")

    def test_all_fields_optional(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        req = SlideContentUpdate()
        assert req.title is None
        assert req.bullets is None
        assert req.visual_hint is None

    def test_partial_update_only_title(self):
        from app.api.v1.slide_editing import SlideContentUpdate

        req = SlideContentUpdate(title="New Title")
        data = req.model_dump(exclude_none=True)
        assert list(data.keys()) == ["title"]


# ---------------------------------------------------------------------------
# 18.2  RegenerateSlideRequest schema
# ---------------------------------------------------------------------------


class TestRegenerateSlideRequest:
    def test_no_provider_field(self):
        from app.api.v1.slide_editing import RegenerateSlideRequest

        fields = RegenerateSlideRequest.model_fields
        assert "provider" not in fields
        assert "theme" not in fields

    def test_instantiates_empty(self):
        from app.api.v1.slide_editing import RegenerateSlideRequest

        req = RegenerateSlideRequest()
        assert req is not None


# ---------------------------------------------------------------------------
# 18.3  Lock schemas
# ---------------------------------------------------------------------------


class TestSlideLockSchemas:
    def test_lock_response_fields(self):
        from app.api.v1.slide_editing import SlideLockResponse

        fields = SlideLockResponse.model_fields
        assert "presentation_id" in fields
        assert "slide_id" in fields
        assert "locked_by" in fields
        assert "locked_at" in fields
        assert "expires_at" in fields

    def test_lock_ttl_constant(self):
        from app.api.v1.slide_editing import SLIDE_LOCK_TTL_SECONDS

        assert SLIDE_LOCK_TTL_SECONDS == 300  # 5 minutes


# ---------------------------------------------------------------------------
# 18.4  ReorderRequest schema
# ---------------------------------------------------------------------------


class TestReorderRequest:
    def test_valid_order_accepted(self):
        from app.api.v1.slide_editing import ReorderRequest

        ids = [str(uuid.uuid4()) for _ in range(5)]
        req = ReorderRequest(slide_order=ids)
        assert req.slide_order == ids

    def test_duplicate_ids_rejected(self):
        from app.api.v1.slide_editing import ReorderRequest

        sid = str(uuid.uuid4())
        with pytest.raises(ValidationError):
            ReorderRequest(slide_order=[sid, sid])

    def test_reorder_response_fields(self):
        from app.api.v1.slide_editing import ReorderResponse

        fields = ReorderResponse.model_fields
        assert "presentation_id" in fields
        assert "version_number" in fields
        assert "slide_order" in fields
        assert "narrative_valid" in fields
        assert "message" in fields


# ---------------------------------------------------------------------------
# 18.4  Narrative flow validation
# ---------------------------------------------------------------------------


class TestNarrativeFlowValidation:
    def test_valid_narrative_starts_with_title(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        slides = _make_slides_list(5)
        assert _validate_narrative_flow(slides) is True

    def test_invalid_narrative_no_title_first(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        slides = _make_slides_list(5)
        slides[0]["type"] = "content"  # break the rule
        assert _validate_narrative_flow(slides) is False

    def test_invalid_narrative_no_data_slide(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        slides = [
            _make_slide(slide_number=1, slide_type="title"),
            _make_slide(slide_number=2, slide_type="content"),
            _make_slide(slide_number=3, slide_type="content"),
        ]
        assert _validate_narrative_flow(slides) is False

    def test_valid_narrative_with_chart(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        slides = [
            _make_slide(slide_number=1, slide_type="title"),
            _make_slide(slide_number=2, slide_type="content"),
            _make_slide(slide_number=3, slide_type="chart"),
        ]
        assert _validate_narrative_flow(slides) is True

    def test_valid_narrative_with_table(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        slides = [
            _make_slide(slide_number=1, slide_type="title"),
            _make_slide(slide_number=2, slide_type="content"),
            _make_slide(slide_number=3, slide_type="table"),
        ]
        assert _validate_narrative_flow(slides) is True

    def test_empty_slides_invalid(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        assert _validate_narrative_flow([]) is False

    def test_minimal_deck_skips_strict_validation(self):
        from app.api.v1.slide_editing import _validate_narrative_flow

        slides = [
            _make_slide(slide_number=1, slide_type="title"),
            _make_slide(slide_number=2, slide_type="content"),
        ]
        # 2 slides — minimal deck, skip strict validation
        assert _validate_narrative_flow(slides) is True


# ---------------------------------------------------------------------------
# 18.5  Version schemas
# ---------------------------------------------------------------------------


class TestVersionSchemas:
    def test_version_summary_fields(self):
        from app.api.v1.slide_editing import VersionSummary

        fields = VersionSummary.model_fields
        assert "version_id" in fields
        assert "version_number" in fields
        assert "created_at" in fields
        assert "slide_count" in fields
        assert "parent_version" in fields
        assert "merge_source" in fields

    def test_version_list_response_fields(self):
        from app.api.v1.slide_editing import VersionListResponse

        fields = VersionListResponse.model_fields
        assert "presentation_id" in fields
        assert "versions" in fields


# ---------------------------------------------------------------------------
# 18.6  Rollback and Diff schemas
# ---------------------------------------------------------------------------


class TestRollbackSchemas:
    def test_rollback_request_requires_version_number(self):
        from app.api.v1.slide_editing import RollbackRequest

        with pytest.raises(ValidationError):
            RollbackRequest()

    def test_rollback_request_version_must_be_positive(self):
        from app.api.v1.slide_editing import RollbackRequest

        with pytest.raises(ValidationError):
            RollbackRequest(version_number=0)

    def test_rollback_response_fields(self):
        from app.api.v1.slide_editing import RollbackResponse

        fields = RollbackResponse.model_fields
        assert "presentation_id" in fields
        assert "rolled_back_to" in fields
        assert "new_version_number" in fields
        assert "message" in fields


class TestDiffSchemas:
    def test_diff_response_fields(self):
        from app.api.v1.slide_editing import DiffResponse

        fields = DiffResponse.model_fields
        assert "presentation_id" in fields
        assert "version_a" in fields
        assert "version_b" in fields
        assert "changes" in fields
        assert "total_changes" in fields

    def test_diff_slide_change_types(self):
        from app.api.v1.slide_editing import DiffSlide

        for change_type in ("added", "removed", "modified", "unchanged"):
            d = DiffSlide(slide_id="abc", change_type=change_type)
            assert d.change_type == change_type


# ---------------------------------------------------------------------------
# 18.6  Diff computation logic
# ---------------------------------------------------------------------------


class TestDiffComputation:
    def test_identical_slides_all_unchanged(self):
        from app.api.v1.slide_editing import _compute_slide_diff

        slides = _make_slides_list(3)
        changes = _compute_slide_diff(slides, slides)
        assert all(c.change_type == "unchanged" for c in changes)

    def test_added_slide_detected(self):
        from app.api.v1.slide_editing import _compute_slide_diff

        slides_a = _make_slides_list(2)
        new_slide = _make_slide(slide_number=3, slide_type="content")
        slides_b = slides_a + [new_slide]

        changes = _compute_slide_diff(slides_a, slides_b)
        added = [c for c in changes if c.change_type == "added"]
        assert len(added) == 1
        assert added[0].slide_id == new_slide["slide_id"]

    def test_removed_slide_detected(self):
        from app.api.v1.slide_editing import _compute_slide_diff

        slides_a = _make_slides_list(3)
        slides_b = slides_a[:2]

        changes = _compute_slide_diff(slides_a, slides_b)
        removed = [c for c in changes if c.change_type == "removed"]
        assert len(removed) == 1

    def test_modified_slide_detected(self):
        from app.api.v1.slide_editing import _compute_slide_diff

        import copy
        slides_a = _make_slides_list(2)
        slides_b = copy.deepcopy(slides_a)
        slides_b[1]["title"] = "Modified Title"

        changes = _compute_slide_diff(slides_a, slides_b)
        modified = [c for c in changes if c.change_type == "modified"]
        assert len(modified) == 1
        assert modified[0].before["title"] != modified[0].after["title"]

    def test_total_changes_excludes_unchanged(self):
        from app.api.v1.slide_editing import _compute_slide_diff

        import copy
        slides_a = _make_slides_list(3)
        slides_b = copy.deepcopy(slides_a)
        slides_b[0]["title"] = "Changed"

        changes = _compute_slide_diff(slides_a, slides_b)
        non_unchanged = [c for c in changes if c.change_type != "unchanged"]
        assert len(non_unchanged) == 1


# ---------------------------------------------------------------------------
# 18.7  Merge schemas and logic
# ---------------------------------------------------------------------------


class TestMergeSchemas:
    def test_merge_request_valid_strategies(self):
        from app.api.v1.slide_editing import MergeRequest

        for strategy in ("ours", "theirs", "manual"):
            req = MergeRequest(source_version=1, target_version=2, strategy=strategy)
            assert req.strategy == strategy

    def test_merge_request_invalid_strategy_rejected(self):
        from app.api.v1.slide_editing import MergeRequest

        with pytest.raises(ValidationError):
            MergeRequest(source_version=1, target_version=2, strategy="auto")

    def test_merge_request_default_strategy_is_ours(self):
        from app.api.v1.slide_editing import MergeRequest

        req = MergeRequest(source_version=1, target_version=2)
        assert req.strategy == "ours"

    def test_merge_response_fields(self):
        from app.api.v1.slide_editing import MergeResponse

        fields = MergeResponse.model_fields
        assert "presentation_id" in fields
        assert "merged_version_number" in fields
        assert "source_version" in fields
        assert "target_version" in fields
        assert "conflicts_resolved" in fields
        assert "message" in fields


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


class TestRouterRegistration:
    def test_router_has_update_slide_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/slides/{slide_id}" in routes

    def test_router_has_regenerate_slide_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/slides/{slide_id}/regenerate" in routes

    def test_router_has_lock_routes(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/slides/{slide_id}/lock" in routes

    def test_router_has_reorder_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/slides/reorder" in routes

    def test_router_has_versions_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/versions" in routes

    def test_router_has_version_detail_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/versions/{version_number}" in routes

    def test_router_has_rollback_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/rollback" in routes

    def test_router_has_diff_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/diff" in routes

    def test_router_has_merge_route(self):
        from app.api.v1.slide_editing import router

        routes = {r.path for r in router.routes}
        assert "/presentations/{presentation_id}/merge" in routes

    def test_update_slide_method_is_patch(self):
        from app.api.v1.slide_editing import router

        patch_routes = [r for r in router.routes if "PATCH" in getattr(r, "methods", set())]
        paths = {r.path for r in patch_routes}
        assert "/presentations/{presentation_id}/slides/{slide_id}" in paths

    def test_lock_post_method(self):
        from app.api.v1.slide_editing import router

        post_routes = [r for r in router.routes if "POST" in getattr(r, "methods", set())]
        paths = {r.path for r in post_routes}
        assert "/presentations/{presentation_id}/slides/{slide_id}/lock" in paths

    def test_lock_delete_method(self):
        from app.api.v1.slide_editing import router

        delete_routes = [r for r in router.routes if "DELETE" in getattr(r, "methods", set())]
        paths = {r.path for r in delete_routes}
        assert "/presentations/{presentation_id}/slides/{slide_id}/lock" in paths

    def test_reorder_method_is_patch(self):
        from app.api.v1.slide_editing import router

        patch_routes = [r for r in router.routes if "PATCH" in getattr(r, "methods", set())]
        paths = {r.path for r in patch_routes}
        assert "/presentations/{presentation_id}/slides/reorder" in paths

    def test_rollback_method_is_post(self):
        from app.api.v1.slide_editing import router

        post_routes = [r for r in router.routes if "POST" in getattr(r, "methods", set())]
        paths = {r.path for r in post_routes}
        assert "/presentations/{presentation_id}/rollback" in paths

    def test_diff_method_is_get(self):
        from app.api.v1.slide_editing import router

        get_routes = [r for r in router.routes if "GET" in getattr(r, "methods", set())]
        paths = {r.path for r in get_routes}
        assert "/presentations/{presentation_id}/diff" in paths

    def test_merge_method_is_post(self):
        from app.api.v1.slide_editing import router

        post_routes = [r for r in router.routes if "POST" in getattr(r, "methods", set())]
        paths = {r.path for r in post_routes}
        assert "/presentations/{presentation_id}/merge" in paths


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_valid_visual_hints_set(self):
        from app.api.v1.slide_editing import _VALID_VISUAL_HINTS

        expected = {
            "centered", "bullet-left", "split-chart-right",
            "split-table-left", "two-column", "highlight-metric",
        }
        assert _VALID_VISUAL_HINTS == expected

    def test_valid_slide_types_set(self):
        from app.api.v1.slide_editing import _VALID_SLIDE_TYPES

        expected = {"title", "content", "chart", "table", "comparison"}
        assert _VALID_SLIDE_TYPES == expected

    def test_get_slides_list_from_list(self):
        """_get_slides_list handles slides stored as a plain list."""
        import asyncio
        from unittest.mock import MagicMock
        from app.api.v1.slide_editing import _get_slides_list

        slides = _make_slides_list(3)
        presentation = MagicMock()
        presentation.slides = slides

        result = asyncio.get_event_loop().run_until_complete(_get_slides_list(presentation))
        assert result == slides

    def test_get_slides_list_from_dict(self):
        """_get_slides_list handles slides stored as a dict with 'slides' key."""
        import asyncio
        from unittest.mock import MagicMock
        from app.api.v1.slide_editing import _get_slides_list

        slides = _make_slides_list(3)
        presentation = MagicMock()
        presentation.slides = {"slides": slides, "total": 3}

        result = asyncio.get_event_loop().run_until_complete(_get_slides_list(presentation))
        assert result == slides

    def test_get_slides_list_none_returns_empty(self):
        """_get_slides_list handles None slides."""
        import asyncio
        from unittest.mock import MagicMock
        from app.api.v1.slide_editing import _get_slides_list

        presentation = MagicMock()
        presentation.slides = None

        result = asyncio.get_event_loop().run_until_complete(_get_slides_list(presentation))
        assert result == []
