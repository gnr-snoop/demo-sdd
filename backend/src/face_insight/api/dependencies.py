"""FastAPI dependencies (spec 003, T019/T028, R-6).

Real session validation replacing the spec 001 placeholder:
  - ``require_valid_session``: unsign cookie → SessionManager.get_valid → 401
    unauthenticated on None. Used by protected endpoints.
  - ``get_optional_session``: same but returns None instead of raising (used
    where a handler wants to branch on session presence).

Also provides ``get_login_service`` and ``get_session_cookie_service`` to resolve
the wired ports from ``app.state``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from ..domain.entities import AuthSession
from ..domain.exceptions import (
    DELETION_INTERNAL_ERROR_MESSAGE,
    FORBIDDEN_MESSAGE,
    NOT_FOUND_MESSAGE,
    DeletionInternalError,
    Forbidden,
    NotFound,
    UNAUTHENTICATED_MESSAGE,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class UnauthenticatedError(Exception):
    """Raised by session dependencies when no valid session is present.

    Converted to a ``401`` JSONResponse with the pinned ``unauthenticated``
    body by the handler registered in ``main.py``.
    """


def unauthenticated_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": {"code": "unauthenticated", "message": UNAUTHENTICATED_MESSAGE}},
    )


async def require_valid_session(request: Request) -> AuthSession:
    """Resolve and validate the session from the signed cookie (R-6).

    Raises ``UnauthenticatedError`` (→ 401) when the cookie is absent, tampered,
    unknown, expired, or revoked. On success returns the valid ``AuthSession``.
    """
    cookie_service = request.app.state.session_cookie_service
    session_manager = request.app.state.session_manager
    session_id = cookie_service.read(request)
    if session_id is None:
        raise UnauthenticatedError()
    session = await session_manager.get_valid(session_id, _now())
    if session is None:
        raise UnauthenticatedError()
    return session  # type: ignore[return-value]


async def get_optional_session(request: Request) -> Optional[AuthSession]:
    """Resolve the session without raising; returns None on any invalid state."""
    cookie_service = request.app.state.session_cookie_service
    session_manager = request.app.state.session_manager
    session_id = cookie_service.read(request)
    if session_id is None:
        return None
    return await session_manager.get_valid(session_id, _now())


def get_login_service(request: Request) -> object:
    return request.app.state.login_service


def get_session_cookie_service(request: Request) -> object:
    return request.app.state.session_cookie_service


def get_session_manager(request: Request) -> object:
    return request.app.state.session_manager


def get_mood_service(request: Request) -> object:
    """Resolve the wired ``MoodService`` from ``app.state`` (spec 004, T007/R-6).

    The service is built in ``main.wire_mock_adapters`` / ``create_auth_app``
    from the mock detector + mood estimator ports and stored on
    ``app.state.mood_service``.
    """
    return request.app.state.mood_service


# --- Spec 006 deletion error handlers (T003) --------------------------------
def register_deletion_exception_handlers(app) -> None:
    """Register ``Forbidden``→403, ``NotFound``→404, ``DeletionInternalError``→500
    exception handlers on ``app`` following the existing ``UnauthenticatedError``→401
    registration pattern. Handlers emit the pinned ``{"error": {"code", "message"}}``
    body shape (FR-008, contract delete-face-data.md).
    """

    @app.exception_handler(Forbidden)
    async def _forbidden_handler(_request, _exc):  # noqa: ANN001
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "forbidden", "message": FORBIDDEN_MESSAGE}},
        )

    @app.exception_handler(NotFound)
    async def _not_found_handler(_request, _exc):  # noqa: ANN001
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": NOT_FOUND_MESSAGE}},
        )

    @app.exception_handler(DeletionInternalError)
    async def _deletion_internal_handler(_request, _exc):  # noqa: ANN001
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": DELETION_INTERNAL_ERROR_MESSAGE,
                }
            },
        )


def get_deletion_service(request: Request) -> object:
    """Resolve the wired ``DeletionService`` from ``app.state`` (spec 006, T010).

    The service is built in ``main.wire_mock_adapters`` / ``create_auth_app``
    from the user repository, image storage, and the injected
    ``delete_user_face_data`` UnitOfWork callable.
    """
    return request.app.state.deletion_service
