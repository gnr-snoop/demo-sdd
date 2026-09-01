# Contract: Model Download & Cache (Mood + Age Models)

**Spec**: [spec.md](../spec.md) | **Date**: 2026-09-01

This contract specifies how the concrete mood and age adapters obtain and cache their model files, reusing the `ModelDownloader` infrastructure from spec 008 (FR-009). No new downloader, cache directory, or compose volume is introduced.

---

## Model Files

| Adapter | Filename | URL | License | Runtime |
|---------|----------|-----|---------|---------|
| `EmotiEffMoodEstimator` | `enet_b0_8_best_afew.onnx` | HSEmotion/EmotiEffLib release (raw GitHub or release asset) | Apache 2.0 (code + model) | ONNX Runtime (CPU) |
| `MiVOLOAgeEstimator` | `volo_d1_224_369_age_only-e7ee8cd0.pth` (face-only age checkpoint) | MiVOLO release (raw GitHub or release asset) | Apache 2.0 (code) + open-weights (checkpoint) | PyTorch (CPU) + timm |

Both adapters also reuse the spec 008 model files for internal alignment:
- `face_detection_yunet_2023mar.onnx` (YuNet, MIT) — internal face detection for alignment.
- `face_recognition_sface_2021dec.onnx` (SFace, Apache 2.0) — provides `alignCrop` via `face_crop`.

These are already cached after spec 008; the new adapters load them from the cache (no re-download).

---

## Cache Directory

- **Path**: `settings.models_dir` (default `<repo_root>/models/`, resolved in `config.py`).
- **Bind mount**: `./models:/app/models:rw` in `docker-compose.yml` (from spec 008, unchanged — FR-009 AC-3).
- **Host ↔ container path identity**: the default `<repo_root>/models` mirrors the `usuarios/` convention (Principle V).

---

## Acquisition Contract (`ModelDownloader.ensure(name, url) -> Path`)

Reused verbatim from spec 008:

| Step | Behavior |
|------|----------|
| 1. Cache hit | If `<cache>/<filename>` exists → return its path (no network). |
| 2. Download | Else fetch from `url` to `<cache>/<filename>.part` via `httpx` (single attempt, `connect=30s` / `read=120s` configurable, no retry). |
| 3. Atomic rename | `os.replace(part, final)` on completion → no partial file ever cached. |
| 4. Interrupted download | A lone `.part` file is treated as absent → re-download. |
| 5. Network failure | Any `httpx` error / timeout → `ModelUnavailableError(filename, url)` (fail fast, FR-009). |
| 6. Integrity | Load-test by the adapter constructor (predictor construction); failure → `ModelCorruptError(filename)`. No checksum (spec 008 R-8 / Principle VIII). |

---

## Offline / Air-Gapped Support (FR-009 AC-4)

Pre-placing the model files in `models/` before startup is the supported air-gapped path:

```text
models/
├── face_detection_yunet_2023mar.onnx   (spec 008)
├── face_recognition_sface_2021dec.onnx (spec 008)
├── enet_b0_8_best_afew.onnx            (NEW — mood)
└── volo_d1_224_369_age_only-e7ee8cd0.pth (NEW — age)
```

When all four files are present, no network access is required at runtime. The `ModelDownloader.ensure()` cache-hit path returns immediately.

---

## Fail-Fast Behavior (FR-009)

| Condition | Error | When |
|-----------|-------|------|
| Network unavailable + file absent | `ModelUnavailableError` (names model + URL) | Adapter construction, before app serves traffic |
| Download timeout | `ModelUnavailableError` | Adapter construction |
| Corrupt / truncated file | `ModelCorruptError` (names model) | Adapter construction load-test |
| Unwritable cache dir | `ModelUnavailableError` (OSError wrapped) | Adapter construction |

All errors are raised at adapter construction (inside `wire_production_adapters`), so the process fails fast at startup before serving traffic. The errors name the specific model file for an actionable message.
