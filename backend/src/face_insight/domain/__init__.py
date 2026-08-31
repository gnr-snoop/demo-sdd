"""Pure hexagonal domain layer (Constitution Principle VII).

This package MUST NOT import from ``adapters/``, ``api/``, ``sqlalchemy``, or
any ML package (SC-004, enforced by tests/domain/test_domain_purity.py).
"""
