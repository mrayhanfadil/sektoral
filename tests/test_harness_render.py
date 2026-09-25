"""Rendered-report template checks (app/harness/render_check.py) on synthetic
HTML and PDF page text; no rendering, no database."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.harness import render_check as R  # noqa: E402

SRC = "Source: Company, Sektoral Estimates"
DOC = {"meta": {"ticker": "TEST", "emiten": "PT Uji Coba Tbk", "tanggal": "2026-09-24",
                "rating": "Buy", "tp": 1200, "status": "distributable_assumption_led"}}
CSS = ("@page{@bottom-left{content:'sectors.app'}"
       "@bottom-right{content:'See important disclosure at the back of this report' 'Page ' counter(page)"
       " ' of ' counter(pages)}}"
       "@page{margin-top:19mm;@top-left{content:\"TEST IJ | BUY\"}"
       "@top-right{content:\"Equity Research - Company Update | Kamis, 24 September 2026\"}}")


def html(**over):
    o = {"css": CSS, "date": "Kamis, 24 September 2026", "upside": "+20,0%", "window": "12M",
         "src": [SRC] * 5, "numbers": [1, 2, 3, 4, 5], "analyst": "Equity Analyst",
         "h1": "PT Uji Coba Tbk (TEST IJ)", "base_row": "<tr class='base-row'>",
         "issuer_row": "<tr class='issuer-row'>", "median_row": "<tr class='total-row'>",
         "mean_dash": "6 4", "neg": "(12,0)", "appendix": True, "logo": True}
    o.update(over)
    n = o["numbers"]
    s = o["src"]
    parts = [f"<html><head><style>{o['css']}</style></head><body>",
             "<div class='report-header'><div class='report-title'>TEST IJ | BUY</div>"
             f"<div class='report-subtitle'>Equity Research - Company Update</div><div>{o['date']}</div>"
             + ("<img class='report-wordmark' alt='Sektoral' src='x.png'>" if o["logo"] else "") + "</div>",
             "<div class='cover'><div class='left'>",
             "<div class='rating-row'><span>Harga Terakhir (Rp)</span><b>1.000</b></div>",
             "<div class='rating-row'><span>Target Harga (Rp)</span><b>1.200</b></div>",
             f"<div class='rating-row'><span>Upside/Downside (%)</span><b>{o['upside']}</b></div>",
             f"<div class='info-title'>Exhibit {n[0]}. TEST relative to IHSG ({o['window']}, Sep-25 - Sep-26)</div>",
             "<svg class='price-chart'><title>akses</title><text>Nov-25</text><text>Jan-26</text>"
             "<text>Mar-26</text></svg>",
             f"<div class='info-src'>{s[0]}</div>",
             f"<div class='analyst'><b>Tim Riset Sektoral</b><br>{o['analyst']}</div></div>",
             f"<div class='right'><h1 class='emit'>{o['h1']}</h1>",
             "<div class='exhibit'><table class='exhibit-table'>"
             f"<caption>Exhibit {n[1]}. Key Financials</caption>"
             "<thead><tr><th>Tahun</th><th>2025A</th></tr></thead>"
             f"<tbody><tr><td class='cell-text'>Laba bersih</td><td class='cell-num'>{o['neg']}</td></tr>"
             f"</tbody></table><p class='src'>{s[1]}</p></div></div></div>",
             "<div class='section'><h2>Valuasi</h2>",
             "<div class='exhibit'><table class='exhibit-table'>"
             f"<caption>Exhibit {n[2]}. Sensitivitas nilai DCF: WACC x pertumbuhan terminal</caption>"
             "<tbody><tr><td>WACC 9,9%</td><td class='cell-num'>Rp1.300</td></tr>"
             f"{o['base_row']}<td>WACC 10,9% (basis)</td><td class='cell-num'>Rp1.200</td></tr>"
             f"</tbody></table><p class='src'>{s[2]}</p></div>",
             "<div class='risk-src'>Sumber: rilis resmi</div>",
             "<div class='exhibit'><table class='exhibit-table'>"
             f"<caption>Exhibit {n[3]}. Perbandingan peer Uji</caption>"
             "<tbody><tr><td>AAAA</td><td class='cell-num'>10,0x</td></tr>"
             f"{o['issuer_row']}<td>TEST (emiten)</td><td class='cell-num'>9,1x</td></tr>"
             f"{o['median_row']}<td>Median peer (tanpa emiten)</td><td class='cell-num'>10,0x</td></tr>"
             f"</tbody></table><p class='src'>{s[3]}</p></div>",
             f"<div class='exhibit band'><div class='chart-caption'>Exhibit {n[4]}. Band P/E 12 bulan TEST</div>"
             "<svg class='band-chart' aria-label='Band P/E 12 bulan TEST'>"
             + "".join("<line x1='0' x2='9' y1='1' y2='1' stroke-dasharray='3 3'/>" for _ in range(4))
             + "<polyline points='0,0 1,1' fill='none'/>"
             f"<line x1='0' x2='9' y1='5' y2='5' stroke-dasharray='{o['mean_dash']}'/>"
             "<line x1='0' x2='9' y1='6' y2='6' stroke-dasharray='1.5 3'/>"
             "<path d='M1,1 L2,2 Z' fill='lime'/></svg>"
             f"<p class='src'>{s[4]}</p></div></div>"]
    if o["appendix"]:
        parts.append("<div class='page'><h2 class='sec'>Lampiran: sumber dan catatan exhibit</h2><dl>"
                     + "".join(f"<dt>Exhibit {i}. Judul</dt><dd>Rincian sumber {i}</dd>" for i in n)
                     + "</dl></div>")
    parts.append("</body></html>")
    return "".join(parts)


def checks(text, doc=DOC):
    return {c["check"]: c for c in R.check_rendered(text, doc)["checks"]}


def failed(text, doc=DOC):
    return {k: c for k, c in checks(text, doc).items() if c["status"] == R.FAIL}


def test_compliant_render_passes():
    res = checks(html())
    assert not [f"{k}: {c['message']}" for k, c in res.items() if c["status"] == R.FAIL]
    assert {k for k in res} == {k for k in R.RENDER_CHECKS
                                 if not k.endswith(".pdf") and k != "R.render_error"}


def test_source_line_must_be_exact():
    f = failed(html(src=[SRC, SRC + "; Sectors, company/report", SRC, SRC, SRC]))
    assert f["T1.source_line"]["blocker"] and "Exhibit 2" in f["T1.source_line"]["message"]


def test_missing_source_line_blocks_and_risk_sumber_is_ignored():
    f = failed(html(src=[SRC, SRC, SRC, "", SRC]))
    assert "Exhibit 4: tanpa source line" in f["T1.source_line"]["message"]


def test_numbering_gap_blocks():
    assert failed(html(numbers=[1, 2, 4, 5, 6]))["T1.numbering_rendered"]["blocker"]


def test_appendix_without_known_heading_is_not_a_numbering_break():
    text = html(appendix=False).replace(
        "</body>", "<div><h2>Catatan</h2>" + "".join(f"<p>Exhibit {i}. Rincian</p>" for i in range(1, 6))
        + "</div></body>")
    f = failed(text)
    assert "T1.numbering_rendered" not in f
    assert "judul lampiran" in checks(text)["T1.source_appendix"]["message"]


def test_missing_appendix_warns():
    assert failed(html(appendix=False))["T1.source_appendix"]["severity"] == R.WARNING


def test_header_date_format_and_weekday():
    f = failed(html(date="Jumat, 24 September 2026"))
    assert "hari salah" in f["T1.header"]["message"]
    css = CSS.replace("Kamis, 24 September 2026", "24 Sep 2026")
    assert "header berjalan" in failed(html(css=css))["T1.header"]["message"]
    assert "tanpa logo" in failed(html(logo=False))["T1.header"]["message"]


def test_footer_needs_sectors_app_disclosure_right_and_page_number():
    css = CSS.replace("content:'sectors.app'", "content:'See important disclosure at the back of this report'")
    msg = failed(html(css=css))["T1.footer"]["message"]
    assert "sectors.app" in msg and "kiri" in msg
    css = CSS.replace("'Page ' counter(page) ' of ' counter(pages)", "''")
    assert "nomor halaman" in failed(html(css=css))["T1.footer"]["message"]


def test_price_box_sign_and_one_decimal():
    assert "satu desimal" in failed(html(upside="+20,00%"))["T2.price_box_rendered"]["message"]
    assert "tanpa tanda" in failed(html(upside="20,0%"))["T2.price_box_rendered"]["message"]
    draft = {"meta": {**DOC["meta"], "rating": None, "tp": None}}
    assert checks(html(upside="NA"), draft)["T2.price_box_rendered"]["status"] == R.NA


def test_relative_chart_window():
    assert "3 bulan" in failed(html(window="3M"))["T2.relative_chart_rendered"]["message"]


def test_analyst_and_company_header():
    f = failed(html(analyst="Analis", h1="PT Uji Coba Tbk"))
    assert {"T2.analyst_block", "T2.company_header"} <= set(f)


def test_highlights_and_band_lines():
    f = failed(html(base_row="<tr>", issuer_row="<tr>", median_row="<tr>", mean_dash="1.5 3"))
    for cid in ("T4.sensitivity_highlight_rendered", "T5.peer_highlight_rendered", "T5.band_lines_rendered"):
        assert f[cid]["severity"] == R.WARNING, cid


def test_negative_numbers_in_brackets():
    assert "-12,0" in failed(html(neg="-12,0"))["TN.negatives_brackets"]["message"]


def _pages(src=SRC, footer="sectors.app See important disclosure at the back of this report Page {i} of 2"):
    head = "TEST IJ | BUY Equity Research - Company Update | Kamis, 24 September 2026"
    return [f"{footer.format(i=1)}\n{head}\nExhibit 1. TEST relative to IHSG\n{src}\nExhibit 2. Key Financials\n"
            f"Laba bersih 110\n{src}",
            f"{footer.format(i=2)}\n{head}\nExhibit 3. Laba rugi\nPendapatan 1.000\n{src}"]


def test_pdf_text_checks():
    res = {c["check"]: c for c in R.check_pdf_text(_pages(), DOC)["checks"]}
    assert all(c["status"] == R.PASS for c in res.values()), res
    res = {c["check"]: c for c in R.check_pdf_text(_pages(src=SRC + "; Sectors"), DOC)["checks"]}
    assert res["T1.source_line.pdf"]["blocker"]
    pages = _pages(footer="See important disclosure at the back of this report Page {i} of 2")
    res = {c["check"]: c for c in R.check_pdf_text(pages, DOC)["checks"]}
    assert res["T1.footer.pdf"]["status"] == R.FAIL and res["T1.footer.pdf"]["severity"] == R.WARNING
    pages = [p.replace("| Kamis, 24 September 2026", "| 24 Sep 2026") for p in _pages()]
    res = {c["check"]: c for c in R.check_pdf_text(pages, DOC)["checks"]}
    assert res["T1.header.pdf"]["status"] == R.FAIL and not res["T1.header.pdf"]["blocker"]


def test_render_error_result_is_a_blocker():
    out = R.error_result(KeyError("cover"))
    assert out["blocker"] and out["check"] == "R.render_error"
