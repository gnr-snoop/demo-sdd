"""MockMoodEstimator (T048) + ScriptableMockMoodEstimator (spec 004, T006/R-5).

- ``MockMoodEstimator``: deterministic mood estimation (SC-005). Returns a fixed
  ``neutral`` / ``0.74`` result. Left as the production wiring default (FR-016 —
  real models deferred to Fase 5, Constitution Principle VII). Exposes
  ``model_version = "mock-mood-v1"`` (FR-017).
- ``ScriptableMockMoodEstimator``: fixture-controllable variant for mood
  rejection/variation tests. It substring-searches the **raw request bytes** for
  markers (defined in ``constants.py``):
    ``b"FELIZ"``          → label "feliz", confidence 0.8
    ``b"TRIST"``          → label "triste", confidence 0.7
    ``b"ENOJO"``          → label "enojo", confidence 0.75
    ``b"NOCONCLUSIVE"``   → label "no concluyente", confidence 0.3
    ``b"OOSET"``          → out-of-set label "angry" (→ normalize to "no concluyente")
    ``b"MOODFAIL"``       → raises RuntimeError (→ MoodInternalError → 500)
  otherwise → default ``neutral`` / ``0.74`` (same as ``MockMoodEstimator``).

  Marker precedence: MOODFAIL > FELIZ > TRIST > ENOJO > NOCONCLUSIVE > OOSET > default.
  Test fixtures embed the marker in a JPEG COM segment so Pillow decode succeeds
  AND the estimator still sees the marker in the raw bytes (mirrors
  ``ScriptableMockDetector``).
"""

from __future__ import annotations

from ...domain.result_types import MoodResult
from .constants import (
    MOOD_FAIL_MARKER,
    MOOD_FELIZ_MARKER,
    MOOD_ENOJO_MARKER,
    MOOD_MODEL_VERSION,
    MOOD_NO_CONCLUSIVE_MARKER,
    MOOD_OUT_OF_SET_MARKER,
    MOOD_TRISTE_MARKER,
)

# Hardcoded constant output for the plain mock (data-model.md, SC-005).
_RESULT = MoodResult(label="neutral", confidence=0.74, model_version=MOOD_MODEL_VERSION)


class MockMoodEstimator:
    """Returns a fixed mood of 'neutral' with confidence 0.74 (SC-005)."""

    def estimate_mood(self, face_image: bytes) -> MoodResult:
        return _RESULT


# --- Scriptable (fixture-controllable) variant for mood tests (T006/R-5) ---
_DEFAULT_RESULT = MoodResult(label="neutral", confidence=0.74, model_version=MOOD_MODEL_VERSION)
_FELIZ_RESULT = MoodResult(label="feliz", confidence=0.8, model_version=MOOD_MODEL_VERSION)
_TRISTE_RESULT = MoodResult(label="triste", confidence=0.7, model_version=MOOD_MODEL_VERSION)
_ENOJO_RESULT = MoodResult(label="enojo", confidence=0.75, model_version=MOOD_MODEL_VERSION)
_NO_CONCLUSIVE_RESULT = MoodResult(
    label="no concluyente", confidence=0.3, model_version=MOOD_MODEL_VERSION
)
# Deliberately out-of-set label — the domain normalizer maps it to "no concluyente".
_OUT_OF_SET_RESULT = MoodResult(label="angry", confidence=0.55, model_version=MOOD_MODEL_VERSION)


class ScriptableMockMoodEstimator:
    """Mood estimator whose output is controlled by byte markers in the raw image.

    Marker precedence: MOODFAIL > FELIZ > TRIST > ENOJO > NOCONCLUSIVE > OOSET > default.
    This lets a single valid-JPEG fixture encode a mood case via its COM segment
    while still decoding successfully under Pillow.
    """

    def estimate_mood(self, face_image: bytes) -> MoodResult:
        if face_image is None:
            return _DEFAULT_RESULT
        if MOOD_FAIL_MARKER in face_image:
            raise RuntimeError("scriptable mood estimator failure")
        if MOOD_FELIZ_MARKER in face_image:
            return _FELIZ_RESULT
        if MOOD_TRISTE_MARKER in face_image:
            return _TRISTE_RESULT
        if MOOD_ENOJO_MARKER in face_image:
            return _ENOJO_RESULT
        if MOOD_NO_CONCLUSIVE_MARKER in face_image:
            return _NO_CONCLUSIVE_RESULT
        if MOOD_OUT_OF_SET_MARKER in face_image:
            return _OUT_OF_SET_RESULT
        return _DEFAULT_RESULT


__all__ = ["MockMoodEstimator", "ScriptableMockMoodEstimator"]
