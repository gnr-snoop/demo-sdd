# Contract: GET /api/auth/me

**Source**: PRD §8, FR-011, FR-014, FR-015 | **Status**: real logic (spec 003; supersedes spec 001 stub)

Returns the current session state. Used by the frontend `SessionContext` to bootstrap real session state on app load and by `ProtectedRoute` to gate `/dashboard`. This endpoint is **session-protected** (FR-014).

## Request

No body. The signed session cookie `fid_session` is sent automatically by the browser.

```
GET /api/auth/me
Cookie: fid_session=<signed-session-id>
```

## Success — `200 OK`

```json
{
  "authenticated": true,
  "userId": "550e8400-e29b-41d4-a716-446655440000"
}
```

- `authenticated`: `true`.
- `userId`: UUID v4 string (the `AuthSession.user_id`).

Returned when the cookie's session id maps to an `AuthSession` row with `revokedAt IS NULL` and `expiresAt > now` (FR-006).

## Errors

`401 Unauthorized` — when there is no cookie, the cookie is tampered/unsigned, the session id is unknown, `revokedAt` is set, or `expiresAt` has passed.

```json
{
  "error": {
    "code": "unauthenticated",
    "message": "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."
  }
}
```

All four invalid-session cases (absent, unknown, expired, revoked) and the tampered-cookie case produce this **identical** `401 unauthenticated` response (FR-006/SC-006). No internal error is raised for tampered/unknown cookies.

**Status-code reservation:** `401` here is `unauthenticated` (session-gating), distinct from login's `auth_failed`. The frontend uses the `401` to set `authenticated = false` and redirect `ProtectedRoute` to `/login` (FR-015/SC-008).

## Contract test assertions

- Valid (non-expired, non-revoked) session cookie → `200` with `authenticated == true` and `userId` (UUID v4).
- No cookie → `401` `{"error": {"code": "unauthenticated", ...}}`.
- Tampered cookie → `401` `unauthenticated` (no 500).
- Unknown session id (row deleted out-of-band) → `401` `unauthenticated`.
- Expired session (`expiresAt` in the past) → `401` `unauthenticated`.
- Revoked session (`revokedAt` set) → `401` `unauthenticated`.
- All four invalid cases return byte-identical `401 unauthenticated` responses.
- A deliberate contract-violating change to the success or error shape causes at least one contract test to fail.
