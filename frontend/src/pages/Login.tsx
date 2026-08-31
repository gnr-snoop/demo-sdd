import React from "react";
import Nav from "../components/Nav";

const Login: React.FC = () => {
  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-login">Login</h1>
        <p>Placeholder de login (Fase 1). La verificación facial se implementa en spec 003.</p>
      </main>
    </div>
  );
};

export default Login;
