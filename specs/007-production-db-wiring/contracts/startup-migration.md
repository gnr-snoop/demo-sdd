# Contract: Production Startup — DB Session Factory, Migrations & Fail-Fast

**Spec**: [spec.md](../spec.md) | **Type**: operational startup contract (not an HTTP endpoint)

## Startup sequence (production mode)

```
1. load Settings  → validate APP_MODE (FR-005), validate DATABASE_URL presence
2. build async engine + async_sessionmaker from DATABASE_URL  (FR-006)
3. startup DB probe: SELECT 1  → fail-fast RuntimeError if unreachable/malformed  (FR-006)
4. [entrypoint, before step 1] alembic upgrade head  gated on APP_MODE=production  (FR-007)
5. wire_production_adapters(app)  → real DB adapters + mock ML  (FR-004)
6. build app, register routes, attach mode-aware /health + /readyz
7. serve traffic
```

In **mock mode**: steps 2-4 are skipped; `wire_mock_adapters` runs; no DB is required (FR-003).

## `DATABASE_URL`

| Property | Value |
|----------|-------|
| Env var | `DATABASE_URL` |
| Required form | `postgresql+asyncpg://user:password@host:5432/dbname` (async SQLAlchemy URL) |
| Malformed / sync-only scheme (e.g. `postgresql://`) | fail-fast at engine creation / startup probe (FR-006) |
| Unset / empty | fail-fast with `"APP_MODE=production requires a reachable DATABASE_URL; got <value>"` |
| Unreachable | fail-fast at startup `SELECT 1` probe (FR-006) |
| Mock mode | unused |

## Migration gate (entrypoint)

| Property | Value |
|----------|-------|
| Command (compose backend) | `sh -c "if [ \"$APP_MODE\" = \"production\" ]; then alembic upgrade head; fi && uvicorn face_insight.main:app --host 0.0.0.0 --port 8000 --reload"` |
| Gated on | `APP_MODE=production` (FR-007) |
| Already at head | no-op (Alembic) |
| Behind head | applies pending migrations to head before serving |
| Migration failure | entrypoint exits non-zero; app does not start; no partially-migrated app serves |
| Manual fallback | `make migrate` / `alembic upgrade head` (documented, host-native — FR-011) |
| `alembic/env.py` | unchanged (reads `DATABASE_URL` from `get_settings()`) |

## docker-compose production stack

| Property | Value |
|----------|-------|
| `postgres` service | `postgres:16-alpine`, healthcheck `pg_isready` |
| `backend` depends_on | `postgres: condition: service_healthy` (FR-010) |
| `backend` env | `APP_MODE=production`, `DATABASE_URL=postgresql+asyncpg://faceinsight:faceinsight@postgres:5432/faceinsight` |
| One-command path | `docker compose up` → working production stack (FR-011, Principle IV) |

## Contract assertions (testable)

1. **C-START-1** (FR-006): `APP_MODE=production` + unset `DATABASE_URL` → startup fails fast before serving.
2. **C-START-2** (FR-006): `APP_MODE=production` + unreachable DB → startup fails fast at the `SELECT 1` probe.
3. **C-START-3** (FR-006): `APP_MODE=production` + sync-only URL → startup fails fast at engine creation.
4. **C-START-4** (FR-007): `APP_MODE=production` → migrations apply to head before the app serves; `APP_MODE=mock` → no migration/DB step.
5. **C-START-5** (FR-010): compose backend does not start until PostgreSQL reports healthy; `DATABASE_URL` points to the compose Postgres service.
6. **C-START-6** (FR-011): `docker compose up` from clean state → backend `/health` reports healthy with DB connectivity.
