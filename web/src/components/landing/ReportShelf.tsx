// The stored company updates as one ruled table in the deck's voice: ticker
// in mono, model scenario, value difference, selected method, and two ways in
// (replay the run, or open the report).
import { Link } from "react-router-dom";
import { FileText, Play } from "lucide-react";
import { reportFiles, type ReportItem } from "../../lib/api";
import { pct, rp } from "../../lib/format";
import { RatingBadge } from "../Reports";

const signed = (v: number | null) => (typeof v === "number" && v > 0 ? "+" : "") + pct(v);
const upTone = (_v: number | null) => "text-ink-strong";

function selected(item: ReportItem) {
  return item.chain.find((s) => s.decision === "Terpilih")?.step ?? (item.published ? item.method : "");
}

function Actions({ item }: { item: ReportItem }) {
  const files = reportFiles(item.ticker);
  const href = item.files.html ? files.html : item.files.pdf ? files.pdf : undefined;
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5 max-md:justify-start">
      <Link to={`/laporan/${item.ticker}/putar`} className="btn btn-ghost btn-sm gap-1.5 px-2.5"
        aria-label={`Putar ulang run ${item.ticker}`}>
        <Play aria-hidden className="size-3.5" strokeWidth={2.2} />Putar ulang
      </Link>
      {href && (
        <a href={href} className="btn btn-ghost btn-sm gap-1.5 px-2.5" aria-label={`Buka laporan ${item.ticker}`}>
          <FileText aria-hidden className="size-3.5" strokeWidth={2.2} />Buka laporan
        </a>
      )}
    </div>
  );
}

export function ReportShelf({ items }: { items: ReportItem[] }) {
  const th = "px-4 py-3 text-[13px] font-bold text-ink-soft";
  return (
    <div className="panel overflow-hidden">
      <table className="w-full border-collapse text-[14.5px] max-md:hidden">
        <caption className="sr-only">Company update tersimpan</caption>
        <thead className="border-b border-rule bg-raised text-left">
          <tr>
            <th scope="col" className={th}>Emiten</th>
            <th scope="col" className={`${th} max-xl:hidden`}>Profil</th>
            <th scope="col" className={th}>Skenario nilai</th>
            <th scope="col" className={`${th} text-right`}>Nilai model</th>
            <th scope="col" className={`${th} text-right`}>Selisih dari harga</th>
            <th scope="col" className={th}>Metode terpilih</th>
            <th scope="col" className={`${th} text-right`}><span className="sr-only">Aksi</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.ticker} className="border-t border-rule-soft transition-colors first:border-t-0 hover:bg-raised">
              <th scope="row" className="px-4 py-3 text-left font-normal">
                <span className="block font-mono text-[14.5px] font-semibold tracking-[.04em] text-ink-strong">{item.ticker}</span>
                <span className="block max-w-[26ch] truncate text-[13px] text-ink-soft">{item.name}</span>
              </th>
              <td className="px-4 py-3 text-ink-soft max-xl:hidden">{item.profile}</td>
              <td className="px-4 py-3"><RatingBadge item={item} /></td>
              <td className="px-4 py-3 text-right font-mono font-semibold whitespace-nowrap text-ink-strong tabular-nums">
                {item.published ? `Rp${rp(item.tp)}` : <span className="font-sans font-normal text-ink-faint">ditahan</span>}
              </td>
              <td className={`px-4 py-3 text-right font-mono whitespace-nowrap tabular-nums ${upTone(item.upside)}`}>
                {item.published ? signed(item.upside) : "-"}
              </td>
              <td className="px-4 py-3">
                {item.published
                  ? <span className="font-mono text-[13.5px] text-ink" title={item.method}>{selected(item)}</span>
                  : <span className="text-[13.5px] text-warn-ink">Ditahan: bukti belum lengkap</span>}
              </td>
              <td className="px-4 py-3"><Actions item={item} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul aria-label="Company update tersimpan" className="m-0 list-none p-0 md:hidden">
        {items.map((item) => (
          <li key={item.ticker} className="border-t border-rule-soft px-4 py-3.5 first:border-t-0">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="m-0 font-mono text-[15px] font-semibold tracking-[.04em] text-ink-strong">{item.ticker}</p>
                <p className="m-0 truncate text-[13px] text-ink-soft">{item.name}</p>
              </div>
              <RatingBadge item={item} />
            </div>
            <dl className="m-0 mt-2.5 grid grid-cols-[auto_auto_minmax(0,1fr)] gap-x-5 text-[13px]">
              <div>
                <dt className="text-ink-soft">Nilai model</dt>
                <dd className="m-0 font-mono font-semibold text-ink-strong tabular-nums">{item.published ? `Rp${rp(item.tp)}` : "ditahan"}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Selisih dari harga</dt>
                <dd className={`m-0 font-mono tabular-nums ${upTone(item.upside)}`}>{item.published ? signed(item.upside) : "-"}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-ink-soft">Metode</dt>
                <dd className="m-0 truncate font-mono text-ink">{item.published ? selected(item) : "ditahan"}</dd>
              </div>
            </dl>
            <div className="mt-3"><Actions item={item} /></div>
          </li>
        ))}
      </ul>
    </div>
  );
}
