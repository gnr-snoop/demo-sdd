"""POST /api/onboarding — real onboarding orchestration (spec 002, T014).

Replaces the spec 001 stub. Reads multipart fields, enforces image limits,
decodes/resizes via Pillow, runs the ``OnboardingService`` use-case, and maps
domain exceptions to the pinned ``{"error": {"code", "message"}}`` shape (R-7).
Structured logging (T039, R-10, FR-016) emits event/duration/outcome/code only
— no images, embeddings, or identifiers.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ...config import get_settings
from ...domain.image_handling import decode_and_normalize
from ...domain.onboarding import (
    ConsentRequired,
    IdentifierInvalid,
    IdentifierTaken,
    InsufficientQuality,
    InvalidImage,
    MultipleFaces,
    NoFace,
    OnboardingInternalError,
)
from ...logging import get_logger
from ..schemas import OnboardingResponse

router = APIRouter(prefix="/api", tags=["onboarding"])
logger = get_logger("face_insight.onboarding")


# Exception → (status_code, machine_code, actionable message) (R-7, contract).
_ERROR_MAP = {
    IdentifierInvalid: (
        422,
        "identifier_invalid",
        "El identificador no es válido. Usa un email bien formado o un nombre de "
        "usuario (3–32 caracteres, letras, números, '.', '_', '-').",
    ),
    IdentifierTaken: (
        409,
        "identifier_taken",
        "Ese identificador ya está registrado. Prueba con otro o inicia sesión si es tuyo.",
    ),
    ConsentRequired: (
        422,
        "consent_required",
        "Debes aceptar el consentimiento para el procesamiento facial antes de continuar.",
    ),
    InvalidImage: (
        422,
        "invalid_image",
        "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB.",
    ),
    NoFace: (
        422,
        "no_face",
        "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena "
        "iluminación y vuelve a capturar.",
    ),
    MultipleFaces: (
        422,
        "multiple_faces",
        "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura.",
    ),
    InsufficientQuality: (
        422,
        "insufficient_quality",
        "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la "
        "cámara y vuelve a capturar.",
    ),
    OnboardingInternalError: (
        500,
        "internal_error",
        "Ocurrió un error inesperado. Inténtalo de nuevo.",
    ),
}


def _error_response(exc: Exception) -> JSONResponse:
    status, code, message = _ERROR_MAP[type(exc)]
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
    )


@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
async def onboarding(
    request: Request,
    identifier: Optional[str] = Form(default=None),
    consentAccepted: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
) -> JSONResponse:
    """Register a person and process their face.

    Validates identifier + consent, enforces image limits, decodes/resizes,
    detects exactly one usable face, embeds, and atomically persists
    ``User`` (enrolled) + ``FaceTemplate``. Returns ``201`` on success or a
    pinned ``{"error": {"code", "message"}}`` error on rejection.
    """
    settings = get_settings()
    started = time.monotonic()
    outcome = "error"
    code: Optional[str] = None

    try:
        # --- Consent: accept only the canonical "true" string (FR-003). -----
        if consentAccepted != "true":
            raise ConsentRequired()

        # --- Image presence + size limit (FR-010, OQ-8). --------------------
        if image is None:
            raise InvalidImage("missing image")
        image_bytes = await image.read()
        if not image_bytes:
            raise InvalidImage("empty image")
        if len(image_bytes) > settings.image_max_bytes:
            raise InvalidImage("oversized")

        # --- Decode + resize (R-3, FR-010). --------------------------------
        resized = decode_and_normalize(
            image_bytes, settings.image_max_bytes, settings.image_max_long_edge
        )

        # --- Run the use-case (identifier validation, detect, embed, persist).
        service = request.app.state.onboarding_service
        unit_of_work = getattr(request.app.state, "unit_of_work", None)
        save = unit_of_work.save_user_with_template if unit_of_work is not None else None

        result = await service.onboard(identifier, True, resized, save_user_with_template=save)

        outcome = "success"
        return JSONResponse(
            status_code=201,
            content={
                "userId": str(result.user_id),
                "identifier": result.identifier,
                "status": result.status.value,
            },
        )
    except tuple(_ERROR_MAP) as exc:
        outcome = "rejected" if isinstance(exc, (IdentifierInvalid, IdentifierTaken, ConsentRequired)) else "error"
        code = _ERROR_MAP[type(exc)][1]
        return _error_response(exc)
    except Exception as exc:  # noqa: BLE001 — boundary: wrap unexpected failures
        logger.exception("onboarding_unexpected_failure")
        outcome = "error"
        code = "internal_error"
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Ocurrió un error inesperado. Inténtalo de nuevo."}},
        )
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)
        # R-10/FR-016: no images, embeddings, or identifiers logged.
        logger.info(
            "onboarding",
            duration_ms=duration_ms,
            outcome=outcome,
            code=code,
        )
