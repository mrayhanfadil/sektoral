import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Play } from "lucide-react";
import { api } from "../lib/api";
import { derive } from "../lib/agents";
import { featuredReport } from "../lib/labels";
import { useLoad } from "../components/State";
import { Launcher } from "../components/landing/Launcher";
import { Reel, useStoredRun } from "../components/landing/Reel";
import { Pipeline } from "../components/landing/Pipeline";
import { GateInstruments, MethodChain } from "../components/landing/Framework";
import { EvidenceChecks, ReleaseStatuses, ReviewBand } from "../components/landing/Checks";
import { ReportShelf } from "../components/landing/ReportShelf";
import { LiveMark } from "../components/Mark";
import { useLang, type Bi } from "../lib/i18n";

const SOURCES: [kind: Bi, name: Bi, body: Bi][] = [
  [{ id: "Inti", en: "Core" }, { id: "Sectors", en: "Sectors" },
    { id: "Fundamental, peer, harga, kepemilikan, arus asing, dan data sub-sektor.", en: "Fundamentals, peers, prices, ownership, foreign flows, and sub-sector data." }],
  [{ id: "Rilis resmi", en: "Official filings" }, { id: "Laporan emiten", en: "Issuer filings" },
    { id: "Laporan keuangan interim dan daftar pemegang saham dari IDX dan situs emiten.", en: "Interim financial statements and shareholder registers from IDX and issuer websites." }],
  [{ id: "Perdagangan", en: "Trading" }, { id: "IDX", en: "IDX" },
    { id: "Harga penutupan harian dan IHSG 24 bulan untuk grafik dan band valuasi.", en: "Daily closing prices and 24 months of the JCI for charts and valuation bands." }],
  [{ id: "Konteks", en: "Context" }, { id: "Berita bertanggal", en: "Dated news" },
    { id: "Artikel dibaca utuh; dampak ke laba hanya bila ada driver terukur.", en: "Articles are read in full; an earnings impact only where there is a measurable driver." }],
  [{ id: "Kurs", en: "FX" }, { id: "USD/IDR", en: "USD/IDR" },
    { id: "Kurs penutupan harian untuk emiten yang melapor dalam dolar.", en: "Daily closing rate for issuers that report in dollars." }],
];

const LIMITS: [title: Bi, body: Bi][] = [
  [{ id: "Data bertanggal, bukan siaran langsung", en: "Dated data, not a live feed" },
    { id: "Riset membaca data Sectors yang tersimpan beserta tanggalnya, tanpa panggilan data pasar langsung. Harga penutupan dan rilis resmi yang terbit sesudah tanggal laporan tidak dipakai.",
      en: "Research reads stored Sectors data with its dates, with no live market-data calls. Closing prices and official filings published after the Report Date are not used." }],
  [{ id: "LLM untuk nalar, bukan data", en: "An LLM for reasoning, not for data" },
    { id: "Model bahasa menyusun rencana, asumsi, dan narasi bersumber. Angka finansial, rasio valuasi, dan tanggal laporan selalu diambil dari data terstruktur.",
      en: "The language model drafts the plan, assumptions, and sourced narrative. Financial figures, valuation ratios, and the Report Date always come from structured data." }],
  [{ id: "Tanpa broker dan transaksi", en: "No broker, no trades" },
    { id: "Sektoral adalah alat riset. Tidak ada koneksi ke rekening efek, broker, atau jalur eksekusi pesanan dalam bentuk apa pun.",
      en: "Sektoral is a research tool. There is no connection to securities accounts, brokers, or order execution of any kind." }],
  [{ id: "Bukan rekomendasi investasi", en: "Not investment advice" },
    { id: "Keluaran riset menyajikan informasi dan analisis untuk mendukung kerja analis, bukan ajakan membeli efek atau nasihat keuangan berlisensi.",
      en: "Research output provides information and analysis to support analysts' work; it is not a solicitation to buy securities or licensed financial advice." }],
];

function Section({ id, title, lede, children }: { id: string; title: ReactNode; lede: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-judul`} className="scroll-mt-14 border-t border-rule py-24 max-sm:py-16">
      <div className="wrap">
        <div className="mb-12 grid gap-x-12 gap-y-3 max-sm:mb-9 lg:grid-cols-12 lg:items-end">
          <h2 id={`${id}-judul`} className="text-[clamp(28px,2.6vw,36px)] leading-[1.15] tracking-[-.02em] lg:col-span-6">{title}</h2>
          <p className="m-0 max-w-[62ch] text-[16.5px] text-ink-soft lg:col-span-5 lg:col-start-8">{lede}</p>
        </div>
        {children}
      </div>
    </section>
  );
}

/**
 * The one section drawn in the Deck's console grammar: a ruled panel with a
 * region bar (mark, name, mono reading), because the Method Gates are the
 * part of the product a visitor meets again, live, in the Deck.
 */
function ConsoleSection({ id, title, lede, region, reading, children }:
  { id: string; title: ReactNode; lede: ReactNode; region: string; reading: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-judul`} className="scroll-mt-14 border-t border-rule bg-surface py-24 max-sm:py-16">
      <div className="wrap">
        <div className="panel overflow-hidden bg-canvas shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-rule bg-surface px-6 py-3 max-sm:px-4">
            <span className="flex items-center gap-2.5">
              <LiveMark status="ok" className="h-3 w-3.5" />
              <span className="text-[14px] font-bold text-ink-strong">{region}</span>
            </span>
            <span className="data text-ink-soft">{reading}</span>
          </div>
          <div className="px-6 pt-10 pb-12 max-sm:px-4 max-sm:pt-7 max-sm:pb-8">
            <div className="mb-10 grid gap-x-12 gap-y-3 lg:grid-cols-12 lg:items-end">
              <h2 id={`${id}-judul`} className="text-[clamp(28px,2.6vw,36px)] leading-[1.15] tracking-[-.02em] lg:col-span-6">{title}</h2>
              <p className="m-0 max-w-[62ch] text-[16.5px] text-ink-soft lg:col-span-5 lg:col-start-8">{lede}</p>
            </div>
            {children}
          </div>
        </div>
      </div>
    </section>
  );
}

/** A label column and a content column, the page's ledger rhythm. */
function Ledger({ title, body, children }: { title: string; body?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-x-12 gap-y-5 lg:grid-cols-12">
      <div className="lg:col-span-4">
        <h3 className="text-[20px] leading-snug">{title}</h3>
        {body && <p className="m-0 mt-2 max-w-[48ch] text-[15px] text-ink-soft">{body}</p>}
      </div>
      <div className="min-w-0 lg:col-span-8">{children}</div>
    </div>
  );
}

export default function Landing() {
  const { t } = useLang();
  const reports = useLoad(api.reports);
  const items = useMemo(() => reports.data ?? [], [reports.data]);
  const featured = featuredReport(items) ?? items.find((i) => i.published);
  const ticker = featured?.ticker;
  const run = useStoredRun(ticker, !reports.loading);
  // The featured run read to its end: its gate verdicts, method chain and release status.
  const final = useMemo(() => (run.status === "ready" ? derive(run.run.events, { finished: true }) : undefined), [run]);

  return (
    <>
      <section aria-labelledby="hero-judul">
        <div className="wrap grid items-center gap-x-12 gap-y-10 pt-14 pb-20 max-sm:pt-9 max-sm:pb-14 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <div className="max-w-[580px]">
            <h1 id="hero-judul" className="text-[clamp(31px,2.85vw,42px)] leading-[1.1] font-bold tracking-[-.025em]">
              {t({
                id: "Lihat agen meriset emiten BEI langkah demi langkah, lalu Method Gates memilih metode valuasinya.",
                en: "Watch an agent research an IDX issuer step by step, then the Method Gates choose its valuation method.",
              })}
            </h1>
            <p className="m-0 mt-5 max-w-[46ch] text-[17.5px] leading-relaxed text-ink-soft">
              {t({
                id: "Setiap panggilan tool tercatat bersama alasan dan hasilnya, dan rating di company update hanya terbit bila setiap pemeriksaan lolos.",
                en: "Every tool call is logged with its reason and result, and a company update carries a rating only when every check passes.",
              })}
            </p>
            <div className="mt-8">
              <Launcher id="riset-atas" />
            </div>
            {ticker && (
              <p className="m-0 mt-6 text-[14px] text-ink-soft">
                <Play aria-hidden className="mr-1.5 inline size-3.5 -translate-y-px text-brand-ink" strokeWidth={2.4} />
                <Link to={`/laporan/${ticker}/putar`} className="font-semibold">{t({ id: `Putar ulang run ${ticker}`, en: `Replay the ${ticker} run` })}</Link>{" "}
                {t({ id: "dari jejak auditnya, tanpa memanggil model lagi.", en: "from its audit trace, without calling the model again." })}
              </p>
            )}
          </div>
          <Reel load={run} ticker={ticker} item={featured} />
        </div>
      </section>

      <Section id="cara-kerja" title={t({ id: "Agen menalar, kode menghitung, gerbang memutuskan.", en: "The agent reasons, code computes, the gates decide." })}
        lede={t({
          id: "Model bahasa menyusun rencana, memilih panggilan tool, dan menulis asumsi bersumber. Kode host yang deterministik menjalankan tool, lalu menghitung sinyal, Method Gates, valuasi, dan harness rilis; model tidak dapat mengubahnya.",
          en: "The language model drafts the plan, chooses tool calls, and writes sourced assumptions. Deterministic host code runs the tools, then computes the signals, Method Gates, valuation, and release harness; the model cannot change them.",
        })}>
        <Pipeline />
        <div className="mt-16">
          <Ledger title={t({ id: "Sectors di inti, setiap sumber lain diberi label.", en: "Sectors at the core, every other source labelled." })}
            body={t({
              id: "Tool agent hanya membaca snapshot Sectors lokal, jadi tidak ada run yang memakai kredit API Sectors. Catatan sumber di bawah setiap exhibit menyebut asal angkanya.",
              en: "Agent tools read only the local Sectors Snapshot, so no run spends Sectors API credits. The source note under every exhibit names where its figures come from.",
            })}>
            <dl className="m-0 border-t border-rule">
              {SOURCES.map(([kind, name, body], i) => (
                <div key={name.id} className="grid gap-x-6 gap-y-0.5 border-b border-rule py-4 sm:grid-cols-[112px_160px_minmax(0,1fr)] sm:items-baseline">
                  <dt className={`text-[13px] font-bold ${i === 0 ? "text-brand-ink" : "text-ink-soft"}`}>{t(kind)}</dt>
                  <dd className="m-0 text-[16px] font-bold text-ink-strong">{t(name)}</dd>
                  <dd className="m-0 text-[14.5px] text-ink-soft">{t(body)}</dd>
                </div>
              ))}
            </dl>
          </Ledger>
        </div>
      </Section>

      <ConsoleSection id="framework" title={t({ id: "Enam Method Gates memilih metode sebelum angka dihitung.", en: "Six Method Gates choose the method before any number is computed." })}
        lede={t({
          id: "DCF bukan jawaban untuk semua emiten. Gerbang membaca model bisnis, kualitas data, kepemilikan, siklus, dan tahap usaha, lalu mengurutkan metode utama, fallback, dan silang cek.",
          en: "DCF is not the answer for every issuer. The gates read the business model, data quality, ownership, cycle, and business stage, then rank the primary method, fallbacks, and cross-checks.",
        })}
        region="Method Gates"
        reading={final?.gates.some((g) => g.status !== "idle")
          ? t({
            id: `${final.gates.filter((g) => g.status !== "idle").length}/${final.gates.length} dinilai, run ${ticker}`,
            en: `${final.gates.filter((g) => g.status !== "idle").length}/${final.gates.length} assessed, ${ticker} run`,
          })
          : t({ id: "6 gerbang, urut 0 sampai 5", en: "6 gates, in order 0 to 5" })}>
        <GateInstruments gates={final?.gates} ticker={ticker} />
        <div className="mt-12 border-t border-rule pt-10">
          <MethodChain item={featured} chain={final?.chain} />
        </div>
      </ConsoleSection>

      <Section id="pemeriksaan" title={t({ id: "Apa yang terjadi saat bukti lengkap, dan saat tidak.", en: "What happens when the evidence is complete, and when it isn't." })}
        lede={t({
          id: "Validator berbasis kode memastikan tidak ada klaim yang lolos tanpa rujukan yang sahih. Bila bukti kurang, rating ditahan dan alasannya dicatat.",
          en: "Code-based validators make sure no claim passes without a valid reference. When the evidence falls short, the rating is held and the reason is logged.",
        })}>
        <EvidenceChecks />
        <div className="mt-16 grid gap-16">
          <Ledger title={t({ id: "Status rilis", en: "Release status" })}
            body={t({
              id: "Harness rilis menentukan apakah company update boleh memuat rating dan target harga.",
              en: "The release harness decides whether a company update may carry a rating and target price.",
            })}>
            <ReleaseStatuses current={final?.release?.status} ticker={ticker} />
          </Ledger>
          {items.length > 0 && (
            <Ledger title="Review Required"
              body={t({
                id: "Potensi di atas +100% atau di bawah −50% tidak diberi Buy, Hold, atau Sell. Hasil seperti itu butuh tesis fundamental bersumber dan batasan model yang dinyatakan.",
                en: "Upside above +100% or below −50% gets no Buy, Hold, or Sell. A result like that needs a sourced fundamental thesis and stated model limits.",
              })}>
              <ReviewBand items={items} />
            </Ledger>
          )}
        </div>
      </Section>

      <Section id="laporan"
        title={items.length
          ? t({
            id: `${items.length} company update tersimpan, masing-masing bisa diputar ulang.`,
            en: `${items.length} stored company ${items.length === 1 ? "update" : "updates"}, each one replayable.`,
          })
          : t({ id: "Company update tersimpan.", en: "Stored company updates." })}
        lede={t({
          id: "Setiap laporan menyimpan jejak auditnya. Putar ulang run-nya di Deck untuk melihat langkah agen, atau buka company update-nya langsung.",
          en: "Every report keeps its audit trace. Replay its run in the Deck to see the agent's steps, or open the company update directly.",
        })}>
        {reports.loading ? (
          <div className="panel px-5 py-10 text-center text-[14.5px] text-ink-soft">{t({ id: "Memuat daftar laporan…", en: "Loading reports…" })}</div>
        ) : reports.error ? (
          <div role="alert" className="panel border-err-bg bg-err-bg px-5 py-6 text-[14.5px] text-err-ink">
            {t({ id: "Daftar laporan belum bisa dimuat.", en: "The report list could not be loaded." })} {reports.error}
          </div>
        ) : items.length === 0 ? (
          <div className="panel px-5 py-10 text-center text-[14.5px] text-ink-soft">
            {t({ id: "Belum ada company update tersimpan. Jalankan riset pertama dari kolom di atas.", en: "No company updates stored yet. Run the first research from the field above." })}
          </div>
        ) : (
          <>
            <ReportShelf items={items} />
            <div className="mt-5 flex justify-end">
              <Link to="/laporan" className="btn btn-ghost btn-sm">{t({ id: "Semua laporan", en: "All reports" })}</Link>
            </div>
          </>
        )}
      </Section>

      <Section id="batasan" title={t({ id: "Jelas tentang apa yang tidak kami lakukan.", en: "Clear about what we don't do." })}
        lede={t({ id: "Kepercayaan pada analisis lahir dari kejelasan batas sistem.", en: "Trust in the analysis comes from clear system limits." })}>
        <ul className="m-0 list-none border-t border-rule p-0">
          {LIMITS.map(([title, body]) => (
            <li key={title.id} className="grid gap-x-12 gap-y-2 border-b border-rule py-7 lg:grid-cols-12">
              <h3 className="text-[19px] leading-snug lg:col-span-4">{t(title)}</h3>
              <p className="m-0 max-w-[68ch] text-[16px] text-ink-soft lg:col-span-8">{t(body)}</p>
            </li>
          ))}
        </ul>
      </Section>

      <section aria-labelledby="mulai-judul" className="border-t border-rule">
        <div className="wrap grid items-end gap-x-12 gap-y-8 py-24 max-sm:py-16 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <h2 id="mulai-judul" className="text-[clamp(28px,2.6vw,36px)] leading-[1.15] tracking-[-.02em]">{t({ id: "Mulai dari satu kode emiten.", en: "Start from one ticker." })}</h2>
            <p className="m-0 mt-3 max-w-[48ch] text-[16.5px] text-ink-soft">
              {t({
                id: "Jalankan agen riset, ikuti setiap langkahnya di Deck, lalu buka company update beserta jejak auditnya.",
                en: "Run the research agent, follow each step in the Deck, then open the company update with its audit trace.",
              })}
            </p>
          </div>
          <div className="lg:col-span-6 lg:col-start-7">
            <Launcher id="riset-akhir" />
          </div>
        </div>
      </section>
    </>
  );
}
