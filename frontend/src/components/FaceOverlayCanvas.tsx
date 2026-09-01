// FaceOverlayCanvas — extracted drawing surface (011, T017 optional extraction, T035 polish).
// High-contrast stroke #00E5CC 2px, landmark dot radius 3px, DPR-aware.
// This component is not required to be used directly; CameraCapture inlines drawOverlay
// but this file provides the extracted helper for style-guide alignment and reuse.

import { PreviewDetection } from "../services/previewDetector";

export type FaceOverlayCanvasProps = {
  detections: PreviewDetection[];
  videoWidth: number;
  videoHeight: number;
  cssWidth: number;
  cssHeight: number;
  mirrored: boolean;
  canvasRef: React.RefObject<HTMLCanvasElement>;
};

export function drawFaceOverlay(
  ctx: CanvasRenderingContext2D,
  detections: PreviewDetection[],
  videoWidth: number,
  videoHeight: number,
  cssWidth: number,
  cssHeight: number,
): void {
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  if (detections.length === 0) return;
  const scaleX = cssWidth / (videoWidth || 640);
  const scaleY = cssHeight / (videoHeight || 480);
  ctx.strokeStyle = "#00E5CC";
  ctx.lineWidth = 2;
  for (const det of detections) {
    const x = det.box.x * scaleX;
    const y = det.box.y * scaleY;
    const w = det.box.width * scaleX;
    const h = det.box.height * scaleY;
    ctx.strokeRect(x, y, w, h);
    if (det.landmarks && det.landmarks.length > 0) {
      ctx.fillStyle = "#00E5CC";
      for (const lm of det.landmarks) {
        const lx = lm.x * scaleX;
        const ly = lm.y * scaleY;
        ctx.beginPath();
        ctx.arc(lx, ly, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
}

export default function FaceOverlayCanvas(props: FaceOverlayCanvasProps): null {
  // This component is intentionally renderless — CameraCapture owns the canvas element.
  // The function above is the reusable draw helper for tests/style guide.
  void props;
  return null;
}
