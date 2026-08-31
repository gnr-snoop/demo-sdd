# Research: Login & Session Management (Fase 3)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

Phase 0 research. All NEEDS CLARIFICATION items are resolved below using the pinned orchestrator decisions, the spec clarifications, the constitution defaults, and industry best practice for the FastAPI + PostgreSQL stack. No item was left open.

---

## Codebase Context

The codebase-memory knowledge graph for `demo-sdd` currently contains only spec/config markdown artifacts (443 nodes, all `Section`/`Variable`/`File`/`Module` labels over YAML/Markdown) — the backend/ and frontend/ source trees do not yet exist on disk. Specs 001 and 002 are **plans**, not yet implemented code. Therefore the reuse and integration surface for this spec is established by the spec 001/002 **plans and contracts**, not by indexed source symbols.

**Related existing components (from spec 001/002 plans):**
- `backend/src/face_insight/domain/entities.py` — `User`, `FaceTemplate`, `AuthSession`, `AnalysisRequest` declared as pure domain entities (spec 001).
- `backend/src/face_insight/domain/ports.py` — `Detector`, `Embedder`, `UserRepository`, `FaceTemplateRepository`, `SessionManager`, `ImageStorage` declared (spec 001); `UserRepository`/`FaceTemplateRepository` made async (spec 002). A `Comparison` port is referenced by this spec's FR-021 and assumptions; it is treated as declared in spec 001's ports and **filled with real logic here** (if absent, this spec adds it — either way the plan covers it).
- `backend/src/face_insight/config.py` — pydantic `Settings` with `image_max_bytes`, `image_max_long_edge`, `quality_threshold`, `embedding_model_version` (spec 001/002).
- `backend/src/face_insight/api/dependencies.py` — spec 001 **placeholder** session guard; **replaced** with real session validation in this spec.
- `backend/src/face_insight/api/routes/auth.py` — spec 001 stub handlers for `face-login`, `me`, `logout`; **filled** with real logic here.
- `backend/src/face_insight/adapters/mock/` — deterministic mock detector/embedder (fixture-controllable per spec 002).
- `backend/alembic/versions/0001_initial_schema.py` — `auth_sessions` table already defined (spec 001).
- `frontend/src/context/SessionContext.tsx` — spec 001 in-memory placeholder; **replaced** with real session context here.
- `frontend/src/components/ProtectedRoute` — spec 001 placeholder guard; **replaced** with real gating here.
- `specs/002-onboarding-flow/contracts/onboarding.md` — pins the `{"error": {"code", "message"}}` error shape and machine codes; **reused** for login.

**Reuse opportunities:**
- Image decode/validate/resize: reuse `domain/image_handling.py` (spec 002) for `invalid_image`.
- Identifier normalization (trim + lowercase): reuse `domain/validation.py` (spec 002).
- Error response shape + `ErrorResponse`/`ErrorBody` pydantic schemas: reuse from spec 002 `api/schemas.py`.
- Onboarding state machine pattern (`hooks/useOnboardingMachine.ts`): mirror for the login page state machine.
- `CameraCapture.tsx` component (spec 002): reuse for the login camera preview + still capture.
- Mock detector/embedder fixture-controllable variants (spec 002): reuse for login rejection tests.

**Integration touch-points:**
- `POST /api/auth/face-login` — fills the spec 001 stub.
- `GET /api/auth/me` — fills the spec 001 stub; consumed by `SessionContext` on app load.
- `POST /api/auth/logout` — fills the spec 001 stub.
- `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data` — gain **real session-gating** (logic stays stubbed per spec 001).
- `auth_sessions` table — real CRUD via the `SessionManager` port + DB adapter.
- `frontend/src/router.tsx` — `ProtectedRoute` wired to real session state.

**Coverage limitations:** Graph has no source-code nodes; all evidence was read directly from the spec 001/002 plan/contract files and the PRD. Coverage check on the cited spec paths returned `no_recorded_issue` (clean, best-effort).

---

## R-1 — Cosine similarity comparison & threshold configuration

**Decision:** Implement a `Comparison` port with a single method `compare(a: list[float], b: list[float]) -> float` returning cosine similarity `(a·b)/(||a||·||b||)`. A concrete `CosineComparison` adapter implements it. The domain login use-case compares the captured embedding against the stored `FaceTemplate.embedding` and accepts iff `similarity >= Settings.verification_threshold` (default `0.5`, env `VERIFICATION_THRESHOLD`). The comparison port guards against dimension mismatch: if `len(a) != len(b)` it raises a typed `ComparisonError` that the use-case maps to `internal_error` (recoverable), never producing a meaningless score.

**Rationale:** Constitution OQ-6 default is cosine similarity; the spec pins threshold 0.5 env-overridable via pydantic `Settings` (FR-002/FR-003). Putting the metric behind the port means Fase 5 swaps it without touching the domain (FR-021, Principle VII). Dimension-mismatch guarding is explicit in the spec edge cases.

**Alternatives considered:**
- *Euclidean / L2-normalized dot:* rejected — OQ-6 default is cosine; changing the metric is a Fase 5 concern, behind the port.
- *Threshold in the FaceTemplate row (per-user):* rejected — spec pins a single global env-overridable threshold (FR-003); per-user thresholds are YAGNI for the demo.
- *Numpy dependency for the dot product:* rejected for the domain layer (keeps domain pure-Python, no infra import); the `CosineComparison` adapter may use `math`/pure Python (128-dim vectors are trivial). A numpy-backed adapter is a Fase 5 option behind the port.

---

## R-2 — Server-side AuthSession lifecycle & SessionManager port

**Decision:** The `SessionManager` port (declared in spec 001) is filled with three async methods:
- `create(user_id: UUID, now: datetime, lifetime: timedelta) -> AuthSession` — inserts a row (`id=uuid4()`, `userId`, `createdAt=now`, `expiresAt=now+lifetime`, `revokedAt=None`), returns it.
- `get_valid(session_id: UUID, now: datetime) -> AuthSession | None` — returns the row iff it exists, `revokedAt IS NULL`, and `expiresAt > now`; otherwise `None`.
- `revoke(session_id: UUID, now: datetime) -> None` — sets `revokedAt = now` on the row if it exists (idempotent — no-op if unknown).

A SQLAlchemy async DB adapter implements this against the existing `auth_sessions` table. Session validity is exactly FR-006: valid iff `revokedAt IS NULL AND expiresAt > now`. Default lifetime 30 min (`Settings.session_lifetime_seconds = 1800`, env `SESSION_LIFETIME_SECONDS`). No automatic refresh/renewal (re-login is the refresh path — demo-first). Multiple concurrent sessions allowed: `create` never revokes prior sessions; a `User` may have many `AuthSession` rows.

**Rationale:** Constitution OQ-3 default is server-side session in PostgreSQL keyed by a signed cookie; no JWT (Principle VIII). The spec pins 30 min default, env-overridable, expired = invalid, multiple concurrent sessions allowed (demo-first). `get_valid` collapsing the four invalid cases (absent/expired/revoked/unknown) into `None` makes the session-gating dependency a single clean branch.

**Alternatives considered:**
- *JWT:* rejected — OQ-3 default + Principle VIII (no security guarantee); server-side sessions are simpler and demonstrable.
- *In-memory session store:* rejected — OQ-3 default is PostgreSQL; loses sessions on restart, less demonstrable.
- *Single-session constraint (revoke prior on new login):* rejected — spec explicitly allows multiple concurrent sessions (demo-first).
- *Sliding expiry / auto-refresh:* rejected — spec pins no auto-refresh; re-login is the refresh path.

---

## R-3 — Signed http-only cookie mechanism

**Decision:** Use `itsdangerous.URLSafeTimedSerializer` (a transitive dependency of Starlette/FastAPI) to sign the `AuthSession.id` (UUID v4 string). The cookie value is the signed token; the backend unsigns it on each protected request to recover the session id, then calls `SessionManager.get_valid`. Cookie attributes: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` toggled by `Settings.session_cookie_secure` (off for `localhost` demo, on when served over HTTPS). The signing key is `Settings.session_signing_key` (env `SESSION_SIGNING_KEY`, demo default `"demo-signing-key-change-me"`). On logout the backend sets the cookie with `Max-Age=0` (clears it). A tampered/unsigned/unknown token is treated identically to an absent cookie → `401 unauthenticated` (no internal error raised).

A thin `SessionCookieService` adapter wraps the serializer + cookie read/write so the route handlers and the session dependency stay decoupled from `itsdangerous` internals.

**Rationale:** OQ-3 default is "server-side session in PostgreSQL keyed by a signed cookie". `itsdangerous` is already in the FastAPI dependency closure, adds no new runtime dependency, and gives signed (tamper-evident) tokens without JWT's stateful claims. Keeping the cookie to just the signed session id (not session data) keeps the session server-side in PostgreSQL. `SameSite=Lax` is the demo-default that still allows top-level navigations to `/login`.

**Alternatives considered:**
- *Starlette `SessionMiddleware` (client-side session dict):* rejected — it stores session data in the cookie, which contradicts "server-side session in PostgreSQL"; we need the DB as the source of truth for `revokedAt`/`expiresAt`.
- *Raw unsigned cookie with the session id:* rejected — tamper-evident signing is trivial with `itsdangerous` and matches OQ-3 ("signed cookie").
- *JWT:* rejected (see R-2).

---

## R-4 — Non-revealing error mapping & the `auth_failed` shared response

**Decision:** The login use-case raises a single `AuthFailed` domain exception for both identity-sensitive causes (nonexistent identifier/template, and below-threshold non-match). The route handler maps `AuthFailed` → `401` with body `{"error": {"code": "auth_failed", "message": "No pudimos verificar tu identidad. Inténtalo de nuevo."}}`. The response is constructed from a single constant — both causes produce a byte-identical response (same status, same code, same message), satisfying FR-008/SC-003. Capture-quality failures (`InvalidImage`, `NoFace`, `MultipleFaces`, `InsufficientQuality`) raise distinct exceptions mapped to `400` with their actionable capture codes. `401` is reserved exclusively for `auth_failed` (login) and `unauthenticated` (session-gating on protected endpoints); `400` is reserved exclusively for the capture codes. This makes the capture-vs-auth distinction statically testable in contract tests.

**Rationale:** Pinned by the orchestrator and the spec clarify gate. PRD §6.3/§12/FR-015 require a non-revealing generic login failure. Sharing one exception + one constant for both causes guarantees byte-identity by construction rather than by careful duplication. Reserving 401 for auth-only keeps the contract crisp (FR-010).

**Note on status-code divergence from onboarding:** Spec 002's onboarding contract maps capture errors to `422 Unprocessable Entity` (validation semantics). Spec 003's login maps the same capture codes to `400 Bad Request`. This is a **deliberate, pinned divergence**: on the login endpoint, `400` signals "the capture you sent is unusable" while `401` signals "we could not authenticate you"; reserving 401 for auth-only is what makes the non-revealing contract statically testable. Onboarding has no auth-failure case so 422 (validation) is appropriate there. Both reuse the same `{"error": {"code", "message"}}` body shape and the same machine-code strings. This is documented in the contracts and is not a contradiction (the status code is per-endpoint, the body shape is shared).

**Alternatives considered:**
- *Distinct codes (`identifier_not_found` vs `face_mismatch`):* rejected — violates FR-008 (non-revealing).
- *422 for login capture errors (match onboarding):* rejected — the clarify gate pinned 400 for login to keep 401 exclusively auth; reverting would blur the capture-vs-auth line.

---

## R-5 — Login evaluation order (detection vs. lookup) — RESOLVED

**Decision:** Follow the evaluation order **as explicitly stated in the spec clarifications and assumptions**: (1) image decode + limit validation → `invalid_image` (400); (2) detector → `no_face` / `multiple_faces` / `insufficient_quality` (400); (3) load `User` + `FaceTemplate` by normalized identifier → if not found, `AuthFailed` (401); (4) embedder → embedding (500 `internal_error` on failure); (5) cosine comparison → if `< threshold`, `AuthFailed` (401, identical to step 3); (6) create `AuthSession`, set signed cookie, return `200`.

**Resolution of the spec inconsistency:** The spec's Edge Cases section contains a comment implying lookup-before-detection ("a nonexistent identifier returns the generic `auth_failed` before detection"), which contradicts the two explicit ordering statements (clarifications Q&A + Assumptions) that place detection (step 2) before lookup (step 3). The explicit ordering statements are more authoritative (stated twice, as a numbered sequence). Following detection-before-lookup means capture-quality errors surface **uniformly for all identifiers** (existing or nonexistent), which actually **eliminates** the residual identifier-existence leak that the edge-case comment describes — an outcome that is strictly better for the non-revealing property and fully consistent with Principle VIII (no security guarantee either way). This is a low-impact demo limitation, auto-resolved; the edge-case comment's expected leak is noted as superseded by the explicit order.

**Rationale:** Two authoritative statements specify detection-before-lookup; one edge-case comment implies the opposite. Detection-before-lookup is also less information-leaking. The non-revealing requirement (FR-008) concerns only the two identity-sensitive causes (nonexistent vs below-threshold), both of which occur after detection and are handled identically regardless of order.

**Alternatives considered:**
- *Lookup-before-detection (as the edge-case comment implies):* rejected — contradicts the explicit numbered order stated twice; would introduce the residual leak it describes rather than eliminating it.

---

## R-6 — Session-gating FastAPI dependency & route protection

**Decision:** Replace the spec 001 placeholder in `api/dependencies.py` with a real `require_valid_session` async dependency: read the signed cookie from the `Request`, unsign it → session id (on failure/tamper/absence → `None`), call `SessionManager.get_valid(session_id, now)`; if `None`, raise `HTTPException(401, ...)` with body `{"error": {"code": "unauthenticated", "message": "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."}}`. On success, yield the `AuthSession` (so handlers can read `userId`). Protected endpoints declare `session: AuthSession = Depends(require_valid_session)`. `POST /api/auth/face-login` and `POST /api/onboarding` do **not** declare the dependency (reachable without a session, FR-014). A separate `get_optional_session` dependency is used by `GET /api/auth/me` (which returns 401 on `None` rather than raising, to produce the explicit `{"authenticated": false}`-equivalent 401 body).

**Rationale:** FastAPI dependencies are the idiomatic, minimal way to gate routes; replacing the placeholder keeps the structure spec 001 established. Collapsing all invalid-session cases into `None` → one 401 response keeps the gating uniform (FR-006/FR-014/SC-005/SC-006).

**Alternatives considered:**
- *Middleware-only gating:* rejected — per-endpoint opt-in via `Depends` is clearer and lets `face-login`/`onboarding` stay unprotected explicitly.
- *Decorator-based protection:* rejected — FastAPI dependencies are the idiomatic equivalent and already used for the placeholder.

---

## R-7 — Frontend real session wiring

**Decision:** Replace `frontend/src/context/SessionContext.tsx` (spec 001 placeholder) with a real context that: (a) on mount, calls `GET /api/auth/me` → on 200 sets `{authenticated: true, userId}`, on 401 sets `{authenticated: false, userId: null}`; (b) exposes `login(userId)` and `logout()` actions that update state and call the respective endpoints; (c) provides a `useSession()` hook. Replace `ProtectedRoute` (spec 001 placeholder) with a component that reads `useSession()` and redirects to `/login` (via `react-router-dom` `<Navigate>`) when `authenticated === false`, rendering `<Outlet/>` otherwise. The dashboard page renders a keyboard-accessible "Cerrar sesión" button that calls `POST /api/auth/logout` then `logout()` then navigates to `/login`.

**Rationale:** FR-015/FR-018 require replacing the placeholder with real session state bootstrapped from `/api/auth/me`. `ProtectedRoute` gating on real state delivers AC-006/SC-008. This is the minimal React-idiomatic structure (context + hook + guard component) reusing the router spec 001 set up.

**Alternatives considered:**
- *Redux/Zustand:* rejected — YAGNI; React context is sufficient for a single session flag + userId.
- *Cookie-based gating in the frontend (reading the http-only cookie):* rejected — http-only cookies are not readable from JS by design; the frontend must use `/api/auth/me`, which is exactly FR-011.

---

## R-8 — Login page state machine

**Decision:** Mirror the spec 002 onboarding state machine (`hooks/useOnboardingMachine.ts`) as `hooks/useLoginMachine.ts` with the seven PRD §6.2/§6.3 states: `idle`, `requesting_permission`, `camera_unavailable`, `ready_to_capture`, `processing`, `success_redirect`, `recoverable_error`. Transitions: `idle → requesting_permission` (user requests camera), `requesting_permission → camera_unavailable | ready_to_capture`, `ready_to_capture → processing` (capture pressed), `processing → success_redirect | recoverable_error`, `recoverable_error → ready_to_capture | idle` (retry without reload). Reuse the `CameraCapture` component from spec 002 for the preview + still capture. The page sends `identifier` + captured image to `POST /api/auth/face-login` via `services/api.ts`; on 200 → `login(userId)` + redirect to `/dashboard`; on 401 `auth_failed` → `recoverable_error` with the generic message; on 400 capture code → `recoverable_error` with the actionable capture message. Capture button disabled in `processing`.

**Rationale:** PRD §6.3 flow + FR-016/FR-017. Reusing the onboarding state-machine pattern and `CameraCapture` avoids duplication (Principle I demo-first / YAGNI). The states are analogous, not identical (login has no consent step), so a separate hook is cleaner than parameterizing the onboarding one.

**Alternatives considered:**
- *XState/fsm library:* rejected — YAGNI; a `useReducer`-based machine matches spec 002's pattern and adds no dependency.
- *Parameterize the onboarding hook:* rejected — the flows differ (no consent, different endpoint, different success redirect) and a shared hook would obscure both.

---

## R-9 — Logout idempotence

**Decision:** `POST /api/auth/logout` always returns `200 OK` with `{"status": "ok"}`. Implementation: read the signed cookie; if a valid session id is recovered, call `SessionManager.revoke(session_id, now)` (idempotent — no-op if already revoked or unknown); always set the cookie to `Max-Age=0` (clear) on the response; return `{"status": "ok"}`. No error body is ever returned from logout. This satisfies FR-012/AC-009 story 5: no-cookie, expired, revoked, and valid sessions all get the same success response.

**Rationale:** Pinned by the clarify gate. Idempotence means the client can call logout on any state (e.g. on a stale tab) and get a clean success; the server-side revoke is best-effort. Clearing the cookie on every logout (even no-cookie) is harmless and keeps the client state clean.

**Alternatives considered:**
- *401 on no-cookie logout:* rejected — violates FR-012 idempotence; logout must always "succeed" from the client's perspective.

---

## R-10 — Observability (no biometric data in logs)

**Decision:** Reuse the spec 001 `structlog` JSON logging. Log entries for auth operations contain only: `event` (`auth.login`, `auth.me`, `auth.logout`, `session.create`, `session.revoke`, `session.reject`), `duration_ms`, `status` (`success`/`failure`), `user_id` (only on success, never the identifier value or embedding), `error_code` (the machine code on failure). No image bytes, no embedding vectors, no similarity score, no identifier value in logs. The similarity score is computed and used for the decision but not logged (FR-023/SC-013/Principle VIII).

**Rationale:** PRD §12/§13 + FR-023 require no images/embeddings/biometric responses in logs. Logging the `error_code` is safe (it's the stable machine code, not internal details) and supports the PRD §13 observability requirement of differentiating validation/camera/auth/model errors.

**Alternatives considered:**
- *Log the similarity score for debugging:* rejected — FR-023 forbids biometric data in logs; the score is derivable from the embedding. The threshold and decision (`accept`/`reject`) are logged, not the score.

---

## Summary of NEEDS CLARIFICATION items resolved

| # | Item | Resolution |
|---|------|------------|
| 1 | Comparison metric + threshold | Cosine similarity via `Comparison` port; threshold 0.5 env-overridable (R-1) |
| 2 | Session mechanism | Server-side `AuthSession` in PostgreSQL + signed http-only cookie; 30 min default; no JWT (R-2/R-3) |
| 3 | Non-revealing error shape | Single `AuthFailed` exception → byte-identical 401 `auth_failed`; 400 for capture codes (R-4) |
| 4 | Login evaluation order | Detection before lookup (as explicitly stated); eliminates residual leak (R-5) |
| 5 | Cookie signing | `itsdangerous.URLSafeTimedSerializer` on the session id; http-only, SameSite=Lax (R-3) |
| 6 | Route protection | Real `require_valid_session` FastAPI dependency replacing the placeholder (R-6) |
| 7 | Frontend session wiring | Real `SessionContext` from `/api/auth/me` + `ProtectedRoute` gating (R-7) |
| 8 | Login state machine | Mirror onboarding 7-state machine; reuse `CameraCapture` (R-8) |
| 9 | Logout idempotence | Always 200 `{"status":"ok"}`; best-effort revoke; clear cookie (R-9) |
| 10 | Observability | structlog JSON: event/duration/status/error_code only; no biometrics (R-10) |

No item was escalated as BLOCKING. The one security-adjacent item (R-5, evaluation order) is a documented demo limitation under Principle VIII (no security guarantee), not a security guarantee itself; the resolution follows the spec's explicit ordering statements and is strictly less information-leaking than the alternative.
