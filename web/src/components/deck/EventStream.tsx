// The event stream: every task, tool call and decision of the run, in order.
// A tool call goes out with its reason (a line sweeps under it while it is
// out) and comes back with its result, which springs open under it.
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CornerDownRight, TriangleAlert } from "lucide-react";
import { AGENT, AGENTS, duration, releaseFigures, type AgentId, type DeckState, type Step } from "../../lib/agents";
import type { EventData } from "../../lib/api";
import { decisionCode, gateCode, primaryMethodOf, str, type EventKind } from "../../lib/codes";
import { pick, useLang, type Bi, type Lang } from "../../lib/i18n";
import { EngineTag, Glyph, Hold, Sweep } from "./kit";
import {
  SPRING, clock, decisionWord, gateWord, useChangeCount, verdictGlyph, verdictOf, verdictTone, verdictWord, words,
} from "./read";

/** Whether rows mounting in this render are new arrivals (animate) or a jump (don't). */
const Enter = createContext(false);

type Props = {
  state: DeckState;
  filter: AgentId | null;
  onFilter: (agent: AgentId | null) => void;
  /** New steps are arriving (a running job or a playing replay). */
  live: boolean;
  /** The frame has a fixed height on desktop; the stream fills it. */
  fit: boolean;
  loading?: boolean;
  /** Shown before the first step. */
  empty?: ReactNode;
};

export function EventStream({ state, filter, onFilter, live, fit, loading, empty }: Props) {
  const { t } = useLang();
  const reduce = useReducedMotion();
  const total = state.steps.length;

  // Only a few new steps at a time animate in; a seek, a first load or a
  // filter change swaps rows in place.
  const [seen, setSeen] = useState({ total, filter, enter: false });
  if (seen.total !== total || seen.filter !== filter) {
    const grew = total - seen.total;
    setSeen({ total, filter, enter: seen.filter === filter && grew > 0 && grew <= 6 });
  }
  const enter = seen.enter && !reduce;

  const [follow, setFollow] = useState(true);
  // A run that was live keeps following through its last spring; a finished
  // run opened fresh starts at the top.
  const [everLive, setEverLive] = useState(live);
  if (live && !everLive) setEverLive(true);
  const scroller = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const setByUs = useRef(-1);

  // Follow the newest step while the run is live: stick to the bottom as the
  // list grows (results spring open, so this runs per frame of the growth).
  useLayoutEffect(() => {
    const el = scroller.current;
    const inner = content.current;
    if (!el || !inner || !follow || !everLive) return;
    const stick = () => {
      el.scrollTop = el.scrollHeight;
      setByUs.current = el.scrollTop;
    };
    stick();
    const ro = new ResizeObserver(stick);
    ro.observe(inner);
    return () => ro.disconnect();
  }, [follow, everLive, filter]);

  const onScroll = () => {
    const el = scroller.current;
    if (!el || Math.abs(el.scrollTop - setByUs.current) < 2) return;
    const gap = el.scrollHeight - el.clientHeight - el.scrollTop;
    if (gap > 48 && follow) setFollow(false);
    else if (gap < 4 && !follow && live) setFollow(true);
  };

  const roots = filter
    ? state.steps.filter((s) => s.agent === filter && !(s.parent !== undefined && state.byId.get(s.parent)?.agent === filter))
    : state.roots;
  const agentsWithSteps = AGENTS.filter((a) => state.agents[a.id].steps > 0 || a.id === filter);
  const latest = state.active ?? state.steps[state.steps.length - 1];
  const announce = useThrottled(latest ? latest.result ?? latest.title : "", 2500);

  const height = fit ? "min-[1100px]:min-h-0 min-[1100px]:flex-1 max-[1099px]:h-[min(68dvh,620px)]" : "";
  return (
    <section aria-labelledby="stream-title" className="flex min-h-0 min-w-0 flex-col">
      <div className="flex items-center gap-3 border-b border-rule px-4 py-2.5 max-sm:px-3">
        <h2 id="stream-title" className="text-[14px] font-bold tracking-normal whitespace-nowrap">{t({ id: "Aliran kerja agent", en: "Agent work stream" })}</h2>
        <span className="data whitespace-nowrap text-ink-soft max-sm:hidden">
          {t({ id: `${total} langkah`, en: `${total} ${total === 1 ? "step" : "steps"}` })}
        </span>
        <FollowSwitch on={follow} onChange={(on) => setFollow(on)} disabled={!live} />
      </div>
      {agentsWithSteps.length > 0 && (
        <div role="group" aria-label={t({ id: "Saring menurut agent", en: "Filter by agent" })} className="flex gap-1 overflow-x-auto border-b border-rule-soft px-3 py-2 [scrollbar-width:none]">
          <FilterChip pressed={filter === null} onClick={() => onFilter(null)}>{t({ id: "Semua agent", en: "All agents" })}</FilterChip>
          {agentsWithSteps.map((a) => (
            <FilterChip key={a.id} pressed={filter === a.id} onClick={() => onFilter(filter === a.id ? null : a.id)}>
              {t(a.short)}<span className="data text-ink-soft">{state.agents[a.id].steps}</span>
            </FilterChip>
          ))}
        </div>
      )}
      <div ref={scroller} onScroll={onScroll} tabIndex={0} aria-label={t({ id: "Langkah riset", en: "Research steps" })}
        className={`relative overflow-y-auto overscroll-contain focus-visible:outline-offset-[-2px] ${height} ${total === 0 ? "min-h-[220px]" : ""}`}>
        <div ref={content}>
          {loading ? <Skeleton /> : total === 0 ? (
            <div className="px-5 py-8 text-[14px] text-ink-soft max-sm:px-4">{empty}</div>
          ) : (
            <Enter.Provider value={enter}>
              <ol className="m-0 list-none p-0">
                {roots.map((step) => <StepItem key={step.id} step={step} state={state} filter={filter} depth={0} />)}
              </ol>
            </Enter.Provider>
          )}
        </div>
      </div>
      <p aria-live="polite" className="sr-only">{announce}</p>
    </section>
  );
}

function useThrottled(value: string, ms: number) {
  const [shown, setShown] = useState(value);
  const last = useRef(0);
  useEffect(() => {
    const wait = Math.max(0, last.current + ms - Date.now());
    const id = window.setTimeout(() => { last.current = Date.now(); setShown(value); }, wait);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return shown;
}

function FollowSwitch({ on, onChange, disabled }: { on: boolean; onChange: (on: boolean) => void; disabled: boolean }) {
  const { t } = useLang();
  return (
    <button type="button" role="switch" aria-checked={on} disabled={disabled} onClick={() => onChange(!on)}
      title={t({ id: "Gulir ke langkah terbaru selama run berjalan", en: "Scroll to the newest step while the run is going" })}
      className="ml-auto flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-[13px] font-medium whitespace-nowrap text-ink-soft transition-colors hover:text-ink-strong disabled:cursor-default disabled:opacity-60 disabled:hover:text-ink-soft">
      {t({ id: "Ikuti otomatis", en: "Auto-follow" })}
      <span aria-hidden className={`relative h-[18px] w-8 rounded-full border transition-colors duration-200 ${on ? "border-brand bg-brand" : "border-rule-strong bg-raised"}`}>
        <motion.span className="absolute top-[2px] left-[2px] size-3 rounded-full bg-white shadow-[0_1px_2px_rgb(0_0_0/.25)]"
          animate={{ x: on ? 14 : 0 }} transition={SPRING} />
      </span>
    </button>
  );
}

function FilterChip({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-pressed={pressed} onClick={onClick}
      className={`relative flex h-8 flex-none cursor-pointer items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium transition-colors active:scale-[.97] ${
        pressed ? "text-brand-ink" : "text-ink-soft hover:bg-raised hover:text-ink-strong"}`}>
      {pressed && (
        <motion.span layoutId="stream-filter" aria-hidden transition={SPRING}
          className="absolute inset-0 rounded-md border border-brand-ink/40 bg-brand-50" />
      )}
      <span className="relative flex items-center gap-1.5">{children}</span>
    </button>
  );
}

function Skeleton() {
  return (
    <div aria-hidden className="grid gap-0">
      {[72, 56, 88, 64, 80].map((w, i) => (
        <div key={i} className="grid grid-cols-[16px_1fr] gap-3 border-b border-rule-soft px-4 py-3.5">
          <span className="mt-1 size-3 animate-pulse rounded-full bg-raised" />
          <span className="grid gap-2">
            <span className="h-3 w-32 animate-pulse rounded bg-raised" />
            <span className="h-3 animate-pulse rounded bg-raised" style={{ width: `${w}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}

/** One row of the stream, animated in only when it is a new arrival. */
function StepItem({ step, state, filter, depth }: { step: Step; state: DeckState; filter: AgentId | null; depth: number }) {
  const enter = useContext(Enter);
  const body = step.kind === "task" ? <TaskBlock step={step} state={state} filter={filter} depth={depth} />
    : step.kind === "call" ? <CallCard step={step} showAgent={depth === 0 && !filter} />
    : <CompactRow step={step} showAgent={depth === 0 && !filter} />;
  return (
    <motion.li initial={enter ? { height: 0, opacity: 0 } : false} animate={{ height: "auto", opacity: 1 }}
      transition={{ height: SPRING, opacity: { duration: 0.28, ease: [0.16, 1, 0.3, 1] } }}
      className={`overflow-hidden ${depth === 0 ? "border-b border-rule-soft" : ""}`}>
      {body}
    </motion.li>
  );
}

/** Endpoint paths and tool names read as data. */
function Data({ text }: { text: string }) {
  const parts = text.split(/(?<![\w/])(\/(?:[\w.-]+\/)+)/g);
  return <>{parts.map((p, i) => (i % 2 ? <code key={i} className="font-mono text-[.92em] text-ink-strong">{p}</code> : p))}</>;
}

/**
 * Tool outcomes the pipeline labels "<tool>: …". Indonesian readers keep the
 * pipeline's own words after the prefix; these are the words for the others.
 */
const TOOL_OUTCOME: Record<"tool_error" | "tool_empty", Bi> = {
  tool_error: { id: "data tidak tersedia", en: "Data not available" },
  tool_empty: { id: "data tidak tersedia", en: "No data available" },
};

/** The closing label of a step, cut to what it adds and in the reader's words where the Deck knows it. */
function resultLabel(step: Step, lang: Lang): string | undefined {
  const label = step.result;
  const kind = step.resultEvent;
  if (!label) return undefined;
  if (step.tool && kind === "tool_done") return undefined;
  if (step.tool && (kind === "tool_error" || kind === "tool_empty")) {
    const prefix = `${step.tool}: `;
    return lang === "id" && label.startsWith(prefix) ? label.slice(prefix.length) : pick(TOOL_OUTCOME[kind], lang);
  }
  return valuationLabel(label, kind, step.data, lang);
}

/** The gate agent's closing labels, in the reader's words; any other label passes through. */
function valuationLabel(label: string, kind: EventKind | undefined, data: EventData | undefined, lang: Lang): string {
  if (kind === "primary_method") {
    const method = primaryMethodOf({ label, data }) ?? "";
    return pick({ id: label, en: `Primary method ${method}`.trim() }, lang);
  }
  if (kind === "chain_done") return pick({ id: label, en: "Method Chain done" }, lang);
  if (kind === "release" && data?.status) {
    return pick({ id: label, en: `Release status: ${words(str(data.status), "en")}` }, lang);
  }
  return label;
}

function resultParts(step: Step, lang: Lang): { label?: string; detail?: string } {
  let label = resultLabel(step, lang);
  const path = step.title.match(/(\/\S+)/)?.[1];
  if (label && path && label.startsWith(path)) label = label.slice(path.length).trim();
  if (label) label = label.charAt(0).toUpperCase() + label.slice(1);
  return { label, detail: words(step.resultDetail, lang) };
}

function Stamp({ at }: { at: number }) {
  const { t } = useLang();
  return <span className="data pt-[3px] text-ink-faint" title={t({ id: "Waktu sejak run dimulai", en: "Time since the run started" })}>{clock(at)}</span>;
}

/** The result of a call or task, springing open when it comes back. */
function ResultLine({ step, clampLines = false }: { step: Step; clampLines?: boolean }) {
  // The result is what changed, so it holds the light (not the whole card).
  const { t, lang } = useLang();
  const changed = useChangeCount(step.status);
  const { label, detail } = resultParts(step, lang);
  const back = step.status !== "run" && step.t1 !== undefined;
  const warn = step.status === "warn" || step.status === "error";
  const show = back && (label || detail || step.t1! > step.t0);
  return (
    <AnimatePresence initial={false}>
      {show && (
        <motion.div key="result" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
          transition={{ height: SPRING, opacity: { duration: 0.3 } }} className="overflow-hidden">
          <div className={`relative isolate mt-1.5 grid grid-cols-[14px_minmax(0,1fr)_auto] items-start gap-2 rounded-md px-2.5 py-1.5 text-[13.5px] leading-snug ${
            warn ? (step.status === "error" ? "bg-err-bg text-err-ink" : "bg-warn-bg text-warn-ink") : "bg-raised text-ink-soft"}`}>
            {!warn && <Hold n={changed} tone={step.status} />}
            {warn ? <TriangleAlert aria-hidden className="mt-[2px] size-3.5" strokeWidth={2.2} />
              : <CornerDownRight aria-hidden className="mt-[2px] size-3.5 text-ink-faint" strokeWidth={2.2} />}
            <span className={`min-w-0 break-words ${clampLines ? "line-clamp-2" : ""}`} title={clampLines ? detail : undefined}>
              {label && <span className={`font-medium ${warn ? "" : "text-ink"}`}>{label}</span>}
              {label && detail ? ": " : ""}
              {detail && <Data text={detail} />}
              {!label && !detail && <span>{t({ id: "Selesai", en: "Done" })}</span>}
            </span>
            <span className="data pt-[1px] whitespace-nowrap" title={t({ id: "Durasi", en: "Duration" })}>{duration(step.t1! - step.t0, lang)}</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** The signature card: agent mark, mono tool name, the reason, then the result. */
function CallCard({ step, showAgent }: { step: Step; showAgent: boolean }) {
  const { t } = useLang();
  const tool = step.tool ?? "";
  // The opening "running <tool>" label repeats the tool name; any other title says why.
  const reason = step.reason ?? (step.event !== "tool_start" ? step.title : undefined);
  return (
    <div className="relative px-4 py-2.5 max-sm:px-3">
      <div className="grid grid-cols-[16px_minmax(0,1fr)_auto] items-start gap-x-3">
        <Glyph status={step.status} className="mt-[3px]" />
        <div className="min-w-0">
          <p className="flex flex-wrap items-baseline gap-x-2">
            <code className="font-mono text-[13.5px] font-semibold text-ink-strong">{tool}</code>
            {showAgent && <span className="text-[12.5px] text-ink-soft">{t(AGENT[step.agent].short)}</span>}
            {step.status === "run" && <span className="text-[12.5px] font-medium text-brand-ink">{t({ id: "keluar", en: "out" })}</span>}
          </p>
          {reason && <p className="mt-0.5 text-[14px] leading-snug text-ink"><Data text={reason} /></p>}
          <ResultLine step={step} />
        </div>
        <Stamp at={step.t0} />
      </div>
      {step.status === "run" && <Sweep />}
    </div>
  );
}

/** An agent's task: a section header with its own calls nested under it. */
function TaskBlock({ step, state, filter, depth }: { step: Step; state: DeckState; filter: AgentId | null; depth: number }) {
  const { t } = useLang();
  const meta = AGENT[step.agent];
  const kids = step.children.map((id) => state.byId.get(id)!).filter((c) => c && (!filter || c.agent === filter));
  const busyChild = kids.some((k) => k.status === "run");
  return (
    <div className={depth > 0 ? "border-t border-rule-soft" : ""}>
      <div className="relative px-4 pt-3 pb-2.5 max-sm:px-3">
        <div className="grid grid-cols-[16px_minmax(0,1fr)_auto] items-start gap-x-3">
          <Glyph status={step.status} className="mt-[3px]" />
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-[12.5px] leading-5">
              <span className="font-bold text-ink-soft">{t(meta.name)}</span>
              <EngineTag engine={meta.engine} />
            </p>
            <p className="text-[14.5px] leading-snug font-bold text-ink-strong">{step.title}</p>
            {step.reason && <p className="mt-0.5 text-[13px] leading-snug text-ink-soft"><Data text={step.reason} /></p>}
            {kids.length === 0 && <ResultLine step={step} clampLines />}
          </div>
          <Stamp at={step.t0} />
        </div>
        {step.status === "run" && !busyChild && <Sweep />}
      </div>
      {kids.length > 0 && (
        <>
          <ol className="m-0 ml-[23px] list-none border-l border-rule p-0 max-sm:ml-[19px]">
            {kids.map((k) => <StepItem key={k.id} step={k} state={state} filter={filter} depth={depth + 1} />)}
          </ol>
          <div className="px-4 pb-2.5 pl-[45px] max-sm:px-3 max-sm:pl-[41px]"><ResultLine step={step} clampLines /></div>
        </>
      )}
    </div>
  );
}

/** Hypotheses, verdicts, gates, chain steps, the release and notes: one line each. */
function CompactRow({ step, showAgent }: { step: Step; showAgent: boolean }) {
  const { t, lang } = useLang();
  const d = step.data ?? {};
  let lead: ReactNode = null;
  let text: ReactNode = valuationLabel(step.title, step.event, step.data, lang);
  let side: ReactNode = null;
  let sub: string | undefined = words(step.resultDetail, lang);
  let glyph = step.status;

  if (step.kind === "hypothesis") {
    lead = `H${d.index ?? ""}`;
    text = (step.resultDetail ?? step.title).replace(/^H\d+:\s*/, "");
    sub = undefined;
  } else if (step.kind === "verdict") {
    const v = verdictOf(d);
    lead = `H${d.index ?? ""}`;
    text = <span className={`pill ${verdictTone(v)} px-2 py-0 text-[12.5px]`}>{verdictWord(v, lang) ?? step.title}</span>;
    // An unanswered hypothesis is not a finished test: it carries the warning mark.
    if (step.status !== "run" && verdictGlyph(v) === "warn") glyph = "warn";
  } else if (step.kind === "gate") {
    const g = { verdict: str(d.verdict), code: gateCode(d.verdict_code, d.verdict) };
    lead = `G${d.gate ?? ""}`;
    text = <>{step.title} <span className={`text-[12.5px] font-medium ${step.status === "ok" ? "text-done" : g.code === "not_applicable" ? "text-ink-soft" : "text-warn-ink"}`}>{gateWord(g, lang)}</span></>;
  } else if (step.kind === "chain") {
    const c = { decision: str(d.decision) ?? "", code: decisionCode(d.decision_code, d.decision) };
    text = <><code className="font-mono text-[13px] font-semibold text-ink-strong">{step.title}</code> <span className={c.code === "selected" ? "font-bold text-brand-ink" : "text-ink-soft"}>{decisionWord(c, lang)}</span></>;
    side = <span className="data text-ink-strong">{d.value}</span>;
  } else if (step.kind === "release") {
    side = d.rating ? <span className="data text-ink-strong">{d.rating} {releaseFigures(d, lang).tp}</span> : null;
  }

  return (
    <div className="relative px-4 py-2 max-sm:px-3">
      <div className="grid grid-cols-[16px_minmax(0,1fr)_auto] items-start gap-x-3 text-[13.5px] leading-snug">
        <Glyph status={glyph} className="mt-[2px]" />
        <div className="min-w-0">
          <p className={step.kind === "hypothesis" ? "line-clamp-2" : ""} title={typeof text === "string" ? text : undefined}>
            {lead && <span className="data mr-2 text-ink-soft">{lead}</span>}
            {showAgent && step.kind === "note" && <span className="mr-2 text-[12.5px] text-ink-soft">{t(AGENT[step.agent].short)}</span>}
            <span className={step.kind === "note" || step.kind === "release" ? "font-medium text-ink" : "text-ink"}>{text}</span>
          </p>
          {sub && <p className="mt-0.5 line-clamp-2 text-[13px] text-ink-soft" title={sub}><Data text={sub} /></p>}
        </div>
        {side ?? <Stamp at={step.t0} />}
      </div>
    </div>
  );
}
