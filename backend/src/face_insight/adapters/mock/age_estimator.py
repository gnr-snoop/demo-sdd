"""MockAgeEstimator (T047) + ScriptableMockAgeEstimator (spec 005, T006/R-5).

- ``MockAgeEstimator``: deterministic age estimation (SC-005). Returns a fixed
  ``estimated_age=32`` / ``range=(27, 37)`` result. Left as the production
  wiring default (FR-016 — real models deferred to Fase 5, Constitution
  Principle VII). Exposes ``model_version = "mock-age-estimator-v1"``
  (FR-017).
- ``ScriptableMockAgeEstimator``: fixture-controllable variant for age
  rejection/variation tests. It substring-searches the **raw request bytes**
  for markers (defined in ``constants.py``):
    ``b"AGEPOINT"``  → point-only estimate 40 (range=None) → derived symmetric range
    ``b"AGERANGE"``  → range (35, 45) → estimatedAge = midpoint 40
    ``b"AGEFAIL"``   → raises RuntimeError (→ AgeInternalError → 500)
  otherwise → default ``estimated_age=32`` / ``range=(27, 37)`` (same as
  ``MockAgeEstimator``).

  Marker precedence: AGEFAIL > AGEPOINT > AGERANGE > default.
  Test fixtures embed the marker in a JPEG COM segment so Pillow decode
  succeeds AND the estimator still sees the marker in the raw bytes (mirrors
  ``ScriptableMockMoodEstimator`` / ``ScriptableMockDetector``).
"""

from __future__ import annotations

from ...domain.result_types import AgeResult
from .constants import (
    AGE_MODEL_VERSION,
    AGEFAIL_MARKER,
    AGEPOINT_MARKER,
    AGERANGE_MARKER,
)

# Hardcoded constant output for the plain mock (data-model.md, SC-005).
_RESULT = AgeResult(estimated_age=32, range=(27, 37), model_version=AGE_MODEL_VERSION)


class MockAgeEstimator:
    """Returns a fixed age estimate of 32 (range 27–37)."""

    def estimate_age(self, face_image: bytes) -> AgeResult:
        return _RESULT


# --- Scriptable (fixture-controllable) variant for age tests (T006/R-5) ---
_DEFAULT_RESULT = AgeResult(estimated_age=32, range=(27, 37), model_version=AGE_MODEL_VERSION)
# Point-only: no range → AgeService derives a symmetric range around 40.
_POINT_ONLY_RESULT = AgeResult(estimated_age=40, range=None, model_version=AGE_MODEL_VERSION)
# Range-only: (35, 45) → AgeService sets estimatedAge to the midpoint 40.
_RANGE_RESULT = AgeResult(estimated_age=40, range=(35, 45), model_version=AGE_MODEL_VERSION)


class ScriptableMockAgeEstimator:
    """Age estimator whose output is controlled by byte markers in the raw image.

    Marker precedence: AGEFAIL > AGEPOINT > AGERANGE > default. This lets a
    single valid-JPEG fixture encode an age case via its COM segment while
    still decoding successfully under Pillow.
    """

    def estimate_age(self, face_image: bytes) -> AgeResult:
        if face_image is None:
            return _DEFAULT_RESULT
        if AGEFAIL_MARKER in face_image:
            raise RuntimeError("scriptable age estimator failure")
        if AGEPOINT_MARKER in face_image:
            return _POINT_ONLY_RESULT
        if AGERANGE_MARKER in face_image:
            return _RANGE_RESULT
        return _DEFAULT_RESULT


__all__ = ["MockAgeEstimator", "ScriptableMockAgeEstimator"]
