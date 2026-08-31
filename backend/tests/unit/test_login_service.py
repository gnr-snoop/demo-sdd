"""Unit tests for LoginService (T015/T021, spec 003 US1/US2).

Port-only mocks (no FastAPI, no DB, no ML). Covers:
  - Happy path: accepted comparison → LoginResult with session id (T015)
  - Non-revealing error mapping: nonexistent-identifier and below-threshold both
    raise the single AuthFailed with the identical message (T021, FR-008/SC-003)
  - Capture-quality exceptions (NoFace/MultipleFaces/InsufficientQuality/InvalidImage)
  - Internal errors (embedder failure, comparison dimension mismatch) → LoginInternalError
  - No AuthSession created on any failure path (FR-004/SC-004)
  - Evaluation order: detection before lookup (R-5)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from face_insight.domain.entities import AuthSession, FaceTemplate, User, UserStatus, create_face_template, create_user
from face_insight.domain.exceptions import (
    AUTH_FAILED_MESSAGE,
    AuthFailed,
    InsufficientQuality,
    InvalidImage,
    LoginInternalError,
    MultipleFaces,
    NoFace,
)
from face_insight.domain.login import LoginService
from face_insight.domain.result_types import BoundingBox, DetectionResult, Embedding
from face_insight.domain.comparison import CosineComparison


NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
LIFETIME = timedelta(seconds=1800)
EMBEDDING_DIM = 128


# --- Port test doubles -----------------------------------------------------
class StubDetector:
    def __init__(self, result: DetectionResult):
        self._result = result

    def detect(self, image: bytes) -> DetectionResult:
        return self._result


class StubEmbedder:
    def __init__(self, vector: list[float], fail: bool = False):
        self._vector = vector
        self._fail = fail

    def embed(self, face_image: bytes) -> Embedding:
        if self._fail:
            raise RuntimeError("embedder boom")
        return Embedding(vector=self._vector, model_version="mock-embedder-v1")


class StubUserRepository:
    def __init__(self, user: Optional[User] = None):
        self._user = user

    async def get(self, user_id: object) -> Optional[User]:
        return self._user

    async def get_by_identifier(self, identifier: str) -> Optional[User]:
        if self._user is None:
            return None
        return self._user if self._user.identifier == identifier else None

    async def save(self, user: User) -> User:
        return user

    async def delete(self, user_id: object) -> None:
        pass


class StubFaceTemplateRepository:
    def __init__(self, template: Optional[FaceTemplate] = None):
        self._template = template

    async def get_by_user(self, user_id: object) -> Optional[FaceTemplate]:
        return self._template

    async def save(self, template: FaceTemplate) -> FaceTemplate:
        return template

    async def delete_by_user(self, user_id: object) -> None:
        pass


class RecordingSessionManager:
    """Records created sessions; lets tests assert no-session-on-failure (FR-004)."""

    def __init__(self):
        self.created: list[uuid.UUID] = []
        self.revoked: list[uuid.UUID] = []

    async def create(self, user_id: uuid.UUID, now: datetime, lifetime: timedelta) -> AuthSession:
        from face_insight.domain.entities import create_session

        session = create_session(user_id, now, lifetime)
        self.created.append(session.id)
        return session

    async def get_valid(self, session_id: uuid.UUID, now: datetime) -> Optional[AuthSession]:
        return None

    async def revoke(self, session_id: uuid.UUID, now: datetime) -> None:
        self.revoked.append(session_id)


def _one_face() -> DetectionResult:
    return DetectionResult(face_count=1, boxes=[BoundingBox(0, 0, 100, 100)], score=0.99)


def _matching_vector() -> list[float]:
    return [0.1] * EMBEDDING_DIM


def _seeded_user_and_template():
    user = create_user("demo@example.com", now=lambda: NOW, user_id=uuid.uuid4())
    template = create_face_template(user.id, _matching_vector(), "mock-embedder-v1", now=lambda: NOW)
    return user, template


def _build_service(
    *,
    detector_result=None,
    embed_vector=None,
    embed_fail=False,
    user=None,
    template=None,
    verification_threshold=0.5,
):
    user = user
    template = template
    detector = StubDetector(detector_result if detector_result is not None else _one_face())
    embedder = StubEmbedder(embed_vector if embed_vector is not None else _matching_vector(), fail=embed_fail)
    users = StubUserRepository(user)
    templates = StubFaceTemplateRepository(template)
    sessions = RecordingSessionManager()
    service = LoginService(
        detector=detector,
        embedder=embedder,
        comparison=CosineComparison(),
        user_repository=users,
        face_template_repository=templates,
        session_manager=sessions,
        quality_threshold=0.5,
        verification_threshold=verification_threshold,
    )
    return service, sessions


# ==========================================================================
# T015: Happy path
# ==========================================================================
@pytest.mark.asyncio
async def test_login_happy_path_returns_user_id_and_session():
    user, template = _seeded_user_and_template()
    service, sessions = _build_service(user=user, template=template)
    result = await service.login("demo@example.com", b"jpeg-bytes", NOW, LIFETIME)
    assert result.user_id == user.id
    assert result.status == "authenticated"
    assert isinstance(result.session_id, uuid.UUID)
    assert len(sessions.created) == 1


@pytest.mark.asyncio
async def test_login_happy_path_case_insensitive_identifier():
    user, template = _seeded_user_and_template()
    service, _ = _build_service(user=user, template=template)
    result = await service.login("  Demo@Example.COM  ", b"jpeg-bytes", NOW, LIFETIME)
    assert result.user_id == user.id


@pytest.mark.asyncio
async def test_login_happy_path_threshold_boundary_accepted():
    """similarity == threshold is accepted (>= operator, FR-003)."""
    user, template = _seeded_user_and_template()
    # Vector identical to template → similarity 1.0; threshold 1.0 → accepted (>=).
    service, _ = _build_service(user=user, template=template, verification_threshold=1.0)
    result = await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert result.user_id == user.id


# ==========================================================================
# T021: Non-revealing error mapping (FR-008/SC-003)
# ==========================================================================
@pytest.mark.asyncio
async def test_login_nonexistent_identifier_raises_auth_failed():
    service, sessions = _build_service(user=None, template=None)
    with pytest.raises(AuthFailed) as exc_info:
        await service.login("nope@example.com", b"jpeg", NOW, LIFETIME)
    assert str(exc_info.value) == AUTH_FAILED_MESSAGE
    assert len(sessions.created) == 0  # no session on failure (FR-004)


@pytest.mark.asyncio
async def test_login_below_threshold_raises_auth_failed_with_identical_message():
    user, template = _seeded_user_and_template()
    # Orthogonal vector → cosine similarity 0.0 < 0.5.
    orthogonal = [0.0] * EMBEDDING_DIM
    orthogonal[0] = 0.1
    orthogonal[1] = -0.1
    service, sessions = _build_service(user=user, template=template, embed_vector=orthogonal)
    with pytest.raises(AuthFailed) as exc_info:
        await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert str(exc_info.value) == AUTH_FAILED_MESSAGE
    assert len(sessions.created) == 0


@pytest.mark.asyncio
async def test_auth_failed_message_is_identical_for_both_causes():
    """The two identity-sensitive failures produce byte-identical exceptions (SC-003)."""
    user, template = _seeded_user_and_template()
    orthogonal = [0.0] * EMBEDDING_DIM
    orthogonal[0] = 0.1
    orthogonal[1] = -0.1

    service_nonexistent, _ = _build_service(user=None, template=None)
    service_below, _ = _build_service(user=user, template=template, embed_vector=orthogonal)

    err_a = None
    err_b = None
    try:
        await service_nonexistent.login("nope@example.com", b"jpeg", NOW, LIFETIME)
    except AuthFailed as e:
        err_a = e
    try:
        await service_below.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    except AuthFailed as e:
        err_b = e

    assert type(err_a) is type(err_b) is AuthFailed
    assert str(err_a) == str(err_b) == AUTH_FAILED_MESSAGE


@pytest.mark.asyncio
async def test_login_missing_template_raises_auth_failed():
    """User exists but has no FaceTemplate → AuthFailed (defensive, edge case)."""
    user = create_user("orphan@example.com", now=lambda: NOW, user_id=uuid.uuid4())
    service, sessions = _build_service(user=user, template=None)
    with pytest.raises(AuthFailed):
        await service.login("orphan@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


@pytest.mark.asyncio
async def test_login_malformed_identifier_raises_auth_failed():
    """Malformed identifier → AuthFailed (non-revealing; not a capture code)."""
    service, sessions = _build_service(user=None, template=None)
    with pytest.raises(AuthFailed):
        await service.login("not valid!", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


# ==========================================================================
# Capture-quality exceptions (400 codes) — no session created
# ==========================================================================
@pytest.mark.asyncio
async def test_login_no_face_raises_no_face():
    service, sessions = _build_service(
        detector_result=DetectionResult(face_count=0, boxes=[], score=0.0)
    )
    with pytest.raises(NoFace):
        await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


@pytest.mark.asyncio
async def test_login_multiple_faces_raises_multiple_faces():
    service, sessions = _build_service(
        detector_result=DetectionResult(
            face_count=2,
            boxes=[BoundingBox(0, 0, 100, 100), BoundingBox(120, 0, 100, 100)],
            score=0.99,
        )
    )
    with pytest.raises(MultipleFaces):
        await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


@pytest.mark.asyncio
async def test_login_insufficient_quality_raises_insufficient_quality():
    service, sessions = _build_service(
        detector_result=DetectionResult(face_count=1, boxes=[BoundingBox(0, 0, 100, 100)], score=0.1)
    )
    with pytest.raises(InsufficientQuality):
        await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


@pytest.mark.asyncio
async def test_login_empty_image_raises_invalid_image():
    service, sessions = _build_service()
    with pytest.raises(InvalidImage):
        await service.login("demo@example.com", b"", NOW, LIFETIME)
    assert len(sessions.created) == 0


# ==========================================================================
# Internal errors (500) — no session created
# ==========================================================================
@pytest.mark.asyncio
async def test_login_embedder_failure_raises_internal_error():
    user, template = _seeded_user_and_template()
    service, sessions = _build_service(user=user, template=template, embed_fail=True)
    with pytest.raises(LoginInternalError):
        await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


@pytest.mark.asyncio
async def test_login_dimension_mismatch_raises_internal_error():
    user, template = _seeded_user_and_template()
    # Embedder returns a 127-dim vector; template is 128-dim → ComparisonError → LoginInternalError.
    service, sessions = _build_service(user=user, template=template, embed_vector=[0.1] * 127)
    with pytest.raises(LoginInternalError):
        await service.login("demo@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0


# ==========================================================================
# Evaluation order: detection before lookup (R-5)
# ==========================================================================
@pytest.mark.asyncio
async def test_detection_runs_before_lookup_no_face_for_nonexistent_identifier():
    """A nonexistent identifier with a no-face image yields no_face (400), NOT
    auth_failed — proving detection runs before lookup (R-5). This eliminates the
    identifier-existence leak: capture errors surface uniformly for all identifiers."""
    service, sessions = _build_service(
        detector_result=DetectionResult(face_count=0, boxes=[], score=0.0),
        user=None,
        template=None,
    )
    with pytest.raises(NoFace):
        await service.login("nonexistent@example.com", b"jpeg", NOW, LIFETIME)
    assert len(sessions.created) == 0
