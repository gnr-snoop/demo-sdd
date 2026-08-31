"""Pytest fixtures for the contract + domain + integration suites (T059, spec 002).

No GPU, no network, no real ML models (FR-017, SC-008). The FastAPI app is
driven in-process via httpx ASGITransport.

Spec 002 adds onboarding-specific fixtures: a scriptable-detector app (for
rejection contract tests) and the fixtures directory path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    """Read a fixture file from backend/tests/fixtures/."""
    return (FIXTURES_DIR / name).read_bytes()


@pytest.fixture
async def app():
    application = create_app()
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def scriptable_app():
    """App wired with ScriptableMockDetector for rejection contract tests (R-6)."""
    from face_insight.adapters.mock import ScriptableMockDetector
    from face_insight.domain.onboarding import OnboardingService

    application = create_app()
    application.state.detector = ScriptableMockDetector()
    application.state.onboarding_service = OnboardingService(
        detector=application.state.detector,
        embedder=application.state.embedder,
        user_repository=application.state.user_repository,
        face_template_repository=application.state.face_template_repository,
        image_storage=application.state.image_storage,
        quality_threshold=0.5,
        embedding_model_version="mock-embedder-v1",
    )
    return application


@pytest.fixture
async def scriptable_client(scriptable_app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=scriptable_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Spec 003 auth fixtures (T013/T020/T032) -------------------------------
@pytest.fixture
async def auth_app():
    """App wired with ScriptableMockDetector + ScriptableMockEmbedder for login
    contract tests. Mock repos (no DB) — seeded per-test via app.state."""
    from face_insight.adapters.mock import ScriptableMockDetector, ScriptableMockEmbedder

    from face_insight.main import create_auth_app

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        session_factory=None,
    )
    return app


@pytest.fixture
async def auth_client(auth_app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def seed_user_template(app, identifier="demo@example.com"):
    """Seed the mock repos with a User + FaceTemplate (mock 128-dim 0.1 embedding)."""
    from datetime import datetime, timezone

    from face_insight.adapters.mock.constants import EMBEDDING_DIM, EMBEDDING_FILL, EMBED_MODEL_VERSION
    from face_insight.domain.entities import create_face_template, create_user

    now = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
    user = create_user(identifier, now=lambda: now)
    await app.state.user_repository.save(user)
    template = create_face_template(
        user.id,
        [EMBEDDING_FILL] * EMBEDDING_DIM,
        EMBED_MODEL_VERSION,
        now=lambda: now,
    )
    await app.state.face_template_repository.save(template)
    return user


# A stable JPEG-ish payload for multipart uploads in the spec 001 contract tests
# (non-onboarding stub endpoints that do not decode the image).
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
SESSION_HEADER = {"X-Session-Id": "00000000-0000-4000-8000-000000000002"}
FIXED_USER_ID = "00000000-0000-4000-8000-000000000001"
