"""MockSessionManager (T049) — in-memory, deterministic (SC-005)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from ...domain.entities import AuthSession, create_auth_session
from .constants import FIXED_NOW, FIXED_SESSION_ID, FIXED_USER_ID

_DEFAULT_TTL = 3600


class MockSessionManager:
    """In-memory session manager backed by a dict.

    Deterministic: ``create`` for the fixed user returns the fixed session id
    and a timestamp derived from the injected fixed ``now``.
    """

    def __init__(self, now: Optional[datetime] = None, ttl_seconds: int = _DEFAULT_TTL) -> None:
        self._now = now or FIXED_NOW
        self._ttl = ttl_seconds
        self._sessions: dict[uuid.UUID, AuthSession] = {}

    def create(self, user_id: object) -> AuthSession:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        session_id = FIXED_SESSION_ID if uid == FIXED_USER_ID else uuid.uuid4()
        session = create_auth_session(
            user_id=uid,
            ttl_seconds=self._ttl,
            now=lambda: self._now,
            session_id=session_id,
        )
        self._sessions[session.id] = session
        return session

    def get(self, session_id: object) -> Optional[AuthSession]:
        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
        return self._sessions.get(sid)

    def revoke(self, session_id: object) -> None:
        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
        session = self._sessions.get(sid)
        if session is not None:
            self._sessions[sid] = AuthSession(
                id=session.id,
                user_id=session.user_id,
                created_at=session.created_at,
                expires_at=session.expires_at,
                revoked_at=self._now,
            )

    def is_active(self, session_id: object) -> bool:
        session = self.get(session_id)
        if session is None:
            return False
        return session.revoked_at is None and self._now < session.expires_at
