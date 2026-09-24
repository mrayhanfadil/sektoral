import type { ReportItem } from "./api";

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
