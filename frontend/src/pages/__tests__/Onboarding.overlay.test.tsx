// Onboarding preview reuse (011, T020 — US2, SC-002)

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

import Onboarding from "../Onboarding";

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

describe("Onboarding preview reuse (T020, SC-002)", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ({
      drawImage: vi.fn(),
      clearRect: vi.fn(),
      strokeRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      setTransform: vi.fn(),
    }) as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(((cb: BlobCallback) => cb(new Blob(["x"], { type: "image/jpeg" }))) as unknown as typeof HTMLCanvasElement.prototype.toBlob);
    // Mock fetch for onboarding capture
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ userId: "u1", identifier: "demo@example.com", status: "enrolled" }) }) as unknown as typeof fetch;
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("mount Onboarding with mocked MediaDevices, toggle present when streamReady, ON shows box, capture succeeds", async () => {
    render(
      <MemoryRouter>
        <Onboarding />
      </MemoryRouter>,
    );

    // Start camera via onboarding flow: set identifier + consent + click Solicitar cámara
    const idInput = screen.getByTestId("identifier-input") as HTMLInputElement;
    fireEvent.change(idInput, { target: { value: "demo@example.com" } });
    const consent = screen.getByTestId("consent-checkbox") as HTMLInputElement;
    fireEvent.click(consent);
    const startBtn = screen.getByTestId("start-camera-button");
    fireEvent.click(startBtn);

    // Camera preview appears
    expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
    // Toggle appears when streamReady
    const toggle = await screen.findByTestId("overlay-toggle");
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    // Toggle ON shows overlay (aria-pressed true)
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "true"));

    // Capture succeeds (onCapture → fetch)
    const captureBtn = await screen.findByTestId("capture-button");
    fireEvent.click(captureBtn);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/onboarding"), expect.any(Object)));
  });
});
