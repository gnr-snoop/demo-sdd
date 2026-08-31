"""LoginService use-case (spec 003, T016, FR-021, R-1/R-2/R-5).

Pure domain: imports only ports, entities, result types, exceptions, and the
stdlib. It MUST NOT import adapters, api, SQLAlchemy, FastAPI, Pillow,
itsdangerous, or any ML library (enforced by tests/domain/test_domain_purity.py).

Evaluation order (pinned, R-5): normalize → decode/validate (route-side) →
detect → lookup → embed → compare → session create. Detection precedes lookup
so capture-quality errors surface uniformly for all identifiers (eliminates
the residual identifier-existence leak). Steps "lookup miss" and "below
threshold" raise the SAME ``AuthFailed`` exception with the SAME message →
byte-identical 401 response (FR-008/SC-003). No session is created on any
failure path (FR-004/SC-004).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from .entities import User
from .exceptions import (
    AUTH_FAILED_MESSAGE,
    AuthFailed,
    ComparisonError,
    InsufficientQuality,
    InvalidImage,
    LoginInternalError,
    MultipleFaces,
    NoFace,
)
from .ports import Comparison, Detector, Embedder, FaceTemplateRepository, SessionManager, UserRepository
from .result_types import ComparisonResult, Embedding
from .validation import is_valid_identifier, normalize_identifier


class LoginResult:
    """Successful login outcome (userId, sessionId, status)."""

    __slots__ = ("user_id", "session_id", "status")

    def __init__(self, user_id: uuid.UUID, session_id: uuid.UUID, status: str = "authenticated") -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.status = status


class LoginService:
    """Orchestrates 1:1 face login through injected ports (hexagonal use-case).

    All ML/IO touches go through the ports; the service holds no infra. The
    route handler decodes/validates the image (via ``image_handling``) and
    passes already-resized bytes to ``login``.
    """

    def __init__(
        self,
        detector: Detector,
        embedder: Embedder,
        comparison: Comparison,
        user_repository: UserRepository,
        face_template_repository: FaceTemplateRepository,
        session_manager: SessionManager,
        quality_threshold: float = 0.5,
        verification_threshold: float = 0.5,
    ) -> None:
        self._detector = detector
        self._embedder = embedder
        self._comparison = comparison
        self._users = user_repository
        self._templates = face_template_repository
        self._sessions = session_manager
        self._quality_threshold = quality_threshold
        self._verification_threshold = verification_threshold

    async def login(
        self,
        identifier: str,
        image_bytes: bytes,
        now: datetime,
        session_lifetime: timedelta,
    ) -> LoginResult:
        """Run the login flow (data-model.md §Login use-case orchestration).

        Raises domain exceptions mapped by the route handler:
          - ``InvalidImage`` (400) — empty image
          - ``NoFace`` (400) / ``MultipleFaces`` (400) / ``InsufficientQuality`` (400)
          - ``AuthFailed`` (401) — nonexistent identifier/template OR below threshold
          - ``LoginInternalError`` (500) — embedder/comparison/DB failure
        """
        # 1. Identifier format + normalize (FR-019, reuse spec 002 validation).
        if not is_valid_identifier(identifier):
            # Malformed identifier: raise AuthFailed (non-revealing) — a malformed
            # identifier cannot correspond to a registered user. This keeps the
            # 401/400 reservation crisp (identifier format is not a capture issue).
            raise AuthFailed(AUTH_FAILED_MESSAGE)
        normalized = normalize_identifier(identifier)

        # 2. Image presence (decode/limits/resize handled by the route via
        #    image_handling; the service receives already-resized bytes).
        if not image_bytes:
            raise InvalidImage("empty image")

        # 3. Detect faces (FR-004) — BEFORE lookup (R-5: eliminates identifier-existence leak).
        detection = self._detector.detect(image_bytes)
        if detection.face_count == 0:
            raise NoFace()
        if detection.face_count > 1:
            raise MultipleFaces()
        if detection.score < self._quality_threshold:
            raise InsufficientQuality()

        # 4. Load User + FaceTemplate by normalized identifier (R-5 step 3).
        #    Missing user/template → AuthFailed (non-revealing, identical to step 6).
        user: Optional[User] = await self._users.get_by_identifier(normalized)
        template = None
        if user is not None:
            template = await self._templates.get_by_user(user.id)
        if user is None or template is None:
            raise AuthFailed(AUTH_FAILED_MESSAGE)

        # 5. Embed captured face (R-5 step 4). Embedder failure → internal error.
        try:
            embedding: Embedding = self._embedder.embed(image_bytes)
        except Exception as exc:  # noqa: BLE001 — boundary: wrap infra failures
            raise LoginInternalError("embedder failure") from exc

        # 6. Cosine similarity vs stored embedding (R-5 step 5).
        #    Dimension mismatch → ComparisonError → LoginInternalError (500).
        #    Below threshold → AuthFailed (identical to step 4 — non-revealing).
        try:
            similarity = self._comparison.compare(embedding.vector, template.embedding)
        except ComparisonError as exc:
            raise LoginInternalError("comparison failure") from exc
        except Exception as exc:  # noqa: BLE001
            raise LoginInternalError("comparison failure") from exc

        if similarity < self._verification_threshold:
            raise AuthFailed(AUTH_FAILED_MESSAGE)

        # 7. Create AuthSession (R-5 step 6). DB failure → internal error, no partial state.
        try:
            session = await self._sessions.create(user.id, now, session_lifetime)
        except Exception as exc:  # noqa: BLE001
            raise LoginInternalError("session persistence failure") from exc

        return LoginResult(user_id=user.id, session_id=session.id, status="authenticated")


__all__ = ["LoginResult", "LoginService"]
