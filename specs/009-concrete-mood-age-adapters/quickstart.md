# Quickstart: Concrete Mood & Age Estimation ML Adapters (Fase 5b)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

This guide documents runnable validation scenarios that prove the concrete mood and age adapters work end-to-end in production mode, and that mock mode + existing tests remain unaffected. It does not include full implementation code (see `tasks.md`).

---

## Prerequisites

- Docker + Docker Compose (Principle IV).
- The spec 008 model files cached in `models/` (`face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx`) — obtained automatically on first production startup or pre-placed.
- The new model files: `enet_b0_8_best_afew.onnx` (mood) and the MiVOLO face-only age checkpoint (age) — obtained automatically on first production startup via `ModelDownloader`, or pre-placed in `models/` for offline runs.
- Consented test fixture images in `backend/tests/fixtures/real_ml/` (PRD §12): `single_face.jpg`, `no_face.jpg`, `multi_face.jpg`.

---

## Scenario 1 — Mock mode unchanged (backward compatible, FR-011/FR-018)

**Prerequisites**: no `models/` directory, no `APP_MODE` set.

**Run**:
```bash
cd backend
APP_MODE=mock pytest tests/domain tests/contract tests/unit -q
```

**Expected**: all existing domain, contract, and unit tests pass (no models required, no torch/timm/onnxruntime runtime required). The mock mood/age estimators are wired; the domain purity test passes (no `torch`/`timm`/`hsemotion` import in `domain/`).

**Start the app**:
```bash
docker compose up --build
# APP_MODE defaults to mock; app starts with no models/ dir
```

**Expected**: the app starts and behaves identically to specs 001-008 (mock mood `neutral`/0.74, mock age 32/27-37).

---

## Scenario 2 — Production mode wires real mood + age adapters (FR-010, SC-001/SC-018)

**Prerequisites**: `APP_MODE=production`, `DATABASE_URL` reachable, all four model files in `models/`.

**Run**:
```bash
cd backend
APP_MODE=production pytest tests/unit/test_wiring_selector.py -q
```

**Expected**: the wiring selector test asserts `app.state.mood_estimator` is an `EmotiEffMoodEstimator`, `app.state.age_estimator` is a `MiVOLOAgeEstimator`, and `app.state.detector`/`app.state.embedder` are still the spec 008 concrete instances (`YuNetDetector`/`SFaceEmbedder`).

**Start the app**:
```bash
APP_MODE=production docker compose up --build
```

**Expected**: the app starts; on first startup the mood + age model files are downloaded into `models/` (if absent). Inspect the logs for `model_loaded` events naming `enet_b0_8_best_afew.onnx` and the MiVOLO checkpoint. No image/label/age/confidence is logged (FR-016).

---

## Scenario 3 — Real mood estimation returns a valid label + confidence (FR-001, SC-002)

**Prerequisites**: `APP_MODE=production`, all models present, `single_face.jpg` fixture.

**Run**:
```bash
cd backend
APP_MODE=production pytest tests/integration/test_real_ml_adapters.py::test_mood_estimator_valid_label_and_confidence -q
```

**Expected**: the mood estimator returns a `MoodResult` with `label` in `{neutral, feliz, triste, sorprendido, enojo, no concluyente}`, `confidence` in [0, 1], and `model_version == "emotieff-enet-b0-afew-v1"`.

**Manual check**:
```bash
curl -F "image=@single_face.jpg" http://localhost:8000/api/analysis/mood
# → {"label": "<prd-label>", "confidence": <float>, "modelVersion": "emotieff-enet-b0-afew-v1"}
```

---

## Scenario 4 — Real age estimation returns a point estimate; domain derives range (FR-002/FR-007, SC-003)

**Prerequisites**: `APP_MODE=production`, all models present, `single_face.jpg` fixture.

**Run**:
```bash
cd backend
APP_MODE=production pytest tests/integration/test_real_ml_adapters.py::test_age_estimator_point_only_and_invariants -q
```

**Expected**: the age estimator returns `AgeResult(estimated_age=<non-negative int>, range=None, model_version="mivolo-volo-d1-face-v1")`. After domain normalization, the response satisfies `min >= 0` and `min <= estimatedAge <= max`.

**Manual check**:
```bash
curl -F "image=@single_face.jpg" http://localhost:8000/api/analysis/age
# → {"estimatedAge": <int>, "range": {"min": <int>, "max": <int>}, "modelVersion": "mivolo-volo-d1-face-v1"}
```

---

## Scenario 5 — AFEW → PRD label mapping (FR-005, SC-004)

Inspect `backend/src/face_insight/adapters/ml/constants.py` `AFEW_INDEX_TO_EMOTION_NAME` / `AFEW_TO_PRD_LABEL_MAP`. The index ordering follows the HSEmotion-onnx library `idx_to_class` for `enet_b0_8_best_afew.onnx` (verified by `test_afew_index_order_matches_library`):

| AFEW index | AFEW emotion | PRD label |
|------------|--------------|-----------|
| 0 | Anger | `enojo` |
| 1 | Contempt | `no concluyente` |
| 2 | Disgust | `no concluyente` |
| 3 | Fear | `no concluyente` |
| 4 | Happiness | `feliz` |
| 5 | Neutral | `neutral` |
| 6 | Sadness | `triste` |
| 7 | Surprise | `sorprendido` |

The three AFEW emotions with no PRD §6.4 category (Contempt, Disgust, Fear) are reported as `no concluyente`; Anger is reported as `enojo`. The mapping table is also reproduced (semantically, without indices) in `contracts/adapter-port-conformance.md`. The domain `normalize_mood_label` (spec 004) is the safety net.

---

## Scenario 6 — Low-confidence mood → "no concluyente" (FR-006)

**Prerequisites**: `APP_MODE=production`, `MOOD_CONFIDENCE_THRESHOLD=0.95` (force the override), `single_face.jpg` fixture.

**Run**:
```bash
cd backend
APP_MODE=production MOOD_CONFIDENCE_THRESHOLD=0.95 pytest tests/integration/test_real_ml_adapters.py::test_mood_estimator_low_confidence_no_conclusive -q
```

**Expected**: with the threshold raised above any realistic top-1 probability, the mood label is `no concluyente` and the low confidence value is still returned.

---

## Scenario 7 — No-face and multi-face handling (FR-014, SC-012)

**Prerequisites**: `APP_MODE=production`, all models present, `no_face.jpg` + `multi_face.jpg` fixtures.

**Run**:
```bash
cd backend
APP_MODE=production pytest tests/integration/test_real_ml_adapters.py -k "no_face or multi_face" -q
```

**Expected**: no-face fixture → detector returns `face_count == 0` → domain raises `NoFace` (400 `no_face`); the estimator is not invoked. Multi-face fixture → detector returns `face_count > 1` → domain raises `MultipleFaces` (400 `multiple_faces`).

---

## Scenario 8 — Real-model tests skip when models absent (FR-014, Constitution Quality Gate §7)

**Prerequisites**: `models/` empty or missing the mood/age files.

**Run**:
```bash
cd backend
APP_MODE=production pytest tests/integration/test_real_ml_adapters.py -q
```

**Expected**: all real-model mood/age tests are **skipped** (`requires_models` autouse guard); the rest of the suite remains green.

```bash
APP_MODE=mock pytest tests/integration/test_real_ml_adapters.py -q
```

**Expected**: all real-model tests skipped (`APP_MODE != production` guard).

---

## Scenario 9 — Domain purity (FR-012, SC-005)

**Run**:
```bash
cd backend
pytest tests/domain/test_domain_purity.py -q
```

**Expected**: the domain layer has no import of `torch`, `timm`, `hsemotion`, `emotiefflib`, `mivolo`, `onnxruntime`, `cv2`, `opencv`, `numpy`, `face_crop`, or any `adapters.ml.*` module. (The forbidden-import lists are extended by this spec.)

---

## Scenario 10 — Model download + cache reuse (FR-009, SC-009/SC-010)

**Prerequisites**: empty `models/` cache, network available, `APP_MODE=production`.

**Run**:
```bash
rm -rf models/*  # clear cache
APP_MODE=production docker compose up --build
# first startup: logs show model_download_start + model_download_complete for each file
# second startup: logs show model_cache_hit (no re-download)
```

**Expected**: on first startup, each of the four model files is downloaded once into `models/`. On second startup, all four are served from the cache (no network). A corrupt/unreachable model causes a fail-fast startup error naming the model.

---

## Threshold & Calibration Documentation (FR-015, SC-013)

### Mood — `mood_confidence_threshold`

- **Default**: `0.5` (env: `MOOD_CONFIDENCE_THRESHOLD`, clamped to [0, 1]).
- **Semantics**: the softmax top-1 probability below which the mood label is reported as `no concluyente`.
- **Difference from mock**: the mock always returns `neutral`/`0.74` (above 0.5), so it never triggers the override. Real EmotiEff predictions have a full softmax; low-certainty predictions surface as `no concluyente`.

### Age — `age_range_half_width_years` (existing, spec 005)

- **Default**: `5` (env: `AGE_RANGE_HALF_WIDTH_YEARS`).
- **Semantics**: the half-width used to derive the symmetric range from the MiVOLO point estimate (`min = max(0, est - hw)`, `max = est + hw`).
- **MiVOLO typical error margin**: face-only age MAE is ±3-5 years; a half-width of 5 is a reasonable default.
- **Difference from mock**: the mock returns a fixed range 27-37; the real adapter returns a point estimate and the domain derives the range.

Both thresholds remain configurable via the environment (PRD §11). Mock-mode defaults are unchanged (backward compatible).
