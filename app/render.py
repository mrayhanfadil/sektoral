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
from . import idx_history

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
INDEX_COLOR = SERIES[1]  # Figma: relative-vs-IHSG line in light blue

# Use the canonical wordmark from sectors-hackathon/assets/brand/sectoral-logo.svg.
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "brand" / "sectoral-logo.svg"
LOGO_SVG = LOGO_PATH.read_text(encoding="utf-8")
REPORT_WORDMARK = _b64_brand_asset("report-wordmark.png")
REPORT_DIVIDER = _b64_brand_asset("report-divider.svg")
REPORT_MORSE = _b64_brand_asset("report-morse.svg")
REPORT_SEPARATOR = _b64_brand_asset("report-separator.svg")

PAGE_NUM = ("@page{size:A4;margin:12mm 8.5mm 14mm;"
            "@bottom-left{content:'See important disclosure at the back of this report';"
            "box-sizing:border-box;width:163mm;height:3mm;padding-left:107mm;"
            "background-image:url('data:image/svg+xml;base64," + REPORT_MORSE + "');"
            "background-size:103.7mm 1.7mm;background-position:left center;"
            "background-repeat:no-repeat;white-space:nowrap;"
            "font-family:'Roboto',sans-serif;font-size:7.7pt;line-height:3mm;"
            "text-rendering:geometricPrecision;word-spacing:.05em;"
            "color:" + PRIMARY + "}"
            "@bottom-right{content:'Page ' counter(page) ' of ' counter(pages);font-weight:900;"
            "box-sizing:border-box;width:26mm;height:3mm;text-align:right;white-space:nowrap;"
            "font-family:'Roboto',sans-serif;font-size:7.7pt;line-height:3mm;"
            "text-rendering:geometricPrecision;word-spacing:.05em;"
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
       ";font-size:7.7pt;line-height:1.2;margin:0;"
       # Hinted glyph advances at the Figma 7.7pt body size shrink word gaps
       # below pdftotext's threshold, so copied text merges words
       # (tests/test_pdf_copy_text). Unhinted metrics keep the spaces.
       "text-rendering:geometricPrecision}"
       "p{margin:0 0 3.4mm;text-align:justify}"
       ".topbar{display:flex;justify-content:space-between;align-items:center;"
       "border-bottom:2px solid "
       + PRIMARY + ";padding-bottom:3px;font-size:8.1pt;color:" + PRIMARY + ";font-weight:600}"
       ".brandmark{vertical-align:-4px;margin-right:3px}"
       ".wordmark{display:flex;align-items:center}.wordmark svg{display:block;width:84px;height:18px}"
       ".report-header{display:grid;grid-template-columns:minmax(0,1fr) 32.4mm;"
       "grid-template-rows:auto 0.5mm;column-gap:5mm;row-gap:0.4mm;"
       "align-items:center;padding:0 0 1.7mm;margin:0 0 1.7mm}"
       ".report-heading{grid-column:1;grid-row:1;min-width:0}"
       # Header line 1: stock code + rating action (Roboto Black, blue);
       # line 2: report type + date (Roboto Regular, black).
       ".report-title{font-size:9.6pt;line-height:1.17;color:" + PRIMARY + ";"
       "font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
       ".report-subtitle{font-size:7.7pt;line-height:1.17;color:" + INK + ";margin-top:0.35mm}"
       ".report-wordmark{grid-column:2;grid-row:1;display:block;width:32.4mm;height:5.75mm;"
       "object-fit:contain}"
       ".report-divider{grid-column:1/-1;grid-row:2;display:block;width:100%;"
       "height:0.5mm;object-fit:fill}"
       ".status{font-size:10.5pt;color:" + PRIMARY + ";font-weight:700;margin:5px 0 2px}"
       # Rating block: Roboto Black Italic on the highlight fill.
       ".rating-block{background:" + HIGHLIGHT + ";border-radius:3.4mm;padding:3.4mm;"
       "display:flex;flex-direction:column;align-items:center;gap:3.4mm;margin:0}"
       ".rating-head{text-align:center}"
       ".rating-label{font-size:30.7pt;color:" + PRIMARY + ";font-weight:900;font-style:italic;"
       "line-height:1.17;text-transform:uppercase}"
       ".rating-detail{font-size:9.6pt;color:" + PRIMARY + ";font-weight:900;font-style:italic;"
       "line-height:1.17}"
       ".rating-method{font-size:6.2pt;color:" + PRIMARY + ";margin-top:1.2mm;line-height:1.3}"
       ".rating-sep{display:block;width:92%;height:1px}"
       ".rating-row{display:flex;width:100%;gap:2mm;align-items:center;font-weight:700;"
       "color:" + PRIMARY + ";font-size:7.7pt;line-height:1.17}"
       ".rating-row span{flex:1 1 auto;min-width:0}.rating-row b{font-weight:700;white-space:nowrap}"
       ".rating-row b.na{font-style:italic}"
       ".rating-sub{font-size:9.6pt;font-weight:900;color:" + PRIMARY + ";text-align:center;"
       "text-transform:uppercase;line-height:1.17}"
       # Left-column exhibit (Figma "Information").
       ".info{padding:1.7mm 3.4mm;display:flex;flex-direction:column;gap:1.7mm}"
       ".info-title{font-size:7.7pt;line-height:1.2;color:" + INK + "}"
       ".info-src{font-size:5.8pt;font-style:italic;text-align:center;line-height:1.2}"
       ".draft-banner{background:#fff3e8;border:1px solid #bb4d00;color:#803400;"
       "font-weight:700;padding:5px 8px;margin:5px 0;font-size:8.5pt}"
       ".cover{display:flex;align-items:flex-start;margin-top:1.7mm}"
       ".left{width:35%;padding:1.7mm 3.4mm 3.4mm 0;box-sizing:border-box;display:flex;"
       "flex-direction:column;gap:3.4mm}"
       ".right{width:65%;padding:1.7mm 0 3.4mm 3.4mm;box-sizing:border-box}"
       ".kv{display:flex;justify-content:space-between;align-items:baseline;padding:2.2px 0;"
       "border-bottom:1px solid " + HIGHLIGHT + "}"
       ".kv span{padding-right:4px}.kv b{font-weight:500;color:" + INK + ";white-space:nowrap}"
       ".panel{background:" + PAPER + ";padding:0}"
       # Company name (Roboto Black) and thesis line (Roboto Black Italic).
       "h1.emit{font-size:19.2pt;line-height:1.17;margin:0 0 3.4mm;color:" + INK + ";font-weight:900}"
       ".headline{font-size:9.6pt;line-height:1.17;font-weight:700;font-style:italic;color:" + INK +
       ";margin:0 0 3.4mm}"
       # Highlight callout for the three executive-summary bullets.
       ".highlight{background:" + HIGHLIGHT + ";border-left:1.5pt solid " + PRIMARY + ";"
       "padding:1.7mm;margin:0 0 3.4mm}"
       ".bullets{margin:0 0 0 4mm;padding:0;font-size:7.7pt;line-height:1.17}"
       ".bullets li{margin:0}"
       # Numbered section heads on inner pages (Roboto Black, black).
       "h2.sec{font-size:19.2pt;line-height:1.17;color:" + INK + ";font-weight:900;margin:0 0 3.4mm}"
       "h2.sec .num{color:" + INK + "}"
       "h3.sub{font-size:9.6pt;line-height:1.17;color:" + INK + ";font-weight:700;margin:0 0 1.7mm}"
       # Thesis cards: claim on the left, the metric that backs it on the right.
       ".cards{display:flex;flex-direction:column;margin:0 0 3.4mm}"
       ".card{display:flex;gap:1.7mm;align-items:center;padding:3.4mm;"
       "break-inside:avoid-page;page-break-inside:avoid}"
       ".card:nth-child(odd){background:" + HIGHLIGHT + "}"
       ".card-body{flex:1 1 auto;min-width:0}"
       ".card-title{font-weight:700;font-size:9.6pt;line-height:1.17;margin-bottom:3.2mm;color:" + INK + "}"
       ".card-text{font-size:7.7pt;line-height:1.17}"
       ".card-metric{flex:0 0 44mm;text-align:right;color:" + INK + "}"
       ".card-label{font-size:7.7pt;line-height:1.17}"
       ".card-value{font-size:17.3pt;font-weight:700;line-height:1.17}"
       ".risks .card-title{margin-bottom:1.7mm}"
       ".risk-tag{font-size:6pt;font-weight:900;letter-spacing:.04em;text-transform:uppercase;"
       "color:" + PRIMARY + ";margin-bottom:1mm}"
       ".risk-src{font-size:5.8pt;font-style:italic;line-height:1.3;margin-top:1.2mm}"
       ".risk-head{margin-top:1.7mm}"
       ".exhibit{margin:0 0 3.4mm}"
       ".exhibit.keep{break-inside:avoid-page;page-break-inside:avoid}"
       # Own-history band charts sit two across (struktur Exhibits 12-13).
       ".band-pair{display:grid;grid-template-columns:1fr 1fr;gap:3.4mm;"
       "break-inside:avoid-page;page-break-inside:avoid}"
       ".band-chart{display:block;width:100%;height:auto}"
       ".panel-text{font-size:6.7pt;line-height:1.3;margin:1.2mm 0 0;text-align:left}"
       # Table styling follows sectors-hackathon's .fin-table: a solid header
       # band, horizontal hairlines only (no vertical grid), spec zebra fill
       # and a ruled total line. The old full grid made every figure read as a
       # spreadsheet cell instead of a column.
       ".exhibit-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:7.7pt;"
       "margin:0;font-family:'Roboto',sans-serif;border:0}"
       ".exhibit-table th,.exhibit-table td{border:0;padding:1.7mm;"
       "vertical-align:middle;line-height:1.2;overflow-wrap:break-word;word-break:normal}"
       ".exhibit-table tbody.block:first-of-type tr:first-child td{border-top:0}"
       ".exhibit-table thead{display:table-header-group}"
       ".exhibit-table tbody{display:table-row-group}"
       ".exhibit-table tbody.block{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table tr{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table thead th{background:" + PRIMARY + ";color:#fff;font-weight:900;"
       "white-space:nowrap;padding:1.7mm}"
       ".exhibit-table .cell-text{text-align:left}"
       ".exhibit-table .cell-num{text-align:center;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-date{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-num.short{white-space:nowrap}"
       ".exhibit-table tbody tr:nth-child(even) td{background:" + HIGHLIGHT + "}"
       ".exhibit-table tbody tr.section-row th{background:" + EVEN_ROW + ";color:" + PRIMARY + ";"
       "text-align:left;font-weight:700;letter-spacing:.04em;"
       "border-top:1px solid " + PRIMARY + ";"
       "padding:4px 6px;break-after:avoid-page}"
       ".exhibit-table tbody.block:first-of-type tr.section-row:first-child th{border-top:0}"
       ".exhibit-table tbody tr.total-row td{background:" + PAPER + ";font-weight:700;"
       "border-top:1px solid " + PRIMARY + "}"
       # Exhibit label carries the same brand tick as the section heads.
       ".exhibit-table caption{text-align:left;font-weight:700;font-size:9.6pt;line-height:1.17;"
       "color:" + INK + ";margin-bottom:1.7mm;font-family:'Roboto',sans-serif}"
       ".src{font-size:5.8pt;color:" + INK + ";margin:1.7mm 0 0;line-height:1.4;font-style:italic;"
       "text-align:left;overflow-wrap:anywhere}"
       ".metric-chart{display:block;width:100%;height:180px}"
       ".chart-caption{font-weight:700;font-size:9.6pt;line-height:1.17;color:" + INK + ";margin-bottom:1.7mm}"
       ".research-card{border:1px solid " + RULE + ";"
       "padding:7px 9px;margin:9px 0;break-inside:avoid-page;page-break-inside:avoid}"
       ".research-card h3{color:" + PRIMARY + ";font-size:9pt;margin:0 0 4px}"
       ".research-card p{margin:3px 0;line-height:1.42}"
       ".research-card .research-cite{font-size:6.7pt;color:" + MUT + ";"
       "margin-top:6px;overflow-wrap:anywhere}"
       ".page{page-break-before:always}"
       ".analyst{font-size:8pt;margin-top:3mm;line-height:1.35}"
       ".section{margin-top:3.4mm}.section>.report-header{display:none}"
       "h2.sec{break-after:avoid-page;page-break-after:avoid}"
       ".small{font-size:7.5pt;color:" + MUT + "}"
       ".grid-2{display:flex;gap:12px;width:100%;margin:4px 0;box-sizing:border-box}"
       ".grid-col{flex:1 1 0;min-width:0;box-sizing:border-box}"
       "@media screen{body{max-width:1040px;margin:0 auto;padding:28px 34px;"
       "box-sizing:border-box;font-size:12px;line-height:1.5}"
       ".page{page-break-before:auto;border-top:1px solid " + RULE + ";margin-top:28px;padding-top:18px}"
       ".exhibit{overflow-x:auto}.exhibit-table{min-width:620px;font-size:11px}"
       ".exhibit-table th,.exhibit-table td{padding:7px 10px}"
       ".exhibit-table thead th{padding:8px 10px;font-size:10px}"
       ".exhibit-table caption{font-size:12px;margin-bottom:5px}"
       ".src{font-size:10px;line-height:1.4}"
       ".grid-col .exhibit-table{min-width:0}"
       # The cover's right column is narrower than 620px; its table must fit, not scroll.
       ".cover .exhibit-table{min-width:0}"
       ".cover .exhibit-table th,.cover .exhibit-table td{padding:6px 8px}}"
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


PRICE_WINDOW_DAYS = 730  # struktur: 18-24 months of price history


def _price_window(ticker, as_of):
    """Price and relative-to-IHSG series for the cover chart.

    IDX trading summaries (data/idx_history) give up to 24 months of closes;
    the relative line covers the dates IHSG is also available and is rebased
    at its first common date. Without IDX files the Sectors cache is used,
    both lines on common dates.
    """
    own, index = idx_history.load(ticker, as_of), idx_history.load("IHSG", as_of)
    if own and index:
        end = own["points"][-1][0]
        prices = [(d, c) for d, c in own["points"] if (end - d).days <= PRICE_WINDOW_DAYS]
        ihsg = dict(index["points"])
        common = [(d, c) for d, c in prices if d in ihsg]
        if len(prices) >= 2 and len(common) >= 2:
            first, ihsg_first = common[0][1], ihsg[common[0][0]]
            issuer = [100 * c / first for _, c in common]
            index_line = [100 * ihsg[d] / ihsg_first for d, _ in common]
            return {"price_dates": [d for d, _ in prices], "closes": [c for _, c in prices],
                    "rel_dates": [d for d, _ in common],
                    "relative": [a - b for a, b in zip(issuer, index_line)],
                    "issuer_return": issuer[-1] - 100, "ihsg_return": index_line[-1] - 100,
                    "source": "harga harian dan IHSG: IDX (ringkasan perdagangan)"}
    series = _comparison_series(ticker, as_of)
    if series is None:
        return None
    dates, closes, issuer, ihsg = series
    return {"price_dates": dates, "closes": closes, "rel_dates": dates,
            "relative": [a - b for a, b in zip(issuer, ihsg)],
            "issuer_return": issuer[-1] - 100, "ihsg_return": ihsg[-1] - 100,
            "source": None}


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


def _month_ticks(first, last):
    """First-of-month ticks; every month for short windows, quarterly for long."""
    months = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        day = date(year, month, 1)
        if first <= day <= last:
            months.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    step = 1 if len(months) <= 8 else 3
    return months[::step]


def _price_chart(ticker, as_of, number=None, source=None):
    """Figma cover Exhibit 1: close (left axis, Rp) and performance relative to
    IHSG (right axis, %), dashed grid, black baseline, square legend.

    The relative line is read against its own zero: above it the issuer beat
    the index, a reading a shared rebased scale would flatten.
    """
    window = _price_window(ticker, as_of)
    if window is None:
        return ("<p class='small'>Perbandingan harga belum tersedia: "
                "kurang dari dua tanggal perdagangan yang sama di data Sectors.</p>")

    dates, closes = window["price_dates"], window["closes"]
    rel_dates, relative = window["rel_dates"], window["relative"]
    p_lo, p_hi = _axis_scale(closes, PRICE_STEPS)
    r_lo, r_hi = _axis_scale(relative, REL_STEPS)
    # Figma frame 2611:333 (360 x 320): plot 48..292 x 24..223.
    x0, x1, y0, y1 = 48, 292, 24, 223
    days = (dates[-1] - dates[0]).days or 1

    def x_of(day):
        return x0 + (day - dates[0]).days / days * (x1 - x0)

    def y_of(value, lo, hi):
        return y1 - (value - lo) / (hi - lo) * (y1 - y0)

    def points(values, lo, hi, on=None):
        return " ".join(f"{x_of(day):.1f},{y_of(value, lo, hi):.1f}"
                        for day, value in zip(on or dates, values))

    label = "font-size='12' font-weight='700'"
    parts = []
    for i in range(4):
        y = y0 + i * (y1 - y0) / 3
        price_tick = p_hi - i * (p_hi - p_lo) / 3
        rel_tick = r_hi - i * (r_hi - r_lo) / 3
        if i < 3:
            parts.append(f"<line x1='{x0}' x2='{x1}' y1='{y:.1f}' y2='{y:.1f}' "
                         f"stroke='{GRID}' stroke-width='1' stroke-dasharray='3 3'/>")
        parts.append(f"<text x='10' y='{y + 4:.1f}' {label} fill='{INK}'>"
                     f"{fmt.rp(price_tick)}</text>"
                     f"<text x='302' y='{y + 4:.1f}' {label} fill='{INK}'>{rel_tick:+.0f}%</text>")
    parts.append(f"<polygon points='{x0},{y1} {points(closes, p_lo, p_hi)} {x_of(dates[-1]):.1f},{y1}' "
                 f"fill='{ISSUER_COLOR}' fill-opacity='0.12'/>")
    if r_lo <= 0 <= r_hi:
        zero_y = y_of(0, r_lo, r_hi)
        parts.append(f"<line x1='{x0}' x2='{x1}' y1='{zero_y:.1f}' y2='{zero_y:.1f}' "
                     f"stroke='#000000' stroke-width='1.2'/>")
    parts.append(f"<polyline points='{points(relative, r_lo, r_hi, rel_dates)}' fill='none' "
                 f"stroke='{INDEX_COLOR}' stroke-width='2' stroke-linejoin='round'/>")
    parts.append(f"<polyline points='{points(closes, p_lo, p_hi)}' fill='none' "
                 f"stroke='{ISSUER_COLOR}' stroke-width='2' stroke-linejoin='round'/>")
    parts.append(f"<line x1='{x0}' x2='{x1}' y1='{y1}' y2='{y1}' stroke='#000000' stroke-width='1'/>")
    last_y = y_of(closes[-1], p_lo, p_hi)
    parts.append(f"<text x='{x0 + 10}' y='{min(y1 - 6, last_y + 16):.1f}' {label} fill='{LIME}'>"
                 f"Terakhir {fmt.rp(closes[-1])}</text>")
    # A tick hugging the left edge would sit on the lowest price label.
    ticks = [day for day in _month_ticks(dates[0], dates[-1]) if x_of(day) - x0 >= 16]
    for index, day in enumerate(ticks):
        parts.append(f"<text x='{x_of(day):.1f}' y='{238 + 16 * (index % 2)}' text-anchor='middle' "
                     f"{label} fill='{INK}'>{day:%b-%y}</text>")
    parts.append(f"<rect x='19' y='288' width='14' height='14' fill='{ISSUER_COLOR}'/>"
                 f"<text x='43' y='300' {label} fill='{INK}'>Harga (Rp, kiri)</text>"
                 f"<rect x='150' y='288' width='14' height='14' fill='{INDEX_COLOR}'/>"
                 f"<text x='172' y='300' {label} fill='{INK}'>Relatif vs IHSG (%, kanan)</text>")

    span_months = max(1, round(days / 30.4))
    title = (f"{'Exhibit ' + str(number) + '. ' if number else ''}{html.escape(ticker)} "
             f"relative to IHSG ({span_months}M, {dates[0]:%b-%y} - {dates[-1]:%b-%y})")
    safe_ticker = html.escape(ticker)
    issuer_return, ihsg_return = window["issuer_return"], window["ihsg_return"]
    detail = (f"; {window['source']}" if window["source"] else "")
    if rel_dates[0] != dates[0]:
        detail += f"; garis relatif sejak {rel_dates[0].isoformat()} (cakupan IHSG)"

    def pct(value):
        return f"{value:+.1f}".replace(".", ",")
    return (
        f"<div class='info-title'>{title}</div>"
        "<svg class='price-chart' viewBox='0 0 360 320' width='360' height='320' "
        "style='display:block;width:100%;height:auto' role='img' aria-labelledby='price-chart-title'>"
        f"<title id='price-chart-title'>Harga penutupan {safe_ticker} dan kinerja "
        f"relatif terhadap IHSG, {dates[0].isoformat()} sampai {dates[-1].isoformat()}</title>"
        + "".join(parts) + "</svg>"
        # The data source is the one actually plotted: IDX when its files exist.
        f"<div class='info-src'>{html.escape((fmt.DEFAULT_SOURCE if window['source'] else fmt.house_source_line(source or 'Sectors')) + detail)}; "
        f"{safe_ticker} {pct(issuer_return)}%, IHSG {pct(ihsg_return)}%. "
        f"Selisih {pct(issuer_return - ihsg_return)} poin persentase; "
        f"{len(rel_dates)} tanggal sama, tidak termasuk dividen</div>")


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
    # Statements run to ~15 rows; keep them whole so a header never orphans.
    keep = " keep" if len(rows) <= 18 else ""
    return (f"<div class='exhibit{keep}'><table class='exhibit-table'>"
            f"<caption>Exhibit {ex['n']}. {html.escape(ex['judul'])}</caption>"
            f"<colgroup>{colgroup}</colgroup><thead><tr>{head}</tr></thead>"
            f"{body}</table>"
            f"<p class='src'>{html.escape(fmt.house_source_line(ex['catatan_sumber']))}</p></div>")


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
    parts.append(f"<p class='src'>{html.escape(fmt.house_source_line(ex['catatan_sumber']))}</p></div>")
    return "".join(parts)


def _combo_panel(ex):
    """Struktur Exhibits 4-7: one quadrant, its narrative directly under the
    chart, and the source line."""
    data = ex.get("data") or {}
    series = (data.get("series") or [{}])[0]
    labels = data.get("cols") or []
    title = str(series.get("label") or "")
    key = next((k for k in _LINE_LABELS if title.startswith(k)), "")
    w, h = 360, 190
    parts = [f"<div class='exhibit keep panel'><div class='chart-caption'>Exhibit {ex['n']}. "
             f"{html.escape(ex['judul'])}</div>",
             f"<svg class='combo-chart' viewBox='0 0 {w} {h + 16}' role='img' "
             f"aria-label='{html.escape(ex['judul'])}' style='display:block;width:100%;height:auto'>",
             _mini_chart(0, 0, w, h, title, labels, series.get("bars") or [],
                         series.get("line") or [], series.get("is_forecast") or [],
                         _LINE_LABELS.get(key, "rasio")),
             f"<rect x='0' y='{h + 3}' width='8' height='8' fill='{PRIMARY}'/>"
             f"<text x='12' y='{h + 10}' font-size='8' fill='{INK}'>Aktual</text>"
             f"<rect x='62' y='{h + 3}' width='8' height='8' fill='{EVEN_ROW}'/>"
             f"<text x='74' y='{h + 10}' font-size='8' fill='{INK}'>Proyeksi</text>"
             f"<rect x='130' y='{h + 3}' width='8' height='8' fill='{SERIES[3]}'/>"
             f"<text x='142' y='{h + 10}' font-size='8' fill='{INK}'>Garis (sumbu kanan)</text>",
             "</svg>"]
    if ex.get("narasi"):
        parts.append(f"<p class='panel-text'>{html.escape(ex['narasi'])}</p>")
    parts.append(f"<p class='src'>{html.escape(fmt.house_source_line(ex['catatan_sumber']))}</p></div>")
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
    parts.append(f"<p class='src'>{html.escape(fmt.house_source_line(ex['catatan_sumber']))}</p></div>")
    return "".join(parts)


def _band_chart(ex):
    """Struktur Exhibits 12-13: own-history multiple with mean (dashed),
    median (dotted) and the current level marked at the right edge."""
    data = ex["data"]
    values = data["values"]
    days = [date.fromisoformat(d) for d in data["dates"]]
    lo = min(values + [data["mean"], data["median"]])
    hi = max(values + [data["mean"], data["median"]])
    pad = (hi - lo) * 0.15 or hi * 0.05 or 1
    lo, hi = lo - pad, hi + pad
    x0, x1, y0, y1 = 40, 340, 16, 150
    span = (days[-1] - days[0]).days or 1
    x = lambda d: x0 + (d - days[0]).days / span * (x1 - x0)
    y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
    label = "font-size='10' font-weight='700'"
    parts = [f"<div class='exhibit keep band'><div class='chart-caption'>Exhibit {ex['n']}. "
             f"{html.escape(ex['judul'])}</div>",
             "<svg class='band-chart' viewBox='0 0 360 190' role='img' "
             f"aria-label='{html.escape(ex['judul'])}'>"]
    for i in range(4):
        v = hi - i * (hi - lo) / 3
        gy = y(v)
        parts.append(f"<line x1='{x0}' x2='{x1}' y1='{gy:.1f}' y2='{gy:.1f}' stroke='{GRID}' "
                     "stroke-dasharray='3 3'/>"
                     f"<text x='4' y='{gy + 3:.1f}' {label} fill='{INK}'>{html.escape(fmt.mult(v))}</text>")
    points = " ".join(f"{x(d):.1f},{y(v):.1f}" for d, v in zip(days, values))
    parts.append(f"<polyline points='{points}' fill='none' stroke='{PRIMARY}' stroke-width='2' "
                 "stroke-linejoin='round'/>")
    for key, dash, name in (("mean", "6 4", "Mean"), ("median", "1.5 3", "Median")):
        gy = y(data[key])
        parts.append(f"<line x1='{x0}' x2='{x1}' y1='{gy:.1f}' y2='{gy:.1f}' stroke='{INK}' "
                     f"stroke-width='1.2' stroke-dasharray='{dash}'/>")
    cx, cy = x(days[-1]), y(data["current"])
    parts.append(f"<path d='M{cx:.1f},{cy - 5:.1f} L{cx + 5:.1f},{cy:.1f} L{cx:.1f},{cy + 5:.1f} "
                 f"L{cx - 5:.1f},{cy:.1f} Z' fill='{LIME}' stroke='{INK}' stroke-width='0.8'/>")
    parts.append(f"<line x1='{x0}' x2='{x1}' y1='{y1}' y2='{y1}' stroke='#000000'/>")
    for d, anchor in ((days[0], "start"), (days[len(days) // 2], "middle"), (days[-1], "end")):
        parts.append(f"<text x='{x(d):.1f}' y='{y1 + 14}' text-anchor='{anchor}' {label} "
                     f"fill='{INK}'>{d:%d-%b-%y}</text>")
    legend_y = 182
    parts.append(f"<line x1='40' x2='58' y1='{legend_y - 4}' y2='{legend_y - 4}' stroke='{PRIMARY}' stroke-width='2'/>"
                 f"<text x='62' y='{legend_y}' {label} fill='{INK}'>{html.escape(data['label'])}</text>"
                 f"<line x1='100' x2='118' y1='{legend_y - 4}' y2='{legend_y - 4}' stroke='{INK}' stroke-dasharray='6 4'/>"
                 f"<text x='122' y='{legend_y}' {label} fill='{INK}'>Mean {html.escape(fmt.mult(data['mean']))}</text>"
                 f"<line x1='190' x2='208' y1='{legend_y - 4}' y2='{legend_y - 4}' stroke='{INK}' stroke-dasharray='1.5 3'/>"
                 f"<text x='212' y='{legend_y}' {label} fill='{INK}'>Median {html.escape(fmt.mult(data['median']))}</text>"
                 f"<text x='290' y='{legend_y}' {label} fill='{INK}'>Kini p{data['percentile']:.0f}</text>")
    parts.append("</svg>")
    parts.append(f"<p class='src'>{html.escape(fmt.house_source_line(ex['catatan_sumber']))}</p></div>")
    return "".join(parts)


def _exhibits_paired(exs):
    """Render exhibits in order; consecutive band charts share one row."""
    out, i = [], 0
    while i < len(exs):
        kind = exs[i].get("tipe")
        if (kind in ("band_chart", "combo_panel") and i + 1 < len(exs)
                and exs[i + 1].get("tipe") == kind):
            out.append(f"<div class='band-pair'>{_exhibit(exs[i])}{_exhibit(exs[i + 1])}</div>")
            i += 2
        else:
            out.append(_exhibit(exs[i]))
            i += 1
    return "".join(out)


def _exhibit(ex):
    t = ex.get("tipe")
    if t == "band_chart":
        return _band_chart(ex)
    if t == "combo_panel":
        return _combo_panel(ex)
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
        # Struktur header: "Day, DD Month YYYY", in the report's language.
        weekdays = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
        months = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
                  "Agustus", "September", "Oktober", "November", "Desember")
        display_date = (f"{weekdays[day.weekday()]}, {day.day:02d} "
                        f"{months[day.month - 1]} {day.year}")
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


def _risk_block(risks):
    """Spec §5.4 'Risiko utama': named, categorised risks in the thesis-card
    style, each with the source of its number."""
    res = ["<h3 class='sub risk-head'>Risiko utama</h3><div class='cards risks'>"]
    for risk in risks:
        res.append("<div class='card'><div class='card-body'>"
                   f"<div class='risk-tag'>{html.escape(str(risk.get('kategori') or ''))}</div>"
                   f"<div class='card-title'>{html.escape(str(risk.get('judul') or ''))}</div>"
                   f"<div class='card-text'>{html.escape(str(risk.get('isi') or ''))}</div>"
                   f"<div class='risk-src'>Sumber: {html.escape(str(risk.get('sumber') or '-'))}</div>"
                   "</div></div>")
    res.append("</div>")
    return "".join(res)


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
        split = b.get("risks_after", 0) if b.get("risks") else len(exs)
        res.append(_exhibits_paired(exs[:split]))
        if b.get("risks"):
            res.append(_risk_block(b["risks"]))
        res.append(_exhibits_paired(exs[split:]))

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
    sep = (f"<img class='rating-sep' src='data:image/svg+xml;base64,{REPORT_SEPARATOR}' alt=''>")

    def row(label, value, na=False):
        return (f"<div class='rating-row'><span>{html.escape(label)}</span>"
                f"<b class='{'na' if na else ''}'>{html.escape(value)}</b></div>")

    dp = cov.get("data_pasar") or {}
    released = bool(m.get("rating")) and m.get("tp") is not None
    prev_tp = m.get("tp_sebelumnya")
    both = lambda rp, usd: f"{rp} / {usd}" if usd else rp
    h.append("<div class='cover'><div class='left'>")
    h.append("<div class='rating-block'><div class='rating-head'>"
             f"<div class='rating-label'>{html.escape(str(rating_word))}</div>"
             f"<div class='rating-detail'>({html.escape(str(rating_status))})</div>"
             "<div class='rating-method'>"
             + ("Rating ditahan hingga pemeriksaan selesai.<br>" if draft else "")
             + f"Valuasi: {html.escape(doc.get('method', 'DCF'))}</div></div>" + sep)
    price_label = (f"Harga Terakhir (Rp; {m['harga_tanggal']})"
                   if m.get("harga_tanggal") and m.get("harga_tanggal") != m["tanggal"]
                   else "Harga Terakhir (Rp)")
    h.append(row(price_label, fmt.rp(m["harga"]) if m.get("harga") is not None else "NA",
                 m.get("harga") is None))
    h.append(row("Target Harga (Rp)", fmt.rp(m["tp"]) if released else "NA", not released))
    h.append(row("TP Sebelumnya (Rp)", str(prev_tp) if prev_tp else "NA", not prev_tp))
    h.append(row("Upside/Downside (%)", f"{m['upside_persen']:+.2f}%".replace(".", ",")
                 if released and m.get("upside_persen") is not None else "NA", not released))
    h.append(row("Jumlah Saham (juta)",
                 fmt._id(dp["saham"] / 1e6, 1) if dp.get("saham") is not None else "NA"))
    mcap = fmt._id(dp["market_cap"] / 1e9, 1) if dp.get("market_cap") is not None else "NA"
    h.append(row("Kap. Pasar (Rp miliar / US$ juta)" if dp.get("market_cap_usd")
                 else "Kap. Pasar (Rp miliar)", both(mcap, dp.get("market_cap_usd"))))
    h.append(row("Rata-rata T/O Harian 3M (Rp miliar / US$ juta)" if dp.get("adtv_usd")
                 else "Rata-rata T/O Harian 3M (Rp miliar)",
                 both(str(dp.get("adtv", "NA")), dp.get("adtv_usd"))))
    h.append(row("Free Float (%)", str(dp.get("public_ownership", dp.get("free_float", "NA")))))
    holders = (doc.get("holders") or [])[:4]
    if holders:
        h.append(sep + "<div class='rating-sub'>Pemegang Saham Utama (%)</div>")
        for holder in holders:
            h.append(row(str(holder[0])[:34], str(holder[1])))
    h.append("</div>")
    chart = next((e for e in doc["exhibits"] if e.get("tipe") == "price_chart"), None)
    h.append("<div class='info'>")
    h.append(_price_chart(m["ticker"], m["tanggal"],
                          number=chart["n"] if chart else None,
                          source=(chart or {}).get("catatan_sumber")))
    h.append(sep + "</div>")
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
    # Key Financials sits under the narrative in the main column (design 5.4.2).
    # Without a "Key Financials" exhibit, the first non-chart exhibit that no
    # section places is the cover table (renumber puts it right after the chart).
    placed = {id(e) for b in doc["bagian"] for e in b.get("exhibit", [])}
    cover_tables = [e for e in doc["exhibits"]
                    if e.get("tipe") != "price_chart" and id(e) not in placed]
    key_fin = next((e for e in cover_tables if e.get("judul") == "Key Financials"),
                   cover_tables[0] if cover_tables else None)
    if key_fin:
        h.append(_table(key_fin))
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
