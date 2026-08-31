"""MockMoodEstimator (T048) — deterministic mood estimation (SC-005)."""

from __future__ import annotations

from ...domain.result_types import MoodResult
from .constants import MOOD_MODEL_VERSION

# Hardcoded constant output (data-model.md).
_RESULT = MoodResult(label="neutral", confidence=0.74, model_version=MOOD_MODEL_VERSION)


class MockMoodEstimator:
    """Returns a fixed mood of 'neutral' with confidence 0.74."""

    def estimate_mood(self, face_image: bytes) -> MoodResult:
        return _RESULT
