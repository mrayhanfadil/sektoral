"""Renderer HTML laporan multipage A4. Brand Sektoral, bukan BRIDS.

Struktur: header → status → cover 2 kolom (data pasar + narasi) → Key
Financials → halaman 2-6 → metodologi + disclaimer. Chart SVG native dari
cache daily. Nomor halaman via CSS counter. Cetak via app/pdf.py (A4).
"""
import base64
import html
import math
import re
from datetime import date
from pathlib import Path
from . import cache as cache_mod

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


def _b64_font(filename):
    p = FONTS_DIR / filename
    return base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""


_ROB_REG = _b64_font("Roboto-Regular.ttf")
_ROB_BOLD = _b64_font("Roboto-Bold.ttf")
_ROB_ITA = _b64_font("Roboto-Italic.ttf")

# Sectoral branding spec: primary blue, white paper, near-black-ink text,
# light-gray rules, light-blue even rows, Roboto only.
PRIMARY = "#0928B1"
PAPER = "#ffffff"
INK = "#333333"
RULE = "#D9D9D9"
EVEN_ROW = "#B4C7FF"
MUT = "#555555"
# Categorical chart series, in order.
SERIES = ["#0928B1", "#B4C7FF", "#3ED628", "#1DCD9F", "#0047AB", "#7596FF"]
ISSUER_COLOR = SERIES[0]
INDEX_COLOR = SERIES[3]

# Use the canonical wordmark from sectors-hackathon/assets/brand/sectoral-logo.svg.
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "brand" / "sectoral-logo.svg"
LOGO_SVG = LOGO_PATH.read_text(encoding="utf-8")

PAGE_NUM = ('@page{size:A4;margin:12mm 12mm 14mm}'
            '@page{@bottom-left{content:"sektoral";'
            "font-family:'Roboto',sans-serif;font-size:7pt;color:" + MUT + '}'
            '@bottom-center{content:"Lihat pengungkapan penting di bagian akhir laporan ini";'
            "font-family:'Roboto',sans-serif;font-size:7pt;color:" + MUT + '}'
            '@bottom-right{content:"Halaman " counter(page);'
            "font-family:'Roboto',sans-serif;font-size:7.2pt;color:" + MUT + '}}')

FONT_FACES = (
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_REG}') format('truetype');font-weight:400;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_BOLD}') format('truetype');font-weight:700;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_BOLD}') format('truetype');font-weight:800;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_ITA}') format('truetype');font-weight:400;font-style:italic;}}\n"
)

CSS = (FONT_FACES + PAGE_NUM +
       "body{font-family:'Roboto',sans-serif;color:" + INK + ";background:" + PAPER +
       ";font-size:8.1pt;line-height:1.42;margin:0}"
       ".topbar{display:flex;justify-content:space-between;align-items:center;"
       "border-bottom:2px solid "
       + PRIMARY + ";padding-bottom:3px;font-size:8.1pt;color:" + PRIMARY + ";font-weight:600}"
       ".brandmark{vertical-align:-4px;margin-right:3px}"
       ".wordmark{display:flex;align-items:center}.wordmark svg{display:block;width:84px;height:18px}"
       ".status{font-size:8.5pt;color:" + MUT + ";margin-bottom:3px}"
       ".draft-banner{background:#fff3e8;border:1px solid #bb4d00;color:#803400;"
       "font-weight:700;padding:5px 8px;margin:5px 0;font-size:8.5pt}"
       ".cover{display:flex;gap:12px;margin-top:3px}"
       ".left{width:32%;font-size:7.8pt}"
       ".right{width:68%}"
       ".kv{display:flex;justify-content:space-between;align-items:baseline;padding:2px 0;border-bottom:1px dotted " + RULE + "}"
       ".kv span{padding-right:4px}.kv b{font-weight:700;color:" + INK + ";white-space:nowrap}"
       ".panel{background:" + PAPER + ";padding:5px 6px;border:1px solid " + RULE + ";border-radius:2px}"
       "h1.emit{font-size:12.8pt;margin:0 0 2px;color:" + PRIMARY + ";font-weight:700}"
       ".headline{font-size:10.8pt;font-weight:700;color:" + PRIMARY + ";margin:2px 0 4px}"
       ".bullets{margin:4px 0 6px 14px;padding:0;font-size:7.9pt}.bullets li{margin-bottom:3px}"
       "h2.sec{font-size:11pt;color:" + PRIMARY + ";font-weight:700;margin:10px 0 5px}"
       "h3.sub{font-size:8.8pt;color:" + PRIMARY + ";font-weight:700;margin:5px 0 2px}"
       ".exhibit{margin:7px 0 8px}"
       ".exhibit.keep{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:7.2pt;"
       "margin:0;font-family:'Roboto',sans-serif}"
       ".exhibit-table th,.exhibit-table td{border:1px solid " + RULE + ";padding:3px 5px;"
       "vertical-align:top;line-height:1.35;overflow-wrap:break-word;word-break:normal}"
       ".exhibit-table thead{display:table-header-group}"
       ".exhibit-table tbody{display:table-row-group}"
       ".exhibit-table tbody.block{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table tr{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table thead th{background:" + PRIMARY + ";color:#fff;font-weight:700;"
       "vertical-align:bottom}"
       ".exhibit-table .cell-text{text-align:left}"
       ".exhibit-table .cell-num{text-align:right;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-date{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-num.short{white-space:nowrap}"
       ".exhibit-table tbody tr:nth-child(even) td{background:" + EVEN_ROW + "}"
       ".exhibit-table tbody tr.section-row th{background:" + EVEN_ROW + ";color:" + PRIMARY + ";"
       "text-align:left;font-weight:700;border-top:1.5px solid " + PRIMARY + ";"
       "padding:4px 5px;break-after:avoid-page}"
       ".exhibit-table tbody tr.total-row td{background:" + PAPER + ";font-weight:700;"
       "border-top:1px solid " + RULE + "}"
       ".exhibit-table caption{text-align:left;font-weight:700;font-size:7.8pt;"
       "color:" + PRIMARY + ";margin-bottom:3px;font-family:'Roboto',sans-serif}"
       ".src{font-size:6.7pt;color:" + MUT + ";margin:2px 0 6px;line-height:1.3}"
       ".research-card{border:1px solid " + RULE + ";"
       "padding:7px 9px;margin:9px 0;break-inside:avoid-page;page-break-inside:avoid}"
       ".research-card h3{color:" + PRIMARY + ";font-size:9pt;margin:0 0 4px}"
       ".research-card p{margin:3px 0;line-height:1.42}"
       ".research-card .research-cite{font-size:6.7pt;color:" + MUT + ";"
       "margin-top:6px;overflow-wrap:anywhere}"
       ".page{page-break-before:always}"
       ".small{font-size:7.5pt;color:" + MUT + "}"
       ".grid-2{display:flex;gap:12px;width:100%;margin:4px 0;box-sizing:border-box}"
       ".grid-col{flex:1 1 0;min-width:0;box-sizing:border-box}"
       "@media screen{body{max-width:980px;margin:0 auto;padding:28px 34px;"
       "box-sizing:border-box;font-size:12px;line-height:1.5}"
       ".page{page-break-before:auto;border-top:1px solid " + RULE + ";margin-top:28px;padding-top:18px}"
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
       "@media print{body,body *{font-family:'Roboto',sans-serif!important;"
       "font-variant-ligatures:none;font-feature-settings:'liga' 0,'clig' 0}"
       "@media print{h1,h2,h3{font-weight:400!important}"
       ".exhibit{overflow:visible}.exhibit-table{min-width:0}"
       ".research-summary{display:none!important}"
       ".page{page-break-before:always}}")


def _daily_prices(endpoint, value_field, as_of):
    """Read dated positive prices; later cache snapshots replace older rows."""
    cutoff = date.fromisoformat(str(as_of)[:10]) if as_of else None
    prices = {}
    for _, payload in cache_mod.payloads(endpoint):
        for row in payload.get("data") or []:
            if not isinstance(row, dict):
                continue
            try:
                day = date.fromisoformat(str(row["date"])[:10])
                value = float(row[value_field])
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if value > 0 and math.isfinite(value) and (cutoff is None or day <= cutoff):
                prices[day] = value
    return prices


def _comparison_series(ticker, as_of):
    """Align issuer and IHSG on common dates and rebase both to 100."""
    issuer = _daily_prices(f"/daily/{ticker}/", "close", as_of)
    ihsg = _daily_prices("/index-daily/ihsg/", "price", as_of)
    dates = sorted(issuer.keys() & ihsg.keys())
    if len(dates) < 2:
        return None
    issuer_base, ihsg_base = issuer[dates[0]], ihsg[dates[0]]
    return (dates,
            [100 * issuer[day] / issuer_base for day in dates],
            [100 * ihsg[day] / ihsg_base for day in dates])


def _price_chart(ticker, as_of):
    """Plot issuer and IHSG price performance on identical trading dates."""
    series = _comparison_series(ticker, as_of)
    if series is None:
        return ("<p class='small'>Perbandingan harga belum tersedia: "
                "kurang dari dua tanggal perdagangan yang sama di cache.</p>")

    dates, issuer, ihsg = series
    all_values = issuer + ihsg
    padding = max(4, (max(all_values) - min(all_values)) * 0.08)
    lower = 10 * math.floor((min(all_values) - padding) / 10)
    upper = 10 * math.ceil((max(all_values) + padding) / 10)
    if upper <= lower:
        upper = lower + 10
    x0, x1, y0, y1 = 32, 232, 17, 91
    days = (dates[-1] - dates[0]).days

    def xy(day, value):
        x = x0 + (day - dates[0]).days / days * (x1 - x0)
        y = y1 - (value - lower) / (upper - lower) * (y1 - y0)
        return x, y

    def polyline(values, color, dash=""):
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                          (xy(day, value) for day, value in zip(dates, values)))
        dashed = f" stroke-dasharray='{dash}'" if dash else ""
        end_x, end_y = xy(dates[-1], values[-1])
        return (f"<polyline points='{points}' fill='none' stroke='{color}' "
                f"stroke-width='2' stroke-linecap='round' stroke-linejoin='round'{dashed}/>"
                f"<circle cx='{end_x:.1f}' cy='{end_y:.1f}' r='2.4' fill='{color}'/>")

    ticks = {lower, 100, upper}
    if 100 - lower >= 40:
        ticks.add(10 * round((lower + 100) / 20))
    if upper - 100 >= 40:
        ticks.add(10 * round((upper + 100) / 20))
    ticks = sorted(ticks)
    grid = "".join(
        f"<line x1='{x0}' x2='{x1}' y1='{xy(dates[0], tick)[1]:.1f}' "
        f"y2='{xy(dates[0], tick)[1]:.1f}' stroke='{'#000000' if tick == 100 else '#E6E6E6'}' "
        f"stroke-width='{'1.2' if tick == 100 else '0.5'}'/>"
        f"<text x='26' y='{xy(dates[0], tick)[1] + 2.5:.1f}' text-anchor='end' "
        f"font-size='7.5' fill='{MUT}'>{tick}</text>"
        for tick in ticks if lower <= tick <= upper)

    issuer_return = issuer[-1] - 100
    ihsg_return = ihsg[-1] - 100
    spread = issuer_return - ihsg_return

    def pct(value):
        return f"{value:+.1f}".replace(".", ",")

    safe_ticker = html.escape(ticker)
    return (
        "<svg class='price-chart' viewBox='0 0 240 145' width='240' height='145' "
        "style='display:block;width:100%;height:auto' role='img' aria-labelledby='price-chart-title'>"
        f"<title id='price-chart-title'>Kinerja harga {safe_ticker} dan IHSG, "
        f"{dates[0].isoformat()} sampai {dates[-1].isoformat()}, awal 100</title>"
        f"{grid}{polyline(ihsg, INDEX_COLOR, '4 3')}{polyline(issuer, ISSUER_COLOR)}"
        f"<text x='{x0}' y='105' font-size='7.5' fill='{MUT}'>{dates[0]:%Y-%m}</text>"
        f"<text x='{x1}' y='105' text-anchor='end' font-size='7.5' fill='{MUT}'>{dates[-1]:%Y-%m}</text>"
        f"<line x1='32' x2='44' y1='120' y2='120' stroke='{ISSUER_COLOR}' stroke-width='2'/>"
        f"<text x='48' y='123' font-size='8' fill='{INK}'>{safe_ticker} {pct(issuer_return)}%</text>"
        f"<line x1='135' x2='147' y1='120' y2='120' stroke='{INDEX_COLOR}' stroke-width='2' stroke-dasharray='4 3'/>"
        f"<text x='151' y='123' font-size='8' fill='{INK}'>IHSG {pct(ihsg_return)}%</text>"
        f"<text x='32' y='140' font-size='7.8' fill='{MUT}'>Selisih {pct(spread)} poin persentase</text>"
        "</svg>"
        f"<p class='src'>Sumber: Sectors cache; {len(dates)} tanggal sama "
        f"({dates[0].isoformat()}–{dates[-1].isoformat()}). "
        "Kinerja harga, awal = 100; tidak termasuk dividen.</p>")


def _column_widths(cols):
    """Reserve room for descriptive fields and stable widths for figures."""
    labels = [str(col).strip().lower() for col in cols]
    if len(cols) == 2 and "terakhir" in labels[1]:
        return [31, 69]
    if len(cols) == 2 and labels[0] == "pemeriksaan" and labels[1] == "yang masih diperlukan":
        return [35, 65]
    if len(cols) == 2 and labels[0] == "input" and labels[1] == "kekurangan":
        return [30, 70]
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
        total = bool(re.match(r"^(?:Jumlah |Total |\(=\) |FCFF$|PV FCFF$|Laba bersih$|Nilai skenario gabungan$|WACC$)",
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
            f"{html.escape(str(date))}</span><span class='wordmark' "
            f"aria-label='Sectoral'>{LOGO_SVG}</span></div>")


def _draft_banner(meta):
    if meta.get("status") != "draft_non_distributable":
        return ""
    return ("<div class='draft-banner'>DRAFT: BUKTI BELUM LENGKAP — "
            "skenario nilai belum disajikan sampai data dan model tervalidasi.</div>")


def _render_page_content(b):
    halaman = b.get("halaman")
    exs = b.get("exhibit") or []
    paras = b.get("paragraf") or []

    res = []
    if b.get("layout") == "research_cards":
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        for card in b.get("research_cards") or []:
            refs = "; ".join(card.get("citations") or [])
            res.append("<article class='research-card'>"
                       f"<h3>{html.escape(card['title'])}</h3>"
                       f"<p><b>Observasi.</b> {html.escape(card['observation'])}</p>"
                       f"<p><b>Kaitan.</b> {html.escape(card['implication'])}</p>"
                       f"<p><b>Batasan.</b> {html.escape(card['caveat'])}</p>"
                       f"<p class='research-cite'><b>Rujukan cache:</b> {html.escape(refs)}</p>"
                       "</article>")

    elif b.get("layout") == "stack":
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        for e in exs:
            res.append(_table(e))

    elif halaman == 2:
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
    h = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
    h.append(_topbar(m["tanggal"]))
    h.append(_draft_banner(m))
    report_status = "DRAFT: BUKTI BELUM LENGKAP" if m.get("status") == "draft_non_distributable" else "Analisis skenario informasional"
    h.append(f"<div class='status'>{html.escape(report_status)}</div>")
    h.append("<div class='cover'><div class='left'>")
    h.append(f"<div class='small'>Valuasi: {html.escape(doc.get('method', 'DCF'))}</div>"
             "<div class='panel'>")
    h.append(_kv("Harga Terakhir (Rp)", f"{m['harga']:,.0f}"))
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
    h.append(f"<h3 class='sub'>{html.escape(m['ticker'])} vs IHSG (awal = 100)</h3>")
    h.append(_price_chart(m["ticker"], m["tanggal"]))
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
        page_class = "page research-summary" if b.get("layout") == "research_cards" else "page"
        h.append(f"<div class='{page_class}'>{_topbar(m['tanggal'])}")
        h.append(_draft_banner(m))
        h.append(f"<h2 class='sec'>{html.escape(b['judul'])}</h2>")
        h.append(_render_page_content(b))
        h.append("</div>")

    h.append(f"<div class='page'>{_topbar(m['tanggal'])}"
             f"{_draft_banner(m)}"
             "<h2 class='sec'>Pengungkapan</h2>"
             "<p class='small'>Laporan ini adalah alat informasi dan analisis, bukan "
             "rekomendasi, prediksi, atau saran investasi. Input laporan berasal dari "
             "sectors cache (sectors.app); akurasi tunduk pada kualitas data sumber. Keputusan "
             "investasi sepenuhnya tanggung jawab pembaca. Performa masa lalu tidak "
             "menjamin hasil di masa depan.</p><h2 class='sec'>Catatan metodologi</h2><ul>")
    for c in doc["catatan_metodologi"]:
        h.append(f"<li class='small'>{html.escape(c)}</li>")
    h.append("</ul></div></body></html>")
    return "\n".join(h)
