import { describe, expect, it } from "vitest";

import { mapPreviewDetectionToDisplay } from "../previewDetector";

describe("mapPreviewDetectionToDisplay", () => {
  it("maps boxes and landmarks through the same centered object-fit: cover crop", () => {
    const mapped = mapPreviewDetectionToDisplay(
      {
        box: { x: 160, y: 120, width: 320, height: 240 },
        landmarks: [{ x: 320, y: 120 }],
        frameAt: 1,
      },
      640,
      480,
      400,
      400,
    );

    // 640x480 into 400x400 scales by 400/480 and crops 66.67px on each side.
    expect(mapped.box.x).toBeCloseTo(66.67, 1);
    expect(mapped.box.y).toBeCloseTo(100, 1);
    expect(mapped.box.width).toBeCloseTo(266.67, 1);
    expect(mapped.box.height).toBeCloseTo(200, 1);
    expect(mapped.landmarks?.[0].x).toBeCloseTo(200, 1);
    expect(mapped.landmarks?.[0].y).toBeCloseTo(100, 1);
  });

  it("does not alter coordinates when display and video have the same aspect ratio", () => {
    const mapped = mapPreviewDetectionToDisplay(
      {
        box: { x: 10, y: 20, width: 100, height: 80 },
        landmarks: [{ x: 30, y: 40 }],
        frameAt: 1,
      },
      640,
      480,
      1280,
      960,
    );

    expect(mapped.box).toEqual({ x: 20, y: 40, width: 200, height: 160 });
    expect(mapped.landmarks).toEqual([{ x: 60, y: 80 }]);
  });
});
