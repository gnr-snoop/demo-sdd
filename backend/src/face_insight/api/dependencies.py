"""FastAPI dependencies (T033).

Session-placeholder dependency: reads the ``X-Session-Id`` header and returns
401 when absent/empty (FR-006). Real session enforcement is deferred to spec 003.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status


async def require_session(x_session_id: str | None = Header(default=None)) -> str:
    """Return the session placeholder id, or raise 401 if absent.

    In Fase 1 this is a placeholder: any non-empty value is accepted. Real
    session validation (DB lookup, expiry) is deferred to spec 003.
    """
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated",
        )
    return x_session_id
