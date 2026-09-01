// Dashboard tests (spec 004 + spec 005, FR-008..FR-013/FR-019).
//
// Mocks navigator.mediaDevices.getUserMedia + global.fetch + canvas. Walks the
// mood state machine: idle → button-press → result, and recoverable error →
// retry. Asserts mood result + disclaimer render, ≈NN% confidence rendering,
// error surface + retry, ENABLED age button (spec 005 — placeholder removed),
// keyboard access, no-color-only state, and stream release on unmount.
//
// Spec 005 additions: age button enabled + keyboard-accessible + no placeholder,
// age result rendering (range + point + disclaimer), age error + retry, shared
// capture mutex (both buttons disable while either in flight), independent
// mood/age result surfaces.

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { SessionProvider } from "../../context/SessionContext";
import Dashboard from "../../pages/Dashboard";

// --- Fake MediaStream -----------------------------------------------------
function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn(), kind: "video" } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

const MOOD_DISCLAIMER =
  "Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional.";
const AGE_DISCLAIMER =
  "La edad es una estimación visual y puede contener un margen de error significativo.";

function renderDashboard() {
  return render(
    <SessionProvider initialAuthenticated={true} initialUserId="user-1" skipBootstrap>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Dashboard />
      </MemoryRouter>
    </SessionProvider>,
  );
}

function mockFetchOnce(response: { ok: boolean; json?: () => Promise<unknown> }) {
  const fn = vi.fn().mockResolvedValue({
    ok: response.ok,
    json: response.json ?? (async () => ({})),
  });
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

describe("Dashboard — mood analysis", () => {
  let originalFetch: typeof global.fetch;
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    originalFetch = global.fetch;
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
    // jsdom does not implement canvas 2d / toBlob — mock both.
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      drawImage: vi.fn(),
    })) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.toBlob = vi.fn(
      (callback: BlobCallback, _type: string, _quality?: unknown) => {
        callback(new Blob(["fake-jpeg"], { type: "image/jpeg" }));
      },
    ) as HTMLCanvasElement["toBlob"];
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the dashboard, camera preview, mood button, and ENABLED age button (spec 005)", async () => {
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "feliz", confidence: 0.8, disclaimer: MOOD_DISCLAIMER }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    expect(await screen.findByTestId("page-dashboard")).toBeInTheDocument();
    expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    expect(moodBtn).toBeInTheDocument();
    expect(moodBtn).toHaveAttribute("aria-label", "Detectar estado de ánimo");
    // Spec 005 (FR-013): age button is enabled, no "Próximamente" placeholder.
    const ageBtn = await screen.findByTestId("age-button");
    expect(ageBtn).not.toBeDisabled();
    expect(ageBtn).toHaveAttribute("aria-label", "Calcular edad");
    expect(screen.queryByTestId("age-placeholder")).not.toBeInTheDocument();
  });

  it("walks idle → button-press → result with ≈NN% confidence + disclaimer", async () => {
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "feliz", confidence: 0.8123, disclaimer: MOOD_DISCLAIMER }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    // Result renders (FR-003/FR-012a). The loading indicator is transient and
    // may be batched away by React 18 automatic batching — assert the result.
    const result = await screen.findByTestId("mood-result");
    expect(result).toBeInTheDocument();
    expect(screen.getByTestId("mood-label")).toHaveTextContent("feliz");
    // ≈NN% rendering (0.8123 → ≈81%).
    expect(screen.getByTestId("mood-confidence")).toHaveTextContent("≈81%");
    expect(screen.getByTestId("mood-disclaimer")).toHaveTextContent(MOOD_DISCLAIMER);
    // Loading indicator gone after result.
    expect(screen.queryByTestId("mood-loading")).not.toBeInTheDocument();
  });

  it("renders result without confidence when confidence is null (FR-012a)", async () => {
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "no concluyente", confidence: null, disclaimer: MOOD_DISCLAIMER }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    await screen.findByTestId("mood-result");
    expect(screen.getByTestId("mood-label")).toHaveTextContent("no concluyente");
    expect(screen.queryByTestId("mood-confidence")).not.toBeInTheDocument();
  });

  it("shows recoverable error surface + retry on failure (FR-011/FR-015)", async () => {
    mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: { code: "no_face", message: "No se detectó rostro." } }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    const errorSection = await screen.findByTestId("mood-error");
    expect(errorSection).toBeInTheDocument();
    expect(errorSection).toHaveTextContent("No se detectó rostro.");
    const retryBtn = screen.getByTestId("mood-retry-button");
    expect(retryBtn).toBeInTheDocument();
    // Retry returns to idle (error surface gone).
    fireEvent.click(retryBtn);
    await waitFor(() => {
      expect(screen.queryByTestId("mood-error")).not.toBeInTheDocument();
    });
  });

  it("disables the mood button while in flight (FR-014, one capture at a time)", async () => {
    // A fetch we control manually so we can observe the processing state.
    let resolveFetch!: (v: unknown) => void;
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve;
    });
    mockFetch = vi.fn().mockReturnValue(fetchPromise);
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    // While in flight: button disabled + loading indicator.
    await waitFor(() => expect(moodBtn).toBeDisabled());
    expect(screen.getByTestId("mood-loading")).toBeInTheDocument();
    // Resolve → result + button re-enabled.
    await act(async () => {
      resolveFetch({
        ok: true,
        json: async () => ({ label: "neutral", confidence: 0.74, disclaimer: MOOD_DISCLAIMER }),
      });
    });
    await screen.findByTestId("mood-result");
    await waitFor(() => {
      expect(screen.getByTestId("mood-capture-button")).not.toBeDisabled();
    });
  });

  it("shows camera-permission-denied surface + retry (FR-012c, no backend call)", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    mockFetch = vi.fn();
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const camError = await screen.findByTestId("mood-camera-error");
    expect(camError).toBeInTheDocument();
    const retryBtn = screen.getByTestId("mood-camera-retry-button");
    fireEvent.click(retryBtn);
    await waitFor(() => {
      expect(screen.queryByTestId("mood-camera-error")).not.toBeInTheDocument();
    });
    // No backend call was made (FR-012c).
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("releases the camera stream on unmount (FR-012b)", async () => {
    const trackStop = vi.fn();
    const track = { stop: trackStop, kind: "video" } as unknown as MediaStreamTrack;
    const stream = {
      getTracks: () => [track],
      getVideoTracks: () => [track],
      getAudioTracks: () => [],
    } as unknown as MediaStream;
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(stream) },
      configurable: true,
    });
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "neutral", confidence: 0.74, disclaimer: MOOD_DISCLAIMER }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const { unmount } = renderDashboard();
    await screen.findByTestId("camera-preview");
    unmount();
    expect(trackStop).toHaveBeenCalled();
  });

  it("mood button is keyboard-accessible (focusable, operable, descriptive name)", async () => {
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "feliz", confidence: 0.8, disclaimer: MOOD_DISCLAIMER }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    // Focusable.
    moodBtn.focus();
    expect(moodBtn).toHaveFocus();
    // Descriptive accessible name (FR-012).
    expect(moodBtn).toHaveAttribute("aria-label", "Detectar estado de ánimo");
    // Operable via click (native <button> — Enter/Space activate by default).
    fireEvent.click(moodBtn);
    await screen.findByTestId("mood-result");
  });

  it("does not rely exclusively on color — mood label has text content (FR-012)", async () => {
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ label: "triste", confidence: 0.6, disclaimer: MOOD_DISCLAIMER }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    const label = await screen.findByTestId("mood-label");
    // The label carries the text "triste" (not color-only).
    expect(label).toHaveTextContent("triste");
  });
});

// ==========================================================================
// Spec 005: age analysis dashboard tests (T027/T024)
// ==========================================================================
describe("Dashboard — age analysis (spec 005)", () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
      configurable: true,
    });
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      drawImage: vi.fn(),
    })) as unknown as HTMLCanvasElement["getContext"];
    HTMLCanvasElement.prototype.toBlob = vi.fn(
      (callback: BlobCallback, _type: string, _quality?: unknown) => {
        callback(new Blob(["fake-jpeg"], { type: "image/jpeg" }));
      },
    ) as HTMLCanvasElement["toBlob"];
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("age button is keyboard-accessible with a descriptive name (FR-012/FR-013)", async () => {
    mockFetchOnce({ ok: true, json: async () => ({ estimatedAge: 32, range: { min: 27, max: 37 }, disclaimer: AGE_DISCLAIMER }) });
    renderDashboard();
    const ageBtn = await screen.findByTestId("age-button");
    ageBtn.focus();
    expect(ageBtn).toHaveFocus();
    expect(ageBtn).toHaveAttribute("aria-label", "Calcular edad");
  });

  it("walks age idle → press → result (range + point + disclaimer, FR-012a)", async () => {
    mockFetchOnce({
      ok: true,
      json: async () => ({ estimatedAge: 32, range: { min: 27, max: 37 }, disclaimer: AGE_DISCLAIMER }),
    });
    renderDashboard();
    const ageBtn = await screen.findByTestId("age-button");
    fireEvent.click(ageBtn);
    const result = await screen.findByTestId("age-result");
    expect(result).toBeInTheDocument();
    expect(screen.getByTestId("age-range")).toHaveTextContent("27–37 años");
    expect(screen.getByTestId("age-point")).toHaveTextContent("≈32 años");
    expect(screen.getByTestId("age-disclaimer")).toHaveTextContent(AGE_DISCLAIMER);
  });

  it("renders only the point estimate when range is narrow (min == max, FR-012a)", async () => {
    mockFetchOnce({
      ok: true,
      json: async () => ({ estimatedAge: 42, range: { min: 42, max: 42 }, disclaimer: AGE_DISCLAIMER }),
    });
    renderDashboard();
    const ageBtn = await screen.findByTestId("age-button");
    fireEvent.click(ageBtn);
    await screen.findByTestId("age-result");
    expect(screen.queryByTestId("age-range")).not.toBeInTheDocument();
    expect(screen.getByTestId("age-point")).toHaveTextContent("≈42 años");
  });

  it("shows age error surface + retry on failure (FR-011/FR-015)", async () => {
    mockFetchOnce({
      ok: false,
      json: async () => ({ error: { code: "no_face", message: "No se detectó rostro." } }),
    });
    renderDashboard();
    const ageBtn = await screen.findByTestId("age-button");
    fireEvent.click(ageBtn);
    const errorSection = await screen.findByTestId("age-error");
    expect(errorSection).toHaveTextContent("No se detectó rostro.");
    fireEvent.click(screen.getByTestId("age-retry-button"));
    await waitFor(() => {
      expect(screen.queryByTestId("age-error")).not.toBeInTheDocument();
    });
  });

  it("shared capture mutex: both buttons disable while age in flight (FR-014)", async () => {
    let resolveFetch!: (v: unknown) => void;
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve;
    });
    global.fetch = vi.fn().mockReturnValue(fetchPromise) as unknown as typeof fetch;

    renderDashboard();
    const moodBtn = await screen.findByTestId("mood-capture-button");
    const ageBtn = await screen.findByTestId("age-button");
    // Press age → both buttons disable.
    fireEvent.click(ageBtn);
    await waitFor(() => expect(ageBtn).toBeDisabled());
    await waitFor(() => expect(moodBtn).toBeDisabled());
    expect(screen.getByTestId("age-loading")).toBeInTheDocument();
    // Resolve → both re-enable.
    await act(async () => {
      resolveFetch({
        ok: true,
        json: async () => ({ estimatedAge: 32, range: { min: 27, max: 37 }, disclaimer: AGE_DISCLAIMER }),
      });
    });
    await screen.findByTestId("age-result");
    await waitFor(() => expect(screen.getByTestId("age-button")).not.toBeDisabled());
    await waitFor(() => expect(screen.getByTestId("mood-capture-button")).not.toBeDisabled());
  });

  it("shared capture mutex: pressing mood during age in-flight is ignored (FR-014)", async () => {
    let resolveAge!: (v: unknown) => void;
    let resolveMood!: (v: unknown) => void;
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) {
        // First call: age.
        return new Promise((r) => { resolveAge = r; });
      }
      // Second call would be mood — but it should never happen.
      return new Promise((r) => { resolveMood = r; });
    }) as unknown as typeof fetch;

    renderDashboard();
    const ageBtn = await screen.findByTestId("age-button");
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(ageBtn);
    await waitFor(() => expect(ageBtn).toBeDisabled());
    // Press mood while age in flight → ignored (button disabled).
    fireEvent.click(moodBtn);
    expect(callCount).toBe(1); // only the age request was made
    // Resolve age.
    await act(async () => {
      resolveAge({
        ok: true,
        json: async () => ({ estimatedAge: 32, range: { min: 27, max: 37 }, disclaimer: AGE_DISCLAIMER }),
      });
    });
    await screen.findByTestId("age-result");
  });

  it("independent surfaces: age result not cleared by mood analysis (SC-018)", async () => {
    // First call: age. Second call: mood.
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ estimatedAge: 32, range: { min: 27, max: 37 }, disclaimer: AGE_DISCLAIMER }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ label: "feliz", confidence: 0.8, disclaimer: MOOD_DISCLAIMER }),
      });
    }) as unknown as typeof fetch;

    renderDashboard();
    const ageBtn = await screen.findByTestId("age-button");
    fireEvent.click(ageBtn);
    await screen.findByTestId("age-result");
    // Now run mood — age result should still be visible.
    const moodBtn = await screen.findByTestId("mood-capture-button");
    fireEvent.click(moodBtn);
    await screen.findByTestId("mood-result");
    expect(screen.getByTestId("age-result")).toBeInTheDocument();
  });

  it("age camera-permission-denied surface + retry (FR-012c, no backend call)", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    renderDashboard();
    const camError = await screen.findByTestId("age-camera-error");
    expect(camError).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("age-camera-retry-button"));
    await waitFor(() => {
      expect(screen.queryByTestId("age-camera-error")).not.toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

