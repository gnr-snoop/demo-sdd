# Research: Age Estimation (Fase 4 — age)

**Spec**: [spec.md](./spec.md) | **Branch**: `005-age-analysis` | **Date**: 2026-08-31

## Codebase Context

*(Gathered from the codebase-memory knowledge graph + direct source reads of the existing backend/frontend. All cited paths verified clean coverage via `check_index_coverage` — every path returned `no_recorded_issue`; source was read directly as ground truth.)*

### Existing architecture (reuse points)

- **Backend (FastAPI, hexagonal)** — `backend/src/face_insight/`:
  - `api/routes/analysis.py`: `POST /api/analysis/age` is currently a **stub** — session-gated via `Depends(require_valid_session)` (spec 003 already wired) but returns a fixed `AgeResponse(estimatedAge=32, range=MoodRange(min=27, max=37), disclaimer=AGE_DISCLAIMER)` with no image processing, detection, or error handling. The mood route (`analysis_mood`) is already real (spec 004) and establishes the exact orchestration + `_MOOD_ERROR_MAP` + structured-logging pattern to mirror. **The age route is the primary replacement target.**
  - `domain/ports.py`: `AgeEstimator.estimate_age(face_image: bytes) -> AgeResult` and `Detector.detect(image: bytes) -> DetectionResult` are already declared `Protocol`s — **no port changes needed.**
  - `domain/result_types.py`: `AgeResult(estimated_age: int, range: tuple[int, int], model_version: str)` — `range` is currently a required `tuple[int, int]`. To support the port returning a **point-only** estimate (no range), `range` is widened to `tuple[int, int] | None` (backward-compatible; the mock always supplies a range; the normalization layer guarantees the HTTP response always has a range).
  - `domain/mood.py`: `MoodService` + `normalize_mood_label` — the **exact pattern** `AgeService` + `normalize_age_result` mirrors (port-only deps, detect → estimate → normalize → return, typed exceptions, pure domain).
  - `adapters/mock/age_estimator.py`: `MockAgeEstimator` returns a fixed `AgeResult(estimated_age=32, range=(27, 37), model_version=AGE_MODEL_VERSION)`. **Retained as the production default** (FR-016). A new `ScriptableMockAgeEstimator` (byte-marker controllable, mirroring `ScriptableMockMoodEstimator` in `adapters/mock/mood_estimator.py`) is added for tests that need point-only / range / error triggers.
  - `adapters/mock/constants.py`: `AGE_MODEL_VERSION = "mock-age-v0"` currently. The spec pins `model_version = "mock-age-estimator-v1"` (FR-017) — this constant is **updated** to `"mock-age-estimator-v1"` (consistent with `MOOD_MODEL_VERSION = "mock-mood-v1"` from spec 004). New age byte markers are added (`AGEPOINT`, `AGERANGE`, `AGEFAIL`).
  - `adapters/mock/detector.py`: `ScriptableMockDetector` already substring-searches raw bytes for `NOFACE`/`MULTIFACE`/`LOWQUALITY` markers — **reused unchanged** for age capture-quality tests (including the `insufficient_quality` fixture the spec requires).
  - `api/dependencies.py`: `require_valid_session` (real session validation, spec 003) — **reused unchanged**; raises `UnauthenticatedError` → `401 unauthenticated`. A new `get_age_service` dep (mirroring `get_mood_service`) resolves `app.state.age_service`.
  - `api/routes/analysis.py` (mood): establishes the **error-mapping pattern** to mirror — `_MOOD_ERROR_MAP` dict mapping domain exception types → `(status_code, machine_code, actionable_message)`, `_error_response()` builder, structured logging with `duration_ms`/`status`/`error_code` and no biometric data. The age route replicates this with a `_AGE_ERROR_MAP`.
  - `domain/image_handling.py`: `decode_and_normalize(image_bytes, max_bytes, max_long_edge) -> bytes` raises `InvalidImage` on failure — **reused unchanged** for age image validation.
  - `domain/exceptions.py`: `InvalidImage`, `NoFace`, `MultipleFaces`, `InsufficientQuality` already defined (re-exported). A new `AgeInternalError` is added for port/adapter failures → `500 internal_error` (mirroring `MoodInternalError`).
  - `api/schemas.py`: `AgeResponse(estimatedAge: int, range: MoodRange, disclaimer: str)` + `AGE_DISCLAIMER` constant (already the exact PRD §8 string `"La edad es una estimación visual y puede contener un margen de error significativo."`). A dedicated `AgeRange(BaseModel)` schema (`min: int`, `max: int`) is introduced for clarity (replacing the reused `MoodRange` on the age response); `AgeResponse.range` → `AgeRange`.
  - `config.py`: `quality_threshold`, `image_max_bytes`, `image_max_long_edge`, `age_model_version` already present. A new `age_range_half_width_years: int = 5` field is added (FR-004). `age_model_version` default updated to `"mock-age-estimator-v1"` (FR-017).
  - `main.py`: `wire_mock_adapters` wires `app.state.age_estimator` + `app.state.detector`; needs to build an `AgeService` and store it on `app.state.age_service`. `create_auth_app` (integration-test factory) needs the same wiring.

- **Frontend (React/Vite)** — `frontend/src/`:
  - `pages/Dashboard.tsx`: currently renders the mood flow (spec 004) + a **disabled** "Calcular edad" placeholder (`<button disabled>` + `<span data-testid="age-placeholder">Próximamente</span>`). **Primary update target** — enable the age button (remove placeholder), add age result/error/loading surfaces, and add the shared capture mutex.
  - `components/CameraCapture.tsx`: reusable component with `active` prop, `onCapture(blob)`, `onPermissionGranted`, `onPermissionDenied`, `disabled` props. **Reused unchanged** with `active={true}` on dashboard mount (FR-012b) and `disabled` bound to the shared capture-mutex flag (FR-014).
  - `hooks/useMoodMachine.ts`: establishes the **reducer state-machine pattern** for analysis (spec 004). `useAgeMachine` mirrors this with age-specific states. The shared capture mutex is **not** in either hook — it is a dashboard-level concern (`anyAnalysisInFlight = mood.isProcessing || age.isProcessing`).
  - `services/api.ts`: `analysisAge(image)` exists but does not parse errors or send credentials (no `credentials: "include"`, no `parseError`). Updated to use `parseError` (already defined) and `credentials: "include"` (session cookie) — mirroring the `analysisMood` update from spec 004.

### Integration touch-points

- The age endpoint slot already exists and is session-gated — spec 005 fills the **logic**, not the route registration or the session guard.
- No schema migration, no new entity, no new port. The change is additive logic + one widened optional port-output field + one new config field + one new schema + one new exception.
- The frontend dashboard is the sole consumer; no other frontend route or component is affected.
- The shared capture mutex touches the mood button's `disabled` state (now also disabled during an age analysis) — this is the **only** change to mood behavior; the mood hook, mood endpoint, and mood tests are otherwise unchanged (FR-020).

### Coverage limitations

None material. All cited backend/frontend paths returned `no_recorded_issue` from `check_index_coverage`; source was read directly as ground truth.

---

## Research Items

### R-1: Age domain use-case orchestration (FR-005, FR-015)

**Decision**: Introduce an `AgeService` use-case in a new `domain/age.py` that orchestrates: detect (exactly one face + quality threshold) → estimate_age → normalize result → return `AgeResult`. It depends only on the `Detector` + `AgeEstimator` ports. The route handler performs session validation (via `Depends`) and image decode (via `decode_and_normalize`) before calling `AgeService.analyze(image_bytes)`.

**Rationale**: Mirrors the established `MoodService` pattern from spec 004 (port-only deps, typed exceptions, pure domain). Keeps the domain free of FastAPI/Pillow/ML (Constitution Principle VII, enforced by `test_domain_purity`). The route handler is the HTTP adapter; the service is the decision logic.

**Alternatives considered**:
- *Inline all logic in the route handler* — rejected: violates Principle VII (domain logic in an HTTP adapter) and the established pattern; untestable in isolation without a full app.
- *Reuse `MoodService`* — rejected: mood produces a label + confidence; age produces an estimated age + range with a different normalization rule. A separate focused service is simpler (YAGNI).

### R-2: Age normalization (FR-004, SC-014)

**Decision**: A pure function `normalize_age_result(raw: AgeResult, half_width: int) -> AgeResult` in `domain/age.py` that guarantees the returned `AgeResult` has a non-`None` `range` and satisfies `min >= 0` and `min <= estimated_age <= max`:
- **Port returns a range** (`raw.range is not None`): `estimated_age = round((min + max) / 2)` clamped into `[min, max]`; `range` stays as-is (with `min` clamped to 0).
- **Port returns point-only** (`raw.range is None`): `min = max(0, estimated_age - half_width)`; `max = estimated_age + half_width`; `estimated_age` stays as-is.
- In both cases `min` is clamped to `max(0, min)` (age cannot be negative), and `estimated_age` is clamped into `[min, max]`.

The `AgeService` calls this on the port output before returning. The route handler then builds `{estimatedAge, range:{min,max}, disclaimer}` from the normalized result.

**Rationale**: PRD §6.4 says the result is "una edad estimada en años o, preferentemente, como un rango de edad si el modelo lo permite". To keep the HTTP contract stable regardless of whether the port produces a point estimate or a range, the backend always returns all three fields. The midpoint rule (range → estimate) and the derived-symmetric-range rule (point → range) are the pinned clarify decisions. The default half-width of 5 years reflects the "margen de error significativo" the disclaimer communicates. This is a pure, trivially unit-testable function.

**Alternatives considered**:
- *Return only what the port gives (point or range, not both)* — rejected: the spec pins `range` always present in the `200` response (FR-002); a variable shape would complicate the contract and the frontend.
- *Make the half-width a hardcoded constant* — rejected: the spec pins it as a configurable `Settings` field (FR-004) so it can be tuned without a code change.

### R-3: Configurable half-width (FR-004)

**Decision**: Add `age_range_half_width_years: int = 5` to the existing pydantic `Settings` in `config.py` (with a `>= 0` invariant enforced by a field validator or a clamp in the service). The `AgeService` receives it at construction; the route passes `settings.age_range_half_width_years` when building the service. No new config mechanism or file.

**Rationale**: The spec explicitly pins this as a `Settings` field following the spec 002 pattern. A half-width of 5 is a reasonable demo default. `>= 0` is enforced (a half-width of 0 yields `min == max == estimated_age`, a valid narrow range).

**Alternatives considered**:
- *A separate age config section/class* — rejected: YAGNI; one field does not justify a new config object.

### R-4: Error mapping (FR-006, FR-007, spec 002/003/004 shape)

**Decision**: The age route defines an `_AGE_ERROR_MAP` mirroring spec 004's `_MOOD_ERROR_MAP`:
- `InvalidImage` → `400 invalid_image` (reused message)
- `NoFace` → `400 no_face`
- `MultipleFaces` → `400 multiple_faces`
- `InsufficientQuality` → `400 insufficient_quality`
- `AgeInternalError` → `500 internal_error` ("Ocurrió un error inesperado. Inténtalo de nuevo.")
- `UnauthenticatedError` (from `require_valid_session`) → `401 unauthenticated` (already handled by the exception handler registered in `main.py`).
Unexpected exceptions → `500 internal_error` (boundary catch).

All bodies use the pinned `{"error": {"code": "...", "message": "..."}}` shape. `401` is reserved exclusively for `unauthenticated` (FR-007).

**Rationale**: Reuses the exact pattern + messages established in specs 002/003/004 for consistency. The status-code reservation (`401` = session only, `400` = capture, `500` = internal) stays crisp. The actionable messages are identical to mood's (same capture-quality failures).

**Alternatives considered**:
- *Share a single error-map module between mood and age* — rejected: YAGNI; the maps differ only in the internal-error exception type (`MoodInternalError` vs `AgeInternalError`). Duplicating a small dict is simpler than a generic mapper and keeps each route self-contained.

### R-5: Mock age estimator testability (US1/US2 independent tests)

**Decision**: Add a `ScriptableMockAgeEstimator` in `adapters/mock/age_estimator.py` that substring-searches the raw image bytes for markers (mirroring `ScriptableMockMoodEstimator`):
- `b"AGEPOINT"` → point-only: `AgeResult(estimated_age=40, range=None, model_version=...)` (exercises the derived-range normalization)
- `b"AGERANGE"` → range: `AgeResult(estimated_age=40, range=(35, 45), model_version=...)` (exercises the midpoint normalization)
- `b"AGEFAIL"` → raises `Exception` (to exercise the `500 internal_error` path)
- otherwise → default `AgeResult(estimated_age=32, range=(27, 37), model_version=...)` (same as `MockAgeEstimator`)

Marker precedence: `AGEFAIL > AGEPOINT > AGERANGE > default`. The plain `MockAgeEstimator` stays as the production wiring default (FR-016). Tests inject `ScriptableMockAgeEstimator` via `app.state.age_estimator` + `app.state.age_service` rebuild, the same way `ScriptableMockMoodEstimator` is injected.

**Rationale**: The spec's independent tests require the mock to return a point estimate with a range (US1), a point-only estimate (US2 scenario 6 / SC-014), and trigger a port error (US2 scenario 4). The byte-marker pattern is already established for the detector and mood estimator and keeps fixtures as valid JPEGs with a COM-segment marker. No production wiring changes.

**Alternatives considered**:
- *Make `MockAgeEstimator` itself controllable* — rejected: would make the production default non-deterministic-by-input; the spec requires the production mock to be a fixed constant (SC-005). A separate scriptable variant preserves the clean default.

### R-6: Frontend age state machine + shared capture mutex (FR-008/FR-009/FR-011/FR-014)

**Decision**: A `useAgeMachine` hook (`hooks/useAgeMachine.ts`) using `useReducer` with a transition table, mirroring `useMoodMachine`. States: `idle → processing → result | error` (plus `camera_unavailable` for the permission-denied case). Events: `CAPTURE`, `SUCCEEDED`, `FAILED`, `RETRY`, `RESET`. The dashboard binds the **shared capture mutex** at the dashboard level: `anyAnalysisInFlight = mood.isProcessing || age.isProcessing`. Both `CameraCapture` instances (or the single camera with both capture triggers) and both buttons bind `disabled = anyAnalysisInFlight` (FR-014 — one capture at a time across the dashboard). Each hook retains its own independent `isProcessing` / result / error state, so the loading indicators and result/error surfaces are independent (PRD §6.4). The most recent age result is held in component state and stays visible until a new age analysis or unmount/logout (FR-010).

**Rationale**: Reuses the established reducer pattern (consistent with mood). The shared mutex is a dashboard-level concern (it cross-cuts both hooks), so it is computed in `Dashboard` rather than embedded in either hook — this keeps each hook independent and testable in isolation, and makes the FR-014 "una captura a la vez" policy explicit and visible. No server-side lock is added (demo-first; the frontend guard is the policy).

**Alternatives considered**:
- *A single combined `useAnalysisMachine` for both mood and age* — rejected: the spec pins independent loading/result/error surfaces (PRD §6.4); a combined machine would couple them and complicate the spec 004 mood regression. Two independent hooks + a dashboard-level mutex flag is simpler.
- *No state machine, just useState flags* — rejected: the established pattern is a reducer; a state machine makes the disabled-while-in-flight (FR-014) and retry transitions explicit and testable.

### R-7: Camera lifecycle (FR-012b, FR-012c)

**Decision**: The camera lifecycle is **unchanged from spec 004**. `CameraCapture` (spec 002) already acquires the stream in its `useEffect` on `active` and releases it in the cleanup (on unmount). The age button triggers `CameraCapture`'s `onCapture` (a single still from the live preview); no separate stream per capture. `onPermissionDenied` drives the age error surface with a "grant camera permission" message + retry (no backend call — FR-012c). The age button shares the same camera preview as the mood button (one camera, one still at a time — enforced by the shared mutex).

**Rationale**: `CameraCapture` (spec 002/004) already implements the exact lifecycle the spec pins. Reusing it is the simplest thing that works. The permission-denied path is a frontend-only state distinct from `invalid_image` (no backend call).

**Alternatives considered**:
- *A second `CameraCapture` instance for age* — rejected: YAGNI; one camera, one preview. The shared mutex ensures one still at a time.

### R-8: Transient result — no AnalysisRequest (FR-014)

**Decision**: No `AnalysisRequest` entity, no persistence, no migration. The age result lives in frontend component state and is discarded on dashboard unmount/logout. Consistent with the spec 004 mood decision.

**Rationale**: PRD §7 marks `AnalysisRequest` optional; PRD §19 lists result persistence as a pending decision; no acceptance criterion requires an audit row. Constitution Principle I (demo-first/YAGNI) rules out persisting data no AC requires. The port-based design means adding persistence later (if a demo narrative need arises) is a new spec, not a redesign.

**Alternatives considered**:
- *Write an `AnalysisRequest` row on each age call* — rejected: YAGNI; adds a DB write, a migration, and a repository method for no demo value; contradicts Principle I.

### R-9: Observability (FR-019, SC-013)

**Decision**: The age route emits structured JSON logs (`logger.info("analysis.age", duration_ms=..., status=..., error_code=...)`) consistent with the mood route. No image bytes, embedding, estimated age, or range is logged — only the operation outcome (success/failure), duration, and error code. On unexpected failure, `logger.exception("analysis.age_unexpected_failure")`.

**Rationale**: Matches the established logging pattern (specs 001/002/003/004) and Constitution Principle VIII (no traceability guarantee; demo-level observability only). Logging the estimated age/range is not required and risks leaking inference detail; the outcome + duration is sufficient for the demo.

### R-10: Enable age button — remove placeholder (FR-013)

**Decision**: The dashboard replaces the spec 004 disabled "Calcular edad" placeholder (`<button disabled>` + `<span data-testid="age-placeholder">Próximamente</span>`) with an active, keyboard-accessible button bound to the age capture flow. The "Próximamente" indication is removed. The button's `disabled` state is bound to the shared capture mutex (`anyAnalysisInFlight`). The dashboard layout is otherwise unchanged from spec 004.

**Rationale**: PRD §6.4 lists both buttons; the spec pins enabling the placeholder. Reusing the spec 004 layout avoids rework. The button is keyboard-accessible with a descriptive `aria-label` ("Calcular edad").

**Alternatives considered**:
- *Re-render the entire dashboard* — rejected: YAGNI; only the age button's behavior and the age surfaces are added. The mood UI, camera, session indicator, and logout are reused unchanged (FR-020).

### R-11: Mock model version (FR-017)

**Decision**: The mock age estimator adapter reports `model_version = "mock-age-estimator-v1"` (updating the current `"mock-age-v0"` constant in `constants.py` and the `age_model_version` default in `config.py`). A unit test asserts this version is present and stable so results are reproducible.

**Rationale**: The spec pins this exact string (consistent with `MOOD_MODEL_VERSION = "mock-mood-v1"` from spec 004). Real model adapters in Fase 5 will report their own real version strings. The version is carried in `AgeResult.model_version` (already present in the domain type).

**Alternatives considered**:
- *Keep `"mock-age-v0"`* — rejected: the spec explicitly pins `"mock-age-estimator-v1"` (FR-017) for consistency with the spec 004 mood naming convention.

### R-12: AgeRange schema (contract clarity)

**Decision**: Introduce a dedicated `AgeRange(BaseModel)` schema (`min: int`, `max: int`) in `api/schemas.py` and update `AgeResponse.range` from `MoodRange` to `AgeRange`. The current code reuses `MoodRange` for the age range — a naming smell. `AgeRange` is structurally identical but semantically clear.

**Rationale**: The age range `{min, max}` is conceptually distinct from the mood range (which does not exist in the final mood contract — `MoodRange` was a spec 001 scaffold reused for age). A dedicated schema keeps the contracts self-documenting. This is an additive, backward-compatible change (the JSON shape `{min, max}` is unchanged).

**Alternatives considered**:
- *Keep reusing `MoodRange`* — rejected: works but is a naming smell that confuses the contract documentation; a dedicated `AgeRange` is clearer at negligible cost.

---

## Summary of decisions

| # | Decision | Pin source |
|---|----------|------------|
| R-1 | `AgeService` use-case in `domain/age.py` (port-only) | FR-005/FR-015 |
| R-2 | `normalize_age_result` pure function; range→midpoint, point→derived range, clamp | FR-004/SC-014 |
| R-3 | `age_range_half_width_years: int = 5` on `Settings` | FR-004 |
| R-4 | `_AGE_ERROR_MAP` mirroring `_MOOD_ERROR_MAP`; 400/401/500 reservation | FR-006/FR-007 |
| R-5 | `ScriptableMockAgeEstimator` (byte markers) for tests | US1/US2 |
| R-6 | `useAgeMachine` reducer + dashboard-level shared capture mutex | FR-008/FR-009/FR-014 |
| R-7 | Reuse `CameraCapture` with `active={true}` (unchanged from spec 004) | FR-012b/FR-012c |
| R-8 | Transient result, no `AnalysisRequest` | FR-014 |
| R-9 | Structured JSON logs, no biometric data | FR-019/SC-013 |
| R-10 | Enable age button, remove "Próximamente" placeholder | FR-013 |
| R-11 | `model_version = "mock-age-estimator-v1"` | FR-017 |
| R-12 | Dedicated `AgeRange` schema | contract clarity |
