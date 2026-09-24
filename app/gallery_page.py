"""Report cards and the /laporan gallery page (shared with the landing page)."""
from __future__ import annotations

import html

from . import fmt, ui

CARD_CSS = """
/* report cards */
.rgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}
.rcard{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--rule);
  border-radius:var(--radius);overflow:hidden;transition:border-color .15s}
.rcard:hover{border-color:#B9BDC6}
.rthumb{display:block;aspect-ratio:210/150;overflow:hidden;background:var(--canvas);
  border-bottom:1px solid var(--rule-soft)}
.rthumb img{display:block;width:100%;height:auto;object-fit:cover;object-position:top}
.rbody{display:flex;flex-direction:column;gap:12px;padding:18px 18px 16px;flex:1}
.rhead{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center}
.tbadge{display:inline-grid;place-items:center;min-width:56px;height:40px;padding:0 8px;
  border-radius:10px;background:var(--blue);color:#fff;font-weight:900;font-size:14px;
  letter-spacing:.05em;white-space:nowrap}
.rhead strong{display:block;font-size:14.5px;line-height:1.3}
.rhead span.sub{display:block;font-size:12.5px;color:var(--ink-soft)}
.rating{display:inline-flex;align-items:center;border-radius:999px;padding:4px 12px;font-size:13px;
  font-weight:900;letter-spacing:.02em;white-space:nowrap}
.rating.buy{background:var(--ok-bg);color:var(--ok-ink)}
.rating.hold{background:var(--blue-50);color:var(--blue)}
.rating.sell{background:var(--err-bg);color:var(--err-ink)}
.rating.review{background:var(--warn-bg);color:var(--warn-ink)}
.rheadline{font-weight:700;font-size:15px;line-height:1.35}
.rstats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0}
.rstats div{background:var(--canvas);border-radius:8px;padding:8px 10px}
.rstats dt{font-size:12.5px;color:var(--ink-soft)}
.rstats dd{margin:0;font-weight:900;font-size:15px;font-variant-numeric:tabular-nums}
.rstats dd.neg{color:var(--err-ink)}.rstats dd.pos{color:var(--ok-ink)}
.rmethod{font-size:13px;color:var(--ink-soft)}
.rmethod b{color:var(--ink)}
.ractions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
.btn.sm{min-height:36px;padding:0 14px;font-size:13.5px}
.rheld{font-size:13.5px;color:var(--warn-ink);background:var(--warn-bg);border-radius:8px;
  padding:8px 10px}
"""

_PAGE_CSS = CARD_CSS + """
.gallery-head{padding:48px 0 28px;border-bottom:1px solid var(--rule-soft);
  background:radial-gradient(700px 300px at 90% -20%,var(--blue-50),transparent 70%)}
.gallery-head h1{font-size:clamp(28px,3.4vw,40px);font-weight:900;letter-spacing:-.02em;margin:0 0 10px}
.gallery-head p{color:var(--ink-soft);max-width:70ch}
.gallery-stats{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}
.gallery-body{padding:32px 0 72px}
.empty{border:1px dashed var(--rule);border-radius:var(--radius);padding:32px;color:var(--ink-soft);
  background:var(--canvas)}
.empty code{font-family:var(--mono);font-size:13px;background:var(--surface);padding:2px 6px;
  border-radius:6px;border:1px solid var(--rule-soft)}
"""


def rating_class(item) -> str:
    rating = str(item.get("rating") or "").lower()
    return rating if rating in {"buy", "hold", "sell"} else "review"


def rating_label(item) -> str:
    """Published rating; a held report is a Draft unless Method Gate 5 held it."""
    if item.get("rating"):
        return str(item["rating"])
    return "Review Required" if str(item.get("held_reason") or "").startswith("Method Gate 5") else "Draft"


def _upside(item) -> tuple[str, str]:
    value = item.get("upside")
    if not isinstance(value, (int, float)):
        return "-", ""
    return fmt.pct(value / 100).replace("-", "−"), ("neg" if value < 0 else "pos")


def card(item, thumb: bool = True) -> str:
    """One report card; links point at the gallery routes."""
    t = html.escape(item["ticker"])
    name = html.escape(item["name"])
    sub = html.escape(" · ".join(x for x in (item["profile"], item["date"]) if x))
    upside, cls = _upside(item)
    if item["published"]:
        body = (f'<dl class="rstats"><div><dt>Target</dt><dd>Rp{fmt.rp(item["tp"])}</dd></div>'
                f'<div><dt>Potensi</dt><dd class="{cls}">{upside}</dd></div>'
                f'<div><dt>Harga</dt><dd>Rp{fmt.rp(item["price"])}</dd></div></dl>'
                f'<p class="rmethod">Metode: <b>{html.escape(item["method"])}</b></p>')
    else:
        body = (f'<p class="rheld"><b>Rating ditahan:</b> {html.escape(item.get("held_reason") or "bukti belum lengkap")}. '
                'Rincian tiap pemeriksaan tercatat di jejak.</p>')
    thumb_html = (f'<a class="rthumb" href="/laporan/{t}/pdf" aria-label="Buka PDF {t}">'
                  f'<img src="/laporan/{t}/cover.png" alt="Halaman sampul company update {t}" '
                  f'loading="lazy" width="420" height="300"></a>'
                  if thumb and item["files"].get("pdf") else "")
    actions = []
    if item["files"].get("pdf"):
        actions.append(f'<a class="btn btn-primary sm" href="/laporan/{t}/pdf">Buka PDF</a>')
    if item["files"].get("html"):
        actions.append(f'<a class="btn btn-ghost sm" href="/laporan/{t}/html">Versi web</a>')
    if item["files"].get("trace"):
        actions.append(f'<a class="btn btn-ghost sm" href="/laporan/{t}/trace">Jejak</a>')
    return f"""<article class="rcard">{thumb_html}
  <div class="rbody">
    <div class="rhead"><span class="tbadge">{t}</span>
      <div><strong>{name}</strong><span class="sub">{sub}</span></div>
      <span class="rating {rating_class(item)}">{html.escape(rating_label(item))}</span></div>
    <p class="rheadline">{html.escape(item["headline"])}</p>
    {body}
    <div class="ractions">{"".join(actions)}</div>
  </div>
</article>"""


def render_gallery(items) -> str:
    published = [i for i in items if i["published"]]
    counts = {}
    for item in published:
        counts[item["rating"]] = counts.get(item["rating"], 0) + 1
    stats = "".join(
        f'<span class="pill {"ok" if k == "Buy" else "err" if k == "Sell" else "live"}">'
        f'{v} {html.escape(str(k))}</span>' for k, v in sorted(counts.items()))
    drafts = len(items) - len(published)
    if drafts:
        stats += f'<span class="pill warn">{drafts} Draft</span>'
    grid = ('<div class="rgrid">' + "".join(card(i) for i in items) + "</div>" if items else
            '<div class="empty"><strong>Belum ada laporan.</strong> Jalankan '
            '<code>python -m app.batch BBCA JPFA --out out/reports --pdf</code> lalu muat ulang '
            'halaman ini.</div>')
    body = f"""<body>
{ui.site_header("laporan")}
<main id="konten">
  <section class="gallery-head" aria-labelledby="gallery-title"><div class="wrap">
    <h1 id="gallery-title">Company update yang sudah terbit</h1>
    <p>Setiap laporan memilih metode valuasi lewat gerbang framework, lalu menahan rating bila
    bukti belum cukup. Buka PDF, versi web, atau jejak audit untuk menelusuri tiap angka.</p>
    <div class="gallery-stats">{stats}</div>
  </div></section>
  <section class="gallery-body" aria-label="Daftar laporan"><div class="wrap">{grid}</div></section>
</main>
{ui.site_footer()}
</body>"""
    return ui.document("Sectoral | Laporan", "Company update emiten BEI yang dihasilkan Sectoral.",
                       _PAGE_CSS, body)
