# Contract: Adapter → Port Conformance (YuNetDetector, SFaceEmbedder)

**Spec**: [spec.md](../spec.md) | **Date**: 2026-09-01

The concrete adapters MUST conform to the existing domain `Detector` and `Embedder` protocols (`domain/ports.py`). The port signatures are **unchanged** (FR-018); these contracts specify the concrete adapters' behavior under production wiring.

---

## YuNetDetector : Detector

```
detect(image: bytes) -> DetectionResult
```

| Property | Contract |
|----------|---------|
| **Port** | `domain.ports.Detector` (unchanged) |
| **Model** | `face_detection_yunet_2023mar.onnx` via `cv2.FaceDetectorYN_create` (OpenCV DNN, CPU backend) |
| **License** | MIT (OpenCV model zoo) — satisfies Constitution Principle III |
| **`model_version`** | `"yunet-2023mar-v1"` (distinct from `mock-yolo-v0`, FR-003) |
| **Input** | JPEG/PNG bytes (≤640px long edge, per OQ-8; decoded via `cv2.imdecode`) |
| **Output — single face** | `DetectionResult(face_count=1, boxes=[BoundingBox(x,y,w,h)], score=conf)` with `score >= quality_threshold` |
| **Output — no face** | `DetectionResult(face_count=0, boxes=[], score=0.0)` |
| **Output — N faces** | `DetectionResult(face_count=N, boxes=[BoundingBox,...N], score=max_conf)` |
| **Construction** | Loads model via `ModelDownloader.ensure()`; `score_threshold = settings.quality_threshold`, `nms_threshold=0.3`, `top_k=5000` |
| **Fail-fast** | `ModelUnavailableError` / `ModelCorruptError` at construction, naming the model (FR-009) |
| **Determinism** | Same image + same model file → same `DetectionResult` (no random seed; YuNet is deterministic on CPU) |
| **Domain isolation** | `YuNetDetector` imports `cv2`, `numpy`; the domain layer does **not** import `YuNetDetector`, `cv2`, or `numpy` (FR-013) |

---

## SFaceEmbedder : Embedder

```
embed(face_image: bytes) -> Embedding
```

| Property | Contract |
|----------|---------|
| **Port** | `domain.ports.Embedder` (unchanged) |
| **Model** | `face_recognition_sface_2021dec.onnx` via `cv2.FaceRecognizerSF_create` (OpenCV DNN, CPU backend) |
| **License** | Apache 2.0 (OpenCV model zoo) — satisfies Constitution Principle III |
| **`model_version`** | `"sface-2021dec-v1"` (distinct from `mock-embedder-v1`, FR-003) |
| **Input** | Image bytes (the raw onboarding/login capture; alignment is performed internally — see below) |
| **Output** | `Embedding(vector: list[float], model_version="sface-2021dec-v1")` |
| **Vector dimension** | **128** (asserted in integration tests; matches mock `EMBEDDING_DIM=128` → no schema/result-type change) |
| **Vector normalization** | L2-normalized (SFace property); `||vector||₂ ≈ 1.0` |
| **Alignment** | Internally: decode → YuNet detect → `face_crop` (`cv2.FaceRecognizerSF.alignCrop`, affine transform from 5 landmarks) → `feature`. Both onboarding and login use the same `SFaceEmbedder` instance → same alignment (FR-007) |
| **Construction** | Loads SFace + a YuNet instance (shared model file) via `ModelDownloader.ensure()` |
| **Fail-fast** | `ModelUnavailableError` / `ModelCorruptError` at construction (FR-009); embedder inference failure → `OnboardingInternalError` / `LoginInternalError` (existing domain mapping, unchanged) |
| **Domain isolation** | `SFaceEmbedder` imports `cv2`, `numpy`; the domain layer does not (FR-013) |

---

## Verification Threshold Calibration (SFace + YuNet, cosine similarity)

| Mode | Default `verification_threshold` | Rationale |
|------|----------------------------------|-----------|
| `mock` | `0.5` | Backward compatible (specs 001-007); mock embedder returns all-equal vector → similarity 1.0 ≫ 0.5 |
| `production` | `0.363` | OpenCV official LFW calibration (99.60% accuracy); overridden by `wire_production_adapters` unless `VERIFICATION_THRESHOLD` env is set explicitly |

**Decision rule** (unchanged domain logic, spec 003): `accepted = (cosine_similarity >= verification_threshold)`.

**Calibration source**: OpenCV `face_detect` sample + DNN face tutorial — "two faces have same identity if the cosine distance is greater than or equal to 0.363."

| Benchmark | Accuracy | Cosine threshold |
|-----------|----------|------------------|
| LFW | 99.60% | **0.363** (default) |
| CALFW | 93.95% | 0.340 |
| CPLFW | 91.05% | 0.275 |
| AgeDB-30 | 94.90% | 0.277 |
| CFP-FP | 94.80% | 0.212 |

**Configurability**: `VERIFICATION_THRESHOLD` env var overrides the default in both modes (PRD §11 — "el umbral de verificación debe ser configurable y documentado"). The threshold is **not** hard-coded in the domain; it is injected into `LoginService` at wiring time.

**Difference from mock**: The mock 0.5 threshold works because the mock embedder is degenerate (similarity is always 0.0 or 1.0). Real SFace same-person cosine clusters around 0.4-0.8 and different-person around -0.1-0.3, so 0.363 is the statistically calibrated separator. Using 0.5 with real SFace would reject most genuine logins — hence the mode-specific default.

---

## Wiring Contract (wire_production_adapters — updated)

| `APP_MODE` | detector | embedder | age_estimator | mood_estimator | persistence |
|------------|----------|----------|---------------|----------------|-------------|
| `mock` (or unset) | `MockDetector` | `MockEmbedder` | `MockAgeEstimator` | `MockMoodEstimator` | in-memory mocks |
| `production` | **`YuNetDetector`** (NEW) | **`SFaceEmbedder`** (NEW) | `MockAgeEstimator` (spec 009) | `MockMoodEstimator` (spec 009) | real SQLAlchemy (spec 007, unchanged) |

The selector `select_wiring(app, app_mode)` runs **exactly once** at composition time (Constitution Principle VII). The real SQLAlchemy persistence adapters from spec 007 are unchanged. The mock wiring function is unchanged (FR-018/FR-019).
