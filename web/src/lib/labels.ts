import type { ReportItem } from "./api";
import type { Bi } from "./i18n";

export type RatingTone = "buy" | "hold" | "sell" | "review";

/** Published rating; a held report is a Draft unless Method Gate 5 held it. */
export function ratingLabel(item: Pick<ReportItem, "rating" | "held_reason">): string {
  if (item.rating) return item.rating;
  return item.held_reason?.startsWith("Method Gate 5") ? "Review Required" : "Draft";
}

export function ratingTone(item: Pick<ReportItem, "rating">): RatingTone {
  const rating = (item.rating ?? "").toLowerCase();
  return rating === "buy" || rating === "hold" || rating === "sell" ? rating : "review";
}

/** The featured landing report: primary method selected, most cross-checks. */
export function featuredReport(items: ReportItem[]): ReportItem | undefined {
  const score = (item: ReportItem): [number, number, number] => {
    const decisions = item.chain.map((s) => s.decision);
    return [decisions[0] === "Terpilih" ? 1 : 0, decisions.filter((d) => d === "Silang cek").length, decisions.length];
  };
  const candidates = items.filter((i) => i.published && i.files.pdf && i.chain.length);
  return candidates.reduce<ReportItem | undefined>((best, item) => {
    if (!best) return item;
    const [a, b] = [score(item), score(best)];
    for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i] ? item : best;
    return best;
  }, undefined);
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
