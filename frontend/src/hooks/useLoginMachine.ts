// useLoginMachine — PRD §6.3 seven-state login state machine (T039, R-8).
//
// Mirrors the onboarding state-machine pattern (useOnboardingMachine) but with
// login-specific states: no consent step, redirect to /dashboard on success.
// States: idle, requesting_permission, camera_unavailable, ready_to_capture,
// processing, success_redirect, recoverable_error.

import { useCallback, useReducer } from "react";

export type LoginState =
  | "idle"
  | "requesting_permission"
  | "camera_unavailable"
  | "ready_to_capture"
  | "processing"
  | "success_redirect"
  | "recoverable_error";

// Spanish display labels per PRD §6.3 (English identifiers in code).
export const LOGIN_STATE_LABELS: Record<LoginState, string> = {
  idle: "inicial",
  requesting_permission: "solicitando permiso",
  camera_unavailable: "cámara no disponible",
  ready_to_capture: "listo para capturar",
  processing: "procesando",
  success_redirect: "redirigiendo",
  recoverable_error: "error recuperable",
};

export type LoginEvent =
  | "REQUEST_PERMISSION"
  | "PERMISSION_GRANTED"
  | "PERMISSION_DENIED"
  | "CAPTURE"
  | "SUCCEEDED"
  | "FAILED"
  | "RETRY"
  | "RESET";

// Transition table. Invalid transitions are ignored (state-machine correctness).
const TRANSITIONS: Record<LoginState, Partial<Record<LoginEvent, LoginState>>> = {
  idle: { REQUEST_PERMISSION: "requesting_permission" },
  requesting_permission: {
    PERMISSION_GRANTED: "ready_to_capture",
    PERMISSION_DENIED: "camera_unavailable",
  },
  camera_unavailable: { RETRY: "idle", RESET: "idle" },
  ready_to_capture: { CAPTURE: "processing", RESET: "idle" },
  processing: {
    SUCCEEDED: "success_redirect",
    FAILED: "recoverable_error",
  },
  recoverable_error: { RETRY: "ready_to_capture", RESET: "idle" },
  success_redirect: { RESET: "idle" },
};

export interface UseLoginMachine {
  state: LoginState;
  label: string;
  send: (event: LoginEvent) => void;
  reset: () => void;
  canCapture: boolean;
  isProcessing: boolean;
  isTerminal: boolean;
}

export function useLoginMachine(initial: LoginState = "idle"): UseLoginMachine {
  const [state, dispatch] = useReducer(
    (prev: LoginState, event: LoginEvent): LoginState => {
      const next = TRANSITIONS[prev]?.[event];
      return next ?? prev; // ignore invalid transitions
    },
    initial,
  );

  const send = useCallback((event: LoginEvent) => {
    dispatch(event);
  }, []);

  const reset = useCallback(() => dispatch("RESET"), []);

  return {
    state,
    label: LOGIN_STATE_LABELS[state],
    send,
    reset,
    canCapture: state === "ready_to_capture",
    isProcessing: state === "processing",
    isTerminal: state === "success_redirect",
  };
}

export default useLoginMachine;
