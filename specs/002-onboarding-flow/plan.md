# Implementation Plan: Onboarding Flow (Fase 2)

**Branch**: `002-onboarding-flow` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-onboarding-flow/spec.md`

## Summary

Implement the real onboarding business logic on top of the skeleton/contracts/ports/mocks from spec 001. A person submits an identifier, explicit biometric consent, and a single captured image to `POST /api/onboarding`. The backend validates the identifier (format + case-insensitive duplicate) and consent, decodes and enforces image limits, resizes to the configured long edge, runs the detector port (exactly-one-face + quality-threshold rule), runs the embedder port to produce a facial embedding, and atomically persists a `User` (status `enrolled`) + `FaceTemplate` (modelVersion `mock-embedder-v1`) in a single unit of work, storing the normalized image at `usuarios/<user-id>/pictures.jpg`. All ML touchpoints go through the existing hexagonal ports wired to mock adapters; real models are deferred to Fase 5. The frontend onboarding page is built out with a camera preview and the seven-state PRD §6.2 state machine. Rejection paths return a stable `{"error": {"code", "message"}}` shape with actionable, non-revealing messages.

## Technical Context

**Language/Version**: Python 3.11 (backend); TypeScript 5.x / React 18 / Vite 5 (frontend). Settled by Constitution Principle III + Technology Stack table (OQ-1 FastAPI, OQ-2 Vite defaults). Inherited from spec 001.

**Primary Dependencies**:
- Backend (additive to spec 001): **Pillow** (PIL) for image decode/resize/long-edge normalization; **pydantic-settings** (already present) for the new `quality_threshold` env var; existing FastAPI, SQLAlchemy 2.0 async, Alembic, psycopg/asyncpg, structlog, pytest + pytest-asyncio, httpx.
- Frontend (additive to spec 001): existing react, react-dom, react-router-dom, @vitejs/plugin-react, vitest + @testing-library/react. No new runtime deps (camera via standard `navigator.mediaDevices.getUserMedia`).
- Orchestration: existing Docker Compose (no topology change).

**Storage**: PostgreSQL (dockerized) for `User` + `FaceTemplate` (Constitution Principle VI); local filesystem `usuarios/<user-id>/pictures.jpg` for the captured image, bind-mounted (Principle V). Both inherited from spec 001; the `users.identifier` `UNIQUE` constraint already exists and enforces case-insensitive duplicate detection on the normalized (trim + lowercase) value.

**Testing**: pytest (domain unit + contract + integration), httpx.AsyncClient for contract tests, vitest + @testing-library/react for the frontend state-machine tests. Domain and contract suites run without GPU/network (Constitution Quality Gate §7). Mock detector/embedder are fixture-controllable for rejection paths.

**Target Platform**: Linux container runtime (Docker) for all services; browser (Chrome/Edge latest) with a secure context (`localhost` or HTTPS) for camera access.

**Project Type**: web-service (three-tier), monorepo with `backend/` and `frontend/`. Inherited from spec 001.

**Performance Goals**: Demo-grade only (PRD §13: onboarding < 5s local excluding model load). No SLOs. Mock adapters have negligible latency.

**Constraints**: No GPU, no network, no real ML models required to develop or test (Constitution Principle VII, Quality Gate §7). All-or-nothing persistence: if any step after identifier/consent validation fails, no `User` and no `FaceTemplate` are committed (FR-008). Error responses must not reveal embeddings or internal details (FR-016).

**Scale/Scope**: 2 domain entities touched (`User`, `FaceTemplate`), 1 HTTP endpoint filled with real logic (`POST /api/onboarding`), 1 frontend page built out, 7 onboarding UI states, ~3 new domain modules (validation, image handling, onboarding use-case). Single-tenant demo; no scale targets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ PASS | Mock adapters retained (SC-010); no real ML, no rate limiting, no liveness, no audit log. Image retained on FS is an explicit demo decision (spec Assumptions). YAGNI applied: no orientation normalization, no encryption-at-rest. |
| II. Spec-Driven Workflow | ✅ PASS | This plan is produced from `spec.md` derived from PRD §10 Fase 2; tasks will follow. |
| III. Tech Stack (Python+React+Open-Source ML) | ✅ PASS | FastAPI + React/Vite + PostgreSQL. No ML models integrated (mocks only); real open-source model choice deferred to Fase 5. Pillow is an open-source image library, not an ML model. |
| IV. Containerized Execution (Docker Compose) | ✅ PASS | Reuses the spec 001 compose stack; `usuarios/` bind mount already present. No topology change. |
| V. Local FS Image Storage `usuarios/<user-id>/pictures.jpg` | ✅ PASS | Reuses the spec 001 `FilesystemImageStorage` adapter and `usuarios/` bind mount (FR-009). No object storage. |
| VI. PostgreSQL for Embeddings/Features | ✅ PASS | Reuses the spec 001 schema/migration. `users.identifier` `UNIQUE` constraint already present — enforces case-insensitive duplicate detection on the normalized value (FR-002). `FaceTemplate` stored atomically with `User` (FR-008). |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | The onboarding domain use-case depends only on the ports (`Detector`, `Embedder`, `UserRepository`, `FaceTemplateRepository`, `ImageStorage`) declared in spec 001 (FR-017, SC-007). The route handler is an HTTP adapter; the DB/fs adapters are infra adapters. The domain package imports no ML library, no SQLAlchemy, no FastAPI (enforced by the existing `test_domain_purity` static check, extended in this spec). |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS | No hardening introduced. Error messages are actionable but non-revealing (FR-014/FR-016) — this is a demo-UX concern, not a security guarantee. The unique constraint prevents duplicate profiles for correctness, not as an identity guarantee. No audit log, no rate limiting, no liveness. |

**Open Questions status**: OQ-1 (FastAPI), OQ-2 (Vite), OQ-7 (Alembic), OQ-8 (JPEG ≤2MB ≤640px) resolved to constitution defaults in spec 001 and inherited. OQ-6 (cosine threshold) not exercised in this spec (login is spec 003). OQ-4/OQ-5 (model choices) not exercised — mocks only. This spec adds a `quality_threshold` config (env-overridable, default `0.5`) per the pinned clarify decision — a PATCH-level config addition, not an OQ resolution.

**Pinned decisions (from orchestrator clarify gate)** — all reflected in research.md, data-model.md, contracts/, and quickstart.md:
1. `User.status = "enrolled"`; `User` + `FaceTemplate` created atomically (all-or-nothing rollback on failure).
2. Error response shape `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}` with stable machine codes (`identifier_invalid`, `identifier_taken`, `consent_required`, `invalid_image`, `no_face`, `multiple_faces`, `insufficient_quality`, `internal_error`).
3. Identifier normalization: trim + lowercase; DB unique constraint on normalized identifier catches concurrent duplicates.
4. `FaceTemplate.modelVersion = "mock-embedder-v1"` for the mock adapter.
5. Config via pydantic `Settings`/env vars: 2 MB max image, 640px long edge, quality threshold 0.5.
6. Image resized on backend before storage at `usuarios/<user-id>/pictures.jpg`.

**Contract evolution note (strict-mode flag)**: Spec 001's stub onboarding endpoint returned FastAPI-default `{"detail": ...}` errors. Spec 002 replaces this with the pinned `{"error": {"code", "message"}}` shape. This is a **deliberate, authorized contract evolution** (the spec 001 contract was explicitly a stub with "enforcement deferred to spec 002"; the clarify gate pinned the real shape). The spec 002 contract tests assert the new shape; spec 001's stub contract tests are superseded. No downstream consumer exists (login is spec 003, not yet implemented).

**Gate result**: PASS — no violations, no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/002-onboarding-flow/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   └── onboarding.md    # real POST /api/onboarding contract (supersedes spec 001 stub)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml               # + Pillow dependency
├── alembic/versions/
│   └── 0002_onboarding_normalization.py  # unique index on lower(identifier) if needed
│       # (the existing UNIQUE(identifier) suffices since we store normalized; migration
│       #  is a no-op or adds a citext/functional index — see research R-4)
├── src/face_insight/
│   ├── config.py                # + quality_threshold: float = 0.5
│   ├── domain/
│   │   ├── entities.py          # unchanged (factories reused; normalization happens in service)
│   │   ├── ports.py             # repo ports made async (Detector/Embedder stay sync)
│   │   ├── validation.py        # NEW: identifier format + normalization, consent validation
│   │   ├── image_handling.py    # NEW: decode, size/format limits, long-edge resize (Pillow)
│   │   └── onboarding.py        # NEW: OnboardingService use-case (port-only deps, async)
│   ├── adapters/
│   │   ├── mock/
│   │   │   ├── constants.py     # EMBED_MODEL_VERSION -> "mock-embedder-v1"
│   │   │   ├── detector.py      # + fixture-controllable variant for rejection tests
│   │   │   └── ...              # other mocks unchanged
│   │   ├── db/
│   │   │   ├── repositories.py  # async (already async); add unit-of-work / atomic save
│   │   │   └── ...
│   │   └── fs/
│   │       └── image_storage.py # unchanged (store receives already-resized bytes)
│   └── api/
│       ├── schemas.py           # + ErrorResponse {error: {code, message}}, OnboardingError
│       └── routes/
│           └── onboarding.py    # REPLACED: real orchestration via OnboardingService
└── tests/
    ├── unit/                    # NEW: test_validation, test_image_handling, test_onboarding_service
    ├── contract/test_http_contracts.py  # updated onboarding assertions (new error shape)
    ├── domain/test_domain_purity.py     # extended: assert onboarding.py imports no infra/ML
    └── integration/test_onboarding.py   # NEW: real DB + fs + mock detector/embedder

frontend/
└── src/
    ├── pages/Onboarding.tsx     # REPLACED: real page (identifier, consent, camera, states)
    ├── hooks/useOnboardingMachine.ts  # NEW: PRD §6.2 state machine
    ├── components/CameraCapture.tsx   # NEW: getUserMedia preview + still capture
    └── services/api.ts          # + onboarding() multipart upload helper
```

**Structure Decision**: Web-application layout inherited from spec 001 (Option 2). The new domain modules (`validation.py`, `image_handling.py`, `onboarding.py`) live under `backend/src/face_insight/domain/` and have zero imports from `adapters`, `api`, ML libraries, Pillow, or SQLAlchemy — `image_handling.py` is the one exception (it imports Pillow for decode/resize), so it is classified as a **domain-adjacent service** invoked by the use-case; the pure domain decision (exactly-one-face, quality-threshold, all-or-nothing) lives in `onboarding.py` which imports only ports + entities + result types. The `domain/` package purity check (`test_domain_purity`) is scoped to `onboarding.py` + `entities.py` + `result_types.py` + `validation.py` (the decision logic); `image_handling.py` is an infrastructure-adjacent utility excluded from the purity gate with a documented justification (see research R-3).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
