// Dashboard deletion UI flow tests (spec 006, T019).
//
// Walks: button visible & keyboard-accessible → confirm dialog → processing +
// button disabled → 200 success → session cleared, camera released, navigate
// to "/". Then 500 → actionable error with "Reintentar" + re-enabled button +
// no full reload. Then 401 → redirect to "/login". Cancel → no request,
// dashboard unchanged. State communication is not color-only (text + roles).

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Dashboard from "../src/pages/Dashboard";
import Welcome from "../src/pages/Welcome";
import Login from "../src/pages/Login";
import { SessionProvider } from "../src/context/SessionContext";

const FIXED_USER_ID = "00000000-0000-4000-8000-000000000001";

// --- Fake MediaStream for camera lifecycle assertions ---
function makeFakeStream() {
  const stop = vi.fn();
  const track = { stop };
  return { stream: { getTracks: () => [track] }, stop };
}

function stubMediaDevices(fakeStream: ReturnType<typeof makeFakeStream>) {
  const md = {
    getUserMedia: vi.fn().mockResolvedValue(fakeStream.stream),
  };
  Object.defineProperty(navigator, "mediaDevices", {
    value: md,
    configurable: true,
    writable: true,
  });
}

// --- Controllable fetch mock ---
type MockResponse = { ok: boolean; status: number; json: () => Promise<unknown> };

function makeResp(status: number, body: unknown): MockResponse {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function renderDashboardAt(initialPath = "/dashboard") {
  render(
    <SessionProvider initialAuthenticated initialUserId={FIXED_USER_ID} skipBootstrap>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  );
}

describe("Dashboard deletion UI (spec 006)", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
  });

  it("shows the 'Eliminar mis datos' button with an accessible name (keyboard-reachable)", async () => {
    const fake = makeFakeStream();
    stubMediaDevices(fake);
    renderDashboardAt();
    const btn = await screen.findByTestId("delete-face-data-button");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAccessibleName("Eliminar mis datos");
    // Keyboard-reachable: it is a real <button> (focusable via Tab).
    expect(btn.tagName).toBe("BUTTON");
  });

  it("confirm dialog appears on button press; cancel leaves the dashboard unchanged", async () => {
    const fake = makeFakeStream();
    stubMediaDevices(fake);
    renderDashboardAt();
    const btn = await screen.findByTestId("delete-face-data-button");
    fireEvent.click(btn);
    expect(await screen.findByTestId("delete-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("delete-confirm-message").textContent).toContain(
      "Esta acción eliminará tu perfil y plantilla facial de forma permanente. ¿Continuar?",
    );
    // Cancel → no request, dashboard unchanged.
    fireEvent.click(screen.getByTestId("delete-cancel-button"));
    await waitFor(() => {
      expect(screen.queryByTestId("delete-confirm-dialog")).not.toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("page-dashboard")).toBeInTheDocument();
  });

  it("200 success → processing state, then session cleared + camera released + navigate to /", async () => {
    const fake = makeFakeStream();
    stubMediaDevices(fake);
    fetchMock.mockResolvedValue(
      makeResp(200, { userId: FIXED_USER_ID, status: "deleted" }),
    );
    renderDashboardAt();

    const btn = await screen.findByTestId("delete-face-data-button");
    fireEvent.click(btn);
    fireEvent.click(await screen.findByTestId("delete-confirm-button"));

    // Processing state + button disabled.
    await waitFor(() => {
      expect(screen.getByTestId("delete-processing")).toBeInTheDocument();
    });
    expect(btn).toBeDisabled();

    // The DELETE was called with credentials.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(`/api/users/${FIXED_USER_ID}/face-data`),
        expect.objectContaining({ method: "DELETE", credentials: "include" }),
      );
    });

    // Navigated to "/" (Welcome) → Dashboard unmounted → camera stream released.
    await waitFor(() => {
      expect(screen.getByTestId("page-welcome")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("page-dashboard")).not.toBeInTheDocument();
    // Camera stream tracks were stopped on unmount.
    expect(fake.stop).toHaveBeenCalled();
  });

  it("500 internal_error → actionable error with 'Reintentar' + re-enabled button + no full reload", async () => {
    const fake = makeFakeStream();
    stubMediaDevices(fake);
    fetchMock.mockResolvedValue(
      makeResp(500, {
        error: { code: "internal_error", message: "Ocurrió un error al eliminar tus datos. Inténtalo de nuevo." },
      }),
    );
    renderDashboardAt();

    const btn = await screen.findByTestId("delete-face-data-button");
    fireEvent.click(btn);
    fireEvent.click(await screen.findByTestId("delete-confirm-button"));

    // Actionable error surface (text + role=alert — not color-only).
    const errSection = await screen.findByTestId("delete-error");
    expect(errSection).toBeInTheDocument();
    expect(screen.getByTestId("delete-error-message").textContent).toContain("eliminar tus datos");
    expect(screen.getByTestId("delete-retry-button")).toHaveAccessibleName(
      "Reintentar eliminación de mis datos",
    );
    // Button re-enabled (no longer disabled) — no full page reload occurred.
    await waitFor(() => {
      expect(btn).not.toBeDisabled();
    });
    expect(screen.getByTestId("page-dashboard")).toBeInTheDocument();
  });

  it("401 unauthenticated → redirect to /login", async () => {
    const fake = makeFakeStream();
    stubMediaDevices(fake);
    fetchMock.mockResolvedValue(
      makeResp(401, {
        error: { code: "unauthenticated", message: "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo." },
      }),
    );
    renderDashboardAt();

    const btn = await screen.findByTestId("delete-face-data-button");
    fireEvent.click(btn);
    fireEvent.click(await screen.findByTestId("delete-confirm-button"));

    // Redirected to /login.
    await waitFor(() => {
      expect(screen.getByTestId("page-login")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("page-dashboard")).not.toBeInTheDocument();
  });
});
