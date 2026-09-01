# Contracts: Age Estimation (Fase 4 — age)

HTTP contracts for the age estimation feature. These supersede the spec 001 stub contracts (which were explicitly stubs with "enforcement deferred to specs 002–006").

| Endpoint | Contract | Status |
|----------|----------|--------|
| `POST /api/analysis/age` | [analysis-age.md](./analysis-age.md) | **real** (spec 005 — supersedes spec 001 stub) |

The error body shape `{"error": {"code": "...", "message": "..."}}` is the spec-002-pinned flat shape, reused verbatim. Status-code mapping is pinned: `401` exclusively for `unauthenticated`; `400` for actionable capture-quality codes; `500` for `internal_error`.

The mood endpoint (`POST /api/analysis/mood`, spec 004) is reused unchanged — its real contract is in `specs/004-mood-analysis/contracts/analysis-mood.md`. The face-data deletion endpoint (`DELETE /api/users/{userId}/face-data`) remains a session-gated stub from spec 001/003 — its real contract is deferred to spec 006.
