"""POST /api/onboarding — stub endpoint (T034).

Deterministic mock; no real onboarding logic (SC-010).
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ..schemas import FIXED_USER_ID, OnboardingResponse

router = APIRouter(prefix="/api", tags=["onboarding"])


@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
async def onboarding(
    identifier: str = Form(...),
    consentAccepted: bool = Form(...),
    image: UploadFile = File(...),
) -> OnboardingResponse:
    """Register a person and process their face (mock).

    Returns a deterministic 201 with the enrolled user. Image validation
    (size/format/dims) is deferred to spec 002; here we only require the field
    be present (FastAPI returns 422 when missing).
    """
    if not consentAccepted:
        # FastAPI bool Form parsing already rejects non-bool; explicit 422 for
        # consent == false per contract.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": ["body", "consentAccepted"],
                        "msg": "consent must be accepted (true)",
                        "type": "value_error",
                    }
                ]
            },
        )
    return OnboardingResponse(userId=FIXED_USER_ID, identifier=identifier, status="enrolled")
