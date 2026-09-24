"""Landing page module for Sektoral.

Renders the Indonesian standalone HTML landing page for the Sectoral local
equity research product.
"""
from __future__ import annotations

from . import ui

_CSS = """
/* hero */
.hero{position:relative;overflow:hidden;border-bottom:1px solid var(--rule-soft);
  background:
    radial-gradient(900px 420px at 85% -10%,var(--blue-50),transparent 70%),
    linear-gradient(var(--surface),var(--surface))}
.hero::before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;
  background-image:linear-gradient(var(--rule-soft) 1px,transparent 1px),
    linear-gradient(90deg,var(--rule-soft) 1px,transparent 1px);
  background-size:48px 48px;
  -webkit-mask-image:linear-gradient(180deg,#000 0%,transparent 75%);
  mask-image:linear-gradient(180deg,#000 0%,transparent 75%)}
.hero .wrap{position:relative;display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);
  gap:56px;align-items:center;padding-top:72px;padding-bottom:80px}
.hero h1{font-size:clamp(34px,4.6vw,54px);font-weight:900;letter-spacing:-.025em;line-height:1.06;
  margin:18px 0 20px;max-width:15ch}
.hero h1 em{font-style:normal;color:var(--blue)}
.lead{font-size:18px;color:var(--ink-soft);max-width:54ch}
.cta-row{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}
.facts{display:flex;flex-wrap:wrap;gap:8px 20px;margin:28px 0 0;padding:0;list-style:none;
  font-size:14px;color:var(--ink-soft)}
.facts li{display:flex;align-items:center;gap:8px}
.facts li::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--teal)}

/* product preview */
.preview{background:var(--surface);border:1px solid var(--rule);border-radius:16px;
  box-shadow:var(--shadow);overflow:hidden}
.preview-top{display:flex;justify-content:space-between;align-items:center;gap:12px;
  padding:16px 20px;border-bottom:1px solid var(--rule-soft)}
.preview-ticker{display:flex;align-items:center;gap:12px}
.ticker-badge{display:grid;place-items:center;height:42px;padding:0 10px;border-radius:10px;
  background:var(--blue);color:#fff;font-weight:900;font-size:14px;letter-spacing:.06em}
.preview-ticker strong{display:block;font-size:16px}
.preview-ticker span{font-size:13px;color:var(--ink-soft)}
.steps{list-style:none;margin:0;padding:8px 20px}
.steps li{display:grid;grid-template-columns:28px 1fr;gap:12px;padding:12px 0;
  border-bottom:1px dashed var(--rule-soft)}
.steps li:last-child{border-bottom:0}
.dot{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;
  font-size:13px;font-weight:900;margin-top:1px}
.dot.ok{background:var(--ok-bg);color:var(--ok-ink)}
.dot.warn{background:var(--warn-bg);color:var(--warn-ink)}
.steps strong{display:block;font-size:15px}
.steps span{font-size:13.5px;color:var(--ink-soft)}
.preview-foot{display:flex;gap:8px;flex-wrap:wrap;padding:14px 20px;background:var(--canvas);
  border-top:1px solid var(--rule-soft)}
.fake-btn{font-size:13px;font-weight:700;padding:7px 12px;border-radius:8px;
  border:1px solid var(--rule);background:var(--surface);color:var(--blue)}
.fake-btn.primary{background:var(--blue);border-color:var(--blue);color:#fff}
.preview-caption{margin-top:12px;font-size:13px;color:var(--ink-soft);text-align:center}

/* sections */
section.block{padding:88px 0;scroll-margin-top:64px}
section.block.alt{background:var(--canvas);border-top:1px solid var(--rule-soft);
  border-bottom:1px solid var(--rule-soft)}
.intro{max-width:640px;margin-bottom:44px}
.intro h2{font-size:clamp(26px,3vw,36px);font-weight:900;letter-spacing:-.02em;margin:10px 0 12px}
.intro p{color:var(--ink-soft);font-size:17px}

.how{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;counter-reset:how;
  margin:0;padding:0;list-style:none}
.how li{position:relative;background:var(--surface);border:1px solid var(--rule);
  border-radius:var(--radius);padding:26px 24px 24px}
.how li::before{counter-increment:how;content:"0" counter(how);display:block;font-size:13px;
  font-weight:900;letter-spacing:.1em;color:var(--blue);margin-bottom:14px}
.how li::after{content:"";position:absolute;left:24px;right:24px;top:0;height:3px;
  border-radius:0 0 3px 3px;background:var(--blue)}
.how li:nth-child(2)::after{background:var(--teal)}
.how li:nth-child(3)::after{background:var(--green)}
.how h3{font-size:19px;margin-bottom:10px}
.how p{color:var(--ink-soft);font-size:15px}
.flow{margin:28px 0 0;background:var(--surface);border:1px solid var(--rule);
  border-radius:var(--radius);padding:20px}
.flow img{display:block;width:100%;max-width:760px;margin:0 auto}
.flow figcaption{text-align:center;font-size:13px;color:var(--ink-soft);margin-top:10px}

.compare-wrap{border:1px solid var(--rule);border-radius:var(--radius);overflow:auto;
  background:var(--surface)}
.compare{width:100%;border-collapse:collapse;min-width:680px;font-size:15px}
.compare th,.compare td{text-align:left;vertical-align:top;padding:18px 20px;
  border-bottom:1px solid var(--rule-soft)}
.compare tr:last-child th,.compare tr:last-child td{border-bottom:0}
.compare thead th{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-soft);
  background:var(--canvas);padding-top:14px;padding-bottom:14px}
.compare thead th .pill{margin-left:6px;text-transform:none;letter-spacing:0}
.compare tbody th{width:26%;font-weight:700}
.compare tbody th small{display:block;font-weight:400;color:var(--ink-soft);font-size:13px;margin-top:2px}
.compare td{color:var(--ink-soft);width:37%}
.compare td strong{display:block;color:var(--ink);margin-bottom:2px}

.limits{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.limit{display:grid;grid-template-columns:44px 1fr;gap:16px;padding:24px;border:1px solid var(--rule);
  border-radius:var(--radius);background:var(--surface)}
.limit-icon{display:grid;place-items:center;width:44px;height:44px;border-radius:10px;
  background:var(--blue-50);color:var(--blue)}
.limit-icon svg{width:22px;height:22px}
.limit h3{font-size:17px;margin-bottom:6px}
.limit p{color:var(--ink-soft);font-size:15px}

.cta-band{background:var(--blue);color:#fff;border-radius:20px;padding:48px;display:flex;
  flex-wrap:wrap;align-items:center;justify-content:space-between;gap:24px;position:relative;overflow:hidden}
.cta-band::after{content:"";position:absolute;right:-60px;top:-60px;width:260px;height:260px;
  border-radius:50%;border:40px solid rgba(255,255,255,.06)}
.cta-band h2{color:#fff;font-size:clamp(24px,3vw,32px);font-weight:900;max-width:22ch}
.cta-band p{color:rgba(255,255,255,.85);margin-top:8px;max-width:52ch}
.cta-band .btn{background:#fff;color:var(--blue);position:relative;z-index:1}
.cta-band .btn:hover{background:var(--blue-50)}

@media (max-width:960px){
  .hero .wrap{grid-template-columns:1fr;gap:40px;padding-top:48px;padding-bottom:56px}
  .how{grid-template-columns:1fr}
  .limits{grid-template-columns:1fr}
}
@media (max-width:560px){
  section.block{padding:60px 0}
  .cta-band{padding:32px 24px}
  .cta-row .btn{flex:1 1 100%}
  .limit{grid-template-columns:1fr}
}
"""

_ICON = {
    "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    "split": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h7"/><path d="m17 15 3 3-3 3"/></svg>',
    "ban": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/></svg>',
    "info": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/></svg>',
}


def render_landing() -> str:
    """Render the standalone Indonesian HTML landing page for Sektoral."""
    body = f"""<body>
<!--
THESIS: Evidence-backed company research, not a generic AI finance landing page; refuse claims of live data or trading.
OWN-WORLD: Sectoral blue/white/charcoal/Roboto; thin rules, precise report-like diagrams, restrained teal and green accents.
STORY: Show how dated Sectors source rows become an evidence-checked company update, and what happens when evidence is incomplete.
FIRST VIEWPORT: Brand/navigation; headline and CTA left; labeled product preview right; source and no-advice facts beneath the CTA.
FORM: Evidence instrument, assigned structure, seed ae210778.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
-->
{ui.site_header("home")}
<main id="konten">
  <section class="hero" aria-labelledby="hero-title">
    <div class="wrap">
      <div>
        <span class="pill live">Riset emiten BEI · sitasi terverifikasi</span>
        <h1 id="hero-title">Company update yang <em>setiap angkanya</em> bisa ditelusuri.</h1>
        <p class="lead">Agen AI Sectoral menyusun rencana riset dan hipotesis, memilih data Sectors yang perlu dibaca,
        memeringkat emiten terhadap peer-nya, lalu menguji setiap hipotesis dengan sinyal yang bisa dicek.
        Jika bukti belum cukup, hasilnya ditandai parsial, bukan ditebak.</p>
        <div class="cta-row">
          <a href="/research" class="btn btn-primary">Coba riset emiten <span class="arrow" aria-hidden="true">→</span></a>
          <a href="#cara-kerja" class="btn btn-ghost">Lihat cara kerja</a>
        </div>
        <ul class="facts" aria-label="Ringkasan batasan">
          <li>Peringkat terhadap peer</li>
          <li>Validator sitasi non-LLM</li>
          <li>Tanpa eksekusi transaksi</li>
        </ul>
      </div>

      <figure style="margin:0">
        <div class="preview" role="img" aria-label="Contoh tampilan hasil riset: data dibaca, brief disusun, sitasi divalidasi, rating ditahan karena forecast belum lolos pemeriksaan.">
          <div class="preview-top">
            <div class="preview-ticker">
              <span class="ticker-badge" aria-hidden="true">AMMN</span>
              <div><strong>Riset AMMN</strong><span>Company update · draf</span></div>
            </div>
            <span class="pill warn">Parsial</span>
          </div>
          <ol class="steps">
            <li><span class="dot ok" aria-hidden="true">✓</span><div><strong>Rencana &amp; hipotesis disusun</strong>
              <span>Agen memilih tool: peer, kuartalan, arus asing, valuasi</span></div></li>
            <li><span class="dot ok" aria-hidden="true">✓</span><div><strong>Peer diperingkat, hipotesis diuji</strong>
              <span>Satu hipotesis didukung, satu tidak didukung data</span></div></li>
            <li><span class="dot ok" aria-hidden="true">✓</span><div><strong>Sitasi divalidasi</strong>
              <span>Setiap angka dicocokkan ke baris sumber yang dibaca</span></div></li>
            <li><span class="dot warn" aria-hidden="true">!</span><div><strong>Rating &amp; target harga ditahan</strong>
              <span>Gate forecast belum lolos; alasannya tercatat di jejak audit</span></div></li>
          </ol>
          <div class="preview-foot" aria-hidden="true">
            <span class="fake-btn primary">Buka company update</span><span class="fake-btn">Lihat jejak agent</span>
          </div>
        </div>
        <figcaption class="preview-caption">Ilustrasi tampilan, bukan hasil riset aktual.</figcaption>
      </figure>
    </div>
  </section>

  <section id="cara-kerja" class="block" aria-labelledby="cara-kerja-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Cara kerja</span>
        <h2 id="cara-kerja-title">Agen yang merencanakan, bukan sekadar merangkum.</h2>
        <p>Tidak ada kesimpulan tanpa dasar. Setiap fakta dalam company update dapat ditelusuri kembali ke baris data asalnya.</p>
      </div>
      <ol class="how">
        <li>
          <h3>Rencanakan, lalu pilih data</h3>
          <p>Agen menulis pertanyaan riset dan hipotesis sesuai jenis usaha emiten, lalu memilih tool satu per satu:
          peer, kinerja kuartalan, harga vs IHSG, arus asing, valuasi, berita. Setiap hasil boleh mengubah langkah berikutnya.
          Semua tool membaca data Sectors; agen tidak menjelajah web.</p>
        </li>
        <li>
          <h3>Hitung sinyal, uji hipotesis</h3>
          <p>Peringkat terhadap peer dan anomali (lonjakan laba, divergensi asing vs harga, valuasi vs historis) dihitung
          deterministik. Agen menilai tiap hipotesis didukung atau tidak, dengan mengutip sinyal. Model menalar, bukan menjadi sumber angka.</p>
        </li>
        <li>
          <h3>Validasi, lalu terbitkan</h3>
          <p>Validator Python mencocokkan setiap sitasi dengan data yang benar-benar dibaca. Sitasi gagal atau bukti yang
          kurang otomatis mengubah status laporan menjadi parsial, lengkap dengan banner pengungkapan.</p>
        </li>
      </ol>
      <figure class="flow">
        <img src="{ui.FLOW_URL}" alt="Diagram alur: data Sectors dibaca agen, brief disusun, sitasi divalidasi, lalu company update terbit atau ditandai parsial." width="620" height="420" loading="lazy">
        <figcaption>Alur riset dari pembacaan data hingga validasi sitasi.</figcaption>
      </figure>
    </div>
  </section>

  <section id="pemeriksaan" class="block alt" aria-labelledby="pemeriksaan-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Pemeriksaan bukti</span>
        <h2 id="pemeriksaan-title">Apa yang terjadi saat bukti lengkap, dan saat tidak.</h2>
        <p>Validator berbasis kode memastikan tidak ada klaim yang lolos tanpa rujukan yang sahih.</p>
      </div>
      <div class="compare-wrap" role="region" aria-label="Perbandingan hasil pemeriksaan bukti" tabindex="0">
        <table class="compare">
          <thead><tr>
            <th scope="col">Pemeriksaan</th>
            <th scope="col">Bukti lengkap <span class="pill ok">Lengkap</span></th>
            <th scope="col">Bukti kurang <span class="pill warn">Parsial</span></th>
          </tr></thead>
          <tbody>
            <tr>
              <th scope="row">Angka kuantitatif<small>Pendapatan, margin, valuasi, rasio utang</small></th>
              <td><strong>Cocok dengan sumber</strong>Setiap angka sama dengan baris dan kolom yang dibaca.</td>
              <td><strong>Ditolak</strong>Angka yang tidak terverifikasi dibuang; bagian tersebut dinyatakan tanpa dukungan data.</td>
            </tr>
            <tr>
              <th scope="row">Jejak pembacaan<small>Endpoint yang diakses agen</small></th>
              <td><strong>Tercatat di jejak agent</strong>Seluruh endpoint yang disitasi muncul di log pembacaan host.</td>
              <td><strong>Tidak boleh disimpulkan</strong>Endpoint yang tidak dibaca atau kosong tidak boleh menjadi dasar narasi.</td>
            </tr>
            <tr>
              <th scope="row">Status laporan<small>Label di atas dokumen</small></th>
              <td><strong>Siap ditinjau</strong>Company update terbit tanpa banner peringatan.</td>
              <td><strong>Banner parsial</strong>Dokumen diberi label <em>Analisis parsial: bukti belum lengkap</em>.</td>
            </tr>
            <tr>
              <th scope="row">Rating &amp; target harga<small>Gate forecast dan valuasi</small></th>
              <td><strong>Ditampilkan</strong>Hanya setelah metode valuasi yang dipilih lolos seluruh pemeriksaan.</td>
              <td><strong>Ditahan</strong>Tidak ada tebakan; alasan penahanan tercatat di jejak audit.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="batasan" class="block" aria-labelledby="batasan-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Batasan</span>
        <h2 id="batasan-title">Jelas tentang apa yang tidak kami lakukan.</h2>
        <p>Kepercayaan pada analisis lahir dari kejelasan batas sistem.</p>
      </div>
      <div class="limits">
        <div class="limit"><span class="limit-icon">{_ICON["clock"]}</span><div>
          <h3>Data bertanggal, bukan siaran langsung</h3>
          <p>Riset membaca snapshot data Sectors yang tersimpan beserta tanggalnya, tanpa panggilan data pasar langsung.
          Laporan PDF dapat menambahkan angka dari rilis resmi emiten yang disimpan dengan tanggal dan halaman sumber.</p>
        </div></div>
        <div class="limit"><span class="limit-icon">{_ICON["split"]}</span><div>
          <h3>LLM untuk nalar, bukan data</h3>
          <p>Model bahasa menyusun narasi dan penalaran. Angka finansial, rasio valuasi, dan tanggal laporan selalu diambil
          dari data terstruktur, sehingga tidak ada angka yang dikarang.</p>
        </div></div>
        <div class="limit"><span class="limit-icon">{_ICON["ban"]}</span><div>
          <h3>Tanpa broker dan transaksi</h3>
          <p>Sektoral adalah alat riset. Tidak ada koneksi ke rekening efek, broker, atau jalur eksekusi pesanan dalam bentuk apa pun.</p>
        </div></div>
        <div class="limit"><span class="limit-icon">{_ICON["info"]}</span><div>
          <h3>Bukan rekomendasi investasi</h3>
          <p>Keluaran riset menyajikan informasi dan analisis untuk mendukung kerja analis, bukan ajakan membeli efek
          atau nasihat keuangan berlisensi.</p>
        </div></div>
      </div>
    </div>
  </section>

  <section class="block" style="padding-top:0" aria-labelledby="cta-title">
    <div class="wrap">
      <div class="cta-band">
        <div>
          <h2 id="cta-title">Mulai dari satu kode emiten.</h2>
          <p>Jalankan agen riset, ikuti prosesnya, lalu periksa company update beserta jejak sitasinya.</p>
        </div>
        <a href="/research" class="btn">Coba riset emiten <span class="arrow" aria-hidden="true">→</span></a>
      </div>
    </div>
  </section>
</main>
{ui.site_footer()}
</body>"""
    return ui.document(
        "Sectoral — Company update emiten BEI dengan sitasi terverifikasi",
        "Sectoral mengubah data fundamental Sectors menjadi company update emiten BEI dengan sitasi "
        "yang diperiksa secara deterministik dan batas bukti yang transparan.",
        _CSS,
        body,
    )
