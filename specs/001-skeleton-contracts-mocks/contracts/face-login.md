# Contract: POST /api/auth/face-login

**Source**: PRD §8 | **Status in Fase 1**: stub (deterministic mock; no real verification logic — SC-010)

Verifies a face and creates a session. In Fase 1, returns a deterministic mock `200` (success) or `401` (failure) response.

## Request

`multipart/form-data`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `identifier` | string | yes | non-empty |
| `image` | file (JPEG) | yes | ≤ 2 MB, ≤ 640px long edge |

## Success — `200 OK`

```json
{
  "userId": "00000000-0000-4000-8000-000000000001",
  "status": "authenticated"
}
```

- `userId`: UUID v4 string (mock fixed constant in tests).

## Failure — `401 Unauthorized`

```json
{
  "detail": "authentication failed"
}
```

- **Generic and non-revealing**: the response MUST NOT distinguish between a non-existent identifier and a non-matching face (FR-007, FR-018, PRD §12).

## Errors

| Status | Condition | Body |
|--------|-----------|------|
| `422` | missing `identifier` or `image` | validation error shape |

## Contract test assertions

- Well-formed request (mock success path) → `200` with `userId` (UUID v4) and `status == "authenticated"`.
- Mock failure path → `401` with a generic message; message is identical whether identifier is unknown or face mismatches.
- Missing `identifier`/`image` → `422`.
