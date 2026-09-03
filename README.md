# Face Insight Demo

Demo-grade face-insight application: onboarding, face login, mood and age
analysis. The application uses a hexagonal architecture so the same domain
flows can run with deterministic mocks or with the concrete ML adapters.

## Quickstart

See [`specs/001-skeleton-contracts-mocks/quickstart.md`](./specs/001-skeleton-contracts-mocks/quickstart.md)
for the full runnable validation scenarios.

### Bring up the stack

```bash
docker compose up --build
```

- Backend (FastAPI): http://localhost:8000  (`/health`, `/readyz`)
- Frontend (React + Vite): http://localhost:5173
- PostgreSQL: localhost:5432

### Verify health

```bash
curl -s http://localhost:8000/health   # {"status":"healthy"}
curl -s http://localhost:8000/readyz   # {"status":"ready","db":true}
```

### Run the test suite

```bash
docker compose exec backend pytest tests/ -v
docker compose exec frontend npm test
```

## Models

The Docker Compose stack starts the backend with `APP_MODE=production`. In this
mode the following models are used:

| Model | File | Use | Version |
|---|---|---|---|
| **YuNet** | `face_detection_yunet_2023mar.onnx` | Face detection and five facial landmarks | `yunet-2023mar-v1` |
| **SFace** | `face_recognition_sface_2021dec.onnx` | 128-dimensional face embeddings for registration and login verification | `sface-2021dec-v1` |
| **EmotiEff / HSEmotion** | `enet_b0_8_best_afew.onnx` | Mood classification: `neutral`, `feliz`, `triste`, `sorprendido`, `enojo` or `no concluyente` | `emotieff-enet-b0-afew-v1` |
| **MiVOLO** | `volo_d1_224_369_age_only-e7ee8cd0.pth` | Face-based age estimation | `mivolo-volo-d1-face-v1` |

The models are cached in the repository `models/` directory and mounted into
the backend container at `/app/models`. `ModelDownloader` obtains missing
files and validates them before the concrete adapters are initialized.

YuNet is also used internally by the SFace, EmotiEff and MiVOLO adapters to
locate and align the face before inference. The live face bounding-box and
landmark overlay uses the browser `FaceDetector` when available; otherwise its
server-side preview adapter uses YuNet through the backend.

### Mood model mapping

The EmotiEff model predicts eight AFEW classes. The application maps them as
follows:

| AFEW class | Application label |
|---|---|
| Anger | `enojo` |
| Happiness | `feliz` |
| Neutral | `neutral` |
| Sadness | `triste` |
| Surprise | `sorprendido` |
| Contempt, Disgust, Fear | `no concluyente` |

Predictions below the configured `MOOD_CONFIDENCE_THRESHOLD` (default `0.5`)
are returned as `no concluyente`.

### Mock mode

Set `APP_MODE=mock` to avoid loading real models. Mock mode uses deterministic
adapters for local development and tests:

- Face detection: fixed mock detections.
- Face embeddings: fixed mock vector.
- Mood: `neutral` with confidence `0.74` by default.
- Age: deterministic mock estimate.

The production container currently sets `APP_MODE=production` in
`docker-compose.yml`. Missing model files are downloaded into `models/` by the
backend's model cache before the concrete adapters are initialized.

## Project layout

```
backend/    # FastAPI + SQLAlchemy + Alembic (hexagonal: domain/ adapters/ api/)
frontend/   # React + Vite SPA
usuarios/   # bind-mount root: <user-id>/pictures.jpg created at runtime
docker-compose.yml
```

## Architecture

Hexagonal ports-and-adapters (Constitution Principle VII):

- `backend/src/face_insight/domain/` — pure entities, result types, port
  Protocols. **Zero** infra/ML imports (enforced by
  `tests/domain/test_domain_purity.py`, SC-004).
- `backend/src/face_insight/adapters/mock/` — deterministic mock adapters
  implementing every port for tests and `APP_MODE=mock`.
- `backend/src/face_insight/adapters/ml/` — concrete YuNet, SFace, EmotiEff
  and MiVOLO adapters used by `APP_MODE=production`.
- `backend/src/face_insight/adapters/db/` — SQLAlchemy ORM + repository adapters.
- `backend/src/face_insight/adapters/fs/` — filesystem image storage
  (`usuarios/<user-id>/pictures.jpg`).
- `backend/src/face_insight/api/` — FastAPI routes, Pydantic schemas, session
  dependency.

All primary keys are UUID v4 strings (PostgreSQL `UUID` columns); identity is
domain-owned.
