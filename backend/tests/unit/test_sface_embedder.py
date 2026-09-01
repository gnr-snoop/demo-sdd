"""Port-conformance unit test for SFaceEmbedder (spec 008, US2, FR-002/FR-003).

Asserts ``SFaceEmbedder`` implements the ``Embedder`` protocol signature,
exposes the correct ``model_version``, and that ``EMBEDDING_DIM == 128`` matches
the mock (R-3). No model file is needed for these shape assertions.
"""

from __future__ import annotations

import inspect

from face_insight.adapters.mock.constants import EMBEDDING_DIM as MOCK_EMBEDDING_DIM
from face_insight.adapters.ml import EMBEDDING_DIM, SFACE_MODEL_VERSION, SFaceEmbedder
from face_insight.adapters.ml.sface_embedder import SFaceEmbedder as _Concrete
from face_insight.domain.ports import Embedder
from face_insight.domain.result_types import Embedding


def test_sface_embedder_implements_embedder_protocol():
    """SFaceEmbedder must declare an ``embed(face_image: bytes) -> Embedding``
    method matching the ``Embedder`` protocol signature (FR-002)."""
    assert hasattr(SFaceEmbedder, "embed")
    sig = inspect.signature(SFaceEmbedder.embed)
    params = list(sig.parameters)
    assert params == ["self", "face_image"], f"unexpected params: {params}"
    assert sig.return_annotation is Embedding or sig.return_annotation == "Embedding"


def test_sface_embedder_is_runtime_checkable_against_protocol():
    assert callable(getattr(SFaceEmbedder, "embed", None))


def test_sface_embedder_model_version_constant():
    """FR-003: the embedder exposes a fixed, identifiable model_version
    distinct from the mock version (``mock-embedder-v1``)."""
    assert SFACE_MODEL_VERSION == "sface-2021dec-v1"
    assert SFACE_MODEL_VERSION != "mock-embedder-v1"


def test_sface_embedder_class_has_model_version_attribute():
    assert hasattr(SFaceEmbedder, "model_version") or "model_version" in {
        k for k in vars(SFaceEmbedder)
    }


def test_embedding_dim_matches_mock():
    """R-3: SFace's 128-dim output matches the mock EMBEDDING_DIM=128 → no
    schema/result-type change (FR-018)."""
    assert EMBEDDING_DIM == 128
    assert EMBEDDING_DIM == MOCK_EMBEDDING_DIM


def test_embedding_shape_unchanged():
    """FR-018: Embedding still has vector/model_version (no new attrs)."""
    fields = {f.name for f in __import__("dataclasses").fields(Embedding)}
    assert fields == {"vector", "model_version"}


def test_sface_embedder_module_location():
    assert _Concrete.__module__ == "face_insight.adapters.ml.sface_embedder"
