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
# POST /api/auth/face-login (spec 001 stub — unchanged)
# ==========================================================================
@pytest.mark.asyncio
async def test_face_login_success(client):
    data, files = _multipart("demo@example.com")
    resp = await client.post("/api/auth/face-login", data=data, files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert UUID_RE.match(body["userId"])
    assert body["status"] == "authenticated"


@pytest.mark.asyncio
async def test_face_login_failure_generic_and_non_revealing(client):
    """Mock failure path returns a generic message identical for two triggers."""
    msg_a = await client.post(
        "/api/auth/face-login",
        data={"identifier": "unknown@example.com"},
        files={"image": ("fail.jpg", b"MOCK_FAIL", "image/jpeg")},
    )
    msg_b = await client.post(
        "/api/auth/face-login",
        data={"identifier": "another@example.com"},
        files={"image": ("fail.jpg", b"MOCK_FAIL", "image/jpeg")},
    )
    assert msg_a.status_code == 401
    assert msg_b.status_code == 401
    assert msg_a.json() == msg_b.json() == {"detail": "authentication failed"}


@pytest.mark.asyncio
async def test_face_login_missing_fields_422(client):
    resp = await client.post("/api/auth/face-login", data={})
    assert resp.status_code == 422


# --- GET /api/auth/me ------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_me_unauthenticated_401(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "unauthenticated"}


@pytest.mark.asyncio
async def test_auth_me_with_session_200(client):
    resp = await client.get("/api/auth/me", headers=SESSION_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert UUID_RE.match(body["userId"])
    assert body["status"] == "authenticated"
    assert "expiresAt" in body and body["expiresAt"]


# --- POST /api/auth/logout -------------------------------------------------
@pytest.mark.asyncio
async def test_logout_without_session_401(client):
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_session_200(client):
    resp = await client.post("/api/auth/logout", headers=SESSION_HEADER)
    assert resp.status_code == 200
    assert resp.json() == {"status": "logged_out"}


# --- POST /api/analysis/mood ----------------------------------------------
@pytest.mark.asyncio
async def test_analysis_mood_without_session_401(client):
    files = {"image": ("test.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/analysis/mood", files=files)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analysis_mood_success(client):
    files = {"image": ("test.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/analysis/mood", files=files, headers=SESSION_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "neutral"
    assert body["confidence"] == 0.74
    assert body["disclaimer"] == MOOD_DISCLAIMER


@pytest.mark.asyncio
async def test_analysis_mood_missing_image_422(client):
    resp = await client.post("/api/analysis/mood", headers=SESSION_HEADER)
    assert resp.status_code == 422


# --- POST /api/analysis/age -----------------------------------------------
@pytest.mark.asyncio
async def test_analysis_age_without_session_401(client):
    files = {"image": ("test.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/analysis/age", files=files)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analysis_age_success(client):
    files = {"image": ("test.jpg", JPEG_BYTES, "image/jpeg")}
    resp = await client.post("/api/analysis/age", files=files, headers=SESSION_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimatedAge"] == 32
    assert body["range"] == {"min": 27, "max": 37}
    assert body["estimatedAge"] >= body["range"]["min"]
    assert body["estimatedAge"] <= body["range"]["max"]
    assert body["disclaimer"] == AGE_DISCLAIMER


# --- DELETE /api/users/{userId}/face-data ---------------------------------
@pytest.mark.asyncio
async def test_delete_face_data_without_session_401(client):
    resp = await client.delete(f"/api/users/{FIXED_USER_ID}/face-data")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_face_data_success(client):
    resp = await client.delete(f"/api/users/{FIXED_USER_ID}/face-data", headers=SESSION_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["userId"] == FIXED_USER_ID
    assert body["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_face_data_malformed_uuid_422(client):
    resp = await client.delete("/api/users/not-a-uuid/face-data", headers=SESSION_HEADER)
    assert resp.status_code == 422
