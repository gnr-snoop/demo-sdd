---

description: "Task list for Age Estimation (Fase 4 — age) implementation"
---

# Tasks: Age Estimation from Authenticated Dashboard (Fase 4 — age)

> ## ⏳ PENDING — IMPLEMENTATION DEFERRED FOR A LIVE DEMO
>
> **This `tasks.md` is implementation-ready but is intentionally NOT executed in this session.** It is reserved for a live SDD demo. All upstream gates (specify / clarify / plan / tasks / analyze) produce complete artifacts; the implement gate is deliberately deferred.
>
> The tasks below are complete, ordered, and file-pathed so the live demo can proceed directly from this checklist. Specs 001–004 are already implemented; this spec enables the age button and fills `POST /api/analysis/age` with real orchestration on top of the existing hexagonal ports + mock adapters. Real ML models are deferred to Fase 5 (mock age estimator retained — FR-016).

**Input**: Design documents from `/specs/005-age-analysis/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/analysis-age.md, quickstart.md

**Tests**: The spec mandates an automated test suite (FR-018, User Story 5). Tests are included as first-class tasks per story (unit + contract + integration + frontend), written to fail before implementation.

**Organization**: Tasks are grouped by user story (US1–US5, priority order P1→P5) so each story can be implemented and tested independently and delivered as an MVP increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2). Setup/Foundational/Polish tasks carry NO story label.
- Include exact file paths in descriptions

## Path Conventions

- Web app monorepo: `backend/src/`, `frontend/src/` at repository root (inherited from specs 001–004).
- Backend tests: `backend/tests/{unit,contract,integration,domain}/`.
- Frontend tests: `frontend/src/__tests__/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Additive configuration + constant bumps on the existing stack. No new project, no new dependency, no migration.

- [ ] T001 Add `age_range_half_width_years: int = 5` field to the pydantic `Settings` in `backend/src/face_insight/config.py` (with a `>= 0` invariant via field validator or clamp). Update `age_model_version` default to `"mock-age-estimator-v1"` (FR-004, FR-017, R-3, R-11).
- [ ] T002 [P] Update `AGE_MODEL_VERSION` constant to `"mock-age-estimator-v1"` and add age byte markers (`AGEPOINT`, `AGERANGE`, `AGEFAIL`) in `backend/src/face_insight/adapters/mock/constants.py` (R-5, R-11).

**Checkpoint**: Config + constants ready for the domain and adapter layers.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain types, exception, schema, scriptable mock adapter, dependency wiring, and app wiring that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Widen `AgeResult.range` from `tuple[int, int]` to `tuple[int, int] | None` in `backend/src/face_insight/domain/result_types.py` (backward-compatible; supports point-only port output — data-model.md, research.md R-2).
- [ ] T004 [P] Add `AgeInternalError` domain exception in `backend/src/face_insight/domain/exceptions.py` (mapped to `500 internal_error`; mirrors `MoodInternalError` — R-4).
- [ ] T005 [P] Introduce dedicated `AgeRange(BaseModel)` schema (`min: int`, `max: int`) in `backend/src/face_insight/api/schemas.py` and update `AgeResponse.range` from `MoodRange` to `AgeRange`. Keep `AGE_DISCLAIMER` constant as the exact PRD §8 string (R-12, FR-003).
- [ ] T006 [P] Add `ScriptableMockAgeEstimator` to `backend/src/face_insight/adapters/mock/age_estimator.py` (byte-marker controllable: `AGEPOINT`→point-only `40`/None, `AGERANGE`→range `(35,45)`/`40`, `AGEFAIL`→raise, default→`32`/`(27,37)`). Keep `MockAgeEstimator` as the production default (R-5, FR-016).
- [ ] T007 [P] Add `get_age_service` dependency to `backend/src/face_insight/api/dependencies.py` resolving `app.state.age_service` (mirrors `get_mood_service`).
- [ ] T008 Scaffold `app.state.age_service` slot in `backend/src/face_insight/main.py` (attribute initialization placeholder) and in `create_auth_app`. The real `AgeService` is wired in T008b after T013 creates it.
- [ ] T009 [P] Extend `backend/tests/domain/test_domain_purity.py` to assert `backend/src/face_insight/domain/age.py` imports no FastAPI / Pillow / SQLAlchemy / ML library / `adapters` / `api` (enforces FR-015/SC-009 once `age.py` exists; allow the import-check to skip if the file is absent during foundational phase, then harden after T010).

**Checkpoint**: Foundation ready — domain types, exception, schema, scriptable mock, dependency, and app wiring in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Successful On-Demand Age Estimation (Happy Path) (Priority: P1) 🎯 MVP

**Goal**: An authenticated person presses "Calcular edad", the backend runs the real age orchestration (detect one face → estimate → normalize → respond `200`), and the frontend displays the age range + point estimate + disclaimer.

**Independent Test**: Login (spec 003), call `POST /api/analysis/age` with a one-face fixture the mock age estimator reports as point `32` + range `[27,37]`; assert `200` with `estimatedAge == 32`, `range.min == 27`, `range.max == 37`, `min <= estimatedAge <= max`, and the exact PRD §8 disclaimer.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [ ] T010 [P] [US1] Unit tests for `normalize_age_result` in `backend/tests/unit/test_age_service.py` — range→midpoint, invariants (`min >= 0`, `min <= estimated_age <= max`), `min` clamping to 0 (FR-004/SC-014).
- [ ] T011 [P] [US1] Contract test for the `200` age response shape (integers, range invariants, exact disclaimer, `model_version == "mock-age-estimator-v1"`) in `backend/tests/contract/test_age_contracts.py` (contract assertions 1, 10, 12 from `contracts/analysis-age.md`).
- [ ] T012 [P] [US1] Integration test for the happy path (valid session + one-face fixture → `200` with `estimatedAge/range/disclaimer`) in `backend/tests/integration/test_age_analysis.py`.

### Implementation for User Story 1

- [ ] T013 [P] [US1] Create `AgeService` use-case + pure `normalize_age_result` function in `backend/src/face_insight/domain/age.py` — orchestration: detect (exactly one face + quality threshold) → `estimate_age` → normalize → return `AgeResult` (range guaranteed non-None). Port-only deps (FR-005/FR-015, R-1, R-2).

- [ ] T008b [US1] Wire real `AgeService` into `app.state.age_service` in `wire_mock_adapters` and `create_auth_app` (build from mock `Detector` + mock `AgeEstimator` + `settings.age_range_half_width_years`). (Depends on T008 + T013.)
- [ ] T014 [US1] Replace the stub age handler in `backend/src/face_insight/api/routes/analysis.py` with real orchestration: `Depends(require_valid_session)` → `decode_and_normalize` (spec 002 limits) → `AgeService.analyze` → build `AgeResponse(estimatedAge, range=AgeRange(min,max), disclaimer=AGE_DISCLAIMER)` → `200 OK`. Mirror the spec 004 mood route's structured logging (`analysis.age`, `duration_ms`, `status`). Mood route unchanged (FR-020). (Depends on T007, T013.)
- [ ] T015 [P] [US1] Update `analysisAge(image)` in `frontend/src/services/api.ts` to send `credentials: "include"` (session cookie) and parse errors via the existing `parseError` helper (mirrors the spec 004 `analysisMood` update).
- [ ] T016 [P] [US1] Create `useAgeMachine` reducer hook in `frontend/src/hooks/useAgeMachine.ts` — states `idle → processing → result | error` (+ `camera_unavailable`), events `CAPTURE/SUCCEEDED/FAILED/RETRY/RESET`, mirroring `useMoodMachine` (R-6, FR-008).
- [ ] T017 [US1] Update `frontend/src/pages/Dashboard.tsx` to enable the "Calcular edad" button (remove the `age-placeholder` "Próximamente" indication — FR-013), wire it to `useAgeMachine` + `CameraCapture.onCapture`, and render the age result surface: range as `"min–max años"`, point estimate as `"≈NN años"` (only point estimate when `min == max`), followed by the disclaimer (FR-012a/FR-003). Add the independent age loading indicator. (Depends on T016.)

**Checkpoint**: User Story 1 fully functional — happy-path age estimation works end-to-end and is independently testable.

---

## Phase 4: User Story 2 - Age Capture-Quality & Error Handling (Priority: P2)

**Goal**: Capture-quality failures (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`) return actionable `400`; port errors return recoverable `500 internal_error`; point-only port output is normalized to a derived symmetric range. The frontend shows an actionable age error surface with retry.

**Independent Test**: With a valid session, submit (a) undecodable/oversized → `400 invalid_image`; (b) zero faces → `400 no_face`; (c) two faces → `400 multiple_faces`; (d) one face flagged low quality → `400 insufficient_quality`; (e) port error → `500 internal_error`. In each case assert the pinned error body and no age result. Also assert point-only → derived range `[35,45]` for estimate `40`.

### Tests for User Story 2

- [ ] T018 [P] [US2] Unit tests for point-only normalization (derived symmetric range, half-width 5, `min` clamped to 0) and error-code mapping in `backend/tests/unit/test_age_service.py`.
- [ ] T019 [P] [US2] Contract tests for `400` (`invalid_image`, `no_face`, `multiple_faces`, `insufficient_quality`), `500 internal_error`, point-only → derived range, range → midpoint, and the pinned error body shape in `backend/tests/contract/test_age_contracts.py` (contract assertions 2, 3, 5–9, 11).
- [ ] T020 [P] [US2] Integration tests for each capture-quality failure, the port-error path (`AGEFAIL` fixture), and the `insufficient_quality` fixture (mock detector `LOWQUALITY` marker) in `backend/tests/integration/test_age_analysis.py`.

### Implementation for User Story 2

- [ ] T021 [US2] Add `_AGE_ERROR_MAP` (domain exception → status/code/actionable message) and `_error_response` builder to the age handler in `backend/src/face_insight/api/routes/analysis.py`, mapping `InvalidImage`→`400 invalid_image`, `NoFace`→`400 no_face`, `MultipleFaces`→`400 multiple_faces`, `InsufficientQuality`→`400 insufficient_quality`, `AgeInternalError`→`500 internal_error`, with a boundary catch for unexpected → `500 internal_error`. Wrap `AgeService.analyze` so port failures raise `AgeInternalError`. No age result produced on any error path (FR-006/FR-007, R-4). (Depends on T014.)
- [ ] T022 [US2] Add the age error surface + retry (no full page reload) to `frontend/src/pages/Dashboard.tsx` driven by `useAgeMachine` `error` state, with the actionable message from the parsed error body (FR-011/FR-015). (Depends on T017.)

**Checkpoint**: User Stories 1 AND 2 both work — happy path plus complete, actionable age error handling covering all four capture-quality codes and the port-error path.

---

## Phase 5: User Story 3 - Session Gating & Concurrent-Action Prevention on Age (Priority: P3)

**Goal**: `POST /api/analysis/age` rejects missing/invalid/expired/revoked sessions with `401 unauthenticated` and performs no analysis. The frontend enforces the shared capture mutex: both mood and age buttons disable while either analysis is in flight, and a second press of either is ignored.

**Independent Test**: No cookie → `401 unauthenticated`; expired/revoked session → `401 unauthenticated`. With a valid session, trigger an age analysis and issue a second age press → second press ignored; press the mood button during age in-flight → mood button disabled and press ignored.

### Tests for User Story 3

- [ ] T023 [P] [US3] Contract + integration tests for `401 unauthenticated` (no cookie, expired session, revoked session) and no analysis performed, in `backend/tests/contract/test_age_contracts.py` and `backend/tests/integration/test_age_analysis.py` (contract assertion 4).
- [ ] T024 [P] [US3] Frontend tests for the shared capture mutex in `frontend/src/__tests__/dashboard/` — double press of age ignored, press of mood during age in-flight ignored (and vice versa), both buttons re-enable on completion (FR-014/SC-006).

### Implementation for User Story 3

- [ ] T025 [US3] Add the dashboard-level shared capture mutex to `frontend/src/pages/Dashboard.tsx`: `anyAnalysisInFlight = mood.isProcessing || age.isProcessing`; bind both buttons' `disabled` and `CameraCapture`'s `disabled` to it (FR-009/FR-014, R-6). Each hook retains independent state. (Depends on T017; mood hook unchanged — FR-020.)
- [ ] T026 [US3] Handle in-flight `401 unauthenticated` on the age request in `frontend/src/hooks/useAgeMachine.ts` + `Dashboard.tsx`: discard any partial age result and transition to the unauthenticated state (redirect to `/login`) (AC-008 US3 scenario 5). (Depends on T016, T025.)

**Checkpoint**: Age endpoint is real-session-gated and the dashboard enforces one capture at a time across both analyses.

---

## Phase 6: User Story 4 - Frontend Dashboard Age UI (Enable Placeholder) (Priority: P4)

**Goal**: The dashboard renders an enabled, keyboard-accessible "Calcular edad" button (placeholder removed), independent age loading/result/error surfaces, the most recent age result persisted visible until a new analysis or logout, the `camera_unavailable` state with retry, and independent mood/age surfaces. State communication does not rely exclusively on color.

**Independent Test**: Render `/dashboard` with a mocked `MediaDevices` + mocked fetch; walk age `idle → processing → result | error`; assert the button is enabled, keyboard-reachable, has a descriptive accessible name, no "Próximamente" indication; assert mood button + result still work independently (spec 004 regression).

### Tests for User Story 4

- [ ] T027 [P] [US4] Frontend tests in `frontend/src/__tests__/age/` and `frontend/src/__tests__/dashboard/` for: button enabled + keyboard-accessible + descriptive `aria-label` + no placeholder; age loading indicator on press; result rendering (range, point estimate, disclaimer, narrow-range `min==max` → point only); error surface + retry; `camera_unavailable` state (denied `getUserMedia` → actionable error + retry, no backend call); independent mood/age surfaces (age result not cleared by mood analysis and vice versa); state not communicated exclusively by color (FR-012/FR-012a/FR-012c/SC-016/SC-018).

### Implementation for User Story 4

- [ ] T028 [US4] Add keyboard accessibility + descriptive `aria-label="Calcular edad"` to the age button, ensure result/error states do not rely exclusively on color (use text + icons), and render the narrow-range case (`min == max` → only `"≈NN años"`) in `frontend/src/pages/Dashboard.tsx` (FR-012/FR-012a). (Depends on T017, T022.)
- [ ] T029 [US4] Wire `CameraCapture.onPermissionDenied` to drive `useAgeMachine` `CAMERA_DENIED` → `camera_unavailable` state with an actionable "grant camera permission" message + retry (no backend call) in `frontend/src/pages/Dashboard.tsx` (FR-012c/SC-016). (Depends on T017.)
- [ ] T030 [US4] Ensure the most recent age result is held in `Dashboard` component state and remains visible until a new age analysis or unmount/logout, and is discarded on logout (inaccessible without re-authentication) in `frontend/src/pages/Dashboard.tsx` (FR-010/SC-007/SC-015). (Depends on T017.)

**Checkpoint**: Dashboard age UI complete — accessible, independent, and persistent-visible per PRD §6.4/§10.

---

## Phase 7: User Story 5 - Automated Age Analysis Tests (Priority: P5)

**Goal**: The full age test suite (unit + contract + integration + frontend) passes under no-GPU/no-network constraints, a deliberate contract violation fails a test, a broken invariant fails a unit test, and the spec 004 mood tests still pass (no regression).

**Independent Test**: Run the age suite + mood suite with no GPU and no network; assert all green; assert a deliberate shape change fails a contract test; assert a broken `min <= estimatedAge <= max` invariant fails a unit test; assert mood tests still pass.

### Tests for User Story 5

- [ ] T031 [P] [US5] Add the SC-011 contract-violation check as a parametrized contract test in `backend/tests/contract/test_age_contracts.py` (assert a deliberate rename of `estimatedAge` / a broken invariant causes a failure — documented via a skipped-by-default marker that the demo un-skips to prove the guard fires).
- [ ] T032 [P] [US5] Add a mood regression test run to `backend/tests/integration/test_age_analysis.py` (or a shared conftest marker) ensuring `tests/integration/test_mood_analysis.py` still passes alongside the age suite (FR-020/SC-017).
- [ ] T033 [US5] Harden the `backend/tests/domain/test_domain_purity.py` assertion for `age.py` (remove the foundational-phase skip added in T009) now that `age.py` exists — assert zero imports of FastAPI/Pillow/SQLAlchemy/ML/`adapters`/`api` (FR-015/SC-009). (Depends on T013.)

**Checkpoint**: Green, reproducible age test foundation; mood regression guarded; domain purity enforced.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation.

- [ ] T034 [P] Update `backend/tests/contract/test_http_contracts.py` to exercise the real age logic (supersede the spec 001 stub assertions for age — the contract evolution noted in plan.md).
- [ ] T035 [P] Verify no image / embedding / estimated age / range appears in application logs — only `duration_ms` / `status` / `error_code` (FR-019/SC-013) via a logging assertion in `backend/tests/integration/test_age_analysis.py`.
- [ ] T036 [P] Code cleanup: remove any dead stub remnants from the spec 001 age handler, ensure `_AGE_ERROR_MAP` messages match `contracts/analysis-age.md` verbatim, and confirm `AgeResponse.range` is `AgeRange` everywhere.
- [ ] T037 Run `quickstart.md` validation end-to-end: `docker compose up --build` + the backend/frontend test commands + the manual walkthrough (specs/005-age-analysis/quickstart.md).
- [ ] T038 [P] Documentation: update any inline OpenAPI description for `POST /api/analysis/age` to reflect the real contract (supersedes spec 001 stub).

**Checkpoint**: Age feature complete, tested, and validated against `quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phases 3–7)**: All depend on Foundational phase completion.
  - Recommended order: US1 → US2 → US3 → US4 → US5 (priority order; the route handler is built incrementally across US1/US2 and the dashboard across US1/US2/US3/US4).
  - US1 is the MVP; stop after US1 for a demoable happy path.
- **Polish (Phase 8)**: Depends on all user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. No dependencies on other stories. Produces `age.py`, the real route handler, `useAgeMachine`, and the dashboard age surfaces.
- **US2 (P2)**: Depends on US1 (extends the same route handler `_AGE_ERROR_MAP` and the dashboard error surface). Independently testable via the error fixtures.
- **US3 (P3)**: Depends on US1 (session gating rides on the real route; shared mutex rides on the dashboard age wiring). Independently testable via `401` + double-press/cross-button fixtures.
- **US4 (P4)**: Depends on US1/US2/US3 (polishes the dashboard UI the prior stories wired). Independently testable via the frontend mocked-camera suite.
- **US5 (P5)**: Depends on US1–US4 (hardens the test suite now that all code exists). Independently testable by running the suite under no-GPU/no-network.

### Within Each User Story

- Tests (where included) MUST be written and FAIL before implementation.
- Domain (`age.py`) before route handler; route handler before frontend api helper; api helper before hook; hook before dashboard.
- Core implementation before integration.
- Story complete and independently testable before moving to the next priority.

### Parallel Opportunities

- T001 → T002 (Setup): T002 is independent of T001 (different files).
- T003, T004, T005, T006, T007, T009 (Foundational): all touch different files — can run in parallel once T001/T002 are done. T008 depends on T006/T007 (wires the service + dependency).
- T010, T011, T012 (US1 tests): different files — parallel.
- T013, T015, T016 (US1 impl): different files — parallel. T014 depends on T007+T013; T017 depends on T016.
- T018, T019, T020 (US2 tests): different files — parallel.
- T023, T024 (US3 tests): different files — parallel.
- T027 (US4 tests) is a single frontend test task.
- T031, T032 (US5 tests): different files — parallel; T033 depends on T013.
- T034, T035, T036, T038 (Polish): different files — parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (written first, must FAIL):
Task: "Unit tests for normalize_age_result in backend/tests/unit/test_age_service.py"
Task: "Contract test for 200 age response shape in backend/tests/contract/test_age_contracts.py"
Task: "Integration test for happy path in backend/tests/integration/test_age_analysis.py"

# Launch independent US1 implementation files together:
Task: "Create AgeService + normalize_age_result in backend/src/face_insight/domain/age.py"
Task: "Update analysisAge in frontend/src/services/api.ts"
Task: "Create useAgeMachine in frontend/src/hooks/useAgeMachine.ts"

# Then sequential (same file / depends on prior):
Task: "Replace stub age handler in backend/src/face_insight/api/routes/analysis.py"   # needs T007+T013
Task: "Update Dashboard.tsx age surfaces"                                              # needs T016
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002).
2. Complete Phase 2: Foundational (T003–T009) — CRITICAL, blocks all stories.
3. Complete Phase 3: User Story 1 (T010–T017).
4. **STOP and VALIDATE**: Run the US1 independent test (login → `POST /api/analysis/age` with one-face fixture → `200` with `estimatedAge/range/disclaimer`).
5. Demo the happy path if ready.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. + US1 → test independently → demo happy path (MVP!).
3. + US2 → test independently → demo actionable error handling.
4. + US3 → test independently → demo session gating + shared capture mutex.
5. + US4 → test independently → demo accessible, persistent-visible dashboard UI.
6. + US5 → test independently → demo green, reproducible test foundation.
7. Polish → run `quickstart.md` end-to-end.

### Parallel Team Strategy

With multiple developers and the foundational phase complete:

- Developer A: US1 (domain + route + frontend happy path).
- Developer B: US2 test fixtures (can prepare `ScriptableMockAgeEstimator`-driven fixtures in parallel with US1 impl, merging once US1 lands).
- After US1 lands: US2/US3/US4 can proceed in parallel by different developers (US2 = route error map + dashboard error surface; US3 = shared mutex + 401 tests; US4 = a11y + rendering polish) — coordinate on `Dashboard.tsx` (merge sequentially).
- US5 + Polish after all stories land.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to US1–US5 for traceability; Setup/Foundational/Polish carry no story label.
- Each user story is independently completable and testable; stop at any checkpoint to validate.
- The route handler (`analysis.py`) and the dashboard (`Dashboard.tsx`) are built incrementally across US1→US4 — coordinate merges on these two files.
- Verify tests fail before implementing (TDD).
- Commit after each task or logical group.
- **Implementation is PENDING** — these tasks are implementation-ready but deliberately not executed in this session (reserved for a live SDD demo).
- Avoid: vague tasks, same-file parallel conflicts, cross-story dependencies that break independence.
