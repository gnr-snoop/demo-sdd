---

description: "Task list for Face Data Deletion (Fase 6 partial — hardening)"
---

# Tasks: Face Data Deletion (Fase 6 partial — hardening)

**Input**: Design documents from `/specs/006-delete-face-data/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: The constitution (`.specify/memory/constitution.md`) mandates tests — Quality Gate §4 (tests-first, domain tests use mocks), §5 (contract tests for every PRD §8 endpoint, including `DELETE /api/users/{userId}/face-data`), §6 (integration test per user story via `docker compose`), §7 (no GPU/network required for domain + contract suites). Test tasks are included for every user story and written FIRST (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story (US1..US5, priorities P1..P5) to enable independent implementation and testing of each story. This spec builds on specs 001-004 — the runnable stack, ports, adapters, route stub, schema, frontend api fn, and contract-test scaffolding already exist and are REUSED, not re-created.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app** (per plan.md Project Structure): `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/`
- Backend: Python 3.11 / FastAPI / SQLAlchemy 2.x async / Pydantic v2 / pytest
- Frontend: TypeScript / React 18 / Vite / vitest
- Storage: PostgreSQL (User, FaceTemplate, AuthSession) + local filesystem `usuarios/<user-id>/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature branch and the specs 001-004 scaffolding this spec builds on. No new project initialization — the stack, ports, adapters, route stub, schema, and frontend api fn already exist.

- [X] T001 Verify branch `006-delete-face-data` is checked out and the specs 001-004 scaffolding is present and green: ports (`backend/src/face_insight/domain/ports.py`), adapters (`backend/src/face_insight/adapters/db/repositories.py`, `adapters/mock/`), route stub (`backend/src/face_insight/api/routes/users.py`), schema (`backend/src/face_insight/api/schemas.py`), frontend api fn (`frontend/src/services/api.ts`), and existing contract tests (`backend/tests/contract/test_http_contracts.py`) all exist and the current test suite passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain exceptions and error-handler registration that ALL user stories depend on. These MUST be complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Add `Forbidden`, `NotFound`, and `DeletionInternalError` domain exceptions to `backend/src/face_insight/domain/exceptions.py` as subclasses of `OnboardingError` (reuse the existing error-base pattern from specs 002/003). These carry the pinned machine codes `forbidden`, `not_found`, `internal_error`.
- [X] T003 Register `Forbidden`→`403`, `NotFound`→`404`, `DeletionInternalError`→`500` exception handlers in `backend/src/face_insight/main.py` following the existing `UnauthenticatedError`→`401` handler-registration pattern. Handlers emit the pinned `{"error": {"code": "...", "message": "..."}}` body shape. (depends on T002)

**Checkpoint**: Foundation ready — domain exceptions and error mapping in place; user story implementation can now begin.

---

## Phase 3: User Story 1 - Successful Face Data Deletion (Happy Path) (Priority: P1) 🎯 MVP

**Goal**: An authenticated person can delete their own face data via `DELETE /api/users/{userId}/face-data` and receive `200 OK` with `{userId, status: "deleted"}` — DB rows (User, FaceTemplate, AuthSession) hard-deleted in one transaction, filesystem folder best-effort deleted, cookie cleared.

**Independent Test**: Perform onboarding + login (specs 002/003) so `User`, `FaceTemplate`, `AuthSession`, and `usuarios/<user-id>/pictures.jpg` all exist. Call `DELETE /api/users/{userId}/face-data` with the session cookie and matching `userId`; assert `200` with echoed `userId` and `status == "deleted"`, a cleared cookie, and that all DB rows and the filesystem folder are gone.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [P] [US1] Contract test for `200` deletion happy path in `backend/tests/contract/test_http_contracts.py`: after onboarding + login, `DELETE` with valid session + matching `userId` → `200` with `userId` (echoed UUID v4) and `status == "deleted"`, cleared session cookie, and `User`/`FaceTemplate`/`AuthSession` rows gone from PostgreSQL and `usuarios/<user-id>/` gone from the filesystem.
- [X] T005 [P] [US1] Domain unit test for `DeletionService` happy path in `backend/tests/unit/test_deletion_service.py`: with mock ports + injected `delete_user_face_data` callable, assert the deletion ordering (FaceTemplate rows → AuthSession rows → User row → commit) is invoked, `ImageStorage.delete` is called after the DB callable, and the result carries `userId` + `status:"deleted"`. No GPU/network/real models.
- [X] T006 [P] [US1] Integration test for happy-path deletion in `backend/tests/integration/test_deletion_integration.py`: exercise the real `DELETE` endpoint wired to real PostgreSQL + real filesystem image-storage adapter (create a real `usuarios/<user-id>/pictures.jpg`, then delete); assert `200`, all rows removed, folder removed, cookie cleared.

### Implementation for User Story 1

- [X] T007 [US1] Implement `SqlAlchemyUnitOfWork.delete_user_face_data(user_id: UUID) -> None` in `backend/src/face_insight/adapters/db/repositories.py`: open ONE async `AsyncSession`, delete `FaceTemplateORM` rows → `AuthSessionORM` rows → `UserORM` (dependents first, then parent), commit; on any exception roll back and re-raise. (research R-2; depends on T005 for the callable contract)
- [X] T008 [US1] Implement `MockUnitOfWork.delete_user_face_data` in `backend/src/face_insight/adapters/mock/` for domain tests: record the call and the ordering so `test_deletion_service.py` can assert dependents-before-parent. (depends on T005)
- [X] T009 [US1] Create `DeletionService` in `backend/src/face_insight/domain/deletion.py` with `async def delete_face_data(user_id, session_user_id)`: depends only on `UserRepository.get` (404 lookup), `ImageStorage.delete` (best-effort FS cleanup), an injected `delete_user_face_data` async callable, and a structured logging callable. No SQLAlchemy/FastAPI/ML/filesystem-adapter imports (Principle VII, FR-013/FR-014). (depends on T002, T005)
- [X] T010 [US1] Add `get_deletion_service` resolver in `backend/src/face_insight/api/dependencies.py` and wire `DeletionService` + the `SqlAlchemyUnitOfWork.delete_user_face_data` callable into `app.state` in `backend/src/face_insight/main.py`. (depends on T007, T009)
- [X] T011 [US1] Implement the real `delete_face_data` route handler in `backend/src/face_insight/api/routes/users.py` (replacing the spec 001 stub): `require_valid_session` → authorization check (`session.user_id == path user_id` else raise `Forbidden`) → load `User` via `UserRepository.get` (None → raise `NotFound`) → `DeletionService.delete_face_data` → `session_cookie_service.clear(response)` → `200` `DeleteFaceDataResponse`. (depends on T003, T010)

**Checkpoint**: User Story 1 fully functional — the `DELETE` endpoint returns `200` on the happy path and removes all DB rows + filesystem folder. Independently testable via T004/T005/T006.

---

## Phase 4: User Story 2 - Authorization & Session Gating on Deletion (Priority: P2)

**Goal**: The endpoint rejects unauthenticated requests (`401 unauthenticated`), mismatched-`userId` requests (`403 forbidden`), and malformed UUIDs (`422`) — performing no deletion in each case. Demo-grade authorization: only the owner can delete their own data.

**Independent Test**: Seed two users (A and B) with valid sessions. (a) `DELETE` with no cookie → `401 unauthenticated`, no rows removed. (b) `DELETE` with A's cookie but B's `userId` → `403 forbidden`, no rows removed. (c) `DELETE` with malformed `userId` → `422`, no rows removed. (d) `DELETE` with expired/revoked session → `401 unauthenticated`.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US2] Contract tests for `401 unauthenticated`, `403 forbidden`, and `422 malformed UUID` in `backend/tests/contract/test_http_contracts.py`: assert each status code, the pinned `error.code` strings, and that no `User`/`FaceTemplate`/`AuthSession` rows are removed.
- [X] T013 [P] [US2] Domain unit test for the authorization rule in `backend/tests/unit/test_deletion_service.py`: `session_user_id != path_user_id` raises `Forbidden` and does NOT invoke the `delete_user_face_data` callable or `ImageStorage.delete`; assert the condition evaluation order (authz before user lookup before deletion).
- [X] T014 [P] [US2] Integration tests for `401` (no cookie / expired / revoked session), `403` (mismatched `userId`), `422` (malformed UUID), and `404 not_found` (out-of-band missing user) in `backend/tests/integration/test_deletion_integration.py`: assert each rejection and that no rows/folders are removed for either user.

### Implementation for User Story 2

- [X] T015 [US2] Verify and harden the authorization check + `403` message in `backend/src/face_insight/api/routes/users.py`: confirm `session.user_id != path user_id` raises `Forbidden` with the intentionally-revealing message `"Solo puedes eliminar tus propios datos."` and performs no deletion (no callable invocation, no FS touch). (research R-3; depends on T011)

**Checkpoint**: User Stories 1 AND 2 both work independently — happy path succeeds, all authorization rejections return the pinned codes with no data removed.

---

## Phase 5: User Story 3 - Post-Deletion Invalidation & "Right to Be Forgotten" Verification (Priority: P3)

**Goal**: After a successful deletion, the person is fully forgotten: old cookie invalid (`GET /api/auth/me` → `401 unauthenticated`), login with old identifier fails (`POST /api/auth/face-login` → `401 auth_failed` indistinguishable from never-enrolled), no DB rows remain, no filesystem folder remains.

**Independent Test**: Onboard + login `demo@example.com`, then delete. (a) `GET /api/auth/me` with old cookie → `401 unauthenticated`. (b) `POST /api/auth/face-login` with old identifier + fixture image → `401 auth_failed`. (c) Inspect PostgreSQL → no rows for that `userId`. (d) Inspect filesystem → `usuarios/<user-id>/` absent.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US3] Integration test for post-deletion invalidation in `backend/tests/integration/test_deletion_integration.py`: after a `200` deletion, `GET /api/auth/me` with the old cookie → `401 unauthenticated`; `POST /api/auth/face-login` with the old identifier → `401 auth_failed`; assert no `User`/`FaceTemplate`/`AuthSession` rows in PostgreSQL and `usuarios/<user-id>/` absent on the filesystem. (depends on US1)
- [X] T017 [P] [US3] Contract test for post-deletion invalidation responses in `backend/tests/contract/test_http_contracts.py`: assert old cookie → `401 unauthenticated` and old-identifier login → `401 auth_failed` (indistinguishable from a never-enrolled identifier per spec 003).

### Implementation for User Story 3

- [X] T018 [US3] Verify no additional implementation is needed: the hard delete from US1 already guarantees post-deletion invalidation (no `User`/`FaceTemplate` → login fails at identifier lookup → `401 auth_failed`; no `AuthSession` → `/me` → `401 unauthenticated`). Confirm by running T016 + T017 green. Document the verification in `specs/006-delete-face-data/research.md` if a gap surfaces.

**Checkpoint**: The "right to be forgotten" is verifiable — old cookie invalid, login fails, no DB rows, no filesystem folder.

---

## Phase 6: User Story 4 - Frontend Deletion UI & Logout-After-Deletion Handling (Priority: P4)

**Goal**: The `/dashboard` renders a keyboard-accessible "Eliminar mis datos" button + confirmation dialog. On confirm, it calls `DELETE /api/users/{userId}/face-data`, disables the button during the request, and on `200` clears session state, releases the camera, discards analysis results, and navigates to `/`. On `500` it shows an actionable retry error; on `401` it redirects to `/login`.

**Independent Test**: Render `/dashboard` with an authenticated session and a mocked fetch. Walk: button-press (assert dialog + keyboard reachability) → confirm (assert processing state + button disabled) → 200 response (assert session cleared, camera released, navigate to `/`). Then mock `500` (assert actionable error + retry, no reload). Then mock `401` (assert redirect to `/login`).

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T019 [P] [US4] Frontend deletion UI flow test in `frontend/tests/DashboardDelete.test.tsx`: with mocked fetch + mocked `MediaDevices` lifecycle — button visible & keyboard-accessible → confirm dialog appears → processing state + button disabled → 200 success → session state cleared, camera stream released, navigate to `/`; 500 → actionable error with "Reintentar" + re-enabled button + no full reload; 401 → redirect to `/login`; cancel → no request, dashboard unchanged; state communication not color-only.

### Implementation for User Story 4

- [X] T020 [P] [US4] Add `clearSession()` to `frontend/src/context/SessionContext.tsx`: clears in-memory session state WITHOUT calling `api.logout()` (the session is already destroyed by the deletion transaction; calling logout would hit a deleted session). (research R-6)
- [X] T021 [P] [US4] Fix `deleteFaceData(userId)` in `frontend/src/services/api.ts`: add `credentials: "include"` to the fetch and parse errors on non-2xx responses (return the parsed `{error: {code, message}}` body instead of raw `resp.json()`). (research Codebase Context gap)
- [X] T022 [US4] Add the "Eliminar mis datos" button + lightweight confirmation dialog ("Esta acción eliminará tu perfil y plantilla facial de forma permanente. ¿Continuar?") + processing state to `frontend/src/pages/Dashboard.tsx`. Button and dialog are keyboard-accessible with descriptive accessible names; state communication does not rely exclusively on color (PRD §10). (research R-8; depends on T020, T021)
- [X] T023 [US4] Implement post-deletion handling in `frontend/src/pages/Dashboard.tsx`: on `200` → `clearSession()` + release camera stream + discard held mood/age analysis results + `navigate("/")`; on `500 internal_error` → actionable error surface with "Reintentar" button + re-enable the button + no full page reload; on `401 unauthenticated` → transition to unauthenticated state + redirect to `/login`; on cancel → no request. (research R-7/R-9; depends on T022)

**Checkpoint**: The deletion UI is navigable, accessible, and correctly handles success + recoverable error + unauthenticated + cancel flows.

---

## Phase 7: User Story 5 - Automated Face-Data Deletion Tests (Priority: P5)

**Goal**: A complete automated test suite covering deletion unit (authorization rule, deletion ordering, error mapping, domain purity), integration (real endpoint + real PostgreSQL + real filesystem — happy path, each authorization failure, `404`, DB-failure rollback, best-effort FS-failure), and contract (`200` shape, status codes `200`/`401`/`403`/`404`/`422`/`500`, pinned error body) cases. Domain portions run without GPU/network/real models.

**Independent Test**: Run the deletion test suite with no GPU and no network; assert all tests pass, that a deliberate contract-violating change to the deletion response shape causes a contract test to fail, and that a deliberate change allowing a mismatched-`userId` deletion causes an integration test to fail.

### Tests for User Story 5 ⚠️

- [X] T024 [P] [US5] Add contract test cases for the full status-code matrix (`200`/`401`/`403`/`404`/`422`/`500`), the pinned error body shape `{"error": {"code", "message"}}`, and the best-effort filesystem-failure path (DB commits → `200` + structured warning logged) in `backend/tests/contract/test_http_contracts.py`.
- [X] T025 [P] [US5] Add integration tests for the DB transaction failure path (→ `500 internal_error` + rollback, no partial DB state) and the best-effort filesystem-failure path (DB commits, FS deletion fails → `200` + warning log) in `backend/tests/integration/test_deletion_integration.py`.
- [X] T026 [P] [US5] Add a domain-purity static check test in `backend/tests/unit/test_deletion_service.py`: assert `backend/src/face_insight/domain/deletion.py` imports only from `.ports`, `.entities`, `.exceptions`, and stdlib — no SQLAlchemy, FastAPI, ML port, or filesystem adapter imports (Principle VII, FR-013/FR-014, SC-008/SC-009).
- [X] T027 [US5] Add negative/regression tests in `backend/tests/`: a deliberate contract-violating change to the deletion response shape causes at least one contract test to fail; a deliberate change allowing a mismatched-`userId` deletion causes at least one integration test to fail (SC-011).

**Checkpoint**: The full deletion test suite (unit + integration + contract + frontend) is green under no-GPU/no-network constraints and catches deliberate regressions.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Observability, documentation, and cleanup affecting multiple user stories.

- [X] T028 [P] Add structured JSON logging for the deletion operation in `backend/src/face_insight/domain/deletion.py` and the route handler: `{type:"deletion", userId:<uuid>, status:"deleted"|"failed", duration_ms:<int>}` and `{type:"deletion_fs_cleanup_warning", userId:<uuid>}` on FS-cleanup failure. No image bytes, embedding vectors, or biometric content logged (FR-016, Principle VIII).
- [X] T029 [P] Verify the `docker compose` stack runs the full deletion flow end-to-end and that the `usuarios/` bind-mount is reused; update `specs/006-delete-face-data/quickstart.md` validation scenarios if any drift is found.
- [X] T030 Run all `quickstart.md` validation scenarios 1-6 end-to-end in `docker compose` (happy path, authorization gating, post-deletion invalidation, DB-failure rollback, best-effort FS failure, automated test suite).
- [X] T031 Code cleanup: remove spec 001 route-stub comments/TODOs in `backend/src/face_insight/api/routes/users.py`, ensure no TODOs remain in the deletion code paths, and confirm the domain layer has zero infra/ML imports.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (domain exceptions + error handlers are required by every story).
- **User Stories (Phases 3-7)**: All depend on Foundational completion.
  - US1 (P1) is the MVP and builds the real endpoint + service + UoW + wiring.
  - US2 (P2) hardens/tests the authorization rejections on top of the US1 route.
  - US3 (P3) verifies post-deletion invalidation — depends on US1 (hard delete).
  - US4 (P4) is frontend-only and can proceed in parallel with US2/US3 once Foundational is done.
  - US5 (P5) consolidates the full test suite — depends on US1 + US2 (endpoint + authz exist).
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. No dependencies on other stories. (MVP)
- **US2 (P2)**: Starts after Foundational. Builds on the US1 route handler (T011) for the authz check, but is independently testable by calling the endpoint with no/mismatched/malformed credentials.
- **US3 (P3)**: Starts after Foundational. Depends on US1's hard delete for the invalidation guarantee, but is independently testable by performing a deletion then probing `/me` and `/face-login`.
- **US4 (P4)**: Starts after Foundational. Frontend-only — no backend dependency beyond the existing endpoint contract. Independently testable with a mocked fetch.
- **US5 (P5)**: Starts after Foundational. Consolidates tests across US1-US4; depends on the endpoint (US1) and authz (US2) existing for integration/contract coverage.

### Within Each User Story

- Tests (where included) MUST be written and FAIL before implementation (Red-Green-Refactor).
- Domain service / UoW before route handler.
- Route handler before frontend integration.
- Story complete before moving to next priority.

### Parallel Opportunities

- All Foundational tasks marked [P] can run in parallel (within Phase 2).
- Once Foundational completes, US1, US2, US3, US4 can start in parallel (US5 follows once US1+US2 exist). With a single developer, proceed sequentially P1 → P2 → P3 → P4 → P5.
- All tests for a user story marked [P] can run in parallel (e.g. T004, T005, T006 for US1).
- US4 frontend tasks T020 and T021 (different files, no dependencies) can run in parallel.
- US5 test tasks T024, T025, T026 (different test files) can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (tests-first, expect FAIL):
Task: "Contract test for 200 deletion happy path in backend/tests/contract/test_http_contracts.py"
Task: "Domain unit test for DeletionService happy path in backend/tests/unit/test_deletion_service.py"
Task: "Integration test for happy-path deletion in backend/tests/integration/test_deletion_integration.py"

# Then implement (sequential — each depends on the prior):
Task: "SqlAlchemyUnitOfWork.delete_user_face_data in backend/src/face_insight/adapters/db/repositories.py"
Task: "MockUnitOfWork.delete_user_face_data in backend/src/face_insight/adapters/mock/"
Task: "DeletionService in backend/src/face_insight/domain/deletion.py"
Task: "get_deletion_service resolver + app.state wiring in api/dependencies.py + main.py"
Task: "Real delete_face_data route handler in backend/src/face_insight/api/routes/users.py"
```

## Parallel Example: User Story 4

```bash
# Frontend tests-first:
Task: "DashboardDelete.test.tsx flow test in frontend/tests/"

# Then parallel (different files, no dependencies):
Task: "clearSession() in frontend/src/context/SessionContext.tsx"
Task: "deleteFaceData fix in frontend/src/services/api.ts"
# Then sequential UI work in Dashboard.tsx.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify scaffolding).
2. Complete Phase 2: Foundational (domain exceptions + error handlers — CRITICAL, blocks all stories).
3. Complete Phase 3: User Story 1 (real `DELETE` endpoint happy path).
4. **STOP and VALIDATE**: Test User Story 1 independently — `200 {userId, status:"deleted"}`, DB rows gone, folder gone, cookie cleared.
5. Demo the "right to be forgotten" happy path via `quickstart.md` Scenario 1.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → test independently → demo MVP (working deletion endpoint).
3. Add US2 → test independently → demo authorization gating (401/403/422).
4. Add US3 → test independently → demo verified "right to be forgotten".
5. Add US4 → test independently → demo user-facing deletion UI + post-delete redirect to `/`.
6. Add US5 → run full suite → confirm green under no-GPU/no-network.
7. Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together.
2. Once Foundational is done:
   - Developer A: US1 (backend endpoint + service + UoW)
   - Developer B: US4 (frontend UI — fully independent, frontend-only)
3. After US1 lands:
   - Developer A: US2 (authz hardening + rejection tests)
   - Developer B: US3 (post-deletion invalidation tests)
4. US5 consolidates the full test suite once US1 + US2 are merged.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to a specific user story for traceability.
- Each user story is independently completable and testable.
- Tests are mandated by the constitution (Quality Gates §4/§5/§6/§7) — write them FIRST and verify they FAIL before implementation.
- Domain tests use mocks for all ports (Principle VII) and run without GPU/network/real models.
- This spec introduces NO new persistent entities and NO new top-level directories — it fills in the existing route stub, extends the existing `SqlAlchemyUnitOfWork`, and extends the existing Dashboard.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence.
