"""Application configuration (FR-015, research R-9).

All values are env-overridable via Pydantic BaseSettings. No logic is implemented
here — this is the tunable configuration surface only.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tunable settings for the Face Insight Demo.

    Overridable via environment variables (case-insensitive), e.g.
    ``VERIFICATION_THRESHOLD=0.7``.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://faceinsight:faceinsight@localhost:5432/faceinsight"

    # --- Verification (OQ-6) ------------------------------------------------
    verification_threshold: float = 0.5

    # --- Onboarding quality (spec 002, FR-004) -----------------------------
    quality_threshold: float = 0.5

    # --- Model versions (FR-012) -------------------------------------------
    embedding_model_version: str = "mock-embedder-v1"
    detector_model_version: str = "mock-yolo-v0"
    age_model_version: str = "mock-age-v0"
    mood_model_version: str = "mock-mood-v0"

    # --- Image limits (OQ-8) ------------------------------------------------
    image_max_bytes: int = 2_000_000
    image_format: str = "JPEG"
    image_max_long_edge: int = 640

    # --- Session ------------------------------------------------------------
    session_ttl_seconds: int = 3600


def get_settings() -> Settings:
    """Return a fresh Settings instance (env-overridable)."""
    return Settings()
