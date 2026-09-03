"""Real-model integration tests for concrete ML adapters (spec 008 + spec 009,
US6, FR-014/FR-015, Constitution Quality Gate §6/§7).

These tests exercise ``YuNetDetector``, ``SFaceEmbedder``, ``EmotiEffMoodEstimator``
and ``MiVOLOAgeEstimator`` with real model files. They are skipped when:
  - any model file is absent from ``models/``, OR
  - ``APP_MODE != "production"``

so CI without models stays green (Constitution Quality Gate §7). Fixtures are
consented test images only (PRD §12).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_models

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "real_ml"


def _models_available() -> bool:
    """Check whether all four required model files are present in the models cache."""
    from face_insight.adapters.ml import (
        EMOTIEFF_MODEL_FILENAME,
        MIVOLO_CHECKPOINT_FILENAME,
        SFACE_MODEL_FILENAME,
        YUNET_MODEL_FILENAME,
    )
    from face_insight.config import get_settings

    models_dir = Path(get_settings().models_dir)
    required = (
        YUNET_MODEL_FILENAME,
        SFACE_MODEL_FILENAME,
        EMOTIEFF_MODEL_FILENAME,
        MIVOLO_CHECKPOINT_FILENAME,
    )
    return all((models_dir / name).exists() for name in required)


def _is_production_mode() -> bool:
    from face_insight.config import get_settings

    return get_settings().app_mode == "production"


@pytest.fixture(autouse=True)
def _skip_if_no_models_or_not_production():
    """FR-015 / R-6: skip when models absent OR APP_MODE != production."""
    if not _is_production_mode():
        pytest.skip("APP_MODE != production — real-model tests skipped")
    if not _models_available():
        pytest.skip("real models absent — real-model tests skipped")


def _fixture_bytes(name: str) -> bytes:
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"fixture absent: {name}")
    return path.read_bytes()


# ===========================================================================
# Detector integration assertions (FR-005, SC-002)
# ===========================================================================
def test_detector_single_face():
    from face_insight.adapters.ml import YuNetDetector
    from face_insight.config import get_settings

    detector = YuNetDetector()
    image = _fixture_bytes("single_face.jpg")
    result = detector.detect(image)
    assert result.face_count == 1, f"expected 1 face, got {result.face_count}"
    assert len(result.boxes) == 1
    assert result.score >= get_settings().quality_threshold


def test_detector_no_face():
    from face_insight.adapters.ml import YuNetDetector

    detector = YuNetDetector()
    image = _fixture_bytes("no_face.jpg")
    result = detector.detect(image)
    assert result.face_count == 0
    assert result.boxes == []


def test_detector_multi_face():
    from face_insight.adapters.ml import YuNetDetector

    detector = YuNetDetector()
    image = _fixture_bytes("multi_face.jpg")
    result = detector.detect(image)
    assert result.face_count >= 2, f"expected >= 2 faces, got {result.face_count}"
    assert len(result.boxes) == result.face_count


# ===========================================================================
# Embedder integration assertions (FR-006, SC-003)
# ===========================================================================
def test_embedder_dimension_and_version():
    from face_insight.adapters.ml import EMBEDDING_DIM, SFACE_MODEL_VERSION, SFaceEmbedder

    embedder = SFaceEmbedder()
    image = _fixture_bytes("single_face.jpg")
    embedding = embedder.embed(image)
    assert len(embedding.vector) == EMBEDDING_DIM
    assert embedding.model_version == SFACE_MODEL_VERSION


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def test_same_person_cosine_above_threshold():
    from face_insight.adapters.ml import PRODUCTION_VERIFICATION_THRESHOLD, SFaceEmbedder

    embedder = SFaceEmbedder()
    img1 = _fixture_bytes("person_a_1.jpg")
    img2 = _fixture_bytes("person_a_2.jpg")
    emb1 = embedder.embed(img1)
    emb2 = embedder.embed(img2)
    sim = _cosine_similarity(emb1.vector, emb2.vector)
    assert sim >= PRODUCTION_VERIFICATION_THRESHOLD, (
        f"same-person cosine {sim} < threshold {PRODUCTION_VERIFICATION_THRESHOLD}"
    )


def test_different_person_cosine_below_threshold():
    from face_insight.adapters.ml import PRODUCTION_VERIFICATION_THRESHOLD, SFaceEmbedder

    embedder = SFaceEmbedder()
    img_a = _fixture_bytes("person_a_1.jpg")
    img_b = _fixture_bytes("person_b_1.jpg")
    emb_a = embedder.embed(img_a)
    emb_b = embedder.embed(img_b)
    sim = _cosine_similarity(emb_a.vector, emb_b.vector)
    assert sim < PRODUCTION_VERIFICATION_THRESHOLD, (
        f"different-person cosine {sim} >= threshold {PRODUCTION_VERIFICATION_THRESHOLD}"
    )


# ===========================================================================
# Mood adapter integration assertions (spec 009, FR-001/FR-005/FR-006, SC-002)
# ===========================================================================
_PRD_MOOD_LABELS = frozenset(
    {"neutral", "feliz", "triste", "sorprendido", "enojo", "no concluyente"}
)


def test_mood_estimator_valid_label_and_confidence():
    """T025/FR-001/SC-002: single-face fixture → label in PRD set, confidence
    in [0,1], model_version == EMOTIEFF_MODEL_VERSION."""
    from face_insight.adapters.ml import EMOTIEFF_MODEL_VERSION, EmotiEffMoodEstimator

    estimator = EmotiEffMoodEstimator()
    image = _fixture_bytes("single_face.jpg")
    result = estimator.estimate_mood(image)
    assert result.label in _PRD_MOOD_LABELS, f"unexpected label: {result.label}"
    assert 0.0 <= result.confidence <= 1.0
    assert result.model_version == EMOTIEFF_MODEL_VERSION


def test_mood_estimator_low_confidence_no_conclusive(monkeypatch):
    """T026/FR-006: with MOOD_CONFIDENCE_THRESHOLD raised above any realistic
    top-1 probability, the label is 'no concluyente' and the low confidence is
    still returned."""
    monkeypatch.setenv("MOOD_CONFIDENCE_THRESHOLD", "0.99")
    from face_insight.adapters.ml import EmotiEffMoodEstimator

    estimator = EmotiEffMoodEstimator(confidence_threshold=0.99)
    image = _fixture_bytes("single_face.jpg")
    result = estimator.estimate_mood(image)
    assert result.label == "no concluyente"
    assert result.confidence is not None and result.confidence < 0.99


def test_mood_no_face_raises():
    """T028/FR-014: no-face fixture → the adapter raises ValueError (the domain
    MoodService wraps this into MoodInternalError; the detector's NoFace check
    usually fires first)."""
    from face_insight.adapters.ml import EmotiEffMoodEstimator

    estimator = EmotiEffMoodEstimator()
    image = _fixture_bytes("no_face.jpg")
    with pytest.raises(ValueError, match="no face detected for alignment"):
        estimator.estimate_mood(image)


def test_mood_multi_face():
    """T028/FR-014: multi-face fixture → the adapter processes the first face
    (the domain MultipleFaces check fires at the service level before the
    adapter is invoked; here we assert the adapter itself does not crash)."""
    from face_insight.adapters.ml import EmotiEffMoodEstimator

    estimator = EmotiEffMoodEstimator()
    image = _fixture_bytes("multi_face.jpg")
    result = estimator.estimate_mood(image)
    assert result.label in _PRD_MOOD_LABELS


# ===========================================================================
# Age adapter integration assertions (spec 009, FR-002/FR-007, SC-003)
# ===========================================================================
def test_age_estimator_point_only_and_invariants():
    """T027/FR-002/FR-007/SC-003: single-face fixture → estimated_age >= 0,
    range is None (point-only), model_version == MIVOLO_MODEL_VERSION. After
    domain normalization, min >= 0 and min <= estimated <= max."""
    from face_insight.adapters.ml import MIVOLO_MODEL_VERSION, MiVOLOAgeEstimator
    from face_insight.domain.age import normalize_age_result

    estimator = MiVOLOAgeEstimator()
    image = _fixture_bytes("single_face.jpg")
    raw = estimator.estimate_age(image)
    assert raw.estimated_age >= 0
    assert raw.range is None
    assert raw.model_version == MIVOLO_MODEL_VERSION
    # Domain derives the symmetric range (spec 005, unchanged).
    normalized = normalize_age_result(raw, 5)
    assert normalized.range is not None
    lo, hi = normalized.range
    assert lo >= 0
    assert lo <= normalized.estimated_age <= hi


def test_age_no_face_raises():
    """T028/FR-014: no-face fixture → the adapter raises ValueError."""
    from face_insight.adapters.ml import MiVOLOAgeEstimator

    estimator = MiVOLOAgeEstimator()
    image = _fixture_bytes("no_face.jpg")
    with pytest.raises(ValueError, match="no face detected for alignment"):
        estimator.estimate_age(image)


def test_age_multi_face():
    """T028/FR-014: multi-face fixture → the adapter processes the first face."""
    from face_insight.adapters.ml import MiVOLOAgeEstimator

    estimator = MiVOLOAgeEstimator()
    image = _fixture_bytes("multi_face.jpg")
    result = estimator.estimate_age(image)
    assert result.estimated_age >= 0
    assert result.range is None


# ===========================================================================
# F-04: AFEW index order assertion (spec 009, research R-4)
# ===========================================================================
def test_afew_index_order_matches_library():
    """F-04: assert the HSEmotion-onnx library's ``idx_to_class`` for
    ``enet_b0_8_best_afew`` matches our ``AFEW_INDEX_TO_EMOTION_NAME`` constant.
    This validates that the AFEW→PRD label mapping is applied to the correct
    index ordering (research R-4)."""
    from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

    from face_insight.adapters.ml import AFEW_INDEX_TO_EMOTION_NAME

    recognizer = HSEmotionRecognizer(model_name="enet_b0_8_best_afew")
    assert recognizer.idx_to_class == AFEW_INDEX_TO_EMOTION_NAME, (
        f"Library idx_to_class {recognizer.idx_to_class} != "
        f"AFEW_INDEX_TO_EMOTION_NAME {AFEW_INDEX_TO_EMOTION_NAME}"
    )
