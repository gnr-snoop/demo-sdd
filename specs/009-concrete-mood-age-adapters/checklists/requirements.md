# Specification Quality Checklist: Concrete Mood & Age Estimation ML Adapters (Fase 5b)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-01
**Feature**: [spec.md](../spec.md)

## Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness
- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes
- Items marked incomplete require spec updates before clarify or plan
- Validation pass: 20/20 items satisfied on 2026-09-01.
- All `[NEEDS CLARIFICATION]` markers were auto-resolved at the specify gate (0 markers emitted); the chosen defaults — EmotiEff/HSEmotion mood model (ONNX Runtime, Apache 2.0, 8 AFEW → PRD label mapping with `Anger→enojo` and no-conclusive fallback for Disgust/Fear/Contempt), MiVOLO face-only age model (PyTorch CPU + timm, Apache 2.0 code + checkpoint license verified at plan time), shared face_crop reuse from spec 008 (double-detection pattern), ModelDownloader reuse from spec 008 (same cache/atomic-rename/load-test), mood_confidence_threshold new setting (default 0.5, low-certainty → "no concluyente"), age point-only → domain derives range (reusing spec 005 normalization), new deps torch CPU + timm + hsemotion-onnx isolated to adapters — are recorded in the Assumptions section.
- Content quality note: the spec names concrete model choices (EmotiEff/HSEmotion, MiVOLO) and runtime libraries (ONNX Runtime, PyTorch, timm) because this spec's *subject matter* is the concrete ML adapters themselves — naming the open-source models and their ports is the WHAT (which open-source model behind which port), not prescriptive HOW (code structure, APIs). Model/license provenance, the AFEW→PRD label mapping, and port conformance are user-facing business facts (Constitution Principle III — open-source mandate; PRD §11 — model version + domain isolation; PRD §6.4 — mood/age result contracts). File paths and class names appear only as identifiers grounding the adapters to the existing hexagonal ports, consistent with the precedent set by specs 007 and 008.

---

## Requirement-Quality Audit (dimension-based)

> Appended by `/speckit.checklist` (focus: general, depth: Standard, audience: PR Reviewer).
> Each item tests the *requirements* for completeness/clarity/consistency/measurability/coverage — not the implementation. Items marked `[Gap]` / `[Ambiguity]` / `[Assumption]` indicate a requirement-quality question to resolve or explicitly accept before implementation.

### Requirement Completeness

- [ ] CHK001 Is the *recommended* `mood_confidence_threshold` value for EmotiEff/HSEmotion specified in the spec, or only the default 0.5 with the recommended value deferred to calibration docs? [Completeness, Spec §FR-015 / Gap]
- [ ] CHK002 Is the MiVOLO model's "typical error margin" quantified with a numeric value in the spec, or only required to be documented? [Completeness, Spec §FR-015 / Gap]
- [ ] CHK003 Are the model download URLs and exact pinned filenames specified at the spec level, or deferred to plan-time adapter constants? [Completeness, Spec §FR-009 / Assumptions]
- [ ] CHK004 Is the exact `model_version` string for each adapter pinned, or only exemplified with "e.g." (`emotieff-enet-b0-afew-v1`, `mivolo-volo-d1-face-v1`)? [Completeness, Spec §FR-003 / Ambiguity]
- [ ] CHK005 Are the model input dimensions (crop size) for EmotiEff and MiVOLO specified to confirm `face_crop` output compatibility with both models? [Completeness, Spec §FR-008 / Gap]
- [ ] CHK006 Is the behavior specified when the mood model would return `null` confidence, given `MoodResult.confidence` is typed `float | None`? [Completeness, Spec §FR-001 / Gap]
- [ ] CHK007 Are the exact `torch` / `timm` / `hsemotion-onnx` dependency versions or version constraints pinned, or left unpinned? [Completeness, Spec §FR-013 / Gap]

### Requirement Clarity

- [ ] CHK008 Is "plausible estimated age" (User Story 2) quantified with an acceptable range or bound, or left qualitative? [Clarity, Spec §User Story 2 / Ambiguity]
- [ ] CHK009 Is "clear, actionable error" defined with a consistent error-shape contract across all failure modes (network failure, corrupt file, unwritable cache)? [Clarity, Spec §FR-009 / Gap]
- [ ] CHK010 Is the rounding mode for converting the MiVOLO float age to an integer specified (round / floor / int truncation)? [Clarity, Spec §FR-002 / Ambiguity]
- [ ] CHK011 Is the `mood_confidence_threshold` comparison operator specified — strictly "below" (<) vs ≤ at exactly the threshold? [Clarity, Spec §FR-006 / Ambiguity]
- [ ] CHK012 Is "inference accuracy degrades" (unaligned-crop edge case) quantified, or only qualitative? [Clarity, Spec §Edge Cases / Gap]

### Requirement Consistency

- [ ] CHK013 Is the confidence value returned for an unmapped AFEW class (Anger/Disgust/Fear/Contempt with high probability) specified — does it carry the model's top-1 probability or is it forced to null/low? [Consistency, Spec §FR-005 vs FR-006 / Ambiguity]
- [ ] CHK014 Does the "no upper bound enforced" age edge case (100+) conflict with any PRD §6.4 age-range expectation? [Consistency, Spec §Edge Cases vs PRD §6.4 / Gap]
- [ ] CHK015 Are FR-001's "confidence in [0, 1] or null" and User Story 1 Scenario 1's "confidence in [0, 1]" (no null) consistent? [Consistency, Spec §FR-001 vs User Story 1 / Ambiguity]
- [ ] CHK016 Is the double-detection performance cost (detect twice per mood/age analysis) consistently acknowledged across FR-008, the plan Complexity Tracking table, and the Performance Goals? [Consistency, Spec §FR-008 vs plan §Complexity / Gap]
- [ ] CHK017 Is the `hsemotion-onnx` vs `emotiefflib[onnx]` alternative resolved to a single choice, or carried as an unresolved either/or across FR-013 and Assumptions? [Consistency, Spec §FR-013 / Ambiguity]

### Acceptance Criteria Quality

- [ ] CHK018 Does any acceptance scenario cover the mood confidence value exactly equal to the threshold boundary? [Acceptance Quality, Spec §User Story 1 / Gap]
- [ ] CHK019 Is there an acceptance scenario for the age estimate == 0 (baby) boundary exercising the `min >= 0` clamp? [Acceptance Quality, Spec §Edge Cases / Gap]
- [ ] CHK020 Are the calibration-doc acceptance scenarios (User Story 7) measurable beyond "when reviewed, then it states" — e.g., asserting specific numeric threshold values? [Acceptance Quality, Spec §User Story 7 / Gap]
- [ ] CHK021 Is there an acceptance criterion asserting the mock `model_version` strings remain distinct from the concrete ones as a checked invariant, not just that concrete ones are "distinct"? [Acceptance Quality, Spec §FR-003 / Gap]

### Scenario Coverage

- [ ] CHK022 Is there a happy-path acceptance scenario per AFEW class that maps to a PRD label (Neutral/Happy/Sad/Surprise), not just a generic single-face case? [Scenario Coverage, Spec §User Story 1 Scenario 1 / Gap]
- [ ] CHK023 Is there a scenario for undecodable/corrupt image bytes input (distinct from a valid no-face image)? [Scenario Coverage, Spec §Edge Cases / Gap]
- [ ] CHK024 Is there a scenario for a face detected at the image boundary producing a degenerate/empty crop? [Scenario Coverage, Spec §FR-008 / Gap]
- [ ] CHK025 Is there a scenario for concurrent mood/age analyses exercising model-session thread-safety? [Scenario Coverage, Gap]
- [ ] CHK026 Is the air-gapped pre-download path covered by an acceptance scenario (Story 4 scenario 4 is stated — is it testable)? [Scenario Coverage, Spec §User Story 4 / Gap]

### Edge Case Coverage

- [ ] CHK027 Is the case of a partial/interrupted runtime load (distinct from file download interruption) covered? [Edge Coverage, Spec §Edge Cases / Gap]
- [ ] CHK028 Is the case of the `models/` cache directory being absent (not just read-only) covered? [Edge Coverage, Spec §Edge Cases / Gap]
- [ ] CHK029 Is the case of the mood model returning an unexpected/extra class beyond the 8 AFEW classes covered? [Edge Coverage, Spec §FR-005 / Gap]
- [ ] CHK030 Is the case of ONNX Runtime and PyTorch version/dependency conflict within a single process covered? [Edge Coverage, Spec §FR-013 / Gap]
- [ ] CHK031 Is the case of the MiVOLO checkpoint license being found incompatible at plan time covered with a concrete fallback adapter, or only stated abstractly? [Edge Coverage, Spec §Assumptions / Ambiguity]

### Non-Functional Requirements

- [ ] CHK032 Is the memory footprint of loading both ONNX Runtime and PyTorch (torch CPU) in one process specified or bounded? [NFR, Spec §FR-013 / Gap]
- [ ] CHK033 Is the cold-start time impact of loading two model files + two runtimes specified? [NFR, Spec §plan §Performance Goals / Gap]
- [ ] CHK034 Is the integrity verification mechanism for downloaded model files specified (checksum/hash), or only "load-test"? [NFR, Spec §FR-009 / Gap]
- [ ] CHK035 Is the transport security for model download (HTTPS vs HTTP) specified? [NFR, Spec §FR-009 / Gap]

### Dependencies & Assumptions

- [ ] CHK036 Is the MiVOLO checkpoint license verification tracked as an open assumption with a documented fallback path, or treated as already resolved? [Dependencies, Spec §Assumptions / Ambiguity]
- [ ] CHK037 Does the spec state compatibility of the chosen torch CPU build with the target Linux container platform? [Dependencies, Spec §FR-013 / Gap]
- [ ] CHK038 Is the assumption that the existing domain purity test can be extended (not redesigned) to cover the new imports stated? [Dependencies, Spec §FR-012 / Assumptions]
- [ ] CHK039 Is the assumption that `age_range_half_width_years` default (5) is appropriate for MiVOLO's error margin stated, or deferred to docs? [Dependencies, Spec §FR-007 / Gap]

### Ambiguities & Conflicts

- [ ] CHK040 Are the two "no concluyente" paths (low-confidence gate vs unmapped-class mapping) distinguished in their returned confidence value? [Ambiguity, Spec §FR-005 vs FR-006 / Ambiguity]
- [ ] CHK041 Is the exact MiVOLO checkpoint file pinned (filename + source), or only described by backbone (volo_d1 face-only)? [Ambiguity, Spec §Assumptions / Ambiguity]
- [ ] CHK042 Is the `hsemotion-onnx` vs `emotiefflib[onnx]` dependency choice disambiguated, or carried as an unresolved alternative? [Ambiguity, Spec §FR-013 / Ambiguity]

## Notes (audit)

- 42 new requirement-quality items appended (CHK001–CHK042) across 9 dimensions.
- Traceability: 42/42 items (100%) carry a `[Spec §ref]` and/or `[Gap]`/`[Ambiguity]`/`[Assumption]` tag.
- Recurring themes: (a) values deferred to "plan-time" or "calibration docs" rather than specified (CHK001–CHK005, CHK039); (b) boundary/edge semantics left implicit — threshold equality (CHK011), null confidence (CHK006/CHK013/CHK040), age==0 (CHK019), unmapped-extra class (CHK029); (c) unresolved either/or alternatives (CHK017/CHK042); (d) NFRs (memory, cold-start, integrity, transport) unspecified — acceptable under Constitution Explicit Non-Goals but worth explicit acceptance.
- No items test implementation behavior; all items test requirement quality (completeness, clarity, consistency, measurability, coverage).
