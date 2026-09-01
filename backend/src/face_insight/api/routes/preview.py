"""Preview detection route — live face bbox + landmarks for overlay toggle (011).

POST /api/preview/detect
- Multipart `image` (JPEG, ≤2 MB, long edge ≤640 before inference via decode_and_normalize).
- No session required — preview is before capture, before auth (onboarding/login/dashboard preview).
- Uses the Detector port (`request.app.state.detector`) — real YuNetDetector in production (Docker + CUDA when available),
  MockDetector in mock mode. Returns ephemeral detections, never persisted/logged.
- Returns { detections: [{box:{x,y,width,height}, landmarks:[{x,y}], score, faceCount }]}
  Boxes/landmarks are in the *normalized* image space (after resize to ≤640 long edge).
  Frontend rescales to video coordinates via scaleX/scaleY.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from ...config import get_settings
from ...domain.result_types import DetectionResult
from ...logging import get_logger

router = APIRouter(prefix="/api/preview", tags=["preview"])
logger = get_logger("face_insight.preview")


@router.post("/detect")
async def preview_detect(
    request: Request,
    image: UploadFile = File(...),
) -> JSONResponse:
    settings = get_settings()
    started = time.monotonic()
    try:
        image_bytes = await image.read()
        if not image_bytes:
            return JSONResponse(status_code=400, content={"error": {"code": "invalid_image", "message": "Imagen vacía"}})
        if len(image_bytes) > settings.image_max_bytes:
            return JSONResponse(status_code=400, content={"error": {"code": "invalid_image", "message": "Imagen demasiado grande"}})

        detector = getattr(request.app.state, "detector", None)
        if detector is None:
            return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Detector no disponible"}})

        # Direct detection on snapshot bytes (no resize) — snapshot coords == returned coords
        # This keeps preview boxes aligned to the video frame that was sampled.
        result: DetectionResult = detector.detect(image_bytes)

        detections = []
        for idx, box in enumerate(result.boxes):
            lm = None
            if result.landmarks and idx < len(result.landmarks):
                lm = [{"x": p.x, "y": p.y} for p in result.landmarks[idx]]
            detections.append(
                {
                    "box": {"x": box.x, "y": box.y, "width": box.width, "height": box.height},
                    "landmarks": lm,
                    "score": result.score,
                }
            )

        logger.info("preview.detect", duration_ms=int((time.monotonic() - started) * 1000), status="success", face_count=len(detections))
        return JSONResponse(status_code=200, content={"detections": detections, "faceCount": len(detections)})

    except Exception:  # noqa: BLE001
        logger.exception("preview.detect_unexpected")
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "Error interno"}})
