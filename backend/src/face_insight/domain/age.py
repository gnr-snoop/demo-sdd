"""Age analysis use-case (spec 005, T013, R-1/R-2, FR-005/FR-015/SC-009).

This module is pure domain: it imports only ports, result types, domain
exceptions, and the stdlib. It MUST NOT import adapters, api, SQLAlchemy,
FastAPI, Pillow, or any ML library (enforced by tests/domain/test_domain_purity.py).

``AgeService.analyze`` orchestrates the on-demand age flow per data-model.md:
  1. detect (exactly one usable face: face_count == 1 and score >= threshold)
     — raises NoFace / MultipleFaces / InsufficientQuality.
  2. estimate_age — port failure → AgeInternalError.
  3. normalize_age_result(raw, half_width) — guarantees range non-None +
     invariants (min >= 0, min <= estimated_age <= max) (FR-004).
  4. return AgeResult (range guaranteed).

The age result is transient — no persistence (FR-014).
"""

from __future__ import annotations

from .exceptions import AgeInternalError, InsufficientQuality, MultipleFaces, NoFace
from .ports import AgeEstimator, Detector
from .result_types import AgeResult


def _clamp(value: int, lo: int, hi: int) -> int:
    """Clamp ``value`` to ``[lo, hi]`` (lo <= hi assumed)."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def normalize_age_result(raw: AgeResult, half_width: int) -> AgeResult:
    """Normalize the age_estimator port output to the response contract (FR-004).

    - If the port returned a **range** ``(min, max)``: ``estimatedAge`` is the
      midpoint ``round((min + max) / 2)`` clamped into ``[min, max]``; ``min``
      is clamped to 0 (age cannot be negative).
    - If the port returned a **point-only** estimate (``range is None``): a
      symmetric range is derived around the estimate using ``half_width``
      (``min = max(0, estimated - half_width)``, ``max = estimated + half_width``);
      ``estimatedAge`` is returned as-is.

    Invariants guaranteed on every return: ``min >= 0`` and
    ``min <= estimated_age <= max``. Pure function — trivially unit-testable
    (FR-004/SC-014).
    """
    # Defensive: half_width must be non-negative (Settings clamps it, but the
    # domain does not trust the caller).
    hw = half_width if half_width >= 0 else 0

    if raw.range is not None:
        raw_min, raw_max = raw.range
        # Clamp min to 0 (age cannot be negative — FR-004).
        min_clamped = max(0, raw_min)
        max_val = raw_max
        # If clamping min pushed it above max, preserve max >= min.
        if max_val < min_clamped:
            max_val = min_clamped
        midpoint = round((min_clamped + max_val) / 2)
        estimated = _clamp(midpoint, min_clamped, max_val)
        return AgeResult(
            estimated_age=estimated,
            range=(min_clamped, max_val),
            model_version=raw.model_version,
        )

    # Point-only: derive a symmetric range around the estimate.
    estimated = raw.estimated_age
    min_clamped = max(0, estimated - hw)
    max_val = estimated + hw
    if max_val < min_clamped:
        max_val = min_clamped
    # estimated is already the point; ensure it lies within [min, max].
    estimated = _clamp(estimated, min_clamped, max_val)
    return AgeResult(
        estimated_age=estimated,
        range=(min_clamped, max_val),
        model_version=raw.model_version,
    )


# --- AgeService use-case --------------------------------------------------
class AgeService:
    """Orchestrates on-demand age analysis through injected ports (hexagonal
    use-case, FR-015/SC-009).

    Depends only on the ``Detector`` + ``AgeEstimator`` ports — no infra. The
    Fase 5 real-model swap is a configuration change, not a redesign (FR-016).
    """

    def __init__(
        self,
        detector: Detector,
        age_estimator: AgeEstimator,
        quality_threshold: float = 0.5,
        age_range_half_width_years: int = 5,
    ) -> None:
        self._detector = detector
        self._age_estimator = age_estimator
        self._quality_threshold = quality_threshold
        self._half_width = age_range_half_width_years

    def analyze(self, image_bytes: bytes) -> AgeResult:
        """Run the age analysis flow (FR-005).

        Raises ``NoFace`` / ``MultipleFaces`` / ``InsufficientQuality`` on
        capture-quality failures, and ``AgeInternalError`` on port/estimator
        failure. Returns a normalized ``AgeResult`` (range guaranteed non-None,
        invariants enforced) on success.
        """
        # 1. Detect — exactly one usable face.
        detection = self._detector.detect(image_bytes)
        if detection.face_count == 0:
            raise NoFace()
        if detection.face_count > 1:
            raise MultipleFaces()
        if detection.score < self._quality_threshold:
            raise InsufficientQuality()

        # 2. Estimate age — port failure → AgeInternalError (500).
        try:
            raw = self._age_estimator.estimate_age(image_bytes)
        except Exception as exc:  # noqa: BLE001 — boundary: wrap infra failures
            raise AgeInternalError("age estimator failure") from exc

        # 3. Normalize to {estimatedAge, range:{min,max}} with invariants (FR-004).
        return normalize_age_result(raw, self._half_width)


__all__ = ["AgeService", "normalize_age_result"]
