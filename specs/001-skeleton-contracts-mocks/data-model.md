# Data Model: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md) | **Source of truth**: PRD §7, §9

> **Pinned decision**: All primary keys (`id`, `userId`) are **UUID v4 strings** stored as PostgreSQL `UUID` columns. Identity is domain-owned (`uuid.uuid4()` in entity factories; fixed constants in mock adapters/tests). The DB does not default-generate IDs.

## Entities

### User

The registered person.

| Field | Type | Null | Key | Notes |
|-------|------|------|-----|-------|
| `id` | UUID v4 | NO | **PK** | Domain-generated |
| `identifier` | VARCHAR(255) | NO | UNIQUE | Email or username; validated non-empty, valid format |
| `status` | VARCHAR(16) | NO | — | Enum: `enrolled`, `active`, `disabled` (default `enrolled`) |
| `created_at` | TIMESTAMPTZ | NO | — | Domain-injected `now` |
| `updated_at` | TIMESTAMPTZ | NO | — | Domain-injected `now` |

**Relationships**: has-at-most-one `FaceTemplate` (1:1); has-many `AuthSession` (1:N); has-many `AnalysisRequest` (1:N).

**Validation**: `identifier` non-empty, valid email/username format, unique. `status` ∈ {`enrolled`, `active`, `disabled`}.

### FaceTemplate

The comparable facial representation derived from onboarding.

| Field | Type | Null | Key | Notes |
|-------|------|------|-----|-------|
| `id` | UUID v4 | NO | **PK** | Domain-generated |
| `user_id` | UUID v4 | NO | **FK → User.id** | One template per user (UNIQUE constraint) |
| `embedding` | BYTEA / JSONB | NO | — | Embedding vector (or reference). Stored as JSONB array of floats in Fase 1 (mock). Not logged. |
| `model_version` | VARCHAR(64) | NO | — | Identifiable model version (reproducibility, PRD §11) |
| `created_at` | TIMESTAMPTZ | NO | — | Domain-injected `now` |
| `updated_at` | TIMESTAMPTZ | NO | — | Domain-injected `now` |

**Relationships**: belongs-to `User` (N:1). UNIQUE(`user_id`) — at most one template per user.

**Validation**: `embedding` non-null; `model_version` non-empty. Embedding never appears in logs (PRD §12).

### AuthSession

An authenticated session created after successful face verification.

| Field | Type | Null | Key | Notes |
|-------|------|------|-----|-------|
| `id` | UUID v4 | NO | **PK** | Domain-generated; the session token/cookie maps to this |
| `user_id` | UUID v4 | NO | **FK → User.id** | Owning user |
| `created_at` | TIMESTAMPTZ | NO | — | Domain-injected `now` |
| `expires_at` | TIMESTAMPTZ | NO | — | `created_at` + configured TTL |
| `revoked_at` | TIMESTAMPTZ | YES | — | Nullable; set on logout/invalidation |

**Relationships**: belongs-to `User` (N:1).

**Validation**: `expires_at` > `created_at`. A session is active iff `revoked_at IS NULL AND now < expires_at`. (Enforcement deferred to spec 003; schema established here.)

### AnalysisRequest

An audit record of an on-demand analysis (optional for MVP per PRD §7; schema established now to avoid a later migration).

| Field | Type | Null | Key | Notes |
|-------|------|------|-----|-------|
| `id` | UUID v4 | NO | **PK** | Domain-generated |
| `user_id` | UUID v4 | NO | **FK → User.id** | Requesting user |
| `type` | VARCHAR(8) | NO | — | Enum: `mood`, `age` |
| `model_version` | VARCHAR(64) | NO | — | Model that produced the result |
| `created_at` | TIMESTAMPTZ | NO | — | Domain-injected `now` |
| `status` | VARCHAR(16) | NO | — | Enum: `pending`, `completed`, `failed` (default `pending`) |

**Relationships**: belongs-to `User` (N:1).

**Validation**: `type` ∈ {`mood`, `age`}; `status` ∈ {`pending`, `completed`, `failed`}. **Does not store** the original image or full biometric result (PRD §7).

## Enumerations

| Enum | Values | Default |
|------|--------|---------|
| `UserStatus` | `enrolled`, `active`, `disabled` | `enrolled` |
| `AnalysisType` | `mood`, `age` | — |
| `AnalysisStatus` | `pending`, `completed`, `failed` | `pending` |

## Entity-Relationship Diagram

```text
┌──────────────┐ 1     1 ┌──────────────┐
│     User     │─────────│  FaceTemplate │
│  id (UUID)   │         │  id (UUID)    │
│  identifier  │         │  user_id (FK) │
│  status      │         │  embedding    │
│  created_at  │         │  model_version│
│  updated_at  │         │  created_at   │
└──────┬───────┘         │  updated_at   │
       │                 └───────────────┘
       │ 1
       │
       ├──────N─────────┌──────────────┐
       │                │  AuthSession │
       │                │  id (UUID)    │
       │                │  user_id (FK) │
       │                │  created_at   │
       │                │  expires_at   │
       │                │  revoked_at?  │
       │                └──────────────┘
       │
       └──────N─────────┌──────────────┐
                        │AnalysisRequest│
                        │  id (UUID)    │
                        │  user_id (FK) │
                        │  type         │
                        │  model_version│
                        │  created_at   │
                        │  status       │
                        └──────────────┘
```

## Ports (domain interfaces)

The domain declares these `typing.Protocol` interfaces. Mock adapters (Fase 1) and real adapters (Fase 5) implement them.

| Port | Operation(s) | Returns |
|------|-------------|---------|
| `Detector` | `detect(image: bytes) -> DetectionResult` | `BoundingBox`, `score`, `face_count` |
| `Embedder` | `embed(face: DetectedFace) -> Embedding` | fixed-dim float vector + `model_version` |
| `AgeEstimator` | `estimate_age(face: DetectedFace) -> AgeResult` | `estimated_age`, `range`, `model_version` |
| `MoodEstimator` | `estimate_mood(face: DetectedFace) -> MoodResult` | `label`, `confidence`, `model_version` |
| `SessionManager` | `create(user_id)`, `get(session_id)`, `revoke(session_id)`, `is_active(session_id)` | `AuthSession` / bool |
| `UserRepository` | `get(id)`, `get_by_identifier(identifier)`, `save(user)`, `delete(id)` | `User` / None |
| `FaceTemplateRepository` | `get_by_user(user_id)`, `save(template)`, `delete_by_user(user_id)` | `FaceTemplate` / None |
| `ImageStorage` | `store(user_id, image_bytes) -> path`, `read(user_id) -> bytes`, `delete(user_id)` | path string / bytes |

**Mock adapter constants (deterministic, SC-005)**:

| Mock | Fixed output |
|------|-------------|
| `MockDetector` | `DetectionResult(face_count=1, boxes=[BoundingBox(0,0,100,100)], score=0.99)` |
| `MockEmbedder` | 128-dim vector of `0.1` repeats; `model_version="mock-embed-v0"` |
| `MockAgeEstimator` | `estimated_age=32, range=(27,37), model_version="mock-age-v0"` |
| `MockMoodEstimator` | `label="neutral", confidence=0.74, model_version="mock-mood-v0"` |
| `MockUserRepository` | in-memory dict; returns `FIXED_USER_ID = UUID("00000000-0000-4000-8000-000000000001")` for new users |
| `MockImageStorage` | writes to a temp dir mirroring `usuarios/<user-id>/pictures.jpg` |

## Migrations

Single Alembic revision `0001_initial_schema`:

- Creates `users` table with `id UUID PK`, `identifier VARCHAR(255) UNIQUE NOT NULL`, `status VARCHAR(16) NOT NULL DEFAULT 'enrolled'`, `created_at`/`updated_at TIMESTAMPTZ NOT NULL`.
- Creates `face_templates` table with `id UUID PK`, `user_id UUID FK → users.id ON DELETE CASCADE`, `embedding JSONB NOT NULL`, `model_version VARCHAR(64) NOT NULL`, timestamps; `UNIQUE(user_id)`.
- Creates `auth_sessions` table with `id UUID PK`, `user_id UUID FK → users.id ON DELETE CASCADE`, `created_at`/`expires_at TIMESTAMPTZ NOT NULL`, `revoked_at TIMESTAMPTZ NULL`.
- Creates `analysis_requests` table with `id UUID PK`, `user_id UUID FK → users.id ON DELETE CASCADE`, `type VARCHAR(8) NOT NULL`, `model_version VARCHAR(64) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL`, `status VARCHAR(16) NOT NULL DEFAULT 'pending'`.
- Down revision: `None` (initial). Idempotent via Alembic `upgrade head` (SC-006).

## State Transitions

Established in schema only; enforcement deferred to later specs.

- `User.status`: `enrolled` → `active` (on first successful login, spec 003) → `disabled` (on face-data deletion, spec 006).
- `AnalysisRequest.status`: `pending` → `completed` | `failed` (spec 004).
- `AuthSession`: active → revoked (`revoked_at` set, spec 003) or expired (`now > expires_at`).
