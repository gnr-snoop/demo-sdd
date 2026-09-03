import React from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS: Array<{ to: string; label: string }> = [
  { to: "/", label: "Inicio" },
  { to: "/onboarding", label: "Onboarding" },
  { to: "/login", label: "Login" },
  { to: "/dashboard", label: "Dashboard" },
];

const NAV_ICONS: Record<string, string> = {
  "/": "home",
  "/onboarding": "person_add",
  "/login": "face",
  "/dashboard": "dashboard",
};

const Nav: React.FC = () => {
  const location = useLocation();

  if (location.pathname.startsWith("/dashboard")) {
    return (
      <aside className="dashboard-sidebar" aria-label="Navegación del dashboard">
        <Link to="/" className="dashboard-brand brand-lockup" aria-label="BioScan, inicio">
          <span className="brand-mark" aria-hidden="true">
            <span className="material-symbols-outlined">fingerprint</span>
          </span>
          <span>
            <span className="brand-name">BioScan <em className="text-primary">ID</em></span>
            <span className="brand-caption">Acceso biométrico seguro</span>
          </span>
        </Link>
        <nav className="dashboard-nav" aria-label="Secciones">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link key={item.to} to={item.to} aria-current={active ? "page" : undefined}>
                <span className="material-symbols-outlined" aria-hidden="true">{NAV_ICONS[item.to]}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
    );
  }

  return (
    <header className="page-header">
      <div className="container page-header-inner">
        <Link to="/" className="brand-lockup" aria-label="BioScan, inicio">
          <span className="brand-mark" aria-hidden="true">
            <span className="material-symbols-outlined">fingerprint</span>
          </span>
          <span>
            <span className="brand-name">BioScan</span>
            <span className="brand-caption">Snoop x Claude</span>
          </span>
        </Link>
        <nav className="page-header-nav" aria-label="Navegación principal">
          {NAV_ITEMS.slice(0, 3).map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link key={item.to} to={item.to} aria-current={active ? "page" : undefined}>
                {item.label}
              </Link>
            );
          })}
          <Link className="header-portal-link" to="/login">
            <span className="material-symbols-outlined" aria-hidden="true">fingerprint</span>
            Acceder
          </Link>
        </nav>
      </div>
    </header>
  );
};

export default Nav;
