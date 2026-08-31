# Feature Specification: Login & Session Management (Fase 3)

**Feature Branch**: `003-login-session-management`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Login and session management (Fase 3 of the PRD). This spec implements real face-login verification 1:1, session creation/management, route protection, and logout, building on specs 001 (skeleton/ports/mocks) and 002 (onboarding — User + FaceTemplate now exist). It covers PRD §6.3 (Flujo de login facial + Decisión verificación 1:1), FR-007 (Iniciar sesión con el rostro — verify face against template for given identifier), FR-008 (Aplicar umbral de similitud — configurable threshold, not frontend-only), FR-009 (Crear sesión — only after successful face verification), FR-010 (Proteger dashboard — deny /dashboard and its endpoints without valid session), FR-016 (Cerrar sesión — invalidate session, block protected routes after logout). Acceptance criteria AC-004 (Login exitoso), AC-005 (Login rechazado — generic error, allow retry), AC-006 (Ruta protegida — redirect to login), AC-009 (Logout — invalidate, leave dashboard, cannot re-access). Builds on specs 001 & 002; real ML models deferred to Fase 5 (mock adapters retained)."

## Clarifications

### Session 2026-08-31 (auto-resolved at specify gate)

- Q: What distance metric and default threshold value are used for the 1:1 verification? -> A: Cosine similarity (Constitution OQ-6 default) between the captured embedding and the stored `FaceTemplate.embedding`, with a default acceptance threshold of `0.5` overridable via an environment variable loaded through the existing pydantic `Settings`. The threshold is enforced server-side (FR-008 — not frontend-only). The metric is behind the comparison port so Fase 5 can swap it without touching the domain.
- Q: What session mechanism is used? -> A: Server-side session in PostgreSQL (`AuthSession`, PRD §7) keyed by a signed cookie (Constitution OQ-3 default). On successful verification the backend creates an `AuthSession` row (`id`, `userId`, `createdAt`, `expiresAt`, `revokedAt = null`) and sets a signed, http-only cookie on the response. No JWT (Principle VIII — no security guarantee). Session validity = a row exists for the cookie's session id, `revokedAt` is null, and `expiresAt` is in the future.
- Q: What is the default session lifetime? -> A: 30 minutes, configurable via environment variable. Expired sessions are treated as invalid (no automatic refresh in this spec — demo-first; re-login is the refresh path).
- Q: What is the exact shape of the login failure response, and how is the non-revealing requirement satisfied? -> A: The error body shape established and pinned in spec 002 is reused: `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}` (Content-Type `application/json`). For login, the nonexistent-identifier case and the below-threshold (non-matching-face) case MUST return the same machine code (`auth_failed`) and the same human message, so the two are indistinguishable (PRD §6.3, §12, FR-015). Capture-quality failures (no face, multiple faces, undecodable image) return their own actionable capture codes (`no_face`, `multiple_faces`, `invalid_image`) because they tell the person how to recapture; the residual identifier-existence leak this implies is a documented demo limitation under Constitution Principle VIII (no security guarantee), not a gap to close in this spec.
- Q: What does `GET /api/auth/me` return? -> A: `200 OK` with `{"authenticated": true, "userId": "<id>"}` when a valid session exists; `401 Unauthorized` with the generic error body (`{"error": {"code": "unauthenticated", "message": "..."}}`) when there is no cookie, the session is expired, revoked, or unknown. The frontend uses this to bootstrap the real session state on load and to gate `ProtectedRoute`.
- Q: In what order does the login endpoint evaluate failure conditions? -> A: (1) decode + validate the image (format/size/long-edge, reusing spec 002 limits) → `invalid_image` if undecodable/unsupported/oversized; (2) run the detector port → `no_face` / `multiple_faces` / `insufficient_quality` if the capture is not exactly one usable face; (3) load the `User` + `FaceTemplate` for the normalized identifier via the repository ports → if not found, `401 auth_failed` (generic); (4) run the embedder port on the captured face → embedding; (5) compute cosine similarity vs the stored embedding → if `< threshold`, `401 auth_failed` (generic, identical to step 3's not-found response); (6) on `>= threshold`, create the `AuthSession`, set the signed cookie, return `200` with `userId` + `status: "authenticated"`. Steps 3 and 5 are the two cases that share the identical generic response.
- Q: How is the identifier normalized for the login lookup? -> A: The same normalization as spec 002 — trim leading/trailing whitespace then lowercase — so the login lookup is case-insensitive and matches the canonical stored form.
- Q: Are backend protected endpoints (analysis, delete, me, logout) enforced against the real session in this spec? -> A: Yes. The placeholder session guard from spec 001 is replaced with real session validation: any endpoint marked protected rejects with `401 unauthenticated` when the cookie is absent, the session id is unknown, `revokedAt` is set, or `expiresAt` has passed. The dashboard's own data endpoints (mood/age) remain stubbed from spec 001 but are now genuinely session-gated; their analysis logic is spec 004/005.
- Q: Is `POST /api/auth/face-login` itself session-protected? -> A: No. Login is the session-creation endpoint and must be reachable without a session. `POST /api/onboarding` likewise remains unprotected (spec 002).
- Q: What happens to any pre-existing session when a person logs in again? -> A: A new `AuthSession` is created and a new cookie set; the previous session is not automatically revoked (demo-first — no single-session constraint). The old session remains valid until it expires or is explicitly revoked. This is documented as a demo simplification, not a security policy.

> **RESOLVED at specify gate (2026-08-31)**: The error body shape is the spec-002-pinned `{"error": {"code": "...", "message": "..."}}` flat shape; machine codes are stable strings (`auth_failed`, `unauthenticated`, `no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, `internal_error`) and human messages are actionable per FR-015 and reveal no internal details. This is pinned and flows into plan, contracts, and contract-test assertions.

### Session 2026-08-31 (auto-resolved at clarify gate)

- Q: What HTTP status code is used for capture-quality and invalid-image failures during login? -> A: `400 Bad Request` with the actionable capture error body (`no_face` / `multiple_faces` / `invalid_image` / `insufficient_quality`). `401 Unauthorized` is reserved exclusively for `auth_failed` (identity-sensitive login failure) and `unauthenticated` (session-gating on protected endpoints), so a `401` from the login endpoint always means "we could not authenticate you" and never leaks whether the identifier existed. This keeps the non-revealing contract from FR-008 crisp and makes the capture-vs-auth distinction statically testable in contract tests.
- Q: What is the response shape of `POST /api/auth/logout` on success? -> A: `200 OK` with body `{"status": "ok"}`, consistent with the login response's `status` field and the established JSON-body convention. The same success body is returned idempotently for no-cookie, expired, revoked, and valid sessions alike (FR-012 idempotence); no error body is ever returned from logout.
- Q: Does the successful login response include the session expiry (`expiresAt`)? -> A: No. The login response body is exactly `{"userId": "<id>", "status": "authenticated"}` per FR-005. `expiresAt` is not exposed to the frontend; the frontend learns of expiry reactively when a subsequent protected call returns `401 unauthenticated`. This is consistent with the no-auto-refresh decision (default 30 min lifetime, re-login is the refresh path) and avoids surfacing a server-side session detail to the client.

## User Scenarios & Testing *(mandatory)*

<!--
  This spec implements real face-login verification 1:1, server-side session
  management, route protection, and logout on top of specs 001 (skeleton/ports/
  mocks) and 002 (onboarding — User + FaceTemplate exist). Stories are ordered so
  each independently delivers a demonstrable, testable slice and maps to PRD
  AC-004..AC-006, AC-009 and FR-007..FR-010, FR-016, FR-015. All ML touchpoints
  go through the ports established in spec 001; mock adapters are used in this
  spec (real models arrive in Fase 5).
-->

### User Story 1 - Successful Face Login (Happy Path) (Priority: P1)

A person who has already completed onboarding (spec 002) returns to the login page, enters the same identifier they enrolled with, grants camera permission, captures a new image of their face, and submits. The frontend sends the identifier and the captured image to `POST /api/auth/face-login`. The backend decodes and validates the image, runs the detector port and finds exactly one face, loads the `User` and `FaceTemplate` for the normalized identifier via the repository ports, runs the embedder port to get a captured embedding, computes cosine similarity against the stored template embedding, and finds it at or above the configured threshold. The backend creates an `AuthSession` row in PostgreSQL, sets a signed http-only cookie on the response, and returns `200 OK` with `userId` and `status: "authenticated"`. The frontend stores the session state and redirects to `/dashboard`.

**Why this priority**: This is the core login narrative and the gate to every authenticated experience in the demo (dashboard, analysis). It delivers AC-004 (Login exitoso) and exercises FR-007, FR-008, FR-009 end-to-end. Without a working face login there is no session to protect or revoke.

**Independent Test**: Seed a `User` + `FaceTemplate` (via the onboarding endpoint or a fixture), then call `POST /api/auth/face-login` with the same identifier and a fixture image whose mock-embedder embedding yields cosine similarity `>= threshold` against the stored embedding; assert a `200` response with `userId` and `status: "authenticated"`, a signed cookie in the response, and an `AuthSession` row in the database with `revokedAt = null` and `expiresAt` in the future. Delivers a complete, demonstrable login.

**Acceptance Scenarios**:

1. **Given** a `User` with an enrolled `FaceTemplate` exists, **When** the person submits that identifier and a captured image whose embedding matches the template at cosine similarity `>= threshold`, **Then** the backend returns `200 OK` with `userId` and `status: "authenticated"` and sets a signed http-only session cookie (AC-004).
2. **Given** a successful login response, **When** the database is inspected, **Then** exactly one new `AuthSession` row exists for that `userId` with `revokedAt = null` and `expiresAt` in the future (FR-009).
3. **Given** a successful login response, **When** the frontend receives it, **Then** it transitions to the authenticated session state and redirects to `/dashboard`.
4. **Given** the signed cookie from a successful login, **When** `GET /api/auth/me` is called with that cookie, **Then** it returns `200` with `{"authenticated": true, "userId": "<id>"}`.

---

### User Story 2 - Login Rejected with Generic Non-Revealing Error (Priority: P2)

When verification fails — either because the identifier has no registered profile/template, or because the captured face does not match the stored template (cosine similarity below threshold) — the backend does not create a session and returns a single `401 Unauthorized` response with a generic, non-revealing message that is identical for both failure causes, so an attacker cannot distinguish a nonexistent identifier from a non-matching face. The UI shows the generic error and allows the person to retry without reloading. Capture-quality failures (no face, multiple faces, undecodable image) return actionable capture-specific messages so the person can recapture.

**Why this priority**: Non-revealing rejection is the PRD §6.3 / §12 / FR-015 security-of-the-demo requirement and delivers AC-005 (Login rechazado). It is independently testable by submitting each failure mode and asserting the identical generic response for the two identity-sensitive causes and actionable distinct responses for capture-quality causes.

**Independent Test**: Seed a known `User` + `FaceTemplate`. Submit (a) a nonexistent identifier with any image, and (b) the known identifier with an image whose embedding yields similarity `< threshold`; assert both return `401` with the same machine code `auth_failed` and the same human message, and that no `AuthSession` was created. Separately submit (c) an image with no face and (d) an image with multiple faces for the known identifier; assert each returns an actionable capture error (`no_face` / `multiple_faces`) and no session. Delivers correct, non-revealing rejection.

**Acceptance Scenarios**:

1. **Given** a `User` with a `FaceTemplate` exists, **When** the person submits that identifier with a captured face whose similarity is below the threshold, **Then** the backend returns `401` with the generic `auth_failed` error, creates no `AuthSession`, and the response is byte-identical to the nonexistent-identifier response (AC-005, PRD §6.3/§12).
2. **Given** no `User` exists for the submitted identifier, **When** the person submits any image, **Then** the backend returns `401` with the same generic `auth_failed` error and message as the non-matching-face case, and creates no `AuthSession`.
3. **Given** a valid identifier, **When** the capture contains no face or more than one face, **Then** the backend returns `400 Bad Request` with an actionable capture message (`no_face` / `multiple_faces`) indicating the person should recapture, and creates no `AuthSession`.
4. **Given** a login rejection, **When** the UI receives it, **Then** it shows the generic error for auth failures (with a retry option) or the actionable capture message for capture failures, and allows retry without a full page reload (FR-015).

---

### User Story 3 - Session Validation & Route Protection (Priority: P3)

The backend enforces real session validation on every protected endpoint (`GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`): a request is accepted only when it carries a signed cookie whose session id maps to a non-expired, non-revoked `AuthSession`. The frontend replaces the spec 001 in-memory session placeholder with real session state bootstrapped from `GET /api/auth/me`, and `ProtectedRoute` redirects any unauthenticated visit to `/dashboard` (and its sub-routes) to `/login`. Backend-protected endpoints reject unauthenticated requests with `401 unauthenticated`.

**Why this priority**: Route protection is what makes the dashboard and its endpoints gated behind a real session rather than a placeholder. It delivers AC-006 (Ruta protegida) and FR-010, and is the backbone for logout (Story 4) and for specs 004/005 (analysis endpoints). It is independently testable by attacking each protected route without a session and with an expired/revoked session.

**Independent Test**: Without any cookie, call each protected endpoint and attempt to navigate to `/dashboard`; assert each backend endpoint returns `401 unauthenticated` and the frontend redirects to `/login`. Then perform a successful login, call each protected endpoint with the resulting cookie, and assert they are accepted (analysis endpoints still return their stubbed responses from spec 001, but no longer reject). Then expire/revoke the session and assert the protected endpoints reject again. Delivers real, end-to-end route protection.

**Acceptance Scenarios**:

1. **Given** no valid session, **When** a person attempts to navigate to `/dashboard`, **Then** the frontend redirects them to `/login` (AC-006).
2. **Given** no valid session, **When** any protected backend endpoint is called, **Then** it returns `401 unauthenticated` and performs no protected action (FR-010).
3. **Given** a valid (non-expired, non-revoked) session cookie, **When** a protected endpoint is called, **Then** it is accepted and executes its behavior (analysis endpoints remain stubbed but are no longer session-blocked).
4. **Given** an expired session (`expiresAt` in the past), **When** a protected endpoint is called, **Then** it returns `401 unauthenticated` (the session is treated as invalid).
5. **Given** a revoked session (`revokedAt` set), **When** a protected endpoint is called, **Then** it returns `401 unauthenticated`.
6. **Given** the frontend loads with no cookie, **When** it bootstraps session state via `GET /api/auth/me`, **Then** it receives `401` and renders the unauthenticated state, and `ProtectedRoute` gates `/dashboard`.

---

### User Story 4 - Logout & Session Invalidation (Priority: P4)

From the dashboard, the person can press a "Cerrar sesión" button. The frontend calls `POST /api/auth/logout` with the session cookie. The backend sets `revokedAt` on the `AuthSession` row (invalidating it), clears the cookie, and returns a success response. The frontend clears its session state and navigates away from the dashboard to `/login`. After logout, the revoked session can no longer access any protected route or endpoint, and the person cannot return to `/dashboard` without re-authenticating.

**Why this priority**: Logout completes the session lifecycle and delivers AC-009 and FR-016. It is independently testable by logging in, calling logout, and asserting the session is revoked and all protected routes/endpoint reject afterward.

**Independent Test**: Perform a successful login, call `POST /api/auth/logout` with the session cookie, assert a success response and that the `AuthSession` row now has `revokedAt` set. Then call every protected endpoint with the now-revoked cookie and attempt to navigate to `/dashboard`; assert each returns `401 unauthenticated` and the frontend redirects to `/login`. Delivers a complete logout that truly invalidates the session.

**Acceptance Scenarios**:

1. **Given** the person is authenticated and on `/dashboard`, **When** they press "Cerrar sesión", **Then** the frontend calls `POST /api/auth/logout`, receives a success response, clears its session state, and navigates to `/login` (AC-009, FR-016).
2. **Given** a logout request with a valid session cookie, **When** the backend processes it, **Then** it sets `revokedAt` on the `AuthSession` row, clears the cookie on the response, and returns `200 OK` with `{"status": "ok"}`.
3. **Given** the session has just been revoked by logout, **When** any protected endpoint is called with the old cookie, **Then** it returns `401 unauthenticated` (AC-009 — cannot re-access).
4. **Given** the session has just been revoked, **When** the person attempts to navigate to `/dashboard`, **Then** the frontend redirects to `/login`.
5. **Given** a logout request with no cookie or an already-invalid session, **When** the backend processes it, **Then** it returns a success response (idempotent — logout is always "succeeds" from the client's perspective) and performs no harmful action.

---

### User Story 5 - Frontend Login Page, Real Session Wiring & Logout Button (Priority: P5)

The login page provides an identifier input, a camera preview, and a capture button, and drives the experience through states analogous to the onboarding state machine (inicial, solicitando permiso, cámara no disponible, listo para capturar, procesando, éxito/redirect, error recuperable). It requests camera access via standard browser media APIs, captures a single still on button press, sends the identifier + image to `POST /api/auth/face-login`, and on success redirects to `/dashboard`. On the dashboard, a keyboard-accessible "Cerrar sesión" button is visible and wired to the logout endpoint. The frontend replaces the spec 001 in-memory session placeholder with real session state: a session context bootstrapped from `GET /api/auth/me` on app load and updated on login/logout, and a `ProtectedRoute` component that enforces the real session (redirect to `/login` when unauthenticated). All controls are keyboard-accessible with descriptive names, and errors are actionable and recoverable without a full page reload.

**Why this priority**: The UI is how the demo audience experiences login, protection, and logout. It delivers the PRD §6.3 flow, FR-015 (actionable errors), and the real session wiring that replaces the spec 001 placeholder (referenced by spec 001's assumptions). It is independently testable with a mocked camera device and a mocked fetch layer.

**Independent Test**: Render the login page with a mocked `MediaDevices` source yielding a test frame and a mocked fetch that returns a successful login; walk the state machine from inicial through permission grant, ready-to-capture, processing, and redirect-to-dashboard, and separately through a recoverable auth error and a capture error; assert each state renders the correct controls and messages and the capture button is keyboard-reachable. Then render `/dashboard` with an authenticated session and assert the "Cerrar sesión" button is visible, keyboard-reachable, and triggers the logout flow. Finally, render `/dashboard` with no session and assert `ProtectedRoute` redirects to `/login`. Delivers a navigable, accessible login + protection + logout UI.

**Acceptance Scenarios**:

1. **Given** the login page in the inicial state, **When** the person enters an identifier, **Then** the camera-permission request control is enabled.
2. **Given** the person requests the camera, **When** the browser is requesting permission, **Then** the page is in the solicitando permiso state.
3. **Given** a camera permission denial or missing device, **When** the page handles the failure, **Then** it transitions to the cámara no disponible state with an actionable message and a retry option.
4. **Given** camera permission is granted, **When** the preview stream is active, **Then** the page is in the listo para capturar state showing the live preview and an enabled, keyboard-accessible capture button.
5. **Given** the person presses capture, **When** the login request is in flight, **Then** the page is in the procesando state and the capture button is disabled.
6. **Given** a successful login response, **When** the page receives it, **Then** it stores the real session state and redirects to `/dashboard`.
7. **Given** a `401 auth_failed` response, **When** the page receives it, **Then** it shows the generic error with a retry option that does not require a full page reload.
8. **Given** a capture-error response (`no_face` / `multiple_faces`), **When** the page receives it, **Then** it shows the actionable capture message with a recapture option.
9. **Given** the dashboard is rendered with an authenticated session, **When** the person presses the keyboard-accessible "Cerrar sesión" button, **Then** the logout endpoint is called, the session state is cleared, and the app navigates to `/login`.
10. **Given** the app loads, **When** the session context bootstraps via `GET /api/auth/me`, **Then** `ProtectedRoute` admits `/dashboard` only when the session is valid and redirects to `/login` otherwise.

---

### User Story 6 - Automated Login & Session Tests (Priority: P6)

An automated test suite covers the login and session-management flow: unit tests for cosine-similarity comparison and threshold logic, session validity rules (expired, revoked, unknown id), identifier normalization, and the non-revealing error mapping; integration tests exercising the real `POST /api/auth/face-login`, `GET /api/auth/me`, and `POST /api/auth/logout` endpoints wired to mock detector/embedder adapters and real PostgreSQL persistence (creating and revoking real `AuthSession` rows); and contract tests asserting the request/response shapes and status codes of the three auth endpoints, including the identical generic body for the two identity-sensitive failure causes. The domain portions run without GPU, network, or real models.

**Why this priority**: Tests are the safety net that lets later specs (dashboard analysis in 004/005, deletion in 006) build on real sessions without regressing login or protection (PRD §15, Constitution Quality Gates §4–§7). It is independently testable by running the suite under no-GPU/no-network constraints.

**Independent Test**: Run the login & session test suite in an environment with no GPU and no network; assert all unit, integration, and contract tests pass, that a deliberate contract-violating change to any auth endpoint response causes a contract test to fail, and that a deliberate change making the two identity-sensitive failures distinguishable causes a contract test to fail. Delivers a green, reproducible login & session test foundation.

**Acceptance Scenarios**:

1. **Given** the login & session test suite, **When** it is run with no GPU and no network, **Then** all unit tests for cosine similarity, threshold, session validity, normalization, and error mapping pass.
2. **Given** the test suite, **When** it is run against the real auth endpoints with mock adapters and real PostgreSQL, **Then** the integration tests for successful login, each rejection case, route protection, and logout pass.
3. **Given** the test suite, **When** it is run, **Then** the contract tests assert the request/response shapes and status codes of `POST /api/auth/face-login`, `GET /api/auth/me`, and `POST /api/auth/logout`.
4. **Given** the test suite, **When** it is run, **Then** a contract test asserts that the nonexistent-identifier response and the below-threshold response are identical (same status, same machine code, same message).
5. **Given** a contract-violating change to any auth endpoint response, **When** the contract tests are run, **Then** at least one test fails.

---

### Edge Cases

- What happens when the identifier is valid and exists but the capture contains no face or multiple faces? The backend returns an actionable capture error (`no_face` / `multiple_faces`) and creates no session. (This does imply the identifier exists, since a nonexistent identifier returns the generic `auth_failed` before detection; this residual leak is a documented demo limitation under Constitution Principle VIII, not a gap to close here.)
- What happens when the identifier exists but has no `FaceTemplate` (violating the spec 002 invariant)? The backend treats it as a login failure and returns the generic `401 auth_failed`, creating no session. This is a defensive guard against a data-invariant violation, not an expected state.
- What happens when the detector or embedder port raises an error during login? The backend returns a recoverable `internal_error` (actionable: "try again") and creates no session; no partial session is persisted.
- What happens when the database is unreachable at session-creation time after a successful verification? The backend returns a recoverable error and no `AuthSession` is committed; the person can retry.
- What happens when the signed cookie is tampered with or uses an unknown session id? The backend treats it as unauthenticated (`401 unauthenticated`) on every protected endpoint, including `GET /api/auth/me`; no internal error is raised.
- What happens when the session cookie is present but the `AuthSession` row was deleted out-of-band? The backend treats it as unauthenticated (unknown session id) — `401 unauthenticated`.
- What happens when a person logs in again while an earlier session is still valid? A new `AuthSession` is created and a new cookie set; the previous session remains valid until it expires or is revoked (no single-session constraint — demo-first; documented as a simplification, not a security policy).
- What happens when `POST /api/auth/logout` is called with no cookie or an already-invalid session? The backend returns a success response (idempotent) and performs no harmful action.
- What happens when the configured threshold is changed at runtime via environment variable? The new value takes effect on the next login request (loaded via the pydantic `Settings`); existing sessions are unaffected.
- What happens when the captured image is valid but the stored embedding has a different dimensionality than the captured embedding (e.g. model version mismatch)? The backend returns a recoverable `internal_error` and creates no session; the comparison port guards against dimension mismatch rather than producing a meaningless score. (With mock adapters this is exercised by fixture; real model-version mismatches are a Fase 5 concern.)
- What happens when the browser grants camera permission but the stream ends mid-capture? The UI transitions to a recoverable error state with an actionable message and a retry option.
- What happens when two concurrent login requests for the same identifier both succeed? Two independent `AuthSession` rows are created (one per cookie); this is permitted (no single-session constraint).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST verify a captured face against the `FaceTemplate` associated with the provided identifier using 1:1 verification (the person declares their identifier; the system checks the face matches that record), and MUST NOT perform 1:N recognition against all users (PRD §6.3, FR-007, Constitution Explicit Non-Goals).
- **FR-002**: The system MUST compute cosine similarity (Constitution OQ-6 default) between the captured embedding and the stored `FaceTemplate.embedding` via the comparison port, and MUST accept the verification only when similarity is `>=` the configured threshold (PRD FR-008). The threshold MUST be enforced server-side and MUST NOT be fixed solely in the frontend.
- **FR-003**: The verification threshold MUST be configurable via an environment variable loaded through the existing pydantic `Settings`, with a default of `0.5`; it MUST be overridable per environment without code changes (PRD §11, Constitution OQ-6).
- **FR-004**: The system MUST create an `AuthSession` (persisted in PostgreSQL) ONLY after a successful face verification, and MUST NOT create a session for any failure case (nonexistent identifier, below-threshold, no face, multiple faces, undecodable image, port error) (PRD FR-009, AC-004, AC-005).
- **FR-005**: On successful login, the system MUST return `200 OK` with a body containing exactly `userId` and `status: "authenticated"` (matching the PRD §8 face-login contract; `expiresAt` is NOT exposed to the frontend — expiry is learned reactively via `401 unauthenticated` on the next protected call), and MUST set a signed, http-only cookie referencing the new `AuthSession` (Constitution OQ-3).
- **FR-006**: A session is valid if and only if the cookie's session id maps to an `AuthSession` row with `revokedAt = null` and `expiresAt` in the future; otherwise it is invalid (expired, revoked, unknown, or absent).
- **FR-007**: The default session lifetime MUST be 30 minutes, configurable via an environment variable; an expired session MUST be treated as invalid and rejected by every protected endpoint (PRD §12 "expirar las sesiones").
- **FR-008**: For the two identity-sensitive failure causes — (a) the identifier has no registered `User`/`FaceTemplate` and (b) the captured face's similarity is below the threshold — the system MUST return the identical `401 Unauthorized` response with the same machine code (`auth_failed`) and the same human message, so the two causes are indistinguishable (PRD §6.3, §12, FR-015, AC-005).
- **FR-009**: The login failure response MUST use the error body shape `{"error": {"code": "...", "message": "..."}}` pinned in spec 002, with actionable human messages that reveal no internal details, embeddings, or stack traces (PRD FR-015, §12).
- **FR-010**: Capture-quality failures during login (no face, multiple faces, undecodable/unsupported/oversized image, below-quality-score) MUST return `400 Bad Request` with an actionable capture-specific error code (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`) in the pinned error body so the person can recapture, and MUST create no session. `401` is reserved exclusively for `auth_failed` and `unauthenticated` so the non-revealing contract (FR-008) stays crisp (PRD FR-004, FR-015).
- **FR-011**: The system MUST expose `GET /api/auth/me` returning `200` with `{"authenticated": true, "userId": "<id>"}` when a valid session exists, and `401` with the generic `unauthenticated` error body when the session is absent, expired, revoked, or unknown (PRD §8).
- **FR-012**: The system MUST expose `POST /api/auth/logout` which, given a valid session cookie, sets `revokedAt` on the `AuthSession` row, clears the cookie, and returns `200 OK` with body `{"status": "ok"}`; given no cookie or an already-invalid session, it MUST return the same `200 OK` `{"status": "ok"}` response idempotently and perform no harmful action (PRD §8, FR-016, AC-009).
- **FR-013**: After logout, the revoked session MUST be rejected by every protected endpoint and the person MUST NOT be able to re-access `/dashboard` or its endpoints without re-authenticating (PRD FR-016, AC-009).
- **FR-014**: Every backend endpoint marked protected (`GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`) MUST reject requests without a valid session with `401 unauthenticated`; `POST /api/auth/face-login` and `POST /api/onboarding` MUST remain reachable without a session (PRD FR-010, spec 001).
- **FR-015**: The frontend MUST replace the spec 001 in-memory session placeholder with real session state: a session context bootstrapped from `GET /api/auth/me` on app load and updated on login/logout, and a `ProtectedRoute` that admits `/dashboard` (and sub-routes) only when the session is valid and redirects to `/login` otherwise (PRD §6.1, FR-010, AC-006).
- **FR-016**: The login page MUST provide an identifier input, a camera preview, and a capture button, request camera access via standard browser media APIs, capture a single still on button press (no continuous streaming), send the identifier + image to `POST /api/auth/face-login`, and on success redirect to `/dashboard` (PRD §6.3, §10).
- **FR-017**: The login page MUST disable the capture button while a request is in flight, show actionable error messages with retry that does not require a full page reload, and keep all controls keyboard-accessible with descriptive names (PRD §10, FR-015).
- **FR-018**: The dashboard MUST display a keyboard-accessible "Cerrar sesión" button wired to `POST /api/auth/logout`; on success the frontend MUST clear session state and navigate to `/login` (PRD §6.4, FR-016).
- **FR-019**: The identifier submitted to login MUST be normalized (trim leading/trailing whitespace then lowercase) before the repository lookup, so the login lookup is case-insensitive and matches the canonical form stored by spec 002.
- **FR-020**: The login endpoint MUST reuse the image limits established in spec 002 (accepted formats, max size, long-edge resize) and reject oversized/unsupported/undecodable payloads with `invalid_image` before detection (PRD §11, Constitution OQ-8).
- **FR-021**: The domain orchestration of login and session management MUST depend only on the ports (detector, embedder, comparison, user repository, face-template repository, session manager) and MUST NOT import any concrete ML model, web framework, or infrastructure adapter directly (Constitution Principle VII).
- **FR-022**: An automated test suite MUST cover login & session unit (cosine similarity, threshold, session validity, normalization, non-revealing error mapping), integration (real auth endpoints + mock adapters + real PostgreSQL), and contract (request/response shapes and status codes, identical generic body for the two identity-sensitive failures) cases, with the domain portions running without GPU, network, or real models (PRD §15, Constitution Quality Gates §5/§7).
- **FR-023**: No image, embedding, or biometric response MUST appear in application logs; observability is limited to structured JSON logs (duration, type, status of the auth operation) consistent with specs 001/002 and Constitution Principle VIII (PRD §12, §13).

### Key Entities *(include if feature involves data)*

- **AuthSession**: The authenticated session created after successful face verification. Attributes: `id` (UUID v4), `userId` (UUID v4, FK to `User`), `createdAt`, `expiresAt` (`createdAt` + configurable lifetime, default 30 min), `revokedAt` (nullable; set on logout). A session is valid iff `revokedAt` is null and `expiresAt` is in the future. Persisted in PostgreSQL (Constitution Principle VI, OQ-3). Belongs to one `User`; a `User` may have many `AuthSession` rows (no single-session constraint).
- **User**: The registered person (from spec 002). Looked up by normalized identifier during login; no new attributes are added in this spec.
- **FaceTemplate**: The stored facial embedding (from spec 002). Loaded by identifier during login and compared against the captured embedding via cosine similarity. No new attributes are added in this spec.
- **Signed Session Cookie (infrastructure artifact)**: An http-only, signed cookie set on the login response carrying the `AuthSession.id`; presented by the client on subsequent requests and validated by the backend session middleware. Not a domain entity; referenced by the session-manager port (Constitution OQ-3).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who has completed onboarding can complete face login in under 30 seconds (excluding camera-permission time) in the local demo environment, verifiable by a timed walk-through of the happy path (PRD §16).
- **SC-002**: A valid login request returns `200 OK` with `userId` and `status: "authenticated"`, sets a signed http-only cookie, and leaves exactly one new valid `AuthSession` row in the database, verifiable by calling the endpoint and inspecting persistence (AC-004).
- **SC-003**: The nonexistent-identifier response and the below-threshold response are byte-identical (same status `401`, same machine code `auth_failed`, same human message), verifiable by submitting both cases and comparing the full responses (AC-005, PRD §6.3/§12).
- **SC-004**: No `AuthSession` is created for any failure case (nonexistent identifier, below threshold, no face, multiple faces, undecodable image, port error), verifiable by submitting each case and confirming zero new sessions in the database (AC-005).
- **SC-005**: 100% of protected backend endpoints reject requests without a valid session with `401 unauthenticated`, and accept requests with a valid session, verifiable by calling each protected endpoint with and without a valid session cookie (AC-006, FR-010).
- **SC-006**: An expired or revoked session is rejected by every protected endpoint identically to an absent session, verifiable by expiring/revoking a session and calling each protected endpoint (AC-009, FR-016).
- **SC-007**: After logout, the `AuthSession` row has `revokedAt` set, the cookie is cleared, and the person cannot re-access `/dashboard` or any protected endpoint without re-authenticating, verifiable by performing logout and attempting re-access (AC-009).
- **SC-008**: The frontend redirects any unauthenticated visit to `/dashboard` to `/login`, and admits it only when `GET /api/auth/me` reports an authenticated session, verifiable by loading `/dashboard` with and without a valid session (AC-006).
- **SC-009**: The login & session domain orchestration has zero imports of concrete ML models or infrastructure adapters (it depends only on ports), verifiable by static dependency inspection of the login/session domain code (Constitution Principle VII).
- **SC-010**: The full login & session test suite (unit + integration + contract) passes in an environment with no GPU and no network, verifiable by running the suite under those constraints (PRD §15).
- **SC-011**: A deliberate contract-violating change to any auth endpoint response, or a deliberate change making the two identity-sensitive failures distinguishable, causes at least one contract test to fail, verifiable by introducing and reverting such a change.
- **SC-012**: No real ML model (YOLO or real embedding model) is integrated in this spec — detection and embedding use the mock adapters from spec 001 — verifiable by confirming the spec's scope does not extend into Fase 5 (Constitution Principle VII).
- **SC-013**: No image, embedding, or biometric response appears in application logs, verifiable by inspecting the logs produced during login, session validation, and logout (PRD §12, §13).

## Assumptions

- This spec builds directly on specs 001 and 002: the runnable stack, the four views, the seven HTTP contract endpoints (here `POST /api/auth/face-login`, `GET /api/auth/me`, and `POST /api/auth/logout` are filled with real logic; the analysis and delete endpoints gain real session-gating but their business logic remains stubbed per spec 001), the domain entities (`User`, `FaceTemplate`, `AuthSession`), the hexagonal ports (detector, embedder, comparison, user repository, face-template repository, session manager, image storage), the mock adapters, the PostgreSQL schema/migrations (including the `AuthSession` table from spec 001), and the filesystem image-storage adapter are all assumed to exist and be reused, not re-created.
- The technology stack is fixed by the Constitution (Principle III / Technology Stack table): backend in Python with FastAPI, frontend in React with Vite, PostgreSQL for persistence, Docker Compose for orchestration. These are project-level decisions, not ad hoc implementation choices, and are assumed settled for this spec.
- The session mechanism is server-side session in PostgreSQL (`AuthSession`) keyed by a signed, http-only cookie (Constitution OQ-3 default). No JWT is used (Principle VIII — no security guarantee). This is the established default, not a new design choice.
- The distance metric is cosine similarity (Constitution OQ-6 default) with a default acceptance threshold of `0.5`, configurable via an environment variable loaded through the existing pydantic `Settings`. The metric lives behind the comparison port so Fase 5 can swap it without touching the domain.
- The default session lifetime is 30 minutes, configurable via an environment variable. Expired sessions are invalid; no automatic refresh/renewal is implemented in this spec (re-login is the refresh path — demo-first).
- The error body shape is the spec-002-pinned `{"error": {"code": "...", "message": "..."}}` flat shape. Machine codes are stable strings (`auth_failed`, `unauthenticated`, `no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, `internal_error`). Human messages are actionable per FR-015 and reveal no internal details. Status-code mapping is pinned: `401 Unauthorized` is used exclusively for `auth_failed` (identity-sensitive login failure) and `unauthenticated` (session-gating); `400 Bad Request` is used for the actionable capture-quality codes (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`); recoverable `internal_error` uses `500`. The successful logout response is `200 OK` with `{"status": "ok"}` (idempotent).
- The non-revealing requirement (PRD §6.3/§12) is satisfied for the two identity-sensitive causes (nonexistent identifier vs. below-threshold non-match) by returning identical `401 auth_failed` responses. Capture-quality failures (no face, multiple faces, undecodable) return distinct actionable codes; the residual identifier-existence leak this implies (an existing identifier with a bad capture yields a capture error while a nonexistent identifier yields `auth_failed`) is a documented demo limitation under Constitution Principle VIII (no security guarantee), not a gap to close in this spec.
- The login endpoint evaluates failure conditions in the order: image decode/limit validation → detection (exactly one face) → identifier/template lookup → embedding → cosine comparison → session creation. This ordering means capture-quality errors surface only for existing identifiers; the trade-off is documented above and accepted as demo-first.
- The identifier is normalized (trim leading/trailing whitespace, then lowercase) before the login lookup, matching spec 002's canonical storage form; the lookup is case-insensitive.
- The image limits (accepted formats, max size ≤ 2 MB, long-edge resize ≤ 640px) and the pydantic `Settings` configuration mechanism are reused from spec 002 (Constitution OQ-8).
- `GET /api/auth/me` returns `200` with `{"authenticated": true, "userId": "<id>"}` on a valid session and `401` with the generic `unauthenticated` body otherwise; the frontend bootstraps session state from this on app load and uses `401` to gate `ProtectedRoute`. This is a reasonable demo default (a status endpoint that signals auth state clearly).
- `POST /api/auth/logout` is idempotent: it returns success whether or not a valid session is presented, and performs no harmful action when called with no cookie or an already-invalid session.
- A person may hold multiple concurrent valid sessions (e.g. logging in again does not revoke the prior session). This is a demo simplification (no single-session constraint), not a security policy, and is documented in the edge cases.
- The detector and embedder ports are wired to the mock adapters from spec 001 for this entire spec. Real YOLO and real embedding models are explicitly deferred to Fase 5 and are out of scope here (Constitution Principle VII; SC-012).
- The comparison port guards against embedding-dimension mismatch (returns a recoverable `internal_error` rather than a meaningless score); with mock adapters this is exercised by fixture, and real model-version mismatches are a Fase 5 concern.
- Dashboard analysis (mood/age) logic (spec 004/005), age estimation (spec 005), face-data deletion (spec 006), rate limiting, liveness/anti-spoofing, password flows, MFA, and account recovery are explicitly out of scope for this spec. The analysis and delete endpoints in this spec are session-gated but their business logic remains the spec 001 stubs.
- Observability in this spec is limited to structured JSON logs (duration, type, status of the auth operation) with no images, embeddings, or biometric responses logged, consistent with specs 001/002 and Constitution Principle VIII (no traceability guarantee).
- The frontend camera is accessed via standard browser `getUserMedia`; tests mock `MediaDevices` with controlled test frames and mock the fetch layer for auth responses, as anticipated by PRD §15. A secure context (`localhost` or HTTPS) is required for camera access and is assumed available in the local demo.
- The signed cookie's signing key is provided via environment variable with a demo default; rotation and secure-key management are out of scope (Principle VIII — no security guarantee).
