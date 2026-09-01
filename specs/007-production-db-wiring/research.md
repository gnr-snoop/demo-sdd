# Research: Production DB Wiring + APP_MODE Selector (Fase 5 foundation)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Codebase Context

*Gathered from the codebase-memory knowledge graph (project `demo-sdd`, generation 2026-09-01, fast re-index after 30 changed files). Coverage checked on all evidence paths — no recorded gaps; source read directly as ground truth.*

### Existing architecture (integration surface)

- **App factory** — `backend/src/face_insight/main.py:171` `create_app()` builds the FastAPI app, registers routes, then calls `wire_mock_adapters(app)` **unconditionally** (line 188). This is the single line that the selector replaces: `select_wiring(app, settings.app_mode)`.
- **Mock wiring** — `wire_mock_adapters()` (`main.py:67-168`) attaches 8 mock adapters to `app.state` and builds `OnboardingService`, `LoginService`, `MoodService`, `AgeService`, `DeletionService` from mock ports. It is retained **verbatim** (scope boundary); `select_wiring("mock")` must reproduce today's behavior by delegating to it.
- **Real SQLAlchemy adapters (pre-existing from spec 001, reused verbatim)**:
  - `SqlAlchemyUserRepository`, `SqlAlchemyFaceTemplateRepository`, `SqlAlchemyUnitOfWork` — `adapters/db/repositories.py`
  - `SqlAlchemySessionManager` — `adapters/db/session_manager.py`
  - Already used in integration tests via `create_onboarding_app`/`create_auth_app` (which accept a `session_factory` and override the mock repos). This spec promotes them into the production app factory.
- **DB session factory** — `adapters/db/session.py` already provides `get_engine()` / `get_session_factory()` building an async engine + `async_sessionmaker` from `settings.database_url` with `pool_pre_ping=True`. **Reused** for production wiring (no new session-factory code).
- **Config** — `config.py` `Settings` (pydantic-settings) has `database_url` (default `postgresql+asyncpg://...`) but **no `app_mode`**. This spec adds `app_mode: str = "mock"` with a field validator restricting to `{production, mock}`.
- **Health/readiness probes** — `main.py` defines `/health` (liveness, returns `{"status":"healthy"}`, no DB check) and `/readyz` (readiness, runs `db_is_ready()` → `SELECT 1`, 503 if down). `/readyz`'s `db_is_ready()` uses a module-level lazy `_engine` built from `database_url` — in mock mode with no DB this would hang/fail. The spec makes `/health` **mode-aware** (DB ping in production, no check in mock) and makes `/readyz` mode-aware so mock mode does not require a DB.
- **Alembic** — `backend/alembic/env.py` reads `DATABASE_URL` from `get_settings()` and runs async migrations; `alembic.ini` at `backend/alembic.ini`. Migrations are already applied in the compose entrypoint (`docker-compose.yml` backend `command: sh -c "alembic upgrade head && uvicorn ..."`), but **unconditionally** and the backend **always wires mock** (no `APP_MODE` set) — so today the compose stack runs migrations yet loses all data on restart. This spec fixes both.
- **docker-compose.yml** — backend already `depends_on: postgres: condition: service_healthy` and sets `DATABASE_URL` to the compose Postgres service. Missing: `APP_MODE=production` and migration gating on `APP_MODE`.
- **Existing integration-test pattern** — `tests/integration/test_{onboarding,login_session,deletion_integration}.py` use a `require_db` fixture that **skips if PostgreSQL is unavailable** (no test container); they build `async_sessionmaker(create_async_engine(settings.database_url, pool_pre_ping=True), expire_on_commit=False)` and pass `session_factory` to `create_onboarding_app`/`create_auth_app`. The production-persistence tests for this spec follow the same session-factory construction but drive the app through `create_app()` with `APP_MODE=production` (exercising the real selector path), against a real test container.

### Reuse opportunities

- `adapters/db/session.py` `get_session_factory()` — production session factory, no re-implementation.
- `wire_mock_adapters()` — `select_wiring("mock")` delegates here; the mock ML adapters it builds are reused inside `wire_production_adapters()` (production keeps mock ML).
- `create_onboarding_app`/`create_auth_app` — reference for how to construct `SqlAlchemy*` repos + `SqlAlchemySessionManager` + `SqlAlchemyUnitOfWork` from a session factory and rebuild the services. `wire_production_adapters()` mirrors this structure but writes to `app.state` against the production session factory.
- `db_is_ready()` — reused for the mode-aware `/health` and `/readyz` DB ping in production.

### Integration touch-points

- `config.py` — add `app_mode` field + validator.
- `main.py` — add `wire_production_adapters()`, `select_wiring()`; change `create_app()` to call the selector; make `/health` + `/readyz` mode-aware.
- `docker-compose.yml` — set `APP_MODE=production` on backend; gate migration on `APP_MODE`.
- `backend/Dockerfile` / compose `command` — entrypoint migration gating.
- New tests: `tests/unit/test_wiring_selector.py`, `tests/integration/test_production_wiring.py`.

### Coverage limitations

None material. All evidence paths returned `no_recorded_issue` (metadata-changed freshness noted; source read directly as ground truth). The graph's `frontend/src/__tests__` is excluded by skip-list (irrelevant — frontend unchanged this spec).

---

## Research Items

### R-1: APP_MODE setting shape, validation, and fail-fast on unrecognized values

**Decision**: Add `app_mode: str = "mock"` to `Settings` with a pydantic `field_validator` that normalizes (`.strip().lower()`) and rejects any value not in `{"production", "mock"}` by raising `ValueError("APP_MODE must be 'production' or 'mock'; got '<value>'")`. Pydantic surfaces this at settings-construction time, which is the first step of `create_app()` — so an invalid `APP_MODE` fails fast before any engine/wiring/app build, satisfying FR-005.

**Rationale**: pydantic-settings already validates env-loaded fields; reusing its validator machinery avoids a hand-rolled check (YAGNI, Principle I). Normalizing (strip + lower) makes `APP_MODE=Production` and `APP_MODE=" mock "` lenient-but-correct, matching the demo-friendly posture while still rejecting truly unrecognized values. Default `mock` preserves backward compatibility (FR-001).

**Alternatives considered**:
- *Enum field* (`AppMode = Literal["production","mock"]`): rejected — pydantic `Literal` rejects case variants and surrounding whitespace with a less actionable message; a normalized string + validator gives a clearer fail-fast error.
- *Validation in `select_wiring` instead of Settings*: rejected — defers the failure to wiring time rather than config-load time; the spec's startup sequence validates `APP_MODE` first.

### R-2: select_wiring structure and composition-time guarantee

**Decision**: `select_wiring(app: FastAPI, app_mode: str) -> None` dispatches exactly once: `"mock"` → `wire_mock_adapters(app)`; `"production"` → `wire_production_adapters(app)`. `create_app()` calls `select_wiring(app, get_settings().app_mode)` once, replacing the direct `wire_mock_adapters(app)` call. The result is cached on `app.state` for the process lifetime (the services are stored as attributes). No per-request selection.

**Rationale**: Constitution Principle VII — "concrete models are adapters selected at composition time." A single dispatch function is the simplest seam specs 008/009 extend (they add cases/overrides to `wire_production_adapters`). Calling once in the factory guarantees the composition-time invariant (FR-002).

**Alternatives considered**:
- *Per-request dependency injection of the mode*: rejected — runtime anti-pattern in hexagonal arch, complicates the container for no demo value (Principle I).
- *A registry/factory class*: rejected — YAGNI; a function is sufficient for two modes.

### R-3: wire_production_adapters — real DB adapters + mock ML, session factory from DATABASE_URL

**Decision**: `wire_production_adapters(app)` mirrors `wire_mock_adapters`'s service-construction structure but:
1. Builds the session factory via `adapters.db.session.get_session_factory()` (async engine + `async_sessionmaker` from `settings.database_url`, `pool_pre_ping=True`, `expire_on_commit=False`).
2. Instantiates `SqlAlchemyUserRepository(sf)`, `SqlAlchemyFaceTemplateRepository(sf)`, `SqlAlchemySessionManager(sf)`, `SqlAlchemyUnitOfWork(sf)`.
3. Keeps the **mock ML adapters** (`MockDetector`, `MockEmbedder`, `MockAgeEstimator`, `MockMoodEstimator`) — real ML is specs 008/009 (FR-004, scope boundary).
4. Uses the real `FilesystemImageStorage` for images (Principle V).
5. Rebuilds `OnboardingService`, `LoginService`, `MoodService`, `AgeService`, `DeletionService` from the real persistence ports + mock ML ports + `CosineComparison` + `SessionCookieService`, exactly as `create_auth_app`/`create_onboarding_app` already do — so the service-construction logic is proven (it is the same code path the existing DB integration tests exercise).
6. Stores the engine on `app.state.db_engine` so the lifespan can dispose it and the health probe can ping it.

**Rationale**: Reuses the pre-existing, already-integration-tested SqlAlchemy adapters and the exact service-construction pattern from `create_auth_app`. No new domain logic, no new ports (FR-012/FR-017). Mock ML retained verbatim → deterministic, GPU-free, network-free (Principle VII).

**Alternatives considered**:
- *Reimplement the adapters*: rejected — they exist and are tested (spec 001); reimplementation violates the spec's "reused verbatim" assumption.
- *Real ML now*: rejected — explicitly deferred to specs 008/009 (FR-017).

### R-4: DATABASE_URL validation and fail-fast (malformed / sync-only / unset / unreachable)

**Decision**: Validation is performed implicitly at engine creation. `wire_production_adapters` calls `get_session_factory()` → `get_engine()` → `create_async_engine(settings.database_url, pool_pre_ping=True)`. A missing `DATABASE_URL` (empty string) or a malformed/sync-only scheme (e.g. `postgresql://` without `+asyncpg`) raises during `create_async_engine` / first connect. To make this fail-fast at startup (before serving) rather than at first request, `wire_production_adapters` performs an explicit connectivity probe: it opens a connection and runs `SELECT 1` immediately after building the engine; a failure raises a clear `RuntimeError("APP_MODE=production requires a reachable DATABASE_URL; got <value>")`. An unset `DATABASE_URL` is caught at the probe (or, if the URL is empty, at engine creation) with the same actionable message.

**Rationale**: The spec's clarify gate pinned "engine creation is the validation step" and "malformed URLs share the unified fail-fast path with unreachable-DB errors." Adding one explicit `SELECT 1` probe at startup converts the lazy first-request failure into an immediate startup failure (FR-006), which is the demo-grade behavior that makes misconfiguration obvious. `pool_pre_ping=True` is retained for runtime resilience (PostgreSQL going down after start → recoverable 500s, per the spec's edge case). No separate URL-parsing concern is introduced (YAGNI).

**Alternatives considered**:
- *Parse the URL scheme with a regex*: rejected — duplicates SQLAlchemy's own validation; YAGNI.
- *Rely solely on `pool_pre_ping` at first request*: rejected — violates fail-fast (FR-006); the app would serve traffic then fail on the first persistence op.

### R-5: Alembic migration gating on APP_MODE (entrypoint + manual fallback)

**Decision**: The docker-compose backend `command` becomes:
```
sh -c "if [ \"$APP_MODE\" = \"production\" ]; then alembic upgrade head; fi && uvicorn face_insight.main:app --host 0.0.0.0 --port 8000 --reload"
```
`APP_MODE=production` is set in the backend service environment. In mock mode the `if` skips migrations (no DB required — FR-007). A documented manual fallback `make migrate` (→ `alembic upgrade head`) is added to the backend `Makefile`/docs for host-native production runs (FR-011). `alembic/env.py` is unchanged (it already reads `DATABASE_URL` from settings). A failed migration exits non-zero (Alembic default) → the container does not start the app (spec edge case).

**Rationale**: Constitution Principle VI — "migrations run as part of container startup or a documented `make migrate` step." The entrypoint `if`-gate satisfies "as part of container startup" while keeping `docker compose up` the one-command path (Principle IV). Gating on `APP_MODE` means the mock dev path never needs a DB. The existing compose already ran `alembic upgrade head` unconditionally; this spec only adds the gate and the `APP_MODE` env.

**Alternatives considered**:
- *Run migrations in-app via the FastAPI lifespan*: rejected — couples migrations to the app process and runs them on every (re)load, including `--reload` hot-restarts; the entrypoint runs them once before the process, which is cleaner and matches the existing compose pattern.
- *Always run migrations (no gate)*: rejected — mock mode must not require a DB (FR-003/FR-007).

### R-6: Mode-aware /health and /readyz probes

**Decision**: Both probes become mode-aware via the wired engine. `wire_mock_adapters` does **not** create a DB engine (`app.state.db_engine` is unset/None); `wire_production_adapters` sets `app.state.db_engine`. `/health` returns `{"status":"healthy"}` in mock mode (no DB check) and `{"status":"healthy", "db": <bool>}` in production mode (runs `SELECT 1` against `app.state.db_engine`; `"unhealthy"` + 503 if the ping fails). `/readyz` mirrors this: in mock mode it reports ready with `db: null` (no check); in production it pings. This is a behavioral refinement of the **pre-existing** `/health` and `/readyz` endpoints (no new endpoint — FR-010), and the body addition (`db` field) is an infra-probe detail, not a PRD §8 contract change.

**Rationale**: The clarify gate pinned the per-mode health contract. Requiring a DB ping in mock mode would force a PostgreSQL dependency the spec eliminates for mock (FR-003); omitting it in production would hide DB outages from the compose healthcheck (FR-010). Using the presence of `app.state.db_engine` as the mode signal avoids importing settings into the route handler and keeps the probe coupled to what was actually wired.

**Alternatives considered**:
- *Read `APP_MODE` from settings inside the handler*: rejected — re-reads config per request; the wired engine is the composition-time truth.
- *Leave `/health` as pure liveness and only use `/readyz`*: rejected — the spec explicitly pins `/health` as the compose healthcheck signal (FR-010).

**Note (strict mode)**: The `/health` body gains a `db` field in production mode. This is an infra liveness/readiness probe, **not** a PRD §8 user-facing contract endpoint, and no new endpoint is introduced. Classified as a low-impact infra refinement, not a blocking public-contract change.

### R-7: Production-persistence integration tests — real PostgreSQL test container + cross-restart

**Decision**: Add `backend/tests/integration/test_production_wiring.py` using `testcontainers-python` (`PostgresContainer`) spun up **once per test session** via a session-scoped fixture. The fixture sets `DATABASE_URL` to the container's async URL, applies migrations (`alembic upgrade head` in a thread, mirroring `test_persistence.py`'s proven pattern), and yields. Tests build the app via `create_app()` with `APP_MODE=production` (monkeypatch `os.environ`), drive it through `httpx.AsyncClient(ASGITransport(app=app))`, and:
1. **Cross-request**: `POST /api/onboarding` → `POST /api/auth/face-login` → `GET /api/auth/me` as independent requests; assert each succeeds; then inspect PostgreSQL out-of-band (open a session, query `User`/`FaceTemplate`/`AuthSession` ORM rows) and assert the rows exist and match.
2. **Cross-restart**: dispose the first app's engine, build a **second** `create_app()` against the same container DB (simulating a process restart — same PostgreSQL, fresh in-process state), and call `GET /api/auth/me` with the first app's session cookie; assert it still resolves to the same user. This is the definitive real-persistence proof (FR-009) — an in-memory store cannot survive the second app instance.
3. **Selector + startup tests** (in `tests/unit/test_wiring_selector.py`, no DB): assert `select_wiring("mock")` wires `Mock*Repository` instances and no `db_engine`; `select_wiring("production")` with a reachable URL wires `SqlAlchemy*` instances and sets `db_engine`; an invalid `APP_MODE` raises at settings construction.

The tests are gated by `RUN_PROD_PERSISTENCE_TESTS` (default run) and auto-skip if Docker/the test container cannot start, with a documented skip reason (FR-015, Quality Gate §7). `testcontainers` is added as a test-only dependency in `pyproject.toml` `[project.optional-dependencies] test`.

**Rationale**: Constitution Quality Gate §6 mandates a real-adapter integration test via Docker. A real container is the only thing that proves cross-request + cross-restart persistence (a single transaction would roll back and hide whether data committed — explicitly rejected in the spec's clarify gate). The two-app-instance restart simulation is the practical in-process equivalent of stopping/restarting the process against the same DB; it definitively distinguishes real persistence from in-memory (the second app has no shared memory with the first). `testcontainers-python` is the standard Docker-Compose-aligned choice (Principle IV).

**Alternatives considered**:
- *Reuse the existing `require_db` skip-if-unavailable fixture against a host Postgres*: rejected — the spec mandates a real test container for reproducibility; relying on a manually-started host DB is flaky and not the canonical path.
- *Single shared transaction rolled back at the end*: rejected — defeats the persistence proof (spec clarify gate).
- *Actually spawn/kill a uvicorn subprocess for the restart*: rejected — flaky and slow in a test harness; two `create_app()` instances against the same DB prove the same thing (data outlives the process's memory) with deterministic speed.

### R-8: Observability — structured JSON logs, no biometrics

**Decision**: Reuse the existing `logging.py` `configure_logging()` / `get_logger()`. Add two structured log lines: one at selector dispatch (`{"event":"wiring_selected","app_mode":"production|mock"}`) and one after the migration/DB-probe step in production (`{"event":"db_ready","status":true|false}`). No images, embeddings, or biometric responses are logged (FR-016). No audit log/event store (Principle VIII).

**Rationale**: Consistent with specs 001-006 and Constitution Principle VIII. The two log lines make startup mode and DB connectivity observable for the demo without introducing a new observability stack (YAGNI).

---

## Summary of Resolved Clarifications

| # | Question | Decision |
|---|----------|----------|
| R-1 | APP_MODE shape/validation/default | `app_mode: str = "mock"`, normalized + validated to `{production,mock}`, fail-fast at settings load |
| R-2 | Selector structure & composition-time | `select_wiring(app, app_mode)` called once in `create_app()`; result cached on `app.state` |
| R-3 | Production wiring contents | Real SqlAlchemy DB adapters + mock ML + FilesystemImageStorage; session factory from `adapters.db.session` |
| R-4 | DATABASE_URL validation/fail-fast | Engine creation + explicit startup `SELECT 1` probe → `RuntimeError` with actionable message |
| R-5 | Migration gating | Entrypoint `if APP_MODE=production` gate; `make migrate` fallback; `alembic/env.py` unchanged |
| R-6 | Mode-aware health probes | `/health` + `/readyz` ping DB only when `app.state.db_engine` is wired (production); no new endpoint |
| R-7 | Integration tests | testcontainers-python Postgres, session-scoped; cross-request + cross-restart (two app instances); skippable flag |
| R-8 | Observability | Two structured JSON log lines; no biometrics; no audit log |

All clarifications from the spec's specify/clarify gates were already pinned by the orchestrator; the research above records the implementation-level decisions that realize them. No item touches security, data privacy, compliance, a breaking change, or a PRD §8 public contract — the `/health` body `db` field (R-6) is an infra-probe refinement, not a user-facing contract.
