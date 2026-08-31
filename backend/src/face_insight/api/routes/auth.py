"""Auth routes (spec 003, T018/T024/T029/T034): face-login, me, logout.

Real logic replacing the spec 001 stubs. Wires the ``LoginService`` use-case,
the ``SessionCookieService``, and the ``SessionManager``. Structured logging
(T050, R-10, FR-023/SC-013) emits event/duration/status/error_code only — no
image, embedding, similarity, or identifier value.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from ...config import get_settings
from ...domain.exceptions import (
    AUTH_FAILED_MESSAGE,
    AuthFailed,
    InsufficientQuality,
    InvalidImage,
    LoginInternalError,
    MultipleFaces,
    NoFace,
    Unauthenticated,
    UNAUTHENTICATED_MESSAGE,
)
from ...domain.image_handling import decode_and_normalize
from ...logging import get_logger
from ..dependencies import get_optional_session, get_session_cookie_service, require_valid_session
from ..schemas import LoginResponse, MeResponse, LogoutResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger("face_insight.auth")


# Exception → (status_code, machine_code, actionable message) for face-login
# (R-4, contract face-login.md). Capture codes map to 400; AuthFailed to 401.
_LOGIN_ERROR_MAP = {
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
    AuthFailed: (401, "auth_failed", AUTH_FAILED_MESSAGE),
    LoginInternalError: (500, "internal_error", "Ocurrió un error inesperado. Inténtalo de nuevo."),
}

_INTERNAL_ERROR_BODY = {"error": {"code": "internal_error", "message": "Ocurrió un error inesperado. Inténtalo de nuevo."}}


def _error_response(exc: Exception) -> JSONResponse:
    status, code, message = _LOGIN_ERROR_MAP[type(exc)]
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ==========================================================================
# POST /api/auth/face-login (T018/T023/T024)
# ==========================================================================
@router.post("/face-login", response_model=LoginResponse)
async def face_login(
    request: Request,
    identifier: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
) -> JSONResponse:
    """Verify a face 1:1 and create a session (spec 003).

    Evaluation order (R-5): decode/validate → detect → lookup → embed → compare
    → session create. Sets the signed http-only cookie on success.
    """
    settings = get_settings()
    started = time.monotonic()
    outcome = "error"
    code: Optional[str] = None

    try:
        if identifier is None:
            # Missing identifier form field → treat as auth_failed (non-revealing).
            raise AuthFailed(AUTH_FAILED_MESSAGE)
        if image is None:
            raise InvalidImage("missing image")
        image_bytes = await image.read()
        if not image_bytes:
            raise InvalidImage("empty image")
        if len(image_bytes) > settings.image_max_bytes:
            raise InvalidImage("oversized")

        # Decode + resize (R-3, OQ-8) — raises InvalidImage on failure.
        resized = decode_and_normalize(
            image_bytes, settings.image_max_bytes, settings.image_max_long_edge
        )

        login_service = request.app.state.login_service
        now = _now()
        lifetime = timedelta(seconds=settings.session_lifetime_seconds)
        result = await login_service.login(identifier, resized, now, lifetime)

        # Set signed cookie + return exactly {userId, status} (FR-005).
        cookie_service = request.app.state.session_cookie_service
        response = JSONResponse(
            status_code=200,
            content={"userId": str(result.user_id), "status": result.status},
        )
        cookie_service.set(response, result.session_id)

        outcome = "success"
        logger.info(
            "auth.login",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="success",
            user_id=str(result.user_id),
        )
        return response
    except tuple(_LOGIN_ERROR_MAP) as exc:
        outcome = "rejected" if isinstance(exc, AuthFailed) else "error"
        code = _LOGIN_ERROR_MAP[type(exc)][1]
        logger.info(
            "auth.login",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="failure",
            error_code=code,
        )
        return _error_response(exc)
    except Exception:  # noqa: BLE001 — boundary: wrap unexpected failures
        logger.exception("auth.login_unexpected_failure")
        return JSONResponse(status_code=500, content=_INTERNAL_ERROR_BODY)


# ==========================================================================
# GET /api/auth/me (T029)
# ==========================================================================
@router.get("/me", response_model=MeResponse)
async def me(request: Request) -> JSONResponse:
    """Return the current session state (spec 003, FR-011).

    200 {authenticated: true, userId} on a valid session; 401 unauthenticated
    otherwise. Bootstraps the frontend SessionContext.
    """
    started = time.monotonic()
    cookie_service = request.app.state.session_cookie_service
    session_manager = request.app.state.session_manager
    session_id = cookie_service.read(request)
    session = None
    if session_id is not None:
        session = await session_manager.get_valid(session_id, _now())

    if session is None:
        logger.info(
            "auth.me",
            duration_ms=int((time.monotonic() - started) * 1000),
            status="failure",
            error_code="unauthenticated",
        )
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "unauthenticated", "message": UNAUTHENTICATED_MESSAGE}},
        )

    logger.info(
        "auth.me",
        duration_ms=int((time.monotonic() - started) * 1000),
        status="success",
        user_id=str(session.user_id),
    )
    return JSONResponse(
        status_code=200,
        content={"authenticated": True, "userId": str(session.user_id)},
    )


# ==========================================================================
# POST /api/auth/logout (T034, R-9)
# ==========================================================================
@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request) -> JSONResponse:
    """Revoke the session and clear the cookie; always 200 {status: ok} (FR-012).

    Idempotent: no-cookie / expired / revoked / valid all return the same
    success. Best-effort revoke; the cookie is always cleared.
    """
    started = time.monotonic()
    cookie_service = request.app.state.session_cookie_service
    session_manager = request.app.state.session_manager
    session_id = cookie_service.read(request)
    if session_id is not None:
        try:
            await session_manager.revoke(session_id, _now())
        except Exception:  # noqa: BLE001 — best-effort; logout always succeeds
            logger.exception("auth.logout_revoke_failure")

    response = JSONResponse(status_code=200, content={"status": "ok"})
    cookie_service.clear(response)

    logger.info(
        "auth.logout",
        duration_ms=int((time.monotonic() - started) * 1000),
        status="success",
    )
    return response
