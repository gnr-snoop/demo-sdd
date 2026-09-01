// State-machine tests for useAgeMachine (spec 005, T016/T024, FR-014/PRD §6.4).
//
// Mirrors useMoodMachine.test.tsx. Covers all 5 states, valid transitions,
// invalid-transition prevention, double-press prevention (CAPTURE ignored while
// processing — FR-014), retry from error/camera_unavailable without reload,
// and result persistence (FR-010).

import { act, renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { AgeStateName, useAgeMachine } from "../../hooks/useAgeMachine";
import { AgeResponse } from "../../services/api";

const RESULT: AgeResponse = {
  estimatedAge: 32,
  range: { min: 27, max: 37 },
  disclaimer: "La edad es una estimación visual y puede contener un margen de error significativo.",
};

describe("useAgeMachine — initial state", () => {
  it("starts in `idle` with no result/error", () => {
    const { result } = renderHook(() => useAgeMachine());
    expect(result.current.state).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isProcessing).toBe(false);
    expect(result.current.canCapture).toBe(true);
  });
});

describe("useAgeMachine — valid transitions", () => {
  it("idle → processing → result on SUCCEEDED", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    expect(result.current.state).toBe("processing");
    expect(result.current.isProcessing).toBe(true);
    expect(result.current.canCapture).toBe(false);
    act(() => result.current.send({ type: "SUCCEEDED", result: RESULT }));
    expect(result.current.state).toBe("result");
    expect(result.current.result).toEqual(RESULT);
    expect(result.current.canCapture).toBe(true);
  });

  it("idle → processing → error on FAILED", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "FAILED", code: "no_face", message: "no" }));
    expect(result.current.state).toBe("error");
    expect(result.current.error).toEqual({ code: "no_face", message: "no" });
    expect(result.current.canCapture).toBe(true);
  });

  it("idle → camera_unavailable on CAMERA_DENIED", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAMERA_DENIED" }));
    expect(result.current.state).toBe("camera_unavailable");
    expect(result.current.canCapture).toBe(false);
  });
});

describe("useAgeMachine — double-press prevention (FR-014)", () => {
  it("CAPTURE while `processing` is ignored", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    expect(result.current.state).toBe("processing");
    // Second press while in flight → ignored.
    act(() => result.current.send({ type: "CAPTURE" }));
    expect(result.current.state).toBe("processing");
  });

  it("SUCCEEDED while `idle` is ignored", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "SUCCEEDED", result: RESULT }));
    expect(result.current.state).toBe("idle");
    expect(result.current.result).toBeNull();
  });

  it("FAILED while `idle` is ignored", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "FAILED", code: "x", message: "y" }));
    expect(result.current.state).toBe("idle");
  });
});

describe("useAgeMachine — retry without reload", () => {
  it("error → idle on RETRY", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "FAILED", code: "no_face", message: "no" }));
    expect(result.current.state).toBe("error");
    act(() => result.current.send({ type: "RETRY" }));
    expect(result.current.state).toBe("idle");
    expect(result.current.error).toBeNull();
  });

  it("camera_unavailable → idle on RETRY", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAMERA_DENIED" }));
    act(() => result.current.send({ type: "RETRY" }));
    expect(result.current.state).toBe("idle");
  });
});

describe("useAgeMachine — result persistence (FR-010)", () => {
  it("result remains visible after a failed retry attempt", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "SUCCEEDED", result: RESULT }));
    expect(result.current.result).toEqual(RESULT);
    // New capture fails → result still held.
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "FAILED", code: "no_face", message: "no" }));
    expect(result.current.state).toBe("error");
    expect(result.current.result).toEqual(RESULT);
  });
});

describe("useAgeMachine — reset", () => {
  it("reset returns to `idle` from any state and clears result/error", () => {
    const { result } = renderHook(() => useAgeMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "SUCCEEDED", result: RESULT }));
    act(() => result.current.reset());
    expect(result.current.state).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});

describe("useAgeMachine — all 5 states reachable", () => {
  it("exposes the 5 state names", () => {
    const expected: AgeStateName[] = [
      "idle",
      "processing",
      "result",
      "error",
      "camera_unavailable",
    ];
    // Touch each label to ensure they compile as AgeStateName.
    expect(expected).toHaveLength(5);
  });
});
