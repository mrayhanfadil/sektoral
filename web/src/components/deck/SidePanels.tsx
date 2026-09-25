// The right column of the Deck: the research plan and its verdicts, the six
// Method Gates as fixed instruments, the method chain, and the result.
import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { GATES, type DeckState, type GateState, type Hypothesis } from "../../lib/agents";
import { Clamp, Hold, RegionHead } from "./kit";
import { EXPO, SPRING, SPRING_SOFT, useChangeCount, verdictStatus, verdictTone } from "./read";

const REGION = "border-b border-rule px-5 py-4 max-sm:px-4";

function Empty({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-[13.5px] leading-snug text-ink-soft">{children}</p>;
}

export function PlanPanel({ state, loading }: { state: DeckState; loading?: boolean }) {
  const { question, hypotheses } = state.plan;
  const judged = hypotheses.filter((h) => h.verdict).length;
  return (
    <section aria-labelledby="plan-title" className={REGION}>
      <RegionHead id="plan-title" title="Rencana riset" reading={hypotheses.length ? `${judged}/${hypotheses.length} diuji` : undefined} />
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
      <Hold n={changed} tone={verdictStatus(h.verdict)} />
      <div className="grid grid-cols-[26px_minmax(0,1fr)] gap-x-2 py-2.5">
        <span className="data pt-[2px] text-ink-soft">H{h.index}</span>
        <div className="min-w-0">
          <p className="line-clamp-3 text-[13.5px] leading-snug text-ink" title={text}>{text}</p>
          <div className="mt-1.5 flex min-h-[22px] flex-wrap items-center gap-2">
            <AnimatePresence mode="popLayout" initial={false}>
              {h.verdict ? (
                <motion.span key={h.verdict} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  transition={SPRING_SOFT} className={`pill ${verdictTone(h.verdict)} px-2 py-0 text-[12.5px]`} title={h.reason}>
                  {h.verdict}
                </motion.span>
              ) : (
                <motion.span key="wait" exit={{ opacity: 0 }} className="data text-ink-faint">menunggu uji</motion.span>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.li>
  );
}

/** Each verdict word keeps one look: the gate's single truth. */
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

export function GateBoard({ state }: { state: DeckState }) {
  const settled = state.gates.filter((g) => g.status !== "idle").length;
  return (
    <section aria-labelledby="gates-title" className={REGION}>
      <RegionHead id="gates-title" title="Method Gates" reading={`${settled}/${GATES.length} dinilai`} />
      <ol className="m-0 mt-3 grid list-none grid-cols-3 gap-px overflow-hidden rounded-md border border-rule bg-rule p-0 max-sm:grid-cols-2">
        {state.gates.map((g) => <Gate key={g.n} g={g} />)}
      </ol>
    </section>
  );
}

function Gate({ g }: { g: GateState }) {
  const r = reading(g);
  const changed = useChangeCount(r);
  const tone = r === "pass" ? "ok" : r === "skip" ? "ok" : r === "idle" ? "idle" : "warn";
  return (
    <li className="relative isolate min-w-0 bg-surface px-3 pt-2.5 pb-3" title={g.detail ? `Gate ${g.n}, ${g.name}: ${g.verdict}. ${g.detail}` : undefined}>
      <Hold n={changed} tone={tone} />
      <div className="flex items-start justify-between gap-2">
        <span className="data text-ink-soft">G{g.n}</span>
        <GateMark r={r} />
      </div>
      <p className={`mt-1 text-[13px] leading-tight font-bold ${r === "idle" ? "text-ink-soft" : "text-ink-strong"}`}>{g.name}</p>
      <p className={`data mt-1 ${READING_INK[r]}`}>{r === "idle" ? "belum dinilai" : g.verdict}</p>
      {g.detail && <p className="mt-1 line-clamp-2 text-[12px] leading-snug text-ink-soft">{g.detail}</p>}
    </li>
  );
}

/** The gate's instrument face: an empty ring until the gate settles, then its verdict drawn in. */
function GateMark({ r }: { r: Reading }) {
  return (
    <svg viewBox="0 0 22 22" aria-hidden className="size-[22px] flex-none">
      <circle cx="11" cy="11" r="9.25" className="fill-none stroke-rule-strong" strokeWidth="1.5" strokeDasharray={r === "idle" ? "2.4 2.6" : undefined} />
      <AnimatePresence initial={false}>
        {r !== "idle" && (
          <motion.g key={r} initial={{ opacity: 0, scale: 0.55 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, transition: { duration: 0.12 } }}
            transition={SPRING_SOFT} style={{ originX: "11px", originY: "11px" }}>
            {r === "pass" && (
              <>
                <circle cx="11" cy="11" r="9.25" className="fill-ok-bg stroke-done" strokeWidth="1.5" />
                <motion.path d="M6.8 11.3l2.8 2.8 5.6-6" className="fill-none stroke-done" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.42, ease: EXPO, delay: 0.08 }} />
              </>
            )}
            {r === "fail" && (
              <>
                <circle cx="11" cy="11" r="9.25" className="fill-warn-bg stroke-warn-rule" strokeWidth="1.5" />
                <motion.path d="M11 6.4v5.4" className="fill-none stroke-warn-ink" strokeWidth="2.2" strokeLinecap="round"
                  initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.36, ease: EXPO, delay: 0.08 }} />
                <circle cx="11" cy="15.2" r="1.25" className="fill-warn-ink" />
              </>
            )}
            {r === "unknown" && (
              <>
                <circle cx="11" cy="11" r="9.25" className="fill-none stroke-warn-rule" strokeWidth="1.5" />
                <circle cx="11" cy="11" r="2" className="fill-warn-rule" />
              </>
            )}
            {r === "skip" && (
              <motion.path d="M7 11h8" className="fill-none stroke-ink-faint" strokeWidth="2" strokeLinecap="round"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.36, ease: EXPO }} />
            )}
          </motion.g>
        )}
      </AnimatePresence>
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
  tone: "buy" | "hold" | "sell" | "review";
  tp: string;
  upside: string;
  price?: string;
  method?: string;
  release?: string;
};

const RATING_INK = { buy: "text-ok-ink", hold: "text-ink-strong", sell: "text-err-ink", review: "text-warn-ink" };

/** The result as a ruled data row: rating, target, upside, price; then the method and actions. */
export function ResultBlock({ result, actions }: { result?: ResultData; actions?: ReactNode }) {
  if (!result && !actions) return null;
  const cells: [string, ReactNode][] = result ? [
    ["Rating", <span className={RATING_INK[result.tone]}>{result.rating}</span>],
    ["Target harga", result.tp],
    ["Upside", result.upside],
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
