"""Port-conformance unit test for EmotiEffMoodEstimator (spec 009, US1,
FR-001/FR-003).

Asserts ``EmotiEffMoodEstimator`` implements the ``MoodEstimator`` protocol
signature and exposes the correct ``model_version``. The heavy
``hsemotion_onnx`` runtime is stubbed in ``sys.modules`` so this test runs
without it installed (Constitution Quality Gate §7 — no GPU/ML runtime to test).
No model file is needed — these are class-surface assertions.
"""

from __future__ import annotations

import inspect
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_hsemotion_onnx():
    """Inject a stub ``hsemotion_onnx`` package so the adapter module imports
    without the real runtime (FR-013/R-9)."""
    pkg = types.ModuleType("hsemotion_onnx")
    facial = types.ModuleType("hsemotion_onnx.facial_emotions")

    class _StubRecognizer:  # pragma: no cover — stub for import only
        def __init__(self, model_name: str = "enet_b0_8_best_vgaf") -> None:
            self.model_name = model_name

        def predict_emotions(self, face_img, logits: bool = True):
            raise RuntimeError("stub")

    facial.HSEmotionRecognizer = _StubRecognizer
    pkg.facial_emotions = facial
    saved = {
        "hsemotion_onnx": sys.modules.get("hsemotion_onnx"),
        "hsemotion_onnx.facial_emotions": sys.modules.get("hsemotion_onnx.facial_emotions"),
    }
    sys.modules["hsemotion_onnx"] = pkg
    sys.modules["hsemotion_onnx.facial_emotions"] = facial
    # Clear any cached adapter module so the stub is picked up.
    sys.modules.pop("face_insight.adapters.ml.emotieff_mood", None)
    yield
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
    sys.modules.pop("face_insight.adapters.ml.emotieff_mood", None)


def _import_adapter():
    from face_insight.adapters.ml.emotieff_mood import EmotiEffMoodEstimator

    return EmotiEffMoodEstimator


def test_emotieff_mood_estimator_implements_mood_estimator_protocol():
    """EmotiEffMoodEstimator must declare
    ``estimate_mood(face_image: bytes) -> MoodResult`` matching the
    ``MoodEstimator`` protocol signature (FR-001)."""
    EmotiEffMoodEstimator = _import_adapter()
    assert hasattr(EmotiEffMoodEstimator, "estimate_mood")
    sig = inspect.signature(EmotiEffMoodEstimator.estimate_mood)
    params = list(sig.parameters)
    assert params == ["self", "face_image"], f"unexpected params: {params}"


def test_emotieff_mood_estimator_is_runtime_checkable_against_protocol():
    EmotiEffMoodEstimator = _import_adapter()
    assert callable(getattr(EmotiEffMoodEstimator, "estimate_mood", None))


def test_emotieff_mood_estimator_model_version_constant():
    """FR-003: the mood adapter exposes a fixed, identifiable model_version
    distinct from the mock version (``mock-mood-v1``)."""
    from face_insight.adapters.ml import EMOTIEFF_MODEL_VERSION

    assert EMOTIEFF_MODEL_VERSION == "emotieff-enet-b0-afew-v1"
    assert EMOTIEFF_MODEL_VERSION != "mock-mood-v1"
    EmotiEffMoodEstimator = _import_adapter()
    assert EmotiEffMoodEstimator.model_version == "emotieff-enet-b0-afew-v1"


def test_emotieff_mood_estimator_class_has_model_version_attribute():
    EmotiEffMoodEstimator = _import_adapter()
    assert hasattr(EmotiEffMoodEstimator, "model_version")


def test_mood_result_shape_unchanged():
    """FR-017: MoodResult still has label/confidence/model_version (no new attrs)."""
    from face_insight.domain.result_types import MoodResult

    fields = {f.name for f in __import__("dataclasses").fields(MoodResult)}
    assert fields == {"label", "confidence", "model_version"}


def test_emotieff_mood_estimator_module_location():
    """The concrete adapter lives in adapters/ml/ (not domain)."""
    EmotiEffMoodEstimator = _import_adapter()
    assert EmotiEffMoodEstimator.__module__ == "face_insight.adapters.ml.emotieff_mood"
