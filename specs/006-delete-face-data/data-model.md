# Data Model: Face Data Deletion (Fase 6 partial)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

This spec introduces **no new persistent entities**. It hard-deletes existing
entities from specs 002/003 and exercises existing port capabilities. The only
new construct is a transient view model (the deletion response) and a new
transactional UnitOfWork method.

## Entities (existing — hard-deleted in this spec)

### User (from spec 002)

The registered person. **Hard-deleted** in this spec.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID v4 (PK) | Path parameter `userId`; matched against `AuthSession.user_id` for authz |
| `identifier` | str (normalized, unique) | — |
| `status` | `UserStatus` (`enrolled`) | Not changed to `disabled` — the row is **removed** |
| `created_at` | datetime | — |
| `updated_at` | datetime | — |

**Deletion behavior**: `DELETE FROM users WHERE id = :user_id` inside the
deletion transaction (after dependents). No soft-delete flag is introduced.

### FaceTemplate (from spec 002)

The stored facial embedding. **Deleted** (all rows for the `user_id`) in the
same transaction, before the `User`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID v4 (PK) | — |
| `user_id` | UUID v4 (FK → users.id) | Deletion filter |
| `embedding` | list[float] | Not logged (FR-016) |
| `model_version` | str | — |
| `created_at` | datetime | — |
| `updated_at` | datetime | — |

**Deletion behavior**: `DELETE FROM face_templates WHERE user_id = :user_id`
(first in the transaction — dependent of `User`).

### AuthSession (from spec 003)

The user's authenticated sessions. **All rows for the `user_id` deleted** in the
same transaction, invalidating every session (not just the current one).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID v4 (PK) | Cookie references this; cleared on the 200 response |
| `user_id` | UUID v4 (FK → users.id) | Deletion filter |
| `created_at` | datetime | — |
| `expires_at` | datetime | — |
| `revoked_at` | datetime \| NULL | — |

**Deletion behavior**: `DELETE FROM auth_sessions WHERE user_id = :user_id`
(second in the transaction — dependent of `User`). No per-session revoke; the
rows are physically removed.

### Filesystem Image Folder (from spec 002, Principle V)

Not a DB entity. The `usuarios/<user-id>/` directory and its `pictures.jpg`.

**Deletion behavior**: `ImageStorage.delete(user_id)` → `shutil.rmtree` of the
user dir, **best-effort after DB commit**. No-op if the dir is absent. Failure
does not fail the endpoint (200 + warning log).

## New Constructs

### DeletionResult (transient view model — not persisted)

The `200` response body. Not stored; constructed by the route handler.

```json
{
  "userId": "<UUID v4 echoed from path>",
  "status": "deleted"
}
```

Mapped by the existing `DeleteFaceDataResponse` Pydantic schema (`api/schemas.py`).

### SqlAlchemyUnitOfWork.delete_user_face_data (new transactional method)

Not an entity — a new method on the existing `SqlAlchemyUnitOfWork` adapter
(`adapters/db/repositories.py`) that performs the atomic deletion. See
`research.md` R-2.

**Signature**: `async def delete_user_face_data(self, user_id: UUID) -> None`

**Transaction order** (single `AsyncSession`):
1. `DELETE face_templates WHERE user_id = :user_id`
2. `DELETE auth_sessions WHERE user_id = :user_id`
3. `DELETE users WHERE id = :user_id`
4. `COMMIT` (rollback on any exception → re-raise → `500 internal_error`)

## Relationships

```text
User (1) ──< (N) FaceTemplate     ← deleted first (dependent)
User (1) ──< (N) AuthSession      ← deleted second (dependent)
User        ← deleted last (parent), then COMMIT
Filesystem: usuarios/<user-id>/   ← best-effort, AFTER commit
```

Foreign-key dependency order is respected: dependents before parent.

## Validation Rules

- **Path parameter**: `userId` must be a valid UUID v4 → FastAPI path validation
  → `422` before the handler runs (FR-003).
- **Session**: a valid (present, non-expired, non-revoked) session is required →
  `401 unauthenticated` (FR-001).
- **Authorization**: `session.user_id == path userId` → `403 forbidden` on
  mismatch (FR-002).
- **Existence**: `User` for path `userId` must exist → `404 not_found` (FR-007,
  defensive guard).

## State Transitions

There is no entity state machine in this spec — deletion is a terminal
transition to *absence*:

```text
User.status = enrolled  ──DELETE──▶  (row removed; no "deleted" state)
AuthSession (valid)      ──DELETE──▶  (rows removed; cookie cleared)
FaceTemplate             ──DELETE──▶  (row removed)
usuarios/<id>/           ──DELETE──▶  (dir removed, best-effort)
```

Post-deletion, the person is fully forgotten:
- `GET /api/auth/me` with old cookie → `401 unauthenticated` (session gone).
- `POST /api/auth/face-login` with old identifier → `401 auth_failed`
  (no `User`/`FaceTemplate`; indistinguishable from never-enrolled per spec 003).
