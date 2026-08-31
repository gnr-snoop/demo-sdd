# Quickstart: Login & Session Management (Fase 3)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

Runnable validation scenarios that prove the login, session, route-protection, and logout flows work end-to-end. These are the commands a reviewer runs to validate this spec; they do not include full implementation code.

## Prerequisites

- Docker + Docker Compose installed.
- Specs 001 (skeleton/ports/mocks) and 002 (onboarding) implemented and green.
- The `demo-sdd` repo at the `003-login-session-management` branch.
- No GPU and no network required for the domain/contract suites (Constitution Quality Gate §7).

## Setup

```bash
# from repo root
git checkout 003-login-session-management
docker compose up --build -d          # backend + frontend + postgres + usuarios bind mount
docker compose exec backend alembic upgrade head   # migrations (auth_sessions table already from spec 001)
```

Environment defaults (override in `.env` or `docker-compose.yml`):

| Env Var | Default | |
|---------|---------|-|
| `VERIFICATION_THRESHOLD` | `0.5` | cosine similarity acceptance threshold |
| `SESSION_LIFETIME_SECONDS` | `1800` | 30 min session lifetime |
| `SESSION_SIGNING_KEY` | `demo-signing-key-change-me` | cookie signing key |
| `QUALITY_THRESHOLD` | `0.5` | capture quality threshold (from spec 002) |

## Scenario 1 — Successful face login (AC-004)

```bash
# 1. Onboard a user (spec 002) — seed a User + FaceTemplate
curl -s -X POST http://localhost:8000/api/onboarding \
  -F "identifier=demo@example.com" -F "consentAccepted=true" -F "image=@tests/fixtures/one_face.jpg"
# -> 201 {"userId":"<uuid>","identifier":"demo@example.com","status":"enrolled"}

# 2. Login with the same identifier + a fixture image whose mock embedding matches (similarity >= 0.5)
curl -s -i -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=demo@example.com" -F "image=@tests/fixtures/matching_face.jpg"
# Expected:
#   HTTP/1.1 200 OK
#   Set-Cookie: fid_session=<signed>; HttpOnly; SameSite=Lax; Path=/
#   {"userId":"<uuid>","status":"authenticated"}
#   (exactly two fields — no expiresAt)

# 3. Inspect the DB: exactly one new auth_sessions row with revoked_at = NULL and expires_at in the future
docker compose exec postgres psql -U demo -d demo -c \
  "SELECT id, user_id, revoked_at, expires_at > now() AS valid FROM auth_sessions;"
```

## Scenario 2 — Login rejected, non-revealing (AC-005)

```bash
# (a) Nonexistent identifier
curl -s -o resp_a.json -w "%{http_code}" -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=nope@example.com" -F "image=@tests/fixtures/one_face.jpg"
# Expected: 401  {"error":{"code":"auth_failed","message":"No pudimos verificar tu identidad. Inténtalo de nuevo."}}

# (b) Enrolled identifier + non-matching face (mock embedding yields similarity < 0.5)
curl -s -o resp_b.json -w "%{http_code}" -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=demo@example.com" -F "image=@tests/fixtures/non_matching_face.jpg"
# Expected: 401  identical to (a)

# Assert byte-identity of the two auth_failed responses:
diff resp_a.json resp_b.json   # -> no differences

# (c) Capture-quality failures return 400 with actionable codes (distinct from 401 auth_failed)
curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=demo@example.com" -F "image=@tests/fixtures/no_face.jpg"
# Expected: 400  {"error":{"code":"no_face",...}}
```

## Scenario 3 — Session validation & route protection (AC-006)

```bash
# Without a cookie, every protected endpoint returns 401 unauthenticated
curl -s -w "\n%{http_code}" http://localhost:8000/api/auth/me
# Expected: 401  {"error":{"code":"unauthenticated",...}}

curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/analysis/mood -F "image=@tests/fixtures/one_face.jpg"
# Expected: 401 unauthenticated

# With a valid cookie (from Scenario 1), protected endpoints are accepted
curl -s -b "fid_session=<signed-from-scenario-1>" -w "\n%{http_code}" http://localhost:8000/api/auth/me
# Expected: 200  {"authenticated":true,"userId":"<uuid>"}

# Frontend: navigate to http://localhost:5173/dashboard with no session -> redirected to /login
```

## Scenario 4 — Logout & session invalidation (AC-009)

```bash
# Login (get cookie), then logout
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=demo@example.com" -F "image=@tests/fixtures/matching_face.jpg"
curl -s -b cookies.txt -c cookies.txt -w "\n%{http_code}" -X POST http://localhost:8000/api/auth/logout
# Expected: 200  {"status":"ok"}   (Set-Cookie clears fid_session)

# The revoked session can no longer access protected endpoints
curl -s -b cookies.txt -w "\n%{http_code}" http://localhost:8000/api/auth/me
# Expected: 401 unauthenticated

# Logout is idempotent (no cookie / already-revoked -> still 200)
curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/auth/logout
# Expected: 200  {"status":"ok"}
```

## Scenario 5 — Expired session is rejected

```bash
# Log in, then artificially expire the session in the DB
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=demo@example.com" -F "image=@tests/fixtures/matching_face.jpg"
docker compose exec postgres psql -U demo -d demo -c \
  "UPDATE auth_sessions SET expires_at = now() - interval '1 minute' WHERE revoked_at IS NULL;"

curl -s -b cookies.txt -w "\n%{http_code}" http://localhost:8000/api/auth/me
# Expected: 401 unauthenticated
```

## Automated test suites (no GPU, no network)

```bash
# Domain unit tests (cosine similarity, threshold, session validity, normalization, non-revealing mapping)
docker compose exec backend pytest tests/unit/test_comparison.py tests/unit/test_login_service.py tests/unit/test_session.py -v

# Contract tests (request/response shapes + status codes for the 3 auth endpoints + identical auth_failed body)
docker compose exec backend pytest tests/contract/test_auth_contracts.py -v

# Domain purity (login/session domain imports no ML/infra/SQLAlchemy/FastAPI/itsdangerous)
docker compose exec backend pytest tests/domain/test_domain_purity.py -v

# Integration tests (real auth endpoints + mock detector/embedder + real PostgreSQL)
docker compose exec backend pytest tests/integration/test_login_session.py -v

# Frontend tests (login state machine, ProtectedRoute gating, logout button — mocked MediaDevices + fetch)
docker compose exec frontend npx vitest run src/__tests__/login src/__tests__/session
```

## Expected outcomes

- All unit, contract, and integration suites pass with no GPU and no network (SC-010).
- The nonexistent-identifier and below-threshold responses are byte-identical (SC-003).
- No `AuthSession` is created for any failure case (SC-004).
- 100% of protected endpoints reject without a valid session and accept with one (SC-005).
- After logout, the session is revoked and cannot re-access any protected endpoint (SC-007).
- The login/session domain code has zero imports of concrete ML models or infrastructure adapters (SC-009).
- No image, embedding, or biometric response appears in application logs (SC-013).
- A deliberate contract-violating change to any auth endpoint response, or a change making the two identity-sensitive failures distinguishable, causes at least one contract test to fail (SC-011).
