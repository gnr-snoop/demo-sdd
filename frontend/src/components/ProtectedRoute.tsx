import React from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../context/SessionContext";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * Placeholder route-protection guard (FR-004). Redirects unauthenticated
 * visitors to /login. Real session/cookie enforcement is deferred to spec 003.
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated } = useSession();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export default ProtectedRoute;
