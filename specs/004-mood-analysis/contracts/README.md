# Contracts: Mood Analysis (Fase 4)

HTTP contracts for the mood analysis feature. These supersede the spec 001 stub contracts (which were explicitly stubs with "enforcement deferred to specs 002–006").

| Endpoint | Contract | Status |
|----------|----------|--------|
| `POST /api/analysis/mood` | [analysis-mood.md](./analysis-mood.md) | **real** (spec 004 — supersedes spec 001 stub) |

The error body shape `{"error": {"code": "...", "message": "..."}}` is the spec-002-pinned flat shape, reused verbatim. Status-code mapping is pinned: `401` exclusively for `unauthenticated`; `400` for actionable capture-quality codes; `500` for `internal_error`.

The age endpoint (`POST /api/analysis/age`) and face-data deletion (`DELETE /api/users/{userId}/face-data`) remain session-gated stubs from spec 001/003 — their real contracts are deferred to specs 005/006.
