"""Domain ports (T043) — 8 ``typing.Protocol`` interfaces (data-model.md).

The domain declares the capabilities it needs; mock adapters (Fase 1) and real
adapters (Fase 5) implement these protocols. Composition happens in ``main.py``,
not in the domain (research R-1).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from .entities import AnalysisRequest, AuthSession, FaceTemplate, User
from .result_types import AgeResult, DetectionResult, Embedding, MoodResult


@runtime_checkable
class Detector(Protocol):
    def detect(self, image: bytes) -> DetectionResult: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, face_image: bytes) -> Embedding: ...


@runtime_checkable
class AgeEstimator(Protocol):
    def estimate_age(self, face_image: bytes) -> AgeResult: ...


@runtime_checkable
class MoodEstimator(Protocol):
    def estimate_mood(self, face_image: bytes) -> MoodResult: ...


@runtime_checkable
class Comparison(Protocol):
    """1:1 face-embedding comparison port (spec 003, R-1).

    Implementations return cosine similarity in [-1, 1]. A dimension mismatch
    raises ``ComparisonError`` (mapped to ``internal_error`` by the use-case).
    """

    def compare(self, a: list[float], b: list[float]) -> float: ...


@runtime_checkable
class SessionManager(Protocol):
    """Server-side AuthSession lifecycle port (spec 003, R-2).

    ``get_valid`` returns the row iff it exists, ``revoked_at IS NULL``, and
    ``expires_at > now``; otherwise ``None``. ``revoke`` is idempotent.
    """

    async def create(self, user_id: UUID, now: datetime, lifetime: timedelta) -> AuthSession: ...

    async def get_valid(self, session_id: UUID, now: datetime) -> Optional[AuthSession]: ...

    async def revoke(self, session_id: UUID, now: datetime) -> None: ...


@runtime_checkable
class UserRepository(Protocol):
    async def get(self, user_id: object) -> Optional[User]: ...
    async def get_by_identifier(self, identifier: str) -> Optional[User]: ...
    async def save(self, user: User) -> User: ...
    async def delete(self, user_id: object) -> None: ...


@runtime_checkable
class FaceTemplateRepository(Protocol):
    async def get_by_user(self, user_id: object) -> Optional[FaceTemplate]: ...
    async def save(self, template: FaceTemplate) -> FaceTemplate: ...
    async def delete_by_user(self, user_id: object) -> None: ...


@runtime_checkable
class ImageStorage(Protocol):
    def store(self, user_id: object, image_bytes: bytes) -> str: ...
    def read(self, user_id: object) -> bytes: ...
    def delete(self, user_id: object) -> None: ...
