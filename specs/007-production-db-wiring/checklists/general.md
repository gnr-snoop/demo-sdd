# Requirements-Quality Checklist: Production DB Wiring + APP_MODE Selector (general)

**Purpose**: "Unit tests for the requirements" — evaluate the spec for completeness, clarity, consistency, measurability, and coverage. Items test the *requirements*, not the implementation.
**Created**: 2026-09-01
**Feature**: [spec.md](../spec.md) · **Focus**: general · **Depth**: Standard · **Audience**: Reviewer (PR)
**Note**: Complements the existing `requirements.md` (content-quality gate). This file uses the standard nine-category requirement-quality structure.

---

## Requirement Completeness

- [ ] CHK001 Are functional requirements specified for every user story (US1–US5) with no story left without at least one FR? [Completeness, Spec §User Scenarios/§Requirements]
- [ ] CHK002 Is every functional requirement (FR-001..FR-017) traceable to at least one user story and one success criterion (SC-001..SC-017)? [Completeness, Spec §Requirements/§Success Criteria]
- [ ] CHK003 Are all key entities (User, FaceTemplate, AuthSession, APP_MODE setting, DB Session Factory) defined with their persistence mode and layer (domain vs infrastructure vs config)? [Completeness, Spec §Key Entities]
- [ ] CHK004 Is the `APP_MODE` setting's allowed value set (`production|mock`) and default (`mock`) fully specified including the unset case? [Completeness, Spec §FR-001]
- [ ] CHK005 Is the production-mode startup sequence specified end-to-end (load settings → validate APP_MODE → validate DATABASE_URL → create engine/sessionmaker → run migrations → wire adapters → build app)? [Completeness, Spec §Clarifications/FR-006]
- [ ] CHK006 Are all fail-fast conditions for production mode enumerated (unset DATABASE_URL, unreachable DB, malformed/sync-only URL, invalid APP_MODE)? [Completeness, Spec §FR-005/FR-006/Edge Cases]

## Requirement Clarity

- [ ] CHK007 Is "effective store users on db" quantified with the specific entities (User, FaceTemplate, AuthSession) and persistence outcomes (committed, retrievable) rather than left as a slogan? [Clarity, Spec §US1]
- [ ] CHK008 Is "persist across requests" defined unambiguously as retrieval by a later, independent HTTP request backed by PostgreSQL (not in-process memory)? [Clarity, Spec §Clarifications]
- [ ] CHK009 Is "cross-restart persistence" defined with a concrete procedure (stop process, restart against same DB, confirm rows/cookie still resolve)? [Clarity, Spec §FR-009/US1]
- [ ] CHK010 Is "composition time" vs "per-request" selection disambiguated and pinned to once-at-startup? [Clarity, Spec §FR-002/Clarifications]
- [ ] CHK011 Is the health endpoint's per-mode behavior (DB-ping in production, no DB check in mock) specified clearly enough to assert without guessing? [Clarity, Spec §FR-010/SC-009a]
- [ ] CHK012 Is "reachable PostgreSQL" given a concrete definition (what check constitutes reachability), or is it left implicit? [Clarity, Spec §FR-006 — Gap]

## Requirement Consistency

- [ ] CHK013 Are the `APP_MODE` default (`mock`) and backward-compatibility claims consistent across FR-001, FR-003, US4, and the Assumptions? [Consistency, Spec §FR-001/FR-003/US4/Assumptions]
- [ ] CHK014 Is the real-vs-mock adapter split (real persistence + mock ML in production) consistent between FR-004, the Clarifications, and the Assumptions? [Consistency, Spec §FR-004/Clarifications/Assumptions]
- [ ] CHK015 Is the migration-gating rule (run only when `APP_MODE=production`) consistent between FR-007, US3, and the migration edge cases? [Consistency, Spec §FR-007/US3/Edge Cases]
- [ ] CHK016 Are the scope boundaries in FR-012/FR-017 consistent with the out-of-scope edge cases and the out-of-scope Assumptions list? [Consistency, Spec §FR-012/FR-017/Edge Cases]
- [ ] CHK017 Is the health-endpoint DB-ping contract consistent between FR-010, SC-009a, and the clarify-gate resolution? [Consistency, Spec §FR-010/SC-009a/Clarifications]
- [ ] CHK018 Is the "no new endpoints/entities/ports/frontend" claim consistent across FR-012, FR-017, US-clarifications, and Assumptions? [Consistency, Spec §FR-012/FR-017/Assumptions]

## Acceptance Criteria Quality

- [ ] CHK019 Does each acceptance scenario state a measurable Then-clause (row committed, retrievable out-of-band, fails fast before traffic, passes unchanged)? [Acceptance, Spec §User Scenarios]
- [ ] CHK020 Are fail-fast acceptance scenarios specific about the error surface (before serving traffic, clear actionable error listing allowed values / requiring reachable DATABASE_URL)? [Acceptance, Spec §US2/FR-005/FR-006]
- [ ] CHK021 Is the cross-restart acceptance scenario (US1 #5) stated as the definitive proof with the weaker out-of-band fallback explicitly defined? [Acceptance, Spec §US1/Clarifications]
- [ ] CHK022 Does the regression acceptance (US5 #5) specify both the deliberate regression and the expected failing test? [Acceptance, Spec §US5]
- [ ] CHK023 Are acceptance scenarios for the health endpoint (per-mode DB-ping) present, or only implied by SC-009a? [Acceptance, Spec §SC-009a — Gap]

## Scenario Coverage

- [ ] CHK024 Are both modes (`production` and `mock`) each covered by at least one dedicated user story? [Coverage, Spec §US1/US4]
- [ ] CHK025 Is the invalid `APP_MODE` value scenario covered by both an acceptance scenario and an edge case? [Coverage, Spec §US2/Edge Cases]
- [ ] CHK026 Is the no-Docker / no-PostgreSQL test-skip scenario covered? [Coverage, Spec §FR-015/Edge Cases]
- [ ] CHK027 Is the post-start DB outage resilience scenario (runtime, not startup) covered? [Coverage, Spec §Edge Cases]
- [ ] CHK028 Are the migration states (no-op at head, behind head, mid-apply failure) each covered? [Coverage, Spec §Edge Cases]
- [ ] CHK029 Is the sync-only `DATABASE_URL` scheme scenario covered as both an edge case and a fail-fast path? [Coverage, Spec §Edge Cases/FR-006]

## Edge Case Coverage

- [ ] CHK030 Is an edge case specified for repeated `select_wiring` calls (unsupported, cached once)? [Edge, Spec §Edge Cases]
- [ ] CHK031 Is an edge case specified for mock-mode restart data loss being expected and documented (not a defect)? [Edge, Spec §Edge Cases]
- [ ] CHK032 Are out-of-scope guardrail edge cases (mock adapter / port / entity / endpoint / frontend changes) enumerated so implementers know they are explicit non-goals? [Edge, Spec §Edge Cases/FR-017]
- [ ] CHK034 Is an edge case specified for migrations already at head (no-op) and for the backend starting before PostgreSQL healthy (prevented by compose)? [Edge, Spec §Edge Cases]

## Non-Functional Requirements

- [ ] CHK035 Is the log-safety NFR (no images/embeddings/biometric responses in logs; structured JSON only) specified as a requirement, not just an assumption? [NFR, Spec §FR-016]
- [ ] CHK036 Is the "domain/contract/unit tests run without GPU/network/real models" constraint specified as a requirement? [NFR, Spec §FR-014/FR-015]
- [ ] CHK037 Is the demo-grade performance posture (no real-time SLO; fail-fast before traffic) stated in the spec's requirements, or only in the plan? [NFR, Spec §plan — Gap: not in spec FRs]
- [ ] CHK038 Are the security/traceability/audit-log exclusions stated as explicit non-goals (Principle VIII)? [NFR, Spec §FR-016/Assumptions]

## Dependencies & Assumptions

- [ ] CHK039 Is the dependency on the pre-existing real SQLAlchemy adapters from spec 001 (reused verbatim, not re-created) stated? [Dependencies, Spec §Assumptions]
- [ ] CHK040 Is the dependency on the specs 001-006 baseline (ports, entities, contracts, existing tests) stated? [Dependencies, Spec §Assumptions]
- [ ] CHK041 Is the constitutionally-fixed technology stack assumption recorded as settled (not an ad-hoc choice)? [Dependencies, Spec §Assumptions]
- [ ] CHK042 Is the `testcontainers` test-only dependency documented in the spec, or only in the plan? [Dependencies, Spec §plan — Gap: in plan not spec]

## Ambiguities & Conflicts

- [ ] CHK043 Is "reachable PostgreSQL" concretely defined, or left to engine-creation surfacing (potential ambiguity for test assertion)? [Ambiguity, Spec §FR-006]
- [ ] CHK044 Is the cross-restart "impractical in harness" fallback criterion objective, or left to implementer judgment? [Ambiguity, Spec §Clarifications/Assumptions]
- [ ] CHK045 Could "mock ML adapters in production mode" be misread as real ML being in scope for this spec (potential conflict with FR-004/FR-017)? [Conflict, Spec §FR-004/FR-017]
- [ ] CHK046 Is there any tension between "fail fast on unreachable DB" (FR-006) and "runtime DB outage is recoverable 500" (edge case) — are the startup vs runtime boundaries explicitly drawn? [Conflict, Spec §FR-006/Edge Cases]

---

## Summary

- **New items added**: 44 (CHK001–CHK046, excluding the merged CHK033)
- **Total items in file**: 44
- **Traceability**: 44/44 items carry a `[Dimension, Spec §ref]` reference (100% ≥ 80% threshold)
- **Gaps flagged**: 4 (CHK012 reachable-DB definition; CHK023 health-endpoint acceptance scenario; CHK037 demo-grade NFR in spec; CHK042 testcontainers dependency in spec)
- **Focus areas selected**: (1) Configuration-driven wiring & fail-fast startup, (2) Real-persistence contract & test coverage — the two highest-relevance clusters for this Fase 5 foundation spec
- **Depth**: Standard · **Audience**: Reviewer (PR)
