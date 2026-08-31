# Backend Tests

Automated contract, domain, and integration test suites for the Face Insight Demo
(Fase 1 skeleton). The full suite runs **without GPU, network, or real ML
models** (FR-017, SC-008).

## Layout

```
backend/tests/
├── conftest.py                      # shared fixtures (FastAPI app, httpx client)
├── contract/test_http_contracts.py  # 7 endpoints × shape + status (FR-016)
├── domain/
│   ├── test_entities.py             # entity construction, UUID v4, enum validation
│   ├── test_mock_adapters.py        # deterministic mock outputs (SC-005)
│   └── test_domain_purity.py        # SC-004: domain has no infra/ML imports
└── integration/
    ├── test_stack.py                # /health, /readyz smoke (US1)
    └── test_persistence.py          # migrations + FS adapter (US5; DB tests skip if no PG)
```

## Running

Inside the backend container (recommended):

```bash
docker compose exec backend pytest tests/ -v
```

On the host with a local Python env (backend deps installed):

```bash
cd backend && pytest tests/ -v
```

Run only the contract + domain suite (no DB needed):

```bash
pytest tests/contract tests/domain -v
```

## Determinism (SC-005)

Mock adapters return hardcoded constants. To verify byte-identical output across
repeated runs:

```bash
pytest tests/domain -v > run1.txt
pytest tests/domain -v > run2.txt
diff run1.txt run2.txt   # no output
```

## Contract-violation detection (SC-009)

`tests/contract/test_http_contracts.py::test_contract_violation_is_detected`
asserts the onboarding `status` is `"enrolled"`. Returning `"active"` instead
would fail the suite.
