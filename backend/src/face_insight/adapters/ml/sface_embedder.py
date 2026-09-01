"""SFaceEmbedder — concrete ``Embedder`` port implementation via SFace (OpenCV
DNN, Apache-2.0 license) (spec 008, US2, FR-002/FR-006, research R-3/R-5).

``embed(face_image: bytes) -> Embedding``:
  1. Decode bytes via ``cv2.imdecode``.
  2. Internal YuNet detection → face-box + landmarks (double-detection is
     acceptable — research R-5; the ``Embedder.embed`` port signature is fixed
     by FR-018 and the domain passes raw image bytes).
  3. ``face_crop`` (``alignCrop``) → fixed-size aligned crop.
  4. ``feature()`` → 128-dim L2-normalized vector → ``Embedding``.

Construction is fail-fast: ``ModelDownloader.ensure()`` fetches the SFace +
YuNet model files, then ``cv2.FaceRecognizerSF_create(...)`` loads them; load
failure → ``ModelCorruptError`` (FR-009). Resolves Constitution OQ-4.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...config import get_settings
from ...domain.result_types import Embedding
from ...logging import get_logger
from .constants import (
    EMBEDDING_DIM,
    ModelCorruptError,
    SFACE_MODEL_FILENAME,
    SFACE_MODEL_URL,
    SFACE_MODEL_VERSION,
    YUNET_MODEL_FILENAME,
    YUNET_MODEL_URL,
    YUNET_NMS_THRESHOLD,
    YUNET_TOP_K,
)
from .face_crop import face_crop
from .model_downloader import ModelDownloader

logger = get_logger("face_insight.adapters.ml.sface_embedder")


class SFaceEmbedder:
    """Concrete ``Embedder`` port implementation using SFace via OpenCV DNN.

    The SFace model file AND a YuNet model file (for internal alignment
    detection) are obtained via ``ModelDownloader`` (FR-008). Construction fails
    fast with ``ModelUnavailableError`` / ``ModelCorruptError`` (FR-009).
    """

    model_version = SFACE_MODEL_VERSION

    def __init__(
        self,
        *,
        score_threshold: float | None = None,
        nms_threshold: float = YUNET_NMS_THRESHOLD,
        top_k: int = YUNET_TOP_K,
        sface_model_path: str | None = None,
        yunet_model_path: str | None = None,
        downloader: ModelDownloader | None = None,
    ) -> None:
        settings = get_settings()
        if score_threshold is None:
            score_threshold = settings.quality_threshold

        if downloader is None:
            downloader = ModelDownloader()

        # Obtain model files (lazy download or cache hit — FR-008).
        if sface_model_path is None:
            sface_model_path = str(
                downloader.ensure(SFACE_MODEL_FILENAME, SFACE_MODEL_URL)
            )
        if yunet_model_path is None:
            yunet_model_path = str(
                downloader.ensure(YUNET_MODEL_FILENAME, YUNET_MODEL_URL)
            )

        self._sface_model_path = sface_model_path
        self._score_threshold = float(score_threshold)

        # Fail-fast load-test (FR-009).
        try:
            self._recognizer = cv2.FaceRecognizerSF_create(
                sface_model_path, ""
            )
        except Exception as exc:
            logger.error(
                "model_corrupt",
                model_name=SFACE_MODEL_FILENAME,
                error=str(exc),
            )
            raise ModelCorruptError(SFACE_MODEL_FILENAME, detail=str(exc)) from exc

        try:
            self._detector = cv2.FaceDetectorYN_create(
                yunet_model_path,
                "",
                (320, 320),
                score_threshold=self._score_threshold,
                nms_threshold=float(nms_threshold),
                top_k=int(top_k),
            )
        except Exception as exc:
            logger.error(
                "model_corrupt",
                model_name=YUNET_MODEL_FILENAME,
                error=str(exc),
            )
            raise ModelCorruptError(YUNET_MODEL_FILENAME, detail=str(exc)) from exc

        logger.info(
            "model_loaded",
            model_name=SFACE_MODEL_FILENAME,
            model_version=SFACE_MODEL_VERSION,
        )

    def embed(self, face_image: bytes) -> Embedding:
        """Embed a face image → 128-dim L2-normalized ``Embedding`` (FR-006).

        Alignment is performed internally (research R-5): decode → YuNet detect
        → ``face_crop`` (alignCrop) → ``feature``. Both onboarding and login use
        the same ``SFaceEmbedder`` instance → same alignment (FR-007 AC-2).
        """
        # 1. Decode bytes → OpenCV Mat.
        nparr = np.frombuffer(face_image, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("could not decode image bytes")

        # 2. Internal YuNet detection for face-box + landmarks (R-5).
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _retval, faces = self._detector.detect(img)
        if faces is None or faces.shape[0] == 0:
            raise ValueError("no face detected for embedding alignment")

        # Use the first (highest-confidence) detected face.
        face_box = faces[0]

        # 3. Align + crop via the shared face_crop pipeline (FR-007).
        aligned = face_crop(self._recognizer, img, face_box)

        # 4. Feature extraction → 128-dim L2-normalized vector (R-3).
        feature_mat = self._recognizer.feature(aligned)
        vector = feature_mat.flatten().tolist()

        # Defensive: assert the dimension matches the expected 128 (R-3).
        if len(vector) != EMBEDDING_DIM:
            logger.warning(
                "embedding_dim_mismatch",
                expected=EMBEDDING_DIM,
                actual=len(vector),
            )

        return Embedding(vector=vector, model_version=SFACE_MODEL_VERSION)


__all__ = ["SFaceEmbedder"]
