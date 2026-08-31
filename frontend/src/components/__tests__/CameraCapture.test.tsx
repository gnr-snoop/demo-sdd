// Component test for CameraCapture (T026, FR-012/FR-015).
//
// Mocks navigator.mediaDevices.getUserMedia to yield a fake stream; asserts the
// preview renders and still capture produces a JPEG blob. The capture button
// is keyboard-accessible with an aria-label.

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import CameraCapture from "../CameraCapture";

// --- Fake MediaStream -----------------------------------------------------
function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

describe("CameraCapture", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()),
      },
      configurable: true,
    });
  });

  it("renders a preview and requests the camera when active", async () => {
    const onCapture = vi.fn();
    render(
      <CameraCapture
        active={true}
        onCapture={onCapture}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
      />,
    );
    expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ video: true });
  });

  it("renders an accessible capture button after the stream is ready", async () => {
    const onCapture = vi.fn();
    render(
      <CameraCapture
        active={true}
        onCapture={onCapture}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
      />,
    );
    const btn = await screen.findByTestId("capture-button");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-label", "Capturar rostro");
  });

  it("produces a JPEG blob on capture", async () => {
    const onCapture = vi.fn();
    // jsdom does not implement canvas 2d context / toBlob — mock both.
    const realGetContext = HTMLCanvasElement.prototype.getContext;
    const realToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      drawImage: vi.fn(),
    })) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.toBlob = vi.fn(
      (callback: BlobCallback, _type: string, _quality?: unknown) => {
        callback(new Blob(["fake-jpeg"], { type: "image/jpeg" }));
      },
    ) as HTMLCanvasElement["toBlob"];

    try {
      render(
        <CameraCapture
          active={true}
          onCapture={onCapture}
          onPermissionGranted={vi.fn()}
          onPermissionDenied={vi.fn()}
        />,
      );
      const btn = await screen.findByTestId("capture-button");
      fireEvent.click(btn);
      await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1));
      const blob = onCapture.mock.calls[0][0] as Blob;
      expect(blob).toBeInstanceOf(Blob);
      expect(blob.type).toBe("image/jpeg");
    } finally {
      HTMLCanvasElement.prototype.getContext = realGetContext;
      HTMLCanvasElement.prototype.toBlob = realToBlob;
    }
  });

  it("calls onPermissionDenied when getUserMedia rejects", async () => {
    const onPermissionDenied = vi.fn();
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={onPermissionDenied}
      />,
    );
    await waitFor(() => expect(onPermissionDenied).toHaveBeenCalledTimes(1));
  });

  it("disables the capture button when disabled prop is true", async () => {
    render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        disabled={true}
      />,
    );
    const btn = await screen.findByTestId("capture-button");
    expect(btn).toBeDisabled();
  });
});
