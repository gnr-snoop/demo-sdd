# Quickstart: Live Face Preview Overlay Toggle (011)

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Branch**: `011-implement-toggle-button`

This guide validates the feature end-to-end. All scenarios run **without GPU, without network, without a real detector model** via mocks — per SC-007 and Constitution VII — except the optional manual browser check with a real camera.

---

## Prerequisites

```bash
# From repo root D:\Snoop\demo-sdd
docker compose up --build    # backend :8000, frontend :5173, postgres :5432
# Or for mock-only backend (default, no DB needed for preview itself):
#   APP_MODE=mock docker compose up --build
```

- Node 20+ (frontend), Python 3.11 (backend) if running outside Docker.
- Browser with camera permission (Chrome/Edge latest, secure context `http://localhost:5173` is allowed for `getUserMedia`).
- No GPU required. Host CUDA, if present, is an optimization for capture-time detection only (preview is client-side).

---

## Install & Run (outside Docker, optional)

```bash
# Backend (optional, for targeted backend contract runs — not needed for this feature)
cd backend && pip install -e . && uvicorn face_insight.main:app --reload

# Frontend
cd frontend
npm install
npm run dev -- --host 0.0.0.0   # http://localhost:5173
```

---

## Automated Verification (CI-grade, no camera)

```bash
# Frontend unit — toggle, mirroring, throttle, smoothing, a11y (SC-001/006/007)
cd frontend && npm test           # vitest run — must pass without GPU/camera
# Expected: CameraCapture overlay tests green with mocked MediaDevices + MockPreviewDetector

# Backend — unchanged, must stay green (no new route)
cd backend && python -m pytest tests/unit tests/contract -q
# If using Docker:
docker compose exec backend python -m pytest tests/unit tests/contract -q
```

Frontend test setup mocks:
- `navigator.mediaDevices.getUserMedia` → fake `MediaStream` with `getTracks() => [{stop(){}}]`
- `HTMLVideoElement.videoWidth/videoHeight` → 640×480 via `Object.defineProperty`
- `PreviewDetector` → `MockPreviewDetector` (centered box + 2 faux landmarks; injectable `delayMs`)

---

## Manual Validation Scenarios (with camera)

Each scenario is a runnable script of clicks + observations. Perform on **each** of `/onboarding`, `/login`, and dashboard preview (if present) — the toggle is the same shared `CameraCapture` component (SC-002).

### S-1 — Core toggle ON/OFF + tracking (P1, SC-001)

1. Open `http://localhost:5173/onboarding` → enter `demo@example.com` + check consent → **Solicitar cámara**.
2. **Expect**: plain video preview, **toggle hidden until stream ready**, then toggle button visible with `aria-label "Mostrar contorno facial"` / `Show face overlay` and `aria-pressed="false"` (default OFF, SC-001).
3. Click toggle → **Expect**: `aria-pressed="true"`, a cyan/green 2px box around the face + small dots for eyes/nose/mouth when landmarks available; box tracks movement with ≤200 ms lag (throttled 5 FPS, video itself stays fluid at native FPS). Mirrored selfie preview keeps overlay aligned (shared `scaleX(-1)`).
4. Click toggle again → **Expect**: overlay disappears immediately (≤200 ms after click), video continues, `aria-pressed="false"`. No camera restart.
5. Keyboard: Tab to toggle → Space/Enter flips state, visible focus ring.

### S-2 — Capture neutrality regardless of toggle (SC-004)

1. With toggle **OFF**, press **Capturar** → **Expect**: still JPEG captured and onboarding/login/analysis proceeds exactly as before (same validation, same network payload).
2. Repeat with toggle **ON** and a valid single-face box visible → press **Capturar** → **Expect**: identical behavior; toggle state does not alter crop/validation.

### S-3 — Zero / many faces, empty-overlay contract (SC-003)

1. Toggle ON with **no face** in frame → **Expect**: empty overlay, no error toast, capture still allowed.
2. Toggle ON with **multiple faces** → **Expect**: one box (+ landmarks) per face, capture still allowed; capture-time validation (exactly-one-face) remains the enforcement point at `capture()` (FR-004).

### S-4 — Resilience: slow / failing detector (SC-005)

1. Dev: set `MockPreviewDetector` delay to 1000 ms (or configure `BrowserFaceDetector` to throttle) and open preview with toggle ON + face visible → **Expect**: video stays fluid, overlay updates after ~1s, toggle remains clickable, no frozen preview.
2. Configure mock to throw / return `[]` → **Expect**: preview continues as plain video, overlay shows nothing, optional non-blocking `aria-live="polite"` notice, **capture not blocked**.
3. No GPU / CPU-only host → **Expect**: identical UX, only potentially slower overlay updates.

### S-5 — Mirroring + resize (FR-014, Edge Cases)

1. Front camera → **Expect**: video mirrored (selfie) and boxes/landmarks mirror identically (CSS shared `scaleX(-1)` or flipped coordinates per `mirrorIfNeeded()`).
2. Resize window / rotate device (orientation change) → **Expect**: overlay re-scales proportionally, stays aligned (ResizeObserver path). High-DPI screens render crisp (dpr-aware canvas).

### S-6 — Hidden when camera not ready (FR-015)

1. Block camera permission or open tab without granting → **Expect**: camera-unavailable copy per PRD §6.2, **toggle not rendered** (`queryByTestId('overlay-toggle')` is null), no detection attempted.

### S-7 — Rapid toggle spam (Edge Cases)

1. Toggle ON/OFF rapidly 10× while detection in-flight → **Expect**: last state wins, no leaked timers/requests, no stuck overlay, no crash (epoch + AbortController discard).

### S-8 — Accessibility sweep (SC-006)

```bash
# With the preview active + toggle rendered:
# - Keyboard: Tab → Space/Enter toggles.
# - Screen reader: button announced as "Mostrar contorno facial, toggle button, pressed/not pressed"
#   (NVDA/VoiceOver; or verify via `getByRole('button', {name: /Mostrar contorno facial|Show face overlay/})`
#    and `expect(button).toHaveAttribute('aria-pressed', 'false'|'true')` in vitest).
# - Contrast: 2px cyan/green stroke visible on both light/dark backgrounds (manual glance).
```

---

## Expected Outcomes Checklist

| SC | Criterion | How to verify |
|----|-----------|---------------|
| SC-001 | Toggle ON/OFF within 200 ms, mirrored alignment, tracking | S-1 |
| SC-002 | Same behavior on onboarding/login/dashboard | Repeat S-1 on each page |
| SC-003 | Empty overlay (0 faces) / N boxes (N faces), no block | S-3 |
| SC-004 | Capture succeeds identically in OFF and ON | S-2 |
| SC-005 | Slow/error detector → fluid video, responsive toggle, plain-preview fallback | S-4 |
| SC-006 | Keyboard + `aria-pressed` + focus ring | S-8 + S-1 keyboard step |
| SC-007 | `npm test` passes without GPU/camera (mock detector, mocked MediaDevices) | Automated Verification |

---

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `getUserMedia` fails on `http://` | Use `http://localhost:5173` (secure context) or HTTPS; check browser permission. |
| `FaceDetector is not defined` | Browser does not expose Shape Detection API — overlay falls back to `MockPreviewDetector` (expected). Real WASM model is future work. |
| Overlay misaligned after resize | Ensure `ResizeObserver` polyfill in jsdom is mocked in `setup.ts`; on real browser it is native. |
| Canvas HiDPI blurry | Check `devicePixelRatio` handling — backing store `width = cssWidth * dpr` + `ctx.setTransform(dpr,0,0,dpr,0,0)`. |
| Docker GPU build fails | Remove `deploy.resources.reservations.devices` if host lacks NVIDIA runtime; backend falls back to CPU (preview unaffected). |

---

## Cleanup

```bash
docker compose down
# Optional full prune:
docker compose down --volumes
```

