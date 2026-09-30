import { describe, expect, it } from "vitest";
import { decisionWord, gateWord, isJudged, verdictGlyph, verdictOf, verdictTone, verdictWord, words } from "./read";

describe("hypothesis verdicts", () => {
  it("counts only real verdicts as judged", () => {
    const verdicts = [verdictOf({ verdict_code: "supported" }), verdictOf({ verdict: "tidak didukung" }),
      verdictOf({ verdict: "belum terjawab", verdict_code: "unanswered" }), verdictOf(undefined)];
    expect(verdicts.filter(isJudged).map((v) => v.code)).toEqual(["supported", "not_supported"]);
  });
  it("marks an unanswered hypothesis with the warning glyph, not the done check", () => {
    expect(verdictGlyph(verdictOf({ verdict: "belum terjawab" }))).toBe("warn");
    expect(verdictGlyph(verdictOf({ verdict: "didukung" }))).toBe("ok");
    expect(verdictGlyph(verdictOf({ verdict_code: "not_supported" }))).toBe("ok");
    expect(verdictGlyph(verdictOf(undefined))).toBe("idle");
  });
  it("reads the code first and the Indonesian label without one", () => {
    // A code wins over its label, so a relabelled verdict still reads right.
    expect(verdictTone(verdictOf({ verdict: "supported", verdict_code: "supported" }))).toBe("pill-ok");
    expect(verdictTone(verdictOf({ verdict: "tidak didukung" }))).toBe("pill-err");
    expect(verdictTone(verdictOf({ verdict: "sesuatu yang baru" }))).toBe("pill-warn");
    expect(isJudged(verdictOf({ verdict: "sesuatu yang baru" }))).toBe(true);
  });
  it("shows a verdict in the reader's words", () => {
    expect(verdictWord(verdictOf({ verdict: "sebagian didukung", verdict_code: "partly_supported" }), "en")).toBe("partly supported");
    expect(verdictWord(verdictOf({ verdict: "sebagian didukung" }), "id")).toBe("sebagian didukung");
    expect(verdictWord(verdictOf({ verdict: "sesuatu yang baru" }), "en")).toBe("sesuatu yang baru");
  });
});

describe("gate and chain words", () => {
  it("shows a code in either language and a code-less label as sent", () => {
    expect(gateWord({ verdict: "gagal", code: "fail" }, "en")).toBe("fail");
    expect(gateWord({ verdict: "tidak dapat dinilai" }, "en")).toBe("cannot be assessed");
    expect(decisionWord({ decision: "Terpilih, ekstrem (rantai berhenti)", code: "stop_extreme" }, "en")).toBe("Selected, extreme (chain stops)");
    expect(decisionWord({ decision: "Dipakai ulang" }, "en")).toBe("Dipakai ulang");
  });
});

describe("pipeline words", () => {
  it("shows codes, verdicts and chain decisions in either language", () => {
    expect(words("distributable", "id")).toBe("dapat didistribusikan");
    expect(words("distributable", "en")).toBe("distributable");
    expect(words("tidak berlaku", "id")).toBe("tidak berlaku");
    expect(words("tidak berlaku", "en")).toBe("not applicable");
    expect(words("Silang cek", "en")).toBe("Cross-check");
    expect(words("belum terjawab", "en")).toBe("unanswered");
  });
  it("passes free text and missing values through", () => {
    expect(words("5 emiten", "en")).toBe("5 emiten");
    expect(words("constructor", "en")).toBe("constructor");
    expect(words(undefined, "en")).toBeUndefined();
  });
});
