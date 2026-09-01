# Data Model: Concrete Mood & Age Estimation ML Adapters (Fase 5b)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Scope

This spec introduces **no new domain entities, no new domain result types, no new ports, no schema changes, and no migration**. It is additive adapter infrastructure: two new concrete adapter classes (`EmotiEffMoodEstimator`, `MiVOLOAgeEstimator`) implement the pre-existing `MoodEstimator` and `AgeEstimator` ports; two new model files are added to the existing `models/` cache (spec 008); one new config field (`mood_confidence_threshold`) is added. The `MoodResult` and `AgeResult` value objects are unchanged because their `confidence: float | None` and `range: tuple[int,int] | None` widenings (specs 004/005) already accommodate the concrete adapters' outputs (FR-017).

This document records the (unchanged) domain value objects the adapters populate, the AFEW→PRD label mapping, and the **non-domain** infrastructure surfaces the spec adds, for completeness.

---

## Domain Value Objects (unchanged — reused from specs 001/004/005)

### MoodResult (from spec 001/004, unchanged)

`EmotiEffMoodEstimator.estimate_mood()` populates this. No new attributes (FR-017).

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `label` | `str` | `AFEW_TO_PRD_LABEL_MAP[argmax(softmax)]`, or `"no concluyente"` if top-1 prob < `mood_confidence_threshold` | member of `{neutral, feliz, triste, sorprendido, no concluyente}` (FR-005); domain `normalize_mood_label` is the safety net |
| `confidence` | `float \| None` | softmax top-1 probability | in [0, 1]; domain `_clamp_confidence` is the safety net |
| `model_version` | `str` | constant `"emotieff-enet-b0-afew-v1"` | distinct from `mock-mood-v1` (FR-003) |

### AgeResult (from spec 001/005, unchanged)

`MiVOLOAgeEstimator.estimate_age()` populates this. No new attributes (FR-017). The domain `AgeService.normalize_age_result` derives the symmetric range from the point-only output.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `estimated_age` | `int` | `max(0, round(mivolo_point_estimate))` | non-negative integer (FR-002) |
| `range` | `tuple[int, int] \| None` | **`None`** (point-only — the adapter does not derive a range) | the domain `normalize_age_result` derives `(max(0, est - hw), est + hw)` using `age_range_half_width_years` (spec 005, reused — no domain change) |
| `model_version` | `str` | constant `"mivolo-volo-d1-face-v1"` | distinct from `mock-age-estimator-v1` (FR-003) |

### DetectionResult / BoundingBox / Embedding (from spec 001, unchanged)

Not touched by this spec. The adapters use `YuNetDetector` (spec 008) internally for alignment detection; the domain's own `Detector.detect` call (for count/quality) is unchanged.

---

## AFEW 8-Class → PRD §6.4 Label Mapping (FR-005)

The EmotiEff/HSEmotion model `enet_b0_8_best_afew.onnx` is trained on the AFEW dataset for 8-class dynamic facial emotion recognition. The adapter maps the `argmax` class index to the PRD §6.4 label set via a fixed dictionary in `adapters/ml/constants.py`:

| AFEW index | AFEW emotion | PRD §6.4 label |
|------------|--------------|----------------|
| 0 | Neutral | `neutral` |
| 1 | Happy | `feliz` |
| 2 | Sad | `triste` |
| 3 | Surprise | `sorprendido` |
| 4 | Anger | `no concluyente` |
| 5 | Disgust | `no concluyente` |
| 6 | Fear | `no concluyente` |
| 7 | Contempt | `no concluyente` |

The 4 AFEW emotions with no PRD category (Anger, Disgust, Fear, Contempt) are reported as `no concluyente` — they are surfaced as inconclusive rather than dropped or mislabeled. The domain `normalize_mood_label` (spec 004) remains as a safety net mapping any residual out-of-set label to `no concluyente` (defense-in-depth, FR-005).

**Low-confidence override (FR-006)**: when the softmax top-1 probability < `mood_confidence_threshold` (default 0.5), the label is set to `no concluyente` regardless of the AFEW class (the low confidence value is still returned).

---

## Adapter-Layer Surfaces (new — NOT domain entities)

These are infrastructure/adapter classes, not domain entities. They are not persisted and not part of the domain model; they are documented here for completeness and traceability.

### EmotiEffMoodEstimator (new adapter — implements `MoodEstimator` port)

| Aspect | Value |
|--------|-------|
| Location | `backend/src/face_insight/adapters/ml/emotieff_mood.py` |
| Implements | `domain.ports.MoodEstimator` (`estimate_mood(face_image: bytes) -> MoodResult`) |
| Model | `enet_b0_8_best_afew.onnx` (HSEmotion/EmotiEffLib, Apache 2.0) |
| `model_version` | `"emotieff-enet-b0-afew-v1"` (FR-003) |
| Backend | ONNX Runtime (via `hsemotion-onnx` / `emotiefflib[onnx]` wrapper), CPU |
| Alignment | Internal YuNet detection → `face_crop` (`alignCrop`) → `predict_probs` (research R-7, mirrors `SFaceEmbedder`) |
| Label mapping | `AFEW_TO_PRD_LABEL_MAP[argmax(softmax)]` → PRD label; `"no concluyente"` if top-1 < `mood_confidence_threshold` (FR-005/FR-006) |
| Confidence | softmax top-1 probability (in [0, 1]) |
| Construction | Loads model via `ModelDownloader.ensure()` + YuNet + SFace (for `alignCrop`, all cached from spec 008); load-test → `ModelCorruptError` |
| Fail-fast | `ModelUnavailableError` / `ModelCorruptError` at construction (FR-009) |
| Domain isolation | imports `onnxruntime`/`hsemotion`/`cv2`/`numpy`; the domain does not (FR-012) |

### MiVOLOAgeEstimator (new adapter — implements `AgeEstimator` port)

| Aspect | Value |
|--------|-------|
| Location | `backend/src/face_insight/adapters/ml/mivolo_age.py` |
| Implements | `domain.ports.AgeEstimator` (`estimate_age(face_image: bytes) -> AgeResult`) |
| Model | MiVOLO `volo_d1` face-only age checkpoint (`.pth`, Apache 2.0 code + open-weights checkpoint — R-3) |
| `model_version` | `"mivolo-volo-d1-face-v1"` (FR-003) |
| Backend | PyTorch (CPU) + `timm` (via MiVOLO `VisionAgeGenderPredictor`), CPU |
| Alignment | Internal YuNet detection → `face_crop` (`alignCrop`) → `predict` (research R-7, mirrors `SFaceEmbedder`) |
| Output | point-only: `AgeResult(estimated_age=max(0, round(point)), range=None, ...)`; domain derives range (FR-007) |
| Construction | Loads checkpoint via `ModelDownloader.ensure()` + YuNet + SFace (for `alignCrop`, cached from spec 008); load-test → `ModelCorruptError` |
| Fail-fast | `ModelUnavailableError` / `ModelCorruptError` at construction (FR-009) |
| Domain isolation | imports `torch`/`timm`/`mivolo`/`cv2`/`numpy`; the domain does not (FR-012) |

### ModelDownloader + models/ cache (from spec 008, reused — NOT a domain entity)

Reused unchanged. Two new model files added to the existing cache:

| Model file | Adapter | Source URL | License |
|------------|---------|------------|---------|
| `enet_b0_8_best_afew.onnx` | `EmotiEffMoodEstimator` | HSEmotion/EmotiEffLib release | Apache 2.0 |
| `volo_d1_224_369_age_only-e7ee8cd0.pth` (face-only age) | `MiVOLOAgeEstimator` | MiVOLO release | Apache 2.0 (code) + open-weights (checkpoint, R-3) |

The existing spec 008 model files (`face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx`) are reused by both new adapters for the internal alignment detection + `alignCrop`. No new downloader, cache dir, or compose volume.

---

## Configuration Surface (new setting — NOT a domain entity)

Added to `config.py` `Settings` (pydantic-settings, env-overridable):

| Setting | Type | Default | Env var | Notes |
|---------|------|---------|---------|-------|
| `mood_confidence_threshold` | `float` | `0.5` | `MOOD_CONFIDENCE_THRESHOLD` | Softmax top-1 probability below which the mood label is reported as `no concluyente` (FR-006). Clamped to `[0.0, 1.0]` via a `field_validator`. Mock mood estimator unaffected (returns 0.74 > 0.5). |

The existing `age_range_half_width_years` (default 5, spec 005) is **reused unchanged** to derive the symmetric age range from the MiVOLO point estimate (FR-007). No new age setting is introduced.

The existing `models_dir` + download timeout settings (spec 008) are reused unchanged.

---

## State Transitions

No domain state transitions are introduced or altered. The only stateful flow is model acquisition (identical to spec 008):

```
absent ──ensure()──▶ downloading (.part) ──complete──▶ cached ──load──▶ loaded
   ▲                       │ (fail/timeout)                  │ (corrupt)
   │                       ▼                                 ▼
   └──────── fail-fast (ModelUnavailableError) ◀──────── ModelCorruptError
```

Mood/age results are transient — never persisted (FR-016, spec 004/005).

---

## Validation Rules

- **FR-001**: `EmotiEffMoodEstimator.estimate_mood()` MUST return a `MoodResult` with `label` in `{neutral, feliz, triste, sorprendido, no concluyente}`, `confidence` in [0, 1], and a non-empty `model_version`.
- **FR-002**: `MiVOLOAgeEstimator.estimate_age()` MUST return an `AgeResult` with a non-negative integer `estimated_age`, `range=None` (point-only), and a non-empty `model_version`.
- **FR-003**: `model_version` strings (`emotieff-enet-b0-afew-v1`, `mivolo-volo-d1-face-v1`) MUST be fixed and distinct from the mock versions (`mock-mood-v1`, `mock-age-estimator-v1`).
- **FR-005**: The AFEW→PRD mapping MUST map Neutral→neutral, Happy→feliz, Sad→triste, Surprise→sorprendido, Anger/Disgust/Fear/Contempt→no concluyente.
- **FR-006**: When top-1 softmax probability < `mood_confidence_threshold`, the label MUST be `no concluyente`.
- **FR-007**: The age adapter MUST return `range=None`; the domain `normalize_age_result` MUST derive a symmetric range with `min >= 0` and `min <= estimated_age <= max` (existing spec 005 invariants — no domain change).
- **FR-009**: Adapter construction MUST fail fast with an actionable error naming the model if the file cannot be obtained or loaded — before the app serves traffic.
- **FR-012**: No module under `domain/` imports `torch`, `timm`, `hsemotion`, `emotiefflib`, `mivolo`, `onnxruntime`, `cv2`, `numpy`, `face_crop`, or any `adapters.ml.*` module (enforced by `tests/domain/test_domain_purity.py`).
- **FR-017**: No port, entity, result type, HTTP contract, frontend, mock adapter, or existing test is changed by this spec.
