import { Outlet, createBrowserRouter, RouteObject } from "react-router-dom";
import { SessionProvider } from "./context/SessionContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Welcome from "./pages/Welcome";
import Onboarding from "./pages/Onboarding";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";

// Four routes (FR-003): /, /onboarding, /login, /dashboard.
// /dashboard is wrapped in ProtectedRoute (FR-004) — redirects to /login when
// no session placeholder is present. SessionProvider wraps the outlet so the
// in-memory session flag is available to all child routes.
const routes: RouteObject[] = [
  {
    path: "/",
    element: (
      <SessionProvider>
        <Outlet />
      </SessionProvider>
    ),
    children: [
      { index: true, element: <Welcome /> },
      { path: "onboarding", element: <Onboarding /> },
      { path: "login", element: <Login /> },
      {
        path: "dashboard",
        element: (
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        ),
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
