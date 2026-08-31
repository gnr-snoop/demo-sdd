"""Auth contract tests (spec 003, T013/T020/T032/T047/T048).

Asserts request/response shapes + status codes for the three auth endpoints
per ``specs/003-login-session-management/contracts/``:
  - POST /api/auth/face-login (face-login.md)
  - GET /api/auth/me (auth-me.md)
  - POST /api/auth/logout (logout.md)

Includes the byte-identity assertion for the two auth_failed responses (T020/T047,
FR-008/SC-003) and the contract-violation mutation guard (T048, SC-011).

No GPU, no network, no DB (mock adapters + mock repos seeded in-process).
"""

from __future__ import annotations

import re

import pytest

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)

AUTH_FAILED_BODY = {
    "error": {
        "code": "auth_failed",
        "message": "No pudimos verificar tu identidad. Inténtalo de nuevo.",
    }
}
UNAUTHENTICATED_BODY = {
    "error": {
        "code": "unauthenticated",
        "message": "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo.",
    }
}


def _post_login(client, identifier, image_name="one_face.jpg", image_bytes=None):
    from tests.conftest import fixture_bytes

    payload = image_bytes if image_bytes is not None else fixture_bytes(image_name)
    data = {"identifier": identifier}
    files = {"image": (image_name, payload, "image/jpeg")}
    return client.post("/api/auth/face-login", data=data, files=files)


# ==========================================================================
# T013: POST /api/auth/face-login happy path (US1)
# ==========================================================================
@pytest.mark.asyncio
async def test_face_login_happy_path_shape_and_cookie(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com")
    assert resp.status_code == 200
    body = resp.json()
    # Exactly {userId, status} — no expiresAt (FR-005).
    assert set(body.keys()) == {"userId", "status"}
    assert UUID_RE.match(body["userId"])
    assert body["status"] == "authenticated"
    # Signed http-only cookie set.
    assert "set-cookie" in {k.lower() for k in resp.headers}
    cookie = resp.headers["set-cookie"]
    assert "fid_session=" in cookie
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


@pytest.mark.asyncio
async def test_face_login_case_insensitive_identifier(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app, identifier="demo@example.com")
    resp = await _post_login(auth_client, "  Demo@Example.COM  ")
    assert resp.status_code == 200
    assert resp.json()["status"] == "authenticated"


# ==========================================================================
# T020/T047: byte-identity of the two auth_failed responses (FR-008/SC-003)
# ==========================================================================
@pytest.mark.asyncio
async def test_face_login_nonexistent_identifier_401_auth_failed(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)  # seed demo@example.com
    resp = await _post_login(auth_client, "nonexistent@example.com")
    assert resp.status_code == 401
    assert resp.json() == AUTH_FAILED_BODY


@pytest.mark.asyncio
async def test_face_login_below_threshold_401_auth_failed(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    # NONMATCH marker → ScriptableMockEmbedder returns orthogonal vector → similarity 0.0 < 0.5.
    resp = await _post_login(auth_client, "demo@example.com", image_name="non_match.jpg")
    assert resp.status_code == 401
    assert resp.json() == AUTH_FAILED_BODY


@pytest.mark.asyncio
async def test_auth_failed_responses_are_byte_identical(auth_client, auth_app):
    """T047/SC-003: nonexistent-identifier and below-threshold produce byte-identical responses."""
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp_a = await _post_login(auth_client, "nonexistent@example.com")
    resp_b = await _post_login(auth_client, "demo@example.com", image_name="non_match.jpg")
    assert resp_a.status_code == resp_b.status_code == 401
    # Byte-identity: same status, same body bytes, same code, same message.
    assert resp_a.content == resp_b.content
    assert resp_a.json() == resp_b.json() == AUTH_FAILED_BODY


@pytest.mark.asyncio
async def test_401_never_carries_capture_code_and_400_never_carries_auth_failed(auth_client, auth_app):
    """FR-010: status-code reservation — 401 is auth-only, 400 is capture-only."""
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    # 401 cases.
    r_nonexistent = await _post_login(auth_client, "nope@example.com")
    r_below = await _post_login(auth_client, "demo@example.com", image_name="non_match.jpg")
    for r in (r_nonexistent, r_below):
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "auth_failed"
    # 400 cases.
    r_no_face = await _post_login(auth_client, "demo@example.com", image_name="no_face.jpg")
    r_multi = await _post_login(auth_client, "demo@example.com", image_name="multi_face.jpg")
    r_low_q = await _post_login(auth_client, "demo@example.com", image_name="low_quality.jpg")
    for r in (r_no_face, r_multi, r_low_q):
        assert r.status_code == 400
        assert r.json()["error"]["code"] != "auth_failed"


# ==========================================================================
# T022: capture-quality 400 codes (US2)
# ==========================================================================
@pytest.mark.asyncio
async def test_face_login_no_face_400(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="no_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_face"


@pytest.mark.asyncio
async def test_face_login_multiple_faces_400(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="multi_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "multiple_faces"


@pytest.mark.asyncio
async def test_face_login_insufficient_quality_400(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="low_quality.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_quality"


@pytest.mark.asyncio
async def test_face_login_invalid_image_400_undecodable(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="not_an_image.txt")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_face_login_invalid_image_400_oversized(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="oversized.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_face_login_missing_image_400(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await auth_client.post(
        "/api/auth/face-login", data={"identifier": "demo@example.com"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


# F-003: oversized-image-for-nonexistent-identifier test (capture error surfaces
# uniformly — detection/validation before lookup, R-5).
@pytest.mark.asyncio
async def test_face_login_oversized_image_for_nonexistent_identifier_returns_400_not_401(auth_client):
    """F-003: an oversized image for a nonexistent identifier yields 400 invalid_image,
    NOT 401 auth_failed — proving validation runs before lookup (R-5)."""
    resp = await _post_login(auth_client, "nonexistent@example.com", image_name="oversized.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


# ==========================================================================
# GET /api/auth/me (T029 — contract)
# ==========================================================================
@pytest.mark.asyncio
async def test_me_no_cookie_401_unauthenticated(auth_client):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == UNAUTHENTICATED_BODY


@pytest.mark.asyncio
async def test_me_valid_session_200(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    login = await _post_login(auth_client, "demo@example.com")
    assert login.status_code == 200
    # httpx AsyncClient stores cookies automatically.
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert UUID_RE.match(body["userId"])


@pytest.mark.asyncio
async def test_me_tampered_cookie_401(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    await _post_login(auth_client, "demo@example.com")
    # Tamper the cookie.
    auth_client.cookies.set("fid_session", "tampered-token-value")
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


# ==========================================================================
# T032: POST /api/auth/logout (US4 — contract)
# ==========================================================================
@pytest.mark.asyncio
async def test_logout_no_cookie_200(auth_client):
    resp = await auth_client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_logout_valid_session_200_and_clears_cookie(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    login = await _post_login(auth_client, "demo@example.com")
    assert login.status_code == 200
    resp = await auth_client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # After logout, the cookie is cleared → me returns 401.
    me = await auth_client.get("/api/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_logout_idempotent_after_revoke(auth_client, auth_app):
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    await _post_login(auth_client, "demo@example.com")
    first = await auth_client.post("/api/auth/logout")
    second = await auth_client.post("/api/auth/logout")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {"status": "ok"}


# ==========================================================================
# T048: contract-violation mutation guard (SC-011)
# ==========================================================================
@pytest.mark.asyncio
async def test_contract_login_success_shape_enforced(auth_client, auth_app):
    """SC-011: a deliberate change to the success shape fails this test."""
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "demo@example.com")
    body = resp.json()
    assert set(body.keys()) == {"userId", "status"}, body
    assert body["status"] == "authenticated"


@pytest.mark.asyncio
async def test_contract_error_shape_enforced(auth_client, auth_app):
    """SC-011: every error uses {"error": {"code", "message"}}."""
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    resp = await _post_login(auth_client, "nonexistent@example.com")
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message"}
    assert body["error"]["code"] == "auth_failed"


@pytest.mark.asyncio
async def test_contract_distinguishable_failure_would_fail(auth_client, auth_app):
    """SC-011: if the two identity-sensitive failures became distinguishable (different
    code or message), this test would fail. Today they are byte-identical."""
    from tests.conftest import seed_user_template

    await seed_user_template(auth_app)
    a = await _post_login(auth_client, "nonexistent@example.com")
    b = await _post_login(auth_client, "demo@example.com", image_name="non_match.jpg")
    assert a.content == b.content, "identity-sensitive failures must be byte-identical"
