"""Pydantic v2 request/response schemas for the 7 contract endpoints (T032).

Shapes match ``specs/001-skeleton-contracts-mocks/contracts/*.md`` exactly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Onboarding (POST /api/onboarding) -------------------------------------
class OnboardingResponse(BaseModel):
    userId: str
    identifier: str
    status: str = "enrolled"


# --- Face login (POST /api/auth/face-login) --------------------------------
class FaceLoginResponse(BaseModel):
    userId: str
    status: str = "authenticated"


# --- Auth me (GET /api/auth/me) --------------------------------------------
class AuthMeResponse(BaseModel):
    userId: str
    status: str = "authenticated"
    expiresAt: str


# --- Logout (POST /api/auth/logout) ----------------------------------------
class LogoutResponse(BaseModel):
    status: str = "logged_out"


# --- Analysis: mood (POST /api/analysis/mood) ------------------------------
class MoodRange(BaseModel):
    min: int
    max: int


class MoodResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    disclaimer: str


# --- Analysis: age (POST /api/analysis/age) --------------------------------
class AgeResponse(BaseModel):
    estimatedAge: int
    range: MoodRange
    disclaimer: str


# --- Delete face data (DELETE /api/users/{userId}/face-data) ---------------
class DeleteFaceDataResponse(BaseModel):
    userId: str
    status: str = "deleted"


# --- Error shapes ----------------------------------------------------------
class ErrorDetail(BaseModel):
    detail: str


# Spec 002 error response shape: {"error": {"code": "...", "message": "..."}} (R-7).
class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# Fixed mock constants (SC-005 determinism). Match contracts/*.md exactly.
FIXED_USER_ID = "00000000-0000-4000-8000-000000000001"
FIXED_EXPIRES_AT = "2026-09-01T00:00:00Z"

MOOD_DISCLAIMER = (
    "Resultado estimado por un modelo visual. No representa una medición "
    "objetiva del estado emocional."
)
AGE_DISCLAIMER = (
    "La edad es una estimación visual y puede contener un margen de error significativo."
)
