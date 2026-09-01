---

description: "Task list for Mood Analysis (Fase 4 — mood) implementation"
---

# Tasks: Mood Analysis (Fase 4 — mood)

**Input**: Design documents from `/specs/004-mood-analysis/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/analysis-mood.md, quickstart.md

**Tests**: The spec mandates an automated test suite (User Story 5, FR-018, Constitution Quality Gates §5/§7). Test tasks are included per user story and consolidated in US5. Domain/contract/integration suites run without GPU/network (mock adapters only — FR-016).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. The mood result is transient (no persistence, no migration, no new entity — FR-014). All work is additive to specs 001/002/003.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app (monorepo)**: `backend/src/`, `backend/tests/`, `frontend/src/` — inherited from specs 001/002/003.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Feature branch + confirm no new runtime dependencies (plan §Technical Context — additive only).

- [X] T001 Create/checkout feature branch `004-mood-analysis` from `main`; confirm no new runtime dependencies are required (backend reuses FastAPI/SQLAlchemy/Pillow/structlog/pytest; frontend reuses react/react-router-dom/vitest — plan §Primary Dependencies)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared backend infrastructure (schema/exception widening, scriptable mock, dependency resolver, domain-purity guard) that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Widen `MoodResult.confidence` from `float` to `float | None` in `backend/src/face_insight/domain/result_types.py` (forward-compatible; mock always supplies a value — R-3)
- [X] T003 [P] Add `MoodInternalError` domain exception to `backend/src/face_insight/domain/exceptions.py` (mapped to `500 internal_error` — R-4)
- [X] T004 [P] Widen `MoodResponse.confidence` to `float | None = None` with `[0.0, 1.0]` validation-when-present in `backend/src/face_insight/api/schemas.py` (R-3)
- [X] T005 [P] Add mood byte markers (`FELIZ`, `TRIST`, `NOCONCLUSIVE`, `MOODFAIL`, `OOSET`) to `backend/src/face_insight/adapters/mock/constants.py` (R-5)
- [X] T006 Add `ScriptableMockMoodEstimator` (byte-marker controllable, mirroring `ScriptableMockDetector`) to `backend/src/face_insight/adapters/mock/mood_estimator.py`; retain `MockMoodEstimator` as production default (depends T005 — R-5)
- [X] T007 [P] Add `get_mood_service` dependency resolver (`app.state.mood_service`) to `backend/src/face_insight/api/dependencies.py`
- [X] T008 Extend `backend/tests/domain/test_domain_purity.py` to assert `domain/mood.py` imports no infra/ML/Pillow/FastAPI/SQLAlchemy (guard for FR-015/SC-009; passes once T012 lands)

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Successful On-Demand Mood Analysis (Happy Path) (Priority: P1) 🎯 MVP

**Goal**: A person with a valid session presses "Detectar estado de ánimo"; the backend validates the session, decodes the image, runs the detector (exactly one face) + mood_estimator port, normalizes the label, and returns `200 OK` with `{label, confidence, disclaimer}` per PRD §8.

**Independent Test**: Perform a successful login (spec 003), then call `POST /api/analysis/mood` with the session cookie and a fixture image the mock detector reports as one face and the mock mood estimator reports as `feliz`/`0.8`; assert `200` with `label == "feliz"`, `confidence` in `[0,1]`, and the exact PRD §8 disclaimer.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T009 [P] [US1] Unit tests for `normalize_mood_label` (valid labels pass; out-of-set → `no concluyente`) and confidence clamp to `[0,1]` in `backend/tests/unit/test_mood_service.py`
- [X] T010 [P] [US1] Contract test for `200` mood response shape (`label` ∈ valid set, `confidence` ∈ `[0,1]` or null, `disclaimer` == exact PRD §8 string) in `backend/tests/contract/test_mood_contracts.py`
- [X] T011 [P] [US1] Integration test for happy path (real endpoint + mock detector/mood + real session validation) in `backend/tests/integration/test_mood_analysis.py`

### Implementation for User Story 1

- [X] T012 [P] [US1] Create `MoodService` use-case + `normalize_mood_label` + `VALID_LABELS` in `backend/src/face_insight/domain/mood.py` (port-only deps; orchestration: detect exactly-one-face + quality threshold → `estimate_mood` → normalize label → clamp confidence → return `MoodResult`; raises `NoFace`/`MultipleFaces`/`InsufficientQuality`/`MoodInternalError` — R-1/R-2)
- [X] T013 [US1] Replace stub `POST /api/analysis/mood` handler in `backend/src/face_insight/api/routes/analysis.py` with real orchestration: `Depends(require_valid_session)` → `decode_and_normalize` → `MoodService.analyze` → structured JSON logging (`duration_ms`/`status`, no biometric data) → `200 MoodResponse` (depends T012; age endpoint stays stubbed)
- [X] T014 [US1] Wire `MoodService` from mock ports into `app.state.mood_service` in `backend/src/face_insight/main.py` (`wire_mock_adapters` + `create_auth_app` integration-test factory) (depends T012, T007)
- [X] T015 [US1] Update `backend/tests/contract/test_http_contracts.py` mood assertions to exercise real logic (supersedes spec 001 stub assertions; `confidence` widened to `float | null` — depends T013)

**Checkpoint**: User Story 1 fully functional — happy-path mood analysis works end-to-end and is independently testable.

---

## Phase 4: User Story 2 - Mood Capture-Quality & Error Handling (Priority: P2)

**Goal**: Bad captures (`no_face`/`multiple_faces`/`invalid_image`/`insufficient_quality`) return actionable `400`; port errors return recoverable `500 internal_error`; out-of-set labels normalize to `no concluyente` — all in the pinned `{"error": {"code", "message"}}` shape, no mood result produced.

**Independent Test**: With a valid session, submit (a) undecodable/oversized image → `400 invalid_image`; (b) zero-face fixture → `400 no_face`; (c) two-face fixture → `400 multiple_faces`; (d) port-error fixture → `500 internal_error`; (e) out-of-set fixture → `200 label: "no concluyente"`. Assert pinned error body and no result on error paths.

### Tests for User Story 2

- [X] T016 [P] [US2] Unit tests for error-code mapping (`NoFace`/`MultipleFaces`/`InsufficientQuality`/`MoodInternalError` → expected codes) in `backend/tests/unit/test_mood_service.py`
- [X] T017 [P] [US2] Contract tests for `400` (`no_face`/`multiple_faces`/`invalid_image`/`insufficient_quality`) + `500` (`internal_error`) + pinned error body shape + out-of-set label normalization → `no concluyente` in `backend/tests/contract/test_mood_contracts.py`
- [X] T018 [P] [US2] Integration tests for each capture-quality failure + port-error path (real endpoint + scriptable mocks) in `backend/tests/integration/test_mood_analysis.py`

### Implementation for User Story 2

- [X] T019 [US2] Add `_MOOD_ERROR_MAP` (`InvalidImage`→`400 invalid_image`, `NoFace`→`400 no_face`, `MultipleFaces`→`400 multiple_faces`, `InsufficientQuality`→`400 insufficient_quality`, `MoodInternalError`→`500 internal_error`) + `_error_response` builder to `backend/src/face_insight/api/routes/analysis.py`, mirroring `auth.py`'s `_LOGIN_ERROR_MAP` pattern with actionable Spanish messages from `contracts/analysis-mood.md` (R-4; depends T013)

**Checkpoint**: User Stories 1 AND 2 work independently — happy path and all error paths return correct actionable responses.

---

## Phase 5: User Story 3 - Session Gating & Concurrent-Action Prevention on Mood (Priority: P3)

**Goal**: `POST /api/analysis/mood` rejects no/invalid/expired/revoked sessions with `401 unauthenticated` (no analysis); the frontend mood state machine disables the button while in flight and ignores a second press (FR-014, one capture at a time).

**Independent Test**: Without a cookie → `401 unauthenticated`; with expired/revoked session → `401`; with a valid session, trigger mood and issue a second press before the first resolves → assert the frontend ignores/disables the second press.

### Tests for User Story 3

- [X] T020 [P] [US3] Contract test for `401 unauthenticated` (no cookie / expired / revoked session; `401` reserved exclusively for `unauthenticated` — FR-007) in `backend/tests/contract/test_mood_contracts.py`
- [X] T021 [P] [US3] Integration test for `401 unauthenticated` path (real session validation from spec 003) in `backend/tests/integration/test_mood_analysis.py`
- [X] T022 [P] [US3] Frontend unit test for `useMoodMachine` state transitions + double-press prevention (ignore `CAPTURE` while `processing`) in `frontend/src/__tests__/mood/useMoodMachine.test.tsx`

### Implementation for User Story 3

- [X] T023 [US3] Create `useMoodMachine` hook (`useReducer` + transition table) in `frontend/src/hooks/useMoodMachine.ts`: states `idle → processing → result | error | camera_unavailable`; events `CAPTURE`/`SUCCEEDED`/`FAILED`/`CAMERA_DENIED`/`RETRY`/`RESET`; ignore `CAPTURE` while `processing` (FR-014); mirrors `useLoginMachine` pattern (R-6)
- [X] T024 [US3] Verify session gating via `Depends(require_valid_session)` in `backend/src/face_insight/api/routes/analysis.py` (reused unchanged from spec 003; confirm `401` reserved exclusively for `unauthenticated` and no analysis performed on invalid session — FR-001/FR-007)

**Checkpoint**: User Stories 1–3 work independently — mood endpoint is session-gated and concurrent captures are prevented.

---

## Phase 6: User Story 4 - Frontend Dashboard Mood UI & Disabled Age Placeholder (Priority: P4)

**Goal**: `/dashboard` renders the camera preview, keyboard-accessible "Detectar estado de ánimo" button, independent mood loading indicator, persisted-visible mood result (label + optional `≈NN%` + disclaimer), independent recoverable mood error surface with retry, disabled "Calcular edad" placeholder ("Próximamente"), and "Cerrar sesión" (reused). Camera acquired on mount, released on unmount.

**Independent Test**: Render `/dashboard` with authenticated session + mocked `MediaDevices` + mocked fetch; walk mood state machine (idle → button-press → result, and recoverable error → retry); assert disabled "Calcular edad" placeholder, keyboard reachability, no-color-only state, and stream release on unmount.

### Tests for User Story 4

- [X] T025 [P] [US4] Frontend dashboard tests in `frontend/src/__tests__/dashboard/Dashboard.test.tsx` (mocked `MediaDevices` + `fetch`; walk mood state machine; assert mood result + disclaimer render, `≈NN%` confidence rendering, error surface + retry, disabled age placeholder, keyboard access, no-color-only state, stream release on unmount)

### Implementation for User Story 4

- [X] T026 [P] [US4] Update `analysisMood()` in `frontend/src/services/api.ts` to use `parseError` + `credentials: "include"` (session cookie; reuse `parseError` already defined)
- [X] T027 [US4] Build out `frontend/src/pages/Dashboard.tsx`: `<CameraCapture active={true} ... />` (preview on mount, release on unmount — FR-012b), mood button (keyboard-accessible, `disabled = isProcessing` — FR-014), independent mood loading indicator, mood result surface (label + `≈NN%` when confidence present — FR-012a + disclaimer — FR-003), independent mood error surface + retry (FR-011/FR-015), camera-permission-denied error surface + retry (FR-012c), disabled "Calcular edad" button with "Próximamente" indication (FR-013), "Cerrar sesión" (reused from spec 003); bind to `useMoodMachine` (depends T023, T026)

**Checkpoint**: User Stories 1–4 work independently — the dashboard UI delivers the full mood narrative with a stable layout for spec 005.

---

## Phase 7: User Story 5 - Automated Mood Analysis Tests (Priority: P5)

**Goal**: A green, reproducible mood test suite (unit + contract + integration + domain purity + frontend) that runs without GPU/network and catches contract violations and out-of-set labels.

**Independent Test**: Run the mood test suite under no-GPU/no-network; assert all tests pass, a deliberate contract-violating change fails a contract test, and a deliberate out-of-set allowance fails a unit test.

### Implementation for User Story 5

- [X] T028 [US5] Run full backend mood suite (`pytest tests/unit/test_mood_service.py tests/contract/test_mood_contracts.py tests/integration/test_mood_analysis.py tests/domain/test_domain_purity.py`) under no-GPU/no-network; confirm green per `quickstart.md`
- [X] T029 [US5] Contract-violation check: deliberately break the mood response shape (e.g. rename `label` → `mood`) → assert ≥1 contract test fails; revert (SC-011)
- [X] T030 [US5] Out-of-set label check: deliberately remove `normalize_mood_label` → assert ≥1 unit test fails; revert (SC-011)
- [X] T031 [US5] Run frontend mood + dashboard suites (`npm test -- --run src/__tests__/dashboard src/__tests__/mood`) with mocked camera + fetch; confirm green

**Checkpoint**: All user stories independently functional with a green test foundation for spec 005 / Fase 5.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [X] T032 [P] Documentation: confirm OpenAPI docs reflect the real mood contract (`contracts/analysis-mood.md`); update repo README/quickstart if needed
- [X] T033 [P] Code cleanup: remove any dead stub mood code from spec 001 now superseded by the real orchestration
- [X] T034 Run `quickstart.md` end-to-end manual walkthrough validation (docker compose up → onboarding → login → mood → result visible → logout discards)
- [X] T035 [P] Observability review: confirm no image/embedding/biometric data in logs (FR-019/SC-013); structured JSON logs only (`duration_ms`/`status`/`error_code`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - US1 (P1) → US2 (P2) builds on US1's route handler (T019 depends T013).
  - US1 (P1) → US3 (P3) session gating reuses US1's route; `useMoodMachine` (T023) is independent.
  - US3 (P3) → US4 (P4) Dashboard (T027) consumes `useMoodMachine` (T023) + `analysisMood` (T026).
  - US5 (P5) depends on all prior stories' test tasks being present.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. No dependencies on other stories. (MVP)
- **US2 (P2)**: Starts after Foundational. Integrates with US1's route handler (`_MOOD_ERROR_MAP` added to `analysis.py`).
- **US3 (P3)**: Starts after Foundational. Backend session gating reuses US1's route; frontend `useMoodMachine` is independent of US1/US2.
- **US4 (P4)**: Starts after Foundational + US3's `useMoodMachine` (T023). Dashboard consumes the hook + `analysisMood`.
- **US5 (P5)**: Starts after US1–US4 test tasks exist. Validates the consolidated suite.

### Within Each User Story

- Tests written FIRST and FAIL before implementation (TDD).
- Domain (`mood.py`) before route adapter (`analysis.py`) before wiring (`main.py`).
- Hook (`useMoodMachine`) before Dashboard page consuming it.
- Core implementation before integration tests.
- Story complete before moving to next priority.

### Parallel Opportunities

- All Foundational tasks marked [P] (T002–T005, T007) can run in parallel (independent files).
- US1 tests (T009–T011) can run in parallel; T012 (domain) is parallel with the tests.
- US2 tests (T016–T018) can run in parallel.
- US3 tests (T020–T022) can run in parallel; T023 (hook) is parallel with backend tests.
- US4 test (T025) and api update (T026) can run in parallel before T027 (Dashboard).
- Polish tasks marked [P] (T032, T033, T035) can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (written first, expected to fail):
Task: "Unit tests for normalize_mood_label + confidence clamp in backend/tests/unit/test_mood_service.py"
Task: "Contract test for 200 mood response shape in backend/tests/contract/test_mood_contracts.py"
Task: "Integration test for happy path in backend/tests/integration/test_mood_analysis.py"

# Then implement in parallel where independent:
Task: "Create MoodService + normalize_mood_label in backend/src/face_insight/domain/mood.py"
# → then sequentially: route handler (T013) → main.py wiring (T014) → contract update (T015)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (branch + dependency confirmation).
2. Complete Phase 2: Foundational (schema/exception/mock/dep/purity guard) — CRITICAL, blocks all stories.
3. Complete Phase 3: User Story 1 (MoodService + real route + wiring + happy-path tests).
4. **STOP and VALIDATE**: Test User Story 1 independently — `POST /api/analysis/mood` returns `200 {label, confidence, disclaimer}`.
5. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → test independently → demo MVP (happy-path mood analysis).
3. Add US2 → test independently → demo actionable error handling.
4. Add US3 → test independently → demo session gating + concurrent prevention.
5. Add US4 → test independently → demo full dashboard UI.
6. Add US5 → validate full green suite under no-GPU/no-network.
7. Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together.
2. Once Foundational is done:
   - Developer A: US1 (backend domain + route + wiring).
   - Developer B: US3 frontend hook (`useMoodMachine`) — independent of US1 backend.
3. After US1 lands: US2 (error map) and US4 (Dashboard, needs US3 hook) can proceed in parallel.
4. US5 consolidates and validates once US1–US4 test tasks exist.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Each user story is independently completable and testable.
- Verify tests fail before implementing (TDD).
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.
- **No new persistent entity, no schema migration, no new port, no new runtime dependency** (FR-014, FR-015, FR-016 — additive to specs 001/002/003).
- **Mock mood estimator retained** (real ML models deferred to Fase 5 — Constitution Principle VII).
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence.
