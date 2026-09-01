---

description: "Task list for Concrete Mood & Age Estimation ML Adapters (Fase 5b)"
---

# Tasks: Concrete Mood & Age Estimation ML Adapters (Fase 5b)

**Input**: Design documents from `/specs/009-concrete-mood-age-adapters/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: The constitution mandates tests (Quality Gates §4 tests-first, §5 contract tests, §6 integration tests, §7 no GPU to develop/test). Domain/contract/unit tests use mocks; real-model integration tests are skippable via `pytest.mark.requires_models` / `APP_MODE` guard.

**Organization**: Tasks are grouped by user story (US1..US8) to enable independent implementation and testing of each story. The spec is additive adapter infrastructure — no new ports, entities, result types, endpoints, or frontend changes (FR-017).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Web app layout: `backend/src/`, `backend/tests/` (per plan.md Project Structure).
- Domain layer: `backend/src/face_insight/domain/` (UNCHANGED — FR-017).
- Adapter layer: `backend/src/face_insight/adapters/ml/` (NEW modules + edits).
- Config: `backend/src/face_insight/config.py`.
- Wiring: `backend/src/face_insight/main.py`.
- Deps: `backend/pyproject.toml`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new runtime dependencies isolated to the concrete mood/age adapters (FR-013). No project-structure change — the `adapters/ml/` package, `models/` cache, and `tests/integration/test_real_ml_adapters.py` already exist from spec 008.

- [X] T001 Add `torch` (CPU build), `timm`, and `hsemotion-onnx` (or `emotiefflib[onnx]`) to `backend/pyproject.toml` dependencies; pin `torch` to the CPU build (no CUDA); confirm the existing `requires_models` pytest marker is registered (FR-013, R-9)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story adapter can be implemented — the new config field, the shared model constants + AFEW→PRD label map, the adapter-package exports, and the domain-purity enforcement that keeps the new runtimes out of the domain.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Add `mood_confidence_threshold: float = 0.5` field + a `field_validator` clamping to `[0.0, 1.0]` to `backend/src/face_insight/config.py` `Settings` (env: `MOOD_CONFIDENCE_THRESHOLD`), mirroring the `age_range_half_width_years` pattern (FR-006, R-5)
- [X] T003 [P] Add mood/age model constants to `backend/src/face_insight/adapters/ml/constants.py`: `EMOTIEFF_MODEL_FILENAME`/`URL`/`VERSION` (`"emotieff-enet-b0-afew-v1"`)/`LICENSE` (`"Apache-2.0"`), `MIVOLO_CHECKPOINT_FILENAME`/`URL`/`VERSION` (`"mivolo-volo-d1-face-v1"`)/`LICENSE`, `AFEW_TO_PRD_LABEL_MAP` (0→neutral, 1→feliz, 2→triste, 3→sorprendido, 4-7→no concluyente), and `DEFAULT_MOOD_CONFIDENCE_THRESHOLD = 0.5` (FR-003, FR-005, R-4, R-8)
- [X] T004 Extend `backend/tests/domain/test_domain_purity.py` forbidden-import lists (`FORBIDDEN_PREFIXES` and `REAL_ML_PREFIXES`) with `timm`, `hsemotion`, `emotiefflib`, `mivolo` (FR-012, R-9)
- [X] T005 Add exports for `EmotiEffMoodEstimator`, `MiVOLOAgeEstimator`, and the new constants to `backend/src/face_insight/adapters/ml/__init__.py` (forward references — the modules are created in US1/US2; the exports resolve once those land)

**Checkpoint**: Foundation ready — config field, constants, purity enforcement, and package exports in place; user story adapter implementation can now begin

---

## Phase 3: User Story 1 - Real Mood Estimation via EmotiEff/HSEmotion (Priority: P1) 🎯 MVP

**Goal**: A concrete `EmotiEffMoodEstimator` adapter implementing the existing `MoodEstimator` port using the EmotiEff/HSEmotion ONNX model, returning a PRD §6.4 label + softmax top-1 confidence, with low-certainty predictions gated to "no concluyente".

**Independent Test**: Start with `APP_MODE=production` and the model present; feed a single-face fixture through `estimate_mood()`; assert `label` ∈ `{neutral, feliz, triste, sorprendido, no concluyente}`, `confidence` ∈ [0, 1], `model_version == "emotieff-enet-b0-afew-v1"`. Assert the domain has no `onnxruntime`/`hsemotion` import.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T006 [P] [US1] Add unit test asserting `EmotiEffMoodEstimator` exists, implements `MoodEstimator`, and exposes `model_version == "emotieff-enet-b0-afew-v1"` in `backend/tests/unit/test_ml_licenses.py` (or a new `test_emotieff_mood_adapter.py`), using a mock for the ONNX session (FR-001, FR-003)
- [X] T007 [P] [US1] Add unit test for the AFEW→PRD label mapping + low-confidence override in `backend/tests/unit/test_emotieff_mood_mapping.py`: assert `AFEW_TO_PRD_LABEL_MAP` maps the 8 classes per FR-005 and that top-1 prob < `mood_confidence_threshold` → label `"no concluyente"` (FR-005, FR-006)

### Implementation for User Story 1

- [X] T008 [US1] Create `backend/src/face_insight/adapters/ml/emotieff_mood.py` `EmotiEffMoodEstimator` implementing `MoodEstimator.estimate_mood(face_image: bytes) -> MoodResult`: constructor loads the ONNX model via `ModelDownloader.ensure(EMOTIEFF_MODEL_FILENAME, EMOTIEFF_MODEL_URL)` + constructs the HSEmotion predictor (load-test → `ModelCorruptError`), and constructs an internal YuNet detector + SFace recognizer (cached from spec 008) for `face_crop` alignment; `estimate_mood` decodes bytes → internal YuNet detect → `face_crop` → `predict_probs` → argmax → `AFEW_TO_PRD_LABEL_MAP` → low-confidence override → `MoodResult(label, confidence=top1_prob, model_version=EMOTIEFF_MODEL_VERSION)` (FR-001, FR-005, FR-006, FR-008, R-1, R-7)
- [X] T009 [US1] Add fail-fast error handling to `EmotiEffMoodEstimator` construction: `ModelUnavailableError` on download failure, `ModelCorruptError` on load failure, each naming `EMOTIEFF_MODEL_FILENAME`; raise `ValueError("no face detected for alignment")` when the internal detection finds zero faces (FR-009, R-7)
- [X] T010 [US1] Add structured JSON `model_loaded` log (model name + version) at construction; ensure NO image bytes, mood label, confidence, or biometric response is logged (FR-016, R-12)

**Checkpoint**: `EmotiEffMoodEstimator` conforms to the `MoodEstimator` port and is independently testable with a mock ONNX session

---

## Phase 4: User Story 2 - Real Age Estimation via MiVOLO (Priority: P1) 🎯 MVP

**Goal**: A concrete `MiVOLOAgeEstimator` adapter implementing the existing `AgeEstimator` port using the MiVOLO face-only PyTorch (CPU) model, returning a point-only `AgeResult(range=None)`; the domain `normalize_age_result` (spec 005) derives the symmetric range — no domain change.

**Independent Test**: Start with `APP_MODE=production` and the checkpoint present; feed a single-face fixture through `estimate_age()`; assert `estimated_age` is a non-negative integer, `range is None`, `model_version == "mivolo-volo-d1-face-v1"`. Assert the domain has no `torch`/`timm`/`mivolo` import.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US2] Add unit test asserting `MiVOLOAgeEstimator` exists, implements `AgeEstimator`, exposes `model_version == "mivolo-volo-d1-face-v1"`, and returns `range=None` (point-only) in `backend/tests/unit/test_mivolo_age_adapter.py`, using a mock for the PyTorch predictor (FR-002, FR-003, FR-007)
- [X] T012 [P] [US2] Add license assertion for `MIVOLO_LICENSE == "Apache-2.0"` (code) and document the checkpoint license in `backend/tests/unit/test_ml_licenses.py` (FR-004, R-3)

### Implementation for User Story 2

- [X] T013 [US2] Create `backend/src/face_insight/adapters/ml/mivolo_age.py` `MiVOLOAgeEstimator` implementing `AgeEstimator.estimate_age(face_image: bytes) -> AgeResult`: constructor loads the checkpoint via `ModelDownloader.ensure(MIVOLO_CHECKPOINT_FILENAME, MIVOLO_CHECKPOINT_URL)` + constructs the MiVOLO `VisionAgeGenderPredictor` (`task_type='age'`, `device='cpu'`, load-test → `ModelCorruptError`), and constructs an internal YuNet detector + SFace recognizer (cached from spec 008) for `face_crop` alignment; `estimate_age` decodes bytes → internal YuNet detect → `face_crop` → `predict` → `max(0, round(point))` → `AgeResult(estimated_age=that_int, range=None, model_version=MIVOLO_MODEL_VERSION)` (FR-002, FR-007, FR-008, FR-020, R-2, R-6, R-7)
- [X] T014 [US2] Add fail-fast error handling to `MiVOLOAgeEstimator` construction: `ModelUnavailableError` on download failure, `ModelCorruptError` on load failure, each naming `MIVOLO_CHECKPOINT_FILENAME`; raise `ValueError("no face detected for alignment")` when the internal detection finds zero faces (FR-009, R-7)
- [X] T015 [US2] Add structured JSON `model_loaded` log (model name + version) at construction; ensure NO image bytes, age estimate, or biometric response is logged (FR-016, R-12)

**Checkpoint**: `MiVOLOAgeEstimator` conforms to the `AgeEstimator` port and is independently testable with a mock PyTorch predictor; User Stories 1 AND 2 both deliver concrete adapters

---

## Phase 5: User Story 3 - Shared Face-Crop Reuse for Mood & Age Alignment (Priority: P2)

**Goal**: Confirm both concrete adapters reuse the shared `face_crop` alignment pipeline from spec 008 (internal YuNet detect → `face_crop` → inference), mirroring `SFaceEmbedder`. No new alignment code is introduced.

**Independent Test**: Feed a single-face fixture into both `estimate_mood()` and `estimate_age()`; assert both produce a valid result, confirming the detect → align → infer path works end-to-end through the shared `face_crop`. Feed a no-face image; assert both adapters raise a clear alignment error.

### Tests for User Story 3

- [X] T016 [P] [US3] Add unit test in `backend/tests/unit/test_adapter_alignment.py` asserting both `EmotiEffMoodEstimator` and `MiVOLOAgeEstimator` call `face_crop` (mock the face-crop function and assert it is invoked with the detected face box) and raise on zero faces (FR-008, R-7)

### Implementation for User Story 3

- [X] T017 [US3] Verify/adjust the internal detect → `face_crop` → infer composition in `emotieff_mood.py` and `mivolo_age.py` so both reuse the same `face_crop` utility from spec 008 (no new alignment code); ensure each adapter owns its YuNet + SFace instances for alignment (FR-008, R-7)

**Checkpoint**: Both adapters share the spec 008 alignment pipeline; no new alignment code introduced

---

## Phase 6: User Story 4 - Model Download Reuse for Mood & Age Models (Priority: P2)

**Goal**: Both model files (`enet_b0_8_best_afew.onnx`, MiVOLO face-only age checkpoint) are obtained via the existing `ModelDownloader` from spec 008 (same `models/` cache, atomic `.part`-rename, single-attempt timeout, load-test integrity). Pre-download is supported for air-gapped runs.

**Independent Test**: Start with an empty `models/` cache and `APP_MODE=production`; trigger adapter construction; assert each model file is downloaded once and reused on a second construction. Assert the spec 008 model files are unaffected.

### Tests for User Story 4

- [X] T018 [P] [US4] Add unit test in `backend/tests/unit/test_model_download.py` (or extend the existing spec 008 test) asserting `ModelDownloader.ensure()` is called with `EMOTIEFF_MODEL_FILENAME`/`URL` and `MIVOLO_CHECKPOINT_FILENAME`/`URL` during adapter construction, and that a cache hit returns without re-downloading (FR-009, R-8)
- [X] T019 [P] [US4] Add unit test asserting adapter construction raises `ModelUnavailableError` (network failure) / `ModelCorruptError` (load failure) naming the missing model file, before serving traffic (FR-009, SC-010)

### Implementation for User Story 4

- [X] T020 [US4] Confirm the `ModelDownloader.ensure()` calls in `emotieff_mood.py` and `mivolo_age.py` use the constants from T003 and the existing `models_dir` + timeout settings from spec 008 (no new downloader, cache dir, or compose volume) (FR-009, R-8)

**Checkpoint**: Both model files flow through the spec 008 download/cache infrastructure

---

## Phase 7: User Story 5 - Production Wiring Update (Mood + Age) (Priority: P2)

**Goal**: `wire_production_adapters()` substitutes `EmotiEffMoodEstimator` and `MiVOLOAgeEstimator` for the mock mood/age estimators in production mode; detector/embedder/persistence unchanged; mock mode backward compatible. After this, all four ML ports have concrete real adapters in production (Fase 5 complete).

**Independent Test**: (a) `APP_MODE=production` → `app.state.mood_estimator` is `EmotiEffMoodEstimator`, `app.state.age_estimator` is `MiVOLOAgeEstimator`, detector/embedder still spec 008 concrete. (b) `APP_MODE=mock` → mock instances wired (backward compatible).

### Tests for User Story 5

- [X] T021 [P] [US5] Add production-mode instance-type assertions to `backend/tests/unit/test_wiring_selector.py`: `app.state.mood_estimator` is `EmotiEffMoodEstimator`, `app.state.age_estimator` is `MiVOLOAgeEstimator`, `app.state.detector`/`app.state.embedder` are still `YuNetDetector`/`SFaceEmbedder` (FR-010, SC-001, SC-018)
- [X] T022 [P] [US5] Add mock-mode backward-compatibility assertions to `backend/tests/unit/test_wiring_selector.py`: `APP_MODE=mock` (or unset) wires mock mood/age estimators and requires no models (FR-011, SC-011)

### Implementation for User Story 5

- [X] T023 [US5] Edit `backend/src/face_insight/main.py` `wire_production_adapters()`: replace `MockAgeEstimator()`/`MockMoodEstimator()` with `MiVOLOAgeEstimator()`/`EmotiEffMoodEstimator()` (add the import); leave detector, embedder, persistence, services, `select_wiring`, and `create_app` unchanged (FR-010, FR-011, R-11)

**Checkpoint**: Production mode wires real adapters for all four ML ports; mock mode unchanged

---

## Phase 8: User Story 6 - Real-Model Integration Tests (Priority: P3)

**Goal**: An automated integration suite exercises the concrete mood/age adapters with real model files, verifying labels, confidence, age invariants, and no-face/multi-face handling. Skipped via `requires_models` / `APP_MODE` guard when models absent or mode != production.

**Independent Test**: Run the suite with models present → mood/age assertions pass. Remove models → real-model tests skipped, suite stays green.

### Tests for User Story 6

- [X] T024 [P] [US6] Extend `backend/tests/integration/test_real_ml_adapters.py` `_models_available()` to also check `EMOTIEFF_MODEL_FILENAME` and `MIVOLO_CHECKPOINT_FILENAME` (so the autouse skip fires if any of the four model files is absent) (FR-014, R-10)
- [X] T025 [P] [US6] Add `test_mood_estimator_valid_label_and_confidence` to `backend/tests/integration/test_real_ml_adapters.py`: single-face fixture → label in PRD set, confidence in [0,1], `model_version == EMOTIEFF_MODEL_VERSION` (FR-014, SC-002)
- [X] T026 [P] [US6] Add `test_mood_estimator_low_confidence_no_conclusive` to `backend/tests/integration/test_real_ml_adapters.py`: with `MOOD_CONFIDENCE_THRESHOLD` raised, label is `"no concluyente"` and the low confidence is returned (FR-006, FR-014)
- [X] T027 [P] [US6] Add `test_age_estimator_point_only_and_invariants` to `backend/tests/integration/test_real_ml_adapters.py`: single-face fixture → `estimated_age >= 0`, `range is None`, `model_version == MIVOLO_MODEL_VERSION`; then `normalize_age_result(raw, 5)` → `min >= 0` and `min <= estimated <= max` (FR-007, FR-014, SC-003)
- [X] T028 [P] [US6] Add `test_mood_no_face_raises` / `test_age_no_face_raises` and `test_mood_multi_face` / `test_age_multi_face` to `backend/tests/integration/test_real_ml_adapters.py` using `no_face.jpg` / `multi_face.jpg` fixtures (consented, PRD §12) (FR-014)
- [X] T029 [US6] Add consented test fixtures `single_face.jpg`, `no_face.jpg`, `multi_face.jpg` to `backend/tests/fixtures/real_ml/` if not already present from spec 008 (PRD §12, FR-014)

**Checkpoint**: Real-model integration suite is green with models, skipped without

---

## Phase 9: User Story 7 - Threshold & Calibration Documentation (Priority: P3)

**Goal**: Documentation of the calibration parameters: recommended `mood_confidence_threshold`, the 8 AFEW→PRD label mapping table, recommended `age_range_half_width_years` for MiVOLO + typical error margin, differences from mock behavior, and env-configurability of both thresholds.

**Independent Test**: Review the docs; assert they state the recommended thresholds, the mapping table, the derivation, the mock differences, and confirm both remain env-configurable with mock-mode defaults unchanged.

### Implementation for User Story 7

- [X] T030 [US7] Write/complete `specs/009-concrete-mood-age-adapters/contracts/adapter-port-conformance.md` documenting the `EmotiEffMoodEstimator`/`MiVOLOAgeEstimator` port conformance, the AFEW→PRD label mapping table (FR-005), `model_version` strings (FR-003), and the point-only age output + domain range derivation (FR-007) (FR-015, SC-013)
- [X] T031 [US7] Write/complete `specs/009-concrete-mood-age-adapters/contracts/model-download.md` documenting the model filenames, source URLs, licenses (EmotiEff Apache 2.0, MiVOLO Apache 2.0 code + open-weights checkpoint — R-3), and the `ModelDownloader` reuse + pre-download support (FR-004, FR-009, SC-006)
- [X] T032 [US7] Add the Threshold & Calibration Documentation section to `specs/009-concrete-mood-age-adapters/quickstart.md` (or confirm it is complete): recommended `mood_confidence_threshold` (0.5) + semantics + mock difference; recommended `age_range_half_width_years` (5) + MiVOLO ±3-5 year error margin + symmetric range derivation + mock difference; both env-configurable (FR-015, SC-013)

**Checkpoint**: Calibration docs are complete and reviewable

---

## Phase 10: User Story 8 - Mock Mode & Existing Tests Preserved Unchanged (Priority: P4)

**Goal**: `APP_MODE=mock` (or unset) produces the exact same behavior as specs 001-008: mock adapters wired, no models/runtime required, existing domain/contract/unit tests pass unchanged. The new deps are only imported by the concrete adapters. This is the non-regression safety guarantee.

**Independent Test**: (a) Run existing domain/contract/unit suites with no models → all pass. (b) Start app with `APP_MODE` unset and no `models/` dir → starts as in specs 001-008. (c) Mock adapter source unchanged. (d) Domain has no `torch`/`timm`/`hsemotion`/`onnxruntime`/`cv2` import.

### Tests for User Story 8

- [X] T033 [P] [US8] Add/confirm a regression test in `backend/tests/unit/test_wiring_selector.py` asserting `APP_MODE=mock` wires `MockMoodEstimator`/`MockAgeEstimator` and imports no `adapters.ml.*` mood/age modules (FR-011, FR-018, SC-011, SC-015)
- [X] T034 [US8] Run the existing domain, contract, and unit test suites unchanged with no models present and assert they all pass (non-regression gate; this is a validation step, not a new test file) (FR-018, SC-015)

### Implementation for User Story 8

- [X] T035 [US8] Verify the mock adapters (`backend/src/face_insight/adapters/mock/mood_estimator.py`, `age_estimator.py`) and `wire_mock_adapters()` are retained verbatim — no edit by this spec (FR-017, FR-019, SC-014); confirm the new deps are imported only inside `adapters/ml/emotieff_mood.py` and `adapters/ml/mivolo_age.py` (FR-013, R-9)

**Checkpoint**: Mock mode and the existing test suite are non-regressed

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all stories

- [X] T036 [P] Run `quickstart.md` Scenario 1 (mock mode unchanged) and Scenario 2 (production wiring) end-to-end via `docker compose` (FR-011, FR-010)
- [X] T037 [P] Run `quickstart.md` Scenarios 3-7 (real mood/age, mapping, low-confidence, no-face/multi-face) with models present (FR-001, FR-002, FR-005, FR-006, FR-014)
- [X] T038 Run `quickstart.md` Scenario 8 (real-model tests skip when models absent) and Scenario 9 (domain purity) (FR-014, FR-012, Constitution Quality Gate §7)
- [X] T039 [P] Run `quickstart.md` Scenario 10 (model download + cache reuse) with an empty `models/` cache (FR-009, SC-009, SC-010)
- [X] T040 Confirm no image/label/age/confidence appears in logs across all scenarios (FR-016, SC-016)
- [X] T041 Confirm no changes to detector/embedder adapters, domain ports/entities/result types, HTTP contracts, frontend, or existing tests (FR-017, FR-019, SC-014, SC-017)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001) completion — BLOCKS all user stories
- **User Stories (Phases 3-10)**: All depend on Foundational (Phase 2) completion
  - US1 (Phase 3) and US2 (Phase 4) are co-equal P1 and can proceed in parallel
  - US3 (Phase 5) depends on US1 + US2 (verifies the alignment composition in both adapters)
  - US4 (Phase 6) depends on US1 + US2 (verifies the download calls in both adapters)
  - US5 (Phase 7) depends on US1 + US2 (wires the adapters into production)
  - US6 (Phase 8) depends on US1 + US2 + US5 (exercises the wired adapters with real models)
  - US7 (Phase 9) depends on US1 + US2 (documents their calibration)
  - US8 (Phase 10) depends on US5 (verifies mock mode is non-regressed after the wiring edit)
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependencies on other stories
- **US2 (P1)**: After Foundational — no dependencies on other stories (parallel with US1)
- **US3 (P2)**: After US1 + US2 (alignment reuse verification in both adapters)
- **US4 (P2)**: After US1 + US2 (download reuse verification in both adapters)
- **US5 (P2)**: After US1 + US2 (wiring substitution requires the adapters to exist)
- **US6 (P3)**: After US1 + US2 + US5 (real-model tests need the wired adapters)
- **US7 (P3)**: After US1 + US2 (docs reference the adapters' calibration)
- **US8 (P4)**: After US5 (non-regression check after the wiring edit)

### Within Each User Story

- Tests (where included) MUST be written and FAIL before implementation
- Constants/config before adapter modules
- Adapter modules before wiring
- Story complete before moving to next priority

### Parallel Opportunities

- T003, T004 within Phase 2 can run in parallel (different files)
- US1 (Phase 3) and US2 (Phase 4) can run fully in parallel — different adapter files, no cross-dependency
- All tests marked [P] within a user story can run in parallel
- US3, US4, US7 can run in parallel after US1 + US2 land (different files: alignment test, download test, docs)
- US6 and US8 can run in parallel after US5 (different test files)

---

## Parallel Example: User Stories 1 & 2 (co-equal P1)

```bash
# Launch US1 and US2 in parallel — different adapter files, no cross-dependency:
Task: "US1 — Create EmotiEffMoodEstimator in backend/src/face_insight/adapters/ml/emotieff_mood.py"
Task: "US2 — Create MiVOLOAgeEstimator in backend/src/face_insight/adapters/ml/mivolo_age.py"

# Launch the US1 and US2 test suites together:
Task: "US1 — AFEW mapping + low-confidence tests in backend/tests/unit/test_emotieff_mood_mapping.py"
Task: "US2 — Point-only + license tests in backend/tests/unit/test_mivolo_age_adapter.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2)

1. Complete Phase 1: Setup (T001 — add deps)
2. Complete Phase 2: Foundational (T002-T005 — config, constants, purity, exports)
3. Complete Phase 3 + Phase 4 in parallel: US1 + US2 (the two concrete adapters)
4. **STOP and VALIDATE**: Test US1 and US2 independently with mock ONNX/PyTorch sessions
5. Demo: the concrete mood + age adapters exist behind the ports

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → Concrete mood + age adapters exist (MVP — adapters conform to ports)
3. US3 + US4 → Alignment + download reuse verified
4. US5 → Production wiring substitutes the real adapters (Fase 5 complete)
5. US6 → Real-model integration tests green (with models) / skipped (without)
6. US7 → Calibration documentation complete
7. US8 → Mock mode + existing tests non-regressed
8. Polish → quickstart scenarios validated end-to-end

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (EmotiEff mood adapter)
   - Developer B: US2 (MiVOLO age adapter)
3. After US1 + US2 land:
   - Developer A: US5 (wiring) → US6 (integration tests)
   - Developer B: US3 (alignment) + US4 (download) → US7 (docs)
4. US8 (non-regression) as a final shared gate

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (constitution Quality Gate §4)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- The spec is ADDITIVE: no port, entity, result type, HTTP contract, frontend, mock adapter, or existing test is changed (FR-017/FR-019)
- New deps (`torch` CPU, `timm`, `hsemotion-onnx`) are isolated to `adapters/ml/*` — never imported by domain or mock wiring (FR-013, R-9)
- After this spec, production mode wires real adapters for all four ML ports (detector, embedder, mood, age) — Fase 5 complete (SC-018)

---

## Phase 12: Convergence

**Purpose**: Close documentation defect found by convergence cycle 1 (2026-09-01). The runtime implementation satisfies all FR/SC; this phase fixes a calibration-docs table that contradicts the verified code.

- [X] T042 [US7] Fix the `quickstart.md` Scenario 5 "AFEW → PRD label mapping" table so the index→emotion→PRD-label rows match `AFEW_INDEX_TO_EMOTION_NAME` / `AFEW_TO_PRD_LABEL_MAP` in `backend/src/face_insight/adapters/ml/constants.py` (0=Anger→no concluyente, 1=Contempt→no concluyente, 2=Disgust→no concluyente, 3=Fear→no concluyente, 4=Happiness→feliz, 5=Neutral→neutral, 6=Sadness→triste, 7=Surprise→sorprendido) per FR-005/FR-015/SC-013 (contradicts — the current table lists index 0=Neutral, 1=Happy, 2=Sad, 3=Surprise, 4-7=Anger/Disgust/Fear/Contempt, which is the wrong AFEW index ordering and contradicts the HSEmotion-onnx library `idx_to_class` verified by `test_afew_index_order_matches_library`)
