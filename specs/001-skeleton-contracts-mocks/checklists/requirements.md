# Specification Quality Checklist: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-31
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
- The technology stack (FastAPI/React/Vite/PostgreSQL/Alembic/Docker Compose) is referenced because it is fixed by the ratified Constitution (Principles III–VII and the Technology Stack table), not chosen ad hoc in this spec. These are project-level architectural decisions, not implementation details leaking into the specification.
- This is a scaffolding spec (Fase 1); its primary stakeholders are the development team and demo audience. User stories are framed as demonstrable developer/demo journeys, which is appropriate for a spec whose value is enabling subsequent feature specs.
- No [NEEDS CLARIFICATION] markers were needed: all open questions (OQ-1 through OQ-8) are pre-resolved by the Constitution's defaults and recorded as assumptions.
- Clarify pass (2026-08-31): 4 low-impact ambiguities auto-accepted and integrated (enum values, observability scope, session-placeholder mechanism, mock determinism approach). 1 public-contract question (userId primary-key type) reported as BLOCKING under strict mode for orchestrator surfacing at the gate. No checklist items toggled.

---

# Requirements-Quality Checklist: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Purpose**: "Unit tests for the requirements" — evaluates the spec's requirements for completeness, clarity, consistency, measurability, and coverage (NOT implementation correctness).
**Created**: 2026-08-31
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md)
**Focus areas**: Contract & Interface requirements; Hexagonal domain/ports/mocks requirements
**Depth**: Standard | **Audience**: PR Reviewer

> Item format: `- [ ] CHK### <question about requirement quality> [Dimension, Spec §ref]`
> Dimensions: C=Completeness, Cl=Clarity, Co=Consistency, M=Measurability, Cv=Coverage

## Requirement Completeness

- [ ] CHK001 Are all seven PRD §8 endpoints enumerated as distinct requirements rather than referenced only as a group? [C, Spec FR-005/US3]
- [ ] CHK002 Is every domain entity attribute from PRD §7 (User, FaceTemplate, AuthSession, AnalysisRequest) named explicitly in the requirements? [C, Spec FR-008/Key Entities]
- [ ] CHK003 Are all eight port capabilities (detector, embedder, age, mood, session, user-repo, face-template-repo, image-storage) individually required, or only listed in a single aggregate FR? [C, Spec FR-009]
- [ ] CHK004 Is a requirement present that the domain layer must have ZERO imports of concrete ML/infrastructure (not just "no dependency" prose)? [C, Spec FR-008/SC-004]
- [ ] CHK005 Are requirements specified for the health/readiness endpoint contract, or only mentioned in passing? [C, Spec US1/Clarifications]
- [ ] CHK006 Is there a requirement defining what "deterministic mock" means concretely (hardcoded constants, no RNG/seed)? [C, Spec Clarifications/SC-005]
- [ ] CHK007 Are configuration surfaces (threshold, model versions, image limits) each named as distinct tunable requirements? [C, Spec FR-015]
- [ ] CHK008 Is the requirement to carry model/adapter version identifiers stated for every adapter type, not just generically? [C, Spec FR-012]

## Requirement Clarity

- [ ] CHK009 Is "stub/mock endpoint" defined unambiguously so a reviewer cannot confuse it with "real logic gated by a flag"? [Cl, Spec Assumptions/SC-010]
- [ ] CHK010 Is "session placeholder" quantified — what value, what representation, what lifetime — rather than left as prose? [Cl, Spec Clarifications/FR-006]
- [ ] CHK011 Is "protected endpoint" defined by an explicit enumerated list rather than by implication? [Cl, Spec FR-006]
- [ ] CHK012 Is "non-revealing generic message" for login failure given a concrete definition (no field-level error variation)? [Cl, Spec FR-007/FR-018]
- [ ] CHK013 Is "deterministic bounding box, score, and face count" specified with types/units, or only named? [Cl, Spec FR-011/US4-AC2]
- [ ] CHK014 Is "fixed dimension" for the embedding vector quantified with a number or left as an open parameter? [Cl, Spec US4-AC3]
- [ ] CHK015 Is the `usuarios/<user-id>/pictures.jpg` path convention stated with the exact filename (singular `pictures.jpg`) and no ambiguity over extension/folder? [Cl, Spec FR-014/Principle V]
- [ ] CHK016 Is "no host-native installation required" defined — which runtimes are excluded from the host? [Cl, Spec US1/SC-001]

## Requirement Consistency

- [ ] CHK017 Are the enum values for `User.status` and `AnalysisRequest.status` consistent between the Clarifications block and the Key Entities block? [Co, Spec Clarifications vs Key Entities]
- [ ] CHK018 Is the UUID v4 decision for primary keys consistently reflected across spec FR-005, US3-AC1, Key Entities, and Assumptions? [Co, Spec Clarifications vs FR-005/Key Entities]
- [ ] CHK019 Is the "enrolled" status value used in US3-AC1 consistent with the `User.status` enum defined in Clarifications? [Co, Spec US3-AC1 vs Clarifications]
- [ ] CHK020 Are the protected-endpoint lists in FR-006 and US3-AC8 identical (same five endpoints)? [Co, Spec FR-006 vs US3-AC8]
- [ ] CHK021 Is the "no real business logic" scope (SC-010) consistent with the list of explicitly deferred items in Assumptions? [Co, Spec SC-010 vs Assumptions]
- [ ] CHK022 Is the observability scope (JSON logs + health endpoint) consistent between Clarifications and Assumptions? [Co, Spec Clarifications vs Assumptions]
- [ ] CHK023 Do the seven endpoints listed in US3 match the seven endpoints named in FR-005 and the Constitution Quality Gate §5? [Co, Spec US3 vs FR-005 vs Constitution]

## Acceptance Criteria Quality

- [ ] CHK024 Does every functional requirement (FR-001..FR-018) trace to at least one acceptance scenario with a Given/When/Then? [M, Spec FRs vs Acceptance Scenarios]
- [ ] CHK025 Are acceptance scenarios measurable by inspection or command rather than by subjective judgment ("renders correctly", "works")? [M, Spec US1–US6 ACs]
- [ ] CHK026 Is SC-005 (determinism) specified with a repeatable verification procedure (run twice, compare)? [M, Spec SC-005]
- [ ] CHK027 Is SC-004 (zero domain imports) specified with a verifiable method (static dependency inspection)? [M, Spec SC-004]
- [ ] CHK028 Is SC-009 (contract-violation detection) specified with a concrete procedure (introduce + revert a change)? [M, Spec SC-009]
- [ ] CHK029 Does each success criterion map to at least one functional requirement (no orphan SCs)? [M, Spec SC-001..SC-010 vs FRs]

## Scenario Coverage

- [ ] CHK030 Is there an acceptance scenario for the idempotent-migration case (apply twice → no error)? [Cv, Spec US5-AC3]
- [ ] CHK031 Is there an acceptance scenario for the filesystem adapter read-back from BOTH host and container paths? [Cv, Spec US5-AC2/SC-007]
- [ ] CHK032 Is there an acceptance scenario covering the contract-test failure path (a violation is caught)? [Cv, Spec US6-AC3/SC-009]
- [ ] CHK033 Is there an acceptance scenario for protected-endpoint rejection of sessionless requests across ALL five protected endpoints, not just one? [Cv, Spec US3-AC8/FR-006]
- [ ] CHK034 Is there a scenario covering navigation without full page reload (SPA behavior) as a distinct requirement? [Cv, Spec US2-AC3]

## Edge Case Coverage

- [ ] CHK035 Are all seven Edge Cases listed in the spec traced to a requirement or assumption (not dangling)? [Cv, Spec Edge Cases]
- [ ] CHK036 Is the "port already in use" edge case specified with a required outcome (clear conflict report), not just a question? [Cv, Spec Edge Cases #1]
- [ ] CHK037 Is the "malformed request to stub endpoint" edge case covered by a requirement mandating a documented validation error status? [Cv, Spec Edge Cases #3]
- [ ] CHK038 Is the "filesystem cannot write" edge case covered by a requirement mandating a clear storage error? [Cv, Spec Edge Cases #6]
- [ ] CHK039 Is the "empty/undecodable image to mock adapter" edge case covered by a deterministic-result requirement? [Cv, Spec Edge Cases #7]
- [ ] CHK040 Are edge cases for expired/invalid session placeholder and conflicting-existing-schema migration each tied to a required outcome? [Cv, Spec Edge Cases #4,#5]

## Non-Functional Requirements

- [ ] CHK041 Is the "no GPU / no network / no real models" test constraint stated as an explicit requirement (FR-017), not only a success criterion? [C, Spec FR-017/SC-008]
- [ ] CHK042 Is demo-grade performance (<5s analysis) referenced and explicitly scoped as out-of-SLO for this stub spec? [Cl, Spec plan §Performance Goals]
- [ ] CHK043 Is reproducibility-from-clean-checkout stated as a requirement (FR-001/FR-002), not only an assumption? [C, Spec FR-001/FR-002/SC-001]
- [ ] CHK044 Are the explicit non-goals (no real ML, no rate limiting, no real deletion) stated as requirements-level exclusions, not only assumptions? [C, Spec SC-010/Assumptions]

## Dependencies & Assumptions

- [ ] CHK045 Does every Assumption trace to a Constitution OQ/principle or an explicit deferral to a later spec (002–006)? [Co, Spec Assumptions vs Constitution]
- [ ] CHK046 Is the dependency on the ratified Constitution (Principles III–VIII) explicit for each stack/storage/architecture decision? [Co, Spec Assumptions vs Constitution]
- [ ] CHK047 Are deferred-to specs (002–006) named consistently so a reviewer can confirm the deferral target exists in the plan? [Cl, Spec Assumptions/plan]
- [ ] CHK048 Is the "AnalysisRequest included now to avoid a later migration" assumption justified against a requirement (FR-013)? [Co, Spec Assumptions vs FR-013]

## Ambiguities & Conflicts

- [ ] CHK049 Does the spec resolve the tension between "endpoints return mock responses" and "return a clear not-implemented status" — are these two distinct cases or one? [Cl, Spec FR-005/US3]
- [ ] CHK050 Is "route-protection placeholder" unambiguous vs. real session enforcement (deferred to spec 003) — no reviewer could mistake it for auth? [Cl, Spec FR-004/Assumptions]
- [ ] CHK051 Is there any conflict between SC-010 ("no real business logic") and FR-013/FR-014 (migrations + filesystem adapter do real work)? If so, is the boundary stated? [Co, Spec SC-010 vs FR-013/FR-014]
- [ ] CHK052 Is "deterministic mock values" in US3-ACs consistent with "hardcoded constant outputs (no RNG/seed)" in Clarifications/Assumptions? [Co, Spec US3 vs Clarifications]
- [ ] CHK053 Are open Constitution questions (OQ-4/OQ-5 model choices) explicitly marked "not exercised" so a reviewer does not read them as gaps? [Cl, Spec plan §OQ status]

## Notes

- These items evaluate the REQUIREMENTS, not the implementation. "Is X specified?" / "Is X quantified?" — not "Does X work?".
- Dimensions: C=Completeness, Cl=Clarity, Co=Consistency, M=Measurability, Cv=Coverage.
- §ref points to the spec section where the requirement (or gap) lives; `[Gap]` would indicate no source found.
- Check items off as findings are confirmed: `[x]`; mark unresolved gaps inline with a comment.
