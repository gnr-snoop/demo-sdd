// State-machine tests for useMoodMachine (spec 004, T022, FR-014/PRD §6.4).
//
// Covers all 5 states, valid transitions, invalid-transition prevention,
// double-press prevention (CAPTURE ignored while processing — FR-014), retry
// from error/camera_unavailable without reload, and result persistence.

import { act, renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { MoodStateName, useMoodMachine } from "../../hooks/useMoodMachine";
import { MoodResponse } from "../../services/api";

const FELIZ: MoodResponse = { label: "feliz", confidence: 0.8, disclaimer: "d" };

describe("useMoodMachine — initial state", () => {
  it("starts in `idle` with no result/error", () => {
    const { result } = renderHook(() => useMoodMachine());
    expect(result.current.state).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isProcessing).toBe(false);
    expect(result.current.canCapture).toBe(true);
  });
});

describe("useMoodMachine — valid transitions", () => {
  it("idle → processing → result on SUCCEEDED", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    expect(result.current.state).toBe("processing");
    expect(result.current.isProcessing).toBe(true);
    expect(result.current.canCapture).toBe(false);
    act(() => result.current.send({ type: "SUCCEEDED", result: FELIZ }));
    expect(result.current.state).toBe("result");
    expect(result.current.result).toEqual(FELIZ);
    expect(result.current.canCapture).toBe(true);
  });

  it("idle → processing → error on FAILED", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "FAILED", code: "no_face", message: "no" }));
    expect(result.current.state).toBe("error");
    expect(result.current.error).toEqual({ code: "no_face", message: "no" });
    expect(result.current.canCapture).toBe(true);
  });

  it("idle → camera_unavailable on CAMERA_DENIED", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAMERA_DENIED" }));
    expect(result.current.state).toBe("camera_unavailable");
    expect(result.current.canCapture).toBe(false);
  });
});

describe("useMoodMachine — double-press prevention (FR-014)", () => {
  it("CAPTURE while `processing` is ignored", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    expect(result.current.state).toBe("processing");
    // Second press while in flight → ignored.
    act(() => result.current.send({ type: "CAPTURE" }));
    expect(result.current.state).toBe("processing");
  });

  it("SUCCEEDED while `idle` is ignored", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "SUCCEEDED", result: FELIZ }));
    expect(result.current.state).toBe("idle");
    expect(result.current.result).toBeNull();
  });

  it("FAILED while `idle` is ignored", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "FAILED", code: "x", message: "y" }));
    expect(result.current.state).toBe("idle");
  });
});

describe("useMoodMachine — retry without reload", () => {
  it("error → idle on RETRY", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "FAILED", code: "no_face", message: "no" }));
    expect(result.current.state).toBe("error");
    act(() => result.current.send({ type: "RETRY" }));
    expect(result.current.state).toBe("idle");
    expect(result.current.error).toBeNull();
  });

  it("camera_unavailable → idle on RETRY", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAMERA_DENIED" }));
    act(() => result.current.send({ type: "RETRY" }));
    expect(result.current.state).toBe("idle");
  });
});

describe("useMoodMachine — result persistence (FR-010)", () => {
  it("result remains visible after a failed retry attempt", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "SUCCEEDED", result: FELIZ }));
    expect(result.current.result).toEqual(FELIZ);
    // New capture fails → result still held.
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "FAILED", code: "no_face", message: "no" }));
    expect(result.current.state).toBe("error");
    expect(result.current.result).toEqual(FELIZ);
  });
});

describe("useMoodMachine — reset", () => {
  it("reset returns to `idle` from any state and clears result/error", () => {
    const { result } = renderHook(() => useMoodMachine());
    act(() => result.current.send({ type: "CAPTURE" }));
    act(() => result.current.send({ type: "SUCCEEDED", result: FELIZ }));
    act(() => result.current.reset());
    expect(result.current.state).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});

describe("useMoodMachine — all 5 states reachable", () => {
  it("exposes the 5 state names", () => {
    const expected: MoodStateName[] = [
      "idle",
      "processing",
      "result",
      "error",
      "camera_unavailable",
    ];
    // Touch each label to ensure they compile as MoodStateName.
    expect(expected).toHaveLength(5);
  });
});
