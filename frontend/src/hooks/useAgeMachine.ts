// useAgeMachine — age analysis state machine (spec 005, T016, R-6/FR-014).
//
// Mirrors the useMoodMachine reducer pattern but with age-specific states:
// the result (estimatedAge + range + disclaimer) stays visible until a new
// analysis or unmount/logout (FR-010). States: idle, processing, result, error,
// camera_unavailable.
//
// FR-014: `CAPTURE` is ignored while `processing` (one capture at a time, no
// server-side lock) — the age button is disabled while in flight. The shared
// capture mutex across mood + age is enforced at the Dashboard level
// (anyAnalysisInFlight = mood.isProcessing || age.isProcessing), not here —
// each hook retains its own independent state machine and result/error surface
// (PRD §6.4).

import { useCallback, useReducer } from "react";

import { AgeResponse } from "../services/api";

export type AgeStateName =
  | "idle"
  | "processing"
  | "result"
  | "error"
  | "camera_unavailable";

export type AgeEvent =
  | { type: "CAPTURE" }
  | { type: "SUCCEEDED"; result: AgeResponse }
  | { type: "FAILED"; code: string; message: string }
  | { type: "CAMERA_DENIED" }
  | { type: "RETRY" }
  | { type: "RESET" };

export interface AgeMachineState {
  state: AgeStateName;
  /** The most recent successful age result (held until reset/new analysis). */
  result: AgeResponse | null;
  /** The most recent error code + message (recoverable). */
  error: { code: string; message: string } | null;
}

const INITIAL: AgeMachineState = {
  state: "idle",
  result: null,
  error: null,
};

// Transition table. Invalid transitions are ignored (state-machine correctness).
function reducer(prev: AgeMachineState, event: AgeEvent): AgeMachineState {
  switch (prev.state) {
    case "idle":
      if (event.type === "CAPTURE") {
        return { state: "processing", result: prev.result, error: null };
      }
      if (event.type === "CAMERA_DENIED") {
        return { state: "camera_unavailable", result: prev.result, error: null };
      }
      if (event.type === "RESET") {
        return INITIAL;
      }
      return prev;
    case "processing":
      // FR-014: CAPTURE while processing is ignored (one capture at a time).
      if (event.type === "SUCCEEDED") {
        return { state: "result", result: event.result, error: null };
      }
      if (event.type === "FAILED") {
        return { state: "error", result: prev.result, error: { code: event.code, message: event.message } };
      }
      if (event.type === "RESET") {
        return INITIAL;
      }
      return prev;
    case "result":
      if (event.type === "CAPTURE") {
        return { state: "processing", result: prev.result, error: null };
      }
      if (event.type === "RESET") {
        return INITIAL;
      }
      return prev;
    case "error":
      if (event.type === "RETRY") {
        return { state: "idle", result: prev.result, error: null };
      }
      if (event.type === "CAPTURE") {
        return { state: "processing", result: prev.result, error: null };
      }
      if (event.type === "RESET") {
        return INITIAL;
      }
      return prev;
    case "camera_unavailable":
      if (event.type === "RETRY") {
        return { state: "idle", result: prev.result, error: null };
      }
      if (event.type === "RESET") {
        return INITIAL;
      }
      return prev;
    default:
      return prev;
  }
}

export interface UseAgeMachine {
  state: AgeStateName;
  result: AgeResponse | null;
  error: { code: string; message: string } | null;
  send: (event: AgeEvent) => void;
  reset: () => void;
  /** True while a capture is in flight (FR-014 — button disabled). */
  isProcessing: boolean;
  /** True when the age button should be enabled (idle/result/error). */
  canCapture: boolean;
}

export function useAgeMachine(): UseAgeMachine {
  const [machine, dispatch] = useReducer(reducer, INITIAL);

  const send = useCallback((event: AgeEvent) => {
    dispatch(event);
  }, []);

  const reset = useCallback(() => dispatch({ type: "RESET" }), []);

  return {
    state: machine.state,
    result: machine.result,
    error: machine.error,
    send,
    reset,
    isProcessing: machine.state === "processing",
    canCapture: machine.state === "idle" || machine.state === "result" || machine.state === "error",
  };
}

export default useAgeMachine;
