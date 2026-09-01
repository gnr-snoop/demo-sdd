"""DeletionService use-case (spec 006, T009, FR-004..FR-008/FR-013/FR-014/FR-016).

Pure domain: imports only ports, exceptions, and the stdlib. It MUST NOT import
adapters, api, SQLAlchemy, FastAPI, Pillow, itsdangerous, structlog, or any ML
library (enforced by tests/domain/test_domain_purity.py + tests/unit/
test_deletion_service.py domain-purity check, T026).

Orchestrates the "right to be forgotten" hard-delete through injected ports:
  1. Authorization (FR-002): ``session_user_id == user_id`` else ``Forbidden``.
  2. Existence guard (FR-007): ``UserRepository.get`` → ``NotFound`` if absent.
  3. Atomic DB deletion (FR-004): the injected ``delete_user_face_data`` async
     callable (from ``SqlAlchemyUnitOfWork``) removes FaceTemplate → AuthSession
     → User in one transaction. Failure → ``DeletionInternalError`` (500,
     rollback, no partial state).
  4. Best-effort filesystem cleanup (FR-005): ``ImageStorage.delete`` after the
     DB commit; failure is logged as a structured warning and does NOT fail the
     endpoint (200 + warning).
  5. Structured JSON logging (FR-016): ``{type:"deletion", userId, status,
     duration_ms}`` and ``{type:"deletion_fs_cleanup_warning", userId}`` on FS
     failure. No image/embedding/biometric content is logged (Principle VIII).

No ML port is invoked (FR-014). The ``delete_user_face_data`` callable is
injected at construction (same callable-injection pattern as
``OnboardingService.save_user_with_template``, research R-2) so the domain
stays free of SQLAlchemy.
"""

from __future__ import annotations

import time
from typing import Optional
from uuid import UUID

from .exceptions import (
    DELETION_INTERNAL_ERROR_MESSAGE,
    DeletionInternalError,
    FORBIDDEN_MESSAGE,
    Forbidden,
    NOT_FOUND_MESSAGE,
    NotFound,
)
from .ports import ImageStorage, UserRepository


class DeletionResult:
    """Successful deletion outcome (userId, status)."""

    __slots__ = ("user_id", "status")

    def __init__(self, user_id: UUID, status: str = "deleted") -> None:
        self.user_id = user_id
        self.status = status


class DeletionService:
    """Orchestrates face-data deletion through injected ports (hexagonal use-case).

    All DB/IO touches go through the ports + the injected
    ``delete_user_face_data`` async callable; the service holds no infra. The
    callable performs the atomic DB unit-of-work (T007) and is injected so the
    domain stays free of SQLAlchemy (research R-2/R-10).
    """

    def __init__(
        self,
        user_repository: UserRepository,
        image_storage: ImageStorage,
        delete_user_face_data: object,
        logger: object,
    ) -> None:
        self._users = user_repository
        self._images = image_storage
        self._delete_user_face_data = delete_user_face_data
        self._logger = logger

    async def delete_face_data(
        self,
        user_id: UUID,
        session_user_id: UUID,
    ) -> DeletionResult:
        """Run the deletion flow (data-model.md §Deletion ordering).

        Raises domain exceptions mapped by the route handler / registered
        exception handlers:
          - ``Forbidden`` (403) — ``session_user_id != user_id`` (FR-002).
          - ``NotFound`` (404) — ``User`` absent for ``user_id`` (FR-007).
          - ``DeletionInternalError`` (500) — DB transaction failure (FR-004/FR-008).
        """
        # 1. Authorization (FR-002): the session must own the resource. Evaluated
        #    BEFORE the existence lookup (condition order R-4: 403 → 404). No
        #    deletion callable or FS touch occurs on mismatch.
        if session_user_id != user_id:
            raise Forbidden(FORBIDDEN_MESSAGE)

        # 2. Existence guard (FR-007): defensive — a valid matching session
        #    guarantees the User exists, so 404 is only reachable via out-of-band
        #    deletion or a concurrent race (Principle VIII).
        user = await self._users.get(user_id)
        if user is None:
            raise NotFound(NOT_FOUND_MESSAGE)

        # 3. Atomic DB deletion (FR-004): FaceTemplate → AuthSession → User →
        #    commit, in one transaction via the injected callable. Failure →
        #    rollback + DeletionInternalError (no partial DB state).
        started = time.monotonic()
        try:
            await self._delete_user_face_data(user_id)  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 — boundary: wrap infra failures
            self._log_deletion(user_id, "failed", started)
            raise DeletionInternalError(DELETION_INTERNAL_ERROR_MESSAGE) from exc

        # 4. Best-effort filesystem cleanup (FR-005) AFTER the DB commit. The
        #    ImageStorage.delete is a no-op when the dir is absent; on any other
        #    failure we log a structured warning and still return 200 (the user
        #    is already forgotten in the DB — the source of truth for login).
        try:
            self._images.delete(user_id)
        except Exception:  # noqa: BLE001 — best-effort; endpoint still succeeds
            self._log_fs_cleanup_warning(user_id)

        self._log_deletion(user_id, "deleted", started)
        return DeletionResult(user_id=user_id, status="deleted")

    # --- Structured logging (FR-016, T028) ---------------------------------
    def _log_deletion(self, user_id: UUID, status: str, started: float) -> None:
        try:
            self._logger.info(  # type: ignore[union-attr]
                "deletion",
                user_id=str(user_id),
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception:  # noqa: BLE001 — logging must never break the flow
            pass

    def _log_fs_cleanup_warning(self, user_id: UUID) -> None:
        try:
            self._logger.warning(  # type: ignore[union-attr]
                "deletion_fs_cleanup_warning",
                user_id=str(user_id),
            )
        except Exception:  # noqa: BLE001
            pass


__all__ = ["DeletionResult", "DeletionService"]
