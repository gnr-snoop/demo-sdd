---

description: "Task list for Production DB Wiring + APP_MODE Selector"
---

# Tasks: Production DB Wiring + APP_MODE Selector

**Input**: Design documents from `/specs/007-production-db-wiring/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: No `.specify/memory/constitution.md` present. Tests are not mandated by a constitution, but the spec itself mandates an automated test suite (FR-014, FR-015) and User Story 5 is explicitly the test story. Tests are therefore included (written first per story where practical).

**Organization**: Tasks are grouped by user story (P1→P5) to enable independent implementation and testing of each story. The implementation order matches the priority order: US1 (production wiring function) → US2 (selector that dispatches to it) → US3 (startup/compose) → US4 (mock non-regression) → US5 (test completeness).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/` (this spec touches only `backend/` + `docker-compose.yml`; `frontend/` is unchanged — scope boundary FR-017)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization for the new test-only dependency.

- [X] T001 Add `testcontainers` to `backend/pyproject.toml` under `[project.optional-dependencies] test` (test-only; not a runtime stack change — Constitution Principle III)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `APP_MODE` configuration setting is the seam every user story depends on. It MUST exist and validate before any wiring/selector/startup work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `app_mode: str = "mock"` field with pydantic `field_validator` (normalize `.strip().lower()`, reject values not in `{"production","mock"}` with `ValueError("APP_MODE must be 'production' or 'mock'; got '<value>'")`) to `backend/src/face_insight/config.py` `Settings` (FR-001, FR-005; research R-1)

**Checkpoint**: `APP_MODE` setting loads, defaults to `mock`, fails fast on invalid values — user story implementation can now begin.

---

## Phase 3: User Story 1 - Real Persistence of Users, Templates & Sessions in Production Mode (Priority: P1) 🎯 MVP

**Goal**: In production mode, onboarding commits real `User`+`FaceTemplate` rows, face-login commits a real `AuthSession` row, and `GET /api/auth/me` reads the session — all from PostgreSQL, surviving across requests and an app restart.

**Independent Test**: Start the app with `APP_MODE=production` against a fresh PostgreSQL test container. `POST /api/onboarding` → `POST /api/auth/face-login` → `GET /api/auth/me`; inspect PostgreSQL out-of-band and assert the rows exist. Stop the app, restart against the same PostgreSQL, confirm `GET /api/auth/me` with the old cookie still resolves (cross-restart persistence, FR-009).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T003 [US1] Create `PostgresContainer` session-scoped fixture + `RUN_PROD_PERSISTENCE_TESTS` skip flag (auto-skip when Docker unavailable) in `backend/tests/integration/test_production_wiring.py` (FR-015; research R-7)
- [X] T004 [P] [US1] Integration test: cross-request persistence — onboarding → face-login → `/api/auth/me` as independent requests, then out-of-band DB inspection asserting `User`/`FaceTemplate`/`AuthSession` rows exist in `backend/tests/integration/test_production_wiring.py` (FR-008, SC-001/SC-002)
- [X] T005 [P] [US1] Integration test: cross-restart persistence — build a second `create_app()` against the same container DB, call `GET /api/auth/me` with the first app's session cookie, assert same user in `backend/tests/integration/test_production_wiring.py` (FR-009, SC-003)

### Implementation for User Story 1

- [X] T006 [US1] Implement `wire_production_adapters(app)` in `backend/src/face_insight/main.py`: build session factory via `adapters.db.session.get_session_factory()` from `settings.database_url`, instantiate `SqlAlchemyUserRepository`/`SqlAlchemyFaceTemplateRepository`/`SqlAlchemySessionManager`/`SqlAlchemyUnitOfWork`, keep mock ML adapters (`MockDetector`/`MockEmbedder`/`MockAgeEstimator`/`MockMoodEstimator`), use real `FilesystemImageStorage`, rebuild `OnboardingService`/`LoginService`/`MoodService`/`AgeService`/`DeletionService`, run startup `SELECT 1` probe (fail-fast `RuntimeError` on unreachable/malformed/unset `DATABASE_URL`), store engine on `app.state.db_engine` (FR-004, FR-006, FR-008; research R-3/R-4)
- [X] T007 [US1] Add structured JSON log line `{"event":"db_ready","status":true|false}` after the startup DB probe in `backend/src/face_insight/main.py` (FR-016; research R-8)

**Checkpoint**: `wire_production_adapters` wires real DB adapters + mock ML and probes the DB at startup. Production persistence is functional and testable independently (tests T004/T005 should pass).

---

## Phase 4: User Story 2 - APP_MODE Configuration Selector (Priority: P2)

**Goal**: `select_wiring(app, app_mode)` dispatches exactly once at composition time: `mock` → `wire_mock_adapters`, `production` → `wire_production_adapters`. `create_app()` calls the selector instead of `wire_mock_adapters` directly.

**Independent Test**: (a) `APP_MODE` unset → mock adapters wired, no PostgreSQL required; (b) `APP_MODE=production` + reachable DB → real `SqlAlchemy*` repos + mock ML; (c) `APP_MODE=invalid` → `ValueError` at settings construction.

### Tests for User Story 2 ⚠️

- [X] T008 [P] [US2] Unit tests: `select_wiring("mock")` wires `Mock*` repos + no `db_engine`; `select_wiring("production")` with reachable URL wires `SqlAlchemy*` repos + mock ML + `db_engine`; selector called exactly once in `backend/tests/unit/test_wiring_selector.py` (C-SEL-1/C-SEL-2/C-SEL-3, FR-002/FR-003/FR-004)

### Implementation for User Story 2

- [X] T009 [US2] Implement `select_wiring(app: FastAPI, app_mode: str) -> None` in `backend/src/face_insight/main.py` dispatching `"mock"` → `wire_mock_adapters(app)`, `"production"` → `wire_production_adapters(app)` (depends on T006; FR-002; research R-2)
- [X] T010 [US2] Update `create_app()` in `backend/src/face_insight/main.py` to call `select_wiring(app, get_settings().app_mode)` once after `register_routes(app)`, replacing the unconditional `wire_mock_adapters(app)` call (FR-002; research R-2)
- [X] T011 [US2] Add structured JSON log line `{"event":"wiring_selected","app_mode":"production|mock"}` at selector dispatch in `backend/src/face_insight/main.py` (FR-016; research R-8)

**Checkpoint**: The selector is wired into the app factory. `APP_MODE=mock` (unset) behaves identically to specs 001-006; `APP_MODE=production` wires real persistence. User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Production Startup: DB Session Factory, Migrations & Compose Healthcheck Ordering (Priority: P3)

**Goal**: Production startup constructs the async DB session factory from `DATABASE_URL`, runs Alembic migrations to head as a pre-start entrypoint step gated on `APP_MODE=production`, and the docker-compose backend waits on PostgreSQL healthy with `DATABASE_URL` pointing to the compose Postgres service. `/health` and `/readyz` become mode-aware.

**Independent Test**: `docker compose up` from a clean state → backend waits on PostgreSQL healthy, migrations apply before the app serves, `DATABASE_URL` points to the compose Postgres, `GET /health` reports healthy with DB connectivity.

### Tests for User Story 3 ⚠️

- [X] T012 [P] [US3] Startup unit test: assert DB session factory (async engine + sessionmaker) is constructed from `DATABASE_URL` in production mode and `app.state.db_engine` is set; assert no engine in mock mode in `backend/tests/unit/test_wiring_selector.py` (C-START-1, FR-006)

### Implementation for User Story 3

- [X] T013 [US3] Gate migrations on `APP_MODE=production` and set `APP_MODE=production` + `DATABASE_URL=postgresql+asyncpg://faceinsight:faceinsight@postgres:5432/faceinsight` on the backend service in `docker-compose.yml` (entrypoint `command: sh -c "if [ \"$APP_MODE\" = \"production\" ]; then alembic upgrade head; fi && uvicorn ..."`; FR-007/FR-010; research R-5)
- [X] T014 [P] [US3] Add `make migrate` (→ `alembic upgrade head`) documented manual fallback to `backend/Makefile` (FR-011; research R-5)
- [X] T015 [US3] Make `/health` mode-aware in `backend/src/face_insight/main.py`: mock → `{"status":"healthy"}` (no DB check); production → `{"status":"healthy","db":true}` with `SELECT 1` against `app.state.db_engine`, `503` `{"status":"unhealthy","db":false}` on ping failure (C-HLTH-1/2/3, FR-010; research R-6)
- [X] T016 [US3] Make `/readyz` mode-aware in `backend/src/face_insight/main.py`: mock → `{"status":"ready","db":null}`; production → `SELECT 1` ping with `db: true|false` and 503 on failure (C-HLTH-4, FR-010; research R-6)

**Checkpoint**: The containerized production stack starts correctly ordered, migrated, and DB-health-aware. User Stories 1, 2, AND 3 all work independently.

---

## Phase 6: User Story 4 - Mock Mode Preserved Unchanged (Dev/Demo Safety & Test Non-Regression) (Priority: P4)

**Goal**: `APP_MODE=mock` (or unset) produces behavior identical to specs 001-006: mock adapters wired, no PostgreSQL required, existing domain/contract/unit suites pass unchanged. Mock adapters retained verbatim.

**Independent Test**: (a) Run existing domain/contract/unit suites with no changes → all pass; (b) start app with `APP_MODE` unset → no PostgreSQL required, behaves as specs 001-006; (c) inspect mock adapter source → unchanged from spec 001.

### Tests for User Story 4 ⚠️

- [X] T017 [P] [US4] Regression test: run existing `backend/tests/domain`, `backend/tests/contract`, `backend/tests/unit` suites unchanged in mock mode and assert all pass (no test file modified) — recorded as a regression guard in `backend/tests/integration/test_production_wiring.py` (FR-013, SC-012)

### Implementation for User Story 4

- [X] T018 [US4] Verify `wire_mock_adapters` in `backend/src/face_insight/main.py` leaves `app.state.db_engine` unset/`None` (no code change to mock adapters — assert the mock path requires no DB; FR-003/FR-012/FR-017)

**Checkpoint**: Mock mode is non-regressed; existing suites pass unchanged. User Stories 1-4 all work independently.

---

## Phase 7: User Story 5 - Automated Production-Persistence & Wiring-Selector Tests (Priority: P5)

**Goal**: A complete automated test suite covers production persistence (cross-request + cross-restart), selector wiring (mock/production/invalid), startup (session factory + migrations), and mock-mode non-regression. Domain/contract/unit portions run without GPU/network; integration tests are skippable with a documented flag.

**Independent Test**: Run the wiring test suite → all pass. Introduce a deliberate regression (production wires in-memory repos) → at least one production-persistence test fails.

### Tests for User Story 5 ⚠️

- [X] T019 [P] [US5] Selector test: invalid `APP_MODE` (e.g. `staging`, `prod`, `""`) raises `ValueError` at `Settings` construction before any app is built in `backend/tests/unit/test_wiring_selector.py` (C-SEL-4, FR-005, SC-006)
- [X] T020 [P] [US5] Startup integration test: migrations apply to head before the app serves in production mode; no migration/DB step in mock mode in `backend/tests/integration/test_production_wiring.py` (C-START-4, FR-007, SC-008)
- [X] T021 [US5] Deliberate-regression assertion: temporarily make `APP_MODE=production` delegate to `wire_mock_adapters` and assert the cross-restart or out-of-band DB inspection test fails, then revert in `backend/tests/integration/test_production_wiring.py` (FR-014, SC-014)
- [X] T022 [US5] Documented skip: assert domain/contract/unit portions pass with no GPU and no network, and integration tests skip with a documented reason when `RUN_PROD_PERSISTENCE_TESTS=0` or Docker is unavailable in `backend/tests/integration/test_production_wiring.py` (FR-015, SC-015)

**Checkpoint**: The full wiring test suite is green, reproducible, and catches persistence regressions. All user stories are independently functional and verified.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [X] T023 [P] Documentation: update `backend/README.md` (or docs) with `APP_MODE` selector usage, `make migrate` fallback, and `RUN_PROD_PERSISTENCE_TESTS` skip flag (FR-011/FR-015)
- [X] T024 Run `specs/007-production-db-wiring/quickstart.md` scenarios 1-8 end-to-end validation
- [X] T025 Code cleanup: verify no image/embedding/biometric data in logs — only structured JSON (`wiring_selected`, `db_ready`) in `backend/src/face_insight/main.py` (FR-016, SC-016)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001) — BLOCKS all user stories (`app_mode` setting is the seam).
- **User Story 1 (Phase 3)**: Depends on Foundational (T002). Builds `wire_production_adapters` — the production wiring function US2's selector dispatches to.
- **User Story 2 (Phase 4)**: Depends on US1 (T006 `wire_production_adapters`). Builds `select_wiring` + updates `create_app`.
- **User Story 3 (Phase 5)**: Depends on US2 (T010 `create_app` uses selector). Adds compose gating + mode-aware probes.
- **User Story 4 (Phase 6)**: Depends on US2 (T009 selector delegates to unchanged `wire_mock_adapters`). Mostly a non-regression verification.
- **User Story 5 (Phase 7)**: Depends on US1-US4 (tests exercise all wiring paths). Completes the test suite.
- **Polish (Phase 8)**: Depends on all user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational only. Self-contained: `wire_production_adapters` + its integration tests. Independently testable by calling `wire_production_adapters` directly.
- **User Story 2 (P2)**: Depends on US1 (`wire_production_adapters`). The selector dispatches to it. Independently testable via `select_wiring` unit tests.
- **User Story 3 (P3)**: Depends on US2 (selector in `create_app`). Adds compose + probes. Independently testable via `docker compose up`.
- **User Story 4 (P4)**: Depends on US2 (selector must not alter mock path). Independently testable via existing suites + mock startup.
- **User Story 5 (P5)**: Depends on US1-US4. Cross-cutting test completeness. Independently testable via the suite + deliberate regression.

### Within Each User Story

- Tests (where included) MUST be written and FAIL before implementation.
- Wiring functions before selector; selector before app factory change.
- Compose/entrypoint changes before probe refinements.
- Story complete before moving to next priority.

### Parallel Opportunities

- T001 (Setup) is independent.
- T004 and T005 (US1 integration tests) can be written in parallel once T003 (fixture) exists.
- T008 (US2 unit tests) and T012 (US3 startup unit tests) target different files — can run in parallel.
- T014 (`Makefile`) is independent of T013/T015/T016 (different files) — can run in parallel within US3.
- T017 (US4 regression test) and T019 (US5 selector test) target different files — can run in parallel.
- T019, T020 can run in parallel (different files) within US5.
- **Note**: `backend/tests/integration/test_production_wiring.py` is built incrementally across US1/US3/US4/US5 — tasks targeting it cannot be parallelized across stories (same file).

---

## Parallel Example: User Story 1

```bash
# After T003 (fixture) exists, launch the two integration tests together:
Task: "T004 Integration test: cross-request persistence in backend/tests/integration/test_production_wiring.py"
Task: "T005 Integration test: cross-restart persistence in backend/tests/integration/test_production_wiring.py"
```

## Parallel Example: User Story 3

```bash
# Different files — run in parallel:
Task: "T014 Add make migrate fallback to backend/Makefile"
Task: "T013 Gate migrations + set APP_MODE=production in docker-compose.yml"
# Then sequentially (same file main.py):
Task: "T015 Make /health mode-aware in backend/src/face_insight/main.py"
Task: "T016 Make /readyz mode-aware in backend/src/face_insight/main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001 — add `testcontainers`)
2. Complete Phase 2: Foundational (T002 — `app_mode` setting) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T003-T007 — `wire_production_adapters` + persistence tests)
4. **STOP and VALIDATE**: Run `RUN_PROD_PERSISTENCE_TESTS=1 pytest backend/tests/integration/test_production_wiring.py -q` — assert cross-request + cross-restart persistence passes.
5. Deploy/demo if ready (production persistence works by calling `wire_production_adapters` directly).

### Incremental Delivery

1. Complete Setup + Foundational → `APP_MODE` setting ready.
2. Add User Story 1 → `wire_production_adapters` + persistence tests → Validate (MVP!).
3. Add User Story 2 → `select_wiring` + `create_app` selector → Validate (mock + production modes via selector).
4. Add User Story 3 → compose gating + mode-aware probes → Validate (`docker compose up` one-command path).
5. Add User Story 4 → mock non-regression → Validate (existing suites unchanged).
6. Add User Story 5 → test completeness + deliberate-regression assertion → Validate (suite green, regression caught).
7. Polish → docs + quickstart validation + log hygiene.
8. Each story adds value without breaking previous stories (mock mode default preserves backward compatibility).

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001, T002).
2. Once Foundational is done:
   - Developer A: User Story 1 (T003-T007) — `wire_production_adapters` + integration tests.
   - (US2 depends on US1's T006, so US2 starts after T006; US3/US4/US5 chain after US2.)
3. Once US1's `wire_production_adapters` (T006) is done:
   - Developer B: User Story 2 (T008-T011) — selector + app factory.
4. Once US2's `create_app` change (T010) is done:
   - Developer C: User Story 3 compose/probes (T012-T016) and User Story 4 regression (T017-T018) — mostly independent files.
   - Developer D: User Story 5 test completeness (T019-T022) — fills in remaining test cases.
5. Stories complete and integrate independently; mock mode default guarantees non-regression throughout.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Each user story should be independently completable and testable.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
- **Scope boundaries (FR-012/FR-017)**: no new endpoints, domain entities, ports, mock-adapter changes, frontend changes, or existing-test changes. This spec is pure composition/wiring.
- **Shared test file caveat**: `backend/tests/integration/test_production_wiring.py` is authored incrementally across US1/US3/US4/US5 — do not parallelize tasks that edit the same file.
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence.
