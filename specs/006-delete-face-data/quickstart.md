# Quickstart: Face Data Deletion (Fase 6 partial)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

Runnable validation scenarios that prove the face-data deletion feature works
end-to-end. These are manual/integration checks complementing the automated
suite (tasks.md P5). All scenarios run inside the `docker compose` stack with no
GPU and no network beyond the local services.

## Prerequisites

- Docker + Docker Compose installed.
- Repo root has the `usuarios/` bind-mount (created automatically by the backend
  container on startup).
- The `docker compose` stack brings up backend (FastAPI :8000), frontend
  (Vite :5173), and PostgreSQL.

## Setup

```bash
# From repo root — bring up the full stack
docker compose up --build

# In another terminal: run migrations (if not auto-run on startup)
docker compose exec backend alembic upgrade head
```

The backend is at `http://localhost:8000`, the frontend at `http://localhost:5173`.

## Scenario 1 — Happy path: delete own face data (end-to-end via UI)

**Proves**: SC-001, SC-002, SC-003, FR-004/FR-005/FR-006/FR-010 (User Story 1).

1. Open `http://localhost:5173` → welcome page.
2. Go to `/onboarding`, complete onboarding (identifier + consent + capture).
   → redirected to `/dashboard`.
3. On `/dashboard`, press **"Eliminar mis datos"**.
   → confirmation dialog appears: "Esta acción eliminará tu perfil y plantilla
   facial de forma permanente. ¿Continuar?".
4. Press **Confirm**.
   → button disables, processing state shows.
   → on 200: session state clears, camera releases, browser navigates to `/`.
5. **Verify**:
   - Browser is at `/` (welcome page), not `/login`.
   - `docker compose exec db psql -U demo -d demo -c "SELECT * FROM users;"` →
     no row for the user.
   - `SELECT * FROM face_templates;` → no row.
   - `SELECT * FROM auth_sessions;` → no row.
   - `ls usuarios/` → the `<user-id>/` folder is gone.

**Expected outcome**: `200 {userId, status:"deleted"}`, all DB rows and the
filesystem folder removed, cookie cleared, redirect to `/`.

## Scenario 2 — Authorization gating (401 / 403 / 422)

**Proves**: SC-004, FR-001/FR-002/FR-003 (User Story 2).

Using `curl` against the backend (cookie jar via `-c`/`-b`):

```bash
# (a) No session → 401 unauthenticated
curl -i -X DELETE http://localhost:8000/api/users/00000000-0000-4000-8000-000000000001/face-data
# Expect: HTTP/1.1 401  {"error":{"code":"unauthenticated","message":"..."}}

# (b) Malformed UUID → 422 (before handler)
curl -i -b cookie.jar -X DELETE http://localhost:8000/api/users/not-a-uuid/face-data
# Expect: HTTP/1.1 422  (FastAPI validation error)

# (c) Mismatched userId → 403 forbidden
# After onboarding user A and logging in (cookie.jar holds A's session):
curl -i -b cookie.jar -X DELETE http://localhost:8000/api/users/<user-B-uuid>/face-data
# Expect: HTTP/1.1 403  {"error":{"code":"forbidden","message":"Solo puedes eliminar tus propios datos."}}
```

**Verify**: after each rejection, `SELECT * FROM users;` is unchanged (no rows
removed for A or B).

## Scenario 3 — Post-deletion "right to be forgotten" verification

**Proves**: SC-003, FR-009 (User Story 3).

1. Complete onboarding + login for `demo@example.com` (cookie in `cookie.jar`).
2. Delete: `curl -b cookie.jar -X DELETE .../api/users/<userId>/face-data` → 200.
3. **Verify invalidation**:
   ```bash
   # Old cookie invalid
   curl -i -b cookie.jar http://localhost:8000/api/auth/me
   # Expect: 401 unauthenticated

   # Cannot log in with the old identifier (no profile)
   curl -i -X POST http://localhost:8000/api/auth/face-login \
     -F "identifier=demo@example.com" -F "image=@fixture.jpg"
   # Expect: 401 auth_failed (indistinguishable from never-enrolled)
   ```
4. Navigate to `http://localhost:5173/dashboard` → `ProtectedRoute` redirects to
   `/login` (no valid session).

**Expected outcome**: the person is fully forgotten — old cookie invalid, login
fails, no DB rows, no filesystem folder.

## Scenario 4 — DB transaction failure → 500 + rollback

**Proves**: SC-005, FR-004/FR-008 (User Story 5 integration).

1. Onboard + login a user.
2. Simulate a DB failure during deletion (e.g. stop the PostgreSQL container
   mid-request, or use a test fixture that raises inside the UnitOfWork).
3. Call `DELETE /api/users/<userId>/face-data`.
   → `500 {"error":{"code":"internal_error","message":"..."}}`.
4. **Verify**: `SELECT * FROM users;` — the `User`, `FaceTemplate`, and
   `AuthSession` rows are **all still present** (rollback, no partial deletion).

## Scenario 5 — Best-effort filesystem failure → 200 + warning

**Proves**: SC-006, FR-005 (User Story 5 integration).

1. Onboard + login a user; note the `usuarios/<user-id>/` folder.
2. Make the folder undeletable (e.g. `chmod 555 usuarios/<user-id>/` on Linux,
   or a test fixture that makes `ImageStorage.delete` raise).
3. Call `DELETE /api/users/<userId>/face-data` with the session cookie.
   → `200 {"userId":"...","status":"deleted"}` + cookie cleared.
4. **Verify**: DB rows are gone (commit succeeded); the folder may remain
   (orphaned); a structured warning `deletion_fs_cleanup_warning` appears in the
   backend logs.

## Scenario 6 — Automated test suite (no GPU, no network)

**Proves**: SC-010/SC-011, FR-015 (User Story 5).

```bash
# Backend domain + contract + integration tests (no GPU/network needed)
docker compose exec backend pytest tests/unit/test_deletion_service.py \
                                      tests/contract/test_http_contracts.py \
                                      tests/integration/test_deletion_integration.py -v

# Frontend deletion UI tests
docker compose exec frontend npx vitest run DashboardDelete.test.tsx
```

**Expected outcome**: all tests green. A deliberate contract-violating change
to the deletion response shape, or a change allowing a mismatched-`userId`
deletion, causes at least one test to fail (SC-011).

## Cleanup

```bash
docker compose down -v   # remove containers + volumes (PostgreSQL data)
```
