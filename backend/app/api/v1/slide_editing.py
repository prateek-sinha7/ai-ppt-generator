"""
Slide Editing and Versioning API — Task 18.

Endpoints:
  PATCH  /api/v1/presentations/{id}/slides/{slide_id}            — 18.1 Content modification
  POST   /api/v1/presentations/{id}/slides/{slide_id}/regenerate — 18.2 Single slide regen
  POST   /api/v1/presentations/{id}/slides/{slide_id}/lock       — 18.3 Lock slide
  DELETE /api/v1/presentations/{id}/slides/{slide_id}/lock       — 18.3 Unlock slide
  PATCH  /api/v1/presentations/{id}/slides/reorder               — 18.4 Reorder with narrative validation
  GET    /api/v1/presentations/{id}/versions                     — 18.5 List versions
  GET    /api/v1/presentations/{id}/versions/{version}           — 18.5 Get specific version
  POST   /api/v1/presentations/{id}/rollback                     — 18.6 Rollback to version
  GET    /api/v1/presentations/{id}/diff                         — 18.6 Diff two versions
  POST   /api/v1/presentations/{id}/merge                        — 18.7 Merge branches
"""
from __future__ import annotations

import copy
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_min_role
from app.db.models import (
    Presentation,
    PresentationVersion,
    SlideLock,
    PresentationStatus,
    User,
)
from app.db.session import get_db

router = APIRouter(tags=["slide-editing"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SLIDE_LOCK_TTL_SECONDS = 300  # 5-minute lock TTL

# Consulting storytelling structure — required slide type order for narrative validation
_NARRATIVE_SEQUENCE = [
    "title",
    "content",  # agenda/overview
    "content",  # problem/context
    "content",  # analysis/insights
    "chart",    # data-backed evidence
    "content",  # recommendations
    "content",  # conclusion
]

# Valid visual_hint enum values (Req 17)
_VALID_VISUAL_HINTS = {
    "centered",
    "bullet-left",
    "split-chart-right",
    "split-table-left",
    "two-column",
    "highlight-metric",
}

# Valid slide types
_VALID_SLIDE_TYPES = {"title", "content", "chart", "table", "comparison"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SlideContentUpdate(BaseModel):
    """Partial update payload for a single slide (18.1)."""

    title: Optional[str] = Field(None, description="Slide title (max 8 words)")
    bullets: Optional[List[str]] = Field(None, description="Bullet points (max 4, max 8 words each)")
    chart_data: Optional[Dict[str, Any]] = None
    table_data: Optional[Dict[str, Any]] = None
    comparison_data: Optional[Dict[str, Any]] = None
    icon_name: Optional[str] = None
    highlight_text: Optional[str] = None
    transition: Optional[str] = Field(None, pattern="^(fade|slide|none)$")
    visual_hint: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_max_words(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            words = v.strip().split()
            if len(words) > 8:
                raise ValueError("Title must not exceed 8 words")
        return v

    @field_validator("bullets")
    @classmethod
    def bullets_constraints(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if len(v) > 4:
                raise ValueError("Maximum 4 bullets per slide")
            for bullet in v:
                if len(bullet.strip().split()) > 8:
                    raise ValueError("Each bullet must not exceed 8 words")
        return v

    @field_validator("visual_hint")
    @classmethod
    def valid_visual_hint(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_VISUAL_HINTS:
            raise ValueError(f"visual_hint must be one of: {sorted(_VALID_VISUAL_HINTS)}")
        return v


class SlideUpdateResponse(BaseModel):
    presentation_id: str
    slide_id: str
    version_number: int
    message: str


class RegenerateSlideRequest(BaseModel):
    """No provider field — backend selects from .env (Req 13)."""
    pass


class RegenerateSlideResponse(BaseModel):
    job_id: str
    presentation_id: str
    slide_id: str
    status: str
    message: str


class SlideLockResponse(BaseModel):
    presentation_id: str
    slide_id: str
    locked_by: str
    locked_at: str
    expires_at: str


class ReorderRequest(BaseModel):
    slide_order: List[str] = Field(..., description="Ordered list of slide_ids")

    @field_validator("slide_order")
    @classmethod
    def no_duplicates(cls, v: List[str]) -> List[str]:
        if len(v) != len(set(v)):
            raise ValueError("slide_order must not contain duplicate slide_ids")
        return v


class ReorderResponse(BaseModel):
    presentation_id: str
    version_number: int
    slide_order: List[str]
    narrative_valid: bool
    message: str


class VersionSummary(BaseModel):
    version_id: str
    version_number: int
    created_at: str
    created_by: Optional[str]
    parent_version: Optional[str]
    merge_source: Optional[str]
    slide_count: int


class VersionListResponse(BaseModel):
    presentation_id: str
    versions: List[VersionSummary]


class RollbackRequest(BaseModel):
    version_number: int = Field(..., ge=1)


class RollbackResponse(BaseModel):
    presentation_id: str
    rolled_back_to: int
    new_version_number: int
    message: str


class DiffSlide(BaseModel):
    slide_id: str
    change_type: str  # "added" | "removed" | "modified" | "unchanged"
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None


class DiffResponse(BaseModel):
    presentation_id: str
    version_a: int
    version_b: int
    changes: List[DiffSlide]
    total_changes: int


class MergeRequest(BaseModel):
    source_version: int = Field(..., ge=1, description="Version number to merge from")
    target_version: int = Field(..., ge=1, description="Version number to merge into")
    strategy: str = Field("ours", pattern="^(ours|theirs|manual)$",
                          description="Conflict resolution: ours=keep target, theirs=keep source")


class MergeResponse(BaseModel):
    presentation_id: str
    merged_version_number: int
    source_version: int
    target_version: int
    conflicts_resolved: int
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_presentation_or_404(
    presentation_id: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Presentation:
    result = await db.execute(
        select(Presentation).where(
            Presentation.presentation_id == presentation_id,
            Presentation.tenant_id == tenant_id,
        )
    )
    presentation = result.scalar_one_or_none()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    return presentation


async def _get_slides_list(presentation: Presentation) -> List[Dict[str, Any]]:
    """Extract slides list from presentation, normalising JSONB storage."""
    slides = presentation.slides or []
    if isinstance(slides, dict):
        slides = slides.get("slides", [])
    return list(slides)


async def _find_slide_or_404(slides: List[Dict[str, Any]], slide_id: str) -> Dict[str, Any]:
    slide = next((s for s in slides if s.get("slide_id") == slide_id), None)
    if slide is None:
        raise HTTPException(status_code=404, detail=f"Slide '{slide_id}' not found")
    return slide


async def _get_next_version_number(presentation_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.max(PresentationVersion.version_number)).where(
            PresentationVersion.presentation_id == presentation_id
        )
    )
    max_ver = result.scalar_one_or_none()
    return (max_ver or 0) + 1


async def _create_version_snapshot(
    presentation_id: str,
    slides: List[Dict[str, Any]],
    created_by: uuid.UUID,
    db: AsyncSession,
    parent_version: Optional[uuid.UUID] = None,
    merge_source: Optional[uuid.UUID] = None,
) -> PresentationVersion:
    """Persist a new version snapshot and return it."""
    version_number = await _get_next_version_number(presentation_id, db)
    version = PresentationVersion(
        presentation_id=presentation_id,
        version_number=version_number,
        slides=slides,
        created_by=created_by,
        parent_version=parent_version,
        merge_source=merge_source,
    )
    db.add(version)
    await db.flush()
    return version


async def _check_slide_locked(
    presentation_id: str,
    slide_id: str,
    current_user: User,
    db: AsyncSession,
) -> None:
    """Raise 423 if the slide is locked by another user."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SlideLock).where(
            SlideLock.presentation_id == presentation_id,
            SlideLock.slide_id == slide_id,
            SlideLock.expires_at > now,
        )
    )
    lock = result.scalar_one_or_none()
    if lock and str(lock.locked_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Slide is locked by another user until {lock.expires_at.isoformat()}",
        )


def _validate_narrative_flow(slides: List[Dict[str, Any]]) -> bool:
    """
    Validate that the slide sequence follows consulting storytelling structure.
    Rules:
    - First slide must be type 'title'
    - Last slide must be type 'content' (conclusion)
    - At least one chart or table slide for evidence
    Returns True if valid, False otherwise.
    """
    if not slides:
        return False
    if slides[0].get("type") != "title":
        return False
    if len(slides) < 3:
        return True  # minimal deck — skip strict validation
    # Must have at least one data slide (chart/table) for evidence
    has_data_slide = any(s.get("type") in ("chart", "table") for s in slides)
    return has_data_slide


def _compute_slide_diff(
    slides_a: List[Dict[str, Any]],
    slides_b: List[Dict[str, Any]],
) -> List[DiffSlide]:
    """Compute a per-slide diff between two slide lists."""
    map_a = {s["slide_id"]: s for s in slides_a if "slide_id" in s}
    map_b = {s["slide_id"]: s for s in slides_b if "slide_id" in s}

    all_ids = list(dict.fromkeys(list(map_a.keys()) + list(map_b.keys())))
    changes: List[DiffSlide] = []

    for sid in all_ids:
        in_a = sid in map_a
        in_b = sid in map_b
        if in_a and not in_b:
            changes.append(DiffSlide(slide_id=sid, change_type="removed", before=map_a[sid]))
        elif not in_a and in_b:
            changes.append(DiffSlide(slide_id=sid, change_type="added", after=map_b[sid]))
        elif map_a[sid] != map_b[sid]:
            changes.append(DiffSlide(slide_id=sid, change_type="modified",
                                     before=map_a[sid], after=map_b[sid]))
        else:
            changes.append(DiffSlide(slide_id=sid, change_type="unchanged"))

    return changes


# ---------------------------------------------------------------------------
# 18.1  PATCH /api/v1/presentations/{id}/slides/{slide_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/presentations/{presentation_id}/slides/{slide_id}",
    response_model=SlideUpdateResponse,
)
async def update_slide(
    presentation_id: str,
    slide_id: str,
    body: SlideContentUpdate,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> SlideUpdateResponse:
    """
    Partially update a slide's content.

    - Validates content constraints (title ≤8 words, ≤4 bullets, ≤8 words/bullet)
    - Checks slide is not locked by another user
    - Snapshots current state as a new version before applying changes
    """
    presentation = await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    if presentation.status not in (PresentationStatus.completed, PresentationStatus.failed):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation must be completed before editing slides",
        )

    await _check_slide_locked(presentation_id, slide_id, current_user, db)

    slides = await _get_slides_list(presentation)
    slide = await _find_slide_or_404(slides, slide_id)

    # Snapshot current state before mutation
    version = await _create_version_snapshot(
        presentation_id=presentation_id,
        slides=copy.deepcopy(slides),
        created_by=current_user.id,
        db=db,
    )

    # Apply partial updates
    update_data = body.model_dump(exclude_none=True)

    if "title" in update_data:
        slide["title"] = update_data["title"]

    # Content sub-fields
    content = slide.setdefault("content", {})
    for field in ("bullets", "chart_data", "table_data", "comparison_data",
                  "icon_name", "highlight_text", "transition"):
        if field in update_data:
            content[field] = update_data[field]

    if "visual_hint" in update_data:
        slide["visual_hint"] = update_data["visual_hint"]

    # Update metadata timestamp
    slide.setdefault("metadata", {})["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Persist updated slides
    await db.execute(
        update(Presentation)
        .where(Presentation.presentation_id == presentation_id)
        .values(slides=slides, updated_at=func.now())
    )
    await db.commit()

    return SlideUpdateResponse(
        presentation_id=presentation_id,
        slide_id=slide_id,
        version_number=version.version_number,
        message="Slide updated successfully",
    )


# ---------------------------------------------------------------------------
# 18.2  POST /api/v1/presentations/{id}/slides/{slide_id}/regenerate
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/slides/{slide_id}/regenerate",
    response_model=RegenerateSlideResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_slide(
    presentation_id: str,
    slide_id: str,
    body: RegenerateSlideRequest = RegenerateSlideRequest(),
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> RegenerateSlideResponse:
    """
    Enqueue a single-slide regeneration job.

    No provider field is accepted — backend selects from .env (Req 13).
    Checks slide lock before enqueuing.
    """
    from app.worker.tasks import regenerate_slide_task

    presentation = await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    if presentation.status != PresentationStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation must be completed before regenerating a slide",
        )

    await _check_slide_locked(presentation_id, slide_id, current_user, db)

    slides = await _get_slides_list(presentation)
    await _find_slide_or_404(slides, slide_id)  # validate slide exists

    idempotency_key = f"slide-regen:{presentation_id}:{slide_id}:{int(time.time())}"
    task_result = regenerate_slide_task.apply_async(
        kwargs={
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "idempotency_key": idempotency_key,
        }
    )

    return RegenerateSlideResponse(
        job_id=task_result.id,
        presentation_id=presentation_id,
        slide_id=slide_id,
        status="queued",
        message="Slide regeneration queued. Poll /status for updates.",
    )


# ---------------------------------------------------------------------------
# 18.3  POST /api/v1/presentations/{id}/slides/{slide_id}/lock
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/slides/{slide_id}/lock",
    response_model=SlideLockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def lock_slide(
    presentation_id: str,
    slide_id: str,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> SlideLockResponse:
    """
    Acquire an exclusive lock on a slide for editing.

    Lock TTL is 5 minutes. Returns 409 if already locked by another user.
    """
    presentation = await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    slides = await _get_slides_list(presentation)
    await _find_slide_or_404(slides, slide_id)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=SLIDE_LOCK_TTL_SECONDS)

    # Check for existing active lock
    result = await db.execute(
        select(SlideLock).where(
            SlideLock.presentation_id == presentation_id,
            SlideLock.slide_id == slide_id,
            SlideLock.expires_at > now,
        )
    )
    existing_lock = result.scalar_one_or_none()

    if existing_lock:
        if str(existing_lock.locked_by) == str(current_user.id):
            # Refresh own lock
            await db.execute(
                update(SlideLock)
                .where(SlideLock.id == existing_lock.id)
                .values(expires_at=expires_at)
            )
            await db.commit()
            return SlideLockResponse(
                presentation_id=presentation_id,
                slide_id=slide_id,
                locked_by=str(current_user.id),
                locked_at=existing_lock.locked_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slide is already locked by another user until {existing_lock.expires_at.isoformat()}",
        )

    lock = SlideLock(
        presentation_id=presentation_id,
        slide_id=slide_id,
        locked_by=current_user.id,
        locked_at=now,
        expires_at=expires_at,
    )
    db.add(lock)
    await db.commit()

    return SlideLockResponse(
        presentation_id=presentation_id,
        slide_id=slide_id,
        locked_by=str(current_user.id),
        locked_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# 18.3  DELETE /api/v1/presentations/{id}/slides/{slide_id}/lock
# ---------------------------------------------------------------------------


@router.delete(
    "/presentations/{presentation_id}/slides/{slide_id}/lock",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def unlock_slide(
    presentation_id: str,
    slide_id: str,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Release a slide lock.

    Only the lock owner or an admin can release a lock.
    """
    await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SlideLock).where(
            SlideLock.presentation_id == presentation_id,
            SlideLock.slide_id == slide_id,
            SlideLock.expires_at > now,
        )
    )
    lock = result.scalar_one_or_none()

    if not lock:
        raise HTTPException(status_code=404, detail="No active lock found for this slide")

    if str(lock.locked_by) != str(current_user.id) and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the lock owner or an admin can release this lock",
        )

    await db.delete(lock)
    await db.commit()


# ---------------------------------------------------------------------------
# 18.4  PATCH /api/v1/presentations/{id}/slides/reorder
# ---------------------------------------------------------------------------


@router.patch(
    "/presentations/{presentation_id}/slides/reorder",
    response_model=ReorderResponse,
)
async def reorder_slides(
    presentation_id: str,
    body: ReorderRequest,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> ReorderResponse:
    """
    Reorder slides by providing an ordered list of slide_ids.

    Validates narrative flow after reordering (first slide must be title,
    at least one data slide for evidence). Snapshots current state as a version.
    """
    presentation = await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    if presentation.status not in (PresentationStatus.completed, PresentationStatus.failed):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation must be completed before reordering slides",
        )

    slides = await _get_slides_list(presentation)
    existing_ids = {s["slide_id"] for s in slides if "slide_id" in s}
    requested_ids = set(body.slide_order)

    if requested_ids != existing_ids:
        missing = existing_ids - requested_ids
        extra = requested_ids - existing_ids
        detail_parts = []
        if missing:
            detail_parts.append(f"missing slide_ids: {sorted(missing)}")
        if extra:
            detail_parts.append(f"unknown slide_ids: {sorted(extra)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"slide_order must contain exactly all existing slide_ids. {'; '.join(detail_parts)}",
        )

    # Snapshot before reorder
    version = await _create_version_snapshot(
        presentation_id=presentation_id,
        slides=copy.deepcopy(slides),
        created_by=current_user.id,
        db=db,
    )

    # Build reordered list
    slide_map = {s["slide_id"]: s for s in slides}
    reordered = []
    for i, sid in enumerate(body.slide_order, start=1):
        slide = copy.deepcopy(slide_map[sid])
        slide["slide_number"] = i
        reordered.append(slide)

    narrative_valid = _validate_narrative_flow(reordered)

    await db.execute(
        update(Presentation)
        .where(Presentation.presentation_id == presentation_id)
        .values(slides=reordered, total_slides=len(reordered), updated_at=func.now())
    )
    await db.commit()

    return ReorderResponse(
        presentation_id=presentation_id,
        version_number=version.version_number,
        slide_order=body.slide_order,
        narrative_valid=narrative_valid,
        message=(
            "Slides reordered successfully"
            if narrative_valid
            else "Slides reordered but narrative flow validation failed — consider adjusting slide order"
        ),
    )


# ---------------------------------------------------------------------------
# 18.5  GET /api/v1/presentations/{id}/versions
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/versions",
    response_model=VersionListResponse,
)
async def list_versions(
    presentation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VersionListResponse:
    """List all saved versions for a presentation."""
    await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    result = await db.execute(
        select(PresentationVersion)
        .where(PresentationVersion.presentation_id == presentation_id)
        .order_by(PresentationVersion.version_number.asc())
    )
    versions = result.scalars().all()

    summaries = [
        VersionSummary(
            version_id=str(v.id),
            version_number=v.version_number,
            created_at=v.created_at.isoformat(),
            created_by=str(v.created_by) if v.created_by else None,
            parent_version=str(v.parent_version) if v.parent_version else None,
            merge_source=str(v.merge_source) if v.merge_source else None,
            slide_count=len(v.slides) if isinstance(v.slides, list) else 0,
        )
        for v in versions
    ]

    return VersionListResponse(presentation_id=presentation_id, versions=summaries)


# ---------------------------------------------------------------------------
# 18.5  GET /api/v1/presentations/{id}/versions/{version}
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/versions/{version_number}",
)
async def get_version(
    presentation_id: str,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve the Slide_JSON snapshot for a specific version."""
    await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    result = await db.execute(
        select(PresentationVersion).where(
            PresentationVersion.presentation_id == presentation_id,
            PresentationVersion.version_number == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found")

    slides = version.slides if isinstance(version.slides, list) else []
    return {
        "presentation_id": presentation_id,
        "version_id": str(version.id),
        "version_number": version.version_number,
        "slide_count": len(slides),
        "slides": slides,
        "created_at": version.created_at.isoformat(),
        "created_by": str(version.created_by) if version.created_by else None,
        "parent_version": str(version.parent_version) if version.parent_version else None,
        "merge_source": str(version.merge_source) if version.merge_source else None,
    }


# ---------------------------------------------------------------------------
# 18.6  POST /api/v1/presentations/{id}/rollback
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/rollback",
    response_model=RollbackResponse,
)
async def rollback_presentation(
    presentation_id: str,
    body: RollbackRequest,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """
    Roll back a presentation to a previous version.

    Snapshots the current state as a new version before rolling back,
    so the rollback itself is reversible.
    """
    presentation = await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    # Fetch target version
    result = await db.execute(
        select(PresentationVersion).where(
            PresentationVersion.presentation_id == presentation_id,
            PresentationVersion.version_number == body.version_number,
        )
    )
    target_version = result.scalar_one_or_none()
    if not target_version:
        raise HTTPException(
            status_code=404,
            detail=f"Version {body.version_number} not found",
        )

    # Snapshot current state before rollback
    current_slides = await _get_slides_list(presentation)
    pre_rollback_version = await _create_version_snapshot(
        presentation_id=presentation_id,
        slides=copy.deepcopy(current_slides),
        created_by=current_user.id,
        db=db,
        parent_version=target_version.id,
    )

    # Apply rollback slides
    rollback_slides = (
        target_version.slides
        if isinstance(target_version.slides, list)
        else []
    )

    await db.execute(
        update(Presentation)
        .where(Presentation.presentation_id == presentation_id)
        .values(
            slides=rollback_slides,
            total_slides=len(rollback_slides),
            updated_at=func.now(),
        )
    )
    await db.commit()

    return RollbackResponse(
        presentation_id=presentation_id,
        rolled_back_to=body.version_number,
        new_version_number=pre_rollback_version.version_number,
        message=f"Rolled back to version {body.version_number}. Previous state saved as version {pre_rollback_version.version_number}.",
    )


# ---------------------------------------------------------------------------
# 18.6  GET /api/v1/presentations/{id}/diff
# ---------------------------------------------------------------------------


@router.get(
    "/presentations/{presentation_id}/diff",
    response_model=DiffResponse,
)
async def diff_versions(
    presentation_id: str,
    version_a: int,
    version_b: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiffResponse:
    """
    Compute a per-slide diff between two versions.

    Query params: version_a, version_b (version numbers to compare).
    """
    await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    if version_a == version_b:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="version_a and version_b must be different",
        )

    result = await db.execute(
        select(PresentationVersion).where(
            PresentationVersion.presentation_id == presentation_id,
            PresentationVersion.version_number.in_([version_a, version_b]),
        )
    )
    versions = {v.version_number: v for v in result.scalars().all()}

    if version_a not in versions:
        raise HTTPException(status_code=404, detail=f"Version {version_a} not found")
    if version_b not in versions:
        raise HTTPException(status_code=404, detail=f"Version {version_b} not found")

    slides_a = versions[version_a].slides if isinstance(versions[version_a].slides, list) else []
    slides_b = versions[version_b].slides if isinstance(versions[version_b].slides, list) else []

    changes = _compute_slide_diff(slides_a, slides_b)
    non_unchanged = [c for c in changes if c.change_type != "unchanged"]

    return DiffResponse(
        presentation_id=presentation_id,
        version_a=version_a,
        version_b=version_b,
        changes=changes,
        total_changes=len(non_unchanged),
    )


# ---------------------------------------------------------------------------
# 18.7  POST /api/v1/presentations/{id}/merge
# ---------------------------------------------------------------------------


@router.post(
    "/presentations/{presentation_id}/merge",
    response_model=MergeResponse,
)
async def merge_versions(
    presentation_id: str,
    body: MergeRequest,
    current_user: User = Depends(require_min_role("member")),
    db: AsyncSession = Depends(get_db),
) -> MergeResponse:
    """
    Merge two version branches into a new version.

    Strategies:
    - ours: keep target version slides for conflicts
    - theirs: keep source version slides for conflicts
    - manual: union of both (source slides appended for any slide_id not in target)
    """
    await _get_presentation_or_404(presentation_id, current_user.tenant_id, db)

    if body.source_version == body.target_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_version and target_version must be different",
        )

    result = await db.execute(
        select(PresentationVersion).where(
            PresentationVersion.presentation_id == presentation_id,
            PresentationVersion.version_number.in_([body.source_version, body.target_version]),
        )
    )
    versions = {v.version_number: v for v in result.scalars().all()}

    if body.source_version not in versions:
        raise HTTPException(status_code=404, detail=f"Source version {body.source_version} not found")
    if body.target_version not in versions:
        raise HTTPException(status_code=404, detail=f"Target version {body.target_version} not found")

    source_ver = versions[body.source_version]
    target_ver = versions[body.target_version]

    source_slides: List[Dict[str, Any]] = (
        source_ver.slides if isinstance(source_ver.slides, list) else []
    )
    target_slides: List[Dict[str, Any]] = (
        target_ver.slides if isinstance(target_ver.slides, list) else []
    )

    source_map = {s["slide_id"]: s for s in source_slides if "slide_id" in s}
    target_map = {s["slide_id"]: s for s in target_slides if "slide_id" in s}

    conflicts_resolved = 0
    merged_slides: List[Dict[str, Any]] = []

    if body.strategy == "ours":
        # Keep target for conflicts; add source-only slides at end
        merged_slides = copy.deepcopy(target_slides)
        for sid, slide in source_map.items():
            if sid not in target_map:
                merged_slides.append(copy.deepcopy(slide))
            else:
                conflicts_resolved += 1  # conflict resolved by keeping target

    elif body.strategy == "theirs":
        # Keep source for conflicts; preserve target-only slides
        merged_slides = copy.deepcopy(source_slides)
        for sid, slide in target_map.items():
            if sid not in source_map:
                merged_slides.append(copy.deepcopy(slide))
            else:
                conflicts_resolved += 1  # conflict resolved by keeping source

    else:  # manual — union, source slides appended for new slide_ids
        merged_slides = copy.deepcopy(target_slides)
        for sid, slide in source_map.items():
            if sid not in target_map:
                merged_slides.append(copy.deepcopy(slide))

    # Re-number slides
    for i, slide in enumerate(merged_slides, start=1):
        slide["slide_number"] = i

    # Create merged version with branching metadata
    merged_version = await _create_version_snapshot(
        presentation_id=presentation_id,
        slides=merged_slides,
        created_by=current_user.id,
        db=db,
        parent_version=target_ver.id,
        merge_source=source_ver.id,
    )

    # Apply merged slides to presentation
    await db.execute(
        update(Presentation)
        .where(Presentation.presentation_id == presentation_id)
        .values(
            slides=merged_slides,
            total_slides=len(merged_slides),
            updated_at=func.now(),
        )
    )
    await db.commit()

    return MergeResponse(
        presentation_id=presentation_id,
        merged_version_number=merged_version.version_number,
        source_version=body.source_version,
        target_version=body.target_version,
        conflicts_resolved=conflicts_resolved,
        message=f"Merged version {body.source_version} into {body.target_version} using '{body.strategy}' strategy. New version: {merged_version.version_number}.",
    )
