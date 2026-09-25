import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { JobEvent } from "./api";

/** Longest pause kept between two events on playback, in run seconds. */
const GAP_CAP = 2.4;
/** Shortest pause, so events recorded in the same tenth of a second still arrive one by one. */
const GAP_MIN = 0.22;

/** Playback time (seconds at 1x) of each event: long model waits are shortened, order kept. */
export function playbackTimes(events: JobEvent[]): number[] {
  const out: number[] = [];
  events.forEach((e, i) => {
    if (i === 0) return out.push(0);
    const gap = Math.max(0, e.t - events[i - 1].t);
    out.push(out[i - 1] + Math.min(Math.max(gap, GAP_MIN), GAP_CAP));
  });
  return out;
}

export type Replay = {
  /** Events shown so far. */
  shown: JobEvent[];
  count: number;
  total: number;
  playing: boolean;
  finished: boolean;
  speed: number;
  setSpeed: (speed: number) => void;
  play: () => void;
  pause: () => void;
  restart: () => void;
  /** Jump to show the first ``count`` events. */
  seek: (count: number) => void;
  /** Share of the run shown, 0 to 1, by playback time. */
  progress: number;
};

/**
 * Play a stored run back event by event. ``loop`` restarts after a pause at
 * the end (the landing page reel); the Deck replay stops at the end.
 */
export function useReplay(events: JobEvent[], opts: { speed?: number; autoplay?: boolean; loop?: boolean; startAt?: number } = {}): Replay {
  const times = useMemo(() => playbackTimes(events), [events]);
  const [count, setCount] = useState(() => Math.min(opts.startAt ?? 0, events.length));
  const [playing, setPlaying] = useState(opts.autoplay ?? true);
  const [speed, setSpeed] = useState(opts.speed ?? 4);
  const timer = useRef<number | undefined>(undefined);
  const total = events.length;
  const finished = total > 0 && count >= total;

  useEffect(() => {
    setCount(Math.min(opts.startAt ?? 0, events.length));
    // A new run starts from the top.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (!playing || total === 0) return;
    if (count >= total) {
      if (opts.loop) timer.current = window.setTimeout(() => setCount(0), 4200);
      return;
    }
    const wait = count === 0 ? 350 : ((times[count] - times[count - 1]) / speed) * 1000;
    timer.current = window.setTimeout(() => setCount((c) => Math.min(c + 1, total)), wait);
    return () => window.clearTimeout(timer.current);
  }, [count, playing, speed, total, times, opts.loop]);

  const play = useCallback(() => {
    setPlaying(true);
    setCount((c) => (c >= total ? 0 : c));
  }, [total]);
  const pause = useCallback(() => setPlaying(false), []);
  const restart = useCallback(() => { setCount(0); setPlaying(true); }, []);
  const seek = useCallback((n: number) => setCount(Math.max(0, Math.min(total, Math.round(n)))), [total]);

  const end = times[total - 1] || 1;
  const progress = total === 0 ? 0 : count === 0 ? 0 : Math.min(1, times[count - 1] / end);
  const shown = useMemo(() => events.slice(0, count), [events, count]);
  return { shown, count, total, playing, finished, speed, setSpeed, play, pause, restart, seek, progress };
}
