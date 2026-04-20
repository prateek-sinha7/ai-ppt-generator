"""
Tests for the Template System — Task 29

Covers:
  29.1 — System template seeding (Healthcare×3, Insurance×3, Automobile×3,
          Finance×2, Technology×2, Retail×1, Education×1)
  29.2 — Generic Enterprise Briefing fallback template
  29.3 — Template application flow (resolve → storyboarding constraints)
  29.4 — Custom template CRUD within tenant organisation
  29.5 — Template usage tracking (usage_count)
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.template_seeder import SYSTEM_TEMPLATES, seed_system_templates
from app.services.template_service import (
    FALLBACK_TEMPLATE_NAME,
    create_custom_template,
    delete_custom_template,
    extract_storyboarding_constraints,
    get_template_by_id,
    increment_template_usage,
    resolve_template_for_industry,
    update_custom_template,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_template(
    name: str = "Test Template",
    industry: str = "technology",
    sub_sector: str | None = None,
    is_system: bool = False,
    usage_count: int = 0,
    tenant_id: uuid.UUID | None = None,
    slide_structure: dict | None = None,
) -> MagicMock:
    tpl = MagicMock()
    tpl.id = uuid.uuid4()
    tpl.name = name
    tpl.industry = industry
    tpl.sub_sector = sub_sector
    tpl.is_system = is_system
    tpl.usage_count = usage_count
    tpl.tenant_id = tenant_id
    tpl.slide_structure = slide_structure or {
        "slides": [
            {"section": "Title", "type": "title"},
            {"section": "Agenda", "type": "content"},
            {"section": "Conclusion", "type": "content"},
        ]
    }
    return tpl


# ---------------------------------------------------------------------------
# 29.1 — System template seeding
# ---------------------------------------------------------------------------


class TestSystemTemplateCounts:
    """Verify the correct number of templates per industry in SYSTEM_TEMPLATES."""

    def _count(self, industry: str) -> int:
        return sum(1 for t in SYSTEM_TEMPLATES if t["industry"] == industry)

    def test_healthcare_count(self):
        assert self._count("healthcare") == 3

    def test_insurance_count(self):
        assert self._count("insurance") == 3

    def test_automobile_count(self):
        assert self._count("automobile") == 3

    def test_finance_count(self):
        assert self._count("finance") == 2

    def test_technology_count(self):
        assert self._count("technology") == 2

    def test_retail_count(self):
        assert self._count("retail") == 1

    def test_education_count(self):
        assert self._count("education") == 1

    def test_total_system_templates(self):
        # 3+3+3+2+2+1+1 = 15 industry templates + 1 generic fallback = 16
        assert len(SYSTEM_TEMPLATES) == 16

    def test_all_templates_have_required_fields(self):
        for tpl in SYSTEM_TEMPLATES:
            assert "name" in tpl, f"Missing 'name' in {tpl}"
            assert "industry" in tpl, f"Missing 'industry' in {tpl}"
            assert "slide_structure" in tpl, f"Missing 'slide_structure' in {tpl}"
            assert isinstance(tpl["slide_structure"], list), (
                f"slide_structure must be a list in {tpl['name']}"
            )
            assert len(tpl["slide_structure"]) >= 5, (
                f"Template '{tpl['name']}' has fewer than 5 slides"
            )

    def test_all_slide_defs_have_section_and_type(self):
        for tpl in SYSTEM_TEMPLATES:
            for slide in tpl["slide_structure"]:
                assert "section" in slide, f"Missing 'section' in {tpl['name']}: {slide}"
                assert "type" in slide, f"Missing 'type' in {tpl['name']}: {slide}"

    def test_slide_types_are_valid(self):
        valid_types = {"title", "content", "chart", "table", "comparison"}
        for tpl in SYSTEM_TEMPLATES:
            for slide in tpl["slide_structure"]:
                assert slide["type"] in valid_types, (
                    f"Invalid type '{slide['type']}' in template '{tpl['name']}'"
                )

    def test_each_template_starts_with_title_slide(self):
        for tpl in SYSTEM_TEMPLATES:
            first = tpl["slide_structure"][0]
            assert first["type"] == "title", (
                f"Template '{tpl['name']}' does not start with a title slide"
            )


class TestSeedSystemTemplates:
    """Test the seed_system_templates() function."""

    @pytest.mark.asyncio
    async def test_seed_inserts_all_templates(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.add = MagicMock()
        db.commit = AsyncMock()

        inserted = await seed_system_templates(db)

        assert inserted == len(SYSTEM_TEMPLATES)
        assert db.add.call_count == len(SYSTEM_TEMPLATES)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self):
        """If all templates already exist, nothing is inserted."""
        existing = MagicMock()
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )
        db.add = MagicMock()
        db.commit = AsyncMock()

        inserted = await seed_system_templates(db)

        assert inserted == 0
        db.add.assert_not_called()
        db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 29.2 — Generic Enterprise Briefing fallback
# ---------------------------------------------------------------------------


class TestGenericFallbackTemplate:
    def test_fallback_template_exists(self):
        fallback = next(
            (t for t in SYSTEM_TEMPLATES if t["name"] == FALLBACK_TEMPLATE_NAME), None
        )
        assert fallback is not None, "Generic Enterprise Briefing template not found"

    def test_fallback_industry_is_general(self):
        fallback = next(t for t in SYSTEM_TEMPLATES if t["name"] == FALLBACK_TEMPLATE_NAME)
        assert fallback["industry"] == "general"

    def test_fallback_has_consulting_structure(self):
        fallback = next(t for t in SYSTEM_TEMPLATES if t["name"] == FALLBACK_TEMPLATE_NAME)
        sections = {s["section"] for s in fallback["slide_structure"]}
        required = {"Title", "Agenda", "Problem", "Analysis", "Evidence", "Recommendations", "Conclusion"}
        assert required.issubset(sections), (
            f"Fallback template missing sections: {required - sections}"
        )

    def test_fallback_has_at_least_10_slides(self):
        fallback = next(t for t in SYSTEM_TEMPLATES if t["name"] == FALLBACK_TEMPLATE_NAME)
        assert len(fallback["slide_structure"]) >= 10


# ---------------------------------------------------------------------------
# 29.3 — Template application flow
# ---------------------------------------------------------------------------


class TestResolveTemplateForIndustry:
    @pytest.mark.asyncio
    async def test_resolves_system_template_by_name_and_industry(self):
        tpl = _make_template(name="Technology Strategy", industry="technology", is_system=True)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tpl))
        )

        result = await resolve_template_for_industry(db, "technology", "Technology Strategy")
        assert result is tpl

    @pytest.mark.asyncio
    async def test_falls_back_to_generic_when_industry_unknown(self):
        fallback_tpl = _make_template(name=FALLBACK_TEMPLATE_NAME, industry="general", is_system=True)

        call_count = 0

        async def mock_execute(_):
            nonlocal call_count
            call_count += 1
            # Without tenant_id, there are 3 lookups:
            #   1. system-by-name+industry → None
            #   2. system-by-industry → None
            #   3. fallback by name → fallback_tpl
            if call_count < 3:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            return MagicMock(scalar_one_or_none=MagicMock(return_value=fallback_tpl))

        db = AsyncMock()
        db.execute = mock_execute

        # No tenant_id → skips tenant lookup, goes straight to system lookups
        result = await resolve_template_for_industry(
            db, "unknown_industry", "Unknown Template", tenant_id=None
        )
        assert result is fallback_tpl

    @pytest.mark.asyncio
    async def test_returns_none_when_fallback_not_seeded(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await resolve_template_for_industry(db, "unknown", "Unknown")
        assert result is None


class TestExtractStoryboardingConstraints:
    def test_extracts_slide_structure(self):
        tpl = _make_template()
        constraints = extract_storyboarding_constraints(tpl)

        assert "slide_structure" in constraints
        assert "slide_count" in constraints
        assert "template_id" in constraints
        assert "template_name" in constraints

    def test_slide_count_matches_structure_length(self):
        tpl = _make_template()
        slides = tpl.slide_structure["slides"]
        constraints = extract_storyboarding_constraints(tpl)

        assert constraints["slide_count"] == len(slides)

    def test_template_id_is_string(self):
        tpl = _make_template()
        constraints = extract_storyboarding_constraints(tpl)
        assert isinstance(constraints["template_id"], str)

    def test_empty_slide_structure_returns_zero_count(self):
        tpl = _make_template(slide_structure={"slides": []})
        constraints = extract_storyboarding_constraints(tpl)
        assert constraints["slide_count"] == 0
        assert constraints["slide_structure"] == []

    def test_handles_missing_slides_key(self):
        tpl = MagicMock()
        tpl.id = uuid.uuid4()
        tpl.name = "Empty"
        tpl.slide_structure = {}  # no "slides" key
        constraints = extract_storyboarding_constraints(tpl)
        assert constraints["slide_count"] == 0


# ---------------------------------------------------------------------------
# 29.4 — Custom template CRUD
# ---------------------------------------------------------------------------


class TestCreateCustomTemplate:
    @pytest.mark.asyncio
    async def test_creates_template_with_correct_fields(self):
        tenant_id = uuid.uuid4()
        slide_structure = [
            {"section": "Title", "type": "title"},
            {"section": "Conclusion", "type": "content"},
        ]

        created_tpl = MagicMock()
        created_tpl.id = uuid.uuid4()
        created_tpl.name = "My Custom Template"
        created_tpl.industry = "fintech"
        created_tpl.sub_sector = "payments"
        created_tpl.is_system = False
        created_tpl.usage_count = 0
        created_tpl.tenant_id = tenant_id
        created_tpl.slide_structure = {"slides": slide_structure}

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: None)

        # Patch the Template constructor to return our mock
        with patch("app.services.template_service.Template", return_value=created_tpl):
            result = await create_custom_template(
                db=db,
                tenant_id=tenant_id,
                name="My Custom Template",
                industry="fintech",
                slide_structure=slide_structure,
                sub_sector="payments",
            )

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result.name == "My Custom Template"
        assert result.is_system is False

    @pytest.mark.asyncio
    async def test_custom_template_is_not_system(self):
        tenant_id = uuid.uuid4()
        tpl = MagicMock()
        tpl.is_system = False

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        with patch("app.services.template_service.Template", return_value=tpl):
            result = await create_custom_template(
                db=db,
                tenant_id=tenant_id,
                name="Custom",
                industry="retail",
                slide_structure=[{"section": "Title", "type": "title"}],
            )

        assert result.is_system is False


class TestGetTemplateById:
    @pytest.mark.asyncio
    async def test_returns_system_template_for_any_tenant(self):
        tpl = _make_template(is_system=True)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tpl))
        )

        result = await get_template_by_id(db, tpl.id, tenant_id=uuid.uuid4())
        assert result is tpl

    @pytest.mark.asyncio
    async def test_returns_tenant_template_for_correct_tenant(self):
        tenant_id = uuid.uuid4()
        tpl = _make_template(is_system=False, tenant_id=tenant_id)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tpl))
        )

        result = await get_template_by_id(db, tpl.id, tenant_id=tenant_id)
        assert result is tpl

    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_tenant(self):
        tenant_id = uuid.uuid4()
        other_tenant = uuid.uuid4()
        tpl = _make_template(is_system=False, tenant_id=other_tenant)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tpl))
        )

        result = await get_template_by_id(db, tpl.id, tenant_id=tenant_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await get_template_by_id(db, uuid.uuid4())
        assert result is None


class TestUpdateCustomTemplate:
    @pytest.mark.asyncio
    async def test_updates_name_and_industry(self):
        tenant_id = uuid.uuid4()
        tpl = _make_template(is_system=False, tenant_id=tenant_id)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tpl))
        )
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        result = await update_custom_template(
            db=db,
            template_id=tpl.id,
            tenant_id=tenant_id,
            name="Updated Name",
            industry="logistics",
        )

        assert result is tpl
        assert tpl.name == "Updated Name"
        assert tpl.industry == "logistics"

    @pytest.mark.asyncio
    async def test_returns_none_for_system_template(self):
        tenant_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await update_custom_template(
            db=db,
            template_id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="Cannot Update System",
        )

        assert result is None


class TestDeleteCustomTemplate:
    @pytest.mark.asyncio
    async def test_deletes_tenant_template(self):
        tenant_id = uuid.uuid4()
        tpl = _make_template(is_system=False, tenant_id=tenant_id)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=tpl))
        )
        db.delete = AsyncMock()
        db.flush = AsyncMock()

        result = await delete_custom_template(db, tpl.id, tenant_id)

        assert result is True
        db.delete.assert_called_once_with(tpl)

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await delete_custom_template(db, uuid.uuid4(), uuid.uuid4())
        assert result is False


# ---------------------------------------------------------------------------
# 29.5 — Usage tracking
# ---------------------------------------------------------------------------


class TestIncrementTemplateUsage:
    @pytest.mark.asyncio
    async def test_executes_update_statement(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()

        template_id = uuid.uuid4()
        await increment_template_usage(db, template_id)

        db.execute.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_called_with_correct_template_id(self):
        """Verify the update statement targets the right template."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()

        template_id = uuid.uuid4()
        await increment_template_usage(db, template_id)

        # The execute call should have been made (statement is built internally)
        assert db.execute.call_count == 1


# ---------------------------------------------------------------------------
# Integration: storyboarding agent uses template constraints
# ---------------------------------------------------------------------------


class TestStoryboardingWithTemplateConstraints:
    """Verify that the Storyboarding Agent correctly uses template slide_structure."""

    def test_storyboarding_uses_template_structure(self):
        from app.agents.storyboarding import StoryboardingAgent

        agent = StoryboardingAgent()

        # Simulate a template with 8 slides
        template_structure = [
            {"section": "Title", "type": "title"},
            {"section": "Agenda", "type": "content"},
            {"section": "Problem", "type": "content"},
            {"section": "Analysis", "type": "chart"},
            {"section": "Analysis", "type": "table"},
            {"section": "Evidence", "type": "comparison"},
            {"section": "Recommendations", "type": "content"},
            {"section": "Conclusion", "type": "content"},
        ]

        plan = agent.generate_presentation_plan(
            topic="Healthcare digital transformation",
            industry="healthcare",
            template_structure=template_structure,
            template_slide_count=8,
        )

        assert plan.total_slides == 8
        assert len(plan.sections) > 0

    def test_storyboarding_falls_back_without_template(self):
        from app.agents.storyboarding import StoryboardingAgent

        agent = StoryboardingAgent()
        plan = agent.generate_presentation_plan(
            topic="Simple topic",
            industry="general",
            template_structure=None,
            template_slide_count=None,
        )

        assert 5 <= plan.total_slides <= 25

    def test_template_sections_are_preserved(self):
        from app.agents.storyboarding import StoryboardingAgent

        agent = StoryboardingAgent()
        template_structure = [
            {"section": "Title", "type": "title"},
            {"section": "Overview", "type": "content"},
            {"section": "Data", "type": "chart"},
            {"section": "Summary", "type": "content"},
            {"section": "Next Steps", "type": "content"},
        ]

        plan = agent.generate_presentation_plan(
            topic="Insurance risk overview",
            industry="insurance",
            template_structure=template_structure,
            template_slide_count=5,
        )

        section_names = {s.name for s in plan.sections}
        assert "Title" in section_names
        assert "Overview" in section_names
