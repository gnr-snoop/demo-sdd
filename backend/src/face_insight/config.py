"""Application configuration (FR-015, research R-9).

All values are env-overridable via Pydantic BaseSettings. No logic is implemented
here — this is the tunable configuration surface only.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_APP_MODES = {"production", "mock"}


class Settings(BaseSettings):
    """Tunable settings for the Face Insight Demo.

    Overridable via environment variables (case-insensitive), e.g.
    ``VERIFICATION_THRESHOLD=0.7``.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # --- Application mode (spec 007, FR-001/FR-005) -------------------------
    # ``mock`` (default) wires in-memory adapters (backward compatible with
    # specs 001-006). ``production`` wires real SQLAlchemy DB adapters + mock
    # ML. Normalized via .strip().lower(); unrecognized values fail fast at
    # settings construction (FR-005).
    app_mode: str = "mock"

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://faceinsight:faceinsight@localhost:5432/faceinsight"

    # --- Verification (OQ-6) ------------------------------------------------
    verification_threshold: float = 0.5

    # --- Onboarding quality (spec 002, FR-004) -----------------------------
    quality_threshold: float = 0.5

    # --- Model versions (FR-012) -------------------------------------------
    embedding_model_version: str = "mock-embedder-v1"
    detector_model_version: str = "mock-yolo-v0"
    # Spec 005 (T001, FR-017/R-11): mock age estimator exposes model_version
    # "mock-age-estimator-v1" (identifiable adapter version for reproducibility).
    age_model_version: str = "mock-age-estimator-v1"
    # Spec 004: mock mood estimator version (orchestrator pinned decision).
    mood_model_version: str = "mock-mood-v1"

    # --- Image limits (OQ-8) ------------------------------------------------
    image_max_bytes: int = 2_000_000
    image_format: str = "JPEG"
    image_max_long_edge: int = 640

    # --- Session (spec 003, R-2/R-3) ----------------------------------------
    session_ttl_seconds: int = 3600
    session_lifetime_seconds: int = 1800
    session_cookie_name: str = "fid_session"
    session_cookie_secure: bool = False
    session_signing_key: str = "demo-signing-key-change-me"

    # --- Spec 005 age normalization (FR-004, R-3) --------------------------
    # Half-width (years) used to derive a symmetric age range when the
    # age_estimator port returns only a point estimate. ``min`` is clamped to 0.
    # Must be >= 0 (validated below); defaults to 5 (PRD §6.4 / clarify pin).
    age_range_half_width_years: int = 5

    # --- Spec 009 mood confidence threshold (FR-006, R-5) --------------------
    # Softmax top-1 probability below which the concrete EmotiEff mood adapter
    # reports the label as "no concluyente" (low-certainty gate). Clamped to
    # [0.0, 1.0] via a field_validator (mirrors age_range_half_width_years).
    # Env: MOOD_CONFIDENCE_THRESHOLD. Mock mood estimator unaffected (returns
    # 0.74 > 0.5 default).
    mood_confidence_threshold: float = 0.5

    # --- Spec 008 model cache & download (FR-008, data-model Configuration) -
    # Model cache directory (bind-mounted into the backend container, FR-010).
    # Default is <repo_root>/models so the host↔container path is identical
    # (mirrors the usuarios/ convention from Principle V).
    models_dir: str = ""
    # httpx download timeouts (single attempt, no retry — FR-008).
    model_download_connect_timeout: float = 30.0
    model_download_read_timeout: float = 120.0

    @field_validator("app_mode")
    @classmethod
    def _app_mode_normalized(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _VALID_APP_MODES:
            raise ValueError(
                f"APP_MODE must be 'production' or 'mock'; got '{v}'"
            )
        return normalized

    @field_validator("age_range_half_width_years")
    @classmethod
    def _age_range_half_width_non_negative(cls, v: int) -> int:
        if v < 0:
            return 0  # clamp to 0 (FR-004 invariant: min >= 0)
        return v

    @field_validator("mood_confidence_threshold")
    @classmethod
    def _mood_confidence_threshold_clamped(cls, v: float) -> float:
        """Spec 009 (FR-006/R-5): clamp to [0.0, 1.0] (probability range)."""
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v

    @model_validator(mode="after")
    def _production_requires_database_url(self) -> "Settings":
        """Fail fast: production mode with an empty DATABASE_URL is a
        misconfiguration (FR-006). The DB reachability probe in
        ``wire_production_adapters`` catches unreachable/malformed URLs; this
        validator catches the unset/empty case at settings construction.
        """
        if self.app_mode == "production" and not self.database_url.strip():
            raise ValueError(
                "APP_MODE=production requires a reachable DATABASE_URL; got ''"
            )
        return self

    @model_validator(mode="after")
    def _resolve_models_dir_default(self) -> "Settings":
        """Spec 008 (FR-008): resolve an empty ``models_dir`` to
        ``<repo_root>/models`` so the host↔container bind-mount path is
        identical (mirrors the usuarios/ convention, Principle V).
        """
        if not self.models_dir.strip():
            self.models_dir = str(Path.cwd() / "models")
        return self


def get_settings() -> Settings:
    """Return a fresh Settings instance (env-overridable)."""
    return Settings()
