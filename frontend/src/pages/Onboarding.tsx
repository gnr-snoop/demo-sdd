import React from "react";
import Nav from "../components/Nav";

const Onboarding: React.FC = () => {
  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-onboarding">Onboarding</h1>
        <p>Placeholder de onboarding (Fase 1). La captura y el registro se implementan en spec 002.</p>
      </main>
    </div>
  );
};

export default Onboarding;
