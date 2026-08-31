"""Mock adapter tests (T063, SC-005).

Every port's mock returns deterministic hardcoded constants. Running twice
yields byte-identical results (SC-005).
"""

from __future__ import annotations

import uuid

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
from face_insight.adapters.mock.constants import FIXED_USER_ID
from face_insight.domain.result_types import BoundingBox

IMAGE = b"\xff\xd8\xff\xe0mock"


# --- Detector --------------------------------------------------------------
def test_mock_detector_deterministic():
    d = MockDetector()
    r1 = d.detect(IMAGE)
    r2 = d.detect(IMAGE)
    assert r1.face_count == 1
    assert r1.score == 0.99
    assert r1.boxes == [BoundingBox(x=0, y=0, width=100, height=100)]
    assert r1 == r2  # byte-identical across calls


# --- Embedder --------------------------------------------------------------
def test_mock_embedder_deterministic():
    e = MockEmbedder()
    r1 = e.embed(IMAGE)
    r2 = e.embed(IMAGE)
    assert len(r1.vector) == 128
    assert all(v == 0.1 for v in r1.vector)
    assert r1.model_version == "mock-embed-v0"
    assert r1 == r2


# --- AgeEstimator ----------------------------------------------------------
def test_mock_age_estimator_deterministic():
    a = MockAgeEstimator()
    r1 = a.estimate_age(IMAGE)
    r2 = a.estimate_age(IMAGE)
    assert r1.estimated_age == 32
    assert r1.range == (27, 37)
    assert r1.model_version == "mock-age-v0"
    assert r1 == r2


# --- MoodEstimator ---------------------------------------------------------
def test_mock_mood_estimator_deterministic():
    m = MockMoodEstimator()
    r1 = m.estimate_mood(IMAGE)
    r2 = m.estimate_mood(IMAGE)
    assert r1.label == "neutral"
    assert r1.confidence == 0.74
    assert r1.model_version == "mock-mood-v0"
    assert r1 == r2


# --- SessionManager --------------------------------------------------------
def test_mock_session_manager_deterministic():
    sm = MockSessionManager()
    s1 = sm.create(FIXED_USER_ID)
    s2 = MockSessionManager().create(FIXED_USER_ID)
    # Fixed user → fixed session id and timestamps.
    assert s1.id == s2.id
    assert s1.created_at == s2.created_at
    assert sm.is_active(s1.id)


# --- UserRepository --------------------------------------------------------
def test_mock_user_repository_fixed_id():
    repo = MockUserRepository()
    user = repo.seed_fixed_user()
    assert user.id == FIXED_USER_ID
    assert repo.get(FIXED_USER_ID) is not None
    assert repo.get_by_identifier("demo@example.com") is not None
    repo.delete(FIXED_USER_ID)
    assert repo.get(FIXED_USER_ID) is None


# --- FaceTemplateRepository ------------------------------------------------
def test_mock_face_template_repository_one_per_user():
    from face_insight.domain.entities import create_face_template

    repo = MockFaceTemplateRepository()
    from datetime import datetime, timezone

    now = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
    tpl = create_face_template(FIXED_USER_ID, [0.1] * 128, "mock-embed-v0", now=lambda: now)
    repo.save(tpl)
    assert repo.get_by_user(FIXED_USER_ID) is not None
    repo.delete_by_user(FIXED_USER_ID)
    assert repo.get_by_user(FIXED_USER_ID) is None


# --- ImageStorage ----------------------------------------------------------
def test_mock_image_storage_roundtrip_and_path():
    storage = MockImageStorage()
    try:
        path = storage.store(FIXED_USER_ID, IMAGE)
        assert path == f"usuarios/{FIXED_USER_ID}/pictures.jpg"
        assert storage.read(FIXED_USER_ID) == IMAGE
        storage.delete(FIXED_USER_ID)
    finally:
        storage.close()


# --- SC-005: byte-identical across repeated instantiations ----------------
def test_mocks_byte_identical_across_runs():
    """Two independent mock instances produce identical outputs (SC-005)."""
    d1, d2 = MockDetector(), MockDetector()
    assert d1.detect(IMAGE) == d2.detect(IMAGE)

    e1, e2 = MockEmbedder(), MockEmbedder()
    assert e1.embed(IMAGE) == e2.embed(IMAGE)

    a1, a2 = MockAgeEstimator(), MockAgeEstimator()
    assert a1.estimate_age(IMAGE) == a2.estimate_age(IMAGE)

    m1, m2 = MockMoodEstimator(), MockMoodEstimator()
    assert m1.estimate_mood(IMAGE) == m2.estimate_mood(IMAGE)
