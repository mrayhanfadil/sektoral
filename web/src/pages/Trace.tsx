import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, reportFiles, type TraceView } from "../lib/api";
import { rp } from "../lib/format";
import { INTEL_SECTIONS, IntelPanel } from "../components/Intel";
import { Notice, useLoad } from "../components/State";

// The trace runs to many screens; this index is its table of contents. Labels
// are the headings themselves, and only sections the trace has are listed.
const RESEARCH_SECTIONS: [string, string][] = [
  ["ringkasan", "Ringkasan agent riset"], ["endpoint", "Endpoint data Sectors yang dibaca"],
  ["temuan", "Temuan dan hubungan sebab-akibat"], ["berita", "Berita untuk asumsi forecast"],
  ["asumsi", "Asumsi forecast oleh agent"], ["deep-dive", "Deep-dive berita"],
  ["kurang", "Bukti yang masih kurang"],
];

function Block({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="grid scroll-mt-24 gap-3 border-t border-rule pt-6 first:border-t-0 first:pt-0">
      <h2 id={`${id}-title`} className="text-xl">{title}</h2>
      {children}
    </section>
  );
}

/** Sections present on the page, and the one currently being read. */
function useSectionIndex(ready: boolean) {
  const [present, setPresent] = useState<[string, string][]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  useEffect(() => {
    if (!ready) return;
    const all = [...INTEL_SECTIONS, ...RESEARCH_SECTIONS].filter(([id]) => document.getElementById(id));
    setPresent(all);
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) setCurrent(visible[0].target.id);
    }, { rootMargin: "-96px 0px -60% 0px" });
    all.forEach(([id]) => observer.observe(document.getElementById(id)!));
    return () => observer.disconnect();
  }, [ready]);
  return { present, current };
}

function SectionIndex({ present, current }: { present: [string, string][]; current: string | null }) {
  const link = (id: string) => `no-underline ${current === id ? "text-ink font-bold" : "text-ink-soft hover:text-ink"}`;
  return (
    <>
      <nav aria-label="Bagian jejak riset" className="sticky top-24 max-lg:hidden">
        <p className="mb-2 text-[13px] font-bold text-ink-faint">Di halaman ini</p>
        <ul className="m-0 grid list-none gap-0.5 border-l border-rule p-0">
          {present.map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} aria-current={current === id ? "location" : undefined}
                className={`-ml-px block border-l-2 py-1 pl-3 text-[13.5px] ${current === id ? "border-brand-ink" : "border-transparent hover:border-rule-strong"} ${link(id)}`}>
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <nav aria-label="Bagian jejak riset" className="sticky top-16 z-40 -mx-4 border-b border-rule bg-canvas/95 px-4 backdrop-blur-md lg:hidden">
        <ul className="m-0 flex list-none gap-5 overflow-x-auto p-0 py-3 whitespace-nowrap">
          {present.map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} aria-current={current === id ? "location" : undefined} className={`text-[13.5px] ${link(id)}`}>{label}</a>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}

const box = "rounded-lg bg-canvas px-4 py-3.5";

/** The agent records news without a measurable transmission as driver "none", change 0. */
const isNoEffect = (e: { driver: string | null; change: string | null }) =>
  !e.driver || e.driver === "none" || Number(e.change) === 0;

function statusLabel(report: TraceView["report"]) {
  if (report.published && report.rating) return `Terbit: ${report.rating}, TP Rp${rp(report.target_price)}`;
  return report.release_status ? "Draft, rating ditahan" : "Status belum tercatat";
}

function TraceBody({ trace, reportUrl, pdfUrl }: { trace: TraceView; reportUrl: string; pdfUrl?: string }) {
  const { report, research, news, forecast } = trace;
  const index = useSectionIndex(true);
  return (
    <div className="grid items-start gap-x-10 gap-y-4 lg:grid-cols-[200px_1fr] [&>*]:min-w-0">
    <SectionIndex {...index} />
    <div className="grid gap-6 [&>*]:min-w-0">
      <header className="card border-t-4 border-t-brand">
        <h1 className="mb-2.5 text-[28px] font-black">Jejak riset {trace.ticker}</h1>
        <div className="flex flex-wrap gap-2">
          {report.as_of && <span className="pill pill-live">Data per {report.as_of}</span>}
          <span className={`pill ${report.published ? "pill-ok" : "pill-warn"}`}>{statusLabel(report)}</span>
          {report.published && report.method && <span className="pill pill-live">Metode: {report.method}</span>}
        </div>
        <div className="mt-5 flex flex-wrap gap-2.5">
          <a className="btn btn-primary" href={reportUrl}>Buka company update</a>
          {pdfUrl && <a className="btn btn-ghost" href={pdfUrl}>Buka PDF</a>}
          <Link className="btn btn-ghost" to="/laporan">Galeri laporan</Link>
        </div>
      </header>

      {trace.analyst ? <IntelPanel intel={trace.analyst} /> : (
        <div className="card">
          <h2 className="mb-2 text-xl">Agent analis</h2>
          <p className="text-ink-soft">{trace.analyst_problems.join("; ") || "Agent analis tidak dijalankan untuk riset ini."}</p>
        </div>
      )}

      <div className="card grid gap-7">

      <Block id="ringkasan" title="Ringkasan agent riset">
        <div className={box}>{research.summary || "Belum ada briefing tervalidasi."}</div>
      </Block>

      <Block id="endpoint" title="Endpoint data Sectors yang dibaca">
        <div className={box}>
          {research.endpoints.length ? research.endpoints.map((e) => (
            <span key={e} className="m-[3px] inline-block rounded-md bg-brand-50 px-[9px] py-[3px] font-mono text-[13px] text-brand-ink">{e}</span>
          )) : <span className="text-ink-soft">Tidak ada endpoint tercatat.</span>}
        </div>
      </Block>

      <Block id="temuan" title="Temuan dan hubungan sebab-akibat">
        {research.insights.length ? research.insights.map((insight, i) => (
          <article key={i} className={`${box} grid gap-2`}>
            <h3 className="text-[17px]">{insight.title || "Temuan"}</h3>
            {insight.observation && <p><strong>Observasi.</strong> {insight.observation}</p>}
            {insight.implication && <p><strong>Implikasi.</strong> {insight.implication}</p>}
            {insight.caveat && <p className="text-ink-soft"><strong>Batas bukti.</strong> {insight.caveat}</p>}
            {insight.citations.length > 0 && (
              <ul className="m-0 pl-5 text-[13px] text-ink-soft">
                {insight.citations.map((c, j) => <li key={j}>{c.endpoint}, {c.field_path} = {c.value}</li>)}
              </ul>
            )}
          </article>
        )) : <div className={`${box} text-ink-soft`}>Belum ada temuan yang lolos validasi sitasi.</div>}
      </Block>

      <Block id="berita" title="Berita untuk asumsi forecast">
        <p className="text-ink-soft">
          Pencarian berita web: {news.search.status ?? "tidak dijalankan"}{news.search.as_of ? `, per ${news.search.as_of}` : ""}.
          {news.search.queries.length > 0 && <> Kueri: {news.search.queries.join("; ")}.</>}
        </p>
        {news.articles.length > 0 && (
          <ol className={`${box} m-0 grid gap-1.5 pl-9 text-[14.5px]`}>
            {news.articles.map((a, i) => (
              <li key={i}>
                {a.url ? <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a> : a.title}
                <span className="text-[13px] text-ink-soft"> {[a.date, a.origins.join(", ")].filter(Boolean).join(", ")}</span>
              </li>
            ))}
          </ol>
        )}
        {news.rejected.length > 0 && (
          <details className={box}>
            <summary className="cursor-pointer font-bold">{news.rejected_total} berita ditolak (tidak relevan atau dampak nol)</summary>
            <ol className="mt-2 mb-0 grid gap-1 pl-5 text-[14px]">
              {news.rejected.map((r, i) => <li key={i}>{r.title} <span className="text-ink-soft">({r.reason})</span></li>)}
              {news.rejected_total > news.rejected.length && <li className="text-ink-soft">dan {news.rejected_total - news.rejected.length} penolakan lain</li>}
            </ol>
          </details>
        )}
      </Block>

      <Block id="asumsi" title="Asumsi forecast oleh agent">
        <p className="text-ink-soft">Status: {forecast.status ?? "tidak tercatat"}</p>
        {forecast.news_effects.map((e, i) => (
          <article key={i} className={`${box} grid gap-1.5`}>
            <strong>
              {isNoEffect(e) ? "Tanpa dampak terukur ke forecast" : `${e.driver}: ${e.change}`}{" "}
              {e.years.length > 0 && <span className="font-normal text-ink-soft">({e.years.join(", ")})</span>}
            </strong>
            {e.rationale && <p>{e.rationale}</p>}
            <p className="text-[13px] text-ink-soft">
              {e.date}{e.url && <>, <a href={e.url} target="_blank" rel="noopener noreferrer">sumber</a></>}
              {e.factual_basis && <><br />Fakta: {e.factual_basis}</>}
              {e.mechanism && <><br />Mekanisme: {e.mechanism}</>}
              {e.uncertainty && <><br />Ketidakpastian: {e.uncertainty}</>}
            </p>
          </article>
        ))}
        {forecast.interim && (
          <article className={`${box} grid gap-1.5`}>
            <strong>Skenario hasil interim</strong>
            <p>{forecast.interim.rationale}</p>
            <p className="text-[13px] text-ink-soft">
              {forecast.interim.published_at}{forecast.interim.url && <>, <a href={forecast.interim.url} target="_blank" rel="noopener noreferrer">sumber</a></>}
            </p>
          </article>
        )}
        {forecast.outyears.length > 0 && (
          <div className={`${box} overflow-x-auto`}>
            <table className="w-full min-w-[560px] border-collapse text-sm [&_td]:border-t [&_td]:border-rule-soft [&_td]:px-2 [&_td]:py-2 [&_td]:align-top [&_th]:px-2 [&_th]:py-2 [&_th]:text-left [&_th]:text-[13px] [&_th]:text-ink-soft">
              <thead><tr><th>Tahun</th><th>Revenue</th><th>Margin EBITDA</th><th>Margin laba</th><th>Capex/revenue</th><th>Dasar</th></tr></thead>
              <tbody>
                {forecast.outyears.map((row) => (
                  <tr key={row.year}>
                    <td className="font-bold">{row.year}</td>
                    {[row.revenue_growth_pct, row.ebitda_margin_pct, row.net_income_margin_pct, row.capex_to_revenue_pct].map((v, i) => (
                      <td key={i} className="tabular-nums whitespace-nowrap">{v == null ? "n.a." : `${String(v).replace(".", ",")}%`}</td>
                    ))}
                    <td className="text-ink-soft">{row.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {forecast.problems.length > 0 && <div className={`${box} text-ink-soft`}>{forecast.problems.join("; ")}</div>}
      </Block>

      <Block id="deep-dive" title="Deep-dive berita">
        {trace.deepdive.length ? trace.deepdive.map((item, i) => (
          <article key={i} className={`${box} grid gap-1.5`}>
            <strong>{item.title || "(tanpa judul)"}</strong>
            <p className="text-[13px] text-ink-soft">
              {item.date}{item.url && <>, <a href={item.url} target="_blank" rel="noopener noreferrer">sumber</a></>}, status {item.status}, {item.length} karakter
            </p>
            <p className={item.preview ? "" : "text-ink-soft"}>
              {item.preview ?? "Teks lengkap tidak tersedia; ringkasan berita hanya untuk konteks."}
            </p>
          </article>
        )) : <div className={`${box} text-ink-soft`}>Belum ada hasil deep-dive berita.</div>}
      </Block>

      {research.limitations.length > 0 && (
        <Block id="kurang" title="Bukti yang masih kurang">
          <ul className={`${box} m-0 pl-9`}>{research.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </Block>
      )}
      </div>
      <p className="text-[13px] text-ink-soft">Materi informasi dan analisis; bukan rekomendasi investasi.</p>
    </div>
    </div>
  );
}

export function ReportTrace() {
  const { ticker = "" } = useParams();
  const state = useLoad(() => api.reportTrace(ticker), [ticker]);
  const files = reportFiles(ticker);
  return <TracePage state={state} reportUrl={files.html} pdfUrl={files.pdf} />;
}

export function JobTrace() {
  const { id = "" } = useParams();
  const state = useLoad(() => api.jobTrace(id), [id]);
  const ticker = state.data?.ticker ?? "";
  return <TracePage state={state} reportUrl={`/files/jobs/${id}/${ticker}.html`} />;
}

function TracePage({ state, reportUrl, pdfUrl }: { state: ReturnType<typeof useLoad<TraceView>>; reportUrl: string; pdfUrl?: string }) {
  return (
    <div className="min-h-full bg-canvas py-10 max-sm:py-5">
      <div className="wrap">
        {state.loading && <p className="text-ink-soft">Memuat jejak riset…</p>}
        {state.error && <Notice tone="error">Jejak riset tidak ditemukan. Buka dari galeri laporan atau halaman riset.</Notice>}
        {state.data && <TraceBody trace={state.data} reportUrl={reportUrl} pdfUrl={pdfUrl} />}
      </div>
    </div>
  );
}
