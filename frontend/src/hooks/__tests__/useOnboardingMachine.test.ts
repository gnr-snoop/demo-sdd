// State-machine tests for useOnboardingMachine (T025, FR-011/PRD §6.2).
//
// Covers all 7 states, valid transitions, invalid-transition prevention,
// capture-button disabled in `processing`, and retry from `recoverable_error`
// without reload.

import { act, renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { OnboardingState, STATE_LABELS, useOnboardingMachine } from "../useOnboardingMachine";

describe("useOnboardingMachine — states & labels", () => {
  it("starts in `initial` by default", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    expect(result.current.state).toBe("initial");
    expect(result.current.label).toBe(STATE_LABELS.initial);
  });

  it("exposes all 7 state labels (Spanish display)", () => {
    const expected: OnboardingState[] = [
      "initial",
      "requesting_permission",
      "camera_unavailable",
      "ready_to_capture",
      "processing",
      "success",
      "recoverable_error",
    ];
    for (const s of expected) {
      expect(STATE_LABELS[s]).toBeTruthy();
    }
    expect(Object.keys(STATE_LABELS)).toHaveLength(7);
  });
});

describe("useOnboardingMachine — valid transitions", () => {
  it("initial → requesting_permission → ready_to_capture → processing → success", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    expect(result.current.state).toBe("requesting_permission");
    act(() => result.current.send("PERMISSION_GRANTED"));
    expect(result.current.state).toBe("ready_to_capture");
    expect(result.current.canCapture).toBe(true);
    act(() => result.current.send("CAPTURE"));
    expect(result.current.state).toBe("processing");
    expect(result.current.isProcessing).toBe(true);
    expect(result.current.canCapture).toBe(false); // disabled during processing
    act(() => result.current.send("SUCCEEDED"));
    expect(result.current.state).toBe("success");
    expect(result.current.isTerminal).toBe(true);
  });

  it("requesting_permission → camera_unavailable on denial", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_DENIED"));
    expect(result.current.state).toBe("camera_unavailable");
  });

  it("processing → recoverable_error on failure", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("FAILED"));
    expect(result.current.state).toBe("recoverable_error");
  });
});

describe("useOnboardingMachine — retry without reload", () => {
  it("recoverable_error → ready_to_capture on RETRY (no reload)", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("FAILED"));
    expect(result.current.state).toBe("recoverable_error");
    act(() => result.current.send("RETRY"));
    expect(result.current.state).toBe("ready_to_capture");
  });

  it("camera_unavailable → initial on RETRY", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_DENIED"));
    act(() => result.current.send("RETRY"));
    expect(result.current.state).toBe("initial");
  });
});

describe("useOnboardingMachine — invalid transitions are prevented", () => {
  it("CAPTURE from `initial` is ignored", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("CAPTURE"));
    expect(result.current.state).toBe("initial");
  });

  it("SUCCEEDED from `initial` is ignored", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("SUCCEEDED"));
    expect(result.current.state).toBe("initial");
  });

  it("REQUEST_PERMISSION from `processing` is ignored", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("REQUEST_PERMISSION"));
    expect(result.current.state).toBe("processing");
  });
});

describe("useOnboardingMachine — reset", () => {
  it("reset returns to `initial` from any state", () => {
    const { result } = renderHook(() => useOnboardingMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("SUCCEEDED"));
    expect(result.current.state).toBe("success");
    act(() => result.current.reset());
    expect(result.current.state).toBe("initial");
  });
});
