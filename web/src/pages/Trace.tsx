import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { ArrowLeft, ChevronRight, FileDown, FileText, Play, RefreshCw, Search, TriangleAlert } from "lucide-react";
import { api, reportFiles, type ReportItem, type RunReplay, type TraceView } from "../lib/api";
import { rp } from "../lib/format";
import { validatorNote } from "../lib/labels";
import { AGENT, derive, type AgentId, type Status } from "../lib/agents";
import { LiveMark } from "../components/Mark";
import {
  Chip, Empty, INTEL_SECTIONS, IntelHeadline, IntelSections, Section, Source, StatusWord, SubHead, type ChipTone,
} from "../components/Intel";
import { MethodChain, RatingBadge, signedPct } from "../components/Reports";
import { Notice, useLoad } from "../components/State";
import { ReviewPanel } from "../components/Review";
import { IssuerLogo } from "../components/IssuerLogo";

/* ------------------------------------------------------------------ */
/* The index: the trace's table of contents, grouped by the agent that */
/* produced each part. Only sections present on the page are listed.  */

type IndexGroup = { agent: AgentId; sections: [string, string][] };

const RESEARCH: [string, string][] = [
  ["ringkasan", "Ringkasan brief"], ["endpoint", "Endpoint yang dibaca"],
  ["temuan", "Temuan bersitasi"], ["kurang", "Bukti yang masih kurang"],
];
const NEWS: [string, string][] = [["berita", "Pencarian berita"], ["deep-dive", "Deep-dive berita"]];
const FORECAST: [string, string][] = [
  ["asumsi", "Dampak berita"], ["interim", "Skenario interim"], ["tahun-lanjutan", "Tahun lanjutan"], ["driver-bank", "Driver bank"],
];
const BANK_COLS: [keyof NonNullable<TraceView["forecast"]["bank_drivers"]>[number], string][] = [
  ["loan_growth_pct", "Pertumbuhan kredit"], ["nim_pct", "NIM"], ["non_ii_to_nii_pct", "Non-bunga / NII"],
  ["cost_to_income_pct", "Biaya / pendapatan"], ["cost_of_credit_pct", "Biaya kredit"], ["deposit_growth_pct", "Pertumbuhan DPK"],
];
const LABEL = Object.fromEntries([...RESEARCH, ...NEWS, ...FORECAST]);

const INDEX: IndexGroup[] = [
  { agent: "analis", sections: INTEL_SECTIONS },
  { agent: "riset", sections: RESEARCH },
  { agent: "berita", sections: NEWS },
  { agent: "forecast", sections: FORECAST },
];
const groupId = (agent: AgentId) => `agen-${agent}`;

/** Sections present on the page, and the one being read. */
function useSectionIndex() {
  const [present, setPresent] = useState<IndexGroup[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  useEffect(() => {
    const groups = INDEX
      .filter((g) => document.getElementById(groupId(g.agent)))
      .map((g) => ({ ...g, sections: g.sections.filter(([id]) => document.getElementById(id)) }));
    setPresent(groups);
    // Watch the finest level present (a group only when it has no sections), in document order;
    // the current entry is the first one inside the reading band.
    const ids = groups.flatMap((g) => g.sections.length ? g.sections.map(([id]) => id) : [groupId(g.agent)]);
    setCurrent(ids[0] ?? null);
    const inBand = new Set<string>();
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((e) => (e.isIntersecting ? inBand.add(e.target.id) : inBand.delete(e.target.id)));
      const first = ids.find((id) => inBand.has(id));
      if (first) setCurrent(first);
    }, { rootMargin: "-120px 0px -55% 0px" });
    ids.forEach((id) => observer.observe(document.getElementById(id)!));
    return () => observer.disconnect();
  }, []);
  return { present, current };
}

function SectionIndex({ present, current }: { present: IndexGroup[]; current: string | null }) {
  const reduce = useReducedMotion();
  const bar = useRef<HTMLUListElement>(null);
  const spring = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 420, damping: 40 };
  // Keep the phone bar's current link in view without scrolling the page.
  useEffect(() => {
    const list = bar.current;
    const link = list?.querySelector<HTMLElement>(`[data-id="${current}"]`);
    if (!list || !link) return;
    list.scrollTo({ left: link.offsetLeft - list.clientWidth / 2 + link.clientWidth / 2, behavior: reduce ? "auto" : "smooth" });
  }, [current, reduce]);
  const flat = present.flatMap((g) => g.sections.length ? g.sections : [[groupId(g.agent), AGENT[g.agent].name] as [string, string]]);

  return (
    <>
      <nav aria-label="Bagian jejak riset" className="sticky top-[76px] max-h-[calc(100vh-96px)] min-w-0 overflow-y-auto pb-6 max-lg:hidden">
        <ol className="m-0 grid list-none gap-4 p-0">
          {present.map((g) => (
            <li key={g.agent}>
              <a href={`#${groupId(g.agent)}`} aria-current={current === groupId(g.agent) ? "location" : undefined}
                className="mb-1 flex items-center gap-2 text-[13px] font-semibold text-ink-strong no-underline hover:text-brand-ink">
                <LiveMark status="ok" className="h-2.5 w-3" />{AGENT[g.agent].name}
              </a>
              <ul className="m-0 grid list-none border-l border-rule p-0">
                {g.sections.map(([id, label]) => {
                  const on = current === id;
                  return (
                    <li key={id} className="relative">
                      {on && <motion.span layoutId="trace-index" aria-hidden className="absolute inset-y-0 -left-px w-[2px] rounded-full bg-brand-ink" transition={spring} />}
                      <a href={`#${id}`} aria-current={on ? "location" : undefined}
                        className={`block py-1 pl-3 text-[13.5px] leading-snug no-underline transition-colors ${on ? "font-medium text-ink-strong" : "text-ink-soft hover:text-ink-strong"}`}>
                        {label}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      </nav>

      <nav aria-label="Bagian jejak riset" className="sticky top-[52px] z-30 -mx-6 min-w-0 border-b border-rule bg-surface max-sm:-mx-4 lg:hidden">
        <ul ref={bar} className="relative m-0 flex list-none gap-1 overflow-x-auto px-2 py-1.5 whitespace-nowrap [scrollbar-width:none]">
          {flat.map(([id, label]) => {
            const on = current === id;
            return (
              <li key={id} className="relative" data-id={id}>
                <a href={`#${id}`} aria-current={on ? "location" : undefined}
                  className={`relative block rounded-[5px] px-2.5 py-1.5 text-[13px] no-underline ${on ? "font-medium text-ink-strong" : "text-ink-soft"}`}>
                  {on && <motion.span layoutId="trace-index-bar" aria-hidden className="absolute inset-0 rounded-[5px] bg-raised ring-1 ring-rule" transition={spring} />}
                  <span className="relative">{label}</span>
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}

/* ------------------------------------------------------------------ */

/** One agent's part of the trace: a console panel with its own header. */
function AgentGroup({ agent, status, chip, children }:
  { agent: AgentId; status: Status; chip: React.ReactNode; children: React.ReactNode }) {
  const meta = AGENT[agent];
  const id = groupId(agent);
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="panel scroll-mt-20 max-lg:scroll-mt-[108px]">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-6 py-5 max-sm:px-4">
        <div className="flex min-w-0 items-start gap-3">
          <LiveMark status={status === "warn" ? "warn" : status === "error" ? "error" : "ok"} className="mt-[9px] h-3 w-3.5 flex-none" />
          <div className="min-w-0">
            <h2 id={`${id}-title`} className="text-[20px]">{meta.name}</h2>
            <p className="text-[14px] text-ink-soft">{meta.role}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="dashed">{meta.engine === "llm" ? "Diputuskan model" : "Kode deterministik"}</Chip>
          {chip}
        </div>
      </header>
      {children}
    </section>
  );
}

/** Validator notes (rejected drafts, failed calls) kept visible at the top of an agent's panel. */
function Problems({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="border-t border-rule px-6 py-4 max-sm:px-4">
      <div className="rounded-md border border-warn-rule/60 bg-warn-bg/40 px-4 py-3">
        <p className="flex items-center gap-2 text-[13.5px] font-medium text-warn-ink">
          <TriangleAlert aria-hidden className="size-3.5 flex-none" strokeWidth={2.2} />{title} <span className="data">{items.length}</span>
        </p>
        <ul className="mt-1.5 grid gap-1.5 pl-[22px] text-[13.5px] leading-relaxed break-words text-ink">
          {items.map((p, i) => {
            const { message, removed } = validatorNote(p);
            return (
              <li key={i}>
                {message}{/[.!?]$/.test(message) ? "" : "."}
                {removed.length > 0 && (
                  <span className="ml-1 text-ink-soft">
                    Dihapus dari prosa:{" "}
                    {removed.map((v, j) => (
                      <span key={v}>{j > 0 && ", "}<code className="font-mono text-[12.5px] text-ink-strong">{v}</code></span>
                    ))}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

const epId = (endpoint: string) => `ep-${endpoint.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "")}`;

/** The agent records news without a measurable transmission as driver "none", change 0. */
const isNoEffect = (e: { driver: string | null; change: string | null }) =>
  !e.driver || e.driver === "none" || Number(e.change) === 0;

const pctCell = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });
const pctOf = (v: number | null) => (v == null ? "n.a." : `${pctCell.format(v).replace("-", "−")}%`);

const RELEASE: Record<string, [string, ChipTone]> = {
  production_ready: ["Siap produksi", "ok"],
  distributable_assumption_led: ["Terbit, berbasis asumsi analis", "brand"],
  draft_non_distributable: ["Draft, belum didistribusikan", "warn"],
};

function forecastStatus(status: string | null): [string, Status] {
  if (status === "validated") return ["Tervalidasi", "ok"];
  if (status === "partial") return ["Parsial", "warn"];
  return [status ? `Status ${status}` : "Status tidak tercatat", status ? "warn" : "idle"];
}

/* ------------------------------------------------------------------ */

type Links = {
  reportUrl: string;
  pdfUrl?: string;
  replayUrl?: string;
  deckUrl?: string;
};

/** The report's release as recorded in the trace: a ruled readout plus, when known, its method chain. */
function Release({ trace, item, run }: { trace: TraceView; item?: ReportItem; run?: RunReplay }) {
  const { report } = trace;
  const awaiting = trace.review_state === "pending" && (report.release_status ?? "").startsWith("distributable");
  const [label, tone] = awaiting ? ["Lolos gerbang, menunggu review analis", "warn" as ChipTone]
    : RELEASE[report.release_status ?? ""] ?? [report.release_status ? report.release_status : "Status belum tercatat", "neutral" as ChipTone];
  const counts = useMemo(() => (run?.events.length ? derive(run.events, { finished: true }).counts : null), [run]);
  const cell = "min-w-0 bg-surface px-4 py-3";
  const dt = "mb-1 text-[12px] text-ink-soft";
  return (
    <div className="mt-6 grid gap-3">
      <dl className="m-0 grid grid-cols-6 gap-px overflow-clip rounded-md border border-rule bg-rule xl:grid-cols-[1.3fr_auto_auto_auto_2fr_auto_auto]">
        <div className={`${cell} col-span-6 sm:col-span-3 xl:col-span-1`}>
          <dt className={dt}>Status rilis</dt>
          <dd className="m-0 grid gap-1">
            <span><Chip tone={tone}>{label}</Chip></span>
            {report.release_status && <code className="font-mono text-[11.5px] break-all text-ink-faint">{report.release_status}</code>}
          </dd>
        </div>
        <div className={`${cell} col-span-2 sm:col-span-1`}>
          <dt className={dt}>Rating</dt>
          <dd className="m-0"><RatingBadge item={{ rating: report.published ? report.rating : null, held_reason: item?.held_reason ?? "" }} /></dd>
        </div>
        <div className={`${cell} col-span-2 sm:col-span-1`}>
          <dt className={dt}>Target harga</dt>
          <dd className="m-0 font-mono text-[15px] font-semibold tabular-nums text-ink-strong">{report.published ? `Rp${rp(report.target_price)}` : "Ditahan"}</dd>
        </div>
        <div className={`${cell} col-span-2 sm:col-span-1`}>
          <dt className={dt}>Potensi</dt>
          <dd className={`m-0 font-mono text-[15px] font-semibold tabular-nums ${item?.upside == null ? "text-ink-soft" : item.upside < 0 ? "text-err-ink" : "text-ok-ink"}`}>
            {item ? signedPct(item.upside) : "—"}
          </dd>
        </div>
        <div className={`${cell} col-span-6 sm:col-span-4 xl:col-span-1`}>
          <dt className={dt}>Metode</dt>
          <dd className="m-0 text-[14px] leading-snug text-ink">{report.method || "Belum tercatat"}</dd>
        </div>
        <div className={`${cell} col-span-3 sm:col-span-1`}>
          <dt className={dt}>Data per</dt>
          <dd className="m-0 font-mono text-[13.5px] text-ink-strong">{report.as_of ?? "—"}</dd>
        </div>
        <div className={`${cell} col-span-3 sm:col-span-1`}>
          <dt className={dt}>Harga pasar per</dt>
          <dd className="m-0 font-mono text-[13.5px] text-ink-strong">{report.market_price_date ?? "—"}</dd>
        </div>
      </dl>
      {(item?.chain.length || counts) && (
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          {item?.chain.length ? <MethodChain chain={item.chain} /> : <span />}
          {counts && (
            <p className="text-[13px] text-ink-soft tabular-nums">
              Run {run?.source === "recorded" ? "terekam" : "disusun ulang dari jejak"}: {counts.events} event, {counts.calls} tool call
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function TraceHeader({ trace, item, run, links }: { trace: TraceView; item?: ReportItem; run?: RunReplay; links: Links }) {
  const name = item?.name ?? trace.analyst?.name;
  return (
    <header className="border-b border-rule bg-surface">
      <div className="wrap pt-5 pb-6">
        <nav aria-label="Remah roti" className="mb-4 text-[13px] text-ink-soft">
          <ol className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0">
            <li><Link to="/laporan" className="text-ink-soft no-underline hover:text-brand-ink hover:underline">Laporan</Link></li>
            <li aria-hidden><ChevronRight className="size-3.5 text-ink-faint" strokeWidth={2.2} /></li>
            <li className="font-mono">{trace.ticker}</li>
            <li aria-hidden><ChevronRight className="size-3.5 text-ink-faint" strokeWidth={2.2} /></li>
            <li aria-current="page" className="text-ink">Jejak riset</li>
          </ol>
        </nav>
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
          <div className="flex min-w-0 items-center gap-4">
            <IssuerLogo ticker={trace.ticker} size="lg" className="max-sm:hidden" />
            <div className="min-w-0">
              <h1 className="text-[clamp(26px,3vw,36px)] font-black tracking-[-.02em]">
                Jejak riset <span className="font-mono tracking-[.02em] text-brand-ink">{trace.ticker}</span>
              </h1>
              {name && <p className="mt-1 text-[15.5px] text-ink-soft">{name}</p>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2.5 max-sm:grid max-sm:w-full max-sm:grid-cols-2 max-sm:[&>*:first-child]:col-span-2 max-sm:[&>*:nth-child(2):last-child]:col-span-2">
            {links.replayUrl && (
              <Link className="btn btn-primary" to={links.replayUrl}>
                <Play aria-hidden className="size-4" strokeWidth={2.2} />Putar ulang run
              </Link>
            )}
            <a className={`btn ${links.replayUrl ? "btn-ghost" : "btn-primary"}`} href={links.reportUrl}>
              <FileText aria-hidden className="size-4" strokeWidth={2.2} />
              <span className="max-sm:hidden">Buka company update</span><span className="sm:hidden">Buka laporan</span>
            </a>
            {links.deckUrl && (
              <Link className="btn btn-ghost" to={links.deckUrl}>
                <ArrowLeft aria-hidden className="size-4" strokeWidth={2.2} />Kembali ke deck
              </Link>
            )}
            {links.pdfUrl && (
              <a className="btn btn-ghost" href={links.pdfUrl}>
                <FileDown aria-hidden className="size-4" strokeWidth={2.2} />PDF
              </a>
            )}
          </div>
        </div>
        <Release trace={trace} item={item} run={run} />
      </div>
    </header>
  );
}

function TraceBody({ trace }: { trace: TraceView }) {
  const { research, news, forecast } = trace;
  const index = useSectionIndex();
  const cited = useMemo(() => {
    const n: Record<string, number> = {};
    research.insights.forEach((i) => i.citations.forEach((c) => { if (c.endpoint) n[c.endpoint] = (n[c.endpoint] ?? 0) + 1; }));
    return n;
  }, [research]);
  const analyst = trace.analyst;
  const [fLabel, fStatus] = forecastStatus(forecast.status);
  const searched = news.search.status === "searched";
  const fetched = trace.deepdive.filter((d) => d.status === "fetched").length;

  return (
    <div className="wrap grid grid-cols-1 items-start gap-x-10 pt-6 pb-16 lg:grid-cols-[216px_minmax(0,1fr)] max-lg:pt-0">
      <SectionIndex {...index} />
      <div className="grid gap-5 pt-0 max-lg:pt-4 [&>*]:min-w-0">

        <AgentGroup agent="analis" status={!analyst ? "warn" : analyst.status === "ok" ? "ok" : "warn"}
          chip={analyst ? <StatusWord status={analyst.status === "ok" ? "ok" : "warn"}>{analyst.status === "ok" ? "Selesai" : "Parsial"}</StatusWord>
            : <StatusWord status="idle">Tidak dijalankan</StatusWord>}>
          {analyst ? (
            <>
              <div className="border-t border-rule px-6 py-5 max-sm:px-4"><IntelHeadline intel={analyst} as="p" /></div>
              <Problems title="Catatan validator" items={trace.analyst_problems} />
              <IntelSections intel={analyst} />
            </>
          ) : (
            <div className="border-t border-rule px-6 py-5 max-sm:px-4">
              <Empty>{trace.analyst_problems.join("; ") || "Agent analis tidak dijalankan untuk riset ini."}</Empty>
            </div>
          )}
        </AgentGroup>

        <AgentGroup agent="riset" status={research.summary ? "ok" : "warn"}
          chip={<StatusWord status={research.summary ? "ok" : "warn"}>{research.summary ? "Brief tervalidasi" : "Brief belum tervalidasi"}</StatusWord>}>
          <Section id="ringkasan" title={LABEL.ringkasan}>
            {research.summary ? <p className="max-w-[80ch] text-[15.5px]">{research.summary}</p> : <Empty>Belum ada brief tervalidasi.</Empty>}
          </Section>

          <Section id="endpoint" title={LABEL.endpoint} count={research.endpoints.length}>
            {research.endpoints.length ? (
              <ul className="m-0 grid list-none divide-y divide-rule-soft rounded-md border border-rule p-0">
                {research.endpoints.map((e) => (
                  <li key={e} id={epId(e)} className="flex scroll-mt-28 items-center justify-between gap-3 rounded-[inherit] px-3 py-2 target:animate-hold">
                    <code className="min-w-0 font-mono text-[13px] break-all text-brand-ink">{e}</code>
                    <span className="text-[12.5px] whitespace-nowrap text-ink-faint tabular-nums">{cited[e] ? `${cited[e]} sitasi` : "dibaca"}</span>
                  </li>
                ))}
              </ul>
            ) : <Empty>Tidak ada endpoint tercatat.</Empty>}
          </Section>

          <Section id="temuan" title={LABEL.temuan} count={research.insights.length || undefined}>
            {research.insights.length ? (
              <div className="grid divide-y divide-rule-soft">
                {research.insights.map((insight, i) => (
                  <article key={i} className="grid gap-2.5 py-4 first:pt-0 last:pb-0">
                    <h4 className="text-[16px]">{insight.title || "Temuan"}</h4>
                    <dl className="m-0 grid gap-x-5 gap-y-1.5 text-[15px] sm:grid-cols-[104px_minmax(0,1fr)]">
                      {insight.observation && <><dt className="text-[13.5px] font-medium text-ink-soft sm:pt-px">Observasi</dt><dd className="m-0">{insight.observation}</dd></>}
                      {insight.implication && <><dt className="text-[13.5px] font-medium text-ink-soft sm:pt-px">Implikasi</dt><dd className="m-0">{insight.implication}</dd></>}
                      {insight.caveat && <><dt className="text-[13.5px] font-medium text-ink-soft sm:pt-px">Batas bukti</dt><dd className="m-0 text-ink-soft">{insight.caveat}</dd></>}
                    </dl>
                    {insight.citations.length > 0 && (
                      <ul aria-label="Sitasi" className="m-0 grid list-none divide-y divide-rule-soft rounded-md border border-rule bg-raised p-0">
                        {insight.citations.map((c, j) => (
                          <li key={j} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 px-3 py-2 font-mono text-[12.5px]">
                            <span className="min-w-0 break-all">
                              {c.endpoint ? <a href={`#${epId(c.endpoint)}`} className="text-brand-ink">{c.endpoint}</a> : <span className="text-ink-faint">endpoint tidak tercatat</span>}
                              <ChevronRight aria-hidden className="mx-1 inline size-3 align-[-1px] text-ink-faint" strokeWidth={2.2} />
                              <span className="sr-only">field </span><span className="text-ink">{c.field_path}</span>
                            </span>
                            <span className="font-semibold text-ink-strong tabular-nums"><span className="sr-only">nilai </span>{c.value}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </div>
            ) : <Empty>Belum ada temuan yang lolos validasi sitasi.</Empty>}
          </Section>

          {research.limitations.length > 0 && (
            <Section id="kurang" title={LABEL.kurang} count={research.limitations.length}>
              <ul className="m-0 grid gap-1.5 pl-[18px] text-[15px]">{research.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </Section>
          )}
        </AgentGroup>

        <AgentGroup agent="berita" status={searched ? "ok" : "warn"}
          chip={<StatusWord status={searched ? "ok" : "idle"}>{searched ? "Pencarian dijalankan" : "Pencarian tidak dijalankan"}</StatusWord>}>
          <Section id="berita" title={LABEL.berita}
            aside={<span className="text-[13px] text-ink-soft tabular-nums">{news.articles.length} diterima, {news.rejected_total} ditolak</span>}>
            <p className="text-[14.5px] text-ink-soft">
              Status pencarian: <code className="font-mono text-[13px] text-ink">{news.search.status ?? "tidak dijalankan"}</code>
              {news.search.as_of && <>, per <span className="font-mono text-ink">{news.search.as_of}</span></>}.
            </p>
            {news.search.queries.length > 0 && (
              <div className="mt-4">
                <SubHead>Kueri</SubHead>
                <ul className="m-0 grid list-none divide-y divide-rule-soft rounded-md border border-rule bg-raised p-0">
                  {news.search.queries.map((q, i) => (
                    <li key={i} className="flex items-start gap-2.5 px-3 py-2 font-mono text-[12.5px] break-words text-ink">
                      <Search aria-hidden className="mt-[3px] size-3.5 flex-none text-ink-faint" strokeWidth={2.2} />
                      <span className="min-w-0">{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {news.articles.length > 0 && (
              <div className="mt-5">
                <SubHead>Artikel diterima <span className="data text-ink-faint">{news.articles.length}</span></SubHead>
                <ol className="m-0 grid list-none divide-y divide-rule-soft p-0 text-[14.5px]">
                  {news.articles.map((a, i) => (
                    <li key={a.id ?? i} className="grid gap-x-4 gap-y-0.5 py-2 first:pt-0 sm:grid-cols-[96px_minmax(0,1fr)]">
                      <time dateTime={a.date ?? undefined} title={a.date ?? undefined} className="data pt-[3px] text-ink-soft">{a.date?.slice(0, 10)}</time>
                      <span className="min-w-0">
                        {a.url ? <Source url={a.url}>{a.title}</Source> : a.title}
                        {a.origins.map((o) => <span key={o} className="ml-2 font-mono text-[12px] text-ink-faint">{o}</span>)}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {news.rejected.length > 0 && (
              <details className="group mt-5 rounded-md border border-rule">
                <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-3 py-2.5 text-[14.5px] font-medium text-ink-strong hover:bg-raised [&::-webkit-details-marker]:hidden">
                  <ChevronRight aria-hidden className="size-4 flex-none text-ink-soft transition-transform duration-200 group-open:rotate-90" strokeWidth={2.2} />
                  {news.rejected_total} berita ditolak (tidak relevan atau dampak nol)
                </summary>
                <ol className="m-0 grid list-none divide-y divide-rule-soft border-t border-rule p-0 text-[14px]">
                  {news.rejected.map((r, i) => (
                    <li key={i} className="px-3 py-2">
                      {r.title}
                      {r.reason && <span className="mt-0.5 block text-[13px] text-ink-soft">{r.reason}</span>}
                    </li>
                  ))}
                  {news.rejected_total > news.rejected.length && (
                    <li className="px-3 py-2 text-ink-soft">dan {news.rejected_total - news.rejected.length} penolakan lain</li>
                  )}
                </ol>
              </details>
            )}
          </Section>

          <Section id="deep-dive" title={LABEL["deep-dive"]}
            aside={trace.deepdive.length > 0 && <span className="text-[13px] text-ink-soft tabular-nums">{fetched} dari {trace.deepdive.length} teks terbaca</span>}>
            {trace.deepdive.length ? (
              <div className="grid divide-y divide-rule-soft">
                {trace.deepdive.map((item, i) => {
                  const ok = item.status === "fetched";
                  return (
                    <article key={i} className="grid gap-1.5 py-3.5 first:pt-0 last:pb-0">
                      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                        <h4 className="min-w-0 flex-1 basis-[260px] text-[15px] font-medium">{item.title || "(tanpa judul)"}</h4>
                        <Chip tone={ok ? "ok" : "neutral"}>{ok ? "Teks terbaca" : "Teks tidak terbaca"}</Chip>
                      </div>
                      <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[12px] text-ink-soft">
                        {item.date && <span>{item.date}</span>}
                        {item.url && <Source url={item.url} />}
                        <span>status {item.status}</span>
                        <span>{item.length} karakter</span>
                      </p>
                      {item.preview ? (
                        <p className="mt-1 rounded-md border border-rule-soft bg-raised px-3.5 py-2.5 text-[14px] leading-relaxed whitespace-pre-line text-ink">{item.preview}</p>
                      ) : (
                        <p className="text-[13.5px] text-ink-soft">Teks lengkap tidak tersedia; ringkasan berita hanya untuk konteks.</p>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : <Empty>Belum ada hasil deep-dive berita.</Empty>}
          </Section>
        </AgentGroup>

        <AgentGroup agent="forecast" status={fStatus}
          chip={<StatusWord status={fStatus}>{fLabel}</StatusWord>}>
          <Problems title="Catatan validator forecast" items={forecast.problems} />
          <Section id="asumsi" title={LABEL.asumsi} count={forecast.news_effects.length || undefined}>
            {forecast.news_effects.length ? (
              <div className="grid divide-y divide-rule-soft">
                {forecast.news_effects.map((e, i) => (
                  <article key={i} className="grid gap-2 py-4 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                      {isNoEffect(e)
                        ? <strong className="text-[15px] font-medium text-ink-strong">Tanpa dampak terukur ke forecast</strong>
                        : <strong className="font-mono text-[14px] font-semibold text-brand-ink">{e.driver}: {e.change}</strong>}
                      {e.years.map((y) => <Chip key={y} mono>{y}</Chip>)}
                      <span className="ml-auto flex items-center gap-3 font-mono text-[12px] text-ink-soft">
                        {e.date}{e.url && <Source url={e.url} />}
                      </span>
                    </div>
                    {e.rationale && <p className="text-[15px]">{e.rationale}</p>}
                    {(e.factual_basis || e.mechanism || e.uncertainty) && (
                      <dl className="m-0 grid gap-x-6 gap-y-2.5 text-[14px] text-ink xl:grid-cols-3">
                        {([["Fakta", e.factual_basis], ["Mekanisme", e.mechanism], ["Ketidakpastian", e.uncertainty]] as const).map(([k, v]) => v && (
                          <div key={k} className="min-w-0 border-t border-rule-soft pt-2">
                            <dt className="text-[12.5px] font-medium text-ink-soft">{k}</dt>
                            <dd className="m-0">{v}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </article>
                ))}
              </div>
            ) : <Empty>Subagent dampak berita tidak mencatat dampak.</Empty>}
          </Section>

          {forecast.interim && (
            <Section id="interim" title={LABEL.interim}>
              <p className="max-w-[80ch] text-[15px]">{forecast.interim.rationale}</p>
              <p className="mt-2 flex flex-wrap items-center gap-3 font-mono text-[12px] text-ink-soft">
                {forecast.interim.published_at && <span>Rilis {forecast.interim.published_at}</span>}
                <Source url={forecast.interim.url} />
              </p>
            </Section>
          )}

          {forecast.outyears.length > 0 && (
            <Section id="tahun-lanjutan" title={LABEL["tahun-lanjutan"]} count={forecast.outyears.length}>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[14px]">
                  <thead>
                    <tr className="text-[12.5px] text-ink-soft [&>th]:px-2 [&>th]:pb-2 [&>th]:align-bottom [&>th]:font-medium">
                      <th scope="col" className="text-left">Tahun</th>
                      <th scope="col" className="text-right">Pertumbuhan revenue</th>
                      <th scope="col" className="text-right">Margin EBITDA</th>
                      <th scope="col" className="text-right">Margin laba</th>
                      <th scope="col" className="text-right">Capex/revenue</th>
                    </tr>
                  </thead>
                  {forecast.outyears.map((row, i) => (
                    <tbody key={row.year ?? i} className="border-t border-rule">
                      <tr className="[&>td]:px-2 [&>td]:pt-2.5 [&>td]:pb-1">
                        <th scope="row" className="px-2 pt-2.5 pb-1 text-left font-mono font-semibold text-ink-strong">{row.year}</th>
                        {[row.revenue_growth_pct, row.ebitda_margin_pct, row.net_income_margin_pct, row.capex_to_revenue_pct].map((v, j) => (
                          <td key={j} className={`text-right font-mono whitespace-nowrap tabular-nums ${v == null ? "text-ink-faint" : "text-ink-strong"}`}>{pctOf(v)}</td>
                        ))}
                      </tr>
                      <tr>
                        <td colSpan={5} className="px-2 pb-3 text-[13.5px] text-ink-soft">
                          <span className="sr-only">Dasar: </span>{row.rationale}
                          {row.source_ids.length > 0 && (
                            <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                              {row.source_ids.map((s) => <Chip key={s} mono>{s}</Chip>)}
                            </span>
                          )}
                        </td>
                      </tr>
                    </tbody>
                  ))}
                </table>
              </div>
            </Section>
          )}
          {(forecast.bank_drivers?.length ?? 0) > 0 && (
            <Section id="driver-bank" title={LABEL["driver-bank"]} count={forecast.bank_drivers!.length}>
              <p className="mb-3 max-w-[80ch] text-[14px] text-ink-soft">
                Driver model bank per tahun: tahun berjalan memakai aktual 1H resmi ditambah driver H2; tahun berikutnya setahun penuh.
                Neraca, laba dan dividen dihitung model dari driver ini, dengan batas modal dan pendanaan.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-[14px]">
                  <thead>
                    <tr className="text-[12.5px] text-ink-soft [&>th]:px-2 [&>th]:pb-2 [&>th]:align-bottom [&>th]:font-medium">
                      <th scope="col" className="text-left">Tahun</th>
                      {BANK_COLS.map(([key, label]) => <th key={key} scope="col" className="text-right">{label}</th>)}
                    </tr>
                  </thead>
                  {forecast.bank_drivers!.map((row, i) => (
                    <tbody key={row.year ?? i} className="border-t border-rule">
                      <tr className="[&>td]:px-2 [&>td]:pt-2.5 [&>td]:pb-1">
                        <th scope="row" className="px-2 pt-2.5 pb-1 text-left font-mono font-semibold text-ink-strong">
                          {row.year}{i === 0 && <span className="ml-1.5 font-sans text-[12px] font-normal text-ink-soft">H2</span>}
                        </th>
                        {BANK_COLS.map(([key]) => {
                          const v = row[key] as number | null;
                          return <td key={key} className={`text-right font-mono whitespace-nowrap tabular-nums ${v == null ? "text-ink-faint" : "text-ink-strong"}`}>{pctOf(v)}</td>;
                        })}
                      </tr>
                      {row.rationale && (
                        <tr>
                          <td colSpan={BANK_COLS.length + 1} className="px-2 pb-3 text-[13.5px] text-ink-soft">
                            {/* The table scrolls sideways on phones; the rationale stays in view and wraps to it. */}
                            <div className="sticky left-2 max-w-[min(80ch,calc(100vw-72px))]">
                              <span className="sr-only">Dasar: </span>{row.rationale}
                              {row.source_ids.length > 0 && (
                                <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                                  {row.source_ids.map((s) => <Chip key={s} mono>{s}</Chip>)}
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  ))}
                </table>
              </div>
            </Section>
          )}
        </AgentGroup>

        {(trace.audit_appendix?.length ?? 0) > 0 && <AuditAppendix pages={trace.audit_appendix!} />}

        <p className="text-[13px] text-ink-soft">Materi informasi dan analisis; bukan rekomendasi investasi.</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

/** Report sections kept out of the printed company update, shown here for audit. */
function AuditAppendix({ pages }: { pages: NonNullable<TraceView["audit_appendix"]> }) {
  return (
    <section id="lampiran-audit" aria-labelledby="lampiran-audit-title" className="panel scroll-mt-20">
      <header className="px-6 py-5 max-sm:px-4">
        <h2 id="lampiran-audit-title" className="text-[20px]">Lampiran audit</h2>
        <p className="text-[14px] text-ink-soft">
          Bagian rekonstruksi dan uji rekonsiliasi yang tidak dicetak di company update karena hampir tidak menggerakkan target.
          Angkanya sama dengan yang dihitung saat laporan dibangun.
        </p>
      </header>
      <div className="border-t border-rule">
        {pages.map((page, i) => (
          <details key={`${page.title}-${i}`} className="group border-b border-rule-soft last:border-b-0">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-6 py-3 text-[15px] font-medium text-ink-strong max-sm:px-4">
              <span>{page.title}</span>
              <span className="data text-ink-soft">{page.exhibits.length} tabel</span>
            </summary>
            <div className="grid gap-4 px-6 pb-5 max-sm:px-4 [&>*]:min-w-0">
              {page.paragraphs.map((text, j) => <p key={j} className="max-w-[80ch] text-[14.5px] text-ink">{text}</p>)}
              {page.exhibits.map((e, j) => (
                <figure key={j} className="m-0">
                  <figcaption className="mb-2 text-[14px] font-semibold text-ink-strong">{e.title}</figcaption>
                  <div className="overflow-x-auto rounded-md border border-rule">
                    <table className="w-full border-collapse text-[13.5px]">
                      {e.cols.length > 0 && (
                        <thead>
                          <tr className="bg-raised text-left text-[12.5px] text-ink-soft">
                            {e.cols.map((c, k) => <th key={k} scope="col" className={`px-3 py-2 font-medium ${k ? "text-right" : ""}`}>{c}</th>)}
                          </tr>
                        </thead>
                      )}
                      <tbody>
                        {e.rows.map((row, r) => (
                          <tr key={r} className="border-t border-rule-soft align-top">
                            {row.map((c, k) => <td key={k} className={`px-3 py-1.5 ${k ? "text-right font-mono tabular-nums" : "text-ink"}`}>{c}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {e.note && <p className="mt-1.5 max-w-[90ch] text-[12.5px] text-ink-soft">{e.note}</p>}
                </figure>
              ))}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

export function ReportTrace() {
  const { ticker = "" } = useParams();
  const T = ticker.toUpperCase();
  const state = useLoad(() => api.reportTrace(T), [T]);
  // The gallery entry and the stored run are optional context: the trace renders without them.
  const reports = useLoad(() => api.reports().catch(() => [] as ReportItem[]), []);
  const run = useLoad(() => api.reportRun(T).catch(() => undefined), [T]);
  const item = reports.data?.find((r) => r.ticker === T);
  const files = reportFiles(T);
  return (
    <TracePage state={state} item={item} run={run.data ?? undefined} missing={`Jejak riset ${T} tidak ditemukan.`}
      links={{ reportUrl: files.html, pdfUrl: item?.files.pdf ? files.pdf : undefined, replayUrl: `/laporan/${T}/putar` }}
      review={<ReviewPanel ticker={T} onApproved={() => { state.reload(); reports.reload(); }} />} />
  );
}

export function JobTrace() {
  const { id = "" } = useParams();
  const state = useLoad(() => api.jobTrace(id), [id]);
  const ticker = state.data?.ticker ?? "";
  return (
    <TracePage state={state} missing="Jejak riset ini tidak ditemukan. Riset yang berjalan di server hanya disimpan selama server hidup."
      links={{ reportUrl: `/files/jobs/${id}/${ticker}.html`, deckUrl: `/jobs/${id}` }} />
  );
}

function TracePage({ state, item, run, links, missing, review }:
  { state: ReturnType<typeof useLoad<TraceView>>; item?: ReportItem; run?: RunReplay; links: Links; missing: string;
    review?: React.ReactNode }) {
  if (state.data) {
    return (
      <div className="min-h-full bg-canvas">
        <TraceHeader trace={state.data} item={item} run={run} links={links} />
        {review && <div className="wrap pt-6">{review}</div>}
        <TraceBody trace={state.data} />
      </div>
    );
  }
  return (
    <div className="wrap py-10 max-sm:py-6">
      {state.loading && (
        <div role="status" className="grid gap-5">
          <span className="sr-only">Memuat jejak riset…</span>
          <span aria-hidden className="h-4 w-40 animate-pulse rounded bg-raised" />
          <span aria-hidden className="h-9 w-72 animate-pulse rounded bg-raised" />
          <span aria-hidden className="h-24 w-full animate-pulse rounded-md bg-surface ring-1 ring-rule" />
          <span aria-hidden className="h-64 w-full animate-pulse rounded-lg bg-surface ring-1 ring-rule" />
        </div>
      )}
      {state.error && (
        <Notice tone={state.status === 404 ? "muted" : "error"}>
          {state.status === 404 ? (
            <>
              <p><strong className="text-ink-strong">{missing}</strong> Buka jejak dari galeri laporan atau dari deck riset.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link className="btn btn-sm btn-ghost" to="/laporan">Buka galeri laporan</Link>
                <Link className="btn btn-sm btn-ghost" to="/research">Mulai riset</Link>
              </div>
            </>
          ) : (
            <>
              <p><strong>Jejak riset belum bisa dimuat.</strong> Server API tidak menjawab ({state.error}).</p>
              <button type="button" onClick={state.reload} className="btn btn-sm btn-ghost mt-3">
                <RefreshCw aria-hidden className="size-3.5" strokeWidth={2.2} />Coba lagi
              </button>
            </>
          )}
        </Notice>
      )}
    </div>
  );
}
