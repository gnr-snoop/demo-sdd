// useOnboardingMachine — PRD §6.2 seven-state onboarding state machine (T027, R-9).
//
// State identifiers are English (code); display labels are Spanish (UI).
// States: initial, requesting_permission, camera_unavailable,
// ready_to_capture, processing, success, recoverable_error.

import { useCallback, useState } from "react";

export type OnboardingState =
  | "initial"
  | "requesting_permission"
  | "camera_unavailable"
  | "ready_to_capture"
  | "processing"
  | "success"
  | "recoverable_error";

// Spanish display labels per PRD §6.2 (English identifiers in code).
export const STATE_LABELS: Record<OnboardingState, string> = {
  initial: "inicial",
  requesting_permission: "solicitando permiso",
  camera_unavailable: "cámara no disponible",
  ready_to_capture: "listo para capturar",
  processing: "procesando",
  success: "éxito",
  recoverable_error: "error recuperable",
};

export type OnboardingEvent =
  | "REQUEST_PERMISSION"
  | "PERMISSION_GRANTED"
  | "PERMISSION_DENIED"
  | "CAPTURE"
  | "SUCCEEDED"
  | "FAILED"
  | "RETRY"
  | "RESET";

// Transition table. Invalid transitions are ignored (state-machine correctness).
const TRANSITIONS: Record<OnboardingState, Partial<Record<OnboardingEvent, OnboardingState>>> = {
  initial: { REQUEST_PERMISSION: "requesting_permission" },
  requesting_permission: {
    PERMISSION_GRANTED: "ready_to_capture",
    PERMISSION_DENIED: "camera_unavailable",
  },
  camera_unavailable: { RETRY: "initial", RESET: "initial" },
  ready_to_capture: { CAPTURE: "processing", RESET: "initial" },
  processing: {
    SUCCEEDED: "success",
    FAILED: "recoverable_error",
  },
  recoverable_error: { RETRY: "ready_to_capture", RESET: "initial" },
  success: { RESET: "initial" },
};

export interface UseOnboardingMachine {
  state: OnboardingState;
  label: string;
  send: (event: OnboardingEvent) => void;
  reset: () => void;
  canCapture: boolean;
  isProcessing: boolean;
  isTerminal: boolean;
}

export function useOnboardingMachine(initial: OnboardingState = "initial"): UseOnboardingMachine {
  const [state, setState] = useState<OnboardingState>(initial);

  const send = useCallback((event: OnboardingEvent) => {
    setState((prev) => {
      const next = TRANSITIONS[prev]?.[event];
      return next ?? prev; // ignore invalid transitions
    });
  }, []);

  const reset = useCallback(() => setState("initial"), []);

  return {
    state,
    label: STATE_LABELS[state],
    send,
    reset,
    canCapture: state === "ready_to_capture",
    isProcessing: state === "processing",
    isTerminal: state === "success",
  };
}

export default useOnboardingMachine;
