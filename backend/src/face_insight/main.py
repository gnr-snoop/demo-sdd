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
    and later specs can resolve them without importing concrete adapters.

    Spec 002 (T015): also builds an ``OnboardingService`` from the mock ports
    and stores it on ``app.state.onboarding_service``. No DB unit-of-work is
    wired here (contract tests run without a DB); the service falls back to
    sequential in-memory repository saves.
    """
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
    from .domain.onboarding import OnboardingService  # noqa: PLC0415

    settings = get_settings()

    app.state.detector = MockDetector()
    app.state.embedder = MockEmbedder()
    app.state.age_estimator = MockAgeEstimator()
    app.state.mood_estimator = MockMoodEstimator()
    app.state.session_manager = MockSessionManager()
    app.state.user_repository = MockUserRepository()
    app.state.face_template_repository = MockFaceTemplateRepository()
    app.state.image_storage = MockImageStorage()

    app.state.onboarding_service = OnboardingService(
        detector=app.state.detector,
        embedder=app.state.embedder,
        user_repository=app.state.user_repository,
        face_template_repository=app.state.face_template_repository,
        image_storage=app.state.image_storage,
        quality_threshold=settings.quality_threshold,
        embedding_model_version=settings.embedding_model_version,
    )
    # No atomic DB unit-of-work for the all-mock wiring.
    app.state.unit_of_work = None


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


def create_onboarding_app(
    detector: object,
    embedder: object,
    session_factory: object | None = None,
    image_storage: object | None = None,
    quality_threshold: float | None = None,
) -> FastAPI:
    """Application factory wired for onboarding integration tests (T012).

    Uses the provided mock ``detector``/``embedder`` (no GPU/network), real
    SQLAlchemy async repositories + atomic unit-of-work (when ``session_factory``
    is given), and a real ``FilesystemImageStorage`` (or the provided one).
    Other routes keep their mock wiring.
    """
    from .adapters.db.repositories import (  # noqa: PLC0415
        SqlAlchemyFaceTemplateRepository,
        SqlAlchemyUnitOfWork,
        SqlAlchemyUserRepository,
    )
    from .adapters.fs.image_storage import FilesystemImageStorage  # noqa: PLC0415
    from .domain.onboarding import OnboardingService  # noqa: PLC0415

    settings = get_settings()
    app = FastAPI(title="Face Insight Demo (onboarding test)", version="0.1.0", lifespan=lifespan)
    register_routes(app)
    wire_mock_adapters(app)

    # Override onboarding-relevant ports with real/test doubles.
    app.state.detector = detector
    app.state.embedder = embedder
    if image_storage is None:
        image_storage = FilesystemImageStorage()
    app.state.image_storage = image_storage

    if session_factory is not None:
        user_repo = SqlAlchemyUserRepository(session_factory)
        template_repo = SqlAlchemyFaceTemplateRepository(session_factory)
        unit_of_work = SqlAlchemyUnitOfWork(session_factory)
    else:
        # Fall back to the in-memory mock repos (no DB); no unit-of-work.
        user_repo = app.state.user_repository
        template_repo = app.state.face_template_repository
        unit_of_work = None

    app.state.onboarding_service = OnboardingService(
        detector=detector,
        embedder=embedder,
        user_repository=user_repo,
        face_template_repository=template_repo,
        image_storage=image_storage,
        quality_threshold=settings.quality_threshold if quality_threshold is None else quality_threshold,
        embedding_model_version=settings.embedding_model_version,
    )
    app.state.unit_of_work = unit_of_work
    return app


app = create_app()
