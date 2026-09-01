# Research: Live Face Preview Overlay Toggle (011)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01 | **Branch**: `011-implement-toggle-button`

Phase 0 research. All NEEDS CLARIFICATION items are resolved below using the spec clarifications (10 sessions), the constitution, codebase context, and industry best practice for the React + FastAPI + Docker stack. BLOCKING-01 (preview detection transport) is resolved explicitly in R-1.

---

## Codebase Context

**Graph status**: `demo-sdd` indexed — 1815 nodes / 4664 edges — `ready` — `D:/Snoop/demo-sdd` — graph fresh (no pending changes, parse_partial 0, skipped 0). Coverage check on cited paths: clean (no recorded gap).

**Architecture highlights** (`get_architecture` + source reads):
- Stack: Python 3.11 FastAPI (`backend/src/face_insight`), React 18 + Vite 5 (`frontend/src`), PostgreSQL 16-alpine, Docker Compose (3 services, `usuarios/` + `models/` bind mounts). Constitution I–VIII enforced.
- Backend hexagonal: `domain/ports.py` declares 8 ports — `Detector.detect(image: bytes) -> DetectionResult` (`BoundingBox`, `DetectionResult`), `Embedder`, `AgeEstimator`, `MoodEstimator`, `Comparison`, `SessionManager`, `UserRepository`, `FaceTemplateRepository`, `ImageStorage`. Domain imports no ML/DB/HTTP (enforced by `test_domain_purity`).
- Concrete production ML (Fase 5): `YuNetDetector`, `SFaceEmbedder`, `MiVOLOAgeEstimator`, `EmotiEffMoodEstimator` wired in `main.wire_production_adapters`; mock variants in `adapters/mock/` remain wiring default for tests and for `APP_MODE=mock`. Production verification threshold overridden to `0.363` (OpenCV LFW calibration) when `VERIFICATION_THRESHOLD` unset; mock threshold `0.5`.
- Frontend camera surface: `components/CameraCapture.tsx` (forwardRef, `getUserMedia({video:true})` → `<video>` + hidden `<canvas>` for `toBlob('image/jpeg')`, imperative `capture()` handle for dashboard age button). Pages `Onboarding.tsx`, `Login.tsx`, `Dashboard.tsx` + `Nav.tsx` consume it. Existing `CameraCapture` has no overlay, no mirroring, no throttle — it is the single implementation point to extend.
- DTO `DetectionResult` currently: `{face_count, boxes: BoundingBox[], score}` — no landmarks field. That matches spec's "box alone if landmarks absent" and is reused for capture-time validation (exactly-one-face).
- Compose: `docker-compose.yml` at repo root; backend `ports 8000`, frontend `5173`, postgres `5432`; no GPU reservations yet (CUDA is host-available per feature description, but not yet in compose).

**Related existing components / reuse points:**
- `frontend/src/components/CameraCapture.tsx` — **the single shared preview component** (FR-008). Must be extended, not duplicated. Props: `active`, `onCapture`, `onPermissionGranted/Denied`, `disabled`, `captureButtonLabel*`. Pages `Onboarding`/`Login`/`Dashboard` already import it.
- `backend/src/face_insight/domain/ports.Detector` + `MockDetector`/`ScriptableMockDetector` + `YuNetDetector` — preview detection reuses the **port shape** conceptually, but preview sampling for v1 is client-side (see R-1). Capture-time validation continues through the backend Detector port unchanged.
- `backend/src/face_insight/domain/result_types.BoundingBox` / `DetectionResult` — preview `FaceDetectionMetadata` reuses same coordinate semantics (axis-aligned rect, `x,y,width,height` in frame pixels) so overlay math matches capture contracts.
- `frontend/src/services/api.ts`, `vite.config.ts` proxy `/api` → `http://backend:8000`, `SessionContext`, `ProtectedRoute`, `useOnboardingMachine`/`useLoginMachine` — unchanged by this feature (no new HTTP contracts).
- `frontend/vitest` + `jsdom` + `@testing-library/react` + `src/__tests__/setup.ts` — preview overlay tests run here. Backend `pytest` + `httpx.AsyncClient` unchanged (this feature adds no new backend route).

**Integration touch-points:**
- `CameraCapture.tsx` ← toggle control, overlay canvas, mirroring transform, throttle loop, preview detector adapter (`frontend/src/services/previewDetector.ts` — new).
- `Onboarding.tsx`, `Login.tsx`, `Dashboard.tsx` ← consume the shared `CameraCapture`; no per-page toggle duplication.
- `docker-compose.yml` ← optional `deploy.resources.reservations.devices` GPU reservation for backend (capture-time CUDA optimization only; preview stays client-side).
- No DB migration, no new HTTP route, no new domain entity persisted (preview results are ephemeral, per spec Non-Goals).

**Coverage limitations:** Graph has `D-Snoop-demo-sdd` + `demo-sdd` projects indexed; `frontend/src/__tests__` and `frontend/src/components/__tests__` are in `not_indexed` by ignore rule (deliberate). Overlay code does not yet exist, so evidence was read directly from `CameraCapture.tsx`, `ports.py`, `result_types.py`, `main.py`, `config.py`, `docker-compose.yml`, and `vite.config.ts` rather than graph nodes.

---

## R-1 — Preview detection transport: client-side for v1 (BLOCKING-01 resolved)

**Decision:** **Client-side preview detection for v1.** The live overlay is driven by a **frontend preview-detector adapter** that samples frames from the `<video>` element; no new backend route is introduced. The backend `Detector` port (YuNetDetector / MockDetector, CUDA-accelerated when the host provides it) remains the **capture-time** validation path (exactly-one-face, FR-004) and is untouched. CUDA is therefore a **backend optimization for capture-time detection only** — preview latency is not gated on it.

Frontend adapter interface (new, frontend-only):
```ts
// frontend/src/services/previewDetector.ts
export interface PreviewBox { x:number; y:number; width:number; height:number; }
export interface PreviewLandmark { x:number; y:number; }  // normalized or pixel — adapter normalizes
export interface PreviewDetection { box: PreviewBox; landmarks?: PreviewLandmark[]; score?: number; }
export interface PreviewDetector { detect(video: HTMLVideoElement): Promise<PreviewDetection[]>; }
```
Two adapters behind the interface: `MockPreviewDetector` (deterministic centered box, no landmarks — default for tests/dev; injectable delay/markers for SC-005) and `BrowserFaceDetector` (wraps the browser `FaceDetector` API when available, falling back to mock; a WASM/TFJS BlazeFace adapter may replace it in a later iteration without touching `CameraCapture`). Sampling is throttled (R-2); detection errors yield empty overlay (R-5).

Backend route alternative explicitly **rejected** for v1 and documented as a deferred option: `POST /api/preview/detect` (multipart frame → `Detector` → JSON boxes/landmarks) would add a public route, require privacy review for ephemeral frame handling (no storage guarantee), add network/bandwidth cost per 200 ms, add server load, and require handling concurrent preview streams alongside capture requests. That route would also need auth exemption or session gating and tests mocking a streaming workload. The reserved path `POST /api/preview/detect` is kept free for a future iteration if client-side accuracy proves insufficient — at that point the preview adapter would be swapped to a `ServerPreviewDetector` that POSTs frames through the same throttled sampler, behind the same interface.

**Rationale:** The spec marks this **transport agnostic** but the constitution strict gate asks the plan to pick. Client-side wins on: privacy (preview frames never leave the device), zero new public contract / no privacy-impact review (Constitution VIII), zero backend/QPS impact (the throttle budget in R-2 would otherwise be multiplied by concurrent users), and zero Docker/CUDA coupling for the preview path. It preserves hexagonal isolation (Constitution VII): the preview detector is a **frontend port** mirroring the backend port shape, so swapping to a server adapter later touches only `previewDetector.ts`, not `CameraCapture` internals. CUDA on the host remains useful — `YuNetDetector` in `wire_production_adapters` already benefits from it for the capture still, where latency matters less (single shot) and accuracy matters more.

**Alternatives considered:**
- *Server round-trip with throttled frame POST*: rejected for v1 for the reasons above; reserved as iteration 2.
- *Hybrid (client mock + server fallback toggle)*: rejected — YAGNI; adds branching and two failure modes for no demo value.
- *Backend `Detector` reuse for preview in the same container via polling*: rejected — would need a new route anyway or break hexagonal isolation by importing the backend detector into the frontend.
- *Doing nothing / leave transport undecided*: rejected — strict mode BLOCKING-01 must be resolved in plan, not deferred.

**Trade-off note for the plan gate:** A one-paragraph trade-off table is included in `plan.md` Constitution Check so the orchestrator's strict gate can sign off without re-researching.

---

## R-2 — Throttle budget: ≤5 FPS (~200 ms), decoupled from native video FPS

**Decision:** Detection sampling at **max 5 Hz** (interval ≥200 ms) using a `setInterval` / `requestAnimationFrame`-gated loop that **snapshots** the current `<video>` frame into an offscreen `<canvas>` (optionally downscaled to e.g. 320px long edge for cheap inference). The native `<video>` renders at its own FPS untouched; overlay updates arrive asynchronously via the detector Promise. A `processing` guard discards overlapping ticks: if a detection is in-flight, the next tick is skipped. `AbortController` per toggle-ON epoch: turning OFF or unmounting aborts the pending Promise and clears the timer so stale results never render.

**Rationale:** Spec FR-006 + clarification (200 ms cap) + SC-005 (video stays fluid). Decoupling is standard for preview overlays; throttling keeps CPU/GPU bounded even with `BrowserFaceDetector`. Downscaling the snapshot reduces per-frame work without affecting overlay accuracy (boxes are re-scaled to the displayed video size before draw).

**Alternatives considered:**
- *Per-frame inference (`requestAnimationFrame` without throttle)*: rejected — would exceed CPU budget, especially on CPU-only dev machines.
- *Web Worker offload for v1*: deferred — useful if TFJS is added later, but not required when using `FaceDetector` API or mock. Can be added without changing the interface (adapter internal).
- *Fixed 10 FPS*: rejected — spec budget is ~5 FPS; exceeding it is the constrained dimension.

---

## R-3 — Overlay rendering + mirroring strategy

**Decision:** Add a **second `<canvas>` overlay** absolutely positioned over the `<video>` inside a `position: relative` wrapper. Both `<video>` and overlay `<canvas>` share the same CSS `transform: scaleX(-1)` when the preview is mirrored (front camera selfie expectation, FR-003). This keeps landmark/box math in **unmirrored frame coordinates** and lets the browser handle mirroring — no per-point flip required, fewer bugs. Resize/orientation: `ResizeObserver` on the wrapper + `video.videoWidth/videoHeight` as the intrinsic size; overlay canvas `width/height` are set to wrapper CSS pixels (devicePixelRatio accounted via `canvas.width = cssWidth * dpr`), and boxes are scaled `scaleX = cssWidth / videoWidth`, `scaleY = cssHeight / videoHeight`. Canvas is cleared each draw; boxes drawn with 2px high-contrast stroke (e.g. `#00E5CC`, existing style guide green/cyan) and landmark dots 3px radius.

Fallback if a browser composites `scaleX(-1)` oddly on canvas: flip coordinates instead — `x_mirrored = cssWidth - x_scaled - w_scaled` and per-landmark `x_mirrored = cssWidth - x_scaled`. The helper `mirrorIfNeeded()` is kept so either strategy can be toggled; tests cover both branches.

**Rationale:** Shared CSS transform is the least error-prone and matches the clarification's first option. The overlay canvas is the standard technique (no SVG overhead, trivial high-DPI support). ResizeObserver keeps alignment across window resize and orientation change (FR-014) without polling.

**Alternatives considered:**
- *SVG overlay*: rejected — viable but adds DOM nodes per box/landmark, no advantage over canvas for rectangles/dots.
- *Draw directly on the video frame snapshot*: rejected — would require copying video pixels and lose hardware-accelerated video rendering.
- *Flip coordinates only, no CSS transform*: viable but rejected as default because it requires per-point math; kept as fallback.

---

## R-4 — Toggle control: placement, a11y, state ownership, visibility rule

**Decision:** The toggle is a **`<button>`** (not `<input type=checkbox>`) rendered **inside `CameraCapture`** next to the capture button, only when `streamReady === true` and `active === true`. When the stream is not ready / permission denied, the toggle is **hidden (not rendered)** (FR-015) — no disabled state, no explanatory copy. Props: no prop drilling from pages; internal `const [showOverlay, setShowOverlay] = useState(false)` default OFF. State is **in-memory, per-mount** (no localStorage, no context) — satisfies FR-010 (default OFF on first load; persists while the preview stays mounted; reset on unmount/remount when navigating pages). If cross-page session persistence is ever desired later, lifting `showOverlay` to `App.tsx` context behind the same interface is a one-line move.

Accessible attributes (FR-009): `aria-pressed={showOverlay ? "true" : "false"}`, `aria-label="Show face overlay"` (locale variant `Mostrar contorno facial` when `navigator.language` starts with `es` or app i18n says `es`; v1 may hardcode the Spanish string to match existing copy — `Onboarding.tsx` already uses Spanish — but the constant is extracted as `OVERLAY_TOGGLE_LABEL`). Keyboard: native `<button>` gives Tab + Space/Enter. Visible focus ring via existing focus style (`:focus-visible { outline: 2px solid ... }`). `data-testid="overlay-toggle"` for tests.

Visual: existing style guide — small pill/secondary button (already used for `Capturar`). No new design token for v1; high-contrast + alignment sufficient per Assumptions.

**Rationale:** Single implementation point (FR-008) demands the control live in `CameraCapture`. `aria-pressed` is the correct pattern for a toggle button (`aria-checked` is for `role="switch"`). Hidden-when-not-ready avoids a disabled control that would need extra copy (clarification). Per-mount state is the YAGNI interpretation of "session-scoped while preview stays active" — the simplest that satisfies the spec without adding storage.

**Alternatives considered:**
- *`role="switch"` + `aria-checked`*: valid but rejected for v1 — spec allows either; `aria-pressed` is conventional for buttons and needs no role override.
- *Lifted state in `SessionContext` / `App.tsx`*: rejected for v1 — YAGNI; per-mount already satisfies "persists while preview stays active" when the component stays mounted (e.g., dashboard age flow). Cross-page persistence across unmounts is not required.
- *Disabled toggle when camera not ready*: rejected — spec clarification says hidden.

---

## R-5 — Degradation, flicker smoothing, rapid toggle safety

**Decision:**
- **No-face / no-result**: clear overlay to empty (no toast, no error) — FR-011.
- **Multi-face**: draw N boxes (+ landmarks per box when provided) — FR-012.
- **Detector error / unavailable**: catch → empty overlay → optional non-blocking dismissible notice (e.g., `aria-live="polite"` span "Detección no disponible") — FR-013. Never block `capture()` (capture uses its own backend path).
- **Flicker smoothing** (optional per clarification, best-effort): hold last valid `PreviewDetection[]` for **200 ms** (midpoint of 150–250 ms) and ignore frames with `score < minConfidence` (default 0.5 from config parity; preview adapter may expose it). Implementation: `lastValidRef` + `holdUntilRef = Date.now() + 200` on each successful non-empty result; empty/low-confidence frames within the hold window re-render the last valid boxes instead of clearing. Empty beyond the window → cleared. No toast spamming.
- **Rapid toggle ON/OFF**: each ON epoch gets an incrementing `epochRef`; detection promises capture their epoch and discard on resolution if `epochRef.current !== capturedEpoch` or `showOverlay === false`. Timer/interval cleared synchronously on OFF before state flips; `AbortController` aborts the in-flight `detect()` if the adapter supports it. No leaked listeners/timers/network requests (spec Edge Cases).

**Rationale:** All cases flow from FR-011/FR-013 + Edge Cases. 200 ms hold is inside the allowed 150–250 ms window and visually hides single-frame drops without masking real disappearance. Epoch + abort is the minimal correct concurrency guard for async detectors.

**Alternatives considered:**
- *No smoothing*: acceptable per spec ("optional for v1") but the lightweight hold is trivial and measurably improves SC-001 demos; kept as optional code path with a `HOLD_MS = 200` constant that can be set to 0 to disable.
- *Exponential smoothing / Kalman*: rejected — over-engineered for the demo.

---

## R-6 — Preview frame sampling fidelity and coordinate mapping

**Decision:** Snapshot via `OffscreenCanvas` pattern: `snapshotCanvas.width = snapshotWidth` (e.g., 320 long edge, preserve aspect from `video.videoWidth/video.videoHeight`), `drawImage(video, 0, 0, snapW, snapH)`. Adapter receives the `HTMLVideoElement` directly (or the snapshot `ImageData`/`ImageBitmap` if it prefers pixels); mock adapter returns a pre-scaled centered box mapped back to display CSS pixels. Landmarks, when available, are in the same intrinsic video coordinate space; scaling mirrors the box path: `xCss = x * (cssWidth / videoWidth)`. Mirroring applied via CSS transform so no coordinate flip is needed in the common path.

**Rationale:** Downscaled snapshot reduces per-tick cost; mapping through `videoWidth/videoHeight` → `cssWidth/cssHeight` keeps overlay aligned regardless of responsive sizing or object-fit differences (FR-014).

---

## R-7 — Docker + CUDA: capture-time optimization only

**Decision:** No new image layer or model download for the preview path. Backend `YuNetDetector` (already GPU-capable via OpenCV DNN when built with CUDA) may be built/run with CUDA on hosts that have it. The compose file may gain an **optional** reservation under `backend.deploy.resources.reservations.devices` with `driver: nvidia`, `count: 1`, `capabilities: [gpu]` — guarded by a compose override / profile so CPU-only hosts and CI are unaffected. Frontend preview work stays in the browser; it is not containerized and is not affected by the backend's CUDA choice. No `APP_MODE` change for preview.

**Rationale:** Feature description "Docker is running in host with cuda if needed" is an ops optimization, not a functional requirement (clarification). Keeping CUDA as a capture-time backend concern avoids coupling preview availability to GPU presence (Constitution I demo-first, SC-007 mock-only testability). The `deploy.resources` stanza is the Docker Compose idiomatic way to request GPUs; it is optional and does not break `docker compose up` on hosts without the NVIDIA runtime.

**Alternatives considered:**
- *Add a GPU sidecar / model-serving container*: rejected — YAGNI; YuNet already runs in the backend.
- *Require CUDA for preview*: rejected — violates SC-007 (tests pass without GPU).

---

## R-8 — Testing strategy for the overlay

**Decision:**
- **Frontend unit** (vitest + jsdom + @testing-library/react): mock `navigator.mediaDevices.getUserMedia` with a fake `MediaStream`; mock `HTMLVideoElement` dimensions (`videoWidth=640, videoHeight=480`) via `Object.defineProperty`; mock `PreviewDetector` with deterministic results. Cases: default OFF → no boxes; toggle ON → boxes appear (mock centered box + 2 faux landmarks); toggle OFF → overlay cleared; hidden when `streamReady=false`; `aria-pressed` toggles with clicks and Space/Enter; rapid toggle discards stale promises; ResizeObserver path re-scales; smoothing hold window.
- **Integration (optional, manual)**: exercise with real `FaceDetector` API in a Chrome browser pointed at `http://localhost:5173`; not gated in CI (camera unavailable in CI).
- **Backend**: no new contract/integration tests (no new route). Existing domain + contract suites must still pass. A new `test_domain_purity` extension is not required because no new domain module is added; frontend purity is not enforced by that test.
- **CI**: `vitest run` passes without GPU, without network, without real camera — preview detector defaults to mock in test setup.

**Rationale:** Spec SC-007 requires mock-only testability. Real camera / FaceDetector tests are inherently manual and not CI-gated, consistent with existing camera tests.

---

## Summary of NEEDS CLARIFICATION items resolved

| # | Item | Resolution |
|---|------|------------|
| 1 | Preview detection transport (BLOCKING-01) | **Client-side** for v1 via `PreviewDetector` frontend port; server round-trip `POST /api/preview/detect` reserved but not implemented; CUDA remains capture-time optimization (R-1) |
| 2 | Throttle budget | ≤5 FPS / ≥200 ms interval, decoupled, in-flight guard, per-epoch abort (R-2) |
| 3 | Mirroring + resize alignment | Shared `scaleX(-1)` on video+overlay canvas; ResizeObserver + intrinsic→CSS scaling; flip fallback helper (R-3) |
| 4 | Toggle a11y + visibility | `<button>` `aria-pressed` + `aria-label "Show face overlay"` / `Mostrar contorno facial`; hidden when camera not ready; focus ring; keyboard-native (R-4) |
| 5 | Toggle state ownership | Per-mount `useState(false)` (default OFF, in-memory only; liftable later) (R-4) |
| 6 | Degradation + flicker | Empty overlay on no-face/error; multi-box; 200 ms hold + score threshold smoothing; never blocks capture (R-5) |
| 7 | Rapid toggle safety | Epoch + AbortController + synchronous timer clear; stale results discarded (R-5) |
| 8 | Sampling fidelity | Downscaled offscreen snapshot; intrinsic→CSS scaling (R-6) |
| 9 | Docker/CUDA role | Optional `deploy.resources.reservations.devices` for backend capture-time detector; preview not GPU-gated (R-7) |
| 10 | Testing without GPU/camera | Mock preview detector + mocked MediaDevices in vitest (R-8) |

No item was escalated as BLOCKING beyond R-1, which is resolved above. Strict-mode gate may verify the trade-off note in `plan.md` before marking BLOCKING-01 closed.

