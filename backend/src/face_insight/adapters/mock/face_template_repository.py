"""MockFaceTemplateRepository (T051) — in-memory, one template per user (SC-005)."""

from __future__ import annotations

import uuid
from typing import Optional

from ...domain.entities import FaceTemplate


class MockFaceTemplateRepository:
    """In-memory face-template repository keyed by user id (one per user)."""

    def __init__(self) -> None:
        self._templates: dict[uuid.UUID, FaceTemplate] = {}

    def get_by_user(self, user_id: object) -> Optional[FaceTemplate]:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        return self._templates.get(uid)

    def save(self, template: FaceTemplate) -> FaceTemplate:
        self._templates[template.user_id] = template
        return template

    def delete_by_user(self, user_id: object) -> None:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        self._templates.pop(uid, None)
