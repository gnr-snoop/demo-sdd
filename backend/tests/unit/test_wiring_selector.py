"""Unit tests for the wiring selector + APP_MODE validation (spec 007).

No GPU, no network, no real PostgreSQL for the mock/invalid cases. The
production-reachable case uses a real PostgreSQL test container (skippable).

Covers:
- C-SEL-1: mock wires Mock* repos + no db_engine (FR-003).
- C-SEL-2: production + reachable DB wires SqlAlchemy* repos + mock ML + db_engine (FR-004).
- C-SEL-3: select_wiring called exactly once (FR-002).
- C-SEL-4: invalid APP_MODE raises ValueError at Settings construction (FR-005).
- C-START-1: production constructs DB session factory + sets db_engine (FR-006).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _reset_db_session_singletons():
    """Reset module-level DB session caches between tests so env changes take."""
    import face_insight.adapters.db.session as session_mod

    session_mod._engine = None
    session_mod._session_factory = None
    yield
    session_mod._engine = None
    session_mod._session_factory = None


# ===========================================================================
# C-SEL-1: mock mode wires Mock* repos + no db_engine (FR-003)
# ===========================================================================
def test_mock_mode_wires_mock_repos_and_no_engine(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.adapters.mock import (
        MockAgeEstimator,
        MockDetector,
        MockEmbedder,
        MockFaceTemplateRepository,
        MockImageStorage,
        MockMoodEstimator,
        MockSessionManager,
        MockUserRepository,
    )
    from face_insight.main import create_app

    app = create_app()
    assert isinstance(app.state.user_repository, MockUserRepository)
    assert isinstance(app.state.face_template_repository, MockFaceTemplateRepository)
    assert isinstance(app.state.session_manager, MockSessionManager)
    assert isinstance(app.state.image_storage, MockImageStorage)
    assert isinstance(app.state.detector, MockDetector)
    assert isinstance(app.state.embedder, MockEmbedder)
    assert isinstance(app.state.age_estimator, MockAgeEstimator)
    assert isinstance(app.state.mood_estimator, MockMoodEstimator)
    # No DB engine in mock mode (FR-003).
    assert getattr(app.state, "db_engine", None) is None


# ===========================================================================
# C-SEL-3: select_wiring called exactly once (FR-002)
# ===========================================================================
def test_select_wiring_called_once(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    import face_insight.main as main_mod

    calls: list[str] = []
    original = main_mod.select_wiring

    def _spy(app, app_mode):
        calls.append(app_mode)
        original(app, app_mode)

    monkeypatch.setattr(main_mod, "select_wiring", _spy)
    main_mod.create_app()
    assert calls == ["mock"], f"select_wiring should be called once; got {calls}"


def test_select_wiring_dispatch_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from fastapi import FastAPI

    from face_insight.adapters.mock import MockUserRepository
    from face_insight.main import select_wiring

    app = FastAPI()
    select_wiring(app, "mock")
    assert isinstance(app.state.user_repository, MockUserRepository)
    assert getattr(app.state, "db_engine", None) is None


# ===========================================================================
# C-SEL-4: invalid APP_MODE raises ValueError at Settings construction (FR-005)
# ===========================================================================
@pytest.mark.parametrize("bad", ["staging", "prod", "", "MOCKS", "demo"])
def test_invalid_app_mode_raises(bad):
    from face_insight.config import Settings

    with pytest.raises(Exception):  # pydantic raises ValidationError wrapping ValueError
        Settings(app_mode=bad)


def test_invalid_app_mode_error_message():
    from face_insight.config import Settings

    with pytest.raises(Exception) as exc_info:
        Settings(app_mode="staging")
    assert "APP_MODE must be 'production' or 'mock'" in str(exc_info.value)


def test_app_mode_normalization(tmp_path, monkeypatch):
    """APP_MODE is normalized via .strip().lower() (R-1)."""
    monkeypatch.setenv("APP_MODE", "  Production  ")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.config import get_settings

    assert get_settings().app_mode == "production"


# ===========================================================================
# C-START-1 (mock): no engine in mock mode (FR-006)
# ===========================================================================
def test_no_engine_in_mock_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.main import create_app

    app = create_app()
    assert getattr(app.state, "db_engine", None) is None


# ===========================================================================
# C-START-1 (production): session factory + db_engine set (FR-006)
# C-SEL-2: production wires SqlAlchemy* repos + mock ML + db_engine (FR-004)
# ===========================================================================
def test_production_wiring_with_reachable_db(tmp_path, monkeypatch):
    """Production mode with a reachable PostgreSQL wires SqlAlchemy* repos +
    mock ML + sets db_engine. Skipped if Docker/testcontainer unavailable."""
    import shutil
    import subprocess

    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker unavailable — production wiring test skipped")
    try:
        subprocess.run([docker, "info"], check=False, capture_output=True, timeout=15)
    except Exception:  # noqa: BLE001
        pytest.skip("Docker unavailable — production wiring test skipped")

    from testcontainers.postgres import PostgresContainer

    pg = PostgresContainer(
        "postgres:16-alpine",
        username="faceinsight",
        password="faceinsight",
        dbname="faceinsight",
    )
    try:
        pg.start()
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        url = f"postgresql+asyncpg://faceinsight:faceinsight@{host}:{port}/faceinsight"
    except Exception as exc:  # noqa: BLE001
        try:
            pg.stop()
        except Exception:  # noqa: BLE001
            pass
        pytest.skip(f"Could not start PostgreSQL test container: {exc}")

    # Create the schema so the probe can connect to a real DB. Uses
    # Base.metadata.create_all (equivalent to alembic upgrade head for the
    # test schema) via a worker thread with its own event loop.
    import asyncio
    import concurrent.futures

    def _run():
        from sqlalchemy.ext.asyncio import create_async_engine

        from face_insight.adapters.db.base import Base
        from face_insight.adapters.db import models  # noqa: F401

        async def _create():
            engine = create_async_engine(url, pool_pre_ping=True)
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            finally:
                await engine.dispose()

        asyncio.run(_create())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_run).result()

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    monkeypatch.setenv("MODELS_DIR", str(tmp_path / "models"))

    try:
        from sqlalchemy.ext.asyncio import AsyncEngine

        from face_insight.adapters.db.repositories import (
            SqlAlchemyFaceTemplateRepository,
            SqlAlchemyUnitOfWork,
            SqlAlchemyUserRepository,
        )
        from face_insight.adapters.db.session_manager import SqlAlchemySessionManager
        from face_insight.adapters.fs.image_storage import FilesystemImageStorage
        from face_insight.adapters.ml import SFaceEmbedder, YuNetDetector
        from face_insight.main import create_app

        try:
            app = create_app()
        except Exception as exc:
            if (
                "ModelUnavailable" in type(exc).__name__
                or "ModelCorrupt" in type(exc).__name__
                or isinstance(exc, (ImportError, ModuleNotFoundError))
            ):
                pytest.skip(
                    f"ML models/runtimes unavailable — production wiring test skipped: {exc}"
                )
            raise
        # SqlAlchemy* persistence repos.
        assert isinstance(app.state.user_repository, SqlAlchemyUserRepository)
        assert isinstance(app.state.face_template_repository, SqlAlchemyFaceTemplateRepository)
        assert isinstance(app.state.session_manager, SqlAlchemySessionManager)
        assert isinstance(app.state.unit_of_work, SqlAlchemyUnitOfWork)
        # Spec 008 (FR-011): concrete detector/embedder wired in production.
        assert isinstance(app.state.detector, YuNetDetector)
        assert isinstance(app.state.embedder, SFaceEmbedder)
        # Spec 009 (FR-010, SC-018): concrete mood/age adapters wired in
        # production — EmotiEffMoodEstimator + MiVOLOAgeEstimator. All four ML
        # ports now have concrete real adapters (Fase 5 complete).
        from face_insight.adapters.ml import EmotiEffMoodEstimator, MiVOLOAgeEstimator

        assert isinstance(app.state.mood_estimator, EmotiEffMoodEstimator)
        assert isinstance(app.state.age_estimator, MiVOLOAgeEstimator)
        # Real FS image storage.
        assert isinstance(app.state.image_storage, FilesystemImageStorage)
        # db_engine set (C-START-1).
        assert isinstance(app.state.db_engine, AsyncEngine)
    finally:
        pg.stop()


# ===========================================================================
# C-START-2/3: production with unreachable/malformed DATABASE_URL fails fast
# ===========================================================================
def test_production_unreachable_db_fails_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/nope_db_xyz")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.main import create_app

    with pytest.raises(RuntimeError, match="reachable DATABASE_URL"):
        create_app()


def test_production_malformed_url_fails_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")
    # Sync-only scheme (no +asyncpg driver) → engine creation/probe failure.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.main import create_app

    with pytest.raises((RuntimeError, Exception)):
        create_app()


def test_production_empty_url_fails_fast_at_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.config import Settings

    # The model_validator catches empty DATABASE_URL at settings construction.
    with pytest.raises(Exception, match="reachable DATABASE_URL"):
        Settings()


# ===========================================================================
# Spec 009 (T022/T033): mock-mode backward compatibility — mock mood/age
# estimators wired, no adapters.ml mood/age modules imported (FR-011/FR-018).
# ===========================================================================
def test_mock_mode_wires_mock_mood_and_age(tmp_path, monkeypatch):
    """T022/SC-011: APP_MODE=mock wires MockMoodEstimator/MockAgeEstimator and
    requires no models (FR-011)."""
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    from face_insight.adapters.mock import MockAgeEstimator, MockMoodEstimator
    from face_insight.main import create_app

    app = create_app()
    assert isinstance(app.state.mood_estimator, MockMoodEstimator)
    assert isinstance(app.state.age_estimator, MockAgeEstimator)


def test_mock_mode_imports_no_ml_mood_age_modules(tmp_path, monkeypatch):
    """T033/SC-015: APP_MODE=mock imports no ``adapters.ml.emotieff_mood`` /
    ``adapters.ml.mivolo_age`` modules (FR-011/FR-018 — the heavy runtimes are
    isolated to the concrete adapters, never loaded in mock mode)."""
    import sys

    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setenv("USUARIOS_ROOT", str(tmp_path))
    # Ensure not already imported.
    sys.modules.pop("face_insight.adapters.ml.emotieff_mood", None)
    sys.modules.pop("face_insight.adapters.ml.mivolo_age", None)
    from face_insight.main import create_app

    create_app()
    assert "face_insight.adapters.ml.emotieff_mood" not in sys.modules
    assert "face_insight.adapters.ml.mivolo_age" not in sys.modules


def test_mood_confidence_threshold_config_default_and_clamp():
    """T002/FR-006: mood_confidence_threshold defaults to 0.5 and clamps to [0,1]."""
    from face_insight.config import Settings

    assert Settings().mood_confidence_threshold == 0.5
    assert Settings(mood_confidence_threshold=-0.1).mood_confidence_threshold == 0.0
    assert Settings(mood_confidence_threshold=1.5).mood_confidence_threshold == 1.0
    assert Settings(mood_confidence_threshold=0.7).mood_confidence_threshold == 0.7
