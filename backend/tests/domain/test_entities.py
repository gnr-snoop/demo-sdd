"""Domain entity tests (T062, FR-017).

Entity construction, UUID v4 ids, enum validation, injected ``now``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from face_insight.domain.entities import (
    AnalysisRequest,
    AnalysisStatus,
    AnalysisType,
    AuthSession,
    FaceTemplate,
    User,
    UserStatus,
    create_analysis_request,
    create_auth_session,
    create_face_template,
    create_session,
    create_user,
)


def fixed_now() -> datetime:
    return datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)


def test_create_user_generates_uuid_v4_id():
    user = create_user("demo@example.com", now=fixed_now)
    assert isinstance(user.id, uuid.UUID)
    assert user.id.version == 4


def test_create_user_defaults_to_enrolled():
    user = create_user("demo@example.com", now=fixed_now)
    assert user.status == UserStatus.enrolled
    assert user.status.value == "enrolled"


def test_create_user_injected_now():
    user = create_user("demo@example.com", now=fixed_now)
    assert user.created_at == fixed_now()
    assert user.updated_at == fixed_now()


def test_user_rejects_empty_identifier():
    with pytest.raises(ValueError):
        create_user("", now=fixed_now)
    with pytest.raises(ValueError):
        create_user("   ", now=fixed_now)


def test_user_status_enum_values():
    assert {s.value for s in UserStatus} == {"enrolled", "active", "disabled"}


def test_create_face_template_uuid_v4():
    user = create_user("demo@example.com", now=fixed_now)
    tpl = create_face_template(user.id, [0.1] * 128, "mock-embed-v0", now=fixed_now)
    assert tpl.id.version == 4
    assert tpl.user_id == user.id
    assert len(tpl.embedding) == 128


def test_face_template_rejects_empty_embedding():
    user = create_user("demo@example.com", now=fixed_now)
    with pytest.raises(ValueError):
        create_face_template(user.id, [], "mock-embed-v0", now=fixed_now)


def test_create_auth_session_expires_after_created():
    user = create_user("demo@example.com", now=fixed_now)
    session = create_auth_session(user.id, ttl_seconds=3600, now=fixed_now)
    assert session.id.version == 4
    assert session.expires_at > session.created_at
    assert session.revoked_at is None


def test_auth_session_rejects_non_positive_ttl():
    user = create_user("demo@example.com", now=fixed_now)
    # The positive-lifetime guard lives in the create_session factory (spec 003):
    # a non-positive lifetime is rejected at creation time.
    with pytest.raises(ValueError):
        create_session(user.id, now=fixed_now(), lifetime=timedelta(0))
    with pytest.raises(ValueError):
        create_session(user.id, now=fixed_now(), lifetime=timedelta(seconds=-1))


def test_auth_session_allows_rehydration_with_past_expires_at():
    """A persisted row whose expires_at was moved into the past out-of-band
    (e.g. the quickstart's manual expiry UPDATE) must rehydrate without error;
    validity is governed by is_valid(now), not by construction (spec 003)."""
    user = create_user("demo@example.com", now=fixed_now)
    created = fixed_now()
    session = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        created_at=created,
        expires_at=created - timedelta(minutes=1),  # expired out-of-band
    )
    assert session.is_valid(created) is False  # now after expires_at → invalid
    # Equal timestamps (the original non-positive-ttl shape) also rehydrate.
    equal = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        created_at=created,
        expires_at=created,
    )
    assert equal.is_valid(created) is False


def test_analysis_request_enum_validation():
    user = create_user("demo@example.com", now=fixed_now)
    req = create_analysis_request(user.id, AnalysisType.mood, "mock-mood-v0", now=fixed_now)
    assert req.id.version == 4
    assert req.type == AnalysisType.mood
    assert req.status == AnalysisStatus.pending


def test_analysis_type_enum_values():
    assert {t.value for t in AnalysisType} == {"mood", "age"}


def test_analysis_status_enum_values():
    assert {s.value for s in AnalysisStatus} == {"pending", "completed", "failed"}


def test_analysis_request_rejects_invalid_type():
    user = create_user("demo@example.com", now=fixed_now)
    with pytest.raises(ValueError):
        AnalysisRequest(
            id=uuid.uuid4(),
            user_id=user.id,
            type="bogus",  # type: ignore[arg-type]
            model_version="v0",
            created_at=fixed_now(),
        )
