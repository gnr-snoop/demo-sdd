# Data Model: Production DB Wiring + APP_MODE Selector

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Scope

This spec introduces **no new domain entities and no schema changes**. It is pure composition/wiring: it selects between two already-existing adapter sets and ensures the real DB session factory is constructed from `DATABASE_URL` in production mode. The `User`, `FaceTemplate`, and `AuthSession` entities (and `AnalysisRequest`) are pre-existing from specs 001-003, persisted via the pre-existing SQLAlchemy ORM models and Alembic migrations, and are **reused as-is** (FR-012, FR-017).

This document records the two **non-domain** configuration/infrastructure surfaces the spec adds, for completeness.

---

## Entities (unchanged — reused from specs 001-003)

### User (from spec 002, unchanged)
The registered person. In production mode, persisted to and retrieved from PostgreSQL via the real `SqlAlchemyUserRepository`. No new attributes; no schema change.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| id | UUID (v4) | spec 002 | PK |
| identifier | str | spec 002 | normalized email, unique |
| created_at | datetime | spec 002 | |

### FaceTemplate (from spec 002, unchanged)
The stored facial embedding. In production mode, persisted/retrieved via `SqlAlchemyFaceTemplateRepository`. No new attributes.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| id | UUID | spec 002 | PK |
| user_id | UUID | spec 002 | FK → users |
| embedding | list[float] | spec 002 | 128-dim (mock) |
| model_version | str | spec 002 | |
| created_at | datetime | spec 002 | |

### AuthSession (from spec 003, unchanged)
The authenticated session. In production mode, persisted/retrieved via `SqlAlchemySessionManager`. No new attributes.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| id | UUID | spec 003 | PK (carried in signed cookie) |
| user_id | UUID | spec 003 | FK → users |
| created_at / expires_at / revoked_at | datetime | spec 003 | lifecycle |

### AnalysisRequest (from spec 001, unchanged)
Optional audit-shaped row; unchanged this spec.

---

## Configuration Surface (new — not a domain entity)

### APP_MODE setting

A **process-level configuration value** read from the environment at startup. Not persisted; selects the adapter wiring at composition time. Lives in `config.Settings`, not the domain layer (Constitution Principle VII).

| Attribute | Type | Default | Allowed | Env var | Validation |
|-----------|------|---------|---------|---------|------------|
| `app_mode` | `str` | `"mock"` | `{"production", "mock"}` | `APP_MODE` | `.strip().lower()` then reject if not in allowed set → `ValueError` at settings construction (fail-fast, FR-005) |

**State transitions**: none — read once at startup, fixed for the process lifetime (FR-002).

**Backward compatibility**: default `mock` → behavior identical to specs 001-006 when unset (FR-001, FR-003).

### DATABASE_URL (pre-existing, now validated in production)

| Attribute | Type | Default | Env var | Validation |
|-----------|------|---------|---------|------------|
| `database_url` | `str` | `postgresql+asyncpg://faceinsight:faceinsight@localhost:5432/faceinsight` | `DATABASE_URL` | In production mode: must be a reachable async SQLAlchemy URL (`postgresql+asyncpg://...`); validated via engine creation + startup `SELECT 1` probe → fail-fast `RuntimeError` (FR-006). In mock mode: unused. |

---

## Infrastructure (new — not a domain entity)

### Database Session Factory

Constructed only in production mode from `DATABASE_URL` via `adapters.db.session.get_session_factory()`:

| Component | Type | Notes |
|-----------|------|-------|
| engine | `AsyncEngine` | `create_async_engine(database_url, pool_pre_ping=True)` |
| session_factory | `async_sessionmaker[AsyncSession]` | `async_sessionmaker(engine, expire_on_commit=False)` |
| db_engine on app.state | `AsyncEngine \| None` | set in production; `None` in mock; used by health probe + lifespan dispose |

Shared by `SqlAlchemyUserRepository`, `SqlAlchemyFaceTemplateRepository`, `SqlAlchemySessionManager`, `SqlAlchemyUnitOfWork` for all persistence operations.

---

## Adapter Selection (wiring matrix)

| APP_MODE | UserRepository | FaceTemplateRepository | SessionManager | UnitOfWork | ImageStorage | Detector/Embedder/Age/Mood | DB engine | Migrations |
|-----------|----------------|----------------------|----------------|------------|--------------|---------------------------|-----------|------------|
| `mock` (default) | `MockUserRepository` | `MockFaceTemplateRepository` | `MockSessionManager` | `MockUnitOfWork` (deletion only) | `MockImageStorage` | `Mock*` | none | skipped |
| `production` | `SqlAlchemyUserRepository` | `SqlAlchemyFaceTemplateRepository` | `SqlAlchemySessionManager` | `SqlAlchemyUnitOfWork` | `FilesystemImageStorage` | `Mock*` (real ML in 008/009) | async from `DATABASE_URL` | `alembic upgrade head` (entrypoint) |

**Selection runs once at composition time** (Constitution Principle VII, FR-002). No per-request selection.

---

## Validation Rules (from requirements)

- **VR-1** (FR-005): `APP_MODE` not in `{production, mock}` after normalization → startup fails with actionable error listing allowed values.
- **VR-2** (FR-006): `APP_MODE=production` + `DATABASE_URL` unset/malformed/sync-only/unreachable → startup fails fast before serving traffic.
- **VR-3** (FR-007): `APP_MODE=mock` → no DB connection or migration attempted.
- **VR-4** (FR-008/FR-009): `APP_MODE=production` → onboarding commits `User`+`FaceTemplate`; face-login commits `AuthSession`; data survives an app restart against the same PostgreSQL.
- **VR-5** (FR-012/FR-017): no new entity/port/endpoint/frontend/mock-adapter changes.

## State Transitions

None at the domain level. The only state machine is the process startup sequence (production mode):

```
load Settings (validate APP_MODE, DATABASE_URL)
  → if production: build engine + session_factory → SELECT 1 probe (fail-fast) → (migrations run in entrypoint before this) → wire_production_adapters → build app
  → if mock: wire_mock_adapters → build app
  → select_wiring caches result on app.state for process lifetime
```
