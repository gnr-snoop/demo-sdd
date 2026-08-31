# Contract: POST /api/analysis/age

**Source**: PRD §8 | **Status in Fase 1**: stub (deterministic mock; no real age model — SC-010)

Processes a capture to estimate age. **Requires session.**

## Request

`multipart/form-data`, with a valid session placeholder.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `image` | file (JPEG) | yes | ≤ 2 MB, ≤ 640px long edge |

## Success — `200 OK`

```json
{
  "estimatedAge": 32,
  "range": {
    "min": 27,
    "max": 37
  },
  "disclaimer": "La edad es una estimación visual y puede contener un margen de error significativo."
}
```

- `estimatedAge`: integer. Mock returns `32`.
- `range`: object `{min, max}` integers with `min <= estimatedAge <= max`. Mock returns `{27, 37}`.
- `disclaimer`: fixed string (PRD §6.4 — must communicate this is a visual estimate with significant error margin).

## Errors

| Status | Condition | Body |
|--------|-----------|------|
| `401` | no session placeholder | `{"detail":"unauthenticated"}` |
| `422` | missing `image` | validation error shape |
| `400` | malformed image (image validation) | `{"detail":"invalid image"}` |

## Contract test assertions

- With session + image → `200` with `estimatedAge` (int), `range.min <= estimatedAge <= range.max`, `disclaimer` (exact string).
- Without session → `401`.
- Missing `image` → `422`.
- Mock values are deterministic constants (SC-005).
