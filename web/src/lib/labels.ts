import type { ChainStep, ProblemNote, ReportItem } from "./api";
import { decisionCode } from "./codes";
import { getLang, twin, type Bi, type Lang } from "./i18n";

export type RatingTone = "buy" | "hold" | "sell" | "review";

/** What decides the rating label; the Deck sets `review_required` from its own Method Gate 5 reading. */
export type RatingSource = Pick<ReportItem, "rating"> &
  Partial<Pick<ReportItem, "held_reason" | "publication_state">> & { review_required?: boolean };

/**
 * Published rating; without one, Review Required when Method Gate 5 held it,
 * else Draft. An item with a `publication_state` is held for a publication
 * step (its `held_reason` says which, never the gate); only an older item
 * without it falls back to a `held_reason` that names Method Gate 5.
 */
export function ratingLabel(item: RatingSource): string {
  if (item.rating) return item.rating;
  if (item.review_required) return "Review Required";
  if (item.publication_state) return "Draft";
  return item.held_reason?.startsWith("Method Gate 5") ? "Review Required" : "Draft";
}

export function ratingTone(item: Pick<ReportItem, "rating">): RatingTone {
  const rating = (item.rating ?? "").toLowerCase();
  return rating === "buy" || rating === "hold" || rating === "sell" ? rating : "review";
}

/** The featured landing report: primary method selected, most cross-checks. */
export function featuredReport(items: ReportItem[]): ReportItem | undefined {
  const score = (item: ReportItem): [number, number, number] => {
    const codes = item.chain.map((s) => decisionCode(s.decision_code, s.decision));
    return [codes[0] === "selected" ? 1 : 0, codes.filter((c) => c === "cross_check").length, codes.length];
  };
  const candidates = items.filter((i) => i.published && i.files.pdf && i.chain.length);
  return candidates.reduce<ReportItem | undefined>((best, item) => {
    if (!best) return item;
    const [a, b] = [score(item), score(best)];
    for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i] ? item : best;
    return best;
  }, undefined);
}

/** The chain step the Method Chain selected (by `decision_code`, else the "Terpilih" label). */
export function selectedStep<T extends Pick<ChainStep, "decision" | "decision_code">>(chain: T[]): T | undefined {
  return chain.find((s) => decisionCode(s.decision_code, s.decision) === "selected");
}

export const PROGRESS_STEPS: readonly { title: Bi; sub: Bi }[] = [
  { title: { id: "Rencana", en: "Plan" }, sub: { id: "Pertanyaan & hipotesis", en: "Questions & hypotheses" } },
  { title: { id: "Tool & sinyal", en: "Tools & signals" }, sub: { id: "Data Sectors, peer, anomali", en: "Sectors data, peers, anomalies" } },
  { title: { id: "Uji hipotesis", en: "Hypothesis tests" }, sub: { id: "Kesimpulan tervalidasi", en: "Validated conclusions" } },
  { title: { id: "Skenario & valuasi", en: "Scenarios & valuation" }, sub: { id: "Asumsi, rantai metode, harness", en: "Assumptions, Method Chain, harness" } },
  { title: { id: "Hasil siap", en: "Results ready" }, sub: { id: "Laporan, PDF, dan jejak", en: "Report, PDF and Audit Trace" } },
];

const STEP_OF: Record<string, number> = {
  memory: 0, plan: 0, tool: 1, signals: 1, synthesis: 2, research: 3, forecast: 3, report: 3, done: 4,
};

/** Index of the current progress step (5 when the run completed). */
export function progressStep(state: string, stages: string[]): number {
  if (state === "completed") return 5;
  return stages.reduce((at, stage) => Math.max(at, STEP_OF[stage] ?? 0), 0);
}

/**
 * A validator note read for people: the message, and the tokens it asked the
 * model to remove, cleaned. The analyst validator lists raw prose tokens
 * ("11,", "2026:"), so stray punctuation is stripped and repeats dropped.
 */
export function validatorNote(text: string): { message: string; removed: string[] } {
  const clean = text.replace(/\s*…$/, "").trim();
  const m = clean.match(/^(.*?);\s*hapus(?:\s+kata)?:\s*(.*)$/s);
  const message = (m ? m[1] : clean).trim();
  // A leading plain word starts a sentence; a leading field name ("hypotheses[0]") stays as written.
  const sentence = /^[a-z]+(\s|$)/.test(message) ? message.charAt(0).toUpperCase() + message.slice(1) : message;
  if (!m) return { message: sentence, removed: [] };
  const removed: string[] = [];
  for (const raw of m[2].split(/,\s+|\s+/)) {
    const token = raw.replace(/^[^\p{L}\p{N}+−-]+|[^\p{L}\p{N}%]+$/gu, "");
    if (token && !removed.includes(token)) removed.push(token);
  }
  return { message: sentence, removed };
}

/**
 * The analyst validator's notes for people, in the reader's language: the
 * server's parsed `analyst_problem_notes` (each message's `message_en` twin
 * for an English reader) when it sends them, else each raw note parsed here
 * (`raw_en`, the raw notes' parallel English list, where the server has it).
 */
export function problemNotes(notes: ProblemNote[] | null | undefined, raw: string[],
  raw_en?: (string | null)[], lang: Lang = getLang()): ProblemNote[] {
  if (notes?.length) return lang === "en" ? notes.map((n) => ({ ...n, message: twin(n, "message", lang) })) : notes;
  return twin({ raw, raw_en }, "raw", lang).map(validatorNote);
}
