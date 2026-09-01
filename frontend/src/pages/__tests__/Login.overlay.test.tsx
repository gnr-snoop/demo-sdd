// Login preview reuse (011, T021 — US2, SC-002, PRD §6.3)

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

import Login from "../Login";
import { SessionProvider } from "../../context/SessionContext";

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

describe("Login preview reuse (T021, SC-002)", () => {
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
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ userId: "u1", status: "authenticated" }) }) as unknown as typeof fetch;
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("mount Login with mocked MediaDevices, same toggle assertions, login capture not interfered", async () => {
    render(
      <SessionProvider skipBootstrap>
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      </SessionProvider>,
    );

    const idInput = screen.getByTestId("identifier-input") as HTMLInputElement;
    fireEvent.change(idInput, { target: { value: "demo@example.com" } });
    const startBtn = screen.getByTestId("start-camera-button");
    fireEvent.click(startBtn);

    expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
    const toggle = await screen.findByTestId("overlay-toggle");
    expect(toggle).toBeInTheDocument();

    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "true"));

    // Identifier input still functional (PRD §6.3 not interfered)
    expect(screen.getByTestId("identifier-input")).toBeInTheDocument();

    // Capture via login flow
    const captureBtn = await screen.findByTestId("capture-button");
    fireEvent.click(captureBtn);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/auth/face-login"), expect.any(Object)));
  });
});
