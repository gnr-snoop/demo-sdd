// CameraCapture — camera preview + single still capture (T028, FR-011/FR-012/FR-015).
//
// Uses navigator.mediaDevices.getUserMedia({ video: true }) → <video> preview →
// hidden <canvas> + drawImage + toBlob('image/jpeg'). The capture button is
// keyboard-accessible with an aria-label (FR-015).

import React, { useCallback, useEffect, useRef, useState } from "react";

export interface CameraCaptureProps {
  /** When true, request the camera and show the preview. */
  active: boolean;
  /** Called with a JPEG Blob when the user captures a still. */
  onCapture: (blob: Blob) => void;
  /** Called when camera permission is granted (stream acquired). */
  onPermissionGranted: () => void;
  /** Called when camera permission is denied or unavailable. */
  onPermissionDenied: () => void;
  /** Disable the capture button (e.g. during processing). */
  disabled?: boolean;
}

const CameraCapture: React.FC<CameraCaptureProps> = ({
  active,
  onCapture,
  onPermissionGranted,
  onPermissionDenied,
  disabled = false,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [streamReady, setStreamReady] = useState(false);

  // Acquire the camera stream when `active` becomes true; release on unmount.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        setStreamReady(true);
        onPermissionGranted();
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          // Fire-and-forget; play() may reject in environments without media.
          const playPromise = videoRef.current.play?.();
          if (playPromise && typeof playPromise.catch === "function") {
            playPromise.catch(() => {});
          }
        }
      } catch {
        if (!cancelled) {
          setStreamReady(false);
          onPermissionDenied();
        }
      }
    }

    startCamera();

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      setStreamReady(false);
    };
  }, [active, onPermissionGranted, onPermissionDenied]);

  const handleCapture = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !streamReady) return;
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, width, height);
    canvas.toBlob(
      (blob) => {
        if (blob) onCapture(blob);
      },
      "image/jpeg",
      0.9,
    );
  }, [streamReady, onCapture]);

  return (
    <div data-testid="camera-capture">
      <video
        ref={videoRef}
        data-testid="camera-preview"
        playsInline
        muted
        style={{ maxWidth: "100%", display: streamReady ? "block" : "none" }}
      />
      <canvas ref={canvasRef} style={{ display: "none" }} />
      {active && streamReady && (
        <button
          type="button"
          onClick={handleCapture}
          disabled={disabled}
          aria-label="Capturar rostro"
          data-testid="capture-button"
        >
          Capturar
        </button>
      )}
    </div>
  );
};

export default CameraCapture;
