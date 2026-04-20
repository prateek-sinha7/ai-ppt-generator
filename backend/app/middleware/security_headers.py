"""
Security Headers Middleware (Task 20.3)

Implements:
  - HTTPS enforcement via HSTS header (and redirect in production)
  - Content Security Policy (CSP) headers
  - Additional security headers (X-Frame-Options, X-Content-Type-Options, etc.)

CORS is handled by FastAPI's CORSMiddleware using the CORS_ORIGINS whitelist
from settings (already configured in main.py). This middleware adds the
remaining security headers on every response.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings


# ---------------------------------------------------------------------------
# CSP policy
# ---------------------------------------------------------------------------

_CSP_DIRECTIVES = {
    "default-src": "'self'",
    "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",  # Swagger UI needs inline scripts and CDN
    "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",   # Tailwind + Swagger UI require inline styles
    "img-src": "'self' data: blob: https://cdn.jsdelivr.net",
    "font-src": "'self' https://cdn.jsdelivr.net",
    "connect-src": "'self'",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
    "object-src": "'none'",
}

_CSP_HEADER = "; ".join(f"{k} {v}" for k, v in _CSP_DIRECTIVES.items())

# HSTS: 1 year, include subdomains, preload
_HSTS_HEADER = "max-age=31536000; includeSubDomains; preload"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to every response and enforces HTTPS in production.

    In production (APP_ENV=production):
      - HTTP requests are redirected to HTTPS (301)
      - HSTS header is set

    In all environments:
      - CSP header is set
      - X-Frame-Options: DENY
      - X-Content-Type-Options: nosniff
      - Referrer-Policy: strict-origin-when-cross-origin
      - Permissions-Policy: restricts browser features
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._is_production = settings.APP_ENV == "production"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # HTTPS enforcement in production
        if self._is_production:
            if request.url.scheme == "http":
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(https_url), status_code=301)

        response = await call_next(request)

        # HSTS (only meaningful over HTTPS, but set always so it activates on first HTTPS hit)
        if self._is_production:
            response.headers["Strict-Transport-Security"] = _HSTS_HEADER

        # Content Security Policy
        response.headers["Content-Security-Policy"] = _CSP_HEADER

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # MIME-type sniffing protection
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — disable unused browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )

        # Remove server identification header if present
        if "server" in response.headers:
            del response.headers["server"]
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]

        return response
