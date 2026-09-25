// The right column of the Deck: the research plan and its verdicts, the six
// Method Gates as fixed instruments, the method chain, and the result.
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useSpring } from "motion/react";
import { GATES, type DeckState, type GateState, type Hypothesis } from "../../lib/agents";
import { Clamp, Glyph, Hold, HoldLight, RegionHead } from "./kit";
import { GATE_SETTLE, SPRING, SPRING_SOFT, isJudged, useChangeCount, verdictGlyph, verdictStatus, verdictTone } from "./read";

const REGION = "border-b border-rule px-5 py-4 max-sm:px-4";

function Empty({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-[13.5px] leading-snug text-ink-soft">{children}</p>;
}

export function PlanPanel({ state, loading }: { state: DeckState; loading?: boolean }) {
  const { question, hypotheses } = state.plan;
  // Only a real verdict counts; "belum terjawab" was tried but not answered.
  const judged = hypotheses.filter((h) => isJudged(h.verdict)).length;
  return (
    <section aria-labelledby="plan-title" className={REGION}>
      <RegionHead id="plan-title" title="Rencana riset" reading={hypotheses.length ? `${judged}/${hypotheses.length} terjawab` : undefined} />
      {loading ? <Lines n={3} /> : question ? (
        <div className="mt-2">
          <Clamp lines={3} className="text-[15px] leading-snug font-medium text-ink-strong" title={question}>{question}</Clamp>
        </div>
      ) : (
        <Empty>Pertanyaan riset dan hipotesisnya muncul setelah agent perencana menyusun rencana.</Empty>
      )}
      {hypotheses.length > 0 && (
        <ol className="m-0 mt-3 list-none divide-y divide-rule-soft border-t border-rule-soft p-0">
          <AnimatePresence initial={false}>
            {hypotheses.map((h) => <HypothesisRow key={h.index} h={h} />)}
          </AnimatePresence>
        </ol>
      )}
    </section>
  );
}

function HypothesisRow({ h }: { h: Hypothesis }) {
  const changed = useChangeCount(h.verdict);
  const text = h.text.replace(/^H\d+:\s*/, "");
  return (
    <motion.li initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} transition={{ height: SPRING, opacity: { duration: 0.3 } }}
      className="relative isolate overflow-hidden">
      <HoldLight n={changed} tone={verdictStatus(h.verdict)} />
      <div className="grid grid-cols-[26px_minmax(0,1fr)] gap-x-2 py-2.5 pl-2">
        <span className="data pt-[2px] text-ink-soft">H{h.index}</span>
        <div className="min-w-0">
          <p className="line-clamp-3 text-[13.5px] leading-snug text-ink" title={text}>{text}</p>
          <div className="mt-1.5 flex min-h-[22px] flex-wrap items-center gap-2">
            <Glyph status={verdictGlyph(h.verdict)} />
            <AnimatePresence mode="popLayout" initial={false}>
              {h.verdict ? (
                <motion.span key={h.verdict} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  transition={SPRING_SOFT} className={`pill ${verdictTone(h.verdict)} px-2 py-0 text-[12.5px]`} title={h.reason}>
                  {h.verdict}
                </motion.span>
              ) : (
                <motion.span key="wait" exit={{ opacity: 0 }} className="text-[12.5px] text-ink-faint">menunggu uji</motion.span>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.li>
  );
}

/** Each verdict word keeps one look and one needle position: the gate's single truth. */
type Reading = "idle" | "pass" | "fail" | "unknown" | "skip";
function reading(g: GateState): Reading {
  if (g.status === "idle") return "idle";
  const v = (g.verdict ?? "").toLowerCase();
  if (v === "lolos") return "pass";
  if (v === "gagal") return "fail";
  if (v === "tidak berlaku" || g.status === "skip") return "skip";
  if (v === "tidak dapat dinilai") return "unknown";
  return g.status === "ok" ? "pass" : "fail";
}
const READING_INK: Record<Reading, string> = {
  idle: "text-ink-faint", pass: "text-done", fail: "text-warn-ink", unknown: "text-warn-ink", skip: "text-ink-soft",
};
const READING_WORD: Record<Reading, string> = {
  idle: "belum dinilai", pass: "lolos", fail: "gagal", unknown: "tidak dapat dinilai", skip: "tidak berlaku",
};
/** Short gate names for the instrument strip; the full name is in the title and for screen readers. */
const GATE_SHORT = ["Bisnis", "Data", "Kepemilikan", "Siklus", "Siklus hidup", "Kewajaran"];

/**
 * The six Method Gates as a fixed strip of instruments, pinned above the
 * scrolling plan and chain so every gate stays in view for the whole run.
 */
export function GateBoard({ state }: { state: DeckState }) {
  const settled = state.gates.filter((g) => g.status !== "idle").length;
  return (
    <section aria-labelledby="gates-title" className="border-b border-rule px-5 pt-3 pb-3.5 max-sm:px-4">
      <RegionHead id="gates-title" title="Method Gates" reading={`${settled}/${GATES.length} dinilai`} />
      <ol className="m-0 mt-2.5 grid list-none grid-cols-6 gap-px overflow-hidden rounded-md border border-rule bg-rule p-0 max-sm:grid-cols-3">
        {state.gates.map((g) => <Gate key={g.n} g={g} />)}
      </ol>
    </section>
  );
}

function Gate({ g }: { g: GateState }) {
  const r = reading(g);
  const changed = useChangeCount(r);
  const tone = r === "pass" || r === "skip" ? "ok" : r === "idle" ? "idle" : "warn";
  const word = r === "idle" || !g.verdict ? READING_WORD[r] : g.verdict;
  return (
    <li className="relative isolate min-w-0 bg-surface px-1.5 pt-2 pb-2" title={`Gate ${g.n}, ${g.name}: ${word}${g.detail ? `. ${g.detail}` : ""}`}>
      <Hold n={changed} tone={tone} />
      <div aria-hidden className="flex items-start justify-center gap-1">
        <span className="data -ml-0.5 text-[10.5px] leading-none text-ink-soft">G{g.n}</span>
        <Dial r={r} />
      </div>
      <p aria-hidden className={`mt-1 truncate text-center text-[11.5px] leading-4 font-bold tracking-[-.005em] ${r === "idle" ? "text-ink-soft" : "text-ink-strong"}`}>{GATE_SHORT[g.n] ?? g.name}</p>
      <p aria-hidden className={`line-clamp-2 min-h-8 text-center text-[11.5px] leading-4 font-medium ${READING_INK[r]}`}>{word}</p>
      <span className="sr-only">Method Gate {g.n}, {g.name}: {word}</span>
    </li>
  );
}

/*
 * The dial: a half scale of four segments, left to right gagal, tidak dapat
 * dinilai, tidak berlaku, lolos. The needle rests flat on the left until the
 * gate is judged, then settles on the centre of its verdict's segment on an
 * overdamped spring (no bounce), and that segment takes the verdict's colour.
 */
const CX = 32;
const CY = 30;
const R = 24;
const SEGMENTS: { r: Exclude<Reading, "idle">; from: number; to: number; stroke: string; dash?: string }[] = [
  { r: "fail", from: -90, to: -45, stroke: "var(--color-warn-rule)" },
  { r: "unknown", from: -45, to: 0, stroke: "var(--color-warn-rule)", dash: "2.2 2" },
  { r: "skip", from: 0, to: 45, stroke: "var(--color-ink-faint)" },
  { r: "pass", from: 45, to: 90, stroke: "var(--color-teal)" },
];
const ANGLE: Record<Reading, number> = { idle: -90, fail: -67.5, unknown: -22.5, skip: 22.5, pass: 67.5 };
const NEEDLE_INK: Record<Reading, string> = {
  idle: "var(--color-rule-strong)", fail: "var(--color-warn-ink)", unknown: "var(--color-warn-ink)",
  skip: "var(--color-ink-soft)", pass: "var(--color-done)",
};

function point(deg: number, radius = R): string {
  const a = (deg * Math.PI) / 180;
  return `${(CX + radius * Math.sin(a)).toFixed(2)} ${(CY - radius * Math.cos(a)).toFixed(2)}`;
}
const arc = (from: number, to: number) => `M${point(from + 3)} A${R} ${R} 0 0 1 ${point(to - 3)}`;

function Dial({ r }: { r: Reading }) {
  const reduce = useReducedMotion();
  const needle = useRef<SVGGElement>(null);
  // Mounts at its reading (a finished run opens settled); later changes settle on the spring.
  const angle = useSpring(ANGLE[r], GATE_SETTLE);
  const turn = (a: number) => needle.current?.setAttribute("transform", `rotate(${a.toFixed(2)} ${CX} ${CY})`);
  useLayoutEffect(() => { turn(angle.get()); });
  useMotionValueEvent(angle, "change", turn);
  useEffect(() => {
    if (reduce) angle.jump(ANGLE[r]);
    else angle.set(ANGLE[r]);
  }, [r, reduce, angle]);
  return (
    <svg viewBox="0 0 64 34" aria-hidden className="block h-[26px] w-[49px] flex-none overflow-visible">
      {SEGMENTS.map((s) => {
        const lit = s.r === r;
        return (
          <path key={s.r} d={arc(s.from, s.to)} fill="none" strokeLinecap="round" strokeDasharray={lit ? undefined : s.dash}
            strokeWidth={lit ? 4 : 2.5} style={{ stroke: lit ? s.stroke : "var(--color-rule)", transition: "stroke .5s var(--ease-out-expo), stroke-width .5s var(--ease-out-expo)" }} />
        );
      })}
      <g ref={needle}>
        <line x1={CX} y1={CY} x2={CX} y2={CY - R + 6} strokeWidth="2" strokeLinecap="round"
          style={{ stroke: NEEDLE_INK[r], transition: "stroke .5s var(--ease-out-expo)" }} />
      </g>
      <circle cx={CX} cy={CY} r="2.6" style={{ fill: NEEDLE_INK[r], transition: "fill .5s var(--ease-out-expo)" }} />
    </svg>
  );
}

export function ChainTable({ state }: { state: DeckState }) {
  const chain = state.chain;
  return (
    <section aria-labelledby="chain-title" className={REGION}>
      <RegionHead id="chain-title" title="Rantai metode" reading={chain.length ? `${chain.length} metode` : undefined} />
      {chain.length === 0 ? (
        <Empty>Rantai metode muncul setelah keenam gerbang selesai menilai emiten: gerbang menentukan urutan metode sebelum nilai dihitung.</Empty>
      ) : (
        <table className="mt-2 w-full border-collapse text-[13.5px]">
          <thead>
            <tr className="border-b border-rule text-left text-[12px] text-ink-soft">
              <th scope="col" className="py-1.5 pr-3 font-medium">Metode</th>
              <th scope="col" className="py-1.5 pr-3 font-medium">Keputusan</th>
              <th scope="col" className="py-1.5 text-right font-medium">Nilai per saham</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {chain.map((c) => {
                const picked = c.decision === "Terpilih";
                const skipped = c.value === "-" || /tidak/i.test(c.decision);
                return (
                  <motion.tr key={`${c.order}-${c.method}`} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={SPRING_SOFT}
                    title={c.reason} className={`border-b border-rule-soft last:border-0 ${picked ? "bg-brand-50" : ""}`}>
                    <td className={`py-2 pr-3 pl-2 align-top font-mono text-[13px] font-semibold ${picked ? "text-brand-ink" : skipped ? "text-ink-soft" : "text-ink-strong"}`}>
                      {c.method}
                    </td>
                    <td className={`py-2 pr-3 align-top ${picked ? "font-bold text-brand-ink" : skipped ? "text-ink-soft" : "text-ink"}`}>{c.decision}</td>
                    <td className={`py-2 pr-2 text-right align-top font-mono tabular-nums ${picked ? "font-bold text-brand-ink" : skipped ? "text-ink-soft" : "text-ink"}`}>{c.value}</td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
      )}
    </section>
  );
}

export type ResultData = {
  rating: string;
  tone: "above" | "below" | "equal" | "review";
  tp: string;
  upside: string;
  price?: string;
  method?: string;
  release?: string;
};

const RATING_INK = { above: "text-ink-strong", below: "text-ink-strong", equal: "text-ink-strong", review: "text-warn-ink" };

/** The informational model scenario, per-share value and dated close. */
export function ResultBlock({ result, actions }: { result?: ResultData; actions?: ReactNode }) {
  if (!result && !actions) return null;
  const cells: [string, ReactNode][] = result ? [
    ["Skenario model", <span className={RATING_INK[result.tone]}>{result.rating}</span>],
    ["Nilai model", result.tp],
    ["Selisih dari harga", result.upside],
    ...(result.price ? [["Harga", result.price] as [string, ReactNode]] : []),
  ] : [];
  return (
    <motion.section aria-labelledby="result-title" className={`${REGION} @container`}
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={SPRING_SOFT}>
      <RegionHead id="result-title" title="Hasil run" />
      {result && (
        <>
          <dl className={`mt-3 grid border-y border-rule ${cells.length === 4 ? "grid-cols-2 @md:grid-cols-4" : "grid-cols-3"}`}>
            {cells.map(([label, value]) => (
              <div key={label} className={`min-w-0 border-rule px-2.5 py-2 not-first:border-l ${
                cells.length === 4 ? "@max-md:[&:nth-child(3)]:border-l-0 @max-md:[&:nth-child(n+3)]:border-t" : ""}`}>
                <dt className="text-[12px] text-ink-soft">{label}</dt>
                <dd className="truncate font-mono text-[15px] font-semibold text-ink-strong tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <dl className="mt-2.5 grid gap-1 text-[13px] leading-snug">
            {result.release && (
              <div className="flex gap-2"><dt className="w-[76px] flex-none text-ink-soft">Status rilis</dt><dd className="min-w-0 text-ink">{result.release}</dd></div>
            )}
            {result.method && (
              <div className="flex gap-2"><dt className="w-[76px] flex-none text-ink-soft">Metode</dt><dd className="min-w-0 text-ink">{result.method}</dd></div>
            )}
          </dl>
          <p className="mt-2 text-[12.5px] text-ink-soft">Informasi dan analisis, bukan rekomendasi investasi.</p>
        </>
      )}
      {actions && <div className="mt-3.5 flex flex-wrap gap-2">{actions}</div>}
    </motion.section>
  );
}

function Lines({ n }: { n: number }) {
  return (
    <div aria-hidden className="mt-3 grid gap-2">
      {Array.from({ length: n }, (_, i) => <span key={i} className="h-3 animate-pulse rounded bg-raised" style={{ width: `${92 - i * 18}%` }} />)}
    </div>
  );
}
