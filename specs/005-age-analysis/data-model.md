# Data Model: Age Estimation (Fase 4 — age)

**Spec**: [spec.md](./spec.md) | **Branch**: `005-age-analysis` | **Date**: 2026-08-31

> **No new persistent entity is introduced in this spec.** The age result is a **transient view model** (FR-014 — frontend state only; no `AnalysisRequest` audit row, no DB write, no migration). This document defines the transient view model, the domain value objects touched, the port contracts exercised, and the normalization/error enumerations.

---

## Entities

### AgeResult (transient view model — NOT persisted)

The result of a single age analysis, returned to the frontend and held in client state until a new age analysis or session end.

| Field | Type | Required | Validation / Notes |
|-------|------|----------|--------------------|
| `estimatedAge` | `int` | yes | Integer years. `min <= estimatedAge <= max` (FR-002/FR-004). |
| `range.min` | `int` | yes | Integer years, `min >= 0` (FR-002/FR-004). |
| `range.max` | `int` | yes | Integer years, `max >= min` (FR-002/FR-004). |
| `disclaimer` | `str` | yes | Fixed PRD §8 string, returned verbatim (FR-003). |

**Persistence**: None. The result lives in React component state (`Dashboard`) and is discarded on unmount/logout (FR-010/FR-014). Re-accessing `/dashboard` after logout requires re-authentication and shows no prior result.

**Source**: derived from `AgeEstimator.estimate_age()` port output + `normalize_age_result()`; no DB row, no filesystem artifact.

### Reused entities (unchanged)

| Entity | Spec | Role in this spec |
|--------|------|-------------------|
| `AuthSession` | 003 | Gates `POST /api/analysis/age` via `require_valid_session`. No new attributes. Read-only (the endpoint validates the session; it does not create/modify one). |
| `User` | 002 | Identified by the session's `userId` for logging only (not for result persistence). No new attributes. |
| `MoodResult` | 004 | Unchanged. Reused to assert independence of the age and mood result surfaces (FR-020). |

### Deliberately NOT introduced

| Entity | Reason |
|--------|--------|
| `AnalysisRequest` | PRD §7 optional, §19 pending; no AC requires an audit row. Constitution Principle I (YAGNI). Deferred to a later spec if a demo narrative need arises (FR-014). Consistent with spec 004. |

---

## Domain Value Objects

### AgeResult (domain) — `domain/result_types.py`

```python
@dataclass(frozen=True)
class AgeResult:
    estimated_age: int
    range: tuple[int, int] | None   # widened from tuple[int,int] to tuple[int,int] | None
    model_version: str
```

**Change from spec 001**: `range` widened from `tuple[int, int]` to `tuple[int, int] | None` to permit a **point-only** port output (the estimator may return an estimated age without a range). This is backward-compatible (the mock always supplies a range). The `AgeService` normalization layer guarantees the returned `AgeResult` always has a non-`None` `range` satisfying the invariants. `model_version` carries the adapter's identifiable version (FR-017 — `"mock-age-estimator-v1"` for the mock).

### DetectionResult (domain) — `domain/result_types.py` (unchanged)

```python
@dataclass(frozen=True)
class DetectionResult:
    face_count: int
    boxes: list[BoundingBox]
    score: float
```

Reused from spec 001/002/004. The age service checks `face_count == 1` and `score >= quality_threshold`.

---

## Ports (exercised, unchanged)

| Port | Method | Signature | Adapter (this spec) |
|------|--------|-----------|---------------------|
| `Detector` | `detect` | `(image: bytes) -> DetectionResult` | `MockDetector` (production default) / `ScriptableMockDetector` (tests) — spec 002 |
| `AgeEstimator` | `estimate_age` | `(face_image: bytes) -> AgeResult` | `MockAgeEstimator` (production default, FR-016) / `ScriptableMockAgeEstimator` (tests) |
| `SessionManager` | `get_valid` | `(session_id, now) -> AuthSession \| None` | reused from spec 003 (via `require_valid_session`) |

No port is added or modified. The `AgeService` depends only on `Detector` + `AgeEstimator` (FR-015/SC-009).

---

## Age Service use-case — `domain/age.py` (NEW)

```python
class AgeService:
    def __init__(self, detector: Detector, age_estimator: AgeEstimator,
                 quality_threshold: float = 0.5,
                 age_range_half_width_years: int = 5) -> None: ...

    def analyze(self, image_bytes: bytes) -> AgeResult:
        """Orchestration (FR-005):
        1. detect (exactly one face + quality threshold) — raises NoFace/MultipleFaces/InsufficientQuality
        2. estimate_age — port failure -> AgeInternalError
        3. normalize_age_result(raw, half_width) — guarantees range non-None + invariants
        4. return AgeResult (range guaranteed, min >= 0, min <= estimated_age <= max)
        """
```

**Purity**: imports only `Detector`, `AgeEstimator`, `AgeResult`, and the domain exceptions. No FastAPI, no Pillow, no SQLAlchemy, no ML library (enforced by `test_domain_purity`).

### Normalization — `normalize_age_result(raw: AgeResult, half_width: int) -> AgeResult`

```
if raw.range is not None:
    min_clamped = max(0, raw.range[0])
    max_val = raw.range[1]
    estimated = clamp(round((min_clamped + max_val) / 2), min_clamped, max_val)
else:  # point-only
    estimated = raw.estimated_age
    min_clamped = max(0, estimated - half_width)
    max_val = estimated + half_width
return AgeResult(estimated_age=estimated, range=(min_clamped, max_val), model_version=raw.model_version)

where clamp(v, lo, hi) = max(lo, min(hi, v))
```

Invariants guaranteed: `min >= 0` and `min <= estimated_age <= max`. Pure function; trivially unit-testable (FR-004/SC-014).

---

## Error codes & status mapping (FR-006, FR-007)

Error body shape (spec 002 pinned, reused verbatim): `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}`.

| Status | Code | Condition | Actionable message (es) |
|--------|------|-----------|-------------------------|
| `401` | `unauthenticated` | no/invalid/expired/revoked session | "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo." (reused from spec 003) |
| `400` | `invalid_image` | undecodable/unsupported/oversized image | "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB." (reused from spec 002/003/004) |
| `400` | `no_face` | detector returns `face_count == 0` | "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar." |
| `400` | `multiple_faces` | detector returns `face_count > 1` | "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura." |
| `400` | `insufficient_quality` | single face but `score < quality_threshold` | "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar." |
| `500` | `internal_error` | detector/age_estimator port raises; unexpected failure | "Ocurrió un error inesperado. Inténtalo de nuevo." |

**Reservation**: `401` is reserved exclusively for `unauthenticated` (session-gating). `400` for actionable capture-quality codes. `500` for recoverable `internal_error` (FR-007). No age result is produced on any error path.

---

## Frontend state machine — `useAgeMachine`

| State | Description |
|-------|-------------|
| `idle` | No analysis in progress; age button enabled (subject to shared mutex) |
| `processing` | Capture sent, awaiting response; age loading indicator shown; both buttons disabled (FR-014) |
| `result` | Success; result (range + point estimate + disclaimer) displayed; button re-enabled (subject to shared mutex) |
| `error` | Recoverable error; actionable error surface + retry shown; button re-enabled (subject to shared mutex) |
| `camera_unavailable` | Camera permission denied/unavailable; actionable error + retry; no backend call (FR-012c) |

| Event | Transitions |
|-------|-------------|
| `CAPTURE` | `idle` → `processing` |
| `SUCCEEDED` | `processing` → `result` |
| `FAILED` | `processing` → `error` |
| `CAMERA_DENIED` | `idle` → `camera_unavailable` |
| `RETRY` | `error` → `idle`; `camera_unavailable` → `idle` |
| `RESET` | any → `idle` |

The most recent result is held in `Dashboard` component state and remains visible until a new age analysis or unmount/logout (FR-010). Invalid transitions are ignored (state-machine correctness, mirroring `useMoodMachine`).

### Shared capture mutex (FR-014) — dashboard-level

```
anyAnalysisInFlight = mood.isProcessing || age.isProcessing
```

Both the mood and age buttons (and the `CameraCapture` capture trigger) bind `disabled = anyAnalysisInFlight`. While either analysis is in flight, both buttons are disabled and a second press of either is ignored — one capture at a time across the dashboard. Each hook retains its own independent `isProcessing` / result / error state, so the loading indicators and result/error surfaces are independent (PRD §6.4). No server-side lock is added (demo-first; the frontend guard is the policy).

### Result rendering (FR-012a)

- Range rendered as `"min–max años"` (e.g. `27–37 años`).
- Point estimate rendered as `"≈NN años"` (e.g. `≈32 años`).
- When the range is narrow (`min == max`), only the point estimate `"≈NN años"` is rendered (no redundant `NN–NN años`).
- The `disclaimer` text follows the result.
- The backend contract always returns all three fields; this is a frontend rendering detail.
