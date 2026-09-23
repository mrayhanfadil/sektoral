"""Renderer HTML laporan multipage A4. Brand Sektoral, bukan BRIDS.

Struktur: header → rating → cover 2 kolom (data pasar + narasi) → Key
Financials → halaman 2-6 → metodologi + disclaimer. Chart SVG native dari
cache daily. Nomor halaman via CSS counter. Cetak via app/pdf.py (A4).
"""
import base64
import html
import re
from pathlib import Path
from . import cache as cache_mod
from . import fmt

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
            '@page{@bottom-left{content:"sektoral";'
            'font-family:\'Poppins\',sans-serif;font-size:7pt;color:' + MUT + '}'
            '@bottom-center{content:"Lihat pengungkapan penting di bagian akhir laporan ini";'
            'font-family:\'Poppins\',sans-serif;font-size:7pt;color:' + MUT + '}'
            '@bottom-right{content:"Halaman " counter(page);'
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
       ".exhibit{margin:7px 0 8px}"
       ".exhibit.keep{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:7.2pt;"
       "margin:0;font-family:'Poppins',sans-serif}"
       ".exhibit-table th,.exhibit-table td{border:1px solid #d8e2ed;padding:3px 5px;"
       "vertical-align:top;line-height:1.35;overflow-wrap:break-word;word-break:normal}"
       ".exhibit-table thead{display:table-header-group}"
       ".exhibit-table tbody{display:table-row-group}"
       ".exhibit-table tbody.block{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table tr{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table thead th{background:" + NAVY + ";color:#fff;font-weight:700;"
       "vertical-align:bottom}"
       ".exhibit-table .cell-text{text-align:left}"
       ".exhibit-table .cell-num{text-align:right;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-date{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-num.short{white-space:nowrap}"
       ".exhibit-table tbody tr:nth-child(even) td{background:#f8fafc}"
       ".exhibit-table tbody tr.section-row th{background:#e8f0fa;color:" + NAVY + ";"
       "text-align:left;font-weight:700;border-top:1.5px solid " + ROYAL_BLUE + ";"
       "padding:4px 5px;break-after:avoid-page}"
       ".exhibit-table tbody tr.total-row td{background:#eef4fb;font-weight:700;"
       "border-top:1px solid #9bb3d3}"
       ".exhibit-table caption{text-align:left;font-weight:700;font-size:7.8pt;"
       "color:" + NAVY + ";margin-bottom:3px;font-family:'Poppins',sans-serif}"
       ".src{font-size:6.7pt;color:" + MUT + ";margin:2px 0 6px;line-height:1.3}"
       ".page{page-break-before:always}"
       ".small{font-size:7.5pt;color:" + MUT + "}"
       ".grid-2{display:flex;gap:12px;width:100%;margin:4px 0;box-sizing:border-box}"
       ".grid-col{flex:1 1 0;min-width:0;box-sizing:border-box}"
       "@media screen{body{max-width:980px;margin:0 auto;padding:28px 34px;"
       "box-sizing:border-box;font-size:12px;line-height:1.5}"
       ".page{page-break-before:auto;border-top:1px solid #d8e2ed;margin-top:28px;padding-top:18px}"
       ".exhibit{overflow-x:auto}.exhibit-table{min-width:620px;font-size:11px}"
       ".exhibit-table th,.exhibit-table td{padding:6px 8px}"
       ".exhibit-table caption{font-size:12px;margin-bottom:5px}"
       ".src{font-size:10px;line-height:1.4}"
       ".grid-col .exhibit-table{min-width:0}}"
       "@media screen and (max-width:720px){body{padding:16px}"
       ".cover,.grid-2{flex-direction:column}.left,.right{width:100%}"
       ".exhibit-table,.grid-col .exhibit-table{min-width:680px}"
       ".exhibit-table th,.exhibit-table td{padding:5px 6px}"
       ".exhibit::before{content:'Geser tabel untuk kolom lainnya →';display:block;"
       "text-align:right;font-size:10px;color:" + MUT + ";margin-bottom:2px}}"
       "@media print{.exhibit{overflow:visible}.exhibit-table{min-width:0}"
       ".page{page-break-before:always}}")


def _price_chart(ticker):
    """SVG garis harga dari seluruh window daily cache (tanggal unik)."""
    pts = {}
    for _, p in cache_mod.payloads(f"/daily/{ticker}/"):
        for r in (p.get("data") or []):
            if r.get("date") and r.get("close"):
                pts[r["date"]] = float(r["close"])
    dates = sorted(pts)
    if len(dates) < 2:
        return "<p class='small'>[Grafik harga tidak tersedia — data harian kosong]</p>"
    W, H, P = 220, 85, 6
    vs = [pts[d] for d in dates]
    lo, hi = min(vs), max(vs)
    span = (hi - lo) or 1
    xy = [(P + i * (W - 2 * P) / (len(vs) - 1), H - P - (v - lo) / span * (H - 2 * P))
          for i, v in enumerate(vs)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    d0, d1 = dates[0][:7], dates[-1][:7]
    return (f"<svg width='{W}' height='{H + 14}'><polyline points='{line}' "
            f"fill='none' stroke='{ROYAL_BLUE}' stroke-width='1.5'/>"
            f"<text x='{P}' y='{H + 11}' font-size='8' font-family='Poppins, sans-serif' fill='{MUT}'>{d0}</text>"
            f"<text x='{W - P - 52}' y='{H + 11}' font-size='8' font-family='Poppins, sans-serif' fill='{MUT}'>{d1}</text>"
            f"<text x='{P}' y='10' font-size='8' font-family='Poppins, sans-serif' fill='{MUT}'>Rp{fmt.rp(round(hi))}</text></svg>"
            f"<p class='src'>Harga {html.escape(ticker)} {len(dates)} hari bursa terakhir "
            f"dari data lokal. Overlay IHSG absen (window indeks beda periode).</p>")


def _column_widths(cols):
    """Reserve room for descriptive fields and stable widths for figures."""
    labels = [str(col).strip().lower() for col in cols]
    if len(cols) == 2 and "terakhir" in labels[1]:
        return [31, 69]
    if len(cols) == 2:
        return [78, 22]
    if "dasar" in labels and len(cols) == 6:
        return [18, 10, 11, 11, 11, 39]
    if {"katalis", "waktu", "kenapa penting", "arah"}.issubset(labels):
        return [50, 13, 28, 9]
    return {3: [42, 29, 29], 4: [34, 22, 22, 22],
            5: [48, 12, 12, 12, 16],
            6: [34, 13.2, 13.2, 13.2, 13.2, 13.2]}.get(
                len(cols), [100 / len(cols)] * len(cols))


def _column_kinds(cols, rows):
    kinds = []
    for index, col in enumerate(cols):
        label = str(col).strip().lower()
        values = [str(row[index]).strip() for row in rows if index < len(row) and row[index] != ""]
        if index == 0 or label in {"dasar", "kenapa penting", "arah", "tahap"} or "terakhir" in label:
            kinds.append("text")
        elif label == "waktu" or (values and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in values)):
            kinds.append("date")
        elif values and sum(bool(re.match(r"^(?:Rp|USD\s*)?[\d(~−-]|^n\.a\.$", v))
                            for v in values) >= len(values) / 2:
            kinds.append("num")
        else:
            kinds.append("text")
    return kinds


def _table(ex):
    data = ex["data"]
    cols, rows = data["cols"], data["rows"]
    widths = _column_widths(cols)
    kinds = _column_kinds(cols, rows)
    colgroup = "".join(f"<col style='width:{width}%'>" for width in widths)
    head = "".join(f"<th scope='col' class='cell-{kind}'>{html.escape(str(col))}</th>"
                   for col, kind in zip(cols, kinds))
    groups = [[]]
    for row in rows:
        cells = [str(row[i]) if i < len(row) else "" for i in range(len(cols))]
        if cells[0].startswith("Blok ") and all(not cell for cell in cells[1:]):
            if groups[-1]:
                groups.append([])
            groups[-1].append("<tr class='section-row'>"
                              f"<th scope='rowgroup' colspan='{len(cols)}'>{html.escape(cells[0])}</th></tr>")
            continue
        total = bool(re.match(r"^(?:Jumlah |Total |\(=\) |FCFF$|PV FCFF$|Laba bersih$|TP final$|WACC$)",
                              cells[0], re.I))
        classes = " class='total-row'" if total else ""
        rendered = []
        for cell, kind in zip(cells, kinds):
            short = " short" if kind == "num" and len(cell) <= 13 and " " not in cell else ""
            rendered.append(f"<td class='cell-{kind}{short}'>{html.escape(cell)}</td>")
        groups[-1].append(f"<tr{classes}>" + "".join(rendered) + "</tr>")
    body = "".join(f"<tbody class='block'>{''.join(group)}</tbody>" for group in groups if group)
    keep = " keep" if len(rows) <= 14 else ""
    return (f"<div class='exhibit{keep}'><table class='exhibit-table'>"
            f"<caption>Exhibit {ex['n']}. {html.escape(ex['judul'])}</caption>"
            f"<colgroup>{colgroup}</colgroup><thead><tr>{head}</tr></thead>"
            f"{body}</table>"
            f"<p class='src'>{html.escape(ex['catatan_sumber'])}</p></div>")


def _kv(k, v):
    return f"<div class='kv'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>"


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
                       "</div>")
            for e in exs[2:]:
                res.append(_table(e))
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

    for b in doc["bagian"]:
        h.append(f"<div class='page'>{_topbar(m['tanggal'])}")
        h.append(f"<h2 class='sec'>{html.escape(b['judul'])}</h2>")
        h.append(_render_page_content(b))
        h.append("</div>")

    h.append(f"<div class='page'>{_topbar(m['tanggal'])}"
             "<h2 class='sec'>Pengungkapan</h2>"
             "<p class='small'>Laporan ini adalah alat informasi dan analisis, bukan "
             "rekomendasi, prediksi, atau saran investasi. Data bersumber dari Sectors "
             "(sectors.app) dan IDX; akurasi tunduk pada kualitas data sumber. Keputusan "
             "investasi sepenuhnya tanggung jawab pembaca. Performa masa lalu tidak "
             "menjamin hasil di masa depan.</p><h2 class='sec'>Catatan metodologi</h2><ul>")
    for c in doc["catatan_metodologi"]:
        h.append(f"<li class='small'>{html.escape(c)}</li>")
    h.append("</ul></div></body></html>")
    return "\n".join(h)
