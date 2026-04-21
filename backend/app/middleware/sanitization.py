"""
Input sanitization middleware.

- Strips HTML / script tags from all string fields in JSON request bodies.
- Enforces topic field max-length of 500 characters (returns 422 if exceeded).
- Operates at the ASGI level so it applies to every route automatically.
"""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Matches any HTML / XML tag including <script>, <img onerror=...>, etc.
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.IGNORECASE)
# Matches javascript: URI scheme
_JS_URI_RE = re.compile(r"javascript\s*:", re.IGNORECASE)

TOPIC_MAX_LENGTH = 5000

# Only sanitize JSON bodies on these content-types
_JSON_CONTENT_TYPES = ("application/json",)


def _strip_html(value: str) -> str:
    """Remove HTML tags and javascript: URIs from a string."""
    cleaned = _HTML_TAG_RE.sub("", value)
    cleaned = _JS_URI_RE.sub("", cleaned)
    return cleaned.strip()


def _sanitize_value(value: object) -> object:
    """Recursively sanitize strings inside dicts / lists."""
    if isinstance(value, str):
        return _strip_html(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _validate_topic(body: dict) -> str | None:
    """Return an error message if the topic field violates constraints."""
    topic = body.get("topic")
    if topic is not None and isinstance(topic, str) and len(topic) > TOPIC_MAX_LENGTH:
        return f"topic must not exceed {TOPIC_MAX_LENGTH} characters (got {len(topic)})"
    return None


class SanitizationMiddleware(BaseHTTPMiddleware):
    """Strip XSS vectors from JSON bodies and validate topic length."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_type = request.headers.get("content-type", "")
        is_json = any(ct in content_type for ct in _JSON_CONTENT_TYPES)

        if request.method in ("POST", "PUT", "PATCH") and is_json:
            try:
                raw_body = await request.body()
                if raw_body:
                    body = json.loads(raw_body)

                    # Validate topic length before sanitization
                    error = _validate_topic(body)
                    if error:
                        return JSONResponse(
                            status_code=422,
                            content={"detail": [{"loc": ["body", "topic"], "msg": error, "type": "value_error"}]},
                        )

                    # Sanitize all string values
                    sanitized = _sanitize_value(body)
                    sanitized_bytes = json.dumps(sanitized).encode()

                    # Rebuild the request with the sanitized body
                    async def receive():  # type: ignore[return]
                        return {"type": "http.request", "body": sanitized_bytes, "more_body": False}

                    request = Request(request.scope, receive)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Let FastAPI handle malformed JSON
                pass

        return await call_next(request)
