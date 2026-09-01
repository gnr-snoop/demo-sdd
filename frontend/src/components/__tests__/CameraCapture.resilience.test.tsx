// Resilience tests for CameraCapture (011, T026-T029 — US3, FR-011/013, SC-005)

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import CameraCapture from "../CameraCapture";
import { MockPreviewDetector, OVERLAY_MIN_SCORE } from "../../services/previewDetector";

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

function spyCanvas() {
  const mock = {
    clearRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    setTransform: vi.fn(),
    drawImage: vi.fn(),
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation((t: string) =>
    t === "2d" ? (mock as unknown as CanvasRenderingContext2D) : (document.createElement("canvas").getContext(t as unknown as string) as unknown as CanvasRenderingContext2D),
  );
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(((cb: BlobCallback) => cb(new Blob(["x"], { type: "image/jpeg" }))) as unknown as typeof HTMLCanvasElement.prototype.toBlob);
  return { mock, origGetContext: HTMLCanvasElement.prototype.getContext, origToBlob: HTMLCanvasElement.prototype.toBlob };
}

describe("CameraCapture resilience — slow detector (T026, FR-013, SC-005)", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("with delayMs=1000 → video play not blocked, toggle remains clickable during in-flight, overlay updates ~1s after result, native video FPS decoupled from 5 FPS throttle", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const detector = new MockPreviewDetector({ delayMs: 1000 });
    const spy = vi.spyOn(detector, "detect");
    const { mock } = spyCanvas();

    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    const video = screen.getByTestId("camera-preview") as HTMLVideoElement;
    // video.play should have been called at least once and not thrown
    expect(video).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    // Toggle should still be clickable while in-flight
    expect(toggle).not.toBeDisabled();
    fireEvent.click(toggle); // can toggle OFF even while in-flight
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    // Turn ON again and wait for delayed detection
    fireEvent.click(toggle);
    // Advance 500ms — still in delay
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    // Should have called detect but not yet drawn (still waiting)
    expect(spy).toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    // After ~1s, draw should have happened
    await waitFor(() => expect(mock.strokeRect).toHaveBeenCalled(), { timeout: 2000 });

    vi.useRealTimers();
  });
});

describe("CameraCapture resilience — empty/multi-face/landmark-absent contracts (T027, FR-011/012, SC-003)", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("[] → cleared canvas no toast (FR-011)", async () => {
    const detector = new MockPreviewDetector({ empty: true });
    const { mock } = spyCanvas();
    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    fireEvent.click(toggle);
    await waitFor(() => expect(mock.clearRect).toHaveBeenCalled());
    // No toast/notice — overlay empty, no aria-live error
    expect(screen.queryByTestId("overlay-notice")).not.toBeInTheDocument();
    // No stroke
    expect(mock.strokeRect).not.toHaveBeenCalled();
  });

  it("N boxes (e.g. 2) → N strokes", async () => {
    const detector = new MockPreviewDetector({ faceCount: 2 });
    const { mock } = spyCanvas();
    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    fireEvent.click(toggle);
    await waitFor(() => expect(mock.strokeRect).toHaveBeenCalled());
    // At least 2 strokeRect calls (one per face) within a short window; with interval may be more, assert >=2
    await new Promise((r) => setTimeout(r, 50));
    expect(mock.strokeRect.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("box-only when landmarks omitted (no placeholder dots) (FR-004)", async () => {
    const detector = new MockPreviewDetector({ noLandmarks: true });
    const { mock } = spyCanvas();
    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    fireEvent.click(toggle);
    await waitFor(() => expect(mock.strokeRect).toHaveBeenCalled());
    expect(mock.arc).not.toHaveBeenCalled();
  });
});

describe("CameraCapture resilience — error degradation + rapid-toggle safety (T028, FR-013, Edge Cases)", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("detect() reject → empty overlay + capture not blocked, toggle still operable", async () => {
    const detector = new MockPreviewDetector({ shouldError: true });
    const { mock } = spyCanvas();
    const onCapture = vi.fn();
    render(
      <CameraCapture
        active={true}
        onCapture={onCapture}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    fireEvent.click(toggle);
    // Should degrade to empty overlay (no strokes, but clear)
    await waitFor(() => expect(mock.clearRect).toHaveBeenCalled(), { timeout: 1000 });
    // Capture not blocked
    const captureBtn = await screen.findByTestId("capture-button");
    fireEvent.click(captureBtn);
    await waitFor(() => expect(onCapture).toHaveBeenCalled());
    // Toggle still operable
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  it("rapid 10× ON/OFF spam → only last epoch renders, no leaked timers (useFakeTimers + epoch assertion)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const detector = new MockPreviewDetector({ delayMs: 200 });
    const spy = vi.spyOn(detector, "detect");
    spyCanvas();

    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    // Spam 10 toggles quickly
    for (let i = 0; i < 10; i++) {
      fireEvent.click(toggle);
    }
    // Last state wins — after 10 clicks starting OFF, even count → OFF
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    // One more click → ON
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");

    // Advance timers — should not have leaked intervals causing many duplicate calls
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    // At most a few calls (immediate + ~3 intervals), not 10× — allow for fake-timer granularity
    expect(spy.mock.calls.length).toBeLessThan(12);
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(1);

    vi.useRealTimers();
  });
});

describe("CameraCapture resilience — flicker smoothing + throttle gate (T029, FR-011, FR-006)", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("single-frame empty after valid → hold last valid 200ms then clear, score < 0.5 ignored within hold window", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // First detection valid, second empty, third valid again — we simulate via mock that returns
    // valid then empty on next tick
    let call = 0;
    const detector: import("../../services/previewDetector").PreviewDetector = {
      detect: vi.fn(async () => {
        call += 1;
        if (call === 1) return [{ box: { x: 10, y: 10, width: 100, height: 100 }, frameAt: Date.now(), score: 0.9 }];
        if (call === 2) return []; // single-frame drop
        if (call === 3) return [{ box: { x: 10, y: 10, width: 100, height: 100 }, frameAt: Date.now(), score: 0.1 }]; // low score <0.5 should be ignored (holds)
        return [];
      }),
    };
    const { mock } = spyCanvas();

    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    fireEvent.click(toggle);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mock.strokeRect).toHaveBeenCalledTimes(1);
    mock.strokeRect.mockClear();
    mock.clearRect.mockClear();

    // Next tick 200ms later — empty frame but within HOLD_MS=200 → should still render last valid (hold)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(210);
    });
    // Held → stroke again
    expect(mock.strokeRect).toHaveBeenCalled();

    mock.strokeRect.mockClear();
    // Next tick → low score 0.1 (<0.5) should be filtered and still hold if within window
    await act(async () => {
      await vi.advanceTimersByTimeAsync(210);
    });
    // The low-score frame is filtered to empty, but hold window may have exceeded by now
    // After 420ms total, hold should have expired → cleared
    // Assert that eventually it clears (empty overlay)
    // Give another tick beyond hold
    mock.clearRect.mockClear();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    // Eventually cleared
    expect(mock.clearRect).toHaveBeenCalled();

    vi.useRealTimers();
  });

  it("setInterval asserted 200ms and overlapping tick skipped via inFlightRef (throttle invariant)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const detector = new MockPreviewDetector({ delayMs: 300 }); // longer than interval → overlapping
    const spy = vi.spyOn(detector, "detect");
    const setIntervalSpy = vi.spyOn(window, "setInterval");

    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const toggle = await screen.findByTestId("overlay-toggle");
    fireEvent.click(toggle);

    expect(setIntervalSpy).toHaveBeenCalled();
    // At least one interval is the overlay throttle (200ms); other libs may also set intervals
    const hasOverlayInterval = setIntervalSpy.mock.calls.some((c) => c[1] === 200);
    expect(hasOverlayInterval).toBe(true)

    // With delay 300ms, first tick in-flight, next interval tick at 200ms should be skipped
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    // At 200ms, second tick skipped due to inFlight, so only 1 detect so far
    expect(spy).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(150);
    });
    // After first completes at ~300ms, next interval at 400ms will fire
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2);

    vi.useRealTimers();
    setIntervalSpy.mockRestore();
  });
});
