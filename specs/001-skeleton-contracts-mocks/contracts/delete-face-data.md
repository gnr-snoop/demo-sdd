# Contract: DELETE /api/users/{userId}/face-data

**Source**: PRD §8 | **Status in Fase 1**: stub (mock; no real deletion logic — SC-010; real deletion deferred to spec 006)

Eliminates the face template and associated onboarding data for a user. **Requires session.**

## Request

No body. Path parameter + a valid session placeholder.

| Parameter | Type | Validation |
|-----------|------|------------|
| `userId` | UUID v4 string (path) | valid UUID format |

## Success — `200 OK`

```json
{
  "userId": "00000000-0000-4000-8000-000000000001",
  "status": "deleted"
}
```

- `userId`: the UUID v4 path parameter echoed.
- `status`: `"deleted"` (mock — no real DB/filesystem deletion in Fase 1).

## Errors

| Status | Condition | Body |
|--------|-----------|------|
| `401` | no session placeholder | `{"detail":"unauthenticated"}` |
| `422` | `userId` is not a valid UUID | validation error shape |

## Contract test assertions

- With session + valid UUID `userId` → `200` with `userId` (echoed UUID v4) and `status == "deleted"`.
- Without session → `401`.
- Malformed `userId` (not a UUID) → `422`.
- Mock does not actually remove data in Fase 1 (SC-010); real deletion is spec 006.
