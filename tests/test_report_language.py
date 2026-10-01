"""The Company Update in two languages: Indonesian unchanged, English labels,
English files public only as part of the published bundle (ADR 0015)."""
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


def test_english_method_chain_states_its_reasons_in_english(monkeypatch):
    """A reason joins release limitations with "; "; each part has English."""
    monkeypatch.setattr(render, "_price_window", lambda *_args: None)
    doc = _doc()
    chain = exhibit_ids.find(doc["exhibits"], exhibit_ids.METHOD_CHAIN)
    reason = ("driver ke depan (pertumbuhan kredit, NIM, pendapatan non-bunga, CIR, biaya kredit) "
              "adalah panduan manajemen untuk tahun pertama dan asumsi analis berlabel sesudahnya; "
              "belum Production-Ready: house-assumption policy became effective after the Report Date")
    chain["data"]["rows"][0][3] = reason
    html = render.render(doc, lang="en")
    assert ("forward drivers (loan growth, NIM, non-interest income, CIR, cost of credit) are "
            "management guidance for the first year and labelled Analyst Assumptions after it; not "
            "yet Production-Ready: house-assumption policy became effective after the Report Date"
            in html)
    assert "belum Production-Ready" not in html
    assert "fewer than three valid peer PERs" in html
    assert reason in render.render(doc)


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
    # Audit appendix cells (the AMMN Q2 rebuild and H1 debt-flow reconciliation).
    assert en("Selisih Q1 ke H1; kedua angka sumber dibulatkan ke US$ juta") == (
        "Q1 to H1 difference; both source figures rounded to US$ mn")
    assert en("Angka rinci laporan keuangan; US$340,0m adalah pelunasan dipercepat yang "
              "termasuk di sini.") == ("Detailed financial statement figure; it includes the "
                                       "US$340.0m accelerated repayment.")
    assert en("Dibanding pembayaran pokok jangka panjang rinci US$580,866m, selisih nominal "
              "US$7,134m belum direkonsiliasi; basis keduanya belum terbukti sama.") == (
        "Against detailed long-term principal repayments of US$580.866m, a nominal difference "
        "of US$7.134m is not yet reconciled; the two are not shown to share a basis.")
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


def _client(tmp_path, reports):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app import server
    return TestClient(server.create_app(tmp_path / "jobs", reports, static_dir=None))


def test_english_files_outside_the_bundle_stay_off_public_routes(tmp_path, monkeypatch):
    from test_gallery import _report

    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    # Written after the bundle was finalized and approved: not part of it.
    (reports / "AAAA.en.html").write_text("<html lang='en'>report</html>")
    (reports / "AAAA.en.pdf").write_bytes(b"%PDF-1.4 english")
    item = gallery.load(reports)[0]
    assert item["published"] and item["languages"] == ["id"]
    assert item["publication_state"] == "published"
    assert set(item["files"]) == {"pdf", "html", "trace", "trace_json", "html_en", "pdf_en"}
    assert item["files"]["html_en"] is False and item["files"]["pdf_en"] is False
    assert gallery.public_artifact(reports, "AAAA", "html_en") is None
    client = _client(tmp_path, reports)
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


def test_english_in_the_approved_bundle_is_public_until_its_bytes_change(tmp_path, monkeypatch):
    from test_gallery import _report

    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA", english=True)
    item = gallery.load(reports)[0]
    assert item["publication_basis"] == "analyst_reviewed"
    assert item["languages"] == ["id", "en"]
    assert item["files"]["html_en"] and item["files"]["pdf_en"]
    client = _client(tmp_path, reports)
    listed = client.get("/api/reports").json()["items"][0]
    assert listed["languages"] == ["id", "en"]
    assert listed["files"]["html_en"] is True and listed["files"]["pdf_en"] is True
    english = client.get("/files/reports/AAAA.en.html")
    assert english.status_code == 200 and "lang='en'" in english.text
    pdf = client.get("/files/reports/AAAA.en.pdf")
    assert pdf.status_code == 200 and pdf.content == b"%PDF-1.4 english"

    # A changed English file is no longer the approved bundle: the approval
    # goes stale, and the English file is served by no public route.
    (reports / "AAAA.en.html").write_text("<html lang='en'>edited</html>")
    assert client.get("/files/reports/AAAA.en.html").status_code == 404
    item = gallery.load(reports)[0]
    assert item["review"]["state"] == "pending" and item["languages"] == ["id"]
    assert item["publication_basis"] == "automatic"  # ADR 0014: the gates still pass
    monkeypatch.setenv("SECTORAL_AUTO_PUBLISH", "0")
    assert gallery.load(reports)[0]["languages"] == []
    for name in ("AAAA.html", "AAAA.en.html", "AAAA.en.pdf"):
        assert client.get(f"/files/reports/{name}").status_code == 404


def test_automatic_publication_serves_english_from_its_run_manifest(tmp_path):
    from app import outputs
    from test_gallery import _report

    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA", reviewed=False, english=True)
    item = gallery.load(reports)[0]
    assert item["publication_basis"] == "automatic" and item["languages"] == ["id", "en"]
    client = _client(tmp_path, reports)
    assert client.get("/files/reports/AAAA.en.pdf").status_code == 200

    # The run manifest is the automatic bundle: a changed English PDF is not served.
    (reports / "AAAA.en.pdf").write_bytes(b"%PDF-1.4 replaced")
    assert client.get("/files/reports/AAAA.en.pdf").status_code == 404
    assert client.get("/files/reports/AAAA.en.html").status_code == 200
    assert gallery.load(reports)[0]["files"]["pdf_en"] is False

    # A manifest finalized without English publishes none, whatever file exists.
    manifest = outputs.load(outputs.MANIFEST, reports, "AAAA")
    manifest["artifacts"] = {kind: row for kind, row in manifest["artifacts"].items()
                             if not kind.endswith("_en")}
    outputs.save(outputs.MANIFEST, reports, "AAAA", manifest)
    item = gallery.load(reports)[0]
    assert item["published"] and item["languages"] == ["id"]
    assert client.get("/files/reports/AAAA.en.html").status_code == 404


def test_the_english_cover_route_serves_the_english_pdf_cover(tmp_path, monkeypatch):
    from test_gallery import _render_covers, _report

    reports = tmp_path / "reports"
    reports.mkdir()
    _render_covers(monkeypatch)
    _report(reports, "AAAA", reviewed=False, english=True)
    _report(reports, "BBBB", reviewed=False)
    client = _client(tmp_path, reports)
    english = client.get("/files/reports/AAAA/cover.en.png")
    assert english.status_code == 200 and english.content == b"%PDF-1.4 english"
    assert english.headers["content-type"] == "image/png"
    assert client.get("/files/reports/AAAA/cover.png").content == b"%PDF-1.4 test"
    assert client.get("/files/reports/BBBB/cover.png").status_code == 200
    assert client.get("/files/reports/BBBB/cover.en.png").status_code == 404

def test_a_draft_lists_no_language(tmp_path):
    from test_gallery import _report

    _report(tmp_path, "BBBB", published=False, english=True)
    item = gallery.load(tmp_path)[0]
    assert item["languages"] == [] and not item["files"]["html_en"]
    assert gallery.public_artifact(tmp_path, "BBBB", "html_en") is None


def test_indonesian_render_does_not_depend_on_the_english_one(monkeypatch):
    monkeypatch.setattr(render, "_price_window", lambda *_args: None)
    doc = _doc()
    before = render.render(copy.deepcopy(doc))
    render.render(doc, lang="en")
    assert render.render(doc) == before
