"""FastAPI application entrypoint (Fase 1 skeleton).

Provides ``/health`` (liveness) and ``/readyz`` (readiness with DB connectivity
check, 503 if down). Route registration happens via :func:`register_routes`,
called at startup; US3 wires the seven contract endpoints there.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    # Dispose the production DB engine if one was wired (spec 007).
    engine = getattr(app.state, "db_engine", None)
    if engine is not None:
        await engine.dispose()
    if _engine is not None:
        await _engine.dispose()


def wire_production_adapters(app: FastAPI) -> None:
    """Wire real SQLAlchemy DB adapters + mock ML adapters for production mode
    (spec 007, FR-004/FR-006/FR-008; research R-3/R-4).

    Mirrors ``wire_mock_adapters``'s service-construction structure but:
      1. Builds the session factory via ``adapters.db.session.get_session_factory()``
         (async engine + ``async_sessionmaker`` from ``settings.database_url``).
      2. Instantiates the real ``SqlAlchemy*`` persistence adapters.
      3. Keeps the **mock ML adapters** (real ML is specs 008/009 — FR-004).
      4. Uses the real ``FilesystemImageStorage`` (Principle V).
      5. Rebuilds all services from the real persistence ports + mock ML.
      6. Runs a startup ``SELECT 1`` probe → ``RuntimeError`` on failure (FR-006).
      7. Stores the engine on ``app.state.db_engine`` for lifespan/health probe.
    """
    from .adapters.db.repositories import (  # noqa: PLC0415
        SqlAlchemyFaceTemplateRepository,
        SqlAlchemyUnitOfWork,
        SqlAlchemyUserRepository,
    )
    from .adapters.db.session import get_session_factory  # noqa: PLC0415
    from .adapters.db.session_manager import SqlAlchemySessionManager  # noqa: PLC0415
    from .adapters.fs.image_storage import FilesystemImageStorage  # noqa: PLC0415
    from .adapters.http.session_cookie import SessionCookieService  # noqa: PLC0415
    from .domain.age import AgeService  # noqa: PLC0415
    from .domain.comparison import CosineComparison  # noqa: PLC0415
    from .domain.deletion import DeletionService  # noqa: PLC0415
    from .domain.login import LoginService  # noqa: PLC0415
    from .domain.mood import MoodService  # noqa: PLC0415
    from .domain.onboarding import OnboardingService  # noqa: PLC0415
    from .logging import get_logger as _get_logger  # noqa: PLC0415

    settings = get_settings()

    # 1. Build the async session factory from DATABASE_URL.
    session_factory = get_session_factory()
    engine = session_factory.kw["bind"]  # the AsyncEngine bound to the factory

    # 2. Startup connectivity probe (FR-006, research R-4) — fail fast before
    #    serving traffic. Use a SEPARATE throwaway engine so the probe's
    #    connections (bound to a worker-thread event loop) do not contaminate
    #    the app engine's pool (which must live in the app's own event loop).
    import asyncio  # noqa: PLC0415
    import concurrent.futures  # noqa: PLC0415
    import os  # noqa: PLC0415

    async def _probe() -> bool:
        from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

        probe_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        try:
            async with probe_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001
            return False
        finally:
            await probe_engine.dispose()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        ready = pool.submit(lambda: asyncio.run(_probe())).result()

    logger.info("db_ready", status=bool(ready))  # FR-016, research R-8
    if not ready:
        raise RuntimeError(
            f"APP_MODE=production requires a reachable DATABASE_URL; got {settings.database_url!r}"
        )

    # 3. Real persistence adapters.
    user_repo = SqlAlchemyUserRepository(session_factory)
    template_repo = SqlAlchemyFaceTemplateRepository(session_factory)
    session_manager = SqlAlchemySessionManager(session_factory)
    unit_of_work = SqlAlchemyUnitOfWork(session_factory)

    # 4. Concrete ML adapters (spec 008 + spec 009, FR-011): YuNetDetector +
    #    SFaceEmbedder (spec 008) + EmotiEffMoodEstimator + MiVOLOAgeEstimator
    #    (spec 009) replace the mock ML adapters in production. After this, all
    #    four ML ports have concrete real adapters (Fase 5 complete, SC-018).
    from .adapters.ml import (  # noqa: PLC0415
        EmotiEffMoodEstimator,
        MiVOLOAgeEstimator,
        SFaceEmbedder,
        YuNetDetector,
    )

    detector = YuNetDetector()
    embedder = SFaceEmbedder()
    age_estimator = MiVOLOAgeEstimator()
    mood_estimator = EmotiEffMoodEstimator()

    # 4b. Production-mode verification_threshold override (spec 008, FR-016, R-7):
    #     default 0.363 (OpenCV LFW calibration) unless VERIFICATION_THRESHOLD
    #     is explicitly set in the environment. Mock-mode default stays 0.5.
    verification_threshold = settings.verification_threshold
    if "VERIFICATION_THRESHOLD" not in os.environ:
        from .adapters.ml.constants import PRODUCTION_VERIFICATION_THRESHOLD  # noqa: PLC0415

        verification_threshold = PRODUCTION_VERIFICATION_THRESHOLD
        logger.info(
            "verification_threshold_override",
            mode="production",
            value=verification_threshold,
            source="opencv_lfw_calibration",
        )

    # 5. Real filesystem image storage (Principle V).
    image_storage = FilesystemImageStorage()

    # 6. Attach to app.state.
    app.state.detector = detector
    app.state.embedder = embedder
    app.state.age_estimator = age_estimator
    app.state.mood_estimator = mood_estimator
    app.state.session_manager = session_manager
    app.state.user_repository = user_repo
    app.state.face_template_repository = template_repo
    app.state.image_storage = image_storage
    app.state.unit_of_work = unit_of_work
    app.state.db_engine = engine

    # 7. Rebuild services from the real persistence ports + mock ML.
    app.state.onboarding_service = OnboardingService(
        detector=detector,
        embedder=embedder,
        user_repository=user_repo,
        face_template_repository=template_repo,
        image_storage=image_storage,
        quality_threshold=settings.quality_threshold,
        embedding_model_version=settings.embedding_model_version,
    )

    app.state.comparison = CosineComparison()
    app.state.session_cookie_service = SessionCookieService(settings)
    app.state.login_service = LoginService(
        detector=detector,
        embedder=embedder,
        comparison=app.state.comparison,
        user_repository=user_repo,
        face_template_repository=template_repo,
        session_manager=session_manager,
        quality_threshold=settings.quality_threshold,
        verification_threshold=verification_threshold,
    )

    app.state.mood_service = MoodService(
        detector=detector,
        mood_estimator=mood_estimator,
        quality_threshold=settings.quality_threshold,
    )

    app.state.age_service = AgeService(
        detector=detector,
        age_estimator=age_estimator,
        quality_threshold=settings.quality_threshold,
        age_range_half_width_years=settings.age_range_half_width_years,
    )

    app.state.deletion_service = DeletionService(
        user_repository=user_repo,
        image_storage=image_storage,
        delete_user_face_data=unit_of_work.delete_user_face_data,
        logger=_get_logger("face_insight.deletion"),
    )


def select_wiring(app: FastAPI, app_mode: str) -> None:
    """Dispatch to the correct wiring function exactly once at composition
    time (spec 007, FR-002; research R-2).

    ``mock`` → ``wire_mock_adapters``; ``production`` → ``wire_production_adapters``.
    Called once from ``create_app()`` after ``register_routes(app)``.
    """
    logger.info("wiring_selected", app_mode=app_mode)  # FR-016, research R-8
    if app_mode == "mock":
        wire_mock_adapters(app)
    elif app_mode == "production":
        wire_production_adapters(app)
    else:
        # Defensive: Settings validation should have caught this already (FR-005).
        raise ValueError(
            f"APP_MODE must be 'production' or 'mock'; got '{app_mode}'"
        )


def wire_mock_adapters(app: FastAPI) -> None:
    """Wire the 8 deterministic mock adapters as the default port
    implementations (T052, FR-010). Attached to ``app.state`` so route handlers
    and later specs can resolve them without importing concrete adapters.

    Spec 002 (T015): also builds an ``OnboardingService`` from the mock ports
    and stores it on ``app.state.onboarding_service``. No DB unit-of-work is
    wired here (contract tests run without a DB); the service falls back to
    sequential in-memory repository saves.

    Spec 003 (T019): builds a ``LoginService`` from the mock ports +
    ``CosineComparison`` + ``SessionManager``, and a ``SessionCookieService``.
    """
    from .adapters.mock import (  # noqa: PLC0415
        MockAgeEstimator,
        MockDetector,
        MockEmbedder,
        MockFaceTemplateRepository,
        MockImageStorage,
        MockMoodEstimator,
        MockSessionManager,
        MockUnitOfWork,
        MockUserRepository,
    )
    from .adapters.http.session_cookie import SessionCookieService  # noqa: PLC0415
    from .domain.comparison import CosineComparison  # noqa: PLC0415
    from .domain.deletion import DeletionService  # noqa: PLC0415
    from .domain.login import LoginService  # noqa: PLC0415
    from .domain.mood import MoodService  # noqa: PLC0415
    from .domain.onboarding import OnboardingService  # noqa: PLC0415
    from .logging import get_logger as _get_logger  # noqa: PLC0415

    settings = get_settings()

    app.state.detector = MockDetector()
    app.state.embedder = MockEmbedder()
    app.state.age_estimator = MockAgeEstimator()
    app.state.mood_estimator = MockMoodEstimator()
    app.state.session_manager = MockSessionManager()
    app.state.user_repository = MockUserRepository()
    app.state.face_template_repository = MockFaceTemplateRepository()
    app.state.image_storage = MockImageStorage()
    # Mock mode requires no DB — explicitly unset (spec 007, FR-003/FR-012).
    app.state.db_engine = None

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

    # Spec 003 login wiring.
    app.state.comparison = CosineComparison()
    app.state.session_cookie_service = SessionCookieService(settings)
    app.state.login_service = LoginService(
        detector=app.state.detector,
        embedder=app.state.embedder,
        comparison=app.state.comparison,
        user_repository=app.state.user_repository,
        face_template_repository=app.state.face_template_repository,
        session_manager=app.state.session_manager,
        quality_threshold=settings.quality_threshold,
        verification_threshold=settings.verification_threshold,
    )

    # Spec 004 mood wiring (T014): MoodService from mock ports.
    app.state.mood_service = MoodService(
        detector=app.state.detector,
        mood_estimator=app.state.mood_estimator,
        quality_threshold=settings.quality_threshold,
    )

    # Spec 005 age wiring (T008b): AgeService from mock ports. Built from the
    # mock Detector + mock AgeEstimator + settings.age_range_half_width_years
    # (FR-004). Real age models are deferred to Fase 5 (FR-016).
    from .domain.age import AgeService  # noqa: PLC0415

    app.state.age_service = AgeService(
        detector=app.state.detector,
        age_estimator=app.state.age_estimator,
        quality_threshold=settings.quality_threshold,
        age_range_half_width_years=settings.age_range_half_width_years,
    )

    # Spec 006 deletion wiring (T010): DeletionService from the mock ports + a
    # mock unit-of-work callable (no DB in the all-mock wiring). The callable
    # deletes FaceTemplate → AuthSession → User in memory (research R-2).
    mock_uow = MockUnitOfWork(
        app.state.user_repository,
        app.state.face_template_repository,
        app.state.session_manager,
    )
    app.state.deletion_service = DeletionService(
        user_repository=app.state.user_repository,
        image_storage=app.state.image_storage,
        delete_user_face_data=mock_uow.delete_user_face_data,
        logger=_get_logger("face_insight.deletion"),
    )


def create_app() -> FastAPI:
    """Application factory."""
    from .api.dependencies import (  # noqa: PLC0415
        UnauthenticatedError,
        register_deletion_exception_handlers,
        unauthenticated_response,
    )

    app = FastAPI(title="Face Insight Demo", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app)
    # Spec 007 (T010, FR-002): dispatch to mock/production wiring once at
    # composition time via the selector, replacing the unconditional
    # ``wire_mock_adapters(app)`` call.
    select_wiring(app, get_settings().app_mode)

    @app.exception_handler(UnauthenticatedError)
    async def _unauthenticated_handler(_request, _exc):  # noqa: ANN001
        return unauthenticated_response()

    register_deletion_exception_handlers(app)

    @app.get("/health", tags=["infra"])
    async def health(request: Request) -> JSONResponse:
        """Liveness probe — mode-aware (spec 007, T015, FR-010, research R-6).

        mock → ``{"status":"healthy"}`` (no DB check); production →
        ``{"status":"healthy","db":true}`` with ``SELECT 1`` against
        ``app.state.db_engine``, 503 ``{"status":"unhealthy","db":false}`` on
        ping failure.
        """
        engine = getattr(request.app.state, "db_engine", None)
        if engine is None:
            return JSONResponse(status_code=200, content={"status": "healthy"})
        db_ok = await _ping_engine(engine)
        if db_ok:
            return JSONResponse(status_code=200, content={"status": "healthy", "db": True})
        return JSONResponse(status_code=503, content={"status": "unhealthy", "db": False})

    @app.get("/readyz", tags=["infra"])
    async def readyz(request: Request) -> JSONResponse:
        """Readiness probe — mode-aware (spec 007, T016, FR-010, research R-6).

        mock → ``{"status":"ready","db":null}``; production → ``SELECT 1`` ping
        with ``db: true|false`` and 503 on failure.
        """
        engine = getattr(request.app.state, "db_engine", None)
        if engine is None:
            return JSONResponse(status_code=200, content={"status": "ready", "db": None})
        db_ok = await _ping_engine(engine)
        if db_ok:
            return JSONResponse(status_code=200, content={"status": "ready", "db": True})
        return JSONResponse(status_code=503, content={"status": "unavailable", "db": False})

    return app


async def _ping_engine(engine: AsyncEngine) -> bool:
    """Run ``SELECT 1`` against ``engine``; return False on any failure."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — probe must not crash
        return False


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

    from .api.dependencies import (  # noqa: PLC0415
        UnauthenticatedError,
        register_deletion_exception_handlers,
        unauthenticated_response,
    )

    @app.exception_handler(UnauthenticatedError)
    async def _unauth_handler(_request, _exc):  # noqa: ANN001
        return unauthenticated_response()

    register_deletion_exception_handlers(app)

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

    # Spec 004 (T014): rebuild mood_service with the overridden detector.
    from .domain.mood import MoodService  # noqa: PLC0415

    app.state.mood_service = MoodService(
        detector=detector,
        mood_estimator=app.state.mood_estimator,
        quality_threshold=settings.quality_threshold if quality_threshold is None else quality_threshold,
    )

    # Spec 005 (T008b): rebuild age_service with the overridden detector.
    from .domain.age import AgeService  # noqa: PLC0415

    app.state.age_service = AgeService(
        detector=detector,
        age_estimator=app.state.age_estimator,
        quality_threshold=settings.quality_threshold if quality_threshold is None else quality_threshold,
        age_range_half_width_years=settings.age_range_half_width_years,
    )

    # Spec 006 deletion wiring (T010).
    from .domain.deletion import DeletionService  # noqa: PLC0415
    from .logging import get_logger as _get_logger  # noqa: PLC0415

    if session_factory is not None:
        deletion_callable = unit_of_work.delete_user_face_data
    else:
        from .adapters.mock import MockUnitOfWork  # noqa: PLC0415

        mock_uow = MockUnitOfWork(user_repo, template_repo, app.state.session_manager)
        deletion_callable = mock_uow.delete_user_face_data
    app.state.deletion_service = DeletionService(
        user_repository=user_repo,
        image_storage=image_storage,
        delete_user_face_data=deletion_callable,
        logger=_get_logger("face_insight.deletion"),
    )
    return app


def create_auth_app(
    detector: object,
    embedder: object,
    session_factory: object | None = None,
    image_storage: object | None = None,
    quality_threshold: float | None = None,
    verification_threshold: float | None = None,
    mood_estimator: object | None = None,
    age_estimator: object | None = None,
) -> FastAPI:
    """Application factory wired for login/session integration tests (spec 003).

    Uses the provided mock ``detector``/``embedder`` (no GPU/network), real
    SQLAlchemy async repositories + ``SqlAlchemySessionManager`` (when
    ``session_factory`` is given), and a real ``SessionCookieService``. Onboarding
    is also wired so tests can seed a User + FaceTemplate via POST /api/onboarding.

    Spec 005 (T008b): ``age_estimator`` optionally overrides the mock age
    estimator (mirrors ``mood_estimator``) for age integration/contract tests.
    """
    from .adapters.db.repositories import (  # noqa: PLC0415
        SqlAlchemyFaceTemplateRepository,
        SqlAlchemyUnitOfWork,
        SqlAlchemyUserRepository,
    )
    from .adapters.db.session_manager import SqlAlchemySessionManager  # noqa: PLC0415
    from .adapters.fs.image_storage import FilesystemImageStorage  # noqa: PLC0415
    from .adapters.http.session_cookie import SessionCookieService  # noqa: PLC0415
    from .domain.comparison import CosineComparison  # noqa: PLC0415
    from .domain.login import LoginService  # noqa: PLC0415
    from .domain.mood import MoodService  # noqa: PLC0415
    from .domain.onboarding import OnboardingService  # noqa: PLC0415

    settings = get_settings()
    app = FastAPI(title="Face Insight Demo (auth test)", version="0.1.0", lifespan=lifespan)
    register_routes(app)
    wire_mock_adapters(app)

    from .api.dependencies import (  # noqa: PLC0415
        UnauthenticatedError,
        register_deletion_exception_handlers,
        unauthenticated_response,
    )

    @app.exception_handler(UnauthenticatedError)
    async def _unauth_handler(_request, _exc):  # noqa: ANN001
        return unauthenticated_response()

    register_deletion_exception_handlers(app)

    # Override detector/embedder with the provided (scriptable) test doubles.
    app.state.detector = detector
    app.state.embedder = embedder
    if image_storage is None:
        image_storage = FilesystemImageStorage()
    app.state.image_storage = image_storage

    if session_factory is not None:
        user_repo = SqlAlchemyUserRepository(session_factory)
        template_repo = SqlAlchemyFaceTemplateRepository(session_factory)
        unit_of_work = SqlAlchemyUnitOfWork(session_factory)
        session_manager = SqlAlchemySessionManager(session_factory)
    else:
        # Fall back to the in-memory mock repos + mock session manager (no DB).
        user_repo = app.state.user_repository
        template_repo = app.state.face_template_repository
        unit_of_work = None
        session_manager = app.state.session_manager

    app.state.session_manager = session_manager

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

    # Login wiring (spec 003).
    app.state.comparison = CosineComparison()
    app.state.session_cookie_service = SessionCookieService(settings)
    app.state.login_service = LoginService(
        detector=detector,
        embedder=embedder,
        comparison=app.state.comparison,
        user_repository=user_repo,
        face_template_repository=template_repo,
        session_manager=session_manager,
        quality_threshold=settings.quality_threshold if quality_threshold is None else quality_threshold,
        verification_threshold=settings.verification_threshold if verification_threshold is None else verification_threshold,
    )

    # Spec 004 mood wiring (T014): override the mood estimator if provided, then
    # rebuild MoodService with the (overridden) detector + mood estimator.
    if mood_estimator is not None:
        app.state.mood_estimator = mood_estimator
    app.state.mood_service = MoodService(
        detector=detector,
        mood_estimator=app.state.mood_estimator,
        quality_threshold=settings.quality_threshold if quality_threshold is None else quality_threshold,
    )

    # Spec 005 age wiring (T008b): rebuild AgeService with the (overridden)
    # detector + an optional age_estimator override. The age_estimator defaults
    # to the mock wired by wire_mock_adapters; tests pass a scriptable variant
    # via `age_estimator` (mirrors the mood_estimator override above).
    if age_estimator is not None:
        app.state.age_estimator = age_estimator
    from .domain.age import AgeService  # noqa: PLC0415

    app.state.age_service = AgeService(
        detector=detector,
        age_estimator=app.state.age_estimator,
        quality_threshold=settings.quality_threshold if quality_threshold is None else quality_threshold,
        age_range_half_width_years=settings.age_range_half_width_years,
    )

    # Spec 006 deletion wiring (T010): DeletionService + the
    # SqlAlchemyUnitOfWork.delete_user_face_data callable (real DB transaction
    # when session_factory is given; mock unit-of-work otherwise). Research R-2.
    from .domain.deletion import DeletionService  # noqa: PLC0415
    from .logging import get_logger as _get_logger  # noqa: PLC0415

    if session_factory is not None:
        deletion_callable = unit_of_work.delete_user_face_data
    else:
        from .adapters.mock import MockUnitOfWork  # noqa: PLC0415

        mock_uow = MockUnitOfWork(user_repo, template_repo, session_manager)
        deletion_callable = mock_uow.delete_user_face_data
    app.state.deletion_service = DeletionService(
        user_repository=user_repo,
        image_storage=image_storage,
        delete_user_face_data=deletion_callable,
        logger=_get_logger("face_insight.deletion"),
    )
    return app


app = create_app()
