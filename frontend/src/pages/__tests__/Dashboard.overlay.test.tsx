// Dashboard preview reuse (011, T022 — US2, SC-002, PRD §6.4)

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

import Dashboard from "../Dashboard";
import { SessionProvider } from "../../context/SessionContext";

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

describe("Dashboard preview reuse (T022, SC-002, PRD §6.4)", () => {
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
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "neutral", confidence: 0.8, disclaimer: "disclaimer" }),
    }) as unknown as typeof fetch;
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("dashboard renders preview with same toggle assertions; mood/age analysis buttons not interfered", async () => {
    render(
      <SessionProvider initialAuthenticated={true} initialUserId="user-1" skipBootstrap>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
    // Toggle appears after streamReady (next tick) — wait for it
    const toggle = await screen.findByTestId("overlay-toggle", {}, { timeout: 3000 });
    expect(toggle).toBeInTheDocument();

    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "true"));

    // Mood/age buttons still present and not interfered (PRD §6.4)
    expect(screen.getByTestId("mood-capture-button")).toBeInTheDocument();
    expect(screen.getByTestId("age-button")).toBeInTheDocument();

    // Capture via mood
    const moodBtn = screen.getByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  });
});
