// Login page — identifier + camera + state machine (T040, R-8, FR-016/FR-017).
//
// Replaces the spec 001 placeholder. Drives the PRD §6.3 seven-state machine
// via useLoginMachine and reuses CameraCapture. Submits to POST /api/auth/face-login;
// on 200 → login(userId) + redirect to /dashboard; on 401 auth_failed → recoverable_error
// with the generic message; on 400 capture code → recoverable_error with actionable message.

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

import Nav from "../components/Nav";
import CameraCapture from "../components/CameraCapture";
import { useLoginMachine } from "../hooks/useLoginMachine";
import { useSession } from "../context/SessionContext";
import { api, AuthApiError } from "../services/api";

const Login: React.FC = () => {
  const machine = useLoginMachine();
  const navigate = useNavigate();
  const { login } = useSession();
  const [identifier, setIdentifier] = useState("");
  const [cameraActive, setCameraActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const identifierValid = identifier.trim().length >= 3;
  const canStart = identifierValid && machine.state === "idle";

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
      const result = await api.faceLogin(identifier.trim(), blob);
      login(result.userId);
      machine.send("SUCCEEDED");
      // Redirect to /dashboard after success.
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const message =
        err instanceof AuthApiError
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
    setCameraActive(false);
    machine.reset();
  };

  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-login">Login</h1>
        <p data-testid="login-state-label">Estado: {machine.label}</p>

        {/* Identifier (visible until terminal). */}
        {machine.state !== "success_redirect" && (
          <div>
            <label htmlFor="login-identifier">Identificador (email o usuario)</label>
            <input
              id="login-identifier"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="demo@example.com"
              disabled={machine.state !== "idle"}
              aria-label="Identificador"
              data-testid="identifier-input"
            />

            {machine.state === "idle" && (
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
        {cameraActive && machine.state !== "success_redirect" && (
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
            <button
              type="button"
              onClick={handleRetry}
              aria-label="Reintentar captura"
              data-testid="retry-button"
            >
              Reintentar
            </button>
          </div>
        )}

        {/* Success redirect. */}
        {machine.state === "success_redirect" && (
          <div data-testid="login-success">
            <p>¡Login exitoso! Redirigiendo al dashboard…</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default Login;
