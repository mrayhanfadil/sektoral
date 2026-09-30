// The research Deck, in three modes that share one console layout:
// the launcher (/research), a live job (/jobs/:id) and a stored run played
// back (/laporan/:ticker/putar).
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CircleX, FileDown, FileText, Route, SquareTerminal } from "lucide-react";
import { AGENTS, derive, PHASES, type DeckState } from "../lib/agents";
import { api, ApiError, type Job, type JobEvent, type ReportItem, type RunReplay } from "../lib/api";
import { pct, rp } from "../lib/format";
import { useLang, type Bi, type Lang } from "../lib/i18n";
import { ratingLabel, ratingTone } from "../lib/labels";
import { useReplay } from "../lib/replay";
import { useJob } from "../lib/useJob";
import { IntelPanel } from "../components/Intel";
import { useLoad } from "../components/State";
import { DeckView } from "../components/deck/DeckView";
import { LaunchPanel } from "../components/deck/LaunchPanel";
import { EngineTag, LiveClock, Tweened } from "../components/deck/kit";
import { clock, words } from "../components/deck/read";
import { ReplayControls } from "../components/deck/ReplayControls";
import { RunHeader, type RunPhase } from "../components/deck/RunHeader";
import type { ResultData } from "../components/deck/SidePanels";
import { launch } from "../lib/launch";

const NO_EVENTS: JobEvent[] = [];
const IDLE = derive([]);

function Page({ children }: { children: ReactNode }) {
  return <div className="wrap py-4 max-sm:py-3">{children}</div>;
}

/* ---------------------------------------------------------------- launcher */

export function DeckLaunch() {
  return (
    <Page>
      <DeckView state={IDLE} top={<LaunchPanel />} live={false} fit={false} empty={<IdleLegend />} />
    </Page>
  );
}

/** Before a run: what each agent on the rail will do, in pipeline order. */
function IdleLegend() {
  const { t } = useLang();
  return (
    <>
      <p className="max-w-[64ch]">
        {t({
          id: "Belum ada langkah. Setelah riset dimulai, setiap tool call muncul di sini: nama tool, alasan agent memanggilnya, lalu hasilnya. "
            + "Agent di rail menyala saat bekerja, dan keenam Method Gates di kanan terisi saat valuasi dipilih.",
          en: "No steps yet. Once research starts, every tool call appears here: the tool name, why the agent called it, then its result. "
            + "Agents on the rail light up while they work, and the six Method Gates on the right fill in as the valuation is chosen.",
        })}
      </p>
      <ol aria-label={t({ id: "Urutan agent", en: "Agent order" })} className="m-0 mt-4 list-none border-t border-rule-soft p-0">
        {AGENTS.map((a, i) => (
          <li key={a.id} className="grid grid-cols-[18px_minmax(0,1fr)_auto] items-baseline gap-x-3 border-b border-rule-soft py-2">
            <span className="data text-ink-faint">{i + 1}</span>
            <span className="min-w-0">
              <span className="font-bold text-ink">{t(a.name)}</span>
              <span className="block text-[13px] leading-snug text-ink-soft">{t(a.role)}</span>
            </span>
            <EngineTag engine={a.engine} />
          </li>
        ))}
      </ol>
    </>
  );
}

/* ---------------------------------------------------------------- results */

/** The analyst's chosen method: the gate agent's closing line, else the selected chain step. */
function methodOf(state: DeckState): string | undefined {
  const closing = state.steps.find((s) => s.agent === "gerbang" && s.kind === "task" && s.result?.startsWith("Metode utama "));
  return closing?.result?.slice("Metode utama ".length) ?? state.chain.find((c) => c.decision === "Terpilih")?.method;
}

function signed(value: number | null | undefined, lang: Lang) {
  const text = pct(value, lang);
  return typeof value === "number" && value > 0 ? `+${text}` : text;
}

const WITHHELD: Bi = { id: "ditahan", en: "withheld" };

function fromRelease(state: DeckState, lang: Lang): ResultData | undefined {
  const release = state.release;
  if (!release) return undefined;
  const heldByGate5 = state.gates[5]?.verdict === "gagal";
  const item = { rating: release.rating ?? null, held_reason: heldByGate5 ? "Method Gate 5" : "" };
  return {
    rating: ratingLabel(item), tone: ratingTone(item),
    tp: release.tp ?? WITHHELD[lang], upside: release.upside ?? "-",
    method: methodOf(state), release: words(release.status, lang),
  };
}

function fromReport(report: ReportItem, state: DeckState, lang: Lang): ResultData {
  return {
    rating: ratingLabel(report), tone: ratingTone(report),
    tp: report.published && report.tp !== null ? `Rp${rp(report.tp, lang)}` : WITHHELD[lang],
    upside: report.published ? signed(report.upside, lang) : "-",
    price: report.price !== null ? `Rp${rp(report.price, lang)}` : undefined,
    method: report.method || methodOf(state),
    release: words(state.release?.status, lang) ?? (report.published ? undefined : words("draft_non_distributable", lang)),
  };
}

type Links = { report?: string; trace?: string; pdf?: string };

function OpenReport({ href }: { href: string }) {
  const { t } = useLang();
  return (
    <a className="btn btn-primary" href={href}>
      <FileText aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Buka company update", en: "Open Company Update" })}
    </a>
  );
}

function Actions({ links, rerun }: { links: Links; rerun?: ReactNode }) {
  const { t } = useLang();
  return (
    <>
      {links.report && <OpenReport href={links.report} />}
      {links.trace && (
        <Link className="btn btn-ghost" to={links.trace}>
          <Route aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Lihat jejak agent", en: "View Audit Trace" })}
        </Link>
      )}
      {links.pdf && (
        <a className="btn btn-ghost" href={links.pdf}>
          <FileDown aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Buka PDF", en: "Open PDF" })}
        </a>
      )}
      {rerun}
    </>
  );
}

/** Submit a new run of ``ticker`` and go to it; errors stay next to the button. */
function RerunButton({ ticker, label }: { ticker: string; label: string }) {
  const { t } = useLang();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="flex flex-col gap-1.5">
      <button type="button" className="btn btn-ghost" disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const next = await launch(ticker);
            if (next.replay && location.pathname === next.path) {
              setError(t({
                id: "Riset langsung di situs ini butuh token pemilik; run tersimpan sudah diputar di sini.",
                en: "Live research on this site needs the owner's token; the stored run is already playing here.",
              }));
              setBusy(false);
              return;
            }
            navigate(next.path);
          } catch (e) {
            const message = (e as Error).message;
            setError(t({ id: `Riset belum bisa dimulai: ${message}`, en: `Research could not start: ${message}` }));
            setBusy(false);
          }
        }}>
        <SquareTerminal aria-hidden className="size-4" strokeWidth={2.2} />{busy ? t({ id: "Memulai…", en: "Starting…" }) : label}
      </button>
      {error && <span role="alert" className="text-[13px] font-medium text-err-ink">{error}</span>}
    </span>
  );
}

/* ---------------------------------------------------------------- live job */

const JOB_PHASE: Record<Job["state"], RunPhase> = { pending: "pending", running: "running", completed: "completed", error: "error" };

export function DeckJob() {
  const { id = "" } = useParams();
  const { t, lang } = useLang();
  const { job, error, missing } = useJob(id);
  const { data: reports } = useLoad(api.reports);
  const events = job?.events ?? NO_EVENTS;
  const finished = job?.state === "completed" || job?.state === "error";
  const failed = job?.state === "error";
  const state = useMemo(() => derive(events, { finished, failed }), [events, finished, failed]);

  if (!job) {
    if (missing) {
      return (
        <Page>
          <Message title={t({ id: "Riset tidak ditemukan", en: "Research not found" })}>
            {t({
              id: "Server tidak lagi menyimpan riset ini, atau tautannya salah. Jalankan riset baru dari Deck.",
              en: "The server no longer keeps this research, or the link is wrong. Run new research from the Deck.",
            })}
            <div className="mt-4"><Link className="btn btn-primary" to="/research">{t({ id: "Buka Deck riset", en: "Open the research Deck" })}</Link></div>
          </Message>
        </Page>
      );
    }
    return (
      <Page>
        <DeckView state={IDLE} live={false} loading
          top={<RunHeader ticker="" phase="pending" clock={clock(0)} counts={IDLE.counts} loading />}
          notice={error ? (
            <Notice tone="warn">
              {t({ id: `Status riset belum tersedia (${error}). Deck mencoba lagi otomatis.`, en: `Research status is not available yet (${error}). The Deck retries automatically.` })}
            </Notice>
          ) : undefined} />
      </Page>
    );
  }

  const name = job.intel?.name ?? reports?.find((r) => r.ticker === job.ticker)?.name;
  const done = job.state === "completed";
  const links: Links = { report: job.report_url, trace: job.trace_url, pdf: job.pdf_url };
  const result = fromRelease(state, lang);
  const lastError = [...events].reverse().find((e) => e.status === "error");
  const phase = PHASES[Math.max(0, state.phaseAt)];

  return (
    <Page>
      <DeckView state={state} live={job.state === "running"}
        top={
          <RunHeader ticker={job.ticker} name={name} phase={JOB_PHASE[job.state]} counts={state.counts}
            clock={<LiveClock lastT={state.elapsed} running={job.state === "running"} />}
            badges={done && job.quality === "partial" ? (
              <span className="pill pill-warn px-2 py-0 text-[12.5px]" title={t({
                id: "Bukti belum cukup untuk semua bagian; batasnya dijelaskan di laporan dan jejak agent.",
                en: "Evidence does not yet cover every section; the limits are explained in the report and the Audit Trace.",
              })}>{t({ id: "Parsial", en: "Partial" })}</span>
            ) : undefined}
            action={done && job.report_url ? <OpenReport href={job.report_url} /> : undefined} />
        }
        notice={job.state === "error" ? (
          <Notice tone="error" action={<RerunButton ticker={job.ticker} label={t({ id: "Jalankan ulang riset", en: "Rerun the research" })} />}>
            <strong className="font-bold">
              {t({ id: `Riset ${job.ticker} berhenti di fase ${phase.title.id}.`, en: `The ${job.ticker} research stopped in the ${phase.title.en} phase.` })}
            </strong>{" "}
            {lastError ? `${lastError.label}${lastError.detail ? ` (${lastError.detail})` : ""}. ` : ""}
            {t({ id: "Jalankan ulang riset; jika berhenti lagi, periksa log server lokal.", en: "Rerun the research; if it stops again, check the local server log." })}
          </Notice>
        ) : done && job.quality === "partial" ? (
          <Notice tone="warn">{t({
            id: "Analisis parsial: bukti belum cukup untuk semua bagian. Batasnya dijelaskan di company update dan jejak agent.",
            en: "Partial analysis: evidence does not yet cover every section. The limits are explained in the Company Update and the Audit Trace.",
          })}</Notice>
        ) : undefined}
        empty={job.state === "pending"
          ? t({ id: "Masuk antrean… Riset mulai begitu worker bebas.", en: "Queued… Research starts as soon as a worker is free." })
          : t({ id: "Agent memulai riset…", en: "Agents are starting the research…" })}
        result={result}
        actions={done ? <Actions links={links} rerun={<RerunButton ticker={job.ticker} label={t({ id: "Jalankan riset lagi", en: "Run the research again" })} />} /> : undefined} />
      {done && job.intel && (
        <section aria-label={t({ id: "Temuan agent analis", en: "Analyst agent findings" })} className="mt-4">
          <IntelPanel intel={job.intel} />
        </section>
      )}
    </Page>
  );
}

/* ---------------------------------------------------------------- replay */

export function DeckReplay() {
  const { t, lang } = useLang();
  const { ticker = "" } = useParams();
  const T = ticker.toUpperCase();
  const [load, setLoad] = useState<{ run?: RunReplay; error?: Error }>({});
  useEffect(() => {
    let live = true;
    setLoad({});
    api.reportRun(T).then((run) => live && setLoad({ run }), (error: Error) => live && setLoad({ error }));
    return () => { live = false; };
  }, [T]);

  const run = load.run;
  const events = run?.events ?? NO_EVENTS;
  const replay = useReplay(events, { speed: 4, autoplay: true });
  const state = useMemo(() => derive(replay.shown, { finished: replay.finished }), [replay.shown, replay.finished]);

  if (load.error) {
    const missing = load.error instanceof ApiError && load.error.status === 404;
    return (
      <Page>
        <Message title={missing
          ? t({ id: `Belum ada run tersimpan untuk ${T}`, en: `No stored run for ${T} yet` })
          : t({ id: "Run tersimpan belum bisa dimuat", en: "The stored run could not load" })}>
          {missing
            ? t({ id: "Hanya emiten yang sudah punya company update bisa diputar ulang.", en: "Only issuers that already have a Company Update can be replayed." })
            : `${load.error.message} ${t({ id: "Muat ulang halaman untuk mencoba lagi.", en: "Reload the page to try again." })}`}
          <div className="mt-4 flex flex-wrap gap-2">
            <Link className="btn btn-primary" to="/laporan">{t({ id: "Lihat laporan tersimpan", en: "View stored reports" })}</Link>
            <Link className="btn btn-ghost" to="/research">{t({ id: "Buka Deck riset", en: "Open the research Deck" })}</Link>
          </div>
        </Message>
      </Page>
    );
  }

  if (!run) {
    return (
      <Page>
        <DeckView state={IDLE} live={false} loading
          top={<RunHeader ticker={T} phase="pending" clock={clock(0)} counts={IDLE.counts} loading />} />
      </Page>
    );
  }

  const report = run.report;
  const finished = replay.finished;
  const playing = replay.playing && !finished;
  const phase: RunPhase = finished ? "completed" : playing ? "running" : "paused";
  const result = state.release && report ? fromReport(report, state, lang)
    : state.release ? fromRelease(state, lang)
    : finished && report ? fromReport(report, state, lang) : undefined;
  const links: Links = {
    report: !report || report.files.html ? `/files/reports/${T}.html` : undefined,
    trace: `/laporan/${T}/jejak`,
    pdf: report?.files.pdf ? `/files/reports/${T}.pdf` : undefined,
  };

  return (
    <Page>
      <DeckView state={state} live={playing} paused={!playing && !finished}
        top={
          <RunHeader ticker={run.ticker} name={run.name ?? report?.name} phase={phase} counts={state.counts}
            clock={<Tweened value={state.elapsed} format={clock} />}
            clockNote={run.source === "derived" ? t({ id: "durasi diperkirakan dari jejak audit", en: "durations estimated from the Audit Trace" }) : undefined}
            action={finished && links.report ? <OpenReport href={links.report} /> : undefined}
            controls={<ReplayControls replay={replay} events={events} source={run.source} />} />
        }
        result={result}
        actions={finished ? <Actions links={links} rerun={<RerunButton ticker={run.ticker} label={t({ id: "Jalankan riset baru", en: "Run new research" })} />} /> : undefined} />
    </Page>
  );
}

/* ---------------------------------------------------------------- notices */

function Notice({ tone, action, children }: { tone: "error" | "warn"; action?: ReactNode; children: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : undefined}
      className={`flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule px-5 py-3 text-[14px] leading-snug max-sm:px-4 ${
        tone === "error" ? "bg-err-bg text-err-ink" : "bg-warn-bg text-warn-ink"}`}>
      <p className="flex min-w-0 flex-1 basis-[320px] items-start gap-2.5">
        <CircleX aria-hidden className={`mt-[2px] size-4 flex-none ${tone === "warn" ? "hidden" : ""}`} strokeWidth={2.2} />
        <span>{children}</span>
      </p>
      {action}
    </div>
  );
}

function Message({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-rule bg-surface px-6 py-8 max-sm:px-4 max-sm:py-6">
      <h1 className="text-[22px] font-bold">{title}</h1>
      <div className="mt-2 max-w-[62ch] text-[15px] text-ink-soft">{children}</div>
    </section>
  );
}
