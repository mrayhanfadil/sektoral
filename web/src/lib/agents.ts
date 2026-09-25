// How the Deck reads a research run: which agent did what, which tool calls
// went out and came back, where the run is, and what the Method Gates and the
// method chain decided. Everything here is derived from the progress events
// (app/progress.py), so a live job and a replayed run render the same way.
import type { JobEvent } from "./api";

export type AgentId = "memori" | "analis" | "riset" | "berita" | "forecast" | "gerbang" | "laporan";
export type Status = "idle" | "run" | "ok" | "warn" | "error";

export type AgentMeta = {
  id: AgentId;
  name: string;
  short: string;
  role: string;
  /** "llm": a model decides; "host": deterministic code the model cannot change. */
  engine: "llm" | "host";
};

/** Pipeline order. */
export const AGENTS: AgentMeta[] = [
  { id: "memori", name: "Memori riset", short: "Memori", role: "Membaca riset sebelumnya dan menyimpan hasil baru", engine: "host" },
  { id: "analis", name: "Agent perencana", short: "Perencana", role: "Menyusun pertanyaan, memanggil tool data, menguji hipotesis", engine: "llm" },
  { id: "riset", name: "Agent riset", short: "Riset", role: "Membaca endpoint Sectors dan menulis brief bersitasi", engine: "llm" },
  { id: "berita", name: "Pencari berita", short: "Berita", role: "Mencari berita bertanggal dan menolak yang tidak relevan", engine: "host" },
  { id: "forecast", name: "Agent forecast", short: "Forecast", role: "Subagent menyusun asumsi dari berita dan rilis resmi", engine: "llm" },
  { id: "gerbang", name: "Gerbang metode", short: "Gerbang", role: "Method Gates 0–5 memilih metode; rantai metode menghitung nilai", engine: "host" },
  { id: "laporan", name: "Penyusun laporan", short: "Laporan", role: "Harness rilis, company update, PDF, dan jejak audit", engine: "host" },
];

export const AGENT: Record<AgentId, AgentMeta> = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<AgentId, AgentMeta>;

/** Forecast subagents (agents/forecast_assumptions), in the order they can run. */
export const SUBAGENTS: { id: string; name: string }[] = [
  { id: "news", name: "Dampak berita" },
  { id: "interim", name: "Skenario interim" },
  { id: "earnings", name: "Skenario laba FY" },
  { id: "stage", name: "Tahap bisnis" },
  { id: "outyears", name: "Tahun lanjutan" },
];

const STAGE_AGENT: Record<string, AgentId> = {
  memory: "memori", plan: "analis", tool: "analis", signals: "analis", synthesis: "analis",
  research: "riset", news: "berita", forecast: "forecast", gate: "gerbang", report: "laporan", done: "laporan",
};

export type PhaseMeta = { id: string; title: string; sub: string; stages: string[] };

export const PHASES: PhaseMeta[] = [
  { id: "rencana", title: "Rencana", sub: "Memori, pertanyaan, hipotesis", stages: ["memory", "plan"] },
  { id: "tool", title: "Tool & hipotesis", sub: "Data Sectors, peer, sinyal", stages: ["tool", "signals", "synthesis"] },
  { id: "riset", title: "Riset & berita", sub: "Brief bersitasi, berita bertanggal", stages: ["research", "news"] },
  { id: "forecast", title: "Forecast", sub: "Subagent asumsi", stages: ["forecast"] },
  { id: "valuasi", title: "Valuasi & laporan", sub: "Method Gates, rantai metode, harness", stages: ["gate", "report", "done"] },
];

const PHASE_OF: Record<string, number> = Object.fromEntries(
  PHASES.flatMap((p, i) => p.stages.map((s) => [s, i])),
);

export const GATES: { n: number; name: string }[] = [
  { n: 0, name: "Model bisnis" },
  { n: 1, name: "Kelayakan data" },
  { n: 2, name: "Struktur kepemilikan" },
  { n: 3, name: "Siklus & tahap operasi" },
  { n: 4, name: "Tahap siklus hidup" },
  { n: 5, name: "Kewajaran hasil" },
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
  title: string;
  /** Why the call or task started (the opening event's detail). */
  reason?: string;
  /** The closing event's label, when the step closed with a different one. */
  result?: string;
  resultDetail?: string;
  status: Status;
  t0: number;
  t1?: number;
  data?: Record<string, string>;
  parent?: number;
  children: number[];
};

export type AgentState = { status: Status; steps: number; calls: number; last?: string; lastEvent: number };
export type GateState = { n: number; name: string; status: "idle" | "ok" | "warn" | "skip"; verdict?: string; detail?: string };
export type ChainState = { method: string; decision: string; value: string; reason?: string; order: number };
export type Hypothesis = { index: number; text: string; verdict?: string; reason?: string };

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
  release?: Record<string, string>;
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
 * Read a run's events. ``finished`` closes steps that never reported back
 * (``failed`` marks them as errors instead).
 */
export function derive(events: JobEvent[], opts: { finished?: boolean; failed?: boolean } = {}): DeckState {
  const steps: Step[] = [];
  const byId = new Map<number, Step>();
  const open: Step[] = [];
  const plan: DeckState["plan"] = { hypotheses: [] };
  const gates: GateState[] = GATES.map((g) => ({ ...g, status: "idle" }));
  const chain: ChainState[] = [];
  let release: Record<string, string> | undefined;
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
    lastEvent[agent] = i;
    phaseAt = Math.max(phaseAt, PHASE_OF[e.stage] ?? 0);

    if (kind === "hypothesis") {
      const index = Number(e.data?.index ?? plan.hypotheses.length + 1);
      plan.hypotheses.push({ index, text: e.detail ?? e.label });
    } else if (kind === "verdict") {
      const index = Number(e.data?.index);
      const h = plan.hypotheses.find((x) => x.index === index);
      if (h) Object.assign(h, { verdict: e.data?.verdict ?? e.label, reason: e.detail });
    } else if (kind === "gate") {
      const n = Number(e.data?.gate ?? (e.tool ?? "").slice(5));
      const g = gates.find((x) => x.n === n);
      if (g) {
        const verdict = e.data?.verdict ?? "";
        Object.assign(g, {
          status: verdict === "tidak berlaku" ? "skip" : e.status === "ok" ? "ok" : "warn",
          verdict, detail: e.detail,
        });
      }
    } else if (kind === "chain") {
      chain.push({ method: e.label, decision: e.data?.decision ?? "", value: e.data?.value ?? "-", reason: e.detail, order: chain.length });
    } else if (kind === "release") {
      release = e.data;
    }

    if (e.status === "run") {
      const parent = enclosing(agent, sub) ?? (agent === "gerbang" ? enclosing("laporan") : undefined);
      const step: Step = { id: i, agent, sub, kind, stage: e.stage, tool: e.tool, title: e.label, reason: e.detail,
        status: "run", t0: e.t, data: e.data, parent: parent?.id, children: [] };
      add(step);
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
      Object.assign(s, { status: e.status, t1: e.t, result: e.label !== s.title ? e.label : undefined,
        resultDetail: e.detail, data: { ...s.data, ...e.data } });
      if (s.stage === "plan" && e.detail && !plan.question) plan.question = e.detail;
      return;
    }
    if (e.stage === "plan" && e.detail && !plan.question && kind === "note") plan.question = e.detail;
    const parent = enclosing(agent, sub) ?? (agent === "gerbang" ? enclosing("laporan") : undefined);
    add({ id: i, agent, sub, kind, stage: e.stage, tool: e.tool, title: e.label, resultDetail: e.detail,
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

/** "12,4 dtk" or "2 mnt 05 dtk" for elapsed seconds. */
export function duration(seconds: number | undefined): string {
  if (seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 60) return `${seconds.toFixed(1).replace(".", ",")} dtk`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m} mnt ${String(s).padStart(2, "0")} dtk`;
}

/** Status words of the deck (from the Command Deck: ANTRI / JALAN / SELESAI). */
export const STATUS_WORD: Record<Status, string> = {
  idle: "Antri", run: "Jalan", ok: "Selesai", warn: "Catatan", error: "Gagal",
};
