"""Constants for the concrete ML adapters (spec 008, FR-003/R-4).

Model URLs point at the OpenCV model zoo (raw GitHub). Version strings are
fixed and identifiable (FR-003). Error classes are adapter-layer exceptions
raised at construction/load time (FR-009).
"""

from __future__ import annotations

# --- Model files & URLs (R-4) ----------------------------------------------
YUNET_MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
SFACE_MODEL_FILENAME = "face_recognition_sface_2021dec.onnx"

YUNET_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
SFACE_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx"
)

# --- Model versions (FR-003) — distinct from mock versions -----------------
YUNET_MODEL_VERSION = "yunet-2023mar-v1"
SFACE_MODEL_VERSION = "sface-2021dec-v1"

# --- Licenses (F-001, FR-004, Constitution Principle III) ------------------
# Both are OSI-approved open-source licenses.
YUNET_LICENSE = "MIT"
SFACE_LICENSE = "Apache-2.0"

# --- Embedding dimension (R-3) — matches mock EMBEDDING_DIM=128 -----------
EMBEDDING_DIM = 128

# --- Recommended thresholds (R-7) ------------------------------------------
# Production cosine threshold for SFace+YuNet (OpenCV LFW calibration,
# 99.60% accuracy). The mock-mode default stays 0.5 (backward compatible).
PRODUCTION_VERIFICATION_THRESHOLD = 0.363

# --- Detector construction defaults (R-1/R-2) ------------------------------
YUNET_NMS_THRESHOLD = 0.3
YUNET_TOP_K = 5000

# --- Aligned crop size (SFace expected input, R-5) -------------------------
ALIGNED_CROP_SIZE = 112

# --- Spec 009 mood/age model constants (FR-003/FR-005, R-4/R-8) -------------
# EmotiEff/HSEmotion mood model (ONNX Runtime, Apache 2.0 code + model).
EMOTIEFF_MODEL_FILENAME = "enet_b0_8_best_afew.onnx"
EMOTIEFF_MODEL_URL = (
    "https://github.com/HSE-asavchenko/face-emotion-recognition/raw/main/"
    "models/affectnet_emotions/onnx/enet_b0_8_best_afew.onnx"
)
EMOTIEFF_MODEL_VERSION = "emotieff-enet-b0-afew-v1"
EMOTIEFF_LICENSE = "Apache-2.0"

# MiVOLO face-only age checkpoint (PyTorch CPU + timm, Apache 2.0 code +
# open-weights checkpoint — research R-3).
MIVOLO_CHECKPOINT_FILENAME = "volo_d1_224_369_age_only-e7ee8cd0.pth"
MIVOLO_CHECKPOINT_URL = (
    "https://drive.usercontent.google.com/download?"
    "id=17ysOqgG3FUyEuxrV3Uh49EpmuOiGDxrq&export=download&confirm=t"
)
MIVOLO_MODEL_VERSION = "mivolo-volo-d1-face-v1"
MIVOLO_LICENSE = "Apache-2.0"

# AFEW 8-class → PRD §6.4 label mapping (FR-005, research R-4).
#
# The HSEmotion-onnx library's ``idx_to_class`` for ``enet_b0_8_best_afew`` is:
#   {0: 'Anger', 1: 'Contempt', 2: 'Disgust', 3: 'Fear',
#    4: 'Happiness', 5: 'Neutral', 6: 'Sadness', 7: 'Surprise'}
#
# This ordering is verified at runtime by the F-04 integration assertion
# (``test_afew_index_order_matches_library``) using a known fixture. The 4 AFEW
# emotions with no PRD category (Anger, Contempt, Disgust, Fear) are reported as
# ``"no concluyente"`` rather than dropped or mislabeled (research R-4).
AFEW_INDEX_TO_EMOTION_NAME = {
    0: "Anger",
    1: "Contempt",
    2: "Disgust",
    3: "Fear",
    4: "Happiness",
    5: "Neutral",
    6: "Sadness",
    7: "Surprise",
}

AFEW_TO_PRD_LABEL_MAP = {
    0: "no concluyente",   # Anger    — no PRD category
    1: "no concluyente",   # Contempt — no PRD category
    2: "no concluyente",   # Disgust  — no PRD category
    3: "no concluyente",   # Fear     — no PRD category
    4: "feliz",            # Happiness
    5: "neutral",          # Neutral
    6: "triste",           # Sadness
    7: "sorprendido",      # Surprise
}

# Default mood confidence threshold (FR-006, R-5). Mirrors the config default;
# kept here as an adapter-layer constant for documentation/tests.
DEFAULT_MOOD_CONFIDENCE_THRESHOLD = 0.5


def resolve_mood_label(pred_index: int, top1_prob: float, threshold: float) -> str:
    """Pure label-resolution for the EmotiEff mood adapter (FR-005/FR-006).

    Maps the AFEW ``argmax`` index → PRD §6.4 label via
    ``AFEW_TO_PRD_LABEL_MAP``, then applies the low-confidence override: if
    ``top1_prob < threshold`` the label becomes ``"no concluyente"`` (the low
    confidence is still returned by the adapter). Kept in ``constants.py`` so it
    is unit-testable without the heavy ``hsemotion_onnx`` runtime (FR-013/R-9).
    """
    label = AFEW_TO_PRD_LABEL_MAP[pred_index]
    if top1_prob < threshold:
        return "no concluyente"
    return label


# --- Error classes (FR-009) -------------------------------------------------
class ModelUnavailableError(RuntimeError):
    """Raised when a model file cannot be obtained (network failure, timeout,
    unwritable cache). Names the model and URL for an actionable error (FR-009).
    """

    def __init__(self, model_name: str, url: str, detail: str = "") -> None:
        self.model_name = model_name
        self.url = url
        msg = f"Could not obtain model '{model_name}' from {url}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class ModelCorruptError(RuntimeError):
    """Raised when a model file is present but fails the load-test (corrupt /
    truncated). Names the model for an actionable error (FR-009)."""

    def __init__(self, model_name: str, detail: str = "") -> None:
        self.model_name = model_name
        msg = f"Model '{model_name}' is corrupt or could not be loaded"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class InvalidFaceBox(ValueError):
    """Raised by ``face_crop`` when the detection bounding box has zero or
    negative area (FR-007 AC-3, R-5)."""

    def __init__(self, detail: str = "bounding box has zero or negative area") -> None:
        super().__init__(detail)


__all__ = [
    "YUNET_MODEL_FILENAME",
    "SFACE_MODEL_FILENAME",
    "YUNET_MODEL_URL",
    "SFACE_MODEL_URL",
    "YUNET_MODEL_VERSION",
    "SFACE_MODEL_VERSION",
    "YUNET_LICENSE",
    "SFACE_LICENSE",
    "EMBEDDING_DIM",
    "PRODUCTION_VERIFICATION_THRESHOLD",
    "YUNET_NMS_THRESHOLD",
    "YUNET_TOP_K",
    "ALIGNED_CROP_SIZE",
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
