"""Deterministic mock adapters (Fase 1, SC-005).

Every mock returns hardcoded constant outputs — no RNG, no seed, no clock
(research R-5). Re-exported here for convenient wiring.
"""

from .age_estimator import MockAgeEstimator
from .constants import FIXED_USER_ID
from .detector import MockDetector, ScriptableMockDetector
from .embedder import MockEmbedder, ScriptableMockEmbedder
from .face_template_repository import MockFaceTemplateRepository
from .image_storage import MockImageStorage
from .mood_estimator import MockMoodEstimator, ScriptableMockMoodEstimator
from .session_manager import MockSessionManager
from .user_repository import MockUserRepository
from .unit_of_work import MockUnitOfWork

__all__ = [
    "MockAgeEstimator",
    "MockDetector",
    "ScriptableMockDetector",
    "MockEmbedder",
    "ScriptableMockEmbedder",
    "MockFaceTemplateRepository",
    "MockImageStorage",
    "MockMoodEstimator",
    "ScriptableMockMoodEstimator",
    "MockSessionManager",
    "MockUnitOfWork",
    "MockUserRepository",
    "FIXED_USER_ID",
]
