# Data Model: Concrete Face Detection & Embedding ML Adapters (Fase 5a)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Scope

This spec introduces **no new domain entities, no new domain result types, no new ports, and no schema changes**. It is additive adapter infrastructure: two new concrete adapter classes (`YuNetDetector`, `SFaceEmbedder`) implement the pre-existing `Detector` and `Embedder` ports; two adapter-layer utilities (`face_crop`, `ModelDownloader`) and a `models/` cache directory support them. The `Embedding` result type and `FaceTemplate` schema are unchanged because SFace's 128-dimensional output matches the mock embedder's 128-dimensional vector (spec 001 `EMBEDDING_DIM=128`), per FR-018.

This document records the (unchanged) domain value objects the adapters populate, and the **non-domain** infrastructure surfaces the spec adds, for completeness.

---

## Domain Value Objects (unchanged — reused from spec 001)

### DetectionResult (from spec 001, unchanged)

`YuNetDetector.detect()` populates this from YuNet's output. No new attributes (FR-018).

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `face_count` | `int` | YuNet row count | 0 / 1 / N per FR-005 |
| `boxes` | `list[BoundingBox]` | YuNet rows cols 0-3 | one per detected face; empty when `face_count == 0` |
| `score` | `float` | `max(row[14])` over YuNet rows | highest confidence; 0.0 when no faces |

### BoundingBox (from spec 001, unchanged)

Populated from YuNet row columns `x, y, w, h`. No new attributes.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `x` | `int` | YuNet col 0 | top-left x |
| `y` | `int` | YuNet col 1 | top-left y |
| `width` | `int` | YuNet col 2 | |
| `height` | `int` | YuNet col 3 | |

### Embedding (from spec 001, unchanged)

`SFaceEmbedder.embed()` populates this from SFace's output. No new attributes. **The 128-dim length matches the mock embedder** → no `FaceTemplate.embedding` schema change, no `Comparison` port change.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `vector` | `list[float]` | SFace `feature()` output | **128** elements, L2-normalized (SFace `2021dec`) |
| `model_version` | `str` | constant `"sface-2021dec-v1"` | distinct from `mock-embedder-v1` (FR-003) |

### FaceTemplate (from spec 002, unchanged — no migration)

Persisted via `SqlAlchemyFaceTemplateRepository` (spec 007). The `embedding` column (existing) stores the 128-float list exactly as before; only the *contents* differ (real SFace vector vs. mock `[0.1]*128`). No Alembic migration is produced by this spec.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `id` | UUID | spec 002 | PK |
| `user_id` | UUID | spec 002 | FK → users |
| `embedding` | `list[float]` | SFace (production) / mock (mock) | 128-dim in both modes |
| `model_version` | `str` | `sface-2021dec-v1` (production) / `mock-embedder-v1` (mock) | distinguishes real vs. mock templates |
| `created_at` | datetime | spec 002 | |

---

## Adapter-Layer Surfaces (new — NOT domain entities)

These are infrastructure/adapter classes, not domain entities. They are not persisted and not part of the domain model; they are documented here for completeness and traceability.

### YuNetDetector (new adapter — implements `Detector` port)

| Aspect | Value |
|--------|-------|
| Location | `backend/src/face_insight/adapters/ml/yunet_detector.py` |
| Implements | `domain.ports.Detector` (`detect(image: bytes) -> DetectionResult`) |
| Model | `face_detection_yunet_2023mar.onnx` (OpenCV zoo, MIT license) |
| `model_version` | `"yunet-2023mar-v1"` (FR-003) |
| Backend | `cv2.FaceDetectorYN_create` (OpenCV DNN, CPU) |
| Construction | Loads model via `ModelDownloader.ensure()`; sets `score_threshold = settings.quality_threshold`, `nms_threshold=0.3`, `top_k=5000` |
| Fail-fast | `ModelUnavailableError` / `ModelCorruptError` at construction (FR-009) |

### SFaceEmbedder (new adapter — implements `Embedder` port)

| Aspect | Value |
|--------|-------|
| Location | `backend/src/face_insight/adapters/ml/sface_embedder.py` |
| Implements | `domain.ports.Embedder` (`embed(face_image: bytes) -> Embedding`) |
| Model | `face_recognition_sface_2021dec.onnx` (OpenCV zoo, Apache 2.0) |
| `model_version` | `"sface-2021dec-v1"` (FR-003) |
| Output dim | **128**, L2-normalized (asserted in integration tests; matches mock `EMBEDDING_DIM`) |
| Backend | `cv2.FaceRecognizerSF_create` (OpenCV DNN, CPU) |
| Alignment | Internal YuNet detection → `face_crop` (`alignCrop`) → `feature` (research R-5) |
| Construction | Loads SFace + a YuNet instance (shared model file) via `ModelDownloader.ensure()` |
| Fail-fast | `ModelUnavailableError` / `ModelCorruptError` at construction (FR-009) |

### face_crop (new adapter utility — NOT a port)

| Aspect | Value |
|--------|-------|
| Location | `backend/src/face_insight/adapters/ml/face_crop.py` |
| Signature | `face_crop(recognizer, src_img: cv2.Mat, face_box: cv2.Mat) -> cv2.Mat` |
| Implementation | Wraps `cv2.FaceRecognizerSF.alignCrop` (affine transform from 5 landmarks) |
| Output | Fixed-size aligned face image (SFace's expected input, 112×112) |
| Error path | `InvalidFaceBox` on zero/negative-area box (FR-007 AC-3) |
| Used by | `SFaceEmbedder.embed()` (both onboarding and login routes, via the same instance) |

### ModelDownloader + models/ cache (new infrastructure — NOT a domain entity)

| Aspect | Value |
|--------|-------|
| Location | `backend/src/face_insight/adapters/ml/model_downloader.py` |
| Cache dir | `settings.models_dir` (default `<repo_root>/models/`), bind-mounted into backend container (FR-010) |
| `ensure(name, url) -> Path` | Cache hit → return path; else download to `.part` → atomic `os.replace` → return path |
| Timeout | `connect=30s`, `read=120s` (configurable via settings) — single attempt, no retry (FR-008) |
| Integrity | Load-test by the adapter constructor (FR-009); no checksum (research R-8) |
| Errors | `ModelUnavailableError` (network/timeout), `ModelCorruptError` (load failure) |
| Offline | Pre-place `.onnx` files in `models/` → no network at runtime (FR-008 AC-4) |

---

## Configuration Surface (new settings — NOT domain entities)

Added to `config.py` `Settings` (pydantic-settings, env-overridable):

| Setting | Type | Default | Notes |
|---------|------|---------|-------|
| `models_dir` | `str` | `<repo_root>/models` | Model cache path; bind-mounted in compose (FR-010) |
| `model_download_connect_timeout` | `float` | `30.0` | httpx connect timeout (FR-008) |
| `model_download_read_timeout` | `float` | `120.0` | httpx read timeout (FR-008) |

`verification_threshold` (existing, default `0.5`) is **overridden to `0.363` in production mode** by `wire_production_adapters` unless `VERIFICATION_THRESHOLD` is explicitly set in the environment (research R-7). The field default stays `0.5` (mock-mode backward compatibility, FR-016/FR-019).

`detector_model_version` / `embedding_model_version` (existing, mock defaults) are **not changed** in `Settings`; the concrete adapters carry their own version constants (`yunet-2023mar-v1`, `sface-2021dec-v1`) and the `Embedding.model_version` / detection score reflect the real model in production mode.

---

## State Transitions

No domain state transitions are introduced or altered. The only stateful flow is model acquisition:

```
absent ──ensure()──▶ downloading (.part) ──complete──▶ cached (.onnx) ──load──▶ loaded
   ▲                       │ (fail/timeout)                  │ (corrupt)
   │                       ▼                                 ▼
   └──────── fail-fast (ModelUnavailableError) ◀──────── ModelCorruptError
```

A cached `.onnx` that fails the load-test is reported as `ModelCorruptError` (the file is not auto-deleted — the user inspects/re-places it; re-running with the file removed re-downloads).

---

## Validation Rules

- **FR-005**: `YuNetDetector.detect()` MUST return `face_count == 0` with empty `boxes` for a face-less image; `face_count == N` with N boxes for N faces. (YuNet's own `score_threshold` filter enforces the quality gate at the model level.)
- **FR-006**: SFace embeddings MUST yield same-person cosine similarity ≥ `verification_threshold` (0.363 production) and different-person < threshold. (Validated by the real-model integration tests, FR-015.)
- **Embedding dimension**: `len(Embedding.vector) == 128` (asserted in integration tests; matches mock → no `ComparisonError` on cross-mode comparisons within the same model version).
- **FR-009**: Adapter construction MUST fail fast with an actionable error naming the model if the file cannot be obtained or loaded — before the app serves traffic.
- **FR-013**: No module under `domain/` imports `cv2`, `onnxruntime`, `numpy`, or `adapters.ml.*` (enforced by `tests/domain/test_domain_purity.py`).
