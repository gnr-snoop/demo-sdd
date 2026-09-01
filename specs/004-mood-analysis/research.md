# Research: Mood Analysis (Fase 4)

**Spec**: [spec.md](./spec.md) | **Branch**: `004-mood-analysis` | **Date**: 2026-08-31

## Codebase Context

*(Gathered from the codebase-memory knowledge graph + direct source reads of the existing backend/frontend. All cited paths verified clean coverage via `check_index_coverage`.)*

### Existing architecture (reuse points)

- **Backend (FastAPI, hexagonal)** — `backend/src/face_insight/`:
  - `api/routes/analysis.py`: `POST /api/analysis/mood` is currently a **stub** — session-gated via `Depends(require_valid_session)` (spec 003 already wired) but returns a fixed `MoodResponse(label="neutral", confidence=0.74, disclaimer=MOOD_DISCLAIMER)` with no image processing, detection, or error handling. **This is the primary replacement target.**
  - `domain/ports.py`: `MoodEstimator.estimate_mood(face_image: bytes) -> MoodResult` and `Detector.detect(image: bytes) -> DetectionResult` are already declared `Protocol`s — **no port changes needed.**
  - `domain/result_types.py`: `MoodResult(label: str, confidence: float, model_version: str)` — `confidence` is currently a required `float`. The spec permits null/omitted confidence, so this is widened to `float | None` (forward-compatible; the mock always supplies a value).
  - `adapters/mock/mood_estimator.py`: `MockMoodEstimator` returns a fixed `MoodResult(label="neutral", confidence=0.74, model_version="mock-mood-v0")`. **Retained as the production default** (FR-016). A new `ScriptableMockMoodEstimator` (byte-marker controllable, mirroring `ScriptableMockDetector` in `adapters/mock/detector.py`) is added for tests that need specific labels / error triggers.
  - `adapters/mock/detector.py`: `ScriptableMockDetector` already substring-searches raw bytes for `NOFACE`/`MULTIFACE`/`LOWQUALITY` markers — **reused unchanged** for mood capture-quality tests.
  - `api/dependencies.py`: `require_valid_session` (real session validation, spec 003) — **reused unchanged**; raises `UnauthenticatedError` → `401 unauthenticated`.
  - `api/routes/auth.py`: establishes the **error-mapping pattern** to mirror — `_LOGIN_ERROR_MAP` dict mapping domain exception types → `(status_code, machine_code, actionable_message)`, `_error_response()` builder, structured logging with `duration_ms`/`status`/`error_code` and no biometric data. The mood route replicates this with a `_MOOD_ERROR_MAP`.
  - `domain/login.py`: establishes the **use-case orchestration pattern** — a service class holding only port references, raising typed domain exceptions, pure domain. `MoodService` mirrors this structure (simpler: no lookup/embed/compare/session-create).
  - `domain/image_handling.py`: `decode_and_normalize(image_bytes, max_bytes, max_long_edge) -> bytes` raises `InvalidImage` on failure — **reused unchanged** for mood image validation.
  - `domain/exceptions.py`: `InvalidImage`, `NoFace`, `MultipleFaces`, `InsufficientQuality` already defined (in `onboarding.py`, re-exported). A new `MoodInternalError` is added for port/adapter failures → `500 internal_error`.
  - `api/schemas.py`: `MoodResponse(label, confidence, disclaimer)` + `MOOD_DISCLAIMER` constant (already the exact PRD §8 string). `confidence` widened to `float | None = None`.
  - `config.py`: `quality_threshold`, `image_max_bytes`, `image_max_long_edge`, `mood_model_version` already present — **no new config.**
  - `main.py`: `wire_mock_adapters` wires `app.state.mood_estimator` + `app.state.detector`; needs to build a `MoodService` and store it on `app.state.mood_service`. `create_auth_app` (integration-test factory) needs the same wiring.

- **Frontend (React/Vite)** — `frontend/src/`:
  - `pages/Dashboard.tsx`: currently a placeholder with a "Cerrar sesión" button (spec 003). **Primary build-out target** — add camera preview, mood button, mood result/error surfaces, disabled age placeholder.
  - `components/CameraCapture.tsx`: reusable component with `active` prop (acquires stream in `useEffect`, releases in cleanup on unmount), `onCapture(blob)`, `onPermissionGranted`, `onPermissionDenied`, `disabled` props. **Reused unchanged** with `active={true}` on dashboard mount (FR-012b) and `disabled` bound to the mood in-flight state (FR-014).
  - `hooks/useLoginMachine.ts`: establishes the **reducer state-machine pattern** (`useReducer` + transition table + `send`/`reset`). `useMoodMachine` mirrors this with mood-specific states (`idle → processing → result | error`).
  - `services/api.ts`: `analysisMood(image)` exists but does not parse errors or send credentials. Updated to use `parseError` (already defined) and `credentials: "include"` (session cookie).

### Integration touch-points

- The mood endpoint slot already exists and is session-gated — spec 004 fills the **logic**, not the route registration or the session guard.
- No schema migration, no new entity, no new port. The change is additive logic + one widened optional field.
- The frontend dashboard is the sole consumer; no other frontend route or component is affected.

### Coverage limitations

None material. All cited backend/frontend paths returned `no_recorded_issue` from `check_index_coverage`; source was read directly as ground truth.

---

## Research Items

### R-1: Mood domain use-case orchestration (FR-005, FR-015)

**Decision**: Introduce a `MoodService` use-case in a new `domain/mood.py` that orchestrates: detect (exactly one face + quality threshold) → estimate_mood → normalize label → return `MoodResult`. It depends only on the `Detector` + `MoodEstimator` ports. The route handler performs session validation (via `Depends`) and image decode (via `decode_and_normalize`) before calling `MoodService.analyze(image_bytes)`.

**Rationale**: Mirrors the established `LoginService` / `OnboardingService` pattern (port-only deps, typed exceptions, pure domain). Keeps the domain free of FastAPI/Pillow/ML (Constitution Principle VII, enforced by `test_domain_purity`). The route handler is the HTTP adapter; the service is the decision logic.

**Alternatives considered**:
- *Inline all logic in the route handler* — rejected: violates Principle VII (domain logic in an HTTP adapter) and the established pattern; untestable in isolation without a full app.
- *Reuse `OnboardingService`* — rejected: onboarding persists a `User`+`FaceTemplate`; mood is transient and has no identifier/consent/embed/store steps. A separate focused service is simpler (YAGNI).

### R-2: Label normalization (FR-004)

**Decision**: A pure function `normalize_mood_label(label: str) -> str` in `domain/mood.py`. Valid set `{"neutral", "feliz", "triste", "sorprendido", "no concluyente"}`. Any value not in the set → `"no concluyente"`. The `MoodService` calls this on the port output before returning, so the person always gets a readable category.

**Rationale**: PRD §6.4 defines the set; the spec pins out-of-set → `no concluyente`. Normalizing (not failing) avoids dead-ending the UI on an unexpected port output (demo-first). This is a pure, trivially unit-testable function.

**Alternatives considered**:
- *Raise an error on out-of-set* — rejected: the person gets a failure instead of a readable category; contradicts the spec's "always a readable category" pin and demo-first.
- *Validate in the route handler* — rejected: normalization is domain decision logic; belongs in the domain service, not the HTTP adapter.

### R-3: Optional confidence (FR-012a, contract)

**Decision**: Widen `MoodResult.confidence` to `float | None` and `MoodResponse.confidence` to `float | None = None` (with `Field(ge=0.0, le=1.0)` applied when present via a validator). The `MoodService` clamps a port-returned confidence into `[0,1]`; if the port returns `None` or a non-finite value, the service passes `None` through. The frontend renders `≈NN%` (nearest integer) when present, and omits the confidence line when null/omitted.

**Rationale**: PRD §6.4 says confidence is optional ("opcionalmente"). The mock always supplies `0.74`, but the contract must permit null/omitted for the `no concluyente` case and for future real models that may not produce a score. Clamping guards against a misbehaving port without failing the request (demo-first). This is a backward-compatible widening of the spec 001 stub (which had a required float).

**Alternatives considered**:
- *Keep confidence required, always return a float* — rejected: contradicts PRD §6.4 "opcionalmente" and the pinned clarify decision; a real model in Fase 5 may not produce a score for `no concluyente`.
- *Omit the field entirely when absent (not null)* — rejected: a nullable field is simpler for pydantic + the frontend than conditional key presence, and JSON `null` is the conventional "absent with a known shape" representation.

### R-4: Error mapping (FR-006, FR-007, spec 002/003 shape)

**Decision**: The mood route defines a `_MOOD_ERROR_MAP` mirroring `auth.py`'s `_LOGIN_ERROR_MAP`:
- `InvalidImage` → `400 invalid_image` (reused message from `auth.py`)
- `NoFace` → `400 no_face`
- `MultipleFaces` → `400 multiple_faces`
- `InsufficientQuality` → `400 insufficient_quality`
- `MoodInternalError` → `500 internal_error` ("Ocurrió un error inesperado. Inténtalo de nuevo.")
- `UnauthenticatedError` (from `require_valid_session`) → `401 unauthenticated` (already handled by the exception handler registered in `main.py`).
Unexpected exceptions → `500 internal_error` (boundary catch).

All bodies use the pinned `{"error": {"code": "...", "message": "..."}}` shape. `401` is reserved exclusively for `unauthenticated` (FR-007).

**Rationale**: Reuses the exact pattern + messages established in specs 002/003 for consistency and to share the actionable capture-quality messages. The status-code reservation (`401` = session only, `400` = capture, `500` = internal) stays crisp.

**Alternatives considered**:
- *Map capture errors to `422` (onboarding style)* — rejected: the spec pins `400` for mood capture-quality failures (consistent with login, spec 003). Onboarding's `422` is a deliberate per-endpoint divergence that does not apply here.
- *A shared error-map module* — rejected: YAGNI; the maps differ per endpoint (auth has `auth_failed`, mood does not). Duplicating a small dict is simpler than a generic mapper.

### R-5: Mock mood estimator testability (US1/US2 independent tests)

**Decision**: Add a `ScriptableMockMoodEstimator` in `adapters/mock/mood_estimator.py` that substring-searches the raw image bytes for markers (mirroring `ScriptableMockDetector`):
- `b"FELIZ"` → `label="feliz", confidence=0.8`
- `b"TRIST"` → `label="triste", confidence=0.65`
- `b"NOCONCLUSIVE"` → `label="no concluyente", confidence=None`
- `b"OOSET"` → `label="bogus-out-of-set"` (to exercise normalization → `no concluyente`)
- `b"MOODFAIL"` → raises `Exception` (to exercise the `500 internal_error` path)
- otherwise → default `label="neutral", confidence=0.74` (same as `MockMoodEstimator`)

The plain `MockMoodEstimator` stays as the production wiring default (FR-016). Tests inject `ScriptableMockMoodEstimator` via `app.state.mood_estimator` + `app.state.mood_service` rebuild, the same way `ScriptableMockDetector` is injected.

**Rationale**: The spec's independent tests require the mock to return specific labels (`feliz`/0.8), trigger out-of-set normalization, and trigger a port error. The byte-marker pattern is already established for the detector and keeps fixtures as valid JPEGs with a COM-segment marker. No production wiring changes.

**Alternatives considered**:
- *Make `MockMoodEstimator` itself controllable* — rejected: would make the production default non-deterministic-by-input; the spec requires the production mock to be a fixed constant (SC-005). A separate scriptable variant preserves the clean default.
- *Dependency-inject a custom mock per test without markers* — rejected: works but diverges from the established fixture-marker convention; markers let a single JPEG fixture encode the case and flow through the real multipart decode path.

### R-6: Frontend mood state machine (FR-008/FR-009/FR-011/FR-014)

**Decision**: A `useMoodMachine` hook (`hooks/useMoodMachine.ts`) using `useReducer` with a transition table, mirroring `useLoginMachine`. States: `idle → processing → result | error` (plus `camera_unavailable` for the permission-denied case). Events: `CAPTURE`, `SUCCEEDED`, `FAILED`, `RETRY`, `RESET`. The dashboard binds: mood button `disabled = isProcessing` (FR-014), loading indicator visible when `isProcessing`, result surface when `state === "result"`, error surface when `state === "error"`. The most recent result is held in component state and stays visible until a new analysis or unmount/logout (FR-010).

**Rationale**: Reuses the established reducer pattern (consistent with onboarding + login). The mood machine is simpler than login (no permission-request sub-state beyond the camera component's own callbacks, no redirect). Holding the result in component state (not a context) is sufficient — the result is transient and dashboard-scoped (FR-014).

**Alternatives considered**:
- *Global mood state in `SessionContext`* — rejected: YAGNI; the result is dashboard-scoped and discarded on logout/unmount. A context would outlive the dashboard and leak the transient result.
- *No state machine, just useState flags* — rejected: the established pattern is a reducer; a state machine makes the disabled-while-in-flight (FR-014) and retry transitions explicit and testable.

### R-7: Camera lifecycle (FR-012b, FR-012c)

**Decision**: Render `<CameraCapture active={true} ... />` on the dashboard. `CameraCapture` already acquires the stream in its `useEffect` on `active` and releases it in the cleanup (on unmount) — so mounting the dashboard acquires the preview and unmounting (logout/session-expiry/navigation) releases it. The mood button triggers `CameraCapture`'s `onCapture` (a single still from the live preview); no separate stream per capture. `onPermissionDenied` drives the mood error surface with a "grant camera permission" message + retry (no backend call — FR-012c).

**Rationale**: `CameraCapture` (spec 002) already implements the exact lifecycle the spec pins. Reusing it with `active={true}` is the simplest thing that works. The permission-denied path is a frontend-only state distinct from `invalid_image` (no backend call).

**Alternatives considered**:
- *Acquire the stream on mood button press (not on mount)* — rejected: the spec pins preview-active-on-mount (FR-012b, PRD §6.4); acquiring on press would show no preview until the first press.
- *A new camera component for mood* — rejected: YAGNI; `CameraCapture` is generic (preview + still capture + permission callbacks).

### R-8: Transient result — no AnalysisRequest (FR-014)

**Decision**: No `AnalysisRequest` entity, no persistence, no migration. The mood result lives in frontend component state and is discarded on dashboard unmount/logout.

**Rationale**: PRD §7 marks `AnalysisRequest` optional; PRD §19 lists result persistence as a pending decision; no acceptance criterion requires an audit row. Constitution Principle I (demo-first/YAGNI) rules out persisting data no AC requires. The port-based design means adding persistence later (if a demo narrative need arises) is a new spec, not a redesign.

**Alternatives considered**:
- *Write an `AnalysisRequest` row on each mood call* — rejected: YAGNI; adds a DB write, a migration, and a repository method for no demo value; contradicts Principle I.

### R-9: Observability (FR-019, SC-013)

**Decision**: The mood route emits structured JSON logs (`logger.info("analysis.mood", duration_ms=..., status=..., error_code=...)`) consistent with `auth.py`. No image bytes, embedding, label value, or confidence is logged — only the operation outcome (success/failure), duration, and error code. On unexpected failure, `logger.exception("analysis.mood_unexpected_failure")`.

**Rationale**: Matches the established logging pattern (specs 001/002/003) and Constitution Principle VIII (no traceability guarantee; demo-level observability only). Logging the label/confidence is not required and risks leaking inference detail; the outcome + duration is sufficient for the demo.

### R-10: Disabled age placeholder (FR-013)

**Decision**: The dashboard renders a "Calcular edad" `<button disabled>` with a visible "Próximamente" (coming soon) indication and `aria-disabled`. Pressing it performs no action (disabled button cannot fire `onClick`).

**Rationale**: PRD §6.4 lists both buttons; rendering the age button disabled keeps the dashboard layout stable for spec 005 (no layout rework). This is the pinned clarify decision.

---

## Summary of decisions

| # | Decision | Pin source |
|---|----------|------------|
| R-1 | `MoodService` use-case in `domain/mood.py` (port-only) | FR-005/FR-015 |
| R-2 | `normalize_mood_label` pure function; out-of-set → `no concluyente` | FR-004 |
| R-3 | `confidence: float \| None`; clamp to [0,1]; render `≈NN%` | FR-012a |
| R-4 | `_MOOD_ERROR_MAP` mirroring `auth.py`; 400/401/500 reservation | FR-006/FR-007 |
| R-5 | `ScriptableMockMoodEstimator` (byte markers) for tests | US1/US2 |
| R-6 | `useMoodMachine` reducer (idle→processing→result\|error) | FR-008/FR-009/FR-014 |
| R-7 | Reuse `CameraCapture` with `active={true}` | FR-012b/FR-012c |
| R-8 | Transient result, no `AnalysisRequest` | FR-014 |
| R-9 | Structured JSON logs, no biometric data | FR-019/SC-013 |
| R-10 | Disabled age button + "Próximamente" | FR-013 |
