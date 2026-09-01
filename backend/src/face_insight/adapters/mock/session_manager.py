"""MockSessionManager (T049, spec 003) — in-memory, deterministic (SC-005).

Implements the spec 003 ``SessionManager`` port: ``create(user_id, now, lifetime)``,
``get_valid(session_id, now)``, ``revoke(session_id, now)``. Deterministic: the
fixed user gets the fixed session id when created with the fixed ``now``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from ...domain.entities import AuthSession, create_session
from .constants import FIXED_NOW, FIXED_SESSION_ID, FIXED_USER_ID


class MockSessionManager:
    """In-memory session manager backed by a dict (spec 003 port)."""

    def __init__(self, now: Optional[datetime] = None) -> None:
        self._default_now = now or FIXED_NOW
        self._sessions: dict[uuid.UUID, AuthSession] = {}

    async def create(self, user_id: uuid.UUID, now: datetime, lifetime: timedelta) -> AuthSession:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        session_id = FIXED_SESSION_ID if uid == FIXED_USER_ID and now == self._default_now else uuid.uuid4()
        session = create_session(user_id=uid, now=now, lifetime=lifetime, session_id=session_id)
        self._sessions[session.id] = session
        return session

    async def get_valid(self, session_id: uuid.UUID, now: datetime) -> Optional[AuthSession]:
        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
        session = self._sessions.get(sid)
        if session is None:
            return None
        return session if session.is_valid(now) else None

    async def revoke(self, session_id: uuid.UUID, now: datetime) -> None:
        sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
        session = self._sessions.get(sid)
        if session is not None and session.revoked_at is None:
            self._sessions[sid] = AuthSession(
                id=session.id,
                user_id=session.user_id,
                created_at=session.created_at,
                expires_at=session.expires_at,
                revoked_at=now,
            )

    async def delete_by_user(self, user_id: object) -> None:
        """Remove ALL AuthSession rows for a user (spec 006 mock helper).

        Mock-adapter convenience (NOT a port method — research R-2 explicitly
        adds no ``SessionManager.delete_by_user`` port). Used by
        ``MockUnitOfWork.delete_user_face_data`` to delete sessions in the same
        logical transaction as FaceTemplate/User for domain tests.
        """
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        for sid, session in list(self._sessions.items()):
            if session.user_id == uid:
                del self._sessions[sid]


__all__ = ["MockSessionManager"]
