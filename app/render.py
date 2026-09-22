"""Renderer HTML tiru-layout contoh GMFI (8 halaman). Brand Sektoral, bukan BRIDS.

Struktur: header → rating → cover 2 kolom (data pasar + narasi) → Key
Financials → halaman 2-6 → metodologi + disclaimer. Chart SVG native dari
cache daily. Nomor halaman via CSS counter. Cetak via app/pdf.py (A4).
"""
import html
from . import cache as cache_mod

NAVY = "#1a2e4a"
ACCENT = "#b8860b"
PAPER = "#ffffff"
INK = "#1c1a17"
MUT = "#6b6455"

PAGE_NUM = ('@page{size:A4;margin:14mm 13mm 16mm}'
            '@page{@bottom-right{content:"Halaman " counter(page);'
            'font-family:system-ui;font-size:7.3pt;color:' + MUT + '}}')

CSS = (PAGE_NUM +
       "body{font-family:Georgia,serif;color:" + INK + ";background:" + PAPER +
       ";font-size:8.5pt;line-height:1.45;margin:0}"
       ".topbar{display:flex;justify-content:space-between;border-bottom:3px solid "
       + NAVY + ";padding-bottom:4px;font-family:system-ui;font-size:8.5pt;color:" + MUT + "}"
       ".rating{font-family:system-ui;font-weight:800;font-size:22pt;color:" + NAVY + ";margin:4px 0 0}"
       ".status{font-family:system-ui;font-size:9pt;color:" + MUT + "}"
       ".cover{display:flex;gap:10px;margin-top:4px}"
       ".left{width:31%;font-size:8.3pt;font-family:system-ui}"
       ".right{width:69%}"
       ".kv{display:flex;justify-content:space-between;padding:2.5px 0;border-bottom:1px dotted #ccc}"
       ".kv b{font-weight:700}.panel{background:#f4f1e8;padding:6px;border:1px solid #ddd}"
       "h1.emit{font-size:13.5pt;margin:2px 0;color:" + NAVY + "}"
       ".headline{font-size:11.5pt;font-weight:bold;margin:4px 0 6px}"
       ".bullets{margin:6px 0 6px 16px;padding:0}.bullets li{margin-bottom:4px}"
       "h2.sec{font-size:11.5pt;color:" + NAVY + ";border-bottom:2px solid " + ACCENT +
       ";padding-bottom:2px;margin:14px 0 6px}"
       "h3.sub{font-size:9.5pt;margin:6px 0 3px}"
       "table{border-collapse:collapse;width:100%;font-size:7.5pt;margin:5px 0;font-family:system-ui}"
       "th,td{border:1px solid #cfc9ba;padding:3px 5px;text-align:right;overflow-wrap:break-word}"
       "th:first-child,td:first-child{text-align:left}"
       "th{background:" + NAVY + ";color:#fff}"
       "caption{text-align:left;font-weight:bold;font-size:8.6pt;margin-bottom:2px;font-family:Georgia,serif}"
       ".src{font-size:7.3pt;color:" + MUT + ";margin:0 0 8px}"
       ".page{page-break-before:always}"
       ".foot{font-size:7.3pt;color:" + MUT + ";border-top:1px solid #ccc;margin-top:10px;"
       "padding-top:3px;display:flex;justify-content:space-between;font-family:system-ui}"
       ".small{font-size:7.8pt;color:" + MUT + "}")


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
    W, H, P = 220, 90, 6
    vs = [pts[d] for d in dates]
    lo, hi = min(vs), max(vs)
    span = (hi - lo) or 1
    xy = [(P + i * (W - 2 * P) / (len(vs) - 1), H - P - (v - lo) / span * (H - 2 * P))
          for i, v in enumerate(vs)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    return (f"<svg width='{W}' height='{H + 14}'><polyline points='{line}' "
            f"fill='none' stroke='{NAVY}' stroke-width='1.5'/>"
            f"<text x='{P}' y='{H + 11}' font-size='8' fill='{MUT}'>{dates[0]}</text>"
            f"<text x='{W - P - 52}' y='{H + 11}' font-size='8' fill='{MUT}'>{dates[-1]}</text>"
            f"<text x='{P}' y='10' font-size='8' fill='{MUT}'>{hi:,.0f}</text></svg>"
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
    for holder in (doc.get("holders") or [])[:2]:
        h.append(_kv(str(holder[0])[:22], str(holder[1])))
    h.append("</div>")
    f1 = doc.get("fy26") or {}
    if f1:
        h.append("<div class='panel' style='margin-top:6px'>"
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
        for p in b["paragraf"]:
            h.append(f"<p>{html.escape(p)}</p>")
        for e in b["exhibit"]:
            h.append(_table(e))
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
