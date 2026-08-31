"""MockEmbedder (T046) — deterministic embedding (SC-005).

Spec 003 (T017) adds ``ScriptableMockEmbedder`` for login rejection tests:
byte markers in the raw image control the output (non-matching, dimension
mismatch, embedder failure). Default (no marker) → the same 128-dim 0.1 vector
as ``MockEmbedder``, which yields cosine similarity 1.0 against the stored
template (happy path).
"""

from __future__ import annotations

from ...domain.result_types import Embedding
from .constants import (
    DIM_MISMATCH_MARKER,
    EMBEDDING_DIM,
    EMBEDDING_FILL,
    EMBED_FAIL_MARKER,
    EMBED_MODEL_VERSION,
    MATCH_MARKER,
    NON_MATCH_MARKER,
)

# Hardcoded 128-dim vector of 0.1 repeats (data-model.md).
_VECTOR = [EMBEDDING_FILL] * EMBEDDING_DIM
_RESULT = Embedding(vector=_VECTOR, model_version=EMBED_MODEL_VERSION)


class MockEmbedder:
    """Returns a fixed 128-dim embedding of 0.1 repeats."""

    def embed(self, face_image: bytes) -> Embedding:
        return _RESULT


# --- Scriptable (fixture-controllable) variant for login rejection tests (T017) ---
# An orthogonal vector: 0.1 on dim 0, -0.1 on dim 1, 0 elsewhere. Cosine
# similarity against the all-0.1 template is 0.0 (< default threshold 0.5).
_ORTH_VECTOR = [0.0] * EMBEDDING_DIM
_ORTH_VECTOR[0] = 0.1
_ORTH_VECTOR[1] = -0.1


class ScriptableMockEmbedder:
    """Embedder whose output is controlled by byte markers in the raw image.

    Marker precedence: EMBEDFAIL > DIMMISMATCH > NONMATCH > MATCHFACE > default.
      - ``EMBEDFAIL``    → raises RuntimeError (mapped to LoginInternalError → 500)
      - ``DIMMISMATCH``  → 127-dim vector (triggers ComparisonError → 500)
      - ``NONMATCH``     → orthogonal vector (cosine similarity 0.0 < 0.5 → auth_failed)
      - ``MATCHFACE``    → same as default (similarity 1.0 → happy path)
      - default          → 128-dim 0.1 vector (similarity 1.0 → happy path)
    """

    def embed(self, face_image: bytes) -> Embedding:
        if face_image is None:
            return _RESULT
        if EMBED_FAIL_MARKER in face_image:
            raise RuntimeError("scriptable embedder failure")
        if DIM_MISMATCH_MARKER in face_image:
            return Embedding(vector=[EMBEDDING_FILL] * (EMBEDDING_DIM - 1), model_version=EMBED_MODEL_VERSION)
        if NON_MATCH_MARKER in face_image:
            return Embedding(vector=list(_ORTH_VECTOR), model_version=EMBED_MODEL_VERSION)
        return _RESULT


__all__ = ["MockEmbedder", "ScriptableMockEmbedder"]
