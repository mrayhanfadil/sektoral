import { afterEach, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { idr } from "../lib/format";
import type { ChainStep, ReportItem } from "../lib/api";
import { setLang } from "../lib/i18n";
import { labelParts, MethodChain, PriceDate, RatingBadge, unpublishedNote } from "./Reports";

// Tests that switch the language put back the English the others expect.
afterEach(() => setLang("en"));

describe("money and dates", () => {
  it("shows a missing amount as n.a., never Rpn.a.", () => {
    expect(idr(null, "id")).toBe("n.a.");
    expect(idr(undefined, "en")).toBe("n.a.");
    expect(idr(9150, "id")).toBe("Rp9.150");
    expect(idr(9150, "en")).toBe("Rp9,150");
  });

  it("dates the price in the reader's language, and shows nothing without a date", () => {
    setLang("en");
    expect(renderToStaticMarkup(<PriceDate item={{ price: 9150, price_date: "2026-09-24" }} />)).toContain("as of <time dateTime=\"2026-09-24\">Sep 24, 2026</time>");
    setLang("id");
    expect(renderToStaticMarkup(<PriceDate item={{ price: 9150, price_date: "2026-09-24" }} />)).toContain("per <time dateTime=\"2026-09-24\">24 Sep 2026</time>");
    expect(renderToStaticMarkup(<PriceDate item={{ price: 9150 }} />)).toBe("");
  });
});

describe("method chain values", () => {
  const chain: ChainStep[] = [
    { step: "SOTP/LoM", decision: "Terpilih", decision_code: "selected", value: "Rp3.490", value_en: "Rp3,490" },
    { step: "EV/EBITDA FY", decision: "Silang cek", decision_code: "cross_check", value: "Rp3.900" },
  ];
  it("reads English figures for an English reader and the Indonesian otherwise", () => {
    setLang("en");
    const en = renderToStaticMarkup(<MethodChain chain={chain} />);
    expect(en).toContain("Rp3,490");
    expect(en).not.toContain("Rp3.490");
    expect(en).toContain("Rp3.900"); // no twin: the value as sent
    setLang("id");
    expect(renderToStaticMarkup(<MethodChain chain={chain} />)).toContain("Rp3.490");
  });
});

describe("unpublished reports (ADR 0014)", () => {
  const item = (publication_state: ReportItem["publication_state"], release_status: string) => ({ publication_state, release_status });
  it("never calls a draft one awaiting publication", () => {
    expect(unpublishedNote(item("built", "draft_non_distributable")).en).toBe("Draft, not published");
    expect(unpublishedNote(item("built", "draft_non_distributable")).id).toBe("Draf, tidak diterbitkan");
    expect(unpublishedNote(item("review_pending", "distributable_assumption_led")).en).toContain("awaiting analyst review");
    expect(unpublishedNote(item("withdrawn", "production_ready")).en).toBe("Company Update withdrawn");
  });
});

describe("rating column labels (#44)", () => {
  it("break a long publication state between its parts", () => {
    expect(labelParts("Auto-published · not analyst-reviewed")).toEqual(["Auto-published ·", "not analyst-reviewed"]);
    expect(labelParts("Terbit otomatis · belum direview analis")).toEqual(["Terbit otomatis ·", "belum direview analis"]);
    expect(labelParts("Superseded")).toEqual(["Superseded"]);
  });

  it("wrap inside the column instead of running into the next one", () => {
    const html = renderToStaticMarkup(
      <RatingBadge item={{ rating: "Sell", held_reason: "", release_status: "distributable_assumption_led", publication_state: "auto_published" }} />,
    );
    const labels = [...html.matchAll(/<span class="(inline-flex min-h-6[^"]*)">(.*?)<\/span><\/span>/g)];
    expect(labels.map((m) => m[2].replace(/<[^>]+>/g, "|"))).toEqual([
      "|Release:||Assumption-Led",
      "|Auto-published ·||not analyst-reviewed",
    ]);
    for (const [, cls] of labels) {
      expect(cls).toContain("max-w-full");
      expect(cls).toContain("flex-wrap");
      expect(cls).not.toContain("whitespace-nowrap");
    }
  });
});
