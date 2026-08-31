"""MockEmbedder (T046) — deterministic embedding (SC-005)."""

from __future__ import annotations

from ...domain.result_types import Embedding
from .constants import EMBEDDING_DIM, EMBEDDING_FILL, EMBED_MODEL_VERSION

# Hardcoded 128-dim vector of 0.1 repeats (data-model.md).
_VECTOR = [EMBEDDING_FILL] * EMBEDDING_DIM
_RESULT = Embedding(vector=_VECTOR, model_version=EMBED_MODEL_VERSION)


class MockEmbedder:
    """Returns a fixed 128-dim embedding of 0.1 repeats."""

    def embed(self, face_image: bytes) -> Embedding:
        return _RESULT
