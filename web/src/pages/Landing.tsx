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

const SOURCES = [
  ["Inti", "Sectors", "Fundamental, peer, harga, kepemilikan, arus asing, dan data sub-sektor."],
  ["Rilis resmi", "Laporan emiten", "Laporan keuangan interim dan daftar pemegang saham dari IDX dan situs emiten."],
  ["Perdagangan", "IDX", "Harga penutupan harian dan IHSG 24 bulan untuk grafik dan band valuasi."],
  ["Konteks", "Berita bertanggal", "Artikel dibaca utuh; dampak ke laba hanya bila ada driver terukur."],
  ["Kurs", "USD/IDR", "Kurs penutupan harian untuk emiten yang melapor dalam dolar."],
];

const LIMITS = [
  ["Data bertanggal, bukan siaran langsung",
    "Riset membaca data Sectors yang tersimpan beserta tanggalnya, tanpa panggilan data pasar langsung. Harga penutupan dan rilis resmi yang terbit sesudah tanggal laporan tidak dipakai."],
  ["LLM untuk nalar, bukan data",
    "Model bahasa menyusun rencana, asumsi, dan narasi bersumber. Angka finansial, rasio valuasi, dan tanggal laporan selalu diambil dari data terstruktur."],
  ["Tanpa broker dan transaksi",
    "Sectoral adalah alat riset. Tidak ada koneksi ke rekening efek, broker, atau jalur eksekusi pesanan dalam bentuk apa pun."],
  ["Bukan rekomendasi investasi",
    "Keluaran riset menyajikan informasi dan analisis untuk mendukung kerja analis, bukan ajakan membeli efek atau nasihat keuangan berlisensi."],
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
              Lihat agen meriset emiten BEI langkah demi langkah, lalu Method Gates memilih metode valuasinya.
            </h1>
            <p className="m-0 mt-5 max-w-[46ch] text-[17.5px] leading-relaxed text-ink-soft">
              Setiap panggilan tool tercatat bersama alasan dan hasilnya, dan rating di company update hanya terbit bila setiap pemeriksaan lolos.
            </p>
            <div className="mt-8">
              <Launcher id="riset-atas" />
            </div>
            {ticker && (
              <p className="m-0 mt-6 text-[14px] text-ink-soft">
                <Play aria-hidden className="mr-1.5 inline size-3.5 -translate-y-px text-brand-ink" strokeWidth={2.4} />
                <Link to={`/laporan/${ticker}/putar`} className="font-semibold">Putar ulang run {ticker}</Link>{" "}
                dari jejak auditnya, tanpa memanggil model lagi.
              </p>
            )}
          </div>
          <Reel load={run} ticker={ticker} item={featured} />
        </div>
      </section>

      <Section id="cara-kerja" title="Agen menalar, kode menghitung, gerbang memutuskan."
        lede="Model bahasa menyusun rencana, memilih panggilan tool, dan menulis asumsi bersumber. Kode host yang deterministik menjalankan tool, lalu menghitung sinyal, Method Gates, valuasi, dan harness rilis; model tidak dapat mengubahnya.">
        <Pipeline />
        <div className="mt-16">
          <Ledger title="Sectors di inti, setiap sumber lain diberi label."
            body="Tool agent hanya membaca snapshot Sectors lokal, jadi tidak ada run yang memakai kredit API Sectors. Catatan sumber di bawah setiap exhibit menyebut asal angkanya.">
            <dl className="m-0 border-t border-rule">
              {SOURCES.map(([kind, name, body], i) => (
                <div key={name} className="grid gap-x-6 gap-y-0.5 border-b border-rule py-4 sm:grid-cols-[112px_160px_minmax(0,1fr)] sm:items-baseline">
                  <dt className={`text-[13px] font-bold ${i === 0 ? "text-brand-ink" : "text-ink-soft"}`}>{kind}</dt>
                  <dd className="m-0 text-[16px] font-bold text-ink-strong">{name}</dd>
                  <dd className="m-0 text-[14.5px] text-ink-soft">{body}</dd>
                </div>
              ))}
            </dl>
          </Ledger>
        </div>
      </Section>

      <ConsoleSection id="framework" title="Enam Method Gates memilih metode sebelum angka dihitung."
        lede="DCF bukan jawaban untuk semua emiten. Gerbang membaca model bisnis, kualitas data, kepemilikan, siklus, dan tahap usaha, lalu mengurutkan metode utama, fallback, dan silang cek."
        region="Method Gates"
        reading={final?.gates.some((g) => g.status !== "idle")
          ? `${final.gates.filter((g) => g.status !== "idle").length}/${final.gates.length} dinilai, run ${ticker}`
          : "6 gerbang, urut 0 sampai 5"}>
        <GateInstruments gates={final?.gates} ticker={ticker} />
        <div className="mt-12 border-t border-rule pt-10">
          <MethodChain item={featured} chain={final?.chain} />
        </div>
      </ConsoleSection>

      <Section id="pemeriksaan" title="Apa yang terjadi saat bukti lengkap, dan saat tidak."
        lede="Validator berbasis kode memastikan tidak ada klaim yang lolos tanpa rujukan yang sahih. Bila bukti kurang, rating ditahan dan alasannya dicatat.">
        <EvidenceChecks />
        <div className="mt-16 grid gap-16">
          <Ledger title="Status rilis"
            body="Harness rilis menentukan apakah company update boleh memuat rating dan target harga.">
            <ReleaseStatuses current={final?.release?.status} ticker={ticker} />
          </Ledger>
          {items.length > 0 && (
            <Ledger title="Review Required"
              body="Potensi di atas +100% atau di bawah −50% tidak diberi Buy, Hold, atau Sell. Hasil seperti itu butuh tesis fundamental bersumber dan batasan model yang dinyatakan.">
              <ReviewBand items={items} />
            </Ledger>
          )}
        </div>
      </Section>

      <Section id="laporan"
        title={items.length ? `${items.length} company update tersimpan, masing-masing bisa diputar ulang.` : "Company update tersimpan."}
        lede="Setiap laporan menyimpan jejak auditnya. Putar ulang run-nya di Deck untuk melihat langkah agen, atau buka company update-nya langsung.">
        {reports.loading ? (
          <div className="panel px-5 py-10 text-center text-[14.5px] text-ink-soft">Memuat daftar laporan…</div>
        ) : reports.error ? (
          <div role="alert" className="panel border-err-bg bg-err-bg px-5 py-6 text-[14.5px] text-err-ink">
            Daftar laporan belum bisa dimuat. {reports.error}
          </div>
        ) : items.length === 0 ? (
          <div className="panel px-5 py-10 text-center text-[14.5px] text-ink-soft">Belum ada company update tersimpan. Jalankan riset pertama dari kolom di atas.</div>
        ) : (
          <>
            <ReportShelf items={items} />
            <div className="mt-5 flex justify-end">
              <Link to="/laporan" className="btn btn-ghost btn-sm">Semua laporan</Link>
            </div>
          </>
        )}
      </Section>

      <Section id="batasan" title="Jelas tentang apa yang tidak kami lakukan."
        lede="Kepercayaan pada analisis lahir dari kejelasan batas sistem.">
        <ul className="m-0 list-none border-t border-rule p-0">
          {LIMITS.map(([title, body]) => (
            <li key={title} className="grid gap-x-12 gap-y-2 border-b border-rule py-7 lg:grid-cols-12">
              <h3 className="text-[19px] leading-snug lg:col-span-4">{title}</h3>
              <p className="m-0 max-w-[68ch] text-[16px] text-ink-soft lg:col-span-8">{body}</p>
            </li>
          ))}
        </ul>
      </Section>

      <section aria-labelledby="mulai-judul" className="border-t border-rule">
        <div className="wrap grid items-end gap-x-12 gap-y-8 py-24 max-sm:py-16 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <h2 id="mulai-judul" className="text-[clamp(28px,2.6vw,36px)] leading-[1.15] tracking-[-.02em]">Mulai dari satu kode emiten.</h2>
            <p className="m-0 mt-3 max-w-[48ch] text-[16.5px] text-ink-soft">
              Jalankan agen riset, ikuti setiap langkahnya di Deck, lalu buka company update beserta jejak auditnya.
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
