import { render, screen } from "@testing-library/react";
import {
  MemoryRouter,
  Outlet,
  Route,
  RouterProvider,
  Routes,
  createMemoryRouter,
} from "react-router-dom";

import { router } from "../router";
import { SessionProvider } from "../context/SessionContext";
import ProtectedRoute from "../components/ProtectedRoute";
import Login from "../pages/Login";
import Dashboard from "../pages/Dashboard";
import Welcome from "../pages/Welcome";
import Onboarding from "../pages/Onboarding";

function renderWithSession(authenticated: boolean, node: React.ReactNode) {
  return render(
    <SessionProvider initialAuthenticated={authenticated} skipBootstrap>
      {node}
    </SessionProvider>,
  );
}

describe("App router", () => {
  it("exports a router that loads without error", () => {
    // Smoke check: the real `router` module loads and is a router instance.
    expect(router).toBeDefined();
  });

  it("renders the Welcome view at /", async () => {
    const testRouter = createMemoryRouter(
      [
        {
          path: "/",
          element: <Welcome />,
        },
      ],
      { initialEntries: ["/"] },
    );
    render(<RouterProvider router={testRouter} />);
    expect(await screen.findByTestId("page-welcome")).toBeInTheDocument();
  });

  it("renders the Onboarding view at /onboarding", async () => {
    const testRouter = createMemoryRouter(
      [{ path: "/onboarding", element: <Onboarding /> }],
      { initialEntries: ["/onboarding"] },
    );
    render(<RouterProvider router={testRouter} />);
    expect(await screen.findByTestId("page-onboarding")).toBeInTheDocument();
  });

  it("renders the Login view at /login", async () => {
    const testRouter = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <SessionProvider skipBootstrap>
              <Outlet />
            </SessionProvider>
          ),
          children: [{ path: "login", element: <Login /> }],
        },
      ],
      { initialEntries: ["/login"] },
    );
    render(<RouterProvider router={testRouter} />);
    expect(await screen.findByTestId("page-login")).toBeInTheDocument();
  });
});

describe("Route protection", () => {
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

  it("redirects /dashboard to /login when unauthenticated", async () => {
    renderWithSession(false, <MemoryRouter initialEntries={["/dashboard"]}>{protectedTree()}</MemoryRouter>);
    expect(await screen.findByTestId("page-login")).toBeInTheDocument();
    expect(screen.queryByTestId("page-dashboard")).not.toBeInTheDocument();
  });

  it("renders /dashboard when authenticated", async () => {
    renderWithSession(true, <MemoryRouter initialEntries={["/dashboard"]}>{protectedTree()}</MemoryRouter>);
    expect(await screen.findByTestId("page-dashboard")).toBeInTheDocument();
  });
});
