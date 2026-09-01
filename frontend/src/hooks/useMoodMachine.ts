// useMoodMachine — mood analysis state machine (spec 004, T023, R-6/FR-014).
//
// Mirrors the useLoginMachine reducer pattern but with mood-specific states:
// no identifier, no redirect, the result stays visible until a new analysis or
// unmount/logout (FR-010). States: idle, processing, result, error,
// camera_unavailable.
//
// FR-014: `CAPTURE` is ignored while `processing` (one capture at a time, no
// server-side lock) — the mood button is disabled while in flight.

import { useCallback, useReducer } from "react";

import { MoodResponse } from "../services/api";

export type MoodStateName =
  | "idle"
  | "processing"
  | "result"
  | "error"
  | "camera_unavailable";

export type MoodEvent =
  | { type: "CAPTURE" }
  | { type: "SUCCEEDED"; result: MoodResponse }
  | { type: "FAILED"; code: string; message: string }
  | { type: "CAMERA_DENIED" }
  | { type: "RETRY" }
  | { type: "RESET" };

export interface MoodMachineState {
  state: MoodStateName;
  /** The most recent successful mood result (held until reset/new analysis). */
  result: MoodResponse | null;
  /** The most recent error code + message (recoverable). */
  error: { code: string; message: string } | null;
}

const INITIAL: MoodMachineState = {
  state: "idle",
  result: null,
  error: null,
};

// Transition table. Invalid transitions are ignored (state-machine correctness).
function reducer(prev: MoodMachineState, event: MoodEvent): MoodMachineState {
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

export interface UseMoodMachine {
  state: MoodStateName;
  result: MoodResponse | null;
  error: { code: string; message: string } | null;
  send: (event: MoodEvent) => void;
  reset: () => void;
  /** True while a capture is in flight (FR-014 — button disabled). */
  isProcessing: boolean;
  /** True when the mood button should be enabled (idle/result/error). */
  canCapture: boolean;
}

export function useMoodMachine(): UseMoodMachine {
  const [machine, dispatch] = useReducer(reducer, INITIAL);

  const send = useCallback((event: MoodEvent) => {
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

export default useMoodMachine;
