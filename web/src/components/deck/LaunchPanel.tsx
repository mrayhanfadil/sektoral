// The Deck's command line: type a ticker and run, open the palette, pick a
// ticker with data, or play back a stored run.
import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronRight, CircleAlert, Play, Search } from "lucide-react";
import { api, type ReportItem } from "../../lib/api";
import { rp } from "../../lib/format";
import { ratingLabel, ratingTone } from "../../lib/labels";
import { useLoad } from "../State";
import { usePalette } from "../CommandPalette";
import { IssuerLogo } from "../IssuerLogo";
import { keepRunToken, launch, readRunToken, useLiveRuns } from "../../lib/launch";

const TICKER = /^[A-Za-z0-9][A-Za-z0-9.-]{0,9}$/;
const RATING_INK = { buy: "text-ok-ink", hold: "text-ink-strong", sell: "text-err-ink", review: "text-warn-ink" };

export function LaunchPanel() {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] border-b border-rule min-[1100px]:grid-cols-12">
      <CommandLine />
      <StoredRuns />
    </div>
  );
}

function CommandLine() {
  const navigate = useNavigate();
  const palette = usePalette();
  const input = useRef<HTMLInputElement>(null);
  const { data: tickers = [], loading } = useLoad(api.tickers);
  const [ticker, setTicker] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mode = useLiveRuns();
  const [runToken, setRunToken] = useState(readRunToken);
  const value = ticker.trim().toUpperCase();

  async function start(event: FormEvent) {
    event.preventDefault();
    if (!TICKER.test(value)) {
      setError(value ? `"${value}" bukan kode emiten yang valid. Pakai huruf dan angka, misalnya AMMN.` : "Ketik kode emiten dulu, misalnya AMMN.");
      input.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      navigate((await launch(value)).path);
    } catch (e) {
      setError((e as Error).message || "Riset belum bisa dimulai. Coba lagi sebentar lagi.");
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="launch-title" className="px-5 py-5 max-sm:px-4 max-sm:py-4 min-[1100px]:col-span-7 min-[1100px]:border-r min-[1100px]:border-rule">
      <h1 id="launch-title" className="text-[20px] font-bold">Jalankan riset emiten</h1>
      <p className="mt-1 max-w-[62ch] text-[14px] text-ink-soft">
        Agent menyusun rencana, memanggil tool data Sectors, lalu gerbang metode memilih valuasi. Semua langkahnya tampil di deck di bawah.
        {mode === "token" && " Di situs ini, emiten yang sudah diriset diputar ulang dari jejak auditnya, langkah demi langkah, tanpa memanggil model lagi."}
      </p>
      <form onSubmit={start} noValidate className="mt-4">
        <label htmlFor="deck-ticker" className="sr-only">Kode emiten BEI</label>
        <div className="flex gap-2 max-sm:flex-col">
          <div className={`group flex h-14 min-w-0 flex-1 items-center gap-2 rounded-md border bg-raised pr-2 pl-3 transition-[border-color,box-shadow] duration-200 focus-within:border-brand-ink focus-within:shadow-[0_0_0_3px_var(--color-brand-100)] ${
            error ? "border-err-ink" : "border-rule-strong hover:border-ink-faint"}`}>
            <ChevronRight aria-hidden className="size-5 flex-none text-brand-ink" strokeWidth={2.4} />
            <input ref={input} id="deck-ticker" name="ticker" value={ticker} maxLength={10} autoComplete="off" spellCheck={false}
              placeholder="Kode emiten, misalnya AMMN" aria-invalid={error ? true : undefined} aria-describedby={error ? "deck-ticker-error" : undefined}
              onChange={(e) => { setTicker(e.target.value); setError(null); }}
              className="h-full w-full min-w-0 flex-1 bg-transparent font-mono text-[22px] font-semibold tracking-[.06em] text-ink-strong uppercase outline-none placeholder:font-sans placeholder:text-[15px] placeholder:font-normal placeholder:tracking-normal placeholder:normal-case placeholder:text-ink-faint focus-visible:outline-none" />
            <button type="button" onClick={() => palette.open(value)}
              className="flex h-9 flex-none cursor-pointer items-center gap-2 rounded-[5px] px-2 text-[13.5px] font-medium text-ink-soft transition-colors hover:bg-surface hover:text-ink-strong max-sm:px-1.5">
              <Search aria-hidden className="size-4" strokeWidth={2.2} />
              <span className="max-sm:sr-only">Cari cepat</span>
              <kbd className="kbd max-sm:hidden">⌘K</kbd>
            </button>
          </div>
          <button type="submit" disabled={busy} className="btn btn-primary h-14 px-6 text-[15.5px] max-sm:w-full">
            {busy ? "Memulai…" : "Jalankan riset"}
          </button>
        </div>
        {error && (
          <p id="deck-ticker-error" role="alert" className="mt-2.5 flex items-start gap-2 rounded-md bg-err-bg px-3 py-2 text-[14px] font-medium text-err-ink">
            <CircleAlert aria-hidden className="mt-[3px] size-4 flex-none" strokeWidth={2.2} />{error}
          </p>
        )}
      </form>
      <div className="mt-4">
        <p id="picks-title" className="text-[13px] text-ink-soft">Emiten yang sudah diriset</p>
        <div role="group" aria-labelledby="picks-title" className="mt-2 flex flex-wrap gap-1.5">
          {loading && Array.from({ length: 10 }, (_, i) => <span key={i} aria-hidden className="h-8 w-14 animate-pulse rounded-md bg-raised" />)}
          {tickers.map((t) => (
            <button key={t} type="button" aria-pressed={value === t}
              onClick={() => { setTicker(t); setError(null); input.current?.focus(); }}
              className="h-8 cursor-pointer rounded-md border border-rule px-2.5 font-mono text-[13px] font-semibold tracking-[.03em] text-ink transition-[color,background-color,border-color,transform] duration-150 hover:border-brand-ink hover:bg-brand-50 hover:text-brand-ink active:scale-95 aria-pressed:border-brand aria-pressed:bg-brand aria-pressed:text-white">
              {t}
            </button>
          ))}
        </div>
      </div>
      {mode === "token" && (
        <details className="mt-4 text-[13.5px]">
          <summary className="cursor-pointer text-ink-soft">Riset langsung dengan token pemilik</summary>
          <div className="mt-2 flex max-w-[420px] gap-2">
            <label htmlFor="run-token" className="sr-only">Token riset</label>
            <input id="run-token" type="password" value={runToken} autoComplete="off"
              onChange={(e) => { setRunToken(e.target.value); keepRunToken(e.target.value.trim()); }}
              placeholder="Token riset"
              className="h-9 min-w-0 flex-1 rounded-md border border-rule bg-raised px-3 text-[14px] text-ink-strong placeholder:text-ink-faint focus:border-brand-ink" />
          </div>
          <p className="mt-1.5 text-ink-faint">Dengan token, emiten apa pun dijalankan langsung oleh agent dan memakai kredit API.</p>
        </details>
      )}
    </section>
  );
}

function StoredRuns() {
  const { data: reports = [], loading, error } = useLoad(api.reports);
  return (
    <section aria-labelledby="stored-title" className="px-5 py-5 max-sm:px-4 max-sm:py-4 min-[1100px]:col-span-5 max-[1099px]:border-t max-[1099px]:border-rule">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="stored-title" className="text-[16px] font-bold">Putar ulang run tersimpan</h2>
        {reports.length > 0 && <span className="data text-ink-soft">{reports.length} run</span>}
      </div>
      <p className="mt-1 text-[13.5px] text-ink-soft">Tonton ulang run yang sudah menghasilkan company update, tanpa memanggil model.</p>
      {error && <p role="alert" className="mt-3 text-[14px] text-err-ink">Daftar run belum bisa dimuat. Muat ulang halaman untuk mencoba lagi.</p>}
      {!error && !loading && reports.length === 0 && <p className="mt-3 text-[14px] text-ink-soft">Belum ada run tersimpan. Jalankan riset pertama di sebelah kiri.</p>}
      <ul className="m-0 mt-3 grid list-none border-t border-rule-soft p-0">
        {loading && Array.from({ length: 5 }, (_, i) => (
          <li key={i} aria-hidden className="flex items-center gap-3 border-b border-rule-soft py-2.5">
            <span className="h-4 w-12 animate-pulse rounded bg-raised" /><span className="h-3 flex-1 animate-pulse rounded bg-raised" />
          </li>
        ))}
        {reports.map((r) => <StoredRun key={r.ticker} r={r} />)}
      </ul>
    </section>
  );
}

function StoredRun({ r }: { r: ReportItem }) {
  const rating = ratingLabel(r);
  return (
    <li className="border-b border-rule-soft">
      <Link to={`/laporan/${r.ticker}/putar`} aria-label={`Putar ulang run ${r.ticker}, ${r.name}`}
        className="group grid grid-cols-[58px_minmax(0,1fr)_auto_18px] items-center gap-3 rounded-[4px] py-2 pr-1 pl-1 text-ink no-underline transition-colors hover:bg-raised">
        <span className="font-mono text-[14px] font-bold text-ink-strong">{r.ticker}</span>
        <span className="flex min-w-0 items-center gap-2.5">
          <IssuerLogo ticker={r.ticker} size="sm" className="max-sm:hidden" />
          <span className="truncate text-[13.5px] text-ink-soft">{r.name}</span>
        </span>
        <span className="flex items-baseline gap-2.5 font-mono text-[13px] tabular-nums">
          <span className={`font-semibold ${RATING_INK[ratingTone(r)]}`}>{rating}</span>
          {r.published && r.tp !== null && <span className="text-ink max-sm:hidden">TP Rp{rp(r.tp)}</span>}
        </span>
        <Play aria-hidden className="size-3.5 text-ink-faint transition-colors group-hover:text-brand-ink" strokeWidth={2.4} fill="currentColor" />
      </Link>
    </li>
  );
}
