import React from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS: Array<{ to: string; label: string }> = [
  { to: "/", label: "Inicio" },
  { to: "/onboarding", label: "Onboarding" },
  { to: "/login", label: "Login" },
  { to: "/dashboard", label: "Dashboard" },
];

const Nav: React.FC = () => {
  const location = useLocation();
  return (
    <nav aria-label="principal" style={{ display: "flex", gap: "1rem", padding: "0.5rem 1rem" }}>
      {NAV_ITEMS.map((item) => {
        const active = location.pathname === item.to;
        return (
          <Link
            key={item.to}
            to={item.to}
            style={{ fontWeight: active ? "bold" : "normal" }}
            aria-current={active ? "page" : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
};

export default Nav;
