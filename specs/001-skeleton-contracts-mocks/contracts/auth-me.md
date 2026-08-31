# Contract: GET /api/auth/me

**Source**: PRD §8 | **Status in Fase 1**: stub (placeholder session check; real session enforcement deferred to spec 003)

Returns the state of the current session.

## Request

No body. Reads the session placeholder (header `X-Session-Id` or cookie).

## Success — `200 OK` (with valid session placeholder)

```json
{
  "userId": "00000000-0000-4000-8000-000000000001",
  "status": "authenticated",
  "expiresAt": "2026-09-01T00:00:00Z"
}
```

- `userId`: UUID v4 string.

## Unauthenticated — `401 Unauthorized` (no/expired session placeholder)

```json
{
  "detail": "unauthenticated"
}
```

## Contract test assertions

- No session placeholder → `401` with `unauthenticated` (not an internal error — handles expired/invalid placeholder gracefully, per spec Edge Cases).
- With a session placeholder → `200` with `userId` (UUID v4), `status == "authenticated"`, `expiresAt` present.
