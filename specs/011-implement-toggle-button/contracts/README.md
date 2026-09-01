# Contracts: Live Face Preview Overlay Toggle (011)

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

This feature introduces **no new HTTP API contract**. The preview overlay is **client-side** for v1 (research R-1, plan BLOCKING-01 trade-off); no `POST /api/preview/detect` or other backend route is added.

## HTTP Contracts

| Endpoint | Status |
|----------|--------|
| `POST /api/onboarding` | Reused, unchanged — single still capture at `capture()` time. |
| `POST /api/auth/face-login` | Reused, unchanged — single still capture. |
| `POST /api/analysis/mood`, `POST /api/analysis/age` | Reused — consume the same `capture()` Blob. |
| `GET /api/auth/me`, `POST /api/auth/logout` | Unchanged. |
| `GET /health`, `GET /readyz` | Unchanged. |

**Reserved path (not implemented in v1):** `POST /api/preview/detect` — a throttled multipart frame → boxes/landmarks endpoint (backend `Detector` behind the port, CUDA-optional) is **reserved** for a future iteration if client-side accuracy proves insufficient. If introduced later, it will be an authenticated `POST multipart/form-data` (`frame: file`) returning `200 { detections: { box:{x,y,width,height}, landmarks:{x,y}[]?, score? }[] }` with empty array on no-face, `401 unauthenticated` when session gating is on, `400 invalid_image` on undecodable frame. No decision on it is made in v1.

## Frontend Interface Contract

The **contract for this feature** is the frontend `PreviewDetector` port and the overlay/toggle a11y contract documented in [`preview-overlay.md`](./preview-overlay.md):

- `PreviewDetector.detect(video) -> PreviewDetection[]` — sampling, throttle, and mirroring invariants.
- Overlay canvas: intrinsic → CSS scaling, shared `scaleX(-1)` mirroring, ResizeObserver, dpr awareness.
- Toggle: `aria-pressed` + `aria-label "Show face overlay"` / `Mostrar contorno facial`, hidden when `!streamReady`.

Contract tests for this feature are **frontend vitest** tests (no backend contract suite delta).

