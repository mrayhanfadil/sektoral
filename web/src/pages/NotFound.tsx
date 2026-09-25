import { Link, useLocation } from "react-router-dom";
import { FileText, Search } from "lucide-react";
import { LiveMark } from "../components/Mark";

export default function NotFound() {
  const { pathname } = useLocation();
  return (
    <div className="wrap py-20 max-sm:py-12">
      <div className="panel max-w-[640px]">
        <div className="flex items-center justify-between gap-4 border-b border-rule px-6 py-3 max-sm:px-4">
          <code className="min-w-0 truncate font-mono text-[13px] text-ink-soft">{pathname}</code>
          <span className="data inline-flex flex-none items-center gap-2 text-ink-soft">
            <LiveMark status="idle" className="h-2.5 w-3" />404
          </span>
        </div>
        <div className="px-6 py-7 max-sm:px-4">
          <h1 className="text-[28px] font-black tracking-[-.02em]">Halaman tidak ditemukan</h1>
          <p className="mt-2 text-ink-soft">
            Alamat ini tidak ada di Sectoral. Mulai riset emiten baru di deck, atau buka company update yang sudah terbit.
          </p>
          <div className="mt-6 flex flex-wrap gap-2.5 max-sm:flex-col">
            <Link className="btn btn-primary" to="/research">
              <Search aria-hidden className="size-4" strokeWidth={2.2} />Buka deck riset
            </Link>
            <Link className="btn btn-ghost" to="/laporan">
              <FileText aria-hidden className="size-4" strokeWidth={2.2} />Lihat laporan
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
