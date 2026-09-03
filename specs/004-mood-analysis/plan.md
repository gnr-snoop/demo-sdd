# Implementation Plan: Mood Analysis from Authenticated Dashboard (Fase 4 — mood)

**Branch**: `004-mood-analysis` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-mood-analysis/spec.md`

## Summary

Implement the real on-demand mood analysis flow on top of specs 001 (skeleton/ports/mocks), 002 (onboarding — image limits, error shape, `decode_and_normalize`), and 003 (real sessions, `require_valid_session`, `ProtectedRoute`, logout). An authenticated person on `/dashboard` presses "Detectar estado de ánimo"; the frontend captures a single still from the live camera preview, sends it as `multipart/form-data` to `POST /api/analysis/mood` with the session cookie. The backend validates the real session (reused from spec 003), decodes/validates the image (reusing spec 002 limits + `decode_and_normalize`), runs the detector port (exactly one usable face), runs the mood_estimator port, normalizes the label against `{neutral, feliz, triste, sorprendido, enojo, no concluyente}` (out-of-set → `no concluyente`), and returns `200 OK` with `{label, confidence, disclaimer}` per PRD §8. The mood result is transient (frontend state only — no `AnalysisRequest` persistence, YAGNI). Capture-quality failures return actionable `400` codes; port errors return recoverable `500 internal_error`; no session returns `401 unauthenticated` — all in the spec-002-pinned `{"error": {"code", "message"}}` shape. The frontend dashboard is built out with camera preview (acquired on mount, released on unmount), mood button (disabled while in flight — FR-014, one capture at a time), independent mood loading indicator, persisted-visible mood result, independent recoverable mood error surface with retry, and a disabled "Calcular edad" placeholder (spec 005). The mood_estimator port stays wired to the mock adapter (real models deferred to Fase 5 — Constitution Principle VII).

## Technical Context

**Language/Version**: Python 3.11 (backend); TypeScript 5.x / React 18 / Vite 5 (frontend). Settled by Constitution Principle III + Technology Stack table (OQ-1 FastAPI, OQ-2 Vite defaults). Inherited from specs 001/002/003.

**Primary Dependencies**:
- Backend (additive to spec 003): existing FastAPI, SQLAlchemy 2.0 async, pydantic-settings, structlog, pytest + pytest-asyncio, httpx, Pillow (reused for `decode_and_normalize`). **No new runtime dependencies.** The mood flow reuses `image_handling.decode_and_normalize`, the `Detector` + `MoodEstimator` ports, the mock adapters, and `require_valid_session` — all already present.
- Frontend (additive to spec 003): existing react, react-dom, react-router-dom, @vitejs/plugin-react, vitest + @testing-library/react. **No new runtime deps.** Camera via standard `navigator.mediaDevices.getUserMedia` (reused `CameraCapture`); mood state machine mirrors the `useLoginMachine` reducer pattern.
- Orchestration: existing Docker Compose (no topology change).

**Storage**: No new persistence. The mood result is transient (FR-014 — frontend state only). No `AnalysisRequest` audit row is written (PRD §7 optional, §19 pending; Constitution Principle I — YAGNI). PostgreSQL is reused unchanged for `AuthSession` session gating (spec 003). No filesystem writes (mood does not store a new image).

**Testing**: pytest (domain unit + contract + integration), httpx.AsyncClient for contract tests, vitest + @testing-library/react for the frontend mood state-machine + dashboard tests. Domain and contract suites run without GPU/network (Constitution Quality Gate §7). Mock detector/mood_estimator are fixture-controllable for rejection and label-variation paths (new `ScriptableMockMoodEstimator`, mirroring the `ScriptableMockDetector` pattern from spec 002).

**Target Platform**: Linux container runtime (Docker) for all services; browser (Chrome/Edge latest) with a secure context (`localhost` or HTTPS) for camera access. Inherited from specs 001/002/003.

**Project Type**: web-service (three-tier: React SPA + FastAPI HTTP API + PostgreSQL), monorepo with `backend/` and `frontend/`. Inherited.

**Performance Goals**: Demo-grade only (PRD §13: mood < 5s local excluding model load; SC-001). No SLOs. Mock adapters have negligible latency.

**Constraints**: No GPU, no network, no real ML models required to develop or test (Constitution Principle VII, Quality Gate §7). No mood result persisted server-side (FR-014). `401` reserved exclusively for `unauthenticated` (session-gating); `400` for actionable capture-quality codes; `500` for recoverable `internal_error` (FR-007). No image/embedding/biometric data in logs (FR-019/SC-013). Mood button disabled while in flight — one capture at a time, no server-side lock (FR-014). Camera stream acquired on dashboard mount, released on unmount (FR-012b).

**Scale/Scope**: 1 new domain module (`mood.py` — `MoodService` use-case + label normalization), 1 HTTP endpoint filled with real logic (`POST /api/analysis/mood`), 1 new scriptable mock adapter (`ScriptableMockMoodEstimator`), 1 frontend page built out (Dashboard), 1 new frontend hook (`useMoodMachine`), 1 frontend api helper updated (`analysisMood` with error parsing). No new persistent entity, no schema migration. Single-tenant demo; no scale targets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ PASS | Mock mood estimator retained (SC-012/FR-016); no real ML, no rate limiting, no liveness, no audit log, no server-side analysis lock. Mood result transient — no `AnalysisRequest` persistence (FR-014, YAGNI: no acceptance criterion requires an audit row; PRD §7 optional, §19 pending). Age button disabled placeholder avoids layout rework in spec 005. Camera acquired on mount/released on unmount is the simplest resource-hygiene default. |
| II. Spec-Driven Workflow | ✅ PASS | This plan is produced from `spec.md` derived from PRD §10 Fase 4; `research.md`, `data-model.md`, `contracts/`, `quickstart.md` generated; tasks will follow. |
| III. Tech Stack (Python+React+Open-Source ML) | ✅ PASS | FastAPI + React/Vite + PostgreSQL. No ML models integrated (mocks only — SC-012/FR-016); real open-source mood model choice deferred to Fase 5 (OQ-5). No new dependencies. |
| IV. Containerized Execution (Docker Compose) | ✅ PASS | Reuses the spec 001/002/003 compose stack; no topology change. `docker compose up` remains the canonical run path. |
| V. Local FS Image Storage `usuarios/<user-id>/pictures.jpg` | ✅ PASS | Mood does not write a new image (it decodes the capture in memory, runs the ports, and discards it). No filesystem interaction. No object storage. |
| VI. PostgreSQL for Embeddings/Features | ✅ PASS | No new entity, no schema change. PostgreSQL is reused only for `AuthSession` session validation (spec 003) — the mood endpoint reads the session, it does not persist a result. `AnalysisRequest` is deliberately not introduced (FR-014). |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | The `MoodService` domain use-case depends only on the `Detector` + `MoodEstimator` ports (FR-015/SC-009). The route handler is an HTTP adapter; `decode_and_normalize` is the domain-adjacent image service from spec 002; the mock mood estimator is an adapter. The domain `mood.py` imports no ML library, no SQLAlchemy, no FastAPI, no Pillow (enforced by the extended `test_domain_purity` static check). The port makes the Fase 5 real-model swap a configuration change, not a redesign (FR-016). |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS | No hardening introduced. No audit log, no rate limiting, no liveness, no server-side single-analysis lock (the frontend disabled-button guard is the policy — demo-first). Observability limited to structured JSON logs (event/duration/status/error_code) with no image, embedding, or biometric data (FR-019/SC-013). The transient result is a demo-narrative choice, not a privacy guarantee. |

**Open Questions status**: OQ-1 (FastAPI), OQ-2 (Vite), OQ-3 (server-side session — reused from spec 003), OQ-7 (Alembic), OQ-8 (JPEG ≤2MB ≤640px — reused from spec 002) all resolved to constitution defaults and inherited. OQ-4/OQ-5 (model choices) not exercised — mocks only (FR-016). OQ-6 (cosine) not exercised in this spec. No new config is required (the mood flow reuses `quality_threshold`, `image_max_bytes`, `image_max_long_edge`, and `mood_model_version` already in `Settings`). No OQ resolutions.

**Pinned decisions (from orchestrator + specify/clarify gates)** — all reflected in `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`:
1. Mood result transient — no `AnalysisRequest` persistence (FR-014, YAGNI).
2. `confidence` optional: float ∈ [0,1] when present, or null/omitted; rendered as "≈NN%" in frontend (FR-012a).
3. `disclaimer` = exact PRD §8 string returned verbatim (FR-003).
4. Label set `{neutral, feliz, triste, sorprendido, enojo, no concluyente}`; out-of-set/low-quality normalized to `no concluyente` (FR-004).
5. Error shape `{"error": {"code", "message"}}` (spec 002 pinned, reused verbatim); `400` for `no_face`/`multiple_faces`/`invalid_image`/`insufficient_quality`; `401` for `unauthenticated`; `500` for `internal_error` (FR-006/FR-007).
6. FR-014: mood button disabled while in flight, one capture at a time, no server-side lock.
7. Age button present but disabled ("coming soon" placeholder for spec 005) (FR-013).
8. Mock mood estimator retained (real models Fase 5) (FR-016).
9. Camera: acquired on dashboard mount, released on unmount; mood button captures single still from live preview (FR-012b).
10. Camera permission denied → actionable mood error surface + retry, no backend call (FR-012c).
11. Evaluation order: session → image decode/validate → detect (exactly one face + quality) → mood estimate → label normalization → response (FR-005).

**Contract evolution note (strict-mode flag)**: Spec 001's stub `POST /api/analysis/mood` returns a fixed `MoodResponse(label="neutral", confidence=0.74, disclaimer=...)` with no image processing, no detection, and a `{"detail": ...}` error shape on failures. Spec 004 replaces this with the real orchestration documented in `contracts/analysis-mood.md`. This is a **deliberate, authorized contract evolution** (the spec 001 contract was explicitly a stub with "enforcement deferred to specs 002–006"; the clarify gate pinned the real shape). The spec 004 contract tests assert the real shapes; spec 001's stub contract assertions for mood are superseded. The `confidence` field changes from required-`float` to optional `float | null` (the spec 001 contract showed a numeric value; the real contract permits null/omitted per PRD §6.4 — a backward-compatible widening). No downstream consumer exists (age is spec 005, deletion is spec 006, not yet implemented).

**Gate result**: PASS — no violations, no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/004-mood-analysis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   └── analysis-mood.md # real POST /api/analysis/mood contract (supersedes spec 001 stub)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/face_insight/
│   ├── domain/
│   │   ├── mood.py             # NEW: MoodService use-case + normalize_mood_label (port-only deps)
│   │   ├── exceptions.py       # + MoodInternalError (mapped to 500 internal_error)
│   │   ├── result_types.py     # MoodResult.confidence -> float | None (optional, forward-compatible)
│   │   ├── ports.py            # unchanged (MoodEstimator + Detector already declared)
│   │   ├── image_handling.py   # reused (decode_and_normalize) — unchanged
│   │   └── ...                 # onboarding/login/comparison/validation/entities unchanged
│   ├── adapters/mock/
│   │   ├── mood_estimator.py   # + ScriptableMockMoodEstimator (byte-marker controllable for tests)
│   │   └── constants.py        # + mood byte markers (FELIZ/TRIST/NOCONCLUSIVE/MOODFAIL/OOSET)
│   ├── api/
│   │   ├── schemas.py          # MoodResponse.confidence -> float | None = None (optional)
│   │   ├── routes/analysis.py  # REPLACED: real mood orchestration via MoodService (age stays stubbed)
│   │   └── dependencies.py     # + get_mood_service dep (resolves app.state.mood_service); unchanged else
│   └── main.py                 # wire_mock_adapters: build MoodService from mock ports -> app.state.mood_service
│                              # create_auth_app: also wire MoodService for integration tests
└── tests/
    ├── unit/test_mood_service.py        # NEW: label normalization, confidence clamp, error mapping, valid-label set
    ├── contract/test_mood_contracts.py  # NEW: 200 shape, 400/401/500 status + pinned error body, confidence bounds
    ├── contract/test_http_contracts.py  # updated: mood now exercises real logic (supersedes stub assertions)
    ├── domain/test_domain_purity.py     # extended: assert mood.py imports no infra/ML/Pillow
    └── integration/test_mood_analysis.py # NEW: real endpoint + mock detector/mood + real session validation

frontend/
└── src/
    ├── pages/Dashboard.tsx           # REPLACED: camera preview, mood button, mood result/error, disabled age, logout
    ├── hooks/useMoodMachine.ts       # NEW: mood state machine (idle -> processing -> result | error)
    ├── components/CameraCapture.tsx  # reused from spec 002 (active preview + still capture + permission callbacks)
    └── services/api.ts               # analysisMood() updated: parseError + credentials: "include"
```

**Structure Decision**: Web-application layout inherited from specs 001/002/003 (Option 2). The new domain module `mood.py` lives under `backend/src/face_insight/domain/` and has zero imports from `adapters`, `api`, ML libraries, Pillow, or SQLAlchemy — it imports only ports, result types, exceptions, and the stdlib. The label-normalization function (`normalize_mood_label`) is pure Python. The route handler (`analysis.py`) is the HTTP adapter: it does session validation (via `Depends(require_valid_session)`), image decode (via `image_handling.decode_and_normalize`), exception→response mapping (mirroring `auth.py`'s `_LOGIN_ERROR_MAP` pattern), and structured logging — no business logic. The `domain/` purity check (`test_domain_purity`) is extended to cover `mood.py`. The frontend reuses `CameraCapture` (spec 002) with `active={true}` on dashboard mount (stream acquired in its `useEffect`, released in cleanup on unmount — FR-012b) and adds a separate `useMoodMachine` hook (mirrors `useLoginMachine` reducer pattern; the mood flow differs: no identifier, no redirect, result stays visible).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
