# HTTP Contracts: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Source of truth**: PRD §8 | **Spec**: [spec.md](../spec.md)

> All seven endpoints are **stubs** in Fase 1: they return deterministic mock responses (or a clear not-implemented indication) and do **not** execute real onboarding, login, analysis, or deletion logic (SC-010). Protected endpoints reject requests lacking a session placeholder (FR-006). Every endpoint has a contract test asserting request/response shape and status code (Quality Gate §5).

## Conventions

- **Primary keys / `userId`**: UUID v4 strings (pinned decision). The `DELETE /api/users/{userId}/face-data` path parameter is a UUID string. Mocks return fixed UUID constants in tests.
- **Image uploads**: `multipart/form-data` with an `image` field. Limits: JPEG, ≤ 2 MB, ≤ 640px long edge (Constitution OQ-8; enforced as config, validation deferred to spec 002).
- **Session placeholder**: a header/cookie marker (`X-Session-Id` or cookie) checked by a FastAPI dependency. In Fase 1 this is a placeholder — real session enforcement is deferred to spec 003.
- **Errors**: validation errors return `422` with a documented shape; protected-endpoint violations return `401`; login failure returns `401` with a **generic, non-revealing** message (FR-007/FR-018).
- **Mock determinism**: all mock responses are hardcoded constants (SC-005).

## Endpoints

| Method | Path | Auth | Success | Contract |
|--------|------|------|---------|----------|
| POST | `/api/onboarding` | — | 201 | [onboarding.md](./onboarding.md) |
| POST | `/api/auth/face-login` | — | 200 / 401 | [face-login.md](./face-login.md) |
| GET | `/api/auth/me` | session | 200 / 401 | [auth-me.md](./auth-me.md) |
| POST | `/api/auth/logout` | session | 200 | [logout.md](./logout.md) |
| POST | `/api/analysis/mood` | session | 200 | [analysis-mood.md](./analysis-mood.md) |
| POST | `/api/analysis/age` | session | 200 | [analysis-age.md](./analysis-age.md) |
| DELETE | `/api/users/{userId}/face-data` | session | 200 | [delete-face-data.md](./delete-face-data.md) |

## Infrastructure endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness: `{"status":"healthy"}` |
| GET | `/readyz` | Readiness: `{"status":"ready","db":true}` (503 if DB down) |
