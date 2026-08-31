"""SQLAlchemy repository adapters implementing the domain ports (T056).

These are the real DB-backed adapters (async). In Fase 1 the mock adapters are
the default wiring (T052); these adapters are established here so specs 002+
can swap them in. They implement the capability surface of
``UserRepository`` / ``FaceTemplateRepository`` (the Protocols are name-based).
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...domain.entities import FaceTemplate, User, UserStatus
from ...domain.onboarding import IdentifierTaken
from .models import AnalysisRequestORM, AuthSessionORM, FaceTemplateORM, UserORM


def _to_user(orm: UserORM) -> User:
    return User(
        id=orm.id,
        identifier=orm.identifier,
        status=UserStatus(orm.status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_template(orm: FaceTemplateORM) -> FaceTemplate:
    return FaceTemplate(
        id=orm.id,
        user_id=orm.user_id,
        embedding=list(orm.embedding),
        model_version=orm.model_version,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SqlAlchemyUserRepository:
    """Async UserRepository backed by SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, user_id: object) -> Optional[User]:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        async with self._session_factory() as session:
            orm = await session.get(UserORM, uid)
            return _to_user(orm) if orm else None

    async def get_by_identifier(self, identifier: str) -> Optional[User]:
        async with self._session_factory() as session:
            stmt = select(UserORM).where(UserORM.identifier == identifier)
            orm = (await session.execute(stmt)).scalar_one_or_none()
            return _to_user(orm) if orm else None

    async def save(self, user: User) -> User:
        async with self._session_factory() as session:
            orm = await session.get(UserORM, user.id)
            if orm is None:
                orm = UserORM(
                    id=user.id,
                    identifier=user.identifier,
                    status=user.status.value,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
                session.add(orm)
            else:
                orm.identifier = user.identifier
                orm.status = user.status.value
                orm.updated_at = user.updated_at
            await session.commit()
            return _to_user(orm)

    async def delete(self, user_id: object) -> None:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        async with self._session_factory() as session:
            orm = await session.get(UserORM, uid)
            if orm is not None:
                await session.delete(orm)
                await session.commit()


class SqlAlchemyFaceTemplateRepository:
    """Async FaceTemplateRepository backed by SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_user(self, user_id: object) -> Optional[FaceTemplate]:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        async with self._session_factory() as session:
            stmt = select(FaceTemplateORM).where(FaceTemplateORM.user_id == uid)
            orm = (await session.execute(stmt)).scalar_one_or_none()
            return _to_template(orm) if orm else None

    async def save(self, template: FaceTemplate) -> FaceTemplate:
        async with self._session_factory() as session:
            stmt = select(FaceTemplateORM).where(FaceTemplateORM.user_id == template.user_id)
            orm = (await session.execute(stmt)).scalar_one_or_none()
            if orm is None:
                orm = FaceTemplateORM(
                    id=template.id,
                    user_id=template.user_id,
                    embedding=template.embedding,
                    model_version=template.model_version,
                    created_at=template.created_at,
                    updated_at=template.updated_at,
                )
                session.add(orm)
            else:
                orm.embedding = template.embedding
                orm.model_version = template.model_version
                orm.updated_at = template.updated_at
            await session.commit()
            return _to_template(orm)

    async def delete_by_user(self, user_id: object) -> None:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        async with self._session_factory() as session:
            stmt = select(FaceTemplateORM).where(FaceTemplateORM.user_id == uid)
            orm = (await session.execute(stmt)).scalar_one_or_none()
            if orm is not None:
                await session.delete(orm)
                await session.commit()


class SqlAlchemyUnitOfWork:
    """Atomic unit-of-work for User + FaceTemplate persistence (T010, R-5).

    Wraps both inserts in a single async SQLAlchemy session/transaction. On
    ``IntegrityError`` (e.g. duplicate normalized identifier) the transaction
    rolls back and :class:`IdentifierTaken` is raised so the route handler can
    map it to ``409 identifier_taken``.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_user_with_template(self, user: User, template: FaceTemplate) -> None:
        async with self._session_factory() as session:
            try:
                user_orm = UserORM(
                    id=user.id,
                    identifier=user.identifier,
                    status=user.status.value,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
                template_orm = FaceTemplateORM(
                    id=template.id,
                    user_id=template.user_id,
                    embedding=template.embedding,
                    model_version=template.model_version,
                    created_at=template.created_at,
                    updated_at=template.updated_at,
                )
                session.add(user_orm)
                session.add(template_orm)
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise IdentifierTaken(user.identifier) from exc
