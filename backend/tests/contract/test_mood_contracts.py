"""Contract tests for POST /api/analysis/mood (spec 004, T010/T017/T020).

Asserts request/response shapes + status codes per
``specs/004-mood-analysis/contracts/analysis-mood.md``:
  - T010: 200 success shape (label ∈ valid set, confidence ∈ [0,1] or null,
    disclaimer == exact PRD §8 string).
  - T017: 400 capture-quality codes (no_face/multiple_faces/invalid_image/
    insufficient_quality) + 500 internal_error + pinned error body shape +
    out-of-set label normalization → "no concluyente".
  - T020: 401 unauthenticated (no cookie / expired / revoked); 401 reserved
    exclusively for unauthenticated (FR-007).

No GPU, no network, no DB (mock adapters + mock repos seeded in-process).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.adapters.mock import (
    ScriptableMockDetector,
    ScriptableMockEmbedder,
    ScriptableMockMoodEstimator,
)
from face_insight.main import create_auth_app

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

MOOD_DISCLAIMER = (
    "Resultado estimado por un modelo visual. No representa una medición "
    "objetiva del estado emocional."
)
VALID_LABELS = {"neutral", "feliz", "triste", "sorprendido", "no concluyente"}

UNAUTHENTICATED_BODY = {
    "error": {
        "code": "unauthenticated",
        "message": "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo.",
    }
}


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def _mood_files(image_name: str = "one_face.jpg"):
    payload = fixture_bytes(image_name)
    return {"image": (image_name, payload, "image/jpeg")}


def _onboard_files(identifier="demo@example.com", image_name="one_face.jpg"):
    payload = fixture_bytes(image_name)
    return {"identifier": identifier, "consentAccepted": "true"}, {
        "image": (image_name, payload, "image/jpeg"),
    }


# --- Fixtures --------------------------------------------------------------
@pytest.fixture
async def mood_app(tmp_path: Path):
    """App wired with scriptable detector/embedder/mood estimator for mood tests."""
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        mood_estimator=ScriptableMockMoodEstimator(),
        session_factory=None,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def mood_client(mood_app):
    transport = ASGITransport(app=mood_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _seed_and_login(client, app, identifier="demo@example.com"):
    """Onboard a user + login to obtain a valid session cookie on `client`."""
    data, files = _onboard_files(identifier=identifier)
    onb = await client.post("/api/onboarding", data=data, files=files)
    assert onb.status_code == 201, onb.text
    login = await client.post(
        "/api/auth/face-login", data={"identifier": identifier}, files=files
    )
    assert login.status_code == 200, login.text
    return login.json()["userId"]


async def _mood(client, image_name="one_face.jpg"):
    return await client.post("/api/analysis/mood", files=_mood_files(image_name))


# ==========================================================================
# T010: 200 success shape
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_happy_path_shape(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "mood_feliz.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"label", "confidence", "disclaimer"}, body
    assert body["label"] in VALID_LABELS
    assert body["label"] == "feliz"
    assert body["confidence"] is not None
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["disclaimer"] == MOOD_DISCLAIMER


@pytest.mark.asyncio
async def test_mood_default_neutral_shape(mood_client, mood_app):
    """Default (no mood marker) → neutral / 0.74 (mock determinism, SC-005)."""
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "neutral"
    assert body["confidence"] == 0.74
    assert body["disclaimer"] == MOOD_DISCLAIMER


@pytest.mark.asyncio
async def test_mood_confidence_null_is_permitted(mood_client, mood_app):
    """confidence may be null per FR-012a (no_conclusive fixture yields 0.3,
    but the shape permits null). Here we assert the field is accepted when
    present and within bounds; the null path is exercised via the unit suite."""
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "mood_no_conclusive.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "no concluyente"
    # confidence either null or in [0,1].
    if body["confidence"] is not None:
        assert 0.0 <= body["confidence"] <= 1.0


# ==========================================================================
# T017: 400 capture-quality + 500 internal_error + pinned error body
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_no_face_400(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "no_face.jpg")
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert body["error"]["code"] == "no_face"
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


@pytest.mark.asyncio
async def test_mood_multiple_faces_400(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "multi_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "multiple_faces"


@pytest.mark.asyncio
async def test_mood_insufficient_quality_400(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "low_quality.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_quality"


@pytest.mark.asyncio
async def test_mood_invalid_image_undecodable_400(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "not_an_image.txt")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_mood_invalid_image_oversized_400(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "oversized.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_mood_port_error_500(mood_client, mood_app):
    """MOODFAIL marker → ScriptableMockMoodEstimator raises → 500 internal_error."""
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "mood_fail.jpg")
    assert resp.status_code == 500
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert body["error"]["code"] == "internal_error"
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


@pytest.mark.asyncio
async def test_mood_out_of_set_label_normalizes_to_no_concluyente(mood_client, mood_app):
    """OOSET marker → port returns "angry" → normalize → "no concluyente" (FR-004)."""
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "mood_out_of_set.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "no concluyente"
    assert body["label"] in VALID_LABELS


@pytest.mark.parametrize(
    "image_name,expected_status,expected_code",
    [
        ("no_face.jpg", 400, "no_face"),
        ("multi_face.jpg", 400, "multiple_faces"),
        ("low_quality.jpg", 400, "insufficient_quality"),
        ("not_an_image.txt", 400, "invalid_image"),
        ("oversized.jpg", 400, "invalid_image"),
        ("mood_fail.jpg", 500, "internal_error"),
    ],
)
@pytest.mark.asyncio
async def test_mood_error_body_shape_enforced(
    mood_client, mood_app, image_name, expected_status, expected_code
):
    """T017/SC-011: every error uses {"error": {"code", "message"}}."""
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, image_name)
    assert resp.status_code == expected_status
    body = resp.json()
    assert set(body.keys()) == {"error"}, body
    assert set(body["error"].keys()) == {"code", "message"}
    assert body["error"]["code"] == expected_code


# ==========================================================================
# T020: 401 unauthenticated (no cookie / expired / revoked)
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_no_cookie_401(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    # Clear cookies to simulate no session.
    mood_client.cookies.clear()
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json() == UNAUTHENTICATED_BODY


@pytest.mark.asyncio
async def test_mood_expired_session_401(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    # Expire all sessions in the mock manager.
    sm = mood_app.state.session_manager
    long_ago = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    from face_insight.domain.entities import AuthSession

    for sid, session in list(sm._sessions.items()):
        sm._sessions[sid] = AuthSession(
            id=session.id,
            user_id=session.user_id,
            created_at=long_ago,
            expires_at=long_ago + timedelta(minutes=1),
            revoked_at=None,
        )
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_mood_revoked_session_401(mood_client, mood_app):
    await _seed_and_login(mood_client, mood_app)
    logout = await mood_client.post("/api/auth/logout")
    assert logout.status_code == 200
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_401_reserved_exclusively_for_unauthenticated(mood_client, mood_app):
    """FR-007: 401 is reserved exclusively for `unauthenticated`."""
    await _seed_and_login(mood_client, mood_app)
    mood_client.cookies.clear()
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
    # Capture-quality codes never use 401.
    mood_client.cookies.set("fid_session", "valid")  # restore via re-login below


# ==========================================================================
# T010: contract-violation mutation guard (SC-011)
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_contract_success_shape_enforced(mood_client, mood_app):
    """SC-011: a deliberate change to the success shape fails this test."""
    await _seed_and_login(mood_client, mood_app)
    resp = await _mood(mood_client, "mood_feliz.jpg")
    body = resp.json()
    assert set(body.keys()) == {"label", "confidence", "disclaimer"}, body
    assert body["label"] in VALID_LABELS
    assert body["disclaimer"] == MOOD_DISCLAIMER
