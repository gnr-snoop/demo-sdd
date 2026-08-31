// ProtectedRoute + SessionContext tests (T036, FR-004/FR-015, AC-006).
//
// Verifies that ProtectedRoute redirects to /login when unauthenticated and
// renders the outlet when authenticated. SessionContext bootstraps from
// GET /api/auth/me (mocked fetch).

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { SessionProvider } from "../../context/SessionContext";
import ProtectedRoute from "../../components/ProtectedRoute";
import Login from "../../pages/Login";
import Dashboard from "../../pages/Dashboard";

function protectedTree() {
  return (
    <Routes>
      <Route path="/" element={<Outlet />}>
        <Route path="login" element={<Login />} />
        <Route path="dashboard" element={<ProtectedRoute />}>
          <Route index element={<Dashboard />} />
        </Route>
      </Route>
    </Routes>
  );
}

function renderWithSession(authenticated: boolean, initialEntries: string[]) {
  return render(
    <SessionProvider initialAuthenticated={authenticated} skipBootstrap>
      <MemoryRouter initialEntries={initialEntries}>{protectedTree()}</MemoryRouter>
    </SessionProvider>,
  );
}

describe("ProtectedRoute gating", () => {
  it("redirects /dashboard to /login when unauthenticated", async () => {
    renderWithSession(false, ["/dashboard"]);
    expect(await screen.findByTestId("page-login")).toBeInTheDocument();
    expect(screen.queryByTestId("page-dashboard")).not.toBeInTheDocument();
  });

  it("renders /dashboard when authenticated", async () => {
    renderWithSession(true, ["/dashboard"]);
    expect(await screen.findByTestId("page-dashboard")).toBeInTheDocument();
  });
});

describe("SessionContext bootstrap from GET /api/auth/me", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("sets authenticated=true on 200 from /api/auth/me", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: true, userId: "abc-123" }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const { container } = render(
      <SessionProvider>
        <MemoryRouter initialEntries={["/dashboard"]}>{protectedTree()}</MemoryRouter>
      </SessionProvider>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId("page-dashboard")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining("/api/auth/me"));
    // Cleanup to avoid act warnings.
    container.remove();
  });

  it("sets authenticated=false on 401 from /api/auth/me", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: { code: "unauthenticated", message: "no" } }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const { container } = render(
      <SessionProvider>
        <MemoryRouter initialEntries={["/dashboard"]}>{protectedTree()}</MemoryRouter>
      </SessionProvider>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId("page-login")).toBeInTheDocument();
    });
    container.remove();
  });
});
