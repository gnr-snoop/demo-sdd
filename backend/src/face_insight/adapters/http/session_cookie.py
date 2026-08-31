"""SessionCookieService — signed http-only cookie adapter (T010, R-3).

Wraps ``itsdangerous.URLSafeTimedSerializer`` to sign/unsign the AuthSession id
(UUID v4 string) and read/write the cookie on a FastAPI ``Response``/``Request``.

Cookie attributes: ``HttpOnly``, ``SameSite=Lax``, ``Path=/``, ``Secure``
toggled by ``Settings.session_cookie_secure``. On logout the cookie is cleared
via ``Max-Age=0``. A tampered/unsigned/unknown token is treated identically to
an absent cookie → ``None`` (no internal error raised).
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ...config import Settings


class SessionCookieService:
    """Sign/unsign session ids and read/write the session cookie (R-3)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._serializer = URLSafeTimedSerializer(
            settings.session_signing_key,
            salt="fid-session",
        )

    @property
    def cookie_name(self) -> str:
        return self._settings.session_cookie_name

    def sign(self, session_id: uuid.UUID) -> str:
        """Return the signed cookie value for a session id."""
        return self._serializer.dumps(str(session_id))

    def unsign(self, token: Optional[str]) -> Optional[uuid.UUID]:
        """Recover the session id from a signed cookie value.

        Returns ``None`` on tamper, expiry, malformed input, or absence —
        never raises (tampered/unknown tokens are treated as an absent cookie).
        """
        if not token:
            return None
        try:
            raw = self._serializer.loads(token)
        except (BadSignature, SignatureExpired):
            return None
        except Exception:  # noqa: BLE001 — boundary: never raise on bad cookie
            return None
        try:
            return uuid.UUID(str(raw))
        except (ValueError, TypeError):
            return None

    def read(self, request: Request) -> Optional[uuid.UUID]:
        """Read and unsign the cookie from a request. ``None`` if absent/invalid."""
        token = request.cookies.get(self.cookie_name)
        return self.unsign(token)

    def set(self, response: Response, session_id: uuid.UUID) -> None:
        """Set the signed session cookie on a response (login)."""
        response.set_cookie(
            key=self.cookie_name,
            value=self.sign(session_id),
            httponly=True,
            samesite="lax",
            secure=self._settings.session_cookie_secure,
            path="/",
        )

    def clear(self, response: Response) -> None:
        """Clear the session cookie on a response (logout)."""
        response.set_cookie(
            key=self.cookie_name,
            value="",
            max_age=0,
            httponly=True,
            samesite="lax",
            secure=self._settings.session_cookie_secure,
            path="/",
        )


__all__ = ["SessionCookieService"]
