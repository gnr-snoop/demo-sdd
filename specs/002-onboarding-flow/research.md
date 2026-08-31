# Research: Onboarding Flow (Fase 2)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

This document resolves every NEEDS CLARIFICATION item and records the design decisions, rationale, and alternatives for the onboarding flow. All decisions are grounded in the existing spec 001 skeleton (verified by reading the source) and the pinned clarify-gate decisions.

---

## Codebase Context

*(From Step 0 codebase-memory + direct source inspection. The graph index did not cover the Python source — coverage gap confirmed via `check_index_coverage`; all claims below are from reading the actual files.)*

**Existing architecture (spec 001, verified):**
- **Ports** (`backend/src/face_insight/domain/ports.py`): 8 `typing.Protocol` interfaces — `Detector.detect(image: bytes) -> DetectionResult`, `Embedder.embed(face_image: bytes) -> Embedding`, `UserRepository` (get/get_by_identifier/save/delete), `FaceTemplateRepository` (get_by_user/save/delete_by_user), `ImageStorage` (store/read/delete), plus `AgeEstimator`, `MoodEstimator`, `SessionManager`. **All declared as sync `def`**; the DB repository adapters (`adapters/db/repositories.py`) are **async** — a sync/async friction point (see R-2).
- **Entities** (`domain/entities.py`): frozen dataclasses `User` (id/identifier/status/created_at/updated_at), `FaceTemplate` (id/user_id/embedding/model_version/...). `UserStatus.enrolled` exists. Factories `create_user`/`create_face_template` with injectable `now`. `User.__post_init__` validates only non-empty identifier — **no format validation** (spec 002 adds it in `validation.py`, before construction).
- **Result types** (`domain/result_types.py`): `DetectionResult(face_count, boxes, score)`, `Embedding(vector, model_version)`.
- **Config** (`config.py`): pydantic `Settings` with `image_max_bytes=2_000_000`, `image_max_long_edge=640`, `image_format="JPEG"`, `verification_threshold=0.5`, `embedding_model_version="mock-embed-v0"`. **No `quality_threshold`** — spec 002 adds it. **Model version mismatch** — pinned decision requires `"mock-embedder-v1"`; spec 002 updates `constants.EMBED_MODEL_VERSION`.
- **Mock detector** (`adapters/mock/detector.py`): hardcoded `face_count=1, score=0.99` — **not fixture-controllable**; spec 002 needs a controllable variant for rejection-path tests (see R-6).
- **Mock embedder** (`adapters/mock/embedder.py`): fixed 128-dim `[0.1]*128` vector, `model_version=EMBED_MODEL_VERSION`.
- **DB models** (`adapters/db/models.py`): `users.identifier` is `String(255), unique=True` — **unique constraint already exists**; storing the normalized (trim+lowercase) identifier makes it case-insensitive. `face_templates.user_id` has `unique=True` (1:1).
- **Migration** (`alembic/versions/0001_initial_schema.py`): `UniqueConstraint("identifier")` on `users` — confirmed.
- **FS storage** (`adapters/fs/image_storage.py`): `FilesystemImageStorage.store(user_id, image_bytes)` writes to `usuarios/<user-id>/pictures.jpg` — **already receives raw bytes**; spec 002 passes already-resized bytes.
- **Onboarding route** (`api/routes/onboarding.py`): stub returning `FIXED_USER_ID`, only checks `consentAccepted` false → 422. **No identifier validation, no image validation, no persistence.**
- **Schemas** (`api/schemas.py`): `OnboardingResponse(userId, identifier, status)`. Error shape is FastAPI-default `ErrorDetail(detail)`. **No `{"error": {"code", "message"}}` schema** — spec 002 adds it.
- **Frontend** (`frontend/src/pages/Onboarding.tsx`): placeholder with a `<p>` — no camera, no state machine.
- **Contract tests** (`tests/contract/test_http_contracts.py`): assert `{"detail": ...}` for errors and `status == "enrolled"` for success. Spec 002 updates the error assertions to the new shape.

**Reuse opportunities:** ports, entities, factories, config, DB models/migration, fs adapter, mock embedder (after version bump), `OnboardingResponse` schema, compose stack, `usuarios/` bind mount — all reused, not re-created.

**Integration touch-points:** `api/routes/onboarding.py` (replaced), `config.py` (additive), `adapters/mock/constants.py` (version bump), `adapters/mock/detector.py` (add controllable variant), `domain/ports.py` (async repo ports), `api/schemas.py` (add error schema), `frontend/src/pages/Onboarding.tsx` (replaced).

**Coverage limitation:** The codebase-memory graph indexed only markdown/YAML config files; the Python/TSX source was not in the graph (confirmed via `check_index_coverage` — `backend/` scope returned 0 entries). All structural claims above are from direct `read` of the source files, not the graph. The graph was used only for PRD/spec discovery.

---

## Research Items

### R-1: Identifier validation format and normalization

**Decision**: `identifier` is valid if it matches a well-formed email (RFC 5322 simplified: `^[^@\s]+@[^@\s]+\.[^@\s]+$`) **or** a username pattern (`^[a-zA-Z0-9._-]{3,32}$`). Normalization = `identifier.strip().lower()` applied before duplicate check and canonical storage; the original casing is not preserved. Empty/whitespace-only is rejected before format check.

**Rationale**: Preserves the PRD §6.2 "email o username" wording without forcing a single format (spec clarification). Trim+lowercase is the simplest correct case-insensitive normalization. Storing the normalized form canonically means the existing `UNIQUE(identifier)` constraint enforces case-insensitive uniqueness with zero schema change (R-4).

**Alternatives considered**:
- Email-only: rejected — PRD explicitly says "email o username".
- Separate `username`/`email` columns: rejected — over-engineering for a demo (Principle I); a single normalized identifier column with a union format check is simpler and sufficient.
- Preserve original casing + store normalized in a separate column: rejected — the spec explicitly says "the original casing is not preserved"; adds a column for no demo value.

**Implementation**: `domain/validation.py` — `normalize_identifier(raw: str) -> str`, `is_valid_identifier(raw: str) -> bool`. Pure functions, no infra imports.

---

### R-2: Sync/async port shape and the unit-of-work for atomic persistence

**Decision**: Make the repository ports (`UserRepository`, `FaceTemplateRepository`) **async** in `domain/ports.py` (`async def save`, etc.). Keep `Detector` and `Embedder` **sync** (ML inference is CPU-bound; sync is correct, and FastAPI can offload to a threadpool if needed — for mocks the cost is negligible). The onboarding use-case (`domain/onboarding.py`) is an `async def` that `await`s repo calls and calls detector/embedder directly. Atomicity is implemented as a **single SQLAlchemy async session/transaction** wrapping the `User` insert + `FaceTemplate` insert; the filesystem write happens *inside* the same logical unit and, on FS failure, the DB transaction is rolled back (the image write is attempted first or the DB commit is conditional on FS success — see R-5 for ordering).

**Rationale**: The DB adapters are already async (`adapters/db/repositories.py`); declaring the ports async makes the contract honest and lets the domain `await` them. Sync detector/embedder avoids unnecessary `asyncio.to_thread` wrapping for CPU-bound mock calls. A single session = the simplest correct all-or-nothing guarantee (FR-008) without a heavyweight Unit-of-Work abstraction (Principle I — YAGNI).

**Alternatives considered**:
- Keep all ports sync, run async DB calls via `asyncio.run` inside sync handlers: rejected — breaks FastAPI's async event loop; incorrect.
- Make detector/embedder async too: rejected — adds `async` ceremony to CPU-bound sync mocks for no benefit; real ML adapters (Fase 5) can wrap sync inference in `asyncio.to_thread` at the adapter boundary without changing the port.
- Full Unit-of-Work pattern with a `UnitOfWork` port: rejected — over-engineering for a single atomic two-insert operation (Principle I). A single session-scoped transaction is sufficient and clearer for the demo.

**Implementation**: `domain/onboarding.py` defines `OnboardingService` taking injected ports. The route handler opens an async session (via the existing `adapters/db/session.py` factory), constructs the DB-backed repos with that session, and calls `await service.onboard(...)`. The service raises domain exceptions (`IdentifierTaken`, `NoFaceDetected`, etc.) which the route maps to the error response shape.

---

### R-3: Image decode, format/size limits, and long-edge resize — library and purity placement

**Decision**: Use **Pillow** (`PIL.Image`) for decode, format validation (JPEG), size enforcement, and long-edge resize. `image_handling.py` lives under `domain/` but is classified as a **domain-adjacent service** (it imports Pillow); the pure decision logic (when to reject) lives in `onboarding.py`. The `test_domain_purity` check is scoped to the pure decision modules and explicitly excludes `image_handling.py` with a documented justification.

**Rationale**: Pillow is the standard open-source Python image library, has no ML/model dependency, and handles decode + resize in a few lines. Placing it in `domain/` keeps the use-case's import surface simple (`from .image_handling import decode_and_resize`) while the purity gate focuses on the *decision* logic (the part that must be swappable and testable without infra). Splitting decode (infra-adjacent) from the face-count/quality decision (pure) is the hexagonal seam.

**Alternatives considered**:
- Put `image_handling.py` in `adapters/` (as an image-processing port): rejected — it's not a swappable infrastructure adapter (there's no "real vs mock" image decoder); it's a deterministic transformation. Treating it as a port would add an interface + adapter for a pure function (YAGNI).
- Use `opencv-python`: rejected — heavier dependency, pulls in numpy/compiled binaries; Pillow is lighter and sufficient for decode+resize.
- Resize on the frontend only: rejected — PRD §11 mandates server-side re-validation; the stored artifact must be authoritative (spec clarification).

**Implementation**: `domain/image_handling.py` — `decode_and_normalize(image_bytes, max_bytes, max_long_edge) -> bytes`. Raises `InvalidImage` (undecodable/unsupported format/oversized). Returns resized JPEG bytes. The route reads `UploadFile`, checks `len(bytes) <= max_bytes`, calls this function, then passes normalized bytes to detector/embedder/storage.

---

### R-4: Concurrent-duplicate race — unique constraint sufficiency

**Decision**: The existing `UNIQUE(identifier)` constraint on `users` is sufficient. Since we store the normalized (trim+lowercase) identifier, the constraint is effectively case-insensitive. The onboarding service catches the SQLAlchemy `IntegrityError` on `User` insert and maps it to `IdentifierTaken` → `identifier_taken` error code. No additional migration is needed in the common case; if case-insensitivity at the DB collation level is desired as belt-and-suspenders, a `0002` migration can add a functional index `lower(identifier)` or switch the column to `CITEXT` — but because we already store normalized, this is redundant and **not done** (Principle I).

**Rationale**: The spec clarification explicitly chose "DB unique constraint + catch integrity violation, no explicit lock." Storing normalized means the constraint sees only lowercase values. This is the simplest correct guarantee.

**Alternatives considered**:
- `CITEXT` column: rejected — redundant since we pre-normalize; adds a Postgres extension dependency.
- Explicit `SELECT ... FOR UPDATE` lock: rejected — spec explicitly says no table lock (demo-first).
- Check-then-insert without constraint: rejected — TOCTOU race; the constraint is the correct guarantee.

**Implementation**: No schema change required. The `0002_onboarding_normalization.py` migration is a **no-op placeholder** (or omitted entirely) — documented in research so the tasks phase doesn't expect a schema diff. If the team later wants DB-level case-insensitivity as defense-in-depth, the migration path is documented here.

---

### R-5: All-or-nothing ordering — DB vs filesystem write

**Decision**: Order of operations within the atomic unit: (1) detector → (2) embedder → (3) **filesystem write** of the normalized image → (4) **DB transaction** (insert `User` + insert `FaceTemplate`, single session, commit). If the FS write fails, the DB transaction never opens → no orphaned profile. If the DB commit fails (e.g., unique violation, DB unreachable), the FS file is an orphan → **best-effort cleanup**: the service catches the DB failure and attempts `image_storage.delete(user_id)` to remove the orphan, logging a warning if cleanup fails (Principle VIII — no traceability guarantee; an orphaned image is a demo-acceptable failure mode, not a data-integrity bug, since there's no DB profile referencing it).

**Rationale**: Writing the image before the DB commit avoids holding a DB transaction open during FS I/O. The orphan-on-DB-failure case is unavoidable without a 2-phase commit (which is absurd for a local FS + Postgres demo — Principle I). Best-effort cleanup is the simplest mitigation. The reverse order (DB first, then FS) would leave an orphaned *profile* referencing a missing image — worse, because login (spec 003) would find a profile with no image. FS-first orphans are unreferenced and harmless.

**Alternatives considered**:
- DB first, then FS, rollback DB on FS failure: rejected — leaves a window where a concurrent login could see a profile with no image; also holds the transaction open across FS I/O.
- 2-phase commit / transactional outbox: rejected — gross over-engineering for a local demo (Principle I).
- Write image to a temp path, DB commit, then rename to final path: considered — slightly cleaner (the final path only appears after commit), but adds path-juggling complexity for marginal demo value. **Adopted as a refinement if the tasks phase finds the orphan-cleanup test awkward**: write to `usuarios/<user-id>.tmp/pictures.jpg`, commit DB, then rename the dir to `usuarios/<user-id>/`. For the plan, the FS-first + best-effort-cleanup approach is the baseline.

**Implementation**: `OnboardingService.onboard()` orchestrates the order; the route handler provides the session. The `ImageStorage` port's `delete` is used for cleanup.

---

### R-6: Mock detector fixture control for rejection-path tests

**Decision**: Introduce a **`ScriptableMockDetector`** (test-only, in `adapters/mock/detector.py` alongside the existing `MockDetector`) whose `detect()` result is configured by inspecting **magic byte markers** in the image payload: e.g., a payload starting with `b"NOFACE"` → `face_count=0`; `b"MULTIFACE"` → `face_count=2`; `b"LOWQUALITY"` → `score=0.1`; otherwise → the default `face_count=1, score=0.99`. The production wiring (`main.wire_mock_adapters`) continues to use the plain `MockDetector` (happy path). Integration/contract tests inject `ScriptableMockDetector` via `app.state.detector` for rejection cases.

**Rationale**: The spec says "the threshold is exercised by fixture choice in tests." A byte-marker convention keeps the mock deterministic (SC-005), requires no external config, and lets a single test fixture cover all rejection branches by varying the image bytes. The plain `MockDetector` is untouched for the happy path and production wiring.

**Alternatives considered**:
- Constructor-parameterized mock (`MockDetector(face_count=...)`): rejected — the detector is wired once at app startup; per-request override would require request-scoped wiring, complicating the composition root.
- Env-var-controlled mock: rejected — global mutable config; non-deterministic across tests.
- A separate `FakeDetector` in `tests/`: considered — but placing it in `adapters/mock/` keeps all mocks in one place and makes it available to both unit and integration tests without import gymnastics. Adopted as `ScriptableMockDetector` in `adapters/mock/detector.py`.

**Implementation**: `ScriptableMockDetector.detect(image: bytes) -> DetectionResult` with the marker convention documented in its docstring. The `quality_threshold` from `Settings` is applied in `onboarding.py` (the decision logic), not in the detector — the detector reports `score`; the service decides `score < threshold → insufficient_quality`.

---

### R-7: Error response shape and machine-code mapping

**Decision**: Error responses use the pinned shape `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}` with `Content-Type: application/json`. Status codes and machine codes:

| HTTP Status | Machine Code | Trigger | Human Message (actionable) |
|-------------|-------------|---------|----------------------------|
| 422 | `identifier_invalid` | empty/whitespace/malformed identifier | "El identificador no es válido. Usa un email bien formado o un nombre de usuario (3–32 caracteres, letras, números, '.', '_', '-')." |
| 409 | `identifier_taken` | normalized identifier already registered | "Ese identificador ya está registrado. Prueba con otro o inicia sesión si es tuyo." |
| 422 | `consent_required` | consent not exactly `true` / non-boolean | "Debes aceptar el consentimiento para el procesamiento facial antes de continuar." |
| 422 | `invalid_image` | missing image / unsupported format / undecodable / exceeds max size | "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB." |
| 422 | `no_face` | detector returns `face_count == 0` | "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar." |
| 422 | `multiple_faces` | detector returns `face_count > 1` | "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura." |
| 422 | `insufficient_quality` | `face_count == 1` but `score < quality_threshold` | "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar." |
| 500 | `internal_error` | unexpected failure (embedder error, DB unreachable, FS write failure) | "Ocurrió un error inesperado. Inténtalo de nuevo." (no internal details leaked) |

**Rationale**: Pinned by the clarify gate. Machine codes are stable strings for contract-test assertions (SC-009). Human messages are actionable per FR-014/FR-015 and non-revealing per FR-016 (no embeddings, no stack traces, no identifier-existence leak beyond the `identifier_taken` case which is an onboarding-UX requirement, not a login-security concern — Principle VIII). Status codes: 422 for validation/processing rejections (client can fix and retry), 409 for the duplicate conflict, 500 for unexpected failures.

**Alternatives considered**:
- 400 for all client errors: rejected — 422 is more precise (semantic validation) and FastAPI-idiomatic; 409 is correct for the duplicate conflict.
- `identifier_taken` as 422: considered — but 409 Conflict is the semantically correct status for a duplicate resource; the spec doesn't mandate a specific code, so we use the most precise one.
- Separate `no_face`/`multiple_faces`/`insufficient_quality` vs. a single `bad_capture`: rejected — the spec and AC-002/AC-003 require distinguishable, actionable messages; separate codes let the frontend show specific guidance.

**Implementation**: `api/schemas.py` — `ErrorBody(code: str, message: str)`, `ErrorResponse(error: ErrorBody)`. `domain/onboarding.py` raises typed exceptions (`IdentifierInvalid`, `IdentifierTaken`, `ConsentRequired`, `InvalidImage`, `NoFace`, `MultipleFaces`, `InsufficientQuality`, `OnboardingInternalError`). The route handler has a single exception→response mapping table.

---

### R-8: `FaceTemplate.modelVersion` value and config alignment

**Decision**: Update `adapters/mock/constants.EMBED_MODEL_VERSION` from `"mock-embed-v0"` to `"mock-embedder-v1"` (pinned decision). Update `config.Settings.embedding_model_version` default to `"mock-embedder-v1"` for consistency. The `MockEmbedder` already uses `EMBED_MODEL_VERSION`, so the bump propagates automatically. The `FaceTemplate` created by onboarding carries `model_version = embedding.model_version` (from the `Embedding` result type), so it is always populated.

**Rationale**: Pinned by the clarify gate — downstream login (spec 003) needs to detect mock-origin templates. The `"mock-embedder-v1"` string is distinct from any future real-model version.

**Alternatives considered**:
- Keep `"mock-embed-v0"`: rejected — contradicts the pinned decision.
- `null` / omitted: rejected — the spec requires the field always populated.

**Implementation**: One-line constant change + config default sync. No schema change (`model_version` is already `String(64), nullable=False`).

---

### R-9: Frontend onboarding state machine

**Decision**: Implement the PRD §6.2 state machine as a `useOnboardingMachine` hook using a `useState`-driven finite state: `initial` → `requesting_permission` → (`camera_unavailable` | `ready_to_capture`) → `processing` → (`success` | `recoverable_error`). Camera access via `navigator.mediaDevices.getUserMedia({ video: true })`; preview via a `<video>` element + `srcObject`; capture a single still via a hidden `<canvas>` + `drawImage` + `toBlob('image/jpeg')`. The capture button is disabled in `processing` (FR-013). All controls are keyboard-accessible with `aria-label`s (FR-015). Errors show actionable messages mapped from the backend `error.code` (R-7). Retry from `recoverable_error` returns to `ready_to_capture` without a full reload (PRD §10).

**Rationale**: A hook-based state machine is the simplest React-idiomatic implementation of the 7 states. `getUserMedia` is the standard browser API (PRD §10). Single still capture (not continuous streaming) per FR-012. Tests mock `MediaDevices` with a controlled `MediaStream` yielding a test frame (PRD §15).

**Alternatives considered**:
- A state-machine library (XState): rejected — over-engineering for 7 states in a demo (Principle I); `useState` + a transition function is sufficient and dependency-free.
- Continuous video streaming: rejected — PRD §10/FR-012 explicitly forbids continuous frame submission.

**Implementation**: `frontend/src/hooks/useOnboardingMachine.ts`, `frontend/src/components/CameraCapture.tsx`, `frontend/src/pages/Onboarding.tsx` (replaced). The `services/api.ts` `onboarding()` helper builds `FormData` with `identifier`, `consentAccepted`, `image` and POSTs to `/api/onboarding`.

---

### R-10: Observability (within spec scope)

**Decision**: Structured JSON logs via the existing `structlog` setup (spec 001). Each onboarding attempt logs `{event: "onboarding", duration_ms, outcome: "success"|"rejected"|"error", code?: <machine-code>}`. **No images, no embeddings, no identifiers in logs** (FR-016, PRD §12, Constitution Principle VIII). No new observability infrastructure.

**Rationale**: Spec scope limits observability to structured JSON logs (spec Assumptions). The existing `logging.py` is reused.

**Alternatives considered**:
- Log the identifier for debugging: rejected — FR-016/Principle VIII; the machine code is sufficient for diagnosis.
- Metrics/tracing: rejected — out of scope (Principle VIII, no traceability guarantee).

---

## Summary of Resolved NEEDS CLARIFICATION

| # | Item | Decision |
|---|------|----------|
| R-1 | Identifier format + normalization | Email-or-username union; trim+lowercase; stored normalized |
| R-2 | Sync/async ports + atomicity | Repo ports async; detector/embedder sync; single-session transaction |
| R-3 | Image decode/resize library + purity | Pillow in domain-adjacent `image_handling.py`; purity gate scoped to decision logic |
| R-4 | Concurrent-duplicate race | Existing `UNIQUE(identifier)` + normalized storage; catch `IntegrityError`; no migration |
| R-5 | All-or-nothing ordering | FS write first, then DB commit; best-effort FS cleanup on DB failure |
| R-6 | Mock detector fixture control | `ScriptableMockDetector` with byte-marker convention for tests |
| R-7 | Error shape + machine codes | Pinned `{"error": {"code", "message"}}`; 8 stable codes; status mapping table |
| R-8 | `FaceTemplate.modelVersion` | `"mock-embedder-v1"` (constant + config bump) |
| R-9 | Frontend state machine | `useOnboardingMachine` hook; `getUserMedia`; single still capture |
| R-10 | Observability | Structured JSON logs; no images/embeddings/identifiers logged |

All items resolved without user input. No BLOCKING items in strict mode — the security/contract-sensitive decisions (error shape, atomicity, identifier handling) were pre-pinned by the orchestrator clarify gate and are faithfully reflected here.
