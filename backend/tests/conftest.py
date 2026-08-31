"""Pytest fixtures for the contract + domain + integration suites (T059).

No GPU, no network, no real ML models (FR-017, SC-008). The FastAPI app is
driven in-process via httpx ASGITransport.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from face_insight.main import create_app


@pytest.fixture
async def app():
    application = create_app()
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# A stable JPEG-ish payload for multipart uploads in contract tests.
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
SESSION_HEADER = {"X-Session-Id": "00000000-0000-4000-8000-000000000002"}
FIXED_USER_ID = "00000000-0000-4000-8000-000000000001"
