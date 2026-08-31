// State-machine tests for useLoginMachine (T035, FR-016/PRD §6.3).
//
// Covers all 7 states, valid transitions, invalid-transition prevention,
// capture-button disabled in `processing`, and retry from `recoverable_error`
// without reload.

import { act, renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { LoginState, LOGIN_STATE_LABELS, useLoginMachine } from "../../hooks/useLoginMachine";

describe("useLoginMachine — states & labels", () => {
  it("starts in `idle` by default", () => {
    const { result } = renderHook(() => useLoginMachine());
    expect(result.current.state).toBe("idle");
    expect(result.current.label).toBe(LOGIN_STATE_LABELS.idle);
  });

  it("exposes all 7 state labels (Spanish display)", () => {
    const expected: LoginState[] = [
      "idle",
      "requesting_permission",
      "camera_unavailable",
      "ready_to_capture",
      "processing",
      "success_redirect",
      "recoverable_error",
    ];
    for (const s of expected) {
      expect(LOGIN_STATE_LABELS[s]).toBeTruthy();
    }
    expect(Object.keys(LOGIN_STATE_LABELS)).toHaveLength(7);
  });
});

describe("useLoginMachine — valid transitions", () => {
  it("idle → requesting_permission → ready_to_capture → processing → success_redirect", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    expect(result.current.state).toBe("requesting_permission");
    act(() => result.current.send("PERMISSION_GRANTED"));
    expect(result.current.state).toBe("ready_to_capture");
    expect(result.current.canCapture).toBe(true);
    act(() => result.current.send("CAPTURE"));
    expect(result.current.state).toBe("processing");
    expect(result.current.isProcessing).toBe(true);
    expect(result.current.canCapture).toBe(false);
    act(() => result.current.send("SUCCEEDED"));
    expect(result.current.state).toBe("success_redirect");
    expect(result.current.isTerminal).toBe(true);
  });

  it("requesting_permission → camera_unavailable on denial", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_DENIED"));
    expect(result.current.state).toBe("camera_unavailable");
  });

  it("processing → recoverable_error on failure", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("FAILED"));
    expect(result.current.state).toBe("recoverable_error");
  });
});

describe("useLoginMachine — retry without reload", () => {
  it("recoverable_error → ready_to_capture on RETRY (no reload)", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("FAILED"));
    expect(result.current.state).toBe("recoverable_error");
    act(() => result.current.send("RETRY"));
    expect(result.current.state).toBe("ready_to_capture");
  });

  it("camera_unavailable → idle on RETRY", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_DENIED"));
    act(() => result.current.send("RETRY"));
    expect(result.current.state).toBe("idle");
  });
});

describe("useLoginMachine — invalid transitions are prevented", () => {
  it("CAPTURE from `idle` is ignored", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("CAPTURE"));
    expect(result.current.state).toBe("idle");
  });

  it("SUCCEEDED from `idle` is ignored", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("SUCCEEDED"));
    expect(result.current.state).toBe("idle");
  });

  it("REQUEST_PERMISSION from `processing` is ignored", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("REQUEST_PERMISSION"));
    expect(result.current.state).toBe("processing");
  });
});

describe("useLoginMachine — reset", () => {
  it("reset returns to `idle` from any state", () => {
    const { result } = renderHook(() => useLoginMachine());
    act(() => result.current.send("REQUEST_PERMISSION"));
    act(() => result.current.send("PERMISSION_GRANTED"));
    act(() => result.current.send("CAPTURE"));
    act(() => result.current.send("SUCCEEDED"));
    expect(result.current.state).toBe("success_redirect");
    act(() => result.current.reset());
    expect(result.current.state).toBe("idle");
  });
});
