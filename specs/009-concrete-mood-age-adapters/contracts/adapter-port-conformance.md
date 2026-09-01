# Contract: Adapter → Port Conformance (EmotiEffMoodEstimator, MiVOLOAgeEstimator)

**Spec**: [spec.md](../spec.md) | **Date**: 2026-09-01

The concrete adapters MUST conform to the existing domain `MoodEstimator` and `AgeEstimator` protocols (`domain/ports.py`). The port signatures are **unchanged** (FR-017); these contracts specify the concrete adapters' behavior under production wiring.

---

## EmotiEffMoodEstimator : MoodEstimator

```
estimate_mood(face_image: bytes) -> MoodResult
```

| Property | Contract |
|----------|---------|
| **Port** | `domain.ports.MoodEstimator` (unchanged) |
| **Model** | `enet_b0_8_best_afew.onnx` via ONNX Runtime (`hsemotion-onnx`/`emotiefflib[onnx]` wrapper, CPU backend) |
| **License** | Apache 2.0 (HSEmotion/EmotiEffLib code + model) — satisfies Constitution Principle III |
| **`model_version`** | `"emotieff-enet-b0-afew-v1"` (distinct from `mock-mood-v1`, FR-003) |
| **Input** | Image bytes (the raw analysis capture; alignment is performed internally — see below) |
| **Output — valid prediction** | `MoodResult(label=AFEW_TO_PRD_LABEL_MAP[argmax], confidence=top1_prob, model_version="emotieff-enet-b0-afew-v1")` with `label` in `{neutral, feliz, triste, sorprendido, no concluyente}` and `confidence` in [0, 1] |
| **Output — low confidence** | When `top1_prob < mood_confidence_threshold` → `MoodResult(label="no concluyente", confidence=top1_prob, ...)` (FR-006) |
| **Label mapping** | AFEW 8-class → PRD §6.4: Neutral→neutral, Happy→feliz, Sad→triste, Surprise→sorprendido, Anger/Disgust/Fear/Contempt→no concluyente (FR-005) |
| **Alignment** | Internally: decode → YuNet detect → `face_crop` (`cv2.FaceRecognizerSF.alignCrop`) → `predict_probs`. Mirrors `SFaceEmbedder` double-detection (spec 008 R-5) |
| **Construction** | Loads model via `ModelDownloader.ensure()` + a YuNet instance + an SFace recognizer (for `alignCrop`, all cached from spec 008); reads `mood_confidence_threshold` from settings |
| **Fail-fast** | `ModelUnavailableError` / `ModelCorruptError` at construction, naming the model (FR-009); inference failure → `MoodInternalError` (existing domain mapping, unchanged) |
| **Determinism** | Same image + same model file → same `MoodResult` (ONNX Runtime CPU is deterministic) |
| **Domain isolation** | `EmotiEffMoodEstimator` imports `onnxruntime`/`hsemotion`/`cv2`/`numpy`; the domain layer does **not** (FR-012) |

---

## MiVOLOAgeEstimator : AgeEstimator

```
estimate_age(face_image: bytes) -> AgeResult
```

| Property | Contract |
|----------|---------|
| **Port** | `domain.ports.AgeEstimator` (unchanged) |
| **Model** | MiVOLO `volo_d1` face-only age checkpoint (`.pth`) via PyTorch (CPU) + `timm` (`VisionAgeGenderPredictor`, `task_type='age'`) |
| **License** | Apache 2.0 (MiVOLO code) + open-weights checkpoint (research R-3; port-swap fallback if incompatible) — satisfies Constitution Principle III |
| **`model_version`** | `"mivolo-volo-d1-face-v1"` (distinct from `mock-age-estimator-v1`, FR-003) |
| **Input** | Image bytes (the raw analysis capture; alignment is performed internally — see below) |
| **Output** | `AgeResult(estimated_age=max(0, round(point)), range=None, model_version="mivolo-volo-d1-face-v1")` — **point-only** (FR-007); the domain `AgeService.normalize_age_result` derives the symmetric range |
| **Range derivation** | Domain (spec 005, unchanged): `min = max(0, estimated - age_range_half_width_years)`, `max = estimated + age_range_half_width_years`; guarantees `min >= 0` and `min <= estimated_age <= max` |
| **Alignment** | Internally: decode → YuNet detect → `face_crop` (`alignCrop`) → `predict`. Mirrors `SFaceEmbedder` double-detection (spec 008 R-5) |
| **Construction** | Loads checkpoint via `ModelDownloader.ensure()` + a YuNet instance + an SFace recognizer (for `alignCrop`, cached from spec 008) |
| **Fail-fast** | `ModelUnavailableError` / `ModelCorruptError` at construction, naming the model (FR-009); inference failure → `AgeInternalError` (existing domain mapping, unchanged) |
| **Determinism** | Same image + same checkpoint → same `AgeResult` (PyTorch CPU inference in eval mode is deterministic) |
| **Domain isolation** | `MiVOLOAgeEstimator` imports `torch`/`timm`/`mivolo`/`cv2`/`numpy`; the domain layer does **not** (FR-012) |

---

## Mood Confidence Threshold Calibration (EmotiEff/HSEmotion)

| Mode | Default `mood_confidence_threshold` | Rationale |
|------|-------------------------------------|-----------|
| `mock` | `0.5` (unused — mock returns 0.74) | Backward compatible (specs 001-008); mock mood estimator always returns `neutral`/`0.74` ≫ 0.5 |
| `production` | `0.5` | Top-1 softmax probability gate; below this the label is reported as `no concluyente` (FR-006) |

**Decision rule** (adapter-level, FR-006): `label = AFEW_TO_PRD_LABEL_MAP[argmax] if top1_prob >= mood_confidence_threshold else "no concluyente"`.

**Configurability**: `MOOD_CONFIDENCE_THRESHOLD` env var overrides the default in both modes (PRD §11 — "el umbral de verificación debe ser configurable y documentado"). The threshold is read by the adapter at construction, not hard-coded in the domain.

**Difference from mock**: The mock mood estimator always returns `neutral`/`0.74` (above the default 0.5 threshold), so it never triggers the low-confidence override. Real EmotiEff predictions have a full softmax distribution; low-certainty predictions (e.g. a face that is hard to classify) surface as `no concluyente` rather than as a confident wrong label.

---

## Age Range Calibration (MiVOLO)

| Mode | Default `age_range_half_width_years` | Rationale |
|------|--------------------------------------|-----------|
| `mock` | `5` (unused — mock returns range 27-37) | Backward compatible (spec 005); mock age estimator returns a fixed range |
| `production` | `5` | MiVOLO face-only age MAE is typically ±3-5 years; a half-width of 5 yields a ±5-year symmetric range around the point estimate |

**Decision rule** (domain, spec 005, unchanged): `min = max(0, estimated - half_width)`, `max = estimated + half_width`.

**Configurability**: `AGE_RANGE_HALF_WIDTH_YEARS` env var overrides the default (PRD §11). The derivation lives in the domain (`normalize_age_result`), not the adapter — the adapter returns a point-only `AgeResult(range=None)`.

**Difference from mock**: The mock age estimator returns a fixed `estimated_age=32`/`range=(27,37)`. The real MiVOLO adapter returns a model-predicted point estimate with `range=None`; the domain derives the symmetric range. The normalization path is identical (the spec 005 point-only path).

---

## Wiring Contract (wire_production_adapters — updated)

| `APP_MODE` | detector | embedder | age_estimator | mood_estimator | persistence |
|------------|----------|----------|---------------|----------------|-------------|
| `mock` (or unset) | `MockDetector` | `MockEmbedder` | `MockAgeEstimator` | `MockMoodEstimator` | in-memory mocks |
| `production` | `YuNetDetector` (spec 008) | `SFaceEmbedder` (spec 008) | **`MiVOLOAgeEstimator`** (NEW) | **`EmotiEffMoodEstimator`** (NEW) | real SQLAlchemy (spec 007, unchanged) |

The selector `select_wiring(app, app_mode)` runs **exactly once** at composition time (Constitution Principle VII). The real SQLAlchemy persistence adapters from spec 007 are unchanged. The detector/embedder from spec 008 are unchanged. The mock wiring function is unchanged (FR-011/FR-019). After this spec, **all four ML ports have concrete real adapters in production mode — Fase 5 is complete**.
