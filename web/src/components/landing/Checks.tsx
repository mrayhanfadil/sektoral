// What the evidence checks and the release harness decide: the four checks
// with and without enough evidence, the three release statuses, and the
// Review Required band plotted with the stored reports' real upside.
import { useEffect, useRef, useState, type RefObject } from "react";
import { CircleCheck, CircleMinus, CircleSlash } from "lucide-react";
import type { ReportItem } from "../../lib/api";
import { pct } from "../../lib/format";
import { useLang, type Bi } from "../../lib/i18n";

type Check = [title: Bi, sub: Bi, okTitle: Bi, ok: Bi, noTitle: Bi, no: Bi];

const CHECKS: Check[] = [
  [{ id: "Angka kuantitatif", en: "Quantitative figures" }, { id: "Pendapatan, margin, valuasi, rasio utang", en: "Revenue, margins, valuation, debt ratios" },
    { id: "Cocok dengan sumber", en: "Matches the source" },
    { id: "Setiap angka sama dengan baris dan kolom yang dibaca.", en: "Every figure equals the row and column that was read." },
    { id: "Ditolak", en: "Rejected" },
    { id: "Angka yang tidak terverifikasi dibuang; bagian tersebut dinyatakan tanpa dukungan data.", en: "Unverified figures are dropped; that section is stated as lacking data support." }],
  [{ id: "Asumsi agen", en: "Agent assumptions" }, { id: "Skenario laba, risiko, katalis", en: "Earnings scenarios, risks, catalysts" },
    { id: "Tervalidasi", en: "Validated" }, { id: "Sumber, periode, dan besaran lolos pemeriksaan skema.", en: "Source, period, and magnitude pass the schema check." },
    { id: "Ditolak atau diperbaiki", en: "Rejected or corrected" },
    { id: "Asumsi tanpa sumber tidak masuk model; alasannya tercatat.", en: "Unsourced assumptions stay out of the model; the reason is logged." }],
  [{ id: "Metode valuasi", en: "Valuation method" }, { id: "Rantai dari gerbang framework", en: "Chain set by the framework gates" },
    { id: "Metode terpilih lolos", en: "Selected method passes" }, { id: "Nilai, sensitivitas, dan silang cek ditampilkan.", en: "Value, sensitivity, and cross-checks are shown." },
    { id: "Semua metode gagal", en: "Every method fails" }, { id: "Tidak ada tebakan; tiap metode diberi alasan.", en: "No guessing; each method is given a reason." }],
  [{ id: "Rating & target harga", en: "Rating & target price" }, { id: "Gerbang forecast dan valuasi", en: "Forecast and valuation gates" },
    { id: "Ditampilkan", en: "Shown" },
    { id: "Hanya setelah metode yang dipilih lolos seluruh pemeriksaan.", en: "Only after the selected method passes every check." },
    { id: "Ditahan", en: "Held" },
    { id: "Laporan terbit sebagai draf parsial dengan banner bukti belum lengkap dan alasan penahanan.", en: "The report is published as a partial draft with an incomplete-evidence banner and the reason it was held." }],
];

export function EvidenceChecks() {
  const { t } = useLang();
  return (
    <div className="panel overflow-hidden">
      <table className="w-full border-collapse text-[15px] max-md:block">
        <caption className="sr-only">{t({ id: "Hasil pemeriksaan saat bukti lengkap dan saat bukti kurang", en: "Check results when the evidence is complete and when it falls short" })}</caption>
        <thead className="border-b border-rule bg-raised text-left max-md:hidden">
          <tr className="[&>th]:px-5 [&>th]:py-3 [&>th]:text-[13.5px] [&>th]:font-bold [&>th]:text-ink-soft">
            <th scope="col" className="w-[26%]">{t({ id: "Pemeriksaan", en: "Check" })}</th>
            <th scope="col"><span className="inline-flex items-center gap-2">{t({ id: "Bukti lengkap", en: "Complete evidence" })} <span className="pill pill-ok">{t({ id: "Terbit", en: "Published" })}</span></span></th>
            <th scope="col"><span className="inline-flex items-center gap-2">{t({ id: "Bukti kurang", en: "Insufficient evidence" })} <span className="pill pill-warn">Draft</span></span></th>
          </tr>
        </thead>
        <tbody className="max-md:block">
          {CHECKS.map(([title, sub, okTitle, ok, noTitle, no]) => (
            <tr key={title.id} className="border-t border-rule-soft first:border-t-0 max-md:block max-md:px-4 max-md:py-4">
              <th scope="row" className="px-5 py-4 text-left align-top font-bold text-ink-strong max-md:block max-md:p-0">
                {t(title)}
                <small className="mt-0.5 block text-[13px] font-normal text-ink-soft">{t(sub)}</small>
              </th>
              <td className="px-5 py-4 align-top text-ink-soft max-md:mt-3 max-md:block max-md:p-0">
                <strong className="mb-0.5 flex items-center gap-1.5 text-ink">
                  <CircleCheck aria-hidden className="size-4 flex-none text-done" strokeWidth={2.2} />
                  <span className="sr-only md:hidden">{t({ id: "Bukti lengkap: ", en: "Complete evidence: " })}</span>{t(okTitle)}
                </strong>
                {t(ok)}
              </td>
              <td className="px-5 py-4 align-top text-ink-soft max-md:mt-3 max-md:block max-md:p-0">
                <strong className="mb-0.5 flex items-center gap-1.5 text-ink">
                  <CircleSlash aria-hidden className="size-4 flex-none text-warn-ink" strokeWidth={2.2} />
                  <span className="sr-only md:hidden">{t({ id: "Bukti kurang: ", en: "Insufficient evidence: " })}</span>{t(noTitle)}
                </strong>
                {t(no)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const RELEASE: { code: string; title: Bi; body: Bi; outcome: Bi; held: boolean }[] = [
  { code: "production_ready", title: { id: "Siap produksi", en: "Production-ready" },
    body: { id: "Forecast driver yang bersumber dan terekonsiliasi, dinilai dengan metode utama profil.",
      en: "A sourced, reconciled driver forecast, valued with the profile's primary method." },
    outcome: { id: "Rating dan target harga terbit.", en: "Rating and target price published." }, held: false },
  { code: "distributable_assumption_led", title: { id: "Berbasis asumsi", en: "Assumption-led" },
    body: { id: "Dinilai dengan skenario analis yang tervalidasi atau langkah terakhir rantai metode, dengan setiap asumsi diberi label. Forecast belum siap produksi.",
      en: "Valued with a validated analyst scenario or the method chain's last step, with every assumption labelled. The forecast is not production-ready yet." },
    outcome: { id: "Rating dan target harga terbit, asumsinya berlabel.", en: "Rating and target price published, assumptions labelled." }, held: false },
  { code: "draft_non_distributable", title: { id: "Draf", en: "Draft" },
    body: { id: "Tidak untuk didistribusikan. Setiap blocker yang menahan laporan disebut namanya.",
      en: "Not for distribution. Every blocker holding the report back is named." },
    outcome: { id: "Rating dan target harga ditahan.", en: "Rating and target price held." }, held: true },
];

export function ReleaseStatuses({ current, ticker }: { current?: string; ticker?: string }) {
  const { t } = useLang();
  return (
    <ol aria-label={t({ id: "Status rilis", en: "Release statuses" })}
      className="m-0 grid list-none gap-px overflow-hidden rounded-lg border border-rule bg-rule p-0 md:grid-cols-3">
      {RELEASE.map((r) => {
        const here = current === r.code;
        return (
          <li key={r.code} className={`flex flex-col px-5 pt-4 pb-5 ${here ? "bg-brand-50" : "bg-surface"}`}>
            <h4 className="text-[17px]">{t(r.title)}</h4>
            <code className="mt-1 font-mono text-[12px] break-all text-ink-soft">{r.code}</code>
            <p className="m-0 mt-1.5 text-[14px] leading-snug text-ink-soft">{t(r.body)}</p>
            <p className="m-0 mt-auto flex items-center gap-2 pt-4 text-[14px] font-medium text-ink">
              {r.held
                ? <CircleMinus aria-hidden className="size-4 flex-none text-warn-ink" strokeWidth={2.2} />
                : <CircleCheck aria-hidden className="size-4 flex-none text-done" strokeWidth={2.2} />}
              {t(r.outcome)}
            </p>
            {here && ticker && (
              <p className="m-0 mt-2 text-[13px] font-medium text-brand-ink">
                {t({ id: "Run", en: "The" })} <span className="font-mono">{ticker}</span> {t({ id: "berakhir di sini", en: "run ends here" })}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Domain of the band, in percent upside. */
const LO = -75;
const HI = 125;
const at = (v: number) => `${((Math.min(HI, Math.max(LO, v)) - LO) / (HI - LO)) * 100}%`;
const signed = (v: number) => (v > 0 ? "+" : "") + pct(v);

/**
 * Stack ticker labels into lanes above the axis so no two labels overlap and
 * no label lands on an earlier stem. ``half`` is half a label's width, in
 * percent of the axis. A stem that must pass a lower label runs behind it.
 */
function lanes(xs: number[], half: number) {
  const edge: number[] = []; // rightmost occupied point per lane
  return xs.map((x) => {
    let lane = 0;
    while (lane < edge.length && x - half < edge[lane]) lane++;
    for (let k = 0; k < lane; k++) edge[k] = Math.max(edge[k], x + 0.5);
    edge[lane] = x + half;
    return lane;
  });
}

function useWidth(ref: RefObject<HTMLElement | null>) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return width;
}

export function ReviewBand({ items }: { items: ReportItem[] }) {
  const { t } = useLang();
  const points = items
    .filter((i) => i.published && typeof i.upside === "number")
    .map((i) => ({ ticker: i.ticker, upside: i.upside as number, x: ((i.upside as number) - LO) / (HI - LO) * 100 }))
    .sort((a, b) => a.upside - b.upside);
  const axis = useRef<HTMLDivElement>(null);
  const width = useWidth(axis);
  // A four-letter mono ticker at 11px is about 30px wide; keep 4px either side.
  const lane = lanes(points.map((p) => p.x), width ? (19 / width) * 100 : 3);
  const depth = Math.max(1, ...lane.map((l) => l + 1));
  const inside = points.filter((p) => p.upside <= 100 && p.upside >= -50).length;
  const nearest = points.reduce<(typeof points)[number] | undefined>((best, p) => {
    const d = Math.min(100 - p.upside, p.upside + 50);
    return !best || d < Math.min(100 - best.upside, best.upside + 50) ? p : best;
  }, undefined);
  const top = depth * 18 + 10;

  return (
    <figure className="panel m-0 px-5 pt-4 pb-4 max-sm:px-4">
      <p aria-hidden className="m-0 mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[12.5px] text-ink-soft">
        <span className="flex items-center gap-2"><span className="size-2 rounded-full bg-brand-ink" />{t({ id: "Potensi company update terbit", en: "Upside of published company updates" })}</span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-4 rounded-[2px] bg-warn-bg ring-1 ring-warn-rule/40" />Review Required</span>
      </p>
      <div ref={axis} className="relative" style={{ height: top + 34 }} aria-hidden>
        {/* Review Required zones, outside −50% and +100%. */}
        <span className="absolute h-4 rounded-l-[3px] bg-warn-bg" style={{ top: top - 8, left: 0, width: at(-50) }} />
        <span className="absolute h-4 rounded-r-[3px] bg-warn-bg" style={{ top: top - 8, left: at(100), right: 0 }} />
        <span className="absolute inset-x-0 h-px bg-rule-strong" style={{ top }} />
        {[-50, 0, 50, 100].map((v) => (
          <span key={v} className="absolute -translate-x-1/2" style={{ left: at(v), top: top - 4 }}>
            <span className={`mx-auto block h-2 w-px ${v === -50 || v === 100 ? "bg-warn-rule" : "bg-rule-strong"}`} />
            <span className={`mt-2.5 block font-mono text-[11px] tabular-nums ${v === -50 || v === 100 ? "font-semibold text-warn-ink" : "text-ink-soft"}`}>
              {v > 0 ? `+${v}%` : v < 0 ? `−${-v}%` : "0%"}
            </span>
          </span>
        ))}
        {points.map((p, i) => (
          // Label, stem and dot stack so the dot's centre lands on the axis.
          <span key={p.ticker} className="absolute -translate-x-1/2" style={{ left: `${p.x}%`, top: top - lane[i] * 18 - 21.5, zIndex: 10 - lane[i] }}>
            <span className="block bg-surface px-0.5 font-mono text-[11px] leading-[14px] font-semibold text-ink-strong">{p.ticker}</span>
            <span className="mx-auto block w-px bg-rule-strong" style={{ height: lane[i] * 18 + 4 }} />
            <span className="mx-auto block size-[7px] rounded-full bg-brand-ink ring-2 ring-surface" />
          </span>
        ))}
      </div>
      <ul className="sr-only">
        {points.map((p) => <li key={p.ticker}>{p.ticker}: {t({ id: "potensi", en: "upside" })} {signed(p.upside)}</li>)}
      </ul>
      {points.length > 0 && (
        <figcaption className="mt-3 border-t border-rule-soft pt-3 text-[13.5px] text-ink-soft">
          {t({
            id: `${inside} dari ${points.length} company update terbit berada di dalam rentang.`,
            en: `${inside} of ${points.length} published company ${points.length === 1 ? "update falls" : "updates fall"} inside the range.`,
          })}
          {nearest && <>
            {" "}{t({ id: "Paling dekat ke ambang:", en: "Closest to a threshold:" })} <span className="font-mono font-semibold text-ink">{nearest.ticker}</span>,
            {" "}{t({ id: "potensi", en: "upside" })} <span className="font-mono text-ink">{signed(nearest.upside)}</span>.
          </>}
        </figcaption>
      )}
    </figure>
  );
}
