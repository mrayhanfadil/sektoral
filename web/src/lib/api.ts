// Shapes returned by the Python API (app/server.py). Every field is
// whitelisted server-side; see app/jobs.py and app/trace_view.py.

import { pick } from "./i18n";

export type ChainStep = { step: string; decision: string; value: string };

export type ReportItem = {
  ticker: string;
  name: string;
  date: string;
  release_status: "production_ready" | "distributable_assumption_led" | "draft_non_distributable" | string;
  analytically_eligible: boolean;
  publication_state: "built" | "review_pending" | "auto_published" | "published" | "superseded" | "withdrawn";
  price: number | null;
  published: boolean;
  /** Policy 1.3.0: published on the automatic gates, or also approved by an analyst. */
  publication_basis?: "automatic" | "analyst_reviewed" | null;
  rating: string | null;
  tp: number | null;
  upside: number | null;
  method: string;
  profile: string;
  headline: string;
  rating_status?: string | null;
  risks?: string[];
  chain: ChainStep[];
  blockers: number | null;
  held_reason: string;
  /** Release policy freshness: a stale view stays visible with its reason. */
  freshness?: { state: "current" | "stale" | "withdrawal_due"; reason?: string | null; triggers?: string[] } | null;
  files: { pdf: boolean; html: boolean; trace: boolean; trace_json: boolean };
  review?: { state: ReviewState; reviewer: string | null; reviewed_at: string | null; decision: string | null; edits: number };
};

export type ArchivedPublication = {
  state: "archived";
  publication_state: "superseded";
  ticker: string;
  publication_id: string;
  archived_at: string | null;
  review_sha: string | null;
  artifact_hashes: { html: string | null; pdf: string | null; trace_html: string | null };
  files: { html: string | null; pdf: string | null; trace: string | null };
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

export type ReviewAttestation = {
  schema_version: string;
  disposition: "approved";
  reviewer?: string;
  reviewer_id?: string;
  reviewer_role?: string;
  identity_source?: string;
  reviewed_at?: string;
  policy_version?: string;
  publication_fingerprint?: string;
  reviewed_source_ids: string[];
  checklist: Record<string, {
    status: string;
    note: string;
    source_ids: string[];
    period?: string;
    items?: { assumption_id: string; description: string; value_sensitivity: string; source_ids: string[] }[];
  }>;
  objections: { objection: string; response: string; disposition: "resolved" | "accepted"; source_ids: string[] }[];
  required_edits: { description: string; status: "completed" | "not_required" }[];
  disclosures: Record<string, string | { status: "none" | "disclosed" | "unknown"; details: string }>;
  overrides: { description: string; justification: string; policy_version: string }[];
};

export type ReviewSchemaNode = {
  type?: string;
  title?: string;
  const?: string;
  enum?: string[];
  required?: string[];
  properties?: Record<string, ReviewSchemaNode>;
  items?: ReviewSchemaNode;
  minLength?: number;
  minItems?: number;
};

export type ReviewAttestationSchema = {
  $schema: string;
  type: "object";
  required: string[];
  properties: Record<string, ReviewSchemaNode>;
  "x-system-recorded": string[];
};

export type ReviewView = {
  state: ReviewState;
  plan_sha?: string | null;
  reviewer?: string | null;
  reviewer_id?: string | null;
  reviewer_role?: string | null;
  identity_source?: string | null;
  current_reviewer?: { id: string; name: string; role: string } | null;
  reviewed_at?: string | null;
  decision?: "approved" | "approved_with_edits" | null;
  note?: string | null;
  /** Every change behind the approved plan, including those from earlier approvals of it. */
  edits: ReviewEdit[];
  /** Earlier approvals, newest first. */
  history?: ReviewHistory[];
  stale?: boolean;
  enabled: boolean;
  fields?: ReviewField[];
  missing_artifacts?: string[];
  manifest_errors?: string[];
  publication_id?: string | null;
  attestation?: ReviewAttestation | null;
  attestation_schema?: ReviewAttestationSchema | null;
  available_source_ids?: { id: string; kind: string | null; label: string;
    period: string | number | number[] | null; source: string | null }[];
  evidence_register_errors?: string[];
  /** A starting point written from the report's own evidence; the reviewer edits it. */
  attestation_draft?: AttestationDraft | null;
};

export type AttestationDraft = {
  checklist: Record<string, { status: string; note: string; source_ids: string[]; period?: string;
    items?: { assumption_id: string; description: string; value_sensitivity: string; source_ids: string[] }[] }>;
  disclosures: Record<string, string>;
  note: string;
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
  run_manifest?: {
    publication_id: string | null;
    code_revision: string | null;
    source_tree_sha256: string | null;
    working_tree: { dirty: boolean | null; sha256: string | null };
    as_of: string | null;
    profile: string | null;
    forecast_basis: string | null;
    production_ready: boolean | null;
    model: { forecast_agent: string | null; agent_effort: string | null; schema_version: number | null };
    spec_sha256: string | null;
    evidence_register_sha256: string | null;
    release_policy: { version: string | null; effective_date: string | null; status: string | null;
      sha256: string | null; ambiguities: string[] } | null;
    house_assumptions: { version: string | null; documented_as_of: string | null;
      effective_from: string | null; status: string | null; sha256: string | null;
      idr: { risk_free: number | null; risk_free_basis: string | null;
        country_risk_premium: number | null; beta: number | null;
        equity_risk_premium: number | null; cost_of_debt_pretax: number | null;
        cost_of_debt_basis: string | null; terminal_growth: number | null;
        growth_sensitivity: number[] | null; rate_sensitivity: number[] | null };
      usd: { risk_free: number | null; risk_free_basis: string | null;
        country_risk_premium: number | null; beta: number | null;
        equity_risk_premium: number | null; cost_of_debt_pretax: number | null;
        cost_of_debt_basis: string | null; terminal_growth: number | null;
        growth_sensitivity: number[] | null; rate_sensitivity: number[] | null };
      unresolved: string[] } | null;
    source_pack_sha256: Record<string, string | null>;
    cache_snapshot_sha256: Record<string, { cache_key: string | null; content_sha256: string | null }>;
    artifacts: Record<string, { file: string | null; sha256: string | null }>;
    missing_artifacts: string[];
  } | null;
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

/** The fallback message when the server sends no detail of its own. */
const requestFailed = (status: number) =>
  pick({ id: `Permintaan gagal (${status}).`, en: `Request failed (${status}).` });

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init });
  if (!response.ok) {
    let detail = requestFailed(response.status);
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

async function requestBlob(path: string, token: string): Promise<Blob> {
  const response = await fetch(path, {
    cache: "no-store", headers: { "X-Review-Token": token },
  });
  if (!response.ok) {
    let detail = requestFailed(response.status);
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}

export const api = {
  tickers: () => request<{ tickers: string[] }>("/api/tickers").then((r) => r.tickers),
  history: () => request<{ items: HistoryItem[] }>("/api/history").then((r) => r.items),
  reports: () => request<{ items: ReportItem[] }>("/api/reports").then((r) => r.items),
  reportArchives: (ticker: string) => request<{ items: ArchivedPublication[] }>(
    `/api/reports/${encodeURIComponent(ticker)}/archives`,
  ).then((r) => r.items),
  reportRun: (ticker: string) => request<RunReplay>(`/api/reports/${encodeURIComponent(ticker)}/run`),
  reportTrace: (ticker: string) => request<TraceView>(`/api/reports/${encodeURIComponent(ticker)}/trace`),
  reportTracePreview: (ticker: string, token: string) =>
    request<TraceView>(`/api/reports/${encodeURIComponent(ticker)}/trace/preview`, {
      headers: { "X-Review-Token": token },
    }),
  reviewArtifact: (ticker: string, token: string, kind: "pdf" | "html" | "trace") =>
    requestBlob(`/api/reports/${encodeURIComponent(ticker)}/artifact-preview/${kind}`, token),
  review: (ticker: string, token?: string) => request<ReviewView>(
    `/api/reports/${encodeURIComponent(ticker)}/review`,
    token ? { headers: { "X-Review-Token": token } } : undefined,
  ),
  approve: (ticker: string, token: string, body: { note: string; edits: { path: string; value: number; reason: string }[]; attestation: ReviewAttestation }) =>
    request<ReviewView>(`/api/reports/${encodeURIComponent(ticker)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Review-Token": token },
      body: JSON.stringify(body),
    }),
  job: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  jobTrace: (id: string) => request<TraceView>(`/api/jobs/${encodeURIComponent(id)}/trace`),
  config: () => request<{ live_runs: "open" | "token" | "off"; review: boolean }>("/api/config"),
  submit: (ticker: string, runToken?: string) =>
    request<{ id: string }>("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(runToken ? { "X-Run-Token": runToken } : {}) },
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
