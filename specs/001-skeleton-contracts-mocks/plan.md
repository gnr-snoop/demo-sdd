# Implementation Plan: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Branch**: `001-skeleton-contracts-mocks` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-skeleton-contracts-mocks/spec.md`

## Summary

Establish the runnable foundation of the Face Insight Demo: a fully containerized Docker Compose stack (FastAPI backend, React+Vite frontend, PostgreSQL); four navigable frontend views with a placeholder route-protection guard; all seven PRD §8 HTTP contract endpoints exposed as deterministic stub/mock handlers; the four PRD §7 domain entities as pure hexagonal-domain code behind ports with a complete set of deterministic mock adapters; PostgreSQL schema managed by Alembic migrations; and a local-filesystem image-storage adapter under `usuarios/<user-id>/pictures.jpg`. An automated contract + domain test suite runs without GPU or network. **No real business logic** (onboarding, login verification, mood/age inference, deletion) is implemented — all deferred to specs 002–006.

## Technical Context

**Language/Version**: Python 3.11 (backend); TypeScript 5.x / React 18 / Vite 5 (frontend). Settled by Constitution Principle III + Technology Stack table (OQ-1 FastAPI, OQ-2 Vite defaults).

**Primary Dependencies**:
- Backend: FastAPI, Uvicorn, Pydantic v2 (request/response schemas + validation), SQLAlchemy 2.0 (ORM, async), Alembic (migrations), psycopg (PostgreSQL driver), structlog (structured JSON logs), httpx (test client), pytest + pytest-asyncio (tests).
- Frontend: react, react-dom, react-router-dom (routing/navigation), @vitejs/plugin-react, vitest + @testing-library/react (tests).
- Orchestration: Docker Compose (single `docker-compose.yml`).

**Storage**: PostgreSQL (dockerized) for `User`, `FaceTemplate`, `AuthSession`, `AnalysisRequest` (Constitution Principle VI); local filesystem `usuarios/<user-id>/pictures.jpg` for captured images, bind-mounted into the backend container (Principle V).

**Testing**: pytest (domain + contract + integration), httpx.AsyncClient for contract tests against the FastAPI app, vitest for frontend routing tests. Domain and contract suites run without GPU/network (Constitution Quality Gate §7).

**Target Platform**: Linux container runtime (Docker) for all services; browser (Chrome/Edge latest) for the frontend demo.

**Project Type**: web-service (three-tier: React SPA + FastAPI HTTP API + PostgreSQL), monorepo with `backend/` and `frontend/`.

**Performance Goals**: Demo-grade only (PRD §13: analysis < 5s local). No SLOs in this spec — endpoints are stubs returning deterministic mock responses with negligible latency.

**Constraints**: No GPU, no network, no real ML models required to develop or test (Constitution Principle VII, Quality Gate §7). Fully reproducible from a clean checkout via `docker compose up` (Principle IV). Mock adapters must be byte-identical across runs (SC-005, hardcoded constants — no RNG/seed).

**Scale/Scope**: 4 domain entities, 7 HTTP endpoints, 4 frontend routes, ~8 ports + 8 mock adapters, 1 initial migration. Single-tenant demo; no scale targets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ PASS | Spec is scaffolding only (SC-010 explicitly forbids real logic). YAGNI applied: no rate limiting, no real ML, no audit log. |
| II. Spec-Driven Workflow | ✅ PASS | This plan is produced from `spec.md` derived from PRD §10 Fase 1; tasks will follow. |
| III. Tech Stack (Python+React+Open-Source ML) | ✅ PASS | FastAPI + React/Vite + PostgreSQL. No ML models integrated in this spec (mocks only); real open-source model choice deferred to Fase 5 (specs). |
| IV. Containerized Execution (Docker Compose) | ✅ PASS | FR-001/FR-002 mandate `docker-compose.yml` + per-service Dockerfiles; SC-001 single command. |
| V. Local FS Image Storage `usuarios/<user-id>/pictures.jpg` | ✅ PASS | FR-014 + filesystem adapter + bind mount. No object storage. |
| VI. PostgreSQL for Embeddings/Features | ✅ PASS | FR-013 Alembic migrations for the 4 entities; PostgreSQL in compose. |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | FR-008/FR-009/FR-010: pure domain, declared ports, complete mock adapters. Domain imports no ML/infra (SC-004). |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS | No hardening introduced. Observability limited to JSON logs + health endpoint (spec Clarification). Route protection is a placeholder only. Login failure is generic/non-revealing (FR-007/FR-018) — this is a demo-UX concern, not a security guarantee. |

**Open Questions status**: OQ-1 (FastAPI), OQ-2 (Vite), OQ-3 (server-side session — placeholder only here), OQ-6 (cosine threshold — config only, no logic), OQ-7 (Alembic), OQ-8 (JPEG ≤2MB ≤640px — config only) all resolved to their constitution defaults for this spec. OQ-4/OQ-5 (model choices) not exercised — mocks only.

**Pinned decision (from clarify gate)**: All primary keys (`id`, `userId`) are **UUID v4 strings** stored as PostgreSQL `UUID` columns. The `DELETE /api/users/{userId}/face-data` path parameter is a UUID string. Mock adapters return fixed UUID constants in tests. Reflected in data-model.md, migrations, and contract tests.

**Gate result**: PASS — no violations, no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/001-skeleton-contracts-mocks/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (per-endpoint HTTP contracts)
│   ├── README.md
│   ├── onboarding.md
│   ├── face-login.md
│   ├── auth-me.md
│   ├── logout.md
│   ├── analysis-mood.md
│   ├── analysis-age.md
│   └── delete-face-data.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
docker-compose.yml              # backend + frontend + postgres + usuarios bind mount
backend/
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py   # User, FaceTemplate, AuthSession, AnalysisRequest
├── src/face_insight/
│   ├── main.py                 # FastAPI app, route registration, /health, /readyz
│   ├── config.py               # Settings: threshold, model versions, image limits
│   ├── logging.py              # structlog JSON config
│   ├── domain/
│   │   ├── entities.py         # User, FaceTemplate, AuthSession, AnalysisRequest (pure)
│   │   ├── result_types.py     # DetectionResult, BoundingBox, MoodResult, AgeResult
│   │   └── ports.py            # Protocols: Detector, Embedder, AgeEstimator,
│   │                           #   MoodEstimator, SessionManager, UserRepository,
│   │                           #   FaceTemplateRepository, ImageStorage
│   ├── adapters/
│   │   ├── mock/               # 8 deterministic mock adapters (hardcoded constants)
│   │   ├── db/                 # SQLAlchemy ORM models + repository adapters
│   │   └── fs/                 # filesystem image-storage adapter (usuarios/<id>/pictures.jpg)
│   └── api/
│       ├── schemas.py          # Pydantic request/response models (PRD §8 shapes)
│       ├── dependencies.py     # session-placeholder dependency (protected routes)
│       └── routes/
│           ├── onboarding.py
│           ├── auth.py
│           ├── analysis.py
│           └── users.py
└── tests/
    ├── contract/test_http_contracts.py   # 7 endpoints, shapes + status codes
    ├── domain/                           # entities + mock adapters, no GPU/network
    └── integration/test_stack.py         # health, migrations, fs adapter via compose

frontend/
├── Dockerfile
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── router.tsx              # 4 routes + ProtectedRoute guard
    ├── context/SessionContext.tsx   # in-memory session placeholder flag
    ├── pages/                  # Welcome, Onboarding, Login, Dashboard (placeholders)
    ├── components/             # Nav, ProtectedRoute
    └── services/api.ts         # fetch wrapper for the 7 endpoints

usuarios/                       # bind-mount root (gitkeep); <user-id>/pictures.jpg created at runtime
└── .gitkeep
```

**Structure Decision**: Web-application layout (Option 2 from template) — `backend/` (Python/FastAPI, hexagonal `domain` + `adapters` + `api`) and `frontend/` (React/Vite SPA). The `domain` package has zero imports from `adapters`, `api`, ML libraries, or SQLAlchemy (enforced by SC-004 static inspection). Mock adapters live in `adapters/mock/` and are the default wiring for tests and the Fase 1 stub endpoints. `docker-compose.yml` at repo root is the single source of truth for service topology (Principle IV).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
