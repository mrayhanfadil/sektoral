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
from . import fmt

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
BRAND_DIR = Path(__file__).resolve().parent / "assets" / "brand"


def _b64_font(filename):
    p = FONTS_DIR / filename
    return base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""


def _b64_brand_asset(filename):
    p = BRAND_DIR / filename
    return base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""


_ROB_REG = _b64_font("Roboto-Regular.ttf")
_ROB_BOLD = _b64_font("Roboto-Bold.ttf")
_ROB_ITA = _b64_font("Roboto-Italic.ttf")
_ROB_MED = _b64_font("Roboto-Medium.ttf")
_ROB_BOLD_ITA = _b64_font("Roboto-BoldItalic.ttf")
_ROB_BLACK = _b64_font("Roboto-Black.ttf")
_ROB_BLACK_ITA = _b64_font("Roboto-BlackItalic.ttf")

# Sectoral Design System (docs: "Sectoral Design System Documentation").
# Roboto only, on screen and in print: the static Google Fonts v51 faces keep
# copied PDF words intact (the old variable build did not, which is why print
# used to fall back to Arial / Liberation Sans). Sizes are the design's
# artboard points scaled x0.5 to A4.
PRIMARY = "#0928B1"
PAPER = "#ffffff"
INK = "#000000"
RULE = "#E0E0E0"
EVEN_ROW = "#B4C7FF"
HIGHLIGHT = "#E1E9FF"
LIME = "#3ED628"
MUT = "#555555"
GRID = "#E0E0E0"
# Categorical chart series, in order.
SERIES = ["#0928B1", "#B4C7FF", "#3ED628", "#1DCD9F", "#0047AB", "#7596FF"]
ISSUER_COLOR = SERIES[0]
INDEX_COLOR = SERIES[3]

# Use the canonical wordmark from sectors-hackathon/assets/brand/sectoral-logo.svg.
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "brand" / "sectoral-logo.svg"
LOGO_SVG = LOGO_PATH.read_text(encoding="utf-8")
REPORT_WORDMARK = _b64_brand_asset("report-wordmark.png")
REPORT_DIVIDER = _b64_brand_asset("report-divider.svg")
REPORT_MORSE = _b64_brand_asset("report-morse.svg")

PAGE_NUM = ("@page{size:A4;margin:12mm 12mm 14mm;"
            "@bottom-left{content:'See important disclosure at the back of this report';"
            "box-sizing:border-box;width:160mm;height:3mm;padding-left:97mm;"
            "background-image:url('data:image/svg+xml;base64," + REPORT_MORSE + "');"
            "background-size:95mm 1.55mm;background-position:left center;"
            "background-repeat:no-repeat;white-space:nowrap;"
            "font-family:'Roboto',sans-serif;font-size:7.5pt;line-height:3mm;"
            "color:" + PRIMARY + "}"
            "@bottom-right{content:'Page ' counter(page) ' of ' counter(pages);font-weight:900;"
            "box-sizing:border-box;width:26mm;height:3mm;text-align:right;white-space:nowrap;"
            "font-family:'Roboto',sans-serif;font-size:7.5pt;line-height:3mm;"
            "color:" + PRIMARY + "}}")

FONT_FACES = (
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_REG}') format('truetype');font-weight:400;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_ITA}') format('truetype');font-weight:400;font-style:italic;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_MED}') format('truetype');font-weight:500;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_BOLD}') format('truetype');font-weight:700;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_BOLD_ITA}') format('truetype');font-weight:700;font-style:italic;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_BLACK}') format('truetype');font-weight:900;font-style:normal;}}\n"
    f"@font-face{{font-family:'Roboto';src:url('data:font/truetype;charset=utf-8;base64,{_ROB_BLACK_ITA}') format('truetype');font-weight:900;font-style:italic;}}\n"
)

CSS = (FONT_FACES + PAGE_NUM +
       "body{font-family:'Roboto',sans-serif;color:" + INK + ";background:" + PAPER +
       ";font-size:8.1pt;line-height:1.42;margin:0}"
       ".topbar{display:flex;justify-content:space-between;align-items:center;"
       "border-bottom:2px solid "
       + PRIMARY + ";padding-bottom:3px;font-size:8.1pt;color:" + PRIMARY + ";font-weight:600}"
       ".brandmark{vertical-align:-4px;margin-right:3px}"
       ".wordmark{display:flex;align-items:center}.wordmark svg{display:block;width:84px;height:18px}"
       ".report-header{display:grid;grid-template-columns:minmax(0,1fr) 30mm;"
       "grid-template-rows:auto 0.5mm;column-gap:5mm;row-gap:0.4mm;"
       "align-items:center;padding:3mm 3mm 2.5mm;margin:0 0 2mm}"
       ".report-heading{grid-column:1;grid-row:1;min-width:0}"
       # Header line 1: stock code + rating action (Roboto Black, blue);
       # line 2: report type + date (Roboto Regular, black).
       ".report-title{font-size:10pt;line-height:1.15;color:" + PRIMARY + ";"
       "font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
       ".report-subtitle{font-size:8pt;line-height:1.2;color:" + INK + ";margin-top:0.5mm}"
       ".report-wordmark{grid-column:2;grid-row:1;display:block;width:30mm;height:5.35mm;"
       "object-fit:contain}"
       ".report-divider{grid-column:1/-1;grid-row:2;display:block;width:100%;"
       "height:0.5mm;object-fit:fill}"
       ".status{font-size:10.5pt;color:" + PRIMARY + ";font-weight:700;margin:5px 0 2px}"
       # Rating block: Roboto Black Italic on the highlight fill.
       ".rating-block{background:" + HIGHLIGHT + ";padding:4mm 4mm 3.5mm;margin:0 0 3mm}"
       ".rating-label{font-size:32pt;color:" + PRIMARY + ";font-weight:900;font-style:italic;"
       "line-height:0.95;text-transform:uppercase;letter-spacing:-0.01em}"
       ".rating-detail{font-size:10pt;color:" + PRIMARY + ";font-weight:900;font-style:italic;"
       "margin-top:1.2mm}"
       ".rating-method{font-size:7pt;color:" + INK + ";margin-top:2mm;padding-top:1.5mm;"
       "border-top:1px solid #FFFFFF;line-height:1.3}"
       ".basic-head{font-size:10pt;font-weight:700;color:" + INK + ";margin:3.5mm 0 1mm}"
       ".draft-banner{background:#fff3e8;border:1px solid #bb4d00;color:#803400;"
       "font-weight:700;padding:5px 8px;margin:5px 0;font-size:8.5pt}"
       ".cover{display:flex;gap:12px;margin-top:3px}"
       ".left{width:31%;font-size:8pt}"
       ".right{width:68%}"
       ".kv{display:flex;justify-content:space-between;align-items:baseline;padding:2.2px 0;"
       "border-bottom:1px solid " + HIGHLIGHT + "}"
       ".kv span{padding-right:4px}.kv b{font-weight:500;color:" + INK + ";white-space:nowrap}"
       ".panel{background:" + PAPER + ";padding:0}"
       # Company name (Roboto Black) and thesis line (Roboto Black Italic).
       "h1.emit{font-size:20pt;line-height:1.08;margin:0 0 2mm;color:" + INK + ";font-weight:900}"
       ".headline{font-size:14pt;line-height:1.12;font-weight:900;font-style:italic;color:" + INK +
       ";margin:0 0 3mm}"
       # Highlight callout for the three executive-summary bullets.
       ".highlight{background:" + HIGHLIGHT + ";padding:2.5mm 3.5mm;margin:0 0 3mm}"
       ".bullets{margin:0 0 0 12px;padding:0;font-size:8pt}"
       ".bullets li{margin-bottom:1.6mm;font-weight:500}.bullets li:last-child{margin-bottom:0}"
       # Numbered section heads on inner pages (Roboto Black, black).
       "h2.sec{font-size:18pt;line-height:1.1;color:" + INK + ";font-weight:900;margin:3mm 0 3mm}"
       "h2.sec .num{color:" + PRIMARY + "}"
       "h3.sub{font-size:10pt;color:" + INK + ";font-weight:700;margin:2.5mm 0 1mm}"
       # Thesis cards: claim on the left, the metric that backs it on the right.
       ".cards{display:flex;flex-direction:column;gap:2.5mm;margin:2mm 0}"
       ".card{display:flex;gap:4mm;align-items:center;background:" + HIGHLIGHT + ";"
       "padding:3mm 4mm;break-inside:avoid-page;page-break-inside:avoid}"
       ".card-body{flex:1 1 auto;min-width:0}"
       ".card-title{font-weight:900;font-size:10pt;margin-bottom:1mm;color:" + INK + "}"
       ".card-text{font-size:8pt;line-height:1.4}"
       ".card-metric{flex:0 0 32mm;text-align:right}"
       ".card-value{font-size:20pt;font-weight:900;color:" + PRIMARY + ";line-height:1}"
       ".card-label{font-size:7pt;color:" + INK + ";margin-top:1mm;line-height:1.25}"
       ".exhibit{margin:7px 0 8px}"
       ".exhibit.keep{break-inside:avoid-page;page-break-inside:avoid}"
       # Table styling follows sectors-hackathon's .fin-table: a solid header
       # band, horizontal hairlines only (no vertical grid), spec zebra fill
       # and a ruled total line. The old full grid made every figure read as a
       # spreadsheet cell instead of a column.
       ".exhibit-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:7.2pt;"
       "margin:0;font-family:'Roboto',sans-serif;border:1px solid " + RULE + "}"
       ".exhibit-table th,.exhibit-table td{border:0;padding:3.4px 6px;"
       "vertical-align:top;line-height:1.35;overflow-wrap:break-word;word-break:normal}"
       ".exhibit-table tbody td{border-top:1px solid " + RULE + "}"
       ".exhibit-table tbody.block:first-of-type tr:first-child td{border-top:0}"
       ".exhibit-table thead{display:table-header-group}"
       ".exhibit-table tbody{display:table-row-group}"
       ".exhibit-table tbody.block{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table tr{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table thead th{background:" + PRIMARY + ";color:#fff;font-weight:900;"
       "letter-spacing:.02em;white-space:nowrap;padding:4px 6px;vertical-align:bottom}"
       ".exhibit-table .cell-text{text-align:left}"
       ".exhibit-table .cell-num{text-align:right;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-date{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-num.short{white-space:nowrap}"
       ".exhibit-table tbody tr:nth-child(even) td{background:" + EVEN_ROW + "}"
       ".exhibit-table tbody tr.section-row th{background:" + EVEN_ROW + ";color:" + PRIMARY + ";"
       "text-align:left;font-weight:700;letter-spacing:.04em;"
       "border-top:1px solid " + PRIMARY + ";"
       "padding:4px 6px;break-after:avoid-page}"
       ".exhibit-table tbody.block:first-of-type tr.section-row:first-child th{border-top:0}"
       ".exhibit-table tbody tr.total-row td{background:" + PAPER + ";font-weight:700;"
       "border-top:1px solid " + PRIMARY + "}"
       # Exhibit label carries the same brand tick as the section heads.
       ".exhibit-table caption{text-align:left;font-weight:900;font-size:8pt;"
       "color:" + PRIMARY + ";margin-bottom:3px;font-family:'Roboto',sans-serif}"
       ".exhibit-table caption::before{content:'';display:block;width:26pt;"
       "border-top:1.5px solid " + PRIMARY + ";margin-bottom:2.5px}"
       ".src{font-size:6pt;color:" + INK + ";margin:2px 0 6px;line-height:1.3}"
       ".metric-chart{display:block;width:100%;height:180px}"
       ".chart-caption{font-weight:900;font-size:8pt;color:" + PRIMARY + ";margin-bottom:2mm}"
       ".chart-caption::before{content:'';display:block;width:26pt;"
       "border-top:1.5px solid " + PRIMARY + ";margin-bottom:2.5px}"
       ".research-card{border:1px solid " + RULE + ";"
       "padding:7px 9px;margin:9px 0;break-inside:avoid-page;page-break-inside:avoid}"
       ".research-card h3{color:" + PRIMARY + ";font-size:9pt;margin:0 0 4px}"
       ".research-card p{margin:3px 0;line-height:1.42}"
       ".research-card .research-cite{font-size:6.7pt;color:" + MUT + ";"
       "margin-top:6px;overflow-wrap:anywhere}"
       ".page{page-break-before:always}"
       ".analyst{font-size:8pt;margin-top:3mm;line-height:1.35}"
       ".section{margin-top:6mm}.section>.report-header{display:none}"
       "h2.sec{break-after:avoid-page;page-break-after:avoid}"
       ".small{font-size:7.5pt;color:" + MUT + "}"
       ".grid-2{display:flex;gap:12px;width:100%;margin:4px 0;box-sizing:border-box}"
       ".grid-col{flex:1 1 0;min-width:0;box-sizing:border-box}"
       "@media screen{body{max-width:980px;margin:0 auto;padding:28px 34px;"
       "box-sizing:border-box;font-size:12px;line-height:1.5}"
       ".page{page-break-before:auto;border-top:1px solid " + RULE + ";margin-top:28px;padding-top:18px}"
       ".exhibit{overflow-x:auto}.exhibit-table{min-width:620px;font-size:11px}"
       ".exhibit-table th,.exhibit-table td{padding:7px 10px}"
       ".exhibit-table thead th{padding:8px 10px;font-size:10px}"
       ".exhibit-table caption{font-size:12px;margin-bottom:5px}"
       ".src{font-size:10px;line-height:1.4}"
       ".grid-col .exhibit-table{min-width:0}}"
       "@media screen and (max-width:720px){body{padding:16px}"
       ".cover,.grid-2{flex-direction:column}.left,.right{width:100%}"
       ".exhibit-table,.grid-col .exhibit-table{min-width:680px}"
       ".exhibit-table th,.exhibit-table td{padding:5px 6px}"
       ".exhibit::before{content:'Geser tabel untuk kolom lainnya →';display:block;"
       "text-align:right;font-size:10px;color:" + MUT + ";margin-bottom:2px}}"
       # Print keeps Roboto; ligatures stay off so copied words never merge.
       "@media print{body,body *{font-variant-ligatures:none;"
       "font-feature-settings:'liga' 0,'clig' 0}"
       "@media print{"
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
    """Align issuer and IHSG on common dates and rebase both to 100.

    Raw closes come back with the rebased pair: the chart plots price on the
    left axis and the issuer-minus-IHSG spread on the right.
    """
    issuer = _daily_prices(f"/daily/{ticker}/", "close", as_of)
    ihsg = _daily_prices("/index-daily/ihsg/", "price", as_of)
    dates = sorted(issuer.keys() & ihsg.keys())
    if len(dates) < 2:
        return None
    issuer_base, ihsg_base = issuer[dates[0]], ihsg[dates[0]]
    return (dates,
            [issuer[day] for day in dates],
            [100 * issuer[day] / issuer_base for day in dates],
            [100 * ihsg[day] / ihsg_base for day in dates])


# Round tick steps per axis, so the four gridlines land on figures a reader can
# hold in their head instead of on thirds of the raw range.
PRICE_STEPS = (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500,
               5000, 10000, 20000, 25000, 50000)
REL_STEPS = (1, 2, 5, 10, 20, 25, 50, 100, 200, 500)


def _axis_scale(values, steps):
    """Snap a series range to three intervals of a round step."""
    low, high = min(values), max(values)
    if high <= low:
        high = low + 1
    head = (high - low) * 0.07
    low, high = low - head, high + head
    span = high - low
    step = next((c for c in steps if span / c <= 3.0), span / 3)
    base = math.floor(low / step) * step
    if base + 3 * step < high:
        base = math.ceil(high / step) * step - 3 * step
    return base, base + 3 * step


def _price_chart(ticker, as_of):
    """Close on the left axis, performance vs IHSG on the right.

    Adapted from sectors-hackathon's svg_price_vs_jci. The two scales are
    deliberate: the relative line is read against its own zero line (above it
    the issuer beat the index), a reading a shared rebased scale flattens.
    """
    series = _comparison_series(ticker, as_of)
    if series is None:
        return ("<p class='small'>Perbandingan harga belum tersedia: "
                "kurang dari dua tanggal perdagangan yang sama di data Sectors.</p>")

    dates, closes, issuer, ihsg = series
    relative = [a - b for a, b in zip(issuer, ihsg)]
    p_lo, p_hi = _axis_scale(closes, PRICE_STEPS)
    r_lo, r_hi = _axis_scale(relative, REL_STEPS)
    x0, x1, y0, y1 = 30, 212, 15, 101
    days = (dates[-1] - dates[0]).days or 1

    def x_of(day):
        return x0 + (day - dates[0]).days / days * (x1 - x0)

    def y_of(value, lo, hi):
        return y1 - (value - lo) / (hi - lo) * (y1 - y0)

    def points(values, lo, hi):
        return " ".join(f"{x_of(day):.1f},{y_of(value, lo, hi):.1f}"
                        for day, value in zip(dates, values))

    def line(values, lo, hi, color, dash=""):
        dashed = f" stroke-dasharray='{dash}'" if dash else ""
        return (f"<polyline points='{points(values, lo, hi)}' fill='none' stroke='{color}' "
                f"stroke-width='2' stroke-linecap='round' stroke-linejoin='round'{dashed}/>"
                f"<circle cx='{x_of(dates[-1]):.1f}' cy='{y_of(values[-1], lo, hi):.1f}' "
                f"r='2.4' fill='{color}'/>")

    # Four gridlines, price labelled left and relative performance right.
    # Design chart rules: no axis lines or frame, dashed light-gray grid,
    # black baseline, black tick labels.
    grid = []
    for i in range(4):
        y = y0 + i * (y1 - y0) / 3
        price_tick = p_hi - i * (p_hi - p_lo) / 3
        rel_tick = r_hi - i * (r_hi - r_lo) / 3
        grid.append(
            f"<line x1='{x0}' x2='{x1}' y1='{y:.1f}' y2='{y:.1f}' "
            f"stroke='{GRID}' stroke-width='0.6' stroke-dasharray='3 3'/>"
            f"<text x='{x0 - 3}' y='{y + 2.5:.1f}' text-anchor='end' font-size='7' "
            f"fill='{INK}'>{fmt.rp(price_tick)}</text>"
            f"<text x='{x1 + 3}' y='{y + 2.5:.1f}' font-size='7' "
            f"fill='{INK}'>{rel_tick:+.0f}%</text>")
    # Parity: above this line the issuer outperformed the index.
    if r_lo <= 0 <= r_hi:
        zero_y = y_of(0, r_lo, r_hi)
        grid.append(f"<line x1='{x0}' x2='{x1}' y1='{zero_y:.1f}' y2='{zero_y:.1f}' "
                    f"stroke='#000000' stroke-width='1.2'/>")

    area = (f"<polygon points='{x0},{y1} {points(closes, p_lo, p_hi)} {x1},{y1}' "
            f"fill='{ISSUER_COLOR}' fill-opacity='0.12'/>")

    issuer_return = issuer[-1] - 100
    ihsg_return = ihsg[-1] - 100
    spread = issuer_return - ihsg_return

    def pct(value):
        return f"{value:+.1f}".replace(".", ",")

    safe_ticker = html.escape(ticker)
    return (
        "<svg class='price-chart' viewBox='0 0 240 152' width='240' height='152' "
        "style='display:block;width:100%;height:auto' role='img' aria-labelledby='price-chart-title'>"
        f"<title id='price-chart-title'>Harga penutupan {safe_ticker} dan kinerja "
        f"relatif terhadap IHSG, {dates[0].isoformat()} sampai {dates[-1].isoformat()}</title>"
        f"{''.join(grid)}{area}"
        f"{line(relative, r_lo, r_hi, INDEX_COLOR, '4 3')}"
        f"{line(closes, p_lo, p_hi, ISSUER_COLOR)}"
        f"<text x='{x0}' y='112' font-size='7.5' fill='{INK}'>{dates[0]:%b-%y}</text>"
        f"<text x='{x1}' y='112' text-anchor='end' font-size='7.5' fill='{INK}'>{dates[-1]:%b-%y}</text>"
        f"<rect x='{x0}' y='120' width='8' height='8' fill='{ISSUER_COLOR}'/>"
        f"<text x='{x0 + 16}' y='127' font-size='7.5' fill='{INK}'>{safe_ticker} "
        f"{pct(issuer_return)}% - harga Rp, sumbu kiri</text>"
        f"<rect x='{x0}' y='132' width='8' height='8' fill='{INDEX_COLOR}'/>"
        f"<text x='{x0 + 16}' y='139' font-size='7.5' fill='{INK}'>Relatif vs IHSG "
        f"{pct(spread)} pp - sumbu kanan</text>"
        f"<text x='{x0}' y='149' font-size='7' fill='{MUT}'>IHSG {pct(ihsg_return)}%. "
        f"Selisih {pct(spread)} poin persentase</text>"
        "</svg>"
        f"<p class='src'>Sumber: Sectors; {len(dates)} tanggal sama "
        f"({dates[0].isoformat()} - {dates[-1].isoformat()}). "
        "Sumbu kiri harga penutupan (Rp); sumbu kanan kinerja relatif terhadap "
        "IHSG dalam poin persentase, awal = 0; tidak termasuk dividen.</p>")


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
    if "dasar" in labels and len(cols) >= 6:
        driver_w = 18
        dasar_w = 34
        satuan_w = 8
        remaining = 100 - driver_w - dasar_w - satuan_w
        n_years = len(cols) - 3
        year_w = remaining / n_years
        return [driver_w, satuan_w] + [year_w] * n_years + [dasar_w]
    if {"katalis", "waktu", "kenapa penting", "arah"}.issubset(labels):
        return [50, 13, 28, 9]
    if labels and labels[0].startswith("katalis / risiko"):
        return [18, 36, 30, 16]
    return {3: [42, 29, 29], 4: [34, 22, 22, 22],
            5: [48, 12, 12, 12, 16],
            6: [34, 13.2, 13.2, 13.2, 13.2, 13.2],
            7: [34, 11.0, 11.0, 11.0, 11.0, 11.0, 11.0],
            8: [26, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 20.0]}.get(
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
        elif values and sum(bool(re.match(r"^(?:Rp|USD\s*)?[\d(~−-]|^n\.a\.$|^n\.m\.$", v))
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
            if kind == "num":
                # Spec §5.5: negative figures in brackets.
                cell = re.sub(r"^[-−](\d[\d.,]*)(%|x)?$", r"(\1\2)", cell)
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


def _nice_max(value):
    """Round a positive axis top up to 1, 2, 2.5 or 5 x 10^k."""
    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    return next(step * power for step in (1, 2, 2.5, 5, 10) if step * power >= value)


def _short_number(value):
    """Compact bar label: 55.800.818 -> 55,8 jt; 6.524 -> 6.524."""
    magnitude = abs(value)
    if magnitude < 100:
        return fmt._id(value, 1)  # ratios such as DER 0,9x
    for size, suffix in ((1e12, " T"), (1e9, " M"), (1e6, " jt")):
        if magnitude >= size * 10 or (magnitude >= size and size >= 1e9):
            return fmt._id(value / size, 1) + suffix
    return fmt.rp(round(value))


def _mini_chart(ox, oy, w, h, title, labels, bars, line, forecast, line_label):
    """One quadrant: bars (actual solid blue, forecast light blue), optional
    secondary line on its own scale, dashed grid and a black zero baseline."""
    out = [f"<text x='{ox}' y='{oy + 11}' font-size='11' font-weight='700' "
           f"fill='{INK}'>{html.escape(title)}</text>"]
    top, base = oy + 30, oy + h - 22
    values = [v for v in bars if isinstance(v, (int, float))]
    lo = min(0.0, min(values)) if values else 0.0
    # Bars use the lower ~60% of the plot; the secondary line gets the top band,
    # so bar and line labels never collide.
    hi = _nice_max(max(values) * 1.65) if values and max(values) > 0 else 1.0
    span = (hi - lo) or 1.0

    def y_of(v):
        return base - (v - lo) / span * (base - top)

    for i in range(1, 4):
        gy = y_of(lo + span * i / 3)
        out.append(f"<line x1='{ox}' x2='{ox + w}' y1='{gy:.1f}' y2='{gy:.1f}' "
                   f"stroke='{GRID}' stroke-width='0.8' stroke-dasharray='3 3'/>")
    zero = y_of(0)
    n = max(len(labels), 1)
    slot = w / n
    bw = min(34.0, slot * 0.62)
    for i, label in enumerate(labels):
        cx = ox + slot * (i + 0.5)
        v = bars[i] if i < len(bars) else None
        is_fc = bool(forecast[i]) if i < len(forecast) else False
        if isinstance(v, (int, float)):
            y = min(y_of(v), zero)
            height = max(1.2, abs(y_of(v) - zero))
            color = EVEN_ROW if is_fc else PRIMARY
            out.append(f"<rect x='{cx - bw / 2:.1f}' y='{y:.1f}' width='{bw:.1f}' "
                       f"height='{height:.1f}' fill='{color}'/>")
            text_y = y - 3 if height < 14 else y + 10
            fill = INK if (height < 14 or is_fc) else "#FFFFFF"
            out.append(f"<text x='{cx:.1f}' y='{text_y:.1f}' text-anchor='middle' "
                       f"font-size='7.5' font-weight='500' fill='{fill}'>{_short_number(v)}</text>")
        out.append(f"<text x='{cx:.1f}' y='{base + 13}' text-anchor='middle' font-size='8' "
                   f"fill='{INK}'>{html.escape(str(label))}</text>")
    out.append(f"<line x1='{ox}' x2='{ox + w}' y1='{zero:.1f}' y2='{zero:.1f}' "
               f"stroke='#000000' stroke-width='1'/>")
    points = [(ox + slot * (i + 0.5), v) for i, v in enumerate(line or [])
              if isinstance(v, (int, float))]
    if len(points) >= 2:
        l_lo, l_hi = min(v for _, v in points), max(v for _, v in points)
        l_span = (l_hi - l_lo) or 1.0
        band = (base - top) * 0.32
        coords = [(x, top + 8 + (1 - (v - l_lo) / l_span) * band) for x, v in points]
        out.append("<polyline points='" + " ".join(f"{x:.1f},{y:.1f}" for x, y in coords) +
                   f"' fill='none' stroke='{SERIES[3]}' stroke-width='2'/>")
        for (x, y), (_, v) in zip(coords, points):
            out.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='2.2' fill='{SERIES[3]}'/>"
                       f"<text x='{x:.1f}' y='{y - 5:.1f}' text-anchor='middle' font-size='7' "
                       f"fill='{INK}'>{fmt._id(v, 1)}%</text>")
        out.append(f"<text x='{ox + w}' y='{oy + 11}' text-anchor='end' font-size='8' "
                   f"fill='{INK}'>garis: {html.escape(line_label)}</text>")
    return "".join(out)


_LINE_LABELS = {"Pendapatan": "pertumbuhan yoy", "EBITDA": "margin",
                "Laba bersih": "pertumbuhan yoy", "DER": "ROE"}


def _combo_chart(ex):
    """Slide-3 style 2x2 grid; each quadrant tie-outs with Key Financials.

    data: {"cols": [...], "series": [{"label":..., "bars":[...], "line":[...],
            "is_forecast":[bool...]}]}
    """
    data = ex.get("data") or {}
    series = (data.get("series") or [])[:4]
    labels = data.get("cols") or []
    w, h, gap = 360, 175, 20
    rows = (len(series) + 1) // 2
    height = rows * h + (rows - 1) * gap + 22
    parts = [f"<div class='exhibit keep'><div class='chart-caption'>Exhibit {ex['n']}. "
             f"{html.escape(ex['judul'])}</div>",
             f"<svg class='combo-chart' viewBox='0 0 {2 * w + gap} {height}' role='img' "
             f"aria-label='{html.escape(ex['judul'])}' style='display:block;width:100%;height:auto'>"]
    for idx, s in enumerate(series):
        title = str(s.get("label") or "")
        key = next((k for k in _LINE_LABELS if title.startswith(k)), "")
        parts.append(_mini_chart((idx % 2) * (w + gap), (idx // 2) * (h + gap), w, h, title,
                                 labels, s.get("bars") or [], s.get("line") or [],
                                 s.get("is_forecast") or [], _LINE_LABELS.get(key, "rasio")))
    ly = height - 8
    parts.append(f"<rect x='0' y='{ly - 7}' width='8' height='8' fill='{PRIMARY}'/>"
                 f"<text x='12' y='{ly}' font-size='8' fill='{INK}'>Aktual</text>"
                 f"<rect x='62' y='{ly - 7}' width='8' height='8' fill='{EVEN_ROW}'/>"
                 f"<text x='74' y='{ly}' font-size='8' fill='{INK}'>Proyeksi</text>"
                 f"<rect x='130' y='{ly - 7}' width='8' height='8' fill='{SERIES[3]}'/>"
                 f"<text x='142' y='{ly}' font-size='8' fill='{INK}'>Garis (sumbu sendiri)</text>")
    parts.append("</svg>")
    parts.append(f"<p class='src'>{html.escape(ex['catatan_sumber'])}</p></div>")
    return "".join(parts)


def _bar_chart(ex):
    data = ex["data"]
    rows = data["rows"]
    values = [(row.get(key) or 0) / 1e6 for row in rows for key in ("prior", "current")]
    top = _nice_max(max(values + [1]))
    parts = [f"<div class='exhibit keep'><div class='chart-caption'>Exhibit {ex['n']}. "
             f"{html.escape(ex['judul'])}</div>",
             "<svg class='metric-chart' viewBox='0 0 780 205' role='img' "
             f"aria-label='{html.escape(ex['judul'])}'>"]
    for i in range(1, 4):
        gy = 164 - 112 * i / 3
        parts.append(f"<line x1='35' x2='750' y1='{gy:.1f}' y2='{gy:.1f}' stroke='{GRID}' "
                     "stroke-width='0.8' stroke-dasharray='3 3'/>")
    centers = [145, 390, 635] if len(rows) == 3 else [270, 520]
    for center, row in zip(centers, rows):
        for x, key, color in ((center - 70, "prior", EVEN_ROW), (center + 7, "current", PRIMARY)):
            value = max(0, (row.get(key) or 0) / 1e6)
            height = max(1.5, 112 * value / top)
            y = 164 - height
            label = f"{value:,.0f}".replace(",", ".")
            parts.append(f"<rect x='{x}' y='{y:.1f}' width='63' height='{height:.1f}' "
                         f"fill='{color}'/>")
            inside = height >= 18
            fill = ("#FFFFFF" if color == PRIMARY else INK) if inside else INK
            ty = y + 13 if inside else max(13, y - 5)
            parts.append(f"<text x='{x + 31.5}' y='{ty:.1f}' text-anchor='middle' "
                         f"font-size='12' font-weight='500' fill='{fill}'>{label}</text>")
        parts.append(f"<text x='{center}' y='185' text-anchor='middle' "
                     f"font-size='13' fill='{INK}'>{html.escape(row['label'])}</text>")
    parts.append("<line x1='35' x2='750' y1='164' y2='164' stroke='#000000' stroke-width='1'/>")
    parts.append(f"<rect x='34' y='15' width='12' height='12' fill='{EVEN_ROW}'/>")
    parts.append(f"<text x='51' y='26' font-size='13'>{html.escape(data['prior_label'])}</text>")
    parts.append(f"<rect x='130' y='15' width='12' height='12' fill='{PRIMARY}'/>")
    parts.append(f"<text x='147' y='26' font-size='13'>{html.escape(data['current_label'])}</text>")
    parts.append(f"<text x='745' y='26' text-anchor='end' font-size='12' "
                 f"fill='{INK}'>{html.escape(data['unit'])}</text>")
    parts.append("</svg>")
    parts.append(f"<p class='src'>{html.escape(ex['catatan_sumber'])}</p></div>")
    return "".join(parts)


def _exhibit(ex):
    t = ex.get("tipe")
    if t == "bar_chart":
        return _bar_chart(ex)
    if t == "combo_chart":
        return _combo_chart(ex)
    return _table(ex)


def _kv(k, v):
    return f"<div class='kv'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>"


def _topbar(report_date):
    try:
        day = date.fromisoformat(str(report_date)[:10])
        weekdays = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
        months = ("Januari", "Februari", "Maret", "April", "Mei", "Juni",
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember")
        display_date = f"{weekdays[day.weekday()]}, {day.day} {months[day.month-1]} {day.year}"
    except ValueError:
        display_date = str(report_date)
    return ("<div class='topbar'><span>Equity Research - Company Update<br>"
            f"{html.escape(display_date)}</span><span class='wordmark' "
            f"aria-label='Sectoral'>{LOGO_SVG}</span></div>")


def _report_header(report_date, meta):
    """Build the report header from the Figma layout and current report data."""
    try:
        day = date.fromisoformat(str(report_date)[:10])
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        display_date = f"{day.day} {months[day.month - 1]} {day.year}"
    except (TypeError, ValueError):
        display_date = str(report_date)

    ticker = str(meta.get("ticker") or "").strip().upper()
    heading = f"{ticker} IJ" if ticker else "Equity Research"
    rating = meta.get("rating")
    target = meta.get("tp")
    if rating:
        heading += f" | {str(rating).upper()}"
        if target is not None:
            formatted_target = f"{target:,.0f}".replace(",", ".")
            heading += f" · TP Rp {formatted_target}"
    elif meta.get("status") == "draft_non_distributable":
        heading += " | Dalam Peninjauan"

    return ("<div class='report-header'>"
            "<div class='report-heading'>"
            f"<div class='report-title'>{html.escape(heading)}</div>"
            "<div class='report-subtitle'>Equity Research – Company Update | "
            f"{html.escape(display_date)}</div></div>"
            f"<img class='report-wordmark' src='data:image/png;base64,{REPORT_WORDMARK}' "
            "alt='Sektoral'>"
            f"<img class='report-divider' src='data:image/svg+xml;base64,{REPORT_DIVIDER}' "
            "alt=''>"
            "</div>")


def _draft_banner(meta):
    if meta.get("status") != "draft_non_distributable":
        return ""
    if meta.get("illustrative_scenarios"):
        return ("<div class='draft-banner'>DRAFT ILUSTRATIF: skenario memakai fakta "
                "bersumber dan asumsi analis; belum layak sebagai target harga.</div>")
    return ("<div class='draft-banner'>DRAFT: BUKTI BELUM LENGKAP: "
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
                       f"<p class='research-cite'><b>Rujukan data:</b> {html.escape(refs)}</p>"
                       "</article>")

    elif b.get("layout") == "cards":
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        res.append("<div class='cards'>")
        for card in b.get("cards") or []:
            metric = ""
            if card.get("metric"):
                metric = ("<div class='card-metric'>"
                          f"<div class='card-value'>{html.escape(str(card['metric']))}</div>"
                          f"<div class='card-label'>{html.escape(str(card.get('metric_label') or ''))}</div>"
                          "</div>")
            res.append("<div class='card'><div class='card-body'>"
                       f"<div class='card-title'>{html.escape(str(card.get('title') or ''))}</div>"
                       f"<div class='card-text'>{html.escape(str(card.get('text') or ''))}</div>"
                       f"</div>{metric}</div>")
        res.append("</div>")
        for e in exs:
            res.append(_exhibit(e))

    elif b.get("layout") == "stack":
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        for e in exs:
            res.append(_exhibit(e))

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


def _css_string(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _running_header(m):
    """Repeat the report header on every printed page, including overflow pages.

    Section headers live inside each section's HTML, so a section that spills
    onto a second sheet would otherwise print without header or draft label.
    """
    ticker = str(m.get("ticker") or "").upper()
    left = f"{ticker} IJ" if ticker else "Equity Research"
    if m.get("rating"):
        left += f" | {str(m['rating']).upper()}"
        if m.get("tp") is not None:
            left += f" · TP Rp {fmt.rp(m['tp'])}"
    elif m.get("status") == "draft_non_distributable":
        left += " | DRAFT · Dalam Peninjauan"
    try:
        day = date.fromisoformat(str(m.get("tanggal"))[:10])
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        right = f"Equity Research - Company Update | {day.day} {months[day.month - 1]} {day.year}"
    except (TypeError, ValueError):
        right = "Equity Research - Company Update"
    box = ("font-family:'Roboto',sans-serif;font-size:7.6pt;"
           "vertical-align:bottom;padding-bottom:2mm;")
    # Two-colour rule under the header, as in the design divider: blue, then lime.
    return ("@page{margin-top:19mm;"
            f"@top-left{{content:{_css_string(left)};font-weight:900;color:{PRIMARY};{box}"
            f"border-bottom:1.5px solid {PRIMARY}}}"
            f"@top-right{{content:{_css_string(right)};text-align:right;color:{INK};{box}"
            f"border-bottom:1.5px solid {LIME}}}}}"
            "@page:first{margin-top:12mm;@top-left{content:none;border:0}"
            "@top-right{content:none;border:0}}"
            "@media print{.page>.report-header{display:none}}")


def render(doc):
    m, cov = doc["meta"], doc["cover"]
    h = [f"<html><head><meta charset='utf-8'><style>{CSS}{_running_header(m)}</style></head><body>"]
    h.append(_report_header(m["tanggal"], m))
    h.append(_draft_banner(m))
    draft = m.get("status") == "draft_non_distributable"
    rating_word = m.get("rating") or ("Draft" if draft else "Analisis")
    rating_status = m.get("rating_status") or cov.get("rating_status")
    if draft:
        rating_status = rating_status or "Dalam peninjauan"
    elif m.get("rating"):
        rating_status = rating_status or "Inisiasi"
    else:
        rating_status = "Skenario informasional"
    h.append("<div class='cover'><div class='left'>")
    h.append("<div class='rating-block'>"
             f"<div class='rating-label'>{html.escape(str(rating_word))}</div>"
             f"<div class='rating-detail'>({html.escape(str(rating_status))})</div>"
             "<div class='rating-method'>"
             + ("Rating ditahan hingga pemeriksaan selesai.<br>" if draft else "")
             + f"Valuasi: {html.escape(doc.get('method', 'DCF'))}</div>"
             "</div>")
    h.append("<div class='basic-head'>Data pasar</div><div class='panel'>")
    price_label = (f"Harga Terakhir (Rp; {m['harga_tanggal']})"
                   if m.get("harga_tanggal") and m.get("harga_tanggal") != m["tanggal"]
                   else "Harga Terakhir (Rp)")
    harga_val = fmt.rp(m["harga"]) if m.get("harga") is not None else "n.a."
    h.append(_kv(price_label, harga_val))
    h.append(_kv("Target Harga (Rp)",
                 fmt.rp(m["tp"]) if m.get("rating") and m.get("tp") is not None else "-"))
    h.append(_kv("TP Sebelumnya (Rp)", str(m.get("tp_sebelumnya") or "n.a.")))
    h.append(_kv("Upside/Downside", f"{m['upside_persen']:+.1f}%".replace(".", ",")
                 if m.get("rating") and m.get("upside_persen") is not None else "-"))
    dp = cov.get("data_pasar") or {}
    saham_val = fmt._id(dp["saham"] / 1e6, 0) if dp.get("saham") is not None else "n.a."
    mcap_val = fmt._id(dp["market_cap"] / 1e9, 0) if dp.get("market_cap") is not None else "n.a."
    h.append(_kv("Jumlah Saham (juta)", saham_val))
    h.append(_kv("Kap. Pasar (Rp miliar)", mcap_val))
    h.append(_kv("Rata-rata T/O Harian (Rp miliar)", str(dp.get("adtv", "-"))))
    h.append(_kv("Free Float (%)", str(
        dp.get("public_ownership", dp.get("free_float", "-")))))
    h.append("</div>")
    holders = (doc.get("holders") or [])[:3]
    if holders:
        h.append("<div class='basic-head'>Pemegang saham utama</div><div class='panel'>")
        for holder in holders:
            h.append(_kv(str(holder[0])[:26], str(holder[1])))
        h.append("</div>")
    f1 = doc.get("fy26") or {}
    if f1:
        h.append("<div class='basic-head'>FY26F (Rp miliar)</div><div class='panel'>")
        for k in ("Pendapatan", "EBITDA", "Laba bersih"):
            if k in f1:
                v = f1[k]
                h.append(_kv(k, "n.a." if v is None else str(v)))
        h.append("</div>")
    h.append(f"<div class='basic-head'>{html.escape(m['ticker'])} vs IHSG</div>")
    h.append(_price_chart(m["ticker"], m["tanggal"]))
    h.append("<div class='analyst'><b>Tim Riset Sektoral</b><br>Equity Analyst</div>")
    h.append("</div><div class='right'>")
    h.append(f"<h1 class='emit'>{html.escape(m['emiten'])} ({html.escape(m['ticker'])} IJ)</h1>")
    h.append(f"<div class='headline'>{html.escape(cov['headline'])}</div>"
             "<div class='highlight'><ul class='bullets'>")
    for b in cov["bullets"]:
        h.append(f"<li>{html.escape(b)}</li>")
    h.append("</ul></div>")
    for p in cov["paragraf"]:
        h.append(f"<h3 class='sub'>{html.escape(p['judul'])}</h3><p>{html.escape(p['isi'])}</p>")
    by_n = {e["n"]: e for e in doc["exhibits"]}
    # Key Financials sits under the narrative in the main column (design 5.4.2).
    h.append(_table(by_n[1]))
    h.append("</div></div>")

    for number, b in enumerate(doc["bagian"], start=1):
        # The cover owns sheet 1; inner sections flow like the design deck
        # (several short sections per sheet) instead of one section per page.
        page_class = "page" if number == 1 else "section"
        if b.get("layout") == "research_cards":
            page_class += " research-summary"
        h.append(f"<div class='{page_class}'>{_report_header(m['tanggal'], m)}")
        h.append(_draft_banner(m))
        h.append(f"<h2 class='sec'><span class='num'>{number}.</span> "
                 f"{html.escape(b['judul'])}</h2>")
        h.append(_render_page_content(b))
        h.append("</div>")

    disclosure = ("Laporan ini memuat rekomendasi model bersyarat berdasarkan "
                  "asumsi dan sumber yang dinyatakan; keputusan investasi menjadi "
                  "tanggung jawab pembaca. Kinerja masa lalu tidak menjamin hasil ke depan."
                  if m.get("rating") else
                  "Dokumen ini adalah bahan riset dalam peninjauan. Rating dan target "
                  "harga belum diterbitkan karena syarat data atau model belum terpenuhi. "
                  "Keputusan investasi menjadi tanggung jawab pembaca.")
    h.append(f"<div class='page'>{_report_header(m['tanggal'], m)}"
             f"{_draft_banner(m)}"
             "<h2 class='sec'>Pengungkapan</h2>"
             f"<p class='small'>{html.escape(disclosure)}</p>"
             "<h3 class='sub'>Catatan metodologi</h3><ul>")
    for c in doc["catatan_metodologi"]:
        h.append(f"<li class='small'>{html.escape(c)}</li>")
    h.append("</ul></div></body></html>")
    out = "\n".join(h)
    return out.replace("\u2014", " - ").replace("\u2013", "-")
