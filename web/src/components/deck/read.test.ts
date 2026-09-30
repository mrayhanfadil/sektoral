import { describe, expect, it } from "vitest";
import { isJudged, verdictGlyph, words } from "./read";

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

describe("pipeline words", () => {
  it("shows codes, verdicts and chain decisions in either language", () => {
    expect(words("distributable", "id")).toBe("dapat didistribusikan");
    expect(words("distributable", "en")).toBe("distributable");
    expect(words("tidak berlaku", "id")).toBe("tidak berlaku");
    expect(words("tidak berlaku", "en")).toBe("not applicable");
    expect(words("Silang cek", "en")).toBe("Cross-check");
  });
  it("passes free text and missing values through", () => {
    expect(words("5 emiten", "en")).toBe("5 emiten");
    expect(words("constructor", "en")).toBe("constructor");
    expect(words(undefined, "en")).toBeUndefined();
  });
});
