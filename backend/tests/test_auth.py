"""
Unit tests for Task 3: Authentication and RBAC.

These tests exercise:
- JWT creation / verification (3.1)
- Refresh token hashing (3.1)
- Auth endpoints: register, login, refresh, logout, me (3.2)
- RBAC role enforcement (3.3)
- Input sanitization middleware (3.5)

NOTE: Tests that hit the DB are skipped here (no live DB in CI).
      Pure-logic tests run without any DB dependency.
"""
import hashlib
from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.middleware.sanitization import TOPIC_MAX_LENGTH, _sanitize_value, _strip_html


# ---------------------------------------------------------------------------
# 3.1 — JWT and password helpers
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        pw = "S3cur3P@ssw0rd!"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_hashes_are_unique(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestAccessToken:
    def test_access_token_payload(self):
        token = create_access_token(subject="user-123", tenant_id="tenant-abc", role="member")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-abc"
        assert payload["role"] == "member"
        assert payload["type"] == "access"

    def test_access_token_algorithm_is_hs256(self):
        token = create_access_token(subject="u", tenant_id="t", role="viewer")
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    def test_access_token_default_ttl_is_15_min(self):
        import time
        from datetime import datetime, timezone

        before = datetime.now(timezone.utc)
        token = create_access_token(subject="u", tenant_id="t", role="viewer")
        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - before
        # Should be ~15 minutes (allow 5s tolerance)
        assert timedelta(minutes=14, seconds=55) <= delta <= timedelta(minutes=15, seconds=5)

    def test_custom_ttl_respected(self):
        from datetime import datetime, timezone

        token = create_access_token(
            subject="u", tenant_id="t", role="admin", expires_delta=timedelta(hours=1)
        )
        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - datetime.now(timezone.utc)
        assert timedelta(minutes=59) <= delta <= timedelta(hours=1, seconds=5)

    def test_expired_token_raises(self):
        from jose import ExpiredSignatureError

        token = create_access_token(
            subject="u", tenant_id="t", role="viewer", expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(ExpiredSignatureError):
            decode_token(token)


class TestRefreshToken:
    def test_refresh_token_type(self):
        token = create_refresh_token(subject="user-xyz")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-xyz"

    def test_refresh_token_ttl_is_30_days(self):
        from datetime import datetime, timezone

        token = create_refresh_token(subject="u")
        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - datetime.now(timezone.utc)
        assert timedelta(days=29, hours=23) <= delta <= timedelta(days=30, seconds=5)


class TestRefreshTokenHashing:
    def test_hash_is_sha256(self):
        raw = "my-secret-token"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert hash_refresh_token(raw) == expected

    def test_same_input_same_hash(self):
        raw = "deterministic"
        assert hash_refresh_token(raw) == hash_refresh_token(raw)

    def test_different_inputs_different_hashes(self):
        assert hash_refresh_token("a") != hash_refresh_token("b")


# ---------------------------------------------------------------------------
# 3.5 — Sanitization helpers
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_removes_script_tag(self):
        assert _strip_html("<script>alert(1)</script>") == ""

    def test_removes_img_onerror(self):
        result = _strip_html('<img src=x onerror="alert(1)">')
        assert "<img" not in result
        assert "onerror" not in result

    def test_removes_generic_html(self):
        assert _strip_html("<b>bold</b>") == "bold"

    def test_removes_javascript_uri(self):
        result = _strip_html("javascript:alert(1)")
        assert "javascript:" not in result.lower()

    def test_plain_text_unchanged(self):
        text = "Hello, world! This is a normal topic."
        assert _strip_html(text) == text

    def test_strips_whitespace(self):
        assert _strip_html("  hello  ") == "hello"


class TestSanitizeValue:
    def test_nested_dict(self):
        data = {"topic": "<script>xss</script>clean", "count": 5}
        result = _sanitize_value(data)
        assert "<script>" not in result["topic"]
        assert result["count"] == 5

    def test_list_of_strings(self):
        data = ["<b>one</b>", "two"]
        result = _sanitize_value(data)
        assert result == ["one", "two"]

    def test_non_string_passthrough(self):
        assert _sanitize_value(42) == 42
        assert _sanitize_value(3.14) == 3.14
        assert _sanitize_value(None) is None


class TestTopicLengthValidation:
    """Validate the TOPIC_MAX_LENGTH constant and the middleware logic."""

    def test_max_length_constant(self):
        assert TOPIC_MAX_LENGTH == 500

    def test_topic_at_limit_is_ok(self):
        from app.middleware.sanitization import _validate_topic

        body = {"topic": "a" * 500}
        assert _validate_topic(body) is None

    def test_topic_over_limit_returns_error(self):
        from app.middleware.sanitization import _validate_topic

        body = {"topic": "a" * 501}
        error = _validate_topic(body)
        assert error is not None
        assert "500" in error

    def test_missing_topic_is_ok(self):
        from app.middleware.sanitization import _validate_topic

        assert _validate_topic({}) is None
        assert _validate_topic({"other": "field"}) is None


# ---------------------------------------------------------------------------
# 3.3 — RBAC role rank logic
# ---------------------------------------------------------------------------


class TestRoleRank:
    """Test the role hierarchy used by deps and middleware."""

    def test_admin_outranks_member(self):
        from app.middleware.rbac import _ROLE_RANK

        assert _ROLE_RANK["admin"] > _ROLE_RANK["member"]

    def test_member_outranks_viewer(self):
        from app.middleware.rbac import _ROLE_RANK

        assert _ROLE_RANK["member"] > _ROLE_RANK["viewer"]

    def test_unknown_role_has_no_rank(self):
        from app.middleware.rbac import _ROLE_RANK

        assert _ROLE_RANK.get("superuser") is None
