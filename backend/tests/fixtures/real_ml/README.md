# Real-ML Test Fixtures (spec 008, US6, FR-015, PRD §12)

This directory holds **consented test images only** for the real-model
integration suite (`tests/integration/test_real_ml_adapters.py`).

## Required Fixtures

| File | Description |
|------|-------------|
| `single_face.jpg` | An image containing exactly one face. |
| `no_face.jpg` | An image containing no faces (e.g. a landscape). |
| `multi_face.jpg` | An image containing ≥ 2 faces. |
| `person_a_1.jpg` | First capture of person A. |
| `person_a_2.jpg` | Second capture of person A (same person, different photo). |
| `person_b_1.jpg` | A capture of person B (different person). |

## Consent

**All images placed here MUST be from individuals who have explicitly
consented to their use as test data** (PRD §12 — "usar únicamente imágenes de
prueba con consentimiento"). Do not commit images of non-consenting individuals.

## Gitignore

These fixtures may be gitignored (to avoid committing biometric data to the
repo) or committed with documented consent. If gitignored, the real-model
integration tests skip gracefully when the fixtures are absent
(`pytest.skip("fixture absent: ...")`).

## Adding Fixtures

1. Obtain consented images from willing test subjects.
2. Resize to ≤ 640px long edge (OQ-8).
3. Place them in this directory with the filenames above.
4. Run: `APP_MODE=production pytest tests/integration/test_real_ml_adapters.py -q`
