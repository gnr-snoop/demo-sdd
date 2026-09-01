"""Integration tests for mood analysis (spec 004, T011/T018/T021).

Full end-to-end flow: real endpoint + ScriptableMockDetector +
ScriptableMockMoodEstimator + real session validation (spec 003
``require_valid_session``). Onboard → login → POST /api/analysis/mood.

  - T011: happy path (200 {label, confidence, disclaimer}).
  - T018: each capture-quality failure + port-error path (400/500, no result).
  - T021: 401 unauthenticated path (no cookie / expired / revoked).

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


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def _mood_files(image_name="one_face.jpg"):
    return {"image": (image_name, fixture_bytes(image_name), "image/jpeg")}


# --- Fixtures --------------------------------------------------------------
@pytest.fixture
async def mood_app(tmp_path: Path):
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


async def _seed_and_login(client, identifier="demo@example.com"):
    payload = fixture_bytes("one_face.jpg")
    data = {"identifier": identifier, "consentAccepted": "true"}
    files = {"image": ("one_face.jpg", payload, "image/jpeg")}
    onb = await client.post("/api/onboarding", data=data, files=files)
    assert onb.status_code == 201, onb.text
    login = await client.post(
        "/api/auth/face-login", data={"identifier": identifier}, files=files
    )
    assert login.status_code == 200, login.text


async def _mood(client, image_name="one_face.jpg"):
    return await client.post("/api/analysis/mood", files=_mood_files(image_name))


# ==========================================================================
# T011: happy path (US1)
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_happy_path_end_to_end(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "mood_feliz.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"label", "confidence", "disclaimer"}
    assert body["label"] == "feliz"
    assert body["confidence"] == 0.8
    assert body["disclaimer"] == MOOD_DISCLAIMER


@pytest.mark.asyncio
async def test_mood_happy_path_default_neutral(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "neutral"
    assert body["confidence"] == 0.74


@pytest.mark.asyncio
async def test_mood_result_is_transient_no_persistence(mood_client, mood_app):
    """FR-014: no AnalysisRequest row is written (mood result is transient).
    The mock session manager is unchanged by a mood call; no analysis store
    exists on app.state."""
    await _seed_and_login(mood_client)
    sessions_before = len(mood_app.state.session_manager._sessions)
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 200
    sessions_after = len(mood_app.state.session_manager._sessions)
    assert sessions_before == sessions_after  # no new session, no persistence
    assert not hasattr(mood_app.state, "analysis_request_repository") or getattr(
        mood_app.state, "analysis_request_repository", None
    ) is None


# ==========================================================================
# T018: capture-quality failures + port error (US2)
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_no_face_400_no_result(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "no_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_face"
    # No mood result produced on error.
    assert "label" not in resp.json()


@pytest.mark.asyncio
async def test_mood_multiple_faces_400_no_result(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "multi_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "multiple_faces"
    assert "label" not in resp.json()


@pytest.mark.asyncio
async def test_mood_insufficient_quality_400_no_result(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "low_quality.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_quality"
    assert "label" not in resp.json()


@pytest.mark.asyncio
async def test_mood_invalid_image_400_no_result(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "not_an_image.txt")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"
    assert "label" not in resp.json()


@pytest.mark.asyncio
async def test_mood_port_error_500_no_result(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "mood_fail.jpg")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "internal_error"
    assert "label" not in resp.json()


@pytest.mark.asyncio
async def test_mood_out_of_set_normalizes_to_no_concluyente(mood_client, mood_app):
    await _seed_and_login(mood_client)
    resp = await _mood(mood_client, "mood_out_of_set.jpg")
    assert resp.status_code == 200
    assert resp.json()["label"] == "no concluyente"


# ==========================================================================
# T021: 401 unauthenticated (US3)
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_no_cookie_401_no_analysis(mood_client, mood_app):
    await _seed_and_login(mood_client)
    mood_client.cookies.clear()
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
    assert "label" not in resp.json()


@pytest.mark.asyncio
async def test_mood_expired_session_401(mood_client, mood_app):
    await _seed_and_login(mood_client)
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
    await _seed_and_login(mood_client)
    await mood_client.post("/api/auth/logout")
    resp = await _mood(mood_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
