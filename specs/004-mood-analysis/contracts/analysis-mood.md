# Contract: POST /api/analysis/mood

**Source**: PRD §8, §6.4 | **Status**: real (spec 004 — supersedes the spec 001 stub)

Estimates mood from a single captured image. **Requires a valid session** (spec 003 `require_valid_session`). The mood result is transient — not persisted server-side (FR-014).

## Request

`POST /api/analysis/mood` — `multipart/form-data` — with the session cookie (`fid_session`).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `image` | file (JPEG) | yes | ≤ 2 MB, ≤ 640 px long edge (reused from spec 002, OQ-8) |

The session cookie is sent automatically by the browser (`credentials: "include"`); the backend validates it via `require_valid_session` before any processing.

## Evaluation order (FR-005)

1. **Session validation** (`require_valid_session`) → `401 unauthenticated` if absent/invalid/expired/revoked.
2. **Image decode + limit validation** (`decode_and_normalize`) → `400 invalid_image` if undecodable/unsupported/oversized.
3. **Detection** (exactly one usable face: `face_count == 1` and `score >= quality_threshold`) → `400 no_face` / `multiple_faces` / `insufficient_quality`.
4. **Mood estimation** (`MoodEstimator.estimate_mood`) → port failure → `500 internal_error`.
5. **Label normalization** (`normalize_mood_label`) — out-of-set/low-quality → `no concluyente`.
6. **Response** `200 OK` with `{label, confidence, disclaimer}`.

## Success — `200 OK`

```json
{
  "label": "feliz",
  "confidence": 0.8,
  "disclaimer": "Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `label` | string | yes | ∈ `{neutral, feliz, triste, sorprendido, enojo, no concluyente}` (FR-004) |
| `confidence` | number \| null | no | `float ∈ [0.0, 1.0]` when present, or `null`/omitted when the estimator does not produce one (FR-012a). The mock returns `0.74` (neutral) / `0.8` (feliz, test fixture). |
| `disclaimer` | string | yes | Exact fixed string: `"Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."` (PRD §8, FR-003 — returned verbatim on every `200`). |

**Confidence rendering (frontend)**: when present, rendered as `≈NN%` (nearest integer, e.g. `0.8123` → "≈81%"); when `null`/omitted, only the label + disclaimer are rendered (FR-012a).

## Errors

All error bodies use the pinned shape `{"error": {"code": "...", "message": "..."}}` (spec 002).

| Status | Code | Condition | Body |
|--------|------|-----------|------|
| `401` | `unauthenticated` | no/invalid/expired/revoked session | `{"error":{"code":"unauthenticated","message":"Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."}}` |
| `400` | `invalid_image` | image undecodable/unsupported/oversized | `{"error":{"code":"invalid_image","message":"La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB."}}` |
| `400` | `no_face` | detector returns 0 faces | `{"error":{"code":"no_face","message":"No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar."}}` |
| `400` | `multiple_faces` | detector returns > 1 face | `{"error":{"code":"multiple_faces","message":"Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura."}}` |
| `400` | `insufficient_quality` | single face but score < threshold | `{"error":{"code":"insufficient_quality","message":"La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar."}}` |
| `500` | `internal_error` | detector/mood_estimator port failure; unexpected error | `{"error":{"code":"internal_error","message":"Ocurrió un error inesperado. Inténtalo de nuevo."}}` |

**Status-code reservation**: `401` is reserved exclusively for `unauthenticated` (session-gating). `400` for actionable capture-quality codes. `500` for recoverable `internal_error` (FR-007). No mood result is produced on any error path.

## Contract test assertions

1. **Happy path**: with a valid session + a one-face fixture → `200` with `label` ∈ valid set, `confidence` ∈ [0,1] or null, `disclaimer` == exact PRD §8 string.
2. **No session**: without a cookie / with an expired/revoked session → `401` with `code: "unauthenticated"`; no analysis performed.
3. **Invalid image**: undecodable/oversized image → `400` with `code: "invalid_image"`.
4. **No face**: fixture the mock detector reports 0 faces → `400` with `code: "no_face"`.
5. **Multiple faces**: fixture the mock detector reports 2 faces → `400` with `code: "multiple_faces"`.
6. **Insufficient quality**: fixture with score < threshold → `400` with `code: "insufficient_quality"`.
7. **Port error**: fixture triggering a mood_estimator port exception → `500` with `code: "internal_error"`.
8. **Label normalization**: a fixture producing an out-of-set label → `200` with `label: "no concluyente"`.
9. **Confidence bounds**: every `200` `confidence` (when present) is a float in `[0, 1]`.
10. **Error body shape**: every non-`200` response body matches `{"error": {"code": string, "message": string}}`.
11. **Determinism**: the mock mood estimator returns a fixed label + confidence for the same fixture (SC-005).
