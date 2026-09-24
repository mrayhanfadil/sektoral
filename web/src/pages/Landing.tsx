import { Link } from "react-router-dom";
import { api, reportFiles, type ReportItem } from "../lib/api";
import { rp } from "../lib/format";
import { featuredReport } from "../lib/labels";
import { ResearchFlow } from "../components/Brand";
import { RatingBadge, ReportGrid, Stats, TickerBadge, traceHref } from "../components/Reports";
import { useLoad } from "../components/State";

const MARK: Record<string, [string, string]> = {
  Terpilih: ["bg-brand text-white", "✓"],
  "Silang cek": ["bg-ok-bg text-ok-ink", "≈"],
  Dilewati: ["bg-canvas text-ink-soft", "↷"],
};

function HeroCard({ item }: { item?: ReportItem }) {
  if (!item) {
    return (
      <figure className="m-0">
        <div role="img" aria-label="Contoh tampilan hasil riset." className="overflow-hidden rounded-2xl border border-rule bg-white shadow-card">
          <div className="flex items-center justify-between gap-3 border-b border-rule-soft px-5 py-4">
            <div className="flex items-center gap-3">
              <TickerBadge ticker="BEI" />
              <div><strong className="block">Riset emiten</strong><span className="text-[13px] text-ink-soft">Company update</span></div>
            </div>
            <span className="pill pill-live">Contoh</span>
          </div>
          <ol className="m-0 list-none px-5 py-2">
            {[
              ["ok", "✓", "Rencana & hipotesis disusun", "Agen memilih tool: peer, kuartalan, arus asing, valuasi"],
              ["ok", "✓", "Metode valuasi dipilih gerbang framework", "Metode utama, fallback, lalu silang cek"],
              ["warn", "!", "Rating ditahan bila bukti kurang", "Alasannya tercatat di jejak audit"],
            ].map(([tone, mark, title, sub]) => (
              <li key={title} className="grid grid-cols-[28px_1fr] gap-3 border-b border-dashed border-rule-soft py-3 last:border-0">
                <span aria-hidden className={`grid size-6 place-items-center rounded-full text-[13px] font-black ${tone === "ok" ? "bg-ok-bg text-ok-ink" : "bg-warn-bg text-warn-ink"}`}>{mark}</span>
                <div><strong className="block text-[15px]">{title}</strong><span className="text-[13.5px] text-ink-soft">{sub}</span></div>
              </li>
            ))}
          </ol>
        </div>
        <figcaption className="mt-3 text-center text-[13px] text-ink-soft">Ilustrasi tampilan, bukan hasil riset aktual.</figcaption>
      </figure>
    );
  }
  const files = reportFiles(item.ticker);
  const trace = traceHref(item);
  return (
    <figure className="m-0">
      <div className="overflow-hidden rounded-2xl border border-rule bg-white shadow-card">
        <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-rule-soft px-5 py-4">
          <TickerBadge ticker={item.ticker} />
          <div>
            <strong className="block text-[15.5px] leading-tight">{item.name}</strong>
            <span className="block text-[12.5px] text-ink-soft">{item.profile} · {item.date}</span>
          </div>
          <RatingBadge item={item} />
        </div>
        <p className="px-5 pt-3.5 pb-1 text-[17px] leading-snug font-black">{item.headline}</p>
        <div className="mx-5 mt-2.5 mb-1"><Stats item={item} /></div>
        <ol aria-label={`Rantai metode valuasi ${item.ticker}`} className="m-0 mt-2 list-none px-5 pt-1.5 pb-2.5">
          {item.chain.slice(0, 5).map((step) => {
            const [cls, mark] = MARK[step.decision] ?? ["bg-canvas text-ink-soft", "·"];
            const value = step.value !== "-" && step.value !== "ditahan" ? step.value : "";
            return (
              <li key={step.step} className="grid grid-cols-[26px_1fr_auto] items-center gap-2.5 border-b border-dashed border-rule-soft py-2 text-sm last:border-0">
                <span aria-hidden className={`grid size-[22px] place-items-center rounded-full text-xs font-black ${cls}`}>{mark}</span>
                <span className={step.decision === "Dilewati" ? "text-ink-soft" : ""}>
                  {step.step}<span className="block text-xs text-ink-soft">{step.decision}</span>
                </span>
                <span className="text-[13.5px] font-bold tabular-nums">{value}</span>
              </li>
            );
          })}
        </ol>
        <div className="flex flex-wrap gap-2 border-t border-rule-soft bg-canvas px-5 py-3.5">
          <a className="btn btn-sm btn-primary" href={files.pdf}>Buka PDF</a>
          {trace.startsWith("/laporan")
            ? <Link className="btn btn-sm btn-ghost" to={trace}>Lihat jejak audit</Link>
            : <a className="btn btn-sm btn-ghost" href={trace}>Lihat jejak audit</a>}
        </div>
      </div>
      <figcaption className="mt-3 text-center text-[13px] text-ink-soft">
        Hasil riset nyata dari folder laporan, data per {item.date}.
      </figcaption>
    </figure>
  );
}

function Intro({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-11 max-w-[640px]">
      <h2 id={id} className="mb-3 text-[clamp(26px,3vw,36px)] font-black tracking-[-.02em]">{title}</h2>
      <p className="text-[17px] text-ink-soft">{children}</p>
    </div>
  );
}

function Section({ id, alt, labelledBy, children }: { id?: string; alt?: boolean; labelledBy: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={labelledBy}
      className={`scroll-mt-16 py-[88px] max-sm:py-[60px] ${alt ? "border-y border-rule-soft bg-canvas" : ""}`}>
      <div className="wrap">{children}</div>
    </section>
  );
}

const GATES = [
  ["Model bisnis", "Bank ke DDM/P/BV, tambang ke NAV, holding ke SOTP"],
  ["Kelayakan data", "Riwayat, laba usaha, leverage, ekuitas"],
  ["Kepemilikan", "Minoritas 15-40% wajib silang cek SOTP"],
  ["Siklus", "Komoditas atau aset yang baru ramp-up"],
  ["Tahap usaha", "Tumbuh, matang, atau turnaround"],
  ["Kewajaran hasil", "Potensi >100% atau <-50%: Review Required"],
];

const CHECKS = [
  ["Angka kuantitatif", "Pendapatan, margin, valuasi, rasio utang", "Cocok dengan sumber",
    "Setiap angka sama dengan baris dan kolom yang dibaca.", "Ditolak",
    "Angka yang tidak terverifikasi dibuang; bagian tersebut dinyatakan tanpa dukungan data."],
  ["Asumsi agen", "Skenario laba, risiko, katalis", "Tervalidasi", "Sumber, periode, dan besaran lolos pemeriksaan skema.",
    "Ditolak atau diperbaiki", "Asumsi tanpa sumber tidak masuk model; alasannya tercatat."],
  ["Metode valuasi", "Rantai dari gerbang framework", "Metode terpilih lolos", "Nilai, sensitivitas, dan silang cek ditampilkan.",
    "Semua metode gagal", "Tidak ada tebakan; tiap metode diberi alasan."],
  ["Rating & target harga", "Gerbang forecast dan valuasi", "Ditampilkan",
    "Hanya setelah metode yang dipilih lolos seluruh pemeriksaan.", "Ditahan",
    "Laporan terbit sebagai draf parsial dengan banner bukti belum lengkap dan alasan penahanan."],
];

const ICON: Record<string, React.ReactNode> = {
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  split: <><path d="M4 6h16M4 12h10M4 18h7" /><path d="m17 15 3 3-3 3" /></>,
  ban: <><circle cx="12" cy="12" r="9" /><path d="m5.6 5.6 12.8 12.8" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></>,
};

const LIMITS = [
  ["clock", "Data bertanggal, bukan siaran langsung",
    "Riset membaca data Sectors yang tersimpan beserta tanggalnya, tanpa panggilan data pasar langsung. Harga penutupan dan rilis resmi yang terbit sesudah tanggal laporan tidak dipakai."],
  ["split", "LLM untuk nalar, bukan data",
    "Model bahasa menyusun narasi dan asumsi bersumber. Angka finansial, rasio valuasi, dan tanggal laporan selalu diambil dari data terstruktur."],
  ["ban", "Tanpa broker dan transaksi",
    "Sectoral adalah alat riset. Tidak ada koneksi ke rekening efek, broker, atau jalur eksekusi pesanan dalam bentuk apa pun."],
  ["info", "Bukan rekomendasi investasi",
    "Keluaran riset menyajikan informasi dan analisis untuk mendukung kerja analis, bukan ajakan membeli efek atau nasihat keuangan berlisensi."],
];

export default function Landing() {
  const { data: items = [] } = useLoad(api.reports);
  const published = items.filter((i) => i.published);
  const featured = featuredReport(items);
  const th = "px-3.5 py-3 text-left text-[13px] font-bold text-ink-soft";

  return (
    <>
      <section aria-labelledby="hero-title" className="relative overflow-hidden border-b border-rule-soft bg-[radial-gradient(900px_420px_at_85%_-10%,var(--color-brand-50),transparent_70%)]">
        <div className="wrap relative grid items-center gap-14 pt-[72px] pb-20 lg:grid-cols-[1.1fr_.9fr] max-lg:gap-10 max-lg:pt-12 max-lg:pb-14">
          <div>
            <h1 id="hero-title" className="mb-5 max-w-[15ch] text-[clamp(34px,4.6vw,54px)] leading-[1.06] font-black tracking-[-.025em]">
              Company update dengan metode yang tepat, bukan DCF untuk semua.
            </h1>
            <p className="max-w-[54ch] text-lg text-ink-soft">
              Sectoral membaca data Sectors dan rilis resmi emiten, menyusun skenario laba dari berita bertanggal, lalu
              memilih metode valuasi lewat gerbang framework: DDM untuk bank, DCF FCFF untuk korporasi, SOTP untuk grup
              beragam lini, NAV cadangan untuk tambang. Rating hanya terbit bila setiap pemeriksaan lolos.
            </p>
            <div className="mt-[30px] flex flex-wrap gap-3 max-sm:[&>a]:flex-[1_1_100%]">
              <Link to="/research" className="btn btn-primary">Coba riset emiten</Link>
              <Link to="/laporan" className="btn btn-ghost">Lihat laporan</Link>
            </div>
            <ul aria-label="Ringkasan batasan" className="mt-7 flex list-none flex-wrap gap-x-5 gap-y-2 p-0 text-sm text-ink-soft">
              {["Enam gerbang metode", "Risiko utama bersumber", "Tanpa eksekusi transaksi"].map((fact) => (
                <li key={fact} className="flex items-center gap-2 before:size-1.5 before:rounded-full before:bg-teal before:content-['']">{fact}</li>
              ))}
            </ul>
          </div>
          <HeroCard item={featured} />
        </div>
      </section>

      <Section id="cara-kerja" labelledBy="cara-kerja-title">
        <Intro id="cara-kerja-title" title="Agen menalar, kode menghitung, gerbang memutuskan.">
          Model bahasa menyusun rencana, asumsi, dan narasi. Setiap angka dihitung dari data terstruktur, dan setiap
          keputusan terbit atau tahan diambil oleh pemeriksaan berbasis kode.
        </Intro>
        <ol className="m-0 grid list-none gap-5 p-0 md:grid-cols-3">
          {[
            ["Baca bukti bertanggal", "bg-brand",
              "Agen analis memilih data Sectors: peer, kinerja kuartalan, harga vs IHSG, arus asing, valuasi. Rilis resmi emiten dan harga penutupan IDX melengkapi, dan berita bertanggal dibaca utuh sebagai konteks."],
            ["Susun skenario laba", "bg-teal",
              "Agen asumsi memakai aktual 1H resmi untuk skenario semester kedua, tahun lanjutan, tesis, katalis, dan risiko utama. Setiap asumsi wajib mengutip sumber; yang tidak lolos validasi ditolak."],
            ["Pilih metode, lalu periksa", "bg-green",
              "Gerbang framework menentukan rantai metode sebelum nilai dihitung. Harness memeriksa sumber, periode, dan kewajaran hasil; bila ada yang gagal, rating ditahan dan alasannya dicatat."],
          ].map(([title, bar, body], i) => (
            <li key={title} className="relative rounded-xl border border-rule bg-white px-6 pt-[26px] pb-6">
              <span aria-hidden className={`absolute inset-x-6 top-0 h-[3px] rounded-b-[3px] ${bar}`} />
              <span className="mb-3.5 block text-[13px] font-black tracking-[.1em] text-brand">0{i + 1}</span>
              <h3 className="mb-2.5 text-[19px]">{title}</h3>
              <p className="text-[15px] text-ink-soft">{body}</p>
            </li>
          ))}
        </ol>
        <figure className="mt-7 rounded-xl border border-rule bg-white p-5">
          <ResearchFlow />
          <figcaption className="mt-2.5 text-center text-[13px] text-ink-soft">Alur riset dari bukti bertanggal hingga company update.</figcaption>
        </figure>
      </Section>

      <Section id="framework" alt labelledBy="framework-title">
        <Intro id="framework-title" title="Enam gerbang memilih metode sebelum angka dihitung.">
          DCF bukan jawaban untuk semua emiten. Gerbang membaca model bisnis, kualitas data, kepemilikan, siklus, dan
          tahap usaha, lalu mengurutkan metode utama, fallback, dan silang cek.
        </Intro>
        <ol className="m-0 grid list-none grid-cols-1 gap-2.5 p-0 sm:grid-cols-3 xl:grid-cols-6">
          {GATES.map(([title, body], i) => (
            <li key={title} className={`rounded-xl border bg-white px-3.5 py-4 ${i === 5 ? "border-warn-rule" : "border-rule"}`}>
              <b className={`block text-[13px] ${i === 5 ? "text-warn-ink" : "text-brand"}`}>Method Gate {i}</b>
              <strong className="mt-1.5 mb-1 block text-[15px]">{title}</strong>
              <span className="block text-[13px] leading-snug text-ink-soft">{body}</span>
            </li>
          ))}
        </ol>
        <div className="mt-7 grid items-start gap-6 lg:grid-cols-[1fr_1.1fr]">
          <div className="rounded-xl border border-rule bg-white p-[22px]">
            <h3 className="mb-3 text-lg">Rantai metode</h3>
            <ol className="m-0 pl-5 text-[15px] text-ink-soft [&>li]:my-1.5 [&_b]:text-ink">
              <li><b>Metode utama</b> dari gerbang, misalnya DCF atau DDM.</li>
              <li><b>Fallback</b> hanya bila metode sebelumnya tidak memadai, bukan karena hasilnya tidak disukai.</li>
              <li><b>Silang cek</b> wajib: PER peer, P/S, atau SOTP, dengan alasan tercatat.</li>
              <li><b>Rating ditahan</b> bila tidak ada metode yang lolos.</li>
            </ol>
          </div>
          {items.length > 0 && (
            <div role="region" aria-label="Metode terpilih per emiten" tabIndex={0} className="overflow-x-auto rounded-xl">
              <table className="w-full border-separate border-spacing-0 overflow-hidden rounded-xl border border-rule bg-white text-[14.5px]">
                <thead className="bg-canvas">
                  <tr><th scope="col" className={th}>Emiten</th><th scope="col" className={`${th} max-sm:hidden`}>Profil</th>
                    <th scope="col" className={th}>Metode terpilih</th><th scope="col" className={th}>Hasil</th></tr>
                </thead>
                <tbody className="[&_td]:border-t [&_td]:border-rule-soft [&_td]:px-3.5 [&_td]:py-3 [&_td]:align-middle">
                  {items.slice(0, 8).map((item) => (
                    <tr key={item.ticker}>
                      <td className="font-black whitespace-nowrap">{item.ticker}</td>
                      <td className="max-sm:hidden">{item.profile}</td>
                      <td>{item.published ? item.method : `Ditahan: ${item.held_reason}`}</td>
                      <td className="whitespace-nowrap">
                        <RatingBadge item={item} />
                        {item.published && <span className="mt-1 block font-bold tabular-nums">Rp{rp(item.tp)}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Section>

      {items.length > 0 && (
        <Section id="laporan" labelledBy="laporan-title">
          <Intro id="laporan-title"
            title={`${published.length} company update terbit, ${items.length - published.length} ditahan sebagai draft.`}>
            Setiap laporan mengikuti struktur company update: sampul, tesis, industri, kinerja, katalis dan risiko,
            valuasi dengan rantai metode, serta laporan keuangan dua tahun aktual dan tiga tahun forecast.
          </Intro>
          <ReportGrid items={items.slice(0, 6)} />
          <div className="mt-6 flex justify-end"><Link className="btn btn-ghost" to="/laporan">Semua laporan</Link></div>
        </Section>
      )}

      <Section id="sumber" alt labelledBy="sumber-title">
        <Intro id="sumber-title" title="Sectors di inti, setiap sumber lain diberi label.">
          Catatan sumber di bawah setiap exhibit menyebut dari mana angka itu berasal.
        </Intro>
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Inti", "Sectors", "Fundamental, peer, harga, kepemilikan, arus asing, dan data sub-sektor."],
            ["Rilis resmi", "Laporan emiten", "Laporan keuangan interim dan daftar pemegang saham dari IDX dan situs emiten."],
            ["Perdagangan", "IDX", "Harga penutupan harian dan IHSG 24 bulan untuk grafik dan band valuasi."],
            ["Konteks", "Berita bertanggal", "Artikel dibaca utuh; dampak ke laba hanya bila ada driver terukur."],
            ["Kurs", "USD/IDR", "Kurs penutupan harian untuk emiten yang melapor dalam dolar."],
          ].map(([kind, title, body], i) => (
            <div key={title} className={`rounded-xl border bg-white p-[18px] ${i === 0 ? "border-brand shadow-[inset_0_3px_0_var(--color-brand)]" : "border-rule"}`}>
              <b className={`block text-[13px] ${i === 0 ? "text-brand" : "text-ink-soft"}`}>{kind}</b>
              <strong className="my-1.5 block text-base">{title}</strong>
              <p className="text-[13.5px] text-ink-soft">{body}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section id="pemeriksaan" labelledBy="pemeriksaan-title">
        <Intro id="pemeriksaan-title" title="Apa yang terjadi saat bukti lengkap, dan saat tidak.">
          Validator berbasis kode memastikan tidak ada klaim yang lolos tanpa rujukan yang sahih.
        </Intro>
        <div role="region" aria-label="Perbandingan hasil pemeriksaan bukti" tabIndex={0} className="overflow-auto rounded-xl border border-rule bg-white">
          <table className="w-full min-w-[680px] border-collapse text-[15px] [&_td]:w-[37%] [&_td]:text-ink-soft">
            <thead className="bg-canvas text-left text-sm font-bold text-ink-soft [&_th]:px-5 [&_th]:py-3.5">
              <tr><th scope="col">Pemeriksaan</th>
                <th scope="col">Bukti lengkap <span className="pill pill-ok ml-1.5">Terbit</span></th>
                <th scope="col">Bukti kurang <span className="pill pill-warn ml-1.5">Draft</span></th></tr>
            </thead>
            <tbody className="[&_td]:border-t [&_td]:border-rule-soft [&_td]:px-5 [&_td]:py-[18px] [&_td]:align-top [&_th]:border-t [&_th]:border-rule-soft [&_th]:px-5 [&_th]:py-[18px] [&_th]:text-left [&_th]:align-top">
              {CHECKS.map(([title, sub, okTitle, ok, noTitle, no]) => (
                <tr key={title}>
                  <th scope="row" className="w-[26%] font-bold">{title}<small className="mt-0.5 block text-[13px] font-normal text-ink-soft">{sub}</small></th>
                  <td><strong className="mb-0.5 block text-ink">{okTitle}</strong>{ok}</td>
                  <td><strong className="mb-0.5 block text-ink">{noTitle}</strong>{no}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="batasan" alt labelledBy="batasan-title">
        <Intro id="batasan-title" title="Jelas tentang apa yang tidak kami lakukan.">
          Kepercayaan pada analisis lahir dari kejelasan batas sistem.
        </Intro>
        <div className="grid gap-5 md:grid-cols-2">
          {LIMITS.map(([icon, title, body]) => (
            <div key={title} className="grid grid-cols-[44px_1fr] gap-4 rounded-xl border border-rule bg-white p-6 max-sm:grid-cols-1">
              <span className="grid size-11 place-items-center rounded-[10px] bg-brand-50 text-brand">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="size-[22px]">{ICON[icon]}</svg>
              </span>
              <div><h3 className="mb-1.5 text-[17px]">{title}</h3><p className="text-[15px] text-ink-soft">{body}</p></div>
            </div>
          ))}
        </div>
      </Section>

      <section aria-labelledby="cta-title" className="py-[88px] max-sm:py-[60px]">
        <div className="wrap">
          <div className="relative flex flex-wrap items-center justify-between gap-6 overflow-hidden rounded-[20px] bg-brand p-12 text-white max-sm:px-6 max-sm:py-8">
            <div>
              <h2 id="cta-title" className="max-w-[22ch] text-[clamp(24px,3vw,32px)] font-black text-white">Mulai dari satu kode emiten.</h2>
              <p className="mt-2 max-w-[52ch] text-white/85">Jalankan agen riset, ikuti prosesnya, lalu buka company update beserta jejak auditnya.</p>
            </div>
            <Link to="/research" className="btn bg-white text-brand hover:bg-brand-50">Coba riset emiten</Link>
          </div>
        </div>
      </section>
    </>
  );
}
