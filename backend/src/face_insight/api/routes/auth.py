"""Auth routes (T035): face-login, me, logout.

All deterministic mocks (SC-010). Login failure is generic and non-revealing
(FR-007/FR-018, T039).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ..dependencies import require_session
from ..schemas import FIXED_EXPIRES_AT, FIXED_USER_ID, AuthMeResponse, FaceLoginResponse, LogoutResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Sentinel image content that triggers the mock failure path (test affordance).
# The failure message is identical regardless of the trigger (non-revealing).
_FAIL_SENTINEL = b"MOCK_FAIL"
_GENERIC_AUTH_FAILURE = JSONResponse(
    status_code=401,
    content={"detail": "authentication failed"},
)


@router.post("/face-login", response_model=FaceLoginResponse)
async def face_login(
    identifier: str = Form(...),
    image: UploadFile = File(...),
) -> FaceLoginResponse | JSONResponse:
    """Verify a face and create a session (mock).

    Mock success path: returns 200 with the authenticated user. Mock failure
    path: triggered by an image whose content is the ``MOCK_FAIL`` sentinel;
    returns 401 with a generic, non-revealing message (FR-007/FR-018).
    """
    content = await image.read()
    if content == _FAIL_SENTINEL:
        return _GENERIC_AUTH_FAILURE
    return FaceLoginResponse(userId=FIXED_USER_ID, status="authenticated")


@router.get("/me", response_model=AuthMeResponse)
async def me(session_id: str = Depends(require_session)) -> AuthMeResponse:
    """Return the current session state (mock)."""
    return AuthMeResponse(
        userId=FIXED_USER_ID,
        status="authenticated",
        expiresAt=FIXED_EXPIRES_AT,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(session_id: str = Depends(require_session)) -> LogoutResponse:
    """Invalidate the current session (mock)."""
    return LogoutResponse(status="logged_out")
