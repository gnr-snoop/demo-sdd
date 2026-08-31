# Requirements-Quality Checklist: Onboarding Flow (Fase 2)

**Purpose**: "Unit Tests for English" — validate the *requirements* (not the implementation) for completeness, clarity, consistency, measurability, and coverage.
**Created**: 2026-08-31
**Feature**: [spec.md](../spec.md) | **Focus**: general | **Depth**: Standard | **Audience**: Reviewer (PR)
**Supplements**: [requirements.md](./requirements.md) (content-quality/readiness gate)

> Each item probes a requirement-quality dimension. `[Spec §ref]` points to the spec section under scrutiny; `[Gap]` / `[Ambiguity]` / `[Conflict]` mark newly surfaced issues. Items do NOT test implementation behavior.

## Requirement Completeness

- [ ] CHK001 Are the accepted image formats enumerated as a requirement (e.g. JPEG-only vs JPEG+PNG), rather than the vague "accepted image formats" / "supported image format" phrasing? [Clarity, Spec §FR-010 / Assumptions §image-constraints]
- [ ] CHK002 Is there a functional requirement that states the captured image is *retained* after onboarding (FR-009 only says "stored"; retention is only an Assumption)? [Completeness, Spec §FR-009 vs Assumptions §retention]
- [ ] CHK003 Is there a functional requirement encoding the observability/logging behavior (duration, type, status), or is it only an Assumption with no FR backing? [Completeness, Spec §Assumptions §observability]
- [ ] CHK004 Is the embedding vector dimensionality/shape specified as part of the FaceTemplate requirement, given downstream login (spec 003) must compare vectors? [Completeness, Spec §FR-006 / Key Entities §FaceTemplate]
- [ ] CHK005 Is the order of side-effects (DB write vs filesystem write) specified at the requirement level so that orphan-image vs orphan-profile semantics are defined? [Completeness, Spec §FR-008 / FR-009 / Edge Cases §filesystem-write-failure]
- [ ] CHK006 Is there a requirement covering consent persistence/audit, or is consent only validated-then-discarded? (FR-003 requires it but says nothing about storage.) [Completeness, Spec §FR-003]
- [ ] CHK007 Is a maximum total identifier length (covering long email local-parts) specified, or only the 3–32 char username sub-pattern? [Completeness, Spec §FR-002 / Clarifications §identifier-format]
- [ ] CHK008 Are the stable machine error codes enumerated in a functional requirement, or only in the Clarifications/plan (FR-014/FR-016 reference "actionable messages" without the code list)? [Completeness, Spec §FR-014 / FR-016 vs Clarifications §error-shape]

## Requirement Clarity

- [ ] CHK009 Is "insufficient quality" quantified with a defined score domain (e.g. [0.0, 1.0]) rather than only "below a configurable threshold"? [Measurability, Spec §FR-004 / Clarifications §quality]
- [ ] CHK010 Is "actionable" (FR-014) quantified — e.g. "states a possible next action" — in the requirement itself rather than only in SC-006? [Measurability, Spec §FR-014 vs SC-006]
- [ ] CHK011 Is "keyboard-accessible and have descriptive names" (FR-015) given a measurable criterion (e.g. WCAG 2.1 AA, tab-reachability, accessible-name) rather than left unquantified? [Measurability, Spec §FR-015]
- [ ] CHK012 Is "a single atomic unit of work" (FR-008) defined for the cross-resource case (DB + filesystem), given filesystem writes are not transactional with PostgreSQL? [Clarity, Spec §FR-008 / FR-009]
- [ ] CHK013 Is "the same attempt" (FR-013, "no concurrent onboarding requests for the same attempt") defined — per page-load, per identifier, per session? [Clarity, Spec §FR-013]
- [ ] CHK014 Is the success-response body specified as an exact field set ("exactly userId, identifier, status") or only "containing" (which permits extra fields)? [Clarity, Spec §FR-007]
- [ ] CHK015 Is the username pattern's treatment of leading/trailing/consecutive special chars (`.`, `_`, `-`) specified, or only the character class? [Clarity, Spec §FR-002 / Clarifications §identifier-format]
- [ ] CHK016 Is aspect-ratio preservation required during the long-edge resize (FR-010), or may the resize distort the image? [Clarity, Spec §FR-010]

## Requirement Consistency

- [ ] CHK017 Are the error machine codes consistent between the Clarifications/plan pin and the FR-014/FR-016 enumeration (the codes appear only in Clarifications, not in the FRs)? [Consistency, Spec §FR-014 / FR-016 vs Clarifications §error-shape]
- [ ] CHK018 Is FR-016 ("distinguish only the recoverable cause") consistent with the `internal_error` code from the pinned error shape, given internal errors are not user-recoverable? [Consistency, Spec §FR-016 vs Clarifications §error-shape]
- [ ] CHK019 Is FR-002's "without revealing stored biometric data" consistent with FR-016's non-revelation rule, and does the `identifier_taken` message create a user-enumeration side effect that the spec acknowledges? [Consistency, Spec §FR-002 / FR-016]
- [ ] CHK020 Is the "client-error status" used across SC-002/SC-003/SC-004 and the acceptance scenarios consistent in code (400 vs 409 vs 422), or is it left undefined at the requirement level? [Consistency, Spec §SC-002 / SC-003 / SC-004 / User Stories 2–3]
- [ ] CHK021 Is the all-or-nothing rollback (FR-008) consistent with the filesystem-write-failure edge case (DB rollback on fs failure) and the DB-unreachable edge case (no partial commit) — i.e. is the rollback direction symmetric and complete? [Consistency, Spec §FR-008 / Edge Cases §db-unreachable / §fs-write-failure]
- [ ] CHK022 Is `User.status = "enrolled"` (Clarifications gate + FR-007) consistent with the Key Entities `status ∈ {"enrolled", "active", "disabled"}` enumeration, and is "enrolled" vs "active" distinguished for this spec? [Consistency, Spec §FR-007 / Key Entities §User]

## Acceptance Criteria Quality

- [ ] CHK023 Does each User Story's Independent Test assert *no persistence* on rejection, and is that assertion present in the Acceptance Scenarios (not only the Independent Test)? [Measurability, Spec §User Stories 2–3]
- [ ] CHK024 Are acceptance scenarios measurable without referencing implementation (e.g. "the database is inspected" — is the observable state criterion clear)? [Measurability, Spec §User Story 1 §scenarios 2–3]
- [ ] CHK025 Does User Story 4 (frontend state machine) have an acceptance scenario for every PRD §6.2 state, or only a subset (the 7 scenarios map 1:1 to states but transitions like procesando→error recuperable are implicit)? [Coverage, Spec §FR-011 / User Story 4]
- [ ] CHK026 Is there an acceptance criterion that invalid state transitions are prevented (state-machine correctness), not only that valid transitions occur? [Measurability, Spec §FR-011]
- [ ] CHK027 Does User Story 6's contract-test acceptance scenario (scenario 4) specify *which* contract violation triggers failure, or only "a contract-violating change"? [Measurability, Spec §User Story 6 §scenario 4]

## Scenario Coverage

- [ ] CHK028 Are boundary values of the username pattern (exactly 3 chars, exactly 32 chars, 33 chars) covered by a scenario or edge case? [Coverage, Spec §FR-002]
- [ ] CHK029 Is the email-format branch of the identifier (vs username branch) explicitly covered in a scenario, or only the merged "email-or-username" statement? [Coverage, Spec §FR-002 / Clarifications §identifier-format]
- [ ] CHK030 Is the concurrent-duplicate race covered as an acceptance scenario (not only an Edge Case bullet), given FR-002 and the DB-unique-constraint decision? [Coverage, Spec §Edge Cases §concurrent-duplicate vs FR-002]
- [ ] CHK031 Is the embedder-port-failure-after-successful-detection path covered by an acceptance scenario, not only an Edge Case bullet? [Coverage, Spec §Edge Cases §embedder-failure vs FR-008]
- [ ] CHK032 Is the "image field missing entirely" edge case promoted to an acceptance scenario, or only an Edge Case bullet? [Coverage, Spec §Edge Cases §missing-image]
- [ ] CHK033 Are non-boolean consent values (e.g. string `"true"`) covered by a scenario, not only an Edge Case bullet? [Coverage, Spec §Edge Cases §non-boolean-consent vs FR-003]
- [ ] CHK034 Is the rotated/mirrored image case (accepted as-is) covered by a scenario, not only an Edge Case bullet? [Coverage, Spec §Edge Cases §rotated-image]

## Edge Case Coverage

- [ ] CHK035 Is there an edge case for the filesystem write succeeding but the DB commit failing afterward (orphan image), given the non-transactional fs? [Gap, Spec §FR-008 / FR-009]
- [ ] CHK036 Is there an edge case for the detector returning a face count but no score (or score outside the assumed domain)? [Gap, Spec §FR-004 / FR-005]
- [ ] CHK037 Is there an edge case for the image meeting the long-edge limit but exceeding the max *byte size* after resize (or vice versa)? [Gap, Spec §FR-010]
- [ ] CHK038 Is there an edge case for camera permission granted then revoked mid-session (distinct from stream-ended mid-capture)? [Gap, Spec §User Story 4 / Edge Cases §stream-ends]

## Non-Functional Requirements

- [ ] CHK039 Is the performance goal "onboarding < 5s local" (plan §Performance Goals) reflected in a requirement or success criterion, or only in the plan? [Completeness, Spec §SC-001 vs plan §Performance Goals]
- [ ] CHK040 Is SC-001's "under 2 minutes" operationalized (who times, what environment, what constitutes "complete")? [Measurability, Spec §SC-001]
- [ ] CHK041 Is there a non-functional requirement on log content (no images/embeddings logged), or is it only an Assumption? [Completeness, Spec §Assumptions §observability]
- [ ] CHK042 Is SC-010 ("no real ML model") measurable by a runtime or static check, or only by "confirming the spec's scope" (a document-level assertion)? [Measurability, Spec §SC-010]
- [ ] CHK043 Is there a non-functional requirement on test-suite coverage threshold, or only that a suite exists (FR-018)? [Measurability, Spec §FR-018]

## Dependencies & Assumptions

- [ ] CHK044 Is the dependency on spec 001's existing `UNIQUE(identifier)` constraint stated as a requirement-level precondition, or only in Assumptions/plan? [Completeness, Spec §Assumptions §spec-001-reuse / plan §Constitution Check]
- [ ] CHK045 Is the assumption that `usuarios/` is bind-mounted and identical inside/outside the container captured in a requirement (FR-009 mentions it parenthetically but is it normative)? [Clarity, Spec §FR-009]
- [ ] CHK046 Is the "secure context (localhost or HTTPS) required for camera" assumption reflected in a requirement or only Assumptions? [Completeness, Spec §Assumptions §secure-context / FR-012]
- [ ] CHK047 Are out-of-scope items (login, mood, age, deletion, rate limiting, liveness) enumerated in a dedicated Requirements section, or only in Assumptions? [Completeness, Spec §Assumptions §out-of-scope]

## Ambiguities & Conflicts

- [ ] CHK048 Does the spec resolve whether the success response may include additional fields beyond `userId`, `identifier`, `status` (FR-007 says "containing")? [Ambiguity, Spec §FR-007]
- [ ] CHK049 Does the spec resolve which HTTP status code each rejection case returns (the codes are named but not numbered)? [Ambiguity, Spec §FR-004 / FR-014 / Clarifications §error-shape]
- [ ] CHK050 Does the spec resolve the tension between "actionable error for internal_error" (FR-014) and "internal errors are not user-recoverable" (implicit in FR-016)? [Conflict, Spec §FR-014 / FR-016 / Clarifications §error-shape]
- [ ] CHK051 Does the spec resolve whether the `identifier_taken` message is itself an allowed revelation of account existence, given FR-016's non-revelation rule? [Conflict, Spec §FR-002 / FR-016]
- [ ] CHK052 Does the spec resolve the filesystem-vs-DB atomicity gap (no transaction spans both resources) without relying solely on an unstated operation order? [Ambiguity, Spec §FR-008 / FR-009]

---

## Summary

- **New items added**: 52 (CHK001–CHK052)
- **Total items in file**: 52
- **Traceability**: 52/52 items carry a `[Spec §ref]`, `[Gap]`, `[Ambiguity]`, or `[Conflict]` tag (100% ≥ 80% threshold).
- **Focus areas selected**: (1) Input validation & error-contract clarity (FR-002/FR-004/FR-014/FR-016), (2) Cross-resource atomicity & state-machine coverage (FR-008/FR-009/FR-011) — the two highest-risk requirement clusters for this feature.
- **Dimensions covered**: Completeness, Clarity, Consistency, Measurability, Coverage.
- **Note**: This checklist is requirements-only ("Unit Tests for English"). It does not assert implementation behavior. Several items surfaced real candidate gaps (CHK005/CHK035 cross-resource atomicity, CHK008/CHK017 error-code enumeration, CHK020/CHK049 status-code numbering, CHK014/CHK048 response-field exactness) that the reviewer may want to resolve at the spec or contract layer before plan execution.
