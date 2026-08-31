# Contract: POST /api/onboarding

**Source**: PRD §8, FR-001..FR-006, FR-015, FR-016 | **Status**: real logic (spec 002; supersedes spec 001 stub)

Registers a person and processes their face. Validates the identifier and consent, decodes and normalizes the image, detects exactly one usable face, generates a facial embedding, and atomically persists a `User` (status `enrolled`) + `FaceTemplate`.

## Request

`multipart/form-data`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `identifier` | string | yes | non-empty after trim; valid email (`^[^@\s]+@[^@\s]+\.[^@\s]+$`) **or** username (`^[a-zA-Z0-9._-]{3,32}$`); not already registered (case-insensitive on trim+lowercase) |
| `consentAccepted` | boolean | yes | must be exactly `true` (non-boolean truthy values rejected) |
| `image` | file (JPEG) | yes | ≤ 2 MB (`IMAGE_MAX_BYTES`); decoded as JPEG; resized so long edge ≤ 640 px (`IMAGE_MAX_LONG_EDGE`) before detection and storage |

## Success — `201 Created`

```json
{
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "identifier": "demo@example.com",
  "status": "enrolled"
}
```

- `userId`: UUID v4 string (domain-generated).
- `identifier`: the **normalized** identifier (trim + lowercase) that was stored.
- `status`: `"enrolled"` (matches `User.status`).

**Side effects on success:**
- Exactly one `User` (status `enrolled`) and one associated `FaceTemplate` (`modelVersion = "mock-embedder-v1"`) committed atomically.
- Image stored at `usuarios/<userId>/pictures.jpg` (resized, JPEG).

## Errors

All errors use the shape `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}`.

| Status | Code | Condition | Message (actionable, non-revealing) |
|--------|------|-----------|--------------------------------------|
| 422 | `identifier_invalid` | identifier empty/whitespace or malformed (neither valid email nor username) | "El identificador no es válido. Usa un email bien formado o un nombre de usuario (3–32 caracteres, letras, números, '.', '_', '-')." |
| 409 | `identifier_taken` | normalized identifier already registered | "Ese identificador ya está registrado. Prueba con otro o inicia sesión si es tuyo." |
| 422 | `consent_required` | `consentAccepted` missing, `false`, or non-boolean | "Debes aceptar el consentimiento para el procesamiento facial antes de continuar." |
| 422 | `invalid_image` | image missing, unsupported format, undecodable, or exceeds `IMAGE_MAX_BYTES` | "La imagen no es válida o es demasiado grande. Usa una imagen JPEG de menos de 2 MB." |
| 422 | `no_face` | detector returns `face_count == 0` | "No se detectó ningún rostro. Asegúrate de estar frente a la cámara con buena iluminación y vuelve a capturar." |
| 422 | `multiple_faces` | detector returns `face_count > 1` | "Se detectó más de un rostro. Asegúrate de que solo una persona aparezca en la captura." |
| 422 | `insufficient_quality` | `face_count == 1` but `score < QUALITY_THRESHOLD` (default 0.5) | "La calidad de la captura es insuficiente. Mejora la iluminación, acércate a la cámara y vuelve a capturar." |
| 500 | `internal_error` | unexpected failure (embedder error, DB unreachable, FS write failure) | "Ocurrió un error inesperado. Inténtalo de nuevo." |

**Non-revealing guarantee (FR-016):** Error responses contain no embeddings, no stack traces, no internal details. The `identifier_taken` case reveals only that the identifier is registered (an onboarding-UX requirement), not any stored biometric data. The `internal_error` case is uniform regardless of root cause.

**All-or-nothing guarantee (FR-008):** On any error after step 1 (identifier format), no `User` and no `FaceTemplate` are persisted. On `internal_error` after the filesystem write, best-effort cleanup removes the orphaned image.

## Configuration (env-overridable via pydantic Settings)

| Env Var | Default | Purpose |
|---------|---------|---------|
| `IMAGE_MAX_BYTES` | `2000000` | Max image payload size |
| `IMAGE_MAX_LONG_EDGE` | `640` | Max long edge after resize |
| `IMAGE_FORMAT` | `JPEG` | Accepted image format |
| `QUALITY_THRESHOLD` | `0.5` | Min detector score for a usable face |
| `EMBEDDING_MODEL_VERSION` | `mock-embedder-v1` | `FaceTemplate.modelVersion` for the mock embedder |

## Contract test assertions

- Well-formed request (valid identifier, `consentAccepted=true`, valid JPEG with one face) → `201` with `userId` (UUID v4), `identifier` (normalized), `status == "enrolled"`.
- Empty/whitespace identifier → `422` `{"error": {"code": "identifier_invalid", ...}}`.
- Malformed identifier → `422` `identifier_invalid`.
- Already-registered identifier (case-insensitive) → `409` `identifier_taken`.
- `consentAccepted=false` → `422` `consent_required`.
- `consentAccepted="true"` (string) → `422` `consent_required`.
- Missing image → `422` `invalid_image`.
- Oversized image → `422` `invalid_image`.
- Undecodable/non-JPEG image → `422` `invalid_image`.
- Image with no face → `422` `no_face`.
- Image with multiple faces → `422` `multiple_faces`.
- Image with one face, score < threshold → `422` `insufficient_quality`.
- Embedder failure → `500` `internal_error` (no partial persistence).
- Successful onboarding leaves exactly one `User` + one `FaceTemplate` in the DB and one image at `usuarios/<userId>/pictures.jpg`.
- A deliberate contract-violating change to the success or error shape causes at least one contract test to fail (SC-009).
