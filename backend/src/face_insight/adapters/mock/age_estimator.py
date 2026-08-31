"""MockAgeEstimator (T047) — deterministic age estimation (SC-005)."""

from __future__ import annotations

from ...domain.result_types import AgeResult
from .constants import AGE_MODEL_VERSION

# Hardcoded constant output (data-model.md).
_RESULT = AgeResult(estimated_age=32, range=(27, 37), model_version=AGE_MODEL_VERSION)


class MockAgeEstimator:
    """Returns a fixed age estimate of 32 (range 27–37)."""

    def estimate_age(self, face_image: bytes) -> AgeResult:
        return _RESULT
