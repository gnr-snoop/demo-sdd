# Requirements-Quality Checklist: Mood Analysis from Authenticated Dashboard (Fase 4 — mood)

**Purpose**: "Unit tests for the requirements" — evaluate the spec for completeness, clarity, consistency, measurability, and coverage. This checklist tests the *requirements themselves*, not the implementation.
**Created**: 2026-08-31
**Feature**: [spec.md](../spec.md)
**Focus areas**: API contract & error-handling requirements; Frontend UX / session / concurrency requirements
**Depth**: Standard
**Audience**: Reviewer (PR)

> Item format: `- [ ] CHK### <question about requirement quality> [Dimension, Spec §ref]`
> Dimensions: C=Completeness, Cl=Clarity, Co=Consistency, M=Measurability, Cv=Coverage

---

## Requirement Completeness

- [ ] CHK001 Are all mood response fields (`label`, `confidence`, `disclaimer`) explicitly defined with type, allowed values, and optionality in the requirements? [C, Spec §FR-002 / Assumptions]
- [ ] CHK002 Is the complete valid label set `{neutral, feliz, triste, sorprendido, no concluyente}` enumerated in a single normative location, with all other references pointing to it rather than re-listing? [C, Spec §FR-004 / FR-002]
- [ ] CHK003 Are all error codes (`unauthenticated`, `no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, `internal_error`) enumerated with their corresponding HTTP status codes (401/400/400/400/400/500)? [C, Spec §FR-006 / FR-007]
- [ ] CHK004 Is the exact `disclaimer` string pinned verbatim in the requirements, with a requirement that it be returned and rendered unchanged? [C, Spec §FR-003]
- [ ] CHK005 Is the evaluation order of endpoint conditions (session → image decode → detect → estimate → normalize → respond) specified as a requirement, not only in clarifications? [C, Spec §FR-005]
- [ ] CHK006 Are the reused image limits (JPEG, ≤ 2 MB, ≤ 640px long edge) referenced as requirements, with their source (spec 002 / OQ-8) cited? [C, Spec §FR-005 / Assumptions]
- [ ] CHK007 Is the transient (non-persisted) nature of the mood result stated as an explicit requirement, with the deferred `AnalysisRequest` persistence called out as out of scope? [C, Spec §FR-014 / Assumptions]
- [ ] CHK008 Is the mock-only mood estimator constraint (real models deferred to Fase 5) stated as a requirement with its rationale? [C, Spec §FR-016 / SC-012]
- [ ] CHK009 Are the camera stream lifecycle requirements (acquire on mount, release on unmount) specified? [C, Spec §FR-012b / SC-015]
- [ ] CHK010 Is the camera-permission-denied journey specified as a requirement distinct from `invalid_image`? [C, Spec §FR-012c / SC-016]
- [ ] CHK011 Is the "Calcular edad" disabled-placeholder behavior (present, disabled, "coming soon", no action) specified as a requirement? [C, Spec §FR-013 / SC-008]
- [ ] CHK012 Are the observability/logging constraints (no image/embedding/biometric data; structured JSON only) specified as a requirement? [C, Spec §FR-019 / SC-013]
- [ ] CHK013 Is the hexagonal port-only dependency constraint for the mood domain orchestration specified as a requirement? [C, Spec §FR-015 / SC-009]

## Requirement Clarity

- [ ] CHK014 Is "exactly one usable face" quantified — does the spec define what makes a face "usable" vs. merely detected (quality threshold)? [Cl, Spec §FR-005 / Edge Cases]
- [ ] CHK015 Is "low-quality signal" (mapped to `no concluyente`) defined with a measurable threshold or left as a port-internal concern? [Cl, Spec §FR-004 / Edge Cases]
- [ ] CHK016 Is "independent loading indicator" / "independent error surface" defined precisely enough to distinguish from a shared indicator? [Cl, Spec §FR-008 / FR-011 / PRD §6.4]
- [ ] CHK017 Is "actionable message" quantified — does the spec define what makes an error message actionable (recapture instruction, retry presence)? [Cl, Spec §FR-006 / FR-015]
- [ ] CHK018 Is "recoverable error" defined — does it mean retry-without-reload, or something broader? [Cl, Spec §FR-007 / FR-011]
- [ ] CHK019 Is the confidence rendering format ("≈NN%", nearest integer) specified unambiguously for both present and absent cases? [Cl, Spec §FR-012a / SC-014]
- [ ] CHK020 Is "keyboard-accessible" given concrete criteria (focusable, operable via Enter/Space, descriptive accessible name)? [Cl, Spec §FR-012]
- [ ] CHK021 Is "does not rely exclusively on color" given concrete criteria (icon/text/aria-label accompaniment)? [Cl, Spec §FR-012 / PRD §10]
- [ ] CHK022 Is "coming soon" indication for the age button specified with concrete content/affordance? [Cl, Spec §FR-013]
- [ ] CHK023 Is the "< 5 seconds" performance goal scoped precisely (local demo env, excluding model-load, end-to-end)? [Cl, Spec §SC-001]

## Requirement Consistency

- [ ] CHK024 Are the `confidence` optionality rules consistent between FR-002 (response contract), FR-012a (rendering), and the Edge Cases section? [Co, Spec §FR-002 / FR-012a / Edge Cases]
- [ ] CHK025 Is the error body shape `{"error": {"code", "message"}}` referenced consistently across FR-006, FR-007, and Assumptions (no competing shapes)? [Co, Spec §FR-006 / FR-007 / Assumptions]
- [ ] CHK026 Is the status-code mapping (401 exclusively `unauthenticated`; 400 for capture-quality; 500 for `internal_error`) consistent across FR-001, FR-006, FR-007, and Assumptions? [Co, Spec §FR-001 / FR-006 / FR-007 / Assumptions]
- [ ] CHK027 Is the "one capture at a time" / button-disabled-while-in-flight rule stated consistently across FR-009, FR-014 clarifications, and Edge Cases? [Co, Spec §FR-009 / Clarifications / Edge Cases]
- [ ] CHK028 Is the transient-result rule consistent between FR-014, SC-007, and the Assumptions (no contradiction with any persistence requirement)? [Co, Spec §FR-014 / SC-007 / Assumptions]
- [ ] CHK029 Are the reused spec 002/003 elements (limits, error shape, `require_valid_session`, `ProtectedRoute`, logout) referenced consistently without redefinition that could conflict? [Co, Spec §Assumptions / FR-001 / FR-005]
- [ ] CHK030 Is the mock-adapter-only constraint consistent between FR-016, SC-012, and the Constitution Check (Principle VII)? [Co, Spec §FR-016 / SC-012 / plan.md]
- [ ] CHK031 Is the label-normalization rule (out-of-set → `no concluyente`) consistent between FR-004, Edge Cases, and User Story 2 scenario 6? [Co, Spec §FR-004 / Edge Cases / US2]

## Acceptance Criteria Quality

- [ ] CHK032 Does each User Story have at least one Independent Test that is self-contained and asserts a measurable outcome? [M, Spec §User Stories 1–5]
- [ ] CHK033 Are acceptance scenarios written in Given/When/Then form with concrete, verifiable conditions (not vague behaviors)? [M, Spec §User Stories 1–5]
- [ ] CHK034 Does every FR map to at least one acceptance scenario or success criterion (full traceability)? [Cv, Spec §FR-001..FR-019 / SC-001..SC-016]
- [ ] CHK035 Are the success criteria (SC-001..SC-016) each verifiable by a concrete, repeatable method stated in the criterion? [M, Spec §Success Criteria]
- [ ] CHK036 Is AC-007 (PRD) explicitly traced to the user stories/FRs that deliver it? [Cv, Spec §User Story 1 / FR-002]

## Scenario Coverage

- [ ] CHK037 Is the happy path (valid session, one face, valid label, confidence present) covered by an acceptance scenario? [Cv, Spec §US1]
- [ ] CHK038 Is the happy path with confidence absent/null covered by an acceptance scenario or edge case? [Cv, Spec §Edge Cases / FR-012a]
- [ ] CHK039 Are all four capture-quality failure codes (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`) each covered by a dedicated scenario? [Cv, Spec §US2 / FR-006]
- [ ] CHK040 Is the port/adapter error → `500 internal_error` path covered by a scenario? [Cv, Spec §US2 scenario 4 / FR-007]
- [ ] CHK041 Is the out-of-set label → `no concluyente` normalization path covered by a scenario? [Cv, Spec §US2 scenario 6 / FR-004]
- [ ] CHK042 Are the unauthenticated paths (no cookie, expired, revoked) each covered by scenarios? [Cv, Spec §US3 scenarios 1–2 / FR-001]
- [ ] CHK043 Is the mid-flight session expiry path covered by a scenario? [Cv, Spec §US3 scenario 4 / Edge Cases]
- [ ] CHK044 Is the double-press / concurrent-capture prevention covered by a scenario? [Cv, Spec §US3 scenario 3 / FR-009]
- [ ] CHK045 Is the camera-permission-denied journey covered by a scenario or edge case? [Cv, Spec §Edge Cases / FR-012c]
- [ ] CHK046 Is the camera stream release on logout/expiry covered by a scenario or edge case? [Cv, Spec §US4 scenario 7 / Edge Cases / FR-012b]
- [ ] CHK047 Is the result-persistence-visible-until-new-analysis-or-logout rule covered by scenarios? [Cv, Spec §US1 scenarios 4–5 / US4 scenario 3 / FR-010]
- [ ] CHK048 Is the disabled age placeholder covered by a scenario? [Cv, Spec §US4 scenario 5 / FR-013]
- [ ] CHK049 Is the non-color-reliance accessibility requirement covered by a scenario? [Cv, Spec §US4 scenario 6 / FR-012]
- [ ] CHK050 Are the automated-test expectations (unit/integration/contract, no GPU/network) covered by scenarios? [Cv, Spec §US5 / FR-018]

## Edge Case Coverage

- [ ] CHK051 Is the confidence-outside-[0,1] port output case covered (clamp/normalize/absent)? [Cv, Spec §Edge Cases / FR-002]
- [ ] CHK052 Is the concurrent-backend-requests race case covered (permitted server-side, guarded client-side)? [Cv, Spec §Edge Cases]
- [ ] CHK053 Is the camera-stream-ends-or-permission-revoked-mid-capture case covered? [Cv, Spec §Edge Cases]
- [ ] CHK054 Is the oversized/invalid-image case covered distinctly from capture-quality face failures? [Cv, Spec §Edge Cases / FR-006]
- [ ] CHK055 Is the logout-while-result-displayed case covered (result discarded, re-auth required)? [Cv, Spec §Edge Cases / FR-010]

## Non-Functional Requirements

- [ ] CHK056 Is the performance goal (mood < 5s local, excluding model load) stated as a measurable requirement with an environment scope? [M, Spec §SC-001 / PRD §13]
- [ ] CHK057 Is the no-GPU/no-network test-execution constraint stated as a requirement? [M, Spec §FR-018 / SC-010]
- [ ] CHK058 Are the accessibility requirements (keyboard, descriptive name, non-color-reliance) stated as measurable requirements? [M, Spec §FR-012]
- [ ] CHK059 Is the observability/no-PII-in-logs constraint stated as a measurable requirement? [M, Spec §FR-019 / SC-013]
- [ ] CHK060 Is the hexagonal purity constraint (zero infra/ML imports in domain) stated as a measurable, statically-checkable requirement? [M, Spec §FR-015 / SC-009]
- [ ] CHK061 Is the reproducibility requirement (identifiable model version on the adapter) stated? [M, Spec §FR-017]

## Dependencies & Assumptions

- [ ] CHK062 Are all reused elements from specs 001/002/003 (ports, error shape, limits, session validation, entities, UI components) explicitly enumerated as assumptions? [C, Spec §Assumptions]
- [ ] CHK063 Are the out-of-scope items (age, deletion, real ML, continuous video, rate limiting, liveness, audit persistence) explicitly listed? [C, Spec §Assumptions]
- [ ] CHK064 Is the secure-context assumption for camera access (`localhost`/HTTPS) stated? [C, Spec §Assumptions]
- [ ] CHK065 Are the Constitution-level technology-stack decisions referenced as settled assumptions, not re-litigated? [C, Spec §Assumptions / plan.md Constitution Check]
- [ ] CHK066 Is the contract-evolution from spec 001 stub → spec 004 real shape acknowledged as an authorized change? [Co, Spec §plan.md Contract evolution note]

## Ambiguities & Conflicts

- [ ] CHK067 Does any requirement use an unquantified vague term ("usable", "low-quality", "actionable", "recoverable", "coming soon") without a definition or measurable criterion? [Cl, Spec §FR-004 / FR-006 / FR-007 / FR-013]
- [ ] CHK068 Is there any conflict between the transient-result rule (FR-014) and any PRD reference to result persistence? [Co, Spec §FR-014 / PRD §7 / §19]
- [ ] CHK069 Is there any conflict between "no server-side single-analysis lock" (demo-first) and FR-014 (one capture at a time)? [Co, Spec §FR-009 / Assumptions / Edge Cases]
- [ ] CHK070 Is there any ambiguity in whether `insufficient_quality` is a detector concern or a mood-estimator concern? [Cl, Spec §FR-005 / FR-006 / Edge Cases]
- [ ] CHK071 Is the boundary between frontend-only error states (camera permission) and backend error codes (invalid_image) unambiguous? [Cl, Spec §FR-012c / FR-006]
- [ ] CHK072 Are there any requirements that specify implementation behavior (frameworks, code structure) rather than required qualities? [Co, Spec §FR-015 / plan.md Structure Decision]

---

## Summary

- **Total items**: 72
- **Dimensions covered**: Completeness (13), Clarity (10), Consistency (8), Measurability (6), Coverage (24+5 edge), Ambiguities/Conflicts (6)
- **Traceability**: 100% of items include a `[Spec §ref]` or `[Gap]`-style reference (≥80% threshold met).
- **Focus clusters**: (1) API contract & error-handling requirements (FR-001..FR-007, FR-019, SC-002..SC-005, SC-013); (2) Frontend UX / session / concurrency requirements (FR-008..FR-013, SC-006..SC-016).
- **Note**: This checklist complements the existing `requirements.md` (generic content-quality gate). It tests the *requirements* as written in `spec.md` for quality defects; it does not test the implementation.
