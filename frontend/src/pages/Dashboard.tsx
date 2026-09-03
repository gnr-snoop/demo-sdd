// Dashboard page — mood + age analysis UI (spec 004 + spec 005).
//
// Camera preview acquired on mount, released on unmount (FR-012b). The mood
// button ("Detectar estado de ánimo") and age button ("Calcular edad") each
// capture a single still from the live preview and POST to their respective
// /api/analysis/* endpoint. FR-014 shared capture mutex: while either analysis
// is in flight, BOTH buttons (and the camera capture trigger) are disabled and
// a second press of either is ignored — one capture at a time across the
// dashboard (anyAnalysisInFlight = mood.isProcessing || age.isProcessing).
// Each hook retains independent loading/result/error state surfaces (PRD §6.4).
// Results stay visible until a new analysis or unmount/logout (FR-010).
// Recoverable errors show an actionable surface with retry (FR-011/FR-015).
// Camera-permission denial shows an actionable surface with retry and makes no
// backend call (FR-012c). "Cerrar sesión" is reused from spec 003.

import React, { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import CameraCapture, { CameraCaptureHandle } from "../components/CameraCapture";
import Nav from "../components/Nav";
import { useSession } from "../context/SessionContext";
import { useAgeMachine } from "../hooks/useAgeMachine";
import { useMoodMachine } from "../hooks/useMoodMachine";
import { api, AgeResponse, MoodResponse } from "../services/api";

const MOOD_BUTTON_LABEL = "Detectar estado de ánimo";
const AGE_BUTTON_LABEL = "Calcular edad";
const DELETE_BUTTON_LABEL = "Eliminar mis datos";
const DELETE_CONFIRM_MESSAGE =
  "Esta acción eliminará tu perfil y plantilla facial de forma permanente. ¿Continuar?";

/** Render confidence as "≈NN%" (nearest integer) when present (FR-012a). */
function formatConfidence(confidence: number | null): string | null {
  if (confidence === null || confidence === undefined) return null;
  return `≈${Math.round(confidence * 100)}%`;
}

type DeleteState = "idle" | "confirming" | "processing" | "error";

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { logout, clearSession, userId } = useSession();
  const mood = useMoodMachine();
  const age = useAgeMachine();
  // Whether the camera stream is live (permission granted). Acquired on mount
  // via CameraCapture; released on unmount (FR-012b).
  const [cameraReady, setCameraReady] = useState(false);
  const cameraRef = useRef<CameraCaptureHandle>(null);

  // Spec 006 (T022/T023): deletion UI state.
  const [deleteState, setDeleteState] = useState<DeleteState>("idle");
  const [deleteError, setDeleteError] = useState<string>("");

  // FR-014 shared capture mutex: one capture at a time across the dashboard.
  const anyAnalysisInFlight = mood.isProcessing || age.isProcessing;

  // Tracks which analysis a capture should feed (mood vs age). The CameraCapture
  // has a single onCapture callback; this ref routes the captured blob.
  const pendingCaptureRef = useRef<"mood" | "age">("mood");

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const handlePermissionGranted = useCallback(() => {
    setCameraReady(true);
  }, []);

  const handlePermissionDenied = useCallback(() => {
    setCameraReady(false);
    // FR-012c: camera permission denied → actionable error surfaces + retry,
    // no backend call. Both mood and age surfaces show the camera-unavailable
    // state (the camera is shared).
    mood.send({ type: "CAMERA_DENIED" });
    age.send({ type: "CAMERA_DENIED" });
  }, [mood, age]);

  // Single onCapture handler routed by pendingCaptureRef. The CameraCapture's
  // built-in button is the mood button; the age button triggers capture via the
  // ref after setting pendingCaptureRef to "age".
  const handleCapture = useCallback(
    async (blob: Blob) => {
      const which = pendingCaptureRef.current;
      pendingCaptureRef.current = "mood"; // reset to default
      const machine = which === "age" ? age : mood;
      machine.send({ type: "CAPTURE" });
      try {
        if (which === "age") {
          const result: AgeResponse = await api.analysisAge(blob);
          age.send({ type: "SUCCEEDED", result });
        } else {
          const result: MoodResponse = await api.analysisMood(blob);
          mood.send({ type: "SUCCEEDED", result });
        }
      } catch (err) {
        const code = (err as { code?: string })?.code ?? "internal_error";
        const message =
          (err as { message?: string })?.message ??
          "Ocurrió un error inesperado. Inténtalo de nuevo.";
        // AC-008 US3 scenario 5: in-flight 401 → discard partial result,
        // transition to unauthenticated (redirect to /login).
        if (code === "unauthenticated") {
          machine.send({ type: "FAILED", code, message });
          clearSession();
          navigate("/login", { replace: true });
          return;
        }
        machine.send({ type: "FAILED", code, message });
      }
    },
    [mood, age, clearSession, navigate],
  );

  const handleMoodRetry = useCallback(() => {
    mood.send({ type: "RETRY" });
  }, [mood]);

  const handleAgeRetry = useCallback(() => {
    age.send({ type: "RETRY" });
  }, [age]);

  // Age button press: route the next capture to the age flow, then trigger a
  // still from the shared camera preview (FR-013).
  const handleAgeButtonClick = useCallback(() => {
    if (anyAnalysisInFlight) return; // FR-014: ignore while in flight
    pendingCaptureRef.current = "age";
    cameraRef.current?.capture();
  }, [anyAnalysisInFlight]);

  // --- Spec 006 deletion handlers (T022/T023, research R-7/R-9) ---
  const handleDeleteClick = useCallback(() => {
    setDeleteError("");
    setDeleteState("confirming");
  }, []);

  const handleDeleteCancel = useCallback(() => {
    // Cancel: no request, dashboard unchanged (FR-010).
    setDeleteError("");
    setDeleteState("idle");
  }, []);

  const performDeletion = useCallback(async () => {
    if (!userId) return;
    setDeleteState("processing");
    setDeleteError("");
    try {
      await api.deleteFaceData(userId);
      // 200: clear session (without calling /logout), discard held mood/age
      // results, and navigate to "/" (welcome page). Navigating away unmounts
      // the Dashboard → CameraCapture unmounts → camera stream released.
      mood.reset();
      age.reset();
      clearSession();
      navigate("/", { replace: true });
    } catch (err) {
      const code = (err as { code?: string })?.code ?? "internal_error";
      const message =
        (err as { message?: string })?.message ??
        "Ocurrió un error al eliminar tus datos. Inténtalo de nuevo.";
      if (code === "unauthenticated") {
        // 401: session expired mid-request → unauthenticated + redirect to /login.
        clearSession();
        navigate("/login", { replace: true });
        return;
      }
      // 500 internal_error (or other recoverable) → actionable error + retry,
      // button re-enabled, no full page reload (FR-011).
      setDeleteError(message);
      setDeleteState("error");
    }
  }, [userId, mood, age, clearSession, navigate]);

  const handleDeleteConfirm = useCallback(() => {
    void performDeletion();
  }, [performDeletion]);

  const handleDeleteRetry = useCallback(() => {
    // Re-enter the confirmation flow (actionable retry, no full reload).
    setDeleteError("");
    setDeleteState("confirming");
  }, []);

  const confidenceLabel = mood.result ? formatConfidence(mood.result.confidence) : null;
  const deleteBusy = deleteState === "processing" || deleteState === "confirming";

  // Age result rendering (FR-012a): range "min–max años" + point "≈NN años".
  // When min == max (narrow range), only the point estimate is rendered.
  const ageResult = age.result;
  const ageNarrow = ageResult && ageResult.range.min === ageResult.range.max;

  return (
    <div className="dashboard-shell">
      <Nav />
      <main className="dashboard-main">
        <div className="dashboard-content">
          <section>
            <header className="dashboard-heading">
              <div>
                <h1 data-testid="page-dashboard">Análisis <span>en vivo</span></h1>
                <p>Telemetría facial y computación biométrica en tiempo real.</p>
                {userId && <p className="session-caption">Sesión activa: <code>{userId}</code></p>}
              </div>
              <span className="status-pill">Sensor activo</span>
            </header>

            <div className="result-card dashboard-camera-card">
              <CameraCapture
                ref={cameraRef}
                active={true}
                onCapture={handleCapture}
                onPermissionGranted={handlePermissionGranted}
                onPermissionDenied={handlePermissionDenied}
                disabled={anyAnalysisInFlight}
                captureButtonLabel={MOOD_BUTTON_LABEL}
                captureButtonAriaLabel={MOOD_BUTTON_LABEL}
                captureButtonTestId="mood-capture-button"
              />
            </div>

            <div className="dashboard-actions">
              <button className="button-primary" type="button" onClick={handleAgeButtonClick} disabled={anyAnalysisInFlight || !cameraReady} aria-label={AGE_BUTTON_LABEL} data-testid="age-button">
                <span className="material-symbols-outlined" aria-hidden="true">cake</span>
                {AGE_BUTTON_LABEL}
              </button>
            </div>

            {mood.isProcessing && <p className="state-surface" data-testid="mood-loading" role="status" aria-live="polite">Analizando estado de ánimo…</p>}
            {age.isProcessing && <p className="state-surface" data-testid="age-loading" role="status" aria-live="polite">Calculando edad…</p>}
            {mood.state === "error" && mood.error && (
              <section className="state-surface" data-testid="mood-error" role="alert" aria-live="assertive">
                <p>{mood.error.message}</p>
                <button className="button-secondary" type="button" onClick={handleMoodRetry} aria-label="Reintentar análisis de ánimo" data-testid="mood-retry-button">Reintentar</button>
              </section>
            )}
            {mood.state === "camera_unavailable" && (
              <section className="state-surface" data-testid="mood-camera-error" role="alert" aria-live="assertive">
                <p>No se pudo acceder a la cámara. Revisa los permisos del navegador y vuelve a intentarlo.</p>
                <button className="button-secondary" type="button" onClick={handleMoodRetry} aria-label="Reintentar acceso a la cámara" data-testid="mood-camera-retry-button">Reintentar</button>
              </section>
            )}
            {age.state === "error" && age.error && (
              <section className="state-surface" data-testid="age-error" role="alert" aria-live="assertive">
                <p data-testid="age-error-message">{age.error.message}</p>
                <button className="button-secondary" type="button" onClick={handleAgeRetry} aria-label="Reintentar cálculo de edad" data-testid="age-retry-button">Reintentar</button>
              </section>
            )}
            {age.state === "camera_unavailable" && (
              <section className="state-surface" data-testid="age-camera-error" role="alert" aria-live="assertive">
                <p>No se pudo acceder a la cámara. Revisa los permisos del navegador y vuelve a intentarlo.</p>
                <button className="button-secondary" type="button" onClick={handleAgeRetry} aria-label="Reintentar acceso a la cámara para edad" data-testid="age-camera-retry-button">Reintentar</button>
              </section>
            )}
          </section>

          <aside className="results-column">
            <header className="dashboard-heading">
              <div>
                <h2>Resultados <span>del análisis</span></h2>
                <p>Salida del modelo y nivel de confianza.</p>
              </div>
            </header>
            {age.state === "result" && ageResult && (
              <section className="result-card" data-testid="age-result" aria-live="polite">
                <div className="result-card-main">
                  <div>
                    <div className="result-label">Edad estimada</div>
                    {!ageNarrow && <p className="result-value" data-testid="age-range">{ageResult.range.min}–{ageResult.range.max} <small>años</small></p>}
                    <p className="result-value" data-testid="age-point">≈{ageResult.estimatedAge} <small>años</small></p>
                    <p className="result-subtext" data-testid="age-disclaimer">{ageResult.disclaimer}</p>
                  </div>
                  <span className="result-icon material-symbols-outlined" aria-hidden="true">cake</span>
                </div>
              </section>
            )}
            {mood.state === "result" && mood.result && (
              <section className="result-card mood-card" data-testid="mood-result" aria-live="polite">
                <div className="result-card-main">
                  <div>
                    <div className="result-label">Estado de ánimo</div>
                    <p className="result-value" data-testid="mood-label">{mood.result.label}{confidenceLabel && <small data-testid="mood-confidence"> {confidenceLabel}</small>}</p>
                    <p className="result-subtext" data-testid="mood-disclaimer">{mood.result.disclaimer}</p>
                  </div>
                  <span className="result-icon material-symbols-outlined" aria-hidden="true">mood</span>
                </div>
              </section>
            )}
            <div className="privacy-note">
              <span className="material-symbols-outlined" aria-hidden="true">info</span>
              <span><strong>Protección biométrica:</strong> los vectores faciales se procesan en memoria transitoria. No se guardan capturas originales.</span>
            </div>
          </aside>
        </div>

        <div className="dashboard-utility">
          <button
            className="danger-button"
            type="button"
            onClick={handleDeleteClick}
            disabled={deleteBusy}
            aria-label={DELETE_BUTTON_LABEL}
            data-testid="delete-face-data-button"
          >
            {DELETE_BUTTON_LABEL}
          </button>

          {deleteState === "confirming" && (
            <section className="state-surface"
              role="dialog"
              aria-modal="true"
              aria-labelledby="delete-confirm-heading"
              data-testid="delete-confirm-dialog"
            >
              <h2 id="delete-confirm-heading">Confirmar eliminación</h2>
              <p data-testid="delete-confirm-message">{DELETE_CONFIRM_MESSAGE}</p>
              <button className="button-primary"
                type="button"
                onClick={handleDeleteConfirm}
                aria-label="Confirmar eliminación de mis datos"
                data-testid="delete-confirm-button"
              >
                Confirmar
              </button>
              <button className="button-secondary"
                type="button"
                onClick={handleDeleteCancel}
                aria-label="Cancelar eliminación de mis datos"
                data-testid="delete-cancel-button"
              >
                Cancelar
              </button>
            </section>
          )}

          {deleteState === "processing" && (
            <p className="state-surface" data-testid="delete-processing" role="status" aria-live="polite">
              Eliminando tus datos…
            </p>
          )}

          {deleteState === "error" && (
            <section className="state-surface" data-testid="delete-error" role="alert" aria-live="assertive">
              <p data-testid="delete-error-message">{deleteError}</p>
              <button className="button-secondary"
                type="button"
                onClick={handleDeleteRetry}
                aria-label="Reintentar eliminación de mis datos"
                data-testid="delete-retry-button"
              >
                Reintentar
              </button>
              <button className="button-secondary"
                type="button"
                onClick={handleDeleteCancel}
                aria-label="Cancelar eliminación de mis datos"
                data-testid="delete-error-cancel-button"
              >
                Cancelar
              </button>
            </section>
          )}
        </div>

        <button className="button-dark"
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
