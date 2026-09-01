# Contract: POST /api/analysis/age

**Source**: PRD §8, §6.4 | **Status**: real (spec 005 — supersedes the spec 001 stub)

Estimates age from a single captured image. **Requires a valid session** (spec 003 `require_valid_session`). The age result is transient — not persisted server-side (FR-014).

## Request

`POST /api/analysis/age` — `multipart/form-data` — with the session cookie (`fid_session`).

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `image` | file (JPEG) | yes | ≤ 2 MB, ≤ 640 px long edge (reused from spec 002, OQ-8) |

The session cookie is sent automatically by the browser (`credentials: "include"`); the backend validates it via `require_valid_session` before any processing.

## Evaluation order (FR-005)

1. **Session validation** (`require_valid_session`) → `401 unauthenticated` if absent/invalid/expired/revoked.
2. **Image decode + limit validation** (`decode_and_normalize`) → `400 invalid_image` if undecodable/unsupported/oversized.
3. **Detection** (exactly one usable face: `face_count == 1` and `score >= quality_threshold`) → `400 no_face` / `multiple_faces` / `insufficient_quality`.
4. **Age estimation** (`AgeEstimator.estimate_age`) → port failure → `500 internal_error`.
5. **Normalization** (`normalize_age_result`) — point-only → derived symmetric range; range → midpoint estimate; `min` clamped to 0; invariants enforced.
6. **Response** `200 OK` with `{estimatedAge, range, disclaimer}`.

## Success — `200 OK`

```json
{
  "estimatedAge": 32,
  "range": { "min": 27, "max": 37 },
  "disclaimer": "La edad es una estimación visual y puede contener un margen de error significativo."
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `estimatedAge` | integer | yes | Integer years. `range.min <= estimatedAge <= range.max` (FR-002/FR-004). |
| `range.min` | integer | yes | Integer years, `>= 0` (FR-002/FR-004). |
| `range.max` | integer | yes | Integer years, `>= range.min` (FR-002/FR-004). |
| `disclaimer` | string | yes | Exact fixed string: `"La edad es una estimación visual y puede contener un margen de error significativo."` (PRD §8, FR-003 — returned verbatim on every `200`). |

**Normalization rule (FR-004/SC-014)**:
- If the `age_estimator` port returns a **range** `[min, max]`: `estimatedAge = round((min + max) / 2)` clamped into `[min, max]`; `range` is returned as-is (with `min` clamped to 0).
- If the port returns a **point-only** estimate: `range = {max(0, estimatedAge - half_width), estimatedAge + half_width}` where `half_width = Settings.age_range_half_width_years` (default 5); `estimatedAge` is returned as-is.
- Invariants on every `200`: `range.min >= 0` and `range.min <= estimatedAge <= range.max`.

**Rendering (frontend, FR-012a)**: range rendered as `"min–max años"` (e.g. `27–37 años`); point estimate as `"≈NN años"` (e.g. `≈32 años`); when `min == max` only the point estimate is rendered; disclaimer follows.

## Errors

All error bodies use the pinned shape `{"error": {"code": "...", "message": "..."}}` (spec 002).

| Status | Code | Condition | Body |
|--------|------|-----------|------|
| `401` | `unauthenticated` | no/invalid/expired/revoked session | `{"error":{"code":"unauthenticated","message":"Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."}}` |
| `400` | `invalid_image` | image undecodable/unsupported/oversized | `{"error":{"code":"invalid_image","message":"La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB."}}` |
| `400` | `no_face` | detector returns 0 faces | `{"error":{"code":"no_face","message":"No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar."}}` |
| `400` | `multiple_faces` | detector returns > 1 face | `{"error":{"code":"multiple_faces","message":"Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura."}}` |
| `400` | `insufficient_quality` | single face but score < threshold | `{"error":{"code":"insufficient_quality","message":"La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar."}}` |
| `500` | `internal_error` | detector/age_estimator port failure; unexpected error | `{"error":{"code":"internal_error","message":"Ocurrió un error inesperado. Inténtalo de nuevo."}}` |

**Status-code reservation**: `401` is reserved exclusively for `unauthenticated` (session-gating). `400` for actionable capture-quality codes. `500` for recoverable `internal_error` (FR-007). No age result is produced on any error path.

## Contract test assertions

1. **Happy path (range)**: with a valid session + a one-face fixture the mock age estimator reports as point estimate `32` with range `[27, 37]` → `200` with `estimatedAge == 32`, `range.min == 27`, `range.max == 37`, `min <= estimatedAge <= max`, `min >= 0`, and the exact PRD §8 disclaimer string.
2. **Happy path (point-only → derived range)**: a fixture the mock age estimator reports as point-only `40` (no range) → `200` with `estimatedAge == 40`, `range.min == 35`, `range.max == 45` (default half-width 5), invariants hold.
3. **Happy path (range → midpoint)**: a fixture the mock age estimator reports as range `[35, 45]` → `200` with `estimatedAge == 40` (midpoint), invariants hold.
4. **No session**: without a cookie / with an expired/revoked session → `401` with `code: "unauthenticated"`; no analysis performed.
5. **Invalid image**: undecodable/oversized image → `400` with `code: "invalid_image"`.
6. **No face**: fixture the mock detector reports 0 faces → `400` with `code: "no_face"`.
7. **Multiple faces**: fixture the mock detector reports 2 faces → `400` with `code: "multiple_faces"`.
8. **Insufficient quality**: fixture with score < threshold → `400` with `code: "insufficient_quality"`.
9. **Port error**: fixture triggering an age_estimator port exception → `500` with `code: "internal_error"`.
10. **Integer/range invariants**: every `200` response has `estimatedAge`, `range.min`, `range.max` as integers with `min >= 0` and `min <= estimatedAge <= max`.
11. **Error body shape**: every non-`200` response body matches `{"error": {"code": string, "message": string}}`.
12. **Determinism**: the mock age estimator returns a fixed result for the same fixture (SC-005); `model_version == "mock-age-estimator-v1"` (FR-017).
