// Onboarding page — identifier + consent + camera + state machine (T030, FR-011..FR-013/FR-015).
//
// Drives the PRD §6.2 seven-state machine via useOnboardingMachine and the
// CameraCapture component. Maps backend error codes to actionable messages.

import React, { useState } from "react";
import { Link } from "react-router-dom";

import Nav from "../components/Nav";
import Footer from "../components/Footer";
import CameraCapture from "../components/CameraCapture";
import { useOnboardingMachine } from "../hooks/useOnboardingMachine";
import { api, OnboardingApiError } from "../services/api";

const Onboarding: React.FC = () => {
  const machine = useOnboardingMachine();
  const [identifier, setIdentifier] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [successUserId, setSuccessUserId] = useState<string>("");

  const identifierValid = identifier.trim().length >= 3;
  const canStart = identifierValid && consentAccepted && machine.state === "initial";

  const handleStartCamera = () => {
    setErrorMessage("");
    setCameraActive(true);
    machine.send("REQUEST_PERMISSION");
  };

  const handlePermissionGranted = () => {
    machine.send("PERMISSION_GRANTED");
  };

  const handlePermissionDenied = () => {
    setErrorMessage("No se pudo acceder a la cámara. Revisa los permisos del navegador e inténtalo de nuevo.");
    machine.send("PERMISSION_DENIED");
  };

  const handleCapture = async (blob: Blob) => {
    machine.send("CAPTURE");
    setErrorMessage("");
    try {
      const result = await api.onboarding(identifier.trim(), consentAccepted, blob);
      setSuccessUserId(result.userId);
      machine.send("SUCCEEDED");
    } catch (err) {
      const message =
        err instanceof OnboardingApiError
          ? err.message
          : "Ocurrió un error inesperado. Inténtalo de nuevo.";
      setErrorMessage(message);
      machine.send("FAILED");
    }
  };

  const handleRetry = () => {
    setErrorMessage("");
    machine.send("RETRY");
  };

  const handleReset = () => {
    setErrorMessage("");
    setSuccessUserId("");
    setCameraActive(false);
    machine.reset();
  };

  return (
    <div className="page-frame page-centered">
      <Nav />
      <main className="onboarding-layout">
        <header className="onboarding-intro">
          <div className="eyebrow">Registro de identidad segura</div>
          <h1 data-testid="page-onboarding">Crea tu identificación BioScan</h1>
          <p>Protege tu cuenta con autenticación biométrica facial.</p>
          <p className="sr-only" data-testid="onboarding-state-label">Estado: {machine.label}</p>
        </header>

        {/* Identifier + consent (visible until terminal). */}
        {machine.state !== "success" && (
          <section className="auth-card onboarding-card">
            <div className="form-stack">
              <div className="field">
                <label htmlFor="onboarding-identifier">Identificador</label>
                <input
                  id="onboarding-identifier"
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="nombre@empresa.com"
                  disabled={machine.state !== "initial"}
                  aria-label="Identificador"
                  data-testid="identifier-input"
                />
              </div>
              <div className="consent-field">
                <label htmlFor="onboarding-consent">
                  <input
                    id="onboarding-consent"
                    type="checkbox"
                    checked={consentAccepted}
                    onChange={(e) => setConsentAccepted(e.target.checked)}
                    disabled={machine.state !== "initial"}
                    aria-label="Aceptar consentimiento de procesamiento facial"
                    data-testid="consent-checkbox"
                  />
                  Acepto el consentimiento para el procesamiento facial y el uso puntual de la cámara.
                </label>
              </div>
              {!cameraActive && (
                <div className="camera-placeholder state-surface">
                  <span className="material-symbols-outlined" aria-hidden="true">photo_camera</span>
                  <span>Tu rostro se procesará de forma segura y no se guardará la imagen original.</span>
                </div>
              )}
              {machine.state === "initial" && (
                <button
                  className="button-primary"
                  type="button"
                  onClick={handleStartCamera}
                  disabled={!canStart}
                  aria-label="Solicitar cámara"
                  data-testid="start-camera-button"
                >
                  <span className="material-symbols-outlined" aria-hidden="true">photo_camera</span>
                  Activar cámara
                </button>
              )}
            </div>

            {cameraActive && (
              <div className="form-stack">
                <span className="camera-label">Firma biométrica</span>
                <CameraCapture
                  active={cameraActive}
                  onCapture={handleCapture}
                  onPermissionGranted={handlePermissionGranted}
                  onPermissionDenied={handlePermissionDenied}
                  disabled={machine.isProcessing}
                  captureButtonLabel="Registrar rostro"
                  captureButtonAriaLabel="Registrar rostro"
                />
              </div>
            )}

            <div className="onboarding-progress">
              <div className="scanner-meta"><strong>Datos de cuenta</strong><span>Verificación facial</span></div>
              <div className="progress-track" aria-hidden="true"><span /></div>
            </div>
          </section>
        )}

        {/* Camera unavailable. */}
        {machine.state === "camera_unavailable" && (
          <div className="state-surface" role="alert" data-testid="camera-unavailable-message">
            <p>{errorMessage}</p>
            <button type="button" onClick={handleReset} aria-label="Reintentar">
              Reintentar
            </button>
          </div>
        )}

        {/* Recoverable error. */}
        {machine.state === "recoverable_error" && (
          <div className="state-surface" role="alert" data-testid="recoverable-error-message">
            <p>{errorMessage}</p>
            <button type="button" onClick={handleRetry} aria-label="Reintentar captura" data-testid="retry-button">
              Reintentar
            </button>
          </div>
        )}

        {/* Success. */}
        {machine.state === "success" && (
          <div className="auth-card onboarding-card state-surface" data-testid="onboarding-success">
            <h2>Registro completado</h2>
            <p>Tu identificador biométrico ha sido registrado correctamente.</p>
            <p>
              Usuario: <code>{successUserId}</code>
            </p>
            <Link to="/login" data-testid="go-to-login">
              Ir a inicio de sesión
            </Link>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
};

export default Onboarding;
