import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "./Brand";

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

const navLink = "rounded-lg px-3 py-2 text-[15px] font-medium text-ink-soft no-underline hover:bg-canvas hover:text-ink max-md:hidden";

function SiteHeader() {
  return (
    <>
      <a href="#konten" className="absolute -top-12 left-4 z-[100] rounded-b-lg bg-brand px-3.5 py-2 font-bold text-white no-underline focus:top-0">
        Lewati ke konten utama
      </a>
      <header className="sticky top-0 z-50 border-b border-rule-soft bg-white/90 backdrop-blur-md">
        <div className="wrap flex h-16 items-center justify-between gap-4">
          <Link to="/" aria-label="Sectoral, beranda" className="flex-none">
            <Logo />
          </Link>
          <nav aria-label="Navigasi utama" className="flex items-center gap-1">
            <Link to="/#cara-kerja" className={navLink}>Cara kerja</Link>
            <Link to="/#framework" className={navLink}>Framework</Link>
            <NavLink to="/laporan" end className={({ isActive }) => `${navLink} ${isActive ? "!text-brand" : ""}`}>
              Laporan
            </NavLink>
            <Link to="/research" className="btn btn-primary ml-2 min-h-0 px-3 py-2 text-[15px] max-md:ml-0">
              Coba riset emiten
            </Link>
          </nav>
        </div>
      </header>
    </>
  );
}

function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-rule-soft bg-canvas">
      <div className="wrap grid gap-[18px] pt-7 pb-8">
        <p className="max-w-[80ch] text-[13.5px] text-ink-soft">
          <strong>Bukan rekomendasi investasi.</strong> Sectoral menyajikan informasi dan analisis untuk mendukung kerja
          analis. Rating dan target harga hanya muncul setelah pemeriksaan data, forecast, dan valuasi lolos. Sectoral
          tidak terhubung ke broker dan tidak mengeksekusi transaksi. Keputusan investasi tetap tanggung jawab pembaca.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3 text-[13px] text-ink-soft">
          <Logo className="h-5" />
          <nav aria-label="Tautan footer" className="flex flex-wrap gap-4 [&>a]:text-ink-soft [&>a]:no-underline [&>a:hover]:text-brand">
            <Link to="/research">Aplikasi riset</Link>
            <Link to="/laporan">Laporan</Link>
            <Link to="/#cara-kerja">Cara kerja</Link>
            <Link to="/#pemeriksaan">Pemeriksaan bukti</Link>
            <Link to="/#batasan">Batasan</Link>
          </nav>
          <span>© 2026 Sectoral, dibuat untuk Sectors Hackathon 2026</span>
        </div>
      </div>
    </footer>
  );
}

export default function Layout() {
  useScrollToHash();
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main id="konten" className="flex-1">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
