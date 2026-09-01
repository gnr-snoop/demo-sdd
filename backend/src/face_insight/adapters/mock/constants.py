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
# Spec 005 (T002, R-5/R-11): mock age estimator exposes model_version
# "mock-age-estimator-v1" (FR-017 — identifiable adapter version so results
# are reproducible; consistent with spec 001 mock naming).
AGE_MODEL_VERSION = "mock-age-estimator-v1"
# Spec 004 (orchestrator pinned decision): mock mood estimator exposes
# model_version "mock-mood-v1" (FR-017 — identifiable adapter version).
MOOD_MODEL_VERSION = "mock-mood-v1"

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

# --- Spec 004 mood fixture control (T005/R-5) -------------------------------
# Byte markers embedded in the raw request image control the scriptable mock
# mood estimator's output for mood rejection/variation tests (R-5). The
# ScriptableMockMoodEstimator substring-searches the raw bytes for these markers.
MOOD_FELIZ_MARKER = b"FELIZ"              # → label "feliz", confidence 0.8
MOOD_TRISTE_MARKER = b"TRIST"             # → label "triste", confidence 0.7
MOOD_NO_CONCLUSIVE_MARKER = b"NOCONCLUSIVE"  # → label "no concluyente", confidence 0.3
MOOD_FAIL_MARKER = b"MOODFAIL"            # estimator raises → MoodInternalError (500)
MOOD_OUT_OF_SET_MARKER = b"OOSET"         # → out-of-set label "angry" → normalize to "no concluyente"

# --- Spec 005 age fixture control (T002/R-5) --------------------------------
# Byte markers embedded in the raw request image control the scriptable mock
# age estimator's output for age rejection/variation tests (R-5). The
# ScriptableMockAgeEstimator substring-searches the raw bytes for these markers.
AGEPOINT_MARKER = b"AGEPOINT"   # → point-only estimate 40 (no range) → derived symmetric range
AGERANGE_MARKER = b"AGERANGE"   # → range (35, 45) → estimatedAge = midpoint 40
AGEFAIL_MARKER = b"AGEFAIL"     # estimator raises → AgeInternalError (500)
