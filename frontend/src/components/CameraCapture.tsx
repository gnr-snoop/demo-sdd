// CameraCapture — camera preview + single still capture (T028, FR-011/FR-012/FR-015).
//
// Uses navigator.mediaDevices.getUserMedia({ video: true }) → <video> preview →
// hidden <canvas> + drawImage + toBlob('image/jpeg'). The capture button is
// keyboard-accessible with an aria-label (FR-015).
//
// Spec 005: exposes an imperative `capture()` method via forwardRef so an
// external button (e.g. the age button on the dashboard) can trigger a still
// capture from the same live preview without opening a second stream (FR-012b).
// The built-in capture button (when `captureButtonLabel` is provided) calls the
// same `capture()` method — both paths go through `onCapture`.

import React, { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";

export interface CameraCaptureHandle {
  /** Trigger a still capture from the live preview. No-op if the stream is not ready. */
  capture: () => void;
}

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
  /** Optional capture button label (default "Capturar"). When undefined, no
   * built-in button is rendered (the caller triggers captures via the ref). */
  captureButtonLabel?: string;
  /** Optional capture button aria-label (default "Capturar rostro"). */
  captureButtonAriaLabel?: string;
  /** Optional test id for the capture button (default "capture-button"). */
  captureButtonTestId?: string;
}

const CameraCapture = forwardRef<CameraCaptureHandle, CameraCaptureProps>(function CameraCapture(
  {
    active,
    onCapture,
    onPermissionGranted,
    onPermissionDenied,
    disabled = false,
    captureButtonLabel = "Capturar",
    captureButtonAriaLabel = "Capturar rostro",
    captureButtonTestId = "capture-button",
  },
  ref,
) {
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

  const capture = useCallback(() => {
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

  // Expose the imperative capture method (spec 005).
  useImperativeHandle(ref, () => ({ capture }), [capture]);

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
          onClick={capture}
          disabled={disabled}
          aria-label={captureButtonAriaLabel}
          data-testid={captureButtonTestId}
        >
          {captureButtonLabel}
        </button>
      )}
    </div>
  );
});

export default CameraCapture;
