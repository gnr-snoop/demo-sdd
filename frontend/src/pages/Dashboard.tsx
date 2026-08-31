import React from "react";
import Nav from "../components/Nav";

const Dashboard: React.FC = () => {
  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-dashboard">Dashboard</h1>
        <p>Placeholder del dashboard (Fase 1). Los análisis de mood/edad se implementan en spec 004.</p>
      </main>
    </div>
  );
};

export default Dashboard;
