# Face Insight Demo

Demo-grade face-insight application: onboarding, face login, mood/age analysis.
This repository contains the **Fase 1 skeleton** — runnable stack, navigation,
HTTP contracts, pure hexagonal domain with deterministic mock adapters, and an
automated contract + domain test suite. No real business logic is implemented
yet (deferred to specs 002–006).

## Quickstart

See [`specs/001-skeleton-contracts-mocks/quickstart.md`](./specs/001-skeleton-contracts-mocks/quickstart.md)
for the full runnable validation scenarios.

### Bring up the stack

```bash
docker compose up --build
```

- Backend (FastAPI): http://localhost:8000  (`/health`, `/readyz`)
- Frontend (React + Vite): http://localhost:5173
- PostgreSQL: localhost:5432

### Verify health

```bash
curl -s http://localhost:8000/health   # {"status":"healthy"}
curl -s http://localhost:8000/readyz   # {"status":"ready","db":true}
```

### Run the test suite

```bash
docker compose exec backend pytest tests/ -v
docker compose exec frontend npm test
```

## Project layout

```
backend/    # FastAPI + SQLAlchemy + Alembic (hexagonal: domain/ adapters/ api/)
frontend/   # React + Vite SPA (4 routes, placeholder route protection)
usuarios/   # bind-mount root: <user-id>/pictures.jpg created at runtime
docker-compose.yml
```

## Architecture

Hexagonal ports-and-adapters (Constitution Principle VII):

- `backend/src/face_insight/domain/` — pure entities, result types, port
  Protocols. **Zero** infra/ML imports (enforced by
  `tests/domain/test_domain_purity.py`, SC-004).
- `backend/src/face_insight/adapters/mock/` — 8 deterministic mock adapters
  (hardcoded constants, SC-005) implementing every port.
- `backend/src/face_insight/adapters/db/` — SQLAlchemy ORM + repository adapters.
- `backend/src/face_insight/adapters/fs/` — filesystem image storage
  (`usuarios/<user-id>/pictures.jpg`).
- `backend/src/face_insight/api/` — FastAPI routes, Pydantic schemas, session
  dependency.

All primary keys are UUID v4 strings (PostgreSQL `UUID` columns); identity is
domain-owned.
