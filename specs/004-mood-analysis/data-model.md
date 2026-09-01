# Data Model: Mood Analysis (Fase 4)

**Spec**: [spec.md](./spec.md) | **Branch**: `004-mood-analysis` | **Date**: 2026-08-31

> **No new persistent entity is introduced in this spec.** The mood result is a **transient view model** (FR-014 — frontend state only; no `AnalysisRequest` audit row, no DB write, no migration). This document defines the transient view model, the domain value objects touched, the port contracts exercised, and the label/error enumerations.

---

## Entities

### MoodResult (transient view model — NOT persisted)

The result of a single mood analysis, returned to the frontend and held in client state until a new analysis or session end.

| Field | Type | Required | Validation / Notes |
|-------|------|----------|--------------------|
| `label` | `str` | yes | ∈ `{neutral, feliz, triste, sorprendido, no concluyente}` (FR-004). Normalized from the port output; out-of-set/low-quality → `no concluyente`. |
| `confidence` | `float \| None` | no | `float ∈ [0.0, 1.0]` when present, or `None`/omitted when the estimator does not produce one (FR-012a). Clamped to `[0,1]` by the service. Rendered as `≈NN%` (nearest integer) in the frontend; omitted from the UI when null. |
| `disclaimer` | `str` | yes | Fixed PRD §8 string, returned verbatim (FR-003). |

**Persistence**: None. The result lives in React component state (`Dashboard`) and is discarded on unmount/logout (FR-010/FR-014). Re-accessing `/dashboard` after logout requires re-authentication and shows no prior result.

**Source**: derived from `MoodEstimator.estimate_mood()` port output + `normalize_mood_label()`; no DB row, no filesystem artifact.

### Reused entities (unchanged)

| Entity | Spec | Role in this spec |
|--------|------|-------------------|
| `AuthSession` | 003 | Gates `POST /api/analysis/mood` via `require_valid_session`. No new attributes. Read-only (the endpoint validates the session; it does not create/modify one). |
| `User` | 002 | Identified by the session's `userId` for logging only (not for result persistence). No new attributes. |

### Deliberately NOT introduced

| Entity | Reason |
|--------|--------|
| `AnalysisRequest` | PRD §7 optional, §19 pending; no AC requires an audit row. Constitution Principle I (YAGNI). Deferred to a later spec if a demo narrative need arises (FR-014). |

---

## Domain Value Objects

### MoodResult (domain) — `domain/result_types.py`

```python
@dataclass(frozen=True)
class MoodResult:
    label: str
    confidence: float | None   # widened from float (spec 001) to float | None
    model_version: str
```

**Change from spec 001**: `confidence` widened from `float` to `float | None` to permit null/omitted confidence per PRD §6.4 (backward-compatible; the mock always supplies a value). `model_version` carries the adapter's identifiable version (FR-017 — `"mock-mood-v0"` for the mock).

### DetectionResult (domain) — `domain/result_types.py` (unchanged)

```python
@dataclass(frozen=True)
class DetectionResult:
    face_count: int
    boxes: list[BoundingBox]
    score: float
```

Reused from spec 001/002. The mood service checks `face_count == 1` and `score >= quality_threshold`.

---

## Ports (exercised, unchanged)

| Port | Method | Signature | Adapter (this spec) |
|------|--------|-----------|---------------------|
| `Detector` | `detect` | `(image: bytes) -> DetectionResult` | `MockDetector` (production default) / `ScriptableMockDetector` (tests) — spec 002 |
| `MoodEstimator` | `estimate_mood` | `(face_image: bytes) -> MoodResult` | `MockMoodEstimator` (production default, FR-016) / `ScriptableMockMoodEstimator` (tests) |
| `SessionManager` | `get_valid` | `(session_id, now) -> AuthSession \| None` | reused from spec 003 (via `require_valid_session`) |

No port is added or modified. The `MoodService` depends only on `Detector` + `MoodEstimator` (FR-015/SC-009).

---

## Mood Service use-case — `domain/mood.py` (NEW)

```python
class MoodService:
    def __init__(self, detector: Detector, mood_estimator: MoodEstimator,
                 quality_threshold: float = 0.5) -> None: ...

    def analyze(self, image_bytes: bytes) -> MoodResult:
        """Orchestration (FR-005):
        1. detect (exactly one face + quality threshold) — raises NoFace/MultipleFaces/InsufficientQuality
        2. estimate_mood — port failure -> MoodInternalError
        3. normalize_mood_label(result.label) — out-of-set -> 'no concluyente'
        4. clamp confidence to [0,1] (None passes through)
        5. return MoodResult
        """
```

**Purity**: imports only `Detector`, `MoodEstimator`, `MoodResult`, and the domain exceptions. No FastAPI, no Pillow, no SQLAlchemy, no ML library (enforced by `test_domain_purity`).

### Label normalization — `normalize_mood_label(label: str) -> str`

```
VALID_LABELS = {"neutral", "feliz", "triste", "sorprendido", "no concluyente"}
normalize_mood_label(label) = label if label in VALID_LABELS else "no concluyente"
```

Pure function; trivially unit-testable (FR-004).

---

## Label set (FR-004)

| Label | Meaning |
|-------|---------|
| `neutral` | Neutral mood |
| `feliz` | Happy |
| `triste` | Sad |
| `sorprendido` | Surprised |
| `no concluyente` | Inconclusive (also the normalization target for any out-of-set/low-quality port output) |

Enforced by `normalize_mood_label` in the domain service and asserted by the contract test (the `200` response `label` is always a member of this set).

---

## Error codes & status mapping (FR-006, FR-007)

Error body shape (spec 002 pinned, reused verbatim): `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}`.

| Status | Code | Condition | Actionable message (es) |
|--------|------|-----------|-------------------------|
| `401` | `unauthenticated` | no/invalid/expired/revoked session | "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo." (reused from spec 003) |
| `400` | `invalid_image` | undecodable/unsupported/oversized image | "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB." (reused from spec 002/003) |
| `400` | `no_face` | detector returns `face_count == 0` | "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar." |
| `400` | `multiple_faces` | detector returns `face_count > 1` | "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura." |
| `400` | `insufficient_quality` | single face but `score < quality_threshold` | "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar." |
| `500` | `internal_error` | detector/mood_estimator port raises; unexpected failure | "Ocurrió un error inesperado. Inténtalo de nuevo." |

**Reservation**: `401` is reserved exclusively for `unauthenticated` (session-gating). `400` for actionable capture-quality codes. `500` for recoverable `internal_error` (FR-007). No mood result is produced on any error path.

---

## Frontend state machine — `useMoodMachine`

| State | Description |
|-------|-------------|
| `idle` | No analysis in progress; mood button enabled |
| `processing` | Capture sent, awaiting response; mood button disabled (FR-014), loading indicator shown |
| `result` | Success; result (label + optional ≈NN% + disclaimer) displayed; button re-enabled |
| `error` | Recoverable error; actionable error surface + retry shown; button re-enabled |
| `camera_unavailable` | Camera permission denied/unavailable; actionable error + retry; no backend call (FR-012c) |

| Event | Transitions |
|-------|-------------|
| `CAPTURE` | `idle` → `processing` |
| `SUCCEEDED` | `processing` → `result` |
| `FAILED` | `processing` → `error` |
| `CAMERA_DENIED` | `idle` → `camera_unavailable` |
| `RETRY` | `error` → `idle`; `camera_unavailable` → `idle` |
| `RESET` | any → `idle` |

The most recent result is held in `Dashboard` component state and remains visible until a new analysis or unmount/logout (FR-010). Invalid transitions are ignored (state-machine correctness, mirroring `useLoginMachine`).
