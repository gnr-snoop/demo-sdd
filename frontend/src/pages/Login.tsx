// Login page — identifier + camera + state machine (T040, R-8, FR-016/FR-017).
//
// Replaces the spec 001 placeholder. Drives the PRD §6.3 seven-state machine
// via useLoginMachine and reuses CameraCapture. Submits to POST /api/auth/face-login;
// on 200 → login(userId) + redirect to /dashboard; on 401 auth_failed → recoverable_error
// with the generic message; on 400 capture code → recoverable_error with actionable message.

import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

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
    <div className="page-frame page-centered">
      <Nav />
      <main className="auth-page">
        <section className="auth-camera" aria-label="Cámara de autenticación facial">
          <div className="status-pill auth-camera-label">
            <span>{cameraActive ? "Cámara activa" : "Cámara protegida"}</span>
          </div>
          {cameraActive ? (
            <CameraCapture
              active={cameraActive}
              onCapture={handleCapture}
              onPermissionGranted={handlePermissionGranted}
              onPermissionDenied={handlePermissionDenied}
              disabled={machine.isProcessing}
            />
          ) : (
            <div className="camera-placeholder">
              <span className="material-symbols-outlined" aria-hidden="true">face</span>
              <span>Coloca tu rostro en el encuadre para iniciar</span>
            </div>
          )}
          <div className="camera-status"><span className="camera-status-dot" /> Procesamiento puntual y seguro</div>
        </section>

        <section className="auth-form">
          <div>
            <div className="accent-bar" />
            <h1 data-testid="page-login">BioScan</h1>
            <p>Autenticación biométrica segura para tu espacio Snoop.</p>
            <p className="sr-only" data-testid="login-state-label">Estado: {machine.label}</p>

            {machine.state !== "success_redirect" && (
              <div className="form-stack">
                <div className="field">
                  <label htmlFor="login-identifier">Identificador</label>
                  <input
                    id="login-identifier"
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="nombre@empresa.com"
                    disabled={machine.state !== "idle"}
                    aria-label="Identificador"
                    data-testid="identifier-input"
                  />
                </div>
                {machine.state === "idle" && (
                  <button
                    className="button-primary"
                    type="button"
                    onClick={handleStartCamera}
                    disabled={!canStart}
                    aria-label="Solicitar cámara"
                    data-testid="start-camera-button"
                  >
                    <span className="material-symbols-outlined" aria-hidden="true">fingerprint</span>
                    Activar cámara y escanear
                  </button>
                )}
              </div>
            )}

            {machine.state === "camera_unavailable" && (
              <div className="state-surface" role="alert" data-testid="camera-unavailable-message">
                <p>{errorMessage}</p>
                <button className="button-secondary" type="button" onClick={handleReset} aria-label="Reintentar">Reintentar</button>
              </div>
            )}
            {machine.state === "recoverable_error" && (
              <div className="state-surface" role="alert" data-testid="recoverable-error-message">
                <p>{errorMessage}</p>
                <button className="button-secondary" type="button" onClick={handleRetry} aria-label="Reintentar captura" data-testid="retry-button">Reintentar</button>
              </div>
            )}
            {machine.state === "success_redirect" && (
              <div className="state-surface" data-testid="login-success">
                <p>Login exitoso. Redirigiendo al dashboard…</p>
              </div>
            )}
          </div>
          <div className="auth-footer">
            <span>¿Necesitas una cuenta?</span>
            <Link to="/onboarding">Registrarse <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></Link>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Login;
