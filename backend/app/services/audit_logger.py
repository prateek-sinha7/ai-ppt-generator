"""
Audit Logger Service (Task 20.4)

Provides structured audit logging for all data access and mutations.
Writes to the audit_logs table in PostgreSQL.

Usage:
    from app.services.audit_logger import audit_logger

    await audit_logger.log(
        db=db,
        action="presentation.create",
        resource_type="presentation",
        resource_id=str(presentation_id),
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        metadata={"topic": topic},
    )

Action naming convention:
    <resource>.<verb>   e.g. presentation.create, slide.update, user.login
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Canonical action names
# ---------------------------------------------------------------------------

# Auth
ACTION_USER_REGISTER = "user.register"
ACTION_USER_LOGIN = "user.login"
ACTION_USER_LOGOUT = "user.logout"
ACTION_TOKEN_REFRESH = "token.refresh"

# Presentations
ACTION_PRESENTATION_CREATE = "presentation.create"
ACTION_PRESENTATION_READ = "presentation.read"
ACTION_PRESENTATION_REGENERATE = "presentation.regenerate"
ACTION_PRESENTATION_DELETE = "presentation.delete"
ACTION_PRESENTATION_EXPORT = "presentation.export"

# Slides
ACTION_SLIDE_UPDATE = "slide.update"
ACTION_SLIDE_REGENERATE = "slide.regenerate"
ACTION_SLIDE_REORDER = "slide.reorder"
ACTION_SLIDE_LOCK = "slide.lock"
ACTION_SLIDE_UNLOCK = "slide.unlock"

# Versions
ACTION_VERSION_CREATE = "version.create"
ACTION_VERSION_ROLLBACK = "version.rollback"
ACTION_VERSION_MERGE = "version.merge"

# Templates
ACTION_TEMPLATE_CREATE = "template.create"
ACTION_TEMPLATE_READ = "template.read"
ACTION_TEMPLATE_UPDATE = "template.update"
ACTION_TEMPLATE_DELETE = "template.delete"

# Prompts
ACTION_PROMPT_READ = "prompt.read"
ACTION_PROMPT_ROLLBACK = "prompt.rollback"

# Admin / providers
ACTION_PROVIDER_READ = "provider.read"
ACTION_PROVIDER_HEALTH_CHECK = "provider.health_check"

# Cache
ACTION_CACHE_READ = "cache.read"
ACTION_CACHE_INVALIDATE = "cache.invalidate"

# Jobs
ACTION_JOB_CANCEL = "job.cancel"


class AuditLoggerService:
    """
    Writes structured audit log entries to the audit_logs table.

    All writes are fire-and-forget — failures are logged to structlog
    but never propagate to the caller so audit logging never breaks
    the main request flow.
    """

    async def log(
        self,
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Persist an audit log entry.

        Args:
            db:            Active async SQLAlchemy session.
            action:        Canonical action name (e.g. "presentation.create").
            resource_type: Type of resource affected (e.g. "presentation").
            resource_id:   ID of the affected resource (optional).
            user_id:       UUID string of the acting user (optional).
            tenant_id:     UUID string of the tenant (optional).
            metadata:      Additional context dict (optional).
        """
        try:
            entry = AuditLog(
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                user_id=uuid.UUID(user_id) if user_id else None,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                extra_metadata=metadata or {},
            )
            db.add(entry)
            # Use flush (not commit) — the caller owns the transaction
            await db.flush()

            logger.info(
                "audit_log_written",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )

        except Exception as e:
            # Never let audit logging break the main flow
            logger.error(
                "audit_log_write_failed",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                error=str(e),
            )

    async def log_access(
        self,
        db: AsyncSession,
        resource_type: str,
        resource_id: str,
        user_id: str,
        tenant_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Convenience method for read/access events."""
        action = f"{resource_type}.read"
        await self.log(
            db=db,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            tenant_id=tenant_id,
            metadata=metadata,
        )

    async def log_mutation(
        self,
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: str,
        tenant_id: str,
        before: Optional[dict[str, Any]] = None,
        after: Optional[dict[str, Any]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Convenience method for mutation events (create/update/delete).

        Captures before/after state snapshots in metadata.
        """
        metadata: dict[str, Any] = extra or {}
        if before is not None:
            metadata["before"] = before
        if after is not None:
            metadata["after"] = after

        await self.log(
            db=db,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            tenant_id=tenant_id,
            metadata=metadata,
        )


# Global singleton
audit_logger = AuditLoggerService()
