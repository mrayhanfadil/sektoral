import { api } from "../lib/api";
import { ReportGrid } from "../components/Reports";
import { Notice, useLoad } from "../components/State";

export default function Gallery() {
  const { data: items, error, loading } = useLoad(api.reports);
  const published = (items ?? []).filter((i) => i.published);
  const counts = published.reduce<Record<string, number>>((acc, i) => ({ ...acc, [i.rating ?? ""]: (acc[i.rating ?? ""] ?? 0) + 1 }), {});
  const drafts = (items?.length ?? 0) - published.length;
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
          <div className="mt-[18px] flex flex-wrap gap-2.5">
            {Object.entries(counts).sort().map(([rating, n]) => <span key={rating} className={`pill ${tone(rating)}`}>{n} {rating}</span>)}
            {drafts > 0 && <span className="pill pill-warn">{drafts} Draft</span>}
          </div>
        </div>
      </section>
      <section aria-label="Daftar laporan" className="pt-8 pb-[72px]">
        <div className="wrap">
          {error && <Notice tone="error">Daftar laporan belum bisa dimuat. Pastikan server API berjalan, lalu muat ulang halaman.</Notice>}
          {!loading && !error && !items?.length && (
            <Notice>
              <strong>Belum ada laporan.</strong> Jalankan{" "}
              <code className="rounded-md border border-rule-soft bg-white px-1.5 py-0.5 font-mono text-[13px]">python -m app.batch BBCA JPFA --out out/reports --pdf</code>{" "}
              lalu muat ulang halaman ini.
            </Notice>
          )}
          {items && items.length > 0 && <ReportGrid items={items} />}
        </div>
      </section>
    </>
  );
}
