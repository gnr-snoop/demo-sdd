"""Integration tests for login & session management (spec 003, T014/T022/T027/T033).

Two layers:
  1. **Mock-only** (always runs, no DB): real auth endpoints + ScriptableMockDetector/
     ScriptableMockEmbedder + mock in-memory repos + MockSessionManager. Verifies
     the full HTTP flow, session creation, cookie sign/unsign, route protection,
     and logout.
  2. **DB-required** (skips without PostgreSQL): real SQLAlchemy async repos +
     SqlAlchemySessionManager + real PostgreSQL. Verifies real DB session
     persistence, revocation, and expiry.

No GPU, no network (mock detector/embedder only).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.adapters.mock import MockEmbedder, ScriptableMockDetector, ScriptableMockEmbedder
from face_insight.main import create_auth_app


def fixture_bytes(name: str) -> bytes:
    return (Path(__file__).resolve().parents[1] / "fixtures" / name).read_bytes()


def _post_login(client, identifier="demo@example.com", image_name="one_face.jpg"):
    payload = fixture_bytes(image_name)
    data = {"identifier": identifier}
    files = {"image": (image_name, payload, "image/jpeg")}
    return client.post("/api/auth/face-login", data=data, files=files)


def _post_onboard(client, identifier="demo@example.com", image_name="one_face.jpg"):
    payload = fixture_bytes(image_name)
    data = {"identifier": identifier, "consentAccepted": "true"}
    files = {"image": (image_name, payload, "image/jpeg")}
    return client.post("/api/onboarding", data=data, files=files)


async def _client_for(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ==========================================================================
# Layer 1: Mock-only (always runs)
# ==========================================================================
@pytest.fixture
async def auth_app(tmp_path: Path):
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        session_factory=None,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def auth_client(auth_app) -> AsyncClient:
    async with await _client_for(auth_app) as ac:
        yield ac


async def _seed(app, identifier="demo@example.com"):
    """Onboard a user so login has a User + FaceTemplate to verify against."""
    async with await _client_for(app) as ac:
        resp = await _post_onboard(ac, identifier=identifier)
        assert resp.status_code == 201, resp.text
        return resp.json()["userId"]


# --- T014: successful login → AuthSession row persisted (mock) -------------
@pytest.mark.asyncio
async def test_mock_login_success_creates_session_and_sets_cookie(auth_client, auth_app):
    await _seed(auth_app)
    resp = await _post_login(auth_client, "demo@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"userId", "status"}
    assert body["status"] == "authenticated"
    # Cookie set.
    assert "fid_session" in auth_client.cookies
    # Session recorded in the mock session manager.
    sm = auth_app.state.session_manager
    now = datetime.now(tz=timezone.utc)
    sessions = [s for s in sm._sessions.values() if s.revoked_at is None]
    assert len(sessions) >= 1
    assert all(s.expires_at > now for s in sessions)


# --- T022: capture-quality 400 codes + no session --------------------------
@pytest.mark.asyncio
async def test_mock_login_no_face_400_no_session(auth_client, auth_app):
    await _seed(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="no_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_face"
    assert len(auth_app.state.session_manager._sessions) == 0


@pytest.mark.asyncio
async def test_mock_login_multiple_faces_400_no_session(auth_client, auth_app):
    await _seed(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="multi_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "multiple_faces"
    assert len(auth_app.state.session_manager._sessions) == 0


@pytest.mark.asyncio
async def test_mock_login_invalid_image_400_no_session(auth_client, auth_app):
    await _seed(auth_app)
    resp = await _post_login(auth_client, "demo@example.com", image_name="not_an_image.txt")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"
    assert len(auth_app.state.session_manager._sessions) == 0


@pytest.mark.asyncio
async def test_mock_login_auth_failed_no_session(auth_client, auth_app):
    await _seed(auth_app)
    resp = await _post_login(auth_client, "nonexistent@example.com")
    assert resp.status_code == 401
    assert len(auth_app.state.session_manager._sessions) == 0


# --- T027: protected endpoints with valid / absent / expired / revoked -----
@pytest.mark.asyncio
async def test_mock_protected_endpoints_reject_without_cookie(auth_client, auth_app):
    await _seed(auth_app)
    # /me
    r = await auth_client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"
    # analysis/mood
    files = {"image": ("t.jpg", fixture_bytes("one_face.jpg"), "image/jpeg")}
    r = await auth_client.post("/api/analysis/mood", files=files)
    assert r.status_code == 401
    # analysis/age
    r = await auth_client.post("/api/analysis/age", files=files)
    assert r.status_code == 401
    # delete face-data
    r = await auth_client.delete(f"/api/users/{uuid.uuid4()}/face-data")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mock_protected_endpoints_accept_with_valid_cookie(auth_client, auth_app):
    await _seed(auth_app)
    await _post_login(auth_client, "demo@example.com")
    r = await auth_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["authenticated"] is True
    files = {"image": ("t.jpg", fixture_bytes("one_face.jpg"), "image/jpeg")}
    r = await auth_client.post("/api/analysis/mood", files=files)
    assert r.status_code == 200
    r = await auth_client.post("/api/analysis/age", files=files)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_mock_expired_session_rejected(auth_client, auth_app):
    await _seed(auth_app)
    await _post_login(auth_client, "demo@example.com")
    # Expire all sessions in the mock manager.
    sm = auth_app.state.session_manager
    long_ago = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    for sid, session in list(sm._sessions.items()):
        from face_insight.domain.entities import AuthSession

        sm._sessions[sid] = AuthSession(
            id=session.id,
            user_id=session.user_id,
            created_at=long_ago,
            expires_at=long_ago + timedelta(minutes=1),
            revoked_at=None,
        )
    r = await auth_client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_mock_revoked_session_rejected(auth_client, auth_app):
    await _seed(auth_app)
    await _post_login(auth_client, "demo@example.com")
    # Revoke via logout.
    r = await auth_client.post("/api/auth/logout")
    assert r.status_code == 200
    # After logout, cookie cleared → me returns 401.
    r = await auth_client.get("/api/auth/me")
    assert r.status_code == 401


# --- T033: logout revokes session + protected reject afterward -------------
@pytest.mark.asyncio
async def test_mock_logout_revokes_session(auth_client, auth_app):
    await _seed(auth_app)
    await _post_login(auth_client, "demo@example.com")
    sm = auth_app.state.session_manager
    active_before = [s for s in sm._sessions.values() if s.revoked_at is None]
    assert len(active_before) >= 1
    r = await auth_client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    active_after = [s for s in sm._sessions.values() if s.revoked_at is None]
    assert len(active_after) == 0


@pytest.mark.asyncio
async def test_mock_logout_idempotent_no_cookie(auth_client):
    r = await auth_client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --- Concurrent sessions allowed (demo-first) ------------------------------
@pytest.mark.asyncio
async def test_mock_multiple_concurrent_sessions_allowed(auth_client, auth_app):
    await _seed(auth_app)
    r1 = await _post_login(auth_client, "demo@example.com")
    assert r1.status_code == 200
    # Second login without logout → new session, old still valid.
    # Clear cookie to simulate a fresh client but same server-side state.
    auth_client.cookies.clear()
    r2 = await _post_login(auth_client, "demo@example.com")
    assert r2.status_code == 200
    sm = auth_app.state.session_manager
    active = [s for s in sm._sessions.values() if s.revoked_at is None]
    assert len(active) >= 2  # multiple concurrent sessions allowed


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
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from face_insight.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    # Run alembic upgrade in an isolated thread: alembic/env.py calls
    # asyncio.run() at import time, which is forbidden inside the running
    # pytest-asyncio event loop. A fresh thread has no running loop.
    import threading

    from alembic import command
    from alembic.config import Config

    err_box: list[BaseException] = []

    def _run_upgrade() -> None:
        try:
            cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            cfg.set_main_option("sqlalchemy.url", settings.database_url)
            command.upgrade(cfg, "head")
        except BaseException as exc:  # noqa: BLE001
            err_box.append(exc)

    t = threading.Thread(target=_run_upgrade)
    t.start()
    t.join()
    if err_box:
        raise err_box[0]

    async with engine.begin() as conn:
        for tbl in ("auth_sessions", "face_templates", "users"):
            await conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE"))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    async with engine.begin() as conn:
        for tbl in ("auth_sessions", "face_templates", "users"):
            await conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def db_auth_app(db_session_factory, tmp_path: Path):
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        session_factory=db_session_factory,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def db_auth_client(db_auth_app) -> AsyncClient:
    async with await _client_for(db_auth_app) as ac:
        yield ac


# --- T014 (DB): login persists AuthSession row in PostgreSQL ---
@pytest.mark.asyncio
async def test_db_login_persists_auth_session(db_auth_client, db_auth_app, db_session_factory):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from face_insight.adapters.db.models import AuthSessionORM

    await _seed(db_auth_app)
    resp = await _post_login(db_auth_client, "demo@example.com")
    assert resp.status_code == 200
    user_id = resp.json()["userId"]

    async with db_session_factory() as session:  # type: AsyncSession
        rows = (await session.execute(select(AuthSessionORM))).scalars().all()
    assert len(rows) == 1
    assert str(rows[0].user_id) == user_id
    assert rows[0].revoked_at is None
    assert rows[0].expires_at > datetime.now(tz=timezone.utc)


# --- T033 (DB): logout revokes session in PostgreSQL ---
@pytest.mark.asyncio
async def test_db_logout_revokes_session(db_auth_client, db_auth_app, db_session_factory):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from face_insight.adapters.db.models import AuthSessionORM

    await _seed(db_auth_app)
    await _post_login(db_auth_client, "demo@example.com")
    r = await db_auth_client.post("/api/auth/logout")
    assert r.status_code == 200

    async with db_session_factory() as session:  # type: AsyncSession
        rows = (await session.execute(select(AuthSessionORM))).scalars().all()
    assert len(rows) == 1
    assert rows[0].revoked_at is not None


# --- T027 (DB): expired session rejected ---
@pytest.mark.asyncio
async def test_db_expired_session_rejected(db_auth_client, db_auth_app, db_session_factory):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    await _seed(db_auth_app)
    await _post_login(db_auth_client, "demo@example.com")
    # Expire the session in the DB.
    async with db_session_factory() as session:  # type: AsyncSession
        await session.execute(
            text("UPDATE auth_sessions SET expires_at = now() - interval '1 minute'")
        )
        await session.commit()
    r = await db_auth_client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


# --- T027 (DB): no AuthSession on failure paths ---
@pytest.mark.asyncio
async def test_db_no_session_on_auth_failure(db_auth_client, db_auth_app, db_session_factory):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from face_insight.adapters.db.models import AuthSessionORM

    await _seed(db_auth_app)
    resp = await _post_login(db_auth_client, "nonexistent@example.com")
    assert resp.status_code == 401
    async with db_session_factory() as session:  # type: AsyncSession
        rows = (await session.execute(select(AuthSessionORM))).scalars().all()
    assert len(rows) == 0
