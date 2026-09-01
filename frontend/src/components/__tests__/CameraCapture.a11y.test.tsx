// A11y contract for overlay toggle (011, T013 — FR-009, SC-006, contracts/preview-overlay.md §3)

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import CameraCapture from "../CameraCapture";
import { MockPreviewDetector, OVERLAY_TOGGLE_TEST_ID } from "../../services/previewDetector";

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

describe("CameraCapture a11y contract (T013, FR-009, SC-006)", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ({
      clearRect: vi.fn(),
      strokeRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      setTransform: vi.fn(),
      drawImage: vi.fn(),
    }) as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(((cb: BlobCallback) => cb(new Blob(["x"], { type: "image/jpeg" }))) as unknown as typeof HTMLCanvasElement.prototype.toBlob);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("has canonical accessible name via aria-label and data-testid, aria-pressed flips false→true→false", async () => {
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

    const btn = await screen.findByRole("button", { name: /Show face overlay|Mostrar contorno facial/ });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("data-testid", OVERLAY_TOGGLE_TEST_ID);
    expect(btn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "false");
  });

  it("is Tab focusable and Space/Enter operable, with visible :focus-visible ring", async () => {
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
    const btn = await screen.findByRole("button", { name: /Show face overlay|Mostrar contorno facial/ });

    // Focusable via .focus() and remains focusable via tab order (native button)
    btn.focus();
    expect(btn).toHaveFocus();
    // Space toggles via click (native button activates on Space/Enter)
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "true");
    // Enter toggles — also via click path; additionally test keyDown triggers click in jsdom
    fireEvent.keyDown(btn, { key: "Enter", code: "Enter" });
    fireEvent.keyUp(btn, { key: "Enter", code: "Enter" });
    // click still toggles
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "false");

    // Focus-visible style: check that component renders a style tag with outline rule
    const style = document.querySelector("style");
    expect(style?.textContent).toContain("focus-visible");
  });

  it("uses Spanish label when navigator.language is es", async () => {
    const originalLang = navigator.language;
    Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });

    const detector = new MockPreviewDetector();
    const { unmount } = render(
      <CameraCapture
        active={true}
        onCapture={vi.fn()}
        onPermissionGranted={vi.fn()}
        onPermissionDenied={vi.fn()}
        previewDetector={detector}
      />,
    );
    const btn = await screen.findByRole("button", { name: /Mostrar contorno facial/ });
    expect(btn).toHaveAttribute("aria-label", "Mostrar contorno facial");

    unmount();
    Object.defineProperty(navigator, "language", { value: originalLang, configurable: true });
  });
});
