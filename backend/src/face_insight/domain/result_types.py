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
    confidence: float
    model_version: str


@dataclass(frozen=True)
class AgeResult:
    estimated_age: int
    range: tuple[int, int]
    model_version: str
