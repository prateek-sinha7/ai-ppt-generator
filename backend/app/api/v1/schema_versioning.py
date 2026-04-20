"""
Slide_JSON Schema Versioning API (Task 31.5)

Provides:
  GET /api/v1/schema/versions   — changelog, deprecation policy, and all schema versions
  GET /api/v1/schema/current    — current schema version details
  POST /api/v1/schema/validate  — validate a Slide_JSON document and report version issues
  POST /api/v1/schema/migrate   — migrate a v0.9.0 document to v1.0.0

References: Req 35, 36 | Design: Interface Specifications
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.schema_registry import (
    CURRENT_SCHEMA_VERSION,
    PREVIOUS_SCHEMA_VERSION,
    SUPPORTED_VERSIONS,
    SchemaVersionError,
    detect_version,
    get_registry_info,
    migrate_to_current,
    validate_against_version,
    validate_version_compatibility,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/schema", tags=["schema-versioning"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SchemaValidateRequest(BaseModel):
    """Request body for schema validation endpoint."""

    data: Dict[str, Any] = Field(..., description="Slide_JSON document to validate")
    target_version: Optional[str] = Field(
        default=None,
        description=(
            "Schema version to validate against. "
            "Defaults to the detected version in the document."
        ),
    )


class SchemaValidateResponse(BaseModel):
    detected_version: str
    target_version: str
    is_valid: bool
    is_compatible: bool
    errors: List[str]
    warnings: List[str]
    migration_available: bool
    message: str


class SchemaMigrateRequest(BaseModel):
    """Request body for schema migration endpoint."""

    data: Dict[str, Any] = Field(..., description="Slide_JSON document to migrate")


class SchemaMigrateResponse(BaseModel):
    from_version: str
    to_version: str
    migrated: bool
    data: Dict[str, Any]
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/versions",
    summary="Schema version changelog and deprecation policy",
    response_class=JSONResponse,
)
async def get_schema_versions() -> JSONResponse:
    """
    Return the complete Slide_JSON schema version registry including:
    - All supported versions with release and deprecation dates
    - Deprecation policy
    - Changelog per version
    - Migration guidance

    This endpoint fulfils Task 31.5: API versioning changelog and deprecation
    policy documentation endpoint.
    """
    info = get_registry_info()
    return JSONResponse(content=info)


@router.get(
    "/current",
    summary="Current schema version details",
    response_class=JSONResponse,
)
async def get_current_schema_version() -> JSONResponse:
    """Return the current Slide_JSON schema version and its details."""
    return JSONResponse(
        content={
            "current_version": CURRENT_SCHEMA_VERSION,
            "previous_version": PREVIOUS_SCHEMA_VERSION,
            "supported_versions": sorted(SUPPORTED_VERSIONS, reverse=True),
            "deprecation_policy": (
                "Schema versions are deprecated with at least 6 months notice. "
                "Deprecated versions are automatically migrated to the current version. "
                "Incompatible versions (below 0.9.0) are rejected with HTTP 422."
            ),
        }
    )


@router.post(
    "/validate",
    summary="Validate a Slide_JSON document against its schema version",
    response_model=SchemaValidateResponse,
)
async def validate_schema_document(request: SchemaValidateRequest) -> SchemaValidateResponse:
    """
    Validate a Slide_JSON document and report:
    - Detected schema version
    - Whether the version is compatible (migratable) or incompatible (rejected)
    - Validation errors against the target schema
    - Whether automatic migration is available

    Returns HTTP 422 with detailed error information for incompatible versions.
    """
    data = request.data
    detected_version = detect_version(data)
    target_version = request.target_version or detected_version

    # Check version compatibility
    is_compatible, version_error = validate_version_compatibility(data)

    if not is_compatible and version_error:
        logger.warning(
            "schema_validate_endpoint_incompatible",
            detected_version=detected_version,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=version_error.to_dict(),
        )

    # Validate against target version
    is_valid, errors = validate_against_version(data, target_version)

    # Determine if migration is available
    migration_available = (
        detected_version != CURRENT_SCHEMA_VERSION
        and detected_version in SUPPORTED_VERSIONS
    )

    warnings: List[str] = []
    if detected_version == PREVIOUS_SCHEMA_VERSION:
        warnings.append(
            f"Schema version {PREVIOUS_SCHEMA_VERSION} is deprecated. "
            f"Migrate to {CURRENT_SCHEMA_VERSION}. "
            f"Use POST /api/v1/schema/migrate to convert automatically."
        )

    message = "Document is valid." if is_valid else f"Document has {len(errors)} validation error(s)."
    if migration_available:
        message += f" Automatic migration from {detected_version} to {CURRENT_SCHEMA_VERSION} is available."

    return SchemaValidateResponse(
        detected_version=detected_version,
        target_version=target_version,
        is_valid=is_valid,
        is_compatible=is_compatible,
        errors=errors,
        warnings=warnings,
        migration_available=migration_available,
        message=message,
    )


@router.post(
    "/migrate",
    summary="Migrate a Slide_JSON document to the current schema version",
    response_model=SchemaMigrateResponse,
)
async def migrate_schema_document(request: SchemaMigrateRequest) -> SchemaMigrateResponse:
    """
    Migrate a Slide_JSON document from a previous version (e.g. v0.9.0) to the
    current version (v1.0.0).

    Returns HTTP 422 if the document's version is incompatible and cannot be migrated.
    Returns the migrated document if migration succeeds.
    """
    data = request.data
    from_version = detect_version(data)

    # Reject incompatible versions
    is_compatible, version_error = validate_version_compatibility(data)
    if not is_compatible and version_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=version_error.to_dict(),
        )

    if from_version == CURRENT_SCHEMA_VERSION:
        return SchemaMigrateResponse(
            from_version=from_version,
            to_version=CURRENT_SCHEMA_VERSION,
            migrated=False,
            data=data,
            message="Document is already at the current schema version. No migration needed.",
        )

    try:
        migrated_data = migrate_to_current(data)
        logger.info(
            "schema_migration_via_api",
            from_version=from_version,
            to_version=CURRENT_SCHEMA_VERSION,
        )
        return SchemaMigrateResponse(
            from_version=from_version,
            to_version=CURRENT_SCHEMA_VERSION,
            migrated=True,
            data=migrated_data,
            message=(
                f"Successfully migrated from {from_version} to {CURRENT_SCHEMA_VERSION}. "
                "Review the migrated document before use."
            ),
        )
    except Exception as exc:
        logger.error("schema_migration_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {exc}",
        )
