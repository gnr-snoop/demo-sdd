# Contract: Model Download / Cache (ModelDownloader + models/)

**Spec**: [spec.md](../spec.md) | **Date**: 2026-09-01

`ModelDownloader` obtains and caches `.onnx` model files for the concrete ML adapters. It is adapter-layer infrastructure (not a domain port). This contract specifies its behavior (FR-008, FR-009, FR-010).

---

## Cache

| Property | Value |
|----------|-------|
| Directory | `settings.models_dir` (default `<repo_root>/models/`) |
| Gitignored | `models/` is gitignored (model files are not committed) |
| Docker | Bind-mounted `./models:/app/models:rw` in `docker-compose.yml` backend service (FR-010); in-container path matches host path |
| Configurable | `MODELS_DIR` env var overrides |

## Models

| Adapter | File | URL | License |
|---------|------|-----|---------|
| `YuNetDetector` | `face_detection_yunet_2023mar.onnx` | `https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx` | MIT |
| `SFaceEmbedder` | `face_recognition_sface_2021dec.onnx` | `https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx` | Apache 2.0 |

## `ensure(model_name: str, url: str) -> Path`

```
1. final = cache / f"{model_name}.onnx"
2. if final.exists(): return final                      # cache hit (no network)
3. part = cache / f"{model_name}.onnx.part"
4. if part.exists(): remove(part)                        # stale interrupted download → re-fetch
5. GET url → stream to part                              # httpx, single attempt
     timeout = Timeout(connect=30s, read=120s, write=120s, pool=30s)
6. os.replace(part, final)                               # atomic rename → no partial file ever cached
7. return final
```

| Scenario | Behavior |
|----------|----------|
| Cached file present | Return path immediately; **no network fetch** (FR-008 AC-2) |
| Cache empty, network available | Download once to `.part`, atomic rename, return path (FR-008 AC-1) |
| Download interrupted (`.part` left) | Next `ensure()` treats `.part` as absent, re-downloads (FR-008 edge case) |
| Network error / timeout | Raise `ModelUnavailableError(model_name, url)` — **single attempt, no retry** (FR-008/FR-009) |
| Cache dir not writable | Raise `ModelUnavailableError` with a clear message (FR-009 edge case) |
| Air-gapped, file pre-placed | Load from cache, **no network** (FR-008 AC-4) |

## Integrity (load-test, NOT checksum)

After `ensure()` returns a path, the adapter constructor loads the model via OpenCV DNN (`cv2.FaceDetectorYN_create` / `cv2.FaceRecognizerSF_create`). A corrupt/truncated file fails the load → `ModelCorruptError(model_name)`. **No sha256/checksum/signature verification is performed** (research R-8): the OpenCV model repository publishes no signed checksums, and Constitution Principle VIII explicitly waives security guarantees. The load-test covers execution-integrity (a corrupt file cannot produce garbage output because it fails to load).

## Fail-Fast Guarantee (FR-009)

If a model cannot be obtained (network failure, corrupt file, unwritable cache), the concrete adapter construction raises `ModelUnavailableError` / `ModelCorruptError` **before** the app serves traffic. `wire_production_adapters` runs at startup (composition time); an uncaught construction exception prevents the app from starting — the process exits with a clear error naming the model and URL. This is the same fail-fast posture as the spec 007 DB reachability probe.

## Observability (FR-017)

Model download/load emits structured JSON logs only: `model_download_start`, `model_download_complete`, `model_loaded`, `model_unavailable`, `model_corrupt` — with `model_name`, `model_version`, `duration_ms`, `status`. **No image, embedding vector, or biometric data is logged** (Constitution Principle VIII, PRD §12/§13).
