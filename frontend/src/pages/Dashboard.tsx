// Dashboard page — mood analysis UI (spec 004, T027, FR-008..FR-013/FR-019).
//
// Camera preview acquired on mount, released on unmount (FR-012b). The mood
// button ("Detectar estado de ánimo") captures a single still from the live
// preview and POSTs it to /api/analysis/mood. While in flight the button is
// disabled — one capture at a time, no server-side lock (FR-014). The mood
// result (label + optional ≈NN% + disclaimer) stays visible until a new
// analysis or unmount/logout (FR-010). Recoverable errors show an actionable
// surface with retry (FR-011/FR-015). Camera-permission denial shows an
// actionable surface with retry and makes no backend call (FR-012c). The
// "Calcular edad" button is present but disabled ("Próximamente" — spec 005,
// FR-013). "Cerrar sesión" is reused from spec 003.

import React, { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import CameraCapture from "../components/CameraCapture";
import Nav from "../components/Nav";
import { useSession } from "../context/SessionContext";
import { useMoodMachine } from "../hooks/useMoodMachine";
import { api, MoodResponse } from "../services/api";

const MOOD_BUTTON_LABEL = "Detectar estado de ánimo";

/** Render confidence as "≈NN%" (nearest integer) when present (FR-012a). */
function formatConfidence(confidence: number | null): string | null {
  if (confidence === null || confidence === undefined) return null;
  return `≈${Math.round(confidence * 100)}%`;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { logout, userId } = useSession();
  const mood = useMoodMachine();
  // Whether the camera stream is live (permission granted). Acquired on mount
  // via CameraCapture; released on unmount (FR-012b).
  const [cameraReady, setCameraReady] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const handlePermissionGranted = useCallback(() => {
    setCameraReady(true);
  }, []);

  const handlePermissionDenied = useCallback(() => {
    setCameraReady(false);
    // FR-012c: camera permission denied → actionable mood error surface + retry,
    // no backend call.
    mood.send({ type: "CAMERA_DENIED" });
  }, [mood]);

  const handleCapture = useCallback(
    async (blob: Blob) => {
      // FR-014: one capture at a time — transition to processing (button disables).
      mood.send({ type: "CAPTURE" });
      try {
        const result: MoodResponse = await api.analysisMood(blob);
        mood.send({ type: "SUCCEEDED", result });
      } catch (err) {
        // AuthApiError / OnboardingApiError carry code + message.
        const code = (err as { code?: string })?.code ?? "internal_error";
        const message =
          (err as { message?: string })?.message ??
          "Ocurrió un error inesperado. Inténtalo de nuevo.";
        mood.send({ type: "FAILED", code, message });
      }
    },
    [mood],
  );

  const handleRetry = useCallback(() => {
    mood.send({ type: "RETRY" });
  }, [mood]);

  const confidenceLabel = mood.result ? formatConfidence(mood.result.confidence) : null;

  return (
    <div>
      <Nav />
      <main>
        <h1 data-testid="page-dashboard">Dashboard</h1>
        {userId && (
          <p>
            Sesión activa para el usuario: <code>{userId}</code>
          </p>
        )}

        {/* Camera preview — acquired on mount, released on unmount (FR-012b). */}
        <CameraCapture
          active={true}
          onCapture={handleCapture}
          onPermissionGranted={handlePermissionGranted}
          onPermissionDenied={handlePermissionDenied}
          disabled={mood.isProcessing}
          captureButtonLabel={MOOD_BUTTON_LABEL}
          captureButtonAriaLabel={MOOD_BUTTON_LABEL}
          captureButtonTestId="mood-capture-button"
        />

        {/* Independent mood loading indicator (FR-008). */}
        {mood.isProcessing && (
          <p data-testid="mood-loading" role="status" aria-live="polite">
            Analizando estado de ánimo…
          </p>
        )}

        {/* Mood result surface — label + optional ≈NN% + disclaimer (FR-003/FR-012a). */}
        {mood.state === "result" && mood.result && (
          <section data-testid="mood-result" aria-live="polite">
            <p data-testid="mood-label">
              Estado de ánimo: <strong>{mood.result.label}</strong>
              {confidenceLabel && <span data-testid="mood-confidence"> {confidenceLabel}</span>}
            </p>
            <p data-testid="mood-disclaimer">{mood.result.disclaimer}</p>
          </section>
        )}

        {/* Independent recoverable mood error surface + retry (FR-011/FR-015). */}
        {mood.state === "error" && mood.error && (
          <section data-testid="mood-error" role="alert" aria-live="assertive">
            <p>
              {mood.error.message}
            </p>
            <button
              type="button"
              onClick={handleRetry}
              aria-label="Reintentar análisis de ánimo"
              data-testid="mood-retry-button"
            >
              Reintentar
            </button>
          </section>
        )}

        {/* Camera-permission-denied error surface + retry (FR-012c). */}
        {mood.state === "camera_unavailable" && (
          <section data-testid="mood-camera-error" role="alert" aria-live="assertive">
            <p>
              No se pudo acceder a la cámara. Revisa los permisos del navegador y vuelve a
              intentarlo.
            </p>
            <button
              type="button"
              onClick={handleRetry}
              aria-label="Reintentar acceso a la cámara"
              data-testid="mood-camera-retry-button"
            >
              Reintentar
            </button>
          </section>
        )}

        {/* Disabled "Calcular edad" placeholder (FR-013 — spec 005). */}
        <div>
          <button
            type="button"
            disabled
            aria-label="Calcular edad — próximamente"
            data-testid="age-button"
          >
            Calcular edad
          </button>
          <span data-testid="age-placeholder">Próximamente</span>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          aria-label="Cerrar sesión"
          data-testid="logout-button"
        >
          Cerrar sesión
        </button>
      </main>
    </div>
  );
};

export default Dashboard;
