// Overlay tests for CameraCapture (011, T010-T012 — US1)
// Write FIRST, ensure FAIL before implementation (TDD). Now run against implemented component.

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import CameraCapture from "../CameraCapture";
import { MockPreviewDetector } from "../../services/previewDetector";

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

function mockGetUserMediaSuccess() {
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
    configurable: true,
  });
}

function mockGetUserMediaPending() {
  // Never resolves — keeps streamReady false
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn().mockImplementation(() => new Promise(() => {})) },
    configurable: true,
  });
}

// Helper to mock canvas 2d context with spies we can assert
function spyCanvasContext() {
  const drawMock = {
    clearRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    setTransform: vi.fn(),
    drawImage: vi.fn(),
  };
  const getCtxSpy = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation((type: string) => {
    if (type === "2d") return drawMock as unknown as CanvasRenderingContext2D;
    // fallback to original for other context types
    return document.createElement("canvas").getContext(type as unknown as string) as unknown as CanvasRenderingContext2D;
  });
  const toBlobSpy = vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(((callback: BlobCallback) => {
    callback(new Blob(["fake-jpeg"], { type: "image/jpeg" }));
  }) as unknown as typeof HTMLCanvasElement.prototype.toBlob);
  void toBlobSpy;
  void getCtxSpy;
  return { drawMock, original: HTMLCanvasElement.prototype.getContext };
}

describe("CameraCapture overlay — default OFF, hidden when not ready (T010, FR-015, SC-001 scenario 5)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("hides toggle when !streamReady (active true but stream pending) — queryByTestId is null, no detect called", async () => {
    mockGetUserMediaPending();
    const detector = new MockPreviewDetector();
    const spy = vi.spyOn(detector, "detect");

    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );

    // Wait a tick but getUserMedia never resolves → streamReady stays false
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(screen.queryByTestId("overlay-toggle")).toBeNull();
    expect(screen.queryByTestId("face-overlay")).not.toBeNull(); // canvas exists but hidden via display:none
    const overlay = screen.queryByTestId("face-overlay") as HTMLCanvasElement | null;
    if (overlay) {
      expect(overlay.style.display).toBe("none");
    }
    expect(spy).not.toHaveBeenCalled();
  });

  it("shows toggle when streamReady (active && streamReady) — default OFF plain preview, aria-pressed false", async () => {
    mockGetUserMediaSuccess();
    const detector = new MockPreviewDetector();
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
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    // Plain preview: overlay canvas exists but no strokes yet (clearRect may have been called on OFF)
    expect(screen.getByTestId("face-overlay")).toBeInTheDocument();
  });

  it("hides toggle when active is false even if detector would be ready", async () => {
    mockGetUserMediaSuccess();
    const detector = new MockPreviewDetector();
    const spy = vi.spyOn(detector, "detect");
    render(
      <CameraCapture
        active={false}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(screen.queryByTestId("overlay-toggle")).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("CameraCapture overlay — toggle ON shows bbox + landmarks (T011, FR-003/FR-004, SC-001)", () => {
  beforeEach(() => {
    mockGetUserMediaSuccess();
  });
  afterEach(() => vi.restoreAllMocks());

  it("after click toggle ON → aria-pressed true and draws box + landmarks", async () => {
    const detector = new MockPreviewDetector();
    const spy = vi.spyOn(detector, "detect");
    const { drawMock } = spyCanvasContext();

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
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");

    // Wait for the immediate tick to call detect and draw
    await waitFor(() => expect(spy).toHaveBeenCalled());

    // Allow async tick to complete and draw
    await waitFor(() => expect(drawMock.strokeRect).toHaveBeenCalled());
    // Box drawn
    expect(drawMock.strokeRect).toHaveBeenCalled();
    const call = drawMock.strokeRect.mock.calls[0];
    // Scaled centered box: x ~ 0.3*W scaled; ensure numbers are finite
    expect(call[0]).toBeGreaterThanOrEqual(0);
    expect(call[2]).toBeGreaterThan(0);
    // Landmarks: 2 dots → at least 2 arc calls
    expect(drawMock.arc).toHaveBeenCalled();
    expect(drawMock.arc.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("tracks after detector returns multiple calls (interval simulation)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const detector = new MockPreviewDetector();
    const spy = vi.spyOn(detector, "detect").mockResolvedValue([
      { box: { x: 10, y: 20, width: 100, height: 80 }, landmarks: [{ x: 30, y: 40 }], frameAt: Date.now(), score: 0.9 },
    ]);

    // Need real timers for getUserMedia
    mockGetUserMediaSuccess();
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

    // Immediate tick
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(spy).toHaveBeenCalledTimes(1);

    // Advance 200ms → next interval tick
    await act(async () => {
      await vi.advanceTimersByTimeAsync(210);
    });
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2);

    vi.useRealTimers();
  });
});

describe("CameraCapture overlay — toggle OFF clears without stream restart + capture neutrality (T012, FR-005/FR-007, SC-004)", () => {
  beforeEach(() => {
    mockGetUserMediaSuccess();
  });
  afterEach(() => vi.restoreAllMocks());

  it("click ON → OFF clears canvas within 200ms and does not stop MediaStream", async () => {
    const trackStop = vi.fn();
    const stream = {
      getTracks: () => [{ stop: trackStop } as unknown as MediaStreamTrack],
      getVideoTracks: () => [{ stop: trackStop } as unknown as MediaStreamTrack],
      getAudioTracks: () => [],
    } as unknown as MediaStream;
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
      configurable: true,
    });

    const detector = new MockPreviewDetector();
    const { drawMock } = spyCanvasContext();
    vi.spyOn(detector, "detect");

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
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "true"));

    // Clear mock to detect OFF clear
    drawMock.clearRect.mockClear();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    // Within 200ms, canvas cleared (synchronous clearOverlay on OFF)
    await waitFor(() => expect(drawMock.clearRect).toHaveBeenCalled(), { timeout: 300 });

    // MediaStream not stopped
    expect(trackStop).not.toHaveBeenCalled();
  });

  it("capture() via toBlob calls onCapture identically in OFF and ON states (FR-007)", async () => {
    const onCapture = vi.fn();
    const detector = new MockPreviewDetector();
    const spyCapture = spyCanvasContext();

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
    const captureBtn = await screen.findByTestId("capture-button");

    // Capture in OFF
    fireEvent.click(captureBtn);
    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1));
    const blobOff = onCapture.mock.calls[0][0] as Blob;
    expect(blobOff.type).toBe("image/jpeg");

    onCapture.mockClear();

    // Turn ON then capture
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "true"));
    fireEvent.click(captureBtn);
    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1));
    const blobOn = onCapture.mock.calls[0][0] as Blob;
    expect(blobOn.type).toBe("image/jpeg");
    // Both blobs same type/size (capture path unchanged)
    expect(blobOn.size).toBe(blobOff.size);
  });
});
