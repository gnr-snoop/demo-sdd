"""face_crop — shared face-crop & alignment pipeline (spec 008, US3, FR-007,
research R-5).

Thin adapter-layer wrapper over ``cv2.FaceRecognizerSF.alignCrop`` (affine
transform from the 5 landmarks embedded in the YuNet face-box row). Produces a
fixed-size (112×112) aligned face image suitable for the SFace embedder.

Raises ``InvalidFaceBox`` on zero/negative-area boxes (FR-007 AC-3). This is an
adapter utility, NOT a domain port — the domain layer never imports it (FR-013).
"""

from __future__ import annotations

import cv2

from .constants import InvalidFaceBox


def _box_area(face_box: cv2.Mat | object) -> float:
    """Return the area (w * h) of a YuNet face-box row (cols 2, 3)."""
    try:
        w = float(face_box[2])
        h = float(face_box[3])
    except (TypeError, IndexError, ValueError) as exc:
        raise InvalidFaceBox(f"cannot read box dimensions: {exc}") from exc
    return w * h


def face_crop(recognizer, src_img, face_box):
    """Align and crop a face from ``src_img`` using ``face_box`` (YuNet row).

    Parameters
    ----------
    recognizer : cv2.FaceRecognizerSF
        The SFace recognizer instance (provides ``alignCrop``).
    src_img : cv2.Mat
        The decoded source image.
    face_box : cv2.Mat (1×15 row)
        The YuNet detection row (x, y, w, h, landmarks..., conf).

    Returns
    -------
    cv2.Mat
        Fixed-size aligned face image (112×112, SFace's expected input).

    Raises
    ------
    InvalidFaceBox
        If the box has zero or negative area (FR-007 AC-3).
    """
    area = _box_area(face_box)
    if area <= 0:
        raise InvalidFaceBox(
            f"bounding box has zero or negative area ({area})"
        )

    # alignCrop performs the affine transform from the 5 landmarks embedded in
    # the YuNet face-box row → fixed-size (112×112) aligned face image.
    aligned = recognizer.alignCrop(src_img, face_box)
    return aligned


__all__ = ["face_crop"]
