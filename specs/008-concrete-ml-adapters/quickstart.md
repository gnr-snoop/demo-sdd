# Quickstart: Concrete ML Adapters (Fase 5a — Detector + Embedder)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

This guide documents runnable validation scenarios that prove the concrete `YuNetDetector` + `SFaceEmbedder` adapters work end-to-end behind the existing hexagonal ports, and that mock mode + existing tests remain non-regressed. It does **not** include full implementation code (see `tasks.md`).

---

## Prerequisites

- Docker + Docker Compose (Constitution Principle IV — canonical run path).
- Repo root: `D:\Snoop\demo-sdd` (host) / `/app` (backend container).
- No GPU required (CPU-only OpenCV DNN inference).
- Network access on first `APP_MODE=production` start (lazy model download), **or** pre-placed `.onnx` files in `models/` for offline runs.

## Setup

```bash
# From repo root
docker compose build backend
```

The new runtime deps (`opencv-python-headless`, `onnxruntime`, `numpy`) are installed in the backend image via `pyproject.toml`.

---

## Scenario 1 — Mock mode unchanged (non-regression, FR-012/FR-019)

**Goal**: Confirm the app and the existing test suite work identically to specs 001-007 with no models and no ML runtime.

```bash
# Run the existing domain/contract/unit suites with no models present.
APP_MODE=mock docker compose run --rm backend pytest tests/domain tests/contract tests/unit -q
```

**Expected**: All tests pass green. No `models/` directory required. The domain purity test asserts no `cv2`/`onnxruntime`/`numpy`/`adapters.ml` import in `domain/`.

```bash
# Start the app in mock mode with no models/ dir.
APP_MODE=mock docker compose up backend
curl -s http://localhost:8000/health   # → {"status":"healthy"}
```

**Expected**: App starts; `app.state.detector` is `MockDetector`, `app.state.embedder` is `MockEmbedder`.

---

## Scenario 2 — Production wiring substitutes concrete adapters (FR-011, SC-001)

**Goal**: Confirm `wire_production_adapters()` wires `YuNetDetector` + `SFaceEmbedder` (and keeps mock mood/age) when `APP_MODE=production`.

```bash
# Empty cache + network → lazy download on first start.
rm -rf models && mkdir models
APP_MODE=production docker compose up backend
```

**Expected**:
- Logs show `model_download_start` / `model_download_complete` for both `.onnx` files, then `model_loaded` with `yunet-2023mar-v1` and `sface-2021dec-v1`.
- `models/face_detection_yunet_2023mar.onnx` and `models/face_recognition_sface_2021dec.onnx` appear in the cache.
- App starts; `app.state.detector` is `YuNetDetector`, `app.state.embedder` is `SFaceEmbedder`, `app.state.mood_estimator`/`app.state.age_estimator` are still the mock instances.

**Verify wiring types** (unit test):
```bash
docker compose run --rm -e APP_MODE=production backend pytest tests/unit/test_wiring_selector.py -q
```
**Expected**: Tests assert `isinstance(app.state.detector, YuNetDetector)` and `isinstance(app.state.embedder, SFaceEmbedder)` in production, and mock instances in mock mode.

---

## Scenario 3 — Cache reuse (no re-download, FR-008 AC-2, SC-008)

**Goal**: Confirm a second start reuses cached models without network.

```bash
# models/ already populated from Scenario 2.
# Disable network to the backend container (or use --no-deps and a dead URL) and restart:
docker compose restart backend
```

**Expected**: No `model_download_start` log; `model_loaded` directly from cache. App starts normally.

---

## Scenario 4 — Real detection + embedding (FR-005/FR-006, SC-002/SC-003)

**Goal**: Confirm the real detector finds exactly one face in a single-face fixture and zero in a face-less fixture, and the real embedder produces a 128-dim vector with same-person/different-person separation.

> Fixtures are **consented test images only** (PRD §12). Place them under `backend/tests/fixtures/real_ml/` (gitignored or committed with documented consent).

```bash
APP_MODE=production docker compose run --rm backend pytest tests/integration/test_real_ml_adapters.py -q
```

**Expected** (tests marked `pytest.mark.requires_models`):
- `YuNetDetector.detect(single_face.jpg)` → `face_count == 1`, non-empty `boxes`, `score >= quality_threshold`.
- `YuNetDetector.detect(no_face.jpg)` → `face_count == 0`, empty `boxes`.
- `SFaceEmbedder.embed(...)` → `len(vector) == 128`, `model_version == "sface-2021dec-v1"`.
- `cosine(embed(personA_img1), embed(personA_img2)) >= 0.363` (same person).
- `cosine(embed(personA), embed(personB)) < 0.363` (different persons).

---

## Scenario 5 — Real-model tests skip gracefully when models absent (FR-015, SC-012)

**Goal**: Confirm CI without models stays green.

```bash
rm -rf models
APP_MODE=mock docker compose run --rm backend pytest tests/integration/test_real_ml_adapters.py -q
```

**Expected**: Real-model tests are **skipped** (`SKIPPED: real models absent or APP_MODE != production`); the rest of the suite passes green (Constitution Quality Gate §7).

---

## Scenario 6 — Fail-fast on unobtainable model (FR-009, SC-010)

**Goal**: Confirm a missing model + no network fails fast at startup with an actionable error.

```bash
rm -rf models && mkdir models
# Point MODELS_DIR to a read-only path OR block network; e.g. set a dead model URL via env override
# and start production:
APP_MODE=production docker compose up backend
```

**Expected**: The process exits before serving traffic with a `ModelUnavailableError` naming the model and URL (or `ModelCorruptError` for a corrupt file). No `200` from `/health`.

---

## Scenario 7 — Docker volume bind mount (FR-010, SC-009)

**Goal**: Confirm `models/` is bind-mounted into the backend container with a matching path.

```bash
docker compose up -d backend
docker compose exec backend ls -la /app/models
```

**Expected**: `/app/models` exists in the container and reflects the host `./models` contents (same files, same paths). Files placed on the host appear in the container immediately and survive `docker compose restart`.

---

## Scenario 8 — End-to-end onboarding + login with real models

**Goal**: Confirm the full PRD §6.1/§6.3 flow works against real detection + embedding in production mode.

```bash
APP_MODE=production docker compose up -d postgres backend frontend
# Frontend at http://localhost:5173
# 1. Onboard a user with a consented single-face image.
# 2. Log in as the same user with a different capture of the same face → authenticated (200, session cookie).
# 3. Log in as a different person → auth_failed (401).
```

**Expected**: Onboarding stores a real SFace 128-dim `FaceTemplate` in PostgreSQL; login computes cosine similarity ≥ 0.363 for the same person (accepted) and < 0.363 for a different person (401 `auth_failed`). No image/vector appears in logs (FR-017).

---

## Threshold Calibration (FR-016, SC-013)

| Mode | `verification_threshold` default | Source |
|------|----------------------------------|--------|
| `mock` | `0.5` | specs 001-007 (mock embedder: similarity ∈ {0.0, 1.0}) |
| `production` | **`0.363** | OpenCV LFW calibration (99.60% accuracy); see [contracts/adapter-port-conformance.md](./contracts/adapter-port-conformance.md) |

**Override**: `VERIFICATION_THRESHOLD=0.40 docker compose up backend` (env-configurable in both modes, PRD §11).

**Derivation**: 0.363 is OpenCV's published cosine separator for SFace on LFW, not a hand-tuned value. Real SFace same-person cosine ≈ 0.4-0.8; different-person ≈ -0.1-0.3. The mock 0.5 is incompatible with real SFace (would reject most genuine logins) — hence the mode-specific default. The threshold is injected into `LoginService` at wiring time; it is **not** hard-coded in the domain (Constitution Principle VII).

---

## Domain Isolation Check (FR-013, SC-004)

```bash
docker compose run --rm backend pytest tests/domain/test_domain_purity.py -q
```

**Expected**: Pass. The test asserts no module under `domain/` imports `cv2`, `onnxruntime`, `numpy`, `adapters.ml`, or any concrete adapter. The mock wiring path (`wire_mock_adapters`) likewise imports none of them.

---

## Out-of-Scope Reminders (FR-020)

This spec does **not** add: concrete mood/age adapters (spec 009), new HTTP endpoints, frontend changes, domain port/entity/result-type changes, mock-adapter changes, or existing-test changes. The `Embedding` result type and `FaceTemplate` schema are unchanged (SFace 128-dim matches mock 128-dim).

---

## Offline / Air-Gapped Pre-Download (FR-008 AC-4)

For air-gapped or offline demos, pre-place the `.onnx` model files in `models/`
before starting the app — no network access is required at runtime.

```bash
# Pre-download the model files into the host models/ cache (one-time, online).
mkdir -p models
curl -L -o models/face_detection_yunet_2023mar.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -L -o models/face_recognition_sface_2021dec.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

# Now start the app with NO network — models load from the cache.
APP_MODE=production docker compose up backend
```

**Expected**: Logs show `model_cache_hit` for both files (no `model_download_start`), then `model_loaded`. The app starts normally without any network access.
