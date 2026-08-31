# Contract: POST /api/auth/logout

**Source**: PRD §8, FR-012, FR-013, FR-014, FR-016 | **Status**: real logic (spec 003; supersedes spec 001 stub)

Revokes the current session and clears the cookie. **Idempotent** — always returns success from the client's perspective. This endpoint is **session-protected** in the sense that it reads the cookie, but it **never returns an error**; a no-cookie or already-invalid session still gets `200` (FR-012).

## Request

No body. The signed session cookie `fid_session` is sent automatically by the browser.

```
POST /api/auth/logout
Cookie: fid_session=<signed-session-id>
```

## Success — `200 OK` (always)

```json
{
  "status": "ok"
}
```

This response is returned **identically** for:
- a valid session (the `AuthSession` row gets `revokedAt = now`, the cookie is cleared),
- no cookie (no-op, cookie cleared),
- a tampered/unknown session id (no-op, cookie cleared),
- an already-expired session (no-op, cookie cleared),
- an already-revoked session (no-op, cookie cleared).

**No error body is ever returned from logout** (FR-012).

**Side effects when a valid session is presented:**
- `AuthSession.revokedAt` set to `now` (the row is invalidated — FR-016/SC-007).
- Cookie cleared via `Set-Cookie: fid_session=; Max-Age=0; HttpOnly; SameSite=Lax; Path=/`.

After logout, the revoked session is rejected by every protected endpoint with `401 unauthenticated` (FR-013/AC-009).

## Contract test assertions

- Valid session cookie → `200` `{"status": "ok"}`; the `AuthSession` row now has `revokedAt` set; `Set-Cookie` clears the cookie (`Max-Age=0`).
- After a successful logout, calling any protected endpoint with the old cookie → `401 unauthenticated`.
- No cookie → `200` `{"status": "ok"}` (idempotent, no error).
- Tampered/unknown session id → `200` `{"status": "ok"}` (idempotent).
- Already-revoked session → `200` `{"status": "ok"}` (idempotent).
- Expired session → `200` `{"status": "ok"}` (idempotent).
- Logout never returns a non-200 status and never returns an error body.
- A deliberate contract-violating change to the response shape causes at least one contract test to fail.
