import { Link } from "react-router-dom";
import { reportFiles, type ReportItem } from "../lib/api";
import { pct, rp } from "../lib/format";
import { ratingLabel, ratingTone, type RatingTone } from "../lib/labels";

const TONE: Record<RatingTone, string> = {
  buy: "bg-ok-bg text-ok-ink",
  hold: "bg-brand-50 text-brand-ink",
  sell: "bg-err-bg text-err-ink",
  review: "bg-warn-bg text-warn-ink",
};

export function RatingBadge({ item }: { item: ReportItem }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full px-3 py-1 text-[13px] font-black ${TONE[ratingTone(item)]}`}>
      {ratingLabel(item)}
    </span>
  );
}

export function TickerBadge({ ticker }: { ticker: string }) {
  return (
    <span className="inline-grid h-10 min-w-14 place-items-center whitespace-nowrap rounded-[10px] bg-brand px-2 text-sm font-black tracking-[.05em] text-white">
      {ticker}
    </span>
  );
}

export function Stats({ item }: { item: ReportItem }) {
  const upside = item.upside;
  const tone = typeof upside === "number" ? (upside < 0 ? "text-err-ink" : "text-ok-ink") : "";
  return (
    <dl className="m-0 grid grid-cols-3 gap-2">
      {[
        ["Target", `Rp${rp(item.tp)}`, ""],
        ["Potensi", pct(upside), tone],
        ["Harga", `Rp${rp(item.price)}`, ""],
      ].map(([label, value, cls]) => (
        <div key={label} className="rounded-lg bg-canvas px-2.5 py-2">
          <dt className="text-[12.5px] text-ink-soft">{label}</dt>
          <dd className={`m-0 text-[15px] font-black tabular-nums ${cls}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The audit trace: the React view when the trace JSON exists, else the standalone HTML. */
export function traceHref(item: ReportItem) {
  return item.files.trace_json ? `/laporan/${item.ticker}/jejak` : reportFiles(item.ticker).traceHtml;
}

export function ReportCard({ item }: { item: ReportItem }) {
  const files = reportFiles(item.ticker);
  const trace = traceHref(item);
  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-rule bg-surface transition-colors hover:border-rule-strong">
      {item.files.pdf && (
        <a className="block aspect-[210/150] overflow-hidden border-b border-rule-soft bg-canvas" href={files.pdf}
          aria-label={`Buka PDF ${item.ticker}`}>
          <img src={files.cover} alt={`Halaman sampul company update ${item.ticker}`} loading="lazy" width={420} height={300}
            className="block h-auto w-full object-cover object-top" />
        </a>
      )}
      <div className="flex flex-1 flex-col gap-3 px-[18px] pt-[18px] pb-4">
        <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3">
          <TickerBadge ticker={item.ticker} />
          <div>
            <strong className="block text-[14.5px] leading-tight">{item.name}</strong>
            <span className="block text-[12.5px] text-ink-soft">{[item.profile, item.date].filter(Boolean).join(" · ")}</span>
          </div>
          <RatingBadge item={item} />
        </div>
        <p className="text-[15px] leading-snug font-bold">{item.headline}</p>
        {item.published ? (
          <>
            <Stats item={item} />
            <p className="text-[13px] text-ink-soft">Metode: <b className="text-ink">{item.method}</b></p>
          </>
        ) : (
          <p className="rounded-lg bg-warn-bg px-2.5 py-2 text-[13.5px] text-warn-ink">
            <b>Rating ditahan:</b> {item.held_reason || "bukti belum lengkap"}. Rincian tiap pemeriksaan tercatat di jejak.
          </p>
        )}
        <div className="mt-auto flex flex-wrap gap-2">
          {item.files.pdf && <a className="btn btn-sm btn-primary" href={files.pdf}>Buka PDF</a>}
          {item.files.html && <a className="btn btn-sm btn-ghost" href={files.html}>Versi web</a>}
          {(item.files.trace_json || item.files.trace) &&
            (trace.startsWith("/laporan") ? <Link className="btn btn-sm btn-ghost" to={trace}>Jejak</Link>
              : <a className="btn btn-sm btn-ghost" href={trace}>Jejak</a>)}
        </div>
      </div>
    </article>
  );
}

export function ReportGrid({ items }: { items: ReportItem[] }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-5">
      {items.map((item) => <ReportCard key={item.ticker} item={item} />)}
    </div>
  );
}
