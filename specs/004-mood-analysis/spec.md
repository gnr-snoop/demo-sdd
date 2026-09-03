# Feature Specification: Mood Analysis from Authenticated Dashboard (Fase 4 — mood)

**Feature Branch**: `004-mood-analysis`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Mood analysis from the authenticated dashboard (Fase 4 — mood portion of the PRD). This spec implements the real on-demand mood analysis flow, building on specs 001 (skeleton/ports/mocks), 002 (onboarding), and 003 (login/session — real sessions now exist). It covers PRD §6.4 (Dashboard autenticado — mood button + result), §6.4 Resultado de estado de ánimo, FR-011 (Capturar imagen puntual), FR-012 (Detectar estado de ánimo), FR-014 (Evitar acciones simultáneas inválidas), FR-015 (Mostrar errores accionables). Acceptance criterion AC-007 (Estado de ánimo). The flow: authenticated person on /dashboard presses 'Detectar estado de ánimo', frontend captures a single still from the camera (getUserMedia), sends to POST /api/analysis/mood (multipart: image) with the session cookie, backend validates the real session (spec 003), decodes the image, runs the detector port to find exactly one face, runs the mood_estimator port to get a mood category + confidence, returns 200 with {label, confidence, disclaimer} per PRD §8. Mood labels: neutral, feliz, triste, sorprendido, enojo, no concluyente. Frontend: camera preview, mood button, independent loading indicator, most recent mood result persisted visible until new analysis or logout, recoverable error, keyboard-accessible button, button disabled while in progress (FR-014), one capture at a time. Age button present but disabled (placeholder pending spec 005). Real ML models deferred to Fase 5 (mock mood estimator retained)."

## Clarifications

### Session 2026-08-31 (auto-resolved at specify gate)

- Q: Is the mood analysis result persisted server-side (e.g. an `AnalysisRequest` audit row) or transient? -> A: Transient. The mood result is NOT persisted server-side in this spec. PRD §7 marks `AnalysisRequest` as optional for the MVP and PRD §19 lists "Si los resultados de análisis se almacenarán o serán únicamente transitorios" as a pending decision; the demo-first Constitution Principle I and YAGNI rule out persisting audit rows that no acceptance criterion requires. The most recent mood result lives in frontend state and remains visible until a new analysis is triggered or the session ends (logout/expiry), per PRD §10 ("conservar los resultados visibles hasta que se ejecute un nuevo análisis o se cierre la sesión"). `AnalysisRequest` persistence is deferred to a later spec if a demo narrative need arises.
- Q: Is `confidence` always present in the response? -> A: Optional. PRD §6.4 says the result is "acompañada opcionalmente por una confianza presentada como valor aproximado". The response includes `confidence` as a float in `[0.0, 1.0]` when the mood estimator produces one; for the `no concluyente` label the `confidence` field MAY be `null` or omitted. The PRD §8 contract example shows a numeric `confidence`, which is the shape when present. The contract test asserts the field is either a float in `[0,1]` or absent/null.
- Q: What is the exact `disclaimer` text? -> A: The fixed string from PRD §8: `"Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."` It is returned verbatim by the backend on every `200` mood response and rendered by the frontend alongside the result so the interface communicates the result is a model inference, not an objective measurement (PRD §6.4, §12 "No presentar edad o estado de ánimo como hechos ciertos").
- Q: What mood labels are valid and where are they enforced? -> A: The label set is exactly `{neutral, feliz, triste, sorprendido, enojo, no concluyente}` per PRD §6.4. The mood estimator port returns a value from this set; the backend normalizes/validates the port output against this set and maps any out-of-set or low-quality port output to `no concluyente` rather than failing, so the person always gets a readable category. The contract test asserts the label is a member of this set.
- Q: What happens when the mood capture contains no face or more than one face? -> A: The backend returns `400 Bad Request` with the actionable capture error body (`no_face` / `multiple_faces`) in the spec-002-pinned `{"error": {"code": "...", "message": "..."}}` shape, reusing the exact codes and status-code mapping established in specs 002/003. No mood result is produced. This is consistent with FR-004 (validate capture) and FR-015 (actionable errors) and lets the person recapture.
- Q: How is the mood endpoint session-gated, and what does it return without a valid session? -> A: The real `require_valid_session` from spec 003 is reused. The endpoint rejects any request without a valid (non-expired, non-revoked, present) session with `401 unauthenticated` and performs no analysis. This replaces the spec 001 session-placeholder stub with real session enforcement (spec 003 FR-014).
- Q: In what order does the mood endpoint evaluate conditions? -> A: (1) session validation via `require_valid_session` → `401 unauthenticated` if invalid; (2) decode + validate the image (format/size/long-edge, reusing spec 002 limits) → `400 invalid_image` if undecodable/unsupported/oversized; (3) run the detector port → `400 no_face` / `multiple_faces` / `insufficient_quality` if the capture is not exactly one usable face; (4) run the mood_estimator port on the detected face → mood label + optional confidence; (5) normalize the label against the valid set (out-of-set → `no concluyente`); (6) return `200` with `{label, confidence, disclaimer}`. A port/adapter error at step 3 or 4 returns a recoverable `500 internal_error` (actionable: "try again") and produces no result.
- Q: How is FR-014 (no simultaneous invalid actions) implemented for mood? -> A: While a mood analysis request is in flight, the mood button is disabled and a second press is ignored (no second capture/request). One capture at a time. The age button is already disabled as a placeholder (spec 005), so it cannot trigger a concurrent capture. The mood and age loading indicators are independent (PRD §6.4), but since only mood is functional in this spec, only the mood indicator is exercised. The "one capture at a time" policy is explicit and documented.
- Q: Is the age button rendered in this spec? -> A: Yes — present but disabled/non-functional, with a visible indication that age estimation is coming (placeholder pending spec 005). PRD §6.4 lists both buttons, so the dashboard shows both; only the mood button is wired in this spec. This keeps the dashboard layout stable for spec 005.
- Q: Are real ML models used for mood estimation? -> A: No. The mood_estimator port is wired to the mock adapter from spec 001 for this entire spec. Real mood models are explicitly deferred to Fase 5 (Constitution Principle VII; the port makes the swap a configuration change, not a redesign). The mock mood estimator returns a deterministic label + confidence for fixture inputs.

> **RESOLVED at specify gate (2026-08-31)**: The mood response body is `{"label": "<one of neutral|feliz|triste|sorprendido|enojo|no concluyente>", "confidence": <float 0..1 | null | omitted>, "disclaimer": "Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."}` with `200 OK`. Error responses reuse the spec-002-pinned `{"error": {"code": "...", "message": "..."}}` shape with codes `unauthenticated` (401), `no_face` / `multiple_faces` / `invalid_image` / `insufficient_quality` (400), `internal_error` (500). This is pinned and flows into plan, contracts, and contract-test assertions.

### Session 2026-08-31 (auto-resolved at clarify gate)

- Q: How is `confidence` rendered to the person when present? -> A: As a percentage rounded to the nearest integer with a "≈" prefix (e.g. `confidence: 0.8123` renders as "≈81%"), matching PRD §6.4 "valor aproximado". When `confidence` is null or omitted, the frontend renders only the label and disclaimer with no confidence value. This is a frontend rendering detail; the backend contract is unchanged (it returns the raw float in `[0,1]` or null/omitted).
- Q: What happens if the camera permission is denied or unavailable when the dashboard loads / on mood button press? -> A: The frontend shows an actionable mood error surface with a message instructing the person to grant camera permission and a retry option that does not require a full page reload (FR-015, PRD §10). No mood capture or request is initiated until permission is granted. This reuses the recoverable error pattern; it is distinct from `invalid_image` (which is a backend decode/limit failure) and is a frontend-only state (no backend call is made).
- Q: When is the camera stream acquired and released? -> A: The camera stream is acquired on dashboard mount (so the preview is active per PRD §6.4) and released on dashboard unmount (logout/session expiry/navigation away). The mood button captures a single still from the live preview on press; it does not open a separate stream per capture. This minimizes resource use and keeps the preview stable; tests mock `MediaDevices` lifecycle accordingly.

## User Scenarios & Testing *(mandatory)*

<!--
  This spec implements the real on-demand mood analysis flow on top of specs 001
  (skeleton/ports/mocks), 002 (onboarding — User + FaceTemplate), and 003
  (login/session — real sessions, route protection, logout). Stories are ordered
  so each independently delivers a demonstrable, testable slice and maps to PRD
  AC-007 and FR-011/012/014/015. All ML touchpoints go through the ports
  established in spec 001; the mock mood estimator is used in this spec (real
  models arrive in Fase 5).
-->

### User Story 1 - Successful On-Demand Mood Analysis (Happy Path) (Priority: P1)

A person with a valid session is on `/dashboard`. The camera preview is active. They press the keyboard-accessible "Detectar estado de ánimo" button. The frontend captures a single still image from the camera via standard browser media APIs (no continuous streaming), shows an independent loading indicator for mood, disables the mood button (FR-014), and sends the image as `multipart/form-data` to `POST /api/analysis/mood` with the session cookie. The backend validates the session via the real `require_valid_session` (spec 003), decodes and validates the image (reusing spec 002 limits), runs the detector port and finds exactly one face, runs the mood_estimator port to get a mood label + optional confidence, normalizes the label against the valid set, and returns `200 OK` with `{label, confidence, disclaimer}` per PRD §8. The frontend displays the readable mood category, the confidence (when present) as an approximate value, and the disclaimer text communicating this is a model inference, not an objective measurement. The result remains visible until a new analysis is triggered or the session ends.

**Why this priority**: This is the core mood narrative and the primary deliverable of Fase 4's mood portion. It delivers AC-007 (Estado de ánimo) and exercises FR-011 (capture a single image) and FR-012 (detect mood) end-to-end. Without a working mood analysis the dashboard's central on-demand analysis value is absent.

**Independent Test**: Perform a successful login (spec 003), then call `POST /api/analysis/mood` with the session cookie and a fixture image the mock detector reports as exactly one face and the mock mood estimator reports as `feliz` with confidence `0.8`; assert a `200` response with `label == "feliz"`, `confidence` in `[0,1]`, and the exact PRD §8 disclaimer string. Delivers a complete, demonstrable mood analysis.

**Acceptance Scenarios**:

1. **Given** the person has a valid session and the camera is available, **When** they press "Detectar estado de ánimo", **Then** the frontend captures a single still, shows the mood loading indicator, disables the mood button, and sends the image to `POST /api/analysis/mood` with the session cookie (AC-007, FR-011).
2. **Given** a valid session and a capture containing exactly one face, **When** the backend processes the request, **Then** it returns `200 OK` with `label` (a member of `{neutral, feliz, triste, sorprendido, enojo, no concluyente}`), `confidence` (a float in `[0,1]`, or null/omitted), and the exact PRD §8 `disclaimer` string (FR-012, AC-007).
3. **Given** a successful mood response, **When** the frontend receives it, **Then** it hides the loading indicator, re-enables the mood button, and displays the readable mood category, the confidence (when present) as an approximate value, and the disclaimer text (PRD §6.4, §12).
4. **Given** a mood result is displayed, **When** no new analysis is triggered and the session remains valid, **Then** the result stays visible (PRD §10 — conservar resultados visibles hasta un nuevo análisis o cierre de sesión).
5. **Given** a mood result is displayed, **When** the person triggers a new mood analysis that succeeds, **Then** the displayed result is replaced with the new result.

---

### User Story 2 - Mood Capture-Quality & Error Handling (Priority: P2)

When the mood capture does not contain exactly one usable face, or the image cannot be decoded, or the mood estimator port raises an error, the backend returns an actionable error in the pinned `{"error": {"code": "...", "message": "..."}}` shape and produces no mood result. Capture-quality failures (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`) return `400 Bad Request` with a message telling the person how to recapture; a port/adapter failure returns a recoverable `500 internal_error` (actionable: "try again"). The frontend shows the actionable error for the mood operation with a retry option that does not require a full page reload, and re-enables the mood button. The mood error is independent from any age error (separate error surfaces per PRD §6.4).

**Why this priority**: Actionable, recoverable errors are a PRD §6.4 / FR-015 requirement and keep the demo from dead-ending on a bad capture. It is independently testable by submitting each failure mode and asserting the correct actionable code, status, and that no mood result is produced.

**Independent Test**: With a valid session, call `POST /api/analysis/mood` with (a) an undecodable/oversized image → assert `400 invalid_image`; (b) a fixture image the mock detector reports as zero faces → assert `400 no_face`; (c) a fixture image the mock detector reports as two faces → assert `400 multiple_faces`; (d) a fixture triggering a port error → assert `500 internal_error`. In each case assert the body is the pinned error shape and no mood result is returned. Delivers correct, actionable mood error handling.

**Acceptance Scenarios**:

1. **Given** a valid session, **When** the capture contains no face, **Then** the backend returns `400` with `code: "no_face"` and an actionable message indicating the person should recapture, and produces no mood result (FR-004, FR-015).
2. **Given** a valid session, **When** the capture contains more than one face, **Then** the backend returns `400` with `code: "multiple_faces"` and an actionable message indicating only one person should appear, and produces no mood result.
3. **Given** a valid session, **When** the image is undecodable, unsupported, or oversized, **Then** the backend returns `400` with `code: "invalid_image"` and an actionable message, and produces no mood result.
4. **Given** a valid session, **When** the detector or mood_estimator port raises an error, **Then** the backend returns `500` with `code: "internal_error"` and a recoverable message, and produces no mood result.
5. **Given** a mood error response, **When** the frontend receives it, **Then** it hides the loading indicator, re-enables the mood button, and shows the actionable mood error with a retry option that does not require a full page reload (FR-015, PRD §10).
6. **Given** the mood estimator returns an out-of-set or low-quality label, **When** the backend normalizes it, **Then** the response label is `no concluyente` (the person always gets a readable category rather than a failure).

---

### User Story 3 - Session Gating & Concurrent-Action Prevention on Mood (Priority: P3)

The `POST /api/analysis/mood` endpoint is protected by the real session validation from spec 003: a request without a valid (present, non-expired, non-revoked) session is rejected with `401 unauthenticated` and performs no analysis. On the frontend, the mood button is disabled while a mood analysis is in flight (FR-014) and a second press is ignored — one capture at a time. If the session expires or is revoked mid-analysis, the in-flight request receives `401 unauthenticated` and the frontend transitions to the unauthenticated state (redirect to `/login`), discarding any partial mood result.

**Why this priority**: Session gating keeps the mood endpoint behind the real session (FR-010, spec 003) and FR-014 prevents confusing concurrent captures. It is independently testable by attacking the endpoint without/with an invalid session and by attempting a double press during an in-flight analysis.

**Independent Test**: Without a cookie, call `POST /api/analysis/mood` → assert `401 unauthenticated` and no analysis. With an expired/revoked session → assert `401 unauthenticated`. With a valid session, trigger a mood analysis and issue a second `POST /api/analysis/mood` before the first resolves → assert the frontend ignores/disables the second press (one capture at a time). Delivers real session-gated, non-concurrent mood analysis.

**Acceptance Scenarios**:

1. **Given** no valid session, **When** `POST /api/analysis/mood` is called, **Then** it returns `401 unauthenticated` and performs no analysis (FR-010, spec 003).
2. **Given** an expired or revoked session, **When** `POST /api/analysis/mood` is called, **Then** it returns `401 unauthenticated` and performs no analysis.
3. **Given** a mood analysis is in flight, **When** the person presses the mood button again, **Then** the button is disabled and the second press is ignored — no second capture or request is initiated (FR-014, one capture at a time).
4. **Given** a mood analysis is in flight, **When** the session expires or is revoked before the response, **Then** the response is `401 unauthenticated`, the frontend discards any partial mood result, and transitions to the unauthenticated state (redirect to `/login`).
5. **Given** a mood analysis completes (success or error), **When** it finishes, **Then** the mood button is re-enabled and a new analysis can be triggered.

---

### User Story 4 - Frontend Dashboard Mood UI & Disabled Age Placeholder (Priority: P4)

The `/dashboard` renders, for an authenticated person: an active-session indicator, the camera preview, the "Detectar estado de ánimo" button, a "Calcular edad" button present but disabled with a visible "coming soon" indication (placeholder pending spec 005), an independent loading indicator for mood, the most recent mood result (label + optional confidence + disclaimer) persisted visible until a new analysis or logout, an independent recoverable error surface for mood, and the "Cerrar sesión" button (from spec 003). The mood button captures a single still on press (no continuous streaming), drives an independent mood state machine (idle → capturing/loading → result | error), is keyboard-accessible with a descriptive name, shows immediate feedback on press, and allows retry without a full page reload on recoverable errors. Results do not rely exclusively on color to communicate state (PRD §10).

**Why this priority**: The dashboard UI is how the demo audience experiences on-demand mood analysis. It delivers the PRD §6.4 dashboard layout (mood portion), FR-011 (capture), FR-014 (disable while in progress), FR-015 (actionable errors), and PRD §10 frontend requirements. The disabled age placeholder keeps the layout stable for spec 005. It is independently testable with a mocked camera device and a mocked fetch layer.

**Independent Test**: Render `/dashboard` with an authenticated session, a mocked `MediaDevices` source yielding a test frame, and a mocked fetch returning a successful mood response; walk the mood state machine from idle through button-press (assert button disables and loading indicator shows), response (assert result + disclaimer render and button re-enables), and a recoverable error (assert error surface shows with retry, no full reload). Assert the "Calcular edad" button is present, disabled, and shows a "coming soon" indication. Assert the mood button is keyboard-reachable and has a descriptive accessible name. Delivers a navigable, accessible mood dashboard UI.

**Acceptance Scenarios**:

1. **Given** the dashboard is rendered with an authenticated session, **When** the camera preview is active, **Then** the "Detectar estado de ánimo" button and the disabled "Calcular edad" button are both visible, and the mood button is keyboard-accessible with a descriptive name (PRD §6.4, §10).
2. **Given** the dashboard, **When** the person presses the mood button, **Then** a single still is captured, the independent mood loading indicator is shown, and the mood button is disabled (FR-011, FR-014).
3. **Given** a successful mood response, **When** the frontend receives it, **Then** the mood result (label, optional confidence, disclaimer) is rendered and remains visible until a new analysis or logout (PRD §6.4, §10).
4. **Given** a mood error response, **When** the frontend receives it, **Then** the independent mood error surface shows an actionable message with a retry option that does not require a full page reload, and the mood button is re-enabled (FR-015).
5. **Given** the "Calcular edad" button, **When** it is rendered, **Then** it is disabled and shows a visible indication that age estimation is not yet available (placeholder pending spec 005); pressing it performs no action.
6. **Given** a mood result or error is displayed, **When** the state is communicated, **Then** it does not rely exclusively on color (PRD §10).
7. **Given** the person logs out (spec 003) or the session expires, **When** the dashboard unmounts, **Then** any held mood result is discarded and no longer accessible without re-authenticating.

---

### User Story 5 - Automated Mood Analysis Tests (Priority: P5)

An automated test suite covers the mood analysis flow: unit tests for label normalization (out-of-set → `no concluyente`), the valid-label set enforcement, confidence bounds, and the error-code mapping; integration tests exercising the real `POST /api/analysis/mood` endpoint wired to the mock detector and mock mood_estimator adapters and the real session validation (spec 003) — covering the happy path, each capture-quality failure, the port-error path, and the unauthenticated path; and contract tests asserting the `200` response shape (`label`, `confidence`, `disclaimer`), the status codes (`200`/`400`/`401`/`500`), and the error body shape. The domain portions run without GPU, network, or real models.

**Why this priority**: Tests are the safety net that lets spec 005 (age) and Fase 5 (real models) build on the mood flow without regressing it (PRD §15, Constitution Quality Gates §4–§7). It is independently testable by running the suite under no-GPU/no-network constraints.

**Independent Test**: Run the mood test suite in an environment with no GPU and no network; assert all unit, integration, and contract tests pass, that a deliberate contract-violating change to the mood response shape causes a contract test to fail, and that a deliberate change allowing an out-of-set label causes a unit test to fail. Delivers a green, reproducible mood test foundation.

**Acceptance Scenarios**:

1. **Given** the mood test suite, **When** it is run with no GPU and no network, **Then** all unit tests for label normalization, the valid-label set, confidence bounds, and error mapping pass.
2. **Given** the test suite, **When** it is run against the real mood endpoint with mock adapters and real session validation, **Then** the integration tests for the happy path, each capture-quality failure, the port-error path, and the unauthenticated path pass.
3. **Given** the test suite, **When** it is run, **Then** the contract tests assert the `200` response shape (`label`, `confidence`, `disclaimer`), the status codes (`200`/`400`/`401`/`500`), and the pinned error body shape.
4. **Given** a contract-violating change to the mood response, **When** the contract tests are run, **Then** at least one test fails.
5. **Given** a change allowing an out-of-set label, **When** the unit tests are run, **Then** at least one test fails.

---

### Edge Cases

- What happens when the capture contains no face or more than one face during a mood analysis? The backend returns `400 no_face` / `multiple_faces` with an actionable recapture message and produces no mood result (FR-004, FR-015).
- What happens when the mood estimator port returns a label outside the valid set or a low-quality signal? The backend normalizes it to `no concluyente` and returns `200` with the disclaimer; the person always gets a readable category rather than a failure (PRD §6.4).
- What happens when `confidence` is not produced by the mood estimator? The `confidence` field is `null` or omitted in the response; the frontend renders the label and disclaimer without a confidence value (PRD §6.4 — confianza opcional).
- What happens when the detector or mood_estimator port raises an error? The backend returns a recoverable `500 internal_error` (actionable: "try again") and produces no mood result; no partial result is shown.
- What happens when the session expires or is revoked while a mood analysis is in flight? The in-flight request receives `401 unauthenticated`; the frontend discards any partial mood result and transitions to the unauthenticated state (redirect to `/login`).
- What happens when the person presses the mood button twice rapidly? The button is disabled on the first press; the second press is ignored — one capture at a time, no second request (FR-014).
- What happens when the camera stream ends or the permission is revoked mid-capture? The UI transitions to a recoverable mood error state with an actionable message and a retry option (PRD §10).
- What happens when the image is valid but exceeds the size/format/long-edge limits? The backend returns `400 invalid_image` and produces no mood result (reusing spec 002 limits, Constitution OQ-8).
- What happens when the mood endpoint is called without a session cookie? The backend returns `401 unauthenticated` and performs no analysis (FR-010, spec 003).
- What happens when the mood estimator returns a valid label but a `confidence` outside `[0,1]`? The backend clamps/normalizes or treats it as absent (renders without confidence); the contract test asserts `confidence` is in `[0,1]` or null/omitted.
- What happens when a mood result is displayed and the person logs out? The dashboard unmounts and the held mood result is discarded; re-accessing `/dashboard` requires re-authentication and shows no prior result (result is transient, not server-persisted).
- What happens when two concurrent mood requests reach the backend (e.g. a race despite the frontend guard)? The backend processes each independently against the session; this is permitted (no server-side single-analysis lock — demo-first). The frontend guard prevents this in practice.
- What happens when the camera permission is denied or unavailable on dashboard load or mood button press? The frontend shows an actionable mood error surface with a message to grant camera permission and a retry option (no full page reload); no capture or backend request is initiated until permission is granted (FR-015, PRD §10). This is a frontend-only state, distinct from `invalid_image`.
- What happens to the camera stream on logout or session expiry? The dashboard unmounts and the camera stream is released; re-accessing `/dashboard` requires re-authentication and re-acquires the stream (no prior stream or mood result is retained).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose `POST /api/analysis/mood` accepting `multipart/form-data` with an `image` field, protected by the real session validation from spec 003 (`require_valid_session`); requests without a valid (present, non-expired, non-revoked) session MUST be rejected with `401 unauthenticated` and perform no analysis (PRD §8, FR-010, spec 003).
- **FR-002**: On a valid session and a capture containing exactly one usable face, the system MUST run the mood_estimator port on the detected face and return `200 OK` with a body containing `label` (a member of `{neutral, feliz, triste, sorprendido, enojo, no concluyente}`), `confidence` (a float in `[0.0, 1.0]`, or null/omitted when not produced), and `disclaimer` (the exact PRD §8 string) (PRD §8, FR-012, AC-007).
- **FR-003**: The `disclaimer` MUST be the fixed string `"Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."` on every `200` mood response, and the frontend MUST render it alongside the result so the interface communicates the result is a model inference, not an objective measurement (PRD §6.4, §12).
- **FR-004**: The mood label MUST be a member of `{neutral, feliz, triste, sorprendido, enojo, no concluyente}`; any out-of-set or low-quality port output MUST be normalized to `no concluyente` so the person always receives a readable category (PRD §6.4).
- **FR-005**: The endpoint MUST evaluate conditions in the order: session validation → image decode/limit validation → detection (exactly one face) → mood estimation → label normalization → response, reusing the image limits (JPEG, ≤ 2 MB, ≤ 640px long edge) and pydantic `Settings` from spec 002 (Constitution OQ-8).
- **FR-006**: Capture-quality failures MUST return `400 Bad Request` with the pinned error body `{"error": {"code": "...", "message": "..."}}` and actionable codes `no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, with human messages indicating how to recapture; no mood result MUST be produced (PRD FR-004, FR-015, specs 002/003 error shape).
- **FR-007**: A detector or mood_estimator port/adapter error MUST return a recoverable `500 internal_error` with an actionable "try again" message and produce no mood result; `401` is reserved exclusively for `unauthenticated` (session-gating) so the status-code mapping stays crisp (specs 002/003).
- **FR-008**: The frontend MUST capture a single still image from the camera via standard browser media APIs on mood button press (no continuous streaming/frame sending), send it to `POST /api/analysis/mood` with the session cookie, and show an independent mood loading indicator immediately on press (PRD §6.4, §10, FR-011).
- **FR-009**: The frontend MUST disable the mood button while a mood analysis is in flight and ignore a second press — one capture at a time (FR-014). On completion (success or error) the button MUST be re-enabled.
- **FR-010**: The frontend MUST display the most recent mood result (label, optional confidence, disclaimer) and keep it visible until a new analysis is triggered or the session ends (logout/expiry); after logout the held result MUST be discarded and inaccessible without re-authentication (PRD §10, §6.4).
- **FR-011**: The frontend MUST show an independent, actionable mood error surface with a retry option that does not require a full page reload on recoverable errors, separate from any age error surface (PRD §6.4, FR-015).
- **FR-012**: The mood button MUST be keyboard-accessible with a descriptive accessible name, and result/error states MUST NOT rely exclusively on color to communicate state (PRD §10).
- **FR-012a**: When `confidence` is present, the frontend MUST render it as a percentage rounded to the nearest integer with a "≈" prefix (e.g. `0.8123` → "≈81%"); when `confidence` is null or omitted, the frontend MUST render only the label and disclaimer with no confidence value (PRD §6.4 — valor aproximado).
- **FR-012b**: The frontend MUST acquire the camera stream on dashboard mount (preview active) and release it on dashboard unmount (logout/session expiry/navigation away). The mood button captures a single still from the live preview; it does not open a separate stream per capture (PRD §6.4, §10).
- **FR-012c**: If the camera permission is denied or unavailable, the frontend MUST show an actionable mood error surface with a message to grant permission and a retry option (no full page reload); no capture or backend request MUST be initiated until permission is granted (FR-015, PRD §10). This is a frontend-only state distinct from `invalid_image`.
- **FR-013**: The dashboard MUST render a "Calcular edad" button that is present but disabled with a visible "coming soon" indication (placeholder pending spec 005); pressing it MUST perform no action (PRD §6.4, scope boundary).
- **FR-014**: The mood analysis result MUST NOT be persisted server-side in this spec; it is transient (frontend state only). No `AnalysisRequest` audit row is written (PRD §7 optional, §19 pending; Constitution Principle I — demo-first/YAGNI).
- **FR-015**: The domain orchestration of mood analysis MUST depend only on the ports (detector, mood_estimator, session manager) and MUST NOT import any concrete ML model, web framework, or infrastructure adapter directly (Constitution Principle VII).
- **FR-016**: The mood_estimator port MUST be wired to the mock adapter from spec 001 for this entire spec; real mood models are deferred to Fase 5 and are out of scope (Constitution Principle VII; the port makes the swap a configuration change).
- **FR-017**: The mood_estimator adapter MUST carry an identifiable model version so results are reproducible (PRD §11, spec 001 FR-012).
- **FR-018**: An automated test suite MUST cover mood unit (label normalization, valid-label set, confidence bounds, error mapping), integration (real endpoint + mock adapters + real session validation — happy path, each capture failure, port error, unauthenticated), and contract (`200` shape, status codes `200`/`400`/`401`/`500`, pinned error body) cases, with the domain portions running without GPU, network, or real models (PRD §15, Constitution Quality Gates §5/§7).
- **FR-019**: No image, embedding, or biometric response MUST appear in application logs; observability is limited to structured JSON logs (duration, type, status of the mood operation) consistent with specs 001/002/003 and Constitution Principle VIII (PRD §12, §13).

### Key Entities *(include if feature involves data)*

- **MoodResult (transient view model)**: The result of a mood analysis, returned to the frontend and held in client state. Attributes: `label` (∈ `{neutral, feliz, triste, sorprendido, enojo, no concluyente}`), `confidence` (float in `[0,1]` or null/omitted), `disclaimer` (fixed PRD §8 string). Not persisted server-side (FR-014). Derived from the detector + mood_estimator ports; no new persistent entity is introduced in this spec.
- **AuthSession (from spec 003)**: The validated session gating the mood endpoint. No new attributes; reused as-is via `require_valid_session`.
- **User (from spec 002)**: The authenticated person requesting the analysis. No new attributes; the session's `userId` identifies the requester for logging (not for result persistence).
- **Mood Estimator Port (from spec 001)**: The hexagonal port declaring mood estimation against a detected face; the mock adapter implements it deterministically in this spec, and a real open-source model adapter will implement it in Fase 5 (Constitution Principle VII, OQ-5).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with a valid session can trigger a mood analysis from `/dashboard` and see a mood category (or `no concluyente`) with the disclaimer in under 5 seconds in the local demo environment (excluding exceptional model-load time), verifiable by a timed walk-through of the happy path (PRD §13, AC-007).
- **SC-002**: A valid mood request returns `200 OK` with `label` in the valid set, `confidence` in `[0,1]` or null/omitted, and the exact PRD §8 `disclaimer`, verifiable by calling the endpoint with a one-face fixture (AC-007, FR-012).
- **SC-003**: The mood endpoint rejects requests without a valid session with `401 unauthenticated` and performs no analysis, verifiable by calling it with no cookie, an expired session, and a revoked session (FR-010, spec 003).
- **SC-004**: Each capture-quality failure (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`) returns `400` with the pinned error body and produces no mood result, verifiable by submitting each case (FR-004, FR-015).
- **SC-005**: A port/adapter error returns `500 internal_error` with a recoverable message and produces no mood result, verifiable by triggering a port failure (FR-007).
- **SC-006**: The mood button is disabled while an analysis is in flight and a second press is ignored (one capture at a time), verifiable by attempting a double press during an in-flight request (FR-014).
- **SC-007**: The most recent mood result remains visible until a new analysis or logout, and is discarded on logout, verifiable by performing a successful analysis, observing persistence, logging out, and confirming the result is inaccessible (PRD §10).
- **SC-008**: The "Calcular edad" button is present but disabled with a "coming soon" indication and performs no action, verifiable by inspecting the dashboard and pressing the disabled button (scope boundary, PRD §6.4).
- **SC-009**: The mood domain orchestration has zero imports of concrete ML models or infrastructure adapters (it depends only on ports), verifiable by static dependency inspection of the mood domain code (Constitution Principle VII).
- **SC-010**: The full mood test suite (unit + integration + contract) passes in an environment with no GPU and no network, verifiable by running the suite under those constraints (PRD §15).
- **SC-011**: A deliberate contract-violating change to the mood response, or a change allowing an out-of-set label, causes at least one test to fail, verifiable by introducing and reverting such a change.
- **SC-012**: No real ML model is integrated for mood estimation in this spec — the mood_estimator port uses the mock adapter from spec 001 — verifiable by confirming the spec's scope does not extend into Fase 5 (Constitution Principle VII).
- **SC-013**: No image, embedding, or biometric response appears in application logs, verifiable by inspecting the logs produced during mood analysis (PRD §12, §13).
- **SC-014**: When `confidence` is present it renders as "≈NN%" (nearest integer); when null/omitted no confidence is rendered, verifiable by inspecting the frontend output for both cases (FR-012a, PRD §6.4).
- **SC-015**: The camera stream is acquired on dashboard mount and released on unmount (logout/session expiry), verifiable by observing stream lifecycle across mount/unmount and confirming no stream leak after logout (FR-012b).
- **SC-016**: A denied/unavailable camera shows an actionable mood error with retry and initiates no backend request, verifiable by denying `getUserMedia` and asserting no `POST /api/analysis/mood` is issued (FR-012c).

## Assumptions

- This spec builds directly on specs 001, 002, and 003: the runnable stack, the four views, the seven HTTP contract endpoints (here `POST /api/analysis/mood` is filled with real logic; `POST /api/analysis/age` and `DELETE /api/users/{userId}/face-data` remain session-gated stubs per spec 001/003), the domain entities (`User`, `FaceTemplate`, `AuthSession`), the hexagonal ports (detector, embedder, comparison, mood_estimator, age_estimator, session manager, user repository, face-template repository, image storage), the mock adapters, the PostgreSQL schema/migrations, the filesystem image-storage adapter, the real session validation (`require_valid_session`), the `ProtectedRoute`, and the "Cerrar sesión" button are all assumed to exist and be reused, not re-created.
- The technology stack is fixed by the Constitution (Principle III / Technology Stack table): backend in Python with FastAPI, frontend in React with Vite, PostgreSQL for persistence, Docker Compose for orchestration. These are project-level decisions, not ad hoc implementation choices, and are assumed settled for this spec.
- The mood response body is `{"label": "...", "confidence": ..., "disclaimer": "..."}` with `200 OK`. `label` ∈ `{neutral, feliz, triste, sorprendido, enojo, no concluyente}` (PRD §6.4). `confidence` is a float in `[0,1]` when present, or null/omitted when the estimator does not produce one (PRD §6.4 — optional). `disclaimer` is the exact PRD §8 string. This is the pinned contract.
- The error body shape is the spec-002-pinned `{"error": {"code": "...", "message": "..."}}` flat shape, reused verbatim. Machine codes are stable strings (`unauthenticated`, `no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, `internal_error`). Status-code mapping is pinned: `401` exclusively for `unauthenticated` (session-gating); `400` for the actionable capture-quality codes; `500` for recoverable `internal_error`. Human messages are actionable per FR-015 and reveal no internal details.
- The endpoint evaluates conditions in the order: session validation → image decode/limit validation → detection (exactly one face) → mood estimation → label normalization → response. This reuses the spec 002 image limits (JPEG, ≤ 2 MB, ≤ 640px long edge — Constitution OQ-8) and the spec 003 session validation.
- The mood result is transient: it is NOT persisted server-side. No `AnalysisRequest` audit row is written. PRD §7 marks `AnalysisRequest` optional and PRD §19 lists result persistence as pending; the demo-first Constitution Principle I and YAGNI rule out audit rows no acceptance criterion requires. The result lives in frontend state and remains visible until a new analysis or session end (PRD §10). `AnalysisRequest` persistence is deferred to a later spec if a demo narrative need arises.
- The mood label is normalized against the valid set; any out-of-set or low-quality port output becomes `no concluyente` so the person always gets a readable category (PRD §6.4). This is a reasonable demo default that avoids dead-ending the UI on an unexpected port output.
- The `disclaimer` is a fixed string returned verbatim by the backend and rendered by the frontend, satisfying PRD §6.4/§12 ("comunicar que se trata de una inferencia del modelo y no de una medición objetiva"; "No presentar edad o estado de ánimo como hechos ciertos").
- FR-014 (no simultaneous invalid actions) is implemented as: the mood button is disabled while a mood analysis is in flight and a second press is ignored (one capture at a time). The age button is already disabled as a placeholder, so it cannot trigger a concurrent capture. The mood and age loading indicators are independent (PRD §6.4); only the mood indicator is exercised in this spec. No server-side single-analysis lock is added (demo-first); the frontend guard is the policy.
- The "Calcular edad" button is rendered but disabled with a visible "coming soon" indication, keeping the dashboard layout stable for spec 005. PRD §6.4 lists both buttons, so both are shown; only mood is wired in this spec. This is a reasonable default that avoids layout rework in spec 005.
- The mood_estimator port is wired to the mock adapter from spec 001 for this entire spec. Real open-source mood models are explicitly deferred to Fase 5 (Constitution Principle VII, OQ-5); the port makes the swap a configuration change, not a redesign. The mock mood estimator returns a deterministic label + confidence for fixture inputs.
- The mood_estimator adapter carries an identifiable model version (PRD §11, spec 001 FR-012); with the mock adapter this is a fixed mock version string.
- Age estimation (spec 005), face-data deletion (spec 006), real ML models (Fase 5), continuous video analysis, rate limiting, liveness/anti-spoofing, and `AnalysisRequest` persistence are explicitly out of scope for this spec. The age and delete endpoints remain session-gated stubs from spec 001/003.
- Observability in this spec is limited to structured JSON logs (duration, type, status of the mood operation) with no images, embeddings, or biometric responses logged, consistent with specs 001/002/003 and Constitution Principle VIII (no traceability guarantee).
- The frontend camera is accessed via standard browser `getUserMedia`; tests mock `MediaDevices` with controlled test frames and mock the fetch layer for mood responses, as anticipated by PRD §15. A secure context (`localhost` or HTTPS) is required for camera access and is assumed available in the local demo.
- The session validation, `ProtectedRoute`, and "Cerrar sesión" button from spec 003 are reused unchanged; this spec adds the mood button, mood result/error surfaces, mood loading indicator, and the disabled age placeholder to the dashboard.
- The camera stream is acquired on dashboard mount (preview active per PRD §6.4) and released on unmount (logout/session expiry/navigation away); the mood button captures a single still from the live preview and does not open a separate stream per capture. If camera permission is denied or unavailable, the frontend shows an actionable mood error with a retry and makes no backend call until permission is granted. These are reasonable defaults consistent with resource hygiene and the recoverable error pattern.
