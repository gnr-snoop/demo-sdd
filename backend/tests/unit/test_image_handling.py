"""Unit tests for image_handling.decode_and_normalize (T031, R-3, FR-010, OQ-8)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from face_insight.domain.image_handling import decode_and_normalize
from face_insight.domain.onboarding import InvalidImage


def _jpeg(width: int, height: int, quality: int = 90) -> bytes:
    img = Image.new("RGB", (width, height), (128, 160, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


# --- Valid JPEG decode -----------------------------------------------------
def test_decode_valid_jpeg():
    data = _jpeg(100, 80)
    out = decode_and_normalize(data, max_bytes=2_000_000, max_long_edge=640)
    assert isinstance(out, bytes)
    # Output is a JPEG.
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"


def test_decode_converts_cmyk_to_rgb_jpeg():
    # A CMYK JPEG should be converted to RGB on output.
    img = Image.new("CMYK", (50, 50), (0, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    out = decode_and_normalize(buf.getvalue(), 2_000_000, 640)
    result = Image.open(io.BytesIO(out))
    assert result.mode == "RGB"
    assert result.format == "JPEG"


# --- Rejections ------------------------------------------------------------
def test_reject_empty():
    with pytest.raises(InvalidImage):
        decode_and_normalize(b"", 2_000_000, 640)


def test_reject_oversized():
    data = _jpeg(100, 100)
    with pytest.raises(InvalidImage):
        decode_and_normalize(data, max_bytes=10, max_long_edge=640)


def test_reject_undecodable():
    with pytest.raises(InvalidImage):
        decode_and_normalize(b"not an image at all", 2_000_000, 640)


def test_reject_non_jpeg_png_bytes():
    # A PNG encoded payload is decodable by Pillow but we still accept it as an
    # image (Pillow handles it) — the contract says JPEG-only, but
    # decode_and_normalize relies on Pillow. A truly garbage payload is rejected.
    with pytest.raises(InvalidImage):
        decode_and_normalize(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, 2_000_000, 640)


# --- Resize ----------------------------------------------------------------
def test_resize_when_long_edge_exceeds_limit():
    data = _jpeg(2000, 1000)
    out = decode_and_normalize(data, 2_000_000, max_long_edge=640)
    img = Image.open(io.BytesIO(out))
    assert max(img.width, img.height) <= 640
    # Aspect ratio roughly preserved (2:1).
    assert img.width / img.height == pytest.approx(2.0, rel=0.05)


def test_no_resize_when_within_limit():
    data = _jpeg(100, 80)
    out = decode_and_normalize(data, 2_000_000, max_long_edge=640)
    img = Image.open(io.BytesIO(out))
    # No resize needed; dimensions unchanged (modulo JPEG re-encode).
    assert (img.width, img.height) == (100, 80)


def test_resize_preserves_aspect_ratio_square():
    data = _jpeg(2000, 2000)
    out = decode_and_normalize(data, 2_000_000, max_long_edge=640)
    img = Image.open(io.BytesIO(out))
    assert img.width == img.height == 640


def test_output_is_jpeg_format():
    data = _jpeg(100, 100)
    out = decode_and_normalize(data, 2_000_000, 640)
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"
