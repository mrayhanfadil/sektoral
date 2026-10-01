// Shapes returned by the Python API (app/server.py). Every field is
// whitelisted server-side; see app/jobs.py and app/trace_view.py.

import { pick } from "./i18n";

/**
 * One Method Chain row; `decision` is the Indonesian label, `decision_code` its stable code (#34).
 * `step_en` is the method's English name and `value_en` the value in English figures ("Rp3,490"),
 * where the server has them.
 */
export type ChainStep = {
  step: string; step_en?: string | null; decision: string; decision_code?: string; value: string; value_en?: string | null;
};

/** Report languages: Bahasa Indonesia always, English once it is part of the published bundle. */
export type ReportLang = "id" | "en";

export type ReportItem = {
  ticker: string;
  name: string;
  date: string;
  release_status: "production_ready" | "distributable_assumption_led" | "draft_non_distributable" | string;
  analytically_eligible: boolean;
  publication_state: "built" | "review_pending" | "auto_published" | "published" | "superseded" | "withdrawn";
  price: number | null;
  /** ISO date of the close behind `price` and the upside; older servers omit it. */
  price_date?: string | null;
  published: boolean;
  /** Policy 1.3.0: published on the automatic gates, or also approved by an analyst. */
  publication_basis?: "automatic" | "analyst_reviewed" | null;
  rating: string | null;
  tp: number | null;
  upside: number | null;
  // Host-written text: Indonesian, with an English twin `<field>_en` where the
  // server has one (lib/i18n.ts `twin`).
  method: string;
  method_en?: string | null;
  profile: string;
  profile_en?: string | null;
  headline: string;
  headline_en?: string | null;
  rating_status?: string | null;
  risks?: string[];
  risks_en?: (string | null)[];
  chain: ChainStep[];
  blockers: number | null;
  held_reason: string;
  held_reason_en?: string | null;
  /** Release policy freshness: a stale view stays visible with its reason. */
  freshness?: { state: "current" | "stale" | "withdrawal_due"; reason?: string | null; reason_en?: string | null;
    triggers?: string[]; triggers_en?: (string | null)[] } | null;
  /** Public languages of the report (`[]` when unpublished); older servers omit it and publish Indonesian only. */
  languages?: ReportLang[];
  files: { pdf: boolean; html: boolean; trace: boolean; trace_json: boolean; html_en?: boolean; pdf_en?: boolean };
  review?: { state: ReviewState; reviewer: string | null; reviewed_at: string | null; decision: string | null; edits: number };
};

export type ArchivedPublication = {
  state: "archived";
  publication_state: "superseded";
  ticker: string;
  publication_id: string;
  archived_at: string | null;
  review_sha: string | null;
  artifact_hashes: { html: string | null; pdf: string | null; trace_html: string | null;
    html_en?: string | null; pdf_en?: string | null };
  files: { html: string | null; pdf: string | null; trace: string | null; html_en?: string | null; pdf_en?: string | null };
};

export type ReviewState = "approved" | "pending" | "no_plan";

/** One numeric driver of the Forecast Plan an analyst may change. */
export type ReviewField = {
  path: string;
  field: string;
  label: string;
  label_en?: string | null;
  unit: "%" | "x";
  year: number | null;
  value: number;
  rationale: string;
  rationale_en?: string | null;
};

export type ReviewEdit = {
  path: string; label: string; label_en?: string | null; year: number | null; unit: string; from: number; to: number; reason: string;
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

/** A computed signal; its host-written words may carry English twins `<field>_en`. */
export type Signal = {
  id: string | null;
  kind: string | null;
  label: string | null;
  label_en?: string | null;
  display: string | null;
  display_en?: string | null;
  note: string | null;
  note_en?: string | null;
  flag: string | null;
  flag_en?: string | null;
  period: string | null;
  period_en?: string | null;
  median_display: string | null;
  median_display_en?: string | null;
  rank: number | null;
  n: number | null;
  url?: string | null;
  /** Peers ranked on the metric; `outlier` marks a value far outside the group's range, `outlier_note` says why. */
  peers?: { symbol: string | null; display: string | null; display_en?: string | null; outlier?: boolean | null;
    outlier_note?: string | null; outlier_note_en?: string | null }[];
};

/**
 * The research run's peer group. `as_of` dates its source; when the source has no date,
 * `as_of_note` says so (older servers send neither).
 */
export type PeerGroup = {
  basis: string | null; basis_en?: string | null; group: string | null; group_en?: string | null;
  as_of?: string | null; as_of_note?: string | null; as_of_note_en?: string | null;
};

/** The report's own peer group, when the research run ranked against another one. */
export type CurrentPeers = {
  group: string | null; group_en?: string | null; basis: string | null; basis_en?: string | null;
  as_of: string | null; source: string | null; members: string[];
};

// Agent and host text fields may carry an English twin `<field>_en` (#34);
// lib/i18n.ts `twin` picks it for English readers and falls back to the Indonesian.
export type Intel = {
  ticker: string | null;
  name: string | null;
  market_date: string | null;
  status: string | null;
  plan: { question: string | null; question_en?: string | null; source: string | null;
    hypotheses: (string | null)[]; hypotheses_en?: (string | null)[] };
  steps: { tool: string | null; why: string | null; why_en?: string | null; summary: string | null; summary_en?: string | null;
    status: string | null; origin: string | null }[];
  signals: Signal[];
  /** How many signals the run computed; `signals` lists at most 120. */
  signals_total?: number | null;
  peers: PeerGroup;
  /** The research run ranked against another peer group than the report's (`peers_current`); null when unknown. */
  peers_stale?: boolean | null;
  peers_current?: CurrentPeers | null;
  /** `total`: how many items the run found; `items` lists at most 40. */
  web_news: { window: string | null; total?: number | null;
    items: { title: string | null; url: string | null; domain: string | null; date: string | null }[] };
  synthesis: {
    headline: string | null;
    headline_en?: string | null;
    source: string | null;
    findings: { title: string | null; title_en?: string | null; interpretation: string | null; interpretation_en?: string | null;
      caveat: string | null; caveat_en?: string | null; signal_ids: string[] }[];
    hypotheses: { index: number | null; verdict: string | null; verdict_code?: string | null;
      reason: string | null; reason_en?: string | null; signal_ids: string[] }[];
    next_checks: (string | null)[];
    next_checks_en?: (string | null)[];
  };
  changes: {
    first_run: boolean;
    same_market_date: boolean;
    previous_run_at: string | null;
    previous_market_date: string | null;
    items: { kind: string | null; text: string | null; text_en?: string | null }[];
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
  /** Indonesian; logic reads it (lib/codes.ts `eventKind`). */
  label: string;
  /** English twins of the label and detail, where the server has them. */
  label_en?: string | null;
  status: "ok" | "warn" | "error" | "run";
  t: number;
  detail?: string;
  detail_en?: string | null;
  tool?: string;
  agent?: string;
  data?: EventData;
};

/**
 * Short structured fields of an event. Mostly strings; the release event's
 * `tp_value` and `upside_pct` are numbers (#34). Read them with lib/codes.ts
 * `str` and `num`.
 */
export type EventData = Record<string, string | number>;

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

/** A validator note: its message and the tokens it asked the model to remove. */
export type ProblemNote = { message: string; message_en?: string | null; removed: string[] };

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
    /** Hash of the English source-text translations the report prose loaded (#34); older manifests lack it. */
    source_text_en_sha256?: string | null;
  } | null;
  /** Gallery reports only: whether an analyst approved the Forecast Plan. */
  review_state?: ReviewState;
  /** Gallery reports only: sections kept out of the printed report (mining audit detail). */
  audit_appendix?: AppendixPage[];
  report: {
    release_status: string | null;
    published: boolean;
    rating: string | null;
    target_price: number | null;
    method: string | null;
    method_en?: string | null;
    as_of: string | null;
    market_price_date: string | null;
  };
  analyst: Intel | null;
  analyst_problems: string[];
  analyst_problems_en?: (string | null)[];
  /** The same notes parsed server-side (#34); older traces carry only `analyst_problems`. */
  analyst_problem_notes?: ProblemNote[];
  research: {
    summary: string | null;
    summary_en?: string | null;
    endpoints: string[];
    insights: { title: string | null; title_en?: string | null; observation: string | null; observation_en?: string | null;
      implication: string | null; implication_en?: string | null; caveat: string | null; caveat_en?: string | null;
      citations: { endpoint: string | null; field_path: string | null; value: string | null; value_en?: string | null }[] }[];
    limitations: string[];
    limitations_en?: (string | null)[];
  };
  news: {
    search: { status: string | null; status_en?: string | null; as_of: string | null; queries: string[] };
    articles: { id: string | null; date: string | null; origins: string[]; title: string | null; url: string | null }[];
    rejected: { title: string | null; reason: string | null; reason_en?: string | null }[];
    rejected_total: number;
  };
  forecast: {
    status: string | null;
    problems: string[];
    problems_en?: (string | null)[];
    news_effects: { driver: string | null; change: string | null; years: string[]; rationale: string | null; rationale_en?: string | null;
      date: string | null; url: string | null; factual_basis: string | null; factual_basis_en?: string | null;
      mechanism: string | null; mechanism_en?: string | null; uncertainty: string | null; uncertainty_en?: string | null }[];
    interim: { rationale: string | null; rationale_en?: string | null; published_at: string | null; url: string | null } | null;
    /** The agent's out-year table (`analyst_assumption`: the row is the analyst's own scenario). */
    outyears: OutyearRow[];
    /** Whether the model forecast is the agent's table; false when it follows its own schedule (LoM, Operating Model). Null: unknown. */
    outyears_used?: boolean | null;
    outyears_note?: string | null;
    outyears_note_en?: string | null;
    /** The model's own out-years, set when `outyears_used` is false. */
    outyears_model?: OutyearRow[] | null;
    /** Bank Driver Scenario: the interim year's H2 drivers, then the out-years (percent), as the agent proposed them. */
    bank_drivers?: BankDriverRow[];
    /** Whether the bank model ran the agent's drivers; null when unknown. */
    bank_drivers_used?: boolean | null;
    /** The drivers the bank model ran, set when `bank_drivers_used` is false. */
    bank_drivers_model?: BankDriverRow[] | null;
    /** Why the agent's proposal was not used. */
    bank_drivers_note?: string | null;
    bank_drivers_note_en?: string | null;
    /** The basis of the model's payout path (`payout_pct`). */
    bank_payout_rationale?: string | null;
    bank_payout_rationale_en?: string | null;
    /** Spec §5.4 key risks of the earnings scenario; older servers omit them. */
    key_risks?: { category: string | null; category_en?: string | null; headline: string | null; headline_en?: string | null;
      explanation: string | null; explanation_en?: string | null; source_ids: string[] }[];
    /** What could move the scenario, when, through which drivers and which way (`direction`: Positif, Negatif, Dua arah). */
    catalysts?: { item: string | null; item_en?: string | null; timing: string | null; timing_en?: string | null;
      driver_path: string | null; driver_path_en?: string | null; direction: string | null; direction_en?: string | null;
      source_ids: string[] }[];
  };
  deepdive: { title: string | null; date: string | null; url: string | null; status: string | null; length: number; preview: string | null }[];
};

/** One out-year of the earnings forecast (percent). */
export type OutyearRow = {
  year: string | null; revenue_growth_pct: number | null; ebitda_margin_pct: number | null;
  net_income_margin_pct: number | null; capex_to_revenue_pct: number | null; rationale: string | null; rationale_en?: string | null;
  source_ids: string[]; analyst_assumption?: boolean | null;
};

/** What a model driver rests on. */
export type DriverKind = "company_guidance" | "sourced" | "analyst_assumption";

/**
 * One year of bank drivers (percent). Agent rows may be `analyst_assumption`; model rows carry
 * `payout_pct`, each driver's `kinds` and the `source` file they come from.
 */
export type BankDriverRow = {
  year: string | null; loan_growth_pct: number | null; nim_pct: number | null; non_ii_to_nii_pct: number | null;
  cost_to_income_pct: number | null; cost_of_credit_pct: number | null; deposit_growth_pct: number | null;
  payout_pct?: number | null; kinds?: Record<string, DriverKind | string | null> | null;
  rationale: string | null; rationale_en?: string | null; source_ids?: string[]; source?: string | null;
  analyst_assumption?: boolean | null;
};

/** A report section kept out of the printed Company Update; every text may carry an English twin. */
export type AppendixPage = {
  title: string;
  title_en?: string | null;
  paragraphs: string[];
  paragraphs_en?: (string | null)[];
  exhibits: AppendixExhibit[];
};

export type AppendixExhibit = {
  title: string;
  title_en?: string | null;
  cols: string[];
  cols_en?: (string | null)[];
  rows: string[][];
  rows_en?: (string | null)[][];
  note: string;
  note_en?: string | null;
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
  reviewArtifact: (ticker: string, token: string, kind: PreviewKind) =>
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

/** The bundle files a reviewer can preview before publication. */
export type PreviewKind = "pdf" | "html" | "trace" | "html_en" | "pdf_en";

/** Whether the report is published in English: `languages` from the server, else its English file flags. */
export function hasEnglish(item: Pick<ReportItem, "languages" | "files"> | null | undefined): boolean {
  if (!item) return false;
  return item.languages ? item.languages.includes("en") : Boolean(item.files.html_en || item.files.pdf_en);
}

/**
 * Where a report's files live on the server. `html`, `pdf` and the `cover`
 * thumbnail of that PDF follow the reader: the English files when ``lang`` is
 * English and ``english`` says the report is published in English, else the
 * Indonesian ones.
 */
export const reportFiles = (t: string, lang: ReportLang = "id", english = false) => {
  const suffix = lang === "en" && english ? ".en" : "";
  return {
    pdf: `/files/reports/${t}${suffix}.pdf`,
    html: `/files/reports/${t}${suffix}.html`,
    traceHtml: `/files/reports/${t}-trace.html`,
    cover: `/files/reports/${t}/cover${suffix}.png`,
  };
};

/** A report's files in the reader's language, as far as its item says English is published. */
export const readerFiles = (item: Pick<ReportItem, "ticker" | "languages" | "files">, lang: ReportLang) =>
  reportFiles(item.ticker, lang, hasEnglish(item));

/**
 * A finished job's report files in the reader's language. A job's own run
 * folder is never served (`/files/jobs/...` answers 404: a run can be
 * superseded, and only the gated gallery bundle is public), so the job
 * snapshot links to the gallery bundle once it is publishable. An English
 * reader gets that bundle's English edition when the gallery `item` lists it;
 * a link the snapshot does not give stays absent.
 */
export function jobFiles(job: Pick<Job, "ticker" | "report_url" | "pdf_url">,
  item: Pick<ReportItem, "ticker" | "languages" | "files"> | undefined, lang: ReportLang): { html?: string; pdf?: string } {
  const files = item && item.ticker === job.ticker ? readerFiles(item, lang) : undefined;
  return {
    html: job.report_url && (files?.html ?? job.report_url),
    pdf: job.pdf_url && (files?.pdf ?? job.pdf_url),
  };
}
