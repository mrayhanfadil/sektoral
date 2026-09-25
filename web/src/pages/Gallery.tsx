import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { RefreshCw, Search, X } from "lucide-react";
import { api, type ReportItem } from "../lib/api";
import { ratingLabel, ratingTone } from "../lib/labels";
import { ChainLegend, formatDay, ReportRegister, type Sort } from "../components/Reports";
import { Notice, useLoad } from "../components/State";

type Filter = "all" | "published" | "draft";
const FILTERS: [Filter, string][] = [["all", "Semua"], ["published", "Terbit"], ["draft", "Draft"]];

const SORTS: [string, Sort, string][] = [
  ["ticker-asc", { key: "ticker", dir: "asc" }, "Kode A–Z"],
  ["ticker-desc", { key: "ticker", dir: "desc" }, "Kode Z–A"],
  ["upside-desc", { key: "upside", dir: "desc" }, "Potensi tertinggi"],
  ["upside-asc", { key: "upside", dir: "asc" }, "Potensi terendah"],
];
const sortId = (s: Sort) => `${s.key}-${s.dir}`;

function matches(item: ReportItem, filter: Filter, query: string) {
  if (filter === "published" && !item.published) return false;
  if (filter === "draft" && item.published) return false;
  const q = query.trim().toLowerCase();
  return !q || item.ticker.toLowerCase().includes(q) || item.name.toLowerCase().includes(q);
}

function compare(a: ReportItem, b: ReportItem, sort: Sort) {
  const sign = sort.dir === "asc" ? 1 : -1;
  if (sort.key === "upside") {
    // Reports without an upside (drafts) sink to the bottom either way.
    if (a.upside == null || b.upside == null) return a.upside == null ? (b.upside == null ? 0 : 1) : -1;
    return (a.upside - b.upside) * sign;
  }
  return a.ticker.localeCompare(b.ticker) * sign;
}

const MARK: Record<ReturnType<typeof ratingTone>, string> = {
  buy: "bg-ok-ink", hold: "bg-brand-ink", sell: "bg-err-ink", review: "bg-warn-rule",
};

/** Rating tallies and the latest report date, read like the deck's status rail. */
function Tally({ items }: { items: ReportItem[] }) {
  const order = ["Buy", "Hold", "Sell", "Review Required", "Draft"];
  const counts = items.reduce<Record<string, { n: number; tone: ReturnType<typeof ratingTone> }>>((acc, item) => {
    const label = ratingLabel(item);
    acc[label] = { n: (acc[label]?.n ?? 0) + 1, tone: ratingTone(item) };
    return acc;
  }, {});
  const rank = (label: string) => (order.includes(label) ? order.indexOf(label) : order.length);
  const labels = Object.keys(counts).sort((a, b) => rank(a) - rank(b));
  const latest = items.map((i) => i.date).filter(Boolean).sort().at(-1);
  return (
    <dl className="m-0 flex flex-wrap items-stretch gap-px overflow-clip rounded-md border border-rule bg-rule max-sm:w-full [&>div]:flex-auto">
      <div className="bg-surface px-3.5 py-2">
        <dt className="text-[12px] text-ink-soft">Laporan</dt>
        <dd className="m-0 font-mono text-[16px] font-semibold tabular-nums text-ink-strong">{items.length}</dd>
      </div>
      {labels.map((label) => (
        <div key={label} className="bg-surface px-3.5 py-2">
          <dt className="flex items-center gap-1.5 text-[12px] text-ink-soft">
            <span aria-hidden className={`size-1.5 rounded-[1.5px] ${MARK[counts[label].tone]}`} />{label}
          </dt>
          <dd className="m-0 font-mono text-[16px] font-semibold tabular-nums text-ink-strong">{counts[label].n}</dd>
        </div>
      ))}
      {latest && (
        <div className="bg-surface px-3.5 py-2">
          <dt className="text-[12px] text-ink-soft">Terbaru</dt>
          <dd className="m-0 font-mono text-[14px] leading-6 font-medium text-ink-strong"><time dateTime={latest}>{formatDay(latest)}</time></dd>
        </div>
      )}
    </dl>
  );
}

/** "/" focuses the search field, as in most registers. */
function useSlashFocus(ref: React.RefObject<HTMLInputElement | null>) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
      e.preventDefault();
      ref.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ref]);
}

function SkeletonRows() {
  return (
    <div aria-hidden className="divide-y divide-rule-soft">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-4 max-sm:px-4" style={{ opacity: 1 - i * 0.13 }}>
          <span className="h-[62px] w-11 flex-none animate-pulse rounded-[3px] bg-raised max-lg:hidden" />
          <span className="grid flex-none gap-1.5"><span className="h-3.5 w-12 animate-pulse rounded bg-raised" /><span className="h-3 w-14 animate-pulse rounded bg-raised" /></span>
          <span className="grid flex-1 gap-1.5"><span className="h-3.5 w-3/5 animate-pulse rounded bg-raised" /><span className="h-3 w-2/5 animate-pulse rounded bg-raised" /></span>
          <span className="h-6 w-16 flex-none animate-pulse rounded-[5px] bg-raised" />
        </div>
      ))}
    </div>
  );
}

export default function Gallery() {
  const { data: items, error, loading, reload } = useLoad(api.reports);
  const reduce = useReducedMotion();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>({ key: "ticker", dir: "asc" });
  const search = useRef<HTMLInputElement>(null);
  useSlashFocus(search);

  const all = useMemo(() => items ?? [], [items]);
  const published = all.filter((i) => i.published).length;
  const counts: Record<Filter, number> = { all: all.length, published, draft: all.length - published };
  const shown = useMemo(
    () => all.filter((i) => matches(i, filter, query)).sort((a, b) => compare(a, b, sort)),
    [all, filter, query, sort],
  );
  const scale = useMemo(() => Math.max(0, ...all.map((i) => Math.abs(i.upside ?? 0))), [all]);
  const reset = () => { setFilter("all"); setQuery(""); };

  return (
    <>
      <section aria-labelledby="gallery-title" className="border-b border-rule bg-surface">
        <div className="wrap flex flex-wrap items-end justify-between gap-x-10 gap-y-6 pt-10 pb-8 max-sm:pt-7 max-sm:pb-6">
          <div className="max-w-[64ch]">
            <h1 id="gallery-title" className="text-[clamp(28px,3.2vw,38px)] font-black tracking-[-.02em]">Company update</h1>
            <p className="mt-2.5 text-ink-soft">
              Tiap laporan memilih metode valuasi lewat Method Gates dan menahan rating bila bukti belum cukup. Putar ulang run-nya
              untuk melihat agent bekerja, atau buka jejak audit untuk menelusuri tiap angka.
            </p>
          </div>
          {all.length > 0 && <Tally items={all} />}
        </div>
      </section>

      <section aria-labelledby="register-title" className="pt-6 pb-[72px] max-sm:pt-4">
        <div className="wrap">
          <h2 id="register-title" className="sr-only">Daftar company update</h2>

          {error && (
            <Notice tone="error">
              <p><strong>Daftar company update belum bisa dimuat.</strong> Server API tidak menjawab ({error}). Pastikan server berjalan, lalu coba lagi.</p>
              <button type="button" onClick={reload} className="btn btn-sm btn-ghost mt-3">
                <RefreshCw aria-hidden className="size-3.5" strokeWidth={2.2} />Coba lagi
              </button>
            </Notice>
          )}

          {!loading && !error && !all.length && (
            <Notice>
              <p><strong className="text-ink">Belum ada company update.</strong> Jalankan{" "}
                <code className="rounded-[4px] border border-rule bg-raised px-1.5 py-0.5 text-[13px] text-ink">python -m app.batch BBCA JPFA --out out/reports --pdf</code>{" "}
                lalu muat ulang halaman ini.</p>
            </Notice>
          )}

          {(loading || all.length > 0) && (
            <div className="panel">
              <div className="flex flex-wrap items-center gap-3 border-b border-rule px-5 py-3 max-sm:px-4">
                <div role="group" aria-label="Saring status rilis" className="inline-flex rounded-md border border-rule bg-raised p-0.5">
                  {FILTERS.map(([value, label]) => {
                    const active = filter === value;
                    return (
                      <button key={value} type="button" aria-pressed={active} onClick={() => setFilter(value)} disabled={loading}
                        className={`relative h-8 cursor-pointer rounded-[5px] px-3 text-[13.5px] font-medium transition-colors disabled:cursor-progress ${
                          active ? "text-ink-strong" : "text-ink-soft hover:text-ink-strong"}`}>
                        {active && (
                          <motion.span layoutId="gallery-filter" aria-hidden
                            className="absolute inset-0 rounded-[5px] border border-rule-strong bg-surface"
                            transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 500, damping: 42 }} />
                        )}
                        <span className="relative">{label} <span className="data text-ink-soft">{counts[value]}</span></span>
                      </button>
                    );
                  })}
                </div>

                <label className="flex items-center gap-2 text-[13.5px] text-ink-soft lg:hidden">
                  Urutkan
                  <select value={sortId(sort)} onChange={(e) => setSort(SORTS.find(([id]) => id === e.target.value)![1])}
                    className="h-9 cursor-pointer rounded-md border border-rule bg-surface px-2 text-[13.5px] text-ink hover:border-rule-strong focus:border-brand-ink focus:outline-none">
                    {SORTS.map(([id, , label]) => <option key={id} value={id}>{label}</option>)}
                  </select>
                </label>

                <label className="relative ml-auto block w-full max-w-[340px] max-sm:order-first max-sm:max-w-none">
                  <span className="sr-only">Cari kode atau nama emiten</span>
                  <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-faint" strokeWidth={2.2} />
                  <input ref={search} type="search" value={query} placeholder="Cari kode atau nama emiten" disabled={loading}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Escape" && query) { e.preventDefault(); setQuery(""); } }}
                    className="h-9 w-full rounded-md border border-rule bg-surface pr-10 pl-9 text-[14px] text-ink transition-[border-color,box-shadow] duration-200 placeholder:text-ink-faint hover:border-rule-strong focus:border-brand-ink focus:shadow-[0_0_0_3px_var(--color-brand-100)] focus:outline-none disabled:cursor-progress [&::-webkit-search-cancel-button]:hidden" />
                  {query ? (
                    <button type="button" onClick={() => { setQuery(""); search.current?.focus(); }} aria-label="Hapus pencarian"
                      className="absolute top-1/2 right-1.5 grid size-7 -translate-y-1/2 cursor-pointer place-items-center rounded-[5px] text-ink-soft hover:bg-raised hover:text-ink-strong">
                      <X aria-hidden className="size-3.5" strokeWidth={2.4} />
                    </button>
                  ) : (
                    <kbd aria-hidden className="kbd pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 max-sm:hidden">/</kbd>
                  )}
                </label>
              </div>

              {loading ? (
                <>
                  <p role="status" className="sr-only">Memuat company update…</p>
                  <SkeletonRows />
                </>
              ) : shown.length ? (
                <ReportRegister items={shown} scale={scale} sort={sort} onSort={setSort} />
              ) : (
                <div className="px-5 py-12 text-center max-sm:px-4">
                  <p className="font-medium text-ink-strong">
                    Tidak ada company update yang cocok{query.trim() && <> dengan <span className="font-mono">“{query.trim()}”</span></>}
                    {filter !== "all" && <> di saringan {FILTERS.find(([v]) => v === filter)![1]}</>}.
                  </p>
                  <p className="mt-1 text-[14px] text-ink-soft">Coba kode emiten lain, atau tampilkan semua laporan.</p>
                  <button type="button" onClick={reset} className="btn btn-sm btn-ghost mt-4">Tampilkan semua laporan</button>
                </div>
              )}

              {!loading && (
                <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-rule px-5 py-3 max-sm:px-4">
                  <p aria-live="polite" className="text-[13px] text-ink-soft tabular-nums">Menampilkan {shown.length} dari {all.length} laporan</p>
                  <ChainLegend />
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
