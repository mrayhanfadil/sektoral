// The five pipeline phases as one segmented track. The current phase carries a
// moving sweep, finished phases are solid, phases with notes are amber.
import type { DeckState, Status } from "../../lib/agents";

const FILL: Record<Status, string> = {
  idle: "scale-x-0", run: "scale-x-0", ok: "scale-x-100 bg-done", warn: "scale-x-100 bg-warn-rule", error: "scale-x-100 bg-err-ink",
};
const TITLE_INK: Record<Status, string> = {
  idle: "text-ink-soft", run: "text-brand-ink", ok: "text-ink-strong", warn: "text-ink-strong", error: "text-err-ink",
};
const WORD: Record<Status, string> = { idle: "belum mulai", run: "berjalan", ok: "selesai", warn: "selesai dengan catatan", error: "gagal" };

export function PhaseBar({ state }: { state: DeckState }) {
  const current = state.phases.findIndex((p) => p.status === "run");
  const at = current >= 0 ? current : Math.max(0, state.phaseAt);
  const phase = state.phases[at];
  return (
    <div className="px-4 py-3 max-sm:px-3">
      <ol aria-label="Fase riset" className="m-0 grid list-none grid-cols-5 gap-2 p-0 max-sm:hidden">
        {state.phases.map((p, i) => (
          <li key={p.id} aria-current={p.status === "run" ? "step" : undefined} className="min-w-0">
            <Track status={p.status} />
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="data text-ink-faint">{i + 1}</span>
              <span className={`truncate text-[13.5px] leading-tight font-bold transition-colors duration-300 ${TITLE_INK[p.status]}`}>{p.title}</span>
              <span className="sr-only">, {WORD[p.status]}</span>
            </div>
            <p className="mt-0.5 truncate pl-[15px] text-[12.5px] leading-snug text-ink-soft max-lg:hidden">{p.sub}</p>
          </li>
        ))}
      </ol>
      {/* Phones: the current phase in words, the rest as dots. */}
      <div className="sm:hidden">
        <div className="flex items-center gap-3">
          <p className="min-w-0 flex-1 truncate text-[13.5px] font-bold text-ink-strong">
            <span className="data mr-1.5 text-ink-faint">Fase {at + 1}/5</span>
            {phase.title}
            <span className="sr-only">, {WORD[phase.status]}</span>
          </p>
          <ol aria-hidden className="m-0 flex list-none items-center gap-1 p-0">
            {state.phases.map((p, i) => (
              <li key={p.id} className={`relative h-1.5 overflow-hidden rounded-full transition-all duration-300 ${i === at ? "w-6" : "w-1.5"} ${
                p.status === "run" ? "bg-brand-100" : p.status === "ok" ? "bg-done" : p.status === "warn" ? "bg-warn-rule" : p.status === "error" ? "bg-err-ink" : "bg-rule"}`}>
                {p.status === "run" && <span className="absolute inset-y-0 left-0 w-1/2 animate-sweep bg-brand" />}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

function Track({ status, className = "" }: { status: Status; className?: string }) {
  return (
    <span aria-hidden className={`relative block h-1 overflow-hidden rounded-full ${status === "run" ? "bg-brand-100" : "bg-rule-soft"} ${className}`}>
      <span className={`absolute inset-0 origin-left transition-transform duration-[420ms] ease-[var(--ease-out-expo)] ${FILL[status]}`} />
      {status === "run" && <span className="absolute inset-y-0 left-0 w-2/5 animate-sweep rounded-full bg-brand" />}
    </span>
  );
}
