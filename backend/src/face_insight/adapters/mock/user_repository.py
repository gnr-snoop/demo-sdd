"""MockUserRepository (T050) — in-memory dict, deterministic (SC-005)."""

from __future__ import annotations

import uuid
from typing import Optional

from ...domain.entities import User, UserStatus, create_user
from .constants import FIXED_NOW, FIXED_USER_ID


class MockUserRepository:
    """In-memory user repository.

    Saving a new user without an explicit id assigns the fixed user id
    (data-model.md). Pre-seeded with nothing by default.
    """

    def __init__(self, now: Optional[object] = None) -> None:
        self._now = now or FIXED_NOW
        self._users: dict[uuid.UUID, User] = {}

    async def get(self, user_id: object) -> Optional[User]:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        return self._users.get(uid)

    async def get_by_identifier(self, identifier: str) -> Optional[User]:
        for user in self._users.values():
            if user.identifier == identifier:
                return user
        return None

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user

    async def delete(self, user_id: object) -> None:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        self._users.pop(uid, None)

    async def seed_fixed_user(self, identifier: str = "demo@example.com") -> User:
        """Seed the deterministic fixed user (test helper)."""
        user = create_user(
            identifier=identifier,
            now=lambda: self._now,  # type: ignore[arg-type]
            status=UserStatus.enrolled,
            user_id=FIXED_USER_ID,
        )
        return await self.save(user)
