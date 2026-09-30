import { Link, useLocation } from "react-router-dom";
import { FileText, Search } from "lucide-react";
import { LiveMark } from "../components/Mark";
import { useLang } from "../lib/i18n";

export default function NotFound() {
  const { pathname } = useLocation();
  const { t } = useLang();
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
          <h1 className="text-[28px] font-black tracking-[-.02em]">{t({ id: "Halaman tidak ditemukan", en: "Page not found" })}</h1>
          <p className="mt-2 text-ink-soft">
            {t({
              id: "Alamat ini tidak ada di Sektoral. Mulai riset emiten baru di deck, atau buka company update yang sudah terbit.",
              en: "This address does not exist on Sektoral. Start research on a new issuer in the deck, or open a published company update.",
            })}
          </p>
          <div className="mt-6 flex flex-wrap gap-2.5 max-sm:flex-col">
            <Link className="btn btn-primary" to="/research">
              <Search aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Buka deck riset", en: "Open the research deck" })}
            </Link>
            <Link className="btn btn-ghost" to="/laporan">
              <FileText aria-hidden className="size-4" strokeWidth={2.2} />{t({ id: "Lihat laporan", en: "View reports" })}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
