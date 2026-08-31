# Contract: POST /api/auth/logout

**Source**: PRD §8 | **Status in Fase 1**: stub (invalidates the session placeholder; real session revocation deferred to spec 003)

Invalidates the current session.

## Request

No body. Reads the session placeholder.

## Success — `200 OK`

```json
{
  "status": "logged_out"
}
```

## Unauthenticated — `401 Unauthorized` (no session placeholder)

```json
{
  "detail": "unauthenticated"
}
```

## Contract test assertions

- With a session placeholder → `200` with `status == "logged_out"`.
- Without a session placeholder → `401`.
