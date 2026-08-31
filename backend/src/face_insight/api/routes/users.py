"""DELETE /api/users/{userId}/face-data — stub endpoint (T037/T031).

Session-protected via ``require_valid_session`` (spec 003 real gating).
UUID path param, mock success (SC-010). No real deletion.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from ..dependencies import require_valid_session
from ..schemas import DeleteFaceDataResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.delete("/{user_id}/face-data", response_model=DeleteFaceDataResponse)
async def delete_face_data(
    user_id: UUID,
    session=Depends(require_valid_session),
) -> DeleteFaceDataResponse:
    """Delete the face template and onboarding data for a user (mock).

    ``user_id`` is validated as a UUID v4 by FastAPI (422 on malformed input).
    No real DB/filesystem deletion in Fase 1 (SC-010).
    """
    return DeleteFaceDataResponse(userId=str(user_id), status="deleted")
