# Contracts: Production DB Wiring + APP_MODE Selector (Fase 5 foundation)

**Spec**: [spec.md](../spec.md) | **Status**: composition/wiring — no new HTTP endpoints, no new domain entities/ports, no frontend changes.

This spec is **pure composition**: it selects between two already-existing adapter sets at startup and ensures the real DB session factory is built from `DATABASE_URL` in production mode. It introduces **no new PRD §8 HTTP contracts** and **no changes to existing PRD §8 contracts** — the seven endpoints (`POST /api/onboarding`, `POST /api/auth/face-login`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`) are served identically in both modes (FR-012).

The contracts documented here are the **non-PRD-§8 operational interfaces** the spec does define or refine:

| File | Interface | Purpose |
|------|-----------|---------|
| [wiring-selector.md](./wiring-selector.md) | `select_wiring(app, app_mode)` + `APP_MODE` setting | Configuration-driven adapter selection at composition time |
| [startup-migration.md](./startup-migration.md) | Entrypoint migration gate + `DATABASE_URL` fail-fast | Production startup sequence: migrations + DB session factory + fail-fast |
| [health-probe.md](./health-probe.md) | `GET /health`, `GET /readyz` | Mode-aware liveness/readiness (DB ping in production, none in mock) |

## Shared conventions

- **No PRD §8 contract changes.** All seven user-facing endpoints keep their existing request/response shapes, status codes, and error bodies (`{"error": {"code", "message"}}`) from specs 002-006, in both modes. The frontend is unaware of `APP_MODE`.
- **Fail-fast errors** use actionable messages: `"APP_MODE must be 'production' or 'mock'; got '<value>'"` and `"APP_MODE=production requires a reachable DATABASE_URL; got <value>"`.
- **Observability**: structured JSON logs only (`wiring_selected`, `db_ready`); no images/embeddings/biometrics (FR-016, Principle VIII).

## Relationship to specs 001-006

- The mock wiring path (`wire_mock_adapters`) and all mock adapters are **retained verbatim** — `select_wiring("mock")` delegates to `wire_mock_adapters`, producing behavior identical to specs 001-006 (FR-003, FR-013).
- The real SQLAlchemy adapters (`SqlAlchemyUserRepository`, `SqlAlchemyFaceTemplateRepository`, `SqlAlchemySessionManager`, `SqlAlchemyUnitOfWork`) are pre-existing from spec 001 (used in integration tests); this spec wires them into the production app factory, it does not re-create them.
- The `/health` and `/readyz` endpoints are pre-existing from spec 001; this spec makes them **mode-aware** (refinement, not a new endpoint — FR-010).

## Validation

- **Quickstart**: see [../quickstart.md](../quickstart.md) for runnable validation scenarios (both modes, cross-restart persistence, fail-fast, compose stack).
- **Automated tests**: `backend/tests/unit/test_wiring_selector.py` (selector + APP_MODE validation, no DB), `backend/tests/integration/test_production_wiring.py` (real PostgreSQL test container: cross-request + cross-restart persistence), plus the **unchanged** existing domain/contract/unit suites (non-regression, FR-013).
