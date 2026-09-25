// Transport for a stored run: play or pause, restart, speed, and a scrubber
// with the phase boundaries marked. Space toggles play anywhere on the page
// except in a control.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { motion } from "motion/react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { PHASES } from "../../lib/agents";
import type { JobEvent } from "../../lib/api";
import { playbackTimes, type Replay } from "../../lib/replay";
import { SPRING } from "./read";

const SPEEDS = [1, 2, 4, 8];

export function ReplayControls({ replay, events, source }: { replay: Replay; events: JobEvent[]; source: "recorded" | "derived" }) {
  const { playing, finished, play, pause, restart, speed, setSpeed } = replay;
  const toggle = () => (playing && !finished ? pause() : play());

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== " " || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, button, a, [role=slider], [role=radio], [role=switch], [contenteditable=true], [role=dialog]")) return;
      e.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const running = playing && !finished;
  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 max-sm:gap-x-2.5">
        <div className="flex items-center gap-1.5">
          <button type="button" onClick={toggle} aria-label={running ? "Jeda" : finished ? "Putar ulang dari awal" : "Putar"}
            className="grid size-9 cursor-pointer place-items-center rounded-md bg-brand text-white shadow-[inset_0_1px_0_rgb(255_255_255/.14)] transition-[background-color,transform] duration-150 hover:bg-brand-hover active:scale-95">
            {running ? <Pause aria-hidden className="size-4" strokeWidth={2.4} fill="currentColor" />
              : <Play aria-hidden className="size-4 translate-x-[1px]" strokeWidth={2.4} fill="currentColor" />}
          </button>
          <button type="button" onClick={restart} aria-label="Ulang dari awal" title="Ulang dari awal"
            className="grid size-9 cursor-pointer place-items-center rounded-md border border-rule text-ink-soft transition-[color,border-color,transform] duration-150 hover:border-rule-strong hover:text-ink-strong active:scale-95">
            <RotateCcw aria-hidden className="size-4" strokeWidth={2.2} />
          </button>
        </div>
        <Speed speed={speed} setSpeed={setSpeed} />
        <Scrubber replay={replay} events={events} />
        <span className="data whitespace-nowrap text-ink-soft max-sm:ml-auto">
          {replay.count}/{replay.total}<span className="max-sm:sr-only"> event</span>
        </span>
      </div>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] leading-snug text-ink-soft">
        <span>
          {source === "derived"
            ? "Diputar ulang dari jejak audit; durasi diperkirakan."
            : "Direkam langsung saat riset berjalan; jeda panjang model dipersingkat."}
        </span>
        <span className="flex items-center gap-1.5 max-sm:hidden"><kbd className="kbd">Spasi</kbd> putar atau jeda</span>
      </p>
    </div>
  );
}

function Speed({ speed, setSpeed }: { speed: number; setSpeed: (s: number) => void }) {
  const group = useRef<HTMLDivElement>(null);
  const onKeyDown = (e: KeyboardEvent) => {
    const i = SPEEDS.indexOf(speed);
    const next = e.key === "ArrowRight" || e.key === "ArrowDown" ? Math.min(i + 1, SPEEDS.length - 1)
      : e.key === "ArrowLeft" || e.key === "ArrowUp" ? Math.max(i - 1, 0) : -1;
    if (next < 0) return;
    e.preventDefault();
    setSpeed(SPEEDS[next]);
    group.current?.querySelectorAll<HTMLElement>("[role=radio]")[next]?.focus();
  };
  return (
    <div ref={group} role="radiogroup" aria-label="Kecepatan putar" onKeyDown={onKeyDown}
      className="flex h-9 items-center rounded-md border border-rule bg-raised p-[3px]">
      {SPEEDS.map((s) => {
        const on = s === speed;
        return (
          <button key={s} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} onClick={() => setSpeed(s)}
            className={`relative h-full min-w-10 cursor-pointer rounded-[5px] px-2 font-mono max-sm:min-w-9 max-sm:px-1.5 text-[13px] font-semibold transition-colors duration-150 ${
              on ? "text-brand-ink" : "text-ink-soft hover:text-ink-strong"}`}>
            {on && <motion.span layoutId="replay-speed" aria-hidden transition={SPRING} className="absolute inset-0 rounded-[5px] border border-brand-ink/30 bg-brand-100" />}
            <span className="relative">{s}x</span>
          </button>
        );
      })}
    </div>
  );
}

function Scrubber({ replay, events }: { replay: Replay; events: JobEvent[] }) {
  const track = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const times = useMemo(() => playbackTimes(events), [events]);
  const end = times[times.length - 1] || 1;
  const { total, count, seek, progress } = replay;

  // Where each phase starts on the playback timeline.
  const ticks = useMemo(() => PHASES.slice(1).map((p) => {
    const i = events.findIndex((e) => p.stages.includes(e.stage));
    return i < 0 ? null : { title: p.title, at: times[i] / end };
  }).filter((x): x is { title: string; at: number } => x !== null), [events, times, end]);

  const countAt = (clientX: number) => {
    const rect = track.current!.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    if (ratio < 0.004) return 0;
    let n = 0;
    while (n < total && times[n] / end <= ratio + 1e-9) n++;
    return n;
  };
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (!total) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
    seek(countAt(e.clientX));
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) seek(countAt(e.clientX));
  };
  const onKeyDown = (e: KeyboardEvent) => {
    const step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 }[e.key];
    if (step !== undefined) { e.preventDefault(); seek(count + step); }
    else if (e.key === "Home") { e.preventDefault(); seek(0); }
    else if (e.key === "End") { e.preventDefault(); seek(total); }
  };
  const label = events[count - 1]?.label;
  return (
    <div className="flex min-w-[180px] flex-1 items-center max-sm:order-last max-sm:basis-full">
      <div ref={track} role="slider" tabIndex={0} aria-label="Posisi putar ulang" aria-valuemin={0} aria-valuemax={total} aria-valuenow={count}
        aria-valuetext={`Event ${count} dari ${total}${label ? `: ${label}` : ""}`}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onKeyDown={onKeyDown}
        onPointerUp={() => setDragging(false)} onPointerCancel={() => setDragging(false)}
        className="group relative flex h-9 w-full cursor-pointer touch-none items-center rounded-md select-none">
        <span aria-hidden className="relative block h-1.5 w-full overflow-hidden rounded-full bg-rule-soft">
          <span className={`absolute inset-y-0 left-0 rounded-full bg-brand ${dragging ? "" : "transition-[width] duration-300 ease-[var(--ease-out-expo)]"}`} style={{ width: `${progress * 100}%` }} />
        </span>
        {ticks.map((t) => (
          <span key={t.title} aria-hidden title={t.title} className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-rule-strong" style={{ left: `${t.at * 100}%` }} />
        ))}
        <span aria-hidden className={`absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-brand shadow-[0_1px_3px_rgb(0_0_0/.3)] ${
            dragging ? "scale-125" : "transition-[left,transform] duration-300 ease-[var(--ease-out-expo)] group-hover:scale-110"}`}
          style={{ left: `${progress * 100}%` }} />
      </div>
    </div>
  );
}
