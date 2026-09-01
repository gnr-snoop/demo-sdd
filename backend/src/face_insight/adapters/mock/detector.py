"""MockDetector (T045) + ScriptableMockDetector (T009, spec 002, R-6).

- ``MockDetector``: deterministic single-face detection (SC-005). Left as the
  production wiring default.
- ``ScriptableMockDetector``: fixture-controllable variant for rejection tests.
  It substring-searches the **raw request bytes** for markers:
    ``b"NOFACE"``      → face_count 0
    ``b"MULTIFACE"``   → face_count 2
    ``b"LOWQUALITY"``  → face_count 1, score 0.1 (below default threshold 0.5)
  otherwise → default count 1, score 0.99.

  Test fixtures (T037) are valid minimal JPEGs with the marker embedded in a
  JPEG COM (comment) segment so Pillow decode succeeds AND the detector still
  sees the marker in the raw bytes. Tests inject this via ``app.state.detector``.
"""

from __future__ import annotations

from ...domain.result_types import BoundingBox, DetectionResult, Landmark

# Hardcoded constant output for the plain mock (data-model.md).
_RESULT = DetectionResult(
    face_count=1,
    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
    score=0.99,
    landmarks=[[Landmark(x=30, y=35), Landmark(x=70, y=35), Landmark(x=50, y=60), Landmark(x=35, y=80), Landmark(x=65, y=80)]],
)


class MockDetector:
    """Returns a single deterministic detection."""

    def detect(self, image: bytes) -> DetectionResult:
        return _RESULT


# --- Scriptable (fixture-controllable) variant for rejection tests (R-6) ---
_NOFACE_MARKER = b"NOFACE"
_MULTIFACE_MARKER = b"MULTIFACE"
_LOWQUALITY_MARKER = b"LOWQUALITY"

_DEFAULT_RESULT = DetectionResult(
    face_count=1,
    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
    score=0.99,
    landmarks=[[Landmark(x=30, y=35), Landmark(x=70, y=35), Landmark(x=50, y=60), Landmark(x=35, y=80), Landmark(x=65, y=80)]],
)
_NO_FACE_RESULT = DetectionResult(face_count=0, boxes=[], score=0.0, landmarks=None)
_MULTI_FACE_RESULT = DetectionResult(
    face_count=2,
    boxes=[
        BoundingBox(x=0, y=0, width=100, height=100),
        BoundingBox(x=120, y=0, width=100, height=100),
    ],
    score=0.99,
    landmarks=[
        [Landmark(x=30, y=35), Landmark(x=70, y=35), Landmark(x=50, y=60), Landmark(x=35, y=80), Landmark(x=65, y=80)],
        [Landmark(x=150, y=35), Landmark(x=190, y=35), Landmark(x=170, y=60), Landmark(x=155, y=80), Landmark(x=185, y=80)],
    ],
)
_LOW_QUALITY_RESULT = DetectionResult(
    face_count=1,
    boxes=[BoundingBox(x=0, y=0, width=100, height=100)],
    score=0.1,
    landmarks=[[Landmark(x=30, y=35), Landmark(x=70, y=35), Landmark(x=50, y=60), Landmark(x=35, y=80), Landmark(x=65, y=80)]],
)


class ScriptableMockDetector:
    """Detector whose output is controlled by byte markers in the raw image.

    Marker precedence: NOFACE > MULTIFACE > LOWQUALITY > default. This lets a
    single valid-JPEG fixture encode a rejection case via its COM segment while
    still decoding successfully under Pillow.
    """

    def detect(self, image: bytes) -> DetectionResult:
        if image is None:
            return _DEFAULT_RESULT
        if _NOFACE_MARKER in image:
            return _NO_FACE_RESULT
        if _MULTIFACE_MARKER in image:
            return _MULTI_FACE_RESULT
        if _LOWQUALITY_MARKER in image:
            return _LOW_QUALITY_RESULT
        return _DEFAULT_RESULT
