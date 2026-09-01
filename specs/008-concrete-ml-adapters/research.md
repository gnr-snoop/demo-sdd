# Research: Concrete Face Detection & Embedding ML Adapters (Fase 5a — Detector + Embedder)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Codebase Context

*Gathered from the codebase-memory knowledge graph (project `demo-sdd`, generation 2026-09-01, moderate index). `detect_changes` showed 37 changed files (mostly spec 005/007 work + this spec's new files) — graph is current. Coverage checked on all 9 evidence paths below: all `no_recorded_issue` (metadata-changed freshness noted; source read directly as ground truth).*

### Existing architecture (integration surface)

- **Domain ports** — `backend/src/face_insight/domain/ports.py:18-25` defines `Detector.detect(image: bytes) -> DetectionResult` and `Embedder.embed(face_image: bytes) -> Embedding` as `typing.Protocol` interfaces. **Unchanged by this spec** (FR-018) — the concrete adapters implement these exact signatures.
- **Domain result types** — `domain/result_types.py`: `BoundingBox(x,y,width,height)`, `DetectionResult(face_count, boxes, score)`, `Embedding(vector: list[float], model_version: str)`. **Unchanged** — SFace's 128-dim vector populates the existing `Embedding.vector`; `model_version` carries `sface-2021dec-v1`.
- **Mock adapters** — `adapters/mock/detector.py` (`MockDetector` → `DetectionResult(face_count=1, boxes=[BoundingBox(0,0,100,100)], score=0.99)`, version `mock-yolo-v0`) and `adapters/mock/embedder.py` (`MockEmbedder` → 128-dim `[0.1]*128` vector, version `mock-embedder-v1`). Constants in `adapters/mock/constants.py`: `EMBEDDING_DIM=128`, `EMBEDDING_FILL=0.1`. **Retained verbatim** (FR-018/FR-019) — the spec is explicitly forbidden from altering them.
- **Production wiring** — `main.py:72-213` `wire_production_adapters(app)` currently wires real SQLAlchemy persistence + `MockDetector()`/`MockEmbedder()`/`MockAgeEstimator()`/`MockMoodEstimator()` (lines 150-154). This spec edits **only** the two ML lines (detector + embedder) to construct `YuNetDetector`/`SFaceEmbedder`; mood/age stay mock (spec 009). The selector `select_wiring(app, app_mode)` (`main.py:216-232`) and `create_app()` (`main.py:341-401`) are unchanged.
- **Domain services** — `OnboardingService.onboard()` (`domain/onboarding.py:138-150`) calls `self._detector.detect(image_bytes)` then `self._embedder.embed(image_bytes)` — **both with the same raw image bytes**; the detection box is used only for count/quality, never passed to the embedder. `LoginService.login()` (`domain/login.py:106-125`) is identical in this respect. This is the key constraint driving research R-5 (alignment-without-domain-change).
- **Config** — `config.py` `Settings` has `app_mode` (default `mock`), `verification_threshold` (default `0.5`), `quality_threshold` (default `0.5`), `embedding_model_version`/`detector_model_version` (mock defaults). No `models_dir` or download-timeout settings yet.
- **docker-compose.yml** — backend service already sets `APP_MODE=production`, `DATABASE_URL`, bind-mounts `./usuarios:/app/usuarios:rw`. Missing: `./models` bind mount + production `VERIFICATION_THRESHOLD`.
- **pyproject.toml** — dependencies list lacks `opencv-python-headless`, `onnxruntime`, `numpy`. `pytest.ini_options` has no `requires_models` marker registration.
- **Domain purity test** — `tests/domain/test_domain_purity.py` asserts the domain imports no adapters/SQLAlchemy/FastAPI/Pillow. This spec extends the forbidden-import set to include `cv2`, `onnxruntime`, `numpy`, and `adapters.ml`.
- **Existing integration-test skip pattern** — `tests/integration/*` use a `require_db` fixture that skips when PostgreSQL is unavailable. The new `requires_models` marker mirrors this pattern.

### Reuse opportunities

- `wire_production_adapters()` structure — the spec edits two lines inside an existing function; the service-rebuild block (lines 171-213) is reused unchanged because the services already accept `Detector`/`Embedder` ports.
- `select_wiring()` / `create_app()` — unchanged; the selector already dispatches on `APP_MODE`.
- `Settings` (pydantic-settings) — extend with new fields rather than a new config class.
- `tests/domain/test_domain_purity.py` — extend the forbidden-import assertion list rather than a new test.
- `tests/integration` `require_db` skip pattern — mirror for `requires_models`.
- Mock `EMBEDDING_DIM=128` — SFace's 128-dim output matches, so no schema/result-type change (the spec's central compatibility guarantee).

### Integration touch-points

- `backend/src/face_insight/adapters/ml/` — **new** subpackage (`yunet_detector.py`, `sface_embedder.py`, `face_crop.py`, `model_downloader.py`, `constants.py`, `__init__.py`).
- `backend/src/face_insight/main.py` — `wire_production_adapters()`: replace `MockDetector()`/`MockEmbedder()` construction with `YuNetDetector(...)`/`SFaceEmbedder(...)` (guarded by `APP_MODE=production`, which is already the function's precondition).
- `backend/src/face_insight/config.py` — add `models_dir: str`, `model_download_connect_timeout: float = 30.0`, `model_download_read_timeout: float = 120.0`, and a production-mode default for `verification_threshold` (see R-7).
- `backend/pyproject.toml` — add 3 runtime deps + register `requires_models` marker.
- `docker-compose.yml` — add `./models:/app/models:rw` volume to backend; set `VERIFICATION_THRESHOLD: "0.363"` for production.
- `backend/tests/domain/test_domain_purity.py` — extend forbidden imports.
- `backend/tests/unit/test_wiring_selector.py` — add production-mode instance-type assertions.
- New tests: `tests/unit/test_model_downloader.py`, `tests/unit/test_face_crop.py`, `tests/integration/test_real_ml_adapters.py`.
- New docs: `specs/008-concrete-ml-adapters/contracts/` + calibration section in `quickstart.md` (or a dedicated `docs/threshold-calibration.md` — see R-7).

### Coverage limitations

None material. All 9 evidence paths returned `no_recorded_issue`; metadata-changed freshness on several files (they were modified by spec 005/007 after the last index) was resolved by reading source directly as ground truth. The graph's `frontend/src/__tests__` is skip-listed (irrelevant — frontend unchanged this spec).

---

## Research Items

### R-1: OpenCV inference API for YuNet and SFace (mechanism vs. wrapper)

**Decision**: Use OpenCV's DNN-backed face module wrappers — `cv2.FaceDetectorYN_create(model_path, "", input_size, score_threshold, nms_threshold, top_k)` for YuNet and `cv2.FaceRecognizerSF_create(model_path, "")` for SFace — rather than calling `cv2.dnn.readNetFromONNX` directly with hand-rolled pre/post-processing.

**Rationale**: The spec pins "OpenCV's DNN module (`cv2.dnn.readNetFromONNX`)" as the *mechanism*. `FaceDetectorYN_create` and `FaceRecognizerSF_create` are OpenCV's supported API surface over that exact mechanism — they internally load the `.onnx` via the DNN module and encapsulate the model-specific pre/post-processing (input resize, NMS, landmark decoding, affine alignment, L2 normalization). Reimplementing that with raw `readNetFromONNX` would be reimplementing the wrapper, violating Principle I (demo simplicity) with no benefit. The wrappers are part of `opencv-python-headless`'s `cv2` namespace (no extra package). `onnxruntime` is declared as a dependency and selectable as a DNN backend via `backend_id`, but the adapters make no direct `onnxruntime` API calls (FR-014) — the default OpenCV CPU backend is used.

**Alternatives considered**:
- *Raw `cv2.dnn.readNetFromONNX` + manual preprocessing*: rejected — reimplements the wrapper, ~3× the code, error-prone, no demo value.
- *Direct `onnxruntime` sessions*: rejected — contradicts the pinned "single OpenCV DNN backend" decision and FR-014's "no direct onnxruntime API calls."

### R-2: YuNet detection output format → DetectionResult mapping

**Decision**: `cv2.FaceDetectorYN.detect(image)` returns a tuple `(retval, faces)` where `faces` is a `CV_32F` Mat with one row per detected face and 15 columns: `x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, conf`. `YuNetDetector.detect(image_bytes)` decodes the bytes via `cv2.imdecode`, sets the detector input size to the image size, runs `detect`, and maps each row to `BoundingBox(x=int(row[0]), y=int(row[1]), width=int(row[2]), height=int(row[3]))`, collecting `score = max(row[14] for all rows)` (the highest confidence). It returns `DetectionResult(face_count=faces.rows, boxes=[...], score=score)` (empty boxes + score 0.0 for zero faces). The detector is constructed with `score_threshold=settings.quality_threshold` so YuNet's own confidence filter aligns with the domain quality gate.

**Rationale**: This satisfies FR-005 (face_count 1/0/N with boxes + score) and PRD §11's detector contract (bounding box, score, count). Using the max confidence as the aggregate `score` preserves the existing `score < quality_threshold` check in `OnboardingService`/`LoginService` without domain changes. Landmarks (columns 4-13) are not carried in `DetectionResult` (the port has no landmark field — FR-018) but are used internally by `SFaceEmbedder` for alignment (R-5).

**Alternatives considered**:
- *Mean confidence as `score`*: rejected — max is more intuitive for the single-face happy path and matches "the face's confidence."
- *Adding a `landmarks` field to `DetectionResult`*: rejected — violates FR-018 (no result-type change).

### R-3: SFace embedding output → Embedding mapping (128-dim, L2-normalized)

**Decision**: `cv2.FaceRecognizerSF.feature(aligned_img)` returns a `CV_32F` row vector of **128** elements, already L2-normalized by SFace. `SFaceEmbedder.embed(face_image: bytes)` produces the aligned crop (R-5), calls `feature`, converts the Mat to a `list[float]` of length 128, and returns `Embedding(vector=that_list, model_version="sface-2021dec-v1")`. The 128 length is asserted in the real-model integration tests (FR-015) and matches `adapters/mock/constants.EMBEDDING_DIM` (128), so `FaceTemplate.embedding` and the `Comparison` port are unchanged.

**Rationale**: SFace `2021dec` is documented to emit a 128-dim L2-normalized vector; OpenCV's `match(..., FR_COSINE)` is equivalent to dot-product on these vectors. The mock's 128-dim `[0.1]*128` vector has the same dimensionality, so storing/ comparing SFace vectors requires no schema migration and no `ComparisonError`-on-dimension change. `model_version="sface-2021dec-v1"` is distinct from `mock-embedder-v1` (FR-003).

**Alternatives considered**:
- *Using `recognizer.match()` instead of the domain `CosineComparison`*: rejected — the domain owns the comparison (Principle VII); the adapter's job ends at producing the `Embedding`. The domain's `CosineComparison.compare` already computes cosine similarity on `list[float]`.

### R-4: Model acquisition — lazy download, atomic rename, single attempt, load-test integrity

**Decision**: `ModelDownloader` is constructed with a model name, URL, and cache dir (`settings.models_dir`, default `<repo_root>/models`). `ensure(model_name, url) -> Path`:
1. If `<cache>/<model>.onnx` exists → return its path (cache hit).
2. Else, fetch from `url` writing to `<cache>/<model>.onnx.part` using `httpx` (already a dependency) with `timeout=httpx.Timeout(connect=settings.model_download_connect_timeout, read=settings.model_download_read_timeout, write=120.0, pool=30.0)` — **single attempt, no retry**.
3. On completion, atomically `os.replace(part_path, final_path)` (atomic on POSIX; best-effort on Windows but the demo runs in a Linux container).
4. A lone `.part` file (interrupted download) is treated as absent → re-download.
5. On any `httpx` error / timeout → raise `ModelUnavailableError(model_name, url)` (fail fast, FR-009).
6. Integrity = load-test: the adapter constructor calls `cv2.FaceDetectorYN_create(path, ...)` / `cv2.FaceRecognizerSF_create(path, "")` and lets OpenCV raise on a corrupt/truncated file; that exception is wrapped into `ModelCorruptError(model_name)`. **No checksum/signature** (R-8).

Model URLs (OpenCV model zoo, raw GitHub):
- YuNet: `https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx`
- SFace: `https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx`

**Rationale**: Lazy-on-first-use keeps `docker compose up` the one-command path (Principle IV) without a separate fetch step, while pre-placing files in `models/` remains the supported air-gapped fallback (FR-008 AC-4). Atomic `.part` rename guarantees no partial file is ever cached (closes the interrupted-mid-fetch edge case). Single attempt + no retry: retry can mask upstream issues; the user re-runs `docker compose up`. `httpx` is already in the dependency tree (used by tests), so no new HTTP dep. Load-test integrity is sufficient because the OpenCV zoo publishes no signed checksums and Principle VIII waives security guarantees (R-8).

**Alternatives considered**:
- *Eager download at build time (bake into image)*: rejected as the *default* — complicates the image and breaks the "models survive container restarts via bind mount" intent; kept as a documented pre-download alternative.
- *`urllib` instead of `httpx`*: rejected — `httpx` is already a dependency and has a cleaner timeout API.
- *sha256 checksum verification*: rejected — see R-8.

### R-5: Face-crop + alignment without changing the domain (the central design decision)

**Decision**: The `face_crop` utility is a thin adapter-layer function wrapping OpenCV's `cv2.FaceRecognizerSF.alignCrop(src_img, face_box, aligned_img)`, which performs the affine transformation using the 5 landmarks embedded in the YuNet face-box row. Because the `Embedder.embed(face_image: bytes) -> Embedding` port signature is fixed (FR-018) and the domain services pass **raw image bytes** to `embed()` (not the detection box), `SFaceEmbedder` performs alignment **internally**: on `embed(image_bytes)` it (a) decodes the bytes, (b) runs an internal `YuNet` detection to obtain the face-box+landmarks, (c) calls `face_crop` (→ `alignCrop`) to produce the fixed-size aligned crop, (d) calls `feature` to get the 128-dim vector. `YuNetDetector` and `SFaceEmbedder` share the same cached YuNet model file (one download). Both onboarding and login routes use the same `SFaceEmbedder` instance → the same `face_crop` → consistent alignment (FR-007 AC-2).

`face_crop` is independently unit-testable: `test_face_crop.py` feeds a synthetic image + a degenerate (zero-area) box and asserts a clear `InvalidFaceBox` error, without needing model files.

**Rationale**: This is the only design that simultaneously satisfies (1) FR-018 (no port/result-type/domain change), (2) FR-007 (shared alignment pipeline, both routes), and (3) the OpenCV API reality that `alignCrop` needs the detector's face-box. The cost is double face-detection per embed (once in `YuNetDetector.detect` for count/quality, once in `SFaceEmbedder.embed` for alignment). For a ≤640px JPEG on CPU, YuNet inference is ~tens of milliseconds — well within demo tolerance, and the Constitution's Explicit Non-Goals state "no real-time performance SLOs." The trade-off is recorded in the plan's Complexity Tracking table.

**Alternatives considered**:
- *Change `Embedder.embed` to accept the detection box*: rejected — violates FR-018 (port signature change) and would ripple into the domain services + mock embedder + all existing tests.
- *Cache the detector's last result for the embedder*: rejected — couples two independent ports via hidden state, breaking hexagonal isolation.
- *Skip alignment (feed raw crop to SFace)*: rejected — the spec explicitly mandates the alignment pipeline (FR-007) and alignment materially improves same-person/different-person separation (the spec's core correctness claim, FR-006).
- *A composite `AlignedEmbedder` wrapper assembled in `wire_production_adapters`*: equivalent to the chosen design but splits alignment across two adapter classes; rejected for simplicity (one `SFaceEmbedder` class is clearer for the demo).

### R-6: `pytest.mark.requires_models` skip mechanism

**Decision**: Register a `requires_models` marker in `pyproject.toml` `[tool.pytest.ini_options] markers`. Add an autouse fixture in `tests/integration/conftest.py` (or the real-ML test module) that checks whether both `models/face_detection_yunet_2023mar.onnx` and `models/face_recognition_sface_2021dec.onnx` exist **and** `settings.app_mode == "production"`; if not, it calls `pytest.skip("real models absent or APP_MODE != production")` for any test marked `requires_models`. The rest of the suite is unaffected and stays green (Constitution Quality Gate §7).

**Rationale**: Mirrors the existing `require_db` skip pattern, keeping the convention uniform. Checking `APP_MODE` in addition to file presence prevents the real-model tests from running against mock wiring (where they would meaninglessly exercise mocks). No model files are committed to the repo (gitignored `models/`), so CI without models skips cleanly.

**Alternatives considered**:
- *`pytest --ignore`*: rejected — coarse; the marker is per-test and self-documenting.
- *Always downloading models in CI*: rejected — violates "no GPU/network required to develop/test" (Quality Gate §7) and slows CI.

### R-7: Threshold calibration — recommended SFace+YuNet cosine threshold

**Decision**: The recommended cosine similarity verification threshold for SFace embeddings with the YuNet detector is **0.363**, sourced from OpenCV's official documentation and sample code (LFW benchmark: 99.60% accuracy at cosine threshold 0.363 / normL2 threshold 1.128). The production-mode default `verification_threshold` is set to `0.363`; the mock-mode default remains `0.5` (backward compatible — the mock embedder returns an all-equal vector yielding similarity 1.0 ≫ 0.5). The threshold remains env-configurable via `VERIFICATION_THRESHOLD` (PRD §11). Implementation: `config.py` keeps `verification_threshold: float = 0.5` as the field default; `wire_production_adapters` overrides it to `0.363` when `APP_MODE=production` **unless** `VERIFICATION_THRESHOLD` is explicitly set in the environment (detected via `os.environ`). The calibration is documented in `quickstart.md` (Threshold Calibration section) and `contracts/adapter-port-conformance.md`.

**Rationale**: 0.363 is OpenCV's published, benchmark-backed value — not a hand-tuned guess — which makes the demo's verification decision reproducible and auditable (PRD §11: "el umbral de verificación debe ser configurable y documentado"). The mock default 0.5 is preserved so specs 001-007 tests (which assume `similarity 1.0 >= 0.5`) pass unchanged (FR-019). The production override is a settings-layer concern, not a domain hard-code (the domain reads `verification_threshold` from the wired `LoginService`).

**Alternatives considered**:
- *A single 0.5 threshold for both modes*: rejected — 0.5 is far above SFace's same-person distribution (real same-person cosine ≈ 0.4-0.8); 0.5 would reject most genuine logins. The threshold must be model-specific.
- *Hard-coding 0.363 in the domain*: rejected — the domain must stay model-agnostic (Principle VII); the threshold is a wiring/config concern.
- *A per-`FaceTemplate` threshold column*: out of scope (schema change, FR-018); the existing `FaceTemplate` has no threshold field and the spec forbids adding one.

**Calibration source**: OpenCV `face_detect` sample + tutorial (https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html) — "two faces have same identity if the cosine distance is greater than or equal to 0.363." Database: LFW 99.60%, CALFW 93.95% (0.340), AgeDB-30 94.90% (0.277), CFP-FP 94.80% (0.212). 0.363 (LFW) is the standard default.

### R-8: No checksum/signature — Principle VIII justification (strict-mode note)

**Decision**: Model integrity is verified by load-test only (OpenCV DNN load at construction fails fast on corrupt/truncated files → `ModelCorruptError`). No sha256/checksum/signature verification is performed.

**Rationale**: The OpenCV model repository does not publish signed checksums in a standard, machine-verifiable format. Adding a bespoke checksum scheme (hard-coding expected hashes in the adapter) would be production-grade supply-chain hardening that (a) contradicts Constitution Principle I (demo simplicity — does this make the SDD flow clearer? No), (b) is explicitly waived by Constitution Principle VIII ("no security guarantee"), and (c) would need manual hash updates on every model bump. The load-test already covers the *execution-integrity* concern (a corrupt file cannot produce garbage detections because it fails to load). This is a **security-adjacent** decision; in strict mode it is **not blocking** because the Constitution itself (Principle VIII, ratified) explicitly waives security guarantees and the spec (FR-009) pins the load-test approach with the Principle-VIII justification. Recorded in the plan's Complexity Tracking table.

**Alternatives considered**:
- *sha256 verified against a hard-coded constant*: rejected (above).
- *Checking a `.sha256` sidecar file from the repo*: rejected — the upstream doesn't publish one; would require us to generate+commit hashes, adding maintenance burden with no demo value.

### R-9: `opencv-python-headless` vs. `opencv-python`

**Decision**: Depend on `opencv-python-headless` (not `opencv-python`).

**Rationale**: The headless variant excludes GUI/display modules (HighGUI, Qt) that are unavailable/unnecessary in a Docker container and would pull in system GUI libs. The DNN + face modules (`FaceDetectorYN`, `FaceRecognizerSF`) are included in the headless build. This keeps the image small and the container dependency-free (Principle IV). The mock wiring path and domain never import `cv2` (FR-013/FR-014), so mock mode and the domain test suite remain free of the heavy ML runtime.

### R-10: New deps only imported by concrete adapters (FR-014 enforcement)

**Decision**: `cv2`, `onnxruntime`, and `numpy` are imported **only** inside `adapters/ml/*.py` (and `tests/integration/test_real_ml_adapters.py`). The domain purity test (`tests/domain/test_domain_purity.py`) is extended to assert that no module under `domain/` imports `cv2`, `onnxruntime`, `numpy`, or anything under `adapters.ml`. The mock wiring path (`wire_mock_adapters`) imports none of them (it imports only `adapters.mock`), so `APP_MODE=mock` requires no ML runtime (FR-012).

**Rationale**: Direct enforcement via the existing purity test is stronger than a code-review convention and prevents regressions. This is the concrete expression of Constitution Principle VII for this spec.
