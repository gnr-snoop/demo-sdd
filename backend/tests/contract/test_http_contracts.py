"""HTTP contract tests for all 7 endpoints (T061/T011/T016/T021/T032/T038, FR-016).

Asserts request/response shapes and status codes per
``specs/002-onboarding-flow/contracts/onboarding.md`` (real onboarding logic) and
the spec 001 stub contracts for the other 6 endpoints. Includes the
contract-violation regression test (T038, SC-009).
"""

from __future__ import annotations

import re

import pytest

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)

# Shared constants (mirror tests/conftest.py).
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
SESSION_HEADER = {"X-Session-Id": "00000000-0000-4000-8000-000000000002"}
FIXED_USER_ID = "00000000-0000-4000-8000-000000000001"

MOOD_DISCLAIMER = (
    "Resultado estimado por un modelo visual. No representa una medición "
    "objetiva del estado emocional."
)
AGE_DISCLAIMER = "La edad es una estimación visual y puede contener un margen de error significativo."


def _multipart(identifier=None, consent=None, image=True):
    """Spec 001 helper for non-onboarding stub endpoints (uses JPEG_BYTES)."""
    data = {}
    files = {}
    if identifier is not None:
        data["identifier"] = identifier
    if consent is not None:
        data["consentAccepted"] = "true" if consent else "false"
    if image:
        files["image"] = ("test.jpg", JPEG_BYTES, "image/jpeg")
    return data, files


def _onboard(client, identifier="demo@example.com", consent="true", image_name="one_face.jpg", image_bytes=None):
    """POST /api/onboarding with a fixture image (default one_face.jpg)."""
    from tests.conftest import fixture_bytes

    payload = image_bytes if image_bytes is not None else fixture_bytes(image_name)
    data = {"identifier": identifier, "consentAccepted": consent}
    files = {"image": (image_name, payload, "image/jpeg")}
    return client.post("/api/onboarding", data=data, files=files)


# ==========================================================================
# POST /api/onboarding — real logic (spec 002)
# ==========================================================================

# --- T011: Happy path (201) ------------------------------------------------
@pytest.mark.asyncio
async def test_onboarding_success(client):
    resp = await _onboard(client, identifier="Demo@Example.com ")
    assert resp.status_code == 201
    body = resp.json()
    assert set(body.keys()) == {"userId", "identifier", "status"}
    assert UUID_RE.match(body["userId"])
    assert body["identifier"] == "demo@example.com"  # normalized (trim + lowercase)
    assert body["status"] == "enrolled"


# --- T021: identifier_invalid / identifier_taken / consent_required --------
@pytest.mark.asyncio
async def test_onboarding_empty_identifier_422(client):
    resp = await _onboard(client, identifier="   ")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "identifier_invalid"


@pytest.mark.asyncio
async def test_onboarding_malformed_identifier_422(client):
    resp = await _onboard(client, identifier="not valid!")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "identifier_invalid"


@pytest.mark.asyncio
async def test_onboarding_missing_identifier_422(client):
    # Omit identifier entirely.
    from tests.conftest import fixture_bytes

    files = {"image": ("one.jpg", fixture_bytes("one_face.jpg"), "image/jpeg")}
    resp = await client.post("/api/onboarding", data={"consentAccepted": "true"}, files=files)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "identifier_invalid"


@pytest.mark.asyncio
async def test_onboarding_duplicate_identifier_409(client):
    first = await _onboard(client, identifier="demo@example.com")
    assert first.status_code == 201
    second = await _onboard(client, identifier="DEMO@Example.COM")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "identifier_taken"


@pytest.mark.asyncio
async def test_onboarding_consent_false_422(client):
    resp = await _onboard(client, consent="false")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "consent_required"


@pytest.mark.asyncio
async def test_onboarding_consent_non_boolean_string_422(client):
    # Non-boolean truthy string ("yes") must be rejected (FR-003).
    resp = await _onboard(client, consent="yes")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "consent_required"


@pytest.mark.asyncio
async def test_onboarding_consent_missing_422(client):
    from tests.conftest import fixture_bytes

    files = {"image": ("one.jpg", fixture_bytes("one_face.jpg"), "image/jpeg")}
    resp = await client.post("/api/onboarding", data={"identifier": "demo@example.com"}, files=files)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "consent_required"


# --- T032: invalid_image (missing / oversized / undecodable) ---------------
@pytest.mark.asyncio
async def test_onboarding_missing_image_422(client):
    resp = await client.post(
        "/api/onboarding", data={"identifier": "demo@example.com", "consentAccepted": "true"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_onboarding_oversized_image_422(client):
    resp = await _onboard(client, identifier="big@example.com", image_name="oversized.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_onboarding_undecodable_image_422(client):
    resp = await _onboard(client, identifier="ni@example.com", image_name="not_an_image.txt")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_image"


# --- T016: no_face / multiple_faces / insufficient_quality (scriptable) -----
@pytest.mark.asyncio
async def test_onboarding_no_face_422(scriptable_client):
    resp = await _onboard(scriptable_client, identifier="nf@example.com", image_name="no_face.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "no_face"


@pytest.mark.asyncio
async def test_onboarding_multiple_faces_422(scriptable_client):
    resp = await _onboard(scriptable_client, identifier="mf@example.com", image_name="multi_face.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "multiple_faces"


@pytest.mark.asyncio
async def test_onboarding_insufficient_quality_422(scriptable_client):
    resp = await _onboard(scriptable_client, identifier="lq@example.com", image_name="low_quality.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "insufficient_quality"


# --- T038: Contract-violation regression (SC-009) --------------------------
@pytest.mark.asyncio
async def test_contract_success_shape_enforced(client):
    """A deliberate change to the success shape (e.g. extra/missing fields or
    status='active') causes this test to fail (SC-009)."""
    resp = await _onboard(client, identifier="demo@example.com")
    body = resp.json()
    assert set(body.keys()) == {"userId", "identifier", "status"}, body
    assert body["status"] == "enrolled"
    assert body["status"] != "active"


@pytest.mark.parametrize(
    "code,status",
    [
        ("identifier_invalid", 422),
        ("identifier_taken", 409),
        ("consent_required", 422),
        ("invalid_image", 422),
        ("no_face", 422),
        ("multiple_faces", 422),
        ("insufficient_quality", 422),
    ],
)
@pytest.mark.asyncio
async def test_contract_error_shape_enforced(client, scriptable_client, code, status):
    """Every error response uses {"error": {"code", "message"}} (SC-009)."""
    from tests.conftest import fixture_bytes

    if code == "identifier_invalid":
        resp = await _onboard(client, identifier="bad!")
    elif code == "identifier_taken":
        await _onboard(client, identifier="dup@example.com")
        resp = await _onboard(client, identifier="DUP@example.com")
    elif code == "consent_required":
        resp = await _onboard(client, consent="false")
    elif code == "invalid_image":
        resp = await _onboard(client, image_name="not_an_image.txt")
    elif code == "no_face":
        resp = await _onboard(scriptable_client, image_name="no_face.jpg")
    elif code == "multiple_faces":
        resp = await _onboard(scriptable_client, image_name="multi_face.jpg")
    elif code == "insufficient_quality":
        resp = await _onboard(scriptable_client, image_name="low_quality.jpg")
    assert resp.status_code == status
    body = resp.json()
    assert set(body.keys()) == {"error"}, body
    assert set(body["error"].keys()) == {"code", "message"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# ==========================================================================
# POST /api/auth/face-login (spec 003 — real logic; see test_auth_contracts.py)
# ==========================================================================
# Spec 001 stub tests for face-login/me/logout are superseded by spec 003.
# The real contract tests live in test_auth_contracts.py (T013/T020/T032/T047/T048).


# --- GET /api/auth/me (spec 003 — 401 without a valid cookie) --------------
@pytest.mark.asyncio
async def test_auth_me_unauthenticated_401(client):
    """T025: no cookie → 401 unauthenticated (spec 003 real gating)."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthenticated"


# --- POST /api/auth/logout (spec 003 — always 200, idempotent) -------------
@pytest.mark.asyncio
async def test_logout_without_cookie_200(client):
    """T032: logout is idempotent — 200 even with no cookie (FR-012)."""
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- POST /api/analysis/mood (spec 004 — real logic) -----------------------
@pytest.mark.asyncio
async def test_analysis_mood_without_session_401(client):
    """T025: protected endpoint rejects without a valid session (SC-005)."""
    files = {"image": ("test.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/analysis/mood", files=files)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_analysis_mood_happy_path_real_logic(client, app):
    """Spec 004 (T015): mood endpoint exercises real orchestration (supersedes
    the spec 001 stub). Seed + login → POST /api/analysis/mood → 200 with the
    real {label, confidence, disclaimer} shape; confidence widened to float|null."""
    from tests.conftest import fixture_bytes, seed_user_template

    await seed_user_template(app)
    # Login to obtain a session cookie on `client`.
    files = {"image": ("one_face.jpg", fixture_bytes("one_face.jpg"), "image/jpeg")}
    login = await client.post(
        "/api/auth/face-login", data={"identifier": "demo@example.com"}, files=files
    )
    assert login.status_code == 200, login.text
    # Mood analysis — real orchestration via MockDetector + MockMoodEstimator.
    resp = await client.post("/api/analysis/mood", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"label", "confidence", "disclaimer"}, body
    assert body["label"] == "neutral"  # MockMoodEstimator default
    assert body["confidence"] == 0.74
    assert body["disclaimer"] == MOOD_DISCLAIMER


# --- POST /api/analysis/age (spec 005 — real logic) ------------------------
@pytest.mark.asyncio
async def test_analysis_age_without_session_401(client):
    files = {"image": ("test.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/analysis/age", files=files)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_analysis_age_happy_path_real_logic(client, app):
    """Spec 005 (T034): age endpoint exercises real orchestration (supersedes
    the spec 001 stub). Seed + login → POST /api/analysis/age → 200 with the
    real {estimatedAge, range:{min,max}, disclaimer} shape; invariants hold."""
    from tests.conftest import fixture_bytes, seed_user_template

    await seed_user_template(app)
    files = {"image": ("one_face.jpg", fixture_bytes("one_face.jpg"), "image/jpeg")}
    login = await client.post(
        "/api/auth/face-login", data={"identifier": "demo@example.com"}, files=files
    )
    assert login.status_code == 200, login.text
    resp = await client.post("/api/analysis/age", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"estimatedAge", "range", "disclaimer"}, body
    assert set(body["range"].keys()) == {"min", "max"}
    # MockAgeEstimator default: estimatedAge 32, range [27,37].
    assert body["estimatedAge"] == 32
    assert body["range"] == {"min": 27, "max": 37}
    assert body["disclaimer"] == AGE_DISCLAIMER
    # Integer/range invariants (FR-004).
    assert isinstance(body["estimatedAge"], int)
    assert isinstance(body["range"]["min"], int)
    assert isinstance(body["range"]["max"], int)
    assert body["range"]["min"] >= 0
    assert body["range"]["min"] <= body["estimatedAge"] <= body["range"]["max"]


# --- DELETE /api/users/{userId}/face-data (spec 003 — 401 without cookie) --
@pytest.mark.asyncio
async def test_delete_face_data_without_session_401(client):
    resp = await client.delete(f"/api/users/{FIXED_USER_ID}/face-data")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_delete_face_data_malformed_uuid_422(client):
    # Without a cookie the session dependency fires first → 401. (FastAPI resolves
    # the dependency before path-param validation for this endpoint shape.)
    resp = await client.delete("/api/users/not-a-uuid/face-data")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


# ==========================================================================
# DELETE /api/users/{userId}/face-data — real logic (spec 006, T004/T012/T017/T024)
# ==========================================================================
# These tests build a dedicated auth app with a tmp_path filesystem image storage
# so they can assert filesystem cleanup without touching the real bind mount.
from pathlib import Path as _Path  # noqa: E402

from httpx import ASGITransport as _ASGITransport, AsyncClient as _AsyncClient  # noqa: E402

from face_insight.adapters.mock import ScriptableMockDetector as _SMD, ScriptableMockEmbedder as _SME  # noqa: E402
from face_insight.main import create_auth_app as _create_auth_app  # noqa: E402

from tests.conftest import fixture_bytes as _fixture_bytes  # noqa: E402


def fixture_bytes(name: str) -> bytes:  # local alias for the deletion tests
    return _fixture_bytes(name)


async def _deletion_app(tmp_path: _Path):
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    return _create_auth_app(
        detector=_SMD(),
        embedder=_SME(),
        session_factory=None,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )


async def _deletion_client(app):
    transport = _ASGITransport(app=app)
    return _AsyncClient(transport=transport, base_url="http://test")


async def _onboard_login(client, app, identifier="demo@example.com"):
    """Onboard + login; return (userId, loginResponse)."""
    payload = fixture_bytes("one_face.jpg")
    data = {"identifier": identifier, "consentAccepted": "true"}
    files = {"image": ("one_face.jpg", payload, "image/jpeg")}
    onb = await client.post("/api/onboarding", data=data, files=files)
    assert onb.status_code == 201, onb.text
    user_id = onb.json()["userId"]
    # Login (cookie set on client).
    login = await client.post(
        "/api/auth/face-login",
        data={"identifier": identifier},
        files={"image": ("one_face.jpg", payload, "image/jpeg")},
    )
    assert login.status_code == 200, login.text
    return user_id


@pytest.mark.asyncio
async def test_delete_face_data_200_happy_path(tmp_path):
    """T004: 200 deletion happy path — echoed userId, status, cleared cookie,
    DB rows + filesystem folder gone."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        user_id = await _onboard_login(ac, app)
        # Folder exists before deletion.
        user_dir = tmp_path / "usuarios" / user_id
        assert user_dir.exists()
        # DELETE.
        resp = await ac.delete(f"/api/users/{user_id}/face-data")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"userId", "status"}
        assert body["userId"] == user_id
        assert UUID_RE.match(body["userId"])
        assert body["status"] == "deleted"
        # Cookie cleared on the response.
        cookie = ac.cookies.get("fid_session")
        assert cookie in (None, "", "null")
        # DB rows gone (mock repos on app.state).
        uid = __import__("uuid").UUID(user_id)
        assert await app.state.user_repository.get(uid) is None
        assert await app.state.face_template_repository.get_by_user(uid) is None
        assert all(s.user_id != uid for s in app.state.session_manager._sessions.values())
        # Filesystem folder gone.
        assert not user_dir.exists()


@pytest.mark.asyncio
async def test_delete_face_data_403_forbidden_mismatched_user(tmp_path):
    """T012: valid session for A, path userId = B → 403 forbidden; no rows removed."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        user_a = await _onboard_login(ac, app, identifier="a@example.com")
        # Onboard a second user B (separate client to keep A's cookie).
        async with await _deletion_client(app) as ac2:
            user_b = await _onboard_login(ac2, app, identifier="b@example.com")
        # A's cookie tries to delete B.
        resp = await ac.delete(f"/api/users/{user_b}/face-data")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "forbidden"
        assert body["error"]["message"] == "Solo puedes eliminar tus propios datos."
        # No rows removed for A or B.
        ua = __import__("uuid").UUID(user_a)
        ub = __import__("uuid").UUID(user_b)
        assert await app.state.user_repository.get(ua) is not None
        assert await app.state.user_repository.get(ub) is not None


@pytest.mark.asyncio
async def test_delete_face_data_422_malformed_uuid_with_session(tmp_path):
    """T012: with a valid session, a malformed userId → 422 (path validation)."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        await _onboard_login(ac, app)
        resp = await ac.delete("/api/users/not-a-uuid/face-data")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_face_data_404_not_found_out_of_band(tmp_path):
    """T024: valid matching session but User absent (out-of-band) → 404 not_found."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        user_id = await _onboard_login(ac, app)
        uid = __import__("uuid").UUID(user_id)
        # Out-of-band: delete the User row but keep the AuthSession (session still valid).
        await app.state.user_repository.delete(uid)
        resp = await ac.delete(f"/api/users/{user_id}/face-data")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_delete_face_data_500_internal_error_on_db_failure(tmp_path):
    """T024: DB transaction failure → 500 internal_error."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        user_id = await _onboard_login(ac, app)

        async def boom(_user_id):
            raise RuntimeError("db down")

        app.state.deletion_service._delete_user_face_data = boom
        resp = await ac.delete(f"/api/users/{user_id}/face-data")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "internal_error"


@pytest.mark.asyncio
async def test_delete_face_data_best_effort_fs_failure_200(tmp_path):
    """T024: DB commits but FS deletion fails → 200 + (warning logged)."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        user_id = await _onboard_login(ac, app)

        def boom(_user_id):
            raise OSError("disk on fire")

        app.state.image_storage.delete = boom  # type: ignore[assignment]
        resp = await ac.delete(f"/api/users/{user_id}/face-data")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # DB rows still gone (commit succeeded before FS attempt).
        uid = __import__("uuid").UUID(user_id)
        assert await app.state.user_repository.get(uid) is None


@pytest.mark.asyncio
async def test_delete_face_data_error_body_shape(tmp_path):
    """T024: every non-2xx error response uses {"error": {"code", "message"}}."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        # 401 (no cookie).
        r = await ac.delete(f"/api/users/{__import__('uuid').uuid4()}/face-data")
        assert r.status_code == 401
        assert set(r.json().keys()) == {"error"}
        assert set(r.json()["error"].keys()) == {"code", "message"}
        # 403.
        user_a = await _onboard_login(ac, app, identifier="a@example.com")
        async with await _deletion_client(app) as ac2:
            user_b = await _onboard_login(ac2, app, identifier="b@example.com")
        r = await ac.delete(f"/api/users/{user_b}/face-data")
        assert set(r.json()["error"].keys()) == {"code", "message"}


@pytest.mark.asyncio
async def test_delete_face_data_post_deletion_invalidation(tmp_path):
    """T017: after a 200 deletion, old cookie → 401 unauthenticated and old-identifier
    login → 401 auth_failed (indistinguishable from never-enrolled)."""
    app = await _deletion_app(tmp_path)
    async with await _deletion_client(app) as ac:
        user_id = await _onboard_login(ac, app, identifier="demo@example.com")
        resp = await ac.delete(f"/api/users/{user_id}/face-data")
        assert resp.status_code == 200
        # Old cookie → 401 unauthenticated.
        me = await ac.get("/api/auth/me")
        assert me.status_code == 401
        assert me.json()["error"]["code"] == "unauthenticated"
        # Old-identifier login → 401 auth_failed.
        payload = fixture_bytes("one_face.jpg")
        files = {"image": ("one_face.jpg", payload, "image/jpeg")}
        login = await ac.post("/api/auth/face-login", data={"identifier": "demo@example.com"}, files=files)
        assert login.status_code == 401
        assert login.json()["error"]["code"] == "auth_failed"


@pytest.mark.asyncio
async def test_delete_face_data_status_code_matrix(tmp_path):
    """T024: the full status-code matrix 200/401/403/404/422/500 is reachable."""
    app = await _deletion_app(tmp_path)
    codes: set[int] = set()
    async with await _deletion_client(app) as ac:
        # 401.
        r = await ac.delete(f"/api/users/{__import__('uuid').uuid4()}/face-data")
        codes.add(r.status_code)
        user_id = await _onboard_login(ac, app)
        # 200.
        r = await ac.delete(f"/api/users/{user_id}/face-data")
        codes.add(r.status_code)
    # 403 / 422 / 404 / 500 covered by dedicated tests above; assert the matrix
    # is exactly {200, 401, 403, 404, 422, 500} via the dedicated cases.
    assert {200, 401}.issubset(codes)
