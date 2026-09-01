# Contracts: Concrete ML Adapters (Fase 5a)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-01

This spec introduces **no new HTTP contracts and no changes to the PRD §8 API** (FR-018). The existing endpoints (`POST /api/onboarding`, `POST /api/auth/face-login`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/analysis/mood`, `POST /api/analysis/age`, `DELETE /api/users/{userId}/face-data`) are served identically; the frontend is unaware of the adapter substitution.

The contracts documented here are **adapter-layer conformance contracts** (the hexagonal port implementations) and the **model-download contract** (infrastructure), which are the new surfaces this spec exposes.

## Documents

- [adapter-port-conformance.md](./adapter-port-conformance.md) — `YuNetDetector` : `Detector` port and `SFaceEmbedder` : `Embedder` port conformance, including model-version, dimension, and threshold calibration.
- [model-download.md](./model-download.md) — `ModelDownloader` / `models/` cache contract: lazy fetch, atomic rename, single-attempt timeout, load-test integrity, offline pre-placement.
