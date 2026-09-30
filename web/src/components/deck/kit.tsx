// Small shared pieces of the Deck: motion constants, the hold light, the
// status glyph, the engine tag and the run clock.
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { animate, useReducedMotion } from "motion/react";
import { CircleAlert, CircleCheck, CircleX } from "lucide-react";
import type { Status } from "../../lib/agents";
import { useLang } from "../../lib/i18n";
import { LiveMark } from "../Mark";
import { EXPO, clock } from "./read";

const HOLD: Record<Status, string> = {
  idle: "transparent",
  run: "var(--color-brand-50)",
  ok: "var(--color-ok-bg)",
  warn: "var(--color-warn-bg)",
  error: "var(--color-err-bg)",
};

/** The gate-board raise: a changed row holds its light, then settles. Parent needs `relative isolate`. */
export function Hold({ n, tone }: { n: number; tone: Status }) {
  if (n === 0 || tone === "idle") return null;
  return (
    <span key={n} aria-hidden className="pointer-events-none absolute inset-0 -z-10 animate-hold rounded-[inherit]"
      style={{ "--hold-color": HOLD[tone] } as CSSProperties} />
  );
}

const LIGHT: Record<Status, string> = {
  idle: "transparent",
  run: "var(--color-brand-ink)",
  ok: "var(--color-done)",
  warn: "var(--color-warn-rule)",
  error: "var(--color-err-ink)",
};

/**
 * The row-sized hold light: a short bar at the row's left edge that holds the
 * new state's colour, then settles. Used where many rows can change at once
 * (the hypotheses), so a batch of verdicts lights rows, not the whole block.
 * Parent needs `relative`.
 */
export function HoldLight({ n, tone }: { n: number; tone: Status }) {
  if (n === 0 || tone === "idle") return null;
  return (
    <span key={n} aria-hidden className="pointer-events-none absolute top-2 bottom-2 left-0 w-[3px] animate-hold rounded-full"
      style={{ "--hold-color": LIGHT[tone] } as CSSProperties} />
  );
}

/** One glyph per status: the E-mark breathing while running, drawn icons once settled. */
export function Glyph({ status, className = "" }: { status: Status; className?: string }) {
  if (status === "run") return <span className={`inline-grid size-4 flex-none place-items-center ${className}`}><LiveMark status="run" className="h-3 w-3.5" /></span>;
  const common = `size-4 flex-none ${className}`;
  if (status === "ok") return <CircleCheck aria-hidden className={`${common} text-done`} strokeWidth={2.2} />;
  if (status === "warn") return <CircleAlert aria-hidden className={`${common} text-warn-ink`} strokeWidth={2.2} />;
  if (status === "error") return <CircleX aria-hidden className={`${common} text-err-ink`} strokeWidth={2.2} />;
  return <span aria-hidden className={`inline-grid ${common} place-items-center`}><i className="block size-2.5 rounded-full border-[1.5px] border-rule-strong" /></span>;
}

/** "LLM": a model decides. "host": deterministic code the model cannot change. */
export function EngineTag({ engine }: { engine: "llm" | "host" }) {
  const { t } = useLang();
  return (
    <span title={engine === "llm"
      ? t({ id: "Model bahasa memutuskan langkah ini", en: "A language model decides this step" })
      : t({ id: "Kode host yang deterministik", en: "Deterministic host code" })}
      className={`inline-flex h-[18px] flex-none items-center rounded-[4px] px-1.5 font-mono text-[10.5px] leading-none font-semibold ${
        engine === "llm" ? "bg-brand-50 text-brand-ink" : "border border-rule-soft text-ink-soft"}`}>
      {engine === "llm" ? "LLM" : "host"}
    </span>
  );
}

/** A thin line sweeping under something that is still out. */
export function Sweep({ className = "" }: { className?: string }) {
  return (
    <span aria-hidden className={`pointer-events-none absolute inset-x-0 bottom-0 h-px overflow-hidden ${className}`}>
      <span className="block h-full w-2/5 animate-sweep bg-[linear-gradient(90deg,transparent,var(--color-brand-ink),transparent)]" />
    </span>
  );
}

/** A number that eases to its new value instead of jumping (replays skip model waits). */
export function Tweened({ value, format }: { value: number; format: (n: number) => string }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (reduce) { from.current = value; setShown(value); return; }
    const controls = animate(from.current, value, {
      duration: 0.45, ease: EXPO,
      onUpdate: (v) => { from.current = v; setShown(v); },
    });
    return () => controls.stop();
  }, [value, reduce]);
  return <>{format(shown)}</>;
}

/**
 * The live clock of a running job: the server's event times are relative to
 * the job start, so the start is estimated from the earliest reading and the
 * clock ticks on the client between polls.
 */
export function LiveClock({ lastT, running }: { lastT: number; running: boolean }) {
  const start = useRef<number | null>(null);
  const [now, setNow] = useState(() => performance.now() / 1000);
  useLayoutEffect(() => {
    const candidate = performance.now() / 1000 - lastT;
    if (start.current === null || candidate < start.current) start.current = candidate;
  }, [lastT]);
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(performance.now() / 1000), 100);
    return () => window.clearInterval(id);
  }, [running]);
  const value = running && start.current !== null ? Math.max(lastT, now - start.current) : lastT;
  return <>{clock(value)}</>;
}

/** Text clamped to a few lines, with a toggle only when it actually overflows. */
export function Clamp({ lines, className = "", children, title }: { lines: 2 | 3 | 4; className?: string; children: ReactNode; title?: string }) {
  const { t } = useLang();
  const ref = useRef<HTMLParagraphElement>(null);
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setOverflows(el.scrollHeight - el.clientHeight > 2);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [children]);
  const clamp = { 2: "line-clamp-2", 3: "line-clamp-3", 4: "line-clamp-4" }[lines];
  return (
    <>
      <p ref={ref} title={title} className={`${open ? "" : clamp} ${className}`}>{children}</p>
      {(overflows || open) && (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
          className="mt-0.5 cursor-pointer rounded-sm text-[12.5px] font-medium text-brand-ink hover:underline">
          {open ? t({ id: "Ringkas", en: "Show less" }) : t({ id: "Selengkapnya", en: "Show more" })}
        </button>
      )}
    </>
  );
}

/** Section heading row of a console region: a plain heading and a mono reading. */
export function RegionHead({ id, title, reading }: { id: string; title: string; reading?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h2 id={id} className="text-[14px] font-bold tracking-normal text-ink-strong">{title}</h2>
      {reading !== undefined && <span className="data text-ink-soft">{reading}</span>}
    </div>
  );
}
