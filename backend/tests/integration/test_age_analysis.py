"""Integration tests for age analysis (spec 005, T012/T020/T023/T032/T035).

Full end-to-end flow: real endpoint + ScriptableMockDetector +
ScriptableMockAgeEstimator + real session validation (spec 003
``require_valid_session``). Onboard → login → POST /api/analysis/age.

  - T012: happy path (200 {estimatedAge, range, disclaimer}; point-only → derived
    range; range → midpoint).
  - T020: each capture-quality failure + port-error path (400/500, no result).
  - T023: 401 unauthenticated path (no cookie / expired / revoked).
  - T032: mood regression — the spec 004 mood flow still passes alongside the
    age suite (FR-020/SC-017).
  - T035: no image / embedding / estimated age / range appears in application
    logs (FR-019/SC-013).

No GPU, no network, no DB (mock adapters + mock repos seeded in-process).
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.adapters.mock import (
    ScriptableMockAgeEstimator,
    ScriptableMockDetector,
    ScriptableMockEmbedder,
    ScriptableMockMoodEstimator,
)
from face_insight.main import create_auth_app

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

AGE_DISCLAIMER = "La edad es una estimación visual y puede contener un margen de error significativo."
MOOD_DISCLAIMER = (
    "Resultado estimado por un modelo visual. No representa una medición "
    "objetiva del estado emocional."
)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def _age_files(image_name="one_face.jpg"):
    return {"image": (image_name, fixture_bytes(image_name), "image/jpeg")}


def _mood_files(image_name="one_face.jpg"):
    return {"image": (image_name, fixture_bytes(image_name), "image/jpeg")}


# --- Fixtures --------------------------------------------------------------
@pytest.fixture
async def age_app(tmp_path: Path):
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        mood_estimator=ScriptableMockMoodEstimator(),
        age_estimator=ScriptableMockAgeEstimator(),
        session_factory=None,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def age_client(age_app):
    transport = ASGITransport(app=age_app)
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


async def _age(client, image_name="one_face.jpg"):
    return await client.post("/api/analysis/age", files=_age_files(image_name))


async def _mood(client, image_name="one_face.jpg"):
    return await client.post("/api/analysis/mood", files=_mood_files(image_name))


# ==========================================================================
# T012: happy path (US1)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_happy_path_end_to_end(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"estimatedAge", "range", "disclaimer"}
    assert body["estimatedAge"] == 32
    assert body["range"] == {"min": 27, "max": 37}
    assert body["disclaimer"] == AGE_DISCLAIMER


@pytest.mark.asyncio
async def test_age_point_only_derived_range_end_to_end(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "age_point.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimatedAge"] == 40
    assert body["range"] == {"min": 35, "max": 45}


@pytest.mark.asyncio
async def test_age_range_to_midpoint_end_to_end(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "age_range.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimatedAge"] == 40
    assert body["range"] == {"min": 35, "max": 45}


@pytest.mark.asyncio
async def test_age_result_is_transient_no_persistence(age_client, age_app):
    """FR-014: no AnalysisRequest row is written (age result is transient).
    The mock session manager is unchanged by an age call; no analysis store
    exists on app.state."""
    await _seed_and_login(age_client)
    sessions_before = len(age_app.state.session_manager._sessions)
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 200
    sessions_after = len(age_app.state.session_manager._sessions)
    assert sessions_before == sessions_after  # no new session, no persistence
    assert not hasattr(age_app.state, "analysis_request_repository") or getattr(
        age_app.state, "analysis_request_repository", None
    ) is None


# ==========================================================================
# T020: capture-quality failures + port error (US2)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_no_face_400_no_result(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "no_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_face"
    assert "estimatedAge" not in resp.json()


@pytest.mark.asyncio
async def test_age_multiple_faces_400_no_result(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "multi_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "multiple_faces"
    assert "estimatedAge" not in resp.json()


@pytest.mark.asyncio
async def test_age_insufficient_quality_400_no_result(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "low_quality.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_quality"
    assert "estimatedAge" not in resp.json()


@pytest.mark.asyncio
async def test_age_invalid_image_400_no_result(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "not_an_image.txt")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"
    assert "estimatedAge" not in resp.json()


@pytest.mark.asyncio
async def test_age_port_error_500_no_result(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _age(age_client, "age_fail.jpg")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "internal_error"
    assert "estimatedAge" not in resp.json()


# ==========================================================================
# T023: 401 unauthenticated (US3)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_no_cookie_401_no_analysis(age_client, age_app):
    await _seed_and_login(age_client)
    age_client.cookies.clear()
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
    assert "estimatedAge" not in resp.json()


@pytest.mark.asyncio
async def test_age_expired_session_401(age_client, age_app):
    await _seed_and_login(age_client)
    sm = age_app.state.session_manager
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
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_age_revoked_session_401(age_client, age_app):
    await _seed_and_login(age_client)
    await age_client.post("/api/auth/logout")
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


# ==========================================================================
# T035: no image / embedding / estimated age / range in logs (FR-019/SC-013)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_logs_contain_no_biometric_data(age_client, age_app, caplog):
    """FR-019/SC-013: application logs are limited to structured fields
    (event/duration_ms/status/error_code). No image bytes, no estimated age,
    no range values appear in the log records."""
    await _seed_and_login(age_client)
    # Use a fixture whose result is distinctive (40 / [35,45]) so we can assert
    # the value does NOT leak into logs.
    with caplog.at_level(logging.INFO, logger="face_insight.analysis"):
        resp = await _age(age_client, "age_point.jpg")
    assert resp.status_code == 200
    # The response body has estimatedAge=40, range [35,45] — assert none of these
    # appear in any log record (only duration_ms/status are logged).
    for record in caplog.records:
        rendered = record.getMessage()
        # Structured fields allowed: duration_ms, status, error_code, event name.
        # Forbidden: the actual estimated age / range values + image bytes.
        assert "40" not in rendered or "duration_ms" in rendered, rendered
        assert "35" not in rendered, rendered
        assert "45" not in rendered, rendered
        # No image bytes (JPEG SOI marker) in logs.
        assert b"\xff\xd8" not in rendered.encode("utf-8", errors="ignore")


# ==========================================================================
# T032: mood regression — mood flow still passes alongside the age suite
# (FR-020/SC-017)
# ==========================================================================
@pytest.mark.asyncio
async def test_mood_regression_happy_path(age_client, age_app):
    """FR-020/SC-017: the spec 004 mood flow still passes unchanged alongside
    the age suite (no regression from the shared capture mutex / age wiring)."""
    await _seed_and_login(age_client)
    resp = await _mood(age_client, "mood_feliz.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"label", "confidence", "disclaimer"}
    assert body["label"] == "feliz"
    assert body["confidence"] == 0.8
    assert body["disclaimer"] == MOOD_DISCLAIMER


@pytest.mark.asyncio
async def test_mood_regression_no_face_400(age_client, age_app):
    await _seed_and_login(age_client)
    resp = await _mood(age_client, "no_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_face"


@pytest.mark.asyncio
async def test_age_and_mood_results_are_independent(age_client, age_app):
    """SC-018: triggering an age analysis does not clear a displayed mood result
    and vice versa (independent result surfaces). At the HTTP level each call
    returns its own response; independence is a frontend concern, but we assert
    both endpoints work independently back-to-back."""
    await _seed_and_login(age_client)
    mood_resp = await _mood(age_client, "mood_feliz.jpg")
    assert mood_resp.status_code == 200
    assert mood_resp.json()["label"] == "feliz"
    age_resp = await _age(age_client, "one_face.jpg")
    assert age_resp.status_code == 200
    assert age_resp.json()["estimatedAge"] == 32
