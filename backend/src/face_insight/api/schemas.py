"""Pydantic v2 request/response schemas for the 7 contract endpoints (T032).

Shapes match ``specs/001-skeleton-contracts-mocks/contracts/*.md`` exactly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# --- Onboarding (POST /api/onboarding) -------------------------------------
class OnboardingResponse(BaseModel):
    userId: str
    identifier: str
    status: str = "enrolled"


# --- Face login (POST /api/auth/face-login) --------------------------------
class FaceLoginResponse(BaseModel):
    userId: str
    status: str = "authenticated"


# Spec 003 real auth response shapes (supersede the spec 001 stubs).
class LoginResponse(BaseModel):
    """Exactly {userId, status} — no expiresAt (FR-005)."""

    userId: str
    status: str = "authenticated"


class MeResponse(BaseModel):
    authenticated: bool
    userId: str | None = None


class LogoutResponse(BaseModel):
    status: str = "ok"


# --- Auth me (GET /api/auth/me) --------------------------------------------
class AuthMeResponse(BaseModel):
    userId: str
    status: str = "authenticated"
    expiresAt: str


# --- Analysis: mood (POST /api/analysis/mood) ------------------------------
class MoodRange(BaseModel):
    min: int
    max: int


class MoodResponse(BaseModel):
    # Spec 004 (T004/R-3): confidence is optional (`float | None`). When present
    # it must lie in [0.0, 1.0] (validated below). Null/omitted is permitted per
    # PRD §6.4 / FR-012a (the estimator may not produce a confidence).
    label: str
    confidence: float | None = None
    disclaimer: str

    @field_validator("confidence")
    @classmethod
    def _confidence_in_unit_range(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
        return v


# --- Analysis: age (POST /api/analysis/age) --------------------------------
# Spec 005 (T005, R-12): dedicated AgeRange schema (distinct from MoodRange so
# the age and mood contracts can evolve independently). AgeResponse.range uses
# AgeRange; the disclaimer is the exact PRD §8 string (FR-003).
class AgeRange(BaseModel):
    min: int
    max: int


class AgeResponse(BaseModel):
    estimatedAge: int
    range: AgeRange
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
