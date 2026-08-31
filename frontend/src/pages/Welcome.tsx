import React from "react";
import Nav from "../components/Nav";

const Welcome: React.FC = () => {
  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-welcome">Bienvenido a Face Insight Demo</h1>
        <p>Esqueleto de la aplicación (Fase 1). Navega a Onboarding o Login para continuar.</p>
      </main>
    </div>
  );
};

export default Welcome;
