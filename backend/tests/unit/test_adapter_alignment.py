"""Unit test for shared face_crop alignment reuse in the concrete mood/age
adapters (spec 009, US3, FR-008, research R-7).

Asserts both ``EmotiEffMoodEstimator`` and ``MiVOLOAgeEstimator`` call the
shared ``face_crop`` utility (from spec 008) during inference and raise
``ValueError("no face detected for alignment")`` when the internal YuNet
detection finds zero faces. The heavy ML runtimes are stubbed so this test runs
without them installed (Constitution Quality Gate §7).
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _stub_heavy_runtimes():
    """Stub hsemotion_onnx + torch + mivolo so both adapter modules import."""
    # hsemotion_onnx
    hsemotion_pkg = types.ModuleType("hsemotion_onnx")
    hsemotion_facial = types.ModuleType("hsemotion_onnx.facial_emotions")

    class _StubRecognizer:
        def __init__(self, model_name: str = "enet_b0_8_best_vgaf") -> None:
            self.model_name = model_name

        def predict_emotions(self, face_img, logits: bool = True):
            return "Neutral", np.array([0.0] * 8)

    hsemotion_facial.HSEmotionRecognizer = _StubRecognizer
    # torch + mivolo
    torch_mod = types.ModuleType("torch")
    torch_mod.device = lambda x: x
    mivolo_pkg = types.ModuleType("mivolo")
    mivolo_data = types.ModuleType("mivolo.data")
    mivolo_misc = types.ModuleType("mivolo.data.misc")
    mivolo_misc.prepare_classification_images = lambda *a, **k: None
    mivolo_model = types.ModuleType("mivolo.model")
    mivolo_mi_volo = types.ModuleType("mivolo.model.mi_volo")

    class _StubMiVOLO:
        def __init__(self, *a, **k) -> None:
            self.meta = MagicMock(only_age=True, min_age=0, max_age=100, avg_age=50)
            self.input_size = 224
            self.data_config = {"mean": [0.5] * 3, "std": [0.5] * 3}
            self.device = "cpu"

        def inference(self, x):
            return MagicMock()

    mivolo_mi_volo.MiVOLO = _StubMiVOLO

    saved = {}
    for name in (
        "hsemotion_onnx", "hsemotion_onnx.facial_emotions",
        "torch", "mivolo", "mivolo.data", "mivolo.data.misc",
        "mivolo.model", "mivolo.model.mi_volo",
    ):
        saved[name] = sys.modules.get(name)
    sys.modules["hsemotion_onnx"] = hsemotion_pkg
    sys.modules["hsemotion_onnx.facial_emotions"] = hsemotion_facial
    sys.modules["torch"] = torch_mod
    sys.modules["mivolo"] = mivolo_pkg
    sys.modules["mivolo.data"] = mivolo_data
    sys.modules["mivolo.data.misc"] = mivolo_misc
    sys.modules["mivolo.model"] = mivolo_model
    sys.modules["mivolo.model.mi_volo"] = mivolo_mi_volo
    sys.modules.pop("face_insight.adapters.ml.emotieff_mood", None)
    sys.modules.pop("face_insight.adapters.ml.mivolo_age", None)
    yield
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
    sys.modules.pop("face_insight.adapters.ml.emotieff_mood", None)
    sys.modules.pop("face_insight.adapters.ml.mivolo_age", None)


def _make_adapter(cls_name: str):
    """Construct an adapter with stubbed cv2 detector/recognizer (no model files)."""
    import cv2

    if cls_name == "EmotiEffMoodEstimator":
        from face_insight.adapters.ml.emotieff_mood import EmotiEffMoodEstimator

        cls = EmotiEffMoodEstimator
    else:
        from face_insight.adapters.ml.mivolo_age import MiVOLOAgeEstimator

        cls = MiVOLOAgeEstimator

    adapter = cls.__new__(cls)
    adapter._detector = MagicMock()
    adapter._recognizer = MagicMock()
    adapter._confidence_threshold = 0.5
    if cls_name == "EmotiEffMoodEstimator":
        adapter._predictor = MagicMock()
        adapter._predictor.predict_emotions = lambda img, logits=True: (
            "Neutral",
            np.array([0.1, 0.1, 0.1, 0.1, 0.5, 0.05, 0.02, 0.03]),
        )
    else:
        adapter._model = MagicMock()
        adapter._model.meta = MagicMock(only_age=True, min_age=0, max_age=100, avg_age=50)
        adapter._model.input_size = 224
        adapter._model.data_config = {"mean": [0.5] * 3, "std": [0.5] * 3}
        adapter._model.device = "cpu"
        adapter._model.inference = lambda x: np.array([[30.0]])
    return adapter


def _fake_image_bytes() -> bytes:
    """Minimal decodable JPEG-ish bytes (cv2.imdecode returns a small array)."""
    # 1x1 white pixel JPEG.
    import cv2

    img = np.ones((4, 4, 3), dtype=np.uint8) * 255
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def test_emotieff_calls_face_crop():
    """T016/FR-008: EmotiEffMoodEstimator.estimate_mood calls face_crop."""
    from face_insight.adapters.ml import face_crop

    adapter = _make_adapter("EmotiEffMoodEstimator")
    # Stub the internal detector to return one face box.
    face_box = np.array([0.0, 0.0, 4.0, 4.0] + [0.0] * 10 + [0.9])
    adapter._detector.detect = lambda img: (None, np.array([face_box]))
    with patch("face_insight.adapters.ml.emotieff_mood.face_crop", wraps=face_crop) as spy:
        result = adapter.estimate_mood(_fake_image_bytes())
        assert spy.called
    assert result.model_version == "emotieff-enet-b0-afew-v1"


def test_mivolo_calls_face_crop():
    """T016/FR-008: MiVOLOAgeEstimator.estimate_age calls face_crop."""
    from face_insight.adapters.ml import face_crop

    adapter = _make_adapter("MiVOLOAgeEstimator")
    face_box = np.array([0.0, 0.0, 4.0, 4.0] + [0.0] * 10 + [0.9])
    adapter._detector.detect = lambda img: (None, np.array([face_box]))
    with patch("face_insight.adapters.ml.mivolo_age.face_crop", wraps=face_crop) as spy:
        result = adapter.estimate_age(_fake_image_bytes())
        assert spy.called
    assert result.range is None


def test_emotieff_raises_on_zero_faces():
    """T016/R-7: EmotiEffMoodEstimator raises ValueError on zero faces."""
    adapter = _make_adapter("EmotiEffMoodEstimator")
    adapter._detector.detect = lambda img: (None, None)
    with pytest.raises(ValueError, match="no face detected for alignment"):
        adapter.estimate_mood(_fake_image_bytes())


def test_mivolo_raises_on_zero_faces():
    """T016/R-7: MiVOLOAgeEstimator raises ValueError on zero faces."""
    adapter = _make_adapter("MiVOLOAgeEstimator")
    adapter._detector.detect = lambda img: (None, np.zeros((0, 15)))
    with pytest.raises(ValueError, match="no face detected for alignment"):
        adapter.estimate_age(_fake_image_bytes())
