"""
API Versioning Middleware (Task 20.5)

Implements API versioning via URI prefix /api/v1/ with deprecation policy support.

Features:
  - Injects API-Version header on every response indicating the current version
  - Injects Deprecation and Sunset headers for deprecated API versions
  - Returns 410 Gone for versions past their sunset date
  - Provides /api/versions endpoint listing all versions and their status

Version lifecycle:
  active     → current, fully supported
  deprecated → still works, but Deprecation + Sunset headers are set
  sunset     → returns 410 Gone
"""
from __future__ import annotations

from datetime import date
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# Version registry
# ---------------------------------------------------------------------------

CURRENT_VERSION = "1.0.0"

# Each entry: version_prefix → {status, deprecated_date, sunset_date, notes}
VERSION_REGISTRY: dict[str, dict] = {
    "v1": {
        "version": "1.0.0",
        "status": "active",
        "deprecated_date": None,
        "sunset_date": None,
        "notes": "Current stable version.",
    },
    # Example of a deprecated version (uncomment when v2 is released):
    # "v0": {
    #     "version": "0.9.0",
    #     "status": "deprecated",
    #     "deprecated_date": "2025-01-01",
    #     "sunset_date": "2025-07-01",
    #     "notes": "Migrate to /api/v1/. See /api/versions for details.",
    # },
}

# Paths that bypass version checking (health, docs, internal)
_BYPASS_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/versions",
    "/internal/",
)


def _extract_version_prefix(path: str) -> str | None:
    """
    Extract the version prefix from a path like /api/v1/presentations.
    Returns 'v1', 'v2', etc., or None if no version prefix found.
    """
    parts = path.strip("/").split("/")
    # Expected: ["api", "v1", ...]
    if len(parts) >= 2 and parts[0] == "api" and parts[1].startswith("v"):
        return parts[1]
    return None


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Injects API-Version header on all /api/v* responses
    2. Adds Deprecation + Sunset headers for deprecated versions
    3. Returns 410 Gone for sunsetted versions
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Bypass version checking for non-versioned paths
        for prefix in _BYPASS_PREFIXES:
            if path.startswith(prefix):
                response = await call_next(request)
                response.headers["API-Version"] = CURRENT_VERSION
                return response

        version_prefix = _extract_version_prefix(path)

        if version_prefix is None:
            # Not a versioned API path — pass through
            return await call_next(request)

        version_info = VERSION_REGISTRY.get(version_prefix)

        if version_info is None:
            # Unknown version
            return JSONResponse(
                status_code=404,
                content={
                    "detail": f"API version '{version_prefix}' is not recognised.",
                    "supported_versions": list(VERSION_REGISTRY.keys()),
                    "current_version": CURRENT_VERSION,
                },
            )

        # Check if version has been sunsetted
        if version_info["status"] == "sunset":
            sunset_date = version_info.get("sunset_date", "unknown")
            return JSONResponse(
                status_code=410,
                content={
                    "detail": (
                        f"API version '{version_prefix}' was sunsetted on {sunset_date} "
                        f"and is no longer available. Please migrate to /api/v1/."
                    ),
                    "sunset_date": sunset_date,
                    "current_version": CURRENT_VERSION,
                    "migration_guide": "/api/versions",
                },
                headers={
                    "API-Version": version_info["version"],
                    "Sunset": sunset_date,
                    "Link": '</api/versions>; rel="deprecation"',
                },
            )

        response = await call_next(request)

        # Always inject current version header
        response.headers["API-Version"] = version_info["version"]

        # Add deprecation headers for deprecated versions
        if version_info["status"] == "deprecated":
            deprecated_date = version_info.get("deprecated_date", "")
            sunset_date = version_info.get("sunset_date", "")
            notes = version_info.get("notes", "")

            if deprecated_date:
                response.headers["Deprecation"] = deprecated_date
            if sunset_date:
                response.headers["Sunset"] = sunset_date
            response.headers["Link"] = '</api/versions>; rel="deprecation"'
            response.headers["Warning"] = (
                f'299 - "This API version is deprecated. {notes}"'
            )

        return response


# ---------------------------------------------------------------------------
# /api/versions endpoint handler (registered in main.py)
# ---------------------------------------------------------------------------


def get_api_versions_response() -> dict:
    """
    Return the API version registry as a structured response.
    Used by the /api/versions endpoint.
    """
    versions = []
    for prefix, info in VERSION_REGISTRY.items():
        versions.append(
            {
                "prefix": prefix,
                "version": info["version"],
                "status": info["status"],
                "deprecated_date": info.get("deprecated_date"),
                "sunset_date": info.get("sunset_date"),
                "notes": info.get("notes", ""),
                "base_url": f"/api/{prefix}/",
            }
        )

    return {
        "current_version": CURRENT_VERSION,
        "versions": versions,
        "deprecation_policy": (
            "Versions are deprecated with at least 6 months notice before sunset. "
            "Deprecated versions include Deprecation and Sunset response headers. "
            "Sunsetted versions return HTTP 410 Gone."
        ),
    }
