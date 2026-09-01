# Face Insight Backend

FastAPI backend for the Face Insight Demo. Hexagonal architecture (ports &
adapters) with a configuration-driven adapter selector (`APP_MODE`).

## Configuration

### `APP_MODE` (spec 007)

Selects the adapter wiring at startup (composition time). Read from the
`APP_MODE` environment variable.

| Value | Behavior |
|-------|----------|
| `mock` (default, or unset) | In-memory mock adapters — no PostgreSQL required. Backward compatible with specs 001-006. |
| `production` | Real SQLAlchemy DB adapters (PostgreSQL) + mock ML adapters. Requires a reachable `DATABASE_URL`. |

Normalization: the value is `.strip().lower()`'d before validation, so
`APP_MODE=Production` and `APP_MODE=" mock "` are accepted.

Invalid values (e.g. `staging`, `prod`, `demo`) fail fast at startup with:
```
ValueError: APP_MODE must be 'production' or 'mock'; got '<value>'
```

`APP_MODE=production` with an unset/unreachable/malformed `DATABASE_URL` fails
fast at startup with:
```
RuntimeError: APP_MODE=production requires a reachable DATABASE_URL; got <value>
```

### `DATABASE_URL`

Async SQLAlchemy connection string for PostgreSQL. Required in `production`
mode; unused in `mock` mode.

```
DATABASE_URL=postgresql+asyncpg://faceinsight:faceinsight@localhost:5432/faceinsight
```

A sync-only scheme (e.g. `postgresql://` without `+asyncpg`) fails fast at
startup.

## Running

### Mock mode (dev/demo — no DB)

```bash
# From backend/:
APP_MODE=mock uvicorn face_insight.main:app --host 0.0.0.0 --port 8000
# or simply unset APP_MODE (default is mock)
```

### Production mode (docker compose — one command)

```bash
docker compose up --build
```

The compose stack sets `APP_MODE=production` on the backend, waits for
PostgreSQL healthy, runs `alembic upgrade head` (gated on `APP_MODE=production`),
then starts uvicorn.

### Migrations (manual fallback)

```bash
# From backend/:
make migrate          # alembic upgrade head
make migrate-down     # alembic downgrade -1 (rollback one revision)
```

Or directly:
```bash
alembic upgrade head
```

Migrations are gated on `APP_MODE=production` in the docker-compose entrypoint
(skipped in mock mode — no DB required).

## Health Probes

Both probes are mode-aware (the `db` field appears only in production mode):

| Endpoint | Mock | Production (DB up) | Production (DB down) |
|----------|------|--------------------|----------------------|
| `GET /health` | `200 {"status":"healthy"}` | `200 {"status":"healthy","db":true}` | `503 {"status":"unhealthy","db":false}` |
| `GET /readyz` | `200 {"status":"ready","db":null}` | `200 {"status":"ready","db":true}` | `503 {"status":"unavailable","db":false}` |

## Testing

### Domain / contract / unit (no GPU, no network, no DB)

```bash
pytest tests/domain tests/contract tests/unit -q
```

### Wiring selector unit tests (no DB for mock/invalid cases)

```bash
pytest tests/unit/test_wiring_selector.py -q
```

### Production-persistence integration tests (require Docker)

```bash
RUN_PROD_PERSISTENCE_TESTS=1 pytest tests/integration/test_production_wiring.py -q
```

These spin up a real PostgreSQL test container and verify cross-request +
cross-restart persistence of `User` / `FaceTemplate` / `AuthSession`.

**Skip flag**: set `RUN_PROD_PERSISTENCE_TESTS=0` or run without Docker to skip
with a documented reason:

```bash
RUN_PROD_PERSISTENCE_TESTS=0 pytest tests/integration/test_production_wiring.py -q
```

### Full suite

```bash
pip install -e ".[test]"
pytest -q
```

## Project structure

```
src/face_insight/
├── config.py          # Settings (APP_MODE, DATABASE_URL, ...)
├── main.py            # create_app(), select_wiring(), wire_{mock,production}_adapters()
├── adapters/
│   ├── db/            # SqlAlchemy* adapters (real PostgreSQL)
│   ├── mock/          # Mock* adapters (deterministic, no GPU/network)
│   └── fs/            # FilesystemImageStorage
├── api/routes/        # HTTP endpoints (unchanged by APP_MODE)
└── domain/            # Domain entities, services, ports (unchanged by APP_MODE)
```
