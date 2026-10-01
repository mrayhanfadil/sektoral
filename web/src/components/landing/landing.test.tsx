import { afterEach, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { derive } from "../../lib/agents";
import type { JobEvent, ReportItem } from "../../lib/api";
import { setLang, type Lang } from "../../lib/i18n";
import { EvidenceChecks } from "./Checks";
import { GateInstruments, MethodChain } from "./Framework";
import { ReportShelf } from "./ReportShelf";

afterEach(() => setLang("en"));

const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/\s+/g, " ");
const inBoth = (render: () => string) => (["id", "en"] as Lang[]).map((lang) => { setLang(lang); return text(render()); });

describe("release claims match the release gate (ADR 0005, 0014)", () => {
  it("never says a held report is published, nor that every check must pass", () => {
    const [id, en] = inBoth(() => renderToStaticMarkup(<EvidenceChecks />));
    expect(en).toContain("stays a draft and is not published");
    expect(id).toContain("tetap draf dan tidak diterbitkan");
    expect(en).toContain("When every blocking check passes");
    expect(en).not.toMatch(/published as a partial draft|passes every check/);
    expect(id).not.toMatch(/terbit sebagai draf parsial|lolos seluruh pemeriksaan/);
  });

  it("routes banks to DDM / Excess Return and says Gate 5 also flags", () => {
    const [id, en] = inBoth(() => renderToStaticMarkup(<GateInstruments />));
    expect(en).toContain("banks to DDM / Excess Return");
    expect(id).toContain("bank ke DDM / Excess Return");
    expect(en).toContain("terminal value above 80% of EV is flagged");
    expect(en).not.toContain("P/BV");
  });
});

const item: ReportItem = {
  ticker: "AMMN", name: "Amman Mineral", date: "2026-09-24", release_status: "distributable_assumption_led",
  analytically_eligible: true, publication_state: "auto_published", price: 3420, price_date: "2026-09-23", published: true,
  rating: "Buy", tp: 3490, upside: 2.0, method: "SOTP", profile: "Tambang", headline: "",
  chain: [{ step: "SOTP/LoM", decision: "Terpilih", decision_code: "selected", value: "Rp3.490", value_en: "Rp3,490" }],
  blockers: 0, held_reason: "", files: { pdf: false, html: true, trace: false, trace_json: true },
};

describe("landing figures", () => {
  it("shows the chain value in the reader's figures", () => {
    const [id, en] = inBoth(() => renderToStaticMarkup(<MethodChain item={item} />));
    expect(en).toContain("Rp3,490");
    expect(id).toContain("Rp3.490");
  });

  it("dates the price behind the upside on the shelf", () => {
    const [id, en] = inBoth(() => renderToStaticMarkup(<MemoryRouter><ReportShelf items={[item]} /></MemoryRouter>));
    expect(en).toContain("price Rp3,420 , Sep 23, 2026");
    expect(id).toContain("harga Rp3.420 , 23 Sep 2026");
  });

  it("names a flagged gate on the gate meters", () => {
    const events: JobEvent[] = [{ stage: "gate", label: "Kewajaran hasil", status: "warn", t: 1, agent: "gerbang", tool: "gate_5",
      data: { gate: "5", verdict: "ditandai", verdict_code: "flagged" } }];
    const [id, en] = inBoth(() => renderToStaticMarkup(<GateInstruments gates={derive(events).gates} ticker="AMMN" />));
    expect(en).toContain("AMMN flagged");
    expect(id).toContain("AMMN ditandai");
  });
});
