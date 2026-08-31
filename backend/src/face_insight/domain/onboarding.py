"""Onboarding use-case and domain exceptions (spec 002, R-7).

This module is pure domain: it imports only ports, entities, result types, and
the stdlib. It MUST NOT import adapters, api, SQLAlchemy, FastAPI, Pillow, or
any ML library (enforced by tests/domain/test_domain_purity.py).

The ``OnboardingService`` orchestrates the onboarding flow per data-model.md
§Atomicity: validate → decode/resize → detect → quality → embed → FS write →
atomic DB commit, with best-effort FS cleanup on DB failure.
"""

from __future__ import annotations

import uuid
from typing import Optional

from .entities import FaceTemplate, User, UserStatus, create_face_template, create_user
from .ports import Detector, Embedder, FaceTemplateRepository, ImageStorage, UserRepository
from .result_types import Embedding
from .validation import is_valid_identifier, normalize_identifier


# --- Domain exceptions (R-7) ----------------------------------------------
class OnboardingError(Exception):
    """Base for onboarding domain errors."""


class IdentifierInvalid(OnboardingError):
    """Identifier empty/whitespace or malformed (neither email nor username)."""


class IdentifierTaken(OnboardingError):
    """Normalized identifier already registered (case-insensitive)."""


class ConsentRequired(OnboardingError):
    """Consent missing, false, or non-boolean."""


class InvalidImage(OnboardingError):
    """Image missing, unsupported format, undecodable, or oversized."""


class NoFace(OnboardingError):
    """Detector returned face_count == 0."""


class MultipleFaces(OnboardingError):
    """Detector returned face_count > 1."""


class InsufficientQuality(OnboardingError):
    """Single face but score < quality_threshold."""


class OnboardingInternalError(OnboardingError):
    """Unexpected failure (embedder error, DB unreachable, FS write failure)."""


# --- Result value object --------------------------------------------------
class OnboardingResult:
    """Successful onboarding outcome (userId, identifier, status)."""

    __slots__ = ("user_id", "identifier", "status")

    def __init__(self, user_id: uuid.UUID, identifier: str, status: UserStatus) -> None:
        self.user_id = user_id
        self.identifier = identifier
        self.status = status


# --- Service ---------------------------------------------------------------
class OnboardingService:
    """Orchestrates onboarding through injected ports (hexagonal use-case).

    All ML/IO touches go through the ports; the service holds no infra. The
    ``save_user_with_template`` callable performs the atomic DB unit-of-work
    (T010) and is injected so the domain stays free of SQLAlchemy.
    """

    def __init__(
        self,
        detector: Detector,
        embedder: Embedder,
        user_repository: UserRepository,
        face_template_repository: FaceTemplateRepository,
        image_storage: ImageStorage,
        quality_threshold: float = 0.5,
        embedding_model_version: str = "mock-embedder-v1",
    ) -> None:
        self._detector = detector
        self._embedder = embedder
        self._users = user_repository
        self._templates = face_template_repository
        self._images = image_storage
        self._quality_threshold = quality_threshold
        self._embedding_model_version = embedding_model_version

    async def onboard(
        self,
        identifier: str,
        consent: object,
        image_bytes: bytes,
        *,
        save_user_with_template=None,
    ) -> OnboardingResult:
        """Run the onboarding flow.

        ``save_user_with_template`` is an async callable
        ``(user, template) -> None`` that performs the atomic DB insert
        (T010). It is injected to keep the domain free of SQLAlchemy. If not
        provided, the service falls back to sequential ``save`` calls on the
        two repositories (still atomic-ish for the in-memory mocks used in
        unit tests).
        """
        # 1. Identifier format + normalize (FR-002, R-1).
        if not is_valid_identifier(identifier):
            raise IdentifierInvalid(identifier)
        normalized = normalize_identifier(identifier)

        # 2. Consent must be exactly True (FR-003).
        if consent is not True:
            raise ConsentRequired()

        # 3. Image presence (decode/limits/resize handled by the route via
        #    image_handling; the service receives already-resized bytes).
        if not image_bytes:
            raise InvalidImage("empty image")

        # 3b. Pre-commit duplicate check (FR-002). The DB UNIQUE constraint
        #     (R-4) remains the backstop for concurrent duplicates; this check
        #     enables 409 identifier_taken for single-threaded/mock repos.
        existing = await self._users.get_by_identifier(normalized)
        if existing is not None:
            raise IdentifierTaken(normalized)

        # 4. Detect faces (FR-004).
        detection = self._detector.detect(image_bytes)
        if detection.face_count == 0:
            raise NoFace()
        if detection.face_count > 1:
            raise MultipleFaces()

        # 5. Quality threshold (FR-005).
        if detection.score < self._quality_threshold:
            raise InsufficientQuality()

        # 6. Embed (FR-006). Embedder failure → internal error, no persistence.
        try:
            embedding: Embedding = self._embedder.embed(image_bytes)
        except Exception as exc:  # noqa: BLE001 — boundary: wrap infra failures
            raise OnboardingInternalError("embedder failure") from exc

        # Build domain entities (no persistence yet).
        user = create_user(identifier=normalized, status=UserStatus.enrolled)
        template = create_face_template(
            user_id=user.id,
            embedding=embedding.vector,
            model_version=embedding.model_version or self._embedding_model_version,
        )

        # 7. Filesystem write (pre-DB-commit; R-5 ordering).
        try:
            self._images.store(user.id, image_bytes)
        except Exception as exc:  # noqa: BLE001
            raise OnboardingInternalError("image storage failure") from exc

        # 8. Atomic DB commit (FR-008). On failure, best-effort FS cleanup (R-5).
        try:
            if save_user_with_template is not None:
                await save_user_with_template(user, template)
            else:
                await self._users.save(user)
                await self._templates.save(template)
        except IdentifierTaken:
            await self._cleanup_image(user.id)
            raise
        except Exception as exc:  # noqa: BLE001
            await self._cleanup_image(user.id)
            raise OnboardingInternalError("persistence failure") from exc

        return OnboardingResult(user.id, normalized, user.status)

    async def _cleanup_image(self, user_id: uuid.UUID) -> None:
        """Best-effort FS cleanup on DB failure (R-5). Swallows errors."""
        try:
            self._images.delete(user_id)
        except Exception:  # noqa: BLE001 — best-effort
            pass
