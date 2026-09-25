// Pure helpers of the Deck: motion constants, formats and word maps.
import { useState } from "react";
import type { Status } from "../../lib/agents";

/** Damped springs: the deck never bounces. */
export const SPRING = { type: "spring", stiffness: 420, damping: 40, mass: 0.8 } as const;
export const SPRING_SOFT = { type: "spring", stiffness: 240, damping: 34, mass: 1 } as const;
export const EXPO = [0.16, 1, 0.3, 1] as const;
/** A gate needle settling: overdamped (damping above 2*sqrt(k*m)), so it eases in and never overshoots. */
export const GATE_SETTLE = { stiffness: 90, damping: 26, mass: 1 } as const;

export const STATUS_INK: Record<Status, string> = {
  idle: "text-ink-faint", run: "text-brand-ink", ok: "text-done", warn: "text-warn-ink", error: "text-err-ink",
};

/**
 * Counts how often ``value`` changed since mount (0 on mount), so a row can
 * hold its light only for a change the viewer actually watched.
 */
export function useChangeCount(value: unknown): number {
  const [seen, setSeen] = useState({ value, n: 0 });
  if (!Object.is(seen.value, value)) {
    setSeen({ value, n: seen.n + 1 });
    return seen.n + 1;
  }
  return seen.n;
}

/** Run seconds as a console clock, "01:39,1". */
export function clock(seconds: number): string {
  const tenths = Math.max(0, Math.floor(seconds * 10 + 1e-6));
  const m = Math.floor(tenths / 600);
  const s = Math.floor((tenths % 600) / 10);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${tenths % 10}`;
}

const VERDICT_TONE: Record<string, string> = { didukung: "pill-ok", "tidak didukung": "pill-err" };

/** Pill tone of a hypothesis verdict; anything short of a verdict reads as a gap. */
export function verdictTone(verdict?: string): string {
  if (!verdict) return "";
  return VERDICT_TONE[verdict.toLowerCase()] ?? "pill-warn";
}

/** The analyst could not answer the hypothesis: tested, but no verdict. */
export const UNANSWERED = "belum terjawab";

/** A real verdict (didukung, tidak didukung, sebagian...); "belum terjawab" is not one. */
export function isJudged(verdict?: string): boolean {
  return !!verdict && verdict.toLowerCase() !== UNANSWERED;
}

/**
 * The row glyph of a hypothesis: open until the analyst answers, the done
 * check for a real verdict, the warning mark when it stayed unanswered.
 */
export function verdictGlyph(verdict?: string): Status {
  return !verdict ? "idle" : isJudged(verdict) ? "ok" : "warn";
}

export function verdictStatus(verdict?: string): Status {
  const tone = verdictTone(verdict);
  return !verdict ? "idle" : tone === "pill-ok" ? "ok" : tone === "pill-err" ? "error" : "warn";
}

/** Status codes the pipeline puts in a detail, in the deck's words. */
const CODE_WORDS: Record<string, string> = {
  distributable: "dapat didistribusikan",
  distributable_assumption_led: "dapat didistribusikan, berbasis asumsi analis",
  draft_non_distributable: "draft, tidak didistribusikan",
  partial: "parsial",
  complete: "lengkap",
  searched: "pencarian selesai",
  validated: "tervalidasi",
};
export const words = (text?: string) => (text && CODE_WORDS[text]) ?? text;
