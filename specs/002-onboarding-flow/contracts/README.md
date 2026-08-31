# Contracts: Onboarding Flow (Fase 2)

This directory contains the HTTP contract for the endpoint filled with real logic in this spec.

| Endpoint | Contract | Status |
|----------|----------|--------|
| `POST /api/onboarding` | [onboarding.md](./onboarding.md) | **Real logic** (supersedes spec 001 stub) |

All other endpoints (`POST /api/auth/face-login`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`) remain stubs from spec 001 and are out of scope for this spec. Their contracts are defined in `specs/001-skeleton-contracts-mocks/contracts/`.

## Error response convention (introduced in spec 002)

All onboarding error responses use the shape:

```json
{
  "error": {
    "code": "<machine-code>",
    "message": "<actionable human message>"
  }
}
```

`Content-Type: application/json`. Machine codes are stable strings for contract-test assertions. See [onboarding.md](./onboarding.md) for the full code/status table.
