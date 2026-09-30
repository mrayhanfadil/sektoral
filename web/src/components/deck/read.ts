// Pure helpers of the Deck: motion constants, formats and word maps.
import { useState } from "react";
import type { Status, Step } from "../../lib/agents";
import type { EventData } from "../../lib/api";
import {
  DECISION_WORD, GATE_WORD, VERDICT_WORD, primaryMethodOf, str, verdictCode,
  type DecisionCode, type EventKind, type GateCode, type VerdictCode,
} from "../../lib/codes";
import { getLang, pick, type Bi, type Lang } from "../../lib/i18n";

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

/**
 * A hypothesis verdict as the Deck holds it: the label the pipeline sent and
 * its code (lib/codes.ts `verdictCode`). The helpers below read the code; the
 * label only says whether any verdict arrived.
 */
export type Verdict = { verdict?: string | null; code?: VerdictCode };

/** A verdict from an event's data: `verdict_code`, else the label. */
export const verdictOf = (data: EventData | undefined): Verdict =>
  ({ verdict: str(data?.verdict), code: verdictCode(data?.verdict_code, data?.verdict) });

const VERDICT_TONE: Partial<Record<VerdictCode, string>> = { supported: "pill-ok", not_supported: "pill-err" };

/** Pill tone of a hypothesis verdict; anything short of a verdict reads as a gap. */
export function verdictTone(v: Verdict): string {
  if (!v.verdict && !v.code) return "";
  return (v.code && VERDICT_TONE[v.code]) ?? "pill-warn";
}

/** A real verdict (supported, not supported, partly...); "unanswered" is not one. */
export function isJudged(v: Verdict): boolean {
  return Boolean(v.verdict || v.code) && v.code !== "unanswered";
}

/**
 * The row glyph of a hypothesis: open until the analyst answers, the done
 * check for a real verdict, the warning mark when it stayed unanswered.
 */
export function verdictGlyph(v: Verdict): Status {
  return !v.verdict && !v.code ? "idle" : isJudged(v) ? "ok" : "warn";
}

export function verdictStatus(v: Verdict): Status {
  const tone = verdictTone(v);
  return !v.verdict && !v.code ? "idle" : tone === "pill-ok" ? "ok" : tone === "pill-err" ? "error" : "warn";
}

/** A verdict in the reader's words: by its code, else the label as sent. */
export const verdictWord = (v: Verdict, lang: Lang = getLang()) =>
  v.code ? VERDICT_WORD[v.code][lang] : words(v.verdict ?? undefined, lang);

/** A gate verdict in the reader's words: by its code, else the label as sent. */
export const gateWord = (g: { verdict?: string; code?: GateCode }, lang: Lang = getLang()) =>
  g.code ? GATE_WORD[g.code][lang] : words(g.verdict, lang);

/** A chain decision in the reader's words: by its code, else the label as sent. */
export const decisionWord = (c: { decision: string; code?: DecisionCode }, lang: Lang = getLang()) =>
  c.code ? DECISION_WORD[c.code][lang] : words(c.decision, lang);

/**
 * Codes and fixed labels the pipeline sends (release status codes in a
 * detail; the Indonesian labels of hypothesis and gate verdicts and
 * method-chain decisions), in the deck's words. Anything else is free text
 * and passes through. Verdicts and decisions read by code where the Deck has
 * one (`verdictWord`, `gateWord`, `decisionWord`); this map shows a label that
 * came without a code.
 */
const CODE_WORDS = new Map<string, Bi>([
  ...Object.entries({
    distributable: { id: "dapat didistribusikan", en: "distributable" },
    distributable_assumption_led: { id: "dapat didistribusikan, berbasis asumsi analis", en: "distributable, assumption-led" },
    draft_non_distributable: { id: "draft, tidak didistribusikan", en: "draft, not distributable" },
    partial: { id: "parsial", en: "partial" },
    complete: { id: "lengkap", en: "complete" },
    searched: { id: "pencarian selesai", en: "search done" },
    validated: { id: "tervalidasi", en: "validated" },
  }),
  ...[VERDICT_WORD, GATE_WORD, DECISION_WORD].flatMap((map) => Object.values<Bi>(map).map((bi) => [bi.id, bi] as const)),
]);
export const words = (text?: string, lang: Lang = getLang()) => (text && CODE_WORDS.get(text)?.[lang]) || text;

/**
 * The gate agent's closing labels and the release label, in the reader's
 * words (from the event's data, so a label without an English twin still
 * reads English); any other label passes through.
 */
export function valuationLabel(label: string, kind: EventKind | undefined, data: EventData | undefined, lang: Lang = getLang()): string {
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

/** What a step reads as last: its closing label, else its title, in the reader's words. */
export const stepLine = (step: Step, lang: Lang = getLang()): string =>
  step.result ? valuationLabel(step.result, step.resultEvent, step.data, lang) : valuationLabel(step.title, step.event, step.data, lang);
