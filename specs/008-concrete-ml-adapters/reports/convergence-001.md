# Convergence Report — Cycle 1

**Feature Dir**: `specs/008-concrete-ml-adapters`
**Date**: 2026-09-01
**Cycle**: 1
**Artifacts Evaluated**: `spec.md`, `plan.md`, `tasks.md` (no constitution file present — constitution checks skipped gracefully)

## Findings

| ID | Gap Type | Severity | Source | Evidence | Remaining Work |
|----|----------|----------|--------|----------|----------------|
| F-001 | contradicts | HIGH | FR-008 (AC-2/AC-4), SC-008, SC-012, FR-015, quickstart.md (Scenarios 2/3 + Offline section) | `ModelDownloader.ensure()` (`backend/src/face_insight/adapters/ml/model_downloader.py:53`) computes `final_path = self._cache_dir / f"{model_name}.onnx"`, but callers pass `YUNET_MODEL_FILENAME`/`SFACE_MODEL_FILENAME` which already include the `.onnx` extension (`constants.py:11-12`). This produces cache files named `face_detection_yunet_2023mar.onnx.onnx` / `face_recognition_sface_2021dec.onnx.onnx` instead of the documented `*.onnx`. Consequences: (1) **FR-008 AC-4 broken** — a pre-placed `models/face_detection_yunet_2023mar.onnx` (per quickstart offline workflow) is NOT detected as a cache hit → re-download → network required, contradicting the air-gapped guarantee. (2) **SC-008 / quickstart Scenario 2** — the documented cache filename `models/face_detection_yunet_2023mar.onnx` never materializes; `.onnx.onnx` does. (3) **SC-012 / FR-015** — `tests/integration/test_real_ml_adapters.py::_models_available()` checks `models_dir / YUNET_MODEL_FILENAME` (`.onnx`), but the downloader writes `.onnx.onnx`; after a lazy download `_models_available()` returns False → the real-model integration suite skips even when models are present, making the "models present → tests pass" condition unreachable. (4) The unit test `tests/unit/test_model_downloader.py` misses the defect because it uses `model_name = "test_model"` (no extension), so `test_model.onnx` is coincidentally correct. | Fix `ModelDownloader.ensure()` to treat `model_name` as the complete filename (it already carries `.onnx`): `final_path = self._cache_dir / model_name`, `part_path = self._cache_dir / f"{model_name}.part"`. Add a regression unit test in `test_model_downloader.py` that uses the real `YUNET_MODEL_FILENAME` (which ends in `.onnx`) to assert the cached path is `models/face_detection_yunet_2023mar.onnx` (no double extension) and that a pre-placed file of that name is a cache hit. |

## Summary Metrics

- **Requirements checked**: 20 FRs + 17 SCs = 37
- **Plan decisions checked**: project structure, wiring, deps, compose, calibration — all satisfied
- **Constitution principles checked**: 0 (no constitution file present)
- **Findings by gap type**: `contradicts` = 1
- **Findings by severity**: HIGH = 1
- **Actionable findings**: 1 → tasks appended

## Recommendation

Run `speckit-implement` to complete the appended convergence task (Phase 12, T042), then re-run convergence to confirm a clean pass.
