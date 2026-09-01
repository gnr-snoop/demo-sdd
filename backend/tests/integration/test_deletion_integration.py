"""Integration tests for face-data deletion (spec 006, T006/T014/T016/T025).

Two layers:
  1. **Mock-only** (always runs, no DB): real DELETE endpoint + mock repos +
     real FilesystemImageStorage(tmp_path). Verifies the full HTTP flow: happy
     path (200, rows + folder gone, cookie cleared), 401/403/422/404 rejections,
     post-deletion invalidation (old cookie → 401, old identifier → auth_failed).
  2. **DB-required** (skips without PostgreSQL): real SQLAlchemy repos +
     SqlAlchemyUnitOfWork.delete_user_face_data + real PostgreSQL + real FS.
     Verifies the atomic hard-delete (User/FaceTemplate/AuthSession gone in one
     transaction), DB-failure rollback (500, no partial state), best-effort FS
     failure (200 + warning), and post-deletion invalidation.

No GPU, no network (mock detector/embedder only).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.adapters.mock import ScriptableMockDetector, ScriptableMockEmbedder
from face_insight.main import create_auth_app


def fixture_bytes(name: str) -> bytes:
    return (Path(__file__).resolve().parents[1] / "fixtures" / name).read_bytes()


def _onboard_data(identifier="demo@example.com"):
    payload = fixture_bytes("one_face.jpg")
    data = {"identifier": identifier, "consentAccepted": "true"}
    files = {"image": ("one_face.jpg", payload, "image/jpeg")}
    return data, files


def _login_data(identifier="demo@example.com"):
    payload = fixture_bytes("one_face.jpg")
    data = {"identifier": identifier}
    files = {"image": ("one_face.jpg", payload, "image/jpeg")}
    return data, files


async def _client_for(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _onboard_login(client, identifier="demo@example.com"):
    data, files = _onboard_data(identifier)
    onb = await client.post("/api/onboarding", data=data, files=files)
    assert onb.status_code == 201, onb.text
    user_id = onb.json()["userId"]
    ldata, lfiles = _login_data(identifier)
    login = await client.post("/api/auth/face-login", data=ldata, files=lfiles)
    assert login.status_code == 200, login.text
    return user_id


# ==========================================================================
# Layer 1: Mock-only (always runs)
# ==========================================================================
@pytest.fixture
async def mock_app(tmp_path: Path):
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        session_factory=None,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def mock_client(mock_app) -> AsyncClient:
    async with await _client_for(mock_app) as ac:
        yield ac


@pytest.mark.asyncio
async def test_mock_deletion_happy_path(mock_client, mock_app, tmp_path):
    """T006: 200 happy path — DB rows + folder gone, cookie cleared."""
    user_id = await _onboard_login(mock_client)
    user_dir = tmp_path / "usuarios" / user_id
    assert user_dir.exists()
    resp = await mock_client.delete(f"/api/users/{user_id}/face-data")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"userId": user_id, "status": "deleted"}
    # Cookie cleared.
    assert mock_client.cookies.get("fid_session") in (None, "", "null")
    # Rows gone.
    uid = uuid.UUID(user_id)
    assert await mock_app.state.user_repository.get(uid) is None
    assert await mock_app.state.face_template_repository.get_by_user(uid) is None
    assert not user_dir.exists()


@pytest.mark.asyncio
async def test_mock_deletion_401_no_cookie(mock_app):
    async with await _client_for(mock_app) as ac:
        r = await ac.delete(f"/api/users/{uuid.uuid4()}/face-data")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_mock_deletion_403_forbidden(mock_app):
    async with await _client_for(mock_app) as ac:
        user_a = await _onboard_login(ac, identifier="a@example.com")
        async with await _client_for(mock_app) as ac2:
            user_b = await _onboard_login(ac2, identifier="b@example.com")
        r = await ac.delete(f"/api/users/{user_b}/face-data")
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "forbidden"
        # No rows removed.
        assert await mock_app.state.user_repository.get(uuid.UUID(user_a)) is not None
        assert await mock_app.state.user_repository.get(uuid.UUID(user_b)) is not None


@pytest.mark.asyncio
async def test_mock_deletion_422_malformed_uuid(mock_client):
    await _onboard_login(mock_client)
    r = await mock_client.delete("/api/users/not-a-uuid/face-data")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_mock_deletion_404_not_found(mock_client, mock_app):
    """T014: out-of-band user deletion → 404 not_found."""
    user_id = await _onboard_login(mock_client)
    await mock_app.state.user_repository.delete(uuid.UUID(user_id))
    r = await mock_client.delete(f"/api/users/{user_id}/face-data")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_mock_deletion_post_deletion_invalidation(mock_client):
    """T016: after 200, old cookie → 401 unauthenticated, old identifier → auth_failed."""
    user_id = await _onboard_login(mock_client, identifier="demo@example.com")
    r = await mock_client.delete(f"/api/users/{user_id}/face-data")
    assert r.status_code == 200
    me = await mock_client.get("/api/auth/me")
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "unauthenticated"
    ldata, lfiles = _login_data("demo@example.com")
    login = await mock_client.post("/api/auth/face-login", data=ldata, files=lfiles)
    assert login.status_code == 401
    assert login.json()["error"]["code"] == "auth_failed"


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
async def db_app(db_session_factory, tmp_path: Path):
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        session_factory=db_session_factory,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def db_client(db_app) -> AsyncClient:
    async with await _client_for(db_app) as ac:
        yield ac


async def _count_rows(factory, orm) -> int:
    from sqlalchemy import select

    async with factory() as session:
        rows = (await session.execute(select(orm))).scalars().all()
    return len(rows)


@pytest.mark.asyncio
async def test_db_deletion_happy_path_removes_all_rows(db_client, db_app, db_session_factory, tmp_path):
    """T006 (DB): 200 → User/FaceTemplate/AuthSession rows gone, folder gone."""
    from face_insight.adapters.db.models import AuthSessionORM, FaceTemplateORM, UserORM

    user_id = await _onboard_login(db_client)
    user_dir = tmp_path / "usuarios" / user_id
    assert user_dir.exists()
    # Rows exist before deletion.
    assert await _count_rows(db_session_factory, UserORM) == 1
    assert await _count_rows(db_session_factory, FaceTemplateORM) == 1
    assert await _count_rows(db_session_factory, AuthSessionORM) == 1

    resp = await db_client.delete(f"/api/users/{user_id}/face-data")
    assert resp.status_code == 200
    assert resp.json() == {"userId": user_id, "status": "deleted"}

    # All rows gone (single transaction).
    assert await _count_rows(db_session_factory, UserORM) == 0
    assert await _count_rows(db_session_factory, FaceTemplateORM) == 0
    assert await _count_rows(db_session_factory, AuthSessionORM) == 0
    # Folder gone.
    assert not user_dir.exists()
    # Cookie cleared.
    assert db_client.cookies.get("fid_session") in (None, "", "null")


@pytest.mark.asyncio
async def test_db_deletion_403_no_rows_removed(db_client, db_app, db_session_factory):
    """T014 (DB): 403 forbidden removes no rows for either user."""
    from face_insight.adapters.db.models import UserORM

    user_a = await _onboard_login(db_client, identifier="a@example.com")
    async with await _client_for(db_app) as ac2:
        user_b = await _onboard_login(ac2, identifier="b@example.com")
    r = await db_client.delete(f"/api/users/{user_b}/face-data")
    assert r.status_code == 403
    assert await _count_rows(db_session_factory, UserORM) == 2


@pytest.mark.asyncio
async def test_db_deletion_post_deletion_invalidation(db_client, db_session_factory):
    """T016 (DB): after 200, old cookie → 401, old identifier login → auth_failed,
    no rows remain."""
    from face_insight.adapters.db.models import AuthSessionORM, FaceTemplateORM, UserORM

    user_id = await _onboard_login(db_client, identifier="demo@example.com")
    r = await db_client.delete(f"/api/users/{user_id}/face-data")
    assert r.status_code == 200
    # Old cookie invalid.
    me = await db_client.get("/api/auth/me")
    assert me.status_code == 401
    # Old-identifier login fails (no User/FaceTemplate).
    ldata, lfiles = _login_data("demo@example.com")
    login = await db_client.post("/api/auth/face-login", data=ldata, files=lfiles)
    assert login.status_code == 401
    assert login.json()["error"]["code"] == "auth_failed"
    # No rows.
    assert await _count_rows(db_session_factory, UserORM) == 0
    assert await _count_rows(db_session_factory, FaceTemplateORM) == 0
    assert await _count_rows(db_session_factory, AuthSessionORM) == 0


@pytest.mark.asyncio
async def test_db_deletion_db_failure_500_rollback(db_client, db_app, db_session_factory):
    """T025 (DB): DB transaction failure → 500 internal_error + rollback (no partial state)."""
    from face_insight.adapters.db.models import AuthSessionORM, FaceTemplateORM, UserORM

    user_id = await _onboard_login(db_client)

    async def boom(_user_id):
        raise RuntimeError("db down")

    db_app.state.deletion_service._delete_user_face_data = boom
    r = await db_client.delete(f"/api/users/{user_id}/face-data")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    # No partial DB state — all rows still present (rollback).
    assert await _count_rows(db_session_factory, UserORM) == 1
    assert await _count_rows(db_session_factory, FaceTemplateORM) == 1
    assert await _count_rows(db_session_factory, AuthSessionORM) == 1


@pytest.mark.asyncio
async def test_db_deletion_best_effort_fs_failure_200(db_client, db_app, db_session_factory):
    """T025 (DB): DB commits, FS deletion fails → 200 + warning; DB rows gone."""
    from face_insight.adapters.db.models import UserORM

    user_id = await _onboard_login(db_client)

    def boom(_user_id):
        raise OSError("disk on fire")

    db_app.state.image_storage.delete = boom  # type: ignore[assignment]
    r = await db_client.delete(f"/api/users/{user_id}/face-data")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    # DB rows gone (commit succeeded before FS attempt).
    assert await _count_rows(db_session_factory, UserORM) == 0
