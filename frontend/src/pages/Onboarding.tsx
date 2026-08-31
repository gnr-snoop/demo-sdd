// Onboarding page — identifier + consent + camera + state machine (T030, FR-011..FR-013/FR-015).
//
// Drives the PRD §6.2 seven-state machine via useOnboardingMachine and the
// CameraCapture component. Maps backend error codes to actionable messages.

import React, { useState } from "react";
import { Link } from "react-router-dom";

import Nav from "../components/Nav";
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
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-onboarding">Onboarding</h1>
        <p data-testid="onboarding-state-label">Estado: {machine.label}</p>

        {/* Identifier + consent (visible until terminal). */}
        {machine.state !== "success" && (
          <div>
            <label htmlFor="onboarding-identifier">Identificador (email o usuario)</label>
            <input
              id="onboarding-identifier"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="demo@example.com"
              disabled={machine.state !== "initial"}
              aria-label="Identificador"
              data-testid="identifier-input"
            />

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
              Acepto el consentimiento para el procesamiento facial.
            </label>

            {machine.state === "initial" && (
              <button
                type="button"
                onClick={handleStartCamera}
                disabled={!canStart}
                aria-label="Solicitar cámara"
                data-testid="start-camera-button"
              >
                Solicitar cámara
              </button>
            )}
          </div>
        )}

        {/* Camera (active during permission request + ready + processing). */}
        {cameraActive && machine.state !== "success" && (
          <CameraCapture
            active={cameraActive}
            onCapture={handleCapture}
            onPermissionGranted={handlePermissionGranted}
            onPermissionDenied={handlePermissionDenied}
            disabled={machine.isProcessing}
          />
        )}

        {/* Camera unavailable. */}
        {machine.state === "camera_unavailable" && (
          <div role="alert" data-testid="camera-unavailable-message">
            <p>{errorMessage}</p>
            <button type="button" onClick={handleReset} aria-label="Reintentar">
              Reintentar
            </button>
          </div>
        )}

        {/* Recoverable error. */}
        {machine.state === "recoverable_error" && (
          <div role="alert" data-testid="recoverable-error-message">
            <p>{errorMessage}</p>
            <button type="button" onClick={handleRetry} aria-label="Reintentar captura" data-testid="retry-button">
              Reintentar
            </button>
          </div>
        )}

        {/* Success. */}
        {machine.state === "success" && (
          <div data-testid="onboarding-success">
            <p>¡Onboarding completado! Tu identificador ha sido registrado.</p>
            <p>
              Usuario: <code>{successUserId}</code>
            </p>
            <Link to="/login" data-testid="go-to-login">
              Ir a inicio de sesión
            </Link>
          </div>
        )}
      </main>
    </div>
  );
};

export default Onboarding;
