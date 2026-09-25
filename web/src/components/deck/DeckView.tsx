// One Deck, three modes: the launcher, a live job and a replay share this
// layout so the viewer learns it once. A single console surface with ruled
// regions: the top (command line or run header), the agent rail, the phase
// bar, then the event stream beside the plan, gates, chain and result.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { MotionConfig } from "motion/react";
import type { AgentId, DeckState } from "../../lib/agents";
import { AgentRail } from "./AgentRail";
import { EventStream } from "./EventStream";
import { PhaseBar } from "./PhaseBar";
import { ChainTable, GateBoard, PlanPanel, ResultBlock, type ResultData } from "./SidePanels";

type Props = {
  state: DeckState;
  /** Command line (launcher) or run header. */
  top: ReactNode;
  /** A full-width notice under the top region (errors, partial results). */
  notice?: ReactNode;
  /** New steps are arriving. */
  live: boolean;
  /** Freeze every running animation (a paused replay). */
  paused?: boolean;
  /** Fit the console to the viewport on desktop (job and replay). */
  fit?: boolean;
  loading?: boolean;
  empty?: ReactNode;
  result?: ResultData;
  actions?: ReactNode;
};

export function DeckView({ state, top, notice, live, paused, fit = true, loading, empty, result, actions }: Props) {
  const [filter, setFilter] = useState<AgentId | null>(null);
  const aside = useRef<HTMLElement>(null);
  const touched = useRef(false);
  const [everLive, setEverLive] = useState(live);
  if (live && !everLive) setEverLive(true);

  // On desktop the right column scrolls on its own; while a run plays, bring
  // the part that is changing into view: the plan, then the gates, then the result.
  const focus = actions ? "result-title:done" : result ? "result-title"
    : state.gates.some((g) => g.status !== "idle") || state.agents.gerbang.status !== "idle" ? "gates-title" : "plan-title";
  useEffect(() => {
    const el = aside.current;
    if (focus === "plan-title") touched.current = false;
    if (!el || !everLive || touched.current || el.scrollHeight <= el.clientHeight + 1) return;
    const section = el.querySelector<HTMLElement>(`[aria-labelledby="${focus.split(":")[0]}"]`);
    if (!section) return;
    // The result is the last region: scroll to the end once its rows have laid out.
    const id = window.setTimeout(() => {
      const top = focus === "plan-title" ? 0 : focus.startsWith("result-title") ? el.scrollHeight : section.offsetTop;
      el.scrollTo({ top, behavior: "smooth" });
    }, 80);
    return () => window.clearTimeout(id);
  }, [focus, everLive]);
  return (
    <MotionConfig reducedMotion="user">
      <div className={`flex flex-col overflow-hidden rounded-lg border border-rule bg-surface ${
        fit ? "min-[1100px]:h-[calc(100dvh-52px-32px)] min-[1100px]:min-h-[720px]" : ""} ${paused ? "**:[animation-play-state:paused]" : ""}`}>
        <div className="flex-none">{top}</div>
        {notice && <div className="flex-none">{notice}</div>}
        <div className="flex-none border-b border-rule"><AgentRail state={state} filter={filter} onFilter={setFilter} /></div>
        <div className="flex-none border-b border-rule"><PhaseBar state={state} /></div>
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] min-[1100px]:grid-cols-12">
          <div className="flex min-h-0 min-w-0 flex-col max-md:border-b max-md:border-rule min-[1100px]:col-span-7 min-[1100px]:border-r min-[1100px]:border-rule">
            <EventStream state={state} filter={filter} onFilter={setFilter} live={live} fit={fit} loading={loading} empty={empty} />
          </div>
          <aside ref={aside} aria-label="Rencana, gerbang, dan hasil"
            onWheel={() => { touched.current = true; }} onTouchMove={() => { touched.current = true; }}
            className="relative min-w-0 min-[1100px]:col-span-5 min-[1100px]:overflow-y-auto min-[1100px]:overscroll-contain md:max-[1099px]:order-first md:max-[1099px]:grid md:max-[1099px]:grid-cols-2 md:max-[1099px]:border-b md:max-[1099px]:border-rule md:max-[1099px]:[&>*:nth-child(odd)]:border-r md:max-[1099px]:[&>*]:border-rule [&>*:last-child]:border-b-0 md:max-[1099px]:[&>*:nth-last-child(2):nth-child(odd)]:border-b-0">
            <PlanPanel state={state} loading={loading} />
            <GateBoard state={state} />
            <ChainTable state={state} />
            {(result || actions) && <ResultBlock result={result} actions={actions} />}
          </aside>
        </div>
      </div>
    </MotionConfig>
  );
}
