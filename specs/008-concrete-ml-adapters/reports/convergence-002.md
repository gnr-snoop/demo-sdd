# Convergence Report — Cycle 2

**Feature Dir**: `specs/008-concrete-ml-adapters`
**Date**: 2026-09-01
**Cycle**: 2
**Artifacts Evaluated**: `spec.md`, `plan.md`, `tasks.md`, `.specify/memory/constitution.md` (ratified v1.0.0)
**Mode**: strict (`max_convergence_cycles` = 2)

## Findings

| ID | Gap Type | Severity | Source | Evidence | Remaining Work |
|----|----------|----------|--------|----------|----------------|
| — | — | — | — | — | No actionable findings. |

## Assessment Summary

### Cycle 1 resolution verified

- **F-001 / T042 (FIXED)**: `ModelDownloader.ensure()` (`backend/src/face_insight/adapters/ml/model_downloader.py:64`) now sets `final_path = self._cache_dir / model_name` and `part_path = self._cache_dir / f"{model_name}.part"`, treating `model_name` as the complete filename. Callers pass `YUNET_MODEL_FILENAME`/`SFACE_MODEL_FILENAME` (already ending in `.onnx`), so the cached file is `models/face_detection_yunet_2023mar.onnx` (no double extension). Regression tests `test_real_yunet_filename_no_double_extension` and `test_real_yunet_filename_preplaced_is_cache_hit` in `backend/tests/unit/test_model_downloader.py` confirm the fix (FR-008 AC-2/AC-4, SC-008, SC-012).

### Requirements inventory (all satisfied)

| Req | Status | Evidence |
|-----|--------|----------|
| FR-001 YuNetDetector | ✅ | `adapters/ml/yunet_detector.py` implements `Detector.detect(image: bytes) -> DetectionResult` via `cv2.FaceDetectorYN_create`; port-conformance test `tests/unit/test_yunet_detector.py` |
| FR-002 SFaceEmbedder (128-dim) | ✅ | `adapters/ml/sface_embedder.py` implements `Embedder.embed` via `cv2.FaceRecognizerSF_create`; `EMBEDDING_DIM == 128` asserted in `tests/unit/test_sface_embedder.py` |
| FR-003 model_version strings | ✅ | `yunet-2023mar-v1` / `sface-2021dec-v1` in `constants.py`, distinct from mock versions; asserted in unit tests |
| FR-004 open-source licenses | ✅ | `YUNET_LICENSE="MIT"`, `SFACE_LICENSE="Apache-2.0"`; `tests/unit/test_ml_licenses.py` asserts OSI-approved |
| FR-005 detector face_count semantics | ✅ | `yunet_detector.py:117-136` maps YuNet rows → `DetectionResult`; integration test `test_detector_single_face/no_face/multi_face` |
| FR-006 same/different cosine separation | ✅ | integration tests `test_same_person_cosine_above_threshold` / `test_different_person_cosine_below_threshold` |
| FR-007 face_crop alignment pipeline | ✅ | `adapters/ml/face_crop.py` wraps `alignCrop`, raises `InvalidFaceBox` on zero/negative area; wired into `SFaceEmbedder.embed`; `tests/unit/test_face_crop.py` |
| FR-008 ModelDownloader + cache + atomic rename | ✅ | `model_downloader.py` — cache hit, `.part` atomic `os.replace`, stale `.part` treated as absent, single attempt configurable timeout; `tests/unit/test_model_downloader.py` |
| FR-009 fail-fast on unobtainable/corrupt model | ✅ | `ModelUnavailableError` on network/timeout; `ModelCorruptError` wrapping OpenCV load failure in both adapter `__init__`s |
| FR-010 docker-compose models bind mount | ✅ | `docker-compose.yml:36` `./models:/app/models:rw`; `Dockerfile:27` `mkdir -p /app/models` |
| FR-011 production wiring substitution | ✅ | `main.py:152-155` wires `YuNetDetector()`/`SFaceEmbedder()`, keeps `MockAgeEstimator`/`MockMoodEstimator`; `test_wiring_selector.py:236-240` |
| FR-012 mock mode backward compatible | ✅ | `test_wiring_selector.py:57-60` asserts mock instances; mock path unchanged |
| FR-013 domain layer isolation | ✅ | `tests/domain/test_domain_purity.py` forbids `cv2`/`onnxruntime`/`numpy`/`adapters.ml`; grep confirms no ML imports in `domain/` |
| FR-014 runtime deps + import isolation | ✅ | `pyproject.toml` declares `opencv-python-headless`, `onnxruntime`, `numpy`; imported only in `adapters/ml/` |
| FR-015 real-model integration suite (skippable) | ✅ | `tests/integration/test_real_ml_adapters.py` with `pytest.mark.requires_models` + autouse skip guard on model absence / non-production mode |
| FR-016 threshold calibration docs | ✅ | `quickstart.md` "Threshold Calibration" section + `contracts/adapter-port-conformance.md`; `PRODUCTION_VERIFICATION_THRESHOLD=0.363`; env-configurable |
| FR-017 no biometric data in logs | ✅ | adapters log structured JSON (`model_loaded`, `model_cache_hit`, etc.) — no image/vector/biometric payload |
| FR-018 mock adapters/ports/result-types/contracts unchanged | ✅ | `adapters/mock/` has no `cv2`/`onnxruntime`/`numpy`/`adapters.ml` imports; result-type shape assertions in unit tests confirm `DetectionResult`/`BoundingBox`/`Embedding` unchanged |
| FR-019 existing suites pass unchanged | ✅ | T036 verified; mock path intact |
| FR-020 scope boundaries respected | ✅ | no new endpoints/entities/ports/result-types; mood/age remain mock; no 1:N/liveness/training |

### Success criteria (all satisfied)

SC-001 through SC-017 — each maps to one or more satisfied FRs above (see mapping in spec.md). No gaps detected.

### Constitution principles checked (ratified v1.0.0)

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ | Lazy download + pre-download fallback; no retry/checksum hardening |
| III. Technology Stack (open-source ML) | ✅ | YuNet MIT + SFace Apache-2.0 (FR-004, `test_ml_licenses.py`); resolves OQ-4 |
| IV. Containerized Execution | ✅ | `models/` bind-mounted in `docker-compose.yml` (FR-010) |
| V. Local Filesystem Image Storage | ✅ | `usuarios/` untouched; only `models/` cache added |
| VI. PostgreSQL for Embeddings | ✅ | 128-dim matches mock — no schema migration |
| VII. Hexagonal / Ports-and-Adapters | ✅ | Adapters implement existing ports; domain purity enforced (FR-013); mocks retained verbatim (FR-018) |
| VIII. Explicit Non-Goals | ✅ | Load-test integrity only (no checksum), justified by Principle VIII |

No constitution MUST violations found.

## Summary Metrics

- **Requirements checked**: 20 FRs + 17 SCs = 37
- **Plan decisions checked**: project structure, wiring, deps, compose, calibration — all satisfied
- **Constitution principles checked**: 7 (I, III, IV, V, VI, VII, VIII) — all satisfied
- **Findings by gap type**: none
- **Findings by severity**: none
- **Actionable findings**: 0 → converged

## Recommendation

Converged — the implementation satisfies the spec, plan, tasks, and constitution. `tasks.md` was left byte-for-byte unchanged. Recommend proceeding to review / opening a PR.
