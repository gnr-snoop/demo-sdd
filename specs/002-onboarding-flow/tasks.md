---

description: "Task list for Onboarding Flow (Fase 2) implementation"
---

# Tasks: Onboarding Flow (Fase 2)

**Input**: Design documents from `/specs/002-onboarding-flow/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/onboarding.md, quickstart.md

**Tests**: Required. FR-018 mandates an automated test suite (unit + integration + contract) runnable without GPU/network. User Story 6 (P6) is dedicated to the test suite. Tests are written FIRST (red) before each story's implementation.

**Organization**: Tasks are grouped by user story (US1–US6) to enable independent implementation and testing. Shared infrastructure (async ports, error schema, validation module, image handling module, atomic unit-of-work) is lifted into Phase 2 Foundational because every backend story depends on it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2). Setup/Foundational/Polish tasks have NO story label.
- Include exact file paths in descriptions

## Path Conventions

- **Web app (monorepo)**: `backend/src/`, `backend/tests/`, `frontend/src/`
- Backend source root: `backend/src/face_insight/`
- Frontend source root: `frontend/src/`

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Additive dependency and config changes on top of the spec 001 skeleton.

- [X] T001 Add `Pillow` dependency to `backend/pyproject.toml` (image decode/resize; no ML)
- [X] T002 [P] Add `quality_threshold: float = 0.5` to `backend/src/face_insight/config.py` `Settings` (env-overridable `QUALITY_THRESHOLD`)
- [X] T003 [P] Bump `EMBED_MODEL_VERSION` to `"mock-embedder-v1"` in `backend/src/face_insight/adapters/mock/constants.py` and sync `Settings.embedding_model_version` default in `backend/src/face_insight/config.py` (R-8)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain/adapter infrastructure that MUST be complete before ANY backend user story can be implemented.

**⚠️ CRITICAL**: No backend user-story work can begin until this phase is complete. US4 (frontend) can proceed in parallel only after T005 (error schema) is available as a contract reference.

- [X] T004 Make repository ports async in `backend/src/face_insight/domain/ports.py`: `UserRepository` (`get`, `get_by_identifier`, `save`, `delete`) and `FaceTemplateRepository` (`get_by_user`, `save`, `delete_by_user`) → `async def`; keep `Detector`/`Embedder` sync (R-2)
- [X] T005 [P] Add error response schemas to `backend/src/face_insight/api/schemas.py`: `ErrorBody(code: str, message: str)`, `ErrorResponse(error: ErrorBody)` (R-7)
- [X] T006 [P] Define domain onboarding exceptions in `backend/src/face_insight/domain/onboarding.py`: `IdentifierInvalid`, `IdentifierTaken`, `ConsentRequired`, `InvalidImage`, `NoFace`, `MultipleFaces`, `InsufficientQuality`, `OnboardingInternalError` (R-7)
- [X] T007 [P] Implement identifier validation + normalization in `backend/src/face_insight/domain/validation.py`: `normalize_identifier(raw) -> str` (trim+lowercase), `is_valid_identifier(raw) -> bool` (email-or-username union pattern); pure functions, no infra imports (R-1)
- [X] T008 [P] Implement image decode/limits/resize in `backend/src/face_insight/domain/image_handling.py`: `decode_and_normalize(image_bytes, max_bytes, max_long_edge) -> bytes` using Pillow; raises `InvalidImage` on undecodable/unsupported/oversized; returns resized JPEG bytes (R-3)
- [X] T009 [P] Add `ScriptableMockDetector` to `backend/src/face_insight/adapters/mock/detector.py` with byte-marker convention: `detect(image)` substring-searches the **raw request bytes** for markers (`b"NOFACE"`→count 0, `b"MULTIFACE"`→count 2, `b"LOWQUALITY"`→score 0.1, else default count 1/score 0.99). Fixtures (T037) are valid minimal JPEGs with the marker embedded in a JPEG COM (comment) segment so Pillow decode succeeds AND the detector still sees the marker. Tests inject `ScriptableMockDetector` via `app.state.detector` for rejection cases. Leave plain `MockDetector` untouched for production wiring (R-6)
- [X] T010 Implement async atomic unit-of-work for `User` + `FaceTemplate` persistence in `backend/src/face_insight/adapters/db/repositories.py`: single SQLAlchemy async session wrapping both inserts; catch `IntegrityError` → `IdentifierTaken`; expose `save_user_with_template(user, template)` helper (R-2, R-4, R-5)

**Checkpoint**: Foundation ready — async ports, error schema, domain exceptions, validation, image handling, controllable mock detector, and atomic persistence all in place. Backend user-story implementation can now begin.

---

## Phase 3: User Story 1 - Successful Onboarding (Happy Path) (Priority: P1) 🎯 MVP

**Goal**: A person submits a valid identifier, explicit consent, and a single-face image; the backend validates, detects, embeds, and atomically persists `User` (status `enrolled`) + `FaceTemplate` (`modelVersion = "mock-embedder-v1"`), stores the image at `usuarios/<user-id>/pictures.jpg`, and returns `201` with `userId`, `identifier`, `status`. Delivers AC-001, FR-001, FR-003, FR-005, FR-006, FR-007, FR-008, FR-009.

**Independent Test**: Call `POST /api/onboarding` with a valid identifier, `consentAccepted=true`, and a one-face JPEG fixture (mock detector count=1, score>threshold); assert `201` with `userId` (UUID v4), normalized `identifier`, `status: "enrolled"`; confirm exactly one `User` + one `FaceTemplate` in DB and image readable at `usuarios/<userId>/pictures.jpg`.

### Tests for User Story 1

> **NOTE**: Write these FIRST, ensure they FAIL before implementation.

- [X] T011 [P] [US1] Contract test for happy-path `201` response in `backend/tests/contract/test_http_contracts.py` (assert `userId` UUID v4, normalized `identifier`, `status == "enrolled"`, supersedes spec 001 stub assertions)
- [X] T012 [P] [US1] Integration test for happy-path onboarding in `backend/tests/integration/test_onboarding.py` (real DB + real FS + mock detector/embedder; assert one `User` + one `FaceTemplate` + image at `usuarios/<userId>/pictures.jpg`)

### Implementation for User Story 1

- [X] T013 [US1] Implement `OnboardingService.onboard(identifier, consent, image_bytes)` happy path in `backend/src/face_insight/domain/onboarding.py`: validate → decode/resize → detect → embed → FS write → DB atomic commit → return `(userId, identifier, status)`; depends on T004, T007, T008, T010
- [X] T014 [US1] Replace onboarding route handler in `backend/src/face_insight/api/routes/onboarding.py`: read multipart `UploadFile`, call `await service.onboard(...)`, map domain exceptions → `ErrorResponse` with status/code/message table (R-7); depends on T013
- [X] T015 [US1] Wire `OnboardingService` in composition root (`backend/src/face_insight/main.py` / `wire_mock_adapters`): inject `MockDetector`, `MockEmbedder`, async DB repos, `FilesystemImageStorage` into `app.state`; depends on T013, T014

**Checkpoint**: User Story 1 fully functional — happy-path onboarding works end-to-end and is independently testable. MVP demonstrable.

---

## Phase 4: User Story 2 - Onboarding Rejected for Invalid Capture (Priority: P2)

**Goal**: When the captured image has zero faces, multiple faces, is undecodable, or is below the quality threshold, the backend rejects with an actionable error and creates no `User` and no `FaceTemplate`. Delivers AC-002, AC-003, FR-004, FR-005.

**Independent Test**: Submit images with zero faces, two faces, an undecodable payload, and below-threshold quality (via `ScriptableMockDetector` markers); assert each returns a client-error status with the correct machine code and that no `User`/`FaceTemplate` was persisted.

### Tests for User Story 2

- [X] T016 [P] [US2] Contract tests for `no_face`, `multiple_faces`, `insufficient_quality`, and undecodable `invalid_image` in `backend/tests/contract/test_http_contracts.py` (assert status 422 + correct `error.code` + actionable message + non-revealing)
- [X] T017 [P] [US2] Integration tests for each invalid-capture case in `backend/tests/integration/test_onboarding.py` (assert zero `User` + zero `FaceTemplate` after each rejection; detector/embedder invocation order verified)

### Implementation for User Story 2

- [X] T018 [US2] Add face-count + quality-threshold decision branches to `OnboardingService` in `backend/src/face_insight/domain/onboarding.py`: `face_count == 0 → NoFace`, `face_count > 1 → MultipleFaces`, `face_count == 1 and score < quality_threshold → InsufficientQuality`; all raised BEFORE any persistence (depends on T013)
- [X] T019 [US2] Verify all-or-nothing on capture rejection in `backend/src/face_insight/domain/onboarding.py`: detection/embedding happen pre-commit; no DB session opened until all checks pass (depends on T018)

**Checkpoint**: User Stories 1 AND 2 both work — happy path succeeds, invalid captures are rejected with no partial state.

---

## Phase 5: User Story 3 - Identifier & Consent Validation (Priority: P3)

**Goal**: Empty, malformed, or duplicate identifiers and missing/false/non-boolean consent are rejected before any image processing, with no persistence. Delivers FR-002, FR-003.

**Independent Test**: Submit empty identifier, malformed identifier, already-registered identifier (case-insensitive), and valid identifier with `consentAccepted=false`/`"true"`; assert each returns the correct client-error status/code and that no detector/embedder invocation and no DB writes occurred.

### Tests for User Story 3

- [X] T020 [P] [US3] Unit tests for `validation.py` in `backend/tests/unit/test_validation.py`: empty/whitespace, valid email, valid username, malformed, normalization (trim+lowercase), boundary lengths (3 and 32 chars)
- [X] T021 [P] [US3] Contract tests for `identifier_invalid`, `identifier_taken` (409), `consent_required` in `backend/tests/contract/test_http_contracts.py` (include `consentAccepted="true"` string → `consent_required`)
- [X] T022 [P] [US3] Integration test for case-insensitive duplicate + non-boolean consent in `backend/tests/integration/test_onboarding.py` (onboard `demo@example.com` then `DEMO@Example.COM` → 409; assert no image processing on validation rejections)

### Implementation for User Story 3

- [X] T023 [US3] Wire identifier + consent validation into `OnboardingService.onboard` in `backend/src/face_insight/domain/onboarding.py`: call `is_valid_identifier`/`normalize_identifier` (→ `IdentifierInvalid`), check `consent is True` (→ `ConsentRequired`), both BEFORE image decode; depends on T007, T013
- [X] T024 [US3] Map DB unique-violation to `IdentifierTaken` in `backend/src/face_insight/domain/onboarding.py` / route handler: catch `IntegrityError` from `save_user_with_template` (T010) and raise `IdentifierTaken` → 409 `identifier_taken` (R-4); depends on T023

**Checkpoint**: Input validation gate complete — no wasted processing on invalid input, no duplicate profiles.

---

## Phase 6: User Story 4 - Frontend Onboarding Page with Camera & State Machine (Priority: P4)

**Goal**: The onboarding page provides identifier input, consent checkbox, camera preview, and capture button, driven through the PRD §6.2 seven-state machine (`initial`, `requesting_permission`, `camera_unavailable`, `ready_to_capture`, `processing`, `success`, `recoverable_error`) with keyboard-accessible controls and actionable error messages. Delivers FR-011, FR-012, FR-013, FR-015.

**Independent Test**: Render the page with a mocked `MediaDevices` yielding a test frame; walk the state machine through each transition including a recoverable error; assert correct controls/messages per state and keyboard-reachable capture button.

### Tests for User Story 4

- [X] T025 [P] [US4] State-machine tests for `useOnboardingMachine` in `frontend/src/hooks/__tests__/useOnboardingMachine.test.ts`: all 7 states, transitions, capture-button disabled in `processing`, retry from `recoverable_error` without reload
- [X] T026 [P] [US4] Component test for `CameraCapture` in `frontend/src/components/__tests__/CameraCapture.test.tsx` with mocked `navigator.mediaDevices.getUserMedia` yielding a test frame; assert preview renders and still capture produces a JPEG blob

### Implementation for User Story 4

- [X] T027 [US4] Implement `useOnboardingMachine` hook in `frontend/src/hooks/useOnboardingMachine.ts`: `useState`-driven finite state with transition function; states per PRD §6.2; depends on T029 (R-9)
- [X] T028 [US4] Implement `CameraCapture` component in `frontend/src/components/CameraCapture.tsx`: `getUserMedia({video:true})` → `<video>` preview → hidden `<canvas>` + `drawImage` + `toBlob('image/jpeg')` single still; keyboard-accessible capture button with `aria-label` (FR-015); depends on T027
- [X] T029 [P] [US4] Add `onboarding(identifier, consentAccepted, imageBlob)` multipart upload helper in `frontend/src/services/api.ts`: builds `FormData` (`identifier`, `consentAccepted`, `image`), POSTs to `/api/onboarding`, parses `{error: {code, message}}` on failure
- [X] T030 [US4] Replace `Onboarding` page in `frontend/src/pages/Onboarding.tsx`: identifier input, consent checkbox, `CameraCapture`, state-driven controls/messages, success link to login, actionable error mapping from `error.code` (R-7); depends on T027, T028, T029

**Checkpoint**: Frontend onboarding UI complete — all 7 states demonstrable with a mocked camera, keyboard-accessible.

---

## Phase 7: User Story 5 - Image Constraints & Decoding (Priority: P5)

**Goal**: The backend enforces image limits independently of the frontend: rejects unsupported formats and oversized payloads, and resizes so the long edge ≤ 640px before detection and storage. Delivers FR-010, FR-004 decoding branch, OQ-8.

**Independent Test**: Submit a non-image payload, an oversized payload, and a valid image exceeding the long-edge limit; assert the first two are rejected with `invalid_image` and no face processing, and the third is normalized then accepted.

### Tests for User Story 5

- [X] T031 [P] [US5] Unit tests for `image_handling.py` in `backend/tests/unit/test_image_handling.py`: decode valid JPEG, reject non-JPEG, reject undecodable, reject oversized, resize when long edge > limit, no-resize when within limit, output is JPEG
- [X] T032 [P] [US5] Contract tests for `invalid_image` (missing image field, oversized > 2 MB, undecodable/non-JPEG) in `backend/tests/contract/test_http_contracts.py` (assert 422 + `invalid_image` + no persistence)

### Implementation for User Story 5

- [X] T033 [US5] Enforce image limits in route handler before detection in `backend/src/face_insight/api/routes/onboarding.py`: check `len(image_bytes) <= Settings.image_max_bytes` → `InvalidImage`; call `decode_and_normalize` (T008) and pass resized bytes to detector/embedder/storage; depends on T008, T014
- [X] T034 [US5] Verify resized image stored at `usuarios/<user-id>/pictures.jpg` with long edge ≤ `Settings.image_max_long_edge` in `backend/tests/integration/test_onboarding.py` (read stored file, assert dimensions); depends on T033

**Checkpoint**: Server-side image limits enforced — pathological inputs rejected, valid images normalized before storage.

---

## Phase 8: User Story 6 - Automated Onboarding Tests (Priority: P6)

**Goal**: A complete test suite covers onboarding unit (validation, face-count, image limits, service), integration (endpoint + mock adapters + real persistence), and contract (shapes/status codes) cases, all runnable without GPU/network. Delivers FR-018, SC-008, SC-009.

**Independent Test**: Run the full suite under no-GPU/no-network; assert all tests pass and a deliberate contract-violating change causes a contract test to fail.

- [X] T035 [P] [US6] Unit tests for `OnboardingService` in `backend/tests/unit/test_onboarding_service.py`: face-count rules, quality-threshold branch, all-or-nothing (no persistence on any post-validation failure), embedder-failure → `OnboardingInternalError`, identifier normalization flow; uses in-memory fakes for ports
- [X] T036 [P] [US6] Extend domain purity test in `backend/tests/domain/test_domain_purity.py`: assert `onboarding.py`, `entities.py`, `result_types.py`, `validation.py` import no infra/ML/SQLAlchemy/FastAPI/Pillow; explicitly exclude `image_handling.py` with a documented justification comment (R-3, FR-017, SC-007)
- [X] T037 [P] [US6] Add test fixture images in `backend/tests/fixtures/`: `one_face.jpg`, `no_face.jpg` (NOFACE marker), `multi_face.jpg` (MULTIFACE marker), `low_quality.jpg` (LOWQUALITY marker), `not_an_image.txt`, `oversized.jpg` (> 2 MB); document marker convention in a `fixtures/README.md`
- [X] T038 [US6] Contract-violation regression test in `backend/tests/contract/test_http_contracts.py`: parametrized test that asserts the success body shape and each error shape; a deliberate change (e.g., `status: "active"` or `{"detail": ...}`) causes at least one test to fail (SC-009)

**Checkpoint**: Full onboarding test suite green under no-GPU/no-network; contract regression guard in place.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Observability, failure cleanup, and final validation spanning all stories.

- [X] T039 [P] Structured JSON logging for onboarding in `backend/src/face_insight/api/routes/onboarding.py`: log `{event: "onboarding", duration_ms, outcome: "success"|"rejected"|"error", code?}` via existing `structlog`; NO images, embeddings, or identifiers logged (R-10, FR-016)
- [X] T040 Best-effort FS cleanup on DB commit failure in `backend/src/face_insight/domain/onboarding.py`: wrap DB commit in try/except; on failure call `image_storage.delete(user_id)` to remove the orphaned image, log a warning if cleanup fails (R-5); depends on T013
- [X] T041 [P] Verify `quickstart.md` scenarios match implementation: confirm curl commands, expected statuses/bodies, and verification queries in `specs/002-onboarding-flow/quickstart.md` align with the implemented endpoint and fixtures
- [X] T042 Run full validation suite: `docker compose exec backend pytest tests/unit tests/contract tests/integration -v` and `docker compose exec frontend npx vitest run` under no-GPU/no-network; assert all green (SC-008)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001 for Pillow in T008; T002/T003 for config/constants). BLOCKS all backend user stories.
- **User Stories (Phases 3–8)**: All depend on Foundational completion.
  - US1 (Phase 3) is the MVP and unblocks US2/US3/US5 (they extend the same `OnboardingService` and route handler).
  - US4 (frontend, Phase 6) depends only on T005 (error schema as contract reference) and can proceed in parallel with backend stories.
  - US6 (tests, Phase 8) depends on the implementation stories it covers (US1–US5); T035–T038 can be written in parallel once the corresponding implementations exist.
- **Polish (Phase 9)**: T039/T041 can start after US1; T040 depends on T013; T042 is the final gate after all stories.

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (T004, T005, T006, T007, T008, T010). No dependencies on other stories. **MVP**.
- **US2 (P2)**: Depends on US1 (T013 — extends `OnboardingService` with rejection branches) and T009 (`ScriptableMockDetector`).
- **US3 (P3)**: Depends on US1 (T013/T014 — wires validation into the existing service and route) and T010 (IntegrityError mapping).
- **US4 (P4)**: Depends on T005 (error contract shape). Independent of backend stories — can proceed fully in parallel.
- **US5 (P5)**: Depends on US1 (T014 — route handler enforces limits before detection) and T008.
- **US6 (P6)**: Depends on US1–US5 implementations (tests cover them). T035–T038 are independently writable per target.

### Within Each User Story

- Tests written FIRST and FAIL before implementation (red→green).
- Domain modules before services; services before route handlers; route handlers before composition-root wiring.
- Story complete and independently testable before moving to the next priority.

### Parallel Opportunities

- **Phase 1**: T002 ∥ T003 (different files).
- **Phase 2**: T005 ∥ T006 ∥ T007 ∥ T008 ∥ T009 (all different files, no inter-deps); T004 and T010 are sequential (T010 depends on T004's async ports).
- **Phase 3**: T011 ∥ T012 (independent test files).
- **Phase 4**: T016 ∥ T017.
- **Phase 5**: T020 ∥ T021 ∥ T022.
- **Phase 6**: T025 ∥ T026 ∥ T029; then T027 → T028 → T030.
- **Phase 7**: T031 ∥ T032.
- **Phase 8**: T035 ∥ T036 ∥ T037 (independent); T038 after contract tests exist.
- **Cross-story**: US4 (frontend) runs fully in parallel with US1/US2/US3/US5 (backend) — different file trees, no shared state.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "T011 Contract test for happy-path 201 in backend/tests/contract/test_http_contracts.py"
Task: "T012 Integration test for happy-path onboarding in backend/tests/integration/test_onboarding.py"

# Then sequential implementation:
Task: "T013 Implement OnboardingService.onboard happy path in backend/src/face_insight/domain/onboarding.py"
Task: "T014 Replace onboarding route handler in backend/src/face_insight/api/routes/onboarding.py"
Task: "T015 Wire OnboardingService in composition root"
```

## Parallel Example: Foundational + Frontend (cross-tree)

```bash
# Backend foundational (one developer):
Task: "T004 Make repository ports async"
Task: "T005 Add error response schemas"   # parallel
Task: "T006 Define domain onboarding exceptions"   # parallel
Task: "T007 Implement identifier validation"   # parallel
Task: "T008 Implement image decode/resize"   # parallel
Task: "T009 Add ScriptableMockDetector"   # parallel

# Frontend US4 (another developer, starts once T005 error shape is agreed):
Task: "T029 Add onboarding() multipart upload helper in frontend/src/services/api.ts"
Task: "T027 Implement useOnboardingMachine hook"
Task: "T028 Implement CameraCapture component"
Task: "T030 Replace Onboarding page"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003).
2. Complete Phase 2: Foundational (T004–T010) — CRITICAL, blocks all backend stories.
3. Complete Phase 3: User Story 1 (T011–T015).
4. **STOP and VALIDATE**: Run `pytest tests/integration/test_onboarding.py::test_happy_path` and the happy-path contract test; confirm `201` + persistence + filesystem image.
5. Demo the MVP: `curl -F identifier=... -F consentAccepted=true -F image=@one_face.jpg http://localhost:8000/api/onboarding`.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. + US1 → happy path works → **MVP demo** (backend curl).
3. + US2 → invalid captures rejected safely → demo rejection paths.
4. + US3 → input validation gate → demo duplicate/consent rejections.
5. + US4 → frontend UI → **full demo walk-through** (< 2 min, SC-001).
6. + US5 → image limits enforced → demo oversized/format rejection.
7. + US6 → full test suite green → reproducible safety net for spec 003 (login).
8. Polish → observability + cleanup + final validation.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together.
2. Once Foundational is done:
   - **Developer A (backend)**: US1 → US2 → US3 → US5 (sequential; same `OnboardingService`/route files).
   - **Developer B (frontend)**: US4 (fully independent file tree).
   - **Developer C (tests/fixtures)**: T037 fixtures early, then US6 test tasks as implementations land.
3. Polish (T039–T042) after all stories integrate.

---

## Notes

- [P] tasks = different files, no dependencies — safe to run in parallel.
- [Story] label maps each task to its user story for traceability.
- Each user story is independently completable and testable per its **Independent Test** criterion.
- Write tests FIRST (red), then implement to green.
- Commit after each task or logical group.
- Stop at any checkpoint to validate the story independently.
- **Contract evolution note**: Spec 002 replaces spec 001's stub `{"detail": ...}` error shape with the pinned `{"error": {"code", "message"}}` shape. Contract tests assert the new shape; spec 001 stub assertions are superseded (authorized evolution — the stub explicitly deferred enforcement to spec 002).
- **No schema migration needed** (R-4): the existing `UNIQUE(identifier)` constraint enforces case-insensitive uniqueness on the normalized value. The `0002_onboarding_normalization.py` migration is intentionally omitted.
- Avoid: vague tasks, same-file conflicts across parallel tasks, cross-story dependencies that break independent testability.
