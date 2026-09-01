"""MockUnitOfWork (spec 006, T008) — in-memory atomic deletion for domain tests.

Records the deletion call and the dependents-before-parent ordering so
``tests/unit/test_deletion_service.py`` can assert FaceTemplate → AuthSession
→ User. No DB, no GPU, no network (SC-010).
"""

from __future__ import annotations

import uuid


class MockUnitOfWork:
    """In-memory unit-of-work for deletion (domain test double).

    Holds references to the mock user repository, face-template repository,
    and session manager. ``delete_user_face_data`` deletes in the pinned
    order (FaceTemplate → AuthSession → User) and records the order in
    ``deletion_order`` for test assertions.
    """

    def __init__(self, user_repository, face_template_repository, session_manager) -> None:
        self._users = user_repository
        self._templates = face_template_repository
        self._sessions = session_manager
        self.deletion_order: list[str] = []
        self.called: bool = False
        self.last_user_id: object | None = None

    async def delete_user_face_data(self, user_id: object) -> None:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        self.called = True
        self.last_user_id = uid
        # Dependents first, then parent (matches SqlAlchemyUnitOfWork ordering).
        await self._templates.delete_by_user(uid)
        self.deletion_order.append("face_template")
        await self._sessions.delete_by_user(uid)
        self.deletion_order.append("auth_session")
        await self._users.delete(uid)
        self.deletion_order.append("user")


__all__ = ["MockUnitOfWork"]
