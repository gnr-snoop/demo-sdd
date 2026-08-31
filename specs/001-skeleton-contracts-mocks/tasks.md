---

description: "Task list for Skeleton, Contracts, Ports & Mocks (Fase 1)"
---

# Tasks: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Input**: Design documents from `/specs/001-skeleton-contracts-mocks/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: No `.specify/memory/constitution.md` present; tests are optional per the generic rule, BUT this spec explicitly mandates an automated contract + domain test suite (FR-016, FR-017, SC-008, SC-009) as User Story 6. Test tasks are therefore included for US6 and as inline smoke tests where a story is naturally test-first (e.g. frontend routing in US2).

**Organization**: Tasks are grouped by user story (P1→P6) to enable independent implementation and testing of each story. The spec is itself a scaffolding spec — stories are largely orthogonal slices of the skeleton.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app (monorepo)**: `backend/src/`, `frontend/src/` at repository root
- `docker-compose.yml`, `backend/`, `frontend/`, `usuarios/` at repo root
- Paths below follow the structure pinned in `plan.md` §Project Structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure — the repo skeleton every later phase and story builds on.

- [X] T001 Create monorepo directory skeleton: `backend/`, `frontend/`, `usuarios/` (with `usuarios/.gitkeep`)
- [X] T002 [P] Create `docker-compose.yml` at repo root with three services (`backend`, `frontend`, `postgres`), named volume for PG data, `usuarios/` bind mount
- [X] T003 [P] Create `backend/Dockerfile` (Python 3.11 base, install `pyproject.toml`, entrypoint runs `alembic upgrade head` then `uvicorn`)
- [X] T004 [P] Create `frontend/Dockerfile` (Node base, `npm install`, Vite dev server on port 5173)
- [X] T005 [P] Create `backend/pyproject.toml` with deps: FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0 async, Alembic, psycopg, structlog, httpx, pytest, pytest-asyncio
- [X] T006 [P] Create `frontend/package.json` with deps: react, react-dom, react-router-dom, @vitejs/plugin-react, vitest, @testing-library/react
- [X] T007 [P] Create `frontend/vite.config.ts`, `frontend/index.html`, `frontend/tsconfig.json`
- [X] T008 [P] Create `backend/alembic.ini` (Alembic config pointing at `backend/alembic/`)
- [X] T009 [P] Create root `.gitignore` (venvs, `node_modules/`, `__pycache__/`, `.venv/`, `dist/`, `.pytest_cache/`)

**Checkpoint**: Repo skeleton exists; `docker compose build` can succeed (services not yet functional).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared application shells that MUST exist before any user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T010 Create `backend/src/face_insight/config.py` — Pydantic `Settings` (BaseSettings) exposing `verification_threshold`, `embedding_model_version`, `detector_model_version`, `age_model_version`, `mood_model_version`, `image_max_bytes`, `image_format`, `image_max_long_edge`; env-overridable (FR-015, research R-9)
- [X] T011 [P] Create `backend/src/face_insight/logging.py` — structlog JSON renderer config (research R-7)
- [X] T012 Create `backend/src/face_insight/main.py` — FastAPI app, `/health` liveness, `/readyz` readiness (DB connectivity check, 503 if down), route-registration hook
- [X] T013 [P] Create `frontend/src/main.tsx` and `frontend/src/App.tsx` — React root mounting the router
- [X] T014 Create `frontend/src/router.tsx` — `react-router-dom` v6 base `Router` with a placeholder route map (routes filled in US2)

**Checkpoint**: Foundation ready — backend app boots with `/health`+`/readyz`; frontend app boots with a mounted router. User story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Runnable Demo Stack (Priority: P1) 🎯 MVP

**Goal**: A developer/demo audience member can bring up the entire app — backend, frontend, PostgreSQL — with a single `docker compose up --build`, and all three services become healthy on their documented ports with no host-native runtime install (SC-001).

**Independent Test**: From a clean checkout with only Docker installed, run `docker compose up --build`; verify `curl http://localhost:8000/health` → `{"status":"healthy"}`, `curl http://localhost:8000/readyz` → `{"status":"ready","db":true}`, and `http://localhost:5173/` returns 200.

### Implementation for User Story 1

- [X] T015 [US1] Add `postgres` service healthcheck (`pg_isready`) to `docker-compose.yml`
- [X] T016 [US1] Configure `backend` `depends_on` `postgres` with `service_healthy` condition in `docker-compose.yml`
- [X] T017 [US1] Set `backend` container entrypoint/command to run `alembic upgrade head` then `uvicorn face_insight.main:app --host 0.0.0.0 --port 8000`
- [X] T018 [US1] Expose ports in `docker-compose.yml`: backend 8000, frontend 5173, postgres 5432
- [X] T019 [US1] Add `usuarios/` bind mount `./usuarios:/app/usuarios:rw` to the `backend` service in `docker-compose.yml` (Principle V)
- [X] T020 [US1] Wire `/readyz` in `backend/src/face_insight/main.py` to check DB connectivity and return 503 when DB down (research R-7)
- [X] T021 [US1] Create `backend/tests/integration/test_stack.py` smoke test asserting `/health` and `/readyz` return healthy when the stack is up

**Checkpoint**: `docker compose up --build` brings the full stack to healthy; US1 independently testable via Scenario 1 of `quickstart.md`.

---

## Phase 4: User Story 2 — Navigable App Skeleton with Four Views (Priority: P2)

**Goal**: A visitor can navigate between `/`, `/onboarding`, `/login`, and `/dashboard` with in-app navigation; `/dashboard` has a placeholder route-protection guard that redirects unauthenticated visitors to `/login` (FR-003, FR-004, SC-002).

**Independent Test**: Start the frontend, click through each nav target, and directly visit `/dashboard`; confirm the redirect to `/login` and that all four routes render without a full page reload.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T022 [P] [US2] Create `frontend/src/__tests__/router.test.tsx` (vitest + @testing-library/react): asserts all four routes render and `/dashboard` redirects to `/login` when no session placeholder

### Implementation for User Story 2

- [X] T023 [P] [US2] Create `frontend/src/context/SessionContext.tsx` — in-memory `isAuthenticated` flag provider (spec Clarification; research R-6)
- [X] T024 [P] [US2] Create `frontend/src/components/ProtectedRoute.tsx` — reads `SessionContext`, redirects to `/login` when unauthenticated
- [X] T025 [P] [US2] Create `frontend/src/components/Nav.tsx` — navigation links to the four views
- [X] T026 [P] [US2] Create `frontend/src/pages/Welcome.tsx` placeholder view
- [X] T027 [P] [US2] Create `frontend/src/pages/Onboarding.tsx` placeholder view
- [X] T028 [P] [US2] Create `frontend/src/pages/Login.tsx` placeholder view
- [X] T029 [P] [US2] Create `frontend/src/pages/Dashboard.tsx` placeholder view
- [X] T030 [US2] Wire the four routes (`/`, `/onboarding`, `/login`, `/dashboard` wrapped in `ProtectedRoute`) in `frontend/src/router.tsx`
- [X] T031 [P] [US2] Create `frontend/src/services/api.ts` — fetch wrapper scaffold for the 7 backend endpoints (consumed in later specs)

**Checkpoint**: All four routes render and are navigable; `/dashboard` redirects unauthenticated visitors to `/login`. US2 independently testable via Scenario 2 of `quickstart.md`.

---

## Phase 5: User Story 3 — Defined HTTP Contract Endpoints (Priority: P3)

**Goal**: The backend exposes all seven PRD §8 endpoints as deterministic stub/mock handlers returning the documented request/response shapes and status codes; protected endpoints reject requests lacking a session placeholder (FR-005, FR-006, FR-007, FR-018, SC-003).

**Independent Test**: Call each of the seven endpoints with a well-formed request and assert the response status code and body match the contract in `contracts/`; call protected endpoints without a session placeholder and assert 401.

### Implementation for User Story 3

- [X] T032 [P] [US3] Create `backend/src/face_insight/api/schemas.py` — Pydantic v2 request/response models for all 7 endpoints per `contracts/*.md`
- [X] T033 [P] [US3] Create `backend/src/face_insight/api/dependencies.py` — session-placeholder FastAPI dependency returning 401 when the session marker is absent (FR-006)
- [X] T034 [P] [US3] Create `backend/src/face_insight/api/routes/onboarding.py` — `POST /api/onboarding` → 201 with `{userId, identifier, status:"enrolled"}` deterministic mock
- [X] T035 [P] [US3] Create `backend/src/face_insight/api/routes/auth.py` — `POST /api/auth/face-login` (200 authenticated / 401 generic non-revealing failure), `GET /api/auth/me` (session-protected), `POST /api/auth/logout` (session-protected)
- [X] T036 [P] [US3] Create `backend/src/face_insight/api/routes/analysis.py` — `POST /api/analysis/mood` and `POST /api/analysis/age`, session-protected, returning documented mock shapes (`label`,`confidence`,`disclaimer` / `estimatedAge`,`range`,`disclaimer`)
- [X] T037 [P] [US3] Create `backend/src/face_insight/api/routes/users.py` — `DELETE /api/users/{userId}/face-data` (UUID path param, session-protected, mock success)
- [X] T038 [US3] Register all route routers in `backend/src/face_insight/main.py`
- [X] T039 [US3] Ensure `POST /api/auth/face-login` failure response is generic and non-revealing (FR-007/FR-018) — no identifier-existence leak
- [X] T040 [US3] Ensure malformed requests (missing required field, non-image payload) return 422 with the documented validation error shape

**Checkpoint**: All seven endpoints respond per contract; protected endpoints reject without session placeholder. US3 independently testable via Scenario 3 of `quickstart.md`.

---

## Phase 6: User Story 4 — Domain Models & Hexagonal Ports with Mock Adapters (Priority: P4)

**Goal**: The domain layer contains the four pure PRD §7 entities with no infra/ML imports; the 8 ports are declared as `typing.Protocol`; a complete set of deterministic hardcoded-constant mock adapters implements every port (FR-008, FR-009, FR-010, FR-011, FR-012, SC-004, SC-005).

**Independent Test**: Instantiate the domain wired to mock adapters; exercise entity constructors and port calls; assert outputs are deterministic and no model/network/GPU is touched.

### Implementation for User Story 4

- [X] T041 [P] [US4] Create `backend/src/face_insight/domain/entities.py` — pure `User`, `FaceTemplate`, `AuthSession`, `AnalysisRequest` with UUID v4 ids, enum validation (`UserStatus`, `AnalysisType`, `AnalysisStatus`), injected `now` callable (data-model.md)
- [X] T042 [P] [US4] Create `backend/src/face_insight/domain/result_types.py` — `DetectionResult`, `BoundingBox`, `MoodResult`, `AgeResult`, `Embedding` value objects
- [X] T043 [US4] Create `backend/src/face_insight/domain/ports.py` — 8 `typing.Protocol` interfaces: `Detector`, `Embedder`, `AgeEstimator`, `MoodEstimator`, `SessionManager`, `UserRepository`, `FaceTemplateRepository`, `ImageStorage` (data-model.md Ports table)
- [X] T044 [P] [US4] Create `backend/src/face_insight/adapters/mock/__init__.py` re-exporting all 8 mock adapters
- [X] T045 [P] [US4] Create `backend/src/face_insight/adapters/mock/detector.py` — `MockDetector` returning `DetectionResult(face_count=1, boxes=[BoundingBox(0,0,100,100)], score=0.99)`
- [X] T046 [P] [US4] Create `backend/src/face_insight/adapters/mock/embedder.py` — `MockEmbedder` returning 128-dim vector of `0.1` repeats, `model_version="mock-embed-v0"`
- [X] T047 [P] [US4] Create `backend/src/face_insight/adapters/mock/age_estimator.py` — `MockAgeEstimator` returning `estimated_age=32, range=(27,37), model_version="mock-age-v0"`
- [X] T048 [P] [US4] Create `backend/src/face_insight/adapters/mock/mood_estimator.py` — `MockMoodEstimator` returning `label="neutral", confidence=0.74, model_version="mock-mood-v0"`
- [X] T049 [P] [US4] Create `backend/src/face_insight/adapters/mock/session_manager.py` — `MockSessionManager` (in-memory, deterministic)
- [X] T050 [P] [US4] Create `backend/src/face_insight/adapters/mock/user_repository.py` — `MockUserRepository` (in-memory dict, `FIXED_USER_ID = UUID("00000000-0000-4000-8000-000000000001")`)
- [X] T051 [P] [US4] Create `backend/src/face_insight/adapters/mock/face_template_repository.py` — `MockFaceTemplateRepository` (in-memory, one template per user)

- [X] T051b [P] [US4] Create `backend/src/face_insight/adapters/mock/image_storage.py` — `MockImageStorage` implementing the `ImageStorage` port, writing to a temp dir mirroring `usuarios/<user-id>/pictures.jpg` (data-model.md mock constants). Satisfies FR-010/SC-005 ("every declared port has a deterministic mock adapter").

- [X] T052 [US4] Wire mock adapters (all 8, including MockImageStorage) as the default port implementations in `backend/src/face_insight/main.py` for the Fase 1 stub endpoints
**Checkpoint**: Domain is pure (no infra imports); every port has a deterministic mock. US4 independently testable via `tests/domain/` (built in US6).

---

## Phase 7: User Story 5 — Persistent Storage Setup (Priority: P5)

**Goal**: Alembic migrations create the four entity tables idempotently; a filesystem image-storage adapter writes/reads `usuarios/<user-id>/pictures.jpg` via a bind mount identical inside and outside the container (FR-013, FR-014, SC-006, SC-007).

**Independent Test**: Apply migrations to a fresh DB and confirm the four tables with documented columns; re-apply and confirm idempotency; write and read back an image via the FS adapter and confirm the `usuarios/<user-id>/pictures.jpg` path.

### Implementation for User Story 5

- [X] T053 [US5] Create `backend/alembic/env.py` — async SQLAlchemy Alembic env config, `target_metadata` from ORM models (research R-3)
- [X] T054 [P] [US5] Create `backend/src/face_insight/adapters/db/models.py` — SQLAlchemy ORM models for `User`, `FaceTemplate`, `AuthSession`, `AnalysisRequest` with UUID PKs, FKs `ON DELETE CASCADE`, `UNIQUE(user_id)` on `face_templates` (data-model.md Migrations)
- [X] T055 [US5] Create `backend/alembic/versions/0001_initial_schema.py` — initial revision creating `users`, `face_templates`, `auth_sessions`, `analysis_requests`; `down_revision = None`
- [X] T056 [US5] Create `backend/src/face_insight/adapters/db/repositories.py` — SQLAlchemy `UserRepository` and `FaceTemplateRepository` adapters implementing the domain ports
- [X] T057 [US5] Create `backend/src/face_insight/adapters/fs/image_storage.py` — filesystem `ImageStorage` adapter writing/reading `usuarios/<user-id>/pictures.jpg` (Principle V)
- [X] T058 [US5] Create `backend/tests/integration/test_persistence.py` — migrations create 4 tables (idempotent re-apply); FS adapter write/read round-trip at the documented path

**Checkpoint**: Migrations apply idempotently to create the 4 tables; FS adapter round-trips images at `usuarios/<user-id>/pictures.jpg`. US5 independently testable via Scenario 4 (integration portion) of `quickstart.md`.

---

## Phase 8: User Story 6 — Automated Contract & Domain Tests (Priority: P6)

**Goal**: An automated test suite covers the HTTP contracts of all seven endpoints and the behavior of the domain entities and mock adapters; the entire suite runs without GPU, network, or real ML models and is byte-identical across repeated runs (FR-016, FR-017, SC-008, SC-009, SC-005).

**Independent Test**: Run the suite in an environment with no GPU and no network; assert all contract and domain tests pass; run twice and `diff` for byte-identical output; introduce a deliberate contract violation and confirm a test fails.

### Implementation for User Story 6

- [X] T059 [P] [US6] Create `backend/tests/conftest.py` — pytest fixtures (FastAPI app, `httpx.AsyncClient`, mock adapter wiring, no GPU/network)
- [X] T060 [P] [US6] Configure `pytest-asyncio` in `backend/pyproject.toml` and ensure the suite runs without GPU/network
- [X] T061 [P] [US6] Create `backend/tests/contract/test_http_contracts.py` — all 7 endpoints × request/response shape + status code assertions via `httpx.AsyncClient` (FR-016)
- [X] T062 [P] [US6] Create `backend/tests/domain/test_entities.py` — entity construction, UUID v4 ids, enum validation (FR-017)
- [X] T063 [P] [US6] Create `backend/tests/domain/test_mock_adapters.py` — every port's mock returns deterministic hardcoded constants; running twice yields byte-identical results (SC-005)
- [X] T064 [US6] Add a contract-violation test in `backend/tests/contract/test_http_contracts.py` confirming a deliberate response-shape change (e.g. `status:"active"` instead of `"enrolled"`) fails at least one assertion (SC-009)

**Checkpoint**: Full contract + domain suite green with no GPU/network; determinism and violation-detection verified. US6 independently testable via Scenarios 4, 5, 6 of `quickstart.md`.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation.

- [X] T065 [P] Add SC-004 static check: a test/script asserting `backend/src/face_insight/domain/` has no imports from `adapters/`, `api/`, `sqlalchemy`, or any ML package (`yolo`/`torch`/`cv2`)
- [X] T066 [P] Add `backend/tests/README.md` documenting how to run the suite (`docker compose exec backend pytest tests/ -v`)
- [X] T067 [P] Add root `README.md` with quickstart pointer to `specs/001-skeleton-contracts-mocks/quickstart.md`
- [X] T068 Code cleanup and consistent formatting — `ruff`/`black` (backend), `prettier` (frontend)
- [X] T069 Run `quickstart.md` Scenarios 1–7 end-to-end validation against the running stack

**Checkpoint**: All success criteria SC-001 through SC-010 verified; Fase 1 skeleton complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phases 3–8)**: All depend on Foundational phase completion.
  - US1 (Phase 3) wires the compose stack — naturally first since it makes the stack runnable.
  - US2 (Phase 4) and US3 (Phase 5) can proceed in parallel once Foundational is done (frontend vs backend, disjoint files).
  - US4 (Phase 6) is backend-only and disjoint from US2/US3 files — parallelizable.
  - US5 (Phase 7) depends on US4's ORM-facing ports and US3's route registration for the DB-backed wiring; can start in parallel for the migration/FS-adapter files but integrates after US4.
  - US6 (Phase 8) depends on US3 (endpoints to test) and US4 (domain/mocks to test); starts after those land.
- **Polish (Phase 9)**: Depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only — no dependencies on other stories.
- **US2 (P2)**: Foundational only — frontend-only, independent of backend stories.
- **US3 (P3)**: Foundational only — backend-only, independent of frontend stories.
- **US4 (P4)**: Foundational only — backend `domain/` + `adapters/mock/`, disjoint from `api/`.
- **US5 (P5)**: Foundational + US4 (ports to implement) + US3 (route wiring for DB-backed repos) — independently testable via its own integration test.
- **US6 (P6)**: US3 + US4 (subjects under test) — independently testable by running the suite.

### Within Each User Story

- Tests (where included) MUST be written and FAIL before implementation.
- Models before services; services before endpoints; core before integration.
- Story complete before moving to next priority.

### Parallel Opportunities

- All Setup tasks marked [P] (T002–T009) can run in parallel.
- All Foundational tasks marked [P] (T011, T013) can run in parallel within Phase 2.
- Once Foundational completes, US2 / US3 / US4 can be worked on in parallel by different developers (disjoint file sets).
- All page/component tasks in US2 marked [P] (T023–T031) can run in parallel.
- All route-module tasks in US3 marked [P] (T032–T037) can run in parallel.
- All mock-adapter tasks in US4 marked [P] (T044–T051) can run in parallel.
- All US6 test files marked [P] (T059–T063) can run in parallel.

---

## Parallel Example: User Story 4 (Mock Adapters)

```bash
# Launch all mock adapter implementations together (independent files):
Task: "Create MockDetector in backend/src/face_insight/adapters/mock/detector.py"
Task: "Create MockEmbedder in backend/src/face_insight/adapters/mock/embedder.py"
Task: "Create MockAgeEstimator in backend/src/face_insight/adapters/mock/age_estimator.py"
Task: "Create MockMoodEstimator in backend/src/face_insight/adapters/mock/mood_estimator.py"
Task: "Create MockSessionManager in backend/src/face_insight/adapters/mock/session_manager.py"
Task: "Create MockUserRepository in backend/src/face_insight/adapters/mock/user_repository.py"
Task: "Create MockFaceTemplateRepository in backend/src/face_insight/adapters/mock/face_template_repository.py"
```

## Parallel Example: User Story 3 (Route Modules)

```bash
# Launch all route module stubs together (independent files):
Task: "Create onboarding route in backend/src/face_insight/api/routes/onboarding.py"
Task: "Create auth routes in backend/src/face_insight/api/routes/auth.py"
Task: "Create analysis routes in backend/src/face_insight/api/routes/analysis.py"
Task: "Create users route in backend/src/face_insight/api/routes/users.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 — Runnable Demo Stack
4. **STOP and VALIDATE**: `docker compose up --build` brings the stack healthy (Scenario 1)
5. Demo the running (empty) skeleton

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. + US1 → runnable stack → demo (MVP!)
3. + US2 → navigable frontend → demo
4. + US3 → contract-defined API surface → demo
5. + US4 → pure domain + mocks → demo
6. + US5 → persistence foundations → demo
7. + US6 → green test suite → demo
8. Polish → SC-001…SC-010 verified

### Parallel Team Strategy

With multiple developers and Foundational complete:

- Developer A: US1 (compose wiring) + US5 (persistence)
- Developer B: US2 (frontend navigation)
- Developer C: US3 (backend endpoints) + US4 (domain + mocks)
- Once US3 + US4 land: Developer C pivots to US6 (test suite)

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to a specific user story for traceability.
- Each user story is independently completable and testable per its `Independent Test` in `spec.md`.
- This is a scaffolding spec (Fase 1): **no real business logic** is implemented — endpoints are stubs/mocks (SC-010). Real onboarding/login/analysis/deletion deferred to specs 002–006.
- Mock adapters use hardcoded constant outputs (no RNG/seed) for byte-identical determinism (SC-005).
- All primary keys are UUID v4 strings stored as PostgreSQL `UUID` columns; domain owns identity generation (pinned decision).
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently against the corresponding `quickstart.md` scenario.
