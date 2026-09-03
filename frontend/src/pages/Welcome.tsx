import React from "react";
import { Link } from "react-router-dom";
import Nav from "../components/Nav";
import Footer from "../components/Footer";

const Welcome: React.FC = () => {
  return (
    <div className="page-frame page-centered">
      <Nav />
      <main className="hero">
        <section className="hero-copy">
          <div className="eyebrow">
            <span className="eyebrow-dot" aria-hidden="true" />
            Autenticación de nueva generación
          </div>
          <h1 data-testid="page-welcome">
            Acceso biométrico seguro para la <span>web moderna</span>
          </h1>
          <p className="hero-lede">
            Una experiencia de autenticación facial rápida, precisa y transparente para demostrar
            el futuro de las interfaces protegidas.
          </p>
          <div className="hero-actions">
            <Link className="button-primary" to="/onboarding">
              <span className="material-symbols-outlined" aria-hidden="true">face</span>
              Comenzar registro
            </Link>
            <Link className="button-secondary" to="/login">
              Ya tengo una cuenta
              <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
            </Link>
          </div>
          <div className="trust-row" aria-label="Características de seguridad">
            <span className="trust-item"><span className="material-symbols-outlined" aria-hidden="true">verified_user</span> Grado empresarial</span>
            <span className="trust-item"><span className="material-symbols-outlined" aria-hidden="true">lock</span> Datos transitorios</span>
          </div>
        </section>

        <section className="hero-visual" aria-label="Vista previa del escáner biométrico">
          <div className="scanner-card">
            <div className="scanner-card-header">
              <span className="scanner-active">Sistema activo</span>
              <span>BioScan ID</span>
            </div>
            <div className="scanner-view">
              <span className="material-symbols-outlined scanner-face" aria-hidden="true">face</span>
              <span className="viewfinder-line" aria-hidden="true" />
            </div>
            <div className="scanner-meta scanner-footer">
              <span>Protocolo Snoop</span>
              <span>Latencia ~42 ms</span>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
};

export default Welcome;
