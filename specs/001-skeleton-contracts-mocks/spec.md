# Feature Specification: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Feature Branch**: `001-skeleton-contracts-mocks`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Project skeleton, navigation, domain models, HTTP contracts, and mock adapters. Fase 1 of the PRD: establishes the runnable skeleton of the app — four views with navigation and route-protection placeholder; backend app with the seven HTTP contract endpoints from PRD §8 defined as stubs/mocks; domain models from PRD §7 as pure domain entities; hexagonal ports-and-adapters layout with deterministic mock adapters; Docker Compose stack; PostgreSQL schema/migrations; local filesystem image storage under `usuarios/<user-id>/pictures.jpg`; and contract tests + domain unit tests that run without GPU/network. This spec does NOT implement real business logic — only skeleton, contracts, ports, mocks, and the runnable stack."

## Clarifications

### Session 2026-08-31

- Q: What are the allowed enum values for `User.status` and `AnalysisRequest.status`? -> A: `User.status ∈ {"enrolled", "active", "disabled"}`; `AnalysisRequest.status ∈ {"pending", "completed", "failed"}`. Aligns with the already-pinned `"enrolled"` response value and a standard request lifecycle.
- Q: What observability should the Fase 1 skeleton include? -> A: Structured JSON logs plus the health/readiness endpoint only. No metrics, distributed tracing, or audit logging in this spec (deferred; consistent with Constitution Principle VIII — no traceability guarantee).
- Q: How should the frontend represent the "session placeholder" used by the route-protection guard? -> A: An in-memory React context flag (simplest placeholder). Real session/cookie wiring is deferred to spec 003 (Fase 3).
- Q: How should mock adapters achieve determinism — hardcoded constant outputs or a fixed random seed? -> A: Hardcoded constant outputs (no RNG/seed). Maximally deterministic and simplest to assert across repeated runs (supports SC-005).

> **RESOLVED at orchestrator gate (2026-08-31)**: Q: What type should the primary key / `userId` take? **Decision: UUID v4 strings** (opaque, no enumeration/sequential-id risk, standard for face-template identifiers). All `id` / `userId` fields across `User`, `FaceTemplate`, `AuthSession`, `AnalysisRequest` are UUID v4 strings (stored as PostgreSQL `UUID` columns). The `DELETE /api/users/{userId}/face-data` path parameter is a UUID string. Mock adapters return fixed UUID constants in tests. This decision is pinned and flows into plan, migrations, and contract-test assertions.

## User Scenarios & Testing *(mandatory)*

<!--
  This is a scaffolding/spec-0 spec. Its primary "users" are the development team
  and the demo audience: the value delivered is a runnable, navigable, contract-
  validated skeleton that subsequent specs (002–006) fill with real logic.
  Stories are ordered so each independently delivers a demonstrable slice.
-->

### User Story 1 - Runnable Demo Stack (Priority: P1)

A developer or demo audience member can bring up the entire application — backend, frontend, and database — with a single command, and all three services start and become reachable on their documented ports. No host-native installation of runtimes or models is required; the stack is fully containerized.

**Why this priority**: Without a runnable stack nothing else in the demo can be shown or tested. This is the foundation that makes every subsequent story and spec demonstrable (Constitution Principle IV — Containerized Execution via Docker Compose).

**Independent Test**: Run the compose up command from a clean checkout; verify the backend health endpoint, the frontend dev server, and the database each respond. Delivers a running system with no manual setup.

**Acceptance Scenarios**:

1. **Given** a clean repository checkout on a machine with only a container runtime installed, **When** the single compose-up command is run, **Then** the backend, frontend, and PostgreSQL services all reach a healthy/ready state and remain running.
2. **Given** the stack is running, **When** the backend's health/readiness endpoint is requested, **Then** it reports healthy including database connectivity.
3. **Given** the stack is running, **When** the frontend is opened in a browser, **Then** the welcome page renders without server errors.
4. **Given** the stack is stopped and restarted, **When** the database service is ready, **Then** pending schema migrations apply automatically (or via a single documented migrate step) without manual SQL.

---

### User Story 2 - Navigable App Skeleton with Four Views (Priority: P2)

A visitor can navigate between the four application views — welcome (`/`), onboarding (`/onboarding`), login (`/login`), and dashboard (`/dashboard`) — using in-app navigation. The dashboard route has a placeholder route-protection guard that redirects unauthenticated visitors to `/login`. The views are presentational placeholders only; they do not implement real camera capture or business logic.

**Why this priority**: The navigation structure and route map are the skeleton every later spec hangs on. Route protection as a placeholder now prevents rework in Fase 3 (PRD §6.1, FR-010).

**Independent Test**: Start the frontend, click through each navigation target, and attempt to visit `/dashboard` directly; confirm the redirect and that all four routes render. Delivers a navigable SPA skeleton.

**Acceptance Scenarios**:

1. **Given** the frontend is running, **When** a visitor navigates to `/`, `/onboarding`, and `/login`, **Then** each view renders a placeholder page with a clear title and navigation links to the other views.
2. **Given** no valid session is present, **When** a visitor attempts to navigate to `/dashboard`, **Then** they are redirected to `/login`.
3. **Given** the frontend is running, **When** navigation links are used, **Then** the active route is reflected in the browser URL and no full page reload occurs.

---

### User Story 3 - Defined HTTP Contract Endpoints (Priority: P3)

The backend exposes all seven HTTP contract endpoints from PRD §8 — `POST /api/onboarding`, `POST /api/auth/face-login`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, and `DELETE /api/users/{userId}/face-data` — each accepting the documented request shape and returning the documented success response shape. The endpoints are stubs: they return deterministic mock responses (or a clear "not implemented" status) rather than executing real onboarding, login, or analysis logic. Protected endpoints reject requests lacking a session placeholder.

**Why this priority**: The contracts are the interface contract between frontend and backend and the basis for all later specs. Defining them as stubs now lets frontend and backend work proceed in parallel against a stable interface (PRD §8, Constitution Quality Gate §5).

**Independent Test**: Call each of the seven endpoints with a well-formed request and assert the response status code and body match the documented contract. Delivers a stable, testable API surface.

**Acceptance Scenarios**:

1. **Given** the backend is running, **When** `POST /api/onboarding` is called with a valid identifier, consent flag, and image, **Then** it returns `201 Created` with a body containing `userId`, `identifier`, and `status: "enrolled"` (deterministic mock values).
2. **Given** the backend is running, **When** `POST /api/auth/face-login` is called with a valid identifier and image, **Then** it returns `200 OK` with `userId` and `status: "authenticated"` (mock), or `401 Unauthorized` with a non-revealing generic message for failure.
3. **Given** the backend is running, **When** `GET /api/auth/me` is called without a session placeholder, **Then** it returns an unauthenticated response; with a session placeholder it returns the current session state.
4. **Given** the backend is running, **When** `POST /api/auth/logout` is called, **Then** it invalidates the session placeholder and returns a success response.
5. **Given** a session placeholder is present, **When** `POST /api/analysis/mood` is called with an image, **Then** it returns the documented mood response shape (`label`, `confidence`, `disclaimer`) with deterministic mock values.
6. **Given** a session placeholder is present, **When** `POST /api/analysis/age` is called with an image, **Then** it returns the documented age response shape (`estimatedAge`, `range`, `disclaimer`) with deterministic mock values.
7. **Given** the backend is running, **When** `DELETE /api/users/{userId}/face-data` is called with authorization, **Then** it returns a success response indicating the face data was removed (mock — no real deletion logic).
8. **Given** a protected analysis or delete endpoint, **When** it is called without a session placeholder, **Then** it rejects the request with an unauthenticated status.

---

### User Story 4 - Domain Models & Hexagonal Ports with Mock Adapters (Priority: P4)

The domain layer contains the four pure domain entities from PRD §7 — `User`, `FaceTemplate`, `AuthSession`, and `AnalysisRequest` — with no dependency on any specific ML model, web framework, or infrastructure library. The capabilities the domain needs (face detection, embedding generation, age estimation, mood estimation, session management, user repository, face-template repository, and image storage) are declared as ports (interfaces/protocols). A complete set of deterministic mock adapters implements every port so the whole flow can run end-to-end without real models, GPU, or network.

**Why this priority**: Hexagonal isolation is mandated by PRD §11 and Constitution Principle VII. Establishing ports and mocks now makes the domain testable in isolation and makes later substitution of real models (Fase 5) a configuration change, not a redesign.

**Independent Test**: Instantiate the domain wired to mock adapters and exercise the entity constructors and port calls; assert outputs are deterministic and that no model/network/GPU is touched. Delivers a testable, swappable domain core.

**Acceptance Scenarios**:

1. **Given** the domain layer, **When** its imports are inspected, **Then** it has no direct dependency on any concrete ML model, detector library, or infrastructure adapter.
2. **Given** a mock detector adapter, **When** it is given a fixture image, **Then** it returns a deterministic bounding box, score, and face count without invoking any real model.
3. **Given** a mock embedding adapter, **When** it is given a detected face, **Then** it returns a deterministic embedding vector of fixed dimension.
4. **Given** mock age and mood adapters, **When** they are given a face, **Then** they return deterministic age and mood results with model-version identifiers.
5. **Given** mock session, user-repository, face-template-repository, and image-storage adapters, **When** their operations are invoked, **Then** they behave deterministically and require no external service.

---

### User Story 5 - Persistent Storage Setup (Priority: P5)

The database schema for the four PRD §7 entities is defined and managed via migrations that create the `User`, `FaceTemplate`, `AuthSession`, and `AnalysisRequest` tables. A local filesystem image-storage adapter writes and reads captured images under the `usuarios/<user-id>/pictures.jpg` path convention, bind-mounted into the backend container so the path is identical inside and outside the container.

**Why this priority**: Persistence is required for the later onboarding and login specs to have somewhere to write. Establishing the schema and filesystem layout now (Constitution Principles V and VI) prevents schema drift later.

**Independent Test**: Apply migrations to a fresh database and confirm the four tables exist with the documented columns; write and read back an image via the filesystem adapter and confirm the path matches `usuarios/<user-id>/pictures.jpg`. Delivers working persistence foundations.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** migrations are applied, **Then** tables for `User`, `FaceTemplate`, `AuthSession`, and `AnalysisRequest` exist with the attributes defined in PRD §7.
2. **Given** the filesystem image-storage adapter, **When** an image is stored for a given user id, **Then** it is written to `usuarios/<user-id>/pictures.jpg` and is readable at that same path from both the host and the backend container.
3. **Given** migrations have been applied, **When** the same migrations are applied again, **Then** they are idempotent and produce no error.

---

### User Story 6 - Automated Contract & Domain Tests (Priority: P6)

An automated test suite covers the HTTP contracts of all seven endpoints (request/response shapes and status codes) and the behavior of the domain entities and mock adapters. The entire suite runs without a GPU, without network access, and without real ML models, and can be executed as part of the containerized stack.

**Why this priority**: Contract and domain tests are the safety net that lets subsequent specs implement real logic without breaking the interface (PRD §15, Constitution Quality Gates §4–§7). Running without GPU/network keeps the demo reproducible on any machine.

**Independent Test**: Run the test suite in an environment with no GPU and no network; assert all contract and domain tests pass. Delivers a green, reproducible test foundation.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** it is run with no GPU and no network, **Then** all contract tests for the seven endpoints pass, asserting documented request/response shapes and status codes.
2. **Given** the test suite, **When** it is run with no GPU and no network, **Then** all domain unit tests for entities and mock adapters pass and produce deterministic results.
3. **Given** a contract-violating change to an endpoint response, **When** the contract tests are run, **Then** at least one test fails.

---

### Edge Cases

- What happens when the compose-up command is run with a port already in use by another process? The stack should report a clear, actionable conflict rather than failing silently.
- What happens when the database service is unavailable at backend startup? The backend should report unhealthy and avoid crashing the whole stack irrecoverably.
- What happens when a stub endpoint receives a malformed request (e.g., missing required field, non-image payload)? It returns a documented validation error status, not an unhandled exception.
- What happens when `GET /api/auth/me` is called with an expired/invalid session placeholder? It returns an unauthenticated response, not an internal error.
- What happens when migrations are applied to a database with a conflicting existing schema? The migration tool reports the conflict clearly rather than corrupting data.
- What happens when the filesystem adapter cannot write to `usuarios/` (permissions/read-only mount)? It returns a clear storage error rather than a silent failure.
- What happens when a mock adapter is asked to process an empty or undecodable image? It returns a deterministic "no face / invalid image" result consistent with the image-validation rejection conditions (PRD FR-004: no face, multiple faces, insufficient quality, undecodable).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single container-orchestration command that starts the backend, frontend, and database services together (Constitution Principle IV).
- **FR-002**: Per-service build definitions MUST exist alongside each service's source so the stack is reproducible from a clean checkout.
- **FR-003**: The frontend MUST expose four routes — `/`, `/onboarding`, `/login`, `/dashboard` — each rendering a placeholder view, with in-app navigation between them (PRD §6.1).
- **FR-004**: The frontend MUST redirect any visit to `/dashboard` without a valid session placeholder to `/login` (PRD §6.1, FR-010).
- **FR-005**: The backend MUST expose all seven PRD §8 endpoints with the documented request and success-response shapes, returning deterministic mock responses (or a clear not-implemented status) rather than real business logic.
- **FR-006**: Protected endpoints (`GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`) MUST reject requests lacking a session placeholder with an unauthenticated status.
- **FR-007**: The `POST /api/auth/face-login` failure response MUST NOT reveal whether the identifier exists versus the face not matching (PRD §8, §12).
- **FR-008**: The domain layer MUST contain the four pure entities `User`, `FaceTemplate`, `AuthSession`, and `AnalysisRequest` matching PRD §7 attributes, with no dependency on concrete ML models or infrastructure (Constitution Principle VII).
- **FR-009**: The domain MUST declare ports for face detection, embedding generation, age estimation, mood estimation, session management, user repository, face-template repository, and image storage.
- **FR-010**: A deterministic mock adapter MUST implement every port so the full flow runs end-to-end without real models, GPU, or network (PRD §11, Constitution Principle VII).
- **FR-011**: Mock detector output MUST include bounding box, score, and face count, matching PRD §11's detector contract.
- **FR-012**: All models/adapters MUST carry an identifiable version so results are reproducible (PRD §11).
- **FR-013**: Database migrations MUST create tables for the four PRD §7 entities and be idempotent and runnable as part of stack startup or a single documented step (Constitution Principle VI).
- **FR-014**: The image-storage adapter MUST store captured images at `usuarios/<user-id>/pictures.jpg`, with the `usuarios/` tree bind-mounted so the path is identical inside and outside the backend container (Constitution Principle V).
- **FR-015**: The system MUST expose configuration for the verification threshold, model versions, and image limits (max size, format, resolution) as tunable values (PRD §11, Constitution OQ-6/OQ-8).
- **FR-016**: An automated contract test suite MUST cover all seven endpoints' request/response shapes and status codes (Constitution Quality Gate §5).
- **FR-017**: An automated domain test suite MUST cover entity construction and mock-adapter behavior, and MUST run without GPU, network, or real models (Constitution Quality Gate §7).
- **FR-018**: The login failure response MUST be generic and non-revealing, consistent with PRD §12.

### Key Entities *(include if feature involves data)*

- **User**: The registered person. Attributes: `id`, `identifier`, `createdAt`, `updatedAt`, `status` where `status ∈ {"enrolled", "active", "disabled"}` (PRD §7). One user has at most one face template and may have many auth sessions.
- **FaceTemplate**: The comparable facial representation derived from onboarding. Attributes: `id`, `userId`, `embedding` (or reference to secure storage), `modelVersion`, `createdAt`, `updatedAt` (PRD §7). Belongs to one User.
- **AuthSession**: An authenticated session created after successful face verification. Attributes: `id`, `userId`, `createdAt`, `expiresAt`, `revokedAt` (optional) (PRD §7). Belongs to one User.
- **AnalysisRequest**: An audit record of an on-demand analysis. Attributes: `id`, `userId`, `type` (`mood` or `age`), `modelVersion`, `createdAt`, `status` where `status ∈ {"pending", "completed", "failed"}` (PRD §7). Belongs to one User. Does not store the original image or full biometric result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clean checkout can be brought to a fully running state (all three services healthy) using a single command, with no host-native runtime or model installation required.
- **SC-002**: All four frontend routes render and are navigable, and `/dashboard` redirects unauthenticated visitors to `/login`, verifiable by opening the app in a browser.
- **SC-003**: All seven PRD §8 endpoints respond to well-formed requests with the documented status code and response shape, verifiable by calling each endpoint.
- **SC-004**: The domain layer has zero imports of concrete ML models or infrastructure adapters, verifiable by static dependency inspection.
- **SC-005**: Every declared port has a deterministic mock adapter, and exercising the domain wired to mocks produces identical outputs across repeated runs (determinism), verifiable by running the domain test suite twice and comparing results.
- **SC-006**: Applying migrations to a fresh database creates the four entity tables, and re-applying is idempotent, verifiable by running migrations twice.
- **SC-007**: An image stored via the filesystem adapter is readable at `usuarios/<user-id>/pictures.jpg` from both the host and the backend container, verifiable by a read-back check.
- **SC-008**: The full contract and domain test suite passes in an environment with no GPU and no network, verifiable by running the suite under those constraints.
- **SC-009**: A deliberate contract-violating change to any endpoint response causes at least one contract test to fail, verifiable by introducing and reverting such a change.
- **SC-010**: No real business logic (onboarding, login verification, mood/age inference, real deletion) is implemented in this spec — endpoints are stubs/mocks — verifiable by confirming the spec's scope does not extend into Fases 2–6.

## Assumptions

- The technology stack is fixed by the Constitution (Principle III/Technology Stack table): backend in Python with FastAPI, frontend in React with Vite, PostgreSQL for persistence, Alembic for migrations, Docker Compose for orchestration. These are project-level decisions, not arbitrary implementation choices, and are assumed settled for this spec.
- The session mechanism uses server-side sessions in PostgreSQL keyed by a signed cookie (Constitution OQ-3 default); this spec only establishes the placeholder/session port, not real session enforcement.
- The distance metric for verification is cosine similarity with a configurable threshold (Constitution OQ-6 default); the threshold is exposed as configuration but no real comparison logic is implemented in this spec.
- Image constraints default to JPEG, ≤ 2 MB, resized to ≤ 640px on the long edge (Constitution OQ-8 default); these limits are exposed as configuration.
- "Stub/mock endpoints" means endpoints return deterministic hardcoded or mock-adapter-driven responses and a clear not-implemented indication where appropriate, rather than executing real onboarding/login/analysis/deletion logic. Real logic is explicitly deferred to specs 002–006.
- Route protection in this spec is a placeholder guard (redirect to `/login` when no session placeholder is present), represented on the frontend as an in-memory React context flag; real session/cookie validation is deferred to spec 003 (Fase 3).
- The frontend camera capture UI is a placeholder only; real `getUserMedia` capture logic is deferred to spec 002 (Fase 2).
- Rate limiting, real deletion logic, and real ML model integration are explicitly out of scope for this spec (deferred to Fases 5–6).
- The `AnalysisRequest` entity is included in the schema per PRD §7's "optional for MVP" note because its table is cheap to establish now and avoids a later migration; no analysis results are actually persisted in this spec.
- Contract tests assert shapes and status codes against deterministic mock responses; they do not assert real ML outputs, which are deferred to Fase 5.
- Mock adapters produce hardcoded constant outputs (no RNG/seed) so repeated runs are byte-identical and trivially assertable (supports SC-005).
- Observability in this spec is limited to structured JSON logs and the health/readiness endpoint; metrics, distributed tracing, and audit logging are deferred (Constitution Principle VIII — no traceability guarantee).
