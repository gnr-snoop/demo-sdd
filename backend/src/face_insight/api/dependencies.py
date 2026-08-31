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
from ..domain.exceptions import UNAUTHENTICATED_MESSAGE


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
