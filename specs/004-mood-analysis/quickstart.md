# Quickstart: Mood Analysis (Fase 4)

**Spec**: [spec.md](./spec.md) | **Branch**: `004-mood-analysis` | **Date**: 2026-08-31

Runnable validation scenarios that prove the mood analysis feature works end-to-end. The domain portions run without GPU, network, or real ML models (Constitution Quality Gate §7).

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
# Unit: label normalization, confidence clamp, valid-label set, error mapping.
docker compose exec backend pytest tests/unit/test_mood_service.py -v

# Contract: 200 shape, 400/401/500 status codes, pinned error body, confidence bounds.
docker compose exec backend pytest tests/contract/test_mood_contracts.py -v

# Domain purity: mood.py imports no infra/ML/Pillow/FastAPI.
docker compose exec backend pytest tests/domain/test_domain_purity.py -v

# Integration: real endpoint + mock detector/mood + real session validation (PostgreSQL).
docker compose exec backend pytest tests/integration/test_mood_analysis.py -v

# Full mood suite.
docker compose exec backend pytest tests/unit/test_mood_service.py tests/contract/test_mood_contracts.py tests/integration/test_mood_analysis.py tests/domain/test_domain_purity.py -v
```

## Frontend tests (no GPU, no network — mocked camera + fetch)

```bash
cd frontend
npm test -- --run src/__tests__/dashboard src/__tests__/mood
```

Tests mock `navigator.mediaDevices.getUserMedia` with a controlled test frame and mock `fetch` for mood responses, walking the mood state machine (idle → processing → result | error) and asserting the disabled age placeholder.

## Manual end-to-end walkthrough

1. Open `http://localhost:5173` → complete onboarding (spec 002) → login (spec 003) → arrive at `/dashboard`.
2. **Camera preview is active** (stream acquired on mount — FR-012b).
3. Press **"Detectar estado de ánimo"**:
   - The mood button **disables** and a **loading indicator** appears (FR-014).
   - A single still is captured and sent to `POST /api/analysis/mood` with the session cookie.
4. On success: the **mood category** (e.g. "neutral"), **confidence** as `≈NN%` (e.g. "≈74%"), and the **disclaimer** text are displayed; the button re-enables (FR-012a, FR-003).
5. The result **stays visible** until a new analysis or logout (FR-010).
6. **"Calcular edad"** button is present but **disabled** with a "Próximamente" indication (FR-013).

## Expected outcomes (verifies)

| Scenario | Expected | Verifies |
|----------|----------|----------|
| Valid session + one-face image | `200` `{label, confidence, disclaimer}` | FR-002, SC-002, AC-007 |
| No cookie / expired session | `401 unauthenticated`, no analysis | FR-001, SC-003 |
| Undecodable/oversized image | `400 invalid_image` | FR-006, SC-004 |
| No face in capture | `400 no_face` | FR-006, SC-004 |
| Multiple faces | `400 multiple_faces` | FR-006, SC-004 |
| Low quality | `400 insufficient_quality` | FR-006, SC-004 |
| Port error | `500 internal_error` | FR-007, SC-005 |
| Out-of-set label | `200` `label: "no concluyente"` | FR-004 |
| Double press during in-flight | Second press ignored, button disabled | FR-014, SC-006 |
| Camera permission denied | Actionable error + retry, no backend call | FR-012c, SC-016 |
| Logout after result | Result discarded, stream released | FR-010, SC-015 |
| `confidence` present | Renders as `≈NN%` | FR-012a, SC-014 |
| `confidence` null/omitted | Only label + disclaimer render | FR-012a, SC-014 |
| Domain purity | `mood.py` imports no infra/ML | FR-015, SC-009 |
| No biometric data in logs | Logs show only duration/status/error_code | FR-019, SC-013 |

## Contract-violation check (SC-011)

Introduce a deliberate change to the mood response shape (e.g. rename `label` → `mood`) or allow an out-of-set label (remove the normalization), then run the contract/unit suite — at least one test fails. Revert to restore green.
