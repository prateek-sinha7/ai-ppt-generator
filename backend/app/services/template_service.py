"""
Template Service — Tasks 29.3, 29.4, 29.5

Responsibilities:
  29.3 — Template application flow: load slide_structure → pass as Storyboarding constraint
  29.4 — Custom template creation and sharing within tenant organisation
  29.5 — Template usage tracking (usage_count) for effectiveness analytics
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template

logger = structlog.get_logger(__name__)

# Name of the fallback template (must match seeder)
FALLBACK_TEMPLATE_NAME = "Generic Enterprise Briefing"


# ---------------------------------------------------------------------------
# 29.3 — Template application flow
# ---------------------------------------------------------------------------

async def resolve_template_for_industry(
    db: AsyncSession,
    industry: str,
    template_name: str,
    tenant_id: Optional[uuid.UUID] = None,
) -> Optional[Template]:
    """
    Resolve the best-fit template for a given industry and template name.

    Lookup order:
      1. Tenant-specific template matching name + industry
      2. System template matching name + industry
      3. System template matching industry (any name)
      4. Generic Enterprise Briefing fallback

    Returns the Template ORM object or None if nothing found.
    """
    # 1. Tenant-specific template
    if tenant_id:
        result = await db.execute(
            select(Template).where(
                Template.tenant_id == tenant_id,
                Template.industry == industry,
                Template.name == template_name,
            )
        )
        tpl = result.scalar_one_or_none()
        if tpl:
            logger.info(
                "template_resolved_tenant",
                name=tpl.name,
                industry=industry,
                tenant_id=str(tenant_id),
            )
            return tpl

    # 2. System template by name + industry
    result = await db.execute(
        select(Template).where(
            Template.is_system == True,
            Template.industry == industry,
            Template.name == template_name,
        )
    )
    tpl = result.scalar_one_or_none()
    if tpl:
        logger.info("template_resolved_system_name", name=tpl.name, industry=industry)
        return tpl

    # 3. Any system template for the industry
    result = await db.execute(
        select(Template)
        .where(Template.is_system == True, Template.industry == industry)
        .order_by(Template.usage_count.desc())
        .limit(1)
    )
    tpl = result.scalar_one_or_none()
    if tpl:
        logger.info("template_resolved_system_industry", name=tpl.name, industry=industry)
        return tpl

    # 4. Fallback: Generic Enterprise Briefing
    result = await db.execute(
        select(Template).where(
            Template.is_system == True,
            Template.name == FALLBACK_TEMPLATE_NAME,
        )
    )
    tpl = result.scalar_one_or_none()
    if tpl:
        logger.info(
            "template_resolved_fallback",
            industry=industry,
            fallback=FALLBACK_TEMPLATE_NAME,
        )
    else:
        logger.warning("template_fallback_not_found", industry=industry)

    return tpl


def extract_storyboarding_constraints(template: Template) -> dict[str, Any]:
    """
    Extract storyboarding constraints from a template.

    Returns a dict with:
      - slide_structure: list of slide defs for Storyboarding Agent
      - slide_count: total number of slides in the template
      - template_id: UUID string
      - template_name: human-readable name
    """
    raw = template.slide_structure or {}
    slides = raw.get("slides", []) if isinstance(raw, dict) else []

    return {
        "slide_structure": slides,
        "slide_count": len(slides),
        "template_id": str(template.id),
        "template_name": template.name,
    }


# ---------------------------------------------------------------------------
# 29.5 — Usage tracking
# ---------------------------------------------------------------------------

async def increment_template_usage(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> None:
    """
    Atomically increment the usage_count for a template.

    Called by the pipeline after a template is applied to a presentation.
    """
    await db.execute(
        update(Template)
        .where(Template.id == template_id)
        .values(usage_count=Template.usage_count + 1)
    )
    await db.flush()
    logger.debug("template_usage_incremented", template_id=str(template_id))


# ---------------------------------------------------------------------------
# 29.4 — Custom template CRUD
# ---------------------------------------------------------------------------

async def create_custom_template(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    industry: str,
    slide_structure: list[dict[str, Any]],
    sub_sector: Optional[str] = None,
) -> Template:
    """
    Create a custom template scoped to a tenant organisation.

    The template is immediately available to all users within the same tenant.
    """
    template = Template(
        tenant_id=tenant_id,
        name=name,
        industry=industry,
        sub_sector=sub_sector,
        slide_structure={"slides": slide_structure},
        is_system=False,
        usage_count=0,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    logger.info(
        "custom_template_created",
        template_id=str(template.id),
        name=name,
        industry=industry,
        tenant_id=str(tenant_id),
    )
    return template


async def get_template_by_id(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: Optional[uuid.UUID] = None,
) -> Optional[Template]:
    """
    Fetch a template by ID.

    If tenant_id is provided, only returns the template if it is a system
    template or belongs to the given tenant.
    """
    result = await db.execute(
        select(Template).where(Template.id == template_id)
    )
    tpl = result.scalar_one_or_none()

    if tpl is None:
        return None

    # Access control: system templates are visible to all; tenant templates
    # are only visible within the owning tenant.
    if not tpl.is_system and tenant_id and tpl.tenant_id != tenant_id:
        return None

    return tpl


async def update_custom_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
    name: Optional[str] = None,
    industry: Optional[str] = None,
    slide_structure: Optional[list[dict[str, Any]]] = None,
    sub_sector: Optional[str] = None,
) -> Optional[Template]:
    """
    Update a custom (non-system) template owned by the given tenant.

    Returns the updated template or None if not found / not authorised.
    """
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
            Template.tenant_id == tenant_id,
            Template.is_system == False,
        )
    )
    tpl = result.scalar_one_or_none()
    if tpl is None:
        return None

    if name is not None:
        tpl.name = name
    if industry is not None:
        tpl.industry = industry
    if sub_sector is not None:
        tpl.sub_sector = sub_sector
    if slide_structure is not None:
        tpl.slide_structure = {"slides": slide_structure}

    await db.flush()
    await db.refresh(tpl)

    logger.info(
        "custom_template_updated",
        template_id=str(template_id),
        tenant_id=str(tenant_id),
    )
    return tpl


async def delete_custom_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    """
    Delete a custom template owned by the given tenant.

    Returns True if deleted, False if not found or not authorised.
    System templates cannot be deleted via this method.
    """
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
            Template.tenant_id == tenant_id,
            Template.is_system == False,
        )
    )
    tpl = result.scalar_one_or_none()
    if tpl is None:
        return False

    await db.delete(tpl)
    await db.flush()

    logger.info(
        "custom_template_deleted",
        template_id=str(template_id),
        tenant_id=str(tenant_id),
    )
    return True
