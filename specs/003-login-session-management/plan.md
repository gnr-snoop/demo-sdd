# Implementation Plan: Login & Session Management (Fase 3)

**Branch**: `003-login-session-management` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-login-session-management/spec.md`

## Summary

Implement real face-login 1:1 verification, server-side session management, route protection, and logout on top of specs 001 (skeleton/ports/mocks) and 002 (onboarding — `User` + `FaceTemplate` exist). A person submits an identifier + captured image to `POST /api/auth/face-login`; the backend validates the image, detects exactly one usable face, loads the `User`/`FaceTemplate` by normalized identifier, embeds the capture, computes cosine similarity via the `Comparison` port, and on `>= threshold` creates an `AuthSession` in PostgreSQL and sets a signed http-only cookie. The two identity-sensitive failures (nonexistent identifier vs below-threshold) return a byte-identical `401 auth_failed`; capture-quality failures return actionable `400` codes. The spec 001 placeholder session guard is replaced with real session validation on every protected endpoint; `GET /api/auth/me` bootstraps frontend session state and `ProtectedRoute` gates `/dashboard`; `POST /api/auth/logout` revokes the session idempotently. All ML touchpoints stay behind the ports wired to mock adapters (real models are Fase 5).

## Technical Context

**Language/Version**: Python 3.11 (backend); TypeScript 5.x / React 18 / Vite 5 (frontend). Settled by Constitution Principle III + Technology Stack table (OQ-1 FastAPI, OQ-2 Vite defaults). Inherited from specs 001/002.

**Primary Dependencies**:
- Backend (additive to spec 002): **itsdangerous** (`URLSafeTimedSerializer` — transitive via Starlette/FastAPI, no new top-level dep) for signed session cookies; existing FastAPI, SQLAlchemy 2.0 async, Alembic, psycopg/asyncpg, pydantic-settings, structlog, pytest + pytest-asyncio, httpx, Pillow (reused for image decode/resize).
- Frontend (additive to spec 002): existing react, react-dom, react-router-dom, @vitejs/plugin-react, vitest + @testing-library/react. No new runtime deps (camera via standard `navigator.mediaDevices.getUserMedia`, reused `CameraCapture`).
- Orchestration: existing Docker Compose (no topology change).

**Storage**: PostgreSQL (dockerized) for `AuthSession` (Constitution Principle VI, OQ-3); the `auth_sessions` table already exists from spec 001's migration. No filesystem writes in this spec (login does not persist a new image). Inherited from specs 001/002.

**Testing**: pytest (domain unit + contract + integration), httpx.AsyncClient for contract tests, vitest + @testing-library/react for the frontend login state-machine + session/protected-route tests. Domain and contract suites run without GPU/network (Constitution Quality Gate §7). Mock detector/embedder are fixture-controllable for rejection paths (reused from spec 002).

**Target Platform**: Linux container runtime (Docker) for all services; browser (Chrome/Edge latest) with a secure context (`localhost` or HTTPS) for camera access. Inherited from specs 001/002.

**Project Type**: web-service (three-tier: React SPA + FastAPI HTTP API + PostgreSQL), monorepo with `backend/` and `frontend/`. Inherited from specs 001/002.

**Performance Goals**: Demo-grade only (PRD §13: login < 5s local excluding model load; SC-001 < 30s excluding camera permission). No SLOs. Mock adapters have negligible latency.

**Constraints**: No GPU, no network, no real ML models required to develop or test (Constitution Principle VII, Quality Gate §7). No `AuthSession` created on any failure path (FR-004). The two identity-sensitive login failures must be byte-identical (FR-008/SC-003). No image/embedding/biometric data in logs (FR-023/SC-013). `401` reserved exclusively for `auth_failed` + `unauthenticated`; `400` for capture codes (FR-010).

**Scale/Scope**: 1 domain entity filled (`AuthSession`), 1 port filled with real logic (`Comparison`; `SessionManager` filled), 3 HTTP endpoints filled with real logic (`face-login`, `me`, `logout`), 3 endpoints gain real session-gating (`analysis/mood`, `analysis/age`, `delete-face-data`), 1 frontend page built out (Login), 1 frontend context + guard replaced (`SessionContext`, `ProtectedRoute`), 1 logout button. Single-tenant demo; no scale targets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ PASS | Mock adapters retained (SC-012); no real ML, no rate limiting, no liveness, no audit log, no single-session constraint, no auto-refresh (re-login is the refresh path). YAGNI applied: no per-user threshold, no sliding expiry, no session-data-in-cookie, no numpy in domain. Multiple concurrent sessions allowed (demo-first). |
| II. Spec-Driven Workflow | ✅ PASS | This plan is produced from `spec.md` derived from PRD §10 Fase 3; `research.md`, `data-model.md`, `contracts/`, `quickstart.md` generated; tasks will follow. |
| III. Tech Stack (Python+React+Open-Source ML) | ✅ PASS | FastAPI + React/Vite + PostgreSQL. No ML models integrated (mocks only — SC-012); real open-source model choice deferred to Fase 5. `itsdangerous` is a signing library (transitive via Starlette), not an ML model. |
| IV. Containerized Execution (Docker Compose) | ✅ PASS | Reuses the spec 001/002 compose stack; no topology change. `docker compose up` remains the canonical run path. |
| V. Local FS Image Storage `usuarios/<user-id>/pictures.jpg` | ✅ PASS | Login does not write a new image (it reads the stored template from the DB); no filesystem interaction in this spec. No object storage. |
| VI. PostgreSQL for Embeddings/Features | ✅ PASS | `AuthSession` persisted in PostgreSQL via the `SessionManager` port + SQLAlchemy async adapter; reuses the existing `auth_sessions` table from spec 001's migration (no schema change required — data-model.md). |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | The login/session domain use-cases depend only on the ports (`Detector`, `Embedder`, `Comparison`, `UserRepository`, `FaceTemplateRepository`, `SessionManager`) (FR-021, SC-009). The route handlers are HTTP adapters; the DB adapter is an infra adapter; the cookie service is an infra adapter. The domain package imports no ML library, no SQLAlchemy, no FastAPI, no `itsdangerous` (enforced by the extended `test_domain_purity` static check — `image_handling.py` remains the documented domain-adjacent exception from spec 002, not used by the login decision logic). |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS | No hardening introduced. The non-revealing `auth_failed` is a demo-UX concern (PRD §6.3/§12), not a security guarantee. The signed cookie uses a demo key with no rotation/secure-management (documented assumption). The residual capture-vs-auth identifier-existence surface is a documented demo limitation, not a gap to close. No audit log, no rate limiting, no liveness. Observability limited to structured JSON logs (event/duration/status/error_code) with no biometric data (FR-023/SC-013). |

**Open Questions status**: OQ-1 (FastAPI), OQ-2 (Vite), OQ-3 (server-side session in PostgreSQL keyed by signed cookie — **exercised and resolved to default in this spec**), OQ-6 (cosine similarity + configurable threshold — **exercised and resolved to default in this spec**), OQ-7 (Alembic), OQ-8 (JPEG ≤2MB ≤640px — reused from spec 002) all resolved to their constitution defaults. OQ-4/OQ-5 (model choices) not exercised — mocks only. This spec adds config (`VERIFICATION_THRESHOLD`, `SESSION_LIFETIME_SECONDS`, `SESSION_COOKIE_NAME`, `SESSION_COOKIE_SECURE`, `SESSION_SIGNING_KEY`) via the existing pydantic `Settings`/env-var mechanism — PATCH-level config additions, not OQ resolutions.

**Pinned decisions (from orchestrator + specify/clarify gates)** — all reflected in `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`:
1. Distance metric: cosine similarity via the `Comparison` port; default threshold `0.5`, env `VERIFICATION_THRESHOLD` (FR-002/FR-003).
2. Session: server-side `AuthSession` in PostgreSQL + signed http-only cookie (`itsdangerous.URLSafeTimedSerializer` on the session id); default lifetime 30 min, env `SESSION_LIFETIME_SECONDS`; no JWT (OQ-3/Principle VIII).
3. Error shape: `{"error": {"code", "message"}}` (spec 002 pinned). `auth_failed` = single shared code for nonexistent-identifier and below-threshold (non-revealing, byte-identical). `401` reserved for `auth_failed` + `unauthenticated`; `400` for `invalid_image`/`no_face`/`multiple_faces`/`insufficient_quality`; `500` for `internal_error`.
4. `GET /api/auth/me`: `200 {"authenticated": true, "userId"}` on valid session; `401 unauthenticated` otherwise.
5. `POST /api/auth/logout`: `200 {"status": "ok"}` idempotent (no-cookie/expired/revoked/valid all return the same success; no error body ever).
6. Login response: exactly `{"userId", "status": "authenticated"}` (no `expiresAt`).
7. Multiple concurrent sessions allowed (demo-first; re-login does not revoke prior sessions).
8. Login evaluation order: image validation → detection → lookup → embed → compare → session creation (detection before lookup; capture errors uniform across identifiers — research R-5).
9. Identifier normalization: trim + lowercase (reused from spec 002); case-insensitive lookup.
10. Image limits: reused from spec 002 (JPEG ≤ 2 MB, ≤ 640 px long edge).

**Contract evolution note (strict-mode flag)**: Spec 001's stub auth endpoints returned placeholder responses. Spec 003 replaces them with the real contracts documented in `contracts/`. This is a **deliberate, authorized contract evolution** (the spec 001 contracts were explicitly stubs with "enforcement deferred to specs 002–006"). The spec 003 contract tests assert the real shapes; spec 001's stub contract tests for `face-login`/`me`/`logout` are superseded. Additionally, login maps capture errors to `400` while onboarding (spec 002) maps them to `422` — a deliberate, pinned per-endpoint divergence documented in `contracts/face-login.md` and `research.md` R-4 (the body shape and machine codes are shared; only the status code differs by endpoint). No downstream consumer exists (analysis is spec 004/005, deletion is spec 006, not yet implemented).

**Gate result**: PASS — no violations, no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/003-login-session-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (per-endpoint HTTP contracts)
│   ├── README.md
│   ├── face-login.md    # real POST /api/auth/face-login contract (supersedes spec 001 stub)
│   ├── auth-me.md       # real GET /api/auth/me contract (supersedes spec 001 stub)
│   └── logout.md        # real POST /api/auth/logout contract (supersedes spec 001 stub)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml               # + itsdangerous (if not already transitive) — explicit dep for clarity
├── src/face_insight/
│   ├── config.py                # + verification_threshold, session_lifetime_seconds,
│   │                            #   session_cookie_name, session_cookie_secure, session_signing_key
│   ├── domain/
│   │   ├── entities.py          # AuthSession behavior/factories filled (create_session, is_valid)
│   │   ├── ports.py             # Comparison port (filled); SessionManager methods filled
│   │   ├── result_types.py      # + ComparisonResult { similarity, accepted }
│   │   ├── exceptions.py        # NEW: AuthFailed, Unauthenticated, LoginInternalError, ComparisonError
│   │   ├── validation.py        # reused (normalize_identifier) — unchanged
│   │   ├── image_handling.py    # reused (decode/validate/resize) — unchanged
│   │   ├── comparison.py        # NEW: CosineComparison adapter (pure-Python cosine; dim-mismatch guard)
│   │   └── login.py             # NEW: LoginService use-case (port-only deps, async)
│   ├── adapters/
│   │   ├── mock/
│   │   │   ├── constants.py     # + fixture-controllable similarity for login tests
│   │   │   └── ...              # detector/embedder mocks unchanged (fixture-controllable from spec 002)
│   │   ├── db/
│   │   │   ├── session_manager.py  # NEW: SqlAlchemySessionManager (create/get_valid/revoke, async)
│   │   │   └── ...
│   │   └── http/
│   │       └── session_cookie.py   # NEW: SessionCookieService (itsdangerous sign/unsign + cookie read/write)
│   └── api/
│       ├── schemas.py           # + LoginResponse {userId, status}, MeResponse {authenticated, userId},
│       │                        #   LogoutResponse {status}, AuthFailed/Unauthenticated error bodies
│       ├── dependencies.py      # REPLACED: real require_valid_session + get_optional_session deps
│       └── routes/
│           ├── auth.py          # REPLACED: real face-login, me, logout handlers
│           ├── analysis.py      # + Depends(require_valid_session) on mood/age (logic stays stubbed)
│           └── users.py         # + Depends(require_valid_session) on delete-face-data (logic stays stubbed)
└── tests/
    ├── unit/                    # NEW: test_comparison, test_login_service, test_session_validity,
    │                            #   test_session_cookie, test_normalization (reused)
    ├── contract/test_auth_contracts.py  # NEW: face-login/me/logout shapes + status codes + identical auth_failed
    ├── contract/test_http_contracts.py  # updated: protected endpoints now 401 without session
    ├── domain/test_domain_purity.py     # extended: assert login.py/comparison.py import no infra/ML/itsdangerous
    └── integration/test_login_session.py  # NEW: real auth endpoints + mock detector/embedder + real PostgreSQL

frontend/
└── src/
    ├── context/SessionContext.tsx     # REPLACED: real session state from GET /api/auth/me + login/logout actions
    ├── components/ProtectedRoute.tsx  # REPLACED: real gating on useSession() -> redirect /login
    ├── pages/Login.tsx               # REPLACED: real login page (identifier, camera, states, submit)
    ├── pages/Dashboard.tsx           # + "Cerrar sesión" button (keyboard-accessible, wired to logout)
    ├── hooks/useLoginMachine.ts      # NEW: 7-state login state machine (mirrors onboarding pattern)
    ├── components/CameraCapture.tsx  # reused from spec 002 (preview + still capture)
    └── services/api.ts               # + faceLogin(), getMe(), logout() helpers
```

**Structure Decision**: Web-application layout inherited from specs 001/002 (Option 2). New domain modules (`login.py`, `comparison.py`, `exceptions.py`) live under `backend/src/face_insight/domain/` and have zero imports from `adapters`, `api`, ML libraries, SQLAlchemy, FastAPI, `itsdangerous`, or Pillow — `comparison.py` is pure-Python (math only). The `SessionCookieService` is an HTTP/infra adapter (`adapters/http/`), not domain. The `SqlAlchemySessionManager` is a DB adapter (`adapters/db/`). The `domain/` purity check (`test_domain_purity`) is extended to cover `login.py` + `comparison.py` + `exceptions.py` + `entities.py` (session factories) — the decision logic; `image_handling.py` remains the documented domain-adjacent exception from spec 002 (reused, not new). The frontend reuses `CameraCapture` (spec 002) and the state-machine pattern, adding a separate `useLoginMachine` hook (the flows differ: no consent, different endpoint, redirect to `/dashboard`).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
