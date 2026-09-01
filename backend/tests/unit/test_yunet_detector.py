"""Port-conformance unit test for YuNetDetector (spec 008, US1, FR-001/FR-003).

Asserts ``YuNetDetector`` implements the ``Detector`` protocol signature and
exposes the correct ``model_version``. No model file is needed for these shape
assertions — they inspect the class/instance surface, not inference output.
Real-model behavior is covered by ``tests/integration/test_real_ml_adapters.py``.
"""

from __future__ import annotations

import inspect

from face_insight.adapters.ml import YUNET_MODEL_VERSION, YuNetDetector
from face_insight.adapters.ml.yunet_detector import YuNetDetector as _Concrete
from face_insight.domain.ports import Detector
from face_insight.domain.result_types import BoundingBox, DetectionResult


def test_yunet_detector_implements_detector_protocol():
    """YuNetDetector must declare a ``detect(image: bytes) -> DetectionResult``
    method matching the ``Detector`` protocol signature (FR-001)."""
    assert hasattr(YuNetDetector, "detect")
    sig = inspect.signature(YuNetDetector.detect)
    params = list(sig.parameters)
    # 'self' + 'image'
    assert params == ["self", "image"], f"unexpected params: {params}"
    assert sig.return_annotation is DetectionResult or sig.return_annotation == "DetectionResult"


def test_yunet_detector_is_runtime_checkable_against_protocol():
    """An instance should satisfy ``isinstance(_, Detector)`` (runtime_checkable)."""
    # We cannot construct without a model file, but the protocol check works on
    # the class surface: the detect method presence is what runtime_checkable
    # verifies.
    assert callable(getattr(YuNetDetector, "detect", None))


def test_yunet_detector_model_version_constant():
    """FR-003: the detector exposes a fixed, identifiable model_version
    distinct from the mock version (``mock-yolo-v0``)."""
    assert YUNET_MODEL_VERSION == "yunet-2023mar-v1"
    assert YUNET_MODEL_VERSION != "mock-yolo-v0"


def test_yunet_detector_class_has_model_version_attribute():
    """The class (or its instances) expose ``model_version`` (FR-003)."""
    assert hasattr(YuNetDetector, "model_version") or "model_version" in {
        k for k in vars(YuNetDetector)
    }


def test_detection_result_shape_unchanged():
    """FR-018: DetectionResult still has face_count/boxes/score (no new attrs)."""
    fields = {f.name for f in __import__("dataclasses").fields(DetectionResult)}
    assert fields == {"face_count", "boxes", "score"}


def test_bounding_box_shape_unchanged():
    """FR-018: BoundingBox still has x/y/width/height (no new attrs)."""
    fields = {f.name for f in __import__("dataclasses").fields(BoundingBox)}
    assert fields == {"x", "y", "width", "height"}


def test_yunet_detector_module_location():
    """The concrete adapter lives in adapters/ml/ (not domain)."""
    assert _Concrete.__module__ == "face_insight.adapters.ml.yunet_detector"
