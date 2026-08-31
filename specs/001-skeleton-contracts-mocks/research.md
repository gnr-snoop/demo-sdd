# Research: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

## Research Tasks

### R-1: FastAPI project layout for hexagonal (ports-and-adapters) architecture

**Decision**: Single `backend/` Python package (`face_insight`) with three top-level subpackages: `domain/` (entities, result types, port protocols — pure, no infra imports), `adapters/` (mock, db, fs implementations of ports), and `api/` (FastAPI routes, Pydantic schemas, dependencies). Composition (wiring adapters to ports) happens in `main.py` at app startup, not in the domain.

**Rationale**: FastAPI's dependency-injection system composes cleanly with hexagonal ports declared as `typing.Protocol`. Keeping `domain/` import-free of `adapters/` and `api/` makes SC-004 (zero infra imports) statically checkable via a simple import-linter rule or test. This is the standard FastAPI hexagonal layout and matches Constitution Principle VII.

**Alternatives considered**:
- *Clean Architecture concentric packages* (`usecases/`, `interfaces/`, `infrastructure/`): heavier naming, no benefit for a demo of this size. Rejected (Principle I — demo-first).
- *Flat package with `models.py` + `services.py`*: violates Principle VII (domain would import infra). Rejected.

### R-2: Pydantic v2 vs v1 for request/response schemas and validation

**Decision**: Pydantic v2.

**Rationale**: Pydantic v2 is the current default for FastAPI ≥ 0.100, delivers ~10× validation speed (Rust core), and uses the same `BaseModel` API surface needed here. No v1-specific features are required. Constitution OQ-1 default (FastAPI) implies the modern FastAPI stack.

**Alternatives considered**: Pin Pydantic v1 for familiarity — rejected (ecosystem has moved on; v2 is the FastAPI default and reduces demo drift).

### R-3: SQLAlchemy 2.0 async + Alembic migration setup

**Decision**: SQLAlchemy 2.0 async ORM (`AsyncSession`) with `psycopg` (async) driver; Alembic with an `env.py` configured for async + autogenerate. One initial revision `0001_initial_schema.py` creating the four tables. Migrations run as a compose entrypoint step before Uvicorn starts (documented `make migrate` equivalent: `alembic upgrade head`).

**Rationale**: Constitution OQ-7 default is Alembic. Async SQLAlchemy matches FastAPI's async model and avoids thread-pool bridging. A single initial migration is sufficient for Fase 1 (schema only, no data). Idempotency (SC-006) is Alembic's default behavior — `upgrade head` is a no-op when already at head.

**Alternatives considered**:
- *Raw SQL migrations*: loses ORM alignment and autogenerate; rejected (OQ-7 default).
- *Sync SQLAlchemy*: blocks the event loop under FastAPI; rejected.

### R-4: UUID v4 primary keys — column type and generation strategy

**Decision**: All `id` and `userId` columns are PostgreSQL `UUID` type (SQLAlchemy `Uuid` / `PGUuid`). Application-side generation via `uuid.uuid4()` in the domain entity factories / mock adapters (fixed constants in tests). The DB does **not** default-generate IDs — the domain owns identity creation (hexagonal principle: the domain decides identity, the DB only persists). A `CHECK` is unnecessary; `UUID` column type enforces format.

**Rationale**: Pinned at the clarify gate. UUID v4 is opaque (no sequential-id enumeration risk), standard for face-template identifiers, and a native PostgreSQL type with index support. Domain-owned generation keeps the domain testable without a DB and lets mock adapters return fixed constants (SC-005 determinism). Storing as `UUID` (not `TEXT`) gives validation + 16-byte storage + native indexing.

**Alternatives considered**:
- *DB-side `gen_random_uuid()` default*: violates domain-owns-identity and breaks mock determinism (DB would generate, not the mock). Rejected.
- *Store as `TEXT`*: loses native UUID validation/indexing; rejected.
- *Sequential integer IDs*: enumeration risk, conflicts with the pinned decision. Rejected.

### R-5: Mock adapter determinism strategy

**Decision**: Every mock adapter returns **hardcoded constant outputs** — no RNG, no seed, no clock-dependent values. Timestamps use a fixed `DATETIME` constant in tests and `datetime.utcnow()` only in non-test wiring (entity factories accept an injected `now` callable). Mock UUIDs are named constants (e.g. `FIXED_USER_ID = UUID("00000000-0000-4000-8000-000000000001")`).

**Rationale**: Spec Clarification resolved this: hardcoded constants maximize determinism and make SC-005 (byte-identical across repeated runs) trivially assertable. Injecting a `now` callable is a standard hexagonal testing pattern that keeps entities pure.

**Alternatives considered**: Fixed random seed (`random.seed(42)`) — rejected (still order-dependent and harder to assert than literal constants; spec explicitly chose hardcoded).

### R-6: Frontend routing + placeholder route protection

**Decision**: `react-router-dom` v6 with four routes (`/`, `/onboarding`, `/login`, `/dashboard`). A `ProtectedRoute` wrapper reads an in-memory `SessionContext` (React context holding a boolean `isAuthenticated` flag) and redirects to `/login` when false. No cookie/header/session API call in this spec — the flag is toggled in-memory only (spec Clarification: real session wiring deferred to spec 003).

**Rationale**: Simplest thing that satisfies FR-003/FR-004 and prevents rework in Fase 3. React Router is the standard Vite+React routing solution. An in-memory context flag is the minimal placeholder that compiles and tests now.

**Alternatives considered**:
- *Read a real cookie / call `/api/auth/me`*: real session enforcement, out of scope for Fase 1 (deferred to spec 003). Rejected.
- *No route protection now*: violates FR-004 and forces rework later. Rejected.

### R-7: Structured JSON logging + health/readiness endpoint

**Decision**: `structlog` configured with a JSON renderer. A single `/health` (liveness, returns `{"status":"healthy"}`) and `/readyz` (readiness, checks DB connectivity, returns `{"status":"ready","db":true}` or `503`). No metrics, tracing, or audit log (spec Clarification; Constitution Principle VIII).

**Rationale**: Constitution Quality Gate / PRD §13 observability is demo-grade. JSON logs are trivially greppable and avoid embedding images/embeddings (PRD §12 — never log biometrics). The readiness probe supports SC-001 (verifying all services healthy).

**Alternatives considered**: OpenTelemetry tracing — rejected (Principle VIII: no traceability guarantee; out of scope for a demo).

### R-8: Docker Compose topology and bind-mount for `usuarios/`

**Decision**: Three services — `backend` (FastAPI/Uvicorn, port 8000), `frontend` (Vite dev server, port 5173), `postgres` (port 5432). A named volume for PG data; a bind mount `./usuarios:/app/usuarios:rw` on the backend so `usuarios/<user-id>/pictures.jpg` is identical inside and outside the container (Principle V). Backend depends_on postgres with a `service_healthy` condition. Migrations run in the backend entrypoint (`alembic upgrade head` then `uvicorn`).

**Rationale**: Constitution Principle IV — compose is the single source of truth. Bind mount (not a named volume) for `usuarios/` is required so the host can inspect images (SC-007). `service_healthy` prevents backend startup races.

**Alternatives considered**: Named volume for `usuarios/` — rejected (host wouldn't see files; breaks SC-007).

### R-9: Image constraints configuration surface

**Decision**: A `config.py` `Settings` class (Pydantic BaseSettings) exposing `verification_threshold: float = 0.5`, `embedding_model_version: str = "mock-embed-v0"`, `detector_model_version: str = "mock-yolo-v0"`, `age_model_version: str = "mock-age-v0"`, `mood_model_version: str = "mock-mood-v0"`, `image_max_bytes: int = 2_000_000`, `image_format: str = "JPEG"`, `image_max_long_edge: int = 640`. Overridable via env vars.

**Rationale**: FR-015 requires threshold, model versions, and image limits as tunable config. Constitution OQ-6 (cosine threshold) and OQ-8 (JPEG ≤2MB ≤640px) defaults. Pydantic BaseSettings gives env-var override for free — no logic implemented, just the config surface.

**Alternatives considered**: Hardcode constants — rejected (FR-015 requires tunability).

## Codebase Context

*(From Step 0 codebase-memory graph inspection)*

- **Existing architecture**: Greenfield. The knowledge graph (443 nodes) contains only PRD/spec/template markdown sections — no Python, TypeScript, or application source code exists yet. Languages detected: YAML (1 config file). No `backend/` or `frontend/` directories.
- **Reuse opportunities**: None — this spec establishes the foundation. The PRD §7 entity definitions and PRD §8 contract shapes in `PRD.md` are the source-of-truth inputs carried into `data-model.md` and `contracts/`.
- **Integration touch-points**: None yet. Downstream specs 002 (onboarding), 003 (login/session), 004 (dashboard/analysis), 005 (real models), 006 (hardening) will build on the skeleton, ports, and contracts established here.
- **Coverage limitations**: N/A — no application source to cover. The spec/template markdown files are fully indexed (0 skipped, 0 parse_partial).

## Summary of Resolved Clarifications

All NEEDS CLARIFICATION items from Technical Context were resolved to constitution defaults or spec-pinned decisions. No items touch security, data privacy, compliance, breaking changes, or public contracts in a way that requires blocking (the UUID PK decision — a public-contract/data-model concern — was **already pinned at the orchestrator clarify gate** and is applied here, not newly auto-resolved). Mode `strict`: no BLOCKING items.

| Item | Resolution | Source |
|------|-----------|--------|
| Python/React versions | Python 3.11 / React 18 + Vite 5 | Constitution Principle III, OQ-1/OQ-2 |
| Web framework | FastAPI | Constitution OQ-1 default |
| Frontend tooling | Vite | Constitution OQ-2 default |
| Migrations tool | Alembic | Constitution OQ-7 default |
| Primary key type | UUID v4 strings, PG `UUID` columns | **Pinned at clarify gate** |
| Mock determinism | Hardcoded constant outputs | Spec Clarification 2026-08-31 |
| Session placeholder | In-memory React context flag | Spec Clarification 2026-08-31 |
| Observability | JSON logs + health/readyz only | Spec Clarification 2026-08-31 |
| Entity status enums | `User.status ∈ {enrolled,active,disabled}`; `AnalysisRequest.status ∈ {pending,completed,failed}` | Spec Clarification 2026-08-31 |
| Image constraints | JPEG ≤2MB ≤640px (config) | Constitution OQ-8 default |
| Distance metric | Cosine similarity, threshold 0.5 (config, no logic) | Constitution OQ-6 default |
