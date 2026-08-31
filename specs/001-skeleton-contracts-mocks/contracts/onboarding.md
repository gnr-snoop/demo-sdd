# Contract: POST /api/onboarding

**Source**: PRD §8 | **Status in Fase 1**: stub (deterministic mock; no real onboarding logic — SC-010)

Registers a person and processes their face. In Fase 1, returns a deterministic mock `201` response.

## Request

`multipart/form-data`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `identifier` | string | yes | non-empty, valid email/username format |
| `consentAccepted` | boolean | yes | must be `true` |
| `image` | file (JPEG) | yes | ≤ 2 MB, ≤ 640px long edge (config; enforcement deferred to spec 002) |

## Success — `201 Created`

```json
{
  "userId": "00000000-0000-4000-8000-000000000001",
  "identifier": "demo@example.com",
  "status": "enrolled"
}
```

- `userId`: UUID v4 string (mock returns a fixed constant in tests).
- `status`: `"enrolled"` (matches `User.status` enum default and the pinned response value).

## Errors

| Status | Condition | Body |
|--------|-----------|------|
| `422` | missing/invalid `identifier`, `consentAccepted != true`, missing `image` | `{"detail":[{"loc":["body","identifier"],"msg":"...","type":"value_error"}]}` |
| `400` | malformed/non-decodable image (image validation) | `{"detail":"invalid image"}` |

## Contract test assertions

- Well-formed request → `201` with body containing `userId` (UUID v4 string), `identifier` (echoed), `status == "enrolled"`.
- Missing `identifier` → `422`.
- `consentAccepted == false` → `422`.
- Missing `image` → `422`.
