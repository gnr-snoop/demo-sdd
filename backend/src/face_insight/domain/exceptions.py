"""Login & session domain exceptions (spec 003, R-4, data-model.md).

Pure domain: no infra/ML imports. These typed exceptions are raised by the
login/session use-cases and mapped by the route handler to the pinned
``{"error": {"code", "message"}}`` shape.

Capture-quality exceptions (``InvalidImage``, ``NoFace``, ``MultipleFaces``,
``InsufficientQuality``) are re-exported from ``onboarding.py`` (spec 002) so a
single canonical definition is shared across onboarding and login. Login maps
them to ``400`` (R-4); onboarding maps them to ``422``.
"""

from __future__ import annotations

from .onboarding import (
    InsufficientQuality,
    InvalidImage,
    MultipleFaces,
    NoFace,
    OnboardingError,
    OnboardingInternalError,
)


# --- Login/session-specific exceptions (spec 003) ---------------------------
class AuthFailed(OnboardingError):
    """Single exception for both identity-sensitive login failures.

    Raised for (a) nonexistent identifier / missing FaceTemplate AND
    (b) below-threshold non-match. The route handler maps it to a byte-identical
    ``401 auth_failed`` response (FR-008/SC-003). Sharing one exception +
    one message constant guarantees byte-identity by construction.
    """


# Shared, single message constant for the non-revealing auth_failed body
# (FR-008/SC-003). Both causes use exactly this string.
AUTH_FAILED_MESSAGE = "No pudimos verificar tu identidad. Inténtalo de nuevo."


class Unauthenticated(OnboardingError):
    """Session-gating failure on a protected endpoint.

    Raised when the cookie is absent/tampered/unknown or the session is
    expired/revoked. Mapped to ``401 unauthenticated`` (FR-006/SC-006).
    """


UNAUTHENTICATED_MESSAGE = "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."


class LoginInternalError(OnboardingInternalError):
    """Unexpected failure during login (embedder error, comparison dimension
    mismatch, DB unreachable at session creation). Mapped to ``500
    internal_error`` (recoverable)."""


class ComparisonError(OnboardingError):
    """Comparison port failure (e.g. embedding dimension mismatch).

    Raised by ``Comparison.compare`` implementations; the login use-case maps
    it to ``LoginInternalError`` → ``500 internal_error`` (no meaningless score).
    """


__all__ = [
    "AUTH_FAILED_MESSAGE",
    "UNAUTHENTICATED_MESSAGE",
    "AuthFailed",
    "ComparisonError",
    "InsufficientQuality",
    "InvalidImage",
    "LoginInternalError",
    "MultipleFaces",
    "NoFace",
    "OnboardingError",
    "OnboardingInternalError",
    "Unauthenticated",
]
