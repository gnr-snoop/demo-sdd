"""DELETE /api/users/{userId}/face-data — real endpoint (spec 006, T011).

Session-protected via ``require_valid_session`` (spec 003 real gating). UUID
path param (FastAPI → 422 on malformed). Delegates the authorization check
(403 forbidden), existence guard (404 not_found), atomic DB deletion, and
best-effort filesystem cleanup to ``DeletionService`` (spec 006). Clears the
session cookie on the 200 response (FR-006).

Condition evaluation order (R-4): 422 (FastAPI path validation) → 401
(require_valid_session) → 403 (authz, in service) → 404 (existence, in service)
→ deletion → cookie clear → 200.
"""

from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..dependencies import get_deletion_service, require_valid_session
from ..schemas import DeleteFaceDataResponse
from ...logging import get_logger

router = APIRouter(prefix="/api/users", tags=["users"])
logger = get_logger("face_insight.users")


@router.delete("/{user_id}/face-data", response_model=DeleteFaceDataResponse)
async def delete_face_data(
    user_id: UUID,
    request: Request,
    session=Depends(require_valid_session),
) -> JSONResponse:
    """Delete the face template and onboarding data for a user (spec 006).

    ``user_id`` is validated as a UUID v4 by FastAPI (422 on malformed input).
    Requires a valid session (401 unauthenticated) whose ``user_id`` matches
    the path ``user_id`` (403 forbidden on mismatch). On success: hard-deletes
    User/FaceTemplate/AuthSession in one transaction, best-effort deletes the
    ``usuarios/<user-id>/`` folder, clears the session cookie, and returns
    ``200 {userId, status: "deleted"}``.
    """
    started = time.monotonic()
    deletion_service = get_deletion_service(request)
    # DeletionService enforces authz (Forbidden → 403) + existence (NotFound →
    # 404) + atomic DB deletion (DeletionInternalError → 500) + best-effort FS.
    result = await deletion_service.delete_face_data(user_id, session.user_id)

    # Cookie clear on the 200 response (FR-006) — the current AuthSession is
    # among the rows deleted, so the cookie must be invalidated.
    response = JSONResponse(
        status_code=200,
        content={"userId": str(result.user_id), "status": result.status},
    )
    cookie_service = request.app.state.session_cookie_service
    cookie_service.clear(response)

    logger.info(
        "deletion.response",
        user_id=str(result.user_id),
        status=result.status,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return response
