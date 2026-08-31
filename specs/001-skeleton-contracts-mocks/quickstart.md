# Quickstart: Skeleton, Contracts, Ports & Mocks (Fase 1)

**Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

> Runnable validation scenarios that prove the Fase 1 skeleton works end-to-end. No real business logic is exercised — these validate the stack, navigation, contracts, domain, and persistence foundations.

## Prerequisites

- Docker + Docker Compose (container runtime). **No** host-native Python, Node, PostgreSQL, or ML models required.
- A browser (Chrome or Edge latest) for the frontend check.
- Git (clean checkout).

## Scenario 1 — Bring up the full stack (SC-001)

**Setup**: clean checkout, only Docker installed.

```bash
docker compose up --build
```

**Expected**: three services reach healthy/ready:
- `postgres` healthy (log: `database system is ready to accept connections`).
- `backend` logs `alembic upgrade head` → `Running upgrade  -> 0001_initial_schema` then `Uvicorn running on http://0.0.0.0:8000`.
- `frontend` logs Vite dev server on `http://localhost:5173`.

**Verify**:
```bash
curl -s http://localhost:8000/health        # {"status":"healthy"}
curl -s http://localhost:8000/readyz        # {"status":"ready","db":true}
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/   # 200
```

**Pass criterion**: all three return healthy/200 within ~30s of `compose up`.

## Scenario 2 — Frontend navigation & route protection (SC-002)

**Setup**: stack running (Scenario 1). Open `http://localhost:5173/` in a browser.

**Steps & expected**:
1. `/` renders the Welcome placeholder with nav links to Onboarding, Login.
2. Click "Onboarding" → URL becomes `/onboarding`, no full reload, placeholder renders.
3. Click "Login" → `/login` placeholder renders.
4. Type `http://localhost:5173/dashboard` directly → **redirected to `/login`** (no session placeholder set).

**Pass criterion**: all four routes render; `/dashboard` redirects unauthenticated visitors to `/login`.

## Scenario 3 — HTTP contract endpoints (SC-003)

**Setup**: backend running. All responses are deterministic mocks.

```bash
# Onboarding — 201 with enrolled
curl -s -X POST http://localhost:8000/api/onboarding \
  -F "identifier=demo@example.com" -F "consentAccepted=true" -F "image=@test.jpg"
# Expected: 201 {"userId":"<uuid>","identifier":"demo@example.com","status":"enrolled"}

# Face login — 200 authenticated (mock always succeeds with session placeholder)
curl -s -X POST http://localhost:8000/api/auth/face-login \
  -F "identifier=demo@example.com" -F "image=@test.jpg"
# Expected: 200 {"userId":"<uuid>","status":"authenticated"}

# Auth me — unauthenticated without session
curl -s http://localhost:8000/api/auth/me
# Expected: 401 {"detail":"unauthenticated"} (or similar non-revealing shape)

# Logout
curl -s -X POST http://localhost:8000/api/auth/logout
# Expected: 200 success

# Mood (protected — without session → 401)
curl -s -X POST http://localhost:8000/api/analysis/mood -F "image=@test.jpg"
# Expected: 401

# Age (protected — without session → 401)
curl -s -X POST http://localhost:8000/api/analysis/age -F "image=@test.jpg"
# Expected: 401

# Delete face data (protected — without session → 401)
curl -s -X DELETE http://localhost:8000/api/users/00000000-0000-4000-8000-000000000001/face-data
# Expected: 401
```

**Pass criterion**: every endpoint returns the documented status code and response shape. Protected endpoints reject without a session placeholder (FR-006). Login failure (if mocked to fail) is generic/non-revealing (FR-007).

## Scenario 4 — Contract & domain test suite, no GPU/network (SC-008)

**Setup**: repo checkout. Run inside the backend container (or host with Python if preferred).

```bash
docker compose exec backend pytest tests/ -v
```

**Expected**:
- `tests/contract/test_http_contracts.py` — 7 endpoints × shape + status assertions, all pass.
- `tests/domain/test_entities.py` — entity construction with UUID v4 ids, enum validation, all pass.
- `tests/domain/test_mock_adapters.py` — every port's mock returns deterministic constants; running twice yields byte-identical results (SC-005).
- `tests/integration/test_stack.py` — migrations create 4 tables (SC-006); filesystem adapter writes/reads `usuarios/<user-id>/pictures.jpg` (SC-007).

**Pass criterion**: full suite green in an environment with no GPU and no network.

```bash
# Frontend tests
docker compose exec frontend npm test
# Expected: router + ProtectedRoute tests pass
```

## Scenario 5 — Contract-violation detection (SC-009)

**Setup**: green suite (Scenario 4).

**Steps**:
1. Edit a stub endpoint to return a wrong field (e.g. `POST /api/onboarding` returns `status: "active"` instead of `"enrolled"`).
2. Re-run `pytest tests/contract/`.

**Expected**: at least one contract test fails (asserting `status == "enrolled"`).

**Pass criterion**: the violation is caught. Revert the change → suite green again.

## Scenario 6 — Determinism across repeated runs (SC-005)

**Setup**: green domain suite.

```bash
docker compose exec backend pytest tests/domain/ -v > run1.txt
docker compose exec backend pytest tests/domain/ -v > run2.txt
diff run1.txt run2.txt
```

**Expected**: `diff` produces no output — mock adapter outputs are byte-identical across runs.

## Scenario 7 — No real logic present (SC-010)

**Verify** (manual / static inspection):
- `backend/src/face_insight/domain/` has no imports from `adapters/`, `api/`, `sqlalchemy`, `yolo`, or any ML package (SC-004).
- No endpoint executes real onboarding/login/analysis/deletion — all return mock-adapter-driven or hardcoded responses.

**Pass criterion**: `grep -rE "import (yolo|torch|cv2|sqlalchemy)" backend/src/face_insight/domain/` returns nothing; endpoints are stubs.

## Teardown

```bash
docker compose down -v   # stops services and removes the PG volume
```
