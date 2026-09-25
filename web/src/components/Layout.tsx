import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { Search } from "lucide-react";
import { Logo } from "./Brand";
import { ThemeToggle } from "./Theme";
import { PaletteProvider, usePalette } from "./CommandPalette";

function useScrollToHash() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);
}

/** Function-key tabs of the deck; F1–F3 also work from the keyboard. */
const KEYS = [
  { key: "F1", label: "Riset", to: "/research", match: (p: string) => p === "/research" || p.startsWith("/jobs/") || p.endsWith("/putar") },
  { key: "F2", label: "Laporan", to: "/laporan", match: (p: string) => p === "/laporan" || p.endsWith("/jejak") },
  { key: "F3", label: "Cara kerja", to: "/#cara-kerja", match: () => false },
];

function useFunctionKeys() {
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
      const hit = KEYS.find((k) => k.key === e.key);
      if (hit) {
        e.preventDefault();
        navigate(hit.to);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);
}

/** Jakarta wall clock, the deck's time reference. */
function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000 * 15);
    return () => window.clearInterval(id);
  }, []);
  const time = new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" }).format(now);
  return (
    <time dateTime={now.toISOString()} className="data text-ink-soft max-lg:hidden" title="Waktu Jakarta">
      {time} WIB
    </time>
  );
}

function DeckBar() {
  const { pathname } = useLocation();
  const palette = usePalette();
  return (
    <>
      <a href="#konten" className="absolute -top-12 left-4 z-[100] rounded-b-md bg-brand px-3.5 py-2 font-bold text-white no-underline focus:top-0">
        Lewati ke konten utama
      </a>
      <header className="sticky top-0 z-50 border-b border-rule bg-surface">
        <div className="wrap flex h-[52px] items-center gap-5 max-sm:gap-2">
          <Link to="/" aria-label="Sectoral, beranda" className="flex-none">
            <Logo className="h-[22px]" />
          </Link>
          <nav aria-label="Navigasi utama" className="flex h-full items-stretch gap-1 max-sm:ml-auto">
            {KEYS.map((k) => {
              const active = k.match(pathname);
              return (
                <Link key={k.key} to={k.to} aria-current={active ? "page" : undefined}
                  className={`group relative flex items-center gap-2 px-2.5 text-[14px] font-medium no-underline transition-colors max-sm:px-2 ${
                    active ? "text-ink-strong" : "text-ink-soft hover:text-ink-strong"}`}>
                  <kbd className={`kbd transition-colors max-sm:hidden ${active ? "!border-brand-ink/40 !text-brand-ink" : "group-hover:text-ink"}`}>{k.key}</kbd>
                  <span className={k.key === "F3" ? "max-md:hidden" : ""}>{k.label}</span>
                  {active && (
                    <motion.span layoutId="deck-tab" aria-hidden className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-brand-ink"
                      transition={{ type: "spring", stiffness: 500, damping: 40 }} />
                  )}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-3 max-sm:ml-0 max-sm:gap-1">
            <button type="button" onClick={() => palette.open()}
              className="group flex h-9 cursor-pointer items-center gap-2.5 rounded-md border border-rule bg-raised pr-1.5 pl-3 text-[14px] text-ink-soft transition-colors hover:border-rule-strong hover:text-ink-strong max-sm:size-9 max-sm:justify-center max-sm:p-0">
              <Search aria-hidden className="size-4" strokeWidth={2.2} />
              <span className="max-sm:sr-only">Cari emiten</span>
              <kbd className="kbd max-sm:hidden">⌘K</kbd>
            </button>
            <Clock />
            <ThemeToggle />
          </div>
        </div>
      </header>
    </>
  );
}

function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-rule bg-surface">
      <div className="wrap grid gap-4 pt-6 pb-7">
        <p className="max-w-[88ch] text-[13.5px] text-ink-soft">
          <strong className="text-ink">Bukan rekomendasi investasi.</strong> Sectoral menyajikan informasi dan analisis untuk mendukung kerja
          analis. Rating dan target harga hanya muncul setelah pemeriksaan data, forecast, dan valuasi lolos. Sectoral
          tidak terhubung ke broker dan tidak mengeksekusi transaksi. Keputusan investasi tetap tanggung jawab pembaca.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3 text-[13px] text-ink-soft">
          <Logo className="h-[18px]" />
          <nav aria-label="Tautan footer" className="flex flex-wrap gap-4 [&>a]:text-ink-soft [&>a]:no-underline [&>a:hover]:text-brand-ink">
            <Link to="/research">Riset</Link>
            <Link to="/laporan">Laporan</Link>
            <Link to="/#cara-kerja">Cara kerja</Link>
            <Link to="/#batasan">Batasan</Link>
          </nav>
          <span>© 2026 Sectoral, dibuat untuk Sectors Hackathon 2026</span>
        </div>
      </div>
    </footer>
  );
}

function Shell() {
  useScrollToHash();
  useFunctionKeys();
  return (
    <div className="flex min-h-screen flex-col">
      <DeckBar />
      <main id="konten" className="flex-1">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}

export default function Layout() {
  return (
    <PaletteProvider>
      <Shell />
    </PaletteProvider>
  );
}
