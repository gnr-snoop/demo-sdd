"""Unit tests for the MoodService use-case (spec 004, T009/T016).

Covers:
   - T009: ``normalize_mood_label`` (valid labels pass; out-of-set → ``no concluyente``)
    and confidence clamping to ``[0, 1]`` (None passes through).
  - T016: error-code mapping (``NoFace``/``MultipleFaces``/``InsufficientQuality``/
    ``MoodInternalError`` raised by the orchestration on the corresponding detector /
    mood-estimator outputs).

Pure domain: no FastAPI, no Pillow, no network (mock ports only — FR-016).
"""

from __future__ import annotations

import pytest

from face_insight.domain.exceptions import (
    InsufficientQuality,
    MoodInternalError,
    MultipleFaces,
    NoFace,
)
from face_insight.domain.mood import VALID_LABELS, MoodService, normalize_mood_label
from face_insight.domain.result_types import BoundingBox, DetectionResult, MoodResult
from face_insight.adapters.mock.mood_estimator import ScriptableMockMoodEstimator


# --- Fake ports ------------------------------------------------------------
class _FakeDetector:
    def __init__(self, result: DetectionResult):
        self._result = result

    def detect(self, image: bytes) -> DetectionResult:
        return self._result


CATCH = DetectionResult(
    face_count=1, boxes=[BoundingBox(x=0, y=0, width=100, height=100)], score=0.99
)


class _FakeMoodEstimator:
    def __init__(self, result: MoodResult | Exception):
        self._result = result

    def estimate_mood(self, face_image: bytes) -> MoodResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


# ==========================================================================
# T009: normalize_mood_label
# ==========================================================================
class TestNormalizeMoodLabel:
    @pytest.mark.parametrize(
        "label",
        ["neutral", "feliz", "triste", "sorprendido", "enojo", "no concluyente"],
    )
    def test_valid_labels_pass_through(self, label: str):
        assert normalize_mood_label(label) == label

    @pytest.mark.parametrize(
        "label",
        ["happy", "angry", "NEUTRAL", "Feliz", "", "enojado", "surprised", "mood"],
    )
    def test_out_of_set_normalizes_to_no_concluyente(self, label: str):
        assert normalize_mood_label(label) == "no concluyente"

    def test_valid_labels_set_contains_the_six_supported_labels(self):
        assert VALID_LABELS == {
            "neutral",
            "feliz",
            "triste",
            "sorprendido",
            "enojo",
            "no concluyente",
        }


# ==========================================================================
# T009: confidence clamping
# ==========================================================================
class TestConfidenceClamp:
    def test_confidence_within_range_passes_through(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("feliz", 0.8, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.confidence == 0.8

    def test_confidence_above_one_is_clamped_to_one(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("feliz", 1.5, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.confidence == 1.0

    def test_confidence_below_zero_is_clamped_to_zero(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("triste", -0.3, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.confidence == 0.0

    def test_none_confidence_passes_through(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("neutral", None, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.confidence is None


# ==========================================================================
# T009: label normalization is applied to the port output
# ==========================================================================
class TestLabelNormalizationApplied:
    def test_out_of_set_label_from_port_normalizes_to_no_concluyente(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("angry", 0.55, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.label == "no concluyente"

    def test_valid_label_from_port_is_preserved(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("sorprendido", 0.6, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.label == "sorprendido"

    def test_anger_label_from_port_is_preserved(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(MoodResult("enojo", 0.75, "mock-mood-v1")),
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.label == "enojo"

    def test_scriptable_mock_can_emit_anger(self):
        result = ScriptableMockMoodEstimator().estimate_mood(b"ENOJO")
        assert result.label == "enojo"
        assert result.confidence == 0.75


# ==========================================================================
# T016: error-code mapping (detector → capture-quality exceptions)
# ==========================================================================
class TestErrorMapping:
    def test_no_face_raises_no2(self):
        svc = MoodService(
            detector=_FakeDetector(DetectionResult(face_count=0, boxes=[], score=0.0)),
            mood_estimator=_FakeMoodEstimator(MoodResult("neutral", 0.5, "mock-mood-v1")),
        )
        with pytest.raises(NoFace):
            svc.analyze(b"\xff\xd8fake")

    def test_multiple_faces_raises(self):
        svc = MoodService(
            detector=_FakeDetector(
                DetectionResult(
                    face_count=2,
                    boxes=[
                        BoundingBox(x=0, y=0, width=100, height=100),
                        BoundingBox(x=120, y=0, width=100, height=100),
                    ],
                    score=0.99,
                )
            ),
            mood_estimator=_FakeMoodEstimator(MoodResult("neutral", 0.5, "mock-mood-v1")),
        )
        with pytest.raises(MultipleFaces):
            svc.analyze(b"\xff\xd8fake")

    def test_insufficient_quality_raises(self):
        svc = MoodService(
            detector=_FakeDetector(
                DetectionResult(
                    face_count=1,
                    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
                    score=0.1,  # below default threshold 0.5
                )
            ),
            mood_estimator=_FakeMoodEstimator(MoodResult("neutral", 0.5, "mock-mood-v1")),
        )
        with pytest.raises(InsufficientQuality):
            svc.analyze(b"\xff\xd8fake")

    def test_mood_estimator_port_failure_raises_mood_internal_error(self):
        svc = MoodService(
            detector=_FakeDetector(CATCH),
            mood_estimator=_FakeMoodEstimator(RuntimeError("port boom")),
        )
        with pytest.raises(MoodInternalError):
            svc.analyze(b"\xff\xd8fake")

    def test_quality_threshold_is_configurable(self):
        # score 0.4 — below 0.5 default but at/above a custom 0.3 threshold.
        svc = MoodService(
            detector=_FakeDetector(
                DetectionResult(
                    face_count=1,
                    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
                    score=0.4,
                )
            ),
            mood_estimator=_FakeMoodEstimator(MoodResult("feliz", 0.8, "mock-mood-v1")),
            quality_threshold=0.3,
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.label == "feliz"
