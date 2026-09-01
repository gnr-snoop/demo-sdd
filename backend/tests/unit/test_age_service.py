"""Unit tests for the AgeService use-case (spec 005, T010/T018).

Covers:
  - T010: ``normalize_age_result`` — range → midpoint estimate; point-only →
    derived symmetric range (half-width 5, ``min`` clamped to 0); invariants
    (``min >= 0``, ``min <= estimated_age <= max``) on every output (FR-004/SC-014).
  - T018: point-only normalization edge cases (negative estimate clamping,
    half-width 0) and error-code mapping (``NoFace``/``MultipleFaces``/
    ``InsufficientQuality``/``AgeInternalError`` raised by the orchestration on
    the corresponding detector / age-estimator outputs).

Pure domain: no FastAPI, no Pillow, no network (mock ports only — FR-016).
"""

from __future__ import annotations

import pytest

from face_insight.domain.age import AgeService, normalize_age_result
from face_insight.domain.exceptions import (
    AgeInternalError,
    InsufficientQuality,
    MultipleFaces,
    NoFace,
)
from face_insight.domain.result_types import AgeResult, BoundingBox, DetectionResult


# --- Fake ports ------------------------------------------------------------
class _FakeDetector:
    def __init__(self, result: DetectionResult):
        self._result = result

    def detect(self, image: bytes) -> DetectionResult:
        return self._result


CATCH = DetectionResult(
    face_count=1, boxes=[BoundingBox(x=0, y=0, width=100, height=100)], score=0.99
)


class _FakeAgeEstimator:
    def __init__(self, result: AgeResult | Exception):
        self._result = result

    def estimate_age(self, face_image: bytes) -> AgeResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


# ==========================================================================
# T010: normalize_age_result — range → midpoint
# ==========================================================================
class TestNormalizeRangeToMidpoint:
    def test_range_midpoint_is_returned_as_estimated_age(self):
        raw = AgeResult(estimated_age=0, range=(35, 45), model_version="mock-age-estimator-v1")
        out = normalize_age_result(raw, half_width=5)
        assert out.range == (35, 45)
        assert out.estimated_age == 40  # midpoint

    def test_range_midpoint_rounds_to_nearest_integer(self):
        raw = AgeResult(estimated_age=0, range=(27, 38), model_version="m")
        out = normalize_age_result(raw, half_width=5)
        # midpoint = 32.5 → round → 32 (Python banker's rounding rounds to even)
        # 32.5 → 32; ensure within [27, 38].
        assert out.range == (27, 38)
        assert 27 <= out.estimated_age <= 38

    def test_range_min_clamped_to_zero(self):
        raw = AgeResult(estimated_age=10, range=(-5, 15), model_version="m")
        out = normalize_age_result(raw, half_width=5)
        assert out.range[0] == 0
        assert out.range == (0, 15)
        assert 0 <= out.estimated_age <= 15

    def test_range_invariants_hold(self):
        raw = AgeResult(estimated_age=999, range=(20, 30), model_version="m")
        out = normalize_age_result(raw, half_width=5)
        assert out.range[0] >= 0
        assert out.range[0] <= out.estimated_age <= out.range[1]

    def test_model_version_is_preserved(self):
        raw = AgeResult(estimated_age=40, range=(35, 45), model_version="mock-age-estimator-v1")
        out = normalize_age_result(raw, half_width=5)
        assert out.model_version == "mock-age-estimator-v1"


# ==========================================================================
# T010/T018: normalize_age_result — point-only → derived symmetric range
# ==========================================================================
class TestNormalizePointOnlyToDerivedRange:
    def test_point_only_derives_symmetric_range_default_half_width(self):
        raw = AgeResult(estimated_age=40, range=None, model_version="m")
        out = normalize_age_result(raw, half_width=5)
        assert out.estimated_age == 40
        assert out.range == (35, 45)

    def test_point_only_min_clamped_to_zero(self):
        # estimate 3, half_width 5 → raw min would be -2 → clamped to 0.
        raw = AgeResult(estimated_age=3, range=None, model_version="m")
        out = normalize_age_result(raw, half_width=5)
        assert out.range[0] == 0
        assert out.range == (0, 8)
        assert 0 <= out.estimated_age <= 8

    def test_point_only_half_width_zero_yields_degenerate_range(self):
        raw = AgeResult(estimated_age=42, range=None, model_version="m")
        out = normalize_age_result(raw, half_width=0)
        assert out.range == (42, 42)
        assert out.estimated_age == 42

    def test_point_only_negative_half_width_treated_as_zero(self):
        # The domain does not trust the caller; negative half-width → 0.
        raw = AgeResult(estimated_age=42, range=None, model_version="m")
        out = normalize_age_result(raw, half_width=-3)
        assert out.range == (42, 42)

    def test_point_only_invariants_hold(self):
        raw = AgeResult(estimated_age=50, range=None, model_version="m")
        out = normalize_age_result(raw, half_width=5)
        assert out.range[0] >= 0
        assert out.range[0] <= out.estimated_age <= out.range[1]


# ==========================================================================
# T010: invariants hold on every output (SC-014)
# ==========================================================================
class TestInvariants:
    @pytest.mark.parametrize(
        "raw,half_width",
        [
            (AgeResult(32, (27, 37), "m"), 5),
            (AgeResult(40, None, "m"), 5),
            (AgeResult(3, None, "m"), 5),
            (AgeResult(0, (0, 0), "m"), 5),
            (AgeResult(100, (90, 110), "m"), 5),
            (AgeResult(40, (35, 45), "m"), 0),
        ],
    )
    def test_min_ge_zero_and_min_le_estimated_le_max(self, raw, half_width):
        out = normalize_age_result(raw, half_width)
        assert out.range is not None
        lo, hi = out.range
        assert lo >= 0
        assert lo <= out.estimated_age <= hi


# ==========================================================================
# T018: error-code mapping (detector → capture-quality exceptions)
# ==========================================================================
class TestErrorMapping:
    def test_no_face_raises(self):
        svc = AgeService(
            detector=_FakeDetector(DetectionResult(face_count=0, boxes=[], score=0.0)),
            age_estimator=_FakeAgeEstimator(AgeResult(32, (27, 37), "m")),
        )
        with pytest.raises(NoFace):
            svc.analyze(b"\xff\xd8fake")

    def test_multiple_faces_raises(self):
        svc = AgeService(
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
            age_estimator=_FakeAgeEstimator(AgeResult(32, (27, 37), "m")),
        )
        with pytest.raises(MultipleFaces):
            svc.analyze(b"\xff\xd8fake")

    def test_insufficient_quality_raises(self):
        svc = AgeService(
            detector=_FakeDetector(
                DetectionResult(
                    face_count=1,
                    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
                    score=0.1,  # below default threshold 0.5
                )
            ),
            age_estimator=_FakeAgeEstimator(AgeResult(32, (27, 37), "m")),
        )
        with pytest.raises(InsufficientQuality):
            svc.analyze(b"\xff\xd8fake")

    def test_age_estimator_port_failure_raises_age_internal_error(self):
        svc = AgeService(
            detector=_FakeDetector(CATCH),
            age_estimator=_FakeAgeEstimator(RuntimeError("port boom")),
        )
        with pytest.raises(AgeInternalError):
            svc.analyze(b"\xff\xd8fake")

    def test_quality_threshold_is_configurable(self):
        # score 0.4 — below 0.5 default but at/above a custom 0.3 threshold.
        svc = AgeService(
            detector=_FakeDetector(
                DetectionResult(
                    face_count=1,
                    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
                    score=0.4,
                )
            ),
            age_estimator=_FakeAgeEstimator(AgeResult(32, (27, 37), "m")),
            quality_threshold=0.3,
        )
        result = svc.analyze(b"\xff\xd8fake")
        assert result.range == (27, 37)


# ==========================================================================
# T018: AgeService.analyze normalizes the port output
# ==========================================================================
class TestAnalyzeNormalization:
    def test_range_port_output_is_normalized_to_midpoint(self):
        svc = AgeService(
            detector=_FakeDetector(CATCH),
            age_estimator=_FakeAgeEstimator(AgeResult(0, (35, 45), "mock-age-estimator-v1")),
        )
        out = svc.analyze(b"\xff\xd8fake")
        assert out.estimated_age == 40
        assert out.range == (35, 45)
        assert out.model_version == "mock-age-estimator-v1"

    def test_point_only_port_output_is_normalized_to_derived_range(self):
        svc = AgeService(
            detector=_FakeDetector(CATCH),
            age_estimator=_FakeAgeEstimator(AgeResult(40, None, "mock-age-estimator-v1")),
        )
        out = svc.analyze(b"\xff\xd8fake")
        assert out.estimated_age == 40
        assert out.range == (35, 45)

    def test_half_width_is_configurable(self):
        svc = AgeService(
            detector=_FakeDetector(CATCH),
            age_estimator=_FakeAgeEstimator(AgeResult(40, None, "m")),
            age_range_half_width_years=10,
        )
        out = svc.analyze(b"\xff\xd8fake")
        assert out.range == (30, 50)
