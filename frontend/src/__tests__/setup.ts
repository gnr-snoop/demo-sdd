import "@testing-library/jest-dom";
import { vi } from "vitest";

// ---------------------------------------------------------------------------
// Global test harness for preview overlay (011, T007 / research R-8)
// Mock helpers are additive: per-test beforeEach can still override
// navigator.mediaDevices.getUserMedia with its own spy. The defaults below
// provide a safe fallback when a test does not set one.
// ---------------------------------------------------------------------------

// Fake MediaStream factory used by default and available to tests
function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

// Ensure navigator.mediaDevices.getUserMedia exists (jsdom does not provide it)
if (typeof navigator !== "undefined") {
  const nav = navigator as unknown as Record<string, unknown>;
  if (!nav.mediaDevices) {
    Object.defineProperty(navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()),
      },
      writable: true,
      configurable: true,
    });
  } else {
    const md = nav.mediaDevices as Record<string, unknown>;
    if (!md.getUserMedia) {
      md.getUserMedia = vi.fn().mockResolvedValue(makeFakeStream());
    }
  }
}

// HTMLVideoElement intrinsic dimensions: 640×480 via configurable property
// (per-test code can still override via Object.defineProperty on an instance)
try {
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
    get() {
      // Allow per-instance override via _videoWidth if test sets it
      const self = this as unknown as Record<string, unknown>;
      if (typeof self._videoWidth === "number") return self._videoWidth as number;
      return 640;
    },
    configurable: true,
  });
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
    get() {
      const self = this as unknown as Record<string, unknown>;
      if (typeof self._videoHeight === "number") return self._videoHeight as number;
      return 480;
    },
    configurable: true,
  });
} catch {
  // Some jsdom versions freeze prototype — ignore
}

// window.FaceDetector stub: undefined by default (mock path), but allow tests
// to set window.FaceDetector = class MockFD {...} to exercise BrowserFaceDetector
if (typeof window !== "undefined" && !("FaceDetector" in window)) {
  // Leave undefined so BrowserFaceDetector falls back to mock; tests that want
  // native path can install a stub via (window as unknown as ...).FaceDetector = ...
}

// ResizeObserver mock (native in browser, absent in jsdom)
if (typeof window !== "undefined" && typeof (window as unknown as { ResizeObserver?: unknown }).ResizeObserver === "undefined") {
  class MockResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
    constructor(_cb: ResizeObserverCallback) {}
  }
  (window as unknown as Record<string, unknown>).ResizeObserver = MockResizeObserver;
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = MockResizeObserver;
}

// devicePixelRatio handling — jsdom defaults to 1; expose as configurable
if (typeof window !== "undefined" && window.devicePixelRatio === undefined) {
  Object.defineProperty(window, "devicePixelRatio", {
    value: 1,
    writable: true,
    configurable: true,
  });
}

// HTMLMediaElement.play mock — jsdom throws "Not implemented: HTMLMediaElement.prototype.play"
// We override to return a resolved Promise, matching browser behavior for tests.
if (typeof HTMLMediaElement !== "undefined") {
  try {
    const originalPlay = HTMLMediaElement.prototype.play;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (HTMLMediaElement.prototype as any).play = function () {
      // If test has mocked play via spy, let spy handle it; otherwise resolve
      if (this._mockPlay) return this._mockPlay();
      return Promise.resolve();
    };
    void originalPlay;
  } catch {
    // ignore
  }
}

// HTMLCanvasElement mocks for jsdom — provide minimal 2d context so overlay
// drawing can be exercised without a real canvas backend. Tests that need to
// assert draw calls can spy on ctx methods.
if (typeof HTMLCanvasElement !== "undefined") {
  const originalGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (
    this: HTMLCanvasElement,
    contextId: string,
    ...args: unknown[]
  ) {
    if (contextId === "2d") {
      // Return a lightweight mock 2d context; caller can still spy via vi.spyOn
      const ctx = {
        clearRect: vi.fn(),
        strokeRect: vi.fn(),
        strokeStyle: "",
        lineWidth: 0,
        beginPath: vi.fn(),
        arc: vi.fn(),
        fill: vi.fn(),
        fillStyle: "",
        drawImage: vi.fn(),
        setTransform: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        scale: vi.fn(),
        translate: vi.fn(),
        canvas: this,
      } as unknown as CanvasRenderingContext2D;
      return ctx;
    }
    // For other contexts, fallback to original (if any)
    return (originalGetContext as unknown as (...a: unknown[]) => unknown).apply(this, [contextId, ...args]) as unknown as CanvasRenderingContext2D;
  } as unknown as typeof HTMLCanvasElement.prototype.getContext;

  // toBlob mock — jsdom does not implement; tests for capture use their own mock,
  // but preview loop does not need it. Keep generic fallback.
  if (!HTMLCanvasElement.prototype.toBlob || HTMLCanvasElement.prototype.toBlob.toString().includes("Not implemented")) {
    HTMLCanvasElement.prototype.toBlob = function (callback: BlobCallback, _type?: string) {
      callback(new Blob(["fake"], { type: "image/jpeg" }));
    } as unknown as typeof HTMLCanvasElement.prototype.toBlob;
  }
}

// Silence jsdom HTMLMediaElement.play "Not implemented" console errors in test output
const originalConsoleError = console.error;
vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
  const msg = typeof args[0] === "string" ? args[0] as string : "";
  if (msg.includes("Not implemented: HTMLMediaElement.prototype.play")) return;
  return originalConsoleError.apply(console, args as never);
});
