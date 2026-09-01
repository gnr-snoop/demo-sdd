# Implementation Plan: Concrete Mood & Age Estimation ML Adapters (Fase 5b)

**Branch**: `009-concrete-mood-age-adapters` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-concrete-mood-age-adapters/spec.md`

## Summary

This spec completes Fase 5 by wiring two concrete open-source ML adapters behind the existing hexagonal `MoodEstimator` and `AgeEstimator` ports: `EmotiEffMoodEstimator` (EmotiEff/HSEmotion, ONNX Runtime, `enet_b0_8_best_afew.onnx`, Apache 2.0) and `MiVOLOAgeEstimator` (MiVOLO face-only, PyTorch CPU + timm, Apache 2.0). Both reuse the `face_crop` alignment pipeline and `ModelDownloader`/`models/` cache from spec 008 (double-detection pattern mirroring `SFaceEmbedder`). The mood adapter maps the 8 AFEW emotion classes to the PRD §6.4 label set and gates low-confidence predictions to "no concluyente" via a new `mood_confidence_threshold` setting (default 0.5). The age adapter returns a point-only `AgeResult(range=None)`; the existing domain `normalize_age_result` (spec 005) derives the symmetric range — no domain change. `wire_production_adapters()` is updated to substitute these for the mock mood/age estimators in production mode; mock mode and all existing tests are unchanged. New deps `torch` (CPU), `timm`, `hsemotion-onnx` are isolated to `adapters/ml/*`. Resolves Constitution OQ-5.

## Technical Context

**Language/Version**: Python 3.11 (backend, fixed by Constitution Principle III / `pyproject.toml requires-python = ">=3.11"`)

**Primary Dependencies**: FastAPI, SQLAlchemy, pydantic-settings, OpenCV (`opencv-python-headless`, `onnxruntime`, `numpy` — from spec 008), **new**: `torch` (CPU build), `timm`, `hsemotion-onnx` (or `emotiefflib[onnx]`). Frontend: React + Vite (unchanged).

**Storage**: PostgreSQL (embeddings/sessions, spec 007 — unchanged) + local filesystem `usuarios/` (Principle V — unchanged) + `models/` cache dir (spec 008 — reused, two new model files added). No schema migration.

**Testing**: pytest + pytest-asyncio (existing). New: real-model integration tests for mood/age adapters, skipped via `pytest.mark.requires_models` / `APP_MODE` guard when models absent or mode != production (reusing the spec 008 pattern).

**Target Platform**: Linux container via Docker Compose (Principle IV). CPU-only inference — no GPU required (Constitution Quality Gate §7).

**Project Type**: web-service (FastAPI backend + React frontend). This spec touches only the backend.

**Performance Goals**: Demo-grade only (Constitution Explicit Non-Goals — "no real-time performance SLOs"). Mood/age inference on a ≤640px JPEG on CPU is expected in the hundreds-of-milliseconds range; acceptable for an on-demand dashboard analysis.

**Constraints**: Domain layer must not import `torch`/`timm`/`hsemotion`/`onnxruntime`/`cv2`/`numpy`/`face_crop`/any adapter module (Constitution Principle VII, FR-012). Mock mode must remain model-free and runtime-free (FR-011). No port/entity/result-type/HTTP-contract/frontend change (FR-017). Existing domain/contract/unit tests unchanged (FR-018).

**Scale/Scope**: 2 new adapter modules + 1 config field + 1 wiring edit + 1 domain-purity-test extension + 1 real-model integration test module + calibration docs. No new endpoints, entities, ports, or frontend changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Demo-First Scope** | ✅ PASS | Real mood/age adapters are the core Fase 5 demo deliverable (PRD §18). No production-grade scope creep; reuses spec 008 infrastructure rather than building new. YAGNI respected — no new ports, endpoints, or frontend. |
| **II. Spec-Driven Workflow** | ✅ PASS | This plan follows spec → plan → tasks → implement. Builds on specs 001-008. |
| **III. Open-Source ML** | ✅ PASS | EmotiEff/HSEmotion: Apache 2.0 (code + model). MiVOLO: Apache 2.0 (code) + open-weights checkpoint (license verified at plan time, R-3; port abstraction is the safeguard if incompatible). Both OSI-approved. |
| **IV. Containerized Execution** | ✅ PASS | `models/` bind mount from spec 008 reused; no compose topology change. New deps installed in the backend image. |
| **V. Local Filesystem Image Storage** | ✅ PASS | No image-storage change. `usuarios/` untouched. |
| **VI. PostgreSQL for Embeddings** | ✅ PASS | No DB/schema change. No migration. Mood/age results are transient (never persisted). |
| **VII. Hexagonal Domain Isolation** | ✅ PASS | New adapters implement existing `MoodEstimator`/`AgeEstimator` ports; domain purity test extended to forbid `torch`/`timm`/`hsemotion`. Composition-time selection only. |
| **VIII. No Security/Traceability/Identity** | ✅ PASS | No security/traceability/identity hardening introduced. Observability limited to structured JSON logs (no images/labels/ages logged). No audit log. |

**Quality Gates**:
- §6 (integration tests): real-model integration tests added (FR-014), skippable in CI.
- §7 (no GPU to develop/test): domain/contract/unit tests use mocks, model-free; ML-adapter integration tests skip when models absent. Both new runtimes CPU-only.
- §1 (Constitution Check): this table. No violations.

**Post-Phase-1 re-check**: The Phase 1 design introduces no port/entity/result-type/contract change (FR-017) and no domain import of the new runtimes (FR-012). The `mood_confidence_threshold` setting follows the exact `quality_threshold`/`age_range_half_width_years` pattern (no new config mechanism). Re-check PASS.

## Project Structure

### Documentation (this feature)

```text
specs/009-concrete-mood-age-adapters/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── adapter-port-conformance.md
│   └── model-download.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   └── face_insight/
│       ├── adapters/
│       │   └── ml/
│       │       ├── emotieff_mood.py      # NEW — EmotiEffMoodEstimator (ONNX Runtime)
│       │       ├── mivolo_age.py         # NEW — MiVOLOAgeEstimator (PyTorch CPU + timm)
│       │       ├── constants.py          # EDIT — add mood/age model constants + AFEW mapping
│       │       ├── __init__.py           # EDIT — export new adapters
│       │       ├── face_crop.py          # REUSED (spec 008)
│       │       ├── model_downloader.py   # REUSED (spec 008)
│       │       ├── yunet_detector.py     # REUSED (spec 008)
│       │       └── sface_embedder.py     # REUSED (spec 008, the pattern to mirror)
│       ├── config.py                     # EDIT — add mood_confidence_threshold
│       ├── domain/                       # UNCHANGED (ports, mood.py, age.py, result_types.py)
│       └── main.py                       # EDIT — wire_production_adapters mood/age lines
├── tests/
│   ├── domain/test_domain_purity.py      # EDIT — extend forbidden imports (torch/timm/hsemotion)
│   ├── unit/test_ml_licenses.py          # EDIT — add mood/age license assertions
│   ├── unit/test_wiring_selector.py      # EDIT — add production mood/age instance-type assertions
│   └── integration/test_real_ml_adapters.py  # EDIT — add mood/age real-model tests
└── pyproject.toml                        # EDIT — add torch (CPU), timm, hsemotion-onnx

frontend/                                 # UNCHANGED
docker-compose.yml                        # UNCHANGED (models/ bind mount already from spec 008)
```

**Structure Decision**: Web application layout (backend + frontend) from specs 001-008, unchanged. This spec is additive to `backend/src/face_insight/adapters/ml/` (two new adapter modules) plus small edits to `config.py`, `main.py`, `constants.py`, `__init__.py`, the domain purity test, the license test, the wiring selector test, the real-model integration test, and `pyproject.toml`. No frontend, compose, or domain change.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two different inference runtimes in one spec (ONNX Runtime for mood + PyTorch/timm for age) | Mandated by the model formats: `enet_b0_8_best_afew.onnx` is an ONNX graph (→ ONNX Runtime); MiVOLO is a PyTorch/timm model loading a checkpoint (→ PyTorch). A single runtime cannot serve both. | A single-runtime alternative would require converting one model to the other's format (ONNX export of MiVOLO or retraining EmotiEff in PyTorch) — that is model-training/conversion work explicitly out of scope (FR-019, Constitution Explicit Non-Goals "no model training/fine-tuning") and contradicts Principle I (demo simplicity). |
| Double face-detection per mood/age inference (once in `Detector.detect` for count/quality, once inside each adapter for alignment) | The `MoodEstimator.estimate_mood`/`AgeEstimator.estimate_age` port signatures receive raw image bytes, not a pre-cropped face (FR-017 — no port change). Alignment needs the detector's face-box+landmarks. Mirrors the `SFaceEmbedder` pattern from spec 008 (research R-5). | Changing the port signature to accept a pre-cropped face violates FR-017 (no port change) and ripples into the domain services + mock adapters + all existing tests. Caching the detector's last result couples independent ports via hidden state, breaking hexagonal isolation. |
