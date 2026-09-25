// How a run moves: the five phases in order, with what a language model does
// in each and what deterministic host code does. On wide screens it reads as
// two lanes across the phases; on narrow screens as one list per phase.
import { AGENT, PHASES, SUBAGENTS, type AgentId } from "../../lib/agents";
import { LiveMark } from "../Mark";

type Lane = "llm" | "host";
type Entry = { agent?: AgentId; title?: string; body?: string; tags?: string[] };
type Cell = { phase: number; span?: number; lane: Lane; entries: Entry[] };

/** Analyst tools the planner may call (agents/analyst/tools.py). */
const TOOLS = ["find_peers", "rank_peers", "quarterly_financials", "price_history", "foreign_flow", "valuation_history", "news", "web_news"];

// In pipeline order; the order is also the reading order on phones.
const CELLS: Cell[] = [
  { phase: 0, lane: "host", entries: [{ agent: "memori" }] },
  { phase: 0, span: 2, lane: "llm", entries: [{ agent: "analis", tags: TOOLS }] },
  { phase: 1, lane: "host", entries: [{
    title: "Eksekusi tool dan sinyal",
    body: "Host menjalankan setiap panggilan tool pada data Sectors lokal, mencatatnya di jejak, lalu menghitung sinyal yang wajib dikutip agent.",
  }] },
  { phase: 2, lane: "llm", entries: [{ agent: "riset", tags: ["cache_get"] }] },
  { phase: 2, lane: "host", entries: [
    { agent: "berita" },
    { title: "Validator kutipan", body: "Brief diperiksa terhadap baris yang benar-benar dibaca; bukti yang kurang tetap ditandai parsial." },
  ] },
  { phase: 3, lane: "llm", entries: [{ agent: "forecast", tags: SUBAGENTS.map((s) => s.name) }] },
  { phase: 3, lane: "host", entries: [{
    title: "Validator asumsi",
    body: "Asumsi tanpa sumber, periode, dan besaran yang lolos skema ditolak dan tidak masuk model; alasannya tercatat.",
  }] },
  { phase: 4, lane: "host", entries: [{ agent: "gerbang" }, { agent: "laporan" }] },
  // Shown on wide screens only: the valuation phase has no model in it.
  { phase: 4, lane: "llm", entries: [] },
];

const LANES: Record<Lane, { title: string; body: string }> = {
  llm: { title: "Model bahasa", body: "Merencanakan, memilih panggilan tool, menulis asumsi" },
  host: { title: "Kode host", body: "Menghitung sinyal, gerbang, valuasi, dan harness rilis" },
};

// Explicit grid placement for the lane layout (Tailwind needs literal classes).
const COL = ["lg:col-start-2", "lg:col-start-3", "lg:col-start-4", "lg:col-start-5", "lg:col-start-6"];
const SPAN = ["", "lg:col-span-1", "lg:col-span-2"];
const ROW: Record<Lane, string> = { llm: "lg:row-start-2", host: "lg:row-start-3" };

export function Pipeline() {
  return (
    <div className="panel grid overflow-hidden lg:grid-cols-[164px_repeat(5,minmax(0,1fr))]">
      {PHASES.map((phase, i) => (
        <PhaseBlock key={phase.id} index={i} title={phase.title} sub={phase.sub}
          cells={CELLS.filter((c) => c.phase === i)} />
      ))}
      {/* Lane labels come last in the source so phones start with phase 1; wide screens place them left. */}
      {(["llm", "host"] as Lane[]).map((lane) => (
        <div key={lane} aria-hidden
          className={`hidden border-t border-r border-rule px-4 py-4 lg:block lg:col-start-1 ${ROW[lane]} ${lane === "llm" ? "bg-brand-50/60" : "bg-raised"}`}>
          <EngineTag lane={lane} />
          <p className="m-0 mt-2.5 text-[14.5px] font-bold text-ink-strong">{LANES[lane].title}</p>
          <p className="m-0 mt-1.5 text-[12.5px] leading-snug text-ink-soft">{LANES[lane].body}</p>
        </div>
      ))}
      <div aria-hidden className="hidden border-r border-rule bg-raised lg:block lg:col-start-1 lg:row-start-1" />
    </div>
  );
}

function PhaseBlock({ index, title, sub, cells }: { index: number; title: string; sub: string; cells: Cell[] }) {
  // `lg:contents` lets the phase header and its lane cells join the parent grid on wide screens,
  // while phones keep them together as one group in reading order.
  return (
    <section aria-labelledby={`fase-${index}`} className="border-t border-rule first:border-t-0 lg:contents">
      <header className={`relative px-4 pt-4 pb-3.5 lg:row-start-1 lg:border-rule ${COL[index]} ${index < 4 ? "lg:border-r" : ""}`}>
        {/* The track that joins the five phase numbers. */}
        <span aria-hidden className="absolute top-[27px] right-0 left-0 hidden h-px bg-rule lg:block" />
        <div className="relative flex items-center gap-2.5">
          <span className="grid size-6 flex-none place-items-center rounded-[5px] border border-rule-strong bg-surface font-mono text-[12px] font-semibold text-ink-strong">
            {index + 1}
          </span>
          <h3 id={`fase-${index}`} className="bg-surface pr-2 text-[15.5px]">{title}</h3>
        </div>
        <p className="relative m-0 mt-1.5 text-[13px] leading-snug text-ink-soft">{sub}</p>
      </header>
      {cells.map((cell, i) => (
        <LaneCell key={`${cell.lane}-${cell.phase}`} cell={cell} divided={i > 0} last={cell.phase + (cell.span ?? 1) - 1 >= 4} />
      ))}
    </section>
  );
}

function LaneCell({ cell, divided, last }: { cell: Cell; divided: boolean; last: boolean }) {
  const place = `${COL[cell.phase]} ${SPAN[cell.span ?? 1]} ${ROW[cell.lane]}`;
  const tint = cell.lane === "llm" ? "lg:bg-brand-50/60" : "";
  if (cell.entries.length === 0) {
    return (
      <div className={`hidden border-t border-rule px-4 py-4 lg:block ${place} ${tint} ${last ? "" : "lg:border-r"}`}>
        <p className="m-0 rounded-md border border-dashed border-rule-strong px-3 py-3 text-[13px] leading-snug text-ink-soft">
          Tidak ada agent model di fase ini. Metode, nilai, dan status rilis dihitung kode.
        </p>
      </div>
    );
  }
  return (
    <div className={`px-4 pb-4 lg:border-t lg:border-rule lg:pt-4 ${place} ${tint} ${last ? "" : "lg:border-r"} ${
      divided ? "max-lg:mx-4 max-lg:border-t max-lg:border-dashed max-lg:border-rule max-lg:px-0 max-lg:pt-3.5" : ""}`}>
      {cell.entries.map((entry, i) => (
        <EntryBlock key={entry.agent ?? entry.title} entry={entry} lane={cell.lane} divided={i > 0} />
      ))}
    </div>
  );
}

function EntryBlock({ entry, lane, divided }: { entry: Entry; lane: Lane; divided: boolean }) {
  const meta = entry.agent ? AGENT[entry.agent] : undefined;
  const title = meta?.name ?? entry.title;
  const body = meta?.role ?? entry.body;
  return (
    <div className={divided ? "mt-3.5 border-t border-dashed border-rule pt-3.5" : ""}>
      <div className="flex items-center gap-2">
        {meta && <LiveMark status="ok" className="h-2.5 w-3 flex-none" />}
        <h4 className="text-[14.5px] leading-snug">
          {title}<span className="sr-only">, {lane === "llm" ? "model bahasa" : "kode host"}</span>
        </h4>
        <EngineTag lane={lane} className="ml-auto lg:hidden" />
      </div>
      <p className="m-0 mt-1 text-[13.5px] leading-snug text-ink-soft">{body}</p>
      {entry.tags && (
        <ul aria-label={meta?.id === "forecast" ? "Subagent" : "Tool"} className="m-0 mt-2.5 flex list-none flex-wrap gap-1 p-0">
          {entry.tags.map((tag) => (
            <li key={tag} className={`rounded-[4px] border border-rule-soft bg-surface px-1.5 text-[12px] leading-[20px] text-ink ${
              meta?.id === "forecast" ? "" : "font-mono text-[11.5px]"}`}>{tag}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EngineTag({ lane, className = "" }: { lane: Lane; className?: string }) {
  return (
    <span aria-hidden className={`inline-flex h-5 flex-none items-center rounded-[4px] px-1.5 font-mono text-[10.5px] font-semibold tracking-[.04em] ${
      lane === "llm" ? "bg-brand-100 text-brand-ink" : "border border-rule bg-surface text-ink-soft"} ${className}`}>
      {lane === "llm" ? "LLM" : "KODE"}
    </span>
  );
}
