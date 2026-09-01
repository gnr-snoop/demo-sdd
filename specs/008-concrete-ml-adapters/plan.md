# Implementation Plan: Concrete Face Detection & Embedding ML Adapters (Fase 5a — Detector + Embedder)

**Branch**: `008-concrete-ml-adapters` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-concrete-ml-adapters/spec.md`

## Summary

Wire two concrete open-source ML adapters behind the existing hexagonal `Detector` and `Embedder` ports: `YuNetDetector` (YuNet via OpenCV DNN, MIT) and `SFaceEmbedder` (SFace via OpenCV DNN, Apache-2.0, 128-dim L2-normalized embeddings). Add a shared `face_crop` alignment pipeline (thin wrapper over OpenCV's `alignCrop` affine transform), a `ModelDownloader` with a `models/` cache + Docker bind mount, and update `wire_production_adapters()` to substitute the real detector+embedder (mood/age stay mock — spec 009). New runtime deps: `opencv-python-headless`, `onnxruntime`, `numpy`. Add a skippable real-model integration suite (`pytest.mark.requires_models`) and threshold-calibration docs (recommended SFace+YuNet cosine threshold **0.363**, per OpenCV's LFW calibration). The domain layer, mock adapters, result types, HTTP contracts, and frontend are unchanged (FR-018) — the spec is purely additive adapter infrastructure. Resolves Constitution OQ-4.

## Technical Context

**Language/Version**: Python 3.11 (fixed by Constitution Principle III / existing `pyproject.toml` `requires-python = ">=3.11"`).

**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic-Settings (existing); **new**: `opencv-python-headless` (DNN module — single inference backend for YuNet + SFace), `onnxruntime` (declared, available as OpenCV DNN backend; no direct API calls — FR-014), `numpy` (array interop with OpenCV Mats). OpenCV's `cv2.FaceDetectorYN_create` / `cv2.FaceRecognizerSF_create` are the DNN-backed wrappers used (they load the `.onnx` via the DNN module internally — see research R-3).

**Storage**: PostgreSQL for embeddings (unchanged, spec 007); local filesystem `usuarios/<id>/pictures.jpg` (unchanged, Principle V); **new** `models/` cache dir at repo root for `.onnx` files, bind-mounted into the backend container (FR-010).

**Testing**: pytest + pytest-asyncio (existing); **new** `pytest.mark.requires_models` marker + autouse guard skipping real-model integration tests when model files absent or `APP_MODE != production` (FR-015, Constitution Quality Gate §7).

**Target Platform**: Linux container (Docker Compose, Constitution Principle IV); CPU-only inference (no GPU required — Non-Goals).

**Project Type**: web-service backend (additive adapter modules; no frontend change).

**Performance Goals**: Demo-grade only (Constitution Non-Goals: "no real-time performance SLOs"). YuNet+SFace on a ≤640px JPEG on CPU is well under 1s; double-detection in the embedder path is acceptable (research R-5).

**Constraints**: Open-source models only (Principle III); domain layer must not import OpenCV/ONNX/NumPy/concrete adapters (Principle VII, FR-013); mock mode + existing tests unchanged (FR-012/FR-018/FR-019); no new endpoints/entities/ports/result-types (FR-018); fail-fast on model unobtainability (FR-009).

**Scale/Scope**: Single-process demo; 2 model files (~few MB each); 3 new adapter modules + 1 utility + config/compose edits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Demo-First Scope** | ✅ PASS | Additive adapter wiring behind existing ports; no production hardening. Model download is lazy-on-first-use with a documented pre-download fallback (simplest path that keeps `docker compose up` canonical). No retry, no checksum — demo-simple, justified by Principle VIII. |
| **II. Spec-Driven Workflow** | ✅ PASS | This plan follows spec → plan → tasks → implement; spec derived from PRD §18 Fase 5a / §11. |
| **III. Technology Stack (open-source ML)** | ✅ PASS | YuNet (MIT via OpenCV model zoo) + SFace (Apache 2.0) — both OSI-approved open-weights. Resolves OQ-4 to SFace. `opencv-python-headless`/`onnxruntime`/`numpy` are additive Python packages, not a stack change. |
| **IV. Containerized Execution** | ✅ PASS | `models/` cache bind-mounted into the backend container via `docker-compose.yml` (FR-010); `docker compose up` remains canonical. |
| **V. Local Filesystem Image Storage** | ✅ PASS | Unchanged — `usuarios/` storage untouched; only `models/` cache added (model files, not user images). |
| **VI. PostgreSQL for Embeddings** | ✅ PASS | Unchanged — `FaceTemplate.embedding` stays 128-dim (SFace matches mock dimension); no schema migration. |
| **VII. Hexagonal / Ports-and-Adapters** | ✅ PASS | `YuNetDetector` implements existing `Detector` port; `SFaceEmbedder` implements existing `Embedder` port; `face_crop` + `ModelDownloader` are adapter-layer utilities, not domain ports. Domain layer imports none of them (FR-013, verified by extending `tests/domain/test_domain_purity.py` assertions). Mocks retained verbatim (FR-018). |
| **VIII. Explicit Non-Goals (no security/traceability/identity)** | ✅ PASS | No checksum/signature on model files (load-test only — FR-009); explicitly justified by Principle VIII (no security guarantee). No audit log, no liveness, no 1:N. See Complexity Tracking. |

**Open Questions resolved by this spec**: **OQ-4** (embedding model) → SFace (PATCH-level constitution bump per Governance; updates Technology Stack table embedding-model row). OQ-6 (distance metric) reaffirmed as cosine with a model-specific threshold (0.363 production / 0.5 mock).

**No blocking violations.** One Principle-VIII-adjacent decision (no model checksum) is recorded in Complexity Tracking with its Principle-VIII justification.

## Project Structure

### Documentation (this feature)

```text
specs/008-concrete-ml-adapters/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   ├── adapter-port-conformance.md
│   └── model-download.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/face_insight/
│   ├── adapters/
│   │   ├── ml/                      # NEW — concrete ML adapters (this spec)
│   │   │   ├── __init__.py          #   exports YuNetDetector, SFaceEmbedder, face_crop
│   │   │   ├── yunet_detector.py    #   YuNetDetector (Detector port)
│   │   │   ├── sface_embedder.py    #   SFaceEmbedder (Embedder port)
│   │   │   ├── face_crop.py         #   shared align+crop utility (wraps cv2 alignCrop)
│   │   │   ├── model_downloader.py  #   ModelDownloader + models/ cache
│   │   │   └── constants.py         #   model URLs, versions, dims, thresholds
│   │   ├── mock/                    # UNCHANGED (retained verbatim — FR-018)
│   │   ├── db/                      # UNCHANGED (spec 007 real persistence)
│   │   ├── fs/                      # UNCHANGED
│   │   └── http/                    # UNCHANGED
│   ├── domain/                      # UNCHANGED — no ports/entities/result-types added or altered (FR-018)
│   ├── config.py                    # EDIT — add models_dir, model download timeouts, production verification_threshold default
│   └── main.py                      # EDIT — wire_production_adapters() swaps MockDetector/MockEmbedder → YuNetDetector/SFaceEmbedder
├── tests/
│   ├── domain/test_domain_purity.py # EDIT — extend import-forbidden set: cv2, onnxruntime, numpy, adapters.ml
│   ├── unit/
│   │   ├── test_model_downloader.py # NEW
│   │   ├── test_face_crop.py        # NEW (degenerate-box error path; no model needed)
│   │   └── test_wiring_selector.py  # EDIT — assert production wires concrete detector/embedder types
│   └── integration/
│       └── test_real_ml_adapters.py # NEW — pytest.mark.requires_models; real YuNet+SFace assertions
├── pyproject.toml                   # EDIT — add opencv-python-headless, onnxruntime, numpy
└── Dockerfile                       # EDIT (if needed) — models/ dir creation; system deps for opencv headless

models/                               # NEW at repo root — .onnx cache (gitignored, bind-mounted)
docker-compose.yml                    # EDIT — bind-mount ./models:/app/models; set production verification_threshold
```

**Structure Decision**: Web-application layout (existing `backend/` + `frontend/`), unchanged. New code lives under `backend/src/face_insight/adapters/ml/` — a new `ml` adapter subpackage parallel to `mock/`, `db/`, `fs/`, `http/`, consistent with the hexagonal convention (one folder per adapter family). The `models/` cache sits at the repo root (next to `usuarios/`) so the host↔container bind-mount path is identical inside and outside the container (mirrors Principle V's `usuarios/` convention). No frontend changes.

## Complexity Tracking

> One Principle-VIII-adjacent decision recorded with justification. No unjustified violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No checksum/signature verification of downloaded model files (FR-009 specifies load-test only) | The OpenCV model repository does not publish signed checksums in a standard, machine-verifiable way; adding a bespoke checksum scheme would be production-grade hardening that contradicts the demo's purpose. | A checksum/sha256 verification step was rejected because (a) the upstream has no signed checksums to verify against, (b) Constitution Principle VIII explicitly waives security guarantees for this demo, and (c) the load-test (OpenCV DNN load at construction) already fails fast on corrupt/truncated files — covering the integrity-of-execution concern without a separate crypto step. |
| Double face-detection per embed (SFaceEmbedder re-runs YuNet internally for alignment — research R-5) | The `Embedder.embed(bytes)` port signature is fixed (FR-018) and the domain passes raw image bytes; OpenCV's `alignCrop` needs the detector's face-box+landmarks, so the embedder must obtain them itself. | Passing the detection box from the domain into the embedder was rejected because it would require changing the `Embedder` port signature or the domain service call — both forbidden by FR-018 (scope boundary: no port/entity/result-type change). Caching the detector's last result across port boundaries was rejected because it couples independent ports. The double-detection cost (~tens of ms on a ≤640px CPU image) is acceptable under the Constitution's explicit Non-Goal "no real-time performance SLOs." |
