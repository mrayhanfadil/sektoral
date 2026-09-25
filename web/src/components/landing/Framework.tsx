// The six Method Gates as fixed instruments, and the method chain they fix.
// When the featured run is loaded, each instrument also shows that run's
// verdict and the chain shows its real decisions and reasons.
import { GATES, type ChainState, type GateState } from "../../lib/agents";
import type { ReportItem } from "../../lib/api";
import { GATE_TONE, GateMeter } from "./GateMeter";

/** What each gate decides (PRODUCT.md, CONTEXT.md). */
const DECIDES: Record<number, string> = {
  0: "Memilih keluarga metode: bank ke DDM atau P/BV, tambang ke NAV, holding ke SOTP.",
  1: "Memeriksa riwayat laporan, laba usaha, leverage, dan ekuitas.",
  2: "Kepemilikan minoritas 15–40% mewajibkan silang cek SOTP.",
  3: "Menandai emiten komoditas atau aset yang baru ramp-up.",
  4: "Membaca tahap usaha: tumbuh, matang, atau turnaround.",
  5: "Potensi di atas +100% atau di bawah −50% menjadi Review Required.",
};

export function GateInstruments({ gates, ticker }: { gates?: GateState[]; ticker?: string }) {
  const read = gates && gates.some((g) => g.status !== "idle") ? gates : undefined;
  return (
    <div>
      <ol aria-label="Method Gates 0 sampai 5"
        className="m-0 grid list-none grid-cols-2 gap-px overflow-hidden rounded-lg border border-rule bg-rule p-0 md:grid-cols-3 xl:grid-cols-6">
        {GATES.map((gate) => {
          const g = read?.find((x) => x.n === gate.n);
          return (
            <li key={gate.n} className="flex flex-col bg-surface px-5 pt-5 pb-5 max-sm:px-4">
              <span aria-hidden className="font-mono text-[40px] leading-none font-medium tracking-[-.02em] text-brand-ink tabular-nums">{gate.n}</span>
              <h3 className="mt-5 text-[16px] leading-snug">
                <span className="sr-only">Method Gate {gate.n}: </span>{gate.name}
              </h3>
              <p className="m-0 mt-1.5 text-[14px] leading-snug text-ink-soft">{DECIDES[gate.n]}</p>
              {g && ticker && (
                <div className="mt-auto pt-5">
                  <GateMeter status={g.status} className="h-[3px]" />
                  <p className="m-0 mt-2 flex items-baseline justify-between gap-2 text-[12.5px] font-medium">
                    <span className="font-mono text-[11.5px] text-ink-soft">{ticker}</span>
                    <span className={`truncate ${GATE_TONE[g.status].text}`}>{g.verdict || "belum dinilai"}</span>
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className="m-0 mt-3 text-[13.5px] text-ink-soft">
        {read && ticker ? `Meter di bawah setiap gerbang menunjukkan putusannya pada run ${ticker}. ` : ""}
        Lembaga keuangan hanya dinilai pada gerbang 0 dan 5.
      </p>
    </div>
  );
}

const DECISION_TONE: Record<string, string> = {
  Terpilih: "bg-brand text-white",
  "Silang cek": "bg-ok-bg text-ok-ink",
};

type ChainRow = { method: string; decision: string; value: string; reason?: string };

export function MethodChain({ item, chain }: { item?: ReportItem; chain?: ChainState[] }) {
  const rows: ChainRow[] = chain?.length ? chain : (item?.chain ?? []).map((s) => ({ method: s.step, decision: s.decision, value: s.value }));
  return (
    <div className="grid gap-x-12 gap-y-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div>
        <h3 className="text-[20px]">Rantai metode</h3>
        <p className="m-0 mt-2 text-[15px] text-ink-soft">Urutan metode ditetapkan dari putusan gerbang sebelum nilai apa pun dihitung.</p>
        <ol className="m-0 mt-5 list-none p-0 text-[15px]">
          {[
            ["Metode utama", "dari gerbang, misalnya DCF atau DDM."],
            ["Fallback", "hanya bila metode sebelumnya tidak memadai, bukan karena hasilnya tidak disukai."],
            ["Silang cek", "wajib: PER peer, P/S, atau SOTP, dengan alasan tercatat. Hanya metode terpilih yang menetapkan target harga; silang cek tidak pernah dirata-rata."],
            ["Rating ditahan", "bila tidak ada metode yang lolos."],
          ].map(([term, body], i) => (
            <li key={term} className="grid grid-cols-[28px_minmax(0,1fr)] gap-x-3 border-t border-rule py-3.5">
              <span aria-hidden className="font-mono text-[13px] leading-6 font-semibold text-brand-ink">{i + 1}</span>
              <p className="m-0 text-ink-soft"><b className="font-bold text-ink-strong">{term}</b> {body}</p>
            </li>
          ))}
        </ol>
      </div>
      {rows.length > 0 && item && (
        <div className="panel self-start overflow-hidden">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule px-4 py-3.5">
            <h3 className="text-[16px]">Rantai metode <span className="font-mono tracking-[.03em]">{item.ticker}</span></h3>
            <span className="text-[13px] text-ink-soft">Profil {item.profile}</span>
          </div>
          <ol aria-label={`Rantai metode ${item.ticker}`} className="m-0 list-none p-0">
            {rows.map((row, i) => (
              <li key={`${row.method}-${i}`}
                className={`grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 border-t border-rule-soft px-4 py-3 first:border-t-0 ${row.decision === "Terpilih" ? "bg-brand-50/70" : ""}`}>
                <p className="m-0 flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
                  <span className="font-mono text-[14px] font-semibold text-ink-strong">{row.method}</span>
                  <span className={`rounded-full px-2 text-[12px] leading-[20px] font-bold ${DECISION_TONE[row.decision] ?? "bg-raised text-ink-soft"}`}>{row.decision}</span>
                </p>
                <span className={`self-center font-mono text-[14px] tabular-nums ${row.value === "-" ? "text-ink-faint" : "font-semibold text-ink-strong"}`}>
                  {row.value === "-" ? "tanpa nilai" : row.value}
                </span>
                {row.reason && <p className="col-span-2 m-0 line-clamp-2 text-[13px] leading-snug text-ink-soft">{row.reason}</p>}
              </li>
            ))}
          </ol>
          {item.method && (
            <p className="m-0 border-t border-rule bg-raised px-4 py-3 text-[13px] leading-snug text-ink-soft">
              Metode di laporan: <span className="text-ink">{item.method}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
