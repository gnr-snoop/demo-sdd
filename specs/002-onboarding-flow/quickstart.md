# Quickstart: Onboarding Flow (Fase 2)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-08-31

Runnable validation scenarios that prove the onboarding feature works end-to-end. All scenarios run without GPU or network (mock adapters only).

---

## Prerequisites

- Docker + Docker Compose (Constitution Principle IV).
- The spec 001 skeleton is implemented: `docker-compose.yml`, `backend/`, `frontend/`, PostgreSQL, `usuarios/` bind mount.
- Pillow installed in the backend image (added by this spec's `pyproject.toml`).

## Setup

```bash
# From repo root
docker compose up --build -d          # backend + frontend + postgres
docker compose exec backend alembic upgrade head   # migrations (0001 already present)
```

The `usuarios/` directory is bind-mounted; images written inside the container appear at `usuarios/<user-id>/pictures.jpg` on the host.

## Scenario 1 — Successful onboarding (happy path, AC-001)

**Command:**
```bash
# Valid identifier, consent accepted, a JPEG fixture with one face
curl -s -X POST http://localhost:8000/api/onboarding \
  -F "identifier=demo@example.com" \
  -F "consentAccepted=true" \
  -F "image=@tests/fixtures/one_face.jpg"
```

**Expected:**
- HTTP `201 Created`.
- Body: `{"userId": "<uuid-v4>", "identifier": "demo@example.com", "status": "enrolled"}`.
- DB: exactly one `User` (status `enrolled`) and one `FaceTemplate` (modelVersion `mock-embedder-v1`).
- FS: `usuarios/<userId>/pictures.jpg` exists and is a readable JPEG ≤ 640px long edge.

**Verify persistence:**
```bash
docker compose exec postgres psql -U faceinsight -d faceinsight \
  -c "SELECT id, identifier, status FROM users;"
docker compose exec postgres psql -U faceinsight -d faceinsight \
  -c "SELECT user_id, model_version FROM face_templates;"
ls usuarios/*/pictures.jpg
```

## Scenario 2 — Rejected: no face (AC-002)

**Command:**
```bash
# Image bytes starting with the NOFACE marker (ScriptableMockDetector convention)
curl -s -X POST http://localhost:8000/api/onboarding \
  -F "identifier=noface@example.com" \
  -F "consentAccepted=true" \
  -F "image=@tests/fixtures/no_face.jpg"
```

**Expected:**
- HTTP `422`.
- Body: `{"error": {"code": "no_face", "message": "..."}}` (actionable message).
- DB: zero `User`, zero `FaceTemplate` for this identifier.

## Scenario 3 — Rejected: multiple faces (AC-003)

**Command:**
```bash
curl -s -X POST http://localhost:8000/api/onboarding \
  -F "identifier=multi@example.com" \
  -F "consentAccepted=true" \
  -F "image=@tests/fixtures/multi_face.jpg"
```

**Expected:**
- HTTP `422`, `{"error": {"code": "multiple_faces", ...}}`.
- DB: zero `User`, zero `FaceTemplate`.

## Scenario 4 — Rejected: invalid identifier / duplicate / consent

**Commands:**
```bash
# Empty identifier
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier= " -F "consentAccepted=true" -F "image=@tests/fixtures/one_face.jpg"
# → 422 {"error": {"code": "identifier_invalid", ...}}

# Malformed identifier
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier=not valid!" -F "consentAccepted=true" -F "image=@tests/fixtures/one_face.jpg"
# → 422 {"error": {"code": "identifier_invalid", ...}}

# Duplicate (case-insensitive) — after Scenario 1 succeeded with demo@example.com
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier=DEMO@Example.COM" -F "consentAccepted=true" -F "image=@tests/fixtures/one_face.jpg"
# → 409 {"error": {"code": "identifier_taken", ...}}

# Consent not accepted
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier=new@example.com" -F "consentAccepted=false" -F "image=@tests/fixtures/one_face.jpg"
# → 422 {"error": {"code": "consent_required", ...}}
```

**Expected:** Each returns the indicated status + error code. No image processing occurs (detector/embedder not invoked). DB unchanged.

## Scenario 5 — Rejected: invalid image / oversized / insufficient quality

**Commands:**
```bash
# Undecodable payload
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier=img@example.com" -F "consentAccepted=true" -F "image=@tests/fixtures/not_an_image.txt"
# → 422 {"error": {"code": "invalid_image", ...}}

# Oversized (> 2 MB)
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier=big@example.com" -F "consentAccepted=true" -F "image=@tests/fixtures/oversized.jpg"
# → 422 {"error": {"code": "invalid_image", ...}}

# Insufficient quality (score < 0.5)
curl -s -X POST http://localhost:8000/api/onboarding -F "identifier=lowq@example.com" -F "consentAccepted=true" -F "image=@tests/fixtures/low_quality.jpg"
# → 422 {"error": {"code": "insufficient_quality", ...}}
```

## Scenario 6 — Automated test suite (no GPU, no network)

**Command:**
```bash
# Backend unit + contract + integration
docker compose exec backend pytest tests/unit tests/contract tests/integration -v

# Frontend state-machine tests (mocked MediaDevices)
docker compose exec frontend npx vitest run
```

**Expected:**
- All unit tests for identifier validation, consent validation, face-count rules, image limits, and the onboarding service pass.
- All contract tests for `POST /api/onboarding` (success + every error code + shape assertions) pass.
- All integration tests (real DB + real FS + mock detector/embedder) for the happy path and each rejection case pass.
- Frontend tests cover the 7 PRD §6.2 states with a mocked camera.
- A deliberate contract-violating change (e.g., returning `status: "active"`) causes a contract test to fail (SC-009).

## Scenario 7 — Frontend walk-through (manual, < 2 minutes, SC-001)

1. Open `http://localhost:5173/onboarding` (or the configured frontend port).
2. Enter a valid identifier (e.g., `test@example.com`).
3. Check the consent checkbox.
4. Click "Solicitar cámara" → grant permission → preview appears (`ready_to_capture`).
5. Click "Capturar" → `processing` → success (`éxito`) with a link to login.
6. Verify `usuarios/<userId>/pictures.jpg` exists on the host.

**Expected:** The page transitions through `initial → requesting_permission → ready_to_capture → processing → success`. The capture button is disabled during `processing`. All controls are keyboard-accessible.
