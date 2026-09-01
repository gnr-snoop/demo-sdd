# Contract: DELETE /api/users/{userId}/face-data

**Source**: PRD §8, FR-017 | **Status**: real (spec 006 — supersedes the spec 001 stub)

Eliminates the face template and associated onboarding data for a user. **Requires
a valid session, and the session's `userId` must match the path `userId`** (demo-grade
authorization — Constitution Principle VIII; no admin panel).

## Request

No body. Path parameter + a valid session cookie.

| Parameter | Type | Validation |
|-----------|------|------------|
| `userId` | UUID v4 string (path) | valid UUID v4 format (FastAPI → 422 on malformed) |

The session cookie (signed, HttpOnly — spec 003) must be present and reference a
valid (non-expired, non-revoked) `AuthSession`.

## Success — `200 OK`

```json
{
  "userId": "00000000-0000-4000-8000-000000000001",
  "status": "deleted"
}
```

- `userId`: the UUID v4 path parameter echoed.
- `status`: `"deleted"`.
- The session cookie is **cleared** on the response (the current `AuthSession`
  is among the rows deleted).

### Side effects (on 200)

1. `FaceTemplate` row(s) for the user — deleted.
2. All `AuthSession` rows for the user — deleted (every session invalidated).
3. `User` row — hard-deleted.
4. Steps 1-3 execute in a **single PostgreSQL transaction** (dependents first,
   then parent, then commit). On failure → rollback, `500`, no partial DB state.
5. After commit, `usuarios/<user-id>/` folder + `pictures.jpg` — best-effort
   `shutil.rmtree`; absence or failure does not fail the endpoint (200 + warning log).

## Errors

All error responses use the spec-002-pinned shape
`{"error": {"code": "...", "message": "..."}}`.

| Status | `code` | Condition | Message (example) |
|--------|--------|-----------|-------------------|
| `422` | *(FastAPI validation)* | `userId` is not a valid UUID v4 | FastAPI validation error shape (before handler) |
| `401` | `unauthenticated` | no valid session (absent/tampered/unknown/expired/revoked) | "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo." |
| `403` | `forbidden` | valid session but `session.userId != path userId` | "Solo puedes eliminar tus propios datos." |
| `404` | `not_found` | valid matching session but `User` for path `userId` does not exist (out-of-band deletion / race) | "No se encontró el usuario." |
| `500` | `internal_error` | DB transaction failure (rollback, no partial state) or unexpected port error | "Ocurrió un error al eliminar tus datos. Inténtalo de nuevo." |

### Condition evaluation order (FR-008)

```text
422 (malformed UUID) → 401 (unauthenticated) → 403 (forbidden)
  → 404 (not_found) → deletion → cookie clear → 200
```

A malformed path is rejected before any session/authz work; an unauthenticated
caller is rejected before the authz check. The `403 forbidden` is **intentionally
revealing** (the caller is already authenticated; the demo narrative is "you can
only delete your own data") — distinct from login's non-revealing `auth_failed`.

## Contract test assertions

- **200 happy path**: with a valid session and matching `userId` (after onboarding
  + login) → `200` with `userId` (echoed UUID v4) and `status == "deleted"`, a
  cleared session cookie, and `User`/`FaceTemplate`/`AuthSession` rows gone from
  PostgreSQL and `usuarios/<user-id>/` gone from the filesystem.
- **401 unauthenticated**: without a session cookie → `401` with
  `error.code == "unauthenticated"`; no rows removed.
- **401 expired/revoked**: with an expired/revoked session → `401 unauthenticated`;
  no rows removed.
- **403 forbidden**: with a valid session for user A and user B's `userId` in the
  path → `403` with `error.code == "forbidden"`; no rows removed for A or B.
- **404 not_found**: (edge case — out-of-band user deletion) valid matching session
  but `User` absent → `404` with `error.code == "not_found"`; no deletion.
- **422 malformed UUID**: `userId = "not-a-uuid"` → `422` validation error; no
  rows removed.
- **500 internal_error**: DB transaction failure → `500` with
  `error.code == "internal_error"`; no partial DB state (rollback).
- **Best-effort FS failure**: DB commits but filesystem deletion fails → `200`
  with `userId`/`status:"deleted"`; a structured warning is logged.
- **Error body shape**: every non-2xx error response is
  `{"error": {"code": "<string>", "message": "<string>"}}`.
- **Post-deletion invalidation**: after a 200, `GET /api/auth/me` with the old
  cookie → `401 unauthenticated`, and `POST /api/auth/face-login` with the old
  identifier → `401 auth_failed` (indistinguishable from never-enrolled).

## Out of scope (FR-017)

Soft-delete / retention policies, rate limiting, admin panel/UI, audit trail,
idempotent 200-on-already-deleted semantics. No ML port is invoked.
