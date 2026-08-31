"""Integration smoke test: stack health endpoints (US1, T021)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.main import create_app


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_returns_healthy(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_readyz_endpoint_shape(client: AsyncClient) -> None:
    """readyz always returns the documented shape; db flag reflects connectivity."""
    resp = await client.get("/readyz")
    body = resp.json()
    assert set(body.keys()) == {"status", "db"}
    assert isinstance(body["db"], bool)
    # Without a live DB the probe reports 503; with a live DB it reports 200.
    if body["db"]:
        assert resp.status_code == 200
        assert body["status"] == "ready"
    else:
        assert resp.status_code == 503
        assert body["status"] == "unavailable"
