# Contract: POST /api/analysis/mood

**Source**: PRD §8 | **Status in Fase 1**: stub (deterministic mock; no real mood model — SC-010)

Processes a capture to estimate mood. **Requires session.**

## Request

`multipart/form-data`, with a valid session placeholder.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `image` | file (JPEG) | yes | ≤ 2 MB, ≤ 640px long edge |

## Success — `200 OK`

```json
{
  "label": "neutral",
  "confidence": 0.74,
  "disclaimer": "Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."
}
```

- `label`: one of `neutral`, `feliz`, `triste`, `sorprendido`, `no concluyente` (PRD §6.4). Mock returns `"neutral"`.
- `confidence`: float ∈ [0, 1]. Mock returns `0.74`.
- `disclaimer`: fixed string (PRD §6.4 — must communicate this is a model inference, not objective measurement).

## Errors

| Status | Condition | Body |
|--------|-----------|------|
| `401` | no session placeholder | `{"detail":"unauthenticated"}` |
| `422` | missing `image` | validation error shape |
| `400` | malformed image (image validation) | `{"detail":"invalid image"}` |

## Contract test assertions

- With session + image → `200` with `label`, `confidence` (float), `disclaimer` (exact string).
- Without session → `401`.
- Missing `image` → `422`.
- Mock values are deterministic constants (SC-005).
