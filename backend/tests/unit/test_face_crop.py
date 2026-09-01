"""Unit test for face_crop (spec 008, US3, FR-007, research R-5).

Asserts ``InvalidFaceBox`` is raised on zero-area and negative-area boxes.
The valid-box path is tested with a fake recognizer (no model file required).
"""

from __future__ import annotations

import numpy as np
import pytest

from face_insight.adapters.ml.constants import InvalidFaceBox
from face_insight.adapters.ml.face_crop import face_crop


class _FakeRecognizer:
    """Minimal stand-in for cv2.FaceRecognizerSF.alignCrop — records the call."""

    def __init__(self) -> None:
        self.called = False

    def alignCrop(self, src_img, face_box, aligned=None):
        self.called = True
        # Return a 112x112 dummy image (simulating OpenCV's aligned crop).
        import numpy as np

        return np.zeros((112, 112, 3), dtype=np.uint8)


def _make_box(x, y, w, h, conf=0.9):
    """Build a 15-column YuNet face-box row as a numpy array."""
    row = [x, y, w, h, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, conf]
    return np.array(row, dtype=np.float32)


def test_zero_area_box_raises_invalid_face_box():
    """FR-007 AC-3: a zero-area box (w=0 or h=0) → InvalidFaceBox."""
    rec = _FakeRecognizer()
    src = np.zeros((100, 100, 3), dtype=np.uint8)
    box = _make_box(10, 10, 0, 50)
    with pytest.raises(InvalidFaceBox, match="zero or negative area"):
        face_crop(rec, src, box)
    assert not rec.called


def test_zero_height_box_raises_invalid_face_box():
    rec = _FakeRecognizer()
    src = np.zeros((100, 100, 3), dtype=np.uint8)
    box = _make_box(10, 10, 50, 0)
    with pytest.raises(InvalidFaceBox):
        face_crop(rec, src, box)


def test_negative_area_box_raises_invalid_face_box():
    """FR-007 AC-3: a negative-area box (w<0 or h<0) → InvalidFaceBox."""
    rec = _FakeRecognizer()
    src = np.zeros((100, 100, 3), dtype=np.uint8)
    box = _make_box(10, 10, -20, 50)
    with pytest.raises(InvalidFaceBox, match="zero or negative area"):
        face_crop(rec, src, box)


def test_valid_box_calls_aligncrop():
    """A valid (positive-area) box passes through to alignCrop (R-5)."""
    rec = _FakeRecognizer()
    src = np.zeros((200, 200, 3), dtype=np.uint8)
    box = _make_box(10, 10, 100, 100)
    face_crop(rec, src, box)
    assert rec.called is True


def test_face_crop_is_not_a_domain_port():
    """FR-013: face_crop lives in adapters.ml, not domain."""
    from face_insight.adapters.ml.face_crop import face_crop as fc

    assert fc.__module__ == "face_insight.adapters.ml.face_crop"
