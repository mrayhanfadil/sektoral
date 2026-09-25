// What the evidence checks and the release harness decide: the four checks
// with and without enough evidence, the three release statuses, and the
// Review Required band plotted with the stored reports' real upside.
import { useEffect, useRef, useState, type RefObject } from "react";
import { CircleCheck, CircleMinus, CircleSlash } from "lucide-react";
import type { ReportItem } from "../../lib/api";
import { pct } from "../../lib/format";

const CHECKS = [
  ["Angka kuantitatif", "Pendapatan, margin, valuasi, rasio utang", "Cocok dengan sumber",
    "Setiap angka sama dengan baris dan kolom yang dibaca.", "Ditolak",
    "Angka yang tidak terverifikasi dibuang; bagian tersebut dinyatakan tanpa dukungan data."],
  ["Asumsi agen", "Skenario laba, risiko, katalis", "Tervalidasi", "Sumber, periode, dan besaran lolos pemeriksaan skema.",
    "Ditolak atau diperbaiki", "Asumsi tanpa sumber tidak masuk model; alasannya tercatat."],
  ["Metode valuasi", "Rantai dari gerbang framework", "Metode terpilih lolos", "Nilai, sensitivitas, dan silang cek ditampilkan.",
    "Semua metode gagal", "Tidak ada tebakan; tiap metode diberi alasan."],
  ["Rating & target harga", "Gerbang forecast dan valuasi", "Ditampilkan",
    "Hanya setelah metode yang dipilih lolos seluruh pemeriksaan.", "Ditahan",
    "Laporan terbit sebagai draf parsial dengan banner bukti belum lengkap dan alasan penahanan."],
] as const;

export function EvidenceChecks() {
  return (
    <div className="panel overflow-hidden">
      <table className="w-full border-collapse text-[15px] max-md:block">
        <caption className="sr-only">Hasil pemeriksaan saat bukti lengkap dan saat bukti kurang</caption>
        <thead className="border-b border-rule bg-raised text-left max-md:hidden">
          <tr className="[&>th]:px-5 [&>th]:py-3 [&>th]:text-[13.5px] [&>th]:font-bold [&>th]:text-ink-soft">
            <th scope="col" className="w-[26%]">Pemeriksaan</th>
            <th scope="col"><span className="inline-flex items-center gap-2">Bukti lengkap <span className="pill pill-ok">Terbit</span></span></th>
            <th scope="col"><span className="inline-flex items-center gap-2">Bukti kurang <span className="pill pill-warn">Draft</span></span></th>
          </tr>
        </thead>
        <tbody className="max-md:block">
          {CHECKS.map(([title, sub, okTitle, ok, noTitle, no]) => (
            <tr key={title} className="border-t border-rule-soft first:border-t-0 max-md:block max-md:px-4 max-md:py-4">
              <th scope="row" className="px-5 py-4 text-left align-top font-bold text-ink-strong max-md:block max-md:p-0">
                {title}
                <small className="mt-0.5 block text-[13px] font-normal text-ink-soft">{sub}</small>
              </th>
              <td className="px-5 py-4 align-top text-ink-soft max-md:mt-3 max-md:block max-md:p-0">
                <strong className="mb-0.5 flex items-center gap-1.5 text-ink">
                  <CircleCheck aria-hidden className="size-4 flex-none text-done" strokeWidth={2.2} />
                  <span className="sr-only md:hidden">Bukti lengkap: </span>{okTitle}
                </strong>
                {ok}
              </td>
              <td className="px-5 py-4 align-top text-ink-soft max-md:mt-3 max-md:block max-md:p-0">
                <strong className="mb-0.5 flex items-center gap-1.5 text-ink">
                  <CircleSlash aria-hidden className="size-4 flex-none text-warn-ink" strokeWidth={2.2} />
                  <span className="sr-only md:hidden">Bukti kurang: </span>{noTitle}
                </strong>
                {no}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const RELEASE = [
  { code: "production_ready", title: "Siap produksi",
    body: "Forecast driver yang bersumber dan terekonsiliasi, dinilai dengan metode utama profil.",
    outcome: "Rating dan target harga terbit.", held: false },
  { code: "distributable_assumption_led", title: "Berbasis asumsi",
    body: "Dinilai dengan skenario analis yang tervalidasi atau langkah terakhir rantai metode, dengan setiap asumsi diberi label. Forecast belum siap produksi.",
    outcome: "Rating dan target harga terbit, asumsinya berlabel.", held: false },
  { code: "draft_non_distributable", title: "Draf",
    body: "Tidak untuk didistribusikan. Setiap blocker yang menahan laporan disebut namanya.",
    outcome: "Rating dan target harga ditahan.", held: true },
];

export function ReleaseStatuses({ current, ticker }: { current?: string; ticker?: string }) {
  return (
    <ol aria-label="Status rilis"
      className="m-0 grid list-none gap-px overflow-hidden rounded-lg border border-rule bg-rule p-0 md:grid-cols-3">
      {RELEASE.map((r) => {
        const here = current === r.code;
        return (
          <li key={r.code} className={`flex flex-col px-5 pt-4 pb-5 ${here ? "bg-brand-50" : "bg-surface"}`}>
            <h4 className="text-[17px]">{r.title}</h4>
            <code className="mt-1 font-mono text-[12px] break-all text-ink-soft">{r.code}</code>
            <p className="m-0 mt-1.5 text-[14px] leading-snug text-ink-soft">{r.body}</p>
            <p className="m-0 mt-auto flex items-center gap-2 pt-4 text-[14px] font-medium text-ink">
              {r.held
                ? <CircleMinus aria-hidden className="size-4 flex-none text-warn-ink" strokeWidth={2.2} />
                : <CircleCheck aria-hidden className="size-4 flex-none text-done" strokeWidth={2.2} />}
              {r.outcome}
            </p>
            {here && ticker && <p className="m-0 mt-2 text-[13px] font-medium text-brand-ink">Run <span className="font-mono">{ticker}</span> berakhir di sini</p>}
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
        <span className="flex items-center gap-2"><span className="size-2 rounded-full bg-brand-ink" />Potensi company update terbit</span>
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
        {points.map((p) => <li key={p.ticker}>{p.ticker}: potensi {signed(p.upside)}</li>)}
      </ul>
      {points.length > 0 && (
        <figcaption className="mt-3 border-t border-rule-soft pt-3 text-[13.5px] text-ink-soft">
          {inside} dari {points.length} company update terbit berada di dalam rentang.
          {nearest && <> Paling dekat ke ambang: <span className="font-mono font-semibold text-ink">{nearest.ticker}</span>, potensi <span className="font-mono text-ink">{signed(nearest.upside)}</span>.</>}
        </figcaption>
      )}
    </figure>
  );
}
