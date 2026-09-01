# Implementation Plan: Face Data Deletion (Fase 6 partial — hardening)

**Branch**: `006-delete-face-data` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-delete-face-data/spec.md`

## Summary

Implement the real `DELETE /api/users/{userId}/face-data` operation: an authorized,
hard-delete "right to be forgotten" flow that removes a user's `FaceTemplate`,
all `AuthSession` rows, and the `User` row in a single PostgreSQL transaction
(dependents first, then parent), then best-effort deletes the
`usuarios/<user-id>/` filesystem folder, clears the session cookie, and returns
`200 {userId, status: "deleted"}`. Authorization is demo-grade: the session's
`userId` must match the path `userId` (no admin panel). The frontend `/dashboard`
gains a keyboard-accessible "Eliminar mis datos" button + confirmation dialog;
on success it clears session state, releases the camera, and navigates to `/`.
Builds on specs 001-004 (ports, adapters, route stub, schema, frontend api fn,
and contract-test scaffolding already exist). Constitution Principles V/VI/VIII.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x / React 18 / Vite (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x (async), Pydantic v2, pytest;
React, react-router-dom, vitest. All already in the stack (specs 001-004).

**Storage**: PostgreSQL (User, FaceTemplate, AuthSession rows — hard delete) +
local filesystem `usuarios/<user-id>/` folder (best-effort `shutil.rmtree`).

**Testing**: pytest (unit/contract/integration), vitest (frontend unit). Domain
tests run without GPU/network/real models (deletion invokes no ML port).

**Target Platform**: Docker Compose stack (backend + frontend + PostgreSQL),
local filesystem bind-mount of `usuarios/`.

**Project Type**: web-service (Python/FastAPI backend + React/Vite frontend).

**Performance Goals**: Demo-grade only (no real-time SLO — Constitution Explicit Non-Goals).

**Constraints**: Single PostgreSQL transaction for DB deletion; filesystem cleanup
best-effort after commit (no two-phase commit — Principle I). No ML ports invoked.

**Scale/Scope**: Single demo user deletion; no batch, no admin, no retention.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Demo-First Scope | ✅ PASS | Hard delete (simplest), best-effort FS cleanup (no two-phase commit), lightweight native confirm dialog. YAGNI: no soft-delete/retention/idempotence/audit. |
| II. Spec-Driven Workflow | ✅ PASS | This plan follows spec → plan → tasks → implement. Spec derives from PRD §8/FR-017. |
| III. Technology Stack | ✅ PASS | Python/FastAPI + React/Vite + PostgreSQL — unchanged from specs 001-004. No new tech. |
| IV. Containerized Execution | ✅ PASS | Runs in existing `docker compose` stack; `usuarios/` bind-mount reused. |
| V. Local Filesystem Image Storage | ✅ PASS | FS cleanup targets `usuarios/<user-id>/` via the existing `ImageStorage.delete` port (already a `shutil.rmtree` no-op-when-absent). |
| VI. PostgreSQL for Embeddings | ✅ PASS | DB deletion via SQLAlchemy UnitOfWork in one transaction. |
| VII. Hexagonal / Ports-and-Adapters | ✅ PASS | `DeletionService` depends only on ports + an injected `delete_user_face_data` callable (same callable-injection pattern as `OnboardingService.save_user_with_template`). No SQLAlchemy/framework import in domain. No ML port invoked. |
| VIII. No Security/Traceability/Identity Guarantees | ✅ PASS (justified) | Demo-grade authorization (session userId == path userId; 403 intentionally revealing — caller already authenticated). No audit log, no retention, no rate limiting. `403 forbidden` is a demo-grade authz signal, not a security guarantee — explicitly within Principle VIII. No BLOCKING items: all security/privacy-relevant decisions are pinned by the spec and justified under Principle VIII/I. |

**Gate result**: PASS. No violations requiring Complexity Tracking entries. The
`403 forbidden` "intentionally revealing" choice and hard-delete-without-audit
choice are security/data-privacy-relevant but are explicitly pinned in the spec
and justified under Principles VIII (no security/traceability guarantee) and I
(demo-first). In strict mode these are acknowledged, not BLOCKING — they narrow
guarantees (a non-goal), they do not introduce new ones.

## Project Structure

### Documentation (this feature)

```text
specs/006-delete-face-data/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── delete-face-data.md   # Phase 1 output (real contract, supersedes spec 001 stub)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/face_insight/
│   ├── domain/
│   │   ├── deletion.py          # NEW — DeletionService use-case (ports + injected UoW callable)
│   │   ├── exceptions.py        # EDIT — add Forbidden, NotFound, DeletionInternalError
│   │   └── ports.py             # EDIT — (no new port; UoW callable injected, see research R-2)
│   ├── adapters/
│   │   ├── db/
│   │   │   └── repositories.py  # EDIT — SqlAlchemyUnitOfWork.delete_user_face_data (one transaction)
│   │   └── mock/
│   │       └── ...              # EDIT — MockUnitOfWork.delete_user_face_data for domain tests
│   ├── api/
│   │   ├── routes/users.py      # EDIT — real delete_face_data: authz → 404 → service → cookie clear → 200
│   │   ├── dependencies.py      # EDIT — get_deletion_service resolver
│   │   └── schemas.py           # (unchanged — DeleteFaceDataResponse, ErrorResponse already exist)
│   └── main.py                  # EDIT — wire DeletionService + UoW into app.state
└── tests/
    ├── unit/
    │   └── test_deletion_service.py   # NEW — authz rule, ordering, error mapping
    ├── contract/
    │   └── test_http_contracts.py     # EDIT — add 200/403/404/500 deletion contract cases
    └── integration/
        └── test_deletion_integration.py  # NEW — real PG + real FS adapter end-to-end

frontend/
├── src/
│   ├── pages/Dashboard.tsx          # EDIT — "Eliminar mis datos" button + confirm dialog + post-delete handling
│   ├── context/SessionContext.tsx   # EDIT — add clearSession() (clear state without calling /logout)
│   └── services/api.ts              # EDIT — deleteFaceData: add credentials:"include" + error parsing
└── tests/
    └── DashboardDelete.test.tsx     # NEW — UI flow: button → confirm → processing → success/error/cancel
```

**Structure Decision**: Web application layout (Option 2) — unchanged from specs
001-004. This spec adds one new domain module (`deletion.py`), extends the
existing `SqlAlchemyUnitOfWork` with a transactional deletion method, fills in
the existing route stub, and extends the existing Dashboard. No new top-level
directories or packages.

## Complexity Tracking

> No Constitution Check violations require justification. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
