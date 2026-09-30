// The run header: the ticker, the company, the run state with its pulse, the
// run clock, the counters, and (for replays) the transport controls.
import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { DeckState, Status } from "../../lib/agents";
import { useLang, type Bi } from "../../lib/i18n";
import { LiveMark } from "../Mark";
import { STATUS_INK } from "./read";
import { IssuerLogo } from "../IssuerLogo";

export type RunPhase = "pending" | "running" | "completed" | "error" | "paused";

const STATE_WORD: Record<RunPhase, Bi> = {
  pending: { id: "Antri", en: "Queued" },
  running: { id: "Jalan", en: "Running" },
  completed: { id: "Selesai", en: "Done" },
  error: { id: "Gagal", en: "Failed" },
  paused: { id: "Jeda", en: "Paused" },
};
const STATE_STATUS: Record<RunPhase, Status> = { pending: "idle", running: "run", completed: "ok", error: "error", paused: "idle" };
const STATE_CHIP: Record<RunPhase, string> = {
  pending: "border-rule bg-raised",
  running: "border-brand-ink/40 bg-brand-50",
  completed: "border-done/40 bg-ok-bg",
  error: "border-err-ink/40 bg-err-bg",
  paused: "border-rule-strong bg-raised",
};

type Props = {
  ticker: string;
  name?: string | null;
  phase: RunPhase;
  /** Rendered run clock (live or tweened). */
  clock: ReactNode;
  clockNote?: string;
  counts: DeckState["counts"];
  /** Extra state marks next to the chip (e.g. "Parsial"). */
  badges?: ReactNode;
  /** The primary action once the run is done. */
  action?: ReactNode;
  /** Replay transport, under the header row. */
  controls?: ReactNode;
  loading?: boolean;
};

export function RunHeader({ ticker, name, phase, clock, clockNote, counts, badges, action, controls, loading }: Props) {
  const { t } = useLang();
  const status = STATE_STATUS[phase];
  return (
    <header className="border-b border-rule">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4 max-sm:px-4 max-sm:py-3">
        <div className="flex min-w-[min(100%,300px)] flex-1 basis-[300px] items-center gap-4 max-sm:gap-3">
          {ticker && <IssuerLogo ticker={ticker} size="md" className="max-sm:hidden" />}
          <h1 className="font-mono text-[34px] leading-none font-semibold tracking-[-.01em] text-ink-strong max-sm:text-[26px]">
            {ticker || <span className="text-ink-faint">----</span>}
          </h1>
          <div className="min-w-0 flex-1">
            {loading ? <span className="block h-3.5 w-56 max-w-full animate-pulse rounded bg-raised" />
              : <p className="truncate text-[15px] leading-tight font-medium text-ink max-sm:text-[13.5px]">{name ?? t({ id: "Emiten BEI", en: "IDX issuer" })}</p>}
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <span className={`inline-flex h-6 items-center gap-1.5 rounded-[5px] border px-2 font-mono text-[12px] font-semibold tracking-[.08em] uppercase ${STATE_CHIP[phase]} ${STATUS_INK[status]}`}>
                <LiveMark status={phase === "paused" ? "idle" : status} className="h-2.5 w-3" />
                {t(STATE_WORD[phase])}
              </span>
              {badges}
            </div>
          </div>
        </div>
        <dl className="flex items-stretch divide-x divide-rule-soft max-sm:w-full max-sm:justify-between max-sm:divide-x-0">
          <Reading label={t({ id: "Waktu run", en: "Run time" })} note={clockNote} wide>{clock}</Reading>
          <Reading label={t({ id: "Tool call", en: "Tool calls" })}>{counts.calls}</Reading>
          <Reading label={t({ id: "Langkah LLM", en: "LLM steps" })}>{counts.llmSteps}</Reading>
          <Reading label={t({ id: "Catatan", en: "Notes" })} warn={counts.warnings > 0}>{counts.warnings}</Reading>
        </dl>
        <AnimatePresence initial={false}>
          {action && (
            <motion.div key="action" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
              transition={{ type: "spring", stiffness: 380, damping: 34 }} className="flex flex-none gap-2 max-sm:w-full max-sm:[&>*]:flex-1">
              {action}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      {controls && <div className="border-t border-rule-soft px-5 py-2.5 max-sm:px-4">{controls}</div>}
    </header>
  );
}

function Reading({ label, note, wide, warn, children }: { label: string; note?: string; wide?: boolean; warn?: boolean; children: ReactNode }) {
  return (
    <div className={`px-4 first:pl-0 last:pr-0 max-sm:px-0 ${wide ? "min-w-[104px]" : ""}`}>
      <dt className="text-[12px] leading-tight whitespace-nowrap text-ink-soft" title={note}>
        {label}{note && <span className="sr-only">, {note}</span>}
      </dt>
      <dd className={`mt-1 font-mono text-[17px] leading-none font-semibold tabular-nums ${warn ? "text-warn-ink" : "text-ink-strong"}`}>
        {note && <span aria-hidden className="mr-0.5 text-ink-soft">≈</span>}{children}
      </dd>
    </div>
  );
}
