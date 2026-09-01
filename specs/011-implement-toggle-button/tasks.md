# Tasks: Live Face Preview Overlay Toggle (011)

**Input**: Design documents from `/specs/011-implement-toggle-button/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md
**Constitution**: `.specify/memory/constitution.md` v1.0.0 — demo-first, hexagonal, Docker Compose, no GPU required for tests
**Branch**: `011-implement-toggle-button` | **Date**: 2026-09-01 | **Stack**: Python 3.11 FastAPI + React 18.3/Vite 5.4 + PostgreSQL 16-alpine

**Organization**: Tasks grouped by user story for independent implementation and testing. Each story is independently testable; shared primitives live in Foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/` at repo root
- **Monorepo**: `backend/` + `frontend/` + `docker-compose.yml`
- Paths below assume web app layout per plan.md §Project Structure — adjust only if structure file moves

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Validate branch, toolchain, and single implementation point before any code change

- [X] T001 Verify feature branch `011-implement-toggle-button` docs exist: `specs/011-implement-toggle-button/spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/preview-overlay.md` in specs/011-implement-toggle-button/
- [X] T002 Run baseline verification `cd frontend && npm install && npx tsc --noEmit && npm test` and `cd backend && python -m pytest tests/unit tests/contract -q` to confirm green baseline before overlay changes in frontend/package.json and backend/pyproject.toml
- [X] T003 [P] Audit existing shared preview surface `frontend/src/components/CameraCapture.tsx` and its consumers `frontend/src/pages/Onboarding.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/Dashboard.tsx` to confirm single implementation point (FR-008) and capture via `<video>` + hidden `<canvas>` + `capture()` handle

**Checkpoint**: Branch + toolchain + shared component audited — foundational work may begin

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Frontend PreviewDetector port + mock/browser adapters + test harness — MUST complete before ANY user story work. No backend route, no DB migration.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create PreviewDetector port types and interface in `frontend/src/services/previewDetector.ts` — `PreviewBox`, `PreviewLandmark`, `PreviewDetection {box, landmarks?, score?, frameAt}`, `PreviewDetector { detect(video: HTMLVideoElement): Promise<PreviewDetection[]> }` per data-model.md and contracts/preview-overlay.md §1
- [X] T005 [P] Implement `MockPreviewDetector` adapter in `frontend/src/services/previewDetector.ts` — deterministic centered box `{x:0.3*W,y:0.3*H,w:0.4*W,h:0.4*H}` plus 2 faux landmarks, injectable `delayMs`/`shouldError`/`empty` modes for SC-005 tests, `detect()` never throws (returns `[]` on error)
- [X] T006 [P] Implement `BrowserFaceDetector` adapter in `frontend/src/services/previewDetector.ts` — wraps `window.FaceDetector` (`{fastMode:true,maxDetectedFaces:5}`) when `typeof FaceDetector !== 'undefined'`, falls back to `MockPreviewDetector` otherwise, normalizes coordinates to intrinsic `videoWidth/videoHeight` space
- [X] T007 [P] Enhance frontend test harness in `frontend/src/__tests__/setup.ts` — mock `navigator.mediaDevices.getUserMedia` → fake `MediaStream` with `getTracks() => [{stop(){}}]`, `HTMLVideoElement.videoWidth/videoHeight` via `Object.defineProperty` (640×480), `window.FaceDetector` availability stub, `ResizeObserver` mock with `observe/unobserve/disconnect`, `devicePixelRatio` handling
- [X] T008 Define overlay constants in `frontend/src/components/CameraCapture.tsx` (or exported from `frontend/src/services/previewDetector.ts`) — `OVERLAY_TOGGLE_TEST_ID="overlay-toggle"`, `OVERLAY_TOGGLE_LABEL_EN="Show face overlay"`, `OVERLAY_TOGGLE_LABEL_ES="Mostrar contorno facial"`, `OVERLAY_SAMPLE_INTERVAL_MS=200`, `OVERLAY_HOLD_MS=200`, `OVERLAY_MIN_SCORE=0.5` per data-model.md §Types
- [X] T009 Verify foundational compilation `cd frontend && npx tsc --noEmit` passes and `vitest run` baseline still green with mocked MediaDevices (no GPU, no network required per SC-007)

**Checkpoint**: Foundation ready — `PreviewDetector` port + 2 adapters + constants + test harness compile and mock-only tests pass — user stories can now begin in parallel

---

## Phase 3: User Story 1 - Toggle face overlay on live preview before capture (Priority: P1) 🎯 MVP

**Goal**: Person with camera permission sees live preview with a toggle that shows bbox + landmarks when ON and plain preview when OFF, without restarting the stream and without altering capture.

**Independent Test**: Open any view with live preview (`/onboarding`, `/login`, or dashboard preview), verify plain preview with toggle OFF default, click toggle ON → boxes/landmarks track movement, click OFF → overlay disappears while preview continues, press capture in both states → same JPEG still + validation flow (spec §User Story 1 Independent Test, quickstart S-1 + S-2).

### Tests for User Story 1 (write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T010 [P] [US1] Write vitest for default OFF plain preview and hidden-when-not-ready in `frontend/src/components/__tests__/CameraCapture.overlay.test.tsx` — `active && !streamReady` → `queryByTestId("overlay-toggle")` is null, no `detect()` called, canvas cleared (FR-015, SC-001 scenario 5)
- [X] T011 [P] [US1] Write vitest for toggle ON shows bbox + landmarks and tracks in `frontend/src/components/__tests__/CameraCapture.overlay.test.tsx` — mock `MockPreviewDetector` returns centered box + 2 landmarks → after click `aria-pressed="true"` and `<canvas data-testid="face-overlay">` draw called with scaled coordinates (FR-003/FR-004, SC-001 scenario 2)
- [X] T012 [P] [US1] Write vitest for toggle OFF clears overlay without stream restart + capture neutrality in `frontend/src/components/__tests__/CameraCapture.overlay.test.tsx` — click ON→OFF clears canvas within 200ms, `MediaStream.getTracks().stop` not called, `capture()` via `toBlob('image/jpeg')` calls `onCapture` identically in both toggle states (FR-005/FR-007, SC-004)
- [X] T013 [P] [US1] Write vitest for a11y contract in `frontend/src/components/__tests__/CameraCapture.a11y.test.tsx` — `getByRole('button',{name:/Show face overlay|Mostrar contorno facial/})`, `aria-pressed` flips false→true→false, Tab/Space/Enter operable, `data-testid="overlay-toggle"`, visible `:focus-visible` ring per contracts/preview-overlay.md §3 (FR-009, SC-006)

### Implementation for User Story 1

- [X] T014 [US1] Extend `frontend/src/components/CameraCapture.tsx` wrapper to `position:relative` containing `<video data-testid="camera-preview">` + `<canvas data-testid="face-overlay">` with `position:absolute; inset:0; pointer-events:none` and DPR-aware backing store (`canvas.width=cssWidth*dpr`, `ctx.setTransform(dpr,0,0,dpr,0,0)`)
- [X] T015 [US1] Add toggle state in `frontend/src/components/CameraCapture.tsx` — `const [showOverlay,setShowOverlay]=useState(false)` default OFF, `epochRef`, `inFlightRef`, `lastValidRef`/`lastValidAtRef`, button gated on `active && streamReady` only (hidden not rendered when not ready), `aria-pressed={showOverlay?"true":"false"}`, `aria-label` resolved via `navigator.language` or app i18n (`Mostrar contorno facial` / `Show face overlay`), `data-testid="overlay-toggle"` (FR-002/FR-010/FR-015)
- [X] T016 [US1] Implement throttled sampling loop in `frontend/src/components/CameraCapture.tsx` — `setInterval(tick, OVERLAY_SAMPLE_INTERVAL_MS=200)` on `showOverlay` false→true with immediate `tick()`, `inFlightRef` guard skips overlapping ticks, `epochRef` tags pending promises, cleanup `clearInterval` + `epochRef++` + `abortController.abort()` on OFF/unmount, stale-result discard if `epoch !== epochRef.current` (FR-006, R-2/R-5)
- [X] T017 [US1] Implement drawing path in `frontend/src/components/CameraCapture.tsx` (or extract to `frontend/src/components/FaceOverlayCanvas.tsx`) — `drawOverlay(ctx, detections, videoWidth, videoHeight, cssWidth, cssHeight, mirrored)` clears ctx each tick, scales `scaleX=cssWidth/videoWidth, scaleY=cssHeight/videoHeight`, strokes box 2px `#00E5CC` and landbox dots radius 3px; empty array → cleared canvas (no toast)
- [X] T018 [US1] Add mirroring + resize alignment in `frontend/src/components/CameraCapture.tsx` — shared `transform:scaleX(-1)` on both `<video>` and overlay `<canvas>` when front-camera selfie, fallback helper `mirrorIfNeeded(x,w,cssWidth,mirrored)` (`x_mirrored=cssWidth-x_scaled-w_scaled`, landmarks flipped), `ResizeObserver` on wrapper + `loadedmetadata` listener updates `cssWidth/cssHeight` then rescales backing store (FR-003/FR-014, R-3)
- [X] T019 [US1] Verify capture path independence in `frontend/src/components/CameraCapture.tsx` — audit `capture()` reads `<video>` directly via `drawImage` + `toBlob("image/jpeg",0.9)` without reading `showOverlay` or `PreviewDetector`, `forwardRef` handle unchanged per spec 005 (FR-007)

**Checkpoint**: At this point User Story 1 is fully functional and independently testable via `vitest run` and quickstart S-1 + S-2; overlay toggles within 200ms, mirrored alignment holds, capture unchanged

---

## Phase 4: User Story 2 - Consistent toggle across onboarding, login, and dashboard previews (Priority: P2)

**Goal**: Same camera preview experience wherever live preview appears (`/onboarding`, `/login`, `/dashboard`) — toggle behavior and labeling identical because it lives once in the shared `CameraCapture` component.

**Independent Test**: Navigate to onboarding → verify toggle works; to login → same; to dashboard preview (if present) → same; each page independently shows same overlay behavior and capture flow, and in-memory state persists while preview stays mounted (spec §User Story 2 Independent Test, quickstart S-2).

### Tests for User Story 2

- [X] T020 [P] [US2] Write integration test for onboarding preview reuse in `frontend/src/pages/__tests__/Onboarding.overlay.test.tsx` — mount `Onboarding.tsx` with mocked `MediaDevices` + `MockPreviewDetector`, assert `getByTestId("overlay-toggle")` present when streamReady, ON shows box, capture succeeds (SC-002)
- [X] T021 [P] [US2] Write integration test for login preview reuse in `frontend/src/pages/__tests__/Login.overlay.test.tsx` — same assertions on `Login.tsx` (identifier input + login capture flow not interfered, PRD §6.3) (SC-002)
- [X] T022 [P] [US2] Write integration test for dashboard preview reuse in `frontend/src/pages/__tests__/Dashboard.overlay.test.tsx` — if dashboard renders preview, same toggle assertions; mood/age analysis buttons not interfered (PRD §6.4) (SC-002)

### Implementation for User Story 2

- [X] T023 [US2] Audit `frontend/src/pages/Onboarding.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/Dashboard.tsx` to confirm they consume shared `frontend/src/components/CameraCapture.tsx` without per-page toggle duplication, no duplicated `PreviewDetector` imports, single label constant reused (FR-008)
- [X] T024 [US2] Verify in-memory session persistence while preview stays mounted in `frontend/src/components/CameraCapture.tsx` — `showOverlay` is per-mount `useState(false)` (default OFF on first load, retained while mounted, reset on unmount/remount per FR-010); document that lifting to `App.tsx` context is a one-line future move if cross-page persistence is ever required
- [X] T025 [US2] Run quickstart S-1 + S-2 + S-6 across `/onboarding`, `/login`, `/dashboard` and record manual results in `specs/011-implement-toggle-button/checklists/requirements.md` (or `run-log.md`)

**Checkpoint**: User Stories 1 AND 2 both work independently — shared component reuse verified, no per-page duplication, all three contexts pass

---

## Phase 5: User Story 3 - Responsive, degraded preview when detection is slow or unavailable (Priority: P3)

**Goal**: Smooth preview regardless of detector latency; graceful empty-overlay degradation on no-face/multi-face/error/slow/CPU-only/mock, toggle always responsive, never blocks capture.

**Independent Test**: With toggle ON test three conditions: (a) fast detector, (b) artificially slow (1000ms) detector, (c) mock returning [] or throw — in all cases video fluid, toggle clickable, overlay tracks / delayed / empty respectively, capture never blocked (spec §User Story 3 Independent Test, quickstart S-3 + S-4 + S-7).

### Tests for User Story 3

- [X] T026 [P] [US3] Write vitest for slow detector resilience in `frontend/src/components/__tests__/CameraCapture.resilience.test.tsx` — `MockPreviewDetector` with `delayMs=1000` → video `play()` not blocked, toggle remains clickable during in-flight, overlay updates ~1s after result, native video FPS decoupled from 5 FPS throttle (FR-013, SC-005)
- [X] T027 [P] [US3] Write vitest for empty/multi-face/landmark-absent contracts in `frontend/src/components/__tests__/CameraCapture.resilience.test.tsx` — `[]` → cleared canvas no toast (FR-011), N boxes (e.g. 2) → N strokes, box-only when `landmarks` omitted (no placeholder dots) (FR-004/FR-012, SC-003)
- [X] T028 [P] [US3] Write vitest for error degradation + rapid-toggle safety in `frontend/src/components/__tests__/CameraCapture.resilience.test.tsx` — `detect()` reject → empty overlay + optional `aria-live="polite"` notice, `capture()` not blocked; rapid 10× ON/OFF spam → only last epoch renders, no leaked timers (use `vi.useFakeTimers()` + `epochRef` assertion) (FR-013, Edge Cases)
- [X] T029 [P] [US3] Write vitest for flicker smoothing + throttle gate in `frontend/src/components/__tests__/CameraCapture.resilience.test.tsx` — single-frame empty after valid → hold last valid 200ms then clear, `score < OVERLAY_MIN_SCORE=0.5` ignored within hold window, `setInterval` asserted `200ms` and overlapping tick skipped via `inFlightRef` (FR-011 clarification, FR-006)

### Implementation for User Story 3

- [X] T030 [US3] Add flicker smoothing logic in `frontend/src/components/CameraCapture.tsx` — `lastValidRef` + `holdUntilRef=Date.now()+OVERLAY_HOLD_MS(200)` + `OVERLAY_MIN_SCORE(0.5)` gate in `tick()` via `applyHoldSmoothing(detections, lastValidRef, HOLD_MS, MIN_SCORE)` — single-frame drop re-renders last valid boxes within window, empty beyond clears; constant can be set 0 to disable (R-5)
- [X] T031 [US3] Add error/degradation path in `frontend/src/components/CameraCapture.tsx` — `await detector.detect(video).catch(()=>[])` → empty overlay, render optional dismissible `<span aria-live="polite">Detección no disponible</span>` that never blocks `capture()` and is cleared on next valid result (FR-013)
- [X] T032 [US3] Harden rapid-toggle concurrency in `frontend/src/components/CameraCapture.tsx` — per-ON epoch `AbortController`, synchronous `clearInterval` before `setShowOverlay(false)`, captured epoch discard `if(epoch!==epochRef.current || !showOverlay) return`, `inFlightRef` reset on discard (Edge Cases)
- [X] T033 [US3] Assert throttle invariant in `frontend/src/components/CameraCapture.tsx` — `OVERLAY_SAMPLE_INTERVAL_MS=200` interval, decouple video native FPS from detection (video `play()` uninterrupted), document CPU-only / no-GPU parity (tests already mock-only per SC-007, R-7)

**Checkpoint**: All three user stories independently functional — fast/slow/error/zero/multi-face all degrade to fluid video + empty or N-box overlay, throttle ≤5 FPS holds

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Visual polish, a11y sweep, Docker CUDA docs, regression gates, cleanup

- [X] T034 [P] Add optional GPU reservation stanza to `docker-compose.yml` under `backend.deploy.resources.reservations.devices` — `driver:nvidia, count:1, capabilities:[gpu]` with comment that it is additive, safe to omit on CPU hosts/CI, requires NVIDIA Container Toolkit; preview remains client-side unaffected (R-7)
- [X] T035 [P] Polish overlay visuals and focus in `frontend/src/components/CameraCapture.tsx` and `frontend/src/components/FaceOverlayCanvas.tsx` — 2px high-contrast stroke `#00E5CC`, 3px landmark dot radius, alignment per style guide, `:focus-visible {outline:2px solid ...}` ring, label constant `OVERLAY_TOGGLE_LABEL_EN/ES` extracted, contrast glance on light/dark backgrounds per Assumptions
- [X] T036 [P] Add non-blocking notice affordance in `frontend/src/components/CameraCapture.tsx` — dismissible `aria-live="polite"` span for detector-unavailable (FR-013), cleared on successful detection, not rendered when toggle hidden
- [X] T037 [P] Add offscreen snapshot downscale helper in `frontend/src/services/previewDetector.ts` or `frontend/src/components/CameraCapture.tsx` — optional snapshot canvas 320px long-edge downscale preserving aspect from `videoWidth/videoHeight` before passing to detector, re-scale boxes via `cssWidth/videoWidth` mapping (R-6)
- [X] T038 Run full automated verification `cd frontend && npm test` (vitest run) and `cd backend && python -m pytest tests/unit tests/contract -q` (or `docker compose exec backend python -m pytest tests/unit tests/contract -q`) — confirms no new backend route, existing suites green, SC-007 mock-only pass without GPU/network
- [X] T039 Execute manual quickstart validation S-1..S-8 in `specs/011-implement-toggle-button/quickstart.md` across `/onboarding`, `/login`, `/dashboard` on Chrome/Edge `http://localhost:5173` with real camera; verify 200ms toggle, mirrored alignment, ResizeObserver rescale, HiDPI crispness, troubleshooting table entries
- [X] T040 Cleanup and docs — remove debug logs, ensure preview frames/boxes/landmarks never stored/logged (ephemeral canvas clear on OFF/unmount, no `fetch`/`localStorage` in preview path), update `specs/011-implement-toggle-button/checklists/requirements.md` (or `run-log.md`) with SC-001..SC-007 checklist, `ruff`/`tsc` lint passes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed) or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete; CUDA stanza (T034) can be done earlier but validated at polish

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories — delivers MVP (toggle + overlay + throttle + mirroring)
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — May integrate with US1 components but independently testable (reuse audit + page integration tests); benefits from US1 overlay logic but does not duplicate it
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) — May integrate with US1/US2 but independently testable (resilience, smoothing, multi-face, error path); builds on US1's loop but adds hold/error/epoch guards

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation (Constitution Development Workflow §4 Red-Green-Refactor)
- Port/constants before adapters; adapters before loop; loop before drawing; drawing before polish
- Core implementation before integration; story complete before moving to next priority
- Keep `capture()` path untouched throughout (audit in T019, T038)

### Dependency Graph (textual)

```
T001 → T002 → T003
  ↓
T004 → T005 ─┐
  ↓    T006 ─┤→ T007 → T008 → T009 (foundational gate)
  └──────────┘
         ↓ (gate passes)
  ┌──────┼──────┐
  ↓      ↓      ↓
 US1    US2    US3   (parallel after gate, but priority order P1→P2→P3 recommended)
  T010-T019   T020-T025   T026-T033
  └──────┼──────┘
         ↓
  Polish T034-T040
```

---

## Parallel Opportunities

- **Phase 1**: T003 audit can run parallel to T002 baseline builds (different concerns)
- **Phase 2**: T005 (MockPreviewDetector), T006 (BrowserFaceDetector), T007 (test harness mocks) are parallel — same file but distinct logical blocks; T005 and T006 touch `previewDetector.ts`, so serialize if lone editor, parallel if split by reviewer
- **Phase 3 Tests**: T010, T011, T012, T013 can all run in parallel (different assertions in same or separate test files, no shared mutation)
- **Phase 3 Impl**: T017 (FaceOverlayCanvas extraction) can run parallel to T015/T016 once interface defined; T014 and T018 share `CameraCapture.tsx` so serialize those two
- **Phase 4 Tests**: T020, T021, T022 parallel (different page test files)
- **Phase 5 Tests**: T026, T027, T028, T029 parallel (different case blocks in `CameraCapture.resilience.test.tsx` — parallelizable by file copy, otherwise sequential in one file)
- **Phase 6 Polish**: T034 (docker-compose.yml), T035 (CameraCapture visuals), T036 (aria-live notice), T037 (snapshot helper) are parallel (different files)
- **Cross-story**: Once Foundational gate passes, US1, US2, US3 teams can work in parallel on separate test files and shared component branches (merge via `CameraCapture.tsx` coordination)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (different files, no dependencies):
Task: "Write vitest for default OFF plain preview and hidden-when-not-ready in frontend/src/components/__tests__/CameraCapture.overlay.test.tsx"  # T010
Task: "Write vitest for toggle ON shows bbox + landmarks and tracks in frontend/src/components/__tests__/CameraCapture.overlay.test.tsx"       # T011
Task: "Write vitest for toggle OFF clears overlay without stream restart + capture neutrality in frontend/src/components/__tests__/CameraCapture.overlay.test.tsx" # T012
Task: "Write vitest for a11y contract in frontend/src/components/__tests__/CameraCapture.a11y.test.tsx"                                      # T013

# Foundational parallel example:
Task: "Implement MockPreviewDetector adapter in frontend/src/services/previewDetector.ts"      # T005
Task: "Implement BrowserFaceDetector adapter in frontend/src/services/previewDetector.ts"      # T006
Task: "Enhance frontend test harness in frontend/src/__tests__/setup.ts"                       # T007
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003) — audit shared component, baseline green
2. Complete Phase 2: Foundational (T004-T009) — PreviewDetector port + mocks + harness compiles (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (T010-T019) — toggle OFF default / ON bbox+landmarks / OFF clears / hidden when not ready / a11y / throttle / mirroring / capture neutrality
4. **STOP and VALIDATE**: `cd frontend && npm test` passes without GPU/camera (mock detector), manual quickstart S-1 + S-2 on `/onboarding` with real camera shows 200ms toggle + mirrored tracking, `capture()` identical in both states
5. Deploy/demo if ready — single shared component increment is viable; US2/US3 deferrable

### Incremental Delivery

1. Setup + Foundational → Foundation ready (port + adapters + harness)
2. Add US1 → Test independently via `CameraCapture.overlay.test.tsx` + `CameraCapture.a11y.test.tsx` → Demo MVP (plain ↔ overlay, capture unchanged)
3. Add US2 → Test independently via `Onboarding.overlay.test.tsx` + `Login.overlay.test.tsx` + `Dashboard.overlay.test.tsx` → Demo consistent reuse across pages (SC-002)
4. Add US3 → Test independently via `CameraCapture.resilience.test.tsx` (slow/empty/multi-face/error/rapid/smoothing) → Demo graceful degradation (SC-003/005, S-3/S-4/S-7)
5. Polish → `docker-compose.yml` CUDA docs + visual polish + full S-1..S-8 sweep; each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after Foundational gate:

1. Team completes Setup + Foundational together (coordinate on `previewDetector.ts` interface shape)
2. Once Foundational is done:
   - Developer A: US1 (CameraCapture toggle + overlay canvas + loop + mirroring + draw)
   - Developer B: US2 (page integration tests + reuse audit — low code, high verification)
   - Developer C: US3 (smoothing + error + epoch hardening — builds on A's loop, branch off A or pair)
3. Stories complete and integrate via `CameraCapture.tsx` — rebase US2/US3 onto US1 overlay logic before Polish; `npm test` + quickstart S-1..S-8 is the merge gate

---

## Notes

- [P] tasks = different files, no dependencies — parallelizable; tasks without [P] share files (especially `CameraCapture.tsx`) and must be serialized
- [Story] label maps task to specific user story for traceability (US1, US2, US3); Setup/Foundational/Polish have no story label
- Each user story is independently completable and testable — see Independent Test under each phase header
- Verify tests fail before implementing (Red → Green) per constitution Workflow §4
- Commit after each task or logical group; push only when orchestrator requests
- Stop at any checkpoint to validate story independently; MVP is Phase 3 alone
- Avoid: vague tasks, same-file conflicts without sequencing, cross-story dependencies that break independence, persisting preview frames/boxes/landmarks, adding new HTTP routes (v1 is client-side), requiring GPU for tests
- Docker CUDA host optimization is compose-only, optional, never gates preview availability (Constitution VII, SC-007)
- Preview detection is throttled ≤5 FPS (≥200 ms) decoupled from video native FPS; smoothing hold 200 ms midpoint of 150–250 ms window
- Toggle is `<button aria-pressed>` with canonical `Show face overlay` / `Mostrar contorno facial`, hidden when `!streamReady` (FR-015), per-mount in-memory state default OFF
