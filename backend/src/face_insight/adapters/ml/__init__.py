"""Concrete ML adapters (spec 008 + spec 009, Fase 5 — all four ML ports).

This subpackage hosts the concrete open-source ML adapter implementations:
- ``YuNetDetector`` — real face detection via YuNet (OpenCV DNN, MIT). [spec 008]
- ``SFaceEmbedder`` — real face embedding via SFace (OpenCV DNN, Apache-2.0). [spec 008]
- ``EmotiEffMoodEstimator`` — real mood via EmotiEff/HSEmotion (ONNX Runtime, Apache-2.0). [spec 009]
- ``MiVOLOAgeEstimator`` — real age via MiVOLO (PyTorch CPU + timm, Apache-2.0). [spec 009]
- ``face_crop`` — shared alignment pipeline (wraps ``cv2.FaceRecognizerSF.alignCrop``).
- ``ModelDownloader`` — lazy model fetch + ``models/`` cache (FR-008).

These adapters implement the existing ``Detector``, ``Embedder``, ``MoodEstimator``
and ``AgeEstimator`` domain ports (Constitution Principle VII). The domain layer
never imports this subpackage (FR-013, enforced by
``tests/domain/test_domain_purity.py``).

Import isolation (FR-013/R-9): ``cv2``, ``onnxruntime`` and ``numpy`` are imported
by the spec 008 modules. ``hsemotion_onnx`` is imported only by
``emotieff_mood.py``; ``torch``/``timm``/``mivolo`` only by ``mivolo_age.py``. To
keep the lightweight constants/exports importable without the heavy mood/age
runtimes installed, ``EmotiEffMoodEstimator`` and ``MiVOLOAgeEstimator`` are
**lazy** exports (resolved on first attribute access via ``__getattr__``).
"""

from __future__ import annotations

from .constants import (
    AFEW_INDEX_TO_EMOTION_NAME,
    AFEW_TO_PRD_LABEL_MAP,
    DEFAULT_MOOD_CONFIDENCE_THRESHOLD,
    EMBEDDING_DIM,
    EMOTIEFF_LICENSE,
    EMOTIEFF_MODEL_FILENAME,
    EMOTIEFF_MODEL_URL,
    EMOTIEFF_MODEL_VERSION,
    InvalidFaceBox,
    MIVOLO_CHECKPOINT_FILENAME,
    MIVOLO_CHECKPOINT_URL,
    MIVOLO_LICENSE,
    MIVOLO_MODEL_VERSION,
    ModelCorruptError,
    ModelUnavailableError,
    PRODUCTION_VERIFICATION_THRESHOLD,
    SFACE_LICENSE,
    SFACE_MODEL_FILENAME,
    SFACE_MODEL_URL,
    SFACE_MODEL_VERSION,
    YUNET_LICENSE,
    YUNET_MODEL_FILENAME,
    YUNET_MODEL_URL,
    YUNET_MODEL_VERSION,
    resolve_mood_label,
)
from .face_crop import face_crop
from .model_downloader import ModelDownloader
from .sface_embedder import SFaceEmbedder
from .yunet_detector import YuNetDetector

__all__ = [
    "YuNetDetector",
    "SFaceEmbedder",
    "EmotiEffMoodEstimator",
    "MiVOLOAgeEstimator",
    "face_crop",
    "ModelDownloader",
    "EMBEDDING_DIM",
    "PRODUCTION_VERIFICATION_THRESHOLD",
    "YUNET_MODEL_VERSION",
    "SFACE_MODEL_VERSION",
    "YUNET_MODEL_FILENAME",
    "SFACE_MODEL_FILENAME",
    "YUNET_MODEL_URL",
    "SFACE_MODEL_URL",
    "YUNET_LICENSE",
    "SFACE_LICENSE",
    "EMOTIEFF_MODEL_FILENAME",
    "EMOTIEFF_MODEL_URL",
    "EMOTIEFF_MODEL_VERSION",
    "EMOTIEFF_LICENSE",
    "MIVOLO_CHECKPOINT_FILENAME",
    "MIVOLO_CHECKPOINT_URL",
    "MIVOLO_MODEL_VERSION",
    "MIVOLO_LICENSE",
    "AFEW_INDEX_TO_EMOTION_NAME",
    "AFEW_TO_PRD_LABEL_MAP",
    "DEFAULT_MOOD_CONFIDENCE_THRESHOLD",
    "resolve_mood_label",
    "ModelUnavailableError",
    "ModelCorruptError",
    "InvalidFaceBox",
]


def __getattr__(name: str):  # PEP 562 — module-level lazy attribute access.
    """Lazy-load the heavy mood/age adapters only when actually accessed.

    This keeps ``from face_insight.adapters.ml import SFaceEmbedder`` (and the
    constants) working without ``hsemotion_onnx``/``torch``/``timm``/``mivolo``
    installed (FR-013/R-9). Only ``from face_insight.adapters.ml import
    EmotiEffMoodEstimator`` / ``MiVOLOAgeEstimator`` triggers the heavy import.
    """
    if name == "EmotiEffMoodEstimator":
        from .emotieff_mood import EmotiEffMoodEstimator

        return EmotiEffMoodEstimator
    if name == "MiVOLOAgeEstimator":
        from .mivolo_age import MiVOLOAgeEstimator

        return MiVOLOAgeEstimator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
