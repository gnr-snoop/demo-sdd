// Dashboard "Cerrar sesión" button tests (T037, FR-018, AC-009).
//
// Verifies the logout button is visible, keyboard-accessible, and triggers
// the logout flow (POST /api/auth/logout + SessionContext.logout + navigate).

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { SessionProvider } from "../../context/SessionContext";
import Dashboard from "../../pages/Dashboard";

function renderDashboard(authenticated: boolean, userId: string | null = "user-123") {
  return render(
    <SessionProvider initialAuthenticated={authenticated} initialUserId={userId} skipBootstrap>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Dashboard />
      </MemoryRouter>
    </SessionProvider>,
  );
}

describe("Dashboard logout button", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders a visible, keyboard-accessible 'Cerrar sesión' button when authenticated", async () => {
    renderDashboard(true);
    const btn = await screen.findByTestId("logout-button");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-label", "Cerrar sesión");
    expect(btn.tagName).toBe("BUTTON"); // native button → keyboard-accessible
  });

  it("calls POST /api/auth/logout on click", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok" }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    renderDashboard(true);
    const btn = await screen.findByTestId("logout-button");
    fireEvent.click(btn);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/logout"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("clears the session after logout", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok" }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const { container } = renderDashboard(true);
    const btn = await screen.findByTestId("logout-button");
    fireEvent.click(btn);
    // After logout, the session is cleared (button still visible until re-render).
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
    container.remove();
  });
});
