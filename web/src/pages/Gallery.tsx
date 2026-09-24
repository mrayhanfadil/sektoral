import { useMemo, useState } from "react";
import { api, type ReportItem } from "../lib/api";
import { ReportGrid } from "../components/Reports";
import { Notice, useLoad } from "../components/State";
import { Icon } from "../components/Icon";

type Filter = "all" | "published" | "draft";
const FILTERS: [Filter, string][] = [["all", "Semua"], ["published", "Terbit"], ["draft", "Draft"]];

function matches(item: ReportItem, filter: Filter, query: string) {
  if (filter === "published" && !item.published) return false;
  if (filter === "draft" && item.published) return false;
  const q = query.trim().toLowerCase();
  return !q || item.ticker.toLowerCase().includes(q) || item.name.toLowerCase().includes(q);
}

export default function Gallery() {
  const { data: items, error, loading } = useLoad(api.reports);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const all = items ?? [];
  const published = all.filter((i) => i.published);
  const counts: Record<Filter, number> = { all: all.length, published: published.length, draft: all.length - published.length };
  const ratings = published.reduce<Record<string, number>>((acc, i) => ({ ...acc, [i.rating ?? ""]: (acc[i.rating ?? ""] ?? 0) + 1 }), {});
  const shown = useMemo(() => all.filter((i) => matches(i, filter, query)), [all, filter, query]);
  const tone = (rating: string) => (rating === "Buy" ? "pill-ok" : rating === "Sell" ? "pill-err" : "pill-live");

  return (
    <>
      <section aria-labelledby="gallery-title" className="border-b border-rule-soft bg-[radial-gradient(700px_300px_at_90%_-20%,var(--color-brand-50),transparent_70%)] pt-12 pb-7">
        <div className="wrap">
          <h1 id="gallery-title" className="mb-2.5 text-[clamp(28px,3.4vw,40px)] font-black tracking-[-.02em]">Company update</h1>
          <p className="max-w-[70ch] text-ink-soft">
            Setiap laporan memilih metode valuasi lewat gerbang framework, lalu menahan rating bila bukti belum cukup.
            Buka PDF, versi web, atau jejak audit untuk menelusuri tiap angka.
          </p>
          {all.length > 0 && (
            <div className="mt-[18px] flex flex-wrap gap-2.5">
              {Object.entries(ratings).sort().map(([rating, n]) => <span key={rating} className={`pill ${tone(rating)}`}>{n} {rating}</span>)}
              {counts.draft > 0 && <span className="pill pill-warn">{counts.draft} Draft</span>}
            </div>
          )}
        </div>
      </section>
      <section aria-label="Daftar laporan" className="pt-8 pb-[72px]">
        <div className="wrap">
          {all.length > 0 && (
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
              <div role="group" aria-label="Saring status" className="inline-flex rounded-lg border border-rule bg-surface p-1">
                {FILTERS.map(([value, label]) => (
                  <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}
                    className="cursor-pointer rounded-md px-3 py-1.5 text-sm font-bold text-ink-soft transition-colors hover:text-ink aria-pressed:bg-brand-50 aria-pressed:text-brand-ink">
                    {label} <span className="font-normal tabular-nums">{counts[value]}</span>
                  </button>
                ))}
              </div>
              <label className="relative block w-full max-w-[280px] max-sm:max-w-none">
                <span className="sr-only">Cari emiten</span>
                <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-faint"><Icon name="search" /></span>
                <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cari kode atau nama emiten"
                  className="h-10 w-full rounded-lg border border-rule bg-surface pr-3 pl-9 text-sm text-ink placeholder:text-ink-faint hover:border-rule-strong focus:border-brand-ink focus:shadow-[0_0_0_4px_var(--color-brand-100)] focus:outline-none" />
              </label>
            </div>
          )}
          {error && <Notice tone="error">Daftar laporan belum bisa dimuat. Pastikan server API berjalan, lalu muat ulang halaman.</Notice>}
          {loading && <p className="text-ink-soft">Memuat laporan…</p>}
          {!loading && !error && !all.length && (
            <Notice>
              <strong>Belum ada laporan.</strong> Jalankan{" "}
              <code className="rounded-md border border-rule-soft bg-surface px-1.5 py-0.5 text-[13px]">python -m app.batch BBCA JPFA --out out/reports --pdf</code>{" "}
              lalu muat ulang halaman ini.
            </Notice>
          )}
          {all.length > 0 && shown.length === 0 && (
            <Notice>
              Tidak ada laporan yang cocok.{" "}
              <button type="button" onClick={() => { setFilter("all"); setQuery(""); }} className="cursor-pointer font-bold text-brand-ink underline">
                Tampilkan semua laporan
              </button>
            </Notice>
          )}
          {shown.length > 0 && <ReportGrid items={shown} />}
        </div>
      </section>
    </>
  );
}
