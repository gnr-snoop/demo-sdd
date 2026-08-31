"""Persistence integration tests (T058, US5).

- Migrations create the 4 entity tables (idempotent re-apply) — requires a live
  PostgreSQL; skipped if DB unavailable.
- Filesystem image-storage adapter write/read round-trip at
  ``usuarios/<user-id>/pictures.jpg`` (SC-007) — no DB needed.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from face_insight.adapters.fs.image_storage import FilesystemImageStorage


# --- FS adapter round-trip (always runs) -----------------------------------
def test_filesystem_image_storage_roundtrip(tmp_path: Path) -> None:
    user_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    storage = FilesystemImageStorage(root=tmp_path)
    payload = b"\xff\xd8\xff\xe0JPEGMOCK"  # JPEG-ish sentinel bytes

    relative_path = storage.store(user_id, payload)
    assert relative_path == f"usuarios/{user_id}/pictures.jpg"

    absolute = tmp_path / relative_path
    assert absolute.exists()
    assert absolute.read_bytes() == payload

    read_back = storage.read(user_id)
    assert read_back == payload

    storage.delete(user_id)
    assert not absolute.exists()


# --- Migrations (require a live DB) ----------------------------------------
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
        pytest.skip("PostgreSQL not available — migration test skipped")
    yield


@pytest.mark.asyncio
async def test_migrations_create_four_tables(require_db) -> None:
    """Apply migrations and confirm the 4 entity tables exist (SC-006)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine

    from face_insight.config import get_settings

    engine = create_async_engine(get_settings().database_url)

    # Apply migrations via Alembic programmatically.
    from alembic.config import Config
    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    expected = {"users", "face_templates", "auth_sessions", "analysis_requests"}
    assert expected.issubset(set(tables)), f"missing tables: {expected - set(tables)}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_migrations_idempotent(require_db) -> None:
    """Re-applying migrations is a no-op (SC-006)."""
    from alembic import command
    from alembic.config import Config

    from face_insight.config import get_settings

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")  # first apply
    command.upgrade(cfg, "head")  # idempotent re-apply — must not raise
