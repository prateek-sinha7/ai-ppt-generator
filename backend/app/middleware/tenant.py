"""
Tenant isolation middleware.

On every authenticated request this middleware:
1. Extracts `tenant_id` from the JWT access token.
2. Stores it on `request.state.tenant_id` for use by route handlers.

The actual PostgreSQL session variable (`app.current_tenant_id`) is set
inside the `get_db` dependency (see app/db/session.py) using the value
stored on request.state, enabling Row-Level Security policies.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.security import decode_token

_PUBLIC_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/auth/",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Populate request.state.tenant_id from the JWT so the DB session can set RLS."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Skip public routes
        for prefix in _PUBLIC_PREFIXES:
            if path.startswith(prefix):
                request.state.tenant_id = None
                return await call_next(request)

        tenant_id: str | None = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                payload = decode_token(auth[len("Bearer "):])
                if payload.get("type") == "access":
                    tenant_id = payload.get("tenant_id")
            except Exception:
                pass

        request.state.tenant_id = tenant_id
        return await call_next(request)
