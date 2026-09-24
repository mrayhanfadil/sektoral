"""Landing page module for Sektoral.

Renders the Indonesian standalone HTML landing page for the Sectoral local
equity research product.
"""
from __future__ import annotations

import html

from . import fmt, gallery_page, ui

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

/* hero result card (real report) */
.hero-card{background:var(--surface);border:1px solid var(--rule);border-radius:16px;
  box-shadow:var(--shadow);overflow:hidden}
.hc-top{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;
  padding:16px 20px;border-bottom:1px solid var(--rule-soft)}
.hc-top strong{display:block;font-size:15.5px;line-height:1.3}
.hc-top span.sub{display:block;font-size:12.5px;color:var(--ink-soft)}
.hc-head{padding:14px 20px 4px;font-weight:900;font-size:17px;line-height:1.3}
.hc-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:10px 20px 4px}
.hc-stats div{background:var(--canvas);border-radius:8px;padding:8px 10px}
.hc-stats dt{font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.06em}
.hc-stats dd{margin:0;font-weight:900;font-size:16px;font-variant-numeric:tabular-nums}
.hc-stats dd.neg{color:var(--err-ink)}.hc-stats dd.pos{color:var(--ok-ink)}
.chain{list-style:none;margin:8px 0 0;padding:6px 20px 10px}
.chain li{display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:center;
  padding:8px 0;border-bottom:1px dashed var(--rule-soft);font-size:14px}
.chain li:last-child{border-bottom:0}
.chain .mark{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;
  font-size:12px;font-weight:900}
.chain .sel .mark{background:var(--blue);color:#fff}
.chain .skip .mark{background:var(--canvas);color:var(--ink-soft)}
.chain .skip span.step{color:var(--ink-soft)}
.chain .xchk .mark{background:var(--ok-bg);color:var(--ok-ink)}
.chain .val{font-weight:700;font-variant-numeric:tabular-nums;font-size:13.5px}
.chain .dec{display:block;font-size:12px;color:var(--ink-soft)}
.hc-foot{display:flex;gap:8px;flex-wrap:wrap;padding:14px 20px;background:var(--canvas);
  border-top:1px solid var(--rule-soft)}

/* framework */
.gates{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:0;padding:0;list-style:none}
.gates li{background:var(--surface);border:1px solid var(--rule);border-radius:var(--radius);
  padding:16px 14px;position:relative}
.gates li b{display:block;font-size:12px;letter-spacing:.1em;color:var(--blue);text-transform:uppercase}
.gates li strong{display:block;font-size:15px;margin:6px 0 4px}
.gates li span{display:block;font-size:13px;color:var(--ink-soft);line-height:1.45}
.gates li:last-child{border-color:var(--warn-rule)}
.gates li:last-child b{color:var(--warn-ink)}
.chain-demo{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:24px;margin-top:28px;
  align-items:start}
.chain-steps{background:var(--surface);border:1px solid var(--rule);border-radius:var(--radius);padding:22px}
.chain-steps h3{font-size:18px;margin-bottom:12px}
.chain-steps ol{margin:0;padding-left:20px;color:var(--ink-soft);font-size:15px}
.chain-steps li{margin:6px 0}
.chain-steps li b{color:var(--ink)}
.method-table{width:100%;border-collapse:separate;border-spacing:0;background:var(--surface);
  border:1px solid var(--rule);border-radius:var(--radius);overflow:hidden;font-size:14.5px}
.method-table th,.method-table td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--rule-soft);
  vertical-align:middle}
.method-table thead th{background:var(--canvas);font-size:12px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-soft)}
.method-table td.t{font-weight:900;white-space:nowrap}
.method-table td.o{white-space:nowrap}
.method-table td.o .tp{display:block;margin-top:4px;font-weight:700;font-variant-numeric:tabular-nums}
.flow svg{display:block;width:100%;height:auto;max-width:1060px;margin:0 auto}
.flow figcaption a{margin-left:6px}
.method-table tr:last-child td{border-bottom:0}

/* sources */
.sources{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}
.source{border:1px solid var(--rule);border-radius:var(--radius);padding:18px;background:var(--surface)}
.source.core{border-color:var(--blue);box-shadow:inset 0 3px 0 var(--blue)}
.source b{display:block;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-soft)}
.source.core b{color:var(--blue)}
.source strong{display:block;font-size:16px;margin:6px 0}
.source p{font-size:13.5px;color:var(--ink-soft)}
.more-link{margin-top:24px;display:flex;justify-content:flex-end}

@media (max-width:1080px){
  .gates{grid-template-columns:repeat(3,minmax(0,1fr))}
  .sources{grid-template-columns:repeat(2,minmax(0,1fr))}
  .chain-demo{grid-template-columns:1fr}
}
.method-wrap{overflow-x:auto;border-radius:var(--radius)}
@media (max-width:560px){
  .method-table th:nth-child(2),.method-table td:nth-child(2){display:none}
  .gates{grid-template-columns:1fr}
  .sources{grid-template-columns:1fr}
}

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


def _hero_card(item) -> str:
    """A real report: rating, target and the method chain that produced it."""
    if not item:
        return """<figure style="margin:0">
        <div class="preview" role="img" aria-label="Contoh tampilan hasil riset.">
          <div class="preview-top">
            <div class="preview-ticker">
              <span class="ticker-badge" aria-hidden="true">BEI</span>
              <div><strong>Riset emiten</strong><span>Company update</span></div>
            </div>
            <span class="pill live">Contoh</span>
          </div>
          <ol class="steps">
            <li><span class="dot ok" aria-hidden="true">✓</span><div><strong>Rencana &amp; hipotesis disusun</strong>
              <span>Agen memilih tool: peer, kuartalan, arus asing, valuasi</span></div></li>
            <li><span class="dot ok" aria-hidden="true">✓</span><div><strong>Metode valuasi dipilih gerbang framework</strong>
              <span>Metode utama, fallback, lalu silang cek</span></div></li>
            <li><span class="dot warn" aria-hidden="true">!</span><div><strong>Rating ditahan bila bukti kurang</strong>
              <span>Alasannya tercatat di jejak audit</span></div></li>
          </ol>
        </div>
        <figcaption class="preview-caption">Ilustrasi tampilan, bukan hasil riset aktual.</figcaption>
      </figure>"""
    t = html.escape(item["ticker"])
    upside = item.get("upside")
    up_text = fmt.pct(upside / 100).replace("-", "−") if isinstance(upside, (int, float)) else "-"
    up_cls = "neg" if isinstance(upside, (int, float)) and upside < 0 else "pos"
    marks = {"Terpilih": ("sel", "✓"), "Silang cek": ("xchk", "≈"), "Dilewati": ("skip", "↷"),
             "Tidak dijalankan": ("skip", "·")}
    rows = []
    for step in item["chain"][:5]:
        cls, mark = marks.get(step["decision"], ("skip", "·"))
        value = step["value"] if step["value"] not in ("-", "ditahan") else ""
        rows.append(f'<li class="{cls}"><span class="mark" aria-hidden="true">{mark}</span>'
                    f'<span class="step">{html.escape(step["step"])}'
                    f'<span class="dec">{html.escape(step["decision"])}</span></span>'
                    f'<span class="val">{html.escape(value)}</span></li>')
    return f"""<figure style="margin:0">
        <div class="hero-card">
          <div class="hc-top"><span class="tbadge">{t}</span>
            <div><strong>{html.escape(item["name"])}</strong>
              <span class="sub">{html.escape(item["profile"])} · {html.escape(item["date"])}</span></div>
            <span class="rating {gallery_page.rating_class(item)}">{html.escape(gallery_page.rating_label(item))}</span></div>
          <p class="hc-head">{html.escape(item["headline"])}</p>
          <dl class="hc-stats"><div><dt>Target</dt><dd>Rp{fmt.rp(item["tp"])}</dd></div>
            <div><dt>Potensi</dt><dd class="{up_cls}">{up_text}</dd></div>
            <div><dt>Harga</dt><dd>Rp{fmt.rp(item["price"])}</dd></div></dl>
          <ol class="chain" aria-label="Rantai metode valuasi {t}">{"".join(rows)}</ol>
          <div class="hc-foot">
            <a class="btn btn-primary sm" href="/laporan/{t}/pdf">Buka PDF</a>
            <a class="btn btn-ghost sm" href="/laporan/{t}/trace">Lihat jejak audit</a>
          </div>
        </div>
        <figcaption class="preview-caption">Hasil riset nyata dari folder laporan, data per {html.escape(item["date"])}.</figcaption>
      </figure>"""


def _method_rows(items) -> str:
    rows = []
    for item in items[:8]:
        if item["published"]:
            outcome = (f'<span class="rating {gallery_page.rating_class(item)}">'
                       f'{html.escape(item["rating"])}</span><span class="tp">Rp{fmt.rp(item["tp"])}</span>')
            method = item["method"]
        else:
            outcome = '<span class="rating review">Review</span>'
            method = f'Ditahan: {item["held_reason"]}'
        rows.append(f'<tr><td class="t">{html.escape(item["ticker"])}</td>'
                    f'<td>{html.escape(item["profile"])}</td>'
                    f'<td>{html.escape(method)}</td><td class="o">{outcome}</td></tr>')
    return "".join(rows)


def render_landing(items=None) -> str:
    """Render the Indonesian landing page; ``items`` are gallery summaries."""
    items = list(items or [])
    published = [i for i in items if i["published"]]
    # Feature a report whose primary method set the target, with the most
    # cross-checks beside it.
    def richness(item):
        decisions = [step["decision"] for step in item["chain"]]
        primary = bool(decisions) and decisions[0] == "Terpilih"
        return (primary, decisions.count("Silang cek"), len(decisions))
    featured = max((i for i in published if i["files"].get("pdf") and i["chain"]),
                   key=richness, default=None)
    coverage = "".join(gallery_page.card(i) for i in items[:6])
    method_table = (f"""<div class="method-wrap" role="region" aria-label="Metode terpilih per emiten" tabindex="0"><table class="method-table">
          <thead><tr><th scope="col">Emiten</th><th scope="col">Profil</th>
            <th scope="col">Metode terpilih</th><th scope="col">Hasil</th></tr></thead>
          <tbody>{_method_rows(items)}</tbody></table></div>""" if items else "")
    body = f"""<body>
<!--
THESIS: Evidence-backed company research, not a generic AI finance landing page; refuse claims of live data or trading.
OWN-WORLD: Sectoral blue/white/charcoal/Roboto; thin rules, precise report-like diagrams, restrained teal and green accents.
STORY: A ticker becomes a rated company update whose valuation method is chosen by framework gates, and held back when evidence is short.
FIRST VIEWPORT: Brand/navigation; headline and CTA left; a real report with its method chain right; source and no-advice facts beneath the CTA.
FORM: Evidence instrument, assigned structure, seed ae210778.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
-->
{ui.site_header("home")}
<main id="konten">
  <section class="hero" aria-labelledby="hero-title">
    <div class="wrap">
      <div>
        <span class="pill live">Riset emiten BEI · metode valuasi berbasis gerbang</span>
        <h1 id="hero-title">Company update dengan <em>metode yang tepat</em>, bukan DCF untuk semua.</h1>
        <p class="lead">Sectoral membaca data Sectors dan rilis resmi emiten, menyusun skenario laba dari
        berita bertanggal, lalu memilih metode valuasi lewat gerbang framework: DDM untuk bank, DCF FCFF
        untuk korporasi, SOTP untuk grup beragam lini, NAV cadangan untuk tambang. Rating hanya terbit bila
        setiap pemeriksaan lolos.</p>
        <div class="cta-row">
          <a href="/research" class="btn btn-primary">Coba riset emiten <span class="arrow" aria-hidden="true">→</span></a>
          <a href="/laporan" class="btn btn-ghost">Lihat laporan</a>
        </div>
        <ul class="facts" aria-label="Ringkasan batasan">
          <li>Gerbang framework 0-5</li>
          <li>Risiko utama bersumber</li>
          <li>Tanpa eksekusi transaksi</li>
        </ul>
      </div>
      {_hero_card(featured)}
    </div>
  </section>

  <section id="cara-kerja" class="block" aria-labelledby="cara-kerja-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Cara kerja</span>
        <h2 id="cara-kerja-title">Agen menalar, kode menghitung, gerbang memutuskan.</h2>
        <p>Model bahasa menyusun rencana, asumsi, dan narasi. Setiap angka dihitung dari data terstruktur,
        dan setiap keputusan terbit atau tahan diambil oleh pemeriksaan berbasis kode.</p>
      </div>
      <ol class="how">
        <li>
          <h3>Baca bukti bertanggal</h3>
          <p>Agen analis memilih data Sectors: peer, kinerja kuartalan, harga vs IHSG, arus asing, valuasi.
          Rilis resmi emiten dan harga penutupan IDX melengkapi, dan berita bertanggal dibaca utuh sebagai konteks.</p>
        </li>
        <li>
          <h3>Susun skenario laba</h3>
          <p>Agen asumsi memakai aktual 1H resmi untuk skenario semester kedua, tahun lanjutan, tesis, katalis,
          dan risiko utama. Setiap asumsi wajib mengutip sumber; yang tidak lolos validasi ditolak.</p>
        </li>
        <li>
          <h3>Pilih metode, lalu periksa</h3>
          <p>Gerbang framework menentukan rantai metode sebelum nilai dihitung. Harness memeriksa sumber,
          periode, dan kewajaran hasil; bila ada yang gagal, rating ditahan dan alasannya dicatat.</p>
        </li>
      </ol>
      <figure class="flow">
        {ui.FLOW_SVG}
        <figcaption>Alur riset dari bukti bertanggal hingga company update.
          <a href="{ui.FLOW_URL}">Buka diagram</a></figcaption>
      </figure>
    </div>
  </section>

  <section id="framework" class="block alt" aria-labelledby="framework-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Framework valuasi</span>
        <h2 id="framework-title">Enam gerbang memilih metode sebelum angka dihitung.</h2>
        <p>DCF bukan jawaban untuk semua emiten. Gerbang membaca model bisnis, kualitas data, kepemilikan,
        siklus, dan tahap usaha, lalu mengurutkan metode utama, fallback, dan silang cek.</p>
      </div>
      <ol class="gates">
        <li><b>Method Gate 0</b><strong>Model bisnis</strong><span>Bank ke DDM/P/BV, tambang ke NAV, holding ke SOTP</span></li>
        <li><b>Method Gate 1</b><strong>Kelayakan data</strong><span>Riwayat, laba usaha, leverage, ekuitas</span></li>
        <li><b>Method Gate 2</b><strong>Kepemilikan</strong><span>Minoritas 15-40% wajib silang cek SOTP</span></li>
        <li><b>Method Gate 3</b><strong>Siklus</strong><span>Komoditas atau aset yang baru ramp-up</span></li>
        <li><b>Method Gate 4</b><strong>Tahap usaha</strong><span>Tumbuh, matang, atau turnaround</span></li>
        <li><b>Method Gate 5</b><strong>Kewajaran hasil</strong><span>Potensi &gt;100% atau &lt;-50%: Review Required</span></li>
      </ol>
      <div class="chain-demo">
        <div class="chain-steps">
          <h3>Rantai metode</h3>
          <ol>
            <li><b>Metode utama</b> dari gerbang, misalnya DCF atau DDM.</li>
            <li><b>Fallback</b> hanya bila metode sebelumnya tidak memadai, bukan karena hasilnya tidak disukai.</li>
            <li><b>Silang cek</b> wajib: PER peer, P/S, atau SOTP, dengan alasan tercatat.</li>
            <li><b>Rating ditahan</b> bila tidak ada metode yang lolos.</li>
          </ol>
        </div>
        {method_table}
      </div>
    </div>
  </section>

  {f'''<section id="laporan" class="block" aria-labelledby="laporan-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Laporan</span>
        <h2 id="laporan-title">{len(published)} company update terbit, {len(items) - len(published)} ditahan untuk review.</h2>
        <p>Setiap laporan mengikuti struktur company update: sampul, tesis, industri, kinerja, katalis dan risiko,
        valuasi dengan rantai metode, serta laporan keuangan dua tahun aktual dan tiga tahun forecast.</p>
      </div>
      <div class="rgrid">{coverage}</div>
      <div class="more-link"><a class="btn btn-ghost" href="/laporan">Semua laporan <span class="arrow" aria-hidden="true">→</span></a></div>
    </div>
  </section>''' if items else ""}

  <section id="sumber" class="block alt" aria-labelledby="sumber-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Sumber data</span>
        <h2 id="sumber-title">Sectors di inti, setiap sumber lain diberi label.</h2>
        <p>Catatan sumber di bawah setiap exhibit menyebut dari mana angka itu berasal.</p>
      </div>
      <div class="sources">
        <div class="source core"><b>Inti</b><strong>Sectors</strong>
          <p>Fundamental, peer, harga, kepemilikan, arus asing, dan data sub-sektor.</p></div>
        <div class="source"><b>Rilis resmi</b><strong>Laporan emiten</strong>
          <p>Laporan keuangan interim dan daftar pemegang saham dari IDX dan situs emiten.</p></div>
        <div class="source"><b>Perdagangan</b><strong>IDX</strong>
          <p>Harga penutupan harian dan IHSG 24 bulan untuk grafik dan band valuasi.</p></div>
        <div class="source"><b>Konteks</b><strong>Berita bertanggal</strong>
          <p>Artikel dibaca utuh; dampak ke laba hanya bila ada driver terukur.</p></div>
        <div class="source"><b>Kurs</b><strong>USD/IDR</strong>
          <p>Kurs penutupan harian untuk emiten yang melapor dalam dolar.</p></div>
      </div>
    </div>
  </section>

  <section id="pemeriksaan" class="block" aria-labelledby="pemeriksaan-title">
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
            <th scope="col">Bukti lengkap <span class="pill ok">Terbit</span></th>
            <th scope="col">Bukti kurang <span class="pill warn">Review</span></th>
          </tr></thead>
          <tbody>
            <tr>
              <th scope="row">Angka kuantitatif<small>Pendapatan, margin, valuasi, rasio utang</small></th>
              <td><strong>Cocok dengan sumber</strong>Setiap angka sama dengan baris dan kolom yang dibaca.</td>
              <td><strong>Ditolak</strong>Angka yang tidak terverifikasi dibuang; bagian tersebut dinyatakan tanpa dukungan data.</td>
            </tr>
            <tr>
              <th scope="row">Asumsi agen<small>Skenario laba, risiko, katalis</small></th>
              <td><strong>Tervalidasi</strong>Sumber, periode, dan besaran lolos pemeriksaan skema.</td>
              <td><strong>Ditolak atau diperbaiki</strong>Asumsi tanpa sumber tidak masuk model; alasannya tercatat.</td>
            </tr>
            <tr>
              <th scope="row">Metode valuasi<small>Rantai dari gerbang framework</small></th>
              <td><strong>Metode terpilih lolos</strong>Nilai, sensitivitas, dan silang cek ditampilkan.</td>
              <td><strong>Semua metode gagal</strong>Tidak ada tebakan; tiap metode diberi alasan.</td>
            </tr>
            <tr>
              <th scope="row">Rating &amp; target harga<small>Gerbang forecast dan valuasi</small></th>
              <td><strong>Ditampilkan</strong>Hanya setelah metode yang dipilih lolos seluruh pemeriksaan.</td>
              <td><strong>Ditahan</strong>Laporan terbit sebagai draf parsial dengan banner bukti belum lengkap dan alasan penahanan.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="batasan" class="block alt" aria-labelledby="batasan-title">
    <div class="wrap">
      <div class="intro">
        <span class="eyebrow">Batasan</span>
        <h2 id="batasan-title">Jelas tentang apa yang tidak kami lakukan.</h2>
        <p>Kepercayaan pada analisis lahir dari kejelasan batas sistem.</p>
      </div>
      <div class="limits">
        <div class="limit"><span class="limit-icon">{_ICON["clock"]}</span><div>
          <h3>Data bertanggal, bukan siaran langsung</h3>
          <p>Riset membaca data Sectors yang tersimpan beserta tanggalnya, tanpa panggilan data pasar langsung.
          Harga penutupan dan rilis resmi yang terbit sesudah tanggal laporan tidak dipakai.</p>
        </div></div>
        <div class="limit"><span class="limit-icon">{_ICON["split"]}</span><div>
          <h3>LLM untuk nalar, bukan data</h3>
          <p>Model bahasa menyusun narasi dan asumsi bersumber. Angka finansial, rasio valuasi, dan tanggal laporan
          selalu diambil dari data terstruktur.</p>
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

  <section class="block" aria-labelledby="cta-title">
    <div class="wrap">
      <div class="cta-band">
        <div>
          <h2 id="cta-title">Mulai dari satu kode emiten.</h2>
          <p>Jalankan agen riset, ikuti prosesnya, lalu buka company update beserta jejak auditnya.</p>
        </div>
        <a href="/research" class="btn">Coba riset emiten <span class="arrow" aria-hidden="true">→</span></a>
      </div>
    </div>
  </section>
</main>
{ui.site_footer()}
</body>"""
    return ui.document(
        "Sectoral — Company update emiten BEI dengan metode valuasi berbasis gerbang",
        "Sectoral mengubah data Sectors dan rilis resmi emiten menjadi company update emiten BEI "
        "dengan metode valuasi yang dipilih gerbang framework dan batas bukti yang transparan.",
        _CSS + gallery_page.CARD_CSS,
        body,
    )
