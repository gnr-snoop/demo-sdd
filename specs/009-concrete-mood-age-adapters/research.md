# Research: Concrete Mood & Age Estimation ML Adapters (Fase 5b — Mood + Age)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Codebase Context

*Gathered from the codebase-memory knowledge graph (project `demo-sdd`, generation 2026-09-01, moderate index). `detect_changes` showed 48 changed files (spec 005/007/008 work + this spec's new files) — graph is current for the integration surface. Coverage checked on 14 evidence paths: all `no_recorded_issue` (the `tests/integration/` subtree is excluded by design — `test_real_ml_adapters.py` read directly as ground truth).*

### Existing architecture (integration surface)

- **Domain ports** — `backend/src/face_insight/domain/ports.py:28-35` defines `AgeEstimator.estimate_age(face_image: bytes) -> AgeResult` and `MoodEstimator.estimate_mood(face_image: bytes) -> MoodResult` as `typing.Protocol` interfaces. **Unchanged by this spec** (FR-017) — the concrete adapters implement these exact signatures.
- **Domain result types** — `domain/result_types.py:29-49`: `MoodResult(label: str, confidence: float | None, model_version: str)` and `AgeResult(estimated_age: int, range: tuple[int, int] | None, model_version: str)`. **Unchanged** — `EmotiEffMoodEstimator` populates `MoodResult` with the mapped PRD label + softmax top-1 probability; `MiVOLOAgeEstimator` populates `AgeResult` with the rounded point estimate + `range=None`. The `confidence: float | None` and `range: ... | None` widenings (specs 004/005) already accommodate these.
- **Domain services** — `domain/mood.py` `MoodService.analyze()` (lines 77-107): detect → `estimate_mood` → `normalize_mood_label` (safety net, maps out-of-set → "no concluyente") → `_clamp_confidence` ([0,1]). `domain/age.py` `AgeService.analyze()` (lines 105-129): detect → `estimate_age` → `normalize_age_result(raw, half_width)` (derives symmetric range from point-only, clamps `min >= 0`). **Both unchanged** — the adapters' outputs flow through the existing normalization. The mood adapter's AFEW→PRD mapping (FR-005) and the domain `normalize_mood_label` are defense-in-depth, not redundant.
- **Mock adapters** — `adapters/mock/mood_estimator.py` `MockMoodEstimator` → `MoodResult(label="neutral", confidence=0.74, model_version="mock-mood-v1")`; `adapters/mock/age_estimator.py` `MockAgeEstimator` → `AgeResult(estimated_age=32, range=(27,37), model_version="mock-age-estimator-v1")`. **Retained verbatim** (FR-017/FR-019) — the spec is explicitly forbidden from altering them.
- **Production wiring** — `main.py:72-213` `wire_production_adapters(app)` currently wires real SQLAlchemy persistence + `YuNetDetector()` + `SFaceEmbedder()` (spec 008, lines 152-155) + `MockAgeEstimator()` + `MockMoodEstimator()` (lines 156-157). This spec edits **only** the two mood/age lines to construct `EmotiEffMoodEstimator`/`MiVOLOAgeEstimator`; detector/embedder/persistence unchanged. The selector `select_wiring(app, app_mode)` (lines 234-250) and `create_app()` (lines 359-419) are unchanged.
- **Spec 008 adapter pattern (the template to mirror)** — `adapters/ml/sface_embedder.py` `SFaceEmbedder.embed()`: decode bytes → internal YuNet detection (double-detection, research R-5) → `face_crop` (`cv2.FaceRecognizerSF.alignCrop`) → `feature` → `Embedding`. Construction: `ModelDownloader.ensure()` fetches model files → `cv2.FaceRecognizerSF_create` load-test → `ModelCorruptError` on failure. `adapters/ml/face_crop.py` `face_crop(recognizer, src_img, face_box)` wraps `alignCrop`, raises `InvalidFaceBox` on zero-area box. `adapters/ml/model_downloader.py` `ModelDownloader.ensure(name, url) -> Path`: cache hit → return; else download to `.part` → atomic `os.replace` → return; `ModelUnavailableError` on failure. `adapters/ml/constants.py` holds model filenames/URLs/versions/licenses + `ModelUnavailableError`/`ModelCorruptError`/`InvalidFaceBox`.
- **Config** — `config.py` `Settings` has `app_mode` (default `mock`), `quality_threshold` (0.5), `age_range_half_width_years` (5, spec 005), `models_dir` + download timeouts (spec 008). **Missing**: `mood_confidence_threshold` (new this spec, FR-006).
- **Domain purity test** — `tests/domain/test_domain_purity.py` asserts the domain imports no `face_insight.adapters`/`sqlalchemy`/`fastapi`/`torch`/`cv2`/`opencv`/`numpy`/`onnxruntime`/`PIL`/etc. `FORBIDDEN_PREFIXES` (line 60) and `REAL_ML_PREFIXES` (line 80) already include `torch`, `onnxruntime`. **This spec extends both to add `timm`, `hsemotion`, `emotiefflib`, `mivolo`** (FR-012).
- **Real-model integration test pattern** — `tests/integration/test_real_ml_adapters.py` (spec 008): `pytestmark = pytest.mark.requires_models` + an autouse fixture `_skip_if_no_models_or_not_production` that skips when `APP_MODE != production` or model files absent. `_models_available()` checks the `models/` cache. **This spec extends `_models_available()` to also check the mood/age model files and adds mood/age test functions.**
- **License test** — `tests/unit/test_ml_licenses.py` (spec 008) asserts YuNet/SFace license constants. **This spec adds assertions for the EmotiEff + MiVOLO license constants.**
- **pyproject.toml** — dependencies list (lines 10-29) has `opencv-python-headless`, `onnxruntime`, `numpy` (spec 008). **Missing**: `torch` (CPU), `timm`, `hsemotion-onnx`. `requires_models` marker already registered (line 55).
- **docker-compose.yml** — `models/` bind mount already present (spec 008). **No compose change** this spec.

### Reuse opportunities

- `SFaceEmbedder` structure — the mood/age adapters mirror it exactly: constructor does `ModelDownloader.ensure()` + load-test → `ModelCorruptError`; the `estimate_*` method does decode → internal YuNet detect → `face_crop` → inference. Copy the pattern, swap the inference backend.
- `face_crop` — reused unchanged (the same `cv2.FaceRecognizerSF.alignCrop` wrapper). Both new adapters need an SFace recognizer instance *only* for `alignCrop` (the alignment transform), exactly as `SFaceEmbedder` does. This means each adapter loads the SFace model file too (already cached from spec 008) — no extra download.
- `ModelDownloader` + `models/` cache — reused unchanged; two new model filenames/URLs added to `constants.py`.
- `YuNet` model file — reused for the internal alignment detection (already cached from spec 008).
- `Settings` (pydantic-settings) — extend with one new field (`mood_confidence_threshold`) rather than a new config class; follows the `age_range_half_width_years` pattern.
- `tests/domain/test_domain_purity.py` — extend the forbidden-import lists rather than a new test.
- `tests/integration/test_real_ml_adapters.py` — extend `_models_available()` + add test functions rather than a new module.
- `normalize_age_result` (spec 005) — the age adapter returns `range=None` (point-only) and the existing domain normalization derives the symmetric range. **No domain change** — the point-only path is already exercised by `ScriptableMockAgeEstimator` (spec 005).
- `normalize_mood_label` (spec 004) — the mood adapter maps AFEW→PRD internally; the domain normalizer is the safety net. **No domain change.**

### Integration touch-points

- `backend/src/face_insight/adapters/ml/emotieff_mood.py` — **new** (`EmotiEffMoodEstimator`).
- `backend/src/face_insight/adapters/ml/mivolo_age.py` — **new** (`MiVOLOAgeEstimator`).
- `backend/src/face_insight/adapters/ml/constants.py` — **edit**: add `EMOTIEFF_MODEL_FILENAME`/`URL`/`VERSION`/`LICENSE`, `MIVOLO_CHECKPOINT_FILENAME`/`URL`/`VERSION`/`LICENSE`, the `AFEW_TO_PRD_LABEL_MAP`, and `DEFAULT_MOOD_CONFIDENCE_THRESHOLD`.
- `backend/src/face_insight/adapters/ml/__init__.py` — **edit**: export `EmotiEffMoodEstimator`, `MiVOLOAgeEstimator` + new constants.
- `backend/src/face_insight/config.py` — **edit**: add `mood_confidence_threshold: float = 0.5` + a `[0,1]` clamp validator.
- `backend/src/face_insight/main.py` — **edit**: in `wire_production_adapters`, replace `MockAgeEstimator()`/`MockMoodEstimator()` with `MiVOLOAgeEstimator()`/`EmotiEffMoodEstimator()` (lines 156-157).
- `backend/pyproject.toml` — **edit**: add `torch` (CPU), `timm`, `hsemotion-onnx`.
- `backend/tests/domain/test_domain_purity.py` — **edit**: extend `FORBIDDEN_PREFIXES`/`REAL_ML_PREFIXES` with `timm`, `hsemotion`, `emotiefflib`, `mivolo`.
- `backend/tests/unit/test_ml_licenses.py` — **edit**: add EmotiEff/MiVOLO license assertions.
- `backend/tests/unit/test_wiring_selector.py` — **edit**: add production-mode `EmotiEffMoodEstimator`/`MiVOLOAgeEstimator` instance-type assertions.
- `backend/tests/integration/test_real_ml_adapters.py` — **edit**: extend `_models_available()` + add mood/age real-model tests.
- New docs: `specs/009-concrete-mood-age-adapters/contracts/` + `quickstart.md` calibration section.

### Coverage limitations

None material. All 14 evidence paths returned `no_recorded_issue`; the `tests/integration/` subtree is excluded from the graph by design (not a failure) — `test_real_ml_adapters.py` was read directly as ground truth. Metadata-changed freshness on several files (modified by spec 008 after the last full index) was resolved by reading source directly.

---

## Research Items

### R-1: EmotiEff/HSEmotion inference API (ONNX Runtime) — mood adapter mechanism

**Decision**: Use the `hsemotion-onnx` (or `emotiefflib[onnx]`) wrapper library, which loads `enet_b0_8_best_afew.onnx` into an ONNX Runtime session and exposes a high-level `predict(image)` / `predict_probs(image)` API returning the softmax distribution over the 8 AFEW classes. `EmotiEffMoodEstimator` constructs the HSEmotion predictor from the model path (obtained via `ModelDownloader.ensure()`), runs `predict_probs` on the aligned face crop, takes `argmax` (→ AFEW class index → mapped PRD label via `AFEW_TO_PRD_LABEL_MAP`) and the top-1 probability as confidence. If the top-1 probability < `settings.mood_confidence_threshold`, the label becomes "no concluyente" (the low confidence is still returned). The adapter makes no direct `onnxruntime.InferenceSession` calls — it goes through the wrapper, mirroring how `SFaceEmbedder` uses OpenCV's wrapper rather than raw `cv2.dnn.readNetFromONNX` (spec 008 R-1).

**Rationale**: The spec pins "ONNX Runtime" as the runtime and `enet_b0_8_best_afew.onnx` as the model. `hsemotion-onnx`/`emotiefflib[onnx]` is the supported inference wrapper over that exact runtime — it encapsulates the model-specific preprocessing (resize to 224×224, normalization, channel ordering) and postprocessing (softmax). Reimplementing that with a raw `onnxruntime.InferenceSession` would be reimplementing the wrapper, violating Principle I (demo simplicity) with no benefit. The wrapper is Apache 2.0 (FR-004).

**Alternatives considered**:
- *Raw `onnxruntime.InferenceSession` + manual pre/post-processing*: rejected — reimplements the wrapper, ~3× the code, error-prone, no demo value.
- *A different EmotiEff model (e.g. `enet_b0_8_best_va_mtl.onnx`)*: rejected — the spec pins `enet_b0_8_best_afew.onnx` (AFEW 8-class). The adapter is swappable behind the port if a different model is later desired (Principle VII).

### R-2: MiVOLO inference API (PyTorch CPU + timm) — age adapter mechanism

**Decision**: Use the MiVOLO library's `Models`/`VisionAgeGenderPredictor` entrypoint with `task_type='age'`, `with_tensors=False`, loading the `volo_d1` face-only age checkpoint on CPU (`device='cpu'`). `MiVOLOAgeEstimator` constructs the predictor from the checkpoint path (obtained via `ModelDownloader.ensure()`), runs `predict(image)` on the aligned face crop, extracts the returned age (a float), rounds it to a non-negative integer (`max(0, round(age))`), and returns `AgeResult(estimated_age=that_int, range=None, model_version="mivolo-volo-d1-face-v1")`. The domain `normalize_age_result` (spec 005) derives the symmetric range. The adapter imports `torch` and `timm` (transitively, via `mivolo`) only inside `adapters/ml/mivolo_age.py`.

**Rationale**: MiVOLO is a PyTorch/timm model that loads a `.pth` checkpoint — it is not an ONNX graph, so ONNX Runtime cannot serve it. PyTorch CPU + timm is the model's native runtime, mandated by the model format (FR-020). MiVOLO's `VisionAgeGenderPredictor` is the supported high-level API; using it mirrors the wrapper-first approach of `SFaceEmbedder`/`EmotiEffMoodEstimator`. CPU-only satisfies Constitution Quality Gate §7 (no GPU).

**Alternatives considered**:
- *Exporting MiVOLO to ONNX and using ONNX Runtime*: rejected — that is model-conversion work explicitly out of scope (FR-019, Constitution Explicit Non-Goals "no model training/fine-tuning") and would require a separate conversion step + a different checkpoint artifact.
- *A different age model (e.g. DEX)*: rejected — the spec pins MiVOLO face-only. Swappable behind the port (Principle VII).

### R-3: MiVOLO checkpoint license verification (Constitution Principle III, strict-mode note)

**Decision**: The MiVOLO *code* is Apache 2.0 (verified from the repo `LICENSE` file). The MiVOLO *checkpoint* (`volo_d1` face-only age) is released under the repo's Apache 2.0 / a compatible research-use license — the working assumption (pinned by the orchestrator) is that it is distributable for research/demo use. Plan-time verification: the `tests/unit/test_ml_licenses.py` test asserts `MIVOLO_LICENSE == "Apache-2.0"` (code) and documents the checkpoint license. **If plan-time verification finds an incompatible checkpoint license, the adapter is swapped behind the `AgeEstimator` port (Constitution Principle VII) without a spec change** — the port abstraction is the constitutional safeguard (the spec's own edge case, line 206).

**Rationale**: Constitution Principle III requires open-source/open-weights models. MiVOLO's code license is unambiguously Apache 2.0. The checkpoint is the only uncertainty; the port abstraction means an incompatible license does not invalidate the spec — it triggers a swap, not a redesign. This is a **compliance-adjacent** decision; in strict mode it is **not blocking** because (a) the orchestrator pinned the working assumption (Apache 2.0 / open-weights), (b) the spec explicitly provides the port-swap fallback, and (c) the demo does not redistribute the checkpoint (it is downloaded at runtime via `ModelDownloader`, like the spec 008 models). Recorded here for traceability.

**Alternatives considered**:
- *Bundling the checkpoint in the repo*: rejected — bloats the repo and creates a redistribution concern; runtime download (like spec 008) is cleaner and the `models/` cache + bind mount already support it.
- *A different age model with an unambiguous checkpoint license*: rejected — the spec pins MiVOLO; the port-swap fallback is the safeguard.

### R-4: AFEW 8-class → PRD §6.4 label mapping (FR-005)

**Decision**: The mapping is a fixed dictionary in `adapters/ml/constants.py`:

```python
AFEW_TO_PRD_LABEL_MAP = {
    0: "neutral",          # Neutral
    1: "feliz",            # Happy
    2: "triste",           # Sad
    3: "sorprendido",      # Surprise
    4: "no concluyente",   # Anger   — no PRD category
    5: "no concluyente",   # Disgust — no PRD category
    6: "no concluyente",   # Fear    — no PRD category
    7: "no concluyente",   # Contempt — no PRD category
}
```

The exact AFEW class index → emotion name ordering is taken from the HSEmotion/EmotiEffLib documentation for `enet_b0_8_best_afew.onnx` (AFEW 8-class: Neutral, Happy, Sad, Surprise, Anger, Disgust, Fear, Contempt). The adapter applies the map after `argmax`; the domain `normalize_mood_label` (spec 004) is the safety net that maps any residual out-of-set label to "no concluyente". The mapping table is reproduced in the calibration docs (`quickstart.md` + `contracts/adapter-port-conformance.md`).

**Rationale**: The PRD §6.4 label set is `{neutral, feliz, triste, sorprendido, enojo, no concluyente}` — 6 labels. AFEW has 8 classes. The 3 AFEW emotions with no PRD category (Disgust, Fear, Contempt) are reported as "no concluyente"; Anger is reported as "enojo".

**Alternatives considered**:
- *Dropping the 4 unmapped classes (return None / skip)*: rejected — loses the signal that a prediction was made; "no concluyente" is the PRD's intended bucket for "not classifiable into the supported set."
- *Mapping Anger→triste, etc. (closest-emotion heuristic)*: rejected — introduces a subjective mapping with no PRD basis; "no concluyente" is the honest, auditable choice.

### R-5: Mood confidence threshold — new setting (FR-006)

**Decision**: Add `mood_confidence_threshold: float = 0.5` to `config.py` `Settings`, with a `field_validator` clamping it to `[0.0, 1.0]` (mirroring how `age_range_half_width_years` is clamped to `>= 0`). `EmotiEffMoodEstimator` reads it from `get_settings()` at construction (or accepts an override for testability). When the model's top-1 softmax probability < `mood_confidence_threshold`, the adapter returns `MoodResult(label="no concluyente", confidence=that_low_prob, model_version=...)`. The mock mood estimator is unaffected (it returns `0.74 > 0.5`). The threshold is env-configurable via `MOOD_CONFIDENCE_THRESHOLD` and documented in the calibration docs.

**Rationale**: 0.5 is a reasonable default for a top-1 softmax probability gate — below half-confidence, the prediction is not trustworthy. The spec pins this default and env-configurability (PRD §11). The clamp to `[0,1]` matches the confidence range. Following the `age_range_half_width_years` pattern keeps the config surface uniform.

**Alternatives considered**:
- *No threshold (always return the argmax label)*: rejected — the spec explicitly requires low-certainty predictions to surface as "no concluyente" (FR-006, US1 AC-2).
- *A per-class threshold*: rejected — YAGNI (Principle I); a single top-1 threshold is sufficient for the demo.

### R-6: Age adapter returns point-only; domain derives range (FR-007, no domain change)

**Decision**: `MiVOLOAgeEstimator.estimate_age()` returns `AgeResult(estimated_age=round(point), range=None, model_version="mivolo-volo-d1-face-v1")`. The existing `AgeService.normalize_age_result(raw, half_width)` (spec 005, `domain/age.py:34-81`) already handles `range is None` by deriving `min = max(0, estimated - half_width)`, `max = estimated + half_width`, guaranteeing `min >= 0` and `min <= estimated_age <= max`. **No domain change** — this is the exact point-only path already exercised by `ScriptableMockAgeEstimator`'s `AGEPOINT` marker (spec 005). The existing `age_range_half_width_years` setting (default 5) is reused; the calibration docs document the recommended half-width for the real MiVOLO model and its typical error margin (±3-5 years for face-only age estimation).

**Rationale**: Reusing the existing normalization path is the spec's central "no domain change" guarantee (FR-007/FR-017). The point-only `range=None` widening was added in spec 005 precisely to accommodate this.

**Alternatives considered**:
- *The adapter deriving the range itself*: rejected — duplicates the domain normalization logic, violating hexagonal isolation and the spec's "no domain change" guarantee.
- *Returning a range from MiVOLO (if the model provided one)*: MiVOLO face-only returns a point estimate; there is no model-native range to return.

### R-7: Shared face_crop reuse + double-detection (FR-008, mirroring SFaceEmbedder)

**Decision**: Both `EmotiEffMoodEstimator` and `MiVOLOAgeEstimator` follow the `SFaceEmbedder.embed()` composition exactly: on `estimate_mood`/`estimate_age(image_bytes)` they (a) decode the bytes via `cv2.imdecode`, (b) run an internal YuNet detection (reusing the YuNet model file already cached by spec 008) to obtain the face-box+landmarks, (c) call `face_crop` (→ `cv2.FaceRecognizerSF.alignCrop`) to produce the fixed-size aligned crop, (d) run model inference on the aligned crop. Each adapter constructs its own YuNet detector instance + SFace recognizer instance (for `alignCrop`) at construction, loading the already-cached model files (no re-download). If the internal detection finds zero faces, the adapter raises `ValueError("no face detected for alignment")` (mirroring `SFaceEmbedder`); the domain `MoodService`/`AgeService` wrap this into `MoodInternalError`/`AgeInternalError` → 500 (the domain's own `NoFace` check on `Detector.detect` runs first and usually catches the no-face case before the adapter is invoked).

**Rationale**: The `MoodEstimator.estimate_mood`/`AgeEstimator.estimate_age` port signatures receive raw image bytes, not a pre-cropped face (FR-017 — no port change). Alignment needs the detector's face-box+landmarks. This is the exact pattern from spec 008's `SFaceEmbedder` (research R-5): double-detection is acceptable because YuNet inference on a ≤640px JPEG on CPU is ~tens of ms, well within demo tolerance, and the Constitution waives real-time SLOs. The aligned crop materially improves mood/age inference quality (US3). Reusing `face_crop` means no new alignment code (FR-008 AC-2).

**Alternatives considered**:
- *Change the port signature to accept a pre-cropped/aligned face*: rejected — violates FR-017 (port change), ripples into domain services + mock adapters + all existing tests.
- *Skip alignment (feed raw crop to the mood/age model)*: rejected — the spec mandates the alignment pipeline (FR-008) and alignment materially improves accuracy (US3).
- *A shared alignment helper that both adapters call without each owning a YuNet/SFace instance*: equivalent but complicates construction; each adapter owning its instances (like `SFaceEmbedder`) is simpler and keeps the adapters independent.

### R-8: Model acquisition — ModelDownloader reuse (FR-009, no new infrastructure)

**Decision**: Both model files are obtained via the existing `ModelDownloader` from spec 008 (same `models/` cache, same atomic `.part`-rename, same single-attempt timeout, same load-test integrity). Two new entries in `constants.py`:
- `EMOTIEFF_MODEL_FILENAME = "enet_b0_8_best_afew.onnx"`, `EMOTIEFF_MODEL_URL = <HSEmotion release URL>`.
- `MIVOLO_CHECKPOINT_FILENAME = "volo_d1_224_369_age_only-e7ee8cd0.pth"` (or the exact face-only age checkpoint filename), `MIVOLO_CHECKPOINT_URL = <MiVOLO release URL>`.

Each adapter constructor calls `downloader.ensure(FILENAME, URL)` then load-tests the model (HSEmotion predictor construction / MiVOLO predictor construction); load failure → `ModelCorruptError` (reusing the spec 008 exception). `ModelUnavailableError` on network failure. Pre-placing the files in `models/` (pre-download) is supported for air-gapped runs (FR-009 AC-4). The `models/` bind mount from spec 008 is reused unchanged — no compose change.

**Rationale**: Reusing spec 008's infrastructure is the spec's explicit design (FR-009, US4). No new downloader, cache dir, or compose volume. The load-test (predictor construction) is the integrity check, consistent with spec 008 R-8 (no checksum — Principle VIII waives security guarantees).

**Alternatives considered**:
- *A separate cache dir for mood/age models*: rejected — no benefit; the spec 008 `models/` cache + bind mount already handle it.
- *Checksum verification*: rejected — see spec 008 R-8 (Principle VIII waiver; upstream publishes no signed checksums; load-test covers execution integrity).

### R-9: New deps isolated to adapters/ml/* (FR-013, domain purity enforcement)

**Decision**: `torch`, `timm`, and `hsemotion-onnx` (or `emotiefflib[onnx]`) are imported **only** inside `adapters/ml/emotieff_mood.py` and `adapters/ml/mivolo_age.py` (transitively, via the wrapper libraries). The domain purity test (`tests/domain/test_domain_purity.py`) is extended to add `timm`, `hsemotion`, `emotiefflib`, and `mivolo` to both `FORBIDDEN_PREFIXES` and `REAL_ML_PREFIXES`. The mock wiring path (`wire_mock_adapters`) imports none of them (it imports only `adapters.mock`), so `APP_MODE=mock` requires no ML runtime (FR-011). `torch` is installed as the CPU build (no CUDA) to avoid GPU dependencies in the container.

**Rationale**: Direct enforcement via the existing purity test is stronger than a code-review convention and prevents regressions (mirrors spec 008 R-10). This is the concrete expression of Constitution Principle VII for this spec.

### R-10: Real-model integration tests — extend the spec 008 module (FR-014)

**Decision**: Extend `tests/integration/test_real_ml_adapters.py` rather than create a new module. Extend `_models_available()` to also check `EMOTIEFF_MODEL_FILENAME` and `MIVOLO_CHECKPOINT_FILENAME` (so the autouse skip fires if any of the four model files is absent). Add test functions:
- `test_mood_estimator_valid_label_and_confidence`: single-face fixture → label in PRD set, confidence in [0,1], `model_version == EMOTIEFF_MODEL_VERSION`.
- `test_mood_estimator_low_confidence_no_conclusive`: (if a low-confidence fixture is available) → label "no concluyente".
- `test_age_estimator_point_only_and_invariants`: single-face fixture → `estimated_age >= 0`, `range is None`, `model_version == MIVOLO_MODEL_VERSION`; then run `normalize_age_result(raw, 5)` and assert `min >= 0` and `min <= estimated <= max`.
- `test_mood_no_face_raises` / `test_age_no_face_raises`: no-face fixture → adapter raises (or the detector returns 0 and the domain raises `NoFace`).
- `test_mood_multi_face` / `test_age_multi_face`: multi-face fixture → domain raises `MultipleFaces`.

All guarded by the existing `requires_models` marker + autouse skip. Fixtures are consented test images in `tests/fixtures/real_ml/` (PRD §12).

**Rationale**: Extending the existing module keeps the real-model test surface unified and reuses the skip machinery. Mirrors the spec 008 pattern exactly.

### R-11: Production wiring update (FR-010, backward compatible)

**Decision**: In `wire_production_adapters()` (`main.py`), replace:
```python
age_estimator = MockAgeEstimator()
mood_estimator = MockMoodEstimator()
```
with:
```python
from .adapters.ml import EmotiEffMoodEstimator, MiVOLOAgeEstimator  # noqa: PLC0415
age_estimator = MiVOLOAgeEstimator()
mood_estimator = EmotiEffMoodEstimator()
```
The detector (`YuNetDetector`) and embedder (`SFaceEmbedder`) lines (spec 008) are unchanged. The real SQLAlchemy persistence adapters (spec 007) are unchanged. The service-rebuild block is unchanged (the services already accept `MoodEstimator`/`AgeEstimator` ports). `wire_mock_adapters` is unchanged (FR-011/FR-019). `select_wiring` and `create_app` are unchanged. After this edit, production mode wires real adapters for all four ML ports (Fase 5 complete).

**Rationale**: This is the composition seam (Constitution Principle VII). The edit is two lines + an import; everything downstream is port-polymorphic.

### R-12: Observability — no biometric data in logs (FR-016)

**Decision**: The adapters log only structured JSON events: `model_loaded` (model name + version) at construction, and inference duration/status at the `estimate_*` level if desired. **No image bytes, mood label, age estimate, confidence value, or biometric response is logged.** This is consistent with specs 001-008 and Constitution Principle VIII (no traceability guarantee; PRD §12/§13).

**Rationale**: Constitution Principle VIII explicitly waives traceability. Logging biometric data would contradict PRD §12 and the existing convention. The structured logs (adapter loaded, model version) are sufficient for demo observability.
