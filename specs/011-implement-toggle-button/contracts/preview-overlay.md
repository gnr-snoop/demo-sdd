# Contract: Preview Overlay (frontend interface) — 011

**Spec**: [../spec.md](../spec.md) | **Date**: 2026-09-01 | **Status**: Draft (v1 client-side)

This is a **frontend interface contract** (not an HTTP contract). It is the `PreviewDetector` port and the overlay/toggle invariants that `CameraCapture` implements. A `ServerPreviewDetector` adapter posting to `POST /api/preview/detect` may later implement the same interface without changing this contract.

---

## 1. PreviewDetector Port

**Location**: `frontend/src/services/previewDetector.ts`

```ts
export type PreviewBox = { x: number; y: number; width: number; height: number; };
export type PreviewLandmark = { x: number; y: number; };
export type PreviewDetection = {
  box: PreviewBox;
  landmarks?: PreviewLandmark[]; // omitted or empty → show box alone
  score?: number;                // [0,1], optional; adapter may gate < OVERLAY_MIN_SCORE
  frameAt: number;               // Date.now() of sampled frame
};

export interface PreviewDetector {
  /** Detect faces in the current <video> frame. Never throws — returns [] on failure/empty. */
  detect(video: HTMLVideoElement): Promise<PreviewDetection[]>;
}
```

**Invariants:**
- Coordinates are in **intrinsic video frame pixels** (`video.videoWidth / video.videoHeight` space), axis-aligned.
- All values `x,y >= 0`, `width,height > 0`. Boxes outside frame are clamped by the renderer (not the adapter).
- `landmarks` when present are in the same intrinsic space; absence → renderer shows box alone (no placeholder dots).
- `detect()` must not throw to the loop — adapters catch and return `[]`; the loop catches any residual reject → empty overlay.
- **Throttle:** caller guarantees `detect()` is invoked at most once every `OVERLAY_SAMPLE_INTERVAL_MS = 200` ms (≤5 FPS) while `showOverlay===true`. In-flight guard skips overlapping ticks.
- **Ephemeral:** returned detections are discarded after render; no storage, no network in the default adapters.

**Adapters (behind the interface):**

| Adapter | Source | Production |
|---------|--------|------------|
| `MockPreviewDetector` | Deterministic centered box + 2 faux landmarks, injectable `delayMs`/empty/error. | Default in `APP_MODE=mock`, `vitest`, and fallback when native API unavailable. |
| `BrowserFaceDetector` | Wraps `window.FaceDetector` (Chrome Shape Detection API) when `typeof FaceDetector !== 'undefined'`. Signature: `new FaceDetector({fastMode:true, maxDetectedFaces:5})`. | Uses native fast detector; falls back to `MockPreviewDetector` if unavailable/throws. |

Future `TFLitePreviewDetector` / `BlazeFace` (TFJS) ports implement the same interface; `CameraCapture` is agnostic.

---

## 2. CameraCapture Overlay Extension

**Location**: `frontend/src/components/CameraCapture.tsx` (shared, single implementation point — FR-008)

**Props (existing, unchanged):**
```ts
export interface CameraCaptureProps {
  active: boolean;
  onCapture: (blob: Blob) => void;
  onPermissionGranted: () => void;
  onPermissionDenied: () => void;
  disabled?: boolean;
  captureButtonLabel?: string;
  captureButtonAriaLabel?: string;
  captureButtonTestId?: string;
}
```
No new prop is required for the overlay — toggle state is internal `useState(false)` default OFF. A future lift (e.g., controlled toggle from `App.tsx`) would add an optional `defaultShowOverlay?: boolean` without breaking.

**Internal constants:**
```ts
export const OVERLAY_TOGGLE_TEST_ID = "overlay-toggle";
export const OVERLAY_TOGGLE_LABEL_EN = "Show face overlay";
export const OVERLAY_TOGGLE_LABEL_ES = "Mostrar contorno facial";
export const OVERLAY_SAMPLE_INTERVAL_MS = 200; // throttle cap
export const OVERLAY_HOLD_MS = 200;            // flicker hold window (150–250 ms pick)
export const OVERLAY_MIN_SCORE = 0.5;          // preview confidence gate
```

**Visibility rule (FR-015):** The toggle `<button>` is rendered only when `active && streamReady`. When `!streamReady` (pending/denied), it is **not rendered** (`queryByTestId` is null) and no detection is attempted.

**Mirroring + resize (FR-003/FR-014):**
- Wrapper: `position: relative` containing `<video>` + `<canvas data-testid="face-overlay">` (`position:absolute; inset:0; pointer-events:none`).
- Mirroring: when front-camera selfie (default `true`; `facingMode==="user"`), both `<video>` and overlay `<canvas>` carry `style={{ transform: "scaleX(-1)" }}`. Fallback helper `mirrorIfNeeded(x,w,cssWidth,mirrored)` provides flipped coordinates if CSS path is ever removed.
- Resize: `ResizeObserver` on wrapper + `loadedmetadata` listener → `cssWidth/cssHeight` → backing store `canvas.width = cssWidth*dpr`, `canvas.height = cssHeight*dpr` + `ctx.setTransform(dpr,0,0,dpr,0,0)` then per-tick scalable draw with `scaleX = cssWidth/videoWidth`, `scaleY = cssHeight/videoHeight`.

**Drawing:** Clear `ctx` each tick; for each detection → `strokeRect` 2px `#00E5CC` (high-contrast) + small filled circles radius 3px for landmarks. Empty array → cleared canvas (empty overlay, no error toast). Errors → empty overlay + optional `aria-live="polite"` notice "Detección no disponible" (FR-013), dismissible, never blocks `capture()`.

**Sampling loop (FR-006, R-2/R-5):**
```
on showOverlay transition false→true:
  epochRef.current += 1; sampleImmediately();
  intervalId = setInterval(tick, 200);

tick():
  if inFlightRef.current) return;            // decoupled, skip overlapping
  if !showOverlay || !streamReady) return;
  inFlightRef.current = true; epoch = epochRef.current;
  detections = await detector.detect(video).catch(()=>[]);
  if epoch !== epochRef.current || !showOverlay) { inFlightRef.current=false; return; } // stale discard
  // smoothing: hold last valid 200 ms
  detections = applyHoldSmoothing(detections, lastValidRef, HOLD_MS, MIN_SCORE);
  drawOverlay(ctx, detections mapped cssWidth/cssHeight [+ mirrored]);
  inFlightRef.current = false;

on showOverlay true→false or unmount:
  clearInterval(intervalId); epochRef.current += 1; abortController?.abort();
  clear overlay canvas; lastValidRef.current = null;
```
`capture()` path is independent — reads `video` directly, does not read toggle state, does not go through `PreviewDetector` (FR-007).

---

## 3. Toggle A11y Contract (FR-009)

**Element:** `<button>` (native, focusable, Space/Enter operable, visible focus ring via `:focus-visible`).

**Accessible name:**
- `aria-label={i18n.isSpanish ? OVERLAY_TOGGLE_LABEL_ES : OVERLAY_TOGGLE_LABEL_EN}` — canonical `Show face overlay` / `Mostrar contorno facial`.
- `data-testid={OVERLAY_TOGGLE_TEST_ID}` for tests.

**State exposure:** `aria-pressed={showOverlay ? "true" : "false"}`. Do **not** use `role="switch"` / `aria-checked` in v1 (spec allows either; `aria-pressed` is the button pattern).

**Keyboard:** Tab reachable; Space/Enter toggles.

**Test assertions (vitest + @testing-library):**
```ts
const btn = getByRole('button', { name: /Show face overlay|Mostrar contorno facial/ });
expect(btn).toHaveAttribute('aria-pressed', 'false'); // default OFF
await user.click(btn);
expect(btn).toHaveAttribute('aria-pressed', 'true');
await user.keyboard('{Tab}'); // focus
await user.keyboard(' ');      // Space toggles
expect(btn).toHaveAttribute('aria-pressed', 'false');
```

---

## 4. Non-Goals / Out-of-Scope (enforced by this contract)

- No `POST /api/preview/detect` in v1 (see `README.md` reserved path).
- No persisted boxes/landmarks, no logging of preview frames, no new DB entity.
- No capture validation change — preview overlay never blocks `capture()`; `exactly-one-face` remains capture-time (backend `Detector`).
- No liveness / 1:N search / anti-spoofing.

