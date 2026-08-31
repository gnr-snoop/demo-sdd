"""Unit test for session validity rules (T026, spec 003 US3, FR-006).

Covers AuthSession.is_valid() for: valid, expired, revoked, and the
SessionManager.get_valid collapsing of unknown id / absent cookie.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from face_insight.adapters.mock import MockSessionManager
from face_insight.domain.entities import AuthSession, create_session


NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
LIFETIME = timedelta(seconds=1800)


def test_is_valid_true_for_fresh_unrevoked_session():
    session = create_session(uuid.uuid4(), NOW, LIFETIME)
    assert session.is_valid(NOW) is True
    assert session.is_valid(NOW + timedelta(minutes=29)) is True


def test_is_valid_false_when_expired():
    session = create_session(uuid.uuid4(), NOW, LIFETIME)
    later = NOW + LIFETIME + timedelta(seconds=1)
    assert session.is_valid(later) is False


def test_is_valid_false_when_revoked():
    session = create_session(uuid.uuid4(), NOW, LIFETIME)
    revoked = AuthSession(
        id=session.id,
        user_id=session.user_id,
        created_at=session.created_at,
        expires_at=session.expires_at,
        revoked_at=NOW + timedelta(minutes=1),
    )
    assert revoked.is_valid(NOW + timedelta(minutes=2)) is False


def test_is_valid_false_at_exact_expiry_boundary():
    """expires_at == now is NOT valid (strict >)."""
    session = create_session(uuid.uuid4(), NOW, LIFETIME)
    assert session.is_valid(NOW + LIFETIME) is False


@pytest.mark.asyncio
async def test_session_manager_get_valid_returns_none_for_unknown_id():
    sm = MockSessionManager()
    result = await sm.get_valid(uuid.uuid4(), NOW)
    assert result is None


@pytest.mark.asyncio
async def test_session_manager_get_valid_returns_session_for_valid_id():
    sm = MockSessionManager()
    user_id = uuid.uuid4()
    session = await sm.create(user_id, NOW, LIFETIME)
    result = await sm.get_valid(session.id, NOW)
    assert result is not None
    assert result.id == session.id


@pytest.mark.asyncio
async def test_session_manager_get_valid_returns_none_for_expired():
    sm = MockSessionManager()
    user_id = uuid.uuid4()
    session = await sm.create(user_id, NOW, LIFETIME)
    later = NOW + LIFETIME + timedelta(seconds=1)
    result = await sm.get_valid(session.id, later)
    assert result is None


@pytest.mark.asyncio
async def test_session_manager_get_valid_returns_none_for_revoked():
    sm = MockSessionManager()
    user_id = uuid.uuid4()
    session = await sm.create(user_id, NOW, LIFETIME)
    await sm.revoke(session.id, NOW + timedelta(minutes=1))
    result = await sm.get_valid(session.id, NOW + timedelta(minutes=2))
    assert result is None


@pytest.mark.asyncio
async def test_session_manager_revoke_is_idempotent():
    sm = MockSessionManager()
    user_id = uuid.uuid4()
    session = await sm.create(user_id, NOW, LIFETIME)
    await sm.revoke(session.id, NOW + timedelta(minutes=1))
    await sm.revoke(session.id, NOW + timedelta(minutes=2))  # no-op
    result = await sm.get_valid(session.id, NOW)
    assert result is None
