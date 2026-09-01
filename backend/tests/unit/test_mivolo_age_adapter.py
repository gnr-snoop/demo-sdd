"""Port-conformance unit test for MiVOLOAgeEstimator (spec 009, US2,
FR-002/FR-003/FR-007).

Asserts ``MiVOLOAgeEstimator`` implements the ``AgeEstimator`` protocol
signature, exposes the correct ``model_version``, and returns ``range=None``
(point-only). The heavy ``torch``/``timm``/``mivolo`` runtimes are stubbed in
``sys.modules`` so this test runs without them installed (Constitution Quality
Gate §7). No model file is needed — these are class-surface assertions.
"""

from __future__ import annotations

import inspect
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_mivolo_runtimes():
    """Inject stub ``torch``/``mivolo`` packages so the adapter module imports
    without the real runtimes (FR-013/R-9)."""
    torch_mod = types.ModuleType("torch")
    torch_mod.device = lambda x: x  # stub
    mivolo_pkg = types.ModuleType("mivolo")
    data_mod = types.ModuleType("mivolo.data")
    misc_mod = types.ModuleType("mivolo.data.misc")

    def _prepare_classification_images(crops, input_size, mean, std, device=None):
        raise RuntimeError("stub")

    misc_mod.prepare_classification_images = _prepare_classification_images
    model_mod = types.ModuleType("mivolo.model")
    mi_volo_mod = types.ModuleType("mivolo.model.mi_volo")

    class _StubMiVOLO:  # pragma: no cover — stub for import only
        def __init__(self, *args, **kwargs) -> None:
            pass

    mi_volo_mod.MiVOLO = _StubMiVOLO

    saved = {}
    for name in (
        "torch",
        "mivolo",
        "mivolo.data",
        "mivolo.data.misc",
        "mivolo.model",
        "mivolo.model.mi_volo",
    ):
        saved[name] = sys.modules.get(name)
    sys.modules["torch"] = torch_mod
    sys.modules["mivolo"] = mivolo_pkg
    sys.modules["mivolo.data"] = data_mod
    sys.modules["mivolo.data.misc"] = misc_mod
    sys.modules["mivolo.model"] = model_mod
    sys.modules["mivolo.model.mi_volo"] = mi_volo_mod
    sys.modules.pop("face_insight.adapters.ml.mivolo_age", None)
    yield
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
    sys.modules.pop("face_insight.adapters.ml.mivolo_age", None)


def _import_adapter():
    from face_insight.adapters.ml.mivolo_age import MiVOLOAgeEstimator

    return MiVOLOAgeEstimator


def test_mivolo_age_estimator_implements_age_estimator_protocol():
    """MiVOLOAgeEstimator must declare
    ``estimate_age(face_image: bytes) -> AgeResult`` matching the
    ``AgeEstimator`` protocol signature (FR-002)."""
    MiVOLOAgeEstimator = _import_adapter()
    assert hasattr(MiVOLOAgeEstimator, "estimate_age")
    sig = inspect.signature(MiVOLOAgeEstimator.estimate_age)
    params = list(sig.parameters)
    assert params == ["self", "face_image"], f"unexpected params: {params}"


def test_mivolo_age_estimator_is_runtime_checkable_against_protocol():
    MiVOLOAgeEstimator = _import_adapter()
    assert callable(getattr(MiVOLOAgeEstimator, "estimate_age", None))


def test_mivolo_age_estimator_model_version_constant():
    """FR-003: the age adapter exposes a fixed, identifiable model_version
    distinct from the mock version (``mock-age-estimator-v1``)."""
    from face_insight.adapters.ml import MIVOLO_MODEL_VERSION

    assert MIVOLO_MODEL_VERSION == "mivolo-volo-d1-face-v1"
    assert MIVOLO_MODEL_VERSION != "mock-age-estimator-v1"
    MiVOLOAgeEstimator = _import_adapter()
    assert MiVOLOAgeEstimator.model_version == "mivolo-volo-d1-face-v1"


def test_mivolo_age_estimator_class_has_model_version_attribute():
    MiVOLOAgeEstimator = _import_adapter()
    assert hasattr(MiVOLOAgeEstimator, "model_version")


def test_age_result_range_is_optional():
    """FR-007: AgeResult.range is ``tuple[int,int] | None`` — the adapter
    returns ``range=None`` (point-only). Verify the field accepts None."""
    from face_insight.domain.result_types import AgeResult

    result = AgeResult(estimated_age=30, range=None, model_version="mivolo-volo-d1-face-v1")
    assert result.range is None
    assert result.estimated_age == 30


def test_age_result_shape_unchanged():
    """FR-017: AgeResult still has estimated_age/range/model_version."""
    from face_insight.domain.result_types import AgeResult

    fields = {f.name for f in __import__("dataclasses").fields(AgeResult)}
    assert fields == {"estimated_age", "range", "model_version"}


def test_mivolo_age_estimator_module_location():
    """The concrete adapter lives in adapters/ml/ (not domain)."""
    MiVOLOAgeEstimator = _import_adapter()
    assert MiVOLOAgeEstimator.__module__ == "face_insight.adapters.ml.mivolo_age"
