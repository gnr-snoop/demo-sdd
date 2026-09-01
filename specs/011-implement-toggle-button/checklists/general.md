# General Requirements Quality Checklist: Live Face Preview Overlay Toggle

**Purpose**: Unit tests for English — validate completeness, clarity, consistency, measurability, and coverage of the 011 toggle-button requirements before implementation
**Created**: 2026-09-01
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md) | [research.md](../research.md) | [data-model.md](../data-model.md)
**Focus**: General (derived from spec/plan/tasks signals — top relevance clusters: preview-overlay behavior & a11y/throttle invariants)
**Depth**: Standard | **Audience**: Reviewer (PR) | **Source**: spec.md 164 lines, 17 FRs, 7 SCs, 10 clarifications, 9 edge cases; plan.md BLOCKING-01 resolved client-side

## Requirement Completeness

- [ ] CHK001 Are requirements for default toggle state and session-scoped persistence defined for all lifecycle events (first load, in-session navigation, remount)? [Completeness, Spec §FR-010, §Assumptions]
- [ ] CHK002 Are requirements for overlay content completeness specified when detector returns bbox only vs. bbox+landmarks? [Completeness, Spec §FR-004, §Clarifications Q1]
- [ ] CHK003 Are requirements for toggle visibility in every camera readiness state (grant, pending, denied, stream-lost) defined? [Completeness, Spec §FR-015, §FR-001]
- [ ] CHK004 Are requirements for capture neutrality specified to guarantee overlay state does not alter still capture payload or validation? [Completeness, Spec §FR-007, §SC-004]
- [ ] CHK005 Are requirements for the shared-component reuse scope (onboarding/login/dashboard) defined without per-page duplication? [Completeness, Spec §FR-008, §User Story 2]

## Requirement Clarity

- [ ] CHK006 Is the toggle control type quantified — is "button or switch" resolved to a single canonical pattern with ARIA mapping? [Clarity, Spec §FR-002, §FR-009]
- [ ] CHK007 Is the throttle budget quantified with specific criteria (≤5 FPS / ≥200 ms decoupled from native FPS) consistently across FR, SC, and Assumptions? [Clarity, Measurability, Spec §FR-006, §SC-001/005]
- [ ] CHK008 Is "mirrored identically" defined with a deterministic method (shared scaleX(-1) vs. flipped x = width - x - w) and coordinate space? [Clarity, Spec §FR-003, §Assumptions]
- [ ] CHK009 Is the canonical accessible name and locale variant specified deterministically including language-selection rule? [Clarity, Spec §FR-009, §Clarifications Q9]
- [ ] CHK010 Is "immediately" for overlay disappearance quantified with a measurable bound? [Clarity, Measurability, Spec §FR-006, §SC-001]

## Requirement Consistency

- [ ] CHK011 Are requirements consistent between FR-003/FR-014 (mirroring+resize alignment) and the spec Assumption on overlay canvas/scale handling? [Consistency, Spec §FR-003, §FR-014, §Assumptions]
- [ ] CHK012 Are FR-006/SC-005/plan R-2 consistent on throttle cap vs. smoothing hold window (200 ms interval vs. 150–250 ms hold) without overlap confusion? [Consistency, Spec §FR-006, §FR-011, §SC-005]
- [ ] CHK013 Are FR-015 (hidden toggle) and User Story 1 Acceptance Scenario 5 consistent on "hidden not rendered" vs. "disabled" semantics? [Consistency, Spec §FR-015, §US1-AC5]
- [ ] CHK014 Are FR-016/FR-017 (detector port, mock-only tests) consistent with Constitution VII and plan BLOCKING-01 trade-off (client-side preview, CUDA capture-only)? [Consistency, Spec §FR-016, §FR-017, Plan §Constitution Check]
- [ ] CHK015 Are SC-007 (tests without GPU/network) and Non-Goals/Dependencies consistent on "no new route, no DB migration"? [Consistency, Spec §SC-007, §Non-Goals, Plan §Storage]

## Acceptance Criteria Quality

- [ ] CHK016 Are acceptance scenarios for toggle ON/OFF written in Given/When/Then with observable outcomes rather than implementation steps? [Acceptance Criteria Quality, Spec §US1-AC1..AC5]
- [ ] CHK017 Is the independent-test description for P1 defined to validate OFF→ON→OFF→capture without requiring other stories? [Acceptance Criteria Quality, Spec §US1 Independent Test]
- [ ] CHK018 Are cross-page acceptance criteria (US2-AC1..AC4) defined to verify identical behavior per page and session-state retention? [Acceptance Criteria Quality, Spec §US2-AC4, §FR-010]
- [ ] CHK019 Are degradation acceptance scenarios (US3-AC1..AC5) measurable for fluid video and responsive toggle under slow/failing detector? [Acceptance Criteria Quality, Spec §US3-AC1, §SC-005]
- [ ] CHK020 Is SC-006 defined with quantified accessibility criteria (canonical name, aria-pressed/checked state, keyboard operability, visible focus ring)? [Acceptance Criteria Quality, Measurability, Spec §SC-006, §FR-009]

## Scenario Coverage

- [ ] CHK021 Are requirements for zero-face and multi-face preview scenarios covered without blocking capture? [Coverage, Spec §FR-011, §FR-012, §US3-AC2/AC3, §SC-003]
- [ ] CHK022 Are requirements for slow/unavailable detector scenarios covered with degraded-to-empty-overlay behavior? [Coverage, Spec §FR-013, §US3-AC4/AC5]
- [ ] CHK023 Are requirements for resize/orientation-change and high-DPI alignment covered? [Coverage, Spec §FR-014, §Edge Cases p3]
- [ ] CHK024 Are requirements for navigation away/back and camera permission-denied recovery covered? [Coverage, Spec §Edge Cases p4/p6, §FR-015]

## Edge Case Coverage

- [ ] CHK025 Are requirements for rapid ON/OFF toggling with in-flight detection discard specified (no leaked timers/requests)? [Edge Case Coverage, Spec §Edge Cases p2, §FR-006]
- [ ] CHK026 Are requirements for low-confidence flicker and smoothing window (150–250 ms hold, threshold gating) specified as optional vs. required for v1? [Edge Case Coverage, Spec §FR-011, §Clarifications Q10]
- [ ] CHK027 Are requirements for landmark granularity variability (5-point, 68-point, adapter-determined) specified without mandating a specific model? [Edge Case Coverage, Spec §Assumptions, §FR-004]
- [ ] CHK028 Are requirements for mocked camera / jsdom test environment without real MediaDevices specified? [Edge Case Coverage, Spec §Edge Cases p8, §FR-017]

## Non-Functional Requirements

- [ ] CHK029 Are performance requirements for toggle transition (200 ms) and detection throttle (≤5 FPS) defined as measurable budgets decoupled from native video FPS? [NFR-Measurability, Spec §SC-001, §FR-006]
- [ ] CHK030 Are testability requirements defined to require mock-only execution without GPU/network/real models? [NFR-Coverage, Spec §FR-017, §SC-007, Constitution VII]
- [ ] CHK031 Are accessibility non-functional requirements quantified per WCAG-relevant behavior (keyboard, ARIA state, focus ring, i18n name)? [NFR-Clarity, Spec §FR-009, §SC-006]
- [ ] CHK032 Are visual/UX non-functional requirements bounded (high-contrast stroke, dot size, style-guide alignment) without requiring new design tokens for v1? [NFR-Clarity, Spec §Assumptions]

## Dependencies & Assumptions

- [ ] CHK033 Are dependencies on shared CameraCapture, detector port/mock adapter, and Docker Compose stack explicitly listed with reuse note? [Dependencies, Spec §Dependencies, Plan §Technical Context]
- [ ] CHK034 Are assumptions about coordinate space (axis-aligned bbox, intrinsic video pixels, canvas overlay layer) documented with mirroring transform assumption? [Assumptions, Spec §Assumptions, §FR-003]
- [ ] CHK035 Are assumptions about CUDA/host GPU as optional optimization (not prerequisite) documented and reflected in FR-016/FR-017? [Assumptions, Spec §Assumptions, §FR-016, §FR-017]
- [ ] CHK036 Are assumptions about ephemeral preview results (not stored/logged/used for enrollment) and in-memory-only toggle state documented with persistence boundary? [Assumptions, Spec §Assumptions, §Non-Goals]

## Ambiguities & Conflicts

- [ ] CHK037 Is the "session" scope for toggle persistence disambiguated — is it component-mount lifecycle vs. browser tab session vs. auth session? [Ambiguity, Spec §FR-010, §Clarifications Q4]
- [ ] CHK038 Is the confidence threshold for preview filtering disambiguated — is it adapter-defined vs. a specified numeric threshold? [Ambiguity, Spec §FR-011, §Clarifications Q10, Data Model §OVERLAY_MIN_SCORE]
- [ ] CHK039 Are potential conflicts between "optional smoothing 150–250 ms" and "must not hide real disappearance" resolved with a defined hold-reset rule? [Ambiguity, Spec §FR-011, §Edge Cases p5]
- [ ] CHK040 Is the Spanish locale name trigger specified — app locale vs. navigator.language vs. hardcoded — to avoid inconsistent accessible names? [Ambiguity, Spec §FR-009, §Assumptions]
- [ ] CHK041 Is the conflict between SC-005 "video stays fluid at native FPS" and throttled 5 FPS detection resolved by specifying decoupling requirement? [Conflict, Spec §SC-005, §FR-006]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline
- Traceability: 41/41 items (100%) carry explicit Spec/Plan/Constitution references; ≥80% threshold satisfied.
- Focus rationale: General checklist prioritizes the two dominant requirement clusters for 011 — preview-overlay invariants (visibility, mirroring, throttle, degrade) and cross-cutting quality (a11y, testability, hexagonal isolation) — per Standard depth / Reviewer audience.
- Constitution alignment spot-checks: FR-016/FR-017 trace to Principle VII (ports-and-adapters, mock-only tests); storage non-goals trace to Principles V/VI (no filesystem/DB change); Docker+CUDA traces to Principle IV as optional optimization; demo-first (Principle I) scopes smoothing as optional for v1.
