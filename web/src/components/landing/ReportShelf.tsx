// The stored company updates as one ruled table in the deck's voice: ticker
// in mono, rating, target, upside, the selected method, and the two ways in
// (replay the run, or open the report).
import { Link } from "react-router-dom";
import { FileText, Play } from "lucide-react";
import { readerFiles, type ReportItem } from "../../lib/api";
import { pct, rp } from "../../lib/format";
import { twin, useLang, type Lang } from "../../lib/i18n";
import { selectedStep } from "../../lib/labels";
import { RatingBadge } from "../Reports";

const signed = (v: number | null) => (typeof v === "number" && v > 0 ? "+" : "") + pct(v);
const upTone = (v: number | null) => (typeof v !== "number" ? "text-ink-faint" : v < 0 ? "text-err-ink" : "text-ok-ink");

function selected(item: ReportItem, lang: Lang) {
  const step = selectedStep(item.chain);
  return step ? twin(step, "step", lang) : item.published ? twin(item, "method", lang) : "";
}

function Actions({ item }: { item: ReportItem }) {
  const { t, lang } = useLang();
  const files = readerFiles(item, lang);
  const href = item.files.html ? files.html : item.files.pdf ? files.pdf : undefined;
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5 max-md:justify-start">
      <Link to={`/laporan/${item.ticker}/putar`} className="btn btn-ghost btn-sm gap-1.5 px-2.5"
        aria-label={t({ id: `Putar ulang run ${item.ticker}`, en: `Replay the ${item.ticker} run` })}>
        <Play aria-hidden className="size-3.5" strokeWidth={2.2} />{t({ id: "Putar ulang", en: "Replay" })}
      </Link>
      {href && (
        <a href={href} className="btn btn-ghost btn-sm gap-1.5 px-2.5" aria-label={t({ id: `Buka laporan ${item.ticker}`, en: `Open the ${item.ticker} report` })}>
          <FileText aria-hidden className="size-3.5" strokeWidth={2.2} />{t({ id: "Buka laporan", en: "Open report" })}
        </a>
      )}
    </div>
  );
}

export function ReportShelf({ items }: { items: ReportItem[] }) {
  const { t, lang } = useLang();
  const held = t({ id: "ditahan", en: "held" });
  const th = "px-4 py-3 text-[13px] font-bold text-ink-soft";
  return (
    <div className="panel overflow-hidden">
      <table className="w-full border-collapse text-[14.5px] max-md:hidden">
        <caption className="sr-only">{t({ id: "Company update tersimpan", en: "Stored company updates" })}</caption>
        <thead className="border-b border-rule bg-raised text-left">
          <tr>
            <th scope="col" className={th}>{t({ id: "Emiten", en: "Issuer" })}</th>
            <th scope="col" className={`${th} max-xl:hidden`}>{t({ id: "Profil", en: "Profile" })}</th>
            <th scope="col" className={th}>Rating</th>
            <th scope="col" className={`${th} text-right`}>Target</th>
            <th scope="col" className={`${th} text-right`}>{t({ id: "Potensi", en: "Upside" })}</th>
            <th scope="col" className={th}>{t({ id: "Metode terpilih", en: "Selected method" })}</th>
            <th scope="col" className={`${th} text-right`}><span className="sr-only">{t({ id: "Aksi", en: "Actions" })}</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.ticker} className="border-t border-rule-soft transition-colors first:border-t-0 hover:bg-raised">
              <th scope="row" className="px-4 py-3 text-left font-normal">
                <span className="block font-mono text-[14.5px] font-semibold tracking-[.04em] text-ink-strong">{item.ticker}</span>
                <span className="block max-w-[26ch] truncate text-[13px] text-ink-soft">{item.name}</span>
              </th>
              <td className="px-4 py-3 text-ink-soft max-xl:hidden">{twin(item, "profile", lang)}</td>
              <td className="px-4 py-3"><RatingBadge item={item} /></td>
              <td className="px-4 py-3 text-right font-mono font-semibold whitespace-nowrap text-ink-strong tabular-nums">
                {item.published ? `Rp${rp(item.tp)}` : <span className="font-sans font-normal text-ink-faint">{held}</span>}
              </td>
              <td className={`px-4 py-3 text-right font-mono whitespace-nowrap tabular-nums ${upTone(item.upside)}`}>
                {item.published ? signed(item.upside) : "-"}
              </td>
              <td className="px-4 py-3">
                {item.published
                  ? <span className="font-mono text-[13.5px] text-ink" title={twin(item, "method", lang)}>{selected(item, lang)}</span>
                  : <span className="text-[13.5px] text-warn-ink">
                    {t({ id: "Ditahan:", en: "Held:" })} {twin(item, "held_reason", lang) || t({ id: "bukti belum lengkap", en: "incomplete evidence" })}
                  </span>}
              </td>
              <td className="px-4 py-3"><Actions item={item} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul aria-label={t({ id: "Company update tersimpan", en: "Stored company updates" })} className="m-0 list-none p-0 md:hidden">
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
                <dt className="text-ink-soft">Target</dt>
                <dd className="m-0 font-mono font-semibold text-ink-strong tabular-nums">{item.published ? `Rp${rp(item.tp)}` : held}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">{t({ id: "Potensi", en: "Upside" })}</dt>
                <dd className={`m-0 font-mono tabular-nums ${upTone(item.upside)}`}>{item.published ? signed(item.upside) : "-"}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-ink-soft">{t({ id: "Metode", en: "Method" })}</dt>
                <dd className="m-0 truncate font-mono text-ink">{item.published ? selected(item, lang) : held}</dd>
              </div>
            </dl>
            <div className="mt-3"><Actions item={item} /></div>
          </li>
        ))}
      </ul>
    </div>
  );
}
