// The landing's one orchestrated moment: a miniature of the Deck replaying a
// stored run from its audit trace, on loop. It pauses when off-screen, when
// the reader asks, and under reduced motion (then it shows the finished run).
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CornerDownRight, Pause, Play } from "lucide-react";
import { api, type ReportItem, type RunReplay } from "../../lib/api";
import { AGENT, AGENTS, STATUS_WORD, derive, duration, type DeckState, type Status, type Step, type StepKind } from "../../lib/agents";
import { useReplay } from "../../lib/replay";
import { LiveMark } from "../Mark";
import { RatingBadge } from "../Reports";
import { GATE_TONE, GateMeter } from "./GateMeter";

export type StoredRun = { status: "loading" } | { status: "error" } | { status: "ready"; run: RunReplay };

/** The stored run of ``ticker``; ``settled`` says the report list has answered (no ticker then means nothing to play). */
export function useStoredRun(ticker: string | undefined, settled: boolean): StoredRun {
  const [state, setState] = useState<StoredRun>({ status: "loading" });
  useEffect(() => {
    if (!ticker) {
      setState({ status: settled ? "error" : "loading" });
      return;
    }
    let live = true;
    setState({ status: "loading" });
    api.reportRun(ticker).then(
      (run) => live && setState(run.events?.length ? { status: "ready", run } : { status: "error" }),
      () => live && setState({ status: "error" }),
    );
    return () => { live = false; };
  }, [ticker, settled]);
  return state;
}

/** True while the element is at least a quarter on screen and the tab is visible. */
function useOnScreen(ref: RefObject<HTMLElement | null>) {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let visible = typeof IntersectionObserver === "undefined";
    const update = () => setOn(visible && document.visibilityState === "visible");
    const io = visible ? null : new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; update(); }, { threshold: 0.25 });
    io?.observe(el);
    update();
    document.addEventListener("visibilitychange", update);
    return () => { io?.disconnect(); document.removeEventListener("visibilitychange", update); };
  }, [ref]);
  return on;
}

/** Kinds that read as stream rows; gates and the method chain have their own board. */
const STREAM: ReadonlySet<StepKind> = new Set<StepKind>(["task", "call", "note", "release"]);
const ROWS = 7;
const WORD_TONE: Record<Status, string> = {
  idle: "text-ink-faint", run: "text-brand-ink", ok: "text-done", warn: "text-warn-ink", error: "text-err-ink",
};
const HYPOTHESIS_NUMBER = /^H\d+:\s*/;
const STATUS_CODE = /^[a-z][a-z_]+$/;
const SPRING = { type: "spring", stiffness: 380, damping: 38, mass: 0.8 } as const;

export function Reel({ load, ticker, item }: { load: StoredRun; ticker?: string; item?: ReportItem }) {
  if (load.status === "ready") return <Player run={load.run} item={item ?? load.run.report ?? undefined} />;
  return <Still state={load.status} ticker={ticker} />;
}

function Player({ run, item }: { run: RunReplay; item?: ReportItem }) {
  const reduce = !!useReducedMotion();
  const frame = useRef<HTMLDivElement>(null);
  const onScreen = useOnScreen(frame);
  const [held, setHeld] = useState(false);
  const total = run.events.length;
  const replay = useReplay(run.events, { speed: 6, loop: true, autoplay: false, startAt: reduce ? total : 0 });
  const { play, pause, seek } = replay;

  useEffect(() => {
    if (reduce) {
      pause();
      seek(total);
    } else if (onScreen && !held) play();
    else pause();
  }, [reduce, onScreen, held, total, play, pause, seek]);

  const deck = useMemo(() => derive(replay.shown, { finished: replay.finished }), [replay.shown, replay.finished]);
  return (
    <Frame frameRef={frame} deck={deck} ticker={run.ticker} name={run.name} item={item} reduce={reduce}
      recorded={run.source === "recorded"} finished={replay.finished} progress={replay.progress}
      playing={!reduce && replay.playing && !replay.finished} held={held}
      onToggle={reduce ? undefined : () => setHeld((h) => !h)} />
  );
}

function Still({ state, ticker }: { state: "loading" | "error"; ticker?: string }) {
  const deck = useMemo(() => derive([]), []);
  const message = state === "loading" ? (
    <div className="grid h-full place-items-center px-6">
      <p className="flex items-center gap-2.5 text-[14px] text-ink-soft">
        <LiveMark status="run" className="h-2.5 w-3" />
        Memuat jejak run{ticker ? ` ${ticker}` : ""}…
      </p>
    </div>
  ) : (
    <div className="grid h-full place-content-center gap-1.5 px-6 text-center">
      <p className="text-[14.5px] font-medium text-ink">Jejak run belum bisa diputar di sini.</p>
      <p className="text-[13.5px] text-ink-soft">Company update tersimpan tetap bisa dibuka di halaman <Link to="/laporan">Laporan</Link>.</p>
    </div>
  );
  return <Frame deck={deck} ticker={state === "loading" ? ticker : undefined} message={message} reduce />;
}

type FrameProps = {
  frameRef?: RefObject<HTMLDivElement | null>;
  deck: DeckState;
  ticker?: string;
  name?: string | null;
  item?: ReportItem;
  reduce: boolean;
  recorded?: boolean;
  finished?: boolean;
  progress?: number;
  playing?: boolean;
  held?: boolean;
  onToggle?: () => void;
  message?: ReactNode;
};

function Frame({ frameRef, deck, ticker, name, item, reduce, recorded = false, finished = false, progress = 0,
  playing = false, held = false, onToggle, message }: FrameProps) {
  const captionId = useId();
  const rows = deck.steps.filter((s) => STREAM.has(s.kind)).slice(-ROWS);
  const at = deck.phaseAt;
  const chosen = deck.chain.find((c) => c.decision === "Terpilih");
  // Announce phases, not rows: a polite summary that changes a handful of times per run.
  const summary = !playing ? "" : at >= 0 ? `Fase ${at + 1} dari ${deck.phases.length}: ${deck.phases[at].title}` : "";
  const pane = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const [over, setOver] = useState(false);
  // Rows fill from the top; once they overflow the window, it keeps the newest in view
  // (and only then fades the oldest out at the top edge).
  useLayoutEffect(() => {
    const el = pane.current;
    const inner = list.current;
    if (!el || !inner) return;
    const stick = () => {
      setOver(inner.offsetHeight > el.clientHeight + 1);
      el.scrollTop = el.scrollHeight;
    };
    stick();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(stick);
    ro.observe(inner);
    return () => ro.disconnect();
  }, [message]);

  return (
    <figure className="m-0" aria-labelledby={captionId}>
      <div ref={frameRef} className="panel overflow-hidden">
        <div className="flex h-11 items-center gap-3 px-3.5">
          <LiveMark status={finished ? "ok" : playing ? "run" : "idle"} className="h-3 w-3.5" />
          <span className="font-mono text-[13.5px] font-semibold tracking-[.05em] text-ink-strong">{ticker ?? "Emiten"}</span>
          {name && <span className="min-w-0 truncate text-[13px] text-ink-soft max-sm:hidden">{name}</span>}
          <div className="ml-auto flex flex-none items-center gap-3">
            <PhaseTrack deck={deck} finished={finished} />
            {recorded && deck.elapsed > 0 && <span className="data text-ink-soft max-md:hidden">{duration(deck.elapsed)}</span>}
            {onToggle && (
              <button type="button" onClick={onToggle} aria-label={held ? "Lanjutkan putar ulang" : "Jeda putar ulang"}
                className="grid size-8 cursor-pointer place-items-center rounded-md text-ink-soft transition-colors hover:bg-raised hover:text-ink-strong">
                {held ? <Play aria-hidden className="size-4" strokeWidth={2.2} /> : <Pause aria-hidden className="size-4" strokeWidth={2.2} />}
              </button>
            )}
          </div>
        </div>
        <div aria-hidden className="h-px bg-rule">
          <div className="h-full origin-left bg-brand-ink transition-transform duration-300 ease-linear" style={{ transform: `scaleX(${progress})` }} />
        </div>

        <div className="grid sm:h-[396px] sm:grid-cols-[216px_minmax(0,1fr)]">
          <div className="flex min-h-0 flex-col overflow-hidden border-rule sm:border-r">
            <Rail deck={deck} />
            <Plan deck={deck} reduce={reduce} />
          </div>
          <div ref={pane} className={`relative h-full overflow-hidden max-sm:h-[232px] ${over ? "[mask-image:linear-gradient(to_bottom,transparent,#000_26px)]" : ""}`}>
            {message ?? (
              <ol ref={list} aria-label="Langkah terbaru" className="m-0 list-none p-0 max-sm:[&>li:nth-last-child(n+5)]:hidden">
                <AnimatePresence initial={false} mode="popLayout">
                  {rows.map((step) => (
                    <motion.li key={step.id} layout={!reduce}
                      initial={reduce ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
                      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -10, transition: { duration: 0.2 } }}
                      transition={SPRING}
                      className="relative overflow-hidden border-b border-rule-soft">
                      <StreamRow step={step} recorded={recorded} reduce={reduce} />
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ol>
            )}
          </div>
        </div>

        <GateBoard deck={deck} />
        <Outcome deck={deck} item={item} chosen={chosen} reduce={reduce} />
      </div>
      <p className="sr-only" aria-live="polite">{summary}</p>
      <figcaption className={message ? "sr-only" : "mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-[13.5px] text-ink-soft"}>
        <span id={captionId}>{ticker && !message ? `Putar ulang run ${ticker} dari jejak audit.` : "Putar ulang run tersimpan."}</span>
        {ticker && !message && (
          <Link to={`/laporan/${ticker}/putar`} className="btn btn-ghost btn-sm">Buka Deck</Link>
        )}
      </figcaption>
    </figure>
  );
}

function PhaseTrack({ deck, finished }: { deck: DeckState; finished: boolean }) {
  const at = deck.phaseAt;
  const label = finished ? "Selesai" : at >= 0 ? `${at + 1}/${deck.phases.length} ${deck.phases[at].title}` : "Antri";
  const tone: Record<Status, string> = { idle: "bg-rule", run: "bg-brand", ok: "bg-teal", warn: "bg-warn-rule", error: "bg-err-ink" };
  return (
    <div className="flex items-center gap-2.5">
      <span aria-hidden className="flex gap-[3px]">
        {deck.phases.map((p) => (
          <span key={p.id} className={`h-[3px] w-3 rounded-full transition-colors duration-300 ${tone[p.status]}`} />
        ))}
      </span>
      <span className="data text-ink-soft max-sm:hidden">{label}</span>
    </div>
  );
}

function Rail({ deck }: { deck: DeckState }) {
  return (
    <ol aria-label="Status agen" className="m-0 grid list-none p-0 py-1.5 max-sm:grid-cols-2 max-sm:border-b max-sm:border-rule">
      {AGENTS.map((a) => {
        const st = deck.agents[a.id];
        return (
          <li key={a.id} className="relative flex h-8 min-w-0 items-center gap-2 px-3.5">
            {/* Remounts on each event from this agent, so the row holds its light, then settles. */}
            {st.lastEvent >= 0 && <span key={st.lastEvent} aria-hidden className="absolute inset-0 animate-hold" />}
            <LiveMark status={st.status} className="relative h-2.5 w-3 flex-none" />
            <span className={`relative truncate text-[13px] ${st.status === "idle" ? "text-ink-soft" : "font-medium text-ink-strong"}`}>{a.short}</span>
            <span aria-hidden className="relative font-mono text-[10px] text-ink-faint max-sm:hidden">{a.engine === "llm" ? "LLM" : "kode"}</span>
            <span className={`relative ml-auto flex-none font-mono text-[10.5px] font-medium tracking-[.06em] uppercase ${WORD_TONE[st.status]}`}>
              {STATUS_WORD[st.status]}
            </span>
            <span className="sr-only">, {a.engine === "llm" ? "model bahasa" : "kode host"}</span>
          </li>
        );
      })}
    </ol>
  );
}

function Plan({ deck, reduce }: { deck: DeckState; reduce: boolean }) {
  const { question, hypotheses } = deck.plan;
  const planning = deck.agents.analis.status === "run" && !question;
  const tally = new Map<string, number>();
  for (const h of hypotheses) if (h.verdict) tally.set(h.verdict, (tally.get(h.verdict) ?? 0) + 1);
  const fade = reduce ? {} : { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.24 } };
  return (
    <div className="flex-1 border-t border-rule-soft px-3.5 pt-3 pb-3.5 max-sm:hidden">
      <p className="text-[11.5px] font-medium text-ink-faint">Pertanyaan riset</p>
      <AnimatePresence mode="wait" initial={false}>
        {question ? (
          <motion.p key="q" {...fade} className="mt-1 line-clamp-3 text-[12.5px] leading-[1.45] text-ink">{question}</motion.p>
        ) : (
          <motion.p key="w" {...fade} className="mt-1 text-[12.5px] text-ink-faint">{planning ? "Perencana menulis pertanyaan…" : "Belum ada"}</motion.p>
        )}
      </AnimatePresence>
      {hypotheses.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <ul aria-label="Hipotesis" className="m-0 flex list-none gap-1 p-0">
            {hypotheses.map((h) => (
              <li key={h.index} title={h.text.replace(HYPOTHESIS_NUMBER, "")}
                className={`rounded-[4px] border px-1.5 font-mono text-[11px] leading-[18px] font-medium transition-colors duration-300 ${chipTone(h.verdict)}`}>
                H{h.index}<span className="sr-only">: {h.verdict ?? "belum diuji"}</span>
              </li>
            ))}
          </ul>
          {tally.size > 0 && (
            <span className="text-[11.5px] text-ink-soft">{[...tally].map(([v, n]) => `${n} ${v}`).join(", ")}</span>
          )}
        </div>
      )}
    </div>
  );
}

function chipTone(verdict?: string) {
  if (!verdict) return "border-rule text-ink-soft";
  if (verdict === "didukung") return "border-transparent bg-ok-bg text-ok-ink";
  if (verdict === "tidak didukung") return "border-transparent bg-warn-bg text-warn-ink";
  return "border-dashed border-rule-strong text-ink-soft";
}

function StreamRow({ step, recorded, reduce }: { step: Step; recorded: boolean; reduce: boolean }) {
  const call = step.kind === "call";
  const running = step.status === "run";
  const label = call ? step.tool : AGENT[step.agent].short;
  const text = call ? step.reason || step.title : step.title;
  // A call's answer is its result detail; a task's is its closing label, with the detail beside it.
  const main = running ? undefined : call ? step.resultDetail || step.result : step.result ?? step.resultDetail;
  const extra = !running && !call && step.result ? step.resultDetail : undefined;
  const flagged = step.status === "warn" || step.status === "error";
  const right = running || flagged ? STATUS_WORD[step.status]
    : recorded && step.t1 !== undefined && step.t1 > step.t0 ? duration(step.t1 - step.t0) : "";
  return (
    <>
      <span key={step.status} aria-hidden className="absolute inset-0 animate-hold" />
      <div className="relative grid grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-2">
        <LiveMark status={step.status} className="h-2.5 w-3" />
        <p className="truncate text-[13.5px] leading-5">
          <span className={`mr-2 text-ink-strong ${call ? "font-mono text-[12.5px] font-semibold" : "font-semibold"}`}>{label}</span>
          <span className="text-ink-soft">{text}</span>
        </p>
        <span className={`font-mono text-[11px] font-medium tabular-nums ${running || flagged ? "tracking-[.06em] uppercase" : ""} ${WORD_TONE[step.status]}`}>
          {right}
        </span>
        <AnimatePresence initial={false}>
          {main && (
            <motion.p key="result" initial={reduce ? false : { height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
              transition={SPRING} className="col-span-2 col-start-2 m-0 flex min-w-0 items-center gap-1.5 overflow-hidden text-[12.5px] leading-5 text-ink">
              <CornerDownRight aria-hidden className={`size-3.5 flex-none ${flagged ? "text-warn-ink" : "text-done"}`} strokeWidth={2.2} />
              <span className="truncate">
                {main}
                {extra && (STATUS_CODE.test(extra)
                  ? <code className="ml-2 font-mono text-[11.5px] text-ink-faint">{extra}</code>
                  : <span className="ml-2 text-ink-soft">{extra}</span>)}
              </span>
            </motion.p>
          )}
        </AnimatePresence>
      </div>
      {running && !reduce && <span aria-hidden className="absolute bottom-0 left-0 h-px w-2/5 animate-sweep bg-brand-ink" />}
    </>
  );
}

function GateBoard({ deck }: { deck: DeckState }) {
  return (
    <ol aria-label="Method Gates" className="m-0 grid list-none grid-cols-6 border-t border-rule p-0">
      {deck.gates.map((g) => (
        <li key={g.n} className="relative min-w-0 border-r border-rule-soft px-3 pt-2.5 pb-3 last:border-r-0 max-sm:px-2">
          {g.status !== "idle" && <span key={g.verdict} aria-hidden className="absolute inset-0 animate-hold" />}
          <p aria-hidden className="relative m-0 flex items-start gap-1.5">
            <span className="font-mono text-[11px] leading-[15px] font-semibold text-ink-soft">{g.n}</span>
            <span className="line-clamp-2 min-h-[30px] text-[11.5px] leading-[15px] font-medium text-ink max-sm:hidden">{g.name}</span>
          </p>
          <GateMeter status={g.status} className="relative mt-2 h-[3px]" />
          <p aria-hidden className={`relative m-0 mt-1.5 truncate text-[11.5px] font-medium max-sm:hidden ${GATE_TONE[g.status].text}`}>
            {g.verdict || "antri"}
          </p>
          <span className="sr-only">Method Gate {g.n}, {g.name}: {g.verdict || "belum dinilai"}</span>
        </li>
      ))}
    </ol>
  );
}

function Outcome({ deck, item, chosen, reduce }: { deck: DeckState; item?: ReportItem; chosen?: DeckState["chain"][number]; reduce: boolean }) {
  const checks = deck.chain.filter((c) => c.decision === "Silang cek").length;
  const release = deck.release;
  const rated = Boolean(release?.rating);
  const swap = reduce ? {} : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: SPRING };
  return (
    <div className="grid min-h-[62px] grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 border-t border-rule bg-raised px-3.5 py-2.5">
      <div className="min-w-0">
        <p className="m-0 text-[11.5px] font-medium text-ink-faint">Metode terpilih</p>
        <AnimatePresence mode="wait" initial={false}>
          {chosen ? (
            <motion.p key={chosen.method} {...swap} className="m-0 flex min-w-0 items-baseline gap-2">
              <span className="truncate font-mono text-[14.5px] font-semibold text-ink-strong">{chosen.method}</span>
              {chosen.value !== "-" && <span className="flex-none font-mono text-[13px] text-ink tabular-nums">{chosen.value}</span>}
              {checks > 0 && <span className="flex-none text-[12.5px] text-ink-soft max-sm:hidden">{checks} silang cek</span>}
            </motion.p>
          ) : (
            <motion.p key="wait" {...swap} className="m-0 text-[13px] text-ink-faint">Menunggu Method Gates</motion.p>
          )}
        </AnimatePresence>
      </div>
      <AnimatePresence mode="wait" initial={false}>
        {rated && release ? (
          <motion.div key="rated" {...swap} className="flex items-center gap-3">
            {item ? <RatingBadge item={item} /> : <span className="pill">Skenario nilai</span>}
            <div className="text-right leading-tight">
              <p className="m-0 font-mono text-[13.5px] font-semibold text-ink-strong tabular-nums">Nilai model Rp{release.tp}</p>
              {release.upside && <p className="m-0 font-mono text-[12px] text-ink-soft tabular-nums">Selisih dari harga {release.upside}</p>}
            </div>
          </motion.div>
        ) : (
          <motion.span key="wait" {...swap} className="text-[13px] text-ink-faint">Nilai model belum tersedia</motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}
