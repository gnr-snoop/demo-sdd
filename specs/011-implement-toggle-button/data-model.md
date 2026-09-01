# Data Model: Live Face Preview Overlay Toggle (011)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

This feature introduces **no new persistent entities**, no DB migration, and no new HTTP contract. All new types are **ephemeral, frontend-only** and live for the lifetime of the preview tick. The `User`, `FaceTemplate`, `AuthSession`, `AnalysisRequest` entities from PRD §7 remain unchanged (Constitution VI / Non-Goals). Detection results used for the overlay are **never stored, logged, or used for enrollment/verification** (spec Non-Goals); only the still capture at `capture()` time flows through the existing onboarding/login/analysis pipelines.

---

## Entities (ephemeral — frontend only)

### Camera Preview (existing, extended)

Live video stream displayed before capture. Reused from `components/CameraCapture.tsx`.

| Attribute | Type | Notes |
|-----------|------|-------|
| `active` | `boolean` | Prop — when true, requests camera + shows preview. |
| `streamReady` | `boolean` | Internal — true after `getUserMedia` resolves and `video.srcObject` set. |
| `videoWidth` / `videoHeight` | `number` | Intrinsic frame size from `HTMLVideoElement.videoWidth/videoHeight` (e.g. 640×480). Source for capture + overlay scaling. |
| `cssWidth` / `cssHeight` | `number` | Displayed size of the wrapper/`<video>` (responsive, ResizeObserver-observed). Source for overlay canvas sizing. |
| `permissionState` | `"granted" \| "denied" \| "pending"` | Derived from `getUserMedia` outcome; drives toggle visibility. |

**Relationships:** 1 Camera Preview has 0..1 Overlay Toggle State; produces 0..N `PreviewDetection` per tick while toggle is ON.

**State transitions (camera):** `pending → granted → streamReady` (toggle rendered) | `pending → denied` (toggle hidden, camera-unavailable copy per PRD §6.2).

### Overlay Toggle State (new, frontend only)

ON/OFF state of the face-metadata overlay.

| Field | Type | Constraints / Behavior |
|-------|------|------------------------|
| `showOverlay` | `boolean` | `false` default (OFF) on first mount; `true` when user activates toggle. |
| `epoch` | `number` | Internal monotonic counter incremented on each ON→OFF/OFF→ON transition; tags pending detector promises so stale results are discarded. |
| `lastValidAt` | `number \| null` | `Date.now()` of last non-empty successful detection; used for 200 ms hold smoothing. |
| `lastValidDetections` | `PreviewDetection[] \| null` | Snapshot of last valid detections, held for 200 ms after empty/low-confidence frame. |

**Persistence:** In-memory `React.useState` per `CameraCapture` mount only. No `localStorage` / cookie / DB. Page navigation that unmounts the component resets to OFF (spec assumption). Lifting to a context is a future swap that does not affect the data shape.

**Validation:** Boolean only; toggle hidden (not rendered) when `!streamReady || !active` (FR-015). When hidden, `showOverlay` is reset to `false` and any pending detection is aborted.

### Face Detection Metadata — Preview (new, frontend only, ephemeral)

Transient per-frame results used only for visualization before capture. Distinct from `FaceTemplate` (PRD §7) and from backend `DetectionResult` (capture-time, `face_count/boxes/score`).

| Attribute | Type | Constraints |
|-----------|------|-------------|
| `box` | `PreviewBox { x, y, width, height }` | Axis-aligned rect in **intrinsic video frame pixels** (`videoWidth/videoHeight` space). `x,y >= 0`, `width,height > 0`. |
| `landmarks` | `PreviewLandmark[]?` (`{x, y}[]`) | Optional points in the same intrinsic space; omitted or empty when the detector returns no landmarks (show box alone, no placeholder). Granularity 5/68 determined by adapter. |
| `score` | `number?` | Optional confidence in `[0,1]`; adapter-defined threshold may filter low scores before render. |
| `frameAt` | `number` | `Date.now()` of the sampled frame; ephemeral, not persisted. |

**Collection:** `PreviewDetection[]` — `[]` = empty overlay (no boxes); `N>0` = one box (+ optional landmarks) per detected face. Multiple faces shown simultaneously without blocking capture (FR-012).

**Lifecycle:** Produced by `PreviewDetector.detect(video)` every ≤5 FPS while `showOverlay===true && streamReady`; rendered on overlay canvas; discarded on next tick or on toggle OFF/unmount. Never stored, never sent to backend.

### PreviewDetector Port / Adapter (new, frontend port)

Frontend hexagonal boundary mirroring the backend `Detector` port shape, but bound to `<video>` rather than `bytes`.

```
interface PreviewDetector {
  detect(video: HTMLVideoElement): Promise<PreviewDetection[]>;
  // Optional: abort signal for cancellation.
  detectWithSignal?(video: HTMLVideoElement, signal: AbortSignal): Promise<PreviewDetection[]>;
}
```

**Adapters:**
- `MockPreviewDetector` — deterministic centered box (`{x: 0.3*W, y: 0.3*H, width: 0.4*W, height: 0.4*H}`) with 2 faux landmarks, injectable `delayMs` + empty/error markers for SC-005 tests. Default in `APP_MODE=mock` and in `vitest` setup.
- `BrowserFaceDetector` — wraps `window.FaceDetector` (Chrome Shape Detection API) when available; falls back to `MockPreviewDetector` otherwise. Future `TFLitePreviewDetector` / `BlazeFace` behind the same interface.

**Adapter contract:** `detect()` never throws to the caller — adapters catch internally and return `[]`; the preview loop also `catch`es → empty overlay + optional `aria-live` notice (FR-013).

---

## Types / Value Objects (TypeScript)

```ts
// frontend/src/services/previewDetector.ts — frontend port
export type PreviewBox = { x:number; y:number; width:number; height:number; };
export type PreviewLandmark = { x:number; y:number; };
export type PreviewDetection = { box: PreviewBox; landmarks?: PreviewLandmark[]; score?: number; frameAt: number; };
export interface PreviewDetector { detect(video: HTMLVideoElement): Promise<PreviewDetection[]>; }

// frontend/src/components/CameraCapture.tsx — toggle state + constants
export const OVERLAY_TOGGLE_TEST_ID = "overlay-toggle";
export const OVERLAY_TOGGLE_LABEL_EN = "Show face overlay";
export const OVERLAY_TOGGLE_LABEL_ES = "Mostrar contorno facial"; // v1 locale variant
export const OVERLAY_TOGGLE_HOLD_MS = 200;    // 150–250 ms window, midpoint
export const OVERLAY_SAMPLE_INTERVAL_MS = 200; // ≤5 FPS cap (FR-006)
export const OVERLAY_MIN_SCORE = 0.5;         // preview confidence gate (adapter-defined)
```

Canvas overlay helper (internal to `CameraCapture`):
```ts
type OverlayDrawArgs = {
  detections: PreviewDetection[];
  videoWidth: number; videoHeight: number; // intrinsic
  cssWidth: number; cssHeight: number;     // displayed
  mirrored: boolean;                       // front-camera selfie
};
function drawOverlay(ctx: CanvasRenderingContext2D, args: OverlayDrawArgs): void;
function mirrorIfNeeded(x: number, w: number, cssWidth: number, mirrored: boolean): number;
```

---

## Alignment & Scaling Invariants

1. **Intrinsic → CSS scaling:** `scaleX = cssWidth / videoWidth`, `scaleY = cssHeight / videoHeight`. Every `box`/`landmark` is mapped through these before draw.
2. **Mirroring:** When `mirrored===true`, both `<video>` and overlay `<canvas>` carry `transform: scaleX(-1)` (primary path). Fallback math for non-CSS path: `x_mirrored = cssWidth - x_scaled - w_scaled`, `lx_mirrored = cssWidth - lx_scaled`.
3. **Resize:** `ResizeObserver` on wrapper + `video.addEventListener('loadedmetadata')` update `cssWidth/cssHeight` → canvas backing store resized → next draw uses new scales (FR-014).
4. **High-DPI:** Canvas backing store `width = cssWidth * devicePixelRatio`, `height = cssHeight * dpr`, `ctx.setTransform(dpr,0,0,dpr,0,0)` before draw; style size stays `cssWidth × cssHeight`.

---

## Validation Rules

| Rule | Applies to | Enforcement |
|------|------------|-------------|
| Default OFF on first mount | Overlay Toggle State | `useState(false)` — no external default. |
| Hidden when `!streamReady` / permission denied | Overlay Toggle | Conditional render `active && streamReady && <button …>` (FR-015). |
| Interval ≥200 ms between detect calls while ON | PreviewDetector loop | `setInterval(200)` or RAF-gated + `lastTickAt` guard; skip tick if `inFlightRef.current === true`. |
| No persistence of preview frames/boxes/landmarks | Face Detection Metadata | Ephemeral arrays + canvas clear on OFF/unmount; lint rule: no `fetch`/`storage` import in preview path. |
| Capture unchanged regardless of toggle state | `capture()` | `capture()` reads `video` only; toggle state not passed to `onCapture` / backend (FR-007). |
| `aria-pressed` reflects ON/OFF | Toggle button | `aria-pressed={showOverlay ? "true" : "false"}` + `aria-label={label}` (FR-009). |

---

## Relationships Diagram (frontend, ephemeral)

```
[Camera Preview] ──1:0..1── [Overlay Toggle State]
        │                          │
        │ samples @ ≤5 FPS if ON   │ controls visibility
        ▼                          ▼
        └──────────> [PreviewDetector (port)] ──produces──> PreviewDetection[] ──draw──> <canvas overlay>
                                   ▲
                          MockPreviewDetector | BrowserFaceDetector
```

Backend remains unchanged:
```
[Camera Preview capture()] ──JPEG Blob──> POST /api/onboarding | POST /api/auth/face-login
                                              │
                                   Detector(backend) / Embedder(backend) — capture-time only
```

---

## Schema / Migrations

**None.** No PostgreSQL change. The existing `users`, `face_templates`, `auth_sessions` tables (specs 001/002) are untouched. Compose `pgdata` volume unchanged.

Docker Compose change is **compose-only, optional, no migration**:
```yaml
# Optional GPU reservation — backend service, capture-time CUDA optimization only.
# Safe to omit on CPU-only hosts / CI. Requires NVIDIA Container Toolkit on host.
backend:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```
When omitted, `YuNetDetector`/`SFaceEmbedder` run on CPU; preview overlay unaffected (client-side).

---

## Ports & Adapters Summary

| Port | Location | Adapter(s) | When |
|------|----------|------------|------|
| `PreviewDetector` (frontend) | `frontend/src/services/previewDetector.ts` | `MockPreviewDetector` (default/test), `BrowserFaceDetector` (shape-detection API) | Preview ticks while toggle ON |
| `Detector` (backend) | `backend/src/face_insight/domain/ports.py` | `MockDetector` / `ScriptableMockDetector` (mock mode), `YuNetDetector` (production, optional CUDA) | `capture()` → onboarding / face-login / mood / age |

