// Shapes returned by the Python API (app/server.py). Every field is
// whitelisted server-side; see app/jobs.py and app/trace_view.py.

export type ChainStep = { step: string; decision: string; value: string };

export type ReportItem = {
  ticker: string;
  name: string;
  date: string;
  price: number | null;
  published: boolean;
  rating: string | null;
  tp: number | null;
  upside: number | null;
  method: string;
  profile: string;
  headline: string;
  rating_status?: string | null;
  risks?: string[];
  chain: ChainStep[];
  blockers: number;
  held_reason: string;
  files: { pdf: boolean; html: boolean; trace: boolean; trace_json: boolean };
  review?: { state: ReviewState; reviewer: string | null; reviewed_at: string | null; decision: string | null; edits: number };
};

export type ReviewState = "approved" | "pending" | "no_plan";

/** One numeric driver of the Forecast Plan an analyst may change. */
export type ReviewField = {
  path: string;
  field: string;
  label: string;
  unit: "%" | "x";
  year: number | null;
  value: number;
  rationale: string;
};

export type ReviewEdit = {
  path: string; label: string; year: number | null; unit: string; from: number; to: number; reason: string;
  reviewer?: string | null; reviewed_at?: string | null;
};

export type ReviewHistory = { reviewer: string | null; reviewed_at: string | null; decision: string | null; edits: number; note: string | null };

export type ReviewView = {
  state: ReviewState;
  plan_sha: string | null;
  reviewer: string | null;
  reviewed_at: string | null;
  decision: "approved" | "approved_with_edits" | null;
  note: string | null;
  /** Every change behind the approved plan, including those from earlier approvals of it. */
  edits: ReviewEdit[];
  /** Earlier approvals, newest first. */
  history?: ReviewHistory[];
  stale: boolean;
  enabled: boolean;
  fields: ReviewField[];
};

export type HistoryItem = {
  ticker: string;
  runs: number;
  market_date: string | null;
  flags: number;
  pdf_url: string | null;
};

export type Signal = {
  id: string | null;
  kind: string | null;
  label: string | null;
  display: string | null;
  note: string | null;
  flag: string | null;
  period: string | null;
  median_display: string | null;
  rank: number | null;
  n: number | null;
  url?: string | null;
  peers?: { symbol: string | null; display: string | null }[];
};

export type Intel = {
  ticker: string | null;
  name: string | null;
  market_date: string | null;
  status: string | null;
  plan: { question: string | null; source: string | null; hypotheses: (string | null)[] };
  steps: { tool: string | null; why: string | null; summary: string | null; status: string | null; origin: string | null }[];
  signals: Signal[];
  peers: { basis: string | null; group: string | null };
  web_news: { window: string | null; items: { title: string | null; url: string | null; domain: string | null; date: string | null }[] };
  synthesis: {
    headline: string | null;
    source: string | null;
    findings: { title: string | null; interpretation: string | null; caveat: string | null; signal_ids: string[] }[];
    hypotheses: { index: number | null; verdict: string | null; reason: string | null; signal_ids: string[] }[];
    next_checks: (string | null)[];
  };
  changes: {
    first_run: boolean;
    same_market_date: boolean;
    previous_run_at: string | null;
    previous_market_date: string | null;
    items: { kind: string | null; text: string | null }[];
  };
};

/**
 * One progress event of a research run (app/progress.py). ``agent`` names the
 * emitter when the stage alone does not (e.g. "riset", "forecast.news");
 * ``data`` carries a few short structured fields (gate verdicts, method-chain
 * decisions, hypothesis numbers). See lib/agents.ts for how the Deck reads them.
 */
export type JobEvent = {
  stage: string;
  label: string;
  status: "ok" | "warn" | "error" | "run";
  t: number;
  detail?: string;
  tool?: string;
  agent?: string;
  data?: Record<string, string>;
};

/** A stored run to play back: recorded events, or events derived from its audit trace. */
export type RunReplay = {
  ticker: string;
  name: string | null;
  source: "recorded" | "derived";
  events: JobEvent[];
  report: ReportItem | null;
};

export type Job = {
  id: string;
  ticker: string;
  state: "pending" | "running" | "completed" | "error";
  events: JobEvent[];
  quality?: "partial" | "complete";
  report_url?: string;
  trace_url?: string;
  pdf_url?: string;
  gallery_url?: string;
  report_status?: string;
  intel?: Intel;
};

export type TraceView = {
  ticker: string;
  /** Gallery reports only: whether an analyst approved the Forecast Plan. */
  review_state?: ReviewState;
  /** Gallery reports only: sections kept out of the printed report (mining audit detail). */
  audit_appendix?: { title: string; paragraphs: string[];
    exhibits: { title: string; cols: string[]; rows: string[][]; note: string }[] }[];
  report: {
    release_status: string | null;
    published: boolean;
    rating: string | null;
    target_price: number | null;
    method: string | null;
    as_of: string | null;
    market_price_date: string | null;
  };
  analyst: Intel | null;
  analyst_problems: string[];
  research: {
    summary: string | null;
    endpoints: string[];
    insights: { title: string | null; observation: string | null; implication: string | null; caveat: string | null;
      citations: { endpoint: string | null; field_path: string | null; value: string | null }[] }[];
    limitations: string[];
  };
  news: {
    search: { status: string | null; as_of: string | null; queries: string[] };
    articles: { id: string | null; date: string | null; origins: string[]; title: string | null; url: string | null }[];
    rejected: { title: string | null; reason: string | null }[];
    rejected_total: number;
  };
  forecast: {
    status: string | null;
    problems: string[];
    news_effects: { driver: string | null; change: string | null; years: string[]; rationale: string | null; date: string | null;
      url: string | null; factual_basis: string | null; mechanism: string | null; uncertainty: string | null }[];
    interim: { rationale: string | null; published_at: string | null; url: string | null } | null;
    outyears: { year: string | null; revenue_growth_pct: number | null; ebitda_margin_pct: number | null;
      net_income_margin_pct: number | null; capex_to_revenue_pct: number | null; rationale: string | null; source_ids: string[] }[];
    /** Bank Driver Scenario: the interim year's H2 drivers, then the out-years (percent). */
    bank_drivers?: { year: string | null; loan_growth_pct: number | null; nim_pct: number | null; non_ii_to_nii_pct: number | null;
      cost_to_income_pct: number | null; cost_of_credit_pct: number | null; deposit_growth_pct: number | null;
      rationale: string | null; source_ids: string[] }[];
  };
  deepdive: { title: string | null; date: string | null; url: string | null; status: string | null; length: number; preview: string | null }[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init });
  if (!response.ok) {
    let detail = `Permintaan gagal (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  tickers: () => request<{ tickers: string[] }>("/api/tickers").then((r) => r.tickers),
  history: () => request<{ items: HistoryItem[] }>("/api/history").then((r) => r.items),
  reports: () => request<{ items: ReportItem[] }>("/api/reports").then((r) => r.items),
  reportRun: (ticker: string) => request<RunReplay>(`/api/reports/${encodeURIComponent(ticker)}/run`),
  reportTrace: (ticker: string) => request<TraceView>(`/api/reports/${encodeURIComponent(ticker)}/trace`),
  review: (ticker: string) => request<ReviewView>(`/api/reports/${encodeURIComponent(ticker)}/review`),
  approve: (ticker: string, token: string, body: { reviewer: string; note: string; edits: { path: string; value: number; reason: string }[] }) =>
    request<ReviewView>(`/api/reports/${encodeURIComponent(ticker)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Review-Token": token },
      body: JSON.stringify(body),
    }),
  job: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  jobTrace: (id: string) => request<TraceView>(`/api/jobs/${encodeURIComponent(id)}/trace`),
  submit: (ticker: string) =>
    request<{ id: string }>("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    }).then((r) => r.id),
};

/** Where a report's files live on the server. */
export const reportFiles = (t: string) => ({
  pdf: `/files/reports/${t}.pdf`,
  html: `/files/reports/${t}.html`,
  traceHtml: `/files/reports/${t}-trace.html`,
  cover: `/files/reports/${t}/cover.png`,
});
