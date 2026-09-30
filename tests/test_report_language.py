"""The Company Update in two languages: Indonesian unchanged, English labels,
English files kept off public routes until #34."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import exhibit_ids, gallery, render, report_lang  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "render_id_golden.html"


def _doc():
    """A small report document with every exhibit type and page layout."""
    key_fin = {"n": 2, "judul": "Key Financials", "tipe": "tabel", "exhibit_id": "key_financials",
               "catatan_sumber": "Source: Company, Sektoral Estimates",
               "data": {"cols": ["Tahun buku 31 Des", "2024", "2025", "FY26F"],
                        "rows": [["Pendapatan (Rp miliar)", "1.234,5", "1.300,0", "1.450,2"],
                                 ["Laba bersih (Rp miliar)", "(12,0)", "98,7", "120,4"],
                                 ["PER (x)", "n.m.", "12,8x", "belum dimodelkan"]]}}
    chain = {"n": 3, "judul": "Rantai metode valuasi", "tipe": "tabel", "exhibit_id": "method_chain",
             "catatan_sumber": "Source: Sektoral Estimates",
             "data": {"cols": ["Metode", "Keputusan", "Nilai/saham", "Alasan"],
                      "rows": [["1. DCF FCFF (utama)", "Terpilih", "Rp1.200", "input lengkap"],
                               ["2. PER relatif", "Silang cek", "Rp1.050", "peer PER valid kurang dari tiga"]]}}
    sens = {"n": 4, "judul": "Sensitivitas nilai DCF: WACC x pertumbuhan terminal", "tipe": "tabel",
            "catatan_sumber": "Source: Sektoral Estimates",
            "data": {"cols": ["WACC", "g 2,5%", "g 3,5% (basis)", "g 4,5%"],
                     "rows": [["WACC 9,9%", "Rp1.300", "Rp1.350", "Rp1.420"],
                              ["WACC 10,9% (basis)", "Rp1.150", "Rp1.200", "Rp1.260"],
                              ["WACC 11,9%", "Rp1.020", "Rp1.060", "Rp1.100"]]}}
    flow = {"n": 5, "judul": "Arus kas", "tipe": "tabel", "catatan_sumber": "Source: Company",
            "data": {"cols": ["Rp miliar", "2024A", "2025A"],
                     "rows": [["Blok Arus kas operasi", "", ""],
                              ["Laba bersih", "98,7", "120,4"],
                              ["Jumlah arus kas operasi", "150,1", "-4,1"]]}}
    panel = {"n": 6, "judul": "Pendapatan dan pertumbuhan (2024A-FY26F)", "tipe": "combo_panel",
             "exhibit_id": "revenue_panel", "catatan_sumber": "Source: Company",
             "narasi": "Pendapatan tumbuh CAGR 8,4% pada 2022-2025.",
             "data": {"cols": ["2024A", "2025A", "FY26F"],
                      "series": [{"label": "Pendapatan (Rp) & pertumbuhan",
                                  "bars": [1.2345e12, 1.3e12, 1.45e12], "line": [None, 5.3, 11.6],
                                  "is_forecast": [False, False, True]}]}}
    band = {"n": 7, "judul": "Band P/E 12 bulan UJI", "tipe": "band_chart", "catatan_sumber": "Source: IDX",
            "data": {"label": "P/E", "dates": ["2025-09-24", "2026-03-24", "2026-09-24"],
                     "values": [10.5, 12.25, 11.0], "mean": 11.2, "median": 11.0, "current": 11.0,
                     "percentile": 45}}
    bars = {"n": 8, "judul": "Hasil interim resmi dan perubahan yoy", "tipe": "bar_chart",
            "catatan_sumber": "Source: Company",
            "data": {"unit": "Rp miliar", "prior_label": "1H25", "current_label": "1H26",
                     "rows": [{"label": "Pendapatan", "prior": 600e9, "current": 650e9},
                              {"label": "Laba bersih", "prior": 40e9, "current": 55e9}]}}
    grid = {"n": 9, "judul": "Kinerja historis", "tipe": "combo_chart", "catatan_sumber": "Source: Company",
            "data": {"cols": ["2024A", "2025A"],
                     "series": [{"label": "EBITDA (Rp) & margin", "bars": [3e11, 3.3e11],
                                 "line": [24.3, 25.4], "is_forecast": [False, False]}]}}
    return {
        "meta": {"ticker": "UJI", "emiten": "PT Uji Coba Tbk", "tanggal": "2026-09-24",
                 "harga_tanggal": "2026-09-23", "harga": 1000.0, "rating": "Buy", "tp": 1200,
                 "upside_persen": 20.0, "status": "distributable_assumption_led",
                 "rating_status": "Inisiasi"},
        "method": "DCF FCFF skenario FY26F-FY30F + terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
        "cover": {"headline": "Laba naik karena volume.",
                  "bullets": ["Pendapatan 1H26 naik 5,4% yoy ke Rp1.234,5 miliar."],
                  "paragraf": [{"judul": "Hasil terbaru memberi titik awal",
                                "isi": "Laba 1H26 naik 17,5% yoy."}],
                  "data_pasar": {"saham": 1_234_567_890, "market_cap": 1.2345e12, "adtv": "36,5",
                                 "public_ownership": "51,5%", "market_cap_usd": "75,1",
                                 "adtv_usd": "2,2"}},
        "holders": [["PT Induk Uji", "56,3%"]],
        "exhibits": [{"n": 1, "judul": "UJI relatif terhadap IHSG", "tipe": "price_chart",
                      "catatan_sumber": "Source: Sectors"}, key_fin, chain, sens, flow,
                     panel, band, bars, grid],
        "bagian": [
            {"halaman": 2, "judul": "Tesis investasi", "layout": "cards",
             "paragraf": ["Tesis kami bertumpu pada volume."],
             "cards": [{"title": "Volume naik", "text": "Kapasitas bertambah.",
                        "metric": "-10,8%", "metric_label": "Ke target Rp1.200"}],
             "exhibit": [chain]},
            {"halaman": 3, "judul": "Kinerja keuangan dan profitabilitas", "layout": "stack",
             "paragraf": ["Empat grafik berikut memakai periode yang sama."],
             "exhibit": [sens, flow, panel, band, bars, grid],
             "risks": [{"judul": "Harga komoditas turun", "kategori": "Komoditas",
                        "isi": "Harga turun 10%.", "sumber": "rilis resmi"}], "risks_after": 2},
            {"halaman": 4, "judul": "Ringkasan riset", "layout": "research_cards",
             "paragraf": [], "research_cards": [
                 {"title": "Peer", "observation": "Peringkat naik.", "implication": "Positif.",
                  "caveat": "Data terbatas.", "citations": ["sig.peer_rank"]}]}],
        "catatan_metodologi": ["Tanda '-' berarti angka tidak tersedia, bukan nol.",
                               "Kalimat prosa yang tetap berbahasa Indonesia."],
    }


def _render(monkeypatch, lang=None):
    # No price history: the chart falls back to its "not available" line, so
    # the render needs no market data.
    monkeypatch.setattr(render, "_price_window", lambda *_args: None)
    doc = _doc()
    return render.render(doc) if lang is None else render.render(doc, lang=lang)


def _without_assets(html):
    """The render with its embedded fonts and images collapsed (the golden file)."""
    return re.sub(r"base64,[A-Za-z0-9+/=]{64,}", "base64,...", html)


def test_indonesian_render_is_byte_identical_to_main(monkeypatch):
    """GOLDEN was rendered by main before the language work (only embedded
    font and image bytes collapsed). Refresh it only for an intended change to
    the Indonesian Company Update."""
    html = _render(monkeypatch)
    assert html == _render(monkeypatch, "id")
    assert _without_assets(html) == GOLDEN.read_text(encoding="utf-8")


def test_english_render_translates_the_fixed_parts(monkeypatch):
    html = _render(monkeypatch, "en")
    assert html.startswith("<html lang='en'>")
    for fixed in ("Target Price (Rp)", "Last Price (Rp; 2026-09-23)", "Previous TP (Rp)",
                  "Shares Outstanding (mn)", "1,234.6", "Market Cap (Rp bn / US$ mn)",
                  "Major Shareholders (%)", "56.3%", "(Initiation)",
                  "Valuation: FCFF DCF on scenario FY26F-FY30F", "UJI IJ | BUY · TP Rp 1,200",
                  "Exhibit 2. Key Financials", "FY to 31 Dec", "Revenue (Rp bn)", ">1,234.5<",
                  "not modelled", "Exhibit 3. Valuation Method Chain", "1. DCF FCFF (primary)",
                  ">Selected<", "WACC 10.9% (base)", "Operating cash flow", "(4.1)",
                  "Revenue and growth (2024A-FY26F)", "Revenue actual", "Revenue forecast",
                  "12M P/E band, UJI", "Now p45", "Official interim results and yoy change",
                  "Rp bn", "Investment thesis", "To target Rp1,200", "-10.8%", "Key risks",
                  "(commodity)", "Source: rilis resmi", "Observation.", "Disclosures",
                  "Methodology notes", "A &#x27;-&#x27; means the figure is not available, not zero.",
                  "Latest results set the starting point", "Scroll the table for more columns"):
        assert fixed in html, fixed
    for indonesian in ("Harga Terakhir", "Target Harga", "Pengungkapan", "Catatan metodologi",
                       "Rantai metode valuasi", "Tahun buku", "Risiko utama", "Geser tabel"):
        assert indonesian not in html, indonesian


def test_english_file_keeps_prose_and_says_so(monkeypatch):
    html = _render(monkeypatch, "en")
    assert html.count("narrative paragraphs are still in Bahasa Indonesia") == 1
    # Prose paragraphs, bullets and unknown notes are left exactly as written.
    for prose in ("Laba 1H26 naik 17,5% yoy.", "Pendapatan 1H26 naik 5,4% yoy ke Rp1.234,5 miliar.",
                  "Pendapatan tumbuh CAGR 8,4% pada 2022-2025.",
                  "Kalimat prosa yang tetap berbahasa Indonesia."):
        assert prose in html, prose
    assert "prose-lang-note" not in _render(monkeypatch)


def test_english_tables_keep_the_indonesian_layout_marks(monkeypatch):
    html = _render(monkeypatch, "en")
    # Base row and cell of the sensitivity, the section row and the total row
    # are read from the stored Indonesian cells.
    assert "<tr class='base-row'><td class='cell-text'>WACC 10.9% (base)</td>" in html
    assert "base-cell" in html
    assert "<th scope='rowgroup' colspan='3'>Operating cash flow</th>" in html
    assert "<tr class='total-row'><td class='cell-text'>Net operating cash flow</td>" in html


def test_unknown_language_is_refused(monkeypatch):
    with pytest.raises(ValueError):
        _render(monkeypatch, "fr")


def test_labels_translate_terms_patterns_and_figures():
    en = lambda text: report_lang.label(text, "en")
    assert en("Laba bersih (Rp miliar)") == "Net profit (Rp bn)"
    assert en("Band P/BV 12 bulan BBRI") == "12M P/BV band, BBRI"
    assert en("Bank Central Asia (BBCA) (emiten)") == "Bank Central Asia (BBCA) (issuer)"
    assert en("(-) Pajak atas EBIT (22,0%)") == "(-) Tax on EBIT (22.0%)"
    assert en("Rp-370,7 miliar") == "Rp-370.7bn"
    assert en("Akumulasi biaya Des-25 (US$m)") == "Accumulated cost Dec-25 (US$m)"
    assert en("Rata-rata target konsensus (8 analis)") == "Consensus target average (8 analysts)"
    # Unknown words stay; only their figures change.
    assert en("Laba tumbuh 17,5% yoy") == "Laba tumbuh 17.5% yoy"
    assert report_lang.label("Laba bersih (Rp miliar)", "id") == "Laba bersih (Rp miliar)"
    assert report_lang.title({"judul": "Rantai metode valuasi", "exhibit_id": "method_chain"},
                             "en") == "Valuation Method Chain"


def test_file_names_per_language():
    assert report_lang.file_name("ammn") == "AMMN.html"
    assert report_lang.file_name("AMMN", "en", "pdf") == "AMMN.en.pdf"


def test_exhibits_are_found_by_id_and_old_reports_by_title():
    new = {"judul": "Ikhtisar keuangan", "exhibit_id": "key_financials"}
    old = {"judul": "Key Financials"}
    assert exhibit_ids.find([{"judul": "Neraca"}, new], exhibit_ids.KEY_FINANCIALS) is new
    assert exhibit_ids.find([old], exhibit_ids.KEY_FINANCIALS) is old
    # An exhibit with another id is never matched by its title.
    assert not exhibit_ids.is_exhibit({"judul": "Key Financials", "exhibit_id": "x"},
                                      exhibit_ids.KEY_FINANCIALS)
    assert exhibit_ids.is_exhibit({"judul": "Pendapatan dan pertumbuhan (2024A-FY28F)"},
                                  exhibit_ids.REVENUE_PANEL)


def test_english_files_stay_off_public_routes(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app import server
    from test_gallery import _report

    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    (reports / "AAAA.en.html").write_text("<html lang='en'>report</html>")
    (reports / "AAAA.en.pdf").write_bytes(b"%PDF-1.4 english")
    item = gallery.load(reports)[0]
    assert item["published"] and item["languages"] == ["id"]
    assert set(item["files"]) == {"pdf", "html", "trace", "trace_json"}
    assert gallery.public_artifact(reports, "AAAA", "html_en") is None
    client = TestClient(server.create_app(tmp_path / "jobs", reports, static_dir=None))
    assert client.get("/files/reports/AAAA.html").status_code == 200
    for name in ("AAAA.en.html", "AAAA.en.pdf"):
        assert client.get(f"/files/reports/{name}").status_code == 404
    # An authenticated reviewer can read the English file.
    secret = "review-secret-for-language-test-01"
    monkeypatch.setenv("SECTORAL_REVIEWERS", json.dumps([{
        "id": "reviewer-language", "name": "Reviewer", "role": "reviewer",
        "token_sha256": hashlib.sha256(secret.encode()).hexdigest()}]))
    url = "/api/reports/AAAA/artifact-preview/html_en"
    assert client.get(url).status_code == 403
    preview = client.get(url, headers={"X-Review-Token": secret})
    assert preview.status_code == 200 and "lang='en'" in preview.text


def test_a_draft_lists_no_language(tmp_path):
    from test_gallery import _report

    _report(tmp_path, "BBBB", published=False)
    assert gallery.load(tmp_path)[0]["languages"] == []


def test_indonesian_render_does_not_depend_on_the_english_one(monkeypatch):
    monkeypatch.setattr(render, "_price_window", lambda *_args: None)
    doc = _doc()
    before = render.render(copy.deepcopy(doc))
    render.render(doc, lang="en")
    assert render.render(doc) == before
