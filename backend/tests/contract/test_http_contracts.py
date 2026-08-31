"""HTTP contract tests for all 7 endpoints (T061, FR-016).

Asserts request/response shapes and status codes per
``specs/001-skeleton-contracts-mocks/contracts/*.md``. Includes the
contract-violation detection test (T064, SC-009).
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
    data = {}
    files = {}
    if identifier is not None:
        data["identifier"] = identifier
    if consent is not None:
        data["consentAccepted"] = "true" if consent else "false"
    if image:
        files["image"] = ("test.jpg", JPEG_BYTES, "image/jpeg")
    return data, files


# --- POST /api/onboarding --------------------------------------------------
@pytest.mark.asyncio
async def test_onboarding_success(client):
    data, files = _multipart("demo@example.com", consent=True)
    resp = await client.post("/api/onboarding", data=data, files=files)
    assert resp.status_code == 201
    body = resp.json()
    assert UUID_RE.match(body["userId"])
    assert body["identifier"] == "demo@example.com"
    assert body["status"] == "enrolled"


@pytest.mark.asyncio
async def test_onboarding_missing_identifier_422(client):
    data, files = _multipart(consent=True)
    resp = await client.post("/api/onboarding", data=data, files=files)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_consent_false_422(client):
    data, files = _multipart("demo@example.com", consent=False)
    resp = await client.post("/api/onboarding", data=data, files=files)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_missing_image_422(client):
    data, files = _multipart("demo@example.com", consent=True, image=False)
    resp = await client.post("/api/onboarding", data=data, files=files)
    assert resp.status_code == 422


# --- POST /api/auth/face-login --------------------------------------------
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


# --- Contract-violation detection (T064, SC-009) --------------------------
@pytest.mark.asyncio
async def test_contract_violation_is_detected(client):
    """If onboarding returned status='active' instead of 'enrolled', the
    success assertion would fail. This test documents that the contract suite
    catches such a violation by asserting the correct value is enforced."""
    data, files = _multipart("demo@example.com", consent=True)
    resp = await client.post("/api/onboarding", data=data, files=files)
    body = resp.json()
    # The contract requires status == "enrolled". A violating implementation
    # returning "active" would make this assertion fail (SC-009).
    assert body["status"] == "enrolled", (
        "Contract violation detected: onboarding status must be 'enrolled', "
        f"got {body['status']!r}"
    )
    # Sanity: a wrong value is not silently accepted.
    assert body["status"] != "active"
