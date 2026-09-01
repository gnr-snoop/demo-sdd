# Convergence Report — Cycle 1

**Feature Dir**: `specs/009-concrete-mood-age-adapters`
**Date**: 2026-09-01
**Cycle**: 1
**Artifacts Evaluated**: spec.md, plan.md, tasks.md, constitution.md
**Mode**: strict

## Findings

| ID | Gap Type | Severity | Source | Evidence | Remaining Work |
|----|----------|----------|--------|----------|----------------|
| F-001 | contradicts | MEDIUM | FR-015 / SC-013 | `quickstart.md` Scenario 5 "AFEW → PRD label mapping" table states index 0=Neutral→neutral, 1=Happy→feliz, 2=Sad→triste, 3=Surprise→sorprendido, 4-7=Anger/Disgust/Fear/Contempt→no concluyente. This contradicts the verified implementation in `backend/src/face_insight/adapters/ml/constants.py` (`AFEW_INDEX_TO_EMOTION_NAME` + `AFEW_TO_PRD_LABEL_MAP`), which maps 0=Anger, 1=Contempt, 2=Disgust, 3=Fear, 4=Happiness, 5=Neutral, 6=Sadness, 7=Surprise (the HSEmotion-onnx library's `idx_to_class` ordering for `enet_b0_8_best_afew`). The correct mapping is asserted by `test_emotieff_mood_mapping.py::test_afew_map_emotion_to_prd_semantics` and `test_real_ml_adapters.py::test_afew_index_order_matches_library`. The `contracts/adapter-port-conformance.md` states the semantic mapping correctly (without indices); only the `quickstart.md` Scenario 5 indexed table is wrong. | Correct the `quickstart.md` Scenario 5 table to match `AFEW_INDEX_TO_EMOTION_NAME` / `AFEW_TO_PRD_LABEL_MAP` in `constants.py`: 0=Anger→no concluyente, 1=Contempt→no concluyente, 2=Disgust→no concluyente, 3=Fear→no concluyente, 4=Happiness→feliz, 5=Neutral→neutral, 6=Sadness→triste, 7=Surprise→sorprendido. |

## Summary Metrics

- **Requirements checked**: 20 (FR-001..FR-020)
- **Success criteria checked**: 18 (SC-001..SC-018)
- **Plan decisions checked**: Constitution Check table, Project Structure touch-points, Complexity Tracking
- **Constitution principles checked**: I–VIII (all PASS — no violations)
- **Findings by gap type**: contradicts = 1
- **Findings by severity**: MEDIUM = 1
- **Blocking findings** (CRITICAL/HIGH in strict mode): 0

## Assessment

The implementation satisfies all 20 functional requirements and 18 success criteria in runtime behavior. All 41 existing tasks (T001–T041) are complete and verified against the codebase:

- ✅ `EmotiEffMoodEstimator` (`adapters/ml/emotieff_mood.py`) implements `MoodEstimator`, ONNX Runtime, AFEW→PRD mapping, low-confidence override, face_crop alignment, ModelDownloader reuse, fail-fast errors, structured logs (FR-001/FR-005/FR-006/FR-008/FR-009/FR-016/FR-020).
- ✅ `MiVOLOAgeEstimator` (`adapters/ml/mivolo_age.py`) implements `AgeEstimator`, PyTorch CPU + timm, point-only `AgeResult(range=None)`, face_crop alignment, ModelDownloader reuse, fail-fast errors (FR-002/FR-007/FR-008/FR-009/FR-020).
- ✅ Constants (`constants.py`): model versions, licenses, AFEW mapping, `resolve_mood_label` (FR-003/FR-004/FR-005).
- ✅ Config (`config.py`): `mood_confidence_threshold` field + clamp validator (FR-006).
- ✅ Wiring (`main.py`): `wire_production_adapters` wires `EmotiEffMoodEstimator` + `MiVOLOAgeEstimator`; mock wiring unchanged (FR-010/FR-011).
- ✅ Deps (`pyproject.toml`): `torch`, `timm`, `hsemotion-onnx` added; `requires_models` marker registered (FR-013/FR-014).
- ✅ Domain purity test extended with `timm`/`hsemotion`/`emotiefflib`/`mivolo` (FR-012).
- ✅ Unit tests: port conformance, AFEW mapping, low-confidence override, alignment reuse, licenses, wiring selector (FR-001..FR-014).
- ✅ Integration tests: real-model mood/age tests with `requires_models`/`APP_MODE` skip guard (FR-014).
- ✅ Calibration docs: `contracts/adapter-port-conformance.md` and `contracts/model-download.md` correct and complete (FR-015).
- ✅ Constitution Principles I–VIII: all PASS (no violations).

The single finding (F-001) is a documentation defect in `quickstart.md` Scenario 5 where the indexed AFEW→PRD mapping table contradicts the verified implementation. It is MEDIUM severity (documentation only, no runtime impact; the authoritative `contracts/adapter-port-conformance.md` is correct) and **not blocking** in strict mode.
