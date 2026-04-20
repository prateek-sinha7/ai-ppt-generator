"""
RBAC middleware.

Enforces the admin / member / viewer permission matrix on every request.

The middleware reads the JWT from the Authorization header, extracts the role,
and checks it against the route's required permission using a path-prefix +
HTTP-method lookup table.

Routes that are not in the table are allowed through (e.g. /health, /api/docs,
/api/v1/auth/*).  Fine-grained per-endpoint enforcement is done via the
`require_role` / `require_min_role` FastAPI dependencies in app/api/deps.py.
This middleware provides a defence-in-depth layer at the ASGI level.
"""
from __future__ import annotations

import re
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.security import decode_token

# ---------------------------------------------------------------------------
# Permission matrix
# Each entry: (path_regex, http_methods, minimum_role)
# Checked in order; first match wins.
# ---------------------------------------------------------------------------

_ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2}

# Routes that require NO authentication at all
_PUBLIC_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/auth/",
)

# (compiled_regex, frozenset_of_methods_or_None_for_all, min_role)
_RULES: list[tuple[re.Pattern, frozenset[str] | None, str]] = [
    # Admin-only routes
    (re.compile(r"^/internal/"), None, "admin"),
    (re.compile(r"^/api/v1/admin/"), None, "admin"),
    # Member+ routes (create / edit)
    (re.compile(r"^/api/v1/presentations"), frozenset({"POST", "PATCH", "PUT", "DELETE"}), "member"),
    (re.compile(r"^/api/v1/templates"), frozenset({"POST", "PATCH", "PUT", "DELETE"}), "member"),
    # Viewer+ routes (read)
    (re.compile(r"^/api/v1/"), None, "viewer"),
]


def _extract_role(request: Request) -> str | None:
    """Return the role from the Bearer JWT, or None if absent/invalid."""
    # First try Authorization header
    auth = request.headers.get("Authorization", "")
    token = None
    
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):]
    else:
        # For SSE endpoints, check query parameter (EventSource doesn't support custom headers)
        token = request.query_params.get("token")
    
    if not token:
        return None
        
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("role")
    except JWTError:
        return None


class RBACMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Allow public routes without any token check
        for prefix in _PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Find the first matching rule
        method = request.method.upper()
        for pattern, methods, min_role in _RULES:
            if not pattern.match(path):
                continue
            if methods is not None and method not in methods:
                continue

            # Rule matched — enforce role
            role = _extract_role(request)
            if role is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Not authenticated"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_rank = _ROLE_RANK.get(role, -1)
            required_rank = _ROLE_RANK.get(min_role, 0)
            if user_rank < required_rank:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": f"Role '{role}' is not permitted. Minimum required: {min_role}"
                    },
                )
            break  # rule matched and passed — stop checking

        return await call_next(request)
