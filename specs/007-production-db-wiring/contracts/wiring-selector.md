# Contract: Wiring Selector (`select_wiring` + `APP_MODE`)

**Spec**: [spec.md](../spec.md) | **Type**: configuration / composition-time interface (not an HTTP endpoint)

## `APP_MODE` setting

| Property | Value |
|----------|-------|
| Env var | `APP_MODE` |
| Type | `str` |
| Default | `mock` |
| Allowed values | `production`, `mock` |
| Normalization | `.strip().lower()` before validation |
| Invalid value behavior | `ValueError("APP_MODE must be 'production' or 'mock'; got '<value>'")` raised at `Settings` construction → process exits before serving traffic (FR-005) |
| Read frequency | Once, at startup (composition time) |
| Persisted | No — process-level configuration only |

## `select_wiring(app: FastAPI, app_mode: str) -> None`

| Property | Value |
|----------|-------|
| Invocation | Exactly once, inside `create_app()`, after `register_routes(app)` |
| Dispatch | `mock` → `wire_mock_adapters(app)`; `production` → `wire_production_adapters(app)` |
| Result | Adapter set + services cached on `app.state` for the process lifetime |
| Per-request selection | Not supported (Constitution Principle VII) |

## Wired adapter set by mode

| Port | `mock` | `production` |
|------|--------|--------------|
| UserRepository | `MockUserRepository` | `SqlAlchemyUserRepository(session_factory)` |
| FaceTemplateRepository | `MockFaceTemplateRepository` | `SqlAlchemyFaceTemplateRepository(session_factory)` |
| SessionManager | `MockSessionManager` | `SqlAlchemySessionManager(session_factory)` |
| UnitOfWork | `MockUnitOfWork` (deletion) | `SqlAlchemyUnitOfWork(session_factory)` |
| ImageStorage | `MockImageStorage` | `FilesystemImageStorage` |
| Detector | `MockDetector` | `MockDetector` (real in spec 008) |
| Embedder | `MockEmbedder` | `MockEmbedder` (real in spec 008) |
| AgeEstimator | `MockAgeEstimator` | `MockAgeEstimator` (real in spec 009) |
| MoodEstimator | `MockMoodEstimator` | `MockMoodEstimator` (real in spec 009) |
| `app.state.db_engine` | `None` | `AsyncEngine` from `DATABASE_URL` |

## Contract assertions (testable)

1. **C-SEL-1** (FR-003): `APP_MODE` unset or `mock` → wired repos are `Mock*` instances; `app.state.db_engine` is `None`; no PostgreSQL required.
2. **C-SEL-2** (FR-004): `APP_MODE=production` + reachable DB → wired repos are `SqlAlchemy*` instances; ML adapters are `Mock*`; `app.state.db_engine` is an `AsyncEngine`.
3. **C-SEL-3** (FR-002): `select_wiring` is called exactly once; the wired set is fixed for the process lifetime.
4. **C-SEL-4** (FR-005): `APP_MODE=invalid` (e.g. `staging`, `prod`, `""`) → `Settings()` raises `ValueError` listing allowed values; no app is built.
5. **C-SEL-5** (FR-012): mock adapters, domain ports, domain entities, HTTP contracts, and frontend are unchanged from specs 001-006.
