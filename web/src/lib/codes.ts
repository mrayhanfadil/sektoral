// Stable codes the server sends beside its Indonesian labels (#34): Method
// Chain decisions, gate and hypothesis verdicts, and run event kinds. Logic
// matches on the code; a response from before the codes existed carries only
// the label, so each reader falls back to matching the label it knows.
import type { EventData } from "./api";
import type { Bi } from "./i18n";

export type DecisionCode = "selected" | "stop_extreme" | "skipped" | "cross_check" | "not_needed" | "unavailable";
/** `flagged`: a Gate 5 check that is disclosed in the report but does not block the rating. */
export type GateCode = "pass" | "flagged" | "fail" | "not_applicable" | "not_assessable";
export type VerdictCode = "supported" | "not_supported" | "partly_supported" | "unanswered";
export type EventKind =
  | "tool_start" | "tool_done" | "tool_empty" | "tool_error" | "hypothesis"
  | "primary_method" | "chain_done" | "release" | "gate" | "chain_row";

/** Each code's words; the Indonesian is the label the server sends for it. */
export const DECISION_WORD: Record<DecisionCode, Bi> = {
  selected: { id: "Terpilih", en: "Selected" },
  stop_extreme: { id: "Terpilih, ekstrem (rantai berhenti)", en: "Selected, extreme (chain stops)" },
  skipped: { id: "Dilewati", en: "Skipped" },
  cross_check: { id: "Silang cek", en: "Cross-check" },
  not_needed: { id: "Tidak dijalankan", en: "Not run" },
  unavailable: { id: "Belum tersedia", en: "Not yet available" },
};
export const GATE_WORD: Record<GateCode, Bi> = {
  pass: { id: "lolos", en: "pass" },
  flagged: { id: "ditandai", en: "flagged" },
  fail: { id: "gagal", en: "fail" },
  not_applicable: { id: "tidak berlaku", en: "not applicable" },
  not_assessable: { id: "tidak dapat dinilai", en: "cannot be assessed" },
};
export const VERDICT_WORD: Record<VerdictCode, Bi> = {
  supported: { id: "didukung", en: "supported" },
  not_supported: { id: "tidak didukung", en: "not supported" },
  partly_supported: { id: "sebagian didukung", en: "partly supported" },
  unanswered: { id: "belum terjawab", en: "unanswered" },
};

const EVENT_KINDS: ReadonlySet<string> = new Set<EventKind>([
  "tool_start", "tool_done", "tool_empty", "tool_error", "hypothesis",
  "primary_method", "chain_done", "release", "gate", "chain_row",
]);

/** A value as the server sent it: event data holds strings and a few numbers; API fields may be null. */
type Value = string | number | null | undefined;

/** A value as text; undefined when there is none. */
export function str(value: Value): string | undefined {
  return value === null || value === undefined || value === "" ? undefined : String(value);
}

/** A value as a number; undefined when it is not one. */
export function num(value: Value): number | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : undefined;
}

/** The code whose Indonesian word is ``label`` (case-insensitive), for responses without codes. */
function byLabel<C extends string>(words: Record<C, Bi>, label: Value): C | undefined {
  const text = (str(label) ?? "").trim().toLowerCase();
  if (!text) return undefined;
  return (Object.keys(words) as C[]).find((code) => words[code].id.toLowerCase() === text);
}

function known<C extends string>(words: Record<C, Bi>, code: Value): C | undefined {
  const text = str(code);
  return text && Object.prototype.hasOwnProperty.call(words, text) ? (text as C) : undefined;
}

/** A Method Chain decision: `decision_code`, else the label ("Terpilih", "Silang cek", ...). */
export function decisionCode(code: Value, label?: Value): DecisionCode | undefined {
  return known(DECISION_WORD, code)
    // The extreme stop's label once came without its "(rantai berhenti)" note.
    ?? ((str(label) ?? "").startsWith("Terpilih, ekstrem") ? "stop_extreme" : byLabel(DECISION_WORD, label));
}

/** A Method Gate verdict: `verdict_code`, else the label ("lolos", "gagal", ...). */
export function gateCode(code: Value, label?: Value): GateCode | undefined {
  return known(GATE_WORD, code) ?? byLabel(GATE_WORD, label);
}

/** A hypothesis verdict: `verdict_code`, else the label ("didukung", "belum terjawab", ...). */
export function verdictCode(code: Value, label?: Value): VerdictCode | undefined {
  return known(VERDICT_WORD, code) ?? byLabel(VERDICT_WORD, label);
}

/**
 * What a run event reports: `data.kind`, else read from the label the
 * pipeline writes for it ("Menjalankan <tool>", "<tool> selesai",
 * "<tool>: …", "Metode utama <X>").
 */
export function eventKind(e: { label: string; tool?: string; data?: EventData }): EventKind | undefined {
  const kind = str(e.data?.kind);
  if (kind && EVENT_KINDS.has(kind)) return kind as EventKind;
  const tool = e.tool ?? "";
  if (tool === "hypothesis") return "hypothesis";
  if (tool === "release") return "release";
  if (tool === "chain_step") return "chain_row";
  if (tool.startsWith("gate_")) return "gate";
  if (tool) {
    if (e.label === `Menjalankan ${tool}`) return "tool_start";
    if (e.label === `${tool} selesai`) return "tool_done";
    if (e.label.startsWith(`${tool}: `)) return "tool_error";
    return undefined;
  }
  if (e.label.startsWith("Metode utama ")) return "primary_method";
  if (e.label === "Rantai metode selesai") return "chain_done";
  return undefined;
}

/** The primary method an event names: `data.method`, else the text after "Metode utama ". */
export function primaryMethodOf(e: { label?: string; data?: EventData }): string | undefined {
  const method = str(e.data?.method);
  if (method) return method;
  return e.label?.startsWith("Metode utama ") ? e.label.slice("Metode utama ".length) : undefined;
}
