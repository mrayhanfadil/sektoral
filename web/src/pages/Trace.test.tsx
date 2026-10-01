import { afterEach, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import type { BankDriverRow, Intel, Signal, TraceView } from "../lib/api";
import { setLang } from "../lib/i18n";
import { TraceBody, TraceHeader } from "./Trace";

afterEach(() => setLang("en"));

const bankRow = (year: string, nim: number, extra: Partial<BankDriverRow> = {}): BankDriverRow => ({
  year, loan_growth_pct: 8, nim_pct: nim, non_ii_to_nii_pct: 20, cost_to_income_pct: 30, cost_of_credit_pct: 0.5,
  deposit_growth_pct: 7, rationale: null, source_ids: [], ...extra,
});

const peerSignal = (extra: Partial<Signal> = {}): Signal => ({
  id: "peer.pe", kind: "peer", label: "P/E", label_en: "P/E", display: "12,1x", display_en: "12.1x", note: null, flag: null,
  period: null, median_display: "15,4x", median_display_en: "15.4x", rank: 4, n: 6,
  peers: [{ symbol: "AAAA", display: "312,0x", display_en: "312.0x", outlier: true,
    outlier_note: "P/E jauh di luar rentang grup", outlier_note_en: "P/E far outside the group's range" }, { symbol: "BBBB", display: "15,4x", display_en: "15.4x" }],
  ...extra,
});

const analyst = (extra: Partial<Intel> = {}): Intel => ({
  ticker: "GMFI", name: "GMF AeroAsia", market_date: "2026-09-11", status: "ok",
  plan: { question: "Q?", source: "agent", hypotheses: [] }, steps: [], signals: [peerSignal()],
  peers: { basis: "tabel peer Sectors", basis_en: "the Sectors peer table", group: "Operator Bandara", group_en: "Airport Operators" },
  web_news: { window: null, items: [] },
  synthesis: { headline: "H", source: "agent", findings: [], hypotheses: [], next_checks: [] },
  changes: { first_run: true, same_market_date: false, previous_run_at: null, previous_market_date: null, items: [] },
  ...extra,
});

const trace = (extra: { forecast?: Partial<TraceView["forecast"]>; analyst?: Intel | null; review_state?: TraceView["review_state"] } = {}): TraceView => ({
  ticker: "BBCA",
  review_state: extra.review_state,
  report: { release_status: "distributable_assumption_led", published: true, rating: "Sell", target_price: 5550,
    method: "DDM", as_of: "2026-09-24", market_price_date: "2026-09-23" },
  analyst: extra.analyst ?? null, analyst_problems: [],
  research: { summary: null, endpoints: [], insights: [], limitations: [] },
  news: { search: { status: null, as_of: null, queries: [] }, articles: [], rejected: [], rejected_total: 0 },
  forecast: { status: "validated", problems: [], news_effects: [], interim: null, outyears: [], ...extra.forecast },
  deepdive: [],
});

const body = (view: TraceView) => renderToStaticMarkup(<MemoryRouter><TraceBody trace={view} /></MemoryRouter>);
const header = (view: TraceView) => renderToStaticMarkup(<MemoryRouter><TraceHeader trace={view} links={{}} /></MemoryRouter>);
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&amp;/g, "&").replace(/\s+/g, " ");

describe("bank drivers", () => {
  const agent = [bankRow("2026", 5.1, { source_ids: ["news:5"] }), bankRow("2027", 5.0, { analyst_assumption: true })];

  it("shows the drivers the model ran, with their kinds and payout, and the agent's rows as an unused proposal", () => {
    const html = text(body(trace({ forecast: {
      bank_drivers: agent, bank_drivers_used: false,
      bank_drivers_model: [
        bankRow("2026", 5.6, { payout_pct: 72, kinds: { nim_pct: "company_guidance", loan_growth_pct: "sourced" }, source: "data/bank_drivers/BBCA.json" }),
        bankRow("2027", 5.5, { payout_pct: 70, kinds: { nim_pct: "analyst_assumption" }, source: "data/bank_drivers/BBCA.json" }),
      ],
      bank_drivers_note: "Model bank tidak memakai driver usulan agent ini.",
      bank_drivers_note_en: "The bank model did not use the agent's proposed drivers: the balance sheet, earnings and dividends are computed from the curated driver file.",
      bank_payout_rationale: "Rasio dividen 72% sesuai RUPS.", bank_payout_rationale_en: "A 72% payout as set by the AGM.",
    } })));
    expect(html).toContain("Drivers the model ran");
    expect(html).toContain("5.6% G (company guidance)");
    expect(html).toContain("5.5% A (analyst assumption)");
    expect(html).toContain("Payout");
    expect(html).toContain("72%");
    expect(html).toContain("G = company guidance · A = analyst assumption; unmarked = sourced.");
    expect(html).toContain("Source: data/bank_drivers/BBCA.json");
    expect(html).toContain("Payout: A 72% payout as set by the AGM.");
    expect(html).toContain("The bank model did not use the agent's proposed drivers");
    expect(html).toContain("The forecast agent's proposed drivers Agent's proposal, not used by the model");
    expect(html).toContain("from the drivers it ran");
  });

  it("claims the model ran the agent's drivers only when the server says so", () => {
    const used = text(body(trace({ forecast: { bank_drivers: agent, bank_drivers_used: true } })));
    expect(used).toContain("from the drivers it ran");
    expect(used).not.toContain("not used by the model");
    // Older traces do not say: the table shows without the claim.
    const unknown = text(body(trace({ forecast: { bank_drivers: agent } })));
    expect(unknown).toContain("5.1%");
    expect(unknown).not.toContain("from the drivers it ran");
    expect(unknown).not.toContain("Drivers the model ran");
    expect(unknown).not.toContain("not used by the model");
  });

  it("marks the agent's own-scenario rows as analyst assumptions", () => {
    setLang("id");
    const html = text(body(trace({ forecast: { bank_drivers: agent, bank_drivers_used: true } })));
    expect(html).toContain("Asumsi analis");
    expect(html).toContain("news:5");
  });
});

describe("out-years", () => {
  const outyear = { year: "2027", revenue_growth_pct: 5, ebitda_margin_pct: 20, net_income_margin_pct: 10, capex_to_revenue_pct: 4,
    rationale: "r", source_ids: [] };
  it("shows the model's own out-years and folds the agent's table away as unused", () => {
    setLang("id");
    const html = text(body(trace({ forecast: { outyears: [outyear], outyears_used: false,
      outyears_model: [{ ...outyear, revenue_growth_pct: 9, rationale: "jadwal LoM" }],
      outyears_note: "Model tidak memakai tabel tahun lanjutan agent ini: forecast FY27F-FY27F mengikuti jadwal LoM.",
      outyears_note_en: "The model did not use the agent's out-year table." } })));
    expect(html).toContain("Forecast yang dijalankan model");
    expect(html).toContain("9%");
    expect(html).toContain("Tabel tahun lanjutan agent forecast Usulan agent, tidak dipakai model");
    expect(html).toContain("mengikuti jadwal LoM.");
  });
  it("labels the agent's table as unused even without the model's rows", () => {
    const html = text(body(trace({ forecast: { outyears: [outyear], outyears_used: false } })));
    expect(html).toContain("Agent's proposal, not used by the model");
  });
  it("adds no label when the table is used or the server does not say", () => {
    expect(text(body(trace({ forecast: { outyears: [outyear] } })))).not.toContain("not used by the model");
    expect(text(body(trace({ forecast: { outyears: [outyear], outyears_used: true } })))).not.toContain("not used by the model");
  });
});

describe("analyst peers and signals", () => {
  it("warns when the ranking used another peer group, naming the report's", () => {
    const html = text(body(trace({ analyst: analyst({ peers_stale: true,
      peers_current: { group: "MRO Asia", group_en: "Asian MRO", basis: "grup kurasi MRO", basis_en: null,
        as_of: "2026-09-20", source: "data/peer_groups/GMFI.json", members: ["SIAL", "STEC"] } }) })));
    expect(html).toContain("differs from the one the report now compares against");
    expect(html).toContain("The report's peer group: Asian MRO , as of Sep 20, 2026 · data/peer_groups/GMFI.json");
    expect(html).toContain("SIAL STEC");
    expect(html).toContain("grup kurasi MRO"); // no English twin: the Indonesian as sent
    expect(html).toContain("Research run group: Airport Operators");
  });
  it("says nothing about the peer group when staleness is unknown or false", () => {
    expect(text(body(trace({ analyst: analyst({ peers_stale: null }) })))).not.toContain("differs from");
    expect(text(body(trace({ analyst: analyst({ peers_stale: false }) })))).not.toContain("differs from");
  });
  it("dates the research run's peer table, or says why it cannot", () => {
    expect(text(body(trace({ analyst: analyst({ peers: { ...analyst().peers, as_of: "2026-09-11" } }) }))))
      .toContain("Basis: the Sectors peer table, as of Sep 11, 2026 .");
    expect(text(body(trace({ analyst: analyst({ peers: { ...analyst().peers, as_of: null, as_of_note: "Tanpa tanggal.",
      as_of_note_en: "The research run's peer table source states no snapshot date." } }) }))))
      .toContain("Basis: the Sectors peer table. The research run's peer table source states no snapshot date.");
  });
  it("marks outlier peers and reads the median in English figures", () => {
    const html = body(trace({ analyst: analyst() }));
    expect(text(html)).toContain("outlier AAAA 312.0x");
    expect(html).toContain("title=\"P/E far outside the group's range\"".replace("'", "&#x27;"));
    expect(text(html)).toContain("15.4x");
    expect(text(html)).not.toContain("15,4x");
    expect(text(html)).not.toContain("differs from");
  });
  it("says how many signals and news items are shown when the run found more", () => {
    expect(text(body(trace({ analyst: analyst({ signals_total: 140 }) })))).toContain("1 of 140 signals shown");
    expect(text(body(trace({ analyst: analyst({ signals_total: 1 }) })))).not.toContain("signals shown");
    const news = { window: "30d", total: 55, items: [{ title: "T", url: null, domain: null, date: "2026-09-01" }] };
    expect(text(body(trace({ analyst: analyst({ web_news: news }) })))).toContain("1 of 55 shown");
  });
});

describe("release readout", () => {
  it("labels the report date and dates in the reader's language", () => {
    const html = text(header(trace()));
    expect(html).toContain("Report date Sep 24, 2026");
    expect(html).toContain("Market price as of Sep 23, 2026");
    expect(html).not.toContain("Data as of");
  });
  it("reads the real review state: an auto-published report as not reviewed, never as awaiting review", () => {
    const html = text(header(trace({ review_state: "pending" })));
    expect(html).toContain("Auto-published · not analyst-reviewed");
    expect(html).not.toContain("awaiting analyst review");
    expect(text(header(trace({ review_state: "approved" })))).toContain("Published · analyst-reviewed");
    // Review-gated mode: cleared the gates, not public yet.
    const held = trace({ review_state: "pending" });
    held.report.published = false;
    expect(text(header(held))).toContain("Passed the gates, awaiting analyst review");
  });
});
