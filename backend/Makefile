# Face Insight backend Makefile (spec 007, FR-011, research R-5).
#
# Manual fallback for running Alembic migrations to head on a host-native
# production setup (the docker-compose entrypoint runs this automatically
# gated on APP_MODE=production).

.PHONY: migrate migrate-down test

# Apply all pending migrations to head (FR-011).
migrate:
	alembic upgrade head

# Roll back the most recent migration (convenience).
migrate-down:
	alembic downgrade -1

# Run the test suite (domain/contract/unit — no GPU/network).
test:
	pytest tests/domain tests/contract tests/unit -q
