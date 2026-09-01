# Implementation Plan: Age Estimation from Authenticated Dashboard (Fase 4 — age)

**Branch**: `005-age-analysis` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-age-analysis/spec.md`

> ## ⏳ PENDING — IMPLEMENTATION DEFERRED FOR A LIVE DEMO
>
> **This spec is fully documented (spec, plan, tasks, analyze) but is intentionally NOT implemented in this session.** It is reserved for a live SDD demo. The `tasks.md` (produced by `/speckit.tasks`) is implementation-ready. The implement gate is deliberately deferred; all upstream gates (specify/clarify/plan/tasks/analyze) produce complete artifacts.
>
> This plan therefore describes **what will be built and how**, grounded in the existing codebase (specs 001–004 are implemented), so the live demo can proceed directly from `tasks.md`.

## Summary

Implement the real on-demand age estimation flow on top of specs 001 (skeleton/ports/mocks), 002 (onboarding — image limits, error shape, `decode_and_normalize`), 003 (real sessions, `require_valid_session`, `ProtectedRoute`, logout), and 004 (mood — dashboard, camera, mood button + result/error/loading surfaces, disabled age placeholder). An authenticated person on `/dashboard` presses "Calcular edad" (currently a disabled placeholder — this spec **enables** it); the frontend captures a single still from the live camera preview, sends it as `multipart/form-data` to `POST /api/analysis/age` with the session cookie. The backend validates the real session (reused from spec 003), decodes/validates the image (reusing spec 002 limits + `decode_and_normalize`), runs the detector port (exactly one usable face), runs the `age_estimator` port, normalizes the port output to `{estimatedAge, range:{min,max}}` (range → midpoint estimate; point-only → derived symmetric range with configurable half-width, `min` clamped to 0), and returns `200 OK` with `{estimatedAge, range, disclaimer}` per PRD §8. The age result is transient (frontend state only — no `AnalysisRequest` persistence, YAGNI, consistent with spec 004). Capture-quality failures return actionable `400` codes; port errors return recoverable `500 internal_error`; no session returns `401 unauthenticated` — all in the spec-002-pinned `{"error": {"code", "message"}}` shape. **FR-014 shared capture mutex**: while either a mood or an age analysis is in flight, both buttons disable and a second press of either is ignored (one capture at a time across the dashboard); mood and age retain independent loading/result/error state surfaces. The `age_estimator` port stays wired to the mock adapter (real models deferred to Fase 5 — Constitution Principle VII). Mood (spec 004) is reused unchanged except for the shared capture mutex; the spec 004 mood tests must still pass.

## Technical Context

**Language/Version**: Python 3.11 (backend); TypeScript 5.x / React 18 / Vite 5 (frontend). Settled by Constitution Principle III + Technology Stack table (OQ-1 FastAPI, OQ-2 Vite defaults). Inherited from specs 001/002/003/004.

**Primary Dependencies**:
- Backend (additive to spec 004): existing FastAPI, SQLAlchemy 2.0 async, pydantic-settings, structlog, pytest + pytest-asyncio, httpx, Pillow (reused for `decode_and_normalize`). **No new runtime dependencies.** The age flow reuses `image_handling.decode_and_normalize`, the `Detector` + `AgeEstimator` ports, the mock adapters, and `require_valid_session` — all already present.
- Frontend (additive to spec 004): existing react, react-dom, react-router-dom, @vitejs/plugin-react, vitest + @testing-library/react. **No new runtime deps.** Camera via standard `navigator.mediaDevices.getUserMedia` (reused `CameraCapture`); age state machine mirrors the `useMoodMachine` reducer pattern from spec 004.
- Orchestration: existing Docker Compose (no topology change).

**Storage**: No new persistence. The age result is transient (FR-014 — frontend state only). No `AnalysisRequest` audit row is written (PRD §7 optional, §19 pending; Constitution Principle I — YAGNI). PostgreSQL is reused unchanged for `AuthSession` session gating (spec 003). No filesystem writes (age does not store a new image). Consistent with the spec 004 mood decision.

**Testing**: pytest (domain unit + contract + integration), httpx.AsyncClient for contract tests, vitest + @testing-library/react for the frontend age state-machine + dashboard tests. Domain and contract suites run without GPU/network (Constitution Quality Gate §7). Mock detector/age_estimator are fixture-controllable for rejection and point-only/range/normalization paths (new `ScriptableMockAgeEstimator`, mirroring the `ScriptableMockMoodEstimator` pattern from spec 004).

**Target Platform**: Linux container runtime (Docker) for all services; browser (Chrome/Edge latest) with a secure context (`localhost` or HTTPS) for camera access. Inherited from specs 001/002/003/004.

**Project Type**: web-service (three-tier: React SPA + FastAPI HTTP API + PostgreSQL), monorepo with `backend/` and `frontend/`. Inherited.

**Performance Goals**: Demo-grade only (PRD §13: age < 5s local excluding model load; SC-001). No SLOs. Mock adapters have negligible latency.

**Constraints**: No GPU, no network, no real ML models required to develop or test (Constitution Principle VII, Quality Gate §7). No age result persisted server-side (FR-014). `401` reserved exclusively for `unauthenticated` (session-gating); `400` for actionable capture-quality codes; `500` for recoverable `internal_error` (FR-007). No image/embedding/biometric data in logs (FR-019/SC-013). FR-014 shared capture mutex: both mood + age buttons disable while either analysis is in flight; no server-side lock (demo-first; the frontend guard is the policy). Camera stream lifecycle unchanged from spec 004 (acquired on dashboard mount, released on unmount — FR-012b).

**Scale/Scope**: 1 new domain module (`age.py` — `AgeService` use-case + `normalize_age_result`), 1 HTTP endpoint filled with real logic (`POST /api/analysis/age`), 1 new scriptable mock adapter (`ScriptableMockAgeEstimator`), 1 new frontend hook (`useAgeMachine`), 1 frontend page updated (Dashboard — enable age button, add age result/error/loading surfaces, shared capture mutex), 1 frontend api helper updated (`analysisAge` with error parsing + credentials), 1 new config field (`age_range_half_width_years`), 1 new domain exception (`AgeInternalError`), 1 new schema (`AgeRange`). No new persistent entity, no schema migration. Single-tenant demo; no scale targets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ PASS | Mock age estimator retained (SC-012/FR-016); no real ML, no rate limiting, no liveness, no audit log, no server-side analysis lock. Age result transient — no `AnalysisRequest` persistence (FR-014, YAGNI: no acceptance criterion requires an audit row; PRD §7 optional, §19 pending). Enabling the age button reuses the spec 004 layout (no rework). Shared capture mutex is the simplest FR-014 policy (frontend guard, no server lock). Camera lifecycle reused unchanged from spec 004. |
| II. Spec-Driven Workflow | ✅ PASS | This plan is produced from `spec.md` derived from PRD §10 Fase 4 (age portion); `research.md`, `data-model.md`, `contracts/`, `quickstart.md` generated; tasks will follow. |
| III. Tech Stack (Python+React+Open-Source ML) | ✅ PASS | FastAPI + React/Vite + PostgreSQL. No ML models integrated (mocks only — SC-012/FR-016); real open-source age model choice deferred to Fase 5 (OQ-5). No new dependencies. |
| IV. Containerized Execution (Docker Compose) | ✅ PASS | Reuses the spec 001/002/003/004 compose stack; no topology change. `docker compose up` remains the canonical run path. |
| V. Local FS Image Storage `usuarios/<user-id>/pictures.jpg` | ✅ PASS | Age does not write a new image (it decodes the capture in memory, runs the ports, and discards it). No filesystem interaction. No object storage. |
| VI. PostgreSQL for Embeddings/Features | ✅ PASS | No new entity, no schema change. PostgreSQL is reused only for `AuthSession` session validation (spec 003) — the age endpoint reads the session, it does not persist a result. `AnalysisRequest` is deliberately not introduced (FR-014). |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | The `AgeService` domain use-case depends only on the `Detector` + `AgeEstimator` ports (FR-015/SC-009). The route handler is an HTTP adapter; `decode_and_normalize` is the domain-adjacent image service from spec 002; the mock age estimator is an adapter. The domain `age.py` imports no ML library, no SQLAlchemy, no FastAPI, no Pillow (enforced by the extended `test_domain_purity` static check). The port makes the Fase 5 real-model swap a configuration change, not a redesign (FR-016). |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS | No hardening introduced. No audit log, no rate limiting, no liveness, no server-side single-analysis lock (the frontend shared-capture-mutex guard is the policy — demo-first). Observability limited to structured JSON logs (event/duration/status/error_code) with no image, embedding, or biometric data (FR-019/SC-013). The transient result is a demo-narrative choice, not a privacy guarantee. |

**Open Questions status**: OQ-1 (FastAPI), OQ-2 (Vite), OQ-3 (server-side session — reused from spec 003), OQ-7 (Alembic), OQ-8 (JPEG ≤2MB ≤640px — reused from spec 002) all resolved to constitution defaults and inherited. OQ-4/OQ-5 (model choices) not exercised — mocks only (FR-016). OQ-6 (cosine) not exercised in this spec. One new config field (`age_range_half_width_years`, default 5) is added to the existing pydantic `Settings` (FR-004) — no new config mechanism. No OQ resolutions.

**Pinned decisions (from orchestrator + specify/clarify gates)** — all reflected in `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`:
1. Age result transient — no `AnalysisRequest` persistence (FR-014, YAGNI; consistent with spec 004).
2. `range` always present in the `200` response; `estimatedAge`, `min`, `max` are integers with `min >= 0` and `min <= estimatedAge <= max` (FR-002/FR-004).
3. Normalization: port range → `estimatedAge` = midpoint (rounded, clamped into `[min, max]`); port point-only → derived symmetric range (half-width `age_range_half_width_years`, default 5, `min` clamped to 0) (FR-004).
4. `disclaimer` = exact PRD §8 string `"La edad es una estimación visual y puede contener un margen de error significativo."` returned verbatim (FR-003).
5. Error shape `{"error": {"code", "message"}}` (spec 002 pinned, reused verbatim); `400` for `no_face`/`multiple_faces`/`invalid_image`/`insufficient_quality`; `401` for `unauthenticated`; `500` for `internal_error` (FR-006/FR-007).
6. FR-014 shared capture mutex: both mood + age buttons disable while either analysis in flight; independent loading/result/error surfaces; no server-side lock.
7. Age button enables the spec 004 disabled placeholder (removes "coming soon") (FR-013).
8. Mock age estimator retained (real models Fase 5); `model_version = "mock-age-estimator-v1"` (FR-016/FR-017).
9. Mood (spec 004) reused unchanged except shared capture mutex; mood tests must still pass (FR-020).
10. Evaluation order: session → image decode/limits → detect one face → age estimate → normalize → respond (FR-005).
11. Camera lifecycle unchanged from spec 004 (FR-012b); camera permission denied → actionable age error + retry, no backend call (FR-012c).

**Contract evolution note (strict-mode flag)**: Spec 001's stub `POST /api/analysis/age` returns a fixed `AgeResponse(estimatedAge=32, range={min:27,max:37}, disclaimer=...)` with no image processing, no detection, and no error handling (the current `analysis.py` stub). Spec 005 replaces this with the real orchestration documented in `contracts/analysis-age.md`. This is a **deliberate, authorized contract evolution** (the spec 001 contract was explicitly a stub with "enforcement deferred to specs 002–006"; the clarify gate pinned the real shape). The spec 005 contract tests assert the real shapes; spec 001's stub contract assertions for age are superseded. The `AgeResult.range` field widens from required `tuple[int,int]` to `tuple[int,int] | None` at the **port output** level (to represent point-only estimates) — this is backward-compatible (the mock always supplies a range; the normalization layer guarantees the HTTP response always has a range). No downstream consumer exists (deletion is spec 006, not yet implemented). Not a security/privacy/compliance concern — flagged and documented per strict mode; not BLOCKING.

**Gate result**: PASS — no violations, no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/005-age-analysis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   └── analysis-age.md  # real POST /api/analysis/age contract (supersedes spec 001 stub)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/face_insight/
│   ├── domain/
│   │   ├── age.py               # NEW: AgeService use-case + normalize_age_result (port-only deps)
│   │   ├── exceptions.py        # + AgeInternalError (mapped to 500 internal_error)
│   │   ├── result_types.py      # AgeResult.range -> tuple[int,int] | None (optional port output)
│   │   ├── ports.py             # unchanged (AgeEstimator + Detector already declared)
│   │   ├── image_handling.py    # reused (decode_and_normalize) — unchanged
│   │   ├── mood.py              # unchanged (spec 004 — reused, not re-implemented)
│   │   └── ...                  # onboarding/login/comparison/validation/entities unchanged
│   ├── adapters/mock/
│   │   ├── age_estimator.py     # + ScriptableMockAgeEstimator (byte-marker controllable for tests)
│   │   ├── constants.py         # + age byte markers (AGEPOINT/AGERANGE/AGEFAIL); AGE_MODEL_VERSION -> "mock-age-estimator-v1"
│   │   └── mood_estimator.py    # unchanged (spec 004)
│   ├── api/
│   │   ├── schemas.py           # + AgeRange schema; AgeResponse.range -> AgeRange
│   │   ├── routes/analysis.py   # REPLACED (age): real age orchestration via AgeService (mood unchanged)
│   │   └── dependencies.py      # + get_age_service dep (resolves app.state.age_service); unchanged else
│   ├── config.py                # + age_range_half_width_years: int = 5 (FR-004); age_model_version -> "mock-age-estimator-v1"
│   └── main.py                  # wire_mock_adapters: build AgeService from mock ports -> app.state.age_service
│                               # create_auth_app: also wire AgeService for integration tests
└── tests/
    ├── unit/test_age_service.py          # NEW: normalization (point→range, range→midpoint, invariants, clamping), error mapping
    ├── contract/test_age_contracts.py    # NEW: 200 shape, 400/401/500 status + pinned error body, integer/range invariants
    ├── contract/test_http_contracts.py   # updated: age now exercises real logic (supersedes stub assertions)
    ├── domain/test_domain_purity.py      # extended: assert age.py imports no infra/ML/Pillow
    └── integration/test_age_analysis.py  # NEW: real endpoint + mock detector/age + real session validation

frontend/
└── src/
    ├── pages/Dashboard.tsx           # UPDATED: enable age button (remove placeholder), age result/error/loading surfaces, shared capture mutex
    ├── hooks/useAgeMachine.ts        # NEW: age state machine (idle -> processing -> result | error)
    ├── hooks/useMoodMachine.ts       # unchanged (spec 004) — shared mutex is dashboard-level, not in the mood hook
    ├── components/CameraCapture.tsx  # reused from spec 002 (active preview + still capture + permission callbacks)
    └── services/api.ts               # analysisAge() updated: parseError + credentials: "include"
```

**Structure Decision**: Web-application layout inherited from specs 001/002/003/004 (Option 2). The new domain module `age.py` lives under `backend/src/face_insight/domain/` and has zero imports from `adapters`, `api`, ML libraries, Pillow, or SQLAlchemy — it imports only ports, result types, exceptions, and the stdlib. The normalization function (`normalize_age_result`) is pure Python. The route handler (`analysis.py`) is the HTTP adapter: it does session validation (via `Depends(require_valid_session)`), image decode (via `image_handling.decode_and_normalize`), exception→response mapping (mirroring the spec 004 `_MOOD_ERROR_MAP` pattern with a new `_AGE_ERROR_MAP`), and structured logging — no business logic. The `domain/` purity check (`test_domain_purity`) is extended to cover `age.py`. The frontend reuses `CameraCapture` (spec 002/004) with `active={true}` on dashboard mount and adds a separate `useAgeMachine` hook (mirrors `useMoodMachine` reducer pattern). The **shared capture mutex** is implemented at the `Dashboard` level: a single `anyAnalysisInFlight = mood.isProcessing || age.isProcessing` flag drives both `CameraCapture` `disabled` props and both buttons, so a press of either disables both (FR-014). Each hook retains its own independent state machine and result/error surface.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
