---

description: "Task list for Concrete Face Detection & Embedding ML Adapters (Fase 5a — Detector + Embedder)"
---

# Tasks: Concrete Face Detection & Embedding ML Adapters (Fase 5a — Detector + Embedder)

**Input**: Design documents from `/specs/008-concrete-ml-adapters/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: No constitution file is present in this repo. Tests are mandated by the spec itself: FR-015 (real-model integration suite, skippable) and FR-019 (existing domain/contract/unit suites preserved unchanged). Test tasks are included for every user story that introduces runtime behavior or a public adapter contract.

**Organization**: Tasks are grouped by user story. The spec has 8 user stories (US1–US8) with priorities P1→P4. US1 (YuNetDetector) and US2 (SFaceEmbedder) are co-equal P1 MVP. US4 (ModelDownloader) is labeled P2 in the spec but is *enabling infrastructure* for US1/US2 — its core `ModelDownloader` implementation is therefore placed in Phase 2 (Foundational) as a blocking prerequisite so US1/US2 remain independently buildable; US4's own phase validates and configures it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/` (existing layout per plan.md)
- New code lives under `backend/src/face_insight/adapters/ml/`
- `models/` cache sits at repo root (next to `usuarios/`), bind-mounted into the backend container

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add runtime dependencies, test markers, and the model cache directory.

- [X] T001 Add runtime dependencies `opencv-python-headless`, `onnxruntime`, `numpy` to `backend/pyproject.toml` (FR-014)
- [X] T002 [P] Register `pytest.mark.requires_models` marker in `backend/pyproject.toml` `[tool.pytest.ini_options] markers` (FR-015, R-6)
- [X] T003 [P] Create `models/` cache directory at repo root and add `models/` to `.gitignore` (FR-008)
- [X] T004 [P] Edit `backend/Dockerfile` if needed — ensure `models/` dir creation and any system deps for opencv headless (R-9)

**Checkpoint**: Dependencies and cache dir ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story adapter can be implemented. This includes the `ModelDownloader` (US4's core deliverable), which is placed here because US1 (YuNetDetector) and US2 (SFaceEmbedder) both require it to load their model files — placing it here keeps US1/US2 independently buildable.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Edit `backend/src/face_insight/config.py` `Settings` — add `models_dir: str` (default `<repo_root>/models`), `model_download_connect_timeout: float = 30.0`, `model_download_read_timeout: float = 120.0` (FR-008, data-model Configuration Surface)
- [X] T006 [P] Create `backend/src/face_insight/adapters/ml/__init__.py` and `backend/src/face_insight/adapters/ml/constants.py` — model URLs (YuNet + SFace OpenCV zoo raw URLs per R-4), version strings (`yunet-2023mar-v1`, `sface-2021dec-v1`), `EMBEDDING_DIM=128`, recommended thresholds, error classes (`ModelUnavailableError`, `ModelCorruptError`, `InvalidFaceBox`) (FR-003, R-4)
- [X] T007 Create `backend/src/face_insight/adapters/ml/model_downloader.py` — `ModelDownloader.ensure(name, url) -> Path`: cache hit → return path; else `httpx` download to `<model>.onnx.part` → atomic `os.replace` → return path; single attempt with configurable timeout; `ModelUnavailableError` on httpx error/timeout; lone `.part` treated as absent (FR-008, FR-009, R-4)
- [X] T008 [P] Edit `docker-compose.yml` — add `./models:/app/models:rw` volume bind mount to backend service; set `VERIFICATION_THRESHOLD: "0.363"` for production (FR-010, R-7)
- [X] T009 [P] Edit `backend/tests/domain/test_domain_purity.py` — extend forbidden-import assertion set to include `cv2`, `onnxruntime`, `numpy`, and `adapters.ml` (FR-013, R-10)

**Checkpoint**: Foundation ready — config, constants, ModelDownloader, compose volume, and domain purity guard in place. User story adapter implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Real Face Detection via YuNet in Production Mode (Priority: P1) 🎯 MVP

**Goal**: Concrete `YuNetDetector` implementing the existing `Detector` port via OpenCV DNN, returning `DetectionResult` with `face_count`/`boxes`/`score` (FR-001, FR-005).

**Independent Test**: Construct `YuNetDetector` with the YuNet model present; feed a single-face image → `face_count == 1` with valid `BoundingBox` and `score >= quality_threshold`; feed a face-less image → `face_count == 0`. Assert domain layer has no `cv2`/`yunet` import.

### Tests for User Story 1

> **NOTE: Write these FIRST, ensure they FAIL before implementation.**

- [X] T010 [P] [US1] Create port-conformance unit test in `backend/tests/unit/test_yunet_detector.py` — assert `YuNetDetector` implements `Detector` protocol signature, exposes `model_version == "yunet-2023mar-v1"` (FR-003), and maps detect output to `DetectionResult` shape (no model file needed for shape assertions)

### Implementation for User Story 1

- [X] T011 [US1] Create `backend/src/face_insight/adapters/ml/yunet_detector.py` — `YuNetDetector` implementing `Detector.detect(image: bytes) -> DetectionResult` via `cv2.FaceDetectorYN_create` (R-1); decode bytes with `cv2.imdecode`, set input size, run `detect`, map rows → `BoundingBox` list + `score = max(row[14])` per R-2; construct with `score_threshold = settings.quality_threshold`, `nms_threshold=0.3`, `top_k=5000`
- [X] T012 [US1] Export `YuNetDetector` from `backend/src/face_insight/adapters/ml/__init__.py`
- [X] T013 [US1] Add fail-fast construction in `YuNetDetector.__init__` — call `ModelDownloader.ensure()` then `cv2.FaceDetectorYN_create(...)`; wrap load failure in `ModelCorruptError` naming the model (FR-009)

**Checkpoint**: `YuNetDetector` conforms to the `Detector` port and is independently testable.

---

## Phase 4: User Story 2 - Real Face Embedding via SFace in Production Mode (Priority: P1) 🎯 MVP

**Goal**: Concrete `SFaceEmbedder` implementing the existing `Embedder` port via OpenCV DNN, returning a 128-dim L2-normalized `Embedding` (FR-002, FR-006). Resolves Constitution OQ-4.

**Independent Test**: Construct `SFaceEmbedder` with the SFace model present; embed two crops of the same person → cosine similarity ≥ 0.363; embed two different people → cosine similarity < 0.363; assert `len(vector) == 128` and `model_version == "sface-2021dec-v1"`. Assert domain layer has no `onnxruntime`/`sface` import.

### Tests for User Story 2

> **NOTE: Write these FIRST, ensure they FAIL before implementation.**

- [X] T014 [P] [US2] Create port-conformance unit test in `backend/tests/unit/test_sface_embedder.py` — assert `SFaceEmbedder` implements `Embedder` protocol signature, exposes `model_version == "sface-2021dec-v1"` (FR-003), and `EMBEDDING_DIM == 128` constant matches mock (R-3)

### Implementation for User Story 2

- [X] T015 [US2] Create `backend/src/face_insight/adapters/ml/sface_embedder.py` — `SFaceEmbedder` implementing `Embedder.embed(face_image: bytes) -> Embedding` via `cv2.FaceRecognizerSF_create` (R-1); on `embed()`: decode bytes → internal YuNet detect for face-box+landmarks → `face_crop` (alignCrop) → `feature()` → 128-dim `list[float]` → `Embedding(vector, "sface-2021dec-v1")` per R-3/R-5; share cached YuNet model file with `YuNetDetector`
- [X] T016 [US2] Export `SFaceEmbedder` from `backend/src/face_insight/adapters/ml/__init__.py`
- [X] T017 [US2] Add fail-fast construction in `SFaceEmbedder.__init__` — `ModelDownloader.ensure()` for SFace + YuNet, then `cv2.FaceRecognizerSF_create(...)`; wrap load failure in `ModelCorruptError` (FR-009)

**Checkpoint**: `SFaceEmbedder` conforms to the `Embedder` port and is independently testable. User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Shared Face-Crop & Alignment Pipeline (Priority: P2)

**Goal**: Shared `face_crop` adapter utility wrapping OpenCV's `alignCrop` affine transform, used by both onboarding and login routes for consistent alignment before embedding (FR-007).

**Independent Test**: Feed a test image + known bounding box + landmarks into `face_crop` → assert output is a fixed-size (112×112) aligned crop; feed a degenerate (zero-area) box → assert `InvalidFaceBox` error. No model file needed.

### Tests for User Story 3

> **NOTE: Write these FIRST, ensure they FAIL before implementation.**

- [X] T018 [P] [US3] Create unit test in `backend/tests/unit/test_face_crop.py` — assert `InvalidFaceBox` raised on zero-area and negative-area boxes; assert valid box returns an aligned crop of expected dimensions (no model file required, R-5)

### Implementation for User Story 3

- [X] T019 [US3] Create `backend/src/face_insight/adapters/ml/face_crop.py` — `face_crop(recognizer, src_img, face_box) -> cv2.Mat` wrapping `cv2.FaceRecognizerSF.alignCrop` (affine transform from 5 landmarks); raise `InvalidFaceBox` on zero/negative-area box (FR-007 AC-3, R-5)
- [X] T020 [US3] Export `face_crop` from `backend/src/face_insight/adapters/ml/__init__.py`
- [X] T021 [US3] Wire `face_crop` into `SFaceEmbedder.embed()` alignment path (T015) so both onboarding and login routes align through the same shared instance (FR-007 AC-2)

**Checkpoint**: Alignment pipeline verified; embedder receives consistently aligned crops.

---

## Phase 6: User Story 4 - Model Download/Cache & Docker Volume (Priority: P2)

**Goal**: Validate and configure the `ModelDownloader` (implemented in Foundational T007) — cache reuse, atomic rename, fail-fast, offline pre-download, and the Docker volume bind mount (FR-008, FR-010).

**Note**: The `ModelDownloader` implementation lives in Phase 2 (Foundational T007) because US1/US2 depend on it. This phase validates its behavior and documents the offline fallback.

**Independent Test**: Start with empty `models/` + `APP_MODE=production`; trigger adapter construction → each model downloaded once and reused on second construction (no re-download). Bring up compose stack → `models/` bind-mounted into backend container with matching in-container path.

### Tests for User Story 4

- [X] T022 [P] [US4] Add cache-hit/reuse unit test in `backend/tests/unit/test_model_downloader.py` — assert second `ensure()` call returns cached path without network fetch (FR-008 AC-2, SC-008)
- [X] T023 [P] [US4] Add fail-fast unit test in `backend/tests/unit/test_model_downloader.py` — assert `ModelUnavailableError` on network failure/timeout and `ModelCorruptError` on corrupt file; assert atomic `.part` rename leaves no partial cache entry (FR-008, FR-009, SC-010)

### Implementation for User Story 4

- [X] T024 [US4] Document pre-download / air-gapped offline fallback in `specs/008-concrete-ml-adapters/quickstart.md` — pre-place `.onnx` files in `models/` to avoid runtime network (FR-008 AC-4)
- [X] T025 [US4] Verify docker-compose bind mount from T008 — validate Scenario 7 (`docker compose exec backend ls -la /app/models` reflects host `./models`); in-container path matches `settings.models_dir` (FR-010, SC-009)

**Checkpoint**: Model supply is cached, volume-backed, and reproducible across machines.

---

## Phase 7: User Story 5 - Production Wiring Update (Detector + Embedder Only) (Priority: P2)

**Goal**: Update `wire_production_adapters()` to substitute `YuNetDetector` + `SFaceEmbedder` for `MockDetector` + `MockEmbedder` when `APP_MODE=production`; mood/age stay mock (spec 009); mock mode backward compatible (FR-011, FR-012).

**Independent Test**: (a) `APP_MODE=production` + models present → `app.state.detector` is `YuNetDetector`, `app.state.embedder` is `SFaceEmbedder`, mood/age still mock. (b) `APP_MODE=mock` → mock instances (backward compatible).

### Tests for User Story 5

- [X] T026 [P] [US5] Edit `backend/tests/unit/test_wiring_selector.py` — assert production mode wires `YuNetDetector`/`SFaceEmbedder` instance types and keeps `MockAgeEstimator`/`MockMoodEstimator`; assert mock mode wires mock detector/embedder (backward compatible, FR-011/FR-012, SC-001)

### Implementation for User Story 5

- [X] T027 [US5] Edit `backend/src/face_insight/main.py` `wire_production_adapters()` — replace `MockDetector()`/`MockEmbedder()` construction with `YuNetDetector(...)`/`SFaceEmbedder(...)`; keep `MockAgeEstimator`/`MockMoodEstimator`; leave real SQLAlchemy persistence adapters unchanged (FR-011)
- [X] T028 [US5] Add production-mode `verification_threshold` override to `0.363` in `wire_production_adapters` (or config) when `APP_MODE=production` **unless** `VERIFICATION_THRESHOLD` is explicitly set in the environment; mock-mode default stays `0.5` (FR-016, R-7)

**Checkpoint**: Production app runs real detection + real embedding with real persistence; mock mode unchanged.

---

## Phase 8: User Story 6 - Real-Model Integration Tests (Priority: P3)

**Goal**: Automated integration suite exercising concrete adapters with real model files; skippable when models absent or `APP_MODE != production` (FR-015, Constitution Quality Gate §7).

**Independent Test**: Run suite with models present → all detector/embedder/similarity assertions pass. Remove models → real-model tests skipped, rest of suite green.

### Tests for User Story 6

- [X] T029 [US6] Create `backend/tests/integration/test_real_ml_adapters.py` — add `pytest.mark.requires_models` autouse skip guard: skip when model files absent OR `settings.app_mode != "production"` (FR-015, R-6)
- [X] T030 [US6] Add detector integration assertions — single-face fixture → `face_count == 1` + valid box + `score >= quality_threshold`; face-less fixture → `face_count == 0`; multi-face fixture → `face_count == N` (FR-005, SC-002)
- [X] T031 [US6] Add embedder integration assertions — `len(vector) == 128`, `model_version == "sface-2021dec-v1"`; same-person cosine ≥ 0.363; different-person cosine < 0.363 (FR-006, SC-003)
- [X] T032 [US6] Add consented test fixtures under `backend/tests/fixtures/real_ml/` (single-face, no-face, multi-face, same-person pair, different-person pair) — gitignored or committed with documented consent (PRD §12, FR-015 AC-4)

**Checkpoint**: Real-model correctness verified; CI without models stays green.

---

## Phase 9: User Story 7 - Threshold Calibration Documentation (Priority: P3)

**Goal**: Document the recommended SFace+YuNet cosine threshold (0.363), its derivation, and the difference from the mock 0.5; confirm `verification_threshold` remains env-configurable (FR-016, SC-013).

**Independent Test**: Review the calibration docs → recommended threshold stated, derivation described, mock difference noted, configurability confirmed.

### Implementation for User Story 7

- [X] T033 [US7] Add Threshold Calibration section to `specs/008-concrete-ml-adapters/quickstart.md` — recommended cosine threshold 0.363, OpenCV LFW derivation (99.60% accuracy), difference from mock 0.5, env-configurable via `VERIFICATION_THRESHOLD` (FR-016, R-7)
- [X] T034 [P] [US7] Document calibration in `specs/008-concrete-ml-adapters/contracts/adapter-port-conformance.md` — SFace+YuNet cosine threshold, calibration source URL, mode-specific defaults table

**Checkpoint**: Verification threshold is documented, calibrated, and configurable.

---

## Phase 10: User Story 8 - Mock Mode & Existing Tests Preserved Unchanged (Priority: P4)

**Goal**: Guarantee the concrete-adapter addition is non-destructive — mock mode and existing domain/contract/unit suites pass unchanged with no models present (FR-012, FR-018, FR-019).

**Independent Test**: (a) Run existing domain/contract/unit suites with no models → all pass. (b) Start app with `APP_MODE` unset + no `models/` dir → starts as specs 001-007. (c) Mock adapter source unchanged. (d) Domain layer has no opencv/onnxruntime/numpy import.

### Implementation for User Story 8

- [X] T035 [US8] Verify mock adapters retained verbatim — diff `backend/src/face_insight/adapters/mock/` against specs 001-007 baseline; confirm no source changes (FR-018 AC-3, SC-014)
- [X] T036 [US8] Verify existing domain/contract/unit suites pass unchanged with no models present — run quickstart Scenario 1 (`APP_MODE=mock pytest tests/domain tests/contract tests/unit`) (FR-019, SC-015)
- [X] T037 [US8] Verify `APP_MODE` unset/mock starts without `models/` dir and without ML runtime — run quickstart Scenario 1 app start; assert `MockDetector`/`MockEmbedder` wired (FR-012, SC-011)

**Checkpoint**: Non-regression confirmed; mock mode and existing tests intact.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [X] T038 [P] Update `specs/008-concrete-ml-adapters/contracts/README.md` and `specs/008-concrete-ml-adapters/contracts/model-download.md` — adapter port conformance summary, model download contract (FR-008/FR-009)
- [X] T039 [P] Run `specs/008-concrete-ml-adapters/quickstart.md` validation scenarios 1–8 end-to-end against the implemented stack
- [X] T040 Verify no image, embedding vector, or biometric response appears in logs — structured JSON logs only (adapter loaded, model version, operation duration/status) (FR-017, SC-016)
- [X] T041 [P] Confirm scope boundaries — no new endpoints/entities/ports/result-types/frontend changes; no concrete mood/age (spec 009); no 1:N/liveness/training (FR-020, SC-017)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - US1 (YuNetDetector) and US2 (SFaceEmbedder) can proceed in parallel after Foundational.
  - US3 (face_crop) can proceed in parallel after Foundational; T021 (wire into SFaceEmbedder) depends on T015 (US2).
  - US4 (ModelDownloader validation) can proceed in parallel after Foundational — its core implementation is T007 in Foundational.
  - US5 (production wiring) depends on US1 (T012) + US2 (T016) — wiring references the concrete adapter classes.
  - US6 (integration tests) depends on US1 + US2 + US3 + US5 (wired, working adapters).
  - US7 (calibration docs) depends on US5 (threshold override in place).
  - US8 (non-regression) depends on US5 (to confirm mock path unchanged).
- **Polish (Phase 11)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (T007 ModelDownloader). No dependencies on other stories.
- **US2 (P1)**: Depends on Foundational (T007 ModelDownloader). T021 (US3) wires into it, but US2 is independently buildable first.
- **US3 (P2)**: Depends on Foundational. T021 depends on US2 T015.
- **US4 (P2)**: Depends on Foundational T007 (its own core, placed there as blocking infra). Validates/configures ModelDownloader.
- **US5 (P2)**: Depends on US1 + US2 (wires the concrete adapter classes).
- **US6 (P3)**: Depends on US1 + US2 + US3 + US5.
- **US7 (P3)**: Depends on US5 (threshold override).
- **US8 (P4)**: Depends on US5 (confirms mock path preserved).

### Within Each User Story

- Tests (where included) MUST be written and FAIL before implementation.
- Models/constants before adapters.
- Adapters before wiring.
- Wiring before integration tests.
- Story complete before moving to next priority.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002, T003, T004).
- All Foundational tasks marked [P] can run in parallel within Phase 2 (T006, T008, T009); T005 and T007 are sequential prerequisites.
- Once Foundational completes, US1, US2, US3, and US4 can all start in parallel (if team capacity allows).
- All tests for a user story marked [P] can run in parallel (T010/T011 within US1; T022/T023 within US4; etc.).
- US7's two doc tasks (T033/T034) can run in parallel.
- Polish doc/validation tasks (T038/T039/T041) can run in parallel.

---

## Parallel Example: User Story 1 + User Story 2 (after Foundational)

```bash
# Foundational complete → launch US1 and US2 in parallel (different files, no cross-deps):
Task: "T010 [US1] port-conformance test in tests/unit/test_yunet_detector.py"
Task: "T014 [US2] port-conformance test in tests/unit/test_sface_embedder.py"

# Then adapters in parallel:
Task: "T011 [US1] YuNetDetector in adapters/ml/yunet_detector.py"
Task: "T015 [US2] SFaceEmbedder in adapters/ml/sface_embedder.py"
```

## Parallel Example: Foundational Phase

```bash
# T005 (config) and T007 (ModelDownloader) are sequential (T007 may reference settings).
# T006, T008, T009 can run in parallel after T005:
Task: "T006 adapters/ml/__init__.py + constants.py"
Task: "T008 docker-compose.yml bind mount + VERIFICATION_THRESHOLD"
Task: "T009 tests/domain/test_domain_purity.py forbidden imports"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: US1 (YuNetDetector) + Phase 4: US2 (SFaceEmbedder) — these are co-equal P1 and can proceed in parallel.
4. **STOP and VALIDATE**: Test US1 and US2 independently (real detection + real embedding behind the ports).
5. Deploy/demo if ready.

### Incremental Delivery

1. Complete Setup + Foundational → foundation ready.
2. Add US1 + US2 → test independently → real detection + embedding work (MVP!).
3. Add US3 → alignment pipeline improves embedding quality.
4. Add US4 → model supply validated, volume-backed, offline-capable.
5. Add US5 → production wiring substitutes real adapters.
6. Add US6 → real-model integration suite green (or skipped).
7. Add US7 → threshold calibration documented.
8. Add US8 → non-regression confirmed.
9. Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together.
2. Once Foundational is done:
   - Developer A: US1 (YuNetDetector)
   - Developer B: US2 (SFaceEmbedder)
   - Developer C: US3 (face_crop) + US4 (ModelDownloader validation)
3. US5 (wiring) proceeds once US1 + US2 land.
4. US6 (integration tests) proceeds once US5 lands.
5. US7 (docs) + US8 (non-regression) proceed in parallel after US5.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Each user story should be independently completable and testable.
- Verify tests fail before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
- **Key spec constraint**: No domain port/entity/result-type/HTTP-contract/frontend change (FR-018). The spec is additive — new concrete adapters implement existing ports.
- **ModelDownloader placement**: Implemented in Foundational (T007) rather than US4's phase because US1/US2 hard-depend on it; US4's phase validates and configures it. This preserves US1/US2 independent buildability.
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence.

---

## Phase 12: Convergence

**Purpose**: Close the gap found by convergence cycle 1 (F-001). The `ModelDownloader.ensure()` cache-filename construction double-appends `.onnx`, breaking the offline pre-download path (FR-008 AC-4), the documented cache filenames (SC-008), and the real-model integration suite's model-presence detection (SC-012/FR-015).

- [X] T042 Fix `ModelDownloader.ensure()` in `backend/src/face_insight/adapters/ml/model_downloader.py` — treat `model_name` as the complete filename (callers pass `YUNET_MODEL_FILENAME`/`SFACE_MODEL_FILENAME` which already include `.onnx`): set `final_path = self._cache_dir / model_name` and `part_path = self._cache_dir / f"{model_name}.part"` so the cached file is `models/face_detection_yunet_2023mar.onnx` (not `.onnx.onnx`). Add a regression unit test in `backend/tests/unit/test_model_downloader.py` using the real `YUNET_MODEL_FILENAME` (ends in `.onnx`) asserting the cached path has no double extension and that a pre-placed `models/face_detection_yunet_2023mar.onnx` is a cache hit (FR-008 AC-2/AC-4, SC-008, SC-012)
