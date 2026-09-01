# Implementation Plan: Live Face Preview Overlay Toggle (011)

**Branch**: `011-implement-toggle-button` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-implement-toggle-button/spec.md` — toggle button to show face bbox + landmarks in camera preview before capture; OFF = plain preview, ON = overlay; Docker host has CUDA if needed; 10 clarifications recorded (mirroring, hidden toggle, 5 FPS throttle, aria-pressed, flicker smoothing); BLOCKING-01 (preview detection transport) resolved in this plan.

## Summary

A person with camera permission sees a live preview before capture. A toggle button inside the shared `CameraCapture` component switches a face-metadata overlay (bbox + landmarks when available) ON and OFF without restarting the stream. **Technical approach (from research R-1..R-7):** preview detection is **client-side** for v1 via a new frontend `PreviewDetector` port (`MockPreviewDetector` default + `BrowserFaceDetector` using the Shape Detection API when available) sampled at **≤5 FPS / ≥200 ms** (decoupled from native video FPS) and rendered on an absolutely-positioned overlay `<canvas>` sharing `scaleX(-1)` mirroring with the `<video>`. Capture (`<canvas>.toBlob` → `onCapture`) is untouched — backend `Detector` (`YuNetDetector` / mock) still validates exactly-one-face at capture time, optionally CUDA-accelerated in Docker but not required for the preview path. No new HTTP route, no DB migration, no persisted state. This closes BLOCKING-01 with an explicit trade-off note signed in the Constitution Check gate.

## Technical Context

**Language/Version**: Python 3.11 (backend, ruff-pinned in `pyproject.toml` / `Dockerfile`); TypeScript 5.5 / React 18.3 / Vite 5.4 (frontend, `frontend/package.json`). Inherited from Constitution III and specs 001–010; unchanged.

**Primary Dependencies**:
- Backend (no change for this feature): FastAPI + Starlette CORS, SQLAlchemy 2.0 async + asyncpg, Alembic, pydantic-settings, structlog, itsdangerous (session cookie), Pillow (capture decode/resize — capture path only). ML: `YuNetDetector`/`SFaceEmbedder`/`MiVOLO`/`EmotiEff` via `adapters/ml` in production; mock adapters in `APP_MODE=mock` (default).
- Frontend (additive): React, react-router-dom, @vitejs/plugin-react, vitest + @testing-library/react + jsdom (existing). **Preview detection**: browser `FaceDetector` Shape Detection API (no npm dep, availability-checked at runtime) as `BrowserFaceDetector`; fallback/mock is a pure-TS `MockPreviewDetector` with no ML dependency. No new runtime dep is required for v1 — TFJS/BlazeFace remains a future swap behind the same `PreviewDetector` interface if accuracy demands it.
- Orchestration: Docker Compose (postgres 16-alpine, backend :8000, frontend :5173, bind mounts `usuarios/` + `models/`); optional `deploy.resources.reservations.devices` GPU reservation for backend capture-time CUDA (research R-7, additive, safe to omit on CPU hosts/CI).

**Storage**: PostgreSQL (dockerized) for `User` / `FaceTemplate` / `AuthSession` / `AnalysisRequest` (Constitution VI) — **no schema change** (preview results ephemeral, not persisted). Local filesystem `usuarios/<user-id>/pictures.jpg` (Constitution V) — unchanged. Compose volume `pgdata` unchanged.

**Testing**: `frontend: vitest run` (jsdom + @testing-library/react, `src/__tests__/setup.ts`) — preview overlay + a11y + throttle/smoothing tests with mocked `MediaDevices` + `MockPreviewDetector`; `backend: pytest -q` (unit + contract via `httpx.AsyncClient`) — existing suite must stay green (no new backend route). Domain purity `test_domain_purity` unchanged (no new domain module). All suites run **without GPU, without network, with mock detectors** (Constitution VII, Quality Gate §7, SC-007).

**Target Platform**: Linux containers via Docker (`docker compose up` canonical — Constitution IV); browser (Chrome/Edge latest, secure context for `getUserMedia`). `FRONT_CAMERA` mirrored selfie is standard mobile/ laptop path; no native mobile app.

**Project Type**: Web application (three-tier: React SPA + FastAPI API + PostgreSQL), monorepo (`backend/` + `frontend/`). Inherited (Option 2).

**Performance Goals**: SC-001: toggle ON/OFF overlay visibility within **200 ms** after interaction; preview detection throttled **≤5 FPS (≥200 ms interval)** while native video stays at its own FPS (FR-006, clarification). Optional flicker smoothing holds last valid result **150–250 ms** (picked 200 ms). Demo-grade only (Constitution I); no backend SLO change.

**Constraints**: No GPU/network/real model required to develop or test (Constitution VII, SC-007). Toggle hidden (not rendered) when stream not ready (FR-015). Toggle state in-memory per-mount, default OFF, no localStorage/cookie persistence (FR-010). `aria-pressed` + canonical label `Show face overlay` / `Mostrar contorno facial` + visible focus ring (FR-009). Overlay Canvas must keep mirroring aligned via shared `scaleX(-1)` or flipped coordinates per `mirrorIfNeeded()` (FR-003/FR-014).

**Scale/Scope**: 1 shared component (`CameraCapture.tsx`) extended; ~2 new frontend modules (`services/previewDetector.ts`, `components/FaceOverlayCanvas.tsx` or in-component canvas); 3 consumers (Onboarding/Login/Dashboard) reuse without duplication; 0 new backend files/routes; optional compose GPU stanza. Single-tenant demo; no scale targets beyond one preview at a time.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Demo-First Scope | ✅ PASS | Preview overlay is visualization only; does not alter capture validation, embeddings, or auth (FR-007, Non-Goals). Client-side mock default keeps demo self-contained; YAGNI applied — no Worker, no TFJS, no per-user threshold, no server streaming. |
| II. Spec-Driven Workflow | ✅ PASS | This plan is derived from `specs/011-implement-toggle-button/spec.md` (164 lines, 17 FRs, 7 SCs, 10 clarifications, 9 edge cases). `research.md`, `data-model.md`, `quickstart.md`, `contracts/` generated; `tasks.md` will follow. |
| III. Tech Stack (Python+React+Open-Source ML) | ✅ PASS | Python + React/Vite + PostgreSQL. No new ML model introduced; preview uses browser Shape Detection API (open platform API, not a model dependency) with mock fallback. Backend ML stays open-source (YuNet/SFace per `adapters/ml`). No proprietary weights. |
| IV. Containerized Execution (Docker Compose) | ✅ PASS | Reuses existing compose stack; no topology change. Preview overlay is a browser concern — no new service. Optional GPU `deploy.resources` for backend capture-time CUDA is compose-idiomatic and gracefully absent on CPU hosts/CI. |
| V. Local FS Image Storage `usuarios/<user-id>/pictures.jpg` | ✅ PASS | Only the single still at `capture()` is stored (existing path). Preview frames/boxes/landmarks are ephemeral in memory and never written (Non-Goals). |
| VI. PostgreSQL for Embeddings/Features | ✅ PASS | No DB change. `FaceTemplate`/`User`/`AuthSession` untouched. No new table, no migration. |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | Preview detection sits behind a **new frontend port** `PreviewDetector` (`frontend/src/services/previewDetector.ts`) with swappable adapters (`MockPreviewDetector`, `BrowserFaceDetector`), mirroring the backend `Detector` port pattern. Domain (`domain/`) imports no new infra/ML; backend ports untouched. Capture-time path still goes through `Detector`/`Embedder` ports. |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS | Overlay is a visual aid; it never bypasses `exactly-one-face` capture validation (PRD FR-004, spec FR-007). No new auth, no audit log, no identity federation. Preview frames never leave the device (client-side), so no privacy-impact storage/log to review. |

**Re-check after Phase 1 design:** No new gating principle introduced. Design adds a frontend port + canvas overlay only; backend/persistence/views (§6.x routing) unchanged. Gate stays **PASS**.

**BLOCKING-01 — Preview detection transport — resolved trade-off (strict-mode sign-off)**

| Option | What | Privacy / contract | Load | Complexity | Demo fit |
|--------|------|-------------------|------|-----------|----------|
| **A. Client-side (chosen for v1)** | Frames sampled from `<video>` in-browser; `PreviewDetector` port; no new route. | Frames never leave device; no new public contract, no storage/log review. | Zero backend QPS for preview (throttle is browser-local). | ~2 TS modules, canvas math, mock + Shape API adapter. | Best for SC-007 (mock-only tests), Constitution VII. |
| B. Server round-trip | `POST /api/preview/detect` every ~200 ms; backend Detector (CUDA if available). | Ephemeral preview frames traverse the network and must be handled/stored/lodged with a privacy guarantee (Non-Goals forbid persistence). New authenticated/unauthenticated route, status codes, load tests. | Preview QPS added per concurrent preview user (×5 rps each). | New route, multipart handling, auth/rate-limit question, error mapping. | Useful if client accuracy proves insufficient — reserved path `POST /api/preview/detect` kept free. |

Decision **A** for v1 (research R-1). If client accuracy is later insufficient (e.g., Shape API unavailable, need higher fidelity), swap `MockPreviewDetector` → `ServerPreviewDetector` (POST frames via the same throttled sampler) behind the same `PreviewDetector` interface. CUDA on the host remains **capture-time only**: `YuNetDetector` in `wire_production_adapters` benefits from `deploy.resources.reservations.devices` when the NVIDIA runtime is present, improving single-still latency without gating preview availability on GPU.

## Project Structure

### Documentation (this feature)

```text
specs/011-implement-toggle-button/
├── plan.md              # This file
├── spec.md              # Feature specification (17 FRs, 7 SCs, already clarified)
├── research.md          # Phase 0 output (R-1..R-8, Codebase Context, BLOCKING-01 resolved)
├── data-model.md        # Phase 1 output (ephemeral frontend types, no DB migration)
├── quickstart.md        # Phase 1 output (automated + 8 manual scenarios S-1..S-8)
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16 pass, validation iteration 2)
└── contracts/           # Phase 1 output (no new HTTP contract; frontend interface contract)
    ├── README.md        # Explains no new HTTP route for v1 + reserved path + a11y contract
    └── preview-overlay.md  # Frontend PreviewDetector + overlay + toggle a11y contract
```

### Source Code (repository root)

```text
backend/
├── src/face_insight/
│   ├── adapters/        # Untouched — YuNetDetector/SFaceEmbedder (production, optional CUDA),
│   │   └── ...          #   MockDetector/ScriptableMockDetector (mock/test) for capture-time
│   ├── api/             # Untouched — no new route for v1; optional compose GPU note in docs
│   ├── config.py        # Untouched — no new settings for preview (YAGNI; HOLD_MS / throttle are frontend constants)
│   └── domain/          # Untouched — DetectionResult/BoundingBox reused conceptually only
└── pyproject.toml       # Untouched

frontend/
├── src/
│   ├── components/
│   │   ├── CameraCapture.tsx          # EXTENDED — toggle button, overlay <canvas>, ResizeObserver,
│   │   │                              #   throttled PreviewDetector loop, mirroring, smoothing, a11y
│   │   └── FaceOverlayCanvas.tsx      # NEW (optional extraction) — draws boxes/landmarks, dpr-aware
│   ├── services/
│   │   └── previewDetector.ts         # NEW — PreviewDetector port + MockPreviewDetector +
│   │                                  #   BrowserFaceDetector (Shape Detection API, graceful fallback)
│   ├── pages/
│   │   ├── Onboarding.tsx             # Reused — consumes extended CameraCapture, no per-page toggle duplication
│   │   ├── Login.tsx                  # Reused — same
│   │   └── Dashboard.tsx              # Reused — same (age/mood capture flows untouched)
│   ├── hooks/                         # Untouched — useOnboardingMachine / useLoginMachine reuse CameraCapture
│   └── __tests__/
│       └── setup.ts                   # Mock helpers for MediaDevices + FaceDetector availability
└── vite.config.ts                     # Untouched — /api proxy unchanged; overlay not proxied

docker-compose.yml                     # OPTIONAL additive — backend.deploy.resources.reservations.devices
                                       #   for capture-time CUDA (safe to omit on CPU hosts/CI)
```

**Structure Decision**: Web-application layout (Option 2) inherited from specs 001–010. New frontend modules live under `frontend/src/services/` (port) and `frontend/src/components/` (overlay), mirroring the backend ports/adapters naming but scoped to the browser. The shared `CameraCapture` component is the single implementation point (FR-008); pages are not duplicated. Backend is intentionally untouched — the `Detector` port there remains capture-time only. This keeps the change reviewable as a ~100–150 line TS addition plus styles.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

