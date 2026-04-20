"""
Audit Logging Middleware (Task 20.4)

Automatically logs all mutating requests (POST, PUT, PATCH, DELETE) and
sensitive GET requests to the audit_logs table.

The middleware extracts user/tenant context from the JWT and records:
  - HTTP method + path
  - Response status code
  - User ID and tenant ID
  - Request metadata (IP, user-agent)

Fine-grained before/after state logging is done inside individual route
handlers using the audit_logger service directly.
"""
from __future__ import annotations

import time
from typing import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.security import decode_token

logger = structlog.get_logger(__name__)

# Methods that always produce an audit log entry
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# GET paths that should also be audited (sensitive reads)
_AUDITED_GET_PREFIXES = (
    "/internal/",
    "/api/v1/presentations/",   # individual presentation reads
    "/api/v1/prompts",
    "/api/v1/cache",
)

# Paths to skip entirely (health checks, docs, auth endpoints)
_SKIP_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)


def _should_audit(method: str, path: str) -> bool:
    for prefix in _SKIP_PREFIXES:
        if path.startswith(prefix):
            return False
    if method in _MUTATING_METHODS:
        return True
    if method == "GET":
        return any(path.startswith(p) for p in _AUDITED_GET_PREFIXES)
    return False


def _extract_user_context(request: Request) -> tuple[str | None, str | None]:
    """Return (user_id, tenant_id) from the JWT, or (None, None)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None
    try:
        payload = decode_token(auth[len("Bearer "):])
        if payload.get("type") != "access":
            return None, None
        return payload.get("sub"), payload.get("tenant_id")
    except Exception:
        return None, None


def _resource_from_path(path: str) -> tuple[str, str | None]:
    """
    Derive resource_type and resource_id from the URL path.

    Examples:
      /api/v1/presentations/abc-123        → ("presentation", "abc-123")
      /api/v1/presentations/abc/slides/s1  → ("slide", "s1")
      /api/v1/templates                    → ("template", None)
      /internal/providers/p1/metrics       → ("provider", "p1")
    """
    parts = [p for p in path.split("/") if p]

    # Strip api/v1 prefix
    if parts and parts[0] == "api":
        parts = parts[1:]
    if parts and parts[0] == "v1":
        parts = parts[1:]

    if not parts:
        return "unknown", None

    resource_map = {
        "presentations": "presentation",
        "slides": "slide",
        "templates": "template",
        "prompts": "prompt",
        "providers": "provider",
        "jobs": "job",
        "cache": "cache",
        "auth": "auth",
        "versions": "version",
    }

    resource_type = resource_map.get(parts[0], parts[0].rstrip("s"))
    resource_id: str | None = None

    keywords = set(resource_map.keys()) | {
        "status", "stream", "regenerate", "export", "pptx",
        "lock", "reorder", "rollback", "diff", "merge", "metrics",
        "health-check", "stats", "internal",
    }

    # Walk the path segments to find the deepest resource type and its ID.
    # Pattern: /resource/id/sub-resource/sub-id
    current_resource = resource_type
    current_id: str | None = None

    i = 1
    while i < len(parts):
        part = parts[i]
        if part in resource_map:
            # New sub-resource — update resource type, reset id
            current_resource = resource_map[part]
            current_id = None
        elif part not in keywords:
            # This is an ID segment
            current_id = part
        i += 1

    resource_type = current_resource
    resource_id = current_id

    return resource_type, resource_id


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that writes an audit log entry for every mutating request
    and selected sensitive GET requests.

    Uses a background DB session so it doesn't interfere with the
    request's own session lifecycle.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        method = request.method.upper()
        path = request.url.path

        if not _should_audit(method, path):
            return await call_next(request)

        start_time = time.time()
        user_id, tenant_id = _extract_user_context(request)
        resource_type, resource_id = _resource_from_path(path)

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        # Derive action name from method
        method_action_map = {
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
            "GET": "read",
        }
        verb = method_action_map.get(method, method.lower())
        action = f"{resource_type}.{verb}"

        # Log asynchronously — don't block the response
        try:
            from app.db.session import AsyncSessionLocal
            from app.db.models import AuditLog
            import uuid as _uuid

            async with AsyncSessionLocal() as db:
                entry = AuditLog(
                    tenant_id=_uuid.UUID(tenant_id) if tenant_id else None,
                    user_id=_uuid.UUID(user_id) if user_id else None,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    extra_metadata={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "ip": request.client.host if request.client else None,
                        "user_agent": request.headers.get("user-agent"),
                    },
                )
                db.add(entry)
                await db.commit()

        except Exception as e:
            # Never let audit logging break the response
            logger.error(
                "audit_middleware_write_failed",
                action=action,
                path=path,
                error=str(e),
            )

        return response
