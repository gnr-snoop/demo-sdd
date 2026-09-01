# Quickstart: Age Estimation (Fase 4 — age)

**Spec**: [spec.md](./spec.md) | **Branch**: `005-age-analysis` | **Date**: 2026-08-31

> **⏳ PENDING — implementation is deferred for a live demo.** The validation scenarios below describe what the implementation-ready `tasks.md` will deliver. Once implemented, these commands prove the age feature works end-to-end.

Runnable validation scenarios that prove the age estimation feature works end-to-end. The domain portions run without GPU, network, or real ML models (Constitution Quality Gate §7).

## Prerequisites

- Docker + Docker Compose (Principle IV).
- A seeded user: complete onboarding (spec 002) and login (spec 003) so a valid session exists. The integration tests do this programmatically.
- Browser with a secure context (`localhost` or HTTPS) for camera access (frontend scenarios).

## Setup

```bash
# From the repo root — bring up the full stack (backend, frontend, PostgreSQL).
docker compose up --build

# Backend API: http://localhost:8000  (OpenAPI docs: /docs)
# Frontend:     http://localhost:5173
```

## Backend tests (no GPU, no network)

```bash
# Unit: normalization (point→range, range→midpoint, invariants, clamping), error mapping.
docker compose exec backend pytest tests/unit/test_age_service.py -v

# Contract: 200 shape, 400/401/500 status codes, pinned error body, integer/range invariants.
docker compose exec backend pytest tests/contract/test_age_contracts.py -v

# Domain purity: age.py imports no infra/ML/Pillow/FastAPI.
docker compose exec backend pytest tests/domain/test_domain_purity.py -v

# Integration: real endpoint + mock detector/age + real session validation (PostgreSQL).
docker compose exec backend pytest tests/integration/test_age_analysis.py -v

# Full age suite + mood regression (FR-020).
docker compose exec backend pytest tests/unit/test_age_service.py tests/contract/test_age_contracts.py tests/integration/test_age_analysis.py tests/domain/test_domain_purity.py tests/integration/test_mood_analysis.py -v
```

## Frontend tests (no GPU, no network — mocked camera + fetch)

```bash
cd frontend
npm test -- --run src/__tests__/dashboard src/__tests__/age
```

Tests mock `navigator.mediaDevices.getUserMedia` with a controlled test frame and mock `fetch` for age responses, walking the age state machine (idle → processing → result | error), asserting the age button is enabled (placeholder removed), asserting the shared capture mutex (both buttons disable during either analysis), and asserting the spec 004 mood tests still pass (no regression — FR-020).

## Manual end-to-end walkthrough

1. Open `http://localhost:5173` → complete onboarding (spec 002) → login (spec 003) → arrive at `/dashboard`.
2. **Camera preview is active** (stream acquired on mount — FR-012b, unchanged from spec 004).
3. Press **"Calcular edad"** (now **enabled** — the spec 004 "Próximamente" placeholder is removed, FR-013):
   - **Both** the mood and age buttons **disable** and an independent **age loading indicator** appears (FR-014 shared capture mutex).
   - A single still is captured and sent to `POST /api/analysis/age` with the session cookie.
4. On success: the **age range** (e.g. "27–37 años"), **point estimate** (e.g. "≈32 años"), and the **disclaimer** text are displayed; both buttons re-enable (FR-002/FR-003/FR-012a).
5. The result **stays visible** until a new age analysis or logout (FR-010). Triggering a mood analysis does **not** clear the age result (independent surfaces — SC-018).
6. **"Detectar estado de ánimo"** still works independently (spec 004 regression — FR-020).

## Expected outcomes (verifies)

| Scenario | Expected | Verifies |
|----------|----------|----------|
| Valid session + one-face image (range) | `200` `{estimatedAge, range, disclaimer}` with invariants | FR-002, SC-002, AC-008 |
| Port returns point-only | `200` with derived symmetric range (half-width 5) | FR-004, SC-014 |
| Port returns range | `200` with `estimatedAge` = midpoint | FR-004, SC-014 |
| No cookie / expired session | `401 unauthenticated`, no analysis | FR-001, SC-003 |
| Undecodable/oversized image | `400 invalid_image` | FR-006, SC-004 |
| No face in capture | `400 no_face` | FR-006, SC-004 |
| Multiple faces | `400 multiple_faces` | FR-006, SC-004 |
| Low quality | `400 insufficient_quality` | FR-006, SC-004 |
| Port error | `500 internal_error` | FR-007, SC-005 |
| Double press during in-flight | Second press ignored, both buttons disabled | FR-014, SC-006 |
| Press mood during age in-flight | Mood button disabled, press ignored (shared mutex) | FR-014, SC-006 |
| Camera permission denied | Actionable age error + retry, no backend call | FR-012c, SC-016 |
| Logout after result | Result discarded, stream released | FR-010, SC-015 |
| Narrow range (`min == max`) | Only point estimate "≈NN años" rendered | FR-012a |
| Domain purity | `age.py` imports no infra/ML | FR-015, SC-009 |
| No biometric data in logs | Logs show only duration/status/error_code | FR-019, SC-013 |
| Mood regression | Spec 004 mood tests still pass | FR-020, SC-017 |
| Independent surfaces | Age result not cleared by mood analysis (and vice versa) | SC-018 |

## Contract-violation check (SC-011)

Introduce a deliberate change to the age response shape (e.g. rename `estimatedAge` → `age`) or break the `min <= estimatedAge <= max` invariant (e.g. remove the clamping in `normalize_age_result`), then run the contract/unit suite — at least one test fails. Revert to restore green.
