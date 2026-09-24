import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Job as JobState } from "../lib/api";
import { PROGRESS_STEPS, progressStep } from "../lib/labels";
import { IntelHeadline, IntelSections } from "../components/Intel";
import { Notice } from "../components/State";
import { Icon } from "../components/Icon";
import { ResearchPanels } from "./Research";

const STATE_LABEL = { pending: "Menunggu", running: "Sedang diproses", completed: "Selesai", error: "Tidak selesai" };
const EVENT_DOT = { ok: "bg-ok-bg text-ok-ink", warn: "bg-warn-bg text-warn-ink", error: "bg-err-bg text-err-ink", run: "" };
const EVENT_ICON = { ok: "check", warn: "alert", error: "x" } as const;

function useJob(id: string) {
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const next = await api.job(id);
        if (!live) return;
        setJob(next);
        setError(null);
        if (next.state === "pending" || next.state === "running") timer = window.setTimeout(poll, 1000);
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    };
    poll();
    return () => { live = false; window.clearTimeout(timer); };
  }, [id]);
  return { job, error };
}

function StatusPill({ job }: { job: JobState }) {
  const partial = job.state === "completed" && job.quality === "partial";
  const tone = job.state === "error" ? "pill-err" : partial ? "pill-warn" : job.state === "completed" ? "pill-ok" : "pill-live";
  return <span className={`pill px-3 py-[5px] text-sm ${tone}`}>{partial ? "Selesai, parsial" : STATE_LABEL[job.state]}</span>;
}

function Progress({ job }: { job: JobState }) {
  const at = progressStep(job.state, job.events.map((e) => e.stage));
  const partial = job.state === "completed" && job.quality === "partial";
  return (
    <ol aria-label="Tahap riset" className="mt-7 grid list-none grid-cols-5 gap-2 p-0 max-md:grid-cols-1 max-md:gap-3">
      {PROGRESS_STEPS.map((step, i) => {
        const done = job.state !== "pending" && i < at;
        const active = job.state !== "pending" && i === at;
        const failed = active && job.state === "error";
        const bar = failed ? "bg-err-ink/50" : done ? (partial && i === 4 ? "bg-warn-rule" : "bg-brand")
          : active ? "animate-pulse bg-[linear-gradient(90deg,var(--color-brand)_0_35%,var(--color-brand-100)_35%_100%)]" : "bg-rule-soft";
        const text = failed ? "text-err-ink" : done ? "text-ink" : active ? "text-brand-ink" : "text-ink-faint";
        return (
          <li key={step.title} aria-current={active ? "step" : undefined} className={`relative pt-[18px] text-sm font-bold ${text}`}>
            <span aria-hidden className={`absolute inset-x-0 top-0 h-1.5 rounded-md ${bar}`} />
            {step.title}<small className="block text-[13px] font-normal">{step.sub}</small>
          </li>
        );
      })}
    </ol>
  );
}

function EventLog({ job }: { job: JobState }) {
  const list = useRef<HTMLOListElement>(null);
  const shown = job.events.filter((e, i) => e.status !== "run" || (i === job.events.length - 1 && job.state === "running"));
  useEffect(() => {
    if (job.state === "running" && list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [shown.length, job.state]);
  if (!shown.length) return null;
  return (
    <details open className="mt-[22px] border-t border-rule-soft pt-3.5">
      <summary className="cursor-pointer text-sm font-bold text-ink-soft">Log kerja agent</summary>
      <ol ref={list} className="m-0 mt-3 max-h-[340px] list-none overflow-auto p-0">
        {shown.map((e, i) => (
          <li key={i} className="grid grid-cols-[22px_1fr] gap-2.5 border-b border-dashed border-rule-soft py-[7px] last:border-0">
            <span className={`mt-0.5 grid size-5 place-items-center rounded-full ${
              e.status === "run" ? "animate-spin border-2 border-brand-100 border-t-brand-ink bg-brand-50" : EVENT_DOT[e.status]}`}>
              {e.status !== "run" && <Icon name={EVENT_ICON[e.status]} className="size-3" />}
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-2 text-[14.5px]">
                <strong>{e.label}</strong>
                {e.tool && <code className="rounded-[5px] bg-brand-50 px-1.5 py-px font-mono text-xs text-brand-ink">{e.tool}</code>}
                <span className="ml-auto text-xs text-ink-faint tabular-nums max-sm:ml-0">{e.t} dtk</span>
              </div>
              {e.detail && <p className="mt-0.5 text-[13.5px] break-words text-ink-soft">{e.detail}</p>}
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}

function detail(job: JobState) {
  if (job.state === "error") return "Proses riset mengalami kendala. Periksa log lokal untuk detail.";
  if (job.state === "completed") {
    return job.quality === "partial"
      ? "Analisis parsial: bukti belum cukup untuk semua bagian. Batasnya dijelaskan di laporan dan jejak agent."
      : "Laporan dan jejak validasi siap ditinjau.";
  }
  if (job.state === "running") {
    const last = job.events[job.events.length - 1];
    return last ? `${last.label}…` : "Agent memulai riset…";
  }
  return "Riset masuk antrean dan akan segera dimulai.";
}

export default function Job() {
  const { id = "" } = useParams();
  const { job, error } = useJob(id);

  return (
    <div className="min-h-full bg-canvas py-10 max-sm:py-5">
      <div className="wrap grid gap-6 [&>*]:min-w-0">
        <h1 className="sr-only">Riset emiten</h1>
        {error && !job && <Notice tone="error">{error === "Riset tidak ditemukan." ? "Riset tidak ditemukan. Mulai riset baru di bawah." : "Status belum tersedia. Muat ulang halaman untuk mencoba lagi."}</Notice>}
        {job && (
          <section className="card" aria-labelledby="job-title">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <h2 id="job-title" className="text-[26px] font-black tracking-[-.02em]">Riset {job.ticker}</h2>
              <StatusPill job={job} />
            </div>
            <Progress job={job} />
            <p aria-live="polite" className="mt-[22px] text-base text-ink-soft">{detail(job)}</p>
            {job.state === "completed" && (
              <div className="mt-5 flex flex-wrap gap-2.5 max-sm:[&>*]:flex-[1_1_100%]">
                {job.report_url && <a className="btn btn-primary" href={job.report_url}>Buka company update</a>}
                {job.trace_url && <Link className="btn btn-ghost" to={job.trace_url}>Lihat jejak agent</Link>}
                {job.pdf_url && <a className="btn btn-ghost" href={job.pdf_url}>Buka PDF</a>}
                {job.gallery_url && <Link className="btn btn-ghost" to={job.gallery_url}>Lihat di galeri laporan</Link>}
              </div>
            )}
            <EventLog job={job} />
          </section>
        )}
        {job?.intel && (
          <section aria-label="Intelijen pasar" className="grid gap-6 [&>*]:min-w-0">
            <IntelHeadline intel={job.intel} />
            <IntelSections intel={job.intel} />
            <p className="text-[13.5px] text-ink-soft">
              Sinyal dihitung deterministik dari data Sectors; agent memilih pemeriksaan dan menafsirkan hasilnya.
              Informasi dan analisis, bukan rekomendasi investasi.
            </p>
          </section>
        )}
        <ResearchPanels afterJob />
      </div>
    </div>
  );
}
