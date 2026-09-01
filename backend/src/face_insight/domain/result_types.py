"""Domain value objects / result types (T042, data-model.md Ports table)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class DetectionResult:
    face_count: int
    boxes: list[BoundingBox]
    score: float


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    model_version: str


@dataclass(frozen=True)
class MoodResult:
    label: str
    # Spec 004 (T002/R-3): widened from `float` to `float | None` to permit
    # null/omitted confidence per PRD §6.4 (backward-compatible; the mock always
    # supplies a value). Clamped to [0,1] by MoodService when present.
    confidence: float | None
    model_version: str


@dataclass(frozen=True)
class AgeResult:
    estimated_age: int
    # Spec 005 (T003, data-model.md): widened from `tuple[int, int]` to
    # `tuple[int, int] | None` to permit a **point-only** port output (the
    # estimator may return an estimated age without a range). Backward-
    # compatible (the mock always supplies a range). The `AgeService`
    # normalization layer guarantees the returned `AgeResult` always has a
    # non-`None` `range` satisfying the invariants (FR-004).
    range: tuple[int, int] | None
    model_version: str


@dataclass(frozen=True)
class ComparisonResult:
    """Outcome of a 1:1 face verification comparison (spec 003, R-1).

    ``similarity`` is the cosine similarity in [-1, 1]; ``accepted`` is True iff
    ``similarity >= verification_threshold``. Not persisted; not logged (only
    the accept/reject decision is logged, never the score — FR-023/SC-013).
    """

    similarity: float
    accepted: bool
