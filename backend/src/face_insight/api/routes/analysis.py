"""Analysis routes (T036/T030): mood and age.

Session-protected via ``require_valid_session`` (spec 003 real gating).
Deterministic mocks (SC-010). Values match the contracts and the mock adapters.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..dependencies import require_valid_session
from ..schemas import AGE_DISCLAIMER, MOOD_DISCLAIMER, AgeResponse, MoodRange, MoodResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/mood", response_model=MoodResponse)
async def analysis_mood(
    image: UploadFile = File(...),
    session=Depends(require_valid_session),
) -> MoodResponse:
    """Estimate mood from a capture (mock)."""
    return MoodResponse(label="neutral", confidence=0.74, disclaimer=MOOD_DISCLAIMER)


@router.post("/age", response_model=AgeResponse)
async def analysis_age(
    image: UploadFile = File(...),
    session=Depends(require_valid_session),
) -> AgeResponse:
    """Estimate age from a capture (mock)."""
    return AgeResponse(
        estimatedAge=32,
        range=MoodRange(min=27, max=37),
        disclaimer=AGE_DISCLAIMER,
    )
