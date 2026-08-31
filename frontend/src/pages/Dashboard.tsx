// Dashboard page — placeholder + "Cerrar sesión" button (T043, FR-018, AC-009).
//
// The logout button is keyboard-accessible (native <button> with aria-label),
// wired to POST /api/auth/logout + SessionContext.logout() + navigate to /login.
// Analysis content is stubbed (spec 004/005).

import React from "react";
import { useNavigate } from "react-router-dom";

import Nav from "../components/Nav";
import { useSession } from "../context/SessionContext";

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { logout, userId } = useSession();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-dashboard">Dashboard</h1>
        <p>Placeholder del dashboard (Fase 1). Los análisis de mood/edad se implementan en spec 004.</p>
        {userId && (
          <p>
            Sesión activa para el usuario: <code>{userId}</code>
          </p>
        )}
        <button
          type="button"
          onClick={handleLogout}
          aria-label="Cerrar sesión"
          data-testid="logout-button"
        >
          Cerrar sesión
        </button>
      </main>
    </div>
  );
};

export default Dashboard;
