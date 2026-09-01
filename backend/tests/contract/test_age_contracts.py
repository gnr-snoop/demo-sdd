"""Contract tests for POST /api/analysis/age (spec 005, T011/T019/T023/T031).

Asserts request/response shapes + status codes per
``specs/005-age-analysis/contracts/analysis-age.md``:
  - T011: 200 success shape (estimatedAge/range.min/range.max integers,
    range invariants, exact PRD §8 disclaimer, model_version
    "mock-age-estimator-v1") — contract assertions 1, 10, 12.
  - T019: 400 capture-quality codes (no_face/multiple_faces/invalid_image/
    insufficient_quality) + 500 internal_error + point-only → derived range +
    range → midpoint + pinned error body shape — contract assertions 2, 3, 5–9, 11.
  - T023: 401 unauthenticated (no cookie / expired / revoked); 401 reserved
    exclusively for unauthenticated (FR-007) — contract assertion 4.
  - T031: SC-011 contract-violation mutation guard.

No GPU, no network, no DB (mock adapters + mock repos seeded in-process).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.adapters.mock import (
    ScriptableMockAgeEstimator,
    ScriptableMockDetector,
    ScriptableMockEmbedder,
)
from face_insight.main import create_auth_app

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

AGE_DISCLAIMER = "La edad es una estimación visual y puede contener un margen de error significativo."

UNAUTHENTICATED_BODY = {
    "error": {
        "code": "unauthenticated",
        "message": "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo.",
    }
}


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def _age_files(image_name: str = "one_face.jpg"):
    payload = fixture_bytes(image_name)
    return {"image": (image_name, payload, "image/jpeg")}


def _onboard_files(identifier="demo@example.com", image_name="one_face.jpg"):
    payload = fixture_bytes(image_name)
    return {"identifier": identifier, "consentAccepted": "true"}, {
        "image": (image_name, payload, "image/jpeg"),
    }


# --- Fixtures --------------------------------------------------------------
@pytest.fixture
async def age_app(tmp_path: Path):
    """App wired with scriptable detector/embedder/age estimator for age tests."""
    from face_insight.adapters.fs.image_storage import FilesystemImageStorage

    app = create_auth_app(
        detector=ScriptableMockDetector(),
        embedder=ScriptableMockEmbedder(),
        age_estimator=ScriptableMockAgeEstimator(),
        session_factory=None,
        image_storage=FilesystemImageStorage(root=tmp_path),
    )
    yield app


@pytest.fixture
async def age_client(age_app):
    transport = ASGITransport(app=age_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _seed_and_login(client, app, identifier="demo@example.com"):
    """Onboard a user + login to obtain a valid session cookie on `client`."""
    data, files = _onboard_files(identifier=identifier)
    onb = await client.post("/api/onboarding", data=data, files=files)
    assert onb.status_code == 201, onb.text
    login = await client.post(
        "/api/auth/face-login", data={"identifier": identifier}, files=files
    )
    assert login.status_code == 200, login.text
    return login.json()["userId"]


async def _age(client, image_name="one_face.jpg"):
    return await client.post("/api/analysis/age", files=_age_files(image_name))


# ==========================================================================
# T011: 200 success shape (contract assertions 1, 10, 12)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_happy_path_shape(age_client, age_app):
    """Contract assertion 1: one-face fixture → 200 with estimatedAge 32,
    range [27,37], invariants, exact disclaimer."""
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"estimatedAge", "range", "disclaimer"}, body
    assert set(body["range"].keys()) == {"min", "max"}
    assert body["estimatedAge"] == 32
    assert body["range"]["min"] == 27
    assert body["range"]["max"] == 37
    # Integer invariants (contract assertion 10).
    assert isinstance(body["estimatedAge"], int)
    assert isinstance(body["range"]["min"], int)
    assert isinstance(body["range"]["max"], int)
    assert body["range"]["min"] >= 0
    assert body["range"]["min"] <= body["estimatedAge"] <= body["range"]["max"]
    # Exact PRD §8 disclaimer (contract assertion 1).
    assert body["disclaimer"] == AGE_DISCLAIMER


@pytest.mark.asyncio
async def test_age_point_only_derives_symmetric_range(age_client, age_app):
    """Contract assertion 2: AGEPOINT fixture → point-only 40 → derived [35,45]."""
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "age_point.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimatedAge"] == 40
    assert body["range"]["min"] == 35
    assert body["range"]["max"] == 45
    assert body["range"]["min"] <= body["estimatedAge"] <= body["range"]["max"]


@pytest.mark.asyncio
async def test_age_range_to_midpoint(age_client, age_app):
    """Contract assertion 3: AGERANGE fixture → range [35,45] → estimatedAge 40."""
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "age_range.jpg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimatedAge"] == 40
    assert body["range"] == {"min": 35, "max": 45}


@pytest.mark.asyncio
async def test_age_model_version_is_mock_age_estimator_v1(age_client, age_app):
    """Contract assertion 12 / FR-017: the mock age estimator reports a stable
    model_version. The HTTP response does not expose model_version, but the
    underlying service is deterministic — assert via app.state."""
    await _seed_and_login(age_client, age_app)
    # The wired age_estimator is ScriptableMockAgeEstimator; its results carry
    # AGE_MODEL_VERSION = "mock-age-estimator-v1" (constants.py).
    from face_insight.adapters.mock.constants import AGE_MODEL_VERSION

    assert AGE_MODEL_VERSION == "mock-age-estimator-v1"
    # Determinism: two calls with the same fixture yield the same response.
    r1 = await _age(age_client, "one_face.jpg")
    r2 = await _age(age_client, "one_face.jpg")
    assert r1.json() == r2.json()


# ==========================================================================
# T019: 400 capture-quality + 500 internal_error + pinned error body
# (contract assertions 5–9, 11)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_no_face_400(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "no_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_face"


@pytest.mark.asyncio
async def test_age_multiple_faces_400(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "multi_face.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "multiple_faces"


@pytest.mark.asyncio
async def test_age_insufficient_quality_400(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "low_quality.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_quality"


@pytest.mark.asyncio
async def test_age_invalid_image_undecodable_400(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "not_an_image.txt")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_age_invalid_image_oversized_400(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "oversized.jpg")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_image"


@pytest.mark.asyncio
async def test_age_port_error_500(age_client, age_app):
    """AGEFAIL marker → ScriptableMockAgeEstimator raises → 500 internal_error."""
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "age_fail.jpg")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


@pytest.mark.parametrize(
    "image_name,expected_status,expected_code",
    [
        ("no_face.jpg", 400, "no_face"),
        ("multi_face.jpg", 400, "multiple_faces"),
        ("low_quality.jpg", 400, "insufficient_quality"),
        ("not_an_image.txt", 400, "invalid_image"),
        ("oversized.jpg", 400, "invalid_image"),
        ("age_fail.jpg", 500, "internal_error"),
    ],
)
@pytest.mark.asyncio
async def test_age_error_body_shape_enforced(
    age_client, age_app, image_name, expected_status, expected_code
):
    """Contract assertion 11 / SC-011: every error uses {"error": {"code", "message"}}."""
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, image_name)
    assert resp.status_code == expected_status
    body = resp.json()
    assert set(body.keys()) == {"error"}, body
    assert set(body["error"].keys()) == {"code", "message"}
    assert body["error"]["code"] == expected_code


@pytest.mark.asyncio
async def test_age_no_result_on_error(age_client, age_app):
    """No age result is produced on any error path (FR-006/FR-007)."""
    await _seed_and_login(age_client, age_app)
    for name in ("no_face.jpg", "multi_face.jpg", "low_quality.jpg", "age_fail.jpg"):
        resp = await _age(age_client, name)
        assert "estimatedAge" not in resp.json(), name


# ==========================================================================
# T023: 401 unauthenticated (no cookie / expired / revoked) — contract assertion 4
# ==========================================================================
@pytest.mark.asyncio
async def test_age_no_cookie_401(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    age_client.cookies.clear()
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json() == UNAUTHENTICATED_BODY


@pytest.mark.asyncio
async def test_age_expired_session_401(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    sm = age_app.state.session_manager
    long_ago = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    from face_insight.domain.entities import AuthSession

    for sid, session in list(sm._sessions.items()):
        sm._sessions[sid] = AuthSession(
            id=session.id,
            user_id=session.user_id,
            created_at=long_ago,
            expires_at=long_ago + timedelta(minutes=1),
            revoked_at=None,
        )
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_age_revoked_session_401(age_client, age_app):
    await _seed_and_login(age_client, age_app)
    logout = await age_client.post("/api/auth/logout")
    assert logout.status_code == 200
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_age_401_reserved_exclusively_for_unauthenticated(age_client, age_app):
    """FR-007: 401 is reserved exclusively for `unauthenticated`."""
    await _seed_and_login(age_client, age_app)
    age_client.cookies.clear()
    resp = await _age(age_client, "one_face.jpg")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


# ==========================================================================
# T011/T031: contract-violation mutation guard (SC-011)
# ==========================================================================
@pytest.mark.asyncio
async def test_age_contract_success_shape_enforced(age_client, age_app):
    """SC-011: a deliberate change to the success shape fails this test.

    This is the live guard: it pins the exact key set + invariants. A deliberate
    rename of ``estimatedAge`` or a broken ``min <= estimatedAge <= max`` invariant
    in the response causes this test to fail.
    """
    await _seed_and_login(age_client, age_app)
    resp = await _age(age_client, "one_face.jpg")
    body = resp.json()
    # Shape pinned exactly.
    assert set(body.keys()) == {"estimatedAge", "range", "disclaimer"}, body
    assert set(body["range"].keys()) == {"min", "max"}
    # Invariants pinned.
    assert isinstance(body["estimatedAge"], int)
    assert isinstance(body["range"]["min"], int)
    assert isinstance(body["range"]["max"], int)
    assert body["range"]["min"] >= 0
    assert body["range"]["min"] <= body["estimatedAge"] <= body["range"]["max"]
    assert body["disclaimer"] == AGE_DISCLAIMER


@pytest.mark.asyncio
async def test_age_invariant_violation_would_fail_unit_test():
    """SC-011 (US5): a deliberate change breaking the ``min <= estimatedAge <= max``
    invariant causes a unit test to fail. This test documents the guard by
    asserting the normalizer upholds the invariant for a representative input;
    the live mutation guard lives in tests/unit/test_age_service.py::TestInvariants."""
    from face_insight.domain.age import normalize_age_result
    from face_insight.domain.result_types import AgeResult

    raw = AgeResult(estimated_age=40, range=(35, 45), model_version="m")
    out = normalize_age_result(raw, half_width=5)
    assert out.range is not None
    lo, hi = out.range
    assert lo >= 0
    assert lo <= out.estimated_age <= hi
