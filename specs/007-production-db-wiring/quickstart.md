# Quickstart: Production DB Wiring + APP_MODE Selector

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

Runnable validation scenarios that prove the feature works end-to-end. No full implementation code — commands and expected outcomes only.

## Prerequisites

- Docker (for the compose stack and the PostgreSQL test container).
- Repo root: `D:\Snoop\demo-sdd`.
- Backend deps installed: `pip install -e ".[test]"` (includes `testcontainers`).

## Scenario 1 — Mock mode unchanged (backward compatible)

**Goal**: `APP_MODE` unset → app behaves as specs 001-006, no PostgreSQL required.

```bash
# From backend/, no DB running:
APP_MODE=mock uvicorn face_insight.main:app --host 0.0.0.0 --port 8000
# (or simply unset APP_MODE)
```

**Expected**:
- App starts; `GET /health` → `200 {"status":"healthy"}` (no `db` field).
- No PostgreSQL connection attempted.
- Existing domain/contract/unit suites pass unchanged:
  ```bash
  pytest backend/tests/domain backend/tests/contract backend/tests/unit -q
  ```

## Scenario 2 — Production mode via docker compose (one-command path)

**Goal**: `docker compose up` → working production stack with real PostgreSQL persistence.

```bash
docker compose up --build
# wait for backend healthy
curl http://localhost:8000/health
```

**Expected**:
- PostgreSQL starts; backend waits until `pg_isready` reports healthy.
- Entrypoint runs `alembic upgrade head` (gated on `APP_MODE=production`), then starts uvicorn.
- `GET /health` → `200 {"status":"healthy","db":true}`.
- Onboarding → face-login → `GET /api/auth/me` all succeed against PostgreSQL.

## Scenario 3 — Fail-fast: invalid APP_MODE

**Goal**: unrecognized `APP_MODE` fails at startup.

```bash
APP_MODE=staging uvicorn face_insight.main:app --host 0.0.0.0 --port 8000
```

**Expected**: process exits with `ValueError: APP_MODE must be 'production' or 'mock'; got 'staging'` before serving traffic.

## Scenario 4 — Fail-fast: production with no DATABASE_URL

**Goal**: `APP_MODE=production` + unreachable DB fails at startup.

```bash
APP_MODE=production DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/nope" \
  uvicorn face_insight.main:app --host 0.0.0.0 --port 8000
```

**Expected**: process exits with `RuntimeError: APP_MODE=production requires a reachable DATABASE_URL; got ...` before serving traffic.

## Scenario 5 — Cross-request + cross-restart persistence (automated)

**Goal**: real PostgreSQL test container proves data persists across requests and across an app restart.

```bash
# Requires Docker (for the test container):
RUN_PROD_PERSISTENCE_TESTS=1 pytest backend/tests/integration/test_production_wiring.py -q
```

**Expected**:
- A real PostgreSQL container starts (session-scoped), migrations apply.
- `POST /api/onboarding` commits `User` + `FaceTemplate`; `POST /api/auth/face-login` commits `AuthSession`; `GET /api/auth/me` reads the session — all from PostgreSQL (verified out-of-band).
- A **second** app instance built against the same DB (simulating a process restart) resolves `GET /api/auth/me` with the first app's session cookie → same user (cross-restart persistence, FR-009).

**Skip when no Docker**:
```bash
RUN_PROD_PERSISTENCE_TESTS=0 pytest backend/tests/integration/test_production_wiring.py -q
# → tests skip with a documented reason; domain/contract/unit suites still run
```

## Scenario 6 — Wiring selector unit tests (no DB)

**Goal**: selector wires the correct adapter set per mode; invalid mode fails fast.

```bash
pytest backend/tests/unit/test_wiring_selector.py -q
```

**Expected**: `mock` wires `Mock*` repos + no `db_engine`; `production` wires `SqlAlchemy*` repos + mock ML + `db_engine`; invalid `APP_MODE` raises `ValueError`.

## Scenario 7 — Non-regression (existing suites unchanged)

**Goal**: specs 001-006 domain/contract/unit suites pass without modification.

```bash
pytest backend/tests/domain backend/tests/contract backend/tests/unit -q
```

**Expected**: all green (FR-013). No test file in those directories is modified by this spec.

## Scenario 8 — Deliberate regression is caught

**Goal**: making `APP_MODE=production` wire in-memory repos causes a production-persistence test to fail.

1. Temporarily edit `select_wiring` so `production` delegates to `wire_mock_adapters`.
2. `RUN_PROD_PERSISTENCE_TESTS=1 pytest backend/tests/integration/test_production_wiring.py -q`
3. **Expected**: the cross-restart or out-of-band DB inspection assertion fails (FR-014).
4. Revert the edit.
