import type { ReportItem } from "./api";

export type RatingTone = "above" | "below" | "equal" | "review";
type ScenarioLabelInput = { rating?: string | null; upside?: number | string | null; held_reason?: string | null };

function difference(value: number | string | null | undefined): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const cleaned = value.trim().replace(/[−–]/g, "-").replace(/[%\s]/g, "").replace(",", ".");
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Describe the model value relative to the close without an action label. */
export function ratingLabel(item: ScenarioLabelInput): string {
  if (!item.rating) return item.held_reason?.startsWith("Method Gate 5") ? "Perlu ditinjau" : "Draf";
  const upside = difference(item.upside);
  if (upside !== null) {
    if (upside > 0) return "Di atas harga pasar";
    if (upside < 0) return "Di bawah harga pasar";
    return "Setara harga pasar";
  }
  return ["Di atas harga pasar", "Di bawah harga pasar", "Setara harga pasar", "Skenario nilai"]
    .includes(item.rating) ? item.rating : "Skenario nilai";
}

export function ratingTone(item: ScenarioLabelInput): RatingTone {
  if (!item.rating) return "review";
  const upside = difference(item.upside);
  if (upside === null || upside === 0) return "equal";
  return upside > 0 ? "above" : "below";
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

export const PROGRESS_STEPS = [
  { title: "Rencana", sub: "Pertanyaan & hipotesis" },
  { title: "Tool & sinyal", sub: "Data Sectors, peer, anomali" },
  { title: "Uji hipotesis", sub: "Kesimpulan tervalidasi" },
  { title: "Skenario & valuasi", sub: "Asumsi, rantai metode, harness" },
  { title: "Hasil siap", sub: "Laporan, PDF, dan jejak" },
] as const;

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
