"""Mood analysis use-case (spec 004, T012, R-1/R-2, FR-005/FR-015/SC-009).

This module is pure domain: it imports only ports, result types, domain
exceptions, and the stdlib. It MUST NOT import adapters, api, SQLAlchemy,
FastAPI, Pillow, or any ML library (enforced by tests/domain/test_domain_purity.py).

``MoodService.analyze`` orchestrates the on-demand mood flow per data-model.md:
  1. detect (exactly one usable face: face_count == 1 and score >= threshold)
     — raises NoFace / MultipleFaces / InsufficientQuality.
  2. estimate_mood — port failure → MoodInternalError.
  3. normalize_mood_label(result.label) — out-of-set → "no concluyente" (FR-004).
  4. clamp confidence to [0, 1] (None passes through — FR-012a).
  5. return MoodResult.

The mood result is transient — no persistence (FR-014).
"""

from __future__ import annotations

from .exceptions import MoodInternalError, MultipleFaces, NoFace, InsufficientQuality
from .ports import Detector, MoodEstimator
from .result_types import MoodResult

# --- Label set (FR-004) ----------------------------------------------------
# The single normative enumeration of valid mood labels. Out-of-set / low-quality
# port output is normalized to "no concluyente" by ``normalize_mood_label``.
VALID_LABELS: frozenset[str] = frozenset(
    {"neutral", "feliz", "triste", "sorprendido", "enojo", "no concluyente"}
)

# Normalization target for any out-of-set / low-quality label.
_NO_CONCLUSIVE = "no concluyente"


def normalize_mood_label(label: str) -> str:
    """Normalize a mood label against the valid set (FR-004).

    Valid labels pass through unchanged; any out-of-set / low-quality label
    (including empty strings, wrong case, unknown labels) is normalized to
    ``"no concluyente"``. Pure function — trivially unit-testable.
    """
    if label in VALID_LABELS:
        return label
    return _NO_CONCLUSIVE


def _clamp_confidence(value: float | None) -> float | None:
    """Clamp a confidence value to [0.0, 1.0]; None passes through (FR-012a)."""
    if value is None:
        return None
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


# --- MoodService use-case --------------------------------------------------
class MoodService:
    """Orchestrates on-demand mood analysis through injected ports (hexagonal
    use-case, FR-015/SC-009).

    Depends only on the ``Detector`` + ``MoodEstimator`` ports — no infra. The
    Fase 5 real-model swap is a configuration change, not a redesign (FR-016).
    """

    def __init__(
        self,
        detector: Detector,
        mood_estimator: MoodEstimator,
        quality_threshold: float = 0.5,
    ) -> None:
        self._detector = detector
        self._mood_estimator = mood_estimator
        self._quality_threshold = quality_threshold

    def analyze(self, image_bytes: bytes) -> MoodResult:
        """Run the mood analysis flow (FR-005).

        Raises ``NoFace`` / ``MultipleFaces`` / ``InsufficientQuality`` on
        capture-quality failures, and ``MoodInternalError`` on port/estimator
        failure. Returns a normalized ``MoodResult`` on success.
        """
        # 1. Detect — exactly one usable face.
        detection = self._detector.detect(image_bytes)
        if detection.face_count == 0:
            raise NoFace()
        if detection.face_count > 1:
            raise MultipleFaces()
        if detection.score < self._quality_threshold:
            raise InsufficientQuality()

        # 2. Estimate mood — port failure → MoodInternalError (500).
        try:
            raw = self._mood_estimator.estimate_mood(image_bytes)
        except Exception as exc:  # noqa: BLE001 — boundary: wrap infra failures
            raise MoodInternalError("mood estimator failure") from exc

        # 3. Normalize label (FR-004) + clamp confidence (FR-012a).
        label = normalize_mood_label(raw.label)
        confidence = _clamp_confidence(raw.confidence)

        return MoodResult(
            label=label,
            confidence=confidence,
            model_version=raw.model_version,
        )


__all__ = ["VALID_LABELS", "MoodService", "normalize_mood_label"]
