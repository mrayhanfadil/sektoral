import { describe, expect, it } from "vitest";
import { detectLang, pick, twin } from "./i18n";

describe("language from browser settings", () => {
  it("takes the first Indonesian or English entry", () => {
    expect(detectLang(["id-ID", "en-US"])).toBe("id");
    expect(detectLang(["en-GB", "id"])).toBe("en");
    expect(detectLang(["ja-JP", "id-ID", "en"])).toBe("id");
  });
  it("reads the legacy Indonesian code", () => {
    expect(detectLang(["in-ID"])).toBe("id");
  });
  it("falls back to English", () => {
    expect(detectLang(["ja-JP", "fr"])).toBe("en");
    expect(detectLang([])).toBe("en");
  });
});

describe("twin", () => {
  const risk = { headline: "Margin menyempit", headline_en: "Margins narrow", caveat: "Data terbatas", caveat_en: " " };
  it("gives English readers the English twin and Indonesian readers the Indonesian", () => {
    expect(twin(risk, "headline", "en")).toBe("Margins narrow");
    expect(twin(risk, "headline", "id")).toBe("Margin menyempit");
  });
  it("falls back to the Indonesian when the twin is missing or blank", () => {
    expect(twin(risk, "caveat", "en")).toBe("Data terbatas");
    expect(twin({ reason: "Belum cukup bukti" }, "reason", "en")).toBe("Belum cukup bukti");
    expect(twin({ reason: null, reason_en: null }, "reason", "en")).toBeNull();
  });
  it("takes a parallel list item by item", () => {
    const plan = { hypotheses: ["H satu", "H dua", "H tiga"], hypotheses_en: ["H one", null, ""] };
    expect(twin(plan, "hypotheses", "en")).toEqual(["H one", "H dua", "H tiga"]);
    expect(twin(plan, "hypotheses", "id")).toEqual(["H satu", "H dua", "H tiga"]);
    expect(twin({ next_checks: ["Cek A"] }, "next_checks", "en")).toEqual(["Cek A"]);
  });
});

describe("pick", () => {
  it("returns the value for the language asked", () => {
    expect(pick({ id: "Laporan", en: "Reports" }, "id")).toBe("Laporan");
    expect(pick({ id: "Laporan", en: "Reports" }, "en")).toBe("Reports");
  });
});
