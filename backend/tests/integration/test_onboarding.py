"""Integration tests for POST /api/onboarding (T012/T017/T022/T034).

Two layers:
  1. **FS-only** (always runs, no DB): real FilesystemImageStorage + mock
     in-memory repos + mock detector/embedder via ``create_onboarding_app``.
     Verifies the full HTTP flow, FS image storage, mock-repo persistence, and
     resize dimensions.
  2. **DB-required** (skips without PostgreSQL): real SQLAlchemy async repos +
     atomic unit-of-work + real FS. Verifies real DB persistence, the
     IntegrityError → 409 path, and all-or-nothing on rejection.

No GPU, no network (mock detector/embedder only).
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from face_insight.adapters.fs.image_storage import FilesystemImageStorage
from face_insight.adapters.mock import MockEmbedder, ScriptableMockDetector
from face_insight.main import create_onboarding_app


# --- Helpers ---------------------------------------------------------------
def fixture_bytes(name: str) -> bytes:
    return (Path(__file__).resolve().parents[1] / "fixtures" / name).read_bytes()


def _post(client, identifier="demo@example.com", consent="true", image_name="one_face.jpg"):
    payload = fixture_bytes(image_name)
    data = {"identifier": identifier, "consentAccepted": consent}
    files = {"image": (image_name, payload, "image/jpeg")}
    return client.post("/api/onboarding", data=data, files=files)


async def _client_for(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ==========================================================================
# Layer 1: FS-only (always runs)
# ==========================================================================

@pytest.fixture
async def fs_app(tmp_path: Path):
    storage = FilesystemImageStorage(root=tmp_path)
    app = create_onboarding_app(
        detector=ScriptableMockDetector(),
        embedder=MockEmbedder(),
        session_factory=None,
        image_storage=storage,
    )
    yield app


@pytest.fixture
async def fs_client(fs_app) -> AsyncClient:
    async with await _client_for(fs_app) as ac:
        yield ac


# --- T012: happy path ------------------------------------------------------
@pytest.mark.asyncio
async def test_fs_happy_path_201_and_image_stored(fs_client, fs_app, tmp_path):
    resp = await _post(fs_client, identifier="Demo@Example.com ")
    assert resp.status_code == 201
    body = resp.json()
    assert body["identifier"] == "demo@example.com"
    assert body["status"] == "enrolled"
    user_id = body["userId"]
    # UUID v4
    u = uuid.UUID(user_id)
    assert u.version == 4
    # Image stored at usuarios/<userId>/pictures.jpg on the real FS.
    img_path = tmp_path / "usuarios" / user_id / "pictures.jpg"
    assert img_path.exists()
    stored = Image.open(img_path)
    assert stored.format == "JPEG"
    # Long edge <= 640 (resize enforced).
    assert max(stored.width, stored.height) <= 640


# --- T017: invalid capture rejections (no persistence) ---------------------
@pytest.mark.asyncio
async def test_fs_no_face_422_no_persistence(fs_client, fs_app):
    resp = await _post(fs_client, identifier="nf@example.com", image_name="no_face.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "no_face"
    assert await fs_app.state.user_repository.get_by_identifier("nf@example.com") is None


@pytest.mark.asyncio
async def test_fs_multiple_faces_422_no_persistence(fs_client, fs_app):
    resp = await _post(fs_client, identifier="mf@example.com", image_name="multi_face.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "multiple_faces"
    assert await fs_app.state.user_repository.get_by_identifier("mf@example.com") is None


@pytest.mark.asyncio
async def test_fs_insufficient_quality_422_no_persistence(fs_client, fs_app):
    resp = await _post(fs_client, identifier="lq@example.com", image_name="low_quality.jpg")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "insufficient_quality"
    assert await fs_app.state.user_repository.get_by_identifier("lq@example.com") is None


@pytest.mark.asyncio
async def test_fs_undecodable_422_no_persistence(fs_client, fs_app):
    resp = await _post(fs_client, identifier="ni@example.com", image_name="not_an_image.txt")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_image"
    assert await fs_app.state.user_repository.get_by_identifier("ni@example.com") is None


# --- T022: case-insensitive duplicate (mock repos, pre-commit check) -------
@pytest.mark.asyncio
async def test_fs_case_insensitive_duplicate_409(fs_client):
    first = await _post(fs_client, identifier="demo@example.com")
    assert first.status_code == 201
    second = await _post(fs_client, identifier="DEMO@Example.COM")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "identifier_taken"


# --- T022: non-boolean consent --------------------------------------------
@pytest.mark.asyncio
async def test_fs_non_boolean_consent_422(fs_client):
    resp = await _post(fs_client, identifier="demo@example.com", consent="yes")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "consent_required"


# --- T034: resized image dimensions ---------------------------------------
@pytest.mark.asyncio
async def test_fs_resized_image_long_edge_within_limit(fs_client, tmp_path):
    # one_face.jpg is 100x100 (within 640) — no resize. Use a large fixture
    # built on the fly to exercise resize end-to-end through the route.
    big = Image.new("RGB", (2000, 1200), (200, 100, 50))
    buf = io.BytesIO()
    big.save(buf, format="JPEG", quality=90)
    resp = await fs_client.post(
        "/api/onboarding",
        data={"identifier": "big@example.com", "consentAccepted": "true"},
        files={"image": ("big.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert resp.status_code == 201
    user_id = resp.json()["userId"]
    img_path = tmp_path / "usuarios" / user_id / "pictures.jpg"
    stored = Image.open(img_path)
    assert max(stored.width, stored.height) <= 640
    # Aspect ratio roughly preserved (2000:1200 ≈ 1.67).
    assert stored.width / stored.height == pytest.approx(1.67, rel=0.05)


# ==========================================================================
# Layer 2: DB-required (skips without PostgreSQL)
# ==========================================================================

async def _db_available() -> bool:
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from face_insight.config import get_settings

        engine = create_async_engine(get_settings().database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
async def require_db():
    if not await _db_available():
        pytest.skip("PostgreSQL not available — DB integration test skipped")
    yield


@pytest.fixture
async def db_session_factory(require_db):
    """Yield a fresh async session factory with migrations applied; truncate after."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from face_insight.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    # Apply migrations. Run in an isolated thread: alembic/env.py calls
    # asyncio.run() at import time, which is forbidden inside the running
    # pytest-asyncio event loop.
    import threading
    from alembic import command
    from alembic.config import Config

    def _run_upgrade() -> None:
        cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")

    t = threading.Thread(target=_run_upgrade)
    t.start()
    t.join()

    # Truncate tables for a clean slate.
    async with engine.begin() as conn:
        for tbl in ("face_templates", "users"):
            await conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE"))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    # Cleanup.
    async with engine.begin() as conn:
        for tbl in ("face_templates", "users"):
            await conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def db_app(db_session_factory, tmp_path: Path):
    storage = FilesystemImageStorage(root=tmp_path)
    app = create_onboarding_app(
        detector=ScriptableMockDetector(),
        embedder=MockEmbedder(),
        session_factory=db_session_factory,
        image_storage=storage,
    )
    yield app


@pytest.fixture
async def db_client(db_app) -> AsyncClient:
    async with await _client_for(db_app) as ac:
        yield ac


# --- T012 (DB): happy path persists one User + one FaceTemplate ------------
@pytest.mark.asyncio
async def test_db_happy_path_persists_atomically(db_client, db_session_factory):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from face_insight.adapters.db.models import FaceTemplateORM, UserORM

    resp = await _post(db_client, identifier="demo@example.com")
    assert resp.status_code == 201
    user_id = resp.json()["userId"]

    async with db_session_factory() as session:  # type: AsyncSession
        users = (await session.execute(select(UserORM))).scalars().all()
        templates = (await session.execute(select(FaceTemplateORM))).scalars().all()
    assert len(users) == 1
    assert str(users[0].id) == user_id
    assert users[0].status == "enrolled"
    assert users[0].identifier == "demo@example.com"
    assert len(templates) == 1
    assert str(templates[0].user_id) == user_id
    assert templates[0].model_version == "mock-embedder-v1"


# --- T022 (DB): case-insensitive duplicate via DB unique constraint --------
@pytest.mark.asyncio
async def test_db_case_insensitive_duplicate_409(db_client):
    first = await _post(db_client, identifier="demo@example.com")
    assert first.status_code == 201
    second = await _post(db_client, identifier="DEMO@Example.COM")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "identifier_taken"


# --- T017 (DB): no persistence on capture rejection ------------------------
@pytest.mark.asyncio
async def test_db_no_face_no_persistence(db_client, db_session_factory):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from face_insight.adapters.db.models import UserORM

    resp = await _post(db_client, identifier="nf@example.com", image_name="no_face.jpg")
    assert resp.status_code == 422
    async with db_session_factory() as session:  # type: AsyncSession
        users = (await session.execute(select(UserORM))).scalars().all()
    assert len(users) == 0
