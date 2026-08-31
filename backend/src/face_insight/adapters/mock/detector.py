"""MockDetector (T045) — deterministic face detection (SC-005)."""

from __future__ import annotations

from ...domain.result_types import BoundingBox, DetectionResult

# Hardcoded constant output (data-model.md).
_RESULT = DetectionResult(
    face_count=1,
    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
    score=0.99,
)


class MockDetector:
    """Returns a single deterministic detection."""

    def detect(self, image: bytes) -> DetectionResult:
        return _RESULT
