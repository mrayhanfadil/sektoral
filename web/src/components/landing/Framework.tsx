// The six Method Gates as fixed instruments, and the method chain they fix.
// When the featured run is loaded, each instrument also shows that run's
// verdict and the chain shows its real decisions and reasons.
import { GATES, type ChainState, type GateState } from "../../lib/agents";
import type { ReportItem } from "../../lib/api";
import { useLang, type Bi } from "../../lib/i18n";
import { words } from "../deck/read";
import { GATE_TONE, GateMeter } from "./GateMeter";

/** What each gate decides (PRODUCT.md, CONTEXT.md). */
const DECIDES: Record<number, Bi> = {
  0: { id: "Memilih keluarga metode: bank ke DDM atau P/BV, tambang ke NAV, holding ke SOTP.",
    en: "Picks the method family: banks to DDM or P/BV, miners to NAV, holding companies to SOTP." },
  1: { id: "Memeriksa riwayat laporan, laba usaha, leverage, dan ekuitas.", en: "Checks the reporting history, operating profit, leverage, and equity." },
  2: { id: "Kepemilikan minoritas 15–40% mewajibkan silang cek SOTP.", en: "A 15–40% minority holding requires a SOTP cross-check." },
  3: { id: "Menandai emiten komoditas atau aset yang baru ramp-up.", en: "Flags commodity issuers or assets still ramping up." },
  4: { id: "Membaca tahap usaha: tumbuh, matang, atau turnaround.", en: "Reads the business stage: growth, mature, or turnaround." },
  5: { id: "Potensi di atas +100% atau di bawah −50% menjadi Review Required.", en: "Upside above +100% or below −50% becomes Review Required." },
};

export function GateInstruments({ gates, ticker }: { gates?: GateState[]; ticker?: string }) {
  const { lang, t } = useLang();
  const read = gates && gates.some((g) => g.status !== "idle") ? gates : undefined;
  return (
    <div>
      <ol aria-label={t({ id: "Method Gates 0 sampai 5", en: "Method Gates 0 to 5" })}
        className="m-0 grid list-none grid-cols-2 gap-px overflow-hidden rounded-lg border border-rule bg-rule p-0 md:grid-cols-3 xl:grid-cols-6">
        {GATES.map((gate) => {
          const g = read?.find((x) => x.n === gate.n);
          return (
            <li key={gate.n} className="flex flex-col bg-surface px-5 pt-5 pb-5 max-sm:px-4">
              <span aria-hidden className="font-mono text-[40px] leading-none font-medium tracking-[-.02em] text-brand-ink tabular-nums">{gate.n}</span>
              <h3 className="mt-5 text-[16px] leading-snug">
                <span className="sr-only">Method Gate {gate.n}: </span>{t(gate.name)}
              </h3>
              <p className="m-0 mt-1.5 text-[14px] leading-snug text-ink-soft">{t(DECIDES[gate.n])}</p>
              {g && ticker && (
                <div className="mt-auto pt-5">
                  <GateMeter status={g.status} className="h-[3px]" />
                  <p className="m-0 mt-2 flex items-baseline justify-between gap-2 text-[12.5px] font-medium">
                    <span className="font-mono text-[11.5px] text-ink-soft">{ticker}</span>
                    <span className={`truncate ${GATE_TONE[g.status].text}`}>{words(g.verdict, lang) || t({ id: "belum dinilai", en: "not assessed yet" })}</span>
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className="m-0 mt-3 text-[13.5px] text-ink-soft">
        {read && ticker
          ? t({ id: `Meter di bawah setiap gerbang menunjukkan putusannya pada run ${ticker}. `, en: `The meter under each gate shows its verdict on the ${ticker} run. ` })
          : ""}
        {t({ id: "Lembaga keuangan hanya dinilai pada gerbang 0 dan 5.", en: "Financial institutions are assessed on gates 0 and 5 only." })}
      </p>
    </div>
  );
}

const DECISION_TONE: Record<string, string> = {
  Terpilih: "bg-brand text-white",
  "Silang cek": "bg-ok-bg text-ok-ink",
};

type ChainRow = { method: string; decision: string; value: string; reason?: string };

/** The numbered rules of the chain, in order. */
const RULES: [term: Bi, body: Bi][] = [
  [{ id: "Metode utama", en: "Primary method" }, { id: "dari gerbang, misalnya DCF atau DDM.", en: "from the gates, for example DCF or DDM." }],
  [{ id: "Fallback", en: "Fallback" },
    { id: "hanya bila metode sebelumnya tidak memadai, bukan karena hasilnya tidak disukai.", en: "only when the method before it is insufficient, never because its result is disliked." }],
  [{ id: "Silang cek", en: "Cross-check" },
    { id: "wajib: PER peer, P/S, atau SOTP, dengan alasan tercatat. Hanya metode terpilih yang menetapkan target harga; silang cek tidak pernah dirata-rata.",
      en: "required: peer PER, P/S, or SOTP, with the reason logged. Only the selected method sets the target price; cross-checks are never averaged in." }],
  [{ id: "Rating ditahan", en: "Rating held" }, { id: "bila tidak ada metode yang lolos.", en: "when no method passes." }],
];

export function MethodChain({ item, chain }: { item?: ReportItem; chain?: ChainState[] }) {
  const { lang, t } = useLang();
  const rows: ChainRow[] = chain?.length ? chain : (item?.chain ?? []).map((s) => ({ method: s.step, decision: s.decision, value: s.value }));
  return (
    <div className="grid gap-x-12 gap-y-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div>
        <h3 className="text-[20px]">{t({ id: "Rantai metode", en: "Method Chain" })}</h3>
        <p className="m-0 mt-2 text-[15px] text-ink-soft">
          {t({ id: "Urutan metode ditetapkan dari putusan gerbang sebelum nilai apa pun dihitung.", en: "The gates' verdicts fix the method order before any value is computed." })}
        </p>
        <ol className="m-0 mt-5 list-none p-0 text-[15px]">
          {RULES.map(([term, body], i) => (
            <li key={term.id} className="grid grid-cols-[28px_minmax(0,1fr)] gap-x-3 border-t border-rule py-3.5">
              <span aria-hidden className="font-mono text-[13px] leading-6 font-semibold text-brand-ink">{i + 1}</span>
              <p className="m-0 text-ink-soft"><b className="font-bold text-ink-strong">{t(term)}</b> {t(body)}</p>
            </li>
          ))}
        </ol>
      </div>
      {rows.length > 0 && item && (
        <div className="panel self-start overflow-hidden">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule px-4 py-3.5">
            <h3 className="text-[16px]">{t({ id: "Rantai metode", en: "Method Chain" })} <span className="font-mono tracking-[.03em]">{item.ticker}</span></h3>
            <span className="text-[13px] text-ink-soft">{t({ id: "Profil", en: "Profile" })} {item.profile}</span>
          </div>
          <ol aria-label={t({ id: `Rantai metode ${item.ticker}`, en: `Method Chain ${item.ticker}` })} className="m-0 list-none p-0">
            {rows.map((row, i) => (
              <li key={`${row.method}-${i}`}
                className={`grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 border-t border-rule-soft px-4 py-3 first:border-t-0 ${row.decision === "Terpilih" ? "bg-brand-50/70" : ""}`}>
                <p className="m-0 flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
                  <span className="font-mono text-[14px] font-semibold text-ink-strong">{row.method}</span>
                  <span className={`rounded-full px-2 text-[12px] leading-[20px] font-bold ${DECISION_TONE[row.decision] ?? "bg-raised text-ink-soft"}`}>{words(row.decision, lang)}</span>
                </p>
                <span className={`self-center font-mono text-[14px] tabular-nums ${row.value === "-" ? "text-ink-faint" : "font-semibold text-ink-strong"}`}>
                  {row.value === "-" ? t({ id: "tanpa nilai", en: "no value" }) : row.value}
                </span>
                {row.reason && <p className="col-span-2 m-0 line-clamp-2 text-[13px] leading-snug text-ink-soft">{row.reason}</p>}
              </li>
            ))}
          </ol>
          {item.method && (
            <p className="m-0 border-t border-rule bg-raised px-4 py-3 text-[13px] leading-snug text-ink-soft">
              {t({ id: "Metode di laporan:", en: "Method in the report:" })} <span className="text-ink">{item.method}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
