# Contracts: Login & Session Management (Fase 3)

**Spec**: [spec.md](../spec.md) | **Status**: real logic (spec 003; supersedes spec 001 stubs for the auth endpoints)

This directory documents the HTTP contracts for the three auth endpoints filled with real logic in spec 003, building on the error-body shape pinned in spec 002 (`{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}`).

## Endpoints

| File | Endpoint | Purpose |
|------|----------|---------|
| [face-login.md](./face-login.md) | `POST /api/auth/face-login` | Verify a captured face 1:1 against the stored template and create a session |
| [auth-me.md](./auth-me.md) | `GET /api/auth/me` | Return the current session state (bootstrap for `ProtectedRoute`) |
| [logout.md](./logout.md) | `POST /api/auth/logout` | Revoke the session and clear the cookie (idempotent) |

## Shared conventions

- **Content-Type:** `application/json` for all responses (requests to `face-login` are `multipart/form-data`).
- **Error body:** `{"error": {"code": "<machine-code>", "message": "<actionable human message>"}}` — reused from spec 002.
- **Status-code reservation:** `401` is used **exclusively** for `auth_failed` (login identity failure) and `unauthenticated` (session-gating on protected endpoints). `400` is used **exclusively** for the capture-quality codes (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`). `500` for `internal_error`. This makes the capture-vs-auth distinction statically testable in contract tests.
- **Non-revealing guarantee:** The nonexistent-identifier and below-threshold login failures produce a **byte-identical** `401 auth_failed` response (same status, same code, same message).
- **Session cookie:** `fid_session` — http-only, `SameSite=Lax`, `Path=/`, signed with `itsdangerous.URLSafeTimedSerializer`; carries only the signed `AuthSession.id`. All session state (expiry, revocation) is server-side in PostgreSQL.

## Relationship to spec 001/002 contracts

- Spec 001 defined stub handlers for these three endpoints; spec 003 **supersedes** them with real logic. The spec 001 stub contract tests for `face-login`/`me`/`logout` are superseded by the contract tests described here.
- The `{"error": {"code", "message"}}` body shape and the capture machine codes (`no_face`, `multiple_faces`, `invalid_image`, `insufficient_quality`, `internal_error`) are reused from spec 002. The **status codes differ by endpoint**: onboarding (spec 002) maps capture errors to `422` (validation semantics); login (spec 003) maps them to `400` (bad-request semantics) so that `401` stays exclusively auth. This is a deliberate, pinned divergence documented in [face-login.md](./face-login.md) and the plan's `research.md` (R-4).
- `POST /api/analysis/mood`, `POST /api/analysis/age`, and `DELETE /api/users/{userId}/face-data` gain **real session-gating** in spec 003 (reject with `401 unauthenticated` without a valid session) but their business logic remains the spec 001 stubs; their full contracts are deferred to specs 004/005/006.

## Validation

- **Quickstart**: see [../quickstart.md](../quickstart.md) for runnable end-to-end validation scenarios (login, rejection, route protection, logout, expiry) and the automated test-suite commands.
- **Automated tests**: `backend/tests/contract/test_auth_contracts.py` (shapes + byte-identical `auth_failed`), `backend/tests/integration/test_login_session.py` (real auth endpoints + mock adapters + real PostgreSQL), `backend/tests/unit/test_{comparison,login_service,session,session_cookie,normalization}.py` (domain unit tests), `backend/tests/domain/test_domain_purity.py` (domain purity), `frontend/src/__tests__/{login,session}/` (frontend state machine + ProtectedRoute + logout button).
