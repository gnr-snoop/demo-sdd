"""Image decode / limits / long-edge resize (spec 002, R-3, FR-010, OQ-8).

Domain-adjacent service: imports Pillow (PIL) for decode/resize. It is NOT part
of the pure-domain purity gate (see tests/domain/test_domain_purity.py —
``image_handling.py`` is explicitly excluded with a documented justification).
The pure onboarding decision logic lives in ``onboarding.py`` and calls this
module via the route adapter, keeping the domain free of Pillow.

Raises ``InvalidImage`` (from onboarding.py) on undecodable/unsupported/
oversized input. Returns resized JPEG bytes with long edge <= max_long_edge.
"""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

from .onboarding import InvalidImage


def decode_and_normalize(image_bytes: bytes, max_bytes: int, max_long_edge: int) -> bytes:
    """Decode, enforce limits, and resize a captured image.

    Steps:
      1. Reject empty or oversized payloads (> ``max_bytes``).
      2. Decode with Pillow; reject undecodable/non-image payloads.
      3. Convert to RGB (drop alpha/palette) and resize so the long edge
         <= ``max_long_edge`` (aspect ratio preserved, LANCZOS).
      4. Re-encode as JPEG and return the bytes.

    Raises :class:`InvalidImage` on any failure.
    """
    if not image_bytes:
        raise InvalidImage("empty image")
    if len(image_bytes) > max_bytes:
        raise InvalidImage("image exceeds max bytes")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImage("undecodable image") from exc

    # Normalize mode to RGB (JPEG has no alpha).
    if img.mode != "RGB":
        try:
            img = img.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise InvalidImage("unsupported image mode") from exc

    # Resize so the long edge <= max_long_edge (aspect ratio preserved).
    long_edge = max(img.width, img.height)
    if long_edge > max_long_edge:
        scale = max_long_edge / long_edge
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    try:
        img.save(buf, format="JPEG", quality=90)
    except Exception as exc:  # noqa: BLE001
        raise InvalidImage("jpeg re-encode failure") from exc
    return buf.getvalue()
