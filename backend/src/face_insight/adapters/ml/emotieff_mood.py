"""EmotiEffMoodEstimator — concrete ``MoodEstimator`` port implementation via
EmotiEff/HSEmotion (ONNX Runtime, Apache-2.0 license) (spec 009, US1,
FR-001/FR-005/FR-006/FR-008, research R-1/R-4/R-7).

``estimate_mood(face_image: bytes) -> MoodResult``:
  1. Decode bytes via ``cv2.imdecode``.
  2. Internal YuNet detection → face-box + landmarks (double-detection,
     mirroring ``SFaceEmbedder`` — research R-7).
  3. ``face_crop`` (``alignCrop``) → fixed-size aligned crop.
  4. ``HSEmotionRecognizer.predict_emotions(aligned, logits=False)`` →
     ``(emotion_name, softmax_probs)``.
  5. ``argmax(softmax_probs)`` → ``AFEW_TO_PRD_LABEL_MAP[index]`` → PRD label.
  6. Low-confidence override (FR-006): if ``top1_prob < mood_confidence_threshold``
     → label ``"no concluyente"`` (the low confidence is still returned).
  7. ``MoodResult(label, confidence=top1_prob, model_version=EMOTIEFF_MODEL_VERSION)``.

Construction is fail-fast (FR-009): ``ModelDownloader.ensure()`` fetches the
EmotiEff + YuNet + SFace model files; the HSEmotion predictor + YuNet detector +
SFace recognizer are load-tested → ``ModelCorruptError`` on failure.

The heavy runtime (``hsemotion_onnx``) is imported ONLY here (FR-013/R-9).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

from ...config import get_settings
from ...domain.result_types import MoodResult
from ...logging import get_logger
from .constants import (
    EMOTIEFF_MODEL_FILENAME,
    EMOTIEFF_MODEL_URL,
    EMOTIEFF_MODEL_VERSION,
    ModelCorruptError,
    SFACE_MODEL_FILENAME,
    SFACE_MODEL_URL,
    YUNET_MODEL_FILENAME,
    YUNET_MODEL_URL,
    YUNET_NMS_THRESHOLD,
    YUNET_TOP_K,
    resolve_mood_label,
)
from .face_crop import face_crop
from .model_downloader import ModelDownloader

logger = get_logger("face_insight.adapters.ml.emotieff_mood")

# The HSEmotion-onnx library key for the AFEW 8-class model (filename without
# the ``.onnx`` extension — the library appends it internally).
_HSEMOTION_MODEL_NAME = "enet_b0_8_best_afew"


def _bridge_to_hsemotion_cache(model_path: str) -> None:
    """Ensure the HSEmotion-onnx library can find our ModelDownloader-cached
    model file without re-downloading.

    The library's ``get_model_path`` looks in ``~/.hsemotion/<model_name>.onnx``.
    We place a copy there (if absent or stale) pointing at our ``models/`` cache
    so the wrapper uses our file (downloaded via ``ModelDownloader`` with our
    timeouts/atomic-rename) rather than its own ``urllib`` fetch.
    """
    cache_dir = Path.home() / ".hsemotion"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{_HSEMOTION_MODEL_NAME}.onnx"
    src = Path(model_path)
    if not target.exists() or target.stat().st_size != src.stat().st_size:
        try:
            shutil.copy2(src, target)
        except OSError as exc:  # pragma: no cover — filesystem edge case
            logger.warning("hsemotion_cache_bridge_failed", error=str(exc))


class EmotiEffMoodEstimator:
    """Concrete ``MoodEstimator`` port implementation using EmotiEff/HSEmotion
    via ONNX Runtime (spec 009, US1, FR-001).

    The EmotiEff model file AND the YuNet + SFace model files (for internal
    alignment detection + ``alignCrop``) are obtained via ``ModelDownloader``
    (FR-008/FR-009). Construction fails fast with ``ModelUnavailableError`` /
    ``ModelCorruptError`` (FR-009).
    """

    model_version = EMOTIEFF_MODEL_VERSION

    def __init__(
        self,
        *,
        score_threshold: float | None = None,
        nms_threshold: float = YUNET_NMS_THRESHOLD,
        top_k: int = YUNET_TOP_K,
        confidence_threshold: float | None = None,
        emotieff_model_path: str | None = None,
        yunet_model_path: str | None = None,
        sface_model_path: str | None = None,
        downloader: ModelDownloader | None = None,
    ) -> None:
        settings = get_settings()
        if score_threshold is None:
            score_threshold = settings.quality_threshold
        if confidence_threshold is None:
            confidence_threshold = settings.mood_confidence_threshold

        if downloader is None:
            downloader = ModelDownloader()

        # Obtain model files (lazy download or cache hit — FR-008/FR-009).
        if emotieff_model_path is None:
            emotieff_model_path = str(
                downloader.ensure(EMOTIEFF_MODEL_FILENAME, EMOTIEFF_MODEL_URL)
            )
        if yunet_model_path is None:
            yunet_model_path = str(
                downloader.ensure(YUNET_MODEL_FILENAME, YUNET_MODEL_URL)
            )
        if sface_model_path is None:
            sface_model_path = str(
                downloader.ensure(SFACE_MODEL_FILENAME, SFACE_MODEL_URL)
            )

        self._confidence_threshold = float(confidence_threshold)
        self._score_threshold = float(score_threshold)
        self._nms_threshold = float(nms_threshold)
        self._top_k = int(top_k)

        # Fail-fast load-test for the EmotiEff model (FR-009).
        try:
            _bridge_to_hsemotion_cache(emotieff_model_path)
            self._predictor = self._build_predictor()
        except Exception as exc:
            logger.error(
                "model_corrupt",
                model_name=EMOTIEFF_MODEL_FILENAME,
                error=str(exc),
            )
            raise ModelCorruptError(EMOTIEFF_MODEL_FILENAME, detail=str(exc)) from exc

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
            model_name=EMOTIEFF_MODEL_FILENAME,
            model_version=EMOTIEFF_MODEL_VERSION,
        )

    def _build_predictor(self) -> HSEmotionRecognizer:
        """Construct the HSEmotion predictor (load-test). Override hook for tests."""
        return HSEmotionRecognizer(model_name=_HSEMOTION_MODEL_NAME)

    def estimate_mood(self, face_image: bytes) -> MoodResult:
        """Estimate mood from ``face_image`` bytes → ``MoodResult`` (FR-001).

        Alignment is performed internally (research R-7): decode → YuNet detect
        → ``face_crop`` (alignCrop) → ``predict_emotions``.
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

        # 4. Emotion prediction → softmax probs (R-1).
        _emotion_name, probs = self._predictor.predict_emotions(aligned, logits=False)
        probs_arr = np.asarray(probs, dtype=np.float64)
        pred_index = int(np.argmax(probs_arr))
        top1_prob = float(probs_arr[pred_index])

        # 5. AFEW → PRD label mapping (FR-005) + low-confidence override (FR-006).
        label = resolve_mood_label(pred_index, top1_prob, self._confidence_threshold)

        # 6. MoodResult (FR-001). No biometric data logged (FR-016/R-12).
        return MoodResult(
            label=label,
            confidence=top1_prob,
            model_version=EMOTIEFF_MODEL_VERSION,
        )


__all__ = ["EmotiEffMoodEstimator"]
