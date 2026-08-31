"""SqlAlchemySessionManager — async DB adapter for the SessionManager port (T009, R-2).

Implements ``create`` / ``get_valid`` / ``revoke`` against the existing
``auth_sessions`` table (spec 001 migration). ``get_valid`` returns the row iff
``revoked_at IS NULL AND expires_at > now``; ``revoke`` is idempotent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...domain.entities import AuthSession, create_session
from .models import AuthSessionORM


def _to_session(orm: AuthSessionORM) -> AuthSession:
    return AuthSession(
        id=orm.id,
        user_id=orm.user_id,
        created_at=orm.created_at,
        expires_at=orm.expires_at,
        revoked_at=orm.revoked_at,
    )


class SqlAlchemySessionManager:
    """Async SessionManager backed by SQLAlchemy (spec 003, R-2)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, user_id: uuid.UUID, now: datetime, lifetime: timedelta) -> AuthSession:
        session = create_session(user_id, now, lifetime)
        async with self._session_factory() as db:
            orm = AuthSessionORM(
                id=session.id,
                user_id=session.user_id,
                created_at=session.created_at,
                expires_at=session.expires_at,
                revoked_at=None,
            )
            db.add(orm)
            await db.commit()
        return session

    async def get_valid(self, session_id: uuid.UUID, now: datetime) -> Optional[AuthSession]:
        sid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
        async with self._session_factory() as db:
            stmt = select(AuthSessionORM).where(AuthSessionORM.id == sid)
            orm = (await db.execute(stmt)).scalar_one_or_none()
            if orm is None:
                return None
            session = _to_session(orm)
            return session if session.is_valid(now) else None

    async def revoke(self, session_id: uuid.UUID, now: datetime) -> None:
        sid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
        async with self._session_factory() as db:
            stmt = (
                update(AuthSessionORM)
                .where(AuthSessionORM.id == sid, AuthSessionORM.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await db.execute(stmt)
            await db.commit()


__all__ = ["SqlAlchemySessionManager"]
