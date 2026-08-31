# Data Model: Onboarding Flow (Fase 2)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

This spec does not introduce new entities — it implements the real persistence behavior for the `User` and `FaceTemplate` entities established in spec 001. The data model below documents the fields, validation rules, relationships, and state transitions as they apply to onboarding, plus the error/result value objects introduced by this spec.

---

## Entities (from spec 001, behavior implemented in spec 002)

### User

The registered person, created by onboarding.

| Field | Type | Constraints | Onboarding Behavior |
|-------|------|-------------|---------------------|
| `id` | UUID v4 | PK, domain-owned (`uuid.uuid4()` in `create_user`) | Generated on successful onboarding |
| `identifier` | string (≤ 255) | `UNIQUE`, non-null, **normalized** (trim + lowercase), valid email-or-username format | Normalized before storage; uniqueness enforced by DB constraint (case-insensitive) |
| `status` | enum `UserStatus` | non-null, default `enrolled` | Set to `enrolled` on creation (pinned decision) |
| `created_at` | timestamptz | non-null | Set on creation (injectable `now` for tests) |
| `updated_at` | timestamptz | non-null | Set on creation |

**Validation rules (FR-002, R-1):**
- Non-empty after trim.
- Matches email pattern `^[^@\s]+@[^@\s]+\.[^@\s]+$` **OR** username pattern `^[a-zA-Z0-9._-]{3,32}$`.
- Normalized value (`strip().lower()`) not already present in `users` — enforced by `UNIQUE(identifier)` constraint; `IntegrityError` → `identifier_taken`.

**State transitions:**
- Onboarding creates `User` with `status = enrolled`. No transition in this spec.
- Future: `enrolled → active` (after first login, spec 003), `active → disabled` (deletion, spec 006). Out of scope here.

### FaceTemplate

The comparable facial representation, created atomically with the `User`.

| Field | Type | Constraints | Onboarding Behavior |
|-------|------|-------------|---------------------|
| `id` | UUID v4 | PK, domain-owned | Generated on successful onboarding |
| `user_id` | UUID v4 | FK → `users.id` `ON DELETE CASCADE`, `UNIQUE` (1:1) | Set to the created `User.id` |
| `embedding` | list[float] (JSONB) | non-empty, 128-dim for mock | From `Embedder.embed()` result vector |
| `model_version` | string (≤ 64) | non-null | `"mock-embedder-v1"` (from `Embedding.model_version`, R-8) |
| `created_at` | timestamptz | non-null | Set on creation |
| `updated_at` | timestamptz | non-null | Set on creation |

**Validation rules:**
- `embedding` must be non-empty (entity `__post_init__`).
- `model_version` must be non-empty (entity `__post_init__`); always `"mock-embedder-v1"` for the mock embedder in this spec.

**Relationships:**
- `User` 1 — 1 `FaceTemplate` (after onboarding). A `User` has at most one `FaceTemplate` (`UNIQUE(user_id)`).
- Created in the **same DB transaction** as the `User` (FR-008, all-or-nothing).

### Captured Image (filesystem artifact — not a domain entity)

| Attribute | Value |
|-----------|-------|
| Path | `usuarios/<user-id>/pictures.jpg` |
| Format | JPEG |
| Max size | 2 MB (`Settings.image_max_bytes`) |
| Max long edge | 640 px (`Settings.image_max_long_edge`) — resized before storage |
| Lifecycle | Written before DB commit; best-effort cleanup on DB failure (R-5) |

---

## Value Objects / Result Types (from spec 001, used by onboarding)

### DetectionResult
`face_count: int`, `boxes: list[BoundingBox]`, `score: float`. The detector port returns this; the onboarding service applies the rules: `face_count == 0 → no_face`, `face_count > 1 → multiple_faces`, `face_count == 1 and score < quality_threshold → insufficient_quality`.

### Embedding
`vector: list[float]`, `model_version: str`. The embedder port returns this; `model_version` flows into `FaceTemplate.model_version`.

---

## New Value Objects (spec 002)

### Error response (API layer, R-7)

```
ErrorResponse { error: ErrorBody }
ErrorBody { code: str, message: str }
```

Stable machine codes: `identifier_invalid`, `identifier_taken`, `consent_required`, `invalid_image`, `no_face`, `multiple_faces`, `insufficient_quality`, `internal_error`.

### Onboarding domain exceptions (R-7)

Typed exceptions raised by `OnboardingService`, mapped by the route handler to `ErrorResponse`:

| Exception | HTTP Status | Machine Code |
|-----------|-------------|-------------|
| `IdentifierInvalid` | 422 | `identifier_invalid` |
| `IdentifierTaken` | 409 | `identifier_taken` |
| `ConsentRequired` | 422 | `consent_required` |
| `InvalidImage` | 422 | `invalid_image` |
| `NoFace` | 422 | `no_face` |
| `MultipleFaces` | 422 | `multiple_faces` |
| `InsufficientQuality` | 422 | `insufficient_quality` |
| `OnboardingInternalError` | 500 | `internal_error` |

---

## Ports (from spec 001, shape changes in spec 002)

| Port | Methods | Change in spec 002 |
|------|---------|---------------------|
| `Detector` | `detect(image: bytes) -> DetectionResult` | Unchanged (sync) |
| `Embedder` | `embed(face_image: bytes) -> Embedding` | Unchanged (sync) |
| `UserRepository` | `get`, `get_by_identifier`, `save`, `delete` | **Made async** (`async def`) (R-2) |
| `FaceTemplateRepository` | `get_by_user`, `save`, `delete_by_user` | **Made async** (`async def`) (R-2) |
| `ImageStorage` | `store`, `read`, `delete` | Unchanged (sync; FS I/O is fast) |

---

## Schema / Migrations

**No schema change required.** The existing `0001_initial_schema` migration already defines:
- `users` with `UNIQUE(identifier)` — enforces case-insensitive uniqueness on the normalized value (R-4).
- `face_templates` with `UNIQUE(user_id)` and `FK → users.id ON DELETE CASCADE`.

A `0002_onboarding_normalization.py` migration is **not needed** (documented in research R-4). If defense-in-depth DB-level case-insensitivity is later desired, a functional index `CREATE UNIQUE INDEX ... ON users (lower(identifier))` or a `CITEXT` column would be the path — explicitly deferred (Principle I).

---

## Atomicity / Unit of Work (FR-008, R-5)

```
OnboardingService.onboard(identifier, consent, image_bytes):
  1. validate identifier (format + normalize)     → IdentifierInvalid
  2. validate consent (exactly true)              → ConsentRequired
  3. decode + enforce limits + resize image        → InvalidImage
  4. detect faces                                 → NoFace / MultipleFaces
  5. quality check (score >= threshold)           → InsufficientQuality
  6. embed face                                   → OnboardingInternalError on failure
  7. write image to filesystem                    → OnboardingInternalError on failure
  8. BEGIN DB TRANSACTION
       insert User (status=enrolled, normalized identifier)
       insert FaceTemplate (embedding, model_version)
     COMMIT                                       → IdentifierTaken on unique violation
  9. on DB failure: best-effort image_storage.delete(user_id)
  10. return (userId, identifier, status)
```

Steps 1–6 are pre-commit (no persistence). Step 7 (FS) is pre-DB-commit. Step 8 is the atomic DB unit. If 8 fails, step 9 cleans up the FS orphan. No partial `User`/`FaceTemplate` is ever committed.
