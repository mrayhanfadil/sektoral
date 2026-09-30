// The landing's command line: type an IDX ticker and start a research run,
// or open the Cmd-K palette to find one.
import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, CircleAlert, Search } from "lucide-react";
import { usePalette } from "../CommandPalette";
import { launch, useLiveRuns } from "../../lib/launch";
import { useLang, type Bi } from "../../lib/i18n";

const TICKER = /^[A-Za-z0-9][A-Za-z0-9.-]{0,9}$/;

/** Reader-facing problem with a typed ticker, or null when it can be submitted. */
export function tickerProblem(value: string): Bi | null {
  const ticker = value.trim();
  if (!ticker) return { id: "Ketik kode emiten dulu, misalnya AMMN.", en: "Type a ticker first, for example AMMN." };
  if (!TICKER.test(ticker)) {
    return {
      id: "Kode emiten hanya berisi huruf, angka, titik, atau tanda hubung, paling banyak 10 karakter.",
      en: "A ticker holds only letters, digits, dots, or hyphens, at most 10 characters.",
    };
  }
  return null;
}

export function Launcher({ id }: { id: string }) {
  const navigate = useNavigate();
  const palette = usePalette();
  const { t } = useLang();
  const input = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  // A message from the API or launcher is shown as-is; our own follows the language.
  const [error, setError] = useState<Bi | string | null>(null);
  const [busy, setBusy] = useState(false);
  const mode = useLiveRuns();
  const inputId = `${id}-ticker`;
  const errorId = `${id}-error`;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const problem = tickerProblem(value);
    if (problem) {
      setError(problem);
      input.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      navigate((await launch(value.trim().toUpperCase())).path);
    } catch (err) {
      setError((err as Error).message || { id: "Riset belum bisa dimulai. Coba lagi sebentar lagi.", en: "Research could not start. Try again in a moment." });
      setBusy(false);
      input.current?.focus();
    }
  };

  return (
    <form onSubmit={submit} noValidate aria-label={t({ id: "Jalankan riset emiten", en: "Run issuer research" })}>
      <div className="flex gap-2 max-sm:flex-col">
        <div className={`flex h-14 min-w-0 flex-none items-center sm:flex-1 rounded-lg border bg-surface transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand-ink ${
          error ? "border-err-ink" : "border-rule-strong hover:border-ink-faint"}`}>
          <ChevronRight aria-hidden className="ml-3 size-[18px] flex-none text-brand-ink" strokeWidth={2.4} />
          <label htmlFor={inputId} className="sr-only">{t({ id: "Kode emiten", en: "Ticker" })}</label>
          <input ref={input} id={inputId} value={value} readOnly={busy}
            onChange={(e) => { setValue(e.target.value.toUpperCase()); if (error) setError(null); }}
            placeholder={t({ id: "Kode emiten, misalnya AMMN", en: "Ticker, for example AMMN" })} maxLength={10} autoComplete="off" autoCapitalize="characters" spellCheck={false}
            aria-invalid={error ? true : undefined} aria-describedby={error ? errorId : undefined}
            className="h-full min-w-0 flex-1 bg-transparent pr-3 pl-2 font-mono text-[17px] font-semibold tracking-[.06em] text-ink-strong uppercase outline-none focus-visible:outline-none read-only:opacity-60 placeholder:font-sans placeholder:text-[15px] placeholder:font-normal placeholder:tracking-normal placeholder:normal-case placeholder:text-ink-faint" />
        </div>
        <button type="submit" disabled={busy} aria-busy={busy || undefined} className="btn btn-primary h-14 px-5 text-[15.5px]">
          {busy ? t({ id: "Memulai riset…", en: "Starting research…" }) : t({ id: "Jalankan riset", en: "Run research" })}
        </button>
      </div>
      <div aria-live="polite">
        {error && (
          <p id={errorId} role="alert" className="mt-2.5 flex items-start gap-2 text-[14px] leading-snug text-err-ink">
            <CircleAlert aria-hidden className="mt-px size-4 flex-none" strokeWidth={2.2} />
            {typeof error === "string" ? error : t(error)}
          </p>
        )}
      </div>
      {mode === "token" && (
        <p className="mt-2.5 text-[13.5px] text-ink-soft">
          {t({
            id: "Di situs ini, emiten yang sudah diriset diputar ulang dari jejak auditnya, langkah demi langkah, tanpa memanggil model lagi.",
            en: "On this site, issuers already researched are replayed from their audit trace, step by step, without calling the model again.",
          })}
        </p>
      )}
      <button type="button" onClick={() => palette.open(value.trim())}
        className="btn btn-ghost btn-sm mt-3 gap-2.5 pr-1.5 text-ink hover:text-ink-strong">
        <Search aria-hidden className="size-4 text-ink-soft" strokeWidth={2.2} />
        {t({ id: "Cari emiten", en: "Search issuers" })}
        <kbd className="kbd">⌘K</kbd>
      </button>
    </form>
  );
}
