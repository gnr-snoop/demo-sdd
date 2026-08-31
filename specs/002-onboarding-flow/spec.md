# Feature Specification: Onboarding Flow (Fase 2)

**Feature Branch**: `002-onboarding-flow`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Onboarding flow (Fase 2 of the PRD). Implements the real onboarding business logic on top of the skeleton/contracts/ports/mocks established in spec 001-skeleton-contracts-mocks. Covers PRD §6.2 (Flujo de onboarding + Estados de onboarding), FR-001 (Crear perfil facial), FR-002 (Validar identificador — reject empty/invalid-format/duplicate), FR-003 (Solicitar consentimiento — explicit acceptance required before capture/processing), FR-004 (Validar captura facial — reject no-face/multiple-faces/insufficient-quality/undecodable), FR-005 (Detectar rostro via detector port — mock adapter for now), FR-006 (Generar plantilla facial — embedding via embedder port, associated to profile). Acceptance criteria AC-001 (Onboarding exitoso), AC-002 (Onboarding rechazado sin rostro), AC-003 (Onboarding rechazado con múltiples rostros). Builds on spec 001; real ML models deferred to Fase 5."

## Clarifications

### Session 2026-08-31

- Q: What identifier format(s) does the onboarding endpoint accept — email only, username only, or either? -> A: Accept a single `identifier` field that is valid if it matches a well-formed email **or** a username pattern (3–32 chars, alphanumeric plus `.` `_` `-`). This preserves the PRD §6.2 "email o username" wording without forcing a choice, and the duplicate check is case-insensitive on the normalized value.
- Q: Where does image resizing to ≤ 640px long edge happen — frontend or backend? -> A: Backend resizes before storage (PRD §11 mandates server-side re-validation of all frontend data; the stored artifact is the authoritative one). The frontend may additionally downscale for transport, but the backend limit is binding.
- Q: What does "insufficient quality" mean for the mock detector in this spec? -> A: The detector port returns a score and a face count; a capture is rejected as insufficient quality when the score is below a configurable threshold. With the mock adapter the score is deterministic, so the threshold is exercised by fixture choice in tests; no real quality model is introduced (deferred to Fase 5).
- Q: Should the captured image be retained after onboarding, or discarded once the embedding is generated? -> A: Retained on the filesystem at `usuarios/<user-id>/pictures.jpg` per Constitution Principle V (the path convention is referenced by the later deletion endpoint). This is an explicit demo decision, not a production retention policy.
- Q: Where are the configurable thresholds (max image size, long-edge limit, quality threshold) defined — env vars, a config file, or hardcoded constants? -> A: Environment variables loaded via a pydantic `Settings` class, with defaults matching OQ-8 (2 MB max size, 640px long edge) and a quality-threshold default of `0.5`; overridable per environment.
- Q: What value does `FaceTemplate.modelVersion` take for the mock embedder in this spec — a literal string, `null`, or omitted? -> A: The literal string `"mock-embedder-v1"`, so `FaceTemplate.modelVersion` is always populated and downstream login (spec 003) can detect mock-origin templates.
- Q: How is the identifier normalized for the case-insensitive duplicate check — lowercase only, or also trim + strip whitespace? -> A: Trim leading/trailing whitespace, then lowercase; the normalized form is what is checked for duplicates and stored canonically (the original casing is not preserved).
- Q: How is the concurrent-duplicate race (two concurrent requests with the same new identifier) prevented — DB unique constraint with catch, explicit lock, or optimistic check-then-insert? -> A: Rely on a DB unique constraint on the normalized-identifier column and catch the integrity violation as the duplicate signal; no explicit table lock (demo-first; the unique index is the simplest correct guarantee).

> **RESOLVED at orchestrator gate (2026-08-31)**: Q: What status value does a freshly onboarded `User` receive, and is a `FaceTemplate` created in the same transaction? **Decision: `User.status = "enrolled"` and a `FaceTemplate` (embedding + modelVersion) is created atomically with the User in a single unit of work.** If any step after identifier/consent validation fails (no face, multiple faces, undecodable, embedding error), no User and no FaceTemplate are persisted (all-or-nothing). This is pinned and flows into plan, integration tests, and AC-002/AC-003 assertions.

> **RESOLVED at orchestrator gate (2026-08-31)**: Q: What is the exact body shape for rejection/error responses? **Decision: a flat `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}` shape** (Content-Type `application/json`). Machine codes are stable strings (e.g. `identifier_invalid`, `identifier_taken`, `consent_required`, `invalid_image`, `no_face`, `multiple_faces`, `insufficient_quality`, `internal_error`). Human messages are actionable per FR-015 and do not leak internal details. This is pinned and flows into plan, contracts, and contract-test assertions.

## User Scenarios & Testing *(mandatory)*

<!--
  This spec implements real onboarding business logic on the skeleton from spec 001.
  Stories are ordered so each independently delivers a demonstrable, testable slice
  of the onboarding flow and maps to PRD AC-001..AC-003 and FR-001..FR-006/FR-015.
  All ML touchpoints go through the ports established in spec 001; mock adapters
  are used in this spec (real models arrive in Fase 5).
-->

### User Story 1 - Successful Onboarding (Happy Path) (Priority: P1)

A person completes the full onboarding journey: they enter a valid identifier, explicitly accept biometric consent, grant camera permission, see the camera preview, and press capture. The frontend sends a single captured image to the onboarding endpoint. The backend validates the identifier and consent, decodes the image, runs the detector port and finds exactly one face, runs the embedder port to generate a facial embedding, creates a User profile (status `enrolled`) and an associated FaceTemplate in a single atomic operation, stores the captured image on the filesystem under the per-user path, and returns a success response with the new user identifier and status. The UI shows the success state and offers a link to login.

**Why this priority**: This is the core demo narrative — the happy path that every subsequent spec (login, dashboard) depends on. It delivers AC-001 (Onboarding exitoso) and exercises FR-001, FR-003, FR-005, FR-006 end-to-end. Without a working onboarding there is no registered profile to verify against.

**Independent Test**: Call the onboarding endpoint with a valid identifier, `consentAccepted = true`, and a fixture image containing exactly one face (mock detector returns count = 1, score above threshold); assert a `201` response with `userId`, `identifier`, and `status: "enrolled"`, and confirm a User + FaceTemplate exist in the database and the image is readable at the per-user filesystem path. Delivers a complete, demonstrable registration.

**Acceptance Scenarios**:

1. **Given** a person on the onboarding page with a valid identifier and consent accepted, **When** they capture an image containing exactly one face and submit, **Then** the backend returns `201 Created` with a body containing `userId`, `identifier`, and `status: "enrolled"`.
2. **Given** a successful onboarding response, **When** the database is inspected, **Then** exactly one `User` (status `enrolled`) and one associated `FaceTemplate` (with an embedding and a model version) exist, created atomically.
3. **Given** a successful onboarding response, **When** the filesystem is inspected, **Then** the captured image is stored at `usuarios/<user-id>/pictures.jpg` and is readable from both the host and the backend container.
4. **Given** a successful onboarding, **When** the UI receives the success response, **Then** it transitions to the success state and presents a link to the login page.

---

### User Story 2 - Onboarding Rejected for Invalid Capture (Priority: P2)

When the captured image does not contain exactly one usable face, the backend rejects the onboarding, creates no profile and no face template, and returns an actionable error that tells the person how to recover. This covers the two rejection cases in the PRD: no face detected (AC-002) and more than one face detected (AC-003), plus the undecodable-image and insufficient-quality cases from FR-004.

**Why this priority**: Rejecting bad captures without leaving partial state is what makes onboarding trustworthy and recoverable. It delivers AC-002 and AC-003 and exercises the detector-port validation path. It is independently testable by submitting each invalid capture type and asserting no persistence occurred.

**Independent Test**: Submit an image with zero faces, an image with two faces, an undecodable payload, and a below-threshold-quality image (each via the mock detector configured for that case); assert each returns a client-error status with an actionable message and that no `User` or `FaceTemplate` was persisted. Delivers safe rejection behavior.

**Acceptance Scenarios**:

1. **Given** a valid identifier and consent, **When** the capture contains no face, **Then** the backend rejects the request with a client-error status, returns an actionable message indicating the person should repeat the capture, and creates no User and no FaceTemplate (AC-002).
2. **Given** a valid identifier and consent, **When** the capture contains more than one face, **Then** the backend rejects the request with a client-error status, returns an actionable message asking for a single person in frame, and creates no User and no FaceTemplate (AC-003).
3. **Given** a valid identifier and consent, **When** the capture cannot be decoded or has an unsupported format, **Then** the backend rejects the request with a client-error status and an actionable message, and creates no User and no FaceTemplate.
4. **Given** a valid identifier and consent, **When** the capture's detected-face score is below the configured quality threshold, **Then** the backend rejects the request with a client-error status and an actionable message, and creates no User and no FaceTemplate.

---

### User Story 3 - Identifier & Consent Validation (Priority: P3)

Before any image processing, the backend validates the identifier and the consent flag. An empty, malformed, or already-registered identifier is rejected, and a request where consent was not explicitly accepted is rejected — in all cases before the detector or embedder is invoked and without persisting anything.

**Why this priority**: Input validation is the gate that prevents wasted processing and duplicate profiles. It delivers FR-002 (Validar identificador) and FR-003 (Solicitar consentimiento). It is independently testable by submitting each invalid input combination and asserting early rejection.

**Independent Test**: Submit requests with an empty identifier, a malformed identifier, an already-registered identifier, and a valid identifier with `consentAccepted = false`; assert each returns a client-error status with an actionable message, that no image processing occurred, and that no User or FaceTemplate was created. Delivers correct input gating.

**Acceptance Scenarios**:

1. **Given** an onboarding request, **When** the identifier is empty or whitespace, **Then** the backend rejects it with a client-error status and an actionable message before any image processing.
2. **Given** an onboarding request, **When** the identifier does not match the accepted email-or-username format, **Then** the backend rejects it with a client-error status and an actionable message before any image processing.
3. **Given** an identifier that is already registered, **When** a new onboarding request uses that same identifier (case-insensitive), **Then** the backend rejects it with a client-error status indicating the identifier is taken, without revealing stored biometric data.
4. **Given** an onboarding request with a well-formed identifier, **When** `consentAccepted` is not `true`, **Then** the backend rejects it with a client-error status and an actionable message before any image processing.

---

### User Story 4 - Frontend Onboarding Page with Camera & State Machine (Priority: P4)

The onboarding page provides an identifier input, a consent checkbox, a camera preview, and a capture button, and drives the experience through the PRD §6.2 onboarding states: inicial, solicitando permiso, cámara no disponible, listo para capturar, procesando, éxito, and error recuperable. The page requests camera access via standard browser media APIs, shows a live preview, captures a single still image on button press, disables the capture button while processing, shows actionable error messages, and keeps all buttons keyboard-accessible with descriptive names.

**Why this priority**: The UI is how the demo audience experiences onboarding. It delivers the PRD §6.2 state machine and FR-015 (Mostrar errores accionables) and is what makes the backend stories demonstrable to a human. It is independently testable with a mocked camera device.

**Independent Test**: Render the onboarding page with a mocked media-devices source that yields a test frame; walk the state machine from inicial through permission grant, ready-to-capture, processing, and success, and separately through a recoverable error; assert each state renders the correct controls and messages and that the capture button is keyboard-reachable. Delivers a navigable, accessible onboarding UI.

**Acceptance Scenarios**:

1. **Given** the onboarding page in the inicial state, **When** the person enters an identifier and checks consent, **Then** the camera-permission request control is enabled.
2. **Given** the person requests the camera, **When** the browser is requesting permission, **Then** the page is in the solicitando permiso state.
3. **Given** a camera permission denial or missing device, **When** the page handles the failure, **Then** it transitions to the cámara no disponible state with an actionable message and a retry option.
4. **Given** camera permission is granted, **When** the preview stream is active, **Then** the page is in the listo para capturar state showing the live preview and an enabled, keyboard-accessible capture button.
5. **Given** the person presses capture, **When** the request is in flight, **Then** the page is in the procesando state and the capture button is disabled.
6. **Given** a successful response, **When** the page receives it, **Then** it transitions to the éxito state with a link to login.
7. **Given** a recoverable error response, **When** the page receives it, **Then** it transitions to the error recuperable state with an actionable message and a retry option that does not require a full page reload.

---

### User Story 5 - Image Constraints & Decoding (Priority: P5)

The backend enforces image limits independently of the frontend: only accepted image formats are allowed, the payload must not exceed the configured maximum size, and the image is normalized (resized so the long edge does not exceed the configured maximum) before detection and storage. Oversized, wrong-format, or undecodable payloads are rejected with an actionable message before any face processing.

**Why this priority**: Enforcing limits server-side is mandated by PRD §11 and keeps the demo from crashing on pathological inputs. It delivers the FR-004 decoding/format branch and Constitution OQ-8. It is independently testable by submitting each out-of-limit payload.

**Independent Test**: Submit a non-image payload, an oversized payload, and a supported image exceeding the long-edge limit; assert each is rejected (or normalized then accepted, for the resizable case) with the correct status and that no face processing ran on the rejected ones. Delivers robust image handling.

**Acceptance Scenarios**:

1. **Given** an onboarding request, **When** the image payload is not a supported image format, **Then** the backend rejects it with a client-error status and an actionable message before detection.
2. **Given** an onboarding request, **When** the image payload exceeds the configured maximum size, **Then** the backend rejects it with a client-error status and an actionable message before detection.
3. **Given** an onboarding request with a valid image whose long edge exceeds the configured maximum, **When** the backend processes it, **Then** the image is resized so the long edge is within the limit before detection and storage.

---

### User Story 6 - Automated Onboarding Tests (Priority: P6)

An automated test suite covers the onboarding flow: unit tests for identifier validation, consent validation, face-count rules, and image-limit enforcement; integration tests exercising the real onboarding endpoint wired to mock detector/embedder adapters and the real persistence (database + filesystem); and contract tests asserting the onboarding endpoint's request/response shapes and status codes. The domain portions run without GPU, network, or real models.

**Why this priority**: Tests are the safety net that lets later specs (login, dashboard) build on onboarding without regressing it (PRD §15, Constitution Quality Gates §4–§7). It is independently testable by running the suite under no-GPU/no-network constraints.

**Independent Test**: Run the onboarding test suite in an environment with no GPU and no network; assert all unit, integration, and contract tests pass and that a deliberate contract-violating change causes a contract test to fail. Delivers a green, reproducible onboarding test foundation.

**Acceptance Scenarios**:

1. **Given** the onboarding test suite, **When** it is run with no GPU and no network, **Then** all unit tests for validation rules and face-count logic pass.
2. **Given** the onboarding test suite, **When** it is run against the real endpoint with mock adapters and real persistence, **Then** the integration tests for the happy path and each rejection case pass.
3. **Given** the onboarding test suite, **When** it is run, **Then** the contract tests assert the onboarding endpoint's request and response shapes and status codes.
4. **Given** a contract-violating change to the onboarding response, **When** the contract tests are run, **Then** at least one test fails.

---

### Edge Cases

- What happens when the identifier is valid but the image field is missing entirely from the request? The backend rejects with a client-error status and an actionable message before any processing.
- What happens when two concurrent onboarding requests use the same new identifier? Exactly one succeeds and the other is rejected as a duplicate; no two profiles are created for the same identifier. The race is prevented by a DB unique constraint on the normalized-identifier column; the integrity-violation is caught and surfaced as the duplicate signal (no explicit table lock — demo-first).
- What happens when the detector port returns exactly one face but the embedder port fails? The backend rejects the onboarding with a recoverable error and creates no User and no FaceTemplate (all-or-nothing).
- What happens when the database is unreachable at persistence time after a successful detection and embedding? The backend returns a recoverable error and no partial User/FaceTemplate is committed.
- What happens when the filesystem cannot write the image (permissions, read-only mount, disk full)? The backend returns a clear storage error; no User or FaceTemplate is persisted (the database write has not yet been attempted — persistence order is filesystem-write-first, then DB commit).
- What happens when the browser grants camera permission but the stream ends mid-capture (device disconnected)? The UI transitions to a recoverable error state with an actionable message and a retry option.
- What happens when `consentAccepted` is present but not a boolean (e.g., the string `"true"`)? The backend rejects it as invalid consent before any processing.
- What happens when the captured image is valid but rotated/mirrored? It is accepted and processed as-is; orientation normalization is not required for this spec (demo-first; deferred if needed in Fase 5).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a person to create a facial profile from a valid identifier, explicit consent, and a single captured image containing exactly one usable face (PRD FR-001, AC-001).
- **FR-002**: The system MUST reject identifiers that are empty, whitespace-only, malformed (neither a valid email nor a valid username pattern), or already registered (case-insensitive duplicate check on the normalized value — trim leading/trailing whitespace then lowercase; the normalized form is stored canonically and the original casing is not preserved) before any image processing (PRD FR-002).
- **FR-003**: The system MUST require `consentAccepted` to be exactly `true` before capturing or processing any facial image, and MUST reject requests where consent is missing, false, or non-boolean before any image processing (PRD FR-003).
- **FR-004**: The backend MUST reject a capture that contains no face, more than one face, a face below the configured quality threshold, or a payload that cannot be decoded or is an unsupported format, and MUST create no User and no FaceTemplate in any of these cases (PRD FR-004, AC-002, AC-003).
- **FR-005**: The system MUST locate faces in the capture via the detector port declared in spec 001, and MUST treat the result (face count and score) as the authority for the exactly-one-face rule; the concrete adapter in this spec is the mock from spec 001 (PRD FR-005, Constitution Principle VII).
- **FR-006**: The system MUST generate a facial embedding via the embedder port declared in spec 001, associate it with the created profile as a FaceTemplate carrying a model version (`"mock-embedder-v1"` for the mock adapter in this spec, so the field is always populated and downstream login can detect mock-origin templates), and persist it atomically with the User (PRD FR-006, Constitution Principle VI).
- **FR-007**: On a successful onboarding, the system MUST return `201 Created` with a body containing `userId`, `identifier`, and `status: "enrolled"` matching the PRD §8 onboarding contract.
- **FR-008**: The User and FaceTemplate MUST be created in a single atomic unit of work; if any step after identifier/consent validation fails, no User and no FaceTemplate MAY be persisted (all-or-nothing).
- **FR-009**: The captured image MUST be stored on the local filesystem at `usuarios/<user-id>/pictures.jpg`, with the `usuarios/` tree bind-mounted so the path is identical inside and outside the backend container (Constitution Principle V).
- **FR-010**: The backend MUST enforce image limits independently of the frontend: reject unsupported formats and payloads exceeding the configured maximum size, and resize the image so the long edge does not exceed the configured maximum before detection and storage (PRD §11, Constitution OQ-8).
- **FR-011**: The onboarding page MUST drive the experience through the PRD §6.2 states — inicial, solicitando permiso, cámara no disponible, listo para capturar, procesando, éxito, error recuperable — with the correct controls and messages per state.
- **FR-012**: The onboarding page MUST request camera access via standard browser media APIs, show a live preview when permission is granted, and capture a single still image on button press without streaming video continuously (PRD §10).
- **FR-013**: The capture button MUST be disabled while a request is in flight, and the frontend MUST NOT submit multiple concurrent onboarding requests for the same attempt (PRD §10, FR-014 spirit).
- **FR-014**: All onboarding error messages MUST be actionable — indicating a possible next step such as repeating the capture, revising the identifier, or re-granting camera permission — without exposing internal system details (PRD FR-015).
- **FR-015**: All onboarding controls MUST be keyboard-accessible and have descriptive names (PRD §10).
- **FR-016**: The onboarding failure response MUST NOT reveal stored biometric data or embeddings; rejection messages distinguish only the recoverable cause (identifier taken, invalid format, consent missing, no face, multiple faces, undecodable, insufficient quality) (PRD §12).
- **FR-017**: The domain orchestration of onboarding MUST depend only on the ports (detector, embedder, user repository, face-template repository, image storage) and MUST NOT import any concrete ML model or infrastructure adapter directly (Constitution Principle VII).
- **FR-018**: An automated test suite MUST cover onboarding unit (validation, face-count rules, image limits), integration (endpoint with mock adapters + real persistence), and contract (request/response shapes and status codes) cases, with the domain portions running without GPU, network, or real models (PRD §15, Constitution Quality Gates §5/§7).

### Key Entities *(include if feature involves data)*

- **User**: The registered person. Created by onboarding with `status = "enrolled"`. Attributes: `id` (UUID v4), `identifier` (unique, case-insensitive), `createdAt`, `updatedAt`, `status ∈ {"enrolled", "active", "disabled"}` (PRD §7, spec 001). One user has at most one FaceTemplate after onboarding.
- **FaceTemplate**: The comparable facial representation generated during onboarding. Attributes: `id` (UUID v4), `userId`, `embedding` (or reference to secure storage), `modelVersion` (`"mock-embedder-v1"` for the mock embedder in this spec), `createdAt`, `updatedAt` (PRD §7). Belongs to one User; created atomically with the User.
- **Captured Image (filesystem artifact)**: The onboarding still image stored at `usuarios/<user-id>/pictures.jpg`, normalized to the configured long-edge limit. Not a domain entity; referenced by the image-storage port (Constitution Principle V).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can complete onboarding (identifier, consent, capture, confirmation) in under 2 minutes in the local demo environment, verifiable by a timed walk-through of the happy path (PRD §16).
- **SC-002**: A valid onboarding request returns `201 Created` with `userId`, `identifier`, and `status: "enrolled"`, and leaves exactly one User and one FaceTemplate in the database and one image at `usuarios/<user-id>/pictures.jpg`, verifiable by calling the endpoint and inspecting persistence.
- **SC-003**: Every invalid-capture case (no face, multiple faces, undecodable, insufficient quality) returns a client-error status with an actionable message and leaves zero Users and zero FaceTemplates in the database, verifiable by submitting each case and checking persistence (AC-002, AC-003).
- **SC-004**: Every invalid-input case (empty/malformed/duplicate identifier, missing/false/non-boolean consent) is rejected before any image processing and leaves no persistence, verifiable by submitting each case and confirming no detector/embedder invocation and no database writes.
- **SC-005**: The onboarding page transitions through all seven PRD §6.2 states with the correct controls and messages per state, verifiable by driving the page with a mocked camera through each transition.
- **SC-006**: All onboarding error messages state a possible next action and contain no internal system details, embeddings, or stack traces, verifiable by inspecting the messages produced for each rejection case.
- **SC-007**: The onboarding domain orchestration has zero imports of concrete ML models or infrastructure adapters (it depends only on ports), verifiable by static dependency inspection of the onboarding domain code (Constitution Principle VII).
- **SC-008**: The full onboarding test suite (unit + integration + contract) passes in an environment with no GPU and no network, verifiable by running the suite under those constraints.
- **SC-009**: A deliberate contract-violating change to the onboarding endpoint response causes at least one contract test to fail, verifiable by introducing and reverting such a change.
- **SC-010**: No real ML model (YOLO or real embedding model) is integrated in this spec — detection and embedding use the mock adapters from spec 001 — verifiable by confirming the spec's scope does not extend into Fase 5.

## Assumptions

- This spec builds directly on spec 001-skeleton-contracts-mocks: the runnable stack, the four views, the seven HTTP contract endpoints (here `POST /api/onboarding` is filled with real logic), the domain entities, the hexagonal ports, the mock adapters, the PostgreSQL schema/migrations, and the filesystem image-storage adapter are all assumed to exist and be reused, not re-created.
- The technology stack is fixed by the Constitution (Principle III / Technology Stack table): backend in Python with FastAPI, frontend in React with Vite, PostgreSQL for persistence, Docker Compose for orchestration. These are project-level decisions, not ad hoc implementation choices, and are assumed settled for this spec.
- The `POST /api/onboarding` request is `multipart/form-data` with fields `identifier` (string), `consentAccepted` (boolean), and `image` (a single facial still), and the success response is the PRD §8 shape — this is the established contract from spec 001, not a new design.
- The identifier is valid if it matches a well-formed email **or** a username pattern (3–32 chars, alphanumeric plus `.` `_` `-`); the duplicate check is case-insensitive on the normalized value. This preserves the PRD §6.2 "email o username" wording without forcing a single format.
- Consent must be exactly boolean `true`; non-boolean truthy values (e.g., the string `"true"`) are rejected. Consent is required before any capture/processing (PRD FR-003).
- Image constraints default to JPEG, ≤ 2 MB, resized to ≤ 640px on the long edge before storage (Constitution OQ-8 default). The backend resize is authoritative; any frontend downscaling is for transport only.
- Image resizing/normalization happens on the backend before detection and storage, because PRD §11 mandates server-side re-validation of all frontend data and the stored artifact must be the authoritative one.
- The configurable thresholds (max image size, long-edge limit, quality threshold) are defined as environment variables loaded via a pydantic `Settings` class, with defaults matching OQ-8 (2 MB max size, 640px long edge) and a quality-threshold default of `0.5`; they are overridable per environment.
- The identifier is normalized (trim leading/trailing whitespace, then lowercase) before the duplicate check and canonical storage; the original casing is not preserved.
- `FaceTemplate.modelVersion` is the literal string `"mock-embedder-v1"` for the mock embedder used in this spec, so the field is always populated and downstream login (spec 003) can detect mock-origin templates.
- The concurrent-duplicate race is prevented by a DB unique constraint on the normalized-identifier column; the integrity violation is caught and surfaced as the duplicate signal (no explicit table lock — demo-first).
- "Insufficient quality" is determined by the detector port's score against a configurable threshold; with the mock adapter the score is deterministic, so the threshold is exercised by fixture choice in tests. No real quality model is introduced in this spec (deferred to Fase 5).
- The captured image is retained at `usuarios/<user-id>/pictures.jpg` after onboarding per Constitution Principle V; this is an explicit demo decision (the path is referenced by the later deletion endpoint), not a production retention policy.
- The detector and embedder ports are wired to the mock adapters from spec 001 for this entire spec. Real YOLO and real embedding models are explicitly deferred to Fase 5 and are out of scope here (Constitution Principle VII; SC-010).
- Login/verification (spec 003), mood analysis (spec 004), age estimation (spec 005), face-data deletion (spec 006), rate limiting, and liveness/anti-spoofing are explicitly out of scope for this spec.
- The all-or-nothing persistence semantics (User + FaceTemplate atomic; rollback on any post-validation failure, including embedder failure, DB outage, or filesystem write failure) is assumed to be implemented as a single unit of work at the domain/adapter boundary.
- Observability in this spec is limited to structured JSON logs (duration, type, status of the onboarding operation) with no images or embeddings logged, consistent with spec 001 and Constitution Principle VIII (no traceability guarantee).
- The frontend camera is accessed via standard browser `getUserMedia`; tests mock `MediaDevices` with controlled test frames, as anticipated by PRD §15. A secure context (`localhost` or HTTPS) is required for camera access and is assumed available in the local demo.
