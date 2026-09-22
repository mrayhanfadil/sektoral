"""Renderer HTML tiru-layout contoh GMFI (8 halaman). Brand Sektoral, bukan BRIDS.

Struktur: header → rating → cover 2 kolom (data pasar + narasi) → Key
Financials → halaman 2-6 → metodologi + disclaimer. Chart SVG native dari
cache daily. Nomor halaman via CSS counter. Cetak via app/pdf.py (A4).
"""
import base64
import html
from pathlib import Path
from . import cache as cache_mod

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


def _b64_font(filename):
    p = FONTS_DIR / filename
    return base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""


_POP_REG = _b64_font("Poppins-Regular.ttf")
_POP_BOLD = _b64_font("Poppins-Bold.ttf")
_POP_ITA = _b64_font("Poppins-Italic.ttf")

NAVY = "#002060"
ROYAL_BLUE = "#0F4C9C"
PAPER = "#ffffff"
INK = "#1a1a1a"
MUT = "#555555"

PAGE_NUM = ('@page{size:A4;margin:12mm 12mm 14mm}'
            '@page{@bottom-right{content:"Halaman " counter(page);'
            'font-family:\'Poppins\',sans-serif;font-size:7.2pt;color:' + MUT + '}}')

FONT_FACES = (
    f"@font-face{{font-family:'Poppins';src:url('data:font/truetype;charset=utf-8;base64,{_POP_REG}') format('truetype');font-weight:400;font-style:normal;}}\n"
    f"@font-face{{font-family:'Poppins';src:url('data:font/truetype;charset=utf-8;base64,{_POP_BOLD}') format('truetype');font-weight:700;font-style:normal;}}\n"
    f"@font-face{{font-family:'Poppins';src:url('data:font/truetype;charset=utf-8;base64,{_POP_BOLD}') format('truetype');font-weight:800;font-style:normal;}}\n"
    f"@font-face{{font-family:'Poppins';src:url('data:font/truetype;charset=utf-8;base64,{_POP_ITA}') format('truetype');font-weight:400;font-style:italic;}}\n"
)

CSS = (FONT_FACES + PAGE_NUM +
       "body{font-family:'Poppins',sans-serif;color:" + INK + ";background:" + PAPER +
       ";font-size:8.1pt;line-height:1.42;margin:0}"
       ".topbar{display:flex;justify-content:space-between;border-bottom:2px solid "
       + ROYAL_BLUE + ";padding-bottom:3px;font-size:8.1pt;color:" + ROYAL_BLUE + ";font-weight:600}"
       ".rating{font-weight:800;font-size:22pt;color:" + NAVY + ";margin:2px 0 0;line-height:1.1}"
       ".status{font-size:8.5pt;color:" + MUT + ";margin-bottom:3px}"
       ".cover{display:flex;gap:12px;margin-top:3px}"
       ".left{width:32%;font-size:7.8pt}"
       ".right{width:68%}"
       ".kv{display:flex;justify-content:space-between;align-items:baseline;padding:2px 0;border-bottom:1px dotted #ccc}"
       ".kv span{padding-right:4px}.kv b{font-weight:700;color:" + INK + ";white-space:nowrap}"
       ".panel{background:#f2f5f9;padding:5px 6px;border:1px solid #d5dfea;border-radius:2px}"
       "h1.emit{font-size:12.8pt;margin:0 0 2px;color:" + NAVY + ";font-weight:700}"
       ".headline{font-size:10.8pt;font-weight:700;color:" + ROYAL_BLUE + ";margin:2px 0 4px}"
       ".bullets{margin:4px 0 6px 14px;padding:0;font-size:7.9pt}.bullets li{margin-bottom:3px}"
       "h2.sec{font-size:11pt;color:" + ROYAL_BLUE + ";font-weight:700;margin:10px 0 5px}"
       "h3.sub{font-size:8.8pt;color:" + NAVY + ";font-weight:700;margin:5px 0 2px}"
       "table{border-collapse:collapse;width:100%;font-size:7.2pt;margin:3px 0 2px;font-family:'Poppins',sans-serif}"
       "th,td{border:1px solid #d8dee4;padding:2.5px 5px;text-align:right;overflow-wrap:break-word;word-break:normal}"
       "th:first-child,td:first-child{text-align:left}"
       "th{background:" + NAVY + ";color:#fff;font-weight:700}"
       "tr:nth-child(even) td{background:#f8fafc}"
       "caption{text-align:left;font-weight:700;font-size:7.8pt;color:" + NAVY + ";margin-bottom:2px;font-family:'Poppins',sans-serif}"
       ".src{font-size:6.7pt;color:" + MUT + ";margin:2px 0 6px;line-height:1.3}"
       ".page{page-break-before:always}"
       ".foot{font-size:7pt;color:" + MUT + ";border-top:1px solid #d0d7de;margin-top:8px;"
       "padding-top:3px;display:flex;justify-content:space-between}"
       ".small{font-size:7.5pt;color:" + MUT + "}"
       ".grid-2{display:flex;gap:12px;width:100%;margin:4px 0;box-sizing:border-box}"
       ".grid-col{flex:1 1 0;min-width:0;box-sizing:border-box}")


def _price_chart(ticker):
    """SVG garis harga dari seluruh window daily cache (tanggal unik)."""
    pts = {}
    for _, p in cache_mod.payloads(f"/daily/{ticker}/"):
        for r in (p.get("data") or []):
            if r.get("date") and r.get("close"):
                pts[r["date"]] = float(r["close"])
    dates = sorted(pts)
    if len(dates) < 2:
        return "<p class='small'>[Grafik harga tidak tersedia di cache]</p>"
    W, H, P = 220, 85, 6
    vs = [pts[d] for d in dates]
    lo, hi = min(vs), max(vs)
    span = (hi - lo) or 1
    xy = [(P + i * (W - 2 * P) / (len(vs) - 1), H - P - (v - lo) / span * (H - 2 * P))
          for i, v in enumerate(vs)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    return (f"<svg width='{W}' height='{H + 14}'><polyline points='{line}' "
            f"fill='none' stroke='{ROYAL_BLUE}' stroke-width='1.5'/>"
            f"<text x='{P}' y='{H + 11}' font-size='8' font-family='Poppins, sans-serif' fill='{MUT}'>{dates[0]}</text>"
            f"<text x='{W - P - 52}' y='{H + 11}' font-size='8' font-family='Poppins, sans-serif' fill='{MUT}'>{dates[-1]}</text>"
            f"<text x='{P}' y='10' font-size='8' font-family='Poppins, sans-serif' fill='{MUT}'>{hi:,.0f}</text></svg>"
            f"<p class='src'>Harga {html.escape(ticker)} {len(dates)} hari bursa terakhir "
            f"di cache. Overlay IHSG tidak ditampilkan (window indeks di cache beda periode).</p>")


def _table(ex):
    d = ex["data"]
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r)
                   + "</tr>" for r in d["rows"])
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in d["cols"])
    return (f"<div><table><caption>Exhibit {ex['n']}. {html.escape(ex['judul'])}</caption>"
            f"<tr>{head}</tr>{rows}</table>"
            f"<p class='src'>{html.escape(ex['catatan_sumber'])}</p></div>")


def _kv(k, v):
    return f"<div class='kv'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>"


def _foot():
    return ("<div class='foot'><span>sektoral</span>"
            "<span>Lihat pengungkapan penting di bagian akhir laporan ini</span>"
            "<span></span></div>")


def _topbar(date):
    return ("<div class='topbar'><span>Equity Research - Company Update | "
            f"{html.escape(str(date))}</span><span>Sektoral</span></div>")


def _render_page_content(b):
    halaman = b.get("halaman")
    exs = b.get("exhibit") or []
    paras = b.get("paragraf") or []

    res = []
    if halaman == 2:
        if len(paras) >= 2:
            res.append(f"<p>{html.escape(paras[0])}</p>")
            res.append(f"<p>{html.escape(paras[1])}</p>")
        elif paras:
            for p in paras:
                res.append(f"<p>{html.escape(p)}</p>")

        if len(exs) >= 2:
            res.append(f"<div class='grid-2'>"
                       f"<div class='grid-col'>{_table(exs[0])}</div>"
                       f"<div class='grid-col'>{_table(exs[1])}</div>"
                       f"</div>")
        elif exs:
            for e in exs:
                res.append(_table(e))

        if len(paras) >= 3:
            for p in paras[2:]:
                res.append(f"<p>{html.escape(p)}</p>")

    elif halaman == 5 and len(exs) == 4:
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        res.append("<div class='grid-2'>"
                   f"<div class='grid-col'>{_table(exs[0])}</div>"
                   f"<div class='grid-col'>{_table(exs[1])}{_table(exs[2])}</div>"
                   "</div>")
        res.append(_table(exs[3]))

    elif halaman == 6 and len(exs) == 3:
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        res.append(_table(exs[0]))
        res.append("<div class='grid-2'>"
                   f"<div class='grid-col'>{_table(exs[1])}</div>"
                   f"<div class='grid-col'>{_table(exs[2])}</div>"
                   "</div>")

    else:
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        for e in exs:
            res.append(_table(e))

    return "\n".join(res)


def render(doc):
    m, cov = doc["meta"], doc["cover"]
    up = m["upside_persen"]
    ups = f"{up:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".") + "%"
    h = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
    h.append(_topbar(m["tanggal"]))
    h.append(f"<div class='rating'>{html.escape(m['rating'])}</div>"
             "<div class='status'>(Inisiasi)</div>")
    h.append("<div class='cover'><div class='left'>")
    h.append(f"<div class='small'>Valuasi: {html.escape(doc.get('method', 'DCF'))}</div>"
             "<div class='panel'>")
    h.append(_kv("Harga Terakhir (Rp)", f"{m['harga']:,.0f}"))
    h.append(_kv("Target Harga (Rp)", f"{m['tp']:,}"))
    h.append(_kv("TP Sebelumnya (Rp)", "n.a."))
    h.append(_kv("Upside/Downside", ups))
    h.append(_kv("Jumlah Saham (juta)", f"{cov['data_pasar']['saham']/1e6:,.0f}"))
    h.append(_kv("Kap. Pasar (Rp miliar)", f"{cov['data_pasar']['market_cap']/1e9:,.0f}"))
    h.append(_kv("Rata-rata T/O Harian (Rp miliar)", str(cov["data_pasar"].get("adtv", "-"))))
    h.append(_kv("Free Float (%)", str(cov["data_pasar"].get("free_float", "-"))))
    for holder in (doc.get("holders") or [])[:2]:
        h.append(_kv(str(holder[0])[:22], str(holder[1])))
    h.append("</div>")
    f1 = doc.get("fy26") or {}
    if f1:
        h.append("<div class='panel' style='margin-top:5px'>"
                 "<div class='small'>FY26F: Sektoral Estimates (Rp miliar)</div>")
        for k in ("Pendapatan", "EBITDA", "Laba bersih"):
            if k in f1:
                h.append(_kv(k, f1[k]))
        h.append("</div>")
    h.append(f"<h3 class='sub'>{html.escape(m['ticker'])} relatif terhadap IHSG</h3>")
    h.append(_price_chart(m["ticker"]))
    h.append("<p class='src'>Sumber: Sectors cache (daily)</p>")
    h.append("<div class='small'>Analis Sektoral<br>Tim Riset Sektoral</div>")
    h.append("</div><div class='right'>")
    h.append(f"<h1 class='emit'>{html.escape(m['emiten'])} ({html.escape(m['ticker'])} IJ)</h1>")
    h.append(f"<div class='headline'>{html.escape(cov['headline'])}</div><ul class='bullets'>")
    for b in cov["bullets"]:
        h.append(f"<li>{html.escape(b)}</li>")
    h.append("</ul>")
    for p in cov["paragraf"]:
        h.append(f"<h3 class='sub'>{html.escape(p['judul'])}</h3><p>{html.escape(p['isi'])}</p>")
    h.append("</div></div>")
    by_n = {e["n"]: e for e in doc["exhibits"]}
    h.append(_table(by_n[1]))
    h.append(_foot())

    for b in doc["bagian"]:
        h.append(f"<div class='page'>{_topbar(m['tanggal'])}")
        h.append(f"<h2 class='sec'>{html.escape(b['judul'])}</h2>")
        h.append(_render_page_content(b))
        h.append(_foot() + "</div>")

    h.append(f"<div class='page'>{_topbar(m['tanggal'])}"
             "<h2 class='sec'>Pengungkapan</h2>"
             "<p class='small'>Laporan ini adalah alat informasi dan analisis, bukan "
             "rekomendasi, prediksi, atau saran investasi. Data bersumber dari Sectors "
             "(sectors.app) dan IDX; akurasi tunduk pada kualitas data sumber. Keputusan "
             "investasi sepenuhnya tanggung jawab pembaca. Performa masa lalu tidak "
             "menjamin hasil di masa depan.</p><h2 class='sec'>Catatan metodologi</h2><ul>")
    for c in doc["catatan_metodologi"]:
        h.append(f"<li class='small'>{html.escape(c)}</li>")
    h.append("</ul>" + _foot() + "</div></body></html>")
    return "\n".join(h)

