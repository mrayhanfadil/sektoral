import { describe, expect, it } from "vitest";
import { featuredReport, progressStep, ratingLabel, ratingTone, validatorNote } from "./labels";
import { pct, rp } from "./format";
import type { ReportItem } from "./api";

const item = (over: Partial<ReportItem>): ReportItem => ({
  ticker: "AAAA", name: "PT A", date: "2026-09-24", price: 100, published: true, rating: "Hold", tp: 110,
  upside: 10, method: "m", profile: "Korporasi", headline: "h", blockers: 0, held_reason: "",
  files: { pdf: true, html: true, trace: true, trace_json: true },
  chain: [{ step: "DCF", decision: "Terpilih", value: "Rp110" }], ...over,
});

describe("model scenario labels", () => {
  it("describes the model value relative to the dated close", () => {
    expect(ratingLabel(item({}))).toBe("Di atas harga pasar");
    expect(ratingTone(item({ rating: "Sell", upside: -10 }))).toBe("below");
  });
  it("calls a held report a draft or says it needs review", () => {
    expect(ratingLabel(item({ rating: null, held_reason: "forecast belum tervalidasi" }))).toBe("Draf");
    expect(ratingLabel(item({ rating: null, held_reason: "Method Gate 5, hasil ekstrem (Review Required)" }))).toBe("Perlu ditinjau");
    expect(ratingTone(item({ rating: null }))).toBe("review");
  });
});

describe("featured report", () => {
  it("prefers a selected primary method with more cross-checks", () => {
    const plain = item({ ticker: "PLAIN", chain: [{ step: "A", decision: "Dilewati", value: "-" }, { step: "B", decision: "Terpilih", value: "1" }] });
    const rich = item({ ticker: "RICH", chain: [{ step: "A", decision: "Terpilih", value: "1" }, { step: "B", decision: "Silang cek", value: "2" }] });
    expect(featuredReport([plain, rich])?.ticker).toBe("RICH");
    expect(featuredReport([item({ published: false })])).toBeUndefined();
  });
});

describe("formatting matches app/fmt.py", () => {
  it("formats rupiah and percent the Indonesian way", () => {
    expect(rp(1234567.8)).toBe("1.234.568");
    expect(rp(null)).toBe("n.a.");
    expect(pct(-20.886)).toBe("−20,9%");
    expect(pct(98.214)).toBe("98,2%");
  });
});

describe("progress", () => {
  it("advances with the furthest stage and completes at 5", () => {
    expect(progressStep("running", ["memory", "plan", "tool"])).toBe(1);
    expect(progressStep("running", ["forecast"])).toBe(3);
    expect(progressStep("completed", [])).toBe(5);
  });
});

describe("validator notes", () => {
  it("cleans and dedupes the tokens the model was asked to remove", () => {
    const note = validatorNote("prosa tidak boleh memuat angka (angka ditampilkan dari sinyal yang dicite); hapus: 11, 11,, 2026:, 25, 7");
    expect(note.message).toBe("Prosa tidak boleh memuat angka (angka ditampilkan dari sinyal yang dicite)");
    expect(note.removed).toEqual(["11", "2026", "25", "7"]);
  });
  it("keeps decimal commas, percents and words", () => {
    expect(validatorNote("x; hapus: 1,5%, (20), 3.2x").removed).toEqual(["1,5%", "20", "3.2x"]);
    expect(validatorNote("prosa memuat bahasa rekomendasi investasi; hapus kata: beli, beli").removed).toEqual(["beli"]);
  });
  it("passes other notes through", () => {
    expect(validatorNote("hypotheses[0] perlu signal_ids")).toEqual({ message: "hypotheses[0] perlu signal_ids", removed: [] });
  });
});
