# Research: Face Data Deletion (Fase 6 partial)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

Phase 0 research resolves all NEEDS CLARIFICATION items and documents the design
decisions grounded in the existing codebase (specs 001-004). All decisions are
pinned by the spec's Clarifications section; this file records the *technical
mechanism* for each, verified against the actual code.

## Codebase Context

Gathered from the codebase-memory knowledge graph (project `demo-sdd`,
generation 2026-09-01, coverage clean on all cited paths) and source reads.

### Existing scaffolding (reuse — do NOT re-create)

- **Ports** (`backend/src/face_insight/domain/ports.py`): `UserRepository.delete`,
  `FaceTemplateRepository.delete_by_user`, `ImageStorage.delete` **already exist**.
  `SessionManager` has `create`/`get_valid`/`revoke` but **no `delete_by_user`**.
- **Adapters**: `SqlAlchemyUserRepository.delete`, `SqlAlchemyFaceTemplateRepository.delete_by_user`,
  `FilesystemImageStorage.delete` (a `shutil.rmtree` that is a no-op when the dir
  is absent — exactly the best-effort semantics FR-005 needs), and Mock equivalents
  all exist.
- **API route stub** (`api/routes/users.py`): `delete_face_data` exists, is
  session-protected via `require_valid_session`, validates `user_id` as UUID v4
  (FastAPI → 422), and returns a mock `DeleteFaceDataResponse`. Needs real logic.
- **Schema** (`api/schemas.py`): `DeleteFaceDataResponse {userId, status="deleted"}`
  and the error shape `ErrorResponse {error: ErrorBody{code, message}}` already exist.
- **Frontend** (`services/api.ts`): `deleteFaceData(userId)` + `DeleteFaceDataResponse`
  interface exist. **Gap**: the function does not send `credentials: "include"`
  and does not parse errors (it `return resp.json()` even on non-2xx).
- **Contract tests** (`tests/contract/test_http_contracts.py`): only
  `test_delete_face_data_without_session_401` and
  `test_delete_face_data_malformed_uuid_422` exist. Missing 200/403/404/500.
- **Session validation** (`api/dependencies.py`): `require_valid_session` returns
  the valid `AuthSession` (which carries `user_id`) or raises
  `UnauthenticatedError` → 401. This is the session-gating step; the authz check
  (`session.user_id == path user_id`) is new and lives in the route/service.
- **Dashboard** (`pages/Dashboard.tsx`): has mood button, disabled age placeholder,
  and "Cerrar sesión" button. No "Eliminar mis datos" button. Uses `useSession()`
  (`{logout, userId}`) and `useNavigate()`.
- **SessionContext** (`context/SessionContext.tsx`): `logout()` calls
  `api.logout()` then clears state. Deletion needs a `clearSession()` that clears
  state **without** calling `/api/auth/logout` (the session is already destroyed
  by the deletion transaction; calling logout would hit a deleted session).

### Reuse opportunities

- **UnitOfWork callable-injection pattern** (see R-2): `OnboardingService.onboard`
  receives a `save_user_with_template` async callable injected from
  `SqlAlchemyUnitOfWork`, keeping the domain SQLAlchemy-free while achieving
  atomicity. Deletion follows the identical pattern.
- **Error mapping**: `UnauthenticatedError` → 401 is registered in `main.py`.
  New `Forbidden` (→403) and `NotFound` (→404) domain exceptions follow the same
  `OnboardingError` subclass + handler-registration pattern.
- **Cookie clearing**: spec 003 logout clears the session cookie on the response.
  Deletion reuses the same `session_cookie_service.clear(response)` mechanism.

### Integration touch-points

| Touch-point | File | Change |
|-------------|------|--------|
| Route handler | `api/routes/users.py` | Replace stub with authz + 404 + service call + cookie clear |
| Domain use-case | `domain/deletion.py` (NEW) | `DeletionService.delete_face_data(user_id, session_user_id)` |
| Atomic DB op | `adapters/db/repositories.py` | `SqlAlchemyUnitOfWork.delete_user_face_data(user_id)` |
| Wiring | `main.py` | Build + store `DeletionService` on `app.state` |
| Error handlers | `main.py` | Register `Forbidden`→403, `NotFound`→404, `DeletionInternalError`→500 |
| Frontend api | `services/api.ts` | `deleteFaceData`: add `credentials:"include"` + `parseError` |
| Dashboard UI | `pages/Dashboard.tsx` | "Eliminar mis datos" button + confirm dialog + post-delete handling |
| Session ctx | `context/SessionContext.tsx` | `clearSession()` for post-deletion state clear |

### Coverage limitations

None. `check_index_coverage` reported `no_recorded_issue` on all seven cited
source paths; the graph is fresh (only `docs/` and the new spec dir changed
since last index). Claims above are verified against source reads.

---

## Research Items

### R-1: Hard delete vs soft-delete — mechanism

**Decision**: Hard delete. `DELETE` SQL on `User`, `FaceTemplate`, and
`AuthSession` rows within one transaction.

**Rationale**: Pinned by spec Clarifications + Principle I (demo-first) + YAGNI.
Hard delete makes "the user is gone" literally true; post-deletion login fails
at identifier lookup (no `User`) → generic `401 auth_failed` (spec 003
non-revealing contract). No `status = disabled` state, no retention, no audit.

**Alternatives considered**: Soft-delete (`status = disabled`) — rejected: adds
disabled-state handling everywhere (login must filter, me must reject, etc.) for
zero demo value, and contradicts the "right to be forgotten" narrative.

### R-2: How to make DB deletion a single PostgreSQL transaction (FR-004)

**Decision**: Extend the existing `SqlAlchemyUnitOfWork` with a
`delete_user_face_data(user_id)` async method that opens **one** async
`AsyncSession`, deletes `FaceTemplateORM` rows → `AuthSessionORM` rows →
`UserORM` (dependents first, then parent), and commits. On any exception it
rolls back and re-raises. The domain `DeletionService` receives this as an
**injected async callable** (`delete_user_face_data`), exactly mirroring how
`OnboardingService` receives `save_user_with_template`.

**Rationale**: The individual repository port `delete` methods each open their
**own** `async with self._session_factory() as session:` and commit
independently (verified in `SqlAlchemyUserRepository.delete` /
`SqlAlchemyFaceTemplateRepository.delete_by_user`). Calling three port methods
sequentially would be **three separate transactions** — a partial failure could
leave `FaceTemplate` deleted but `User` intact, violating FR-004's "no partial
DB state" guarantee. The `SqlAlchemyUnitOfWork` pattern already exists for
exactly this reason (`save_user_with_template` wraps User+FaceTemplate insert in
one session) and is the established, constitution-compliant (Principle VII)
mechanism: the domain depends on a callable, not on SQLAlchemy.

**Why not add `SessionManager.delete_by_user` as a port method?** The spec
Assumptions mention adding a `delete_by_userId` port method "if not yet present".
But a `SessionManager.delete_by_user` port method would open its **own**
transaction separate from the User/FaceTemplate deletion — it cannot participate
in the same single transaction as the other deletes. The UnitOfWork is the only
mechanism that gives atomicity across all three tables. Adding the port method
is therefore insufficient for FR-004 and is not needed: the UnitOfWork deletes
`AuthSessionORM` rows directly (consistent with how `save_user_with_template`
operates on `UserORM`/`FaceTemplateORM` directly). No new port method is added.

**Alternatives considered**:
- Three sequential port `delete` calls — rejected: three transactions, partial-failure risk.
- A new `UnitOfWork` Protocol port — rejected: the existing pattern injects a
  **callable**, not a port object, and the domain already accepts callables
  (`save_user_with_template`). A Protocol would be more ceremony for no benefit.
- Two-phase commit across DB + filesystem — rejected: Principle I (demo-first),
  explicitly out of scope (FR-005 best-effort).

### R-3: Authorization check placement and the 403 "intentionally revealing" choice

**Decision**: After `require_valid_session` (which gives the valid `AuthSession`
with `user_id`), the route compares `session.user_id` to the path `user_id`. A
mismatch raises `Forbidden` → `403 forbidden` with body
`{"error":{"code":"forbidden","message":"Solo puedes eliminar tus propios datos."}}`.
No deletion occurs.

**Rationale**: Pinned by spec. The caller is **already authenticated** at this
point, so returning 403 (not 401) is correct and the message may reveal that the
caller is authenticated-but-not-the-owner. This is deliberately distinct from
login's non-revealing `auth_failed` (spec 003): there the system must not reveal
whether an identifier exists; here the caller's identity is already established
and the demo narrative is "you can only delete your own data". This is demo-grade
authz under Principle VIII (no security guarantee) — it blocks the obvious abuse
(deleting someone else's data) without production-grade authorization.

**Strict-mode note**: This is a security-relevant decision (intentional
information disclosure in the 403). It is **pinned by the spec** and justified
under Principle VIII. It narrows guarantees (a non-goal), it does not introduce
a new security claim. Not BLOCKING.

**Alternatives considered**: Return 404 instead of 403 (hide that the other user
exists) — rejected: the spec explicitly chooses 403 as intentionally-revealing
for the demo narrative; 404 would be production-grade authz hardening
(contradicts Principle VIII/I).

### R-4: Condition evaluation order (FR-008)

**Decision**: `422` (FastAPI path validation, before handler) → `401`
(`require_valid_session`) → `403` (authz: `session.user_id == path user_id`) →
`404` (load `User` for path `user_id`; absent → `NotFound`) → deletion operation
(`500 internal_error` on failure, rollback) → cookie clear → `200`.

**Rationale**: Pinned by spec. The 404 guard is defensive: a valid matching
session guarantees the `User` exists, so 404 is only reachable via out-of-band
deletion or a concurrent race (documented demo edge case, Principle VIII). The
`User` load is done via `UserRepository.get(user_id)` (existing port).

**Alternatives considered**: Skip the 404 guard (session guarantees existence) —
rejected: the spec explicitly includes it as a defensive guard, and it costs one
`SELECT` (demo-grade cost).

### R-5: Filesystem cleanup semantics (FR-005)

**Decision**: After a successful DB commit, call `ImageStorage.delete(user_id)`
inside a `try/except`. `FilesystemImageStorage.delete` already does
`shutil.rmtree(user_dir)` and is a no-op when the dir is absent — so "folder
already gone" and "deletion succeeds" are both handled. On any exception, log a
structured JSON warning (no image/embedding content — Principle VIII/FR-016) and
**still return 200**. The endpoint does not fail after a successful DB commit.

**Rationale**: The DB is the source of truth for login (no `FaceTemplate` → no
login). An orphaned image folder is a minor demo inconsistency, not a functional
failure. A two-phase commit is out of scope (Principle I).

**Alternatives considered**: Fail the endpoint if FS cleanup fails — rejected:
contradicts FR-005 and Principle I; the user is already forgotten in the DB.

### R-6: Cookie clearing on the 200 response

**Decision**: The route calls `session_cookie_service.clear(response)` on the
`200` `JSONResponse` (same mechanism as spec 003 logout). The frontend also
clears its in-memory session state via a new `clearSession()` (which does **not**
call `api.logout()` — the session is already destroyed by the transaction).

**Rationale**: The current `AuthSession` is among the rows deleted in the
transaction, so the cookie must be invalidated to avoid a stale-cookie reference.
Reusing the logout cookie-clear mechanism is consistent with spec 003.

**Alternatives considered**: Let the frontend clear the cookie via JS — rejected:
the cookie is server-side signed/HttpOnly; only the backend can clear it
authoritatively.

### R-7: Frontend post-deletion navigation target

**Decision**: Navigate to `/` (the welcome page), distinct from logout's `/login`.
Release the camera stream (Dashboard unmounts on navigation) and discard held
mood/age results.

**Rationale**: Pinned by spec. After deletion there is no profile to log in with,
so the welcome/onboarding entry point is the coherent destination. The camera
stream lifecycle is owned by `CameraCapture` (acquired on mount, released on
unmount — spec 004); navigating away unmounts the Dashboard and releases it.

**Alternatives considered**: Redirect to `/login` — rejected: misleading (implies
the person can log back in with the deleted profile).

### R-8: Frontend confirmation dialog implementation

**Decision**: A lightweight native `window.confirm`-style dialog (or a small
inline modal component) with the message "Esta acción eliminará tu perfil y
plantilla facial de forma permanente. ¿Continuar?" and Confirm/Cancel options,
both keyboard-reachable. On confirm: disable the button, show a processing state,
call `api.deleteFaceData(userId)`. On cancel: no request, dashboard unchanged.

**Rationale**: Principle I (demo-first) — a full settings/confirmation page is
YAGNI. The spec calls for "a lightweight native confirm, not a full settings
page". A small inline modal (or `window.confirm`) satisfies FR-010/FR-012
(keyboard-accessible, descriptive names, not color-only state communication).

**Alternatives considered**: A full settings page with a deletion section —
rejected: YAGNI / Principle I.

### R-9: Frontend error handling (FR-011)

**Decision**:
- `500 internal_error` → actionable error surface with a "Reintentar" button,
  re-enable the "Eliminar mis datos" button, no full page reload.
- `401 unauthenticated` (session expired mid-request) → transition to
  unauthenticated state, redirect to `/login`.
- `403 forbidden` / `404 not_found` → show the server message (these are
  edge cases for the self-delete flow but handled for completeness).

**Rationale**: Pinned by spec FR-011. Reuses the Dashboard's existing
recoverable-error pattern (mood error surface + retry).

### R-10: Domain purity — no ML ports, no infra imports (FR-013/FR-014, Principle VII)

**Decision**: `DeletionService` depends only on `UserRepository` (for the 404
lookup), `ImageStorage` (for best-effort FS cleanup), a `Logger`-like structured
logging callable, and the injected `delete_user_face_data` async callable. It
imports **no** SQLAlchemy, FastAPI, detector/embedder/mood/age port, or
filesystem adapter. A `test_domain_purity`-style static check will assert
`deletion.py` imports only from `.ports`, `.entities`, `.exceptions`, and stdlib.

**Rationale**: Constitution Principle VII + FR-013/FR-014. Deletion is a pure
data/infrastructure operation; no ML port is invoked.

### R-11: Observability (FR-016)

**Decision**: Structured JSON logs only: `{type:"deletion", userId:<uuid>,
status:"deleted"|"failed", duration_ms:<int>}` and, on FS-cleanup failure,
`{type:"deletion_fs_cleanup_warning", userId:<uuid>}`. No image bytes, embedding
vectors, or biometric content are logged. No audit log / immutable event store.

**Rationale**: Principle VIII (no traceability guarantee) + FR-016. Consistent
with specs 001-004 logging.

### R-12: Idempotence (spec Clarifications)

**Decision**: No special idempotence. First call succeeds and destroys the
session; a second call with the now-deleted session receives `401 unauthenticated`.
The frontend disables the button during the in-flight first call, preventing
double submission in practice.

**Rationale**: YAGNI / Principle I.

---

## Summary of resolved items

| # | Item | Decision |
|---|------|----------|
| R-1 | Hard vs soft delete | Hard delete |
| R-2 | Single-transaction mechanism | Extend `SqlAlchemyUnitOfWork.delete_user_face_data`; inject as callable |
| R-3 | Authorization + 403 revealing | `session.user_id == path user_id`; 403 intentionally revealing (Principle VIII) |
| R-4 | Condition order | 422 → 401 → 403 → 404 → delete → cookie clear → 200 |
| R-5 | FS cleanup | Best-effort after commit; `ImageStorage.delete` (no-op if absent); 200 + warning on failure |
| R-6 | Cookie clear | Backend clears cookie on 200; frontend `clearSession()` (no `/logout` call) |
| R-7 | Redirect target | `/` (welcome page) |
| R-8 | Confirm dialog | Lightweight native confirm / inline modal |
| R-9 | Frontend errors | 500→retry, 401→/login, 403/404→server message |
| R-10 | Domain purity | Ports + injected callable only; no ML/infra imports |
| R-11 | Observability | Structured JSON logs; no biometric content; no audit |
| R-12 | Idempotence | None (natural 401 on second call) |

All NEEDS CLARIFICATION items resolved. No BLOCKING items in strict mode
(security/privacy-relevant choices are pinned in the spec and justified under
Principles VIII/I — they narrow guarantees, not introduce new ones).
