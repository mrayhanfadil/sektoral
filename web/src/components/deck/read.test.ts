import { describe, expect, it } from "vitest";
import { isJudged, verdictGlyph } from "./read";

describe("hypothesis verdicts", () => {
  it("counts only real verdicts as judged", () => {
    const verdicts = ["didukung", "tidak didukung", "belum terjawab", undefined];
    expect(verdicts.filter(isJudged)).toEqual(["didukung", "tidak didukung"]);
  });
  it("marks an unanswered hypothesis with the warning glyph, not the done check", () => {
    expect(verdictGlyph("belum terjawab")).toBe("warn");
    expect(verdictGlyph("didukung")).toBe("ok");
    expect(verdictGlyph("tidak didukung")).toBe("ok");
    expect(verdictGlyph(undefined)).toBe("idle");
  });
});
