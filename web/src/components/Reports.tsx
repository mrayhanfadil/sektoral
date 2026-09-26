import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowDown, ArrowUp, ChevronRight, FileDown, FileText, Footprints, Play } from "lucide-react";
import { api, reportFiles, type ArchivedPublication, type ChainStep, type ReportItem } from "../lib/api";
import { pct, rp } from "../lib/format";
import { ratingLabel, ratingTone, type RatingTone } from "../lib/labels";
import { IssuerLogo } from "./IssuerLogo";

/* ------------------------------------------------------------------ */
/* Small instruments, also used by the landing page and the trace.     */

const TONE: Record<RatingTone, string> = {
  buy: "border-ok-ink/30 bg-ok-bg text-ok-ink",
  hold: "border-brand-ink/30 bg-brand-50 text-brand-ink",
  sell: "border-err-ink/30 bg-err-bg text-err-ink",
  review: "border-warn-rule/60 bg-warn-bg text-warn-ink",
};

const RELEASE_STATUS_LABEL: Record<string, string> = {
  production_ready: "Production-Ready",
  distributable_assumption_led: "Assumption-Led",
  draft_non_distributable: "Draft",
};
const PUBLICATION_STATE_LABEL: Record<string, string> = {
  built: "Belum lolos release",
  review_pending: "Menunggu review",
  published: "Terbit",
  superseded: "Superseded",
  withdrawn: "Dicabut",
};

/** The rating, analytical Release Status, and separate publication state. */
/** Release policy 1.2.0: a published view that a newer official period has overtaken. */
export function StaleBadge({ item }: { item: Pick<ReportItem, "freshness"> }) {
  const state = item.freshness?.state;
  if (state !== "stale" && state !== "withdrawal_due") return null;
  const why = [item.freshness?.reason, ...(item.freshness?.triggers ?? [])].filter(Boolean).join(" ");
  return (
    <span title={why} className="mt-1 inline-flex h-6 items-center rounded-[5px] border border-warn-rule/60 bg-warn-bg px-2 font-mono text-[11px] leading-none font-medium whitespace-nowrap text-warn-ink">
      {state === "withdrawal_due" ? "Stale · penarikan jatuh tempo" : "Stale · perlu ditinjau"}
    </span>
  );
}

export function RatingBadge({ item }: { item: Pick<ReportItem, "rating" | "held_reason" | "release_status" | "publication_state"> }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className={`inline-flex h-6 items-center gap-1.5 rounded-[5px] border px-2 font-mono text-[12px] leading-none font-semibold whitespace-nowrap ${TONE[ratingTone(item)]}`}>
        <span aria-hidden className="size-1.5 rounded-[1.5px] bg-current" />
        <span className="sr-only">Rating </span>{ratingLabel(item)}
      </span>
      {item.release_status && <span className="inline-flex h-6 items-center rounded-[5px] border border-rule bg-raised px-2 font-mono text-[11px] leading-none font-medium whitespace-nowrap text-ink-soft">
        Release: {RELEASE_STATUS_LABEL[item.release_status] ?? item.release_status}
      </span>}
      <span className={`inline-flex h-6 items-center rounded-[5px] border px-2 font-mono text-[11px] leading-none font-medium whitespace-nowrap ${item.publication_state === "published" ? "border-ok-ink/30 bg-ok-bg text-ok-ink" : "border-warn-rule/50 bg-warn-bg/60 text-warn-ink"}`}>
        {PUBLICATION_STATE_LABEL[item.publication_state] ?? item.publication_state}
      </span>
    </span>
  );
}

export function TickerBadge({ ticker }: { ticker: string }) {
  return (
    <span className="inline-flex h-7 min-w-[52px] items-center justify-center rounded-[5px] bg-brand px-2 font-mono text-[13px] font-bold tracking-[.04em] whitespace-nowrap text-white">
      {ticker}
    </span>
  );
}

/** Upside with its sign: "+61,6%", "−36,8%". */
export function signedPct(value: number | null | undefined): string {
  return typeof value === "number" && value > 0 ? `+${pct(value)}` : pct(value);
}

const upsideTone = (v: number | null | undefined) => (typeof v !== "number" ? "text-ink-soft" : v < 0 ? "text-err-ink" : "text-ok-ink");

export function Stats({ item }: { item: ReportItem }) {
  return (
    <dl className="m-0 grid grid-cols-3 divide-x divide-rule rounded-md border border-rule bg-surface">
      {[
        ["Target", `Rp${rp(item.tp)}`, "text-ink-strong"],
        ["Potensi", signedPct(item.upside), upsideTone(item.upside)],
        ["Harga", `Rp${rp(item.price)}`, "text-ink-strong"],
      ].map(([label, value, cls]) => (
        <div key={label} className="min-w-0 px-3 py-2">
          <dt className="text-[12px] text-ink-soft">{label}</dt>
          <dd className={`m-0 font-mono text-[14.5px] font-semibold tabular-nums ${cls}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The audit trace: the React view when the trace JSON exists, else the standalone HTML. */
export function traceHref(item: ReportItem) {
  return item.files.trace_json ? `/laporan/${item.ticker}/jejak` : reportFiles(item.ticker).traceHtml;
}

const DAY = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** "2026-09-24" → "24 Sep 2026"; anything unparseable is shown as given. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? iso : DAY.format(date);
}

/** The method the chain selected, short ("DDM"); the full description stays in `item.method`. */
export function primaryMethod(item: Pick<ReportItem, "chain" | "method">): string {
  return item.chain.find((s) => s.decision === "Terpilih")?.step ?? item.chain[0]?.step ?? item.method;
}

type Decision = "pick" | "cross" | "skip" | "other";
const decisionOf = (d: string): Decision =>
  d === "Terpilih" ? "pick" : d === "Silang cek" ? "cross" : d === "Tidak dijalankan" ? "skip" : "other";

const STEP: Record<Decision, string> = {
  pick: "border-brand-ink/35 bg-brand-50 font-semibold text-brand-ink",
  cross: "border-rule-strong bg-surface text-ink",
  skip: "border-dashed border-rule-strong bg-transparent text-ink-faint",
  other: "border-rule bg-raised text-ink-soft",
};

const hasValue = (s: ChainStep) => Boolean(s.value && s.value !== "-" && s.value !== "—");

function StepMark({ kind, children }: { kind: Decision; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[4px] border px-1.5 text-[12.5px] leading-[20px] whitespace-nowrap ${STEP[kind]}`}>
      {children}
    </span>
  );
}

/** The method chain as one inline sequence: selected step first-class, cross-checks secondary, unrun steps muted. */
export function MethodChain({ chain, className = "" }: { chain: ChainStep[]; className?: string }) {
  if (!chain.length) return <span className={`text-[13px] text-ink-faint ${className}`}>Rantai metode belum tercatat</span>;
  const skipped = chain.filter((s) => decisionOf(s.decision) === "skip").length;
  return (
    <ol aria-label="Rantai metode" className={`m-0 flex list-none flex-wrap items-center gap-x-1 gap-y-1.5 p-0 ${className}`}>
      {chain.map((s, i) => {
        const kind = decisionOf(s.decision);
        return (
          <li key={`${s.step}-${i}`} title={`${s.step}: ${s.decision}${hasValue(s) ? `, ${s.value}` : ""}`}
            className={`flex items-center gap-1 ${kind === "skip" ? "max-sm:hidden" : ""}`}>
            {i > 0 && <ChevronRight aria-hidden className="size-3 flex-none text-ink-faint" strokeWidth={2.2} />}
            <StepMark kind={kind}>
              <span className="sr-only">{s.decision}: </span>
              {s.step}
              {hasValue(s) && <span className="font-mono text-[12px] tabular-nums">{s.value}</span>}
            </StepMark>
          </li>
        );
      })}
      {skipped > 0 && <li className="text-[12.5px] text-ink-faint tabular-nums sm:hidden">+{skipped} tidak dijalankan</li>}
    </ol>
  );
}

/** Key to the chain marks, shown once per register. */
export function ChainLegend() {
  return (
    <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[12.5px] text-ink-soft">
      <span>Rantai metode:</span>
      <StepMark kind="pick">Terpilih</StepMark>
      <StepMark kind="cross">Silang cek</StepMark>
      <StepMark kind="skip">Tidak dijalankan</StepMark>
    </p>
  );
}

/** A diverging bar for upside: right of the centre line is upside, left is downside. */
function UpsideMeter({ value, scale }: { value: number | null; scale: number }) {
  const reduce = useReducedMotion();
  if (typeof value !== "number" || !scale) return <span aria-hidden className="block h-1.5 w-14 rounded-full bg-rule-soft" />;
  const width = `${(Math.min(1, Math.abs(value) / scale) * 50).toFixed(1)}%`;
  const up = value >= 0;
  return (
    <span aria-hidden className="relative block h-1.5 w-14 flex-none rounded-full bg-rule-soft">
      <motion.span
        className={`absolute inset-y-0 ${up ? "left-1/2 origin-left rounded-r-full bg-ok-ink" : "right-1/2 origin-right rounded-l-full bg-err-ink"}`}
        style={{ width }}
        initial={reduce ? false : { scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ type: "spring", stiffness: 120, damping: 30, delay: 0.12 }}
      />
      <span className="absolute -inset-y-[3px] left-1/2 w-px bg-rule-strong" />
    </span>
  );
}

/** Replay, report, PDF and trace for one company update, as one compact group. */
export function ReportActions({ item, className = "" }: { item: ReportItem; className?: string }) {
  const files = reportFiles(item.ticker);
  const trace = traceHref(item);
  const cell =
    "inline-flex h-8 flex-1 items-center justify-center gap-1.5 px-2.5 text-[13px] font-medium whitespace-nowrap no-underline transition-colors " +
    "first:rounded-l-[5px] last:rounded-r-[5px] focus-visible:outline-offset-[-2px] sm:flex-none";
  const quiet = `${cell} text-ink-soft hover:bg-raised hover:text-ink-strong`;
  const icon = "size-3.5 flex-none max-sm:hidden";
  const who = <span className="sr-only"> {item.ticker}</span>;
  return (
    <>
      <div role="group" aria-label={`Tindakan untuk ${item.ticker}`}
        className={`inline-flex items-stretch divide-x divide-rule rounded-md border border-rule bg-surface ${className}`}>
        <Link to={`/laporan/${item.ticker}/putar`} className={`${cell} font-semibold text-brand-ink hover:bg-brand-50`}>
          <Play aria-hidden className="size-3.5 flex-none" strokeWidth={2.2} />
          Putar ulang<span className="max-sm:hidden"> run</span>{who}
        </Link>
        {item.files.html && (
          <a href={files.html} className={quiet}>
            <FileText aria-hidden className={icon} strokeWidth={2.2} />
            <span className="max-sm:hidden">Buka laporan</span><span className="sm:hidden">Laporan</span>{who}
          </a>
        )}
        {item.files.pdf && (
          <a href={files.pdf} className={quiet}>
            <FileDown aria-hidden className={icon} strokeWidth={2.2} />
            PDF{who}
          </a>
        )}
        {(item.files.trace_json || item.files.trace) && (trace.startsWith("/laporan") ? (
          <Link to={trace} className={quiet}><Footprints aria-hidden className={icon} strokeWidth={2.2} />Jejak{who}</Link>
        ) : (
          <a href={trace} className={quiet}><Footprints aria-hidden className={icon} strokeWidth={2.2} />Jejak{who}</a>
        ))}
      </div>
      <ArchivedVersions ticker={item.ticker} />
    </>
  );
}

/** Earlier approved bundles stay reachable with an explicit archived label. */
function ArchivedVersions({ ticker }: { ticker: string }) {
  const [archives, setArchives] = useState<ArchivedPublication[] | null>(null);
  useEffect(() => {
    let current = true;
    api.reportArchives(ticker).then((rows) => {
      if (current) setArchives(rows);
    }).catch(() => {
      if (current) setArchives([]);
    });
    return () => { current = false; };
  }, [ticker]);

  if (!archives?.length) return null;
  return (
    <details className="relative text-[12.5px] text-ink-soft">
      <summary className="flex h-8 cursor-pointer list-none items-center rounded-md border border-rule bg-surface px-2.5 font-medium hover:bg-raised focus-visible:outline-offset-2">
        Arsip ({archives.length})
      </summary>
      <div className="absolute right-0 z-20 mt-1.5 w-[min(360px,calc(100vw-2rem))] rounded-md border border-rule bg-surface p-3 shadow-[var(--shadow-pop)]">
        <p className="m-0 mb-2 text-[12px] text-ink-soft">Versi terdahulu yang disetujui, disimpan sebagai arsip.</p>
        <ul className="m-0 list-none divide-y divide-rule-soft p-0">
          {archives.map((archive) => (
            <li key={archive.publication_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2 first:pt-0 last:pb-0">
              <span className="min-w-0 flex-1 truncate font-medium text-ink" title={archive.publication_id}>
                Arsip · {formatDay(archive.archived_at)} · {archive.publication_id.slice(0, 10)}
              </span>
              {archive.files.html && <a className="underline underline-offset-2" href={archive.files.html}>HTML</a>}
              {archive.files.pdf && <a className="underline underline-offset-2" href={archive.files.pdf}>PDF</a>}
              {archive.files.trace && <a className="underline underline-offset-2" href={archive.files.trace}>Audit Trace</a>}
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}

/** The PDF cover as a row thumbnail; hover or focus lifts a readable preview beside it. */
function Cover({ item }: { item: ReportItem }) {
  const [broken, setBroken] = useState(false);
  const files = reportFiles(item.ticker);
  if (!item.files.pdf || broken) {
    return <span aria-hidden className="block h-[62px] w-11 rounded-[3px] border border-dashed border-rule" />;
  }
  return (
    <a href={files.pdf} className="group/cover relative block w-11 rounded-[3px] focus-visible:outline-offset-2">
      <img src={files.cover} alt={`Sampul PDF company update ${item.ticker}`} loading="lazy" width={44} height={62}
        onError={() => setBroken(true)}
        className="block h-[62px] w-11 rounded-[3px] border border-rule bg-white object-cover object-top transition-[border-color] group-hover/cover:border-brand-ink" />
      <span aria-hidden
        className="pointer-events-none absolute top-1/2 left-full z-30 ml-3 w-[250px] origin-left -translate-y-1/2 scale-[.96] overflow-hidden rounded-md border border-rule bg-white opacity-0 shadow-[var(--shadow-pop)] transition-[opacity,transform] duration-200 ease-[var(--ease-out-expo)] group-hover/cover:scale-100 group-hover/cover:opacity-100 group-focus-visible/cover:scale-100 group-focus-visible/cover:opacity-100">
        <img src={files.cover} alt="" width={250} height={354} className="block h-auto w-full" />
      </span>
    </a>
  );
}

/* ------------------------------------------------------------------ */
/* The register: one ruled row per company update.                    */

// Rows are one grid; areas move as the width changes. Below lg a row
// stacks (identity, figures, chain and actions); from lg the figures are
// columns, and from xl the method and date get columns of their own.
const ROW =
  "grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-4 [grid-template-areas:'tk_nm_rt'_'num_num_num'_'l2_l2_l2'] " +
  "lg:grid-cols-[44px_76px_minmax(0,1fr)_128px_96px_88px_128px] lg:[grid-template-areas:'cv_tk_nm_rt_tp_px_up'_'cv_._l2_l2_l2_l2_l2'] " +
  "xl:grid-cols-[44px_76px_minmax(0,1fr)_128px_112px_96px_88px_128px_96px] xl:[grid-template-areas:'cv_tk_nm_rt_me_tp_px_up_dt'_'cv_._l2_l2_l2_l2_l2_l2_l2']";
const HEAD =
  "hidden gap-x-4 lg:grid lg:grid-cols-[44px_76px_minmax(0,1fr)_128px_96px_88px_128px] lg:[grid-template-areas:'cv_tk_nm_rt_tp_px_up'] " +
  "xl:grid-cols-[44px_76px_minmax(0,1fr)_128px_112px_96px_88px_128px_96px] xl:[grid-template-areas:'cv_tk_nm_rt_me_tp_px_up_dt']";

export type SortKey = "ticker" | "upside";
export type Sort = { key: SortKey; dir: "asc" | "desc" };

function SortButton({ label, col, sort, onSort, align = "left" }:
  { label: string; col: SortKey; sort?: Sort; onSort?: (s: Sort) => void; align?: "left" | "right" }) {
  if (!sort || !onSort) return <>{label}</>;
  const active = sort.key === col;
  const next: Sort = active ? { key: col, dir: sort.dir === "asc" ? "desc" : "asc" } : { key: col, dir: col === "upside" ? "desc" : "asc" };
  const Arrow = active && sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <button type="button" onClick={() => onSort(next)}
      className={`inline-flex cursor-pointer items-center gap-1 rounded-[4px] transition-colors hover:text-ink-strong ${active ? "text-ink-strong" : ""} ${align === "right" ? "flex-row-reverse" : ""}`}>
      {label}
      <Arrow aria-hidden className={`size-3 transition-opacity ${active ? "opacity-100" : "opacity-40"}`} strokeWidth={2.4} />
      <span className="sr-only">
        {active ? `, diurutkan ${sort.dir === "asc" ? "naik" : "turun"}; klik untuk membalik` : ", klik untuk mengurutkan"}
      </span>
    </button>
  );
}

function RegisterHead({ sort, onSort }: { sort?: Sort; onSort?: (s: Sort) => void }) {
  const cell = "flex items-center";
  return (
    <div className={`${HEAD} sticky top-[52px] z-20 border-b border-rule bg-surface px-5 py-2 text-[12.5px] font-medium text-ink-soft`}>
      <span style={{ gridArea: "tk" }} className={cell}><SortButton label="Kode" col="ticker" sort={sort} onSort={onSort} /></span>
      <span style={{ gridArea: "nm" }} className={cell}>Emiten</span>
      <span style={{ gridArea: "rt" }} className={cell}>Rating</span>
      <span style={{ gridArea: "me" }} className={`${cell} max-xl:hidden`}>Metode utama</span>
      <span style={{ gridArea: "tp" }} className={`${cell} justify-end`}>Target</span>
      <span style={{ gridArea: "px" }} className={`${cell} justify-end`}>Harga</span>
      <span style={{ gridArea: "up" }} className={`${cell} justify-end`}><SortButton label="Potensi" col="upside" sort={sort} onSort={onSort} align="right" /></span>
      <span style={{ gridArea: "dt" }} className={`${cell} justify-end max-xl:hidden`}>Tanggal</span>
    </div>
  );
}

function ReportRow({ item, scale }: { item: ReportItem; scale: number }) {
  const figure = "min-w-0 lg:text-right";
  const label = "text-[11.5px] text-ink-soft lg:sr-only";
  const value = "m-0 font-mono text-[14px] font-medium tabular-nums text-ink-strong";
  return (
    <article aria-labelledby={`row-${item.ticker}`}
      className={`${ROW} items-start px-5 py-3.5 transition-colors duration-200 hover:bg-raised focus-within:bg-raised max-sm:px-4`}>
      <div style={{ gridArea: "cv" }} className="max-lg:hidden"><Cover item={item} /></div>

      <div style={{ gridArea: "tk" }} className="min-w-0">
        <h3 id={`row-${item.ticker}`} className="font-mono text-[14.5px] leading-6 font-bold tracking-[.03em] text-brand-ink">{item.ticker}</h3>
        <p className="text-[12px] leading-5 text-ink-soft">{item.profile}</p>
      </div>

      <div style={{ gridArea: "nm" }} className="flex min-w-0 items-start gap-3">
        <IssuerLogo ticker={item.ticker} size="sm" className="mt-0.5 max-sm:hidden" />
        <div className="min-w-0 flex-1">
        <p className="truncate text-[14.5px] leading-6 font-medium text-ink-strong" title={item.name}>{item.name}</p>
        {item.published ? (
          <p className="truncate text-[13px] leading-5 text-ink-soft" title={item.headline}>{item.headline}</p>
        ) : (
          <p className="text-[13px] leading-5 text-warn-ink">Rating ditahan: {item.held_reason || "bukti belum lengkap"}</p>
        )}
        </div>
      </div>

      <div style={{ gridArea: "rt" }} className="pt-px max-lg:text-right">
        <RatingBadge item={item} />
        <StaleBadge item={item} />
        <time dateTime={item.date} className="data mt-1.5 block text-ink-soft lg:hidden">{formatDay(item.date)}</time>
      </div>

      <p style={{ gridArea: "me" }} className="truncate pt-0.5 text-[13.5px] text-ink max-xl:hidden" title={item.published ? item.method : ""}>
        {item.published ? primaryMethod(item) : "Metode ditampilkan setelah publikasi"}
      </p>

      <dl style={{ gridArea: "num" }}
        className="m-0 mt-2.5 grid grid-cols-3 gap-x-3 border-t border-rule-soft pt-2 lg:contents">
        <div className={`${figure} lg:[grid-area:tp]`}>
          <dt className={label}>Target</dt>
          <dd className={value}>Rp{rp(item.tp)}</dd>
        </div>
        <div className={`${figure} lg:[grid-area:px]`}>
          <dt className={label}>Harga</dt>
          <dd className={`${value} !text-ink`}>Rp{rp(item.price)}</dd>
        </div>
        <div className={`${figure} lg:[grid-area:up]`}>
          <dt className={label}>Potensi</dt>
          <dd className="m-0 flex items-center gap-2 lg:justify-end">
            <span className="order-2 lg:order-1"><UpsideMeter value={item.upside} scale={scale} /></span>
            <span className={`order-1 font-mono text-[14px] font-semibold tabular-nums lg:order-2 ${upsideTone(item.upside)}`}>{signedPct(item.upside)}</span>
          </dd>
        </div>
      </dl>

      <time style={{ gridArea: "dt" }} dateTime={item.date} className="data pt-1 text-right text-ink-soft max-xl:hidden">{formatDay(item.date)}</time>

      <div style={{ gridArea: "l2" }} className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2.5 lg:mt-2">
        {item.published ? <MethodChain chain={item.chain} className="min-w-[200px] flex-1 basis-0" />
          : <span className="text-[13px] text-ink-faint">Company Update menunggu publikasi</span>}
        <time dateTime={item.date} className="data hidden text-ink-soft lg:block xl:hidden">{formatDay(item.date)}</time>
        <ReportActions item={item} className="max-sm:basis-full" />
      </div>
    </article>
  );
}

/** Company updates as a ruled, sortable register. `scale` fixes the upside bars across filters. */
export function ReportRegister({ items, scale, sort, onSort }:
  { items: ReportItem[]; scale?: number; sort?: Sort; onSort?: (s: Sort) => void }) {
  const reduce = useReducedMotion();
  const max = scale ?? Math.max(0, ...items.map((i) => Math.abs(i.upside ?? 0)));
  return (
    <div>
      <RegisterHead sort={sort} onSort={onSort} />
      <ul className="m-0 list-none divide-y divide-rule-soft p-0">
        <AnimatePresence initial={false} mode="popLayout">
          {items.map((item) => (
            <motion.li key={item.ticker}
              layout={reduce ? false : "position"}
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={reduce ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, transition: { duration: 0.16 } }}
              transition={{ layout: { type: "spring", stiffness: 420, damping: 42 }, opacity: { duration: 0.2 } }}>
              <ReportRow item={item} scale={max} />
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}

/** Kept for the landing page: the same register, unsorted. */
export function ReportGrid({ items }: { items: ReportItem[] }) {
  return (
    <div className="panel">
      <ReportRegister items={items} />
    </div>
  );
}
