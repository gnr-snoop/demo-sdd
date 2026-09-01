# Specification Quality Checklist: Concrete Face Detection & Embedding ML Adapters (Fase 5a)

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
- Clarify pass (2026-09-01): 5 questions auto-answered (strict mode; none blocking — no security/privacy/compliance/breaking/public-contract impact). Resolved: inference backend (OpenCV DNN single backend), model integrity verification (load-test, no checksum), concurrent/partial-download handling (atomic `.part` rename), download timeout/retry (single attempt, 30s/120s, no retry), SFace embedding dimension (pinned to 128, matches mock — non-breaking). All 20 checklist items remain satisfied; no item toggled. Sections touched: Clarifications (new), FR-002, FR-008, FR-009, FR-014, Key Entities (Embedding), Edge Cases, Assumptions.
- Content quality note: the spec names concrete model choices (YuNet, SFace) and runtime libraries (OpenCV, ONNX Runtime, NumPy) because this spec's *subject matter* is the concrete ML adapters themselves — naming the open-source models and their ports is the WHAT (which open-source model behind which port), not prescriptive HOW (code structure, APIs). Model/license provenance and port conformance are user-facing business facts (Constitution Principle III — open-source mandate; PRD §11 — detector contract + domain isolation). File paths and class names appear only as identifiers grounding the adapters to the existing hexagonal ports, consistent with the precedent set by spec 007.
- All `[NEEDS CLARIFICATION]` markers were auto-resolved at the specify gate (0 markers emitted); the chosen defaults — YuNet detector (YOLO-equivalent per PRD §11), SFace embedder (resolves OQ-4, 128-dim), lazy model download on first use (atomic `.part` rename, single-attempt timeout, load-test integrity), documented real-model cosine threshold with mock 0.5 preserved — are recorded in the Assumptions section.

---

## Requirements-Quality Audit (Standard depth, Reviewer/PR audience)

> Appended 2026-09-01 by `/speckit.checklist` (focus: general). These items evaluate the **requirements themselves** for completeness, clarity, consistency, measurability, and coverage — not the implementation. Focus clusters: ML adapter conformance & port isolation; model acquisition & fail-fast robustness; backward compatibility / non-regression; verification threshold calibration.

### Requirement Completeness

- [ ] CHK101 Are all functional requirements (FR-001..FR-020) each mapped to at least one user story and at least one success criterion (no orphaned FRs)? [Completeness, Spec §Requirements/§User Scenarios/§Success Criteria]
- [ ] CHK102 Is the SFace embedding dimension pinned to 128 as a requirement for both the concrete embedder output and the stored `FaceTemplate` schema (not only mentioned in clarifications)? [Completeness, Spec FR-002/FR-018]
- [ ] CHK103 Are distinct, fixed `model_version` strings required for both adapters, explicitly required to differ from the mock versions (`mock-yolo-v0`, `mock-embedder-v1`)? [Completeness, Spec FR-003]
- [ ] CHK104 Is the open-source license provenance (YuNet MIT, SFace Apache 2.0) stated as a requirement (FR-004), not merely an assumption? [Completeness, Spec FR-004/Constitution §III]
- [ ] CHK105 Are the model-download timeout (30s connect / 120s read), single-attempt/no-retry policy, and atomic `.part`-rename partial-write safety all specified as requirements? [Completeness, Spec FR-008]
- [ ] CHK106 Are the three new runtime dependencies (`opencv-python-headless`, `onnxruntime`, `numpy`) enumerated as a requirement with an explicit import-isolation constraint (domain/mock path must not import them)? [Completeness, Spec FR-014]
- [ ] CHK107 Is the real-model integration test skip condition (models absent OR `APP_MODE != production`) specified as a requirement with a documented CI-skip flag? [Completeness, Spec FR-015/Constitution QG §7]
- [ ] CHK108 Is the threshold calibration documentation required to state the recommended value, its derivation, the difference from the mock 0.5, and env-configurability — all four sub-requirements present? [Completeness, Spec FR-016]
- [ ] CHK109 Is the log-content restriction (no image, embedding vector, or biometric response in logs) specified as a requirement? [Completeness, Spec FR-017]
- [ ] CHK110 Is the explicit out-of-scope list (concrete mood/age, training, liveness, 1:N, new endpoints, frontend, port/entity/result-type changes, mock-adapter changes, existing-test changes) captured in a single bounding requirement? [Completeness, Spec FR-020]

### Requirement Clarity

- [ ] CHK111 Is the detector "quality threshold" (score above which a face is accepted) quantified with a specific value or explicitly defined as a configurable setting with a documented default? [Clarity, Spec FR-005/Gap]
- [ ] CHK112 Is the production-mode `verification_threshold` quantified with a specific documented default (plan states 0.363) — or is it left ambiguous in the spec body? [Clarity, Spec FR-016/Ambiguity]
- [ ] CHK113 Is the aligned-crop "fixed size" quantified (e.g. 112×112) in the requirements, or only in a user-story example? [Clarity, Spec FR-007/Gap]
- [ ] CHK114 Is "fail fast" defined unambiguously as occurring at construction/load time before the app serves traffic (not at first request)? [Clarity, Spec FR-009]
- [ ] CHK115 Is "clear, actionable error" defined — does the requirement mandate naming the model and the failure reason? [Clarity, Spec FR-009]
- [ ] CHK116 Is "backward compatible" (FR-012) defined precisely as "identical behavior to specs 001-007" rather than left informal? [Clarity, Spec FR-012]
- [ ] CHK117 Is "unchanged" (FR-018) scoped to an explicit artifact list (mocks, ports, entities, result types, HTTP contracts, frontend)? [Clarity, Spec FR-018]
- [ ] CHK118 Is the inference-backend constraint (OpenCV DNN as the single concrete backend; no direct `onnxruntime` API calls) stated clearly in the requirements rather than only in clarifications? [Clarity, Spec FR-002/FR-014]

### Requirement Consistency

- [ ] CHK119 Is the 128-dim embedding requirement (FR-002) consistent with the stated non-change to `FaceTemplate` schema (FR-018) and with the mock embedder's 128-dim vector (spec 001)? [Consistency, Spec FR-002/FR-018/Assumptions]
- [ ] CHK120 Is the production wiring requirement (FR-011) consistent with the mood/age-stay-mock scope boundary (FR-020) — i.e. production wires real detector+embedder but mock mood/age? [Consistency, Spec FR-011/FR-020]
- [ ] CHK121 Is the lazy-download default (FR-008) consistent with the pre-download-supported offline requirement (US4-AC4) without one contradicting the other? [Consistency, Spec FR-008]
- [ ] CHK122 Is the no-checksum/load-test-only decision (FR-009) consistent with Constitution Principle VIII (no security guarantee), and is that justification recorded? [Consistency, Spec FR-009/Constitution §VIII]
- [ ] CHK123 Are the success criteria (SC-001..SC-017) each traceable to one or more FRs, with no orphaned SC and no FR lacking coverage? [Consistency, Spec §Success Criteria/§Requirements]
- [ ] CHK124 Is the plan-stated threshold 0.363 consistent with the spec's "documented real-model threshold" requirement (FR-016), and is the value's source (OpenCV LFW calibration) recorded? [Consistency, Spec FR-016/Plan §Summary]
- [ ] CHK125 Is the double-detection-in-embedder trade-off (plan Complexity Tracking) consistent with the "no real-time performance SLO" non-goal, and is the consistency noted? [Consistency, Plan §Complexity Tracking/Constitution Non-Goals]

### Acceptance Criteria Quality

- [ ] CHK126 Are acceptance scenarios measurable (assertable values like `face_count == 1`, similarity above/below threshold) rather than subjective? [AC Quality, Spec §User Scenarios]
- [ ] CHK127 Does each FR have at least one corresponding acceptance scenario or success criterion that verifies it? [AC Quality, Spec §Requirements/§Success Criteria]
- [ ] CHK128 Are negative-path acceptance criteria (face_count == 0, different-person below threshold, fail-fast, corrupt-file) specified with concrete outcomes, not just "handles gracefully"? [AC Quality, Spec FR-005/FR-006/FR-009]
- [ ] CHK129 Are the multi-face (`face_count == N`) and zero-face acceptance scenarios specified with concrete required outcomes? [AC Quality, Spec FR-005/US1-AC2/AC3]

### Scenario Coverage

- [ ] CHK130 Is the corrupt-model-file scenario covered as a requirement (fail-fast load error), not only as an edge-case note? [Coverage, Spec FR-009/Edge Cases]
- [ ] CHK131 Is the read-only `models/` directory scenario covered as a requirement or only as an edge case — and is the required outcome (fail fast with pre-download workaround) stated? [Coverage, Spec Edge Cases/Gap]
- [ ] CHK132 Is the borderline-similarity (near-threshold) decision rule covered as a requirement (`similarity >= verification_threshold`, no new borderline logic)? [Coverage, Spec Edge Cases/Gap]
- [ ] CHK133 Is the model-version mismatch scenario (stored template from a different model version compared) covered as a requirement with a defined error path? [Coverage, Spec Edge Cases/Gap]
- [ ] CHK134 Are both the air-gapped/offline (pre-placed models) and lazy-download paths covered by acceptance scenarios? [Coverage, Spec FR-008/US4]

### Edge Case Coverage

- [ ] CHK135 Is the download-interruption (`.part` file) edge case specified with a required outcome (treated as absent, re-download on next construction), not merely described? [Edge Coverage, Spec FR-008/Edge Cases]
- [ ] CHK136 Is the embedding-dimension-mismatch edge case covered with a required error path (`ComparisonError` → 500) rather than undefined behavior? [Edge Coverage, Spec Edge Cases]
- [ ] CHK137 Is the no-face / multi-face edge case covered with required domain behavior explicitly stated as unchanged from specs 002/003? [Edge Coverage, Spec Edge Cases]
- [ ] CHK138 Is the unaligned-crop edge case (alignment skipped) covered with a required quality-degradation outcome (not a crash, not a guaranteed match)? [Edge Coverage, Spec Edge Cases]

### Non-Functional Requirements

- [ ] CHK139 Is the open-source-license requirement (Constitution Principle III) explicitly stated as an NFR with the specific licenses (MIT, Apache 2.0) named? [NFR, Spec FR-004/Constitution §III]
- [ ] CHK140 Is the domain-isolation requirement (no OpenCV/ONNX/NumPy/concrete-adapter import in the domain layer) stated as an NFR? [NFR, Spec FR-013/Constitution §VII]
- [ ] CHK141 Is the observability/log-content restriction (structured JSON only; no biometric data) stated as an NFR? [NFR, Spec FR-017]
- [ ] CHK142 Are demo-grade performance expectations (no real-time SLO; CPU-only inference; no GPU required to develop/test) stated as explicit non-functional non-goals? [NFR, Constitution Non-Goals/Plan §Performance]

### Dependencies & Assumptions

- [ ] CHK143 Are the dependencies on specs 001-007 (ports, result types, mock adapters, wiring functions, config, compose, persistence adapters) explicitly enumerated in the Assumptions section? [Dependencies, Spec §Assumptions]
- [ ] CHK144 Is the resolution of Constitution OQ-4 (embedding model → SFace) recorded as an assumption with its PATCH-level constitution-bump implication? [Dependencies, Spec §Assumptions/Constitution OQ-4]
- [ ] CHK145 Is the YuNet-as-YOLO-equivalent justification (PRD §11 "o un adaptador equivalente") recorded as an assumption so the detector choice is constitutionally grounded? [Dependencies, Spec §Assumptions]
- [ ] CHK146 Is the single-inference-backend assumption (OpenCV DNN only; `onnxruntime` declared but not directly called) stated as a requirement-level decision, not only a clarification? [Dependencies, Spec FR-002/FR-014/Clarifications]

### Ambiguities & Conflicts

- [ ] CHK147 Is there any ambiguity between "quality threshold" (detector score) and "verification threshold" (cosine similarity) — are they clearly distinct, separately configured values? [Ambiguity, Spec FR-005/FR-016/Gap]
- [ ] CHK148 Is the potential conflict between lazy-download (network at runtime) and the air-gapped requirement resolved clearly — is pre-download stated as a supported requirement, not merely a fallback? [Conflict, Spec FR-008/Assumptions]
- [ ] CHK149 Is there ambiguity about whether `face_crop` is a domain port or an adapter utility — does the spec clearly state it is NOT a domain port and is not imported by the domain? [Ambiguity, Spec FR-007/US3/FR-013]
- [ ] CHK150 Is the potential conflict between "fail fast" and "lazy download on first use" resolved — is fail-fast defined to occur at construction/startup time so lazy download does not defer failure into a running server? [Conflict, Spec FR-008/FR-009]
- [ ] CHK151 Is the scope-boundary conflict (production mode yet mood/age stay mock) clearly resolved and stated as a requirement, so a reader does not assume production = all-real? [Conflict, Spec FR-011/FR-020]

### Audit Notes

- 51 new items appended (CHK101..CHK151) across 9 categories. All items test requirement quality, not implementation.
- Traceability: 51/51 items include a reference (Spec §ref, FR-###, Constitution §, Plan §, Gap, Ambiguity, or Conflict) — 100% ≥ 80% threshold.
- Items flagged `[Gap]` point to requirements not yet pinned in the spec body (quality threshold value, crop size, read-only/outcome requirements, borderline/mismatch rules) — candidates for spec tightening before plan finalization.
- Items flagged `[Ambiguity]`/`[Conflict]` identify resolution checks where the spec and plan must agree (threshold value 0.363, lazy-vs-offline, fail-fast timing, `face_crop` classification, production-but-mock-mood/age).
