"""Renderer HTML laporan multipage A4. Brand Sektoral, bukan BRIDS.

Struktur: header → status → cover 2 kolom (data pasar + narasi) → Key
Financials → halaman 2-6 → metodologi + disclaimer. Chart SVG native dari
cache daily. Nomor halaman via CSS counter. Cetak via app/pdf.py (A4).

``render(doc, lang)`` writes the same stored document in Indonesian ("id",
the default) or English ("en"): the fixed words, labels and figures follow
``lang`` (app.report_lang, app.fmt); narrative prose stays as written.
"""
import base64
import contextvars
import functools
import html
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit
from . import cache as cache_mod
from . import exhibit_ids
from . import fmt
from . import idx_history
from . import prose_lang
from . import report_lang

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

# Sektoral Design System (docs: "Sektoral Design System Documentation").
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
# Warning surface for the draft banner (DESIGN.md warn-bg / warn-rule / warn-ink).
WARN_BG, WARN_RULE, WARN_INK = "#FFF4DB", "#E3A21A", "#7A4B00"
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

# Footer (Struktur-Template): "sectors.app" bottom left with the design's
# Morse rule after it; the disclosure line and the page number bottom right.
_FOOTER_BOX = ("box-sizing:border-box;height:3mm;white-space:nowrap;"
               "font-family:'Roboto',sans-serif;font-size:7.7pt;line-height:3mm;"
               "text-rendering:geometricPrecision;word-spacing:.05em;"
               "color:" + PRIMARY + ";")
PAGE_NUM = ("@page{size:A4;margin:12mm 8.5mm 14mm;"
            "@bottom-left{content:'sectors.app';width:88mm;font-weight:700;" + _FOOTER_BOX +
            "background-image:url('data:image/svg+xml;base64," + REPORT_MORSE + "');"
            "background-size:61.25mm 1mm;background-position:19mm center;"
            "background-repeat:no-repeat}"
            "@bottom-right{content:'See important disclosure at the back of this report'"
            " '\\2003' 'Page ' counter(page) ' of ' counter(pages);width:105mm;"
            "text-align:right;" + _FOOTER_BOX + "}}")


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
       "p{margin:0 0 3.4mm;text-align:left;line-height:1.3}"
       ".topbar{display:flex;justify-content:space-between;align-items:center;"
       "border-bottom:2px solid "
       + PRIMARY + ";padding-bottom:3px;font-size:7.7pt;color:" + PRIMARY + ";font-weight:600}"
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
       ".status{font-size:9.6pt;color:" + PRIMARY + ";font-weight:700;margin:5px 0 2px}"
       # Rating block: Roboto Black Italic on the highlight fill.
       ".rating-block{background:" + HIGHLIGHT + ";border-radius:3.4mm;padding:3.4mm;"
       "display:flex;flex-direction:column;align-items:center;gap:3.4mm;margin:0}"
       ".rating-head{text-align:center}"
       ".rating-label{font-size:30.7pt;color:" + PRIMARY + ";font-weight:900;font-style:italic;"
       "line-height:1.17}"
       ".rating-detail{font-size:9.6pt;color:" + PRIMARY + ";font-weight:900;font-style:italic;"
       "line-height:1.17}"
       ".rating-method{font-size:6.7pt;color:" + PRIMARY + ";margin-top:1.2mm;line-height:1.3}"
       ".rating-sep{display:block;width:92%;height:1px}"
       ".rating-row{display:flex;width:100%;gap:2mm;align-items:center;font-weight:700;"
       "color:" + PRIMARY + ";font-size:7.7pt;line-height:1.17}"
       ".rating-row span{flex:1 1 auto;min-width:0}.rating-row b{font-weight:700;white-space:nowrap}"
       ".rating-row b.na{font-style:italic}"
       ".rating-sub{font-size:9.6pt;font-weight:900;color:" + PRIMARY + ";text-align:center;"
       "line-height:1.17}"
       # Left-column exhibit (Figma "Information").
       ".info{padding:1.7mm 3.4mm;display:flex;flex-direction:column;gap:1.7mm}"
       ".info-title{font-size:7.7pt;line-height:1.2;color:" + INK + "}"
       ".info-src{font-size:5.8pt;font-style:italic;text-align:center;line-height:1.2}"
       ".info-note{font-size:6.7pt;line-height:1.2}"
       ".draft-banner{background:" + WARN_BG + ";border:1px solid " + WARN_RULE + ";color:" + WARN_INK + ";"
       "font-weight:700;padding:5px 8px;margin:5px 0;font-size:7.7pt}"
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
       "h2.sec{font-size:12pt;line-height:1.17;color:" + INK + ";font-weight:900;margin:0 0 2.5mm}"
       "h2.sec .num{color:" + INK + "}"
       "h2.sub,h3.sub{font-size:9.6pt;line-height:1.17;color:" + INK + ";font-weight:700;margin:0 0 1.7mm}"
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
       ".card-value{font-size:19.2pt;font-weight:700;line-height:1.17}"
       ".risks .card-title{margin-bottom:1.7mm}"
       ".risk-tag{font-size:7.7pt;font-weight:400;"
       "color:" + PRIMARY + "}"
       ".risk-src{font-size:5.8pt;font-style:italic;line-height:1.3;margin-top:1.2mm}"
       ".risk-head{margin-top:1.7mm}"
       ".exhibit{margin:0 0 3.4mm}"
       ".exhibit.keep{break-inside:avoid-page;page-break-inside:avoid}"
       # Own-history band charts sit two across (struktur Exhibits 12-13).
       ".band-pair,.ex-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);"
       "gap:3.4mm;align-items:start;margin:0 0 3.4mm;"
       "break-inside:avoid-page;page-break-inside:avoid}"
       ".pair-col{min-width:0}.pair-col>.exhibit:last-child{margin-bottom:0}"
       ".band-chart{display:block;width:100%;height:auto}"
       ".panel-text{font-size:6.7pt;line-height:1.3;margin:1.2mm 0 0;text-align:left}"
       # Table styling follows sectors-hackathon's .fin-table: a solid header
       # band, horizontal hairlines only (no vertical grid), spec zebra fill
       # and a ruled total line. The old full grid made every figure read as a
       # spreadsheet cell instead of a column.
       ".exhibit-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:7.7pt;"
       "margin:0;font-family:'Roboto',sans-serif;border:0}"
       ".exhibit-table th,.exhibit-table td{border:0;padding:1.05mm 1.7mm;"
       "vertical-align:middle;line-height:1.2;overflow-wrap:break-word;word-break:normal}"
       ".exhibit-table tbody.block:first-of-type tr:first-child td{border-top:0}"
       ".exhibit-table thead{display:table-header-group}"
       ".exhibit-table tbody{display:table-row-group}"
       ".exhibit-table tbody.block{break-inside:avoid-page;page-break-inside:avoid}"
       ".exhibit-table tr{break-inside:avoid-page;page-break-inside:avoid}"
       # Fixed layout: a long header wraps inside its column instead of
       # running into the next one.
       ".exhibit-table thead th{background:" + PRIMARY + ";color:#fff;font-weight:900;"
       "white-space:normal;overflow-wrap:normal;padding:1.3mm 1.7mm}"
       ".exhibit-table .cell-text{text-align:left}"
       ".exhibit-table .cell-num{text-align:right;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-date{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums}"
       ".exhibit-table .cell-num.short{white-space:nowrap}"
       ".exhibit-table td.cell-nm{color:" + MUT + ";font-weight:400}"
       ".exhibit-table tbody tr:nth-child(even) td{background:" + HIGHLIGHT + "}"
       ".exhibit-table tbody tr.section-row th{background:" + EVEN_ROW + ";color:" + PRIMARY + ";"
       "text-align:left;font-weight:700;letter-spacing:.04em;"
       "border-top:1px solid " + PRIMARY + ";"
       "padding:4px 6px;break-after:avoid-page}"
       ".exhibit-table tbody.block:first-of-type tr.section-row:first-child th{border-top:0}"
       ".exhibit-table tbody tr.total-row td{background:" + PAPER + ";font-weight:700;"
       "border-top:1px solid " + PRIMARY + "}"
       # Template highlights: the issuer row in peer tables, peer median and
       # average in bold, the base case of a sensitivity grid.
       ".exhibit-table tbody tr.issuer-row td{background:" + EVEN_ROW + ";font-weight:700}"
       ".exhibit-table tbody tr.summary-row td{font-weight:700;border-top:1px solid " + PRIMARY + "}"
       ".exhibit-table tbody tr.base-row td{font-weight:700}"
       ".exhibit-table tbody tr td.base-cell{background:" + EVEN_ROW + ";font-weight:700}"
       # Exhibit label carries the same brand tick as the section heads.
       ".exhibit-table caption{text-align:left;font-weight:700;font-size:9.6pt;line-height:1.17;"
       "color:" + INK + ";margin-bottom:1.7mm;font-family:'Roboto',sans-serif}"
       ".src{font-size:5.8pt;color:" + INK + ";margin:1.7mm 0 0;line-height:1.4;font-style:italic;"
       "text-align:left;overflow-wrap:anywhere}"
       ".nm-note{font-size:5.8pt;color:" + MUT + ";margin:0.6mm 0 0;line-height:1.35;font-style:italic;"
       "text-align:left;overflow-wrap:anywhere}"
       # Source appendix: one entry per exhibit, links shortened to host/file.
       ".src-list{margin:0;font-size:6.7pt;line-height:1.35}"
       ".src-list dt{font-weight:700;margin-top:1.4mm;break-after:avoid-page}"
       ".src-list dd{margin:0.4mm 0 0;overflow-wrap:anywhere;text-align:left}"
       ".src-list a{color:" + PRIMARY + ";text-decoration:none}"
       ".metric-chart{display:block;width:100%;height:180px}"
       ".chart-caption{font-weight:700;font-size:9.6pt;line-height:1.17;color:" + INK + ";margin-bottom:1.7mm}"
       ".research-card{border:1px solid " + RULE + ";"
       "padding:7px 9px;margin:9px 0;break-inside:avoid-page;page-break-inside:avoid}"
       ".research-card h3{color:" + PRIMARY + ";font-size:9.6pt;margin:0 0 4px}"
       ".research-card p{margin:3px 0;line-height:1.42}"
       ".research-card .research-cite{font-size:6.7pt;color:" + MUT + ";"
       "margin-top:6px;overflow-wrap:anywhere}"
       ".page{page-break-before:always}"
       ".analyst{font-size:7.7pt;margin-top:3mm;line-height:1.35}"
       ".section{margin-top:3.4mm}.section>.report-header{display:none}"
       "h2.sec{break-after:avoid-page;page-break-after:avoid}"
       ".small{font-size:7.7pt;color:" + MUT + "}"
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
       ".nm-note{font-size:10px;line-height:1.4}"
       ".grid-col .exhibit-table,.pair-col .exhibit-table{min-width:0}"
       # The cover's right column is narrower than 620px; its table must fit, not scroll.
       ".cover .exhibit-table{min-width:0}"
       ".cover .exhibit-table th,.cover .exhibit-table td{padding:6px 8px}}"
       "@media screen and (max-width:720px){body{padding:16px}"
       ".cover,.grid-2{flex-direction:column}.left,.right{width:100%}"
       ".band-pair,.ex-pair{grid-template-columns:minmax(0,1fr)}"
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


# The report language of the render in progress (see render()).
_LANG = contextvars.ContextVar("report_lang", default=report_lang.DEFAULT)


def _english():
    return _LANG.get() == "en"


def _say(id_text, en_text):
    """Fixed report wording in the render's language."""
    return en_text if _english() else id_text


def _lbl(text):
    """A label from the (Indonesian) report document, in the render's language."""
    return report_lang.label(text, _LANG.get())


def _title(ex):
    """An exhibit's title in the render's language."""
    return report_lang.title(ex, _LANG.get())


def _bracketed(text, whole=False):
    return fmt.bracket_negatives(text, whole=whole, lang=_LANG.get())


def _figures(text):
    """A short value from the report document with its figures in the render's language."""
    return fmt.localize(text, _LANG.get())


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


def _price_chart(ticker, as_of, number=None, source=None,
                 latest_close=None, latest_date=None):
    """Figma cover Exhibit 1: close (left axis, Rp) and performance relative to
    IHSG (right axis, %), dashed grid, black baseline, square legend.

    The relative line is read against its own zero: above it the issuer beat
    the index, a reading a shared rebased scale would flatten.
    """
    quote_day = None
    chart_as_of = as_of
    try:
        quote_day = date.fromisoformat(str(latest_date)[:10]) if latest_date else None
        report_day = date.fromisoformat(str(as_of)[:10])
        if quote_day:
            chart_as_of = min(report_day, quote_day + timedelta(days=1)).isoformat()
    except (TypeError, ValueError):
        quote_day = None
    window = _price_window(ticker, chart_as_of)
    if window is None:
        return _say("<p class='small'>Perbandingan harga belum tersedia: "
                    "kurang dari dua tanggal perdagangan yang sama di data Sectors.</p>",
                    "<p class='small'>Price comparison not available: fewer than two "
                    "common trading dates in Sectors data.</p>")

    dates, closes = list(window["price_dates"]), list(window["closes"])
    rel_dates, relative = list(window["rel_dates"]), list(window["relative"])
    if quote_day and isinstance(latest_close, (int, float)) and latest_close > 0:
        keep = [(day, close) for day, close in zip(dates, closes) if day <= quote_day]
        dates, closes = [day for day, _ in keep], [close for _, close in keep]
        if dates and dates[-1] == quote_day:
            closes[-1] = float(latest_close)
        elif not dates or dates[-1] < quote_day:
            dates.append(quote_day)
            closes.append(float(latest_close))
        aligned = [(day, value) for day, value in zip(rel_dates, relative) if day <= quote_day]
        rel_dates, relative = [day for day, _ in aligned], [value for _, value in aligned]
    if len(dates) < 2 or len(closes) < 2:
        return _say("<p class='small'>Perbandingan harga belum tersedia: "
                    "belum ada dua tanggal perdagangan sebelum tanggal harga laporan.</p>",
                    "<p class='small'>Price comparison not available: fewer than two "
                    "trading dates before the report's price date.</p>")
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
                     f"{fmt.rp(price_tick, lang=_LANG.get())}</text>"
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
                 f"{_say('Terakhir', 'Last')} {fmt.rp(closes[-1], lang=_LANG.get())}</text>")
    # A tick hugging the left edge would sit on the lowest price label.
    ticks = [day for day in _month_ticks(dates[0], dates[-1]) if x_of(day) - x0 >= 16]
    for index, day in enumerate(ticks):
        parts.append(f"<text x='{x_of(day):.1f}' y='{238 + 16 * (index % 2)}' text-anchor='middle' "
                     f"{label} fill='{INK}'>{_mon(day)}</text>")
    parts.append(f"<rect x='19' y='288' width='14' height='14' fill='{ISSUER_COLOR}'/>"
                 f"<text x='43' y='300' {label} fill='{INK}'>{_say('Harga (Rp, kiri)', 'Price (Rp, lhs)')}</text>"
                 f"<rect x='150' y='288' width='14' height='14' fill='{INDEX_COLOR}'/>"
                 f"<text x='172' y='300' {label} fill='{INK}'>"
                 f"{_say('Relatif vs IHSG (%, kanan)', 'Relative to JCI (%, rhs)')}</text>")

    span_months = max(1, round(days / 30.4))
    heading = _say(f"{ticker} relatif terhadap IHSG ({span_months} bulan, "
                   f"{_mon(dates[0])} s.d. {_mon(dates[-1])})",
                   f"{ticker} relative to the JCI ({span_months} months, "
                   f"{_mon(dates[0])} to {_mon(dates[-1])})")
    title = f"{'Exhibit ' + str(number) + '. ' if number else ''}{html.escape(heading)}"
    safe_ticker = html.escape(ticker)
    issuer_return, ihsg_return = window["issuer_return"], window["ihsg_return"]

    def pct(value):
        return f"{value:+.1f}" if _english() else f"{value:+.1f}".replace(".", ",")
    # The data source is the one actually plotted: IDX when its files exist.
    # It goes to the source appendix with the method notes; the footer is the
    # house line like every other exhibit.
    detail = window["source"] or fmt.provenance_detail(source or "Sectors")
    if rel_dates[0] != dates[0] or rel_dates[-1] != dates[-1]:
        detail += (f"; garis relatif mencakup {rel_dates[0].isoformat()} s.d. "
                   f"{rel_dates[-1].isoformat()} (cakupan IHSG)")
    if quote_day and isinstance(latest_close, (int, float)) and latest_close > 0:
        detail += f"; harga terakhir memakai kutipan laporan {quote_day.isoformat()}"
    detail += (f"; return harga dari {len(rel_dates)} tanggal perdagangan yang sama, "
               "tidak termasuk dividen")
    # The template asks for 12-24 months; say so when the data holds less.
    short_window = (_say(f". Riwayat harga harian yang tersedia hanya {span_months} bulan "
                         f"(sejak {_mon(dates[0])}); template meminta 12-24 bulan",
                         f". Daily price history covers only {span_months} months "
                         f"(since {_mon(dates[0])}); the template asks for 12-24 months")
                    if span_months < 12 else "")
    footer = (_source_line({"n": number, "judul": heading}, detail, title=heading) if number
              else f"<p class='src'>{html.escape(fmt.DEFAULT_SOURCE)}</p>")
    note = _say(f"Return harga sampai {rel_dates[-1].isoformat()}: "
                f"{safe_ticker} {pct(issuer_return)}%, IHSG {pct(ihsg_return)}%. "
                f"Selisih {pct(issuer_return - ihsg_return)} poin persentase",
                f"Price return to {rel_dates[-1].isoformat()}: "
                f"{safe_ticker} {pct(issuer_return)}%, JCI {pct(ihsg_return)}%. "
                f"Difference {pct(issuer_return - ihsg_return)} percentage points")
    chart_title = _say(f"Harga penutupan {safe_ticker} dan kinerja "
                       f"relatif terhadap IHSG, {dates[0].isoformat()} sampai {dates[-1].isoformat()}",
                       f"{safe_ticker} closing price and performance relative to the JCI, "
                       f"{dates[0].isoformat()} to {dates[-1].isoformat()}")
    return (
        f"<div class='info-title'>{title}</div>"
        f"<div class='info-note'>{note}"
        f"{short_window}</div>"
        "<svg class='price-chart' viewBox='0 0 360 320' width='360' height='320' "
        "style='display:block;width:100%;height:auto' role='img' aria-labelledby='price-chart-title'>"
        f"<title id='price-chart-title'>{chart_title}</title>"
        + "".join(parts) + "</svg>" + footer.replace("class='src'", "class='info-src'"))


# Column widths come from the cells, not the column count. Text is measured
# in em with Roboto's advance widths (app/assets/fonts), so the estimate holds
# at any font size; budgets are the printed table widths at 7.7 pt.
_EM_NARROW = frozenset("ijlI.,;:'!|")
_EM_SEMI = frozenset("frt()[]-/")
_EM_WIDE = frozenset("mwMW%@")
_CELL_PAD_EM = 1.25          # 1.7 mm padding on each side of a cell
_HEADER_BOLD = 1.06          # header row is Roboto Black
_TABLE_EM = {"full": 71.0,   # 193 mm content width
             "cover": 45.0,  # cover main column (65% less its gutter)
             "half": 35.0}   # one column of a two-up grid
_TEXT_FLOOR_EM = 7.0         # a wrapping column keeps ~14 characters a line
_COMPACT_EM = 11.0           # figures up to ~20 characters stay on one line
_RAGGED = 1.08               # word wrap leaves the end of each line short
_SOFT_MAX = 6                # row height ~ its tallest cell (smooth maximum)
_FIT = 1.06                  # safety margin on one-line widths


@functools.lru_cache(maxsize=8192)
def _em(text):
    """Printed width of `text` in em (Roboto Regular)."""
    total = 0.0
    for ch in text:
        if ch == " ":
            total += 0.25
        elif ch in _EM_NARROW:
            total += 0.24
        elif ch in _EM_SEMI:
            total += 0.34
        elif ch in _EM_WIDE:
            total += 0.82
        elif ch.isdigit():
            total += 0.56
        elif ch.isupper():
            total += 0.64
        else:
            total += 0.54
    return total


def _longest_word_em(text):
    return max((_em(word) for word in text.split()), default=0.0)


def _wrapped_lines(text, inner):
    """Lines `text` takes at `inner` em with greedy word wrap (long words break)."""
    inner = max(inner, 0.5)
    lines, used = 1, 0.0
    for word in text.split():
        width = _em(word)
        if used and used + 0.25 + width <= inner:
            used += 0.25 + width
            continue
        if used:
            lines += 1
        while width > inner:
            lines += 1
            width -= inner
        used = width
    return lines


def _header_lines(header, inner):
    """Lines a header takes at `inner` em (bold; may break after a slash)."""
    return _wrapped_lines(header.replace("/", "/ "), inner / _HEADER_BOLD)


def _header_width(header, lines):
    """Narrowest inner width (em) that keeps `header` within `lines` lines."""
    width = max(_em(header) * _HEADER_BOLD / lines,
                max((_em(p) for p in re.split(r"\s+|(?<=/)", header)), default=0.0) * _HEADER_BOLD)
    while _header_lines(header, width) > lines:
        width += 0.25
    return width


def _is_section_row(cells):
    return bool(cells) and cells[0].startswith("Blok ") and all(not c for c in cells[1:])


def _column_widths(cols, rows=(), context="full", kinds=None):
    """Percent widths for a table's <colgroup> (see _column_plan)."""
    return _column_plan(cols, rows, context, kinds)[0] if cols else []


def _column_plan(cols, rows, context, kinds=None):
    """Percent widths that give each column room in proportion to its content,
    plus which columns are compact figures and whether the table overflows.

    Figures and dates are compact: each keeps its widest value on one line.
    When everything fits on one line, each column gets its one-line width and
    the spare width is shared in proportion to typical cell length. Otherwise text columns start from a floor (their
    longest word, and at least ~14 characters) and the rest of the table goes,
    a step at a time, to the column whose growth most reduces the summed row
    heights; a last pass takes back width no row needs and hands it to the
    columns still short of one line. Deterministic for a given table.
    `kinds` overrides the column kinds read from `cols` and `rows` (an English
    table keeps the kinds of its Indonesian source).
    """
    n = len(cols)
    budget = _TABLE_EM.get(context, _TABLE_EM["full"])
    kinds = kinds or _column_kinds(cols, rows)
    headers = [str(col).strip() for col in cols]
    body = []
    for row in rows:
        cells = [str(row[i]).strip() if i < len(row) else "" for i in range(n)]
        if not _is_section_row(cells):
            body.append(cells)
    # One-line fits get a 6% margin: estimated glyph widths run slightly
    # short (capitals, bold total rows), and a word must never break inside.
    widest = [max((_em(cells[i]) for cells in body), default=0.0) * _FIT for i in range(n)]
    word = [max(_longest_word_em(cells[i]) for cells in body) * _FIT if body else 0.0
            for i in range(n)]
    compact = [k in ("num", "date") and widest[i] <= _COMPACT_EM for i, k in enumerate(kinds)]

    def needs(header_lines):
        """One-line width of each column; headers may wrap to `header_lines`."""
        need = [max(widest[i], _header_width(headers[i], header_lines)) + _CELL_PAD_EM
                for i in range(n)]
        # A run of figure columns (years, scenarios) reads best at one width.
        figures = [need[i] for i in range(n) if compact[i]]
        if len(figures) > 1 and max(figures) <= 1.6 * min(figures):
            need = [max(figures) if compact[i] else need[i] for i in range(n)]
        floor = [need[i] if compact[i] else
                 min(need[i], max(word[i], _header_width(headers[i], 99), _TEXT_FLOOR_EM)
                     + _CELL_PAD_EM)
                 for i in range(n)]
        return need, floor

    for header_lines in (2, 3, 99):
        need, floor = needs(header_lines)
        if sum(floor) <= budget:
            break

    overflow = sum(floor) > budget
    if sum(need) <= budget:
        # Spare width follows each column's typical (mean) cell, not its
        # longest one, so a single long cell does not widen a column of
        # short figures. Figure columns of one width stay equal.
        typical = [sum(_em(cells[i]) for cells in body if cells[i])
                   / max(1, sum(1 for cells in body if cells[i])) + _CELL_PAD_EM
                   for i in range(n)]
        equal = [i for i in range(n) if compact[i] and need[i] == max(need[j] for j in range(n)
                                                                        if compact[j])]
        if len(equal) > 1:
            typical = [max(typical[j] for j in equal) if i in equal else typical[i]
                       for i in range(n)]
        spare = budget - sum(need)
        widths = [need[i] + spare * typical[i] / sum(typical) for i in range(n)]
    elif sum(floor) >= budget:
        widths = floor
    else:
        widths = _fill_columns(floor, need, compact, headers, body, budget)
    total = sum(widths)
    percents = [round(w * 100 / total, 1) for w in widths]
    largest = percents.index(max(percents))
    percents[largest] = round(percents[largest] + 100 - sum(percents), 1)
    return percents, compact, overflow


def _fill_columns(floor, need, compact, headers, body, budget):
    """Spend `budget - sum(floor)` em on the wrapping columns (see _column_widths)."""
    n = len(floor)
    grow = [i for i in range(n) if not compact[i]]
    table = [[_em(h) * _HEADER_BOLD for h in headers]] + [[_em(c) for c in cells] for cells in body]
    table = [[w * _RAGGED for w in row] for row in table]
    widths = list(floor)

    def height(row, cols):
        return (1 + sum((row[i] / max(cols[i] - _CELL_PAD_EM, 0.5)) ** _SOFT_MAX
                        for i in range(n))) ** (1 / _SOFT_MAX)

    left = budget - sum(widths)
    step = max(0.25, left / 80)
    while left > 1e-9:
        size = min(step, left)
        base = sum(height(row, widths) for row in table)
        best, gain = None, 0.0
        for i in grow:
            trial = widths[:]
            trial[i] += size
            delta = base - sum(height(row, trial) for row in table)
            if best is None or delta > gain + 1e-12:
                best, gain = i, delta
        widths[best] += size
        left -= size

    # Take back width no row needs (row height is its tallest cell), then give
    # it to the columns closest to fitting their content on one line.
    def lines(i, w):
        # Real glyph runs vary, so wrapping text is estimated a little early;
        # figures are sized to fit and only their header may wrap.
        inner = (w - _CELL_PAD_EM) * (1.0 if compact[i] else 0.96)
        return [_header_lines(headers[i], inner)] + [_wrapped_lines(cells[i], inner)
                                                     for cells in body]

    per_col = {i: lines(i, widths[i]) for i in range(n)}
    rows_h = [max(per_col[i][r] for i in range(n)) for r in range(len(body) + 1)]
    freed = 0.0
    for i in grow:
        w = widths[i]
        while w - 0.25 >= floor[i] and all(
                h <= cap for h, cap in zip(lines(i, w - 0.25), rows_h)):
            w -= 0.25
        freed += widths[i] - w
        widths[i] = w
    # Columns closest to fitting on one line first (a label one word short of
    # its line), then whatever is left in proportion to the widths.
    for i in sorted(grow, key=lambda i: (need[i] - widths[i], i)):
        give = min(max(0.0, need[i] - widths[i]), freed)
        widths[i] += give
        freed -= give
    total = sum(widths)
    return [w + freed * w / total for w in widths]


_NUMERIC_CELL = re.compile(r"^(?:Rp|USD\s*)?[\d(~−<>-]|^(?:n\.a\.|n\.m\.|NA)$")


def _column_kinds(cols, rows):
    kinds = []
    for index, col in enumerate(cols):
        label = str(col).strip().lower()
        values = [str(row[index]).strip() for row in rows if index < len(row) and row[index] != ""]
        if index == 0 or label in {"dasar", "kenapa penting", "arah", "tahap"} or "terakhir" in label:
            kinds.append("text")
        elif label == "waktu" or (values and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in values)):
            kinds.append("date")
        # A figure is short: a sentence that opens with a number is still text.
        elif values and sum(bool(_NUMERIC_CELL.match(v)) and len(v) <= 24
                            for v in values) >= len(values) / 2:
            kinds.append("num")
        else:
            kinds.append("text")
    return kinds


# Every exhibit footer is the house source line and nothing else (spec §5.5,
# Struktur-Template "Exhibit labeling dan sourcing"). Each exhibit's own
# provenance and caveats are collected while rendering and printed once, in
# the source appendix at the end of the report. The one exception is a table's
# n.m. reason, printed under its source line (``_nm_note``).
_NOTES = contextvars.ContextVar("exhibit_notes", default=None)


def _source_line(ex, detail=None, title=None):
    notes = _NOTES.get()
    if notes is not None:
        title = report_lang.title(ex, _LANG.get()) if title is None else title
        notes.append((ex.get("n"), str(title or ""),
                      fmt.provenance_detail(ex.get("catatan_sumber") if detail is None else detail)))
    return f"<p class='src'>{html.escape(fmt.DEFAULT_SOURCE)}</p>"


_NM_REASON = re.compile(r"n\.\s?m\.|tidak bermakna|not meaningful|(?:belum|tidak) dimodelkan", re.I)


def _nm_note(ex):
    """Why a table shows n.m.: the part of its note that says so, printed under
    the source line (the n.m. rule of spec/Instruksi-Report-v3.md needs the
    reason where the reader sees the cell). The rest of the provenance stays
    in the source appendix."""
    parts = []
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z])", fmt.provenance_detail(ex.get("catatan_sumber"))):
        if not _NM_REASON.search(sentence):
            continue
        at = sentence.find("n.m. pada")
        if at >= 0:
            parts.append(sentence[at:])
        else:
            parts.extend(c.strip() for c in sentence.split(";") if _NM_REASON.search(c))
    parts = [part for part in parts if part.strip()]
    english = report_lang.nm_note(parts, "en") if _english() else None
    if english:
        text = " ".join(report_lang.plain(part).strip().rstrip(".") + "." for part in english)
        return f"<p class='nm-note'>{html.escape(_bracketed(text))}</p>"
    text = " ".join(part.strip().rstrip(".") + "." for part in parts)
    return f"<p class='nm-note'>{html.escape(fmt.bracket_negatives(text))}</p>" if text else ""


def _header_cell(col, kind):
    text = html.escape(str(col)).replace("/", "/<wbr>")
    return f"<th scope='col' class='cell-{kind}'>{text}</th>"


_MONTHS_ID = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _month(day):
    return (_MONTHS_EN if _english() else _MONTHS_ID)[day.month - 1]


def _mon(day, with_day=False):
    """Short month label in the report language: Sep-24 (or 24-Sep-26 with the day)."""
    label = f"{_month(day)}-{day:%y}"
    return f"{day:%d}-{label}" if with_day else label


_STEP_NUMBER = re.compile(r"[-+]?\d+(?:,\d+)?")


def _middle_of_steps(labels):
    """Index of the middle label when labels are evenly spaced steps around a
    base (g 2,5% / 3,5% / 4,5%), else None."""
    values = []
    for label in labels:
        found = _STEP_NUMBER.findall(str(label))
        if len(found) != 1:
            return None
        values.append(float(found[0].replace(",", ".")))
    if len(values) < 3 or len(values) % 2 == 0:
        return None
    steps = {round(b - a, 6) for a, b in zip(values, values[1:])}
    return len(values) // 2 if len(steps) == 1 and 0 not in steps else None


def _row_marks(ex, cols, rows):
    """Rows and the cell the template highlights (Struktur-Template slides 4-5).

    - issuer row: the first cell says "(emiten)";
    - peer summary rows: "Median ..."/"Rata-rata ..." in a table with an issuer row;
    - sensitivity base: the row labelled "(basis)"/"base" (or the middle of
      evenly spaced row steps), its cell in the column headed dasar/basis/base
      (or the middle of evenly spaced column steps). A builder may set
      data["base"] = {"row": i, "col": j} (column j counts the label column).
    """
    marks = {"rows": {}, "cell": None}
    firsts = [str(row[0]).strip() if row else "" for row in rows]
    issuer = [i for i, cell in enumerate(firsts) if "(emiten)" in cell.lower()]
    for i in issuer:
        marks["rows"][i] = "issuer-row"
    if issuer:
        for i, cell in enumerate(firsts):
            if re.match(r"^(median|rata-rata|average)\b", cell, re.I):
                marks["rows"][i] = "summary-row"
    base = (ex.get("data") or {}).get("base") or {}
    sensitivity = re.match(r"^sensitivit", str(ex.get("judul") or ""), re.I)
    row = base.get("row")
    if row is None:
        row = next((i for i, cell in enumerate(firsts)
                    if re.search(r"\(basis\)|\bbase\b", cell, re.I)), None)
    if row is None and sensitivity:
        row = _middle_of_steps(firsts)
    col = base.get("col")
    if col is None and len(cols) > 1:
        col = next((j for j, head in enumerate(cols) if j and
                    re.search(r"\b(dasar|basis|base)\b", str(head), re.I)), None)
        if col is None and sensitivity:
            middle = _middle_of_steps(cols[1:])
            col = None if middle is None else middle + 1
    if row is not None and 0 <= row < len(rows):
        marks["rows"][row] = "base-row"
        if col is not None:
            marks["cell"] = (row, col)
    return marks


def _cell(row, i, english):
    if i >= len(row):
        return ""
    if isinstance(english, list) and i < len(english) and isinstance(english[i], str):
        return english[i]
    return _lbl(str(row[i]))


def _table(ex, context="full"):
    """Exhibit table; `context` is where it sits (full width, cover column, half grid).

    Column kinds, row marks and section rows are read from the stored
    (Indonesian) cells; the printed cells are in the render's language."""
    data = ex["data"]
    cols, rows = data["cols"], data["rows"]
    kinds = _column_kinds(cols, rows)
    shown_cols = [_lbl(str(col)) for col in cols]
    # A cell the English prose run wrote itself (app.prose_lang ``rows_en``)
    # is printed as written; any other through its report_lang label.
    english = (data.get("rows_en") if _english() else None) or []
    shown = [[_cell(row, i, english[r] if r < len(english) else None) for i in range(len(cols))]
             for r, row in enumerate(rows)]
    if _english() and exhibit_ids.is_exhibit(ex, exhibit_ids.METHOD_CHAIN):
        # A Method Chain reason joins release limitations with "; ": the
        # host's English for them (app.host_lang), as the web app shows it.
        from . import host_lang
        for row, cells in zip(rows, shown):
            if len(row) == len(cols) and cells:
                cells[-1] = host_lang.english(str(row[-1])) or cells[-1]
    body_rows = [cells for row, cells in zip(rows, shown)
                 if not _is_section_row([str(row[i]) if i < len(row) else "" for i in range(len(cols))])]
    widths = _column_widths(shown_cols, body_rows, context, kinds)
    colgroup = "".join(f"<col style='width:{width}%'>" for width in widths)
    head = "".join(_header_cell(col, kind) for col, kind in zip(shown_cols, kinds))
    marks = _row_marks(ex, cols, rows)
    groups = [[]]
    has_nm = False
    for index, row in enumerate(rows):
        cells = [str(row[i]) if i < len(row) else "" for i in range(len(cols))]
        if _is_section_row(cells):
            if groups[-1]:
                groups.append([])
            groups[-1].append("<tr class='section-row'>"
                              f"<th scope='rowgroup' colspan='{len(cols)}'>{html.escape(shown[index][0])}</th></tr>")
            continue
        total = bool(re.match(r"^(?:Jumlah |Total |\(=\) |FCFF$|PV FCFF$|Laba bersih$|Nilai skenario gabungan$|WACC$)",
                              cells[0], re.I))
        cells = shown[index]
        kind_of_row = marks["rows"].get(index) or ("total-row" if total else "")
        classes = f" class='{kind_of_row}'" if kind_of_row else ""
        rendered = []
        for col, (cell, kind) in enumerate(zip(cells, kinds)):
            # Spec §5.5: negative figures in brackets, bare or as inline money.
            cell = fmt.bracket_negatives(cell, whole=True, lang=_LANG.get())
            if kind == "num" and len(cell) > 24 and not _NUMERIC_CELL.match(cell):
                kind = "text"
            short = " short" if kind == "num" and len(cell) <= 13 and " " not in cell else ""
            base = " base-cell" if (index, col) == marks["cell"] else ""
            # A missing figure recedes so the reported ones carry the table.
            muted = " cell-nm" if col and cell.strip() in ("n.m.", "n.a.", "NA") else ""
            has_nm = has_nm or (col and cell.strip() == "n.m.")
            rendered.append(f"<td class='cell-{kind}{short}{base}{muted}'>{html.escape(cell)}</td>")
        groups[-1].append(f"<tr{classes}>" + "".join(rendered) + "</tr>")
    body = "".join(f"<tbody class='block'>{''.join(group)}</tbody>" for group in groups if group)
    # A table that fits one page (about 40 of these rows) stays whole, so it
    # never continues on the next page without its title; only a longer one
    # breaks, with its header row repeated.
    keep = " keep" if len(rows) <= 40 else ""
    return (f"<div class='exhibit{keep}'><table class='exhibit-table'>"
            f"<caption>Exhibit {ex['n']}. {html.escape(_bracketed(_title(ex)))}</caption>"
            f"<colgroup>{colgroup}</colgroup><thead><tr>{head}</tr></thead>"
            f"{body}</table>{_source_line(ex)}{_nm_note(ex) if has_nm else ''}</div>")


def _nice_max(value):
    """Round a positive axis top up to 1, 2, 2.5 or 5 x 10^k."""
    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    return next(step * power for step in (1, 2, 2.5, 5, 10) if step * power >= value)


def _short_number(value):
    """Compact bar label: 55.800.818 -> 55,8 jt; 6.524 -> 6.524."""
    magnitude = abs(value)
    lang = _LANG.get()
    if magnitude < 100:
        return fmt.num(value, 1, lang)  # ratios such as DER 0,9x
    suffixes = (" tn", " bn", " mn") if lang == "en" else (" T", " M", " jt")
    for size, suffix in zip((1e12, 1e9, 1e6), suffixes):
        if magnitude >= size * 10 or (magnitude >= size and size >= 1e9):
            return fmt.num(value / size, 1, lang) + suffix
    return fmt.rp(round(value), lang=lang)


def _mini_chart(ox, oy, w, h, title, labels, bars, line, forecast, line_label=None,
                bar_unit="", line_unit="%"):
    """One quadrant: bars (actual solid blue, forecast light blue), optional
    secondary line on its own scale, dashed grid and a black zero baseline.
    `line_label` names the line in the corner (the 2x2 grid; a single panel
    names it in its legend instead)."""
    out = [f"<text x='{ox}' y='{oy + 11}' font-size='11' font-weight='700' "
           f"fill='{INK}'>{html.escape(_lbl(title))}</text>"]
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
    # Value labels shrink when the widest would reach its neighbour's.
    texts = [f"{_short_number(v)}{bar_unit}" for v in bars if isinstance(v, (int, float))]
    texts += [_line_value(v, line_unit) for v in line or [] if isinstance(v, (int, float))]
    widest = max((_em(t) for t in texts), default=0.0)
    scale = min(1.0, slot * 0.92 / (widest * 7.5)) if widest else 1.0
    bar_font, line_font = max(5.5, 7.5 * scale), max(5.5, 7.0 * scale)
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
                       f"font-size='{bar_font:.1f}' font-weight='500' fill='{fill}'>"
                       f"{_short_number(v)}{bar_unit}</text>")
        out.append(f"<text x='{cx:.1f}' y='{base + 13}' text-anchor='middle' font-size='8' "
                   f"fill='{INK}'>{html.escape(_lbl(str(label)))}</text>")
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
                       f"<text x='{x:.1f}' y='{y - 5:.1f}' text-anchor='middle' font-size='{line_font:.1f}' "
                       f"fill='{INK}'>{html.escape(_line_value(v, line_unit))}</text>")
        if line_label:
            out.append(f"<text x='{ox + w}' y='{oy + 11}' text-anchor='end' font-size='8' "
                       f"fill='{INK}'>{_say('garis', 'line')}: {html.escape(_lbl(line_label))}</text>")
    return "".join(out)


def _line_value(value, unit="%"):
    """A line point's label: '12,4%' for a percentage line; a unit cost
    ('US$/lb') in two decimals, negatives in brackets (a by-product credit
    larger than the cost gives a negative C1)."""
    if unit == "%":
        return f"{fmt.num(value, 1, _LANG.get())}%"
    text = fmt.num(abs(value), 2, _LANG.get())
    return f"({text})" if value < 0 else text


def _series_names(series):
    """Bar and line names from the builder's series label, "Bar (unit) & line"
    (e.g. "Ekuitas (Rp) & ROE"); explicit bar_label/line_label keys win."""
    bar, _, line = str(series.get("label") or "").partition(" & ")
    bar = str(series.get("bar_label") or bar).strip()
    line = str(series.get("line_label") or line).strip()
    return bar, line


def _bar_unit(series):
    return "%" if series.get("bar_unit") == "%" else ""


def _legend(items, x, y, width):
    """Swatch + text legend items left to right, wrapping to a second row."""
    out, row_y = [], y
    for color, text in items:
        size = 12 + _em(text) * 8 + 12
        if x > 0 and x + size > width:
            x, row_y = 0, row_y + 12
        out.append(f"<rect x='{x:.1f}' y='{row_y}' width='8' height='8' fill='{color}'/>"
                   f"<text x='{x + 12:.1f}' y='{row_y + 7}' font-size='8' fill='{INK}'>"
                   f"{html.escape(text)}</text>")
        x += size
    return "".join(out), row_y + 12 - y


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
             f"{html.escape(_title(ex))}</div>",
             f"<svg class='combo-chart' viewBox='0 0 {2 * w + gap} {height}' role='img' "
             f"aria-label='{html.escape(_title(ex))}' style='display:block;width:100%;height:auto'>"]
    for idx, s in enumerate(series):
        title = str(s.get("label") or "")
        parts.append(_mini_chart((idx % 2) * (w + gap), (idx // 2) * (h + gap), w, h, title,
                                 labels, s.get("bars") or [], s.get("line") or [],
                                 s.get("is_forecast") or [], _series_names(s)[1] or None,
                                 _bar_unit(s)))
    ly = height - 8
    parts.append(f"<rect x='0' y='{ly - 7}' width='8' height='8' fill='{PRIMARY}'/>"
                 f"<text x='12' y='{ly}' font-size='8' fill='{INK}'>{_say('Aktual', 'Actual')}</text>"
                 f"<rect x='62' y='{ly - 7}' width='8' height='8' fill='{EVEN_ROW}'/>"
                 f"<text x='74' y='{ly}' font-size='8' fill='{INK}'>{_say('Proyeksi', 'Forecast')}</text>"
                 f"<rect x='130' y='{ly - 7}' width='8' height='8' fill='{SERIES[3]}'/>"
                 f"<text x='142' y='{ly}' font-size='8' fill='{INK}'>"
                 f"{_say('Garis (sumbu sendiri)', 'Line (own axis)')}</text>")
    parts.append("</svg>")
    parts.append(_source_line(ex) + "</div>")
    return "".join(parts)


def _combo_panel(ex):
    """Struktur Exhibits 4-7: one quadrant, its narrative directly under the
    chart, and the source line."""
    data = ex.get("data") or {}
    series = (data.get("series") or [{}])[0]
    labels = data.get("cols") or []
    title = str(series.get("label") or "")
    # The legend names the plotted series as the builder labels them
    # ("Ekuitas (Rp) & ROE": bars Ekuitas, line ROE); the unit stays in the title.
    bar, line = _series_names(series)
    bar = _lbl(re.sub(r"\s*\([^)]*\)", "", bar).strip() or "Nilai")
    line = _lbl(line)
    forecast = series.get("is_forecast") or []
    plotted = [bool(forecast[i]) if i < len(forecast) else False
               for i, v in enumerate(series.get("bars") or []) if isinstance(v, (int, float))]
    items = []
    if False in plotted:
        items.append((PRIMARY, f"{bar} {_say('aktual', 'actual')}"))
    if True in plotted:
        items.append((EVEN_ROW, f"{bar} {_say('proyeksi', 'forecast')}"))
    if sum(isinstance(v, (int, float)) for v in series.get("line") or []) >= 2:
        items.append((SERIES[3], f"{line[:1].upper() + line[1:] if line else _say('Garis', 'Line')} "
                                 f"({series.get('line_unit') or '%'}, {_say('sumbu kanan', 'rhs')})"))
    w, h = 360, 190
    legend, legend_h = _legend(items, 0, h + 3, w)
    parts = [f"<div class='exhibit keep panel'><div class='chart-caption'>Exhibit {ex['n']}. "
             f"{html.escape(_title(ex))}</div>",
             f"<svg class='combo-chart' viewBox='0 0 {w} {h + 4 + legend_h}' role='img' "
             f"aria-label='{html.escape(_title(ex))}' style='display:block;width:100%;height:auto'>",
             _mini_chart(0, 0, w, h, title, labels, series.get("bars") or [],
                         series.get("line") or [], series.get("is_forecast") or [],
                         bar_unit=_bar_unit(series), line_unit=series.get("line_unit") or "%"),
             legend,
             "</svg>", _source_line(ex)]
    # The source line sits right under the chart; the panel's narrative
    # follows it, still inside the panel (Struktur-Template Exhibits 4-7).
    if ex.get("narasi"):
        parts.append(f"<p class='panel-text'>{html.escape(ex['narasi'])}</p>")
    parts.append("</div>")
    return "".join(parts)


_SCALES = (("ribu", 1e3), ("juta", 1e6), ("miliar", 1e9), ("triliun", 1e12))


def _bar_scale(unit, values):
    """Display unit and divisor for raw values labelled `unit` ("Rp miliar",
    "US$ juta"): the stated scale, stepped up while the largest value would
    need five or more integer digits (Rp107.923 miliar reads Rp107,9 triliun)."""
    words = [name for name, _ in _SCALES]
    found = next((name for name in words if re.search(rf"\b{name}\b", unit)), None)
    if found is None:
        return unit, 1e6
    currency = unit.replace(found, "").strip()
    index = words.index(found)
    peak = max((abs(v) for v in values), default=0.0)
    while index + 1 < len(words) and peak / _SCALES[index][1] >= 10_000:
        # US$ has no "triliun" in house style; billions stay "miliar".
        if currency.startswith("US$") and words[index + 1] == "triliun":
            break
        index += 1
    return f"{currency} {words[index]}".strip(), _SCALES[index][1]


def _bar_value(value):
    text = fmt.num(abs(value), 1, _LANG.get())
    return f"({text})" if value < 0 else text


def _bar_chart(ex):
    """Prior vs current bars per metric. Values are labelled in the chart's
    unit with one decimal; a label wider than its bar pair's spacing shrinks,
    then alternates above/below so neighbours never overlap."""
    data = ex["data"]
    rows = data["rows"][:6]
    raw = [row.get(key) or 0 for row in rows for key in ("prior", "current")]
    unit, divisor = _bar_scale(str(data.get("unit") or ""), raw)
    top = _nice_max(max([v / divisor for v in raw] + [1e-9]))
    parts = [f"<div class='exhibit keep'><div class='chart-caption'>Exhibit {ex['n']}. "
             f"{html.escape(_title(ex))}</div>",
             "<svg class='metric-chart' viewBox='0 0 780 205' role='img' "
             f"aria-label='{html.escape(_title(ex))}'>"]
    for i in range(1, 4):
        gy = 164 - 112 * i / 3
        parts.append(f"<line x1='35' x2='750' y1='{gy:.1f}' y2='{gy:.1f}' stroke='{GRID}' "
                     "stroke-width='0.8' stroke-dasharray='3 3'/>")
    slot = 715 / max(len(rows), 1)
    bar_w = min(63.0, slot * 0.4)
    labels = [_bar_value((row.get(key) or 0) / divisor) for row in rows
              for key in ("prior", "current")]
    # Centres of neighbouring bars are bar_w + 7 apart; labels need that room.
    font = 12.0
    widest = max((_em(label) for label in labels), default=0.0)
    while font > 9 and widest * font > bar_w + 5:
        font -= 0.5
    stagger = widest * font > bar_w + 5
    for i, row in enumerate(rows):
        center = 35 + slot * (i + 0.5)
        for j, (x, key, color) in enumerate(((center - bar_w - 3.5, "prior", EVEN_ROW),
                                             (center + 3.5, "current", PRIMARY))):
            value = (row.get(key) or 0) / divisor
            height = max(1.5, 112 * max(0.0, value) / top)
            y = 164 - height
            parts.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' "
                         f"height='{height:.1f}' fill='{color}'/>")
            inside = height >= 18 + (14 if stagger else 0)
            fill = ("#FFFFFF" if color == PRIMARY else INK) if inside else INK
            ty = y + 13 if inside else max(13, y - 5)
            if stagger:
                ty += 14 * j if inside else -14 * (1 - j)
            parts.append(f"<text x='{x + bar_w / 2:.1f}' y='{max(11, ty):.1f}' "
                         f"text-anchor='middle' font-size='{font:g}' font-weight='500' "
                         f"fill='{fill}'>{html.escape(_bar_value(value))}</text>")
        parts.append(f"<text x='{center:.1f}' y='185' text-anchor='middle' "
                     f"font-size='13' fill='{INK}'>{html.escape(_lbl(str(row['label'])))}</text>")
    parts.append("<line x1='35' x2='750' y1='164' y2='164' stroke='#000000' stroke-width='1'/>")
    parts.append(f"<rect x='34' y='15' width='12' height='12' fill='{EVEN_ROW}'/>")
    parts.append(f"<text x='51' y='26' font-size='13'>{html.escape(_lbl(data['prior_label']))}</text>")
    parts.append(f"<rect x='130' y='15' width='12' height='12' fill='{PRIMARY}'/>")
    parts.append(f"<text x='147' y='26' font-size='13'>{html.escape(_lbl(data['current_label']))}</text>")
    parts.append(f"<text x='745' y='26' text-anchor='end' font-size='12' "
                 f"fill='{INK}'>{html.escape(_lbl(unit))}</text>")
    parts.append("</svg>")
    parts.append(_source_line(ex) + "</div>")
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
             f"{html.escape(_title(ex))}</div>",
             "<svg class='band-chart' viewBox='0 0 360 190' role='img' "
             f"aria-label='{html.escape(_title(ex))}'>"]
    for i in range(4):
        v = hi - i * (hi - lo) / 3
        gy = y(v)
        parts.append(f"<line x1='{x0}' x2='{x1}' y1='{gy:.1f}' y2='{gy:.1f}' stroke='{GRID}' "
                     "stroke-dasharray='3 3'/>"
                     f"<text x='4' y='{gy + 3:.1f}' {label} fill='{INK}'>{html.escape(fmt.mult(v, lang=_LANG.get()))}</text>")
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
                     f"fill='{INK}'>{_mon(d, with_day=True)}</text>")
    legend_y = 182
    # A longer multiple name (EV/EBITDA, EV/Sales substituting P/E or P/BV)
    # moves the rest of the legend right so the labels do not overlap.
    dx = max(0, round(62 + 5.8 * len(str(data["label"])) + 8 - 100))
    parts.append(f"<line x1='40' x2='58' y1='{legend_y - 4}' y2='{legend_y - 4}' stroke='{PRIMARY}' stroke-width='2'/>"
                 f"<text x='62' y='{legend_y}' {label} fill='{INK}'>{html.escape(data['label'])}</text>"
                 f"<line x1='{100 + dx}' x2='{118 + dx}' y1='{legend_y - 4}' y2='{legend_y - 4}' stroke='{INK}' stroke-dasharray='6 4'/>"
                 f"<text x='{122 + dx}' y='{legend_y}' {label} fill='{INK}'>Mean {html.escape(fmt.mult(data['mean'], lang=_LANG.get()))}</text>"
                 f"<line x1='{190 + dx}' x2='{208 + dx}' y1='{legend_y - 4}' y2='{legend_y - 4}' stroke='{INK}' stroke-dasharray='1.5 3'/>"
                 f"<text x='{212 + dx}' y='{legend_y}' {label} fill='{INK}'>Median {html.escape(fmt.mult(data['median'], lang=_LANG.get()))}</text>"
                 f"<text x='{290 + dx}' y='{legend_y}' {label} fill='{INK}'>{_say('Kini', 'Now')} p{data['percentile']:.0f}</text>")
    parts.append("</svg>")
    parts.append(_source_line(ex) + "</div>")
    return "".join(parts)


# Two exhibits side by side (spec/GMFI-Company-Update-contoh.pdf pages 2-7).
# Consecutive exhibits of a section that read well in half the text block
# may share a row, left then right; the right column may stack two short
# exhibits against a taller one on the left. Among the possible rows, the
# layout with the least printed height wins (a pair counts 5% lighter, so a
# near tie goes to the pair). Heights are print estimates in mm.
_MM_PER_PT = 25.4 / 72
_LINE_MM = 7.7 * 1.2 * _MM_PER_PT          # one line of table text
_ROW_PAD_MM = 3.4                          # 1.7 mm cell padding top and bottom
_TEXT_MM = 193.0                           # A4 less the 8.5 mm side margins
_GAP_MM = 3.4
_HALF_MM = (_TEXT_MM - _GAP_MM) / 2        # one column of a pair
_HALF_CHARTS = {"band_chart": 190 / 360, "combo_panel": 206 / 360}  # height/width
_PAIR_WEIGHT = 0.95


def _table_shape(ex, context):
    """Estimated lines per body row, header lines, height (mm) and overflow."""
    cols, rows = ex["data"]["cols"], ex["data"]["rows"]
    percents, compact, overflow = _column_plan(cols, rows, context)
    budget = _TABLE_EM[context]
    inner = [p / 100 * budget - _CELL_PAD_EM for p in percents]
    header = max(_header_lines(str(col).strip(), inner[i]) for i, col in enumerate(cols))
    lines, sections = [], 0
    for row in rows:
        cells = [str(row[i]).strip() if i < len(row) else "" for i in range(len(cols))]
        if _is_section_row(cells):
            sections += 1
            continue
        lines.append(max(1 if compact[i] else _wrapped_lines(cell, inner[i])
                         for i, cell in enumerate(cells)))
    caption = _wrapped_lines(f"Exhibit {ex.get('n')}. {ex.get('judul') or ''}",
                             budget * 7.7 / 9.6 / _HEADER_BOLD)
    height = (caption * 9.6 * 1.17 * _MM_PER_PT + 1.7 + header * _LINE_MM + _ROW_PAD_MM
              + sum(n * _LINE_MM + _ROW_PAD_MM for n in lines) + sections * 5.4 + 4.6)
    return lines, header, height, overflow


def _chart_height(ex, width_mm):
    text = 0.0
    if ex.get("narasi"):
        per_line = width_mm / (6.7 * _MM_PER_PT) / 0.5
        text = _wrapped_lines(str(ex["narasi"]), per_line) * 6.7 * 1.3 * _MM_PER_PT + 1.2
    return 5.7 + width_mm * _HALF_CHARTS[ex["tipe"]] + 4.6 + text


def _half_height(ex):
    """Height in mm of `ex` at half width, or None when it needs the full width.

    Tables qualify when, at half width, every figure stays on one line, no
    row wraps past three lines, rows average at most 1.5 lines and headers
    stay within three: figure tables and short two-column tables, not prose.
    """
    if ex.get("tipe") in _HALF_CHARTS:
        return _chart_height(ex, _HALF_MM)
    data = ex.get("data")
    if (ex.get("tipe") in ("bar_chart", "combo_chart", "price_chart") or not isinstance(data, dict)
            or not data.get("cols") or not data.get("rows")):
        return None
    lines, header, height, overflow = _table_shape(ex, "half")
    if overflow or header > 3 or not lines or max(lines) > 3 or sum(lines) > 1.5 * len(lines):
        return None
    return height


def _full_height(ex):
    if ex.get("tipe") in _HALF_CHARTS:
        return _chart_height(ex, _TEXT_MM)
    return _table_shape(ex, "full")[2]


def _pair_rows(exs):
    """Rows for `exs` as index tuples: (i,) full width, (i, j) or (i, j, k)
    with i on the left and j (over k) on the right."""
    count = len(exs)
    half = [_half_height(ex) for ex in exs]
    full = [_full_height(ex) if half[i] is not None else 0.0 for i, ex in enumerate(exs)]
    best, pick = [0.0] * (count + 1), [()] * (count + 1)
    for i in range(count - 1, -1, -1):
        options = [(full[i] + best[i + 1], (i,))]
        if half[i] is not None and i + 1 < count and half[i + 1] is not None:
            options.append((_PAIR_WEIGHT * max(half[i], half[i + 1]) + best[i + 2], (i, i + 1)))
            stack = half[i + 1] + _GAP_MM + half[i + 2] if i + 2 < count and half[i + 2] else None
            if stack is not None and stack <= 1.2 * half[i]:
                options.append((_PAIR_WEIGHT * max(half[i], stack) + best[i + 3], (i, i + 1, i + 2)))
        best[i], pick[i] = min(options, key=lambda option: (round(option[0], 6), -len(option[1])))
    rows, i = [], 0
    while i < count:
        rows.append(pick[i])
        i = pick[i][-1] + 1
    return rows


def _exhibits_paired(exs):
    """Render exhibits in order, two across where the pair layout wins."""
    out = []
    for row in _pair_rows(exs):
        if len(row) == 1:
            out.append(_exhibit(exs[row[0]]))
            continue
        charts = all(exs[j].get("tipe") in _HALF_CHARTS for j in row)
        out.append(f"<div class='{'band-pair' if charts else 'ex-pair'}'>"
                   f"<div class='pair-col'>{_exhibit(exs[row[0]], 'half')}</div>"
                   f"<div class='pair-col'>{''.join(_exhibit(exs[j], 'half') for j in row[1:])}"
                   "</div></div>")
    return "".join(out)


def _exhibit(ex, context="full"):
    t = ex.get("tipe")
    if t == "band_chart":
        return _band_chart(ex)
    if t == "combo_panel":
        return _combo_panel(ex)
    if t == "bar_chart":
        return _bar_chart(ex)
    if t == "combo_chart":
        return _combo_chart(ex)
    return _table(ex, context)


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
            f"aria-label='Sektoral'>{LOGO_SVG}</span></div>")


def _display_date(report_date):
    """Header date as in the Figma header, "DD Mon YYYY" (24 Sep 2026)."""
    try:
        day = date.fromisoformat(str(report_date)[:10])
    except (TypeError, ValueError):
        return str(report_date)
    return f"{day.day:02d} {_month(day)} {day.year}"


def _header_title(meta):
    """Header line 1: stock code, then the rating action and target price.

    A draft or an analysis without a released rating shows its status instead
    of a TP, so an unreviewed number never reaches the running header.
    """
    meta = meta or {}
    code = f"{meta.get('ticker', '')} IJ".strip()
    if meta.get("status") == "draft_non_distributable":
        return f"{code} | DRAFT"
    rating = meta.get("rating")
    if not rating:
        return code
    if meta.get("tp") is None:
        return f"{code} | {str(rating).upper()}"
    return f"{code} | {str(rating).upper()} \u00b7 TP Rp {fmt.rp(meta['tp'], lang=_LANG.get())}"


def _header_subtitle(report_date):
    """Header line 2: report type and publication date. (Hyphen, not an en
    dash: rendered text carries no U+2013, see clean_dashes.)"""
    return f"Equity Research - Company Update | {_display_date(report_date)}"


def _report_header(report_date, meta=None):
    """Report header (Figma node 2627:900): stock code, rating and TP in
    Roboto Black blue; report type and date in Roboto Regular black; the logo
    top right; the blue-to-lime divider under both."""
    return ("<div class='report-header'>"
            "<div class='report-heading'>"
            f"<div class='report-title'>{html.escape(_header_title(meta))}</div>"
            f"<div class='report-subtitle'>{html.escape(_header_subtitle(report_date))}</div></div>"
            f"<img class='report-wordmark' src='data:image/png;base64,{REPORT_WORDMARK}' "
            "alt='Sektoral'>"
            f"<img class='report-divider' src='data:image/svg+xml;base64,{REPORT_DIVIDER}' "
            "alt=''>"
            "</div>")


def _draft_banner(meta):
    if meta.get("status") != "draft_non_distributable":
        return ""
    if meta.get("illustrative_scenarios"):
        return _say("<div class='draft-banner'>DRAFT ILUSTRATIF: skenario memakai fakta "
                    "bersumber dan asumsi analis; belum layak sebagai target harga.</div>",
                    "<div class='draft-banner'>ILLUSTRATIVE DRAFT: scenarios use sourced facts "
                    "and Analyst Assumptions; not fit to serve as a Target Price.</div>")
    return _say("<div class='draft-banner'>DRAFT: BUKTI BELUM LENGKAP: "
                "skenario nilai belum disajikan sampai data dan model tervalidasi.</div>",
                "<div class='draft-banner'>DRAFT: EVIDENCE INCOMPLETE: value scenarios are "
                "withheld until the data and model are validated.</div>")


def _risk_source(risk):
    """A risk's source: document titles as published, a fixed wording in the
    render's language."""
    source = str(risk.get("sumber") or "-")
    return (report_lang.known(source) or source) if _english() else source


def _risk_block(risks):
    """Spec §5.4 'Risiko utama': named, categorised risks in the thesis-card
    style, each with the source of its number."""
    res = [f"<h3 class='sub risk-head'>{_say('Risiko utama', 'Key risks')}</h3><div class='cards risks'>"]
    for risk in risks:
        res.append("<div class='card'><div class='card-body'>"
                   f"<div class='card-title'>{html.escape(str(risk.get('judul') or ''))}"
                   + (f" <span class='risk-tag'>({html.escape(_lbl(str(risk.get('kategori')).strip().lower()))})</span>"
                      if risk.get("kategori") else "") + "</div>"
                   f"<div class='card-text'>{html.escape(str(risk.get('isi') or ''))}</div>"
                   f"<div class='risk-src'>{_say('Sumber', 'Source')}: {html.escape(_risk_source(risk))}</div>"
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
                       f"<p><b>{_say('Observasi', 'Observation')}.</b> {html.escape(card['observation'])}</p>"
                       f"<p><b>{_say('Kaitan', 'Implication')}.</b> {html.escape(card['implication'])}</p>"
                       f"<p><b>{_say('Batasan', 'Caveat')}.</b> {html.escape(card['caveat'])}</p>"
                       f"<p class='research-cite'><b>{_say('Rujukan data', 'Data references')}:</b> "
                       f"{html.escape(refs)}</p>"
                       "</article>")

    elif b.get("layout") == "cards":
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        res.append("<div class='cards'>")
        for card in b.get("cards") or []:
            metric = ""
            if card.get("metric"):
                metric = ("<div class='card-metric'>"
                          f"<div class='card-value'>{html.escape(_figures(str(card['metric'])))}</div>"
                          f"<div class='card-label'>{html.escape(_lbl(str(card.get('metric_label') or '')))}</div>"
                          "</div>")
            res.append("<div class='card'><div class='card-body'>"
                       f"<div class='card-title'>{html.escape(str(card.get('title') or ''))}</div>"
                       f"<div class='card-text'>{html.escape(str(card.get('text') or ''))}</div>"
                       f"</div>{metric}</div>")
        res.append("</div>")
        res.append(_exhibits_paired(exs))

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
                       f"<div class='grid-col'>{_table(exs[0], 'half')}</div>"
                       f"<div class='grid-col'>{_table(exs[1], 'half')}</div>"
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
                   f"<div class='grid-col'>{_table(exs[0], 'half')}</div>"
                   f"<div class='grid-col'>{_table(exs[1], 'half')}{_table(exs[2], 'half')}</div>"
                   "</div>")
        res.append(_table(exs[3]))

    elif halaman == 6 and len(exs) == 3:
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        res.append(_table(exs[0]))
        res.append("<div class='grid-2'>"
                   f"<div class='grid-col'>{_table(exs[1], 'half')}</div>"
                   f"<div class='grid-col'>{_table(exs[2], 'half')}</div>"
                   "</div>")

    else:
        for p in paras:
            res.append(f"<p>{html.escape(p)}</p>")
        res.append(_exhibits_paired(exs))

    return "\n".join(res)


def _css_string(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _running_header(m):
    """Repeat the report header on every printed page, including overflow pages.

    Section headers live inside each section's HTML, so a section that spills
    onto a second sheet would otherwise print without header or draft label.
    Figma header content: stock code, rating and TP over the report type and
    date top left, the logo top right. app/pdf.py replaces this with the captured page-1 header; this
    text form is what browser printing of the HTML shows.
    """
    box = ("font-family:'Roboto',sans-serif;font-size:7.7pt;line-height:1.3;"
           "vertical-align:bottom;padding-bottom:2mm;")
    left = (f"{_css_string(_header_title(m))} '\\A ' "
            f"{_css_string(_header_subtitle(m.get('tanggal')))}")
    # Two-colour rule under the header, as in the design divider: blue, then lime.
    return ("@page{margin-top:19mm;"
            f"@top-left{{content:{left};white-space:pre;font-weight:900;color:{PRIMARY};{box}"
            f"border-bottom:1.5px solid {PRIMARY}}}"
            f"@top-right{{content:'';width:40mm;{box}"
            f"background:url('data:image/png;base64,{REPORT_WORDMARK}') right 0 bottom 2mm"
            "/32.4mm 5.75mm no-repeat;"
            f"border-bottom:1.5px solid {LIME}}}}}"
            "@page:first{margin-top:12mm;@top-left{content:none;border:0}"
            "@top-right{content:none;border:0;background:none}}"
            "@media print{.page>.report-header{display:none}}")


_URL_RE = re.compile(r"https?://[^\s;<>\"']+")


def _link_label(url):
    """Short, readable label for a long document URL: host/…/file name."""
    parts = urlsplit(url)
    host = parts.netloc.removeprefix("www.")
    segments = [seg for seg in parts.path.split("/") if seg]
    if not segments:
        return host
    name = unquote(segments[-1])
    label = f"{host}/{name}" if len(segments) == 1 else f"{host}/…/{name}"
    return label if len(label) <= 72 else label[:71] + "…"


def _linked(text):
    """Escape `text`, turning each URL into a link with a short label."""
    out, last = [], 0
    for match in _URL_RE.finditer(text):
        url = match.group(0)
        tail = ""
        # Sentence punctuation and a closing bracket the URL did not open.
        while url and (url[-1] in ".,:" or (url[-1] == ")" and url.count("(") < url.count(")"))):
            url, tail = url[:-1], url[-1] + tail
        out.append(html.escape(text[last:match.start()]))
        out.append(f"<a href='{html.escape(url, quote=True)}'>{html.escape(_link_label(url))}</a>"
                   + html.escape(tail))
        last = match.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def _exhibit_number(n):
    try:
        return int(n)
    except (TypeError, ValueError):
        return 10 ** 6


# The per-exhibit source appendix is hidden for now: exhibit footers keep the
# house source line, and each exhibit's full note stays in the report
# document and its audit trace. Set True to print it again.
SHOW_SOURCE_APPENDIX = False


def _source_appendix(notes, meta):
    """Spec §5.5: exhibit footers carry only the house line; each exhibit's
    provenance, dates, method and caveats are listed here, in exhibit order."""
    seen, entries = set(), []
    for number, title, detail in sorted(notes or [], key=lambda note: _exhibit_number(note[0])):
        if (number, title) in seen:
            continue
        seen.add((number, title))
        if detail and detail[0].islower() and not _URL_RE.match(detail):
            detail = detail[0].upper() + detail[1:]
        body = _linked(detail) if detail else _say("Data perusahaan dan estimasi Sektoral.",
                                                    "Company data and Sektoral estimates.")
        entries.append(f"<dt>Exhibit {html.escape(str(number))}. {html.escape(title)}</dt>"
                       f"<dd>{body}</dd>")
    if not entries:
        return ""
    return (f"<div class='page source-appendix'>{_report_header(meta['tanggal'], meta)}"
            f"{_draft_banner(meta)}"
            + _say("<h2 class='sec'>Lampiran: sumber dan catatan exhibit</h2>"
                   f"<p class='small'>Setiap exhibit memakai baris sumber \"{html.escape(fmt.DEFAULT_SOURCE)}\". "
                   "Rincian data, tanggal, metode dan batasan tiap exhibit tercantum di bawah. "
                   "Konvensi tabel: angka negatif dalam kurung; n.m. berarti tidak bermakna; "
                   "NA berarti tidak tersedia atau tidak dimodelkan.</p>",
                   "<h2 class='sec'>Appendix: exhibit sources and notes</h2>"
                   f"<p class='small'>Every exhibit carries the source line \"{html.escape(fmt.DEFAULT_SOURCE)}\". "
                   "The data, dates, method and limits of each exhibit are listed below. "
                   "Table conventions: negative figures in brackets; n.m. means not meaningful; "
                   "NA means not available or not modelled.</p>") +
            f"<dl class='src-list'>{''.join(entries)}</dl></div>")


def _local_day(stamp):
    """The calendar day of a timestamp where the report is built (a Report
    Date is a local day; 06:00 WIB is still the day before in UTC)."""
    try:
        return datetime.fromisoformat(str(stamp)).astimezone().date().isoformat()
    except (TypeError, ValueError):
        return None


def build_note(doc):
    """The day the document was built (or rebuilt), when it is not the Report
    Date: a house decision or policy dated after the Report Date then reads as
    what it is, the policy in force when the report was built."""
    manifest = doc.get("run_manifest") if isinstance(doc.get("run_manifest"), dict) else {}
    rebuild = manifest.get("rebuild") if isinstance(manifest.get("rebuild"), dict) else {}
    day = _local_day(rebuild.get("rebuilt_at") or manifest.get("built_at"))
    report_day = str((doc.get("meta") or {}).get("tanggal") or "")[:10]
    if not day or not report_day or day == report_day:
        return None
    if rebuild:
        return _say(f"Disusun ulang {day} atas bukti per Tanggal Laporan {report_day}; rujukan "
                    "bertanggal sesudah Tanggal Laporan adalah kebijakan yang berlaku saat "
                    "disusun ulang.",
                    f"Rebuilt on {day} from evidence as of the Report Date, {report_day}; "
                    "references dated after the Report Date are policies in force at the rebuild.")
    return _say(f"Disusun {day} atas bukti per Tanggal Laporan {report_day}; rujukan bertanggal "
                "sesudah Tanggal Laporan adalah kebijakan yang berlaku saat disusun.",
                f"Built on {day} from evidence as of the Report Date, {report_day}; references "
                "dated after the Report Date are policies in force when it was built.")


def render(doc, lang=report_lang.DEFAULT):
    """The Company Update HTML of `doc` in `lang` ("id" or "en")."""
    token = _NOTES.set([])
    lang_token = _LANG.set(report_lang.check(lang))
    fallback = 0
    if lang == "en":
        doc, fallback = prose_lang.english_view(doc)
    try:
        return _render(doc, prose_fallback=fallback)
    finally:
        _LANG.reset(lang_token)
        _NOTES.reset(token)


# Prose the English edition could not translate (a report stored before
# English prose existed, or agent prose, #34) stays Indonesian; this note
# under the cover header says so, and only then.
_PROSE_NOTE_CSS = (".prose-lang-note{font-size:6.7pt;font-style:italic;color:" + MUT + ";"
                   "margin:1.2mm 0 0}")
_PROSE_NOTE = ("<p class='prose-lang-note'>English edition: labels, tables and figures are in "
               "English; some narrative paragraphs are still in Bahasa Indonesia.</p>")


def _render(doc, prose_fallback=0):
    m, cov = doc["meta"], doc["cover"]
    english = _english()
    css = (CSS.replace("Geser tabel untuk kolom lainnya →", "Scroll the table for more columns →")
           + _PROSE_NOTE_CSS if english else CSS)
    opening = "<html lang='en'>" if english else "<html>"
    h = [f"{opening}<head><meta charset='utf-8'><style>{css}{_running_header(m)}</style></head><body>"]
    h.append(_report_header(m["tanggal"], m))
    h.append(_draft_banner(m))
    if english and prose_fallback:
        h.append(_PROSE_NOTE)
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

    lang = _LANG.get()
    dp = cov.get("data_pasar") or {}
    released = bool(m.get("rating")) and m.get("tp") is not None
    prev_tp = m.get("tp_sebelumnya")
    both = lambda rp, usd: f"{rp} / {usd}" if usd else rp
    h.append("<div class='cover'><div class='left'>")
    h.append("<div class='rating-block'><div class='rating-head'>"
             f"<div class='rating-label'>{html.escape(_lbl(str(rating_word)))}</div>"
             f"<div class='rating-detail'>({html.escape(_lbl(str(rating_status)))})</div>"
             "<div class='rating-method'>"
             + (_say("Rating ditahan hingga pemeriksaan selesai.<br>",
                     "Rating withheld until checks are complete.<br>") if draft else "")
             + f"{_say('Valuasi', 'Valuation')}: {html.escape(_lbl(doc.get('method', 'DCF')))}</div></div>"
             + sep)
    last_price = _say("Harga Terakhir", "Last Price")
    price_label = (f"{last_price} (Rp; {m['harga_tanggal']})"
                   if m.get("harga_tanggal") and m.get("harga_tanggal") != m["tanggal"]
                   else f"{last_price} (Rp)")
    h.append(row(price_label, fmt.rp(m["harga"], lang=lang) if m.get("harga") is not None else "NA",
                 m.get("harga") is None))
    h.append(row(_say("Target Harga (Rp)", "Target Price (Rp)"),
                 fmt.rp(m["tp"], lang=lang) if released else "NA", not released))
    h.append(row(_say("TP Sebelumnya (Rp)", "Previous TP (Rp)"),
                 _figures(str(prev_tp)) if prev_tp else "NA", not prev_tp))
    upside = f"{m['upside_persen']:+.1f}%" if released and m.get("upside_persen") is not None else "NA"
    h.append(row("Upside/Downside (%)", upside if english else upside.replace(".", ","),
                 not released))
    h.append(row(_say("Jumlah Saham (juta)", "Shares Outstanding (mn)"),
                 fmt.num(dp["saham"] / 1e6, 1, lang) if dp.get("saham") is not None else "NA"))
    mcap = fmt.num(dp["market_cap"] / 1e9, 1, lang) if dp.get("market_cap") is not None else "NA"
    h.append(row(_say("Kap. Pasar (Rp miliar / US$ juta)", "Market Cap (Rp bn / US$ mn)")
                 if dp.get("market_cap_usd") else _say("Kap. Pasar (Rp miliar)", "Market Cap (Rp bn)"),
                 both(mcap, _figures(dp.get("market_cap_usd")))))
    h.append(row(_say("Rata-rata T/O Harian 3M (Rp miliar / US$ juta)", "3M Avg Daily T/O (Rp bn / US$ mn)")
                 if dp.get("adtv_usd")
                 else _say("Rata-rata T/O Harian 3M (Rp miliar)", "3M Avg Daily T/O (Rp bn)"),
                 both(_figures(str(dp.get("adtv", "NA"))), _figures(dp.get("adtv_usd")))))
    h.append(row("Free Float (%)",
                 _figures(str(dp.get("public_ownership", dp.get("free_float", "NA"))))))
    holders = (doc.get("holders") or [])[:4]
    if holders:
        h.append(sep + f"<div class='rating-sub'>{_say('Pemegang saham utama (%)', 'Major Shareholders (%)')}</div>")
        for holder in holders:
            h.append(row(str(holder[0])[:34], _figures(str(holder[1]))))
    h.append("</div>")
    chart = next((e for e in doc["exhibits"] if e.get("tipe") == "price_chart"), None)
    h.append("<div class='info'>")
    h.append(_price_chart(m["ticker"], m["tanggal"],
                          number=chart["n"] if chart else None,
                          source=(chart or {}).get("catatan_sumber"),
                          latest_close=m.get("harga"), latest_date=m.get("harga_tanggal")))
    h.append(sep + "</div>")
    h.append(f"<div class='analyst'><b>{_say('Tim Riset Sektoral', 'Sektoral Research Team')}</b>"
             "<br>Equity Analyst</div>")
    h.append("</div><div class='right'>")
    h.append(f"<h1 class='emit'>{html.escape(m['emiten'])} ({html.escape(m['ticker'])} IJ)</h1>")
    h.append(f"<div class='headline'>{html.escape(cov['headline'])}</div>"
             "<div class='highlight'><ul class='bullets'>")
    for b in cov["bullets"]:
        h.append(f"<li>{html.escape(b)}</li>")
    h.append("</ul></div>")
    for p in cov["paragraf"]:
        h.append(f"<h2 class='sub'>{html.escape(_lbl(p['judul']))}</h2><p>{html.escape(p['isi'])}</p>")
    # Key Financials sits under the narrative in the main column (design 5.4.2).
    # Without a "Key Financials" exhibit, the first non-chart exhibit that no
    # section places is the cover table (renumber puts it right after the chart).
    placed = {id(e) for b in doc["bagian"] for e in b.get("exhibit", [])}
    cover_tables = [e for e in doc["exhibits"]
                    if e.get("tipe") != "price_chart" and id(e) not in placed]
    key_fin = (exhibit_ids.find(cover_tables, exhibit_ids.KEY_FINANCIALS)
               or (cover_tables[0] if cover_tables else None))
    if key_fin:
        h.append(_table(key_fin, "cover"))
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
                 f"{html.escape(_lbl(b['judul']))}</h2>")
        h.append(_render_page_content(b))
        h.append("</div>")

    disclosure = (_say("INFORMASI, BUKAN SARAN INVESTASI. Laporan ini adalah keluaran alat "
                       "informasi dan analisis berbasis data Sectors Financial API (sectors.app) "
                       "dan IDX. Rating dan target harga adalah hasil model bersyarat atas asumsi "
                       "dan sumber yang dinyatakan, bukan rekomendasi atau saran investasi. "
                       "Keputusan investasi sepenuhnya tanggung jawab pembaca; lakukan riset "
                       "mandiri dan konsultasikan dengan penasihat keuangan berlisensi. Kinerja "
                       "masa lalu tidak menjamin hasil ke depan.",
                       "INFORMATION, NOT INVESTMENT ADVICE. This report is the output of an "
                       "information and analysis tool built on Sectors Financial API "
                       "(sectors.app) and IDX data. The Rating and Target Price are conditional "
                       "model outputs of the stated assumptions and sources, not a "
                       "recommendation or investment advice. Investment decisions are the "
                       "reader's sole responsibility; do independent research and consult a "
                       "licensed financial advisor. Past performance does not guarantee future "
                       "results.")
                  if m.get("rating") else
                  _say("INFORMASI, BUKAN SARAN INVESTASI. Dokumen ini adalah bahan riset "
                       "dalam peninjauan. Rating dan target harga belum diterbitkan karena "
                       "syarat data atau model belum terpenuhi. Keputusan investasi menjadi "
                       "tanggung jawab pembaca.",
                       "INFORMATION, NOT INVESTMENT ADVICE. This document is research material "
                       "under review. The Rating and Target "
                       "Price are not published because data or model requirements are not yet "
                       "met. Investment decisions are the reader's responsibility."))
    if SHOW_SOURCE_APPENDIX:
        h.append(_source_appendix(_NOTES.get(), m))
    h.append(f"<div class='page'>{_report_header(m['tanggal'], m)}"
             f"{_draft_banner(m)}"
             f"<h2 class='sec'>{_say('Pengungkapan', 'Disclosures')}</h2>"
             f"<p class='small'>{html.escape(disclosure)}</p>"
             f"<h3 class='sub'>{_say('Catatan metodologi', 'Methodology notes')}</h3><ul>")
    for c in doc["catatan_metodologi"]:
        # English prose from the builder is final; only Indonesian notes are looked up.
        note = c if isinstance(c, prose_lang.Translated) else report_lang.note(c, lang)
        h.append(f"<li class='small'>{html.escape(note)}</li>")
    built = build_note(doc)
    if built:
        h.append(f"<li class='small'>{html.escape(built)}</li>")
    h.append("</ul></div></body></html>")
    out = "\n".join(h)
    return out.replace("—", " - ").replace("–", "-")
