# Feature Specification: Concrete Face Detection & Embedding ML Adapters (Fase 5a — Detector + Embedder)

**Feature Branch**: `008-concrete-ml-adapters`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Concrete face detection and embedding ML adapters (PRD §18 Fase 5a — 'Modelos reales', detector + embedder portion). This spec wires concrete open-source ML adapters behind the existing hexagonal Detector and Embedder ports, resolving Constitution OQ-4 (embedding model). It builds on specs 001 (ports/mocks), 002 (onboarding), 003 (login/session), 007 (APP_MODE selector + production wiring foundation). Currently, wire_production_adapters() (from spec 007) uses real DB adapters but mock ML adapters. This spec adds: (1) Concrete Detector adapter YuNetDetector using YuNet via OpenCV DNN; (2) Concrete Embedder adapter SFaceEmbedder using SFace via OpenCV DNN / ONNX Runtime; (3) Shared face-crop + alignment pipeline; (4) Model download/cache directory + Docker volume bind mount + ModelDownloader; (5) Update wire_production_adapters() to use YuNetDetector + SFaceEmbedder when APP_MODE=production (mood/age stay mock — spec 009); (6) New runtime deps opencv-python-headless, onnxruntime, numpy; (7) Real-model integration tests (skipped when models absent or APP_MODE != production); (8) Threshold calibration documentation. Resolves OQ-4."

## Clarifications

### Session 2026-09-01

- Q: Which inference backend do the concrete adapters use — OpenCV DNN only, ONNX Runtime only, or both? -> A: OpenCV's DNN module is the single concrete inference backend for both YuNet and SFace (both `.onnx` files load via `cv2.dnn.readNetFromONNX`). `onnxruntime` remains a declared runtime dependency (FR-014) available as an OpenCV DNN backend, but the adapters make no direct `onnxruntime` API calls — one backend keeps the adapter code simple and the dependency surface coherent.
- Q: How does `ModelDownloader` verify a fetched model file's integrity — checksum/signature or load-test? -> A: Load-test verification: after download, the adapter attempts to load the model via OpenCV DNN at construction time; a corrupt/truncated file fails fast per FR-009. No separate checksum/signature verification (the OpenCV model repository does not publish signed checksums in a standard way, and Constitution Principle VIII explicitly waives security guarantees). Load-failure → clear actionable error naming the model.
- Q: How are concurrent downloads and partial-file writes handled? -> A: Atomic-rename with a `.part` temp file: the download writes to `<model>.onnx.part`, then atomically renames to `<model>.onnx` on completion. A `.part` file is never treated as a valid cache entry; a construction that finds only a `.part` re-downloads. For the demo's single-process startup this rarely races, but atomic rename guarantees no partial file is cached (closes the "interrupted mid-fetch" edge case).
- Q: What is the model-download timeout and retry policy? -> A: Single attempt, configurable timeout (default 30s connect / 120s read). On timeout or network error, fail fast per FR-009 with an actionable error naming the model and URL — no automatic retry (retry can mask upstream issues; the user re-runs `docker compose up`). Pre-placing model files (pre-download) remains the supported offline/reproducible fallback.
- Q: What is SFace's exact embedding dimension, and is it pinned in the spec? -> A: Pinned to **128** dimensions for `sface-2021dec-v1`. SFace as distributed via OpenCV produces a 128-dimensional L2-normalized embedding vector. This matches the mock embedder's 128-dim vector (spec 001), so the `Embedding` result type and stored `FaceTemplate` schema are unchanged (FR-018 scope boundary respected). The dimension is documented in the calibration docs (User Story 7) and asserted in the real-model integration tests (User Story 6).

## User Scenarios & Testing *(mandatory)*

<!--
  This is a Fase 5a "real models" spec. Its primary "users" are the development
  team and the demo audience: the value delivered is a production-mode app that
  performs real face detection (YuNet) and real face embedding (SFace) behind the
  existing hexagonal ports, with no changes to the domain layer, the mock
  adapters, the HTTP contracts, or the frontend. Stories are ordered so each
  independently delivers a demonstrable, testable slice and maps to PRD §18 Fase 5
  (detector + embedder), PRD §11 (vision requirements), and Constitution
  Principles III (open-source ML) and VII (hexagonal — concrete adapters behind
  ports). No new endpoints, entities, ports, or frontend changes are introduced.
-->

### User Story 1 - Real Face Detection via YuNet in Production Mode (Priority: P1)

When the application is started in production mode (`APP_MODE=production`) with the concrete ML adapters wired, onboarding and login perform **real face detection** using the YuNet open-source face detection model (via OpenCV's DNN module). The detector adapter (`YuNetDetector`) implements the existing `Detector` port and returns a `DetectionResult` containing the bounding box, detection score, and face count — the exact contract PRD §11 mandates ("el detector debe devolver como mínimo bounding box, score y cantidad de rostros detectados"). Given a test image containing exactly one face, the real detector finds exactly one face with a score above the quality threshold; given an image with no face, it returns `face_count=0`. The domain layer never imports OpenCV or the model directly (Constitution Principle VII — "la capa de dominio no debe importar directamente la implementación de YOLO").

**Why this priority**: Real detection is the first half of the spec's core deliverable and the reason it exists. Without a concrete detector, the production app cannot locate a real face in a real captured image, and the embedding step has no aligned face crop to operate on. It delivers PRD §18 Fase 5 ("sustituir detector mock por YOLO"), PRD §11 (detector contract + domain isolation), and Constitution Principle III (open-source ML). Every subsequent story depends on this adapter existing and conforming to the port.

**Independent Test**: Start the app with `APP_MODE=production` and the YuNet model present in the models cache. Feed a test image containing exactly one face through the detector; assert `DetectionResult.face_count == 1`, a non-empty `boxes` list with a valid `BoundingBox`, and `score` above the quality threshold. Feed a face-less image; assert `face_count == 0`. Assert the domain layer source has no `cv2` / `opencv` / `yunet` import. Delivers a verifiable real detector behind the port.

**Acceptance Scenarios**:

1. **Given** the app is started with `APP_MODE=production` and the YuNet model is available, **When** an image containing exactly one face is detected, **Then** `YuNetDetector.detect()` returns a `DetectionResult` with `face_count == 1`, a `BoundingBox` enclosing the face, and a `score` reflecting the model's confidence (PRD §11).
2. **Given** an image containing no face, **When** detected, **Then** the result has `face_count == 0` and an empty `boxes` list.
3. **Given** an image containing multiple faces, **When** detected, **Then** the result `face_count` equals the number of detected faces and `boxes` contains one box per face.
4. **Given** the domain layer, **When** its imports are inspected, **Then** it has no direct dependency on OpenCV, ONNX Runtime, YuNet, or any concrete model file (Constitution Principle VII, PRD §11).
5. **Given** `YuNetDetector`, **When** its `model_version` is inspected, **Then** it exposes an identifiable, fixed version string (e.g. `yunet-2023mar-v1`) so results are reproducible (PRD §11 — "los modelos deben tener una versión identificable").

---

### User Story 2 - Real Face Embedding via SFace in Production Mode (Priority: P1)

When the application is started in production mode with the concrete ML adapters wired, onboarding and login compute **real face embeddings** using the SFace open-source face recognition model (via OpenCV's DNN module / ONNX Runtime). The embedder adapter (`SFaceEmbedder`) implements the existing `Embedder` port and returns an `Embedding` containing a fixed-length vector and an identifiable `model_version`. Two embeddings of the same person's face yield a cosine similarity above the verification threshold; embeddings of different people yield a cosine similarity below the threshold. This resolves Constitution Open Question OQ-4 (embedding model) to SFace, an open-weights Apache-2.0 / MIT-licensed model — satisfying Constitution Principle III (all models must be open-source).

**Why this priority**: Real embedding is the second half of the spec's core deliverable. Without a concrete embedder, the production app cannot produce a comparable facial representation, and 1:1 verification (PRD §6.3) cannot work against a real captured image. It delivers PRD §18 Fase 5 ("integrar modelo de embeddings"), PRD §11 ("la generación de embeddings debe estar detrás de una interfaz o puerto reemplazable"), and resolves OQ-4. It is co-equal with User Story 1.

**Independent Test**: Start the app with `APP_MODE=production` and the SFace model present. Embed two different crops of the same person; assert the cosine similarity of the two vectors exceeds the verification threshold. Embed crops of two different people; assert the cosine similarity is below the threshold. Assert the returned vector has a fixed, documented length and a non-empty `model_version`. Assert the domain layer has no `onnxruntime` / `sface` import. Delivers a verifiable real embedder behind the port.

**Acceptance Scenarios**:

1. **Given** the app is started with `APP_MODE=production` and the SFace model is available, **When** a cropped, aligned face image is embedded, **Then** `SFaceEmbedder.embed()` returns an `Embedding` with a fixed-length `vector` (documented dimension) and an identifiable `model_version` (e.g. `sface-2021dec-v1`) (PRD §11).
2. **Given** two embeddings of the same person's face, **When** their cosine similarity is computed, **Then** the similarity exceeds the configured verification threshold (same-person match).
3. **Given** two embeddings of different people's faces, **When** their cosine similarity is computed, **Then** the similarity is below the configured verification threshold (different-person non-match).
4. **Given** the domain layer, **When** its imports are inspected, **Then** it has no direct dependency on ONNX Runtime, SFace, or any concrete model file (Constitution Principle VII, PRD §11).
5. **Given** the embedding model, **When** its license is inspected, **Then** it is an OSI-approved open-source license (Apache 2.0 / MIT), satisfying Constitution Principle III.

---

### User Story 3 - Shared Face-Crop & Alignment Pipeline (Priority: P2)

A shared face-crop and alignment pipeline (`face_crop`) takes a source image, a detection bounding box, and the detected facial landmarks, and produces an aligned, cropped face image suitable for the embedder. The pipeline uses an affine transformation (via OpenCV) to normalize face pose/position before embedding, improving embedding quality and verification accuracy. This pipeline is used by both onboarding and login so the embedder always receives a consistently aligned face. It is an internal adapter utility — not a domain port — and the domain layer does not import it directly.

**Why this priority**: The crop/align pipeline is the glue between detection and embedding: without it, the embedder receives a raw, unaligned region and embedding quality degrades, weakening the same-person/different-person separation that User Stories 1 and 2 depend on. It is independently testable by feeding a known image + box + landmarks and asserting the output is a fixed-size aligned crop. It is P2 because it supports the P1 adapters rather than standing alone as user-visible value.

**Independent Test**: Feed a test image with a known bounding box and landmark set into the face-crop pipeline; assert the output is a decoded image of the expected aligned dimensions (e.g. 112×112) with the face centered. Feed a degenerate box (zero area); assert a clear, recoverable error. Delivers a verifiable alignment step that feeds the embedder.

**Acceptance Scenarios**:

1. **Given** a source image, a detection bounding box, and facial landmarks, **When** the face-crop pipeline runs, **Then** it produces an aligned, cropped face image of a fixed size suitable for the embedder.
2. **Given** onboarding and login both detect then embed, **When** the flow is inspected, **Then** both routes pass the detected face through the same shared alignment pipeline before embedding (consistency).
3. **Given** a degenerate bounding box (zero or negative area), **When** the pipeline runs, **Then** it raises a clear, recoverable error rather than producing a corrupt crop.
4. **Given** the domain layer, **When** its imports are inspected, **Then** it does not import the face-crop utility directly (the pipeline lives in the adapters layer, invoked by the adapter composition).

---

### User Story 4 - Model Download/Cache & Docker Volume (Priority: P2)

The concrete adapters obtain their model files (`face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx`) from a local cache directory (`models/`) at the repo root. A `ModelDownloader` utility fetches a model from its OpenCV model-repository URL on first use if the file is absent (lazy download), and serves it from the cache on subsequent uses. The `models/` directory is bind-mounted into the backend container via Docker Compose so the cache is shared between host and container and survives container restarts. Models may alternatively be pre-downloaded (e.g. baked into the image or fetched at build time) so an air-gapped or offline demo does not require network at runtime. The model cache path is configurable.

**Why this priority**: Without a reliable, reproducible way to obtain and cache the model files, the concrete adapters cannot load and the production app fails to start. It delivers Constitution Principle IV (Docker Compose is the canonical run path — the models volume must be part of that stack) and makes the demo reproducible across machines. It is independently testable by starting with an empty cache, triggering a download, and asserting the file appears and is reused. It is P2 because it is the enabling infrastructure for the P1 adapters.

**Independent Test**: Start with an empty `models/` cache and `APP_MODE=production`; trigger detector/embedder construction; assert each model file is downloaded once into `models/` and that a second construction reuses the cached file (no re-download). Bring up the compose stack and assert the `models/` volume is bind-mounted into the backend container and the path inside the container matches the host path. Delivers a verifiable, cached, volume-backed model supply.

**Acceptance Scenarios**:

1. **Given** the `models/` cache is empty and network is available, **When** a concrete adapter is first constructed, **Then** `ModelDownloader` fetches the required `.onnx` file from its OpenCV model-repository URL into `models/` and the adapter loads it.
2. **Given** the model file already exists in `models/`, **When** the adapter is constructed, **Then** the cached file is reused and no network fetch occurs.
3. **Given** the docker-compose production stack, **When** the backend container starts, **Then** the `models/` directory is bind-mounted into the container and the in-container model path matches the configured cache path (Constitution Principle IV).
4. **Given** an air-gapped environment with the model files pre-placed in `models/`, **When** the app starts, **Then** the adapters load from the cache without any network access (pre-download supported).
5. **Given** a model download fails (network error, corrupt file), **When** the adapter is constructed, **Then** it fails fast with a clear, actionable error indicating which model could not be obtained, before serving traffic.

---

### User Story 5 - Production Wiring Update (Detector + Embedder Only) (Priority: P2)

The production wiring function `wire_production_adapters()` (from spec 007) is updated so that when `APP_MODE=production`, it wires `YuNetDetector` and `SFaceEmbedder` instead of `MockDetector` and `MockEmbedder`. The mood and age estimators remain mock (real mood/age adapters are explicitly deferred to spec 009). The real SQLAlchemy persistence adapters from spec 007 are unchanged. The wiring continues to run exactly once at composition time via `select_wiring()` (Constitution Principle VII). When `APP_MODE=mock` (or unset), the wiring is identical to specs 001-007 (mock detectors/embedders) — backward compatible.

**Why this priority**: This is the composition change that actually substitutes the real adapters into the running production app. Without it, the concrete adapters exist but are never used. It delivers Constitution Principle VII ("concrete models are adapters selected at composition time") and PRD §18 Fase 5. It is independently testable by starting in production mode and inspecting that the wired detector/embedder are the concrete instances while mood/age remain mock. It is P2 because it is the wiring seam, not the adapter implementation itself.

**Independent Test**: (a) Start the app with `APP_MODE=production` and models present; assert `app.state.detector` is a `YuNetDetector` and `app.state.embedder` is an `SFaceEmbedder`, while `app.state.mood_estimator` and `app.state.age_estimator` are still the mock instances. (b) Start with `APP_MODE=mock`; assert the wired detector/embedder are the mock instances (backward compatible). Delivers a verifiable wiring substitution scoped to detector + embedder only.

**Acceptance Scenarios**:

1. **Given** `APP_MODE=production` and models available, **When** the app starts, **Then** `wire_production_adapters()` wires `YuNetDetector` as the detector and `SFaceEmbedder` as the embedder, and keeps `MockAgeEstimator` and `MockMoodEstimator` for age/mood (spec 009 adds real ones).
2. **Given** `APP_MODE=production`, **When** the app starts, **Then** the real SQLAlchemy persistence adapters (UserRepository, FaceTemplateRepository, SessionManager, UnitOfWork) from spec 007 are wired unchanged.
3. **Given** `APP_MODE=mock` (or unset), **When** the app starts, **Then** the wiring is identical to specs 001-007 (mock detector/embedder/age/mood + in-memory repos) — backward compatible.
4. **Given** the selector, **When** it dispatches, **Then** it runs exactly once at composition time and the chosen adapter set is fixed for the process lifetime (Constitution Principle VII).

---

### User Story 6 - Real-Model Integration Tests (Priority: P3)

An automated integration test suite exercises the concrete adapters with real model files. The tests verify: (a) the detector finds exactly one face in a single-face test image and zero faces in a face-less image; (b) the embedder produces a fixed-length vector; (c) cosine similarity of two embeddings of the same person exceeds the verification threshold; (d) cosine similarity of embeddings of two different people is below the threshold. The tests are skipped when the model files are absent (via a `pytest.mark.requires_models` marker / autouse fixture that checks the cache) or when `APP_MODE != production`, so CI without models still runs the rest of the suite green. The tests use consented test fixture images only (PRD §12).

**Why this priority**: Tests are the safety net that confirms the concrete adapters actually work against real models and that the same-person/different-person separation holds — the core correctness claim of the spec. It delivers Constitution Quality Gates §6/§7 (integration tests for real adapters; ML-adapter integration tests may be skipped in CI with a documented flag). It is independently testable by running the suite with models present (pass) and absent (skipped, suite still green). It is P3 because it validates the P1/P2 deliverables rather than delivering standalone user value.

**Independent Test**: Run the real-model integration suite with models present; assert all detector/embedder/similarity assertions pass. Remove the models from the cache and re-run; assert the real-model tests are skipped and the rest of the suite remains green. Delivers a green, reproducible real-model test layer that is gracefully skippable.

**Acceptance Scenarios**:

1. **Given** the model files are present and `APP_MODE=production`, **When** the real-model integration tests run, **Then** the detector finds exactly one face in the single-face fixture and zero in the face-less fixture.
2. **Given** the model files are present, **When** the embedder tests run, **Then** the embedder produces a fixed-length vector and same-person embeddings yield cosine similarity above the threshold while different-person embeddings yield similarity below the threshold.
3. **Given** the model files are absent, **When** the test suite runs, **Then** the real-model tests are skipped (via `requires_models` / `APP_MODE` guard) and the remainder of the suite passes green (Constitution Quality Gate §7).
4. **Given** the test fixtures, **When** they are inspected, **Then** they are consented test images only (PRD §12 — "usar únicamente imágenes de prueba con consentimiento").

---

### User Story 7 - Threshold Calibration Documentation (Priority: P3)

The spec produces documentation of the recommended cosine similarity verification threshold for SFace embeddings used with the YuNet detector, and explains how it differs from the mock threshold (0.5, used by specs 001-007 where the mock embedder returns an all-equal vector yielding similarity 1.0). The documentation covers: the recommended threshold value for real SFace embeddings, how it was derived/calibrated, and that the `verification_threshold` setting remains configurable (PRD §11 — "el umbral de verificación debe ser configurable y documentado"). The default `verification_threshold` in mock mode stays 0.5 (backward compatible); production mode uses the documented real-model threshold (configurable).

**Why this priority**: Calibration documentation is what makes the real verification threshold trustworthy and reproducible, and PRD §11 explicitly requires the threshold to be documented. It is independently testable/reviewable by reading the docs and confirming the recommended threshold, its derivation, and the configurability note are present. It is P3 because it is documentation supporting the P1 adapters, not runtime behavior.

**Independent Test**: Inspect the threshold calibration documentation; assert it states a recommended cosine threshold for SFace+YuNet, describes how it was calibrated, notes the difference from the mock 0.5 threshold, and confirms `verification_threshold` remains env-configurable. Delivers documented, configurable verification calibration.

**Acceptance Scenarios**:

1. **Given** the threshold calibration documentation, **When** it is reviewed, **Then** it states a recommended cosine similarity threshold for SFace embeddings with the YuNet detector.
2. **Given** the documentation, **When** it is reviewed, **Then** it explains how the recommended threshold was derived/calibrated and how it differs from the mock threshold (0.5).
3. **Given** the configuration, **When** `verification_threshold` is inspected, **Then** it remains configurable via the environment (PRD §11), with the mock-mode default unchanged at 0.5 (backward compatible) and the production-mode default set to the documented real-model threshold.

---

### User Story 8 - Mock Mode & Existing Tests Preserved Unchanged (Priority: P4)

Setting `APP_MODE=mock` (or leaving it unset) produces the exact same application behavior as specs 001-007: the mock detector, mock embedder, mock age/mood estimators, and in-memory repositories are wired, no model files or OpenCV/ONNX runtime are required, and the existing domain, contract, and unit tests — which assume mock wiring — continue to pass without any modification. The mock adapters themselves are retained verbatim (not altered, not reimplemented). The new runtime dependencies (opencv-python-headless, onnxruntime, numpy) are only imported by the concrete adapters, never by the domain or the mock wiring path. This guarantees that introducing the concrete ML adapters is non-destructive.

**Why this priority**: This is the safety guarantee that makes the real-adapter addition non-destructive. The feature description explicitly bounds the spec out of changing mock adapters or existing domain/contract/unit tests. It delivers Constitution Principle VII ("mocks are allowed and expected for dev and for domain-level tests") and Principle I (the mock-mode demo path is the primary path and must keep working). It is independently testable by running the existing suite unchanged and starting the app in mock mode without any model files.

**Independent Test**: (a) Run the existing domain, contract, and unit test suites with no changes and no model files present; assert they all pass. (b) Start the app with `APP_MODE` unset and no `models/` directory; assert it starts and behaves as in specs 001-007. (c) Inspect the mock adapter source; assert it is unchanged. (d) Inspect the domain layer; assert it has no opencv/onnxruntime/numpy import. Delivers a non-regressed mock mode and intact existing test suite.

**Acceptance Scenarios**:

1. **Given** `APP_MODE` is unset or `mock`, **When** the app starts, **Then** it requires no model files and no OpenCV/ONNX runtime, and wires the mock adapters (backward compatible with specs 001-007).
2. **Given** the existing domain, contract, and unit test suites (specs 001-007), **When** they are run unchanged with no models present, **Then** they all pass (no test is modified by this spec).
3. **Given** the mock adapters from spec 001, **When** their source is inspected, **Then** they are retained verbatim — not altered or reimplemented (scope boundary).
4. **Given** the domain layer, **When** its imports are inspected, **Then** it has no import of opencv, onnxruntime, numpy, or any concrete adapter module (Constitution Principle VII).

---

### Edge Cases

- What happens when `APP_MODE=mock`? The app wires mock adapters, requires no model files and no OpenCV/ONNX runtime, and behaves identically to specs 001-007 (backward compatible).
- What happens when `APP_MODE=production` but the model files are absent and network is unavailable? The concrete adapter construction fails fast with a clear, actionable error indicating which model could not be obtained, before serving traffic (FR-009).
- What happens when a model file is present but corrupt? The adapter fails fast at load time with a clear error (model-load failure), mapped to a recoverable `500 internal_error` at the HTTP boundary; it does not silently produce garbage detections/embeddings.
- What happens when the detector finds zero faces in onboarding/login? The existing domain behavior from specs 002/003 applies unchanged (onboarding rejects with "no face detected"; login rejects with `auth_failed`) — the real detector just feeds a real `DetectionResult(face_count=0)` through the same port.
- What happens when the detector finds multiple faces? The existing domain behavior applies (onboarding rejects multi-face per spec 002); the real detector returns `face_count > 1` through the same port.
- What happens when the embedder receives an unaligned/raw crop (alignment skipped)? The embedder still produces a vector, but verification accuracy degrades; the shared face-crop pipeline (User Story 3) is the supported path. This is a quality edge case, not a crash.
- What happens when the embedding dimension differs from the stored template's dimension? The existing `ComparisonError` path from spec 003 applies (cosine comparison raises on dimension mismatch → `500`). SFace's fixed dimension matches the documented embedding dimension, so this only occurs if a stored template from a different model version is compared — a model-version mismatch scenario documented in the calibration docs.
- What happens when the model download is interrupted mid-fetch? The download writes to a `.part` temp file and atomically renames on completion, so a partial file is never left as a valid cache entry; the next construction finds no valid cached file (only a `.part`, which is treated as absent) and re-downloads. A corrupt partial file is treated as absent/corrupt and re-fetched.
- What happens when `models/` is read-only (cannot write the cache)? The adapter fails fast with a clear error indicating the cache directory is not writable; pre-placing the model files (pre-download) is the supported workaround for read-only environments.
- What happens when the real-model integration tests run without Docker or without models? They are skipped via the `requires_models` / `APP_MODE` guard; the rest of the suite remains green (Constitution Quality Gate §7).
- What happens if a developer changes a mock adapter in this spec? That is out of scope (scope boundary); mock adapters are retained verbatim.
- What happens if a developer changes a domain port, entity, or result type in this spec? That is out of scope (scope boundary); the spec is additive — new concrete adapters implement existing ports. No port, entity, or result type is added or altered.
- What happens if a developer adds a new HTTP endpoint or frontend change in this spec? That is out of scope (scope boundary); the existing PRD §8 contracts are served identically; the frontend is unaware of the adapter substitution.
- What happens with the mood and age estimators in production mode? They remain mock (scope boundary — real mood/age adapters are spec 009). Only the detector and embedder are substituted in this spec.
- What happens when the same-person cosine similarity is near the threshold (borderline)? The accept/reject decision follows the existing `similarity >= verification_threshold` rule from spec 003; the calibration docs (User Story 7) document the recommended threshold and its trade-offs. No new borderline logic is introduced.
- What happens to logs? No image, embedding vector, or biometric response is logged; observability is limited to structured JSON logs (adapter loaded, model version, operation duration/status) consistent with specs 001-007 and Constitution Principle VIII (PRD §12/§13).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a concrete `Detector` adapter (`YuNetDetector`) that implements the existing `Detector` port (`detect(image: bytes) -> DetectionResult`) using the YuNet open-source face detection model via OpenCV's DNN module; it MUST return a `DetectionResult` with `face_count`, `boxes` (list of `BoundingBox`), and `score` (PRD §11 detector contract).
- **FR-002**: The system MUST provide a concrete `Embedder` adapter (`SFaceEmbedder`) that implements the existing `Embedder` port (`embed(face_image: bytes) -> Embedding`) using the SFace open-source face recognition model via OpenCV's DNN module (the single concrete inference backend — both YuNet and SFace load via `cv2.dnn.readNetFromONNX`); it MUST return an `Embedding` with a fixed-length `vector` of **128 dimensions** (SFace's L2-normalized output for `sface-2021dec-v1`) and an identifiable `model_version` (PRD §11). `onnxruntime` is a declared runtime dependency (FR-014) available as an OpenCV DNN backend but the adapters make no direct `onnxruntime` API calls.
- **FR-003**: Both concrete adapters MUST carry an identifiable, fixed `model_version` string so results are reproducible (PRD §11 — "los modelos deben tener una versión identificable"); the detector version (e.g. `yunet-2023mar-v1`) and embedder version (e.g. `sface-2021dec-v1`) MUST be distinct from the mock versions (`mock-yolo-v0`, `mock-embedder-v1`).
- **FR-004**: Both models MUST be open-source under OSI-approved licenses (YuNet: MIT via OpenCV model dir; SFace: Apache 2.0), satisfying Constitution Principle III (no proprietary or closed-weights models).
- **FR-005**: The detector MUST return `face_count == 1` with a valid `BoundingBox` and `score` above the quality threshold for an image containing exactly one face; `face_count == 0` with an empty `boxes` list for a face-less image; and `face_count == N` with N boxes for an image containing N faces (PRD §11).
- **FR-006**: The embedder MUST produce embeddings such that two embeddings of the same person's face yield cosine similarity above the configured verification threshold, and two embeddings of different people's faces yield cosine similarity below the threshold (PRD §6.3 — 1:1 verification).
- **FR-007**: The system MUST provide a shared face-crop and alignment pipeline (`face_crop`) that, given a source image, a detection bounding box, and facial landmarks, produces an aligned, cropped face image of a fixed size suitable for the embedder, using an affine transformation; onboarding and login MUST both route the detected face through this pipeline before embedding (consistency).
- **FR-008**: The system MUST provide a `ModelDownloader` utility and a `models/` cache directory (configurable path) at the repo root; on first adapter construction with the model absent, the utility MUST fetch the `.onnx` file from its OpenCV model-repository URL into the cache; on subsequent constructions, the cached file MUST be reused without a network fetch. Pre-placing model files in the cache (pre-download) MUST be supported for air-gapped/offline runs. The download writes to a `<model>.onnx.part` temp file and atomically renames to `<model>.onnx` on completion so a partial file is never cached; a lone `.part` file is treated as absent and re-fetched. The download is a single attempt with a configurable timeout (default 30s connect / 120s read); on failure it fails fast per FR-009 (no automatic retry).
- **FR-009**: If a model file cannot be obtained (network failure, corrupt file, unwritable cache), the concrete adapter MUST fail fast at construction/load time with a clear, actionable error indicating which model could not be obtained, before the app serves traffic. Integrity is verified by a load-test: after download (or cache hit), the adapter attempts to load the model via OpenCV DNN; a corrupt or truncated file fails the load and is reported as a corrupt-file error (no separate checksum/signature verification — the OpenCV model repository does not publish signed checksums, and Constitution Principle VIII waives security guarantees).
- **FR-010**: The docker-compose production stack MUST bind-mount the `models/` directory into the backend container so the cache is shared between host and container and survives container restarts, and the in-container model path MUST match the configured cache path (Constitution Principle IV).
- **FR-011**: The production wiring function `wire_production_adapters()` MUST wire `YuNetDetector` as the detector and `SFaceEmbedder` as the embedder when `APP_MODE=production`, while keeping `MockAgeEstimator` and `MockMoodEstimator` for age/mood (real mood/age are spec 009); the real SQLAlchemy persistence adapters from spec 007 MUST remain unchanged. The wiring MUST run exactly once at composition time via `select_wiring()` (Constitution Principle VII).
- **FR-012**: When `APP_MODE=mock` (or unset), the wiring MUST be identical to specs 001-007 (mock detector/embedder/age/mood + in-memory repos); the concrete adapters MUST NOT be constructed and no model files or OpenCV/ONNX runtime MUST be required (backward compatible).
- **FR-013**: The domain layer MUST NOT import OpenCV, ONNX Runtime, NumPy, YuNet, SFace, the `face_crop` utility, or any concrete adapter module; all ML touchpoints remain behind the existing `Detector` and `Embedder` ports (Constitution Principle VII, PRD §11 — "la capa de dominio no debe importar directamente la implementación de YOLO").
- **FR-014**: The system MUST add the runtime dependencies `opencv-python-headless`, `onnxruntime`, and `numpy`; these MUST only be imported by the concrete adapters and the face-crop pipeline, never by the domain layer or the mock wiring path. OpenCV's DNN module is the single concrete inference backend for both YuNet and SFace; `onnxruntime` is retained as a declared dependency (available as an OpenCV DNN backend) but the adapters make no direct `onnxruntime` API calls.
- **FR-015**: An automated real-model integration test suite MUST verify: (a) the detector finds exactly one face in a single-face fixture and zero in a face-less fixture; (b) the embedder produces a fixed-length vector; (c) same-person cosine similarity exceeds the threshold; (d) different-person cosine similarity is below the threshold. The tests MUST be skipped when the model files are absent (via `pytest.mark.requires_models` / autouse guard) or when `APP_MODE != production`, so CI without models remains green (Constitution Quality Gates §6/§7). Test fixtures MUST be consented images only (PRD §12).
- **FR-016**: The system MUST produce threshold calibration documentation stating the recommended cosine similarity threshold for SFace embeddings with the YuNet detector, how it was calibrated, and how it differs from the mock threshold (0.5); `verification_threshold` MUST remain configurable via the environment (PRD §11 — "el umbral de verificación debe ser configurable y documentado"). The mock-mode default MUST remain 0.5 (backward compatible).
- **FR-017**: No image, embedding vector, or biometric response MUST appear in application logs; observability is limited to structured JSON logs (adapter loaded, model version, operation duration/status) consistent with specs 001-007 and Constitution Principle VIII (PRD §12/§13). No audit log or immutable event store is required (Principle VIII).
- **FR-018**: The mock adapters, the mock wiring function, the domain ports, the domain entities, the domain result types (`DetectionResult`, `BoundingBox`, `Embedding`), the HTTP contracts (PRD §8), and the frontend MUST be unchanged by this spec; no new endpoint, entity, port, result type, or frontend change is introduced (scope boundary, Constitution Principle VII). The spec is additive: new concrete adapters implement existing ports.
- **FR-019**: The existing domain, contract, and unit test suites (specs 001-007) MUST continue to pass without modification in mock mode (non-regression; scope boundary — existing tests are not changed).
- **FR-020**: Concrete mood estimator, concrete age estimator, model training, liveness/anti-spoofing, 1:N face search, new HTTP endpoints, frontend changes, changes to domain ports/entities/result types, changes to mock adapters, and changes to existing domain/contract/unit tests are explicitly out of scope for this spec (scope boundary; real mood/age is deferred to spec 009).

### Key Entities *(include if feature involves data)*

- **DetectionResult (from spec 001, unchanged)**: The detector output value object (`face_count: int`, `boxes: list[BoundingBox]`, `score: float`). `YuNetDetector` populates it from YuNet's output. No new attributes (scope boundary).
- **BoundingBox (from spec 001, unchanged)**: `x, y, width, height` enclosing a detected face. Populated by `YuNetDetector` from YuNet's bounding box. No new attributes.
- **Embedding (from spec 001, unchanged)**: The embedder output value object (`vector: list[float]`, `model_version: str`). `SFaceEmbedder` populates it with the SFace vector (128 dimensions, L2-normalized, for `sface-2021dec-v1`) and a real `model_version`. The 128-dim length matches the mock embedder's 128-dim vector (spec 001), so no schema/result-type change is introduced. No new attributes.
- **YuNetDetector (new adapter, not a domain entity)**: Concrete `Detector` port implementation. Lives in the adapters layer (`adapters/ml/yunet_detector.py`); not a domain entity; selected at composition time when `APP_MODE=production`.
- **SFaceEmbedder (new adapter, not a domain entity)**: Concrete `Embedder` port implementation. Lives in the adapters layer (`adapters/ml/sface_embedder.py`); not a domain entity; selected at composition time when `APP_MODE=production`.
- **ModelDownloader + models/ cache (new infrastructure, not a domain entity)**: Utility + cache directory for obtaining/caching `.onnx` model files. Infrastructure, not a domain entity; the cache path is configurable and bind-mounted into the backend container.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `APP_MODE=production` and models present, the wired detector is `YuNetDetector` and the wired embedder is `SFaceEmbedder`, verifiable by starting the app and inspecting `app.state.detector` / `app.state.embedder` instance types (FR-011).
- **SC-002**: The real detector finds exactly one face in a single-face test image and zero faces in a face-less image, verifiable by running the detector on consented fixtures and asserting `face_count` and `boxes` (FR-005, FR-015).
- **SC-003**: The real embedder produces a fixed-length vector, and same-person embeddings yield cosine similarity above the threshold while different-person embeddings yield similarity below the threshold, verifiable by embedding consented fixture pairs and computing cosine similarity (FR-006, FR-015).
- **SC-004**: The domain layer has no import of opencv, onnxruntime, numpy, or any concrete adapter/face-crop module, verifiable by inspecting the domain layer imports (FR-013, Constitution Principle VII).
- **SC-005**: Both models are open-source under OSI-approved licenses (YuNet MIT, SFace Apache 2.0), verifiable by inspecting the model provenance/license documentation (FR-004, Constitution Principle III).
- **SC-006**: Both adapters expose identifiable, fixed `model_version` strings distinct from the mock versions, verifiable by inspecting the returned `Embedding.model_version` and the detector's version (FR-003).
- **SC-007**: The shared face-crop pipeline produces a fixed-size aligned crop from a source image + box + landmarks, and both onboarding and login route through it, verifiable by feeding a known input and inspecting the output dimensions and the route composition (FR-007).
- **SC-008**: With an empty `models/` cache and network available, the first adapter construction downloads each model once and subsequent constructions reuse the cache (no re-download), verifiable by clearing the cache, triggering construction, and asserting the file appears and is reused (FR-008).
- **SC-009**: The docker-compose production stack bind-mounts `models/` into the backend container with a matching in-container path, verifiable by bringing up the stack and inspecting the backend container's mounts (FR-010, Constitution Principle IV).
- **SC-010**: A model that cannot be obtained (network failure / corrupt file / unwritable cache) causes a fail-fast startup error naming the missing model, verifiable by starting with an unreachable URL / corrupt file and asserting the process exits before serving traffic (FR-009).
- **SC-011**: With `APP_MODE=mock` (or unset), the app wires mock adapters, requires no models and no OpenCV/ONNX runtime, and behaves identically to specs 001-007, verifiable by starting unset with no `models/` dir and exercising the existing flows (FR-012).
- **SC-012**: The real-model integration tests pass when models are present and are skipped (suite stays green) when models are absent or `APP_MODE != production`, verifiable by running the suite in both conditions (FR-015, Constitution Quality Gate §7).
- **SC-013**: The threshold calibration documentation states the recommended SFace+YuNet cosine threshold, its derivation, the difference from the mock 0.5, and confirms `verification_threshold` remains configurable, verifiable by reviewing the docs (FR-016).
- **SC-014**: The mock adapters, domain ports/entities/result types, HTTP contracts, and frontend are unchanged, verifiable by diffing the spec's changes against the specs 001-007 baseline (FR-018).
- **SC-015**: The existing domain, contract, and unit test suites pass unchanged in mock mode with no models present, verifiable by running them with no modifications (FR-019).
- **SC-016**: No image, embedding vector, or biometric response appears in logs; only structured JSON logs (adapter loaded, model version, operation duration/status) are produced, verifiable by inspecting startup and runtime logs (FR-017).
- **SC-017**: No concrete mood/age adapter, model training, liveness/anti-spoofing, 1:N search, new endpoint, frontend change, domain port/entity/result-type change, mock adapter change, or existing-test change is introduced, verifiable by confirming the spec's scope excludes these (FR-020).

## Assumptions

- This spec builds directly on specs 001-007: the hexagonal `Detector` and `Embedder` ports (`domain/ports.py`), the domain result types (`DetectionResult`, `BoundingBox`, `Embedding` in `domain/result_types.py`), the mock adapters (`MockDetector`, `MockEmbedder` and their constants — 128-dim 0.1 vector, `mock-embedder-v1`, `mock-yolo-v0`), the `wire_mock_adapters` and `wire_production_adapters` composition functions, the `select_wiring(app_mode)` selector, the `APP_MODE` setting (default `mock`), the `verification_threshold` (default 0.5) and model-version settings in `config.py`, the real SQLAlchemy persistence adapters, the FastAPI app factory, and the `docker-compose.yml` stack are all assumed to exist and be reused, not re-created.
- The technology stack is fixed by the Constitution (Principle III / Technology Stack table): backend in Python with FastAPI, PostgreSQL for persistence, Docker Compose for orchestration. The new runtime dependencies (`opencv-python-headless`, `onnxruntime`, `numpy`) are additive Python packages consistent with the Python backend decision; they are not a stack change.
- **Detector choice — YuNet**: YuNet is selected as the concrete open-source face detector, permitted by PRD §11's "Modelo basado en YOLO **o un adaptador equivalente**" clause. YuNet is a YOLO-equivalent open-source face detector distributed via OpenCV's model repository (MIT license). It is wired behind the existing `Detector` port (Constitution Principle VII — "la generación de embeddings debe estar detrás de una interfaz o puerto reemplazable" applies to the detector too), so it remains swappable. This resolves the detector adapter concretely for Fase 5a without violating the constitution's "YOLO (open-source)" technology-stack entry, since the port is replaceable and PRD §11 explicitly permits an equivalent adapter.
- **Embedder choice — SFace (resolves OQ-4)**: SFace is selected as the concrete open-source face embedding model (Apache 2.0 / open-weights), distributed via OpenCV's model repository. This resolves Constitution Open Question OQ-4 (embedding model) to SFace. SFace produces a fixed-length 128-dimensional L2-normalized embedding vector for `sface-2021dec-v1`; the dimension is documented in the calibration docs and asserted by the integration tests. The 128-dim length matches the mock embedder's 128-dim vector (spec 001), so no schema or result-type change is introduced. SFace is wired behind the existing `Embedder` port, so it remains swappable (Constitution Principle VII).
- **Inference backend — OpenCV DNN (single backend)**: Both YuNet and SFace are loaded via OpenCV's DNN module (`cv2.dnn.readNetFromONNX`) — the single concrete inference backend. `onnxruntime` is retained as a declared runtime dependency (available as an OpenCV DNN backend) but the adapters make no direct `onnxruntime` API calls. One backend keeps the adapter code simple and the dependency surface coherent.
- **Model acquisition — lazy download on first use (default)**: Models are downloaded on first adapter construction if absent from the `models/` cache (lazy), with a documented pre-download alternative for air-gapped/offline demos. Lazy-on-first-use is chosen as the default because it keeps `docker compose up` the canonical one-command path (Constitution Principle IV) without requiring a separate fetch step, while pre-download remains supported for reproducibility and offline operation. The cache path is configurable via settings. Downloads write to a `.part` temp file and atomically rename on completion (no partial file is ever cached); a download is a single attempt with a configurable timeout (default 30s connect / 120s read) and no automatic retry — on failure the adapter fails fast per FR-009. Integrity is verified by a load-test (OpenCV DNN load) rather than a checksum, consistent with Constitution Principle VIII.
- **Threshold — recommended default for SFace+YuNet**: The recommended cosine similarity threshold for SFace embeddings with the YuNet detector is documented in the calibration docs (User Story 7). The mock-mode default `verification_threshold` remains 0.5 (backward compatible — the mock embedder returns an all-equal vector yielding similarity 1.0). The production-mode default is set to the documented real-model threshold and remains env-configurable (PRD §11). The exact recommended value is confirmed by calibration and recorded in the docs; the setting is not hard-coded in the domain.
- The wiring selector runs exactly once at startup (composition time), per Constitution Principle VII and spec 007. This spec only changes *which* detector/embedder instances `wire_production_adapters()` constructs; it does not change the selector, the composition-time semantics, or the mock wiring path.
- The mood and age estimators remain mock in production mode (scope boundary — real mood/age adapters are explicitly deferred to spec 009). Only the detector and embedder are substituted in this spec. This yields a working production app with real persistence (spec 007) + real detection + real embedding but deterministic mock mood/age — the cleanest Fase 5a slice.
- The mock adapters, mock wiring function, domain ports, domain entities, domain result types, HTTP contracts (PRD §8), and frontend are retained unchanged (scope boundary). The spec is additive: two new concrete adapter modules + one face-crop utility + one model-downloader utility implement existing ports; no port, entity, or result type is added or altered. The existing domain/contract/unit tests keep using mocks and are not modified.
- The new runtime dependencies (`opencv-python-headless`, `onnxruntime`, `numpy`) are only imported by the concrete adapters and the face-crop pipeline, never by the domain layer or the mock wiring path. `opencv-python-headless` (not `opencv-python`) is chosen to avoid GUI/display dependencies in the container. This keeps mock mode and the domain test suite free of the heavy ML runtime.
- The real-model integration tests use consented test fixture images only (PRD §12 — "usar únicamente imágenes de prueba con consentimiento") and are skipped via `pytest.mark.requires_models` / an `APP_MODE` guard when models are absent or the mode is not production, so CI without models remains green (Constitution Quality Gate §7).
- Observability in this spec is limited to structured JSON logs (adapter loaded, model version, operation duration/status) with no images, embedding vectors, or biometric responses logged, consistent with specs 001-007 and Constitution Principle VIII (no traceability guarantee). No audit log or immutable event store is required.
- The `models/` cache directory and its Docker Compose bind mount are the operational additions in this spec; the compose file remains the single source of truth for service topology (Constitution Principle IV). The existing `usuarios/` bind mount and other compose configuration are reused unchanged.
- Concrete mood/age adapters (spec 009), model training, liveness/anti-spoofing, 1:N face search, new HTTP endpoints, frontend changes, changes to domain ports/entities/result types, changes to mock adapters, and changes to existing domain/contract/unit tests are explicitly out of scope for this spec.
