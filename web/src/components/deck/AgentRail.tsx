// The agent rail: seven agents in pipeline order on one line. A node lights
// when its agent works and holds its light when its status changes; clicking a
// node filters the event stream to that agent.
import { useEffect, useRef } from "react";
import { motion } from "motion/react";
import { AGENTS, STATUS_WORD, SUBAGENTS, type AgentId, type DeckState, type Status } from "../../lib/agents";
import { EngineTag, Glyph, Hold } from "./kit";
import { SPRING, STATUS_INK, useChangeCount } from "./read";

/** Short names for the forecast subagent chips; the full name is in the title. */
const SUB_SHORT: Record<string, string> = { news: "Berita", interim: "Interim", earnings: "Laba FY", stage: "Tahap", outyears: "Lanjut" };

const LINE: Record<Status, string> = {
  idle: "bg-rule", run: "bg-brand-ink", ok: "bg-done/60", warn: "bg-warn-rule", error: "bg-err-ink/60",
};

type Props = {
  state: DeckState;
  filter: AgentId | null;
  onFilter: (agent: AgentId | null) => void;
};

export function AgentRail({ state, filter, onFilter }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const active = state.active?.agent;

  // On narrow screens the rail scrolls; keep the working agent in view.
  useEffect(() => {
    const el = scroller.current;
    if (!el || !active || el.scrollWidth <= el.clientWidth + 1) return;
    const node = el.querySelector<HTMLElement>(`[data-agent="${active}"]`);
    if (!node) return;
    el.scrollTo({ left: node.offsetLeft - (el.clientWidth - node.offsetWidth) / 2, behavior: "smooth" });
  }, [active]);

  return (
    <div ref={scroller} className="overflow-x-auto overscroll-x-contain [scrollbar-width:none] max-[1099px]:snap-x max-[1099px]:snap-mandatory max-[1099px]:scroll-px-3">
      <div role="group" aria-label="Agent, klik untuk menyaring aliran kerja"
        className="grid min-w-max grid-cols-[repeat(7,minmax(156px,1fr))] px-2 py-2 min-[1100px]:min-w-0 min-[1100px]:grid-cols-7">
        {AGENTS.map((agent, i) => {
          const next = AGENTS[i + 1];
          return (
            <RailNode key={agent.id} id={agent.id} state={state} pressed={filter === agent.id}
              leftLine={i > 0 ? state.agents[agent.id].status : null}
              rightLine={next ? state.agents[next.id].status : null}
              onPress={() => onFilter(filter === agent.id ? null : agent.id)} />
          );
        })}
      </div>
    </div>
  );
}

function RailNode({ id, state, pressed, leftLine, rightLine, onPress }: {
  id: AgentId; state: DeckState; pressed: boolean;
  leftLine: Status | null; rightLine: Status | null; onPress: () => void;
}) {
  const meta = AGENTS.find((a) => a.id === id)!;
  const agent = state.agents[id];
  const changed = useChangeCount(agent.status);
  const count = agent.calls > 0 ? `${agent.calls} call` : agent.steps > 0 ? `${agent.steps} langkah` : "";
  return (
    <div data-agent={id} className="snap-start">
      <button type="button" aria-pressed={pressed} onClick={onPress} title={`${meta.name}: ${meta.role}`}
        className="group relative isolate mx-1 flex w-[calc(100%-8px)] cursor-pointer flex-col gap-1.5 rounded-md px-2 pt-2 pb-2.5 text-left transition-colors hover:bg-raised">
        <Hold n={changed} tone={agent.status} />
        {pressed && (
          <motion.span layoutId="rail-pressed" aria-hidden transition={SPRING}
            className="absolute inset-0 -z-10 rounded-md border border-brand-ink/50 bg-brand-50" />
        )}
        {/* The rail line: each node draws its half of the segment to its neighbours. */}
        {leftLine && <span aria-hidden className={`absolute top-[19px] left-[-4px] h-px w-[12px] transition-colors duration-500 ${LINE[leftLine]}`} />}
        {rightLine && <span aria-hidden className={`absolute top-[19px] right-[-4px] left-[30px] h-px transition-colors duration-500 ${LINE[rightLine]}`} />}
        <span className="flex items-center gap-2">
          <span className="grid size-[22px] flex-none place-items-center">
            <Glyph status={agent.status} />
          </span>
        </span>
        <span className="flex items-center gap-2">
          <span className={`min-w-0 flex-1 truncate text-[14px] leading-tight font-bold ${agent.status === "idle" ? "text-ink-soft" : "text-ink-strong"}`}>{meta.short}</span>
          <EngineTag engine={meta.engine} />
        </span>
        <span className="flex items-baseline gap-1 overflow-hidden whitespace-nowrap">
          <span className={`data text-[10.5px] uppercase ${STATUS_INK[agent.status]}`}>{STATUS_WORD[agent.status]}</span>
          {count && <span className="data truncate text-[10.5px] tracking-normal text-ink-soft" title={count}>{count}</span>}
        </span>
        {/* Forecast subagents: a sub-row inside the node's own width, off the rail line. */}
        {id === "forecast" && <SubChips state={state} />}
      </button>
    </div>
  );
}

function SubChips({ state }: { state: DeckState }) {
  return (
    <span className="-mt-0.5 flex flex-wrap gap-[2px]">
      {SUBAGENTS.map((s) => {
        const status = state.subagents[s.id] ?? "idle";
        return <SubChip key={s.id} name={s.name} short={SUB_SHORT[s.id] ?? s.name} status={status} />;
      })}
    </span>
  );
}

const CHIP: Record<Status, string> = {
  idle: "border-rule bg-surface text-ink-faint",
  run: "border-brand-ink/40 bg-brand-50 text-brand-ink",
  ok: "border-done/35 bg-ok-bg text-ok-ink",
  warn: "border-warn-rule/50 bg-warn-bg text-warn-ink",
  error: "border-err-ink/40 bg-err-bg text-err-ink",
};

function SubChip({ name, short, status }: { name: string; short: string; status: Status }) {
  const changed = useChangeCount(status);
  return (
    <span title={`Subagent ${name}: ${STATUS_WORD[status]}`}
      className={`relative isolate inline-flex h-4 items-center gap-1 rounded-[3px] border px-[3px] text-[10.5px] leading-none font-medium whitespace-nowrap transition-colors duration-300 ${CHIP[status]}`}>
      <Hold n={changed} tone={status} />
      {status === "run" && <i aria-hidden className="size-1.5 animate-pulse rounded-full bg-live" />}
      {short}
      <span className="sr-only">: {STATUS_WORD[status]}</span>
    </span>
  );
}
