"""Shared deterministic constants for mock adapters (SC-005)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

# Fixed UUID constant for the mock user (data-model.md).
FIXED_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
FIXED_SESSION_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
FIXED_TEMPLATE_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")

# Fixed timestamp (UTC) — no clock dependence in mocks.
FIXED_NOW = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

# Model versions (FR-012).
EMBED_MODEL_VERSION = "mock-embedder-v1"
DETECTOR_MODEL_VERSION = "mock-yolo-v0"
AGE_MODEL_VERSION = "mock-age-v0"
MOOD_MODEL_VERSION = "mock-mood-v0"

# Embedding dimension.
EMBEDDING_DIM = 128
EMBEDDING_FILL = 0.1

# --- Spec 003 login fixture control (T017) ---------------------------------
# Byte markers embedded in the raw request image control the mock embedder's
# output for login rejection tests (R-6). The ScriptableMockEmbedder substring-
# searches the raw bytes for these markers.
NON_MATCH_MARKER = b"NONMATCH"   # embedding orthogonal to the stored template → similarity < threshold
MATCH_MARKER = b"MATCHFACE"      # embedding identical to the stored template → similarity = 1.0
DIM_MISMATCH_MARKER = b"DIMMISMATCH"  # embedding of a different dimension → ComparisonError
EMBED_FAIL_MARKER = b"EMBEDFAIL"      # embedder raises → LoginInternalError (500)
