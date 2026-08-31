<!--
=====================================================================
Sync Impact Report
=====================================================================
Version change : (new) → 1.0.0  (first ratification; MINOR/PATCH n/a)
Modified principles : N/A — initial fill from placeholder template
Added sections      : Core Principles (I–VIII), Technology Stack,
                      Development Workflow & Quality Gates,
                      Explicit Non-Goals, Governance, Open Questions
Removed sections     : none
Templates updated    : none (plan/spec/tasks templates are generic
                      placeholders; their Constitution Check / testing
                      notes reference "the constitution" generically and
                      remain aligned with the principles below — no edit
                      required)
Files flagged for
manual follow-up     : .specify/templates/plan-template.md
                        → "Constitution Check" section will be populated
                          per-feature by /speckit.plan using these
                          principles; no template edit needed.
                      .specify/templates/tasks-template.md
                        → "Tests" note already defers to constitution;
                          testing mandates below (contract tests for
                          PRD §8, mocks for domain) are enforceable as-is.
=====================================================================
-->

# Face Insight Demo Constitution

## Core Principles

### I. Demo-First Scope

This project is a **demonstration of Spec-Driven Development (SDD) as a workflow**, not a production biometric or surveillance system. Every design decision is filtered through the question *"Does this make the SDD flow clearer and the demo more understandable?"* — not *"Is this production-grade?"*

- Simplicity and clarity of the end-to-end flow **trump** robustness, scalability, and security hardening.
- The happy path is the product. Edge-case hardening is added only where it materially improves the demo narrative or prevents the demo from crashing.
- YAGNI applies aggressively: features not required by the PRD acceptance criteria (AC-001..AC-009) are deferred or rejected.
- This principle is the highest-ranking tiebreaker: when two principles conflict, the one that yields a simpler, more demonstrable flow wins.

**Rationale**: The repo exists to teach/show SDD. Over-engineering obscures the lesson and contradicts the project's reason for existing.

### II. Spec-Driven Workflow

All work follows the SDD pipeline: **spec → plan → tasks → implement**. No implementation is written against an undocumented feature.

- Every feature begins as a specification (`specs/[###-feature]/spec.md`) derived from the PRD.
- A plan (`plan.md`) with research, data model, and contracts is produced before tasks.
- Tasks (`tasks.md`) are generated from the plan and organized by user story, each independently testable.
- The PRD (`PRD.md`) is the upstream source of truth for scope, views (`/`, `/onboarding`, `/login`, `/dashboard`), HTTP contracts (PRD §8), data model (PRD §7), and acceptance criteria (PRD §9, AC-001..AC-009).
- Implementation phases follow PRD §10 phases 1..6 unless explicitly re-sequenced in a plan.

**Rationale**: The project's purpose is to demonstrate this workflow; violating it would defeat the demo.

### III. Technology Stack: Python + React + Open-Source ML

The stack is fixed and three-tiered:

- **Backend**: Python. (Web framework: FastAPI by default — see Open Questions OQ-1.)
- **Frontend**: React. (Tooling: Vite by default — see Open Questions OQ-2.)
- **ML models**: All models — detector, embedding, age, mood — **must be open-source** (open-weights and/or OSI-approved license). No proprietary or closed-weights models.
  - Detector: **YOLO** (per PRD §11) — open-source.
  - Embedding, age, and mood models: open-source; specific choices deferred to Open Questions OQ-4/OQ-5.

**Rationale**: User-authoritative decision. Open-source ML keeps the demo reproducible, auditable, and license-clean.

### IV. Containerized Execution via Docker Compose

The project **must run inside Docker**, and a `docker compose` file (e.g. `docker-compose.yml`) must be defined at the repo root to bring up **all** services needed for the demo (backend, frontend, PostgreSQL, any ML/model-serving container).

- `docker compose up` is the canonical way to run the demo. No "it works on my machine" host-native setup is the primary path.
- Per-service `Dockerfile`s live alongside their source (`backend/Dockerfile`, `frontend/Dockerfile`, etc.).
- The compose file is the single source of truth for service topology, ports, and volumes (including the `usuarios/` bind mount — see Principle V).

**Rationale**: User-authoritative decision. Containerization makes the demo reproducible across machines and isolates the ML/runtime dependencies.

### V. Local Filesystem Image Storage under `usuarios/<user-id>/pictures.jpg`

The captured onboarding image is stored on the **local filesystem** under the structure:

```
usuarios/<user-id>/pictures.jpg
```

- A `usuarios/` directory lives at the repo/project root.
- One subfolder per user, named by the user-id.
- The image file is named `pictures.jpg` (singular fixed filename per user).
- **No object storage, no cloud, no S3/GCS/Azure.** This is a deliberate demo simplification.
- The `usuarios/` tree is bind-mounted into the backend container via Docker Compose so the path is identical inside and outside the container.
- This path convention is referenced by `DELETE /api/users/{userId}/face-data` (PRD §8) — deletion removes the folder/image and the DB embeddings (Principle VI).

**Rationale**: User-authoritative decision. Local filesystem storage is the simplest thing that could possibly work for a demo and keeps the focus on the SDD flow, not infra plumbing.

### VI. PostgreSQL for Embeddings / Features

The extracted facial features (embeddings) and any derived data needed for login distance computation (e.g. embedding vector, model id, distance threshold) are stored in a **dockerized PostgreSQL** database.

- PostgreSQL runs as a service in the `docker compose` stack (Principle IV).
- The `User`, `FaceTemplate`, `AuthSession`, and optional `AnalysisRequest` entities from PRD §7 are persisted in PostgreSQL.
- Raw onboarding images stay on the filesystem (Principle V); only derived features/embeddings and metadata go in the DB.
- Schema is managed via migrations (tool choice deferred to Open Questions OQ-7); migrations run as part of container startup or a documented `make migrate` step.

**Rationale**: User-authoritative decision. A real RDBMS makes the 1:1 verification lookup (PRD §6.3) realistic without dragging in cloud services.

### VII. Hexagonal / Ports-and-Adapters Domain Isolation

The domain layer is isolated from infrastructure via **ports and adapters** (hexagonal architecture). This is mandated by PRD §11.

- The **domain layer must not import YOLO directly** (PRD §11) — nor any specific embedding/age/mood model.
- Embedding, detector, age, and mood capabilities sit behind **replaceable ports** (interfaces/protocols); concrete models are adapters selected at composition time.
- HTTP adapters implement the PRD §8 contracts; DB adapters talk to PostgreSQL (Principle VI); filesystem adapters talk to `usuarios/` (Principle V).
- **Mocks are allowed and expected** for dev and for domain-level tests. Domain tests must run without GPU, without real models, and without network.
- This is what makes the demo's ML choices swappable and the domain testable in isolation.

**Rationale**: PRD §11 requirement. Also the cleanest way to show, in a demo, how SDD separates *what* (domain/contracts) from *how* (adapters/implementations).

### VIII. Explicit Non-Goals: No Security / Traceability / Identity Guarantees

Because this is a demo, the project makes **explicitly no commitments** around security, traceability, or identity. These are **non-goals**, not gaps to close.

- **No security guarantee.** Face data is stored on a local filesystem and in a local DB with no encryption-at-rest mandate, no hardened auth, no rate limiting unless trivial. PRD §12 items are demo-level best-effort, **not guarantees**.
- **No traceability guarantee.** No audit log, no immutable event store, no compliance trail is required.
- **No identity guarantee.** No proof of personhood, no deduplication against a global identity, no identity federation. 1:1 verification only (PRD §6.3) — the system checks "is this the same person who onboarded under this user-id?", nothing more.
- Downstream specs **must not** introduce security/traceability/identity hardening "for completeness." Any such proposal must be rejected at the Constitution Check gate (see Governance) unless it directly serves the demo narrative.

**Rationale**: User-authoritative decision. Stating this as an explicit non-goal prevents spec/plan/task drift toward production biometric engineering and keeps the demo scoped.

## Technology Stack

| Concern            | Choice                                           | Notes / Reference                       |
|--------------------|--------------------------------------------------|-----------------------------------------|
| Backend language   | Python                                           | Principle III                           |
| Backend framework  | FastAPI (default)                                | OQ-1 open; async-friendly, OpenAPI auto |
| Frontend           | React                                            | Principle III                           |
| Frontend tooling   | Vite (default)                                   | OQ-2 open                               |
| ML detector        | YOLO (open-source)                               | PRD §11                                 |
| ML embedding       | Open-source model (TBD)                          | OQ-4 open                               |
| ML age / mood      | Open-source models (TBD)                         | OQ-5 open                               |
| Feature/embedding DB | PostgreSQL (dockerized)                        | Principle VI                            |
| Image storage      | Local filesystem `usuarios/<user-id>/pictures.jpg` | Principle V                          |
| Orchestration      | Docker Compose                                   | Principle IV                            |
| Session mechanism  | Server-side session / signed cookie (default)    | OQ-3 open; no JWT mandate               |
| Distance metric    | Cosine similarity (default)                      | OQ-6 open                               |
| Migrations         | Alembic (default)                                | OQ-7 open                               |

## Development Workflow & Quality Gates

The workflow is the SDD pipeline (Principle II) with the following gates:

1. **Constitution Check** (before plan Phase 0 research, re-checked after Phase 1 design):
   - Does the feature respect the demo-first scope (Principle I)? Reject production-grade scope creep.
   - Are all ML touchpoints behind ports (Principle VII)? No direct YOLO/model import in domain.
   - Are storage choices consistent with Principles V (images) and VI (embeddings)?
   - Does the design attempt any security/traceability/identity guarantee? If yes, reject (Principle VIII) unless explicitly justified in the plan's Complexity Tracking table.
2. **Spec gate**: User stories are prioritized (P1..Pn), each independently testable, mapped to PRD acceptance criteria AC-001..AC-009.
3. **Plan gate**: `data-model.md` and `contracts/` exist and align with PRD §7 and §8 before tasks are generated.
4. **Tests-first where practical**: For each user story, contract tests and domain unit tests are written before implementation and must fail first (Red-Green-Refactor). Domain tests use **mocks** for all ports (Principle VII).
5. **Contract tests for the HTTP API**: Every endpoint in PRD §8 (`POST /api/onboarding`, `POST /api/auth/face-login`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`) has a contract test asserting request/response shapes and status codes.
6. **Integration tests**: At least one integration test per user story exercising the real adapters (PostgreSQL + filesystem) via `docker compose`.
7. **No GPU required to develop/test**: Domain and contract suites run on any machine; only the ML-adapter integration tests may need a model (and may be skipped in CI with a documented flag).
8. **Phase gates**: PRD §10 phases 1..6 are sequential; a phase is "done" when its acceptance criteria pass and the relevant tests are green.

## Explicit Non-Goals

In addition to Principle VIII (no security/traceability/identity guarantees), the following are **out of scope** per PRD §4 and the demo-first principle:

- **No 1:N recognition / face search** — only 1:1 verification (PRD §6.3).
- **No liveness / anti-spoofing detection.**
- **No continuous video / streaming analysis** — analysis is on-demand from the dashboard (PRD §6.4).
- **No native mobile apps** — web only (views `/`, `/onboarding`, `/login`, `/dashboard`).
- **No admin panel / user management console.**
- **No account recovery, MFA, or password flows** — face is the only credential.
- **No multi-tenant / multi-org isolation.**
- **No cloud services** — everything runs locally via Docker Compose (Principle IV).
- **No model training / fine-tuning** — pre-trained open-source models are used as-is.
- **No real-time performance SLOs** — latency targets are demo-grade only.

## Governance

- This constitution is the **supreme** project document for scope and architectural decisions. Where the PRD and this constitution agree, both apply; where they conflict on a governance matter, this constitution wins (the PRD is the source of *what*, the constitution is the source of *why and how*).
- **Supersedes**: This constitution supersedes any prior constitution version and any ad-hoc practices. Generic framework defaults (e.g. a library's recommended project layout) apply only where they don't conflict with Principles I–VIII.
- **Amendments**:
  - Any principle change requires a written amendment with rationale, a version bump (semver: MAJOR for non-goal/scope changes, MINOR for new principles, PATCH for clarifications), and a re-check of all in-flight specs/plans for alignment.
  - Non-goal expansions (Principle VIII / Explicit Non-Goals) are MINOR bumps and require explicit acknowledgement that no in-flight feature depends on the removed capability.
  - Open Questions resolved into decisions are PATCH bumps and update the Technology Stack table.
- **Compliance review**: The Constitution Check gate (Development Workflow §1) is enforced on every plan. A plan that cannot pass the gate must either be reworked or record a justified exception in its Complexity Tracking table.
- **Runtime guidance**: For day-to-day development guidance not covered here, defer to the PRD and the per-feature `plan.md`; if a gap remains, raise an Open Question rather than silently inventing a rule.

## Open Questions

Each item below has a **default** so work can proceed; defaults are already reflected in the Technology Stack table. Resolving an OQ is a PATCH/MINOR constitution bump (see Governance).

- **OQ-1 — Python web framework**: FastAPI vs Flask vs Django. **Default: FastAPI** (async-friendly, auto OpenAPI docs that double as a demo of the PRD §8 contracts, good type hints for ports).
- **OQ-2 — React tooling/meta-framework**: Vite vs Next.js. **Default: Vite** (lighter, no SSR needed for a demo SPA with a separate Python backend).
- **OQ-3 — Session mechanism**: Server-side session store vs signed cookie vs JWT. **Default: server-side session in PostgreSQL (`AuthSession`, PRD §7) keyed by a signed cookie**. No JWT mandate (Principle VIII — no security guarantee).
- **OQ-4 — Embedding model**: Which open-source face embedding model. **Default: a lightweight open-weights face-recognition embedding (e.g. Facenet/InsightFace family)**, chosen at plan time; swappable behind the embedding port (Principle VII).
- **OQ-5 — Age & mood models**: Which open-source models. **Default: small open-weights CNN/classification heads**, chosen at plan time; swappable behind their ports.
- **OQ-6 — Distance metric for 1:1 verification**: Cosine vs Euclidean vs L2-normalized dot. **Default: cosine similarity** with a configurable threshold stored per `FaceTemplate`.
- **OQ-7 — DB migrations tool**: Alembic vs raw SQL vs other. **Default: Alembic** (standard for SQLAlchemy/FastAPI stacks).
- **OQ-8 — Image constraints**: Max size, format, resolution of the captured onboarding image. **Default: JPEG, ≤ 2 MB, resized to ≤ 640px on the long edge before storage** as `pictures.jpg` (Principle V). Tunable at plan time.

**Version**: 1.0.0 | **Ratified**: 2026-08-31 | **Last Amended**: 2026-08-31
