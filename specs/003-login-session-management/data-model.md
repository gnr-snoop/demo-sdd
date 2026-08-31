# Data Model: Login & Session Management (Fase 3)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

This spec fills the real persistence and lifecycle behavior for the `AuthSession` entity (declared in spec 001, table already migrated). `User` and `FaceTemplate` are reused from specs 001/002 with no new attributes. The data model below documents `AuthSession` fields, validation, relationships, and state transitions, plus the new value objects, ports, and error/result types introduced by this spec.

---

## Entities

### AuthSession (declared spec 001, behavior implemented spec 003)

The authenticated session created after successful face verification.

| Field | Type | Constraints | Login/Session Behavior |
|-------|------|-------------|------------------------|
| `id` | UUID v4 | PK, domain-owned (`uuid.uuid4()`) | Generated on session creation |
| `user_id` | UUID v4 | FK → `users.id`, non-null | Set to the verified `User.id` |
| `created_at` | timestamptz | non-null | Set on creation (injectable `now` for tests) |
| `expires_at` | timestamptz | non-null, `= created_at + session_lifetime` | `created_at + Settings.session_lifetime_seconds` (default 1800s / 30 min) |
| `revoked_at` | timestamptz | nullable | `null` on creation; set to `now` on logout |

**Validity rule (FR-006):** A session is valid **iff** `revoked_at IS NULL AND expires_at > now`. All four invalid cases (absent cookie, unknown id, expired, revoked) collapse to the same `401 unauthenticated` response on protected endpoints.

**Relationships:**
- `User` 1 — N `AuthSession` (a user may hold many concurrent sessions; no single-session constraint — demo-first).
- No FK to `FaceTemplate`; login reads the template via the `User`.

**State transitions:**
```
[created] ──logout──> [revoked]
[created] ──expires_at passes──> [expired]   (no row change; validity computed from expires_at)
[revoked] / [expired] ──any protected call──> 401 unauthenticated
```
Sessions are never un-revoked. Re-login creates a new `AuthSession`; the old row is untouched.

### User (from spec 002, reused — no new attributes)

Looked up by normalized identifier (trim + lowercase) during login via `UserRepository.get_by_identifier`. No new fields, no state transition in this spec (the `enrolled → active` transition noted in spec 002 is not exercised here — demo-first; `User.status` is not required for login).

### FaceTemplate (from spec 002, reused — no new attributes)

Loaded by `FaceTemplateRepository.get_by_user(user_id)` during login. Its `embedding` (JSONB, 128-dim for mock) is compared against the captured embedding via cosine similarity. `model_version` (`"mock-embedder-v1"`) is not consulted for login in this spec (model-version mismatch is guarded at the comparison port by dimension check; real model-version policy is Fase 5).

---

## Value Objects / Result Types

### ComparisonResult (new, spec 003)

```
ComparisonResult { similarity: float, accepted: bool }
```
Produced by the login use-case from `Comparison.compare(captured, stored)` and the threshold: `accepted = similarity >= Settings.verification_threshold`. Not persisted; not logged (only `accept`/`reject` decision is logged, not the score — FR-023).

### Signed session cookie (infrastructure artifact — not a domain entity)

| Attribute | Value |
|-----------|-------|
| Name | `fid_session` (`Settings.session_cookie_name`) |
| Value | `itsdangerous`-signed `AuthSession.id` (UUID v4 string) |
| HttpOnly | `true` |
| SameSite | `Lax` |
| Secure | `Settings.session_cookie_secure` (off for localhost demo) |
| Path | `/` |
| Max-Age | not set on login (session lifetime is server-side); `0` on logout (clear) |

The cookie carries only the signed session id; all session state (expiry, revocation) is server-side in PostgreSQL (OQ-3). Tampered/unsigned/unknown tokens are treated identically to an absent cookie.

### Error response (API layer — reused from spec 002)

```
ErrorResponse { error: ErrorBody }
ErrorBody { code: str, message: str }
```

Stable machine codes used in this spec: `auth_failed`, `unauthenticated`, `no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, `internal_error`.

### Login/session domain exceptions (new, spec 003)

Typed exceptions raised by the login/session use-cases, mapped by the route handler to `ErrorResponse`:

| Exception | HTTP Status | Machine Code | Notes |
|-----------|-------------|-------------|-------|
| `AuthFailed` | 401 | `auth_failed` | Single exception for nonexistent-identifier AND below-threshold (byte-identical response) |
| `InvalidImage` | 400 | `invalid_image` | Undecodable/unsupported/oversized |
| `NoFace` | 400 | `no_face` | Detector returns 0 faces |
| `MultipleFaces` | 400 | `multiple_faces` | Detector returns >1 face |
| `InsufficientQuality` | 400 | `insufficient_quality` | One face, score < quality threshold |
| `Unauthenticated` | 401 | `unauthenticated` | Session-gating on protected endpoints |
| `LoginInternalError` | 500 | `internal_error` | Embedder/comparison/DB failure during login |

**Status-code reservation (FR-010):** `401` is used exclusively for `auth_failed` (login identity failure) and `unauthenticated` (session-gating). `400` is used exclusively for the capture-quality codes. `500` for `internal_error`. This makes the capture-vs-auth distinction statically testable.

---

## Ports

### Comparison (filled with real logic in spec 003)

```
class Comparison(Protocol):
    def compare(self, a: list[float], b: list[float]) -> float:  # cosine similarity
        ...
```
- Raises `ComparisonError` (mapped to `LoginInternalError` → 500) on dimension mismatch (`len(a) != len(b)`).
- Concrete adapter: `CosineComparison` (pure-Python dot product / norms; no numpy in the domain).
- Swappable for Fase 5 (e.g. a numpy-backed or different-metric adapter) without touching the domain (FR-021, Principle VII).

### SessionManager (filled with real logic in spec 003; declared spec 001)

```
class SessionManager(Protocol):
    async def create(self, user_id: UUID, now: datetime, lifetime: timedelta) -> AuthSession: ...
    async def get_valid(self, session_id: UUID, now: datetime) -> AuthSession | None: ...
    async def revoke(self, session_id: UUID, now: datetime) -> None: ...
```
- `get_valid` returns the row iff `revoked_at IS NULL AND expires_at > now`, else `None`.
- `revoke` is idempotent (no-op on unknown/already-revoked id).
- Concrete adapter: `SqlAlchemySessionManager` (async, against the existing `auth_sessions` table).

### Reused ports (unchanged from spec 001/002)

| Port | Methods | Use in login |
|------|---------|--------------|
| `Detector` | `detect(image: bytes) -> DetectionResult` | Capture validation (exactly one face + quality) |
| `Embedder` | `embed(face_image: bytes) -> Embedding` | Produce captured embedding |
| `UserRepository` | `async get_by_identifier(normalized: str) -> User \| None` | Lookup by normalized identifier |
| `FaceTemplateRepository` | `async get_by_user(user_id: UUID) -> FaceTemplate \| None` | Load stored embedding |
| `ImageStorage` | (not used by login — login does not persist a new image) | — |

---

## Schema / Migrations

**No schema change required.** The existing `0001_initial_schema` migration (spec 001) already defines the `auth_sessions` table with `id`, `user_id` (FK → `users.id`), `created_at`, `expires_at`, `revoked_at`.

An optional performance index `CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id)` and `CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at)` may be added in a `0003_session_indexes.py` migration, but for the demo's single-tenant scale this is YAGNI — documented as optional, not required. If added, it is a no-op semantically.

---

## Login use-case orchestration (FR-021 — port-only deps)

```
LoginService.login(identifier: str, image_bytes: bytes, now: datetime):
  1. normalize identifier (trim + lowercase)            # reuse spec 002 validation
  2. decode + enforce image limits + resize              → InvalidImage (400)
     (reuse spec 002 image_handling; limits from Settings)
  3. detect faces                                        → NoFace (400) / MultipleFaces (400)
     quality check (score >= quality_threshold)         → InsufficientQuality (400)
  4. user = await user_repo.get_by_identifier(normalized)
     template = await face_template_repo.get_by_user(user.id)   if user else None
     if user is None or template is None: raise AuthFailed (401)   # generic, non-revealing
  5. captured = embedder.embed(image_bytes)              → LoginInternalError (500) on failure
  6. similarity = comparison.compare(captured.vector, template.embedding)
                                                         → LoginInternalError (500) on dim mismatch
     if similarity < Settings.verification_threshold: raise AuthFailed (401)  # identical to step 4
  7. session = await session_manager.create(user.id, now, lifetime)
  8. return LoginSuccess(userId=user.id, status="authenticated", session_id=session.id)
```

Steps 4 and 6 raise the **same** `AuthFailed` exception with the **same** message → byte-identical 401 response (FR-008/SC-003). No session is created on any failure path (FR-004/SC-004). The use-case imports only ports + entities + result types + exceptions (no FastAPI, no SQLAlchemy, no ML, no `itsdangerous`) — enforced by the extended `test_domain_purity` static check (FR-021/SC-009).

**Evaluation order note (R-5):** Detection (step 3) precedes lookup (step 4), per the spec's explicit ordering. Capture-quality errors therefore surface uniformly for all identifiers (existing or nonexistent), which eliminates the residual identifier-existence leak and is consistent with Principle VIII.

---

## Session-gating dependency

```
require_valid_session(request, session_manager, cookie_service, now):
  token = request.cookies.get(Settings.session_cookie_name)
  session_id = cookie_service.unsign(token)   if token else None     # None on tamper/absence
  session = await session_manager.get_valid(session_id, now)          # None if unknown/expired/revoked
  if session is None: raise HTTPException(401, ErrorResponse(unauthenticated))
  return session
```

Protected endpoints: `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`.
Unprotected: `POST /api/auth/face-login`, `POST /api/onboarding` (FR-014).
