"""Analysis routes (spec 004 + spec 005): mood and age.

- ``POST /api/analysis/mood`` — real orchestration (spec 004, T013/T019):
  ``Depends(require_valid_session)`` → decode/validate → ``MoodService.analyze``
  → structured JSON logging (duration_ms/status, no biometric data) →
  ``200 MoodResponse``. Capture-quality failures map to actionable ``400`` codes;
  port errors map to ``500 internal_error`` (R-4, contracts/analysis-mood.md).
- ``POST /api/analysis/age`` — real orchestration (spec 005, T014/T021):
  ``Depends(require_valid_session)`` → decode/validate → ``AgeService.analyze``
  → build ``AgeResponse(estimatedAge, range=AgeRange(min,max), disclaimer)``
  → structured JSON logging (``analysis.age``, ``duration_ms``, ``status``) →
  ``200 AgeResponse``. Capture-quality failures map to actionable ``400`` codes;
  port errors map to ``500 internal_error`` (R-4, contracts/analysis-age.md).
  Supersedes the spec 001 stub. Mood route unchanged (FR-020).

Session-protected via ``require_valid_session`` (spec 003 real gating, FR-001).
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from ...config import get_settings
from ...domain.exceptions import (
    AgeInternalError,
    InsufficientQuality,
    InvalidImage,
    MoodInternalError,
    MultipleFaces,
    NoFace,
)
from ...domain.image_handling import decode_and_normalize
from ...logging import get_logger
from ..dependencies import get_mood_service, require_valid_session
from ..schemas import (
    AGE_DISCLAIMER,
    MOOD_DISCLAIMER,
    AgeRange,
    AgeResponse,
    MoodRange,
    MoodResponse,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
logger = get_logger("face_insight.analysis")


# Exception → (status_code, machine_code, actionable message) for mood
# (R-4, contracts/analysis-mood.md). Capture codes map to 400; port errors to 500.
# Mirrors auth.py's _LOGIN_ERROR_MAP pattern.
_MOOD_ERROR_MAP = {
    InvalidImage: (
        400,
        "invalid_image",
        "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB.",
    ),
    NoFace: (
        400,
        "no_face",
        "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena "
        "iluminación y vuelve a capturar.",
    ),
    MultipleFaces: (
        400,
        "multiple_faces",
        "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura.",
    ),
    InsufficientQuality: (
        400,
        "insufficient_quality",
        "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la "
        "cámara y vuelve a capturar.",
    ),
    MoodInternalError: (500, "internal_error", "Ocurrió un error inesperado. Inténtalo de nuevo."),
}

# Spec 005 (T021, R-4, contracts/analysis-age.md): age error map. Capture codes
# map to 400; AgeInternalError → 500 internal_error. Messages match the contract
# verbatim. Mirrors _MOOD_ERROR_MAP (the capture-quality messages are identical
# to mood's — both reuse the spec 002 error shape).
_AGE_ERROR_MAP = {
    InvalidImage: (
        400,
        "invalid_image",
        "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB.",
    ),
    NoFace: (
        400,
        "no_face",
        "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena "
        "iluminación y vuelve a capturar.",
    ),
    MultipleFaces: (
        400,
        "multiple_faces",
        "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura.",
    ),
    InsufficientQuality: (
        400,
        "insufficient_quality",
        "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la "
        "cámara y vuelve a capturar.",
    ),
    AgeInternalError: (500, "internal_error", "Ocurrió un error inesperado. Inténtalo de nuevo."),
}

_INTERNAL_ERROR_BODY = {
    "error": {"code": "internal_error", "message": "Ocurrió un error inesperado. Inténtalo de nuevo."}
}


def _mood_error_response(exc: Exception) -> JSONResponse:
    status, code, message = _MOOD_ERROR_MAP[type(exc)]
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _age_error_response(exc: Exception) -> JSONResponse:
    status, code, message = _AGE_ERROR_MAP[type(exc)]
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


# ==========================================================================
# POST /api/analysis/mood (T013/T019)
# ==========================================================================
@router.post("/mood", response_model=MoodResponse)
async def analysis_mood(
    request: Request,
    image: UploadFile = File(...),
    session=Depends(require_valid_session),
) -> JSONResponse:
    """Estimate mood from a single capture (spec 004).

    Evaluation order (FR-005): session → image decode/validate → detect (exactly
    one face + quality) → estimate → normalize label → respond. The mood result
    is transient (FR-014 — not persisted).
    """
    settings = get_settings()
    started = time.monotonic()

    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise InvalidImage("empty image")
        if len(image_bytes) > settings.image_max_bytes:
            raise InvalidImage("oversized")

        # Decode + resize (R-3, OQ-8) — raises InvalidImage on failure.
        resized = decode_and_normalize(
            image_bytes, settings.image_max_bytes, settings.image_max_long_edge
        )

        mood_service = request.app.state.mood_service
        result = mood_service.analyze(resized)

        response = JSONResponse(
            status_code=200,
            content={
                "label": result.label,
                "confidence": result.confidence,
                "disclaimer": MOOD_DISCLAIMER,
            },
        )
        logger.info(
            "analysis.mood",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="success",
        )
        return response
    except tuple(_MOOD_ERROR_MAP) as exc:
        code = _MOOD_ERROR_MAP[type(exc)][1]
        logger.info(
            "analysis.mood",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="failure",
            error_code=code,
        )
        return _mood_error_response(exc)
    except Exception:  # noqa: BLE001 — boundary: wrap unexpected failures
        logger.exception("analysis.mood_unexpected_failure")
        return JSONResponse(status_code=500, content=_INTERNAL_ERROR_BODY)


# ==========================================================================
# POST /api/analysis/age (spec 005, T014/T021)
# ==========================================================================
@router.post("/age", response_model=AgeResponse)
async def analysis_age(
    request: Request,
    image: UploadFile = File(...),
    session=Depends(require_valid_session),
) -> JSONResponse:
    """Estimate age from a single capture (spec 005).

    Evaluation order (FR-005): session → image decode/validate → detect (exactly
    one face + quality) → estimate → normalize → respond. The age result is
    transient (FR-014 — not persisted). Mirrors the mood route's structured
    logging (``analysis.age``, ``duration_ms``, ``status`` — no biometric data,
    FR-019/SC-013).
    """
    settings = get_settings()
    started = time.monotonic()

    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise InvalidImage("empty image")
        if len(image_bytes) > settings.image_max_bytes:
            raise InvalidImage("oversized")

        # Decode + resize (R-3, OQ-8) — raises InvalidImage on failure.
        resized = decode_and_normalize(
            image_bytes, settings.image_max_bytes, settings.image_max_long_edge
        )

        age_service = request.app.state.age_service
        result = age_service.analyze(resized)
        # normalize_age_result guarantees range is non-None (FR-004).
        assert result.range is not None  # invariant: noqa: S101
        lo, hi = result.range

        response = JSONResponse(
            status_code=200,
            content={
                "estimatedAge": result.estimated_age,
                "range": {"min": lo, "max": hi},
                "disclaimer": AGE_DISCLAIMER,
            },
        )
        logger.info(
            "analysis.age",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="success",
        )
        return response
    except tuple(_AGE_ERROR_MAP) as exc:
        code = _AGE_ERROR_MAP[type(exc)][1]
        logger.info(
            "analysis.age",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="failure",
            error_code=code,
        )
        return _age_error_response(exc)
    except Exception:  # noqa: BLE001 — boundary: wrap unexpected failures
        logger.exception("analysis.age_unexpected_failure")
        return JSONResponse(status_code=500, content=_INTERNAL_ERROR_BODY)
