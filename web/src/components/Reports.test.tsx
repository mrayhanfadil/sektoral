import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { labelParts, RatingBadge } from "./Reports";

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
