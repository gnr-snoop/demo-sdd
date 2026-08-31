"""Unit tests for OnboardingService (T035, FR-004/FR-005/FR-008/FR-006).

Uses in-memory mock ports (no DB, no GPU, no network). Covers face-count rules,
quality-threshold branch, all-or-nothing (no persistence on any post-validation
failure), embedder-failure → OnboardingInternalError, identifier normalization,
duplicate detection, and the happy path.
"""

from __future__ import annotations

import pytest

from face_insight.adapters.mock import (
    MockEmbedder,
    MockFaceTemplateRepository,
    MockImageStorage,
    MockUserRepository,
    ScriptableMockDetector,
)
from face_insight.domain.entities import UserStatus
from face_insight.domain.onboarding import (
    ConsentRequired,
    IdentifierInvalid,
    IdentifierTaken,
    InsufficientQuality,
    InvalidImage,
    MultipleFaces,
    NoFace,
    OnboardingInternalError,
    OnboardingService,
)
from face_insight.domain.result_types import BoundingBox, DetectionResult, Embedding


# --- Fakes / helpers -------------------------------------------------------
class FailingEmbedder:
    """Embedder that always raises, to test internal-error handling."""

    def embed(self, face_image: bytes) -> Embedding:
        raise RuntimeError("embedder boom")


class CountingDetector:
    """Detector returning a fixed result for deterministic face-count tests."""

    def __init__(self, result: DetectionResult) -> None:
        self._result = result
        self.invoked = 0

    def detect(self, image: bytes) -> DetectionResult:
        self.invoked += 1
        return self._result


def _service(detector=None, embedder=None, quality_threshold=0.5) -> OnboardingService:
    return OnboardingService(
        detector=detector or ScriptableMockDetector(),
        embedder=embedder or MockEmbedder(),
        user_repository=MockUserRepository(),
        face_template_repository=MockFaceTemplateRepository(),
        image_storage=MockImageStorage(),
        quality_threshold=quality_threshold,
        embedding_model_version="mock-embedder-v1",
    )


def _one_face_bytes() -> bytes:
    from tests.conftest import fixture_bytes

    return fixture_bytes("one_face.jpg")


# --- Happy path ------------------------------------------------------------
@pytest.mark.asyncio
async def test_happy_path_returns_normalized_identifier_and_enrolled():
    svc = _service()
    result = await svc.onboard("  Demo@Example.COM  ", True, _one_face_bytes())
    assert result.identifier == "demo@example.com"
    assert result.status == UserStatus.enrolled
    assert result.user_id is not None


@pytest.mark.asyncio
async def test_happy_path_persists_user_and_template():
    svc = _service()
    result = await svc.onboard("demo@example.com", True, _one_face_bytes())
    user = await svc._users.get(result.user_id)
    assert user is not None and user.status == UserStatus.enrolled
    tpl = await svc._templates.get_by_user(result.user_id)
    assert tpl is not None and tpl.model_version == "mock-embedder-v1"


# --- Identifier validation -------------------------------------------------
@pytest.mark.asyncio
async def test_invalid_identifier_raises():
    svc = _service()
    with pytest.raises(IdentifierInvalid):
        await svc.onboard("not valid!", True, _one_face_bytes())


@pytest.mark.asyncio
async def test_empty_identifier_raises():
    svc = _service()
    with pytest.raises(IdentifierInvalid):
        await svc.onboard("   ", True, _one_face_bytes())


# --- Consent ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_consent_false_raises():
    svc = _service()
    with pytest.raises(ConsentRequired):
        await svc.onboard("demo@example.com", False, _one_face_bytes())


@pytest.mark.asyncio
async def test_consent_non_boolean_raises():
    svc = _service()
    with pytest.raises(ConsentRequired):
        await svc.onboard("demo@example.com", "true", _one_face_bytes())  # type: ignore[arg-type]


# --- Image -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_image_raises():
    svc = _service()
    with pytest.raises(InvalidImage):
        await svc.onboard("demo@example.com", True, b"")


# --- Face-count rules (FR-004) --------------------------------------------
@pytest.mark.asyncio
async def test_no_face_raises():
    detector = CountingDetector(DetectionResult(0, [], 0.0))
    svc = _service(detector=detector)
    with pytest.raises(NoFace):
        await svc.onboard("demo@example.com", True, _one_face_bytes())


@pytest.mark.asyncio
async def test_multiple_faces_raises():
    detector = CountingDetector(
        DetectionResult(2, [BoundingBox(0, 0, 10, 10), BoundingBox(20, 0, 10, 10)], 0.99)
    )
    svc = _service(detector=detector)
    with pytest.raises(MultipleFaces):
        await svc.onboard("demo@example.com", True, _one_face_bytes())


# --- Quality threshold (FR-005) -------------------------------------------
@pytest.mark.asyncio
async def test_insufficient_quality_raises():
    detector = CountingDetector(DetectionResult(1, [BoundingBox(0, 0, 10, 10)], 0.1))
    svc = _service(detector=detector, quality_threshold=0.5)
    with pytest.raises(InsufficientQuality):
        await svc.onboard("demo@example.com", True, _one_face_bytes())


@pytest.mark.asyncio
async def test_quality_at_threshold_passes():
    detector = CountingDetector(DetectionResult(1, [BoundingBox(0, 0, 10, 10)], 0.5))
    svc = _service(detector=detector, quality_threshold=0.5)
    result = await svc.onboard("demo@example.com", True, _one_face_bytes())
    assert result.status == UserStatus.enrolled


# --- All-or-nothing (FR-008): no persistence on rejection ------------------
@pytest.mark.asyncio
async def test_no_persistence_on_no_face():
    detector = CountingDetector(DetectionResult(0, [], 0.0))
    svc = _service(detector=detector)
    with pytest.raises(NoFace):
        await svc.onboard("demo@example.com", True, _one_face_bytes())
    # No user, no template, no image stored.
    assert await svc._users.get_by_identifier("demo@example.com") is None
    # Image storage should not have a directory for any user.
    import shutil

    users_dir = svc._images._usuarios  # type: ignore[attr-defined]
    assert not any(p.is_dir() for p in users_dir.iterdir()) if users_dir.exists() else True


@pytest.mark.asyncio
async def test_no_persistence_on_invalid_identifier():
    svc = _service()
    with pytest.raises(IdentifierInvalid):
        await svc.onboard("bad!", True, _one_face_bytes())
    assert await svc._users.get_by_identifier("bad!") is None


# --- Embedder failure → internal error, no persistence ---------------------
@pytest.mark.asyncio
async def test_embedder_failure_raises_internal_error():
    svc = _service(embedder=FailingEmbedder())
    with pytest.raises(OnboardingInternalError):
        await svc.onboard("demo@example.com", True, _one_face_bytes())
    assert await svc._users.get_by_identifier("demo@example.com") is None


# --- Duplicate identifier (case-insensitive) -------------------------------
@pytest.mark.asyncio
async def test_duplicate_identifier_raises():
    svc = _service()
    await svc.onboard("demo@example.com", True, _one_face_bytes())
    with pytest.raises(IdentifierTaken):
        await svc.onboard("DEMO@Example.COM", True, _one_face_bytes())


# --- Identifier normalization flow ----------------------------------------
@pytest.mark.asyncio
async def test_identifier_normalized_before_duplicate_check():
    svc = _service()
    await svc.onboard("  AliceDoe  ", True, _one_face_bytes())
    # Different case/whitespace same normalized value → taken.
    with pytest.raises(IdentifierTaken):
        await svc.onboard(" alicedoe ", True, _one_face_bytes())
