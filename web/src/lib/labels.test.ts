import { describe, expect, it } from "vitest";
import { featuredReport, problemNotes, progressStep, ratingLabel, ratingTone, selectedStep, validatorNote } from "./labels";
import { pct, rp } from "./format";
import { hasEnglish, readerFiles, type ReportItem } from "./api";

const item = (over: Partial<ReportItem>): ReportItem => ({
  ticker: "AAAA", name: "PT A", date: "2026-09-24", release_status: "distributable",
  analytically_eligible: true, publication_state: "published", price: 100, published: true, rating: "Hold", tp: 110,
  upside: 10, method: "m", profile: "Korporasi", headline: "h", blockers: 0, held_reason: "",
  files: { pdf: true, html: true, trace: true, trace_json: true },
  chain: [{ step: "DCF", decision: "Terpilih", value: "Rp110" }], ...over,
});

describe("rating labels", () => {
  it("shows the published rating", () => {
    expect(ratingLabel(item({}))).toBe("Hold");
    expect(ratingTone(item({ rating: "Sell" }))).toBe("sell");
  });
  it("calls a held gallery report a Draft: its publication state says why it is held", () => {
    expect(ratingLabel(item({ rating: null, publication_state: "review_pending", held_reason: "menunggu review publikasi oleh reviewer" }))).toBe("Draft");
    expect(ratingLabel(item({ rating: null, publication_state: "built", held_reason: "Method Gate 5, hasil ekstrem (Review Required)" }))).toBe("Draft");
    expect(ratingTone(item({ rating: null }))).toBe("review");
  });
  it("says Review Required when the caller read Method Gate 5, or an older item names it", () => {
    expect(ratingLabel({ rating: null, review_required: true })).toBe("Review Required");
    expect(ratingLabel({ rating: null, held_reason: "Method Gate 5, hasil ekstrem (Review Required)" })).toBe("Review Required");
    expect(ratingLabel({ rating: null, held_reason: "forecast belum tervalidasi" })).toBe("Draft");
  });
});

describe("featured report", () => {
  it("prefers a selected primary method with more cross-checks", () => {
    const plain = item({ ticker: "PLAIN", chain: [{ step: "A", decision: "Dilewati", value: "-" }, { step: "B", decision: "Terpilih", value: "1" }] });
    const rich = item({ ticker: "RICH", chain: [{ step: "A", decision: "Terpilih", value: "1" }, { step: "B", decision: "Silang cek", value: "2" }] });
    expect(featuredReport([plain, rich])?.ticker).toBe("RICH");
    expect(featuredReport([item({ published: false })])).toBeUndefined();
  });
  it("reads decision codes before labels", () => {
    // Labels in another language: only the codes say which step was selected.
    const coded = item({ ticker: "CODED", chain: [
      { step: "A", decision: "Selected", decision_code: "selected", value: "1" },
      { step: "B", decision: "Cross-check", decision_code: "cross_check", value: "2" },
      { step: "C", decision: "Cross-check", decision_code: "cross_check", value: "3" },
    ] });
    const labelled = item({ ticker: "LABEL", chain: [{ step: "A", decision: "Terpilih", value: "1" }, { step: "B", decision: "Silang cek", value: "2" }] });
    expect(featuredReport([labelled, coded])?.ticker).toBe("CODED");
    expect(selectedStep(coded.chain)?.step).toBe("A");
    expect(selectedStep([{ step: "X", decision: "Terpilih", decision_code: undefined }])?.step).toBe("X");
  });
});

describe("report files", () => {
  const en = item({ languages: ["id", "en"], files: { pdf: true, html: true, trace: true, trace_json: true, html_en: true, pdf_en: true } });
  it("opens the English files for an English reader when English is published", () => {
    expect(readerFiles(en, "en").html).toBe("/files/reports/AAAA.en.html");
    expect(readerFiles(en, "en").pdf).toBe("/files/reports/AAAA.en.pdf");
    expect(readerFiles(en, "id").html).toBe("/files/reports/AAAA.html");
  });
  it("shows the cover of the PDF the reader opens", () => {
    expect(readerFiles(en, "en").cover).toBe("/files/reports/AAAA/cover.en.png");
    expect(readerFiles(en, "id").cover).toBe("/files/reports/AAAA/cover.png");
    expect(readerFiles(item({ languages: ["id"] }), "en").cover).toBe("/files/reports/AAAA/cover.png");
  });
  it("keeps the Indonesian files when English is not published or the server predates languages", () => {
    expect(readerFiles(item({ languages: ["id"] }), "en").pdf).toBe("/files/reports/AAAA.pdf");
    expect(readerFiles(item({}), "en").html).toBe("/files/reports/AAAA.html");
    expect(hasEnglish(item({ files: { pdf: true, html: true, trace: true, trace_json: true, html_en: true } }))).toBe(true);
    expect(readerFiles(en, "en").traceHtml).toBe("/files/reports/AAAA-trace.html");
  });
});

describe("formatting matches app/fmt.py", () => {
  it("formats rupiah and percent the Indonesian way", () => {
    expect(rp(1234567.8, "id")).toBe("1.234.568");
    expect(rp(null, "id")).toBe("n.a.");
    expect(pct(-20.886, "id")).toBe("−20,9%");
    expect(pct(98.214, "id")).toBe("98,2%");
  });
  it("formats rupiah and percent the English way", () => {
    expect(rp(1234567.8, "en")).toBe("1,234,568");
    expect(pct(-20.886, "en")).toBe("−20.9%");
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
  it("uses the server's parsed notes when it sends them, else parses the raw ones", () => {
    const parsed = [{ message: "Prose must not hold figures", removed: ["11", "2026"] }];
    expect(problemNotes(parsed, ["prosa tidak boleh memuat angka; hapus: 11, 2026"])).toEqual(parsed);
    expect(problemNotes(undefined, ["prosa memuat bahasa rekomendasi investasi; hapus kata: beli"]))
      .toEqual([{ message: "Prosa memuat bahasa rekomendasi investasi", removed: ["beli"] }]);
    expect(problemNotes([], [])).toEqual([]);
  });
  it("gives an English reader the notes' English twins, and the Indonesian where there is none", () => {
    const parsed = [
      { message: "Sintesis ditolak: tulis dalam bahasa Indonesia saja", message_en: "Synthesis rejected: write in Indonesian only", removed: [] },
      { message: "Prosa tidak boleh memuat angka", message_en: null, removed: ["11"] },
    ];
    expect(problemNotes(parsed, [], undefined, "en").map((n) => n.message))
      .toEqual(["Synthesis rejected: write in Indonesian only", "Prosa tidak boleh memuat angka"]);
    expect(problemNotes(parsed, [], undefined, "id")).toBe(parsed);
    const raw = ["prosa memuat bahasa rekomendasi investasi; hapus kata: beli", "hypotheses[0] perlu signal_ids"];
    expect(problemNotes(undefined, raw, ["prose holds investment advice language", null], "en").map((n) => n.message))
      .toEqual(["Prose holds investment advice language", "hypotheses[0] perlu signal_ids"]);
    expect(problemNotes(undefined, raw, ["prose holds investment advice language", null], "id")[0].message)
      .toBe("Prosa memuat bahasa rekomendasi investasi");
  });
});
