"""Domain entities (T041, PRD §7, data-model.md).

Pure: no infra/ML imports. Identity is domain-owned (``uuid.uuid4()`` in
factories; fixed constants in mock adapters/tests). Entity factories accept an
injected ``now`` callable for deterministic timestamps (research R-5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional


# --- Enumerations (data-model.md) ------------------------------------------
class UserStatus(str, Enum):
    enrolled = "enrolled"
    active = "active"
    disabled = "disabled"


class AnalysisType(str, Enum):
    mood = "mood"
    age = "age"


class AnalysisStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


def _now_utc() -> datetime:
    return datetime.now(tz=None)


# --- Entities --------------------------------------------------------------
@dataclass(frozen=True)
class User:
    id: uuid.UUID
    identifier: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.identifier or not self.identifier.strip():
            raise ValueError("identifier must be non-empty")
        if not isinstance(self.status, UserStatus):
            raise ValueError(f"status must be a UserStatus, got {self.status!r}")


@dataclass(frozen=True)
class FaceTemplate:
    id: uuid.UUID
    user_id: uuid.UUID
    embedding: list[float]
    model_version: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.embedding:
            raise ValueError("embedding must be non-empty")
        if not self.model_version:
            raise ValueError("model_version must be non-empty")


@dataclass(frozen=True)
class AuthSession:
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        # No ordering invariant between created_at and expires_at: a persisted
        # row whose expires_at was moved into the past out-of-band (e.g. the
        # quickstart's `UPDATE auth_sessions SET expires_at = now() - interval
        # '1 minute'`) must rehydrate without error. Validity is governed by
        # is_valid(now), not by construction. The positive-lifetime guarantee
        # for freshly created sessions is enforced in create_session below.
        return None

    def is_valid(self, now: datetime) -> bool:
        """Return True iff this session is currently valid (FR-006).

        Valid iff ``revoked_at IS NULL AND expires_at > now``. All four invalid
        cases (expired, revoked, unknown id, absent cookie) collapse to False
        here; the session-gating dependency maps False → ``401 unauthenticated``.
        """
        return self.revoked_at is None and self.expires_at > now


@dataclass(frozen=True)
class AnalysisRequest:
    id: uuid.UUID
    user_id: uuid.UUID
    type: AnalysisType
    model_version: str
    created_at: datetime
    status: AnalysisStatus = AnalysisStatus.pending

    def __post_init__(self) -> None:
        if not isinstance(self.type, AnalysisType):
            raise ValueError(f"type must be an AnalysisType, got {self.type!r}")
        if not isinstance(self.status, AnalysisStatus):
            raise ValueError(f"status must be an AnalysisStatus, got {self.status!r}")
        if not self.model_version:
            raise ValueError("model_version must be non-empty")


# --- Factories (domain owns identity; injected `now`) ----------------------
def create_user(
    identifier: str,
    now: Callable[[], datetime] = _now_utc,
    status: UserStatus = UserStatus.enrolled,
    user_id: Optional[uuid.UUID] = None,
) -> User:
    ts = now()
    return User(
        id=user_id or uuid.uuid4(),
        identifier=identifier,
        status=status,
        created_at=ts,
        updated_at=ts,
    )


def create_face_template(
    user_id: uuid.UUID,
    embedding: list[float],
    model_version: str,
    now: Callable[[], datetime] = _now_utc,
    template_id: Optional[uuid.UUID] = None,
) -> FaceTemplate:
    ts = now()
    return FaceTemplate(
        id=template_id or uuid.uuid4(),
        user_id=user_id,
        embedding=embedding,
        model_version=model_version,
        created_at=ts,
        updated_at=ts,
    )


def create_auth_session(
    user_id: uuid.UUID,
    ttl_seconds: int = 3600,
    now: Callable[[], datetime] = _now_utc,
    session_id: Optional[uuid.UUID] = None,
) -> AuthSession:
    created = now()
    expires = created + timedelta(seconds=ttl_seconds)
    return AuthSession(
        id=session_id or uuid.uuid4(),
        user_id=user_id,
        created_at=created,
        expires_at=expires,
    )


def create_session(
    user_id: uuid.UUID,
    now: datetime,
    lifetime: timedelta,
    session_id: Optional[uuid.UUID] = None,
) -> AuthSession:
    """Factory for an AuthSession from an explicit ``now`` + ``lifetime`` (spec 003, R-2).

    Used by the ``SessionManager.create`` port implementation: the manager
    injects ``now`` (for deterministic tests) and the configured ``lifetime``
    (``SESSION_LIFETIME_SECONDS``). The session starts un-revoked.
    """
    if lifetime <= timedelta(0):
        raise ValueError("lifetime must be positive")
    return AuthSession(
        id=session_id or uuid.uuid4(),
        user_id=user_id,
        created_at=now,
        expires_at=now + lifetime,
    )


def create_analysis_request(
    user_id: uuid.UUID,
    type: AnalysisType,
    model_version: str,
    now: Callable[[], datetime] = _now_utc,
    status: AnalysisStatus = AnalysisStatus.pending,
    request_id: Optional[uuid.UUID] = None,
) -> AnalysisRequest:
    return AnalysisRequest(
        id=request_id or uuid.uuid4(),
        user_id=user_id,
        type=type,
        model_version=model_version,
        created_at=now(),
        status=status,
    )
