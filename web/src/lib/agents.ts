// How the Deck reads a research run: which agent did what, which tool calls
// went out and came back, where the run is, and what the Method Gates and the
// method chain decided. Everything here is derived from the progress events
// (app/progress.py), so a live job and a replayed run render the same way.
import type { EventData, Intel, JobEvent } from "./api";
import { decisionCode, eventKind, gateCode, num, str, verdictCode, type DecisionCode, type EventKind, type GateCode, type VerdictCode } from "./codes";
import { idr, pct } from "./format";
import { getLang, twin, type Bi, type Lang } from "./i18n";

export type AgentId = "memori" | "analis" | "riset" | "berita" | "forecast" | "gerbang" | "laporan";
export type Status = "idle" | "run" | "ok" | "warn" | "error";

export type AgentMeta = {
  id: AgentId;
  name: Bi;
  short: Bi;
  role: Bi;
  /** "llm": a model decides; "host": deterministic code the model cannot change. */
  engine: "llm" | "host";
};

/** Pipeline order. */
export const AGENTS: AgentMeta[] = [
  {
    id: "memori", engine: "host",
    name: { id: "Memori riset", en: "Run memory" }, short: { id: "Memori", en: "Memory" },
    role: { id: "Membaca riset sebelumnya dan menyimpan hasil baru", en: "Reads earlier research and stores the new results" },
  },
  {
    id: "analis", engine: "llm",
    name: { id: "Agent perencana", en: "Planning agent" }, short: { id: "Perencana", en: "Planner" },
    role: { id: "Menyusun pertanyaan, memanggil tool data, menguji hipotesis", en: "Frames the questions, calls data tools, tests hypotheses" },
  },
  {
    id: "riset", engine: "llm",
    name: { id: "Agent riset", en: "Research agent" }, short: { id: "Riset", en: "Research" },
    role: { id: "Membaca endpoint Sectors dan menulis brief bersitasi", en: "Reads Sectors endpoints and writes a cited brief" },
  },
  {
    id: "berita", engine: "host",
    name: { id: "Pencari berita", en: "News search" }, short: { id: "Berita", en: "News" },
    role: { id: "Mencari berita bertanggal dan menolak yang tidak relevan", en: "Finds dated news and rejects what is not relevant" },
  },
  {
    id: "forecast", engine: "llm",
    name: { id: "Agent forecast", en: "Forecast agent" }, short: { id: "Forecast", en: "Forecast" },
    role: { id: "Subagent menyusun asumsi dari berita dan rilis resmi", en: "Subagents build assumptions from news and official releases" },
  },
  {
    id: "gerbang", engine: "host",
    name: { id: "Gerbang metode", en: "Method Gates" }, short: { id: "Gerbang", en: "Gates" },
    role: { id: "Method Gates 0–5 memilih metode; rantai metode menghitung nilai", en: "Method Gates 0–5 choose the method; the Method Chain computes the value" },
  },
  {
    id: "laporan", engine: "host",
    name: { id: "Penyusun laporan", en: "Report builder" }, short: { id: "Laporan", en: "Report" },
    role: { id: "Harness rilis, company update, PDF, dan jejak audit", en: "Release harness, Company Update, PDF and Audit Trace" },
  },
];

export const AGENT: Record<AgentId, AgentMeta> = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<AgentId, AgentMeta>;

/** Forecast subagents (agents/forecast_assumptions), in the order they can run. */
export const SUBAGENTS: { id: string; name: Bi }[] = [
  { id: "news", name: { id: "Dampak berita", en: "News impact" } },
  { id: "interim", name: { id: "Skenario interim", en: "Interim scenario" } },
  { id: "earnings", name: { id: "Skenario laba FY", en: "FY earnings scenario" } },
  { id: "stage", name: { id: "Tahap bisnis", en: "Business stage" } },
  { id: "outyears", name: { id: "Tahun lanjutan", en: "Out-years" } },
];

const STAGE_AGENT: Record<string, AgentId> = {
  memory: "memori", plan: "analis", tool: "analis", signals: "analis", synthesis: "analis",
  research: "riset", news: "berita", forecast: "forecast", gate: "gerbang", report: "laporan", done: "laporan",
};

export type PhaseMeta = { id: string; title: Bi; sub: Bi; stages: string[] };

export const PHASES: PhaseMeta[] = [
  {
    id: "rencana", stages: ["memory", "plan"],
    title: { id: "Rencana", en: "Plan" }, sub: { id: "Memori, pertanyaan, hipotesis", en: "Memory, questions, hypotheses" },
  },
  {
    id: "tool", stages: ["tool", "signals", "synthesis"],
    title: { id: "Tool & hipotesis", en: "Tools & hypotheses" }, sub: { id: "Data Sectors, peer, sinyal", en: "Sectors data, peers, signals" },
  },
  {
    id: "riset", stages: ["research", "news"],
    title: { id: "Riset & berita", en: "Research & news" }, sub: { id: "Brief bersitasi, berita bertanggal", en: "Cited brief, dated news" },
  },
  {
    id: "forecast", stages: ["forecast"],
    title: { id: "Forecast", en: "Forecast" }, sub: { id: "Subagent asumsi", en: "Assumption subagents" },
  },
  {
    id: "valuasi", stages: ["gate", "report", "done"],
    title: { id: "Valuasi & laporan", en: "Valuation & report" }, sub: { id: "Method Gates, rantai metode, harness", en: "Method Gates, Method Chain, harness" },
  },
];

const PHASE_OF: Record<string, number> = Object.fromEntries(
  PHASES.flatMap((p, i) => p.stages.map((s) => [s, i])),
);

export const GATES: { n: number; name: Bi }[] = [
  { n: 0, name: { id: "Model bisnis", en: "Business model" } },
  { n: 1, name: { id: "Kelayakan data", en: "Data eligibility" } },
  { n: 2, name: { id: "Struktur kepemilikan", en: "Ownership structure" } },
  { n: 3, name: { id: "Siklus & tahap operasi", en: "Cyclicality & operating stage" } },
  { n: 4, name: { id: "Tahap siklus hidup", en: "Life-cycle stage" } },
  { n: 5, name: { id: "Kewajaran hasil", en: "Output sanity" } },
];

export type StepKind = "task" | "call" | "note" | "hypothesis" | "verdict" | "gate" | "chain" | "release";

export type Step = {
  /** Index of the event that opened the step; stable across re-derivations. */
  id: number;
  agent: AgentId;
  /** Forecast subagent id (see SUBAGENTS) when a subagent emitted it. */
  sub?: string;
  kind: StepKind;
  stage: string;
  tool?: string;
  /** The opening event's label; this and the texts below read in the language `derive` was given. */
  title: string;
  /** What the opening event reports (lib/codes.ts `eventKind`), when it is one the Deck reads. */
  event?: EventKind;
  /** What the closing event reports, likewise. */
  resultEvent?: EventKind;
  /** Why the call or task started (the opening event's detail). */
  reason?: string;
  /** The closing event's label, when the step closed with a different one. */
  result?: string;
  resultDetail?: string;
  status: Status;
  t0: number;
  t1?: number;
  data?: EventData;
  parent?: number;
  children: number[];
};

export type AgentState = { status: Status; steps: number; calls: number; last?: string; lastEvent: number };
// Each verdict and decision keeps the label the pipeline sent and its code
// (lib/codes.ts: the server's code, else read from the label). Logic reads the code.
export type GateState = { n: number; name: Bi; status: "idle" | "ok" | "warn" | "skip"; verdict?: string; code?: GateCode; detail?: string };
export type ChainState = { method: string; decision: string; code?: DecisionCode; value: string; reason?: string; order: number };
export type Hypothesis = { index: number; text: string; verdict?: string; code?: VerdictCode; reason?: string };

export type DeckState = {
  steps: Step[];
  byId: Map<number, Step>;
  roots: Step[];
  agents: Record<AgentId, AgentState>;
  subagents: Record<string, Status>;
  phases: (PhaseMeta & { status: Status })[];
  phaseAt: number;
  gates: GateState[];
  chain: ChainState[];
  plan: { question?: string; hypotheses: Hypothesis[] };
  release?: EventData;
  counts: { events: number; calls: number; llmSteps: number; warnings: number };
  elapsed: number;
  /** The most recent step still running, if any. */
  active?: Step;
};

function kindOf(e: JobEvent): StepKind {
  const tool = e.tool ?? "";
  if (tool === "hypothesis") return "hypothesis";
  if (tool === "verdict") return "verdict";
  if (tool.startsWith("gate_")) return "gate";
  if (tool === "chain_step") return "chain";
  if (tool === "release") return "release";
  if (tool) return "call";
  return e.status === "run" ? "task" : "note";
}

export function agentOf(e: Pick<JobEvent, "agent" | "stage">): { agent: AgentId; sub?: string } {
  const [base, sub] = (e.agent ?? "").split(".");
  const agent = (base && base in AGENT ? base : STAGE_AGENT[e.stage] ?? "laporan") as AgentId;
  return { agent, sub: sub || undefined };
}

const RANK: Record<Status, number> = { idle: 0, ok: 1, run: 2, warn: 3, error: 4 };

/**
 * An event's label and detail in the reader's language: the server's
 * `label_en`/`detail_en` twins for an English reader where it sent them, the
 * Indonesian otherwise.
 */
export function eventText(e: Pick<JobEvent, "label" | "label_en" | "detail" | "detail_en">, lang: Lang = getLang()): { label: string; detail?: string } {
  return { label: twin(e, "label", lang), detail: twin(e, "detail", lang) ?? undefined };
}

/**
 * Read a run's events. ``finished`` closes steps that never reported back
 * (``failed`` marks them as errors instead). Step titles, reasons, results,
 * gate details, chain rows and the plan read in ``lang`` (`eventText`); what
 * each event reports is still read from its Indonesian label.
 */
export function derive(events: JobEvent[], opts: { finished?: boolean; failed?: boolean; lang?: Lang } = {}): DeckState {
  const lang = opts.lang ?? "id";
  const steps: Step[] = [];
  const byId = new Map<number, Step>();
  const open: Step[] = [];
  // The Indonesian label that opened each step: a closing event with the same label adds no result.
  const opened = new Map<number, string>();
  const plan: DeckState["plan"] = { hypotheses: [] };
  const gates: GateState[] = GATES.map((g) => ({ ...g, status: "idle" }));
  const chain: ChainState[] = [];
  let release: EventData | undefined;
  let phaseAt = -1;
  const lastEvent: Partial<Record<AgentId, number>> = {};

  const enclosing = (agent: AgentId, sub?: string): Step | undefined => {
    for (let i = open.length - 1; i >= 0; i--) {
      const s = open[i];
      if (s.agent === agent && s.kind === "task" && (s.sub === undefined || s.sub === sub)) return s;
    }
    return undefined;
  };

  const add = (step: Step) => {
    steps.push(step);
    byId.set(step.id, step);
    if (step.parent !== undefined) byId.get(step.parent)?.children.push(step.id);
  };

  events.forEach((e, i) => {
    const { agent, sub } = agentOf(e);
    const kind = kindOf(e);
    const { label, detail } = eventText(e, lang);
    lastEvent[agent] = i;
    phaseAt = Math.max(phaseAt, PHASE_OF[e.stage] ?? 0);

    if (kind === "hypothesis") {
      const index = Number(e.data?.index ?? plan.hypotheses.length + 1);
      plan.hypotheses.push({ index, text: detail ?? label });
    } else if (kind === "verdict") {
      const index = Number(e.data?.index);
      const h = plan.hypotheses.find((x) => x.index === index);
      const verdict = str(e.data?.verdict) ?? e.label;
      if (h) Object.assign(h, { verdict, code: verdictCode(e.data?.verdict_code, verdict), reason: detail });
    } else if (kind === "gate") {
      const n = Number(e.data?.gate ?? (e.tool ?? "").slice(5));
      const g = gates.find((x) => x.n === n);
      if (g) {
        const verdict = str(e.data?.verdict) ?? "";
        const code = gateCode(e.data?.verdict_code, verdict);
        Object.assign(g, {
          // A flagged check is disclosed, not passed: it reads as a warning even if its event said ok.
          status: code === "not_applicable" ? "skip" : code === "flagged" ? "warn" : e.status === "ok" ? "ok" : "warn",
          verdict, code, detail,
        });
      }
    } else if (kind === "chain") {
      const decision = str(e.data?.decision) ?? "";
      // The value in the reader's format: the English `value_en` ("Rp3,490") where the server sent one.
      const value = (lang === "en" ? str(e.data?.value_en) : undefined) ?? str(e.data?.value) ?? "-";
      chain.push({ method: label, decision, code: decisionCode(e.data?.decision_code, decision),
        value, reason: detail, order: chain.length });
    } else if (kind === "release") {
      release = e.data;
    }

    if (e.status === "run") {
      const parent = enclosing(agent, sub) ?? (agent === "gerbang" ? enclosing("laporan") : undefined);
      const step: Step = { id: i, agent, sub, kind, stage: e.stage, tool: e.tool, title: label, event: eventKind(e), reason: detail,
        status: "run", t0: e.t, data: e.data, parent: parent?.id, children: [] };
      add(step);
      opened.set(i, e.label);
      open.push(step);
      return;
    }

    // A closing event ends the most recent open step of the same emitter and tool.
    let match = -1;
    for (let j = open.length - 1; j >= 0; j--) {
      const s = open[j];
      if (s.agent === agent && s.sub === sub && (s.tool ?? "") === (e.tool ?? "")) { match = j; break; }
    }
    if (match >= 0) {
      const s = open[match];
      open.splice(match, 1);
      Object.assign(s, { status: e.status, t1: e.t, result: e.label !== opened.get(s.id) ? label : undefined,
        resultEvent: eventKind(e), resultDetail: detail, data: { ...s.data, ...e.data } });
      if (s.stage === "plan" && detail && !plan.question) plan.question = detail;
      return;
    }
    if (e.stage === "plan" && detail && !plan.question && kind === "note") plan.question = detail;
    const parent = enclosing(agent, sub) ?? (agent === "gerbang" ? enclosing("laporan") : undefined);
    add({ id: i, agent, sub, kind, stage: e.stage, tool: e.tool, title: label, event: eventKind(e), resultDetail: detail,
      status: e.status, t0: e.t, t1: e.t, data: e.data, parent: parent?.id, children: [] });
  });

  const elapsed = events.length ? events[events.length - 1].t : 0;
  if (opts.finished) {
    for (const s of open) Object.assign(s, { status: opts.failed ? "error" : "ok", t1: s.t1 ?? elapsed });
    open.length = 0;
  }

  const agents = Object.fromEntries(AGENTS.map((a) => {
    const mine = steps.filter((s) => s.agent === a.id);
    let status: Status = "idle";
    for (const s of mine) {
      const st: Status = s.status === "run" ? "run" : s.status;
      if (RANK[st] > RANK[status]) status = st;
    }
    // A finished agent that only carried warnings reads as done with notes,
    // unless it is still running.
    if (open.some((s) => s.agent === a.id)) status = "run";
    else if (status === "run") status = "ok";
    const last = mine[mine.length - 1];
    return [a.id, { status, steps: mine.length, calls: mine.filter((s) => s.kind === "call").length,
      last: last ? (last.result ?? last.title) : undefined, lastEvent: lastEvent[a.id] ?? -1 }];
  })) as Record<AgentId, AgentState>;

  const subagents: Record<string, Status> = {};
  for (const s of steps) if (s.agent === "forecast" && s.sub) subagents[s.sub] = s.status;

  const phases = PHASES.map((p, i) => {
    let status: Status = "idle";
    if (i < phaseAt || (i === phaseAt && opts.finished)) {
      status = steps.some((s) => p.stages.includes(s.stage) && (s.status === "warn" || s.status === "error")) ? "warn" : "ok";
      if (opts.failed && i === phaseAt) status = "error";
    } else if (i === phaseAt) status = "run";
    return { ...p, status };
  });

  const running = steps.filter((s) => s.status === "run");
  return {
    steps, byId, roots: steps.filter((s) => s.parent === undefined), agents, subagents, phases, phaseAt,
    gates, chain, plan, release,
    counts: {
      events: events.length,
      calls: steps.filter((s) => s.kind === "call").length,
      llmSteps: steps.filter((s) => AGENT[s.agent].engine === "llm" && (s.kind === "task" || s.kind === "call")).length,
      warnings: steps.filter((s) => s.status === "warn" || s.status === "error").length,
    },
    elapsed,
    active: running[running.length - 1],
  };
}

/**
 * The release's target price and upside for display: the raw `tp_value` and
 * `upside_pct` in the reader's format, else (an older event) the Indonesian
 * `tp` and `upside` strings as sent. `down` says the upside is negative.
 */
export function releaseFigures(release: EventData | undefined, lang: Lang = getLang()): { tp?: string; upside?: string; down: boolean } {
  const tpValue = num(release?.tp_value);
  const upsideValue = num(release?.upside_pct);
  const tp = tpValue !== undefined ? idr(tpValue, lang) : str(release?.tp);
  const upside = upsideValue !== undefined ? `${upsideValue > 0 ? "+" : ""}${pct(upsideValue, lang)}` : str(release?.upside);
  const down = upsideValue !== undefined ? upsideValue < 0 : /^[−-]/.test(upside ?? "");
  return { tp, upside, down };
}

/** Event details are cut at 400 characters (app/progress.py), so text is compared on that much. */
const same = (a: string | null | undefined, b: string | null | undefined) =>
  Boolean(a && b) && a!.trim().slice(0, 400) === b!.trim().slice(0, 400);

/**
 * The plan in the reader's language. Run events carry the analyst's
 * Indonesian only; for an English reader the question, each hypothesis and
 * each verdict reason take the English twin from the analyst result
 * (`intel`) where it holds the same Indonesian text, and stay Indonesian
 * otherwise (no twin, or a result from another run).
 */
export function planIn(plan: DeckState["plan"], intel: Intel | null | undefined, lang: Lang): DeckState["plan"] {
  if (lang !== "en" || !intel) return plan;
  const question = same(plan.question, intel.plan.question) ? twin(intel.plan, "question", lang) ?? plan.question : plan.question;
  const texts = twin(intel.plan, "hypotheses", lang);
  const hypotheses = plan.hypotheses.map((h) => {
    const at = h.index - 1;
    const text = same(h.text, intel.plan.hypotheses[at]) ? texts[at] ?? h.text : h.text;
    // Synthesis numbers hypotheses from 0; the plan events from 1.
    const verdict = intel.synthesis.hypotheses.find((v) => v.index === at);
    const reason = verdict && same(h.reason, verdict.reason) ? twin(verdict, "reason", lang) ?? h.reason : h.reason;
    return text === h.text && reason === h.reason ? h : { ...h, text, reason };
  });
  return { question, hypotheses };
}

const UNIT: Bi<{ s: string; m: string; comma: boolean }> = {
  id: { s: "dtk", m: "mnt", comma: true },
  en: { s: "s", m: "min", comma: false },
};

/** "12,4 dtk" or "2 mnt 05 dtk" ("12.4 s", "2 min 05 s") for elapsed seconds. */
export function duration(seconds: number | undefined, lang: Lang = getLang()): string {
  if (seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "";
  const unit = UNIT[lang];
  // Round once, then split: 59.96 s reads "1 min 00 s" and 119.6 s "2 min 00 s", never "60 s".
  const tenths = Math.round(seconds * 10);
  if (tenths < 600) {
    const text = (tenths / 10).toFixed(1);
    return `${unit.comma ? text.replace(".", ",") : text} ${unit.s}`;
  }
  const whole = Math.round(seconds);
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  return `${m} ${unit.m} ${String(s).padStart(2, "0")} ${unit.s}`;
}

/**
 * How many Method Gates a run actually assessed: a gate that does not apply
 * to the issuer, or could not be assessed, is counted apart, not as assessed.
 */
export function gateTally(gates: GateState[]) {
  const read = gates.filter((g) => g.status !== "idle");
  const notApplicable = read.filter((g) => g.code === "not_applicable" || (!g.code && g.status === "skip")).length;
  const notAssessable = read.filter((g) => g.code === "not_assessable").length;
  return { total: gates.length, read: read.length, assessed: read.length - notApplicable - notAssessable, notApplicable, notAssessable };
}

/** "4/6 dinilai, 2 tidak berlaku" ("4/6 assessed, 2 not applicable"). */
export function gateTallyText(gates: GateState[], lang: Lang = getLang()): string {
  const { total, assessed, notApplicable, notAssessable } = gateTally(gates);
  const parts = [lang === "en" ? `${assessed}/${total} assessed` : `${assessed}/${total} dinilai`];
  if (notApplicable) parts.push(lang === "en" ? `${notApplicable} not applicable` : `${notApplicable} tidak berlaku`);
  if (notAssessable) parts.push(lang === "en" ? `${notAssessable} cannot be assessed` : `${notAssessable} tidak dapat dinilai`);
  return parts.join(", ");
}

/** Status words of the deck (from the Command Deck: ANTRI / JALAN / SELESAI). */
export const STATUS_WORD: Record<Status, Bi> = {
  idle: { id: "Antri", en: "Queued" },
  run: { id: "Jalan", en: "Running" },
  ok: { id: "Selesai", en: "Done" },
  warn: { id: "Catatan", en: "Notes" },
  error: { id: "Gagal", en: "Failed" },
};
