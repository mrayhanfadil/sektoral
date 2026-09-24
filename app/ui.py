"""Shared visual system for the local Sectoral web pages.

The landing page and the research workflow render from the same tokens,
header and footer so the product reads as one application. Fonts are
embedded as data URIs because the local server exposes no font route.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"


def _embedded_font(filename: str) -> str:
    try:
        encoded = base64.b64encode((_ASSETS / "fonts" / filename).read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:font/ttf;base64,{encoded}"


@lru_cache(maxsize=1)
def font_faces() -> str:
    faces = []
    for filename, weight, style in (
        ("Roboto-Regular.ttf", "400", "normal"),
        ("Roboto-Bold.ttf", "500 900", "normal"),
        ("Roboto-Italic.ttf", "400", "italic"),
    ):
        src = _embedded_font(filename)
        if src:
            faces.append(
                f"@font-face{{font-family:Roboto;src:url('{src}') format('truetype');"
                f"font-weight:{weight};font-style:{style};font-display:swap}}"
            )
    return "\n".join(faces)


# Sectoral Design System: primary #0928B1, charcoal #333333, rule #D9D9D9,
# table tint #B4C7FF, accents #1DCD9F / #3ED628.
TOKENS = """
:root{
  --blue:#0928B1;--blue-hover:#071F8A;--blue-50:#F2F5FF;--blue-100:#E3E9FF;--tint:#B4C7FF;
  --ink:#333333;--ink-soft:#5B5F6B;--rule:#D9D9D9;--rule-soft:#ECEEF2;
  --surface:#FFFFFF;--canvas:#F7F8FA;
  --teal:#1DCD9F;--green:#3ED628;
  --ok-bg:#E8FAF4;--ok-ink:#0B6B50;--warn-bg:#FFF6E0;--warn-ink:#7A4B00;--warn-rule:#F0B429;
  --err-bg:#FDECEC;--err-ink:#9B1C1C;
  --radius:12px;--radius-sm:8px;
  --font:Roboto,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  --mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --shadow:0 1px 2px rgba(16,24,40,.05),0 8px 24px -12px rgba(16,24,40,.12);
}
"""

BASE_CSS = TOKENS + """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--surface);color:var(--ink);font:16px/1.6 var(--font);
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
h1,h2,h3,h4{margin:0;color:var(--ink);line-height:1.2;letter-spacing:-.01em}
p{margin:0}
a{color:var(--blue)}
img{max-width:100%;height:auto}
[hidden]{display:none!important}
:focus-visible{outline:3px solid var(--blue);outline-offset:2px;border-radius:4px}
.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;border:0}
.skip-link{position:absolute;left:16px;top:-48px;z-index:100;background:var(--blue);color:#fff;
  padding:8px 14px;border-radius:0 0 8px 8px;font-weight:700;text-decoration:none}
.skip-link:focus{top:0}
.wrap{width:100%;max-width:1120px;margin:0 auto;padding:0 24px}

/* header */
.site-header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.92);
  backdrop-filter:saturate(1.4) blur(10px);-webkit-backdrop-filter:saturate(1.4) blur(10px);
  border-bottom:1px solid var(--rule-soft)}
.site-header .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;height:64px}
.brand{display:flex;align-items:center;flex:none}
.brand svg{display:block;height:30px;width:auto}
.nav{display:flex;align-items:center;gap:4px}
.nav a{color:var(--ink-soft);font-size:15px;font-weight:500;text-decoration:none;padding:8px 12px;
  border-radius:8px}
.nav a:hover{color:var(--ink);background:var(--canvas)}
.nav a:not(.nav-cta)[aria-current="page"]{color:var(--blue)}
.nav .nav-cta{color:#fff;background:var(--blue);margin-left:8px}
.nav .nav-cta:hover{color:#fff;background:var(--blue-hover)}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:46px;
  padding:0 20px;border-radius:var(--radius-sm);border:1px solid transparent;font:inherit;
  font-size:15px;font-weight:700;text-decoration:none;cursor:pointer;
  transition:background-color .15s,border-color .15s,color .15s}
.btn-primary{background:var(--blue);color:#fff}
.btn-primary:hover{background:var(--blue-hover)}
.btn-primary:disabled{opacity:.6;cursor:progress}
.btn-ghost{background:var(--surface);color:var(--blue);border-color:var(--rule)}
.btn-ghost:hover{border-color:var(--blue);background:var(--blue-50)}
.btn .arrow{transition:transform .15s}
.btn:hover .arrow{transform:translateX(3px)}

.eyebrow{display:inline-block;color:var(--blue);font-size:12px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}
.pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:3px 10px;
  font-size:13px;font-weight:700;line-height:1.5;background:var(--canvas);color:var(--ink-soft)}
.pill.ok{background:var(--ok-bg);color:var(--ok-ink)}
.pill.warn{background:var(--warn-bg);color:var(--warn-ink)}
.pill.err{background:var(--err-bg);color:var(--err-ink)}
.pill.live{background:var(--blue-50);color:var(--blue)}

/* footer */
.site-footer{border-top:1px solid var(--rule-soft);background:var(--canvas);margin-top:auto}
.site-footer .wrap{padding-top:28px;padding-bottom:32px;display:grid;gap:18px}
.footer-note{font-size:13.5px;color:var(--ink-soft);max-width:80ch}
.footer-row{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px;
  font-size:13px;color:var(--ink-soft)}
.footer-row img{height:20px;width:auto;display:block}
.footer-links{display:flex;flex-wrap:wrap;gap:16px}
.footer-links a{color:var(--ink-soft);text-decoration:none}
.footer-links a:hover{color:var(--blue)}

@media (max-width:720px){
  .wrap{padding:0 16px}
  .nav a:not(.nav-cta){display:none}
  .nav .nav-cta{margin-left:0}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;
    transition-duration:.01ms!important;scroll-behavior:auto!important}
}
"""

LOGO_URL = "/assets/brand/sectoral-logo.svg"
# Inlined so the wordmark text picks up the embedded Roboto face (the web
# shell carries no Arial fallback; Roboto is always embedded).
LOGO_SVG = (_ASSETS / "brand" / "sectoral-logo.svg").read_text(encoding="utf-8").replace(
    "Roboto, Arial, sans-serif", "Roboto, sans-serif")
FLOW_URL = "/assets/brand/research-flow.svg"


def site_header(current: str = "") -> str:
    """Shared top bar. ``current`` is ``"home"`` or ``"research"``."""
    home = "#" if current == "home" else "/#"
    research_attr = ' aria-current="page"' if current == "research" else ""
    return f"""<a href="#konten" class="skip-link">Lewati ke konten utama</a>
<header class="site-header"><div class="wrap">
  <a href="/" class="brand" aria-label="Sectoral, beranda">{LOGO_SVG}</a>
  <nav class="nav" aria-label="Navigasi utama">
    <a href="{home}cara-kerja">Cara kerja</a>
    <a href="{home}pemeriksaan">Pemeriksaan bukti</a>
    <a href="{home}batasan">Batasan</a>
    <a href="/research" class="nav-cta"{research_attr}>Coba riset emiten</a>
  </nav>
</div></header>"""


def site_footer() -> str:
    return f"""<footer class="site-footer"><div class="wrap">
  <p class="footer-note"><strong>Bukan rekomendasi investasi.</strong> Sectoral menyajikan informasi dan analisis
  untuk mendukung kerja analis. Rating dan target harga hanya muncul setelah pemeriksaan data, forecast, dan valuasi lolos.
  Sectoral tidak terhubung ke broker dan tidak mengeksekusi transaksi. Keputusan investasi tetap tanggung jawab pembaca.</p>
  <div class="footer-row">
    <img src="{LOGO_URL}" alt="Sectoral" width="92" height="20">
    <nav class="footer-links" aria-label="Tautan footer">
      <a href="/research">Aplikasi riset</a><a href="/#cara-kerja">Cara kerja</a>
      <a href="/#pemeriksaan">Pemeriksaan bukti</a><a href="/#batasan">Batasan</a>
    </nav>
    <span>© 2026 Sektoral · Sectors Hackathon 2026</span>
  </div>
</div></footer>"""


def document(title: str, description: str, css: str, body: str, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>{font_faces()}
{BASE_CSS}
{css}</style>
</head>
{body}{script}
</html>"""
