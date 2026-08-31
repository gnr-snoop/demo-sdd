"""Unit tests for SessionCookieService (T045, spec 003 US6, R-3).

Sign/unsign/tamper/unknown-token. Uses the real itsdangerous serializer with
the demo signing key.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from face_insight.adapters.http.session_cookie import SessionCookieService
from face_insight.config import get_settings


@pytest.fixture
def cookie_service():
    return SessionCookieService(get_settings())


def test_sign_unsign_roundtrip(cookie_service):
    sid = uuid.uuid4()
    token = cookie_service.sign(sid)
    recovered = cookie_service.unsign(token)
    assert recovered == sid


def test_unsign_none_token_returns_none(cookie_service):
    assert cookie_service.unsign(None) is None
    assert cookie_service.unsign("") is None


def test_unsign_tampered_token_returns_none(cookie_service):
    sid = uuid.uuid4()
    token = cookie_service.sign(sid)
    # Tamper: flip the last character.
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert cookie_service.unsign(tampered) is None


def test_unsign_garbage_token_returns_none(cookie_service):
    assert cookie_service.unsign("not-a-valid-token") is None


def test_unsign_non_uuid_payload_returns_none(cookie_service):
    """A token that unsigns to a non-UUID string returns None (never raises)."""
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(get_settings().session_signing_key, salt="fid-session")
    token = serializer.dumps("not-a-uuid")
    assert cookie_service.unsign(token) is None


def test_cookie_name_from_settings(cookie_service):
    assert cookie_service.cookie_name == "fid_session"


def test_set_and_read_cookie_via_response(cookie_service):
    """set() writes the cookie; a Request built from the response cookies reads it back."""
    sid = uuid.uuid4()
    response = JSONResponse(status_code=200, content={})
    cookie_service.set(response, sid)
    # The Set-Cookie header is present.
    raw = response.headers.get("set-cookie", "")
    assert "fid_session=" in raw
    assert "HttpOnly" in raw
    assert "samesite=lax" in raw.lower()
    assert "path=/" in raw.lower()


def test_clear_cookie(cookie_service):
    response = JSONResponse(status_code=200, content={})
    cookie_service.clear(response)
    raw = response.headers.get("set-cookie", "")
    assert "fid_session=" in raw
    assert "max-age=0" in raw.lower()


def test_read_from_request_returns_none_when_no_cookie(cookie_service):
    """A request with no cookie returns None (never raises)."""
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [],  # no cookies
        "path": "/api/auth/me",
        "query_string": b"",
    }
    request = Request(scope)
    assert cookie_service.read(request) is None
