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


# --- Mood-specific exceptions (spec 004, T003/R-4) -------------------------
class MoodInternalError(OnboardingInternalError):
    """Unexpected failure during mood analysis (detector/mood_estimator port
    raises, or any other unexpected error). Mapped to ``500 internal_error``
    (recoverable — FR-007). No mood result is produced."""


class ComparisonError(OnboardingError):
    """Comparison port failure (e.g. embedding dimension mismatch).

    Raised by ``Comparison.compare`` implementations; the login use-case maps
    it to ``LoginInternalError`` → ``500 internal_error`` (no meaningless score).
    """


# --- Deletion-specific exceptions (spec 006, T002) -------------------------
class Forbidden(OnboardingError):
    """Authorization failure on the deletion endpoint.

    Raised when the authenticated session's ``user_id`` does not match the
    path ``userId``. Mapped to ``403 forbidden`` (FR-002). Intentionally
    revealing: the caller is already authenticated, so disclosing "you can
    only delete your own data" is demo-grade authz under Constitution
    Principle VIII (research R-3).
    """


FORBIDDEN_MESSAGE = "Solo puedes eliminar tus propios datos."


class NotFound(OnboardingError):
    """Defensive guard: the ``User`` for the path ``userId`` does not exist.

    Only reachable via out-of-band deletion or a concurrent race (a valid
    matching session guarantees existence). Mapped to ``404 not_found``
    (FR-007).
    """


NOT_FOUND_MESSAGE = "No se encontró el usuario."


class DeletionInternalError(OnboardingInternalError):
    """Unexpected failure during the deletion transaction (DB rollback).

    Mapped to ``500 internal_error`` (FR-008). No partial DB state is left.
    """


DELETION_INTERNAL_ERROR_MESSAGE = "Ocurrió un error al eliminar tus datos. Inténtalo de nuevo."


__all__ = [
    "AUTH_FAILED_MESSAGE",
    "UNAUTHENTICATED_MESSAGE",
    "AuthFailed",
    "ComparisonError",
    "DeletionInternalError",
    "DELETION_INTERNAL_ERROR_MESSAGE",
    "Forbidden",
    "FORBIDDEN_MESSAGE",
    "InsufficientQuality",
    "InvalidImage",
    "LoginInternalError",
    "MoodInternalError",
    "MultipleFaces",
    "NoFace",
    "NotFound",
    "NOT_FOUND_MESSAGE",
    "OnboardingError",
    "OnboardingInternalError",
    "Unauthenticated",
]
