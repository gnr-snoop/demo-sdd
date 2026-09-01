"""MiVOLOAgeEstimator — concrete ``AgeEstimator`` port implementation via MiVOLO
(PyTorch CPU + timm, Apache-2.0 code + open-weights checkpoint) (spec 009, US2,
FR-002/FR-007/FR-008/FR-020, research R-2/R-6/R-7).

``estimate_age(face_image: bytes) -> AgeResult``:
  1. Decode bytes via ``cv2.imdecode``.
  2. Internal YuNet detection → face-box + landmarks (double-detection,
     mirroring ``SFaceEmbedder`` — research R-7).
  3. ``face_crop`` (``alignCrop``) → fixed-size aligned crop.
  4. MiVOLO ``MiVOLO.inference`` on the preprocessed aligned crop → age float.
  5. ``max(0, round(age))`` → non-negative integer (FR-002).
  6. ``AgeResult(estimated_age=that_int, range=None, model_version=MIVOLO_MODEL_VERSION)``
     — **point-only** (FR-007); the domain ``normalize_age_result`` (spec 005)
     derives the symmetric range — no domain change.

Construction is fail-fast (FR-009): ``ModelDownloader.ensure()`` fetches the
MiVOLO checkpoint + YuNet + SFace model files; the MiVOLO model + YuNet detector
+ SFace recognizer are load-tested → ``ModelCorruptError`` on failure.

The heavy runtimes (``torch``, ``timm``, ``mivolo``) are imported ONLY here
(FR-013/R-9). CPU-only inference (Constitution Quality Gate §7).
"""

from __future__ import annotations

import cv2
import numpy as np
import torch
from mivolo.data.misc import prepare_classification_images
from mivolo.model.mi_volo import MiVOLO

from ...config import get_settings
from ...domain.result_types import AgeResult
from ...logging import get_logger
from .constants import (
    MIVOLO_CHECKPOINT_FILENAME,
    MIVOLO_CHECKPOINT_URL,
    MIVOLO_MODEL_VERSION,
    ModelCorruptError,
    SFACE_MODEL_FILENAME,
    SFACE_MODEL_URL,
    YUNET_MODEL_FILENAME,
    YUNET_MODEL_URL,
    YUNET_NMS_THRESHOLD,
    YUNET_TOP_K,
)
from .face_crop import face_crop
from .model_downloader import ModelDownloader

logger = get_logger("face_insight.adapters.ml.mivolo_age")


class MiVOLOAgeEstimator:
    """Concrete ``AgeEstimator`` port implementation using MiVOLO face-only age
    via PyTorch CPU + timm (spec 009, US2, FR-002).

    The MiVOLO checkpoint AND the YuNet + SFace model files (for internal
    alignment detection + ``alignCrop``) are obtained via ``ModelDownloader``
    (FR-008/FR-009). Construction fails fast with ``ModelUnavailableError`` /
    ``ModelCorruptError`` (FR-009).
    """

    model_version = MIVOLO_MODEL_VERSION

    def __init__(
        self,
        *,
        score_threshold: float | None = None,
        nms_threshold: float = YUNET_NMS_THRESHOLD,
        top_k: int = YUNET_TOP_K,
        checkpoint_path: str | None = None,
        yunet_model_path: str | None = None,
        sface_model_path: str | None = None,
        downloader: ModelDownloader | None = None,
    ) -> None:
        settings = get_settings()
        if score_threshold is None:
            score_threshold = settings.quality_threshold

        if downloader is None:
            downloader = ModelDownloader()

        # Obtain model files (lazy download or cache hit — FR-008/FR-009).
        if checkpoint_path is None:
            checkpoint_path = str(
                downloader.ensure(MIVOLO_CHECKPOINT_FILENAME, MIVOLO_CHECKPOINT_URL)
            )
        if yunet_model_path is None:
            yunet_model_path = str(
                downloader.ensure(YUNET_MODEL_FILENAME, YUNET_MODEL_URL)
            )
        if sface_model_path is None:
            sface_model_path = str(
                downloader.ensure(SFACE_MODEL_FILENAME, SFACE_MODEL_URL)
            )

        self._score_threshold = float(score_threshold)
        self._nms_threshold = float(nms_threshold)
        self._top_k = int(top_k)

        # Fail-fast load-test for the MiVOLO checkpoint (FR-009).
        # face-only age: use_persons=False, disable_faces=False, CPU, no half.
        try:
            self._model = self._build_model(checkpoint_path)
        except Exception as exc:
            logger.error(
                "model_corrupt",
                model_name=MIVOLO_CHECKPOINT_FILENAME,
                error=str(exc),
            )
            raise ModelCorruptError(MIVOLO_CHECKPOINT_FILENAME, detail=str(exc)) from exc

        # YuNet detector for internal alignment detection (R-7).
        try:
            self._detector = cv2.FaceDetectorYN_create(
                yunet_model_path,
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

        # SFace recognizer for alignCrop (face_crop reuse, R-7).
        try:
            self._recognizer = cv2.FaceRecognizerSF_create(sface_model_path, "")
        except Exception as exc:
            logger.error(
                "model_corrupt",
                model_name=SFACE_MODEL_FILENAME,
                error=str(exc),
            )
            raise ModelCorruptError(SFACE_MODEL_FILENAME, detail=str(exc)) from exc

        logger.info(
            "model_loaded",
            model_name=MIVOLO_CHECKPOINT_FILENAME,
            model_version=MIVOLO_MODEL_VERSION,
        )

    def _build_model(self, checkpoint_path: str) -> MiVOLO:
        """Construct the MiVOLO face-only age model (load-test).

        ``use_persons=False`` + ``disable_faces=False`` → face-only model.
        ``device='cpu'`` + ``half=False`` → CPU-only (Quality Gate §7).
        Override hook for tests.
        """
        return MiVOLO(
            checkpoint_path,
            device="cpu",
            half=False,
            use_persons=False,
            disable_faces=False,
        )

    def estimate_age(self, face_image: bytes) -> AgeResult:
        """Estimate age from ``face_image`` bytes → ``AgeResult`` (FR-002).

        Alignment is performed internally (research R-7): decode → YuNet detect
        → ``face_crop`` (alignCrop) → MiVOLO inference. Returns a **point-only**
        ``AgeResult(range=None)``; the domain derives the symmetric range (FR-007).
        """
        # 1. Decode bytes → OpenCV Mat.
        nparr = np.frombuffer(face_image, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("could not decode image bytes")

        # 2. Internal YuNet detection for face-box + landmarks (R-7).
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _retval, faces = self._detector.detect(img)
        if faces is None or faces.shape[0] == 0:
            raise ValueError("no face detected for alignment")

        face_box = faces[0]

        # 3. Align + crop via the shared face_crop pipeline (FR-008).
        aligned = face_crop(self._recognizer, img, face_box)

        # 4. MiVOLO age inference on the aligned face crop (R-2/R-6).
        age_float = self._predict_age(aligned)

        # 5. Non-negative integer (FR-002).
        estimated = max(0, round(age_float))

        # 6. Point-only AgeResult (FR-007). No biometric data logged (FR-016/R-12).
        return AgeResult(
            estimated_age=estimated,
            range=None,
            model_version=MIVOLO_MODEL_VERSION,
        )

    def _predict_age(self, aligned_crop) -> float:
        """Run MiVOLO age inference on a single aligned face crop → age float.

        Bypasses the ``PersonAndFaceResult`` machinery (we do our own detection +
        alignment) and calls ``MiVOLO.inference`` directly on the preprocessed
        crop, then denormalizes the raw output to an age value (research R-2).
        """
        model = self._model
        meta = model.meta
        # Preprocess the aligned crop → model input tensor (R-2).
        faces_input = prepare_classification_images(
            [aligned_crop],
            model.input_size,
            model.data_config["mean"],
            model.data_config["std"],
            device=model.device,
        )
        # Face-only model: model_input is just the face tensor.
        output = model.inference(faces_input)
        # Extract the age logit. For only_age models the output is the age;
        # otherwise col 2 is the age (cols 0-1 are gender).
        if meta.only_age:
            age_logit = float(output[0].item())
        else:
            age_logit = float(output[0, 2].item())
        # Denormalize to years (mirrors MiVOLO.fill_in_results).
        age = age_logit * (meta.max_age - meta.min_age) + meta.avg_age
        return float(age)


__all__ = ["MiVOLOAgeEstimator"]
