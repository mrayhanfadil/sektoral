// The deck's Cmd-K palette: find an issuer, then run a new research, play a
// stored run back, or open its company update. Any page can open it through
// usePalette().
import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CornerDownLeft, FileText, Play, Search, SquareTerminal, Compass } from "lucide-react";
import { api, readerFiles, type ReportItem } from "../lib/api";
import { ratingLabel } from "../lib/labels";
import { rp } from "../lib/format";
import { launch } from "../lib/launch";
import { useLang } from "../lib/i18n";

type PaletteApi = { open: (query?: string) => void; close: () => void };
const PaletteContext = createContext<PaletteApi>({ open: () => {}, close: () => {} });

/** Open the Cmd-K palette from anywhere, optionally with a query typed in. */
export const usePalette = () => useContext(PaletteContext);

const TICKER = /^[A-Za-z0-9][A-Za-z0-9.-]{0,9}$/;

type Item = {
  id: string;
  group: string;
  label: string;
  sub?: string;
  hint: string;
  icon: "run" | "replay" | "report" | "nav";
  run: () => void | Promise<void>;
};

const ICONS = { run: SquareTerminal, replay: Play, report: FileText, nav: Compass };

export function PaletteProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ open: boolean; query: string }>({ open: false, query: "" });
  const open = useCallback((query = "") => setState({ open: true, query }), []);
  const close = useCallback(() => setState((s) => ({ ...s, open: false })), []);
  const api_ = useMemo(() => ({ open, close }), [open, close]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setState((s) => ({ open: !s.open, query: "" }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <PaletteContext.Provider value={api_}>
      {children}
      <AnimatePresence>{state.open && <Palette key="palette" initial={state.query} onClose={close} />}</AnimatePresence>
    </PaletteContext.Provider>
  );
}

function useData() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [tickers, setTickers] = useState<string[]>([]);
  useEffect(() => {
    let live = true;
    api.reports().then((r) => live && setReports(r)).catch(() => {});
    api.tickers().then((t) => live && setTickers(t)).catch(() => {});
    return () => { live = false; };
  }, []);
  return { reports, tickers };
}

function Palette({ initial, onClose }: { initial: string; onClose: () => void }) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const { t, lang } = useLang();
  const { reports, tickers } = useData();
  const [query, setQuery] = useState(initial);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const returnFocus = useRef<Element | null>(document.activeElement);
  const listId = useId();

  useEffect(() => {
    input.current?.focus();
    const previous = returnFocus.current;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);

  const go = useCallback((to: string) => { onClose(); navigate(to); }, [navigate, onClose]);
  const start = useCallback(async (ticker: string) => {
    setBusy(ticker);
    setError(null);
    try {
      const { path } = await launch(ticker);
      onClose();
      navigate(path);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }, [navigate, onClose]);

  const items = useMemo<Item[]>(() => {
    const q = query.trim().toUpperCase();
    const out: Item[] = [];
    const known = new Set(reports.map((r) => r.ticker));
    if (q && TICKER.test(q)) {
      out.push({ id: `run-${q}`, group: t({ id: "Aksi", en: "Actions" }), label: t({ id: `Jalankan riset ${q}`, en: `Run research on ${q}` }),
        sub: t({ id: "Agent menyusun rencana, memanggil tool, lalu menulis company update", en: "The agent plans, calls tools, then writes the company update" }),
        hint: t({ id: "Mulai", en: "Start" }), icon: "run", run: () => start(q) });
    }
    const match = (text: string) => !q || text.toUpperCase().includes(q);
    for (const r of reports.filter((r) => match(`${r.ticker} ${r.name}`)).slice(0, 6)) {
      out.push({ id: `replay-${r.ticker}`, group: t({ id: "Putar ulang run tersimpan", en: "Replay a stored run" }), label: r.ticker, sub: r.name,
        hint: r.published ? `${ratingLabel(r)}, TP Rp${rp(r.tp)}` : ratingLabel(r), icon: "replay",
        run: () => go(`/laporan/${r.ticker}/putar`) });
    }
    for (const r of reports.filter((r) => q && r.ticker === q && r.files.html)) {
      out.push({ id: `report-${r.ticker}`, group: t({ id: "Laporan", en: "Reports" }), label: `Company update ${r.ticker}`, sub: r.headline || r.name,
        hint: t({ id: "Buka", en: "Open" }), icon: "report", run: () => { onClose(); window.location.assign(readerFiles(r, lang).html); } });
    }
    const fresh = tickers.filter((tk) => match(tk) && tk !== q && !known.has(tk)).slice(0, q ? 6 : 4);
    for (const ticker of fresh) {
      out.push({ id: `run-${ticker}`, group: t({ id: "Jalankan riset", en: "Run research" }), label: ticker,
        sub: t({ id: "Belum ada laporan tersimpan", en: "No stored report yet" }), hint: t({ id: "Mulai", en: "Start" }), icon: "run", run: () => start(ticker) });
    }
    const nav: [string, string, string][] = [
      [t({ id: "Riset", en: "Research" }), "/research", "F1"],
      [t({ id: "Laporan", en: "Reports" }), "/laporan", "F2"],
      [t({ id: "Cara kerja", en: "How it works" }), "/#cara-kerja", "F3"],
    ];
    for (const [label, to, key] of nav.filter(([label]) => match(label))) {
      out.push({ id: `nav-${to}`, group: t({ id: "Navigasi", en: "Navigation" }), label, hint: key, icon: "nav", run: () => go(to) });
    }
    return out;
  }, [query, reports, tickers, start, go, onClose, t, lang]);

  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && items[active] && !busy) { e.preventDefault(); items[active].run(); }
    else if (e.key === "Tab") { e.preventDefault(); }
  };

  let lastGroup = "";
  return (
    <motion.div className="fixed inset-0 z-[200] flex items-start justify-center px-4 pt-[12vh] max-sm:pt-4"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16 }}>
      <div aria-hidden className="absolute inset-0 bg-[rgb(6_10_24/.45)] dark:bg-[rgb(0_0_0/.6)]" onClick={onClose} />
      <motion.div role="dialog" aria-modal="true" aria-label={t({ id: "Cari emiten dan perintah", en: "Search issuers and commands" })} onKeyDown={onKeyDown}
        className="relative w-full max-w-[620px] overflow-hidden rounded-xl border border-rule bg-surface shadow-[var(--shadow-pop)]"
        initial={reduce ? false : { opacity: 0, y: -10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.985 }} transition={{ type: "spring", stiffness: 520, damping: 38, mass: 0.7 }}>
        <div className="flex items-center gap-3 border-b border-rule px-4">
          <Search aria-hidden className="size-[18px] flex-none text-ink-faint" strokeWidth={2.2} />
          <input ref={input} value={query} onChange={(e) => { setQuery(e.target.value); setError(null); }}
            role="combobox" aria-expanded="true" aria-controls={listId} aria-autocomplete="list"
            aria-activedescendant={items[active] ? `${listId}-${active}` : undefined}
            placeholder={t({ id: "Kode emiten, misalnya AMMN", en: "Ticker, for example AMMN" })} spellCheck={false} autoComplete="off" maxLength={24}
            className="h-14 min-w-0 flex-1 bg-transparent font-mono text-[17px] font-medium tracking-[.04em] text-ink-strong uppercase outline-none placeholder:font-sans placeholder:text-[15px] placeholder:tracking-normal placeholder:normal-case placeholder:text-ink-faint" />
          <kbd className="kbd">Esc</kbd>
        </div>
        {error && <p role="alert" className="border-b border-rule bg-err-bg px-4 py-2.5 text-[14px] font-medium text-err-ink">{error}</p>}
        <ul ref={list} id={listId} role="listbox" aria-label={t({ id: "Hasil", en: "Results" })} className="m-0 max-h-[min(440px,62vh)] list-none overflow-y-auto overscroll-contain p-2">
          {items.length === 0 && <li className="px-3 py-8 text-center text-[14px] text-ink-soft">
            {t({ id: "Tidak ada yang cocok. Ketik kode emiten BEI untuk menjalankan riset baru.", en: "Nothing matches. Type an IDX ticker to run new research." })}
          </li>}
          {items.map((item, i) => {
            const Icon = ICONS[item.icon];
            const header = item.group !== lastGroup ? (lastGroup = item.group) : null;
            const selected = i === active;
            return (
              <li key={item.id} role="presentation">
                {header && <div role="presentation" className="data px-3 pt-3 pb-1.5 text-ink-faint">{header}</div>}
                <div id={`${listId}-${i}`} role="option" aria-selected={selected} data-index={i}
                  onMouseMove={() => active !== i && setActive(i)} onClick={() => !busy && item.run()}
                  className="relative flex cursor-pointer items-center gap-3 rounded-md px-3 py-2.5">
                  {selected && (
                    <motion.span layoutId="palette-active" aria-hidden className="absolute inset-0 rounded-md bg-brand-50"
                      transition={{ type: "spring", stiffness: 700, damping: 45 }} />
                  )}
                  <Icon aria-hidden className={`relative size-4 flex-none ${selected ? "text-brand-ink" : "text-ink-faint"}`} strokeWidth={2.2} />
                  <span className="relative min-w-0 flex-1">
                    <span className={`block truncate font-mono text-[14.5px] font-semibold ${selected ? "text-ink-strong" : "text-ink"}`}>{item.label}</span>
                    {item.sub && <span className="block truncate text-[13px] text-ink-soft">{item.sub}</span>}
                  </span>
                  <span className="relative flex flex-none items-center gap-1.5 text-[12.5px] text-ink-soft">
                    {busy && item.id === `run-${busy}` ? t({ id: "Memulai…", en: "Starting…" }) : item.hint}
                    {selected && <CornerDownLeft aria-hidden className="size-3.5 text-brand-ink" />}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
        <div className="flex items-center gap-4 border-t border-rule bg-raised px-4 py-2 text-[12px] text-ink-soft max-sm:hidden">
          <span className="flex items-center gap-1.5"><kbd className="kbd">↑</kbd><kbd className="kbd">↓</kbd> {t({ id: "pilih", en: "select" })}</span>
          <span className="flex items-center gap-1.5"><kbd className="kbd">↵</kbd> {t({ id: "jalankan", en: "run" })}</span>
          <span className="ml-auto">{t({ id: "Run tersimpan diputar ulang dari jejak auditnya.", en: "Stored runs replay from their audit trace." })}</span>
        </div>
      </motion.div>
    </motion.div>
  );
}
