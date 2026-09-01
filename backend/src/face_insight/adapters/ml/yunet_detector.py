"""YuNetDetector — concrete ``Detector`` port implementation via YuNet (OpenCV
DNN, MIT license) (spec 008, US1, FR-001/FR-005, research R-1/R-2).

``detect(image: bytes) -> DetectionResult``:
  - Decode bytes via ``cv2.imdecode``.
  - Set the detector input size to the image size.
  - Run ``detect`` → map rows → ``BoundingBox`` list + ``score = max(row[14])``.
  - Constructed with ``score_threshold = settings.quality_threshold``,
    ``nms_threshold=0.3``, ``top_k=5000``.

Construction is fail-fast: ``ModelDownloader.ensure()`` fetches the model, then
``cv2.FaceDetectorYN_create(...)`` loads it; load failure → ``ModelCorruptError``
(FR-009).
"""

from __future__ import annotations

import cv2
import numpy as np

from ...config import get_settings
from ...domain.result_types import BoundingBox, DetectionResult, Landmark
from ...logging import get_logger
from .constants import (
    ModelCorruptError,
    YUNET_MODEL_FILENAME,
    YUNET_MODEL_URL,
    YUNET_MODEL_VERSION,
    YUNET_NMS_THRESHOLD,
    YUNET_TOP_K,
)
from .model_downloader import ModelDownloader

logger = get_logger("face_insight.adapters.ml.yunet_detector")


class YuNetDetector:
    """Concrete ``Detector`` port implementation using YuNet via OpenCV DNN.

    The model file is obtained via ``ModelDownloader`` (lazy download on first
    construction, cache hit thereafter — FR-008). Construction fails fast with
    ``ModelUnavailableError`` / ``ModelCorruptError`` if the model cannot be
    obtained or loaded (FR-009).
    """

    model_version = YUNET_MODEL_VERSION

    def __init__(
        self,
        *,
        score_threshold: float | None = None,
        nms_threshold: float = YUNET_NMS_THRESHOLD,
        top_k: int = YUNET_TOP_K,
        model_path: str | None = None,
        downloader: ModelDownloader | None = None,
    ) -> None:
        settings = get_settings()
        if score_threshold is None:
            score_threshold = settings.quality_threshold

        # Obtain the model file (lazy download or cache hit — FR-008).
        if model_path is None:
            if downloader is None:
                downloader = ModelDownloader()
            model_path = str(
                downloader.ensure(YUNET_MODEL_FILENAME, YUNET_MODEL_URL)
            )

        self._model_path = model_path
        self._score_threshold = float(score_threshold)
        self._nms_threshold = float(nms_threshold)
        self._top_k = int(top_k)

        # Fail-fast load-test (FR-009): construct the detector with a dummy
        # input size; OpenCV raises on a corrupt/truncated file.
        try:
            self._detector = cv2.FaceDetectorYN_create(
                model_path,
                "",
                (320, 320),
                score_threshold=self._score_threshold,
                nms_threshold=self._nms_threshold,
                top_k=self._top_k,
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
            model_name=YUNET_MODEL_FILENAME,
            model_version=YUNET_MODEL_VERSION,
        )

    def detect(self, image: bytes) -> DetectionResult:
        """Detect faces in ``image`` bytes → ``DetectionResult`` (FR-005).

        YuNet's ``detect`` returns ``(retval, faces)`` where ``faces`` is a
        CV_32F Mat with one row per face and 15 columns:
        ``x, y, w, h, landmarks..., conf`` (col 14 = confidence, R-2).
        """
        # Decode bytes → OpenCV Mat.
        nparr = np.frombuffer(image, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return DetectionResult(face_count=0, boxes=[], score=0.0)

        # Set the input size to the image size (YuNet requires this per call).
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))

        _retval, faces = self._detector.detect(img)
        if faces is None or faces.shape[0] == 0:
            return DetectionResult(face_count=0, boxes=[], score=0.0)

        boxes: list[BoundingBox] = []
        all_landmarks: list[list[Landmark]] = []
        max_score = 0.0
        for row in faces:
            x = int(row[0])
            y = int(row[1])
            bw = int(row[2])
            bh = int(row[3])
            conf = float(row[14])
            boxes.append(BoundingBox(x=x, y=y, width=bw, height=bh))
            if conf > max_score:
                max_score = conf
            # YuNet 5 landmarks: (x_re,y_re) row[4], row[5] ... row[12], row[13]
            landmarks: list[Landmark] = []
            for k in range(5):
                lx = int(row[4 + k * 2])
                ly = int(row[4 + k * 2 + 1])
                landmarks.append(Landmark(x=lx, y=ly))
            all_landmarks.append(landmarks)

        return DetectionResult(
            face_count=len(boxes),
            boxes=boxes,
            score=max_score,
            landmarks=all_landmarks if all_landmarks else None,
        )


__all__ = ["YuNetDetector"]
