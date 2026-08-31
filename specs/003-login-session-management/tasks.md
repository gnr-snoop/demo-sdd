---

description: "Task list for Login & Session Management (Fase 3)"
---

# Tasks: Login & Session Management (Fase 3)

**Input**: Design documents from `/specs/003-login-session-management/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Required — FR-022 mandates an automated test suite and User Story 6 (P6) is dedicated to it. Tests are generated for every user story (unit + contract + integration + frontend as applicable). The domain/contract suites MUST run without GPU or network (Constitution Quality Gate §7).

**Organization**: Tasks are grouped by user story (US1–US6) to enable independent implementation and testing of each story. Stories follow priority order P1 → P6.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/` (monorepo inherited from specs 001/002)
- Backend tests: `backend/tests/{unit,contract,integration,domain}/`
- Frontend tests: `frontend/src/__tests__/`
- All new domain modules live under `backend/src/face_insight/domain/` and import only ports/entities/result types/exceptions (no FastAPI, SQLAlchemy, ML, itsdangerous, Pillow).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the one additive dependency and the new configuration fields this feature introduces on top of specs 001/002.

- [X] T001 Add `itsdangerous` as an explicit dependency in `backend/pyproject.toml` (transitive via Starlette; pinned explicit for clarity per plan.md)
- [X] T002 [P] Add session/verification config fields to `backend/src/face_insight/config.py`: `verification_threshold` (default `0.5`, env `VERIFICATION_THRESHOLD`), `session_lifetime_seconds` (default `1800`, env `SESSION_LIFETIME_SECONDS`), `session_cookie_name` (default `fid_session`), `session_cookie_secure` (default `false`), `session_signing_key` (default `demo-signing-key-change-me`, env `SESSION_SIGNING_KEY`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain types, ports, adapters, and schemas that EVERY user story depends on. MUST be complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create domain exceptions in `backend/src/face_insight/domain/exceptions.py`: `AuthFailed`, `Unauthenticated`, `LoginInternalError`, `ComparisonError`, plus capture exceptions `InvalidImage`, `NoFace`, `MultipleFaces`, `InsufficientQuality` (reuse from spec 002 if present)
- [X] T004 [P] Add `ComparisonResult` value object (`similarity: float`, `accepted: bool`) to `backend/src/face_insight/domain/result_types.py`
- [X] T005 [P] Fill the `Comparison` port (`compare(a, b) -> float`) in `backend/src/face_insight/domain/ports.py`
- [X] T006 [P] Implement `CosineComparison` adapter (pure-Python dot product / norms; dimension-mismatch guard raising `ComparisonError`) in `backend/src/face_insight/domain/comparison.py`
- [X] T007 Fill `AuthSession` entity behavior/factories (`create_session(now, lifetime)`, `is_valid(now)`) in `backend/src/face_insight/domain/entities.py`
- [X] T008 Fill `SessionManager` port methods (`create`, `get_valid`, `revoke`) in `backend/src/face_insight/domain/ports.py`
- [X] T009 [P] Implement `SqlAlchemySessionManager` async DB adapter against the existing `auth_sessions` table in `backend/src/face_insight/adapters/db/session_manager.py`
- [X] T010 [P] Implement `SessionCookieService` HTTP adapter (`itsdangerous.URLSafeTimedSerializer` sign/unsign + cookie read/write; HttpOnly, SameSite=Lax, Path=/) in `backend/src/face_insight/adapters/http/session_cookie.py`
- [X] T011 [P] Add auth API schemas to `backend/src/face_insight/api/schemas.py`: `LoginResponse` (`userId`, `status`), `MeResponse` (`authenticated`, `userId`), `LogoutResponse` (`status`), and `AuthFailed`/`Unauthenticated` error bodies (reuse `ErrorResponse`/`ErrorBody` from spec 002)
- [X] T012 Extend domain purity static check to cover `login.py`, `comparison.py`, `exceptions.py`, and `entities.py` session factories (assert no imports of adapters/api/ML/SQLAlchemy/FastAPI/itsdangerous/Pillow) in `backend/tests/domain/test_domain_purity.py`

**Checkpoint**: Foundation ready — domain types, ports, DB/cookie adapters, and schemas in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Successful Face Login (Happy Path) (Priority: P1) 🎯 MVP

**Goal**: A person who completed onboarding submits identifier + captured image to `POST /api/auth/face-login`; the backend validates, detects one face, loads User/FaceTemplate, embeds, compares via cosine similarity, and on `>= threshold` creates an `AuthSession` + sets a signed http-only cookie, returning `200 {userId, status: "authenticated"}`.

**Independent Test**: Seed a `User` + `FaceTemplate`, call `POST /api/auth/face-login` with a fixture image whose mock embedding yields similarity `>= threshold`; assert `200` with `userId` + `status`, a signed cookie, and exactly one new `AuthSession` row (`revokedAt = null`, `expiresAt` in the future).

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T013 [P] [US1] Contract test for `POST /api/auth/face-login` happy-path shape + status + signed cookie in `backend/tests/contract/test_auth_contracts.py`
- [X] T014 [P] [US1] Integration test for successful login → `AuthSession` row persisted in `backend/tests/integration/test_login_session.py`
- [X] T015 [P] [US1] Unit test for `LoginService.login` happy path (port mocks, `ComparisonResult.accepted = True`) in `backend/tests/unit/test_login_service.py`

### Implementation for User Story 1

- [X] T016 [P] [US1] Implement `LoginService` use-case (port-only deps, async; evaluation order: normalize → decode/validate → detect → lookup → embed → compare → session create) in `backend/src/face_insight/domain/login.py`
- [X] T017 [P] [US1] Add fixture-controllable similarity + matching/non-matching embeddings to `backend/src/face_insight/adapters/mock/constants.py`
- [X] T018 [US1] Implement `POST /api/auth/face-login` route handler (multipart `identifier` + `image`, wires `LoginService`, sets signed cookie, returns `LoginResponse`) in `backend/src/face_insight/api/routes/auth.py`
- [X] T019 [US1] Wire `LoginService` + ports + `SessionCookieService` + `SessionManager` into the FastAPI dependency graph in `backend/src/face_insight/api/dependencies.py`

**Checkpoint**: User Story 1 fully functional — a real face login creates a session and sets a signed cookie. Independently testable.

---

## Phase 4: User Story 2 - Login Rejected with Generic Non-Revealing Error (Priority: P2)

**Goal**: The two identity-sensitive failures (nonexistent identifier, below-threshold non-match) return a byte-identical `401 auth_failed`; capture-quality failures return actionable `400` codes (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`). No `AuthSession` is created on any failure path.

**Independent Test**: Submit (a) a nonexistent identifier and (b) a known identifier with a non-matching image; assert both return byte-identical `401 auth_failed` and no session. Submit (c) no-face and (d) multiple-faces images for a known identifier; assert actionable `400` codes and no session.

### Tests for User Story 2

- [X] T020 [P] [US2] Contract test asserting byte-identity of nonexistent-identifier and below-threshold `401 auth_failed` responses in `backend/tests/contract/test_auth_contracts.py`
- [X] T021 [P] [US2] Unit test for non-revealing error mapping (single `AuthFailed` exception for both causes) in `backend/tests/unit/test_login_service.py`
- [X] T022 [P] [US2] Integration test for capture-quality `400` codes (`no_face`, `multiple_faces`, `invalid_image`) and no `AuthSession` created in `backend/tests/integration/test_login_session.py`

### Implementation for User Story 2

- [X] T023 [US2] Raise the single `AuthFailed` exception for both nonexistent-identifier and below-threshold cases (identical message constant) in `backend/src/face_insight/domain/login.py`
- [X] T024 [US2] Map capture exceptions to `400` with actionable bodies and `AuthFailed` to `401` in the face-login route handler in `backend/src/face_insight/api/routes/auth.py`

**Checkpoint**: User Stories 1 AND 2 both work — login succeeds or rejects with the correct, non-revealing contract.

---

## Phase 5: User Story 3 - Session Validation & Route Protection (Priority: P3)

**Goal**: Replace the spec 001 placeholder session guard with real `require_valid_session` validation on every protected endpoint (`GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`). Unauthenticated/expired/revoked/unknown sessions all return `401 unauthenticated`. `GET /api/auth/me` returns `200 {authenticated: true, userId}` on a valid session.

**Independent Test**: Without a cookie, call each protected endpoint and navigate to `/dashboard`; assert `401 unauthenticated` and redirect to `/login`. After login, assert protected endpoints are accepted. Expire/revoke the session and assert rejection again.

### Tests for User Story 3

- [X] T025 [P] [US3] Contract test for `401 unauthenticated` on protected endpoints without a valid session in `backend/tests/contract/test_http_contracts.py`
- [X] T026 [P] [US3] Unit test for session validity rules (expired, revoked, unknown id, absent cookie) in `backend/tests/unit/test_session.py`
- [X] T027 [P] [US3] Integration test for protected endpoints with valid / absent / expired / revoked session in `backend/tests/integration/test_login_session.py`

### Implementation for User Story 3

- [X] T028 [US3] Implement `require_valid_session` and `get_optional_session` FastAPI dependencies (unsign cookie → `SessionManager.get_valid` → `401 unauthenticated` on `None`) in `backend/src/face_insight/api/dependencies.py`
- [X] T029 [US3] Implement `GET /api/auth/me` route handler (`200 {authenticated: true, userId}` on valid session; `401 unauthenticated` otherwise) in `backend/src/face_insight/api/routes/auth.py`
- [X] T030 [P] [US3] Add `Depends(require_valid_session)` to `POST /api/analysis/mood` and `POST /api/analysis/age` (logic stays stubbed) in `backend/src/face_insight/api/routes/analysis.py`
- [X] T031 [P] [US3] Add `Depends(require_valid_session)` to `DELETE /api/users/{userId}/face-data` (logic stays stubbed) in `backend/src/face_insight/api/routes/users.py`

**Checkpoint**: Real backend route protection in place — all protected endpoints gated by a valid server-side session.

---

## Phase 6: User Story 4 - Logout & Session Invalidation (Priority: P4)

**Goal**: `POST /api/auth/logout` sets `revokedAt` on the `AuthSession` row, clears the cookie, and returns `200 {status: "ok"}` idempotently (no-cookie / expired / revoked / valid all return the same success). After logout, the revoked session cannot access any protected endpoint.

**Independent Test**: Login, call `POST /api/auth/logout`, assert `200 {status: "ok"}` and `revokedAt` set on the session row. Call every protected endpoint with the revoked cookie; assert `401 unauthenticated`.

### Tests for User Story 4

- [X] T032 [P] [US4] Contract test for `POST /api/auth/logout` (`200 {status: "ok"}`, idempotent for no-cookie / expired / revoked / valid) in `backend/tests/contract/test_auth_contracts.py`
- [X] T033 [P] [US4] Integration test for logout revokes session + protected endpoints reject afterward in `backend/tests/integration/test_login_session.py`

### Implementation for User Story 4

- [X] T034 [US4] Implement `POST /api/auth/logout` route handler (best-effort `SessionManager.revoke`, always clear cookie, always `200 {status: "ok"}`) in `backend/src/face_insight/api/routes/auth.py`

**Checkpoint**: Complete session lifecycle — login → protected access → logout → revoke. User Stories 1–4 all independently functional.

---

## Phase 7: User Story 5 - Frontend Login Page, Real Session Wiring & Logout Button (Priority: P5)

**Goal**: Replace the spec 001 frontend placeholders with a real login page (identifier + camera + capture, driven by a 7-state machine), a real `SessionContext` bootstrapped from `GET /api/auth/me`, a real `ProtectedRoute` gating `/dashboard`, and a keyboard-accessible "Cerrar sesión" button on the dashboard.

**Independent Test**: Render the login page with a mocked `MediaDevices` + mocked fetch; walk the state machine through idle → permission → ready → processing → redirect, and through recoverable auth/capture errors; assert correct controls and keyboard reachability. Render `/dashboard` authenticated → assert logout button; unauthenticated → assert redirect to `/login`.

### Tests for User Story 5

- [X] T035 [P] [US5] Frontend test for `useLoginMachine` state transitions (idle → requesting_permission → ready_to_capture → processing → success_redirect / recoverable_error) in `frontend/src/__tests__/login/useLoginMachine.test.tsx`
- [X] T036 [P] [US5] Frontend test for `ProtectedRoute` gating + `SessionContext` bootstrap from `GET /api/auth/me` in `frontend/src/__tests__/session/ProtectedRoute.test.tsx`
- [X] T037 [P] [US5] Frontend test for dashboard "Cerrar sesión" button (visible, keyboard-accessible, triggers logout flow) in `frontend/src/__tests__/session/logoutButton.test.tsx`

### Implementation for User Story 5

- [X] T038 [P] [US5] Add `faceLogin(identifier, image)`, `getMe()`, `logout()` helpers to `frontend/src/services/api.ts`
- [X] T039 [P] [US5] Implement `useLoginMachine` hook (7 states, `useReducer`-based, mirrors onboarding pattern) in `frontend/src/hooks/useLoginMachine.ts`
- [X] T040 [US5] Replace `Login` page with real flow (identifier input, `CameraCapture` reuse, state-driven controls, submit to `faceLogin`, redirect to `/dashboard` on success) in `frontend/src/pages/Login.tsx`
- [X] T041 [US5] Replace `SessionContext` with real session state (bootstrap from `getMe` on mount, `login(userId)` / `logout()` actions, `useSession()` hook) in `frontend/src/context/SessionContext.tsx`
- [X] T042 [US5] Replace `ProtectedRoute` with real gating (redirect to `/login` when `authenticated === false`, render `<Outlet/>` otherwise) in `frontend/src/components/ProtectedRoute.tsx`
- [X] T043 [US5] Add keyboard-accessible "Cerrar sesión" button wired to `POST /api/auth/logout` + `logout()` + navigate to `/login` in `frontend/src/pages/Dashboard.tsx`

**Checkpoint**: Full frontend login + protection + logout UI wired to real backend session state.

---

## Phase 8: User Story 6 - Automated Login & Session Tests (Priority: P6)

**Goal**: Consolidate the automated test suite so the full login & session flow is covered: unit (cosine similarity, threshold, session validity, normalization, non-revealing mapping, cookie sign/unsign), integration (real auth endpoints + mock adapters + real PostgreSQL), and contract (shapes, status codes, byte-identical `auth_failed`). The domain portions run without GPU/network.

**Independent Test**: Run the full suite in a no-GPU/no-network environment; assert all tests pass, a contract-violating change to any auth endpoint fails a contract test, and a change making the two identity-sensitive failures distinguishable fails a contract test.

### Tests for User Story 6

- [X] T044 [P] [US6] Unit test for `CosineComparison` (cosine values, threshold boundary, dimension-mismatch → `ComparisonError`) in `backend/tests/unit/test_comparison.py`
- [X] T045 [P] [US6] Unit test for `SessionCookieService` sign/unsign/tamper/unknown-token in `backend/tests/unit/test_session_cookie.py`
- [X] T046 [P] [US6] Unit test for identifier normalization reuse (trim + lowercase, case-insensitive lookup) in `backend/tests/unit/test_normalization.py`
- [X] T047 [P] [US6] Contract test asserting byte-identity of the two `auth_failed` responses (same status, same code, same message body bytes) in `backend/tests/contract/test_auth_contracts.py`
- [X] T048 [P] [US6] Contract-violation mutation guard test (SC-011: a deliberate shape/code change or a distinguishable-failure change causes a contract test to fail) in `backend/tests/contract/test_auth_contracts.py`
- [X] T049 [US6] Validate the full suite passes under no-GPU/no-network constraints per `specs/003-login-session-management/quickstart.md` (run unit + contract + integration + domain-purity + frontend vitest)

**Checkpoint**: Green, reproducible login & session test foundation. Later specs (004/005/006) can build on real sessions without regressing login or protection.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [X] T050 [P] Add structured JSON logging for auth events (`auth.login`, `auth.me`, `auth.logout`, `session.create`, `session.revoke`, `session.reject`) with `event`/`duration_ms`/`status`/`user_id`(success only)/`error_code` and NO image/embedding/similarity/identifier value (FR-023/SC-013) in `backend/src/face_insight/api/routes/auth.py`
- [X] T051 [P] Documentation updates: cross-reference `contracts/` and `quickstart.md` from the feature README in `specs/003-login-session-management/contracts/README.md`
- [X] T052 Run `quickstart.md` validation scenarios 1–5 end-to-end against `docker compose up` and confirm all expected outcomes (SC-002..SC-008, SC-013)
- [X] T053 Security/contract hardening review: confirm `401` is reserved exclusively for `auth_failed` + `unauthenticated`, `400` for capture codes, no biometric data in logs, no `AuthSession` on any failure path (FR-004/FR-010/FR-023)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phases 3–8)**: All depend on Foundational phase completion.
  - US1 (P1) → US2 (P2): US2 extends the same `LoginService` + route handler; implement US1 first.
  - US3 (P3): depends on US1's `SessionManager`/cookie wiring for the `me` handler and protected-endpoint gating.
  - US4 (P4): depends on US3's `require_valid_session` dependency (logout is itself protected) and US1's session creation.
  - US5 (P5): depends on US1 (login endpoint), US3 (`me` endpoint), US4 (logout endpoint) all being implemented.
  - US6 (P6): depends on US1–US5 existing; consolidates and extends the test suite.
- **Polish (Phase 9)**: Depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependencies on other stories. 🎯 MVP
- **US2 (P2)**: After Foundational + US1 (extends `LoginService` + face-login handler with rejection paths).
- **US3 (P3)**: After Foundational + US1 (reuses `SessionManager`/cookie wiring).
- **US4 (P4)**: After Foundational + US1 + US3 (logout is session-protected; revokes US1 sessions).
- **US5 (P5)**: After Foundational + US1 + US3 + US4 (frontend wires all three auth endpoints).
- **US6 (P6)**: After US1–US5 (tests exercise the complete implemented flow).

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD).
- Domain/use-case before route handler before dependency wiring.
- Models/exceptions before services; services before endpoints.
- Story complete and independently testable before moving to the next priority.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002 after T001 only if pyproject is shared; they touch different files → parallel).
- All Foundational tasks marked [P] can run in parallel within Phase 2 (T003–T006, T009–T011 touch distinct files; T007/T008 edit `entities.py`/`ports.py` and sequence after the new modules they reference).
- Within each user story, all tests marked [P] can run in parallel (distinct test files / distinct assertions).
- Within US5, T038 and T039 are independent and parallel; T040–T043 share the frontend tree and sequence after the hook + api helpers.
- US6 test tasks T044–T048 are all [P] (distinct test files) and can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (TDD — write first, watch them fail):
Task: "Contract test for POST /api/auth/face-login happy path in backend/tests/contract/test_auth_contracts.py"
Task: "Integration test for successful login → AuthSession row in backend/tests/integration/test_login_session.py"
Task: "Unit test for LoginService.login happy path in backend/tests/unit/test_login_service.py"

# Launch independent implementation pieces in parallel:
Task: "Implement LoginService use-case in backend/src/face_insight/domain/login.py"
Task: "Add fixture-controllable similarity to backend/src/face_insight/adapters/mock/constants.py"
```

## Parallel Example: User Story 5

```bash
# Frontend tests in parallel:
Task: "useLoginMachine state transitions test in frontend/src/__tests__/login/useLoginMachine.test.tsx"
Task: "ProtectedRoute + SessionContext test in frontend/src/__tests__/session/ProtectedRoute.test.tsx"
Task: "Logout button test in frontend/src/__tests__/session/logoutButton.test.tsx"

# Independent implementation pieces:
Task: "Add faceLogin/getMe/logout helpers in frontend/src/services/api.ts"
Task: "Implement useLoginMachine hook in frontend/src/hooks/useLoginMachine.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002).
2. Complete Phase 2: Foundational (T003–T012) — CRITICAL, blocks all stories.
3. Complete Phase 3: User Story 1 (T013–T019).
4. **STOP and VALIDATE**: Test User Story 1 independently — a real face login creates an `AuthSession` and sets a signed cookie.
5. Deploy/demo the happy path if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → test independently → demo login (MVP!).
3. Add US2 → test non-revealing rejection independently → demo.
4. Add US3 → test route protection independently → demo.
5. Add US4 → test logout independently → demo.
6. Add US5 → test frontend login + protection + logout → demo full UI.
7. Add US6 → green test suite → safety net for specs 004/005/006.
8. Polish → logging, docs, quickstart validation, hardening review.

### Parallel Team Strategy

With multiple developers after Foundational:

1. Team completes Setup + Foundational together.
2. Once Foundational is done, US1 is the critical path (US2–US5 depend on it).
3. After US1: Developer A → US2 (rejection paths), Developer B → US3 (route protection) — US2 and US3 touch different files and can overlap.
4. After US3: US4 (logout) is small and can pair with US5 frontend work.
5. US6 consolidates tests once US1–US5 are merged.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to a specific user story for traceability.
- Each user story is independently completable and testable; stories sequence by priority and by the dependency graph above (US1 is the gate).
- Verify tests fail before implementing (TDD).
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.
- All ML touchpoints stay behind ports wired to mock adapters (SC-012); real models are Fase 5.
- No `AuthSession` is created on any failure path (FR-004/SC-004).
- The two identity-sensitive failures MUST be byte-identical (FR-008/SC-003) — share one `AuthFailed` exception + one message constant.
- No image/embedding/similarity/identifier value in logs (FR-023/SC-013).
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence.
