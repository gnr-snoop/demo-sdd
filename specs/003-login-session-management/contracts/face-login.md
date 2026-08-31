# Contract: POST /api/auth/face-login

**Source**: PRD §8, FR-001..FR-010, FR-019..FR-021 | **Status**: real logic (spec 003; supersedes spec 001 stub)

Verifies a captured face 1:1 against the `FaceTemplate` associated with the provided identifier, and on success creates an `AuthSession` and sets a signed http-only cookie. Login is the session-creation endpoint and is **not** session-protected (FR-014).

## Request

`multipart/form-data`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `identifier` | string | yes | normalized (trim + lowercase) before lookup; case-insensitive match against the canonical form stored by spec 002 |
| `image` | file (JPEG) | yes | ≤ 2 MB (`IMAGE_MAX_BYTES`); decoded as JPEG; resized so long edge ≤ 640 px (`IMAGE_MAX_LONG_EDGE`) before detection and embedding (limits reused from spec 002) |

## Success — `200 OK`

```json
{
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "authenticated"
}
```

- `userId`: UUID v4 string (the verified `User.id`).
- `status`: `"authenticated"`.
- **Exactly these two fields.** `expiresAt` is NOT exposed to the frontend (FR-005); expiry is learned reactively via `401 unauthenticated` on the next protected call.

**Side effects on success:**
- Exactly one new `AuthSession` row created (`id`, `userId`, `createdAt`, `expiresAt = createdAt + SESSION_LIFETIME_SECONDS`, `revokedAt = null`) in PostgreSQL (FR-009/SC-002).
- Signed http-only cookie `fid_session` set on the response, carrying the signed `AuthSession.id`.
- No prior session is revoked (multiple concurrent sessions allowed — demo-first).

**Set-Cookie header:**
```
Set-Cookie: fid_session=<signed-session-id>; HttpOnly; SameSite=Lax; Path=/
```
(`Secure` added when `SESSION_COOKIE_SECURE=true`.)

## Errors

All errors use the shape `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}`.

| Status | Code | Condition | Message (actionable, non-revealing) |
|--------|------|-----------|--------------------------------------|
| 400 | `invalid_image` | image missing, unsupported format, undecodable, or exceeds `IMAGE_MAX_BYTES` | "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB." |
| 400 | `no_face` | detector returns `face_count == 0` | "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar." |
| 400 | `multiple_faces` | detector returns `face_count > 1` | "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura." |
| 400 | `insufficient_quality` | `face_count == 1` but `score < QUALITY_THRESHOLD` | "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar." |
| 401 | `auth_failed` | identifier has no registered `User`/`FaceTemplate` **OR** cosine similarity `< VERIFICATION_THRESHOLD` | "No pudimos verificar tu identidad. Inténtalo de nuevo." |
| 500 | `internal_error` | unexpected failure (embedder error, comparison dimension mismatch, DB unreachable at session creation) | "Ocurrió un error inesperado. Inténtalo de nuevo." |

**Non-revealing guarantee (FR-008/SC-003):** The `auth_failed` response for the nonexistent-identifier case and the below-threshold case are **byte-identical** (same status `401`, same code `auth_failed`, same message). The two identity-sensitive causes are indistinguishable. No `AuthSession` is created on any failure (FR-004/SC-004).

**Status-code reservation (FR-010):** `401` from this endpoint **always** means "we could not authenticate you" (`auth_failed`) and never leaks whether the identifier existed. `400` means the capture itself is unusable. A `401` never carries a capture code; a `400` never carries `auth_failed`.

**Note on status codes vs. onboarding (spec 002):** Onboarding maps capture errors to `422` (validation). Login maps the same capture codes to `400` (bad request) so that `401` stays exclusively auth. The body shape and machine-code strings are shared; only the status code differs by endpoint. This is a deliberate, pinned divergence (see plan `research.md` R-4).

## Evaluation order (pinned)

1. Decode + validate image (format/size/long-edge) → `invalid_image` (400)
2. Detect faces → `no_face` / `multiple_faces` / `insufficient_quality` (400)
3. Load `User` + `FaceTemplate` by normalized identifier → if not found, `auth_failed` (401)
4. Embed captured face → `internal_error` (500) on failure
5. Cosine similarity vs stored embedding → if `< threshold`, `auth_failed` (401, identical to step 3)
6. `>= threshold` → create `AuthSession`, set signed cookie, return `200`

Detection (step 2) precedes lookup (step 3), so capture-quality errors surface uniformly for all identifiers (existing or nonexistent). Steps 3 and 5 share the identical `auth_failed` response.

## Configuration (env-overridable via pydantic Settings)

| Env Var | Default | Purpose |
|---------|---------|---------|
| `VERIFICATION_THRESHOLD` | `0.5` | Min cosine similarity to accept 1:1 verification (FR-003) |
| `QUALITY_THRESHOLD` | `0.5` | Min detector score for a usable capture face (reused from spec 002) |
| `SESSION_LIFETIME_SECONDS` | `1800` | Session lifetime (30 min); expired = invalid (FR-007) |
| `SESSION_COOKIE_NAME` | `fid_session` | Session cookie name |
| `SESSION_COOKIE_SECURE` | `false` | Set cookie `Secure` flag (enable behind HTTPS) |
| `SESSION_SIGNING_KEY` | `demo-signing-key-change-me` | `itsdangerous` signing key for the session cookie |
| `IMAGE_MAX_BYTES` | `2000000` | Max image payload size (reused from spec 002) |
| `IMAGE_MAX_LONG_EDGE` | `640` | Max long edge after resize (reused from spec 002) |

## Contract test assertions

- Well-formed request (enrolled identifier + image whose mock embedding yields similarity `>= threshold`) → `200` with `userId` (UUID v4) and `status == "authenticated"`; response has exactly the `userId` and `status` fields (no `expiresAt`); `Set-Cookie` header present with `HttpOnly`.
- Successful login leaves exactly one new `AuthSession` row (`revokedAt = null`, `expiresAt` in the future) for that `userId`.
- Nonexistent identifier + valid image → `401` `{"error": {"code": "auth_failed", ...}}`; no `AuthSession` created.
- Enrolled identifier + image whose embedding yields similarity `< threshold` → `401` `auth_failed` with a response **byte-identical** to the nonexistent-identifier case (same status, same code, same message); no `AuthSession` created.
- Missing/oversized/undecodable image → `400` `invalid_image`.
- Image with no face → `400` `no_face`.
- Image with multiple faces → `400` `multiple_faces`.
- Image with one face, score < quality threshold → `400` `insufficient_quality`.
- Embedder failure → `500` `internal_error` (no session created).
- Comparison dimension mismatch → `500` `internal_error` (no session created).
- Identifier is case-insensitive: enrolled as `Demo@Example.com`, login with `demo@example.com` → `200`.
- A `401` from this endpoint never carries a capture code; a `400` never carries `auth_failed`.
- A deliberate contract-violating change to the success/error shape, or a change making the two identity-sensitive failures distinguishable, causes at least one contract test to fail (SC-011).
