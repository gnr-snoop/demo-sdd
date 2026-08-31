"""FastAPI application entrypoint (Fase 1 skeleton).

Provides ``/health`` (liveness) and ``/readyz`` (readiness with DB connectivity
check, 503 if down). Route registration happens via :func:`register_routes`,
called at startup; US3 wires the seven contract endpoints there.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import get_settings
from .logging import configure_logging, get_logger

configure_logging()
logger = get_logger("face_insight.main")

# Lazy global async engine for the readiness probe (and later repositories).
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return a lazily-created async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


async def db_is_ready() -> bool:
    """Return True if the database accepts a connection."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — readiness probe must not crash
        return False


def register_routes(app: FastAPI) -> None:
    """Register all API routers (wired in US3, T038)."""
    from .api.routes import analysis, auth, onboarding, users  # noqa: PLC0415

    app.include_router(onboarding.router)
    app.include_router(auth.router)
    app.include_router(analysis.router)
    app.include_router(users.router)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("startup")
    yield
    logger.info("shutdown")
    if _engine is not None:
        await _engine.dispose()


def wire_mock_adapters(app: FastAPI) -> None:
    """Wire the 8 deterministic mock adapters as the default port
    implementations (T052, FR-010). Attached to ``app.state`` so route handlers
    and later specs can resolve them without importing concrete adapters."""
    from .adapters.mock import (  # noqa: PLC0415
        MockAgeEstimator,
        MockDetector,
        MockEmbedder,
        MockFaceTemplateRepository,
        MockImageStorage,
        MockMoodEstimator,
        MockSessionManager,
        MockUserRepository,
    )

    app.state.detector = MockDetector()
    app.state.embedder = MockEmbedder()
    app.state.age_estimator = MockAgeEstimator()
    app.state.mood_estimator = MockMoodEstimator()
    app.state.session_manager = MockSessionManager()
    app.state.user_repository = MockUserRepository()
    app.state.face_template_repository = MockFaceTemplateRepository()
    app.state.image_storage = MockImageStorage()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(title="Face Insight Demo", version="0.1.0", lifespan=lifespan)
    register_routes(app)
    wire_mock_adapters(app)

    @app.get("/health", tags=["infra"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "healthy"}

    @app.get("/readyz", tags=["infra"])
    async def readyz(response: Response) -> dict[str, object]:
        """Readiness probe — checks DB connectivity (503 if down)."""
        ready = await db_is_ready()
        if not ready:
            response.status_code = 503
        return {"status": "ready" if ready else "unavailable", "db": ready}

    return app


app = create_app()
