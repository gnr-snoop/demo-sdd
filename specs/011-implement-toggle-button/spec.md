# Feature Specification: Live Face Preview Overlay Toggle

**Feature Branch**: `011-implement-toggle-button`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "implement a toggle button to show face bbox and landmarks in camera preview previous to capture. If the toggle is on, show metadata, if off only show camera preview. Docker is running in host with cuda if needed"

## Clarifications

### Session 2026-09-01

- Q: What face metadata is shown when the toggle is ON — only bounding box, or bounding box + facial landmarks? -> A: Bounding box **and** facial landmarks (e.g., eyes, nose, mouth points) when the underlying detector provides them; if the detector only returns a box, the box alone is shown and landmarks are omitted without error. This keeps the spec compatible with both lightweight and full detectors while stating the desired completeness.
- Q: Where does the detection that feeds the preview overlay run — client-side or server-side — and does the host CUDA matter? -> A: Detection for the live preview may run either client-side or as a lightweight server round-trip; the host Docker + CUDA availability is an **ops optimization** (GPU-accelerated inference when available) not a functional requirement. Domain logic stays behind the existing detector port; production may use a GPU-capable adapter while tests and local dev use the existing mock/fallback. No change to the hexagonal isolation (Constitution VII).
- Q: On which screens must the toggle be available — onboarding only, or also login and dashboard? -> A: The toggle lives **wherever the live camera preview is shown before capture** and is implemented once in the shared camera preview component. Consequently it is available in onboarding, login, and any dashboard preview that reuses that component; it is not duplicated per page.
- Q: What is the default state of the toggle and does it persist? -> A: Default is **OFF** (plain camera preview) on first load; within a session the toggle state persists while the preview stays active (so flipping screens that keep the same component does not reset it). No cross-session persistence is required (YAGNI, demo-first).
- Q: How does the system behave when no face or multiple faces are visible in the live preview? -> A: The overlay simply shows one box + landmarks per detected face, or nothing if no face is detected; it never blocks capture by itself. Validation that blocks onboarding/login on zero/multiple faces still happens **only at capture time** (PRD FR-004), not during preview.
- Q: How is overlay alignment handled when the front-camera preview is mirrored (selfie view)? -> A: The live preview is presented mirrored horizontally for user-facing cameras (standard selfie expectation). The overlay layer is mirrored identically so boxes and landmarks stay aligned with the mirrored face: either the video and overlay share the same CSS `scaleX(-1)` transform, or bbox x-coordinates are flipped (`x_mirrored = videoWidth - x - w`) and landmark points are flipped accordingly before drawing. No user setting for mirroring is required for v1.
- Q: What is the deterministic visibility of the toggle when the camera is not ready — hidden or disabled? -> A: The toggle is **hidden (not rendered)** when the camera stream is not ready or permission is denied/unavailable, and rendered + enabled only when the preview is active. This avoids a disabled control that would require extra explanatory copy; camera-unavailable copy remains per PRD §6.2.
- Q: What target sampling/throttle rate governs preview detection while keeping video fluid? -> A: Preview detection is **throttled, decoupled from native video FPS**: at most ~5 FPS (every ~200 ms) sampled from the video element. The video itself renders at native frame rate; overlay updates arrive asynchronously on detection results. Faster detectors may deliver sooner but must not exceed the throttle cap; slower detectors simply delay overlay updates without freezing video. No per-frame inference is required.
- Q: What is the canonical accessible name and state pattern for the toggle? -> A: Accessible name is **"Show face overlay"** (Spanish equivalent `Mostrar contorno facial` if the app locale is Spanish, following the existing i18n/style guide). The control exposes ON/OFF programmatically via `aria-pressed` (button) or `aria-checked` (switch) and is keyboard-operable (Tab focus, Space/Enter toggle) with visible focus ring. State announcement is required per SC-006.
- Q: Should low-confidence flicker be smoothed in the preview overlay? -> A: Single-frame low-confidence flicker may be lightly smoothed client-side by holding the last valid result for 150–250 ms and/or ignoring results below a minimal adapter-defined confidence threshold, but smoothing is **optional for v1** and best-effort. The overlay must never spam error toasts; empty result is rendered as empty overlay. Any filtering is ephemeral and does not affect capture-time validation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Toggle face overlay on live preview before capture (Priority: P1)

A person who has granted camera permission sees a live camera preview. A clearly labeled toggle button lets them switch between a plain preview and a preview that overlays face metadata (bounding box and, when available, facial landmarks) on the live video before they press capture. This helps them frame their face correctly and understand what the system sees, without affecting the capture itself.

**Why this priority**: This is the core value of the feature — visual feedback before capture that improves framing and trust. Without it, there is no feature. It is independently demonstrable: a preview with a working toggle is a viable increment even if no other screen is updated, because the shared preview component is the single implementation point.

**Independent Test**: Can be fully tested by opening any view that shows the live camera preview, verifying the preview renders with the toggle in OFF by default, turning the toggle ON and observing boxes/landmarks appear and track the face in real time, turning it OFF again and observing the overlay disappear while the preview continues, and finally pressing capture to confirm capture still works in both states.

**Acceptance Scenarios**:

1. **Given** the camera preview is active and the toggle is OFF, **When** the user looks at the preview, **Then** they see only the plain video with no boxes or landmarks.
2. **Given** the preview is active and the toggle is OFF, **When** the user activates the toggle, **Then** the preview shows a bounding box around each detected face and landmarks (eyes/nose/mouth) when the detector provides them, updated continuously as the person moves.
3. **Given** the preview is active and the toggle is ON with an overlay visible, **When** the user deactivates the toggle, **Then** the overlay disappears immediately and the plain preview remains, without restarting the camera.
4. **Given** the preview is active in either toggle state, **When** the user presses capture, **Then** a still image is captured and sent for processing exactly as before (the toggle does not alter capture behavior, crop, or validation).
5. **Given** the camera permission has not yet been granted or the stream is not ready, **When** the preview area is rendered, **Then** the toggle is hidden (not rendered) and no overlay is attempted.

---

### User Story 2 - Consistent toggle across onboarding, login, and dashboard previews (Priority: P2)

A person encounters the same camera preview experience whether they are in onboarding, login, or the authenticated dashboard. The toggle behaves and looks identically in each context because it is part of the shared preview component, not duplicated per page.

**Why this priority**: The PRD defines three places where the camera preview appears (`/onboarding`, `/login`, `/dashboard`). Implementing the toggle once and reusing it guarantees consistency and reduces maintenance, but the feature still delivers value if only one context is wired first — hence P2, after the core toggle exists.

**Independent Test**: Can be fully tested by navigating to onboarding and verifying the toggle works there, then to login and verifying the same toggle works there, then to dashboard preview (if present) and verifying the same behavior. Each page can be verified independently; success on one page demonstrates the shared component, success on all three demonstrates full coverage.

**Acceptance Scenarios**:

1. **Given** the user is on the onboarding page with the camera active, **When** they interact with the toggle, **Then** the same overlay behavior described in Story 1 occurs.
2. **Given** the user is on the login page with the camera active, **When** they interact with the toggle, **Then** the same overlay behavior occurs and does not interfere with the identifier input or the login capture flow (PRD §6.3).
3. **Given** the user is on the dashboard with an active camera preview, **When** they interact with the toggle (if a preview is shown there), **Then** the same overlay behavior occurs and does not interfere with the analysis buttons (mood/age, PRD §6.4).
4. **Given** the user switches between pages that reuse the preview component without a full reload, **When** they return to a preview, **Then** the toggle retains its last ON/OFF state within the session (default OFF on first load).

---

### User Story 3 - Responsive, degraded preview when detection is slow or unavailable (Priority: P3)

A person using the preview — whether on a GPU-equipped host via Docker or on a CPU-only dev machine, or in tests with mocks — experiences a smooth camera preview regardless of detection latency. If detection is slow, temporarily unavailable, or returns no results, the preview remains usable and the toggle remains responsive; the system degrades gracefully rather than freezing or crashing.

**Why this priority**: The feature description explicitly notes that Docker with CUDA is available on the host if needed, but the constitution requires that domain tests run without GPU and without real models (Principle VII, mocks for dev/tests). The overlay must therefore be resilient to model latency and to the absence of a GPU. This story is testable independently by throttling or disabling detection.

**Independent Test**: Can be fully tested by activating the preview with the toggle ON under three conditions: (a) with a fast detector, (b) with an artificially slow detector, and (c) with a mock detector that returns empty results or errors. In all cases the camera video stays fluid, the toggle remains clickable, and the overlay either tracks, updates with a short delay, or shows nothing — but never blocks capture or crashes the page.

**Acceptance Scenarios**:

1. **Given** the toggle is ON and a face is visible, **When** the detector takes longer than a single video frame to respond, **Then** the camera video continues to render smoothly and the overlay updates as soon as a result arrives (no frozen video, no dropped camera stream).
2. **Given** the toggle is ON and no face is detected in the current frame, **When** the user looks at the preview, **Then** no box or landmarks are shown (empty overlay), and no error message is displayed — the absence of a detection is not treated as a failure.
3. **Given** the toggle is ON and multiple faces appear in the frame, **When** the detector returns multiple results, **Then** a box (and landmarks if available) is shown for each face, without blocking capture; capture-time validation (PRD FR-004, exactly-one-face) still applies only when the user presses capture.
4. **Given** the detector adapter fails or is unavailable (model not loaded, server error, or mock configured to error), **When** the toggle is ON, **Then** the preview continues as plain video, the overlay shows nothing, and a non-blocking, dismissible notice may be shown without preventing capture.
5. **Given** the environment has no GPU or the detector is running in CPU/mock mode, **When** the toggle is used, **Then** the feature works identically from the user's perspective, only potentially slower — no setup or code change is required from the user.

---

### Edge Cases

- What happens when the detector returns a bounding box but no landmarks (lightweight model)? Show the box alone; do not display placeholder or broken landmark points.
- What happens when the user rapidly toggles ON/OFF multiple times per second? The overlay must not leak listeners, timers, or network requests; the last toggle state wins and no crash or stuck overlay occurs. Pending detections from the previous ON period are discarded.
- What happens when the video element is resized (window resize, orientation change, responsive layout) or is mirrored for selfie view? The overlay scales proportionally and preserves mirroring so boxes and landmarks remain aligned with the face.
- What happens when camera permission is denied or the camera becomes unavailable after being granted? The preview shows the existing camera-unavailable state (PRD §6.2), the toggle is **hidden (not rendered)**, and no overlay work is attempted.
- What happens when detection confidence is low or flickers frame-to-frame? The overlay may briefly appear/disappear; it must not spam the user with error toasts or block capture. Optional lightweight smoothing is allowed: hold last valid result for 150–250 ms and/or ignore results below adapter-defined threshold. No smoothing is required for v1; empty overlay when no valid result is acceptable.
- What happens when the user navigates away from the preview and back? The camera stream is reacquired per existing behavior; the toggle resets to its session-persisted in-memory state (default OFF on first load) and does not retain stale boxes from the previous session.
- What happens when the host Docker environment has CUDA versus when it does not? No functional difference is visible to the user; CUDA is purely a performance optimization for the detector adapter and must not be required to run the feature or the test suite.
- What happens when the preview is used in a test environment with a mocked camera (`MediaDevices` mock) and no real video? The toggle renders and can be exercised; overlay rendering can be verified against mock detections without needing a real camera or GPU.
- What happens when the detector is throttled to ~5 FPS? Video remains fluid at native FPS; overlay updates at most every ~200 ms. Verification is that detection sampling does not block the render loop.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a live camera preview that shows video from the device camera before a still capture is taken.
- **FR-002**: The system MUST provide a single toggle control (button or switch) visible alongside the live preview that lets the user switch the face-metadata overlay ON and OFF without restarting the camera stream.
- **FR-003**: When the toggle is ON, the system MUST overlay a bounding box for each face detected in the current preview frame, positioned and scaled to align with the face in the video. For front/user-facing cameras the preview is mirrored; the overlay MUST mirror identically (shared `scaleX(-1)` transform or flipped x-coordinates `x_mirrored = width - x - w`) so boxes remain aligned with the mirrored face.
- **FR-004**: When the toggle is ON and the detector provides facial landmarks (e.g., eyes, nose, mouth points), the system MUST overlay those landmarks aligned to the video (also mirrored when preview is mirrored); when landmarks are not provided, the system MUST show only the bounding box without error.
- **FR-005**: When the toggle is OFF, the system MUST show only the plain camera preview with no boxes, landmarks, or other face metadata overlaid.
- **FR-006**: The overlay MUST update continuously on the live preview (tracking movement) while the toggle is ON, and MUST disappear immediately when the toggle is switched OFF. Detection sampling for preview is throttled to at most ~5 FPS (~200 ms interval) decoupled from native video FPS; overlay updates arrive asynchronously without freezing video.
- **FR-007**: The toggle and overlay MUST NOT alter the still-capture behavior: pressing capture in either toggle state MUST produce the same JPEG still from the video and follow the existing capture/validation flow (PRD FR-004, FR-011).
- **FR-008**: The toggle control MUST be implemented once in the shared camera preview component and be available wherever that component is used (onboarding, login, and any dashboard preview), ensuring consistent behavior and labeling.
- **FR-009**: The toggle MUST be keyboard-accessible (focusable, operable via Space/Enter), have the canonical accessible name **"Show face overlay"** (or locale equivalent per style guide), and indicate its ON/OFF state programmatically via `aria-pressed` (button) or `aria-checked` (switch) with visible focus ring.
- **FR-010**: The system MUST default the toggle to OFF on first load of a preview; within a continuous session where the preview component stays mounted, the toggle state MUST persist in-memory until the user changes it (no localStorage / cross-session persistence required).
- **FR-011**: When no face is detected while the toggle is ON, the system MUST show an empty overlay (no boxes) and MUST NOT display an error or block capture. Transient flicker may be lightly debounced by holding last valid result 150–250 ms, but empty overlay is the steady state when no face present.
- **FR-012**: When multiple faces are visible while the toggle is ON, the system MUST show a box (and landmarks if available) for each detected face; the overlay itself MUST NOT block capture — capture-time validation for exactly-one-face (PRD FR-004) remains the enforcement point.
- **FR-013**: When the detector is slow, temporarily unavailable, or returns an error while the toggle is ON, the system MUST keep the camera video fluid, keep the toggle responsive, and degrade to showing no overlay (with an optional, non-blocking, dismissible notice) without preventing capture.
- **FR-014**: The system MUST handle video resize, orientation change, and responsive layout changes by keeping the overlay aligned and proportionally scaled to the video (and preserve mirroring).
- **FR-015**: When the camera stream is not ready or permission is denied/unavailable, the system MUST **hide (not render)** the toggle and MUST NOT attempt face detection or overlay rendering.
- **FR-016**: The face detection capability that feeds the overlay MUST be accessed behind the existing detector port/adapter boundary (Constitution VII — no direct model import in domain), allowing a GPU-accelerated adapter in production (Docker with CUDA on host when available) and a mock/fallback adapter in development and tests.
- **FR-017**: The system MUST NOT require a GPU to run in development or to pass the test suite; all domain and contract tests for this feature MUST be runnable with a mock detector, without GPU and without network access.

### Key Entities *(include if feature involves data)*

- **Camera Preview**: The live video stream from the device camera displayed before capture. Attributes: stream readiness, video dimensions, permission state. It is the canvas on which the overlay is drawn and the source for the still capture.
- **Overlay Toggle State**: The ON/OFF state of the face-metadata overlay. Attributes: current value (ON/OFF), default (OFF), session-scoped persistence. It controls whether face metadata is rendered on the preview.
- **Face Detection Metadata (Preview)**: Transient, per-frame results used only for visualization before capture. Attributes: bounding box (position and size relative to the frame), optional landmarks (set of points, e.g., eyes/nose/mouth), confidence/detection count. Not persisted; distinct from the embedding/template stored at onboarding (PRD §7 `FaceTemplate`).
- **Detector Port/Adapter**: The hexagonal boundary that provides face localization. The overlay consumes its results; domain code does not depend on a concrete model. Production may use a GPU-capable adapter (CUDA when available); development and tests use a mock adapter.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the camera active, a user can switch the overlay ON and see a face box (and landmarks when available) track their face in the live preview, and switch it OFF and see the plain preview, with the transition completing within 200 ms after the toggle interaction. Mirrored selfie preview keeps overlay aligned.
- **SC-002**: The toggle works identically in onboarding and login (and any dashboard preview that reuses the shared preview component), verified by completing the toggle ON/OFF and capture flow successfully on each of those pages without page-specific failures.
- **SC-003**: When the toggle is ON and no face is present, no overlay is shown and no error blocks the user; when multiple faces are present, a box is shown per face — both verified by manual preview with zero/one/multiple faces visible.
- **SC-004**: Capture succeeds with the same result and validation behavior regardless of toggle state — verified by capturing in OFF and in ON and confirming both produce a valid still that follows the existing onboarding/login validation (PRD AC-001..AC-009).
- **SC-005**: With a slow or failing detector, the camera video remains fluid (no frozen preview, native FPS maintained while preview detection is throttled ≤5 FPS) and the toggle remains operable; the feature degrades to a plain preview without requiring a page reload — verified by simulating detector delay/error while the preview is active.
- **SC-006**: All keyboard and assistive-technology checks pass for the toggle: the control is reachable by keyboard (Tab, Space/Enter), its canonical name "Show face overlay" and ON/OFF `aria-pressed`/`aria-checked` state are announced, with visible focus ring.
- **SC-007**: The test suite for this feature passes without GPU and without network, using the mock detector adapter — verified by running domain and preview-component tests on a CPU-only environment. Mock can inject mirrored-coordinate cases and throttle intervals.

## Assumptions

- The existing shared camera preview component (`CameraCapture`) is the single implementation point; onboarding, login, and dashboard will consume it rather than duplicating preview logic.
- Bounding boxes are axis-aligned rectangles in preview-frame coordinates; landmarks, when provided, are points in the same coordinate space. The overlay is drawn on a canvas or equivalent layer aligned to the `<video>` element. When preview is mirrored for selfie view, both video and overlay are mirrored identically (shared `scaleX(-1)` or flipped coordinates per Clarification Session 2026-09-01).
- Preview-frame detection is throttled to at most ~5 FPS (~200 ms interval) sampled from the video element, decoupled from native video FPS; video stays fluid at native rate while overlay updates asynchronously. This replaces the earlier vague "a few FPS" and is the performance budget for planning.
- The host running Docker may have CUDA-capable GPUs; when present, a production detector adapter may leverage GPU acceleration for lower latency, but this is an optimization and not a prerequisite for correctness or for running tests.
- Facial landmark granularity (5-point, 68-point, etc.) is determined by the concrete detector adapter; the spec requires only that whatever landmarks the adapter returns are rendered when the toggle is ON.
- Preview detection results are ephemeral and are not stored, logged, or used for enrollment/verification; only the still capture at the moment the user presses capture is processed through the existing onboarding/login/analysis flows.
- The visual design of the toggle and overlay (colors, line thickness, landmark dot size) follows the existing frontend style guide where applicable and does not require a separate design token proposal for v1; sufficient contrast and alignment with the video are assumed. Overlay uses a high-contrast stroke (e.g., cyan/green, 2 px) and small landmark dots visible on varied backgrounds.
- The existing camera permission, camera-unavailable, and capture flows (including mocks of `MediaDevices` for tests) remain unchanged except for the addition of the overlay layer. Toggle is hidden (not rendered) when no preview is active, per FR-015.
- Toggle state persistence is in-memory React/component state only, scoped to the mounted preview component lifecycle within a page session; no localStorage, cookie, or cross-session persistence is introduced (YAGNI).

## Non-Goals

- Replacing or altering capture-time face validation (exactly-one-face, quality checks, embedding generation) — preview overlay is visualization only.
- Adding liveness detection, anti-spoofing, or 1:N face search (explicitly out of scope per PRD §4 and Constitution VIII).
- Persisting, logging, or displaying preview detection results beyond the live overlay (no storage of preview frames, boxes, or landmarks).
- Providing server-side recording, streaming analysis, or continuous video analytics (analysis remains on-demand from explicit captures per PRD §6.4).
- Introducing new routes, authentication flows, or database entities; no change to the PRD §7 data model (`User`, `FaceTemplate`, `AuthSession`) is required for this feature.
- Requiring GPU or CUDA for development, CI, or test execution; mocks remain the default for non-production environments.

## Dependencies

- Existing camera preview component and `getUserMedia` permission flow.
- Existing detector port and its mock adapter; concrete production adapter (e.g., YOLO/YuNet family) may be GPU-accelerated inside Docker when CUDA is available on the host.
- Docker Compose stack (Constitution IV) for production deployment; no change to compose topology is required beyond an optional GPU runtime flag for the backend service when CUDA is used.

## Traceability

- PRD §6.2 step 5 (preview), PRD §6.3 (login preview), PRD §6.4 (dashboard preview), PRD FR-004 (exactly-one-face at capture), PRD FR-005/FR-011 (detector + capture), PRD AC-001..AC-009 (overlay must not break any acceptance criterion).
- Constitution I (demo-first), IV (Docker Compose + CUDA host), V/VI (no change to image storage or DB), VII (ports-and-adapters isolation for detector), VIII (no security/identity hardening implied by overlay).
