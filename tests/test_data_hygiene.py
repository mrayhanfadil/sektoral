"""Tests for Lane 1: P0 intake, data, and render hygiene.

Findings tested:
1. EBITDA == 0 with positive EBIT (and EBITDA < EBIT) yields invalid D&A:
   - Sourced depreciation metric is preferred if present.
   - Without sourced depreciation, missing/invalid status is preserved (da is None).
   - Never hidden with max(0, ...) or assumed values.
   - Disclosed in intake catatan/notes so report cannot claim valid cash flow.
2. Missing cash is preserved as unavailable (None) rather than coerced to 0 or Rp0.
   - fmt helpers (_id, rp, miliar, pct, mult, revenue_idr) return 'n.a.' for None.
   - Render handles missing cash and figures without displaying Rp0 or crashing.
3. Dash hygiene:
   - Spec bans long dashes (U+2013 en-dash and U+2014 em-dash).
   - Rendered HTML and text contain zero U+2013 or U+2014 characters.
   - Indonesian wording and number formatting are preserved.
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import fmt, intake, render, build  # noqa: E402


def test_fmt_none_and_invalid_inputs_return_na():
    """Missing values must not be coerced to 0 or Rp0, but rendered as n.a."""
    assert fmt.rp(None) == "n.a."
    assert fmt.miliar(None) == "n.a."
    assert fmt.pct(None) == "n.a."
    assert fmt.mult(None) == "n.a."
    assert fmt._id(None) == "n.a."
    assert fmt.pe(None) == "n.a."
    assert fmt.margin(None) == "n.a."
    assert fmt.revenue_idr(None) == "n.a."

    # Non-numeric strings or bad types
    assert fmt.rp("invalid") == "n.a."
    assert fmt.miliar("invalid") == "n.a."
    assert fmt.pct("invalid") == "n.a."
    assert fmt.mult("invalid") == "n.a."
    assert fmt._id("invalid") == "n.a."


def test_fmt_valid_indonesian_formatting():
    """Ensure Indonesian number conventions are preserved (thousand dot, decimal comma)."""
    assert fmt.rp(1250000) == "1.250.000"
    assert fmt.miliar(1500000000) == "1,5"
    assert fmt.pct(0.125, 1) == "12,5%"
    assert fmt.mult(14.2, 1) == "14,2x"
    assert fmt.pe(15.5) == "15,5x"
    assert fmt.pe(0) == "n.m."
    assert fmt.pe(-5) == "n.m."
    assert fmt.pe(250) == "n.m."


def test_fmt_clean_dashes():
    """clean_dashes replaces en-dash and em-dash with standard hyphens."""
    raw = "2024\u20132025 dan catatan\u2014penting"
    cleaned = fmt.clean_dashes(raw)
    assert "\u2013" not in cleaned
    assert "\u2014" not in cleaned
    assert cleaned == "2024-2025 dan catatan - penting"


def test_intake_ebitda_zero_with_positive_ebit_preserves_none_and_discloses(monkeypatch):
    """When ebitda == 0 and ebit > 0, D&A is invalid (not max(0, ...) = 0).

    Preserve da = None and disclose in notes.
    """
    sample_report = {
        "company_name": "Test Issuer",
        "overview": {
            "last_close_price": 1000,
            "latest_close_date": "2026-09-01",
            "industry": "Mining",
        },
        "financials": {
            "historical_financials": [
                {"year": 2022, "revenue": 1000, "ebitda": 300, "ebit": 200, "outstanding_shares": 100},
                {"year": 2023, "revenue": 1200, "ebitda": 400, "ebit": 250, "outstanding_shares": 100},
                # 2024 has ebitda == 0 but ebit == 300
                {"year": 2024, "revenue": 1500, "ebitda": 0, "ebit": 300, "outstanding_shares": 100},
            ]
        },
    }
    monkeypatch.setattr(intake.cache, "payloads", lambda ep: [("key", sample_report)])
    monkeypatch.setattr(intake.cache, "company_report", lambda t: sample_report)
    monkeypatch.setattr(intake.cache, "first", lambda ep: {})

    data, log = intake.load("TEST")
    annuals = data["annuals"]
    assert len(annuals) == 3

    # 2022 and 2023 calculate normal D&A (100 and 150)
    assert annuals[0]["da"] == 100
    assert annuals[1]["da"] == 150

    # 2024 D&A must be None (never 0 via max(0, ...))
    assert annuals[2]["da"] is None

    # Must be disclosed in notes
    notes = log.get("catatan", [])
    assert any("D&A tahun 2024 tidak valid di data Sectors" in note for note in notes)


def test_intake_uses_sourced_depreciation_metric_if_present(monkeypatch):
    """If a sourced depreciation metric is in cache row, use it even if ebitda is 0."""
    sample_report = {
        "company_name": "Test Sourced Deprec",
        "overview": {
            "last_close_price": 1000,
            "latest_close_date": "2026-09-01",
            "industry": "Mining",
        },
        "financials": {
            "historical_financials": [
                {"year": 2022, "revenue": 1000, "ebitda": 300, "ebit": 200, "outstanding_shares": 100},
                {"year": 2023, "revenue": 1200, "ebitda": 400, "ebit": 250, "outstanding_shares": 100},
                # 2024 has ebitda == 0, ebit == 300, but sourced depreciation == 80
                {
                    "year": 2024,
                    "revenue": 1500,
                    "ebitda": 0,
                    "ebit": 300,
                    "depreciation": 80,
                    "outstanding_shares": 100,
                },
            ]
        },
    }
    monkeypatch.setattr(intake.cache, "payloads", lambda ep: [("key", sample_report)])
    monkeypatch.setattr(intake.cache, "company_report", lambda t: sample_report)
    monkeypatch.setattr(intake.cache, "first", lambda ep: {})

    data, log = intake.load("TEST")
    annuals = data["annuals"]
    assert annuals[2]["da"] == 80


def test_intake_missing_cash_preserves_none_and_discloses(monkeypatch):
    """Missing cash in cache must be preserved as None and disclosed in notes."""
    sample_report = {
        "company_name": "Test Missing Cash",
        "overview": {
            "last_close_price": 1000,
            "latest_close_date": "2026-09-01",
            "industry": "Mining",
        },
        "financials": {
            "historical_financials": [
                {"year": 2022, "revenue": 1000, "ebitda": 300, "ebit": 200, "cash_and_equivalents": 50, "outstanding_shares": 100},
                {"year": 2023, "revenue": 1200, "ebitda": 400, "ebit": 250, "cash_and_equivalents": 60, "outstanding_shares": 100},
                # 2024 has no cash field
                {"year": 2024, "revenue": 1500, "ebitda": 500, "ebit": 350, "outstanding_shares": 100},
            ]
        },
    }
    monkeypatch.setattr(intake.cache, "payloads", lambda ep: [("key", sample_report)])
    monkeypatch.setattr(intake.cache, "company_report", lambda t: sample_report)
    monkeypatch.setattr(intake.cache, "first", lambda ep: {})

    data, log = intake.load("TEST")
    annuals = data["annuals"]
    assert annuals[2]["cash"] is None

    notes = log.get("catatan", [])
    assert any("posisi kas tahun dasar 2024 tidak tersedia di data Sectors" in note for note in notes)


def test_render_no_long_dashes_u2013_u2014():
    """Rendered report HTML and text must contain NO en-dash (U+2013) or em-dash (U+2014)."""
    doc = {
        "meta": {
            "ticker": "TEST",
            "emiten": "PT Uji Sektoral",
            "tanggal": "2026-09-23",
            "harga_tanggal": "2026-09-23",
            "harga": 1500,
            "tp": 2000,
            "tp_sebelumnya": "1.800",
            "upside_persen": 33.3,
            "rating": "BELI",
            "status": "distributable",
        },
        "cover": {
            "headline": "Tinjauan Kinerja 2024\u20132025 \u2014 Pertumbuhan Solid",
            "bullets": [
                "Pertumbuhan pendapatan 15%\u201320% pada FY26F",
                "Arus kas operasional membaik \u2014 efisiensi biaya tercapai",
            ],
            "paragraf": [
                {"judul": "Tesis Investasi", "isi": "Kinerja FY24\u2013FY25 menunjukkan daya tahan marjin."}
            ],
            "data_pasar": {
                "saham": 1000000000,
                "market_cap": 1500000000000,
                "adtv": "25,0",
                "free_float": "40,0",
            },
        },
        "holders": [["Pemegang Mayoritas", "60,0%"]],
        "fy26": {
            "Pendapatan": "2.500,0",
            "EBITDA": "800,0",
            "Laba bersih": "500,0",
        },
        "exhibits": [
            {
                "n": 1,
                "judul": "Ringkasan Finansial FY23\u2013FY26F",
                "tipe": "tabel",
                "data": {
                    "cols": ["Metrik", "FY23", "FY24", "FY25F", "FY26F"],
                    "rows": [
                        ["Pendapatan", "1.000", "1.200", "1.400", "1.600"],
                        ["EBITDA", "300", "350", "400", "450"],
                    ],
                },
                "catatan_sumber": "Sumber: Laporan Keuangan \u2014 diolah oleh Sektoral",
            }
        ],
        "bagian": [],
        "catatan_metodologi": [
            "Estimasi didasarkan pada data historis 2021\u20132025.",
        ],
    }

    html_out = render.render(doc)

    assert "\u2013" not in html_out, f"Found en-dash U+2013 in rendered HTML: {html_out}"
    assert "\u2014" not in html_out, f"Found em-dash U+2014 in rendered HTML: {html_out}"
    assert "Equity Research - Company Update" in html_out
    assert "Ringkasan Finansial FY23-FY26F" in html_out


def test_rendered_report_on_ammn_has_no_long_dashes(tmp_path):
    """Integration test: build AMMN report and verify zero U+2013 and U+2014 in output HTML."""
    doc = build.build("AMMN", tmp_path)
    html_path = tmp_path / "AMMN.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")

    assert "\u2013" not in html_content, "Found U+2013 en-dash in built AMMN.html"
    assert "\u2014" not in html_content, "Found U+2014 em-dash in built AMMN.html"


def test_doc_prose_pass_normalises_periods_outside_agent_plans():
    from app import scrub
    doc = {"cover": {"headline": "Laba naik", "bullets": ["Capex sampai Q4 2027."],
                     "paragraf": [{"judul": "Valuasi", "isi": "Selesai hingga Q4 2027; H1 2026 naik."}]},
           "bagian": [{"paragraf": ["CIP berjalan sampai Q4 2027."]}],
           "risks": [{"isi": "Tertunda ke Q1 2028."}],
           "exhibits": [{"narasi": "Pendapatan H1 2026 naik.", "catatan_sumber": "Q4 2027 report"}]}
    scrub.normalize_doc_prose(doc)
    assert doc["cover"]["paragraf"][0]["isi"] == "Selesai hingga 4Q27; 1H26 naik."
    assert doc["cover"]["bullets"] == ["Capex sampai 4Q27."]
    assert doc["bagian"][0]["paragraf"] == ["CIP berjalan sampai 4Q27."]
    assert doc["risks"][0]["isi"] == "Tertunda ke 1Q28."
    assert doc["exhibits"][0]["narasi"] == "Pendapatan 1H26 naik."
    assert doc["exhibits"][0]["catatan_sumber"] == "Q4 2027 report"  # provenance untouched
