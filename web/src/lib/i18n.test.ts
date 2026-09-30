import { describe, expect, it } from "vitest";
import { detectLang, pick } from "./i18n";

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

describe("pick", () => {
  it("returns the value for the language asked", () => {
    expect(pick({ id: "Laporan", en: "Reports" }, "id")).toBe("Laporan");
    expect(pick({ id: "Laporan", en: "Reports" }, "en")).toBe("Reports");
  });
});
