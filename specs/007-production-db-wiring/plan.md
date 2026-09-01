# Implementation Plan: Production DB Wiring + APP_MODE Selector

**Branch**: `007-production-db-wiring` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-production-db-wiring/spec.md`

## Summary

Introduce a configuration-driven adapter selector (`APP_MODE=production|mock`, default `mock`) that runs once at startup (composition time). In `production` mode the app wires the pre-existing real SQLAlchemy DB adapters (`UserRepository`, `FaceTemplateRepository`, `SessionManager`, `UnitOfWork`) to PostgreSQL while keeping the mock ML adapters (real ML is deferred to specs 008/009); in `mock` mode the app wires the exact same mock adapters as specs 001-006 (backward compatible). Production mode constructs the async DB session factory from `DATABASE_URL`, runs Alembic migrations to head as a pre-start entrypoint step, fails fast on a missing/unreachable/malformed `DATABASE_URL`, and makes the `/health` probe DB-aware. The docker-compose backend service is gated on PostgreSQL healthy and sets `APP_MODE=production`. Integration tests use a real PostgreSQL test container and assert cross-request + cross-restart persistence of `User`/`FaceTemplate`/`AuthSession`. No new endpoints, entities, ports, mock-adapter changes, frontend changes, or existing-test changes are introduced.

## Technical Context

**Language/Version**: Python 3.11 (backend); React + Vite (frontend, unchanged this spec)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async + asyncpg), Alembic, Pydantic v2 / pydantic-settings, httpx (test client), pytest + pytest-asyncio. New test-only dependency: `testcontainers` (Python) for the production-persistence integration tests.

**Storage**: PostgreSQL 16 (dockerized) for `User`/`FaceTemplate`/`AuthSession`/`AnalysisRequest` in production mode; local filesystem `usuarios/<user-id>/pictures.jpg` for images (unchanged). Mock mode uses in-memory repositories (no DB).

**Testing**: pytest (domain/contract/unit, no GPU/network) + pytest-asyncio; integration tests against a real PostgreSQL test container (testcontainers-python), skippable via `RUN_PROD_PERSISTENCE_TESTS=0` / Docker-unavailable.

**Target Platform**: Linux container (Docker Compose); dev host via `docker compose up`.

**Project Type**: web-service (FastAPI backend + React frontend).

**Performance Goals**: Demo-grade only (no real-time SLO). Startup fail-fast must surface misconfiguration before serving traffic.

**Constraints**: `APP_MODE` default `mock` (backward compatible). `DATABASE_URL` must be `postgresql+asyncpg://...`. No images/embeddings/biometrics in logs (structured JSON only). No new HTTP endpoints, domain entities, ports, or frontend changes.

**Scale/Scope**: Single demo deployment; pure composition/wiring spec — no new domain logic.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I — Demo-First / YAGNI | Spec is pure composition/wiring between two already-existing adapter sets. No new features beyond the selector + production session factory + migration gating. `APP_MODE` default `mock` preserves the primary demo path. No scope creep. | PASS |
| II — Spec-Driven Workflow | This plan follows spec → plan → tasks → implement. Builds on specs 001-006. | PASS |
| III — Technology Stack | Python + FastAPI + SQLAlchemy + Alembic + PostgreSQL + React/Vite — all fixed by constitution. `testcontainers` is a test-only tool, not a stack change. | PASS |
| IV — Containerized Execution | `docker compose up` remains canonical; backend gated on PostgreSQL healthy; `APP_MODE=production` set in compose. | PASS |
| V — Filesystem Image Storage | Unchanged — `usuarios/<user-id>/pictures.jpg` reused via the existing `FilesystemImageStorage` adapter (wired in production mode). | PASS |
| VI — PostgreSQL + Migrations | Migrations run as a pre-start entrypoint step gated on `APP_MODE=production`; documented `make migrate`/`alembic upgrade head` fallback for host-native. | PASS |
| VII — Hexagonal / Ports-and-Adapters | Selector chooses adapters at composition time (once at startup). No domain import of concrete adapters; all behind existing ports. Mocks retained for dev/tests. | PASS |
| VIII — No Security/Traceability/Identity | Fail-fast startup + DB health ping are operational, not security hardening. No audit log/event store introduced. No new guarantees. | PASS |
| Quality Gates §5/§6/§7 | Contract tests unchanged (mock). New integration tests exercise real PostgreSQL (§6). Domain/contract/unit run without GPU/network (§7); prod-persistence tests skippable with a documented flag. | PASS |

**Violations**: None. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/007-production-db-wiring/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   ├── wiring-selector.md
│   ├── startup-migration.md
│   └── health-probe.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/face_insight/
│   ├── config.py                      # + app_mode setting (APP_MODE env, default "mock", validated)
│   ├── main.py                        # + wire_production_adapters(), select_wiring(), create_app() uses selector; /health mode-aware
│   ├── adapters/
│   │   ├── db/
│   │   │   ├── session.py             # reused: get_engine()/get_session_factory() from DATABASE_URL
│   │   │   ├── repositories.py         # reused verbatim: SqlAlchemy{User,FaceTemplate}Repository, SqlAlchemyUnitOfWork
│   │   │   └── session_manager.py      # reused verbatim: SqlAlchemySessionManager
│   │   ├── mock/                       # reused verbatim (unchanged)
│   │   └── fs/image_storage.py         # reused verbatim (FilesystemImageStorage wired in production)
│   ├── api/routes/                    # unchanged (no new endpoints)
│   └── domain/                        # unchanged (no new entities/ports)
├── alembic/                            # reused; env.py reads DATABASE_URL from settings
├── tests/
│   ├── integration/
│   │   └── test_production_wiring.py  # NEW: real PostgreSQL test container, cross-request + cross-restart persistence
│   ├── unit/
│   │   └── test_wiring_selector.py    # NEW: select_wiring mock/production/invalid; APP_MODE validation
│   └── ...                            # existing domain/contract/unit suites unchanged
└── Dockerfile                         # entrypoint migration gating (APP_MODE=production)

docker-compose.yml                     # backend: + APP_MODE=production, migration gated on APP_MODE
```

**Structure Decision**: Web-application layout (Option 2) — existing `backend/` + `frontend/` monorepo. This spec touches only `backend/` (config, main, new tests) and `docker-compose.yml`; `frontend/` is unchanged (scope boundary).

## Complexity Tracking

> No constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
