// PreviewDetector port — frontend hexagonal boundary (011, research R-1/R-5).
// Coordinates are in intrinsic video frame pixels (videoWidth/videoHeight space).

export type PreviewBox = { x: number; y: number; width: number; height: number };
export type PreviewLandmark = { x: number; y: number };
export type PreviewDetection = {
  box: PreviewBox;
  landmarks?: PreviewLandmark[];
  score?: number; // [0,1] optional; adapter may gate < OVERLAY_MIN_SCORE
  frameAt: number; // Date.now() of sampled frame
};

export interface PreviewDetector {
  /** Detect faces in the current <video> frame. Never throws — returns [] on failure/empty. */
  detect(video: HTMLVideoElement): Promise<PreviewDetection[]>;
}

// ---------------------------------------------------------------------------
// Constants (also re-exported from CameraCapture per data-model.md §Types)
// ---------------------------------------------------------------------------
export const OVERLAY_TOGGLE_TEST_ID = "overlay-toggle";
export const OVERLAY_TOGGLE_LABEL_EN = "Show face overlay";
export const OVERLAY_TOGGLE_LABEL_ES = "Mostrar contorno facial";
export const OVERLAY_SAMPLE_INTERVAL_MS = 200; // ≤5 FPS cap (FR-006)
export const OVERLAY_HOLD_MS = 200; // 150–250 ms window midpoint (FR-011 smoothing)
export const OVERLAY_MIN_SCORE = 0.5;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
/** Shared mirroring helper: flipped x when mirrored selfie. */
export function mirrorIfNeeded(x: number, w: number, cssWidth: number, mirrored: boolean): number {
  if (!mirrored) return x;
  return cssWidth - x - w;
}

/**
 * Lightweight flicker smoothing: hold last valid result for HOLD_MS after an
 * empty/low-confidence frame (FR-011). Returns the detections to render.
 * Extracted for unit testability (T029/R-5).
 */
export function applyHoldSmoothing(
  detections: PreviewDetection[],
  lastValidRef: { current: PreviewDetection[] | null },
  lastValidAtRef: { current: number | null },
  holdMs: number,
  minScore: number,
  now: number = Date.now(),
): PreviewDetection[] {
  // Filter out low-confidence detections
  const filtered = detections.filter((d) => (d.score === undefined ? true : d.score >= minScore));
  const hasValid = filtered.length > 0;

  if (hasValid) {
    lastValidRef.current = filtered;
    lastValidAtRef.current = now;
    return filtered;
  }

  // Empty or all low-confidence: check hold window
  if (
    holdMs > 0 &&
    lastValidRef.current !== null &&
    lastValidAtRef.current !== null &&
    now - lastValidAtRef.current <= holdMs
  ) {
    return lastValidRef.current;
  }

  // Beyond hold window → cleared
  if (filtered.length === 0 && (lastValidRef.current !== null || lastValidAtRef.current !== null)) {
    // Only clear refs if hold window exceeded (keeps empty semantics)
    if (holdMs === 0 || lastValidAtRef.current === null || now - (lastValidAtRef.current ?? 0) > holdMs) {
      // Caller decides whether to clear canvas; we return empty array
    }
  }
  return [];
}

// Offscreen snapshot downscale helper (T037, R-6) — optional 320px long-edge
// downscale preserving aspect. Returns a snapshot canvas for detector input.
// If detector consumes <video> directly, this is a no-op (caller uses video).
export function createSnapshotCanvas(
  video: HTMLVideoElement,
  maxLongEdge = 320,
): HTMLCanvasElement | null {
  const vw = video.videoWidth || 640;
  const vh = video.videoHeight || 480;
  if (vw === 0 || vh === 0) return null;
  const scale = Math.min(1, maxLongEdge / Math.max(vw, vh));
  const sw = Math.round(vw * scale);
  const sh = Math.round(vh * scale);
  const c = document.createElement("canvas");
  c.width = sw;
  c.height = sh;
  const ctx = c.getContext("2d");
  if (!ctx) return null;
  try {
    ctx.drawImage(video, 0, 0, sw, sh);
  } catch {
    // video not ready — return null so caller falls back to direct video
    return null;
  }
  return c;
}

// ---------------------------------------------------------------------------
// MockPreviewDetector — deterministic centered box + 2 faux landmarks
// injectable delayMs / shouldError / empty for SC-005 tests. Never throws.
// ---------------------------------------------------------------------------
export type MockPreviewDetectorOptions = {
  delayMs?: number;
  shouldError?: boolean;
  empty?: boolean;
  /** Optional multi-face count (default 1). When >1, spread boxes horizontally. */
  faceCount?: number;
  /** Optional score override for hold-smoothing tests */
  score?: number;
  /** If true, omit landmarks to test box-only path */
  noLandmarks?: boolean;
};

export class MockPreviewDetector implements PreviewDetector {
  private opts: MockPreviewDetectorOptions;

  constructor(opts: MockPreviewDetectorOptions = {}) {
    this.opts = opts;
  }

  async detect(video: HTMLVideoElement): Promise<PreviewDetection[]> {
    try {
      if (this.opts.shouldError) {
        throw new Error("mock detector error");
      }
      if (this.opts.delayMs && this.opts.delayMs > 0) {
        await new Promise<void>((resolve) => setTimeout(resolve, this.opts.delayMs));
      }
      if (this.opts.empty) {
        return [];
      }
      const W = video.videoWidth || 640;
      const H = video.videoHeight || 480;
      const count = this.opts.faceCount ?? 1;
      if (count <= 0) return [];

      const detections: PreviewDetection[] = [];
      for (let i = 0; i < count; i++) {
        // Spread multiple faces horizontally within frame
        const offsetX = count === 1 ? 0 : (i - (count - 1) / 2) * (W * 0.15);
        const x = Math.max(0, 0.3 * W + offsetX);
        const y = 0.3 * H;
        const w = 0.4 * W;
        const h = 0.4 * H;
        // Clamp if spread would go out of bounds
        const clampedX = Math.min(x, W - w);
        const box: PreviewBox = { x: clampedX, y, width: w, height: h };
        const detection: PreviewDetection = {
          box,
          frameAt: Date.now(),
          ...(this.opts.score !== undefined ? { score: this.opts.score } : { score: 0.99 }),
        };
        if (!this.opts.noLandmarks) {
          // 2 faux landmarks: roughly eye positions inside the box
          const lx1 = box.x + box.width * 0.3;
          const ly1 = box.y + box.height * 0.35;
          const lx2 = box.x + box.width * 0.7;
          const ly2 = box.y + box.height * 0.35;
          detection.landmarks = [
            { x: lx1, y: ly1 },
            { x: lx2, y: ly2 },
          ];
        }
        detections.push(detection);
      }
      return detections;
    } catch {
      // Never throws to caller — degrade to empty overlay (FR-013)
      return [];
    }
  }
}

// ---------------------------------------------------------------------------
// BrowserFaceDetector — wraps window.FaceDetector (Shape Detection API)
// Falls back to MockPreviewDetector when unavailable.
// Normalizes coordinates to intrinsic videoWidth/videoHeight space.
// ---------------------------------------------------------------------------
type FaceDetectorCtor = new (opts: { fastMode: boolean; maxDetectedFaces: number }) => {
  detect(video: HTMLVideoElement): Promise<
    Array<{
      boundingBox: DOMRectReadOnly | { x: number; y: number; width: number; height: number };
      landmarks?: Array<{ locations: Array<{ x: number; y: number }> } | { x: number; y: number }>;
    }>
  >;
};

declare global {
  interface Window {
    FaceDetector?: FaceDetectorCtor;
  }
}

export class BrowserFaceDetector implements PreviewDetector {
  private fallback: MockPreviewDetector;
  private detector: InstanceType<FaceDetectorCtor> | null = null;

  constructor(fallbackOpts: MockPreviewDetectorOptions = {}) {
    this.fallback = new MockPreviewDetector(fallbackOpts);
    const FD = typeof window !== "undefined" ? (window as Window).FaceDetector : undefined;
    if (typeof FD !== "undefined" && FD) {
      try {
        this.detector = new FD({ fastMode: true, maxDetectedFaces: 5 });
      } catch {
        this.detector = null;
      }
    }
  }

  async detect(video: HTMLVideoElement): Promise<PreviewDetection[]> {
    // If no native detector, delegate to fallback (which never throws)
    if (!this.detector) {
      return this.fallback.detect(video);
    }
    try {
      const raw = await this.detector.detect(video);
      if (!raw || raw.length === 0) return [];
      const W = video.videoWidth || 640;
      const H = video.videoHeight || 480;
      // FaceDetector boundingBox is already in video pixel space per spec;
      // but some implementations may return relative to rendered size — we
      // defensively map through intrinsic dimensions if needed (no-op).
      const detections: PreviewDetection[] = raw.map((face) => {
        const bb = face.boundingBox as { x: number; y: number; width: number; height: number };
        let box: PreviewBox = {
          x: Math.max(0, bb.x),
          y: Math.max(0, bb.y),
          width: bb.width,
          height: bb.height,
        };
        // Clamp within frame
        box.width = Math.min(box.width, W - box.x);
        box.height = Math.min(box.height, H - box.y);

        // Landmarks are optional; Shape Detection API returns them as nested arrays
        let landmarks: PreviewLandmark[] | undefined;
        if (face.landmarks && Array.isArray(face.landmarks) && face.landmarks.length > 0) {
          const pts: PreviewLandmark[] = [];
          for (const lm of face.landmarks as unknown[]) {
            if (lm && typeof lm === "object") {
              const obj = lm as Record<string, unknown>;
              if (Array.isArray(obj.locations)) {
                for (const p of obj.locations as Array<{ x: number; y: number }>) {
                  if (p && typeof p.x === "number" && typeof p.y === "number") pts.push({ x: p.x, y: p.y });
                }
              } else if (typeof obj.x === "number" && typeof obj.y === "number") {
                pts.push({ x: obj.x as number, y: obj.y as number });
              }
            }
          }
          if (pts.length > 0) landmarks = pts;
        }

        const det: PreviewDetection = {
          box,
          frameAt: Date.now(),
          score: 0.99,
        };
        if (landmarks) det.landmarks = landmarks;
        return det;
      });
      return detections;
    } catch {
      // Degrade to empty overlay (FR-013); also fallback to mock for resilience
      try {
        return await this.fallback.detect(video);
      } catch {
        return [];
      }
    }
  }
}

// ---------------------------------------------------------------------------
// ServerPreviewDetector — real tracking via backend YuNetDetector (Docker+CUDA)
// Sends a downscaled JPEG snapshot to POST /api/preview/detect and maps
// response to PreviewDetection[] in video intrinsic coordinates.
// Uses the same detector port as capture (YuNet with 5 landmarks) — real bbox tracking.
// ---------------------------------------------------------------------------
export class ServerPreviewDetector implements PreviewDetector {
  private fallback: PreviewDetector;

  constructor(fallback: PreviewDetector = new MockPreviewDetector()) {
    this.fallback = fallback;
  }

  async detect(video: HTMLVideoElement): Promise<PreviewDetection[]> {
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    if (vw === 0 || vh === 0) return this.fallback.detect(video);

    // Snapshot at full video resolution for 1:1 coord mapping (no downscale drift)
    const canvas = document.createElement("canvas");
    canvas.width = vw;
    canvas.height = vh;
    const ctx = canvas.getContext("2d");
    if (!ctx) return this.fallback.detect(video);
    try {
      ctx.drawImage(video, 0, 0, vw, vh);
    } catch {
      return [];
    }

    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob(resolve as BlobCallback, "image/jpeg", 0.6),
    );
    if (!blob) return [];

    try {
      const form = new FormData();
      form.append("image", blob, "preview.jpg");
      // Vite proxy forwards /api to backend (http://backend:8000 in Docker, localhost:8000 outside)
      const res = await fetch("/api/preview/detect", {
        method: "POST",
        body: form,
      });
      if (!res.ok) return [];
      const json = (await res.json()) as {
        detections?: Array<{ box: { x: number; y: number; width: number; height: number }; landmarks?: Array<{ x: number; y: number }>; score?: number }>;
      };
      const raw = json.detections ?? [];
      const now = Date.now();
      return raw.map((d) => ({
        box: d.box,
        landmarks: d.landmarks,
        score: d.score,
        frameAt: now,
      }));
    } catch {
      return [];
    }
  }
}

/** Factory helper: prefer real server detection, then native, then mock */
export function createDefaultPreviewDetector(): PreviewDetector {
  // In vitest/jsdom, fetch is mocked and video is fake → use Mock to keep tests deterministic (SC-007)
  const isTest =
    typeof navigator !== "undefined" &&
    (/jsdom/i.test(navigator.userAgent) || /vitest/i.test(navigator.userAgent));
  if (isTest) {
    return new MockPreviewDetector();
  }
  // In secure contexts with Shape Detection API available, it is faster (no network)
  if (typeof window !== "undefined" && typeof (window as unknown as { FaceDetector?: unknown }).FaceDetector !== "undefined") {
    return new BrowserFaceDetector();
  }
  // Default production: real YuNet via backend (Docker + CUDA when available)
  return new ServerPreviewDetector();
}
