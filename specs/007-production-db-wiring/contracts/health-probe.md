# Contract: Mode-Aware Health & Readiness Probes

**Spec**: [spec.md](../spec.md) | **Type**: refinement of pre-existing infra endpoints (no new endpoint — FR-010)

## `GET /health` (liveness)

| Mode | Behavior | Response body | Status |
|------|----------|---------------|--------|
| `mock` (default) | no DB check | `{"status": "healthy"}` | `200` |
| `production` (DB up) | `SELECT 1` against `app.state.db_engine` | `{"status": "healthy", "db": true}` | `200` |
| `production` (DB down) | ping fails | `{"status": "unhealthy", "db": false}` | `503` |

## `GET /readyz` (readiness)

| Mode | Behavior | Response body | Status |
|------|----------|---------------|--------|
| `mock` | no DB check | `{"status": "ready", "db": null}` | `200` |
| `production` (DB up) | `SELECT 1` | `{"status": "ready", "db": true}` | `200` |
| `production` (DB down) | ping fails | `{"status": "unavailable", "db": false}` | `503` |

## Mode signal

The probes determine whether to ping via the **wired engine** (`app.state.db_engine`), not by re-reading `APP_MODE` per request:
- `wire_mock_adapters` leaves `app.state.db_engine` unset/`None` → no ping.
- `wire_production_adapters` sets `app.state.db_engine` → ping.

This couples the probe to what was actually wired at composition time (Constitution Principle VII) and avoids a per-request settings read.

## Contract assertions (testable)

1. **C-HLTH-1** (FR-010): mock mode → `GET /health` returns `200` with no `db` check; no PostgreSQL required.
2. **C-HLTH-2** (FR-010): production mode + DB up → `GET /health` returns `200` with `db: true`.
3. **C-HLTH-3** (FR-010): production mode + DB down → `GET /health` returns `503` with `db: false`.
4. **C-HLTH-4**: `/readyz` mirrors `/health`'s mode-aware DB-ping behavior.
5. **C-HLTH-5**: no new endpoint is introduced; `/health` and `/readyz` are the pre-existing spec 001 endpoints (refinement only).

## Note

The `/health` body gains a `db` field in production mode. This is an **infra liveness/readiness probe**, not a PRD §8 user-facing contract endpoint. The seven PRD §8 endpoints are unchanged in both modes (FR-012).
