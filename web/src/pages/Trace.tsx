import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { ArrowLeft, ChevronRight, FileDown, FileText, Play, RefreshCw, Search, TriangleAlert } from "lucide-react";
import { api, ApiError, readerFiles, reportFiles, type ProblemNote, type ReportItem, type RunReplay, type TraceView } from "../lib/api";
import { rp } from "../lib/format";
import { LOCALE, twin, useLang, type Bi } from "../lib/i18n";
import { problemNotes, validatorNote } from "../lib/labels";
import { AGENT, derive, type AgentId, type Status } from "../lib/agents";
import { LiveMark } from "../components/Mark";
import {
  Chip, Empty, INTEL_SECTIONS, IntelHeadline, IntelSections, Section, Source, StatusWord, SubHead, type ChipTone,
} from "../components/Intel";
import { MethodChain, RatingBadge, signedPct } from "../components/Reports";
import { Notice, useLoad } from "../components/State";
import { ReviewPanel, keepReviewToken, readReviewToken } from "../components/Review";
import { IssuerLogo } from "../components/IssuerLogo";

/* ------------------------------------------------------------------ */
/* The index: the trace's table of contents, grouped by the agent that */
/* produced each part. Only sections present on the page are listed.  */

type IndexGroup = { agent: AgentId; sections: [string, Bi][] };

const RESEARCH: [string, Bi][] = [
  ["ringkasan", { id: "Ringkasan brief", en: "Brief summary" }],
  ["endpoint", { id: "Endpoint yang dibaca", en: "Endpoints read" }],
  ["temuan", { id: "Temuan bersitasi", en: "Cited findings" }],
  ["kurang", { id: "Bukti yang masih kurang", en: "Missing evidence" }],
];
const NEWS: [string, Bi][] = [
  ["berita", { id: "Pencarian berita", en: "News search" }],
  ["deep-dive", { id: "Deep-dive berita", en: "News deep-dive" }],
];
const FORECAST: [string, Bi][] = [
  ["asumsi", { id: "Dampak berita", en: "News impact" }],
  ["interim", { id: "Skenario interim", en: "Interim scenario" }],
  ["tahun-lanjutan", { id: "Tahun lanjutan", en: "Out-years" }],
  ["driver-bank", { id: "Driver bank", en: "Bank drivers" }],
  ["katalis", { id: "Katalis", en: "Catalysts" }],
  ["risiko", { id: "Risiko utama", en: "Key risks" }],
];
/** A catalyst's direction code, as the forecast agent writes it, in tone. */
const DIRECTION_TONE: Record<string, ChipTone> = { Positif: "ok", Negatif: "err", "Dua arah": "neutral" };
const BANK_COLS: [keyof NonNullable<TraceView["forecast"]["bank_drivers"]>[number], Bi][] = [
  ["loan_growth_pct", { id: "Pertumbuhan kredit", en: "Loan growth" }],
  ["nim_pct", { id: "NIM", en: "NIM" }],
  ["non_ii_to_nii_pct", { id: "Non-bunga / NII", en: "Non-interest / NII" }],
  ["cost_to_income_pct", { id: "Biaya / pendapatan", en: "Cost / income" }],
  ["cost_of_credit_pct", { id: "Biaya kredit", en: "Cost of credit" }],
  ["deposit_growth_pct", { id: "Pertumbuhan DPK", en: "Deposit growth" }],
];
const LABEL: Record<string, Bi> = Object.fromEntries([...RESEARCH, ...NEWS, ...FORECAST]);

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
  const { t } = useLang();
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
  const flat = present.flatMap((g): [string, string][] =>
    g.sections.length ? g.sections.map(([id, label]) => [id, t(label)]) : [[groupId(g.agent), t(AGENT[g.agent].name)]]);
  const navLabel = t({ id: "Bagian jejak riset", en: "Audit Trace sections" });

  return (
    <>
      <nav aria-label={navLabel} className="sticky top-[76px] max-h-[calc(100vh-96px)] min-w-0 overflow-y-auto pb-6 max-lg:hidden">
        <ol className="m-0 grid list-none gap-4 p-0">
          {present.map((g) => (
            <li key={g.agent}>
              <a href={`#${groupId(g.agent)}`} aria-current={current === groupId(g.agent) ? "location" : undefined}
                className="mb-1 flex items-center gap-2 text-[13px] font-semibold text-ink-strong no-underline hover:text-brand-ink">
                <LiveMark status="ok" className="h-2.5 w-3" />{t(AGENT[g.agent].name)}
              </a>
              <ul className="m-0 grid list-none border-l border-rule p-0">
                {g.sections.map(([id, label]) => {
                  const on = current === id;
                  return (
                    <li key={id} className="relative">
                      {on && <motion.span layoutId="trace-index" aria-hidden className="absolute inset-y-0 -left-px w-[2px] rounded-full bg-brand-ink" transition={spring} />}
                      <a href={`#${id}`} aria-current={on ? "location" : undefined}
                        className={`block py-1 pl-3 text-[13.5px] leading-snug no-underline transition-colors ${on ? "font-medium text-ink-strong" : "text-ink-soft hover:text-ink-strong"}`}>
                        {t(label)}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      </nav>

      <nav aria-label={navLabel} className="sticky top-[52px] z-30 -mx-6 min-w-0 border-b border-rule bg-surface max-sm:-mx-4 lg:hidden">
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
  const { t } = useLang();
  const meta = AGENT[agent];
  const id = groupId(agent);
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="panel scroll-mt-20 max-lg:scroll-mt-[108px]">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-6 py-5 max-sm:px-4">
        <div className="flex min-w-0 items-start gap-3">
          <LiveMark status={status === "warn" ? "warn" : status === "error" ? "error" : "ok"} className="mt-[9px] h-3 w-3.5 flex-none" />
          <div className="min-w-0">
            <h2 id={`${id}-title`} className="text-[20px]">{t(meta.name)}</h2>
            <p className="text-[14px] text-ink-soft">{t(meta.role)}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="dashed">{meta.engine === "llm" ? t({ id: "Diputuskan model", en: "Model-decided" }) : t({ id: "Kode deterministik", en: "Deterministic code" })}</Chip>
          {chip}
        </div>
      </header>
      {children}
    </section>
  );
}

/** Validator notes (rejected drafts, failed calls) kept visible at the top of an agent's panel. */
function Problems({ title, items }: { title: string; items: ProblemNote[] }) {
  const { t } = useLang();
  if (!items.length) return null;
  return (
    <div className="border-t border-rule px-6 py-4 max-sm:px-4">
      <div className="rounded-md border border-warn-rule/60 bg-warn-bg/40 px-4 py-3">
        <p className="flex items-center gap-2 text-[13.5px] font-medium text-warn-ink">
          <TriangleAlert aria-hidden className="size-3.5 flex-none" strokeWidth={2.2} />{title} <span className="data">{items.length}</span>
        </p>
        <ul className="mt-1.5 grid gap-1.5 pl-[22px] text-[13.5px] leading-relaxed break-words text-ink">
          {items.map(({ message, removed }, i) => {
            return (
              <li key={i}>
                {message}{/[.!?]$/.test(message) ? "" : "."}
                {removed.length > 0 && (
                  <span className="ml-1 text-ink-soft">
                    {t({ id: "Dihapus dari prosa:", en: "Removed from prose:" })}{" "}
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

const pctCell: Bi<Intl.NumberFormat> = {
  id: new Intl.NumberFormat(LOCALE.id, { maximumFractionDigits: 1 }),
  en: new Intl.NumberFormat(LOCALE.en, { maximumFractionDigits: 1 }),
};
const pctOf = (v: number | null, cell: Intl.NumberFormat) => (v == null ? "n.a." : `${cell.format(v).replace("-", "−")}%`);

const RELEASE: Record<string, [Bi, ChipTone]> = {
  production_ready: [{ id: "Siap produksi", en: "Production-ready" }, "ok"],
  distributable_assumption_led: [{ id: "Terbit, berbasis asumsi analis", en: "Published, analyst-assumption led" }, "brand"],
  draft_non_distributable: [{ id: "Draft, belum didistribusikan", en: "Draft, not distributed" }, "warn"],
};

function forecastStatus(status: string | null): [Bi, Status] {
  if (status === "validated") return [{ id: "Tervalidasi", en: "Validated" }, "ok"];
  if (status === "partial") return [{ id: "Parsial", en: "Partial" }, "warn"];
  if (status) return [{ id: `Status ${status}`, en: `Status ${status}` }, "warn"];
  return [{ id: "Status tidak tercatat", en: "Status not recorded" }, "idle"];
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
  const { t, lang } = useLang();
  const { report } = trace;
  const awaiting = trace.review_state === "pending" && (report.release_status ?? "").startsWith("distributable");
  const [label, tone] = awaiting ? [t({ id: "Lolos gerbang, menunggu review analis", en: "Passed the gates, awaiting analyst review" }), "warn" as ChipTone]
    : RELEASE[report.release_status ?? ""]
      ? [t(RELEASE[report.release_status!][0]), RELEASE[report.release_status!][1]]
      : [report.release_status ? report.release_status : t({ id: "Status belum tercatat", en: "Status not recorded" }), "neutral" as ChipTone];
  const counts = useMemo(() => (run?.events.length ? derive(run.events, { finished: true }).counts : null), [run]);
  const cell = "min-w-0 bg-surface px-4 py-3";
  const dt = "mb-1 text-[12px] text-ink-soft";
  return (
    <div className="mt-6 grid gap-3">
      <dl className="m-0 grid grid-cols-6 gap-px overflow-clip rounded-md border border-rule bg-rule xl:grid-cols-[1.3fr_auto_auto_auto_2fr_auto_auto]">
        <div className={`${cell} col-span-6 sm:col-span-3 xl:col-span-1`}>
          <dt className={dt}>{t({ id: "Status rilis", en: "Release status" })}</dt>
          <dd className="m-0 grid gap-1">
            <span><Chip tone={tone}>{label}</Chip></span>
            {report.release_status && <code className="font-mono text-[11.5px] break-all text-ink-faint">{report.release_status}</code>}
          </dd>
        </div>
        <div className={`${cell} col-span-2 sm:col-span-1`}>
          <dt className={dt}>Rating</dt>
          <dd className="m-0"><RatingBadge item={{
            rating: report.published ? report.rating : null,
            held_reason: item?.held_reason ?? "",
            release_status: "",
            publication_state: item?.publication_state ?? (report.published ? "published" : "review_pending"),
          }} /></dd>
        </div>
        <div className={`${cell} col-span-2 sm:col-span-1`}>
          <dt className={dt}>{t({ id: "Target harga", en: "Target price" })}</dt>
          <dd className="m-0 font-mono text-[15px] font-semibold tabular-nums text-ink-strong">{report.published ? `Rp${rp(report.target_price)}` : t({ id: "Ditahan", en: "Withheld" })}</dd>
        </div>
        <div className={`${cell} col-span-2 sm:col-span-1`}>
          <dt className={dt}>{t({ id: "Potensi", en: "Upside" })}</dt>
          <dd className={`m-0 font-mono text-[15px] font-semibold tabular-nums ${item?.upside == null ? "text-ink-soft" : item.upside < 0 ? "text-err-ink" : "text-ok-ink"}`}>
            {item ? signedPct(item.upside) : "—"}
          </dd>
        </div>
        <div className={`${cell} col-span-6 sm:col-span-4 xl:col-span-1`}>
          <dt className={dt}>{t({ id: "Metode", en: "Method" })}</dt>
          <dd className="m-0 text-[14px] leading-snug text-ink">{twin(report, "method", lang) || t({ id: "Belum tercatat", en: "Not recorded" })}</dd>
        </div>
        <div className={`${cell} col-span-3 sm:col-span-1`}>
          <dt className={dt}>{t({ id: "Data per", en: "Data as of" })}</dt>
          <dd className="m-0 font-mono text-[13.5px] text-ink-strong">{report.as_of ?? "—"}</dd>
        </div>
        <div className={`${cell} col-span-3 sm:col-span-1`}>
          <dt className={dt}>{t({ id: "Harga pasar per", en: "Market price as of" })}</dt>
          <dd className="m-0 font-mono text-[13.5px] text-ink-strong">{report.market_price_date ?? "—"}</dd>
        </div>
      </dl>
      {(item?.chain.length || counts) && (
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          {item?.chain.length ? <MethodChain chain={item.chain} /> : <span />}
          {counts && (
            <p className="text-[13px] text-ink-soft tabular-nums">
              {run?.source === "recorded"
                ? t({ id: "Run terekam", en: "Recorded run" })
                : t({ id: "Run disusun ulang dari jejak", en: "Run rebuilt from the Audit Trace" })}
              : {counts.events} {t({ id: "event", en: counts.events === 1 ? "event" : "events" })},{" "}
              {counts.calls} {t({ id: "tool call", en: counts.calls === 1 ? "tool call" : "tool calls" })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function TraceHeader({ trace, item, run, links }: { trace: TraceView; item?: ReportItem; run?: RunReplay; links: Links }) {
  const { t } = useLang();
  const name = item?.name ?? trace.analyst?.name;
  return (
    <header className="border-b border-rule bg-surface">
      <div className="wrap pt-5 pb-6">
        <nav aria-label={t({ id: "Remah roti", en: "Breadcrumb" })} className="mb-4 text-[13px] text-ink-soft">
          <ol className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0">
            <li><Link to="/laporan" className="text-ink-soft no-underline hover:text-brand-ink hover:underline">{t({ id: "Laporan", en: "Reports" })}</Link></li>
            <li aria-hidden><ChevronRight className="size-3.5 text-ink-faint" strokeWidth={2.2} /></li>
            <li className="font-mono">{trace.ticker}</li>
            <li aria-hidden><ChevronRight className="size-3.5 text-ink-faint" strokeWidth={2.2} /></li>
            <li aria-current="page" className="text-ink">{t({ id: "Jejak riset", en: "Audit Trace" })}</li>
          </ol>
        </nav>
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
          <div className="flex min-w-0 items-center gap-4">
            <IssuerLogo ticker={trace.ticker} size="lg" className="max-sm:hidden" />
            <div className="min-w-0">
              <h1 className="text-[clamp(26px,3vw,36px)] font-black tracking-[-.02em]">
                {t({ id: "Jejak riset", en: "Audit Trace" })} <span className="font-mono tracking-[.02em] text-brand-ink">{trace.ticker}</span>
              </h1>
              {name && <p className="mt-1 text-[15.5px] text-ink-soft">{name}</p>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2.5 max-sm:grid max-sm:w-full max-sm:grid-cols-2 max-sm:[&>*:first-child]:col-span-2 max-sm:[&>*:nth-child(2):last-child]:col-span-2">
            {links.replayUrl && (
              <Link className="btn btn-primary" to={links.replayUrl}>
                <Play aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Putar ulang run", en: "Replay run" })}
              </Link>
            )}
            <a className={`btn ${links.replayUrl ? "btn-ghost" : "btn-primary"}`} href={links.reportUrl}>
              <FileText aria-hidden className="size-4" strokeWidth={2.2} />
              <span className="max-sm:hidden">{t({ id: "Buka company update", en: "Open Company Update" })}</span>
              <span className="sm:hidden">{t({ id: "Buka laporan", en: "Open report" })}</span>
            </a>
            {links.deckUrl && (
              <Link className="btn btn-ghost" to={links.deckUrl}>
                <ArrowLeft aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Kembali ke deck", en: "Back to deck" })}
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
  const { t, locale, lang } = useLang();
  const { research, news, forecast } = trace;
  const index = useSectionIndex();
  const cell = pctCell[lang];
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
          chip={analyst ? <StatusWord status={analyst.status === "ok" ? "ok" : "warn"}>
            {analyst.status === "ok" ? t({ id: "Selesai", en: "Done" }) : t({ id: "Parsial", en: "Partial" })}
          </StatusWord>
            : <StatusWord status="idle">{t({ id: "Tidak dijalankan", en: "Not run" })}</StatusWord>}>
          {analyst ? (
            <>
              <div className="border-t border-rule px-6 py-5 max-sm:px-4"><IntelHeadline intel={analyst} as="p" /></div>
              <Problems title={t({ id: "Catatan validator", en: "Validator notes" })}
                items={problemNotes(trace.analyst_problem_notes, trace.analyst_problems, trace.analyst_problems_en, lang)} />
              <IntelSections intel={analyst} />
            </>
          ) : (
            <div className="border-t border-rule px-6 py-5 max-sm:px-4">
              <Empty>{twin(trace, "analyst_problems", lang).join("; ") || t({ id: "Agent analis tidak dijalankan untuk riset ini.", en: "The analyst agent was not run for this research." })}</Empty>
            </div>
          )}
        </AgentGroup>

        <AgentGroup agent="riset" status={research.summary ? "ok" : "warn"}
          chip={<StatusWord status={research.summary ? "ok" : "warn"}>{research.summary ? t({ id: "Brief tervalidasi", en: "Brief validated" }) : t({ id: "Brief belum tervalidasi", en: "Brief not yet validated" })}</StatusWord>}>
          <Section id="ringkasan" title={t(LABEL.ringkasan)}>
            {research.summary ? <p className="max-w-[80ch] text-[15.5px]">{twin(research, "summary", lang)}</p> : <Empty>{t({ id: "Belum ada brief tervalidasi.", en: "No validated brief yet." })}</Empty>}
          </Section>

          <Section id="endpoint" title={t(LABEL.endpoint)} count={research.endpoints.length}>
            {research.endpoints.length ? (
              <ul className="m-0 grid list-none divide-y divide-rule-soft rounded-md border border-rule p-0">
                {research.endpoints.map((e) => (
                  <li key={e} id={epId(e)} className="flex scroll-mt-28 items-center justify-between gap-3 rounded-[inherit] px-3 py-2 target:animate-hold">
                    <code className="min-w-0 font-mono text-[13px] break-all text-brand-ink">{e}</code>
                    <span className="text-[12.5px] whitespace-nowrap text-ink-faint tabular-nums">{cited[e]
                      ? t({ id: `${cited[e]} sitasi`, en: `${cited[e]} ${cited[e] === 1 ? "citation" : "citations"}` })
                      : t({ id: "dibaca", en: "read" })}</span>
                  </li>
                ))}
              </ul>
            ) : <Empty>{t({ id: "Tidak ada endpoint tercatat.", en: "No endpoints recorded." })}</Empty>}
          </Section>

          <Section id="temuan" title={t(LABEL.temuan)} count={research.insights.length || undefined}>
            {research.insights.length ? (
              <div className="grid divide-y divide-rule-soft">
                {research.insights.map((insight, i) => (
                  <article key={i} className="grid gap-2.5 py-4 first:pt-0 last:pb-0">
                    <h4 className="text-[16px]">{twin(insight, "title", lang) || t({ id: "Temuan", en: "Finding" })}</h4>
                    <dl className="m-0 grid gap-x-5 gap-y-1.5 text-[15px] sm:grid-cols-[104px_minmax(0,1fr)]">
                      {insight.observation && <><dt className="text-[13.5px] font-medium text-ink-soft sm:pt-px">{t({ id: "Observasi", en: "Observation" })}</dt><dd className="m-0">{twin(insight, "observation", lang)}</dd></>}
                      {insight.implication && <><dt className="text-[13.5px] font-medium text-ink-soft sm:pt-px">{t({ id: "Implikasi", en: "Implication" })}</dt><dd className="m-0">{twin(insight, "implication", lang)}</dd></>}
                      {insight.caveat && <><dt className="text-[13.5px] font-medium text-ink-soft sm:pt-px">{t({ id: "Batas bukti", en: "Evidence limit" })}</dt><dd className="m-0 text-ink-soft">{twin(insight, "caveat", lang)}</dd></>}
                    </dl>
                    {insight.citations.length > 0 && (
                      <ul aria-label={t({ id: "Sitasi", en: "Citations" })} className="m-0 grid list-none divide-y divide-rule-soft rounded-md border border-rule bg-raised p-0">
                        {insight.citations.map((c, j) => (
                          <li key={j} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 px-3 py-2 font-mono text-[12.5px]">
                            <span className="min-w-0 break-all">
                              {c.endpoint ? <a href={`#${epId(c.endpoint)}`} className="text-brand-ink">{c.endpoint}</a> : <span className="text-ink-faint">{t({ id: "endpoint tidak tercatat", en: "endpoint not recorded" })}</span>}
                              <ChevronRight aria-hidden className="mx-1 inline size-3 align-[-1px] text-ink-faint" strokeWidth={2.2} />
                              <span className="sr-only">field </span><span className="text-ink">{c.field_path}</span>
                            </span>
                            <span className="font-semibold text-ink-strong tabular-nums"><span className="sr-only">{t({ id: "nilai ", en: "value " })}</span>{c.value}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </div>
            ) : <Empty>{t({ id: "Belum ada temuan yang lolos validasi sitasi.", en: "No finding has passed citation validation yet." })}</Empty>}
          </Section>

          {research.limitations.length > 0 && (
            <Section id="kurang" title={t(LABEL.kurang)} count={research.limitations.length}>
              <ul className="m-0 grid gap-1.5 pl-[18px] text-[15px]">{twin(research, "limitations", lang).map((l, i) => <li key={i}>{l}</li>)}</ul>
            </Section>
          )}
        </AgentGroup>

        <AgentGroup agent="berita" status={searched ? "ok" : "warn"}
          chip={<StatusWord status={searched ? "ok" : "idle"}>{searched ? t({ id: "Pencarian dijalankan", en: "Search run" }) : t({ id: "Pencarian tidak dijalankan", en: "Search not run" })}</StatusWord>}>
          <Section id="berita" title={t(LABEL.berita)}
            aside={<span className="text-[13px] text-ink-soft tabular-nums">{t({
              id: `${news.articles.length} diterima, ${news.rejected_total} ditolak`,
              en: `${news.articles.length} accepted, ${news.rejected_total} rejected`,
            })}</span>}>
            <p className="text-[14.5px] text-ink-soft">
              {t({ id: "Status pencarian:", en: "Search status:" })}{" "}
              <code className="font-mono text-[13px] text-ink">{twin(news.search, "status", lang) ?? t({ id: "tidak dijalankan", en: "not run" })}</code>
              {news.search.as_of && <>, {t({ id: "per", en: "as of" })} <span className="font-mono text-ink">{news.search.as_of}</span></>}.
            </p>
            {news.search.queries.length > 0 && (
              <div className="mt-4">
                <SubHead>{t({ id: "Kueri", en: "Queries" })}</SubHead>
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
                <SubHead>{t({ id: "Artikel diterima", en: "Accepted articles" })} <span className="data text-ink-faint">{news.articles.length}</span></SubHead>
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
                  {t({
                    id: `${news.rejected_total} berita ditolak (tidak relevan atau dampak nol)`,
                    en: `${news.rejected_total} ${news.rejected_total === 1 ? "article" : "articles"} rejected (irrelevant or zero impact)`,
                  })}
                </summary>
                <ol className="m-0 grid list-none divide-y divide-rule-soft border-t border-rule p-0 text-[14px]">
                  {news.rejected.map((r, i) => (
                    <li key={i} className="px-3 py-2">
                      {r.title}
                      {r.reason && <span className="mt-0.5 block text-[13px] text-ink-soft">{twin(r, "reason", lang)}</span>}
                    </li>
                  ))}
                  {news.rejected_total > news.rejected.length && (
                    <li className="px-3 py-2 text-ink-soft">
                      {t({
                        id: `dan ${news.rejected_total - news.rejected.length} penolakan lain`,
                        en: `and ${news.rejected_total - news.rejected.length} more rejected`,
                      })}
                    </li>
                  )}
                </ol>
              </details>
            )}
          </Section>

          <Section id="deep-dive" title={t(LABEL["deep-dive"])}
            aside={trace.deepdive.length > 0 && <span className="text-[13px] text-ink-soft tabular-nums">
              {t({ id: `${fetched} dari ${trace.deepdive.length} teks terbaca`, en: `${fetched} of ${trace.deepdive.length} texts read` })}
            </span>}>
            {trace.deepdive.length ? (
              <div className="grid divide-y divide-rule-soft">
                {trace.deepdive.map((item, i) => {
                  const ok = item.status === "fetched";
                  return (
                    <article key={i} className="grid gap-1.5 py-3.5 first:pt-0 last:pb-0">
                      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                        <h4 className="min-w-0 flex-1 basis-[260px] text-[15px] font-medium">{item.title || t({ id: "(tanpa judul)", en: "(untitled)" })}</h4>
                        <Chip tone={ok ? "ok" : "neutral"}>{ok ? t({ id: "Teks terbaca", en: "Text read" }) : t({ id: "Teks tidak terbaca", en: "Text not read" })}</Chip>
                      </div>
                      <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[12px] text-ink-soft">
                        {item.date && <span>{item.date}</span>}
                        {item.url && <Source url={item.url} />}
                        <span>status {item.status}</span>
                        <span>{item.length.toLocaleString(locale)} {t({ id: "karakter", en: "characters" })}</span>
                      </p>
                      {item.preview ? (
                        <p className="mt-1 rounded-md border border-rule-soft bg-raised px-3.5 py-2.5 text-[14px] leading-relaxed whitespace-pre-line text-ink">{item.preview}</p>
                      ) : (
                        <p className="text-[13.5px] text-ink-soft">
                          {t({
                            id: "Teks lengkap tidak tersedia; ringkasan berita hanya untuk konteks.",
                            en: "Full text unavailable; the news summary is context only.",
                          })}
                        </p>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : <Empty>{t({ id: "Belum ada hasil deep-dive berita.", en: "No news deep-dive results yet." })}</Empty>}
          </Section>
        </AgentGroup>

        <AgentGroup agent="forecast" status={fStatus}
          chip={<StatusWord status={fStatus}>{t(fLabel)}</StatusWord>}>
          <Problems title={t({ id: "Catatan validator forecast", en: "Forecast validator notes" })} items={twin(forecast, "problems", lang).map(validatorNote)} />
          <Section id="asumsi" title={t(LABEL.asumsi)} count={forecast.news_effects.length || undefined}>
            {forecast.news_effects.length ? (
              <div className="grid divide-y divide-rule-soft">
                {forecast.news_effects.map((e, i) => (
                  <article key={i} className="grid gap-2 py-4 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                      {isNoEffect(e)
                        ? <strong className="text-[15px] font-medium text-ink-strong">
                          {t({ id: "Tanpa dampak terukur ke forecast", en: "No measurable effect on the forecast" })}
                        </strong>
                        : <strong className="font-mono text-[14px] font-semibold text-brand-ink">{e.driver}: {e.change}</strong>}
                      {e.years.map((y) => <Chip key={y} mono>{y}</Chip>)}
                      <span className="ml-auto flex items-center gap-3 font-mono text-[12px] text-ink-soft">
                        {e.date}{e.url && <Source url={e.url} />}
                      </span>
                    </div>
                    {e.rationale && <p className="text-[15px]">{twin(e, "rationale", lang)}</p>}
                    {(e.factual_basis || e.mechanism || e.uncertainty) && (
                      <dl className="m-0 grid gap-x-6 gap-y-2.5 text-[14px] text-ink xl:grid-cols-3">
                        {([
                          [{ id: "Fakta", en: "Fact" }, twin(e, "factual_basis", lang)],
                          [{ id: "Mekanisme", en: "Mechanism" }, twin(e, "mechanism", lang)],
                          [{ id: "Ketidakpastian", en: "Uncertainty" }, twin(e, "uncertainty", lang)],
                        ] as const).map(([k, v]) => v && (
                          <div key={k.id} className="min-w-0 border-t border-rule-soft pt-2">
                            <dt className="text-[12.5px] font-medium text-ink-soft">{t(k)}</dt>
                            <dd className="m-0">{v}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </article>
                ))}
              </div>
            ) : <Empty>{t({ id: "Subagent dampak berita tidak mencatat dampak.", en: "The news-impact subagent recorded no effect." })}</Empty>}
          </Section>

          {forecast.interim && (
            <Section id="interim" title={t(LABEL.interim)}>
              <p className="max-w-[80ch] text-[15px]">{twin(forecast.interim, "rationale", lang)}</p>
              <p className="mt-2 flex flex-wrap items-center gap-3 font-mono text-[12px] text-ink-soft">
                {forecast.interim.published_at && <span>{t({ id: "Rilis", en: "Released" })} {forecast.interim.published_at}</span>}
                <Source url={forecast.interim.url} />
              </p>
            </Section>
          )}

          {forecast.outyears.length > 0 && (
            <Section id="tahun-lanjutan" title={t(LABEL["tahun-lanjutan"])} count={forecast.outyears.length}>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[14px]">
                  <thead>
                    <tr className="text-[12.5px] text-ink-soft [&>th]:px-2 [&>th]:pb-2 [&>th]:align-bottom [&>th]:font-medium">
                      <th scope="col" className="text-left">{t({ id: "Tahun", en: "Year" })}</th>
                      <th scope="col" className="text-right">{t({ id: "Pertumbuhan revenue", en: "Revenue growth" })}</th>
                      <th scope="col" className="text-right">{t({ id: "Margin EBITDA", en: "EBITDA margin" })}</th>
                      <th scope="col" className="text-right">{t({ id: "Margin laba", en: "Net margin" })}</th>
                      <th scope="col" className="text-right">Capex/revenue</th>
                    </tr>
                  </thead>
                  {forecast.outyears.map((row, i) => (
                    <tbody key={row.year ?? i} className="border-t border-rule">
                      <tr className="[&>td]:px-2 [&>td]:pt-2.5 [&>td]:pb-1">
                        <th scope="row" className="px-2 pt-2.5 pb-1 text-left font-mono font-semibold text-ink-strong">{row.year}</th>
                        {[row.revenue_growth_pct, row.ebitda_margin_pct, row.net_income_margin_pct, row.capex_to_revenue_pct].map((v, j) => (
                          <td key={j} className={`text-right font-mono whitespace-nowrap tabular-nums ${v == null ? "text-ink-faint" : "text-ink-strong"}`}>{pctOf(v, cell)}</td>
                        ))}
                      </tr>
                      <tr>
                        <td colSpan={5} className="px-2 pb-3 text-[13.5px] text-ink-soft">
                          <span className="sr-only">{t({ id: "Dasar: ", en: "Basis: " })}</span>{twin(row, "rationale", lang)}
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
            <Section id="driver-bank" title={t(LABEL["driver-bank"])} count={forecast.bank_drivers!.length}>
              <p className="mb-3 max-w-[80ch] text-[14px] text-ink-soft">
                {t({
                  id: "Driver model bank per tahun: tahun berjalan memakai aktual 1H resmi ditambah driver H2; tahun berikutnya setahun penuh. "
                    + "Neraca, laba dan dividen dihitung model dari driver ini, dengan batas modal dan pendanaan.",
                  en: "Bank model drivers by year: the current year uses official 1H actuals plus H2 drivers; later years are full-year. "
                    + "The model derives the balance sheet, earnings and dividends from these drivers, within capital and funding limits.",
                })}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-[14px]">
                  <thead>
                    <tr className="text-[12.5px] text-ink-soft [&>th]:px-2 [&>th]:pb-2 [&>th]:align-bottom [&>th]:font-medium">
                      <th scope="col" className="text-left">{t({ id: "Tahun", en: "Year" })}</th>
                      {BANK_COLS.map(([key, label]) => <th key={key} scope="col" className="text-right">{t(label)}</th>)}
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
                          return <td key={key} className={`text-right font-mono whitespace-nowrap tabular-nums ${v == null ? "text-ink-faint" : "text-ink-strong"}`}>{pctOf(v, cell)}</td>;
                        })}
                      </tr>
                      {row.rationale && (
                        <tr>
                          <td colSpan={BANK_COLS.length + 1} className="px-2 pb-3 text-[13.5px] text-ink-soft">
                            {/* The table scrolls sideways on phones; the rationale stays in view and wraps to it. */}
                            <div className="sticky left-2 max-w-[min(80ch,calc(100vw-72px))]">
                              <span className="sr-only">{t({ id: "Dasar: ", en: "Basis: " })}</span>{twin(row, "rationale", lang)}
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
          {(forecast.catalysts?.length ?? 0) > 0 && (
            <Section id="katalis" title={t(LABEL.katalis)} count={forecast.catalysts!.length}>
              <div className="grid divide-y divide-rule-soft">
                {forecast.catalysts!.map((c, i) => (
                  <article key={i} className="grid gap-1.5 py-4 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                      <strong className="text-[15px] font-medium text-ink-strong">{twin(c, "item", lang)}</strong>
                      {c.direction && <Chip tone={DIRECTION_TONE[c.direction] ?? "neutral"}>{twin(c, "direction", lang)}</Chip>}
                      {c.timing && <span className="ml-auto text-[13px] text-ink-soft">{twin(c, "timing", lang)}</span>}
                    </div>
                    {c.driver_path && <p className="max-w-[80ch] text-[14px] text-ink">{twin(c, "driver_path", lang)}</p>}
                    {c.source_ids.length > 0 && (
                      <span className="flex flex-wrap gap-1">{c.source_ids.map((s) => <Chip key={s} mono>{s}</Chip>)}</span>
                    )}
                  </article>
                ))}
              </div>
            </Section>
          )}
          {(forecast.key_risks?.length ?? 0) > 0 && (
            <Section id="risiko" title={t(LABEL.risiko)} count={forecast.key_risks!.length}>
              <div className="grid gap-x-6 gap-y-4 lg:grid-cols-2">
                {forecast.key_risks!.map((r, i) => (
                  <article key={i} className="grid min-w-0 content-start gap-1.5 border-t border-rule-soft pt-3">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <h4 className="text-[15.5px]">{twin(r, "headline", lang)}</h4>
                      {r.category && <Chip>{twin(r, "category", lang)}</Chip>}
                    </div>
                    {r.explanation && <p className="text-[14px] text-ink">{twin(r, "explanation", lang)}</p>}
                    {r.source_ids.length > 0 && (
                      <span className="flex flex-wrap gap-1">{r.source_ids.map((s) => <Chip key={s} mono>{s}</Chip>)}</span>
                    )}
                  </article>
                ))}
              </div>
            </Section>
          )}
        </AgentGroup>

        {(trace.audit_appendix?.length ?? 0) > 0 && <AuditAppendix pages={trace.audit_appendix!} />}
        {trace.run_manifest && <RunManifest manifest={trace.run_manifest} />}

        <p className="text-[13px] text-ink-soft">
          {t({ id: "Materi informasi dan analisis; bukan rekomendasi investasi.", en: "Information and analysis only; not investment advice." })}
        </p>
      </div>
    </div>
  );
}

function RunManifest({ manifest }: { manifest: NonNullable<TraceView["run_manifest"]> }) {
  const { t } = useLang();
  const artifacts = Object.entries(manifest.artifacts);
  const sources = Object.entries(manifest.source_pack_sha256);
  const caches = Object.entries(manifest.cache_snapshot_sha256);
  const row = (label: string, value: string | null | undefined) => (
    <div className="grid gap-1 border-t border-rule-soft px-5 py-3 sm:grid-cols-[180px_1fr] max-sm:px-4">
      <dt className="text-[13px] text-ink-soft">{label}</dt>
      <dd className="m-0 break-all font-mono text-[12.5px] text-ink-strong">{value || "—"}</dd>
    </div>
  );
  const houseRate = (rates: NonNullable<typeof manifest.house_assumptions>["idr"]) => {
    const pct = (value: number | null) => value == null ? "n.m." : `${(value * 100).toFixed(1)}%`;
    return `Rf ${pct(rates.risk_free)} · CRP ${pct(rates.country_risk_premium)} · ` +
      `beta ${rates.beta == null ? "n.m." : rates.beta.toFixed(2)} · ERP ${pct(rates.equity_risk_premium)} · ` +
      `CoD ${pct(rates.cost_of_debt_pretax)} · g ${pct(rates.terminal_growth)}`;
  };
  return (
    <details className="panel scroll-mt-20">
      <summary className="cursor-pointer list-none px-6 py-5 text-[20px] font-semibold text-ink-strong max-sm:px-4">
        {t({ id: "Provenance dan identitas bundle", en: "Provenance and bundle identity" })}
      </summary>
      <dl className="m-0">
        {row("Publication ID", manifest.publication_id)}
        {row(t({ id: "Kode dan source tree", en: "Code and source tree" }), `${manifest.code_revision ?? "—"} · ${manifest.source_tree_sha256 ?? "—"}`)}
        {row("Working tree", `${manifest.working_tree.dirty == null ? "unknown" : manifest.working_tree.dirty ? "dirty" : "clean"} · ${manifest.working_tree.sha256 ?? "—"}`)}
        {row(t({ id: "Tanggal data / profile", en: "Data date / profile" }), `${manifest.as_of ?? "—"} · ${manifest.profile ?? "—"}`)}
        {row("Forecast agent", `${manifest.model.forecast_agent ?? "—"} · ${manifest.model.agent_effort ?? "—"}`)}
        {row("Spec / evidence register", `${manifest.spec_sha256 ?? "—"} · ${manifest.evidence_register_sha256 ?? "—"}`)}
        {manifest.source_text_en_sha256 !== undefined &&
          row(t({ id: "Terjemahan teks sumber", en: "Source-text translations" }), manifest.source_text_en_sha256)}
        {manifest.release_policy && row("Release policy", `${manifest.release_policy.version ?? "—"} · ${manifest.release_policy.status ?? "—"} · ${manifest.release_policy.sha256 ?? "—"}`)}
        {manifest.release_policy?.ambiguities.length ? row("Policy ambiguities", manifest.release_policy.ambiguities.join(", ")) : null}
        {manifest.house_assumptions && row("House assumptions", `${manifest.house_assumptions.version ?? "—"} · documented ${manifest.house_assumptions.documented_as_of ?? "—"} · effective date ${manifest.house_assumptions.effective_from ?? "unrecorded"} · ${manifest.house_assumptions.status ?? "—"} · ${manifest.house_assumptions.sha256 ?? "—"}`)}
        {manifest.house_assumptions && row("IDR discount inputs", houseRate(manifest.house_assumptions.idr))}
        {manifest.house_assumptions && row("USD discount inputs", `${houseRate(manifest.house_assumptions.usd)} · ${manifest.house_assumptions.usd.risk_free_basis ?? ""}`)}
        {manifest.house_assumptions?.unresolved.length ? row("House-policy open items", manifest.house_assumptions.unresolved.join("; ")) : null}
        <div className="border-t border-rule-soft px-5 py-3 max-sm:px-4">
          <dt className="text-[13px] text-ink-soft">Source pack hashes</dt>
          <dd className="m-0 mt-1 grid gap-1">
            {sources.length ? sources.map(([path, hash]) => <code key={path} className="break-all text-[11.5px]">{path} · {hash}</code>) : <span className="text-[13px] text-ink-faint">{t({ id: "Tidak tercatat", en: "Not recorded" })}</span>}
          </dd>
        </div>
        <div className="border-t border-rule-soft px-5 py-3 max-sm:px-4">
          <dt className="text-[13px] text-ink-soft">Cache snapshot hashes</dt>
          <dd className="m-0 mt-1 grid gap-1">
            {caches.length ? caches.map(([endpoint, value]) => <code key={endpoint} className="break-all text-[11.5px]">{endpoint} · {value.cache_key ?? "—"} · {value.content_sha256 ?? "—"}</code>) : <span className="text-[13px] text-ink-faint">{t({ id: "Tidak tercatat", en: "Not recorded" })}</span>}
          </dd>
        </div>
        <div className="border-t border-rule-soft px-5 py-3 max-sm:px-4">
          <dt className="text-[13px] text-ink-soft">Rendered artifact hashes</dt>
          <dd className="m-0 mt-1 grid gap-1">
            {artifacts.length ? artifacts.map(([kind, value]) => <code key={kind} className="break-all text-[11.5px]">{kind} · {value.file ?? "—"} · {value.sha256 ?? "—"}</code>) : <span className="text-[13px] text-ink-faint">{t({ id: "Tidak tercatat", en: "Not recorded" })}</span>}
            {manifest.missing_artifacts.map((kind) => <span key={kind} className="text-[13px] text-warn-ink">{t({ id: "Artefak hilang", en: "Missing artifact" })}: {kind}</span>)}
          </dd>
        </div>
      </dl>
    </details>
  );
}

/* ------------------------------------------------------------------ */

/** Report sections kept out of the printed company update, shown here for audit. */
function AuditAppendix({ pages }: { pages: NonNullable<TraceView["audit_appendix"]> }) {
  const { t, lang } = useLang();
  return (
    <section id="lampiran-audit" aria-labelledby="lampiran-audit-title" className="panel scroll-mt-20">
      <header className="px-6 py-5 max-sm:px-4">
        <h2 id="lampiran-audit-title" className="text-[20px]">{t({ id: "Lampiran audit", en: "Audit appendix" })}</h2>
        <p className="text-[14px] text-ink-soft">
          {t({
            id: "Bagian rekonstruksi dan uji rekonsiliasi yang tidak dicetak di company update karena hampir tidak menggerakkan target. "
              + "Angkanya sama dengan yang dihitung saat laporan dibangun.",
            en: "Reconstruction and reconciliation sections left out of the printed Company Update because they barely move the target. "
              + "The figures are the same ones computed when the report was built.",
          })}
        </p>
      </header>
      <div className="border-t border-rule">
        {pages.map((page, i) => (
          <details key={`${page.title}-${i}`} className="group border-b border-rule-soft last:border-b-0">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-6 py-3 text-[15px] font-medium text-ink-strong max-sm:px-4">
              <span>{twin(page, "title", lang)}</span>
              <span className="data text-ink-soft">
                {t({ id: `${page.exhibits.length} tabel`, en: `${page.exhibits.length} ${page.exhibits.length === 1 ? "table" : "tables"}` })}
              </span>
            </summary>
            <div className="grid gap-4 px-6 pb-5 max-sm:px-4 [&>*]:min-w-0">
              {twin(page, "paragraphs", lang).map((text, j) => <p key={j} className="max-w-[80ch] text-[14.5px] text-ink">{text}</p>)}
              {page.exhibits.map((e, j) => (
                <figure key={j} className="m-0">
                  <figcaption className="mb-2 text-[14px] font-semibold text-ink-strong">{twin(e, "title", lang)}</figcaption>
                  <div className="overflow-x-auto rounded-md border border-rule">
                    <table className="w-full border-collapse text-[13.5px]">
                      {e.cols.length > 0 && (
                        <thead>
                          <tr className="bg-raised text-left text-[12.5px] text-ink-soft">
                            {twin(e, "cols", lang).map((c, k) => <th key={k} scope="col" className={`px-3 py-2 font-medium ${k ? "text-right" : ""}`}>{c}</th>)}
                          </tr>
                        </thead>
                      )}
                      <tbody>
                        {twin(e, "rows", lang).map((row, r) => (
                          <tr key={r} className="border-t border-rule-soft align-top">
                            {row.map((c, k) => <td key={k} className={`px-3 py-1.5 ${k ? "text-right font-mono tabular-nums" : "text-ink"}`}>{c}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {e.note && <p className="mt-1.5 max-w-[90ch] text-[12.5px] text-ink-soft">{twin(e, "note", lang)}</p>}
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
  const { t, lang } = useLang();
  const T = ticker.toUpperCase();
  const [reviewToken, setReviewToken] = useState(readReviewToken);
  const state = useLoad(async () => {
    try {
      return await api.reportTrace(T);
    } catch (error) {
      if (reviewToken && error instanceof ApiError && error.status === 404) {
        return api.reportTracePreview(T, reviewToken);
      }
      throw error;
    }
  }, [T, reviewToken]);
  const reviewState = useLoad(() => api.review(T), [T]);
  // The gallery entry and the stored run are optional context: the trace renders without them.
  const reports = useLoad(() => api.reports().catch(() => [] as ReportItem[]), []);
  const run = useLoad(() => api.reportRun(T).catch(() => undefined), [T]);
  const item = reports.data?.find((r) => r.ticker === T);
  const files = item ? readerFiles(item, lang) : reportFiles(T);
  // The bundle kinds this run's manifest lists: English previews are offered only when it has them.
  const kinds = Object.keys(state.data?.run_manifest?.artifacts ?? {});
  return (
    <TracePage state={state} item={item} run={run.data ?? undefined} missing={t({ id: `Jejak riset ${T} tidak ditemukan.`, en: `No Audit Trace found for ${T}.` })}
      links={{ reportUrl: files.html, pdfUrl: item?.files.pdf ? files.pdf : undefined, replayUrl: `/laporan/${T}/putar` }}
      review={<ReviewPanel ticker={T} bundleKinds={kinds}
        reviewToken={state.data?.review_state === "pending" ? reviewToken || undefined : undefined}
        onApproved={() => { state.reload(); reports.reload(); }} />}
      reviewAccess={reviewState.data?.enabled && reviewState.data.state === "pending"
        ? <ReviewerPreviewAccess ticker={T} error={state.status === 403 ? state.error : undefined}
            onUnlock={(token) => { keepReviewToken(token); setReviewToken(token); }} />
        : undefined} />
  );
}

function ReviewerPreviewAccess({ ticker, error, onUnlock }: {
  ticker: string; error?: string; onUnlock: (token: string) => void;
}) {
  const { t } = useLang();
  const [token, setToken] = useState(readReviewToken);
  const label = "mb-1 block text-[12.5px] font-medium text-ink-soft";
  const input = "h-10 w-full rounded-md border border-rule bg-raised px-3 text-[14.5px] text-ink-strong placeholder:text-ink-faint focus:border-brand-ink";
  return (
    <section className="panel grid gap-4 p-6 max-sm:p-4" aria-labelledby="preview-access-title">
      <div>
        <h2 id="preview-access-title" className="m-0 text-[18px]">
          {t({ id: "Jejak ini menunggu review publikasi", en: "This trace is awaiting publication review" })}
        </h2>
        <p className="mb-0 mt-1 text-[14px] text-ink-soft">
          {t({
            id: "Masukkan token reviewer untuk membuka pratinjau privat dan memeriksa laporan sebelum diterbitkan.",
            en: "Enter a reviewer token to open the private preview and check the report before it is published.",
          })}
        </p>
      </div>
      <form className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end" onSubmit={(event) => {
        event.preventDefault();
        if (token.trim()) onUnlock(token.trim());
      }}>
        <div>
          <label htmlFor="preview-review-token" className={label}>{t({ id: "Token reviewer", en: "Reviewer token" })}</label>
          <input id="preview-review-token" type="password" value={token}
            onChange={(event) => setToken(event.target.value)} autoComplete="off"
            className={input} />
        </div>
        <button type="submit" disabled={!token.trim()} className="btn btn-primary disabled:cursor-not-allowed">
          {t({ id: "Buka pratinjau", en: "Open preview" })}
        </button>
      </form>
      {error && <p role="alert" className="m-0 text-[14px] text-err-ink">{error}</p>}
      <p className="m-0 text-[12.5px] text-ink-faint">
        {t({ id: "Emiten", en: "Issuer" })} {ticker} ·{" "}
        {t({ id: "Nilai model tetap tidak tersedia untuk umum sampai review lolos.", en: "Model values stay unavailable to the public until the review passes." })}
      </p>
    </section>
  );
}

export function JobTrace() {
  const { id = "" } = useParams();
  const { t } = useLang();
  const state = useLoad(() => api.jobTrace(id), [id]);
  const ticker = state.data?.ticker ?? "";
  return (
    <TracePage state={state} missing={t({
      id: "Jejak riset ini tidak ditemukan. Riset yang berjalan di server hanya disimpan selama server hidup.",
      en: "This Audit Trace was not found. Research run on the server is kept only while the server is up.",
    })}
      links={{ reportUrl: `/files/jobs/${id}/${ticker}.html`, deckUrl: `/jobs/${id}` }} />
  );
}

function TracePage({ state, item, run, links, missing, review, reviewAccess }:
  { state: ReturnType<typeof useLoad<TraceView>>; item?: ReportItem; run?: RunReplay; links: Links; missing: string;
    review?: React.ReactNode; reviewAccess?: React.ReactNode }) {
  const { t } = useLang();
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
          <span className="sr-only">{t({ id: "Memuat jejak riset…", en: "Loading Audit Trace…" })}</span>
          <span aria-hidden className="h-4 w-40 animate-pulse rounded bg-raised" />
          <span aria-hidden className="h-9 w-72 animate-pulse rounded bg-raised" />
          <span aria-hidden className="h-24 w-full animate-pulse rounded-md bg-surface ring-1 ring-rule" />
          <span aria-hidden className="h-64 w-full animate-pulse rounded-lg bg-surface ring-1 ring-rule" />
        </div>
      )}
      {state.error && (
        reviewAccess ?? <Notice tone={state.status === 404 ? "muted" : "error"}>
          {state.status === 404 ? (
            <>
              <p><strong className="text-ink-strong">{missing}</strong>{" "}
                {t({ id: "Buka jejak dari galeri laporan atau dari deck riset.", en: "Open a trace from the Report Gallery or the research deck." })}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link className="btn btn-sm btn-ghost" to="/laporan">{t({ id: "Buka galeri laporan", en: "Open Report Gallery" })}</Link>
                <Link className="btn btn-sm btn-ghost" to="/research">{t({ id: "Mulai riset", en: "Start research" })}</Link>
              </div>
            </>
          ) : (
            <>
              <p>
                <strong>{t({ id: "Jejak riset belum bisa dimuat.", en: "The Audit Trace could not be loaded." })}</strong>{" "}
                {t({ id: "Server API tidak menjawab", en: "The API server did not respond" })} ({state.error}).
              </p>
              <button type="button" onClick={state.reload} className="btn btn-sm btn-ghost mt-3">
                <RefreshCw aria-hidden className="size-3.5" strokeWidth={2.2} />{t({ id: "Coba lagi", en: "Try again" })}
              </button>
            </>
          )}
        </Notice>
      )}
    </div>
  );
}
