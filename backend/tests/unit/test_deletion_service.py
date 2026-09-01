"""Domain unit tests for DeletionService (spec 006, T005/T013/T026).

No GPU, no network, no real models (FR-015, SC-010). Uses mock ports + the
injected ``MockUnitOfWork.delete_user_face_data`` callable (research R-2).
Covers:
  - T005: happy-path deletion ordering (FaceTemplate → AuthSession → User →
    commit), ImageStorage.delete called after the DB callable, result shape.
  - T013: authorization rule (session_user_id != user_id → Forbidden, no
    callable/FS invocation; condition order authz → existence → deletion).
  - T026: domain-purity static check (deletion.py imports only ports/entities/
    exceptions/stdlib).
"""

from __future__ import annotations

import ast
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from face_insight.adapters.mock import (
    MockFaceTemplateRepository,
    MockImageStorage,
    MockSessionManager,
    MockUnitOfWork,
    MockUserRepository,
)
from face_insight.domain.deletion import DeletionResult, DeletionService
from face_insight.domain.entities import (
    AuthSession,
    FaceTemplate,
    User,
    create_auth_session,
    create_face_template,
    create_user,
)
from face_insight.domain.exceptions import (
    DeletionInternalError,
    Forbidden,
    NotFound,
)


# --- Test doubles -----------------------------------------------------------
class FakeLogger:
    """Records structured log calls (no structlog import in the domain)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def info(self, event: str, **kwargs) -> None:
        self.calls.append((event, kwargs))

    def warning(self, event: str, **kwargs) -> None:
        self.calls.append((event, kwargs))


async def _seed(
    user_repo: MockUserRepository,
    template_repo: MockFaceTemplateRepository,
    session_manager: MockSessionManager,
    identifier: str = "demo@example.com",
) -> tuple[User, FaceTemplate, AuthSession]:
    now = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
    user = create_user(identifier, now=lambda: now)
    template = create_face_template(user.id, [0.1] * 8, "mock-v1", now=lambda: now)
    await user_repo.save(user)
    await template_repo.save(template)
    created = await session_manager.create(user.id, now, timedelta(seconds=3600))
    return user, template, created


@pytest.fixture
async def deletion_setup():
    user_repo = MockUserRepository()
    template_repo = MockFaceTemplateRepository()
    session_manager = MockSessionManager()
    image_storage = MockImageStorage()
    uow = MockUnitOfWork(user_repo, template_repo, session_manager)
    logger = FakeLogger()
    service = DeletionService(
        user_repository=user_repo,
        image_storage=image_storage,
        delete_user_face_data=uow.delete_user_face_data,
        logger=logger,
    )
    user, template, session = await _seed(user_repo, template_repo, session_manager)
    return {
        "service": service,
        "uow": uow,
        "user_repo": user_repo,
        "template_repo": template_repo,
        "session_manager": session_manager,
        "image_storage": image_storage,
        "logger": logger,
        "user": user,
        "template": template,
        "session": session,
    }


# ===========================================================================
# T005: Happy path — ordering, FS after DB, result shape
# ===========================================================================
@pytest.mark.asyncio
async def test_deletion_happy_path_ordering_and_result(deletion_setup):
    s = deletion_setup
    user: User = s["user"]

    result = await s["service"].delete_face_data(user.id, user.id)

    # Result shape (FR-006).
    assert isinstance(result, DeletionResult)
    assert result.user_id == user.id
    assert result.status == "deleted"

    # The DB callable was invoked (T005).
    assert s["uow"].called is True
    assert s["uow"].last_user_id == user.id

    # Deletion ordering: FaceTemplate → AuthSession → User (dependents first).
    assert s["uow"].deletion_order == ["face_template", "auth_session", "user"]

    # ImageStorage.delete was called AFTER the DB callable (best-effort, post-commit).
    # The user folder is gone (MockImageStorage.delete rmtree's the user dir).
    user_dir = s["image_storage"]._user_dir(user.id)
    assert not user_dir.exists()

    # DB state: User, FaceTemplate, and all AuthSessions for the user are gone.
    assert await s["user_repo"].get(user.id) is None
    assert await s["template_repo"].get_by_user(user.id) is None
    assert all(sess.user_id != user.id for sess in s["session_manager"]._sessions.values())

    # Structured success log emitted (FR-016, T028).
    events = [e for e, _ in s["logger"].calls]
    assert "deletion" in events


@pytest.mark.asyncio
async def test_deletion_fs_cleanup_failure_does_not_fail_endpoint(deletion_setup):
    """FR-005: ImageStorage.delete failure → 200 + warning log, not an exception."""
    s = deletion_setup
    user: User = s["user"]

    # Make ImageStorage.delete raise.
    def boom(_user_id):
        raise OSError("disk on fire")

    s["image_storage"].delete = boom  # type: ignore[assignment]

    result = await s["service"].delete_face_data(user.id, user.id)
    assert result.status == "deleted"
    # A structured FS-cleanup warning was logged (FR-016/SC-012).
    events = [e for e, _ in s["logger"].calls]
    assert "deletion_fs_cleanup_warning" in events


@pytest.mark.asyncio
async def test_deletion_db_failure_raises_internal_error_and_logs_failed(deletion_setup):
    """FR-004/FR-008: DB callable failure → DeletionInternalError + failed log."""
    s = deletion_setup
    user: User = s["user"]

    async def boom(_user_id):
        raise RuntimeError("db down")

    s["service"]._delete_user_face_data = boom

    with pytest.raises(DeletionInternalError):
        await s["service"].delete_face_data(user.id, user.id)
    events = [e for e, _ in s["logger"].calls]
    assert ("deletion",) and any(
        e == "deletion" and kw.get("status") == "failed" for e, kw in s["logger"].calls
    )


# ===========================================================================
# T013: Authorization rule — Forbidden, no callable/FS, condition order
# ===========================================================================
@pytest.mark.asyncio
async def test_deletion_mismatched_session_raises_forbidden(deletion_setup):
    s = deletion_setup
    user: User = s["user"]
    other = uuid.uuid4()

    with pytest.raises(Forbidden):
        await s["service"].delete_face_data(user.id, other)

    # No deletion callable invocation, no FS touch on mismatch (FR-002).
    assert s["uow"].called is False
    # The user's data is untouched.
    assert await s["user_repo"].get(user.id) is not None
    assert await s["template_repo"].get_by_user(user.id) is not None


@pytest.mark.asyncio
async def test_deletion_authz_evaluated_before_existence(deletion_setup):
    """Condition order (R-4): 403 forbidden is raised even when the User does not
    exist for the path userId (authz precedes the 404 lookup)."""
    s = deletion_setup
    user: User = s["user"]
    nonexistent = uuid.uuid4()

    # session belongs to `user`; path is `nonexistent` → forbidden (not 404).
    with pytest.raises(Forbidden):
        await s["service"].delete_face_data(nonexistent, user.id)
    assert s["uow"].called is False


@pytest.mark.asyncio
async def test_deletion_missing_user_raises_not_found(deletion_setup):
    """FR-007: valid matching session but User absent (out-of-band) → NotFound."""
    s = deletion_setup
    # A session whose user_id has no User row (simulate out-of-band user deletion
    # while the session row lingers — the existence guard catches it).
    orphan_id = uuid.uuid4()
    now = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
    await s["session_manager"].create(orphan_id, now, timedelta(seconds=3600))

    with pytest.raises(NotFound):
        await s["service"].delete_face_data(orphan_id, orphan_id)
    # No DB deletion occurred (the guard fired before the callable).
    assert s["uow"].called is False


# ===========================================================================
# T026: Domain-purity static check (FR-013/FR-014, SC-008/SC-009)
# ===========================================================================
DELETION_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "face_insight"
    / "domain"
    / "deletion.py"
)

ALLOWED_PREFIXES = ("face_insight.domain.",)
# stdlib modules are allowed; everything else is forbidden.
FORBIDDEN_PREFIXES = (
    "face_insight.adapters",
    "face_insight.api",
    "face_insight.logging",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "asyncpg",
    "fastapi",
    "itsdangerous",
    "structlog",
    "PIL",
    "numpy",
    "torch",
    "ultralytics",
    "cv2",
    "opencv",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def test_deletion_module_exists():
    assert DELETION_PATH.is_file(), f"missing domain module: {DELETION_PATH}"


def test_deletion_domain_purity():
    """T026: deletion.py imports only from .ports/.entities/.exceptions + stdlib
    — no SQLAlchemy, FastAPI, structlog, ML, or filesystem-adapter imports."""
    source = DELETION_PATH.read_text(encoding="utf-8")
    modules = _imported_modules(source)
    offenders = {m for m in modules if any(m.startswith(p) or m == p for p in FORBIDDEN_PREFIXES)}
    assert not offenders, f"deletion.py imports forbidden modules: {offenders}"
    # All face_insight.* imports must be from the domain package.
    fi_imports = {m for m in modules if m.startswith("face_insight")}
    non_domain = {m for m in fi_imports if not any(m.startswith(p) for p in ALLOWED_PREFIXES)}
    assert not non_domain, f"deletion.py imports non-domain face_insight modules: {non_domain}"
