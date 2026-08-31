import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useSession } from "../context/SessionContext";

/**
 * Real route-protection guard (T042, FR-004/FR-015, AC-006).
 * Redirects unauthenticated visitors to /login. Renders <Outlet/> when
 * authenticated. Shows nothing while the session is bootstrapping.
 */
const ProtectedRoute: React.FC = () => {
  const { authenticated, loading } = useSession();
  if (loading) {
    return null; // wait for GET /api/auth/me to resolve
  }
  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
};

export default ProtectedRoute;
