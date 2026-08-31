"""Analysis routes (T036): mood and age.

Session-protected, deterministic mocks (SC-010). Values match the contracts and
the mock adapters (SC-005).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..dependencies import require_session
from ..schemas import AGE_DISCLAIMER, MOOD_DISCLAIMER, AgeResponse, MoodRange, MoodResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/mood", response_model=MoodResponse)
async def analysis_mood(
    image: UploadFile = File(...),
    session_id: str = Depends(require_session),
) -> MoodResponse:
    """Estimate mood from a capture (mock)."""
    return MoodResponse(label="neutral", confidence=0.74, disclaimer=MOOD_DISCLAIMER)


@router.post("/age", response_model=AgeResponse)
async def analysis_age(
    image: UploadFile = File(...),
    session_id: str = Depends(require_session),
) -> AgeResponse:
    """Estimate age from a capture (mock)."""
    return AgeResponse(
        estimatedAge=32,
        range=MoodRange(min=27, max=37),
        disclaimer=AGE_DISCLAIMER,
    )
