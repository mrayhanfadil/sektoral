"""Focused test suite for official issuer interim evidence packs.

Validates that each ticker evidence pack:
1. Conforms to schema_version 1.
2. Contains verified provenance: official source_title, stable HTTPS source_url, exact page,
   period, period_end, and publication date.
3. Ensures strict date consistency (period_end <= published_at <= report as_of date).
4. Verifies presence and numeric typing of required financial metrics (revenue, net_profit).
5. Validates integration with app.issuer_evidence and app.intake.
"""
from datetime import date
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import intake, issuer_evidence  # noqa: E402
from app.release import assess_release  # noqa: E402

EVIDENCE_DIR = ROOT / "data" / "issuer_evidence"
TARGET_TICKERS = ["BBRI", "INET", "JPFA", "POWR", "SIDO", "SSIA"]
VERIFIED_TICKERS = ["BBRI", "INET", "JPFA", "POWR", "SIDO", "SSIA"]
ALL_KNOWN_TICKERS = ["AMMN", "BBRI", "GMFI", "INET", "JPFA", "POWR", "SIDO", "SSIA"]
REPORT_AS_OF = "2026-09-22"

VERIFIED_PRIMARY = {
    "BBRI": {
        "source_url": "https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/From_EREP/202608/20260831171524-64205-0/FinancialStatement-2026-II-BBRI.pdf",
        "metrics": {"revenue": 107_923_454_000_000, "net_interest_income": 80_530_442_000_000,
                    "net_profit": 31_182_586_000_000, "net_profit_attributable": 30_865_402_000_000},
    },
    "INET": {
        "source_url": "https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/From_EREP/202609/7cc0570c87_86a3531070.pdf",
        "metrics": {"revenue": 926_453_327_140, "gross_profit": 122_106_633_456,
                    "operating_profit": 71_362_909_254, "net_profit": 34_210_434_283,
                    "net_profit_attributable": 33_671_188_228},
    },
    "JPFA": {
        "source_url": "https://www.idx.co.id/Portals/0/StaticData/ListedCompanies/Corporate_Actions/New_Info_JSX/Jenis_Informasi/01_Laporan_Keuangan/02_Soft_Copy_Laporan_Keuangan//Laporan%20Keuangan%20Tahun%202026/TW2/JPFA/PT%20Japfa%20Tbk%20CFS%2030%20June%202026%20Unaudited.pdf",
        "metrics": {"revenue": 35_355_127_000_000, "gross_profit": 7_625_189_000_000,
                    "net_profit": 2_684_344_000_000, "net_profit_attributable": 2_475_417_000_000},
    },
    "POWR": {
        "source_url": "https://www.listrindo.com/uploads/idx/1fb0306b5c1f30d0319115d5eb5abacb.pdf",
        "metrics": {"revenue": 274_783_475, "operating_profit": 60_493_834,
                    "net_profit": 37_140_130},
    },
    "SIDO": {
        "source_url": "https://www.indopremier.com/xdir/news/LAPORAN%20KEUANGAN/2026/q2/SIDO_Q2_2026.pdf",
        "metrics": {"revenue": 1_466_658_000_000, "gross_profit": 740_745_000_000,
                    "net_profit": 333_653_000_000, "net_profit_attributable": 333_653_000_000},
    },
    "SSIA": {
        "source_url": "https://suryainternusa.com/assets/source/files/press-release/2026.08.04_press-release-ssia-1h26_eng_v2_ebu.pdf",
        "metrics": {"revenue": 3_353_500_000_000, "gross_profit": 1_086_200_000_000,
                    "ebitda": 692_500_000_000, "net_profit": 262_600_000_000},
    },
}


@pytest.mark.parametrize("ticker", ALL_KNOWN_TICKERS)
def test_evidence_file_exists_and_parses_json(ticker):
    file_path = EVIDENCE_DIR / f"{ticker}.json"
    assert file_path.exists(), f"Evidence file missing: {file_path}"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"Evidence for {ticker} must be a JSON object"


@pytest.mark.parametrize("ticker", ALL_KNOWN_TICKERS)
def test_evidence_schema_identity(ticker):
    file_path = EVIDENCE_DIR / f"{ticker}.json"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    assert data.get("ticker") == ticker
    assert data.get("reporting_currency") in {"IDR", "USD"}


@pytest.mark.parametrize("ticker", ALL_KNOWN_TICKERS)
def test_evidence_latest_actual_provenance(ticker):
    file_path = EVIDENCE_DIR / f"{ticker}.json"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    actual = data.get("latest_actual")
    assert isinstance(actual, dict), f"Missing latest_actual in {ticker}"

    required_fields = ["period", "period_end", "published_at", "source_title", "source_url", "page", "unit", "metrics"]
    for field in required_fields:
        assert actual.get(field), f"Missing field '{field}' in {ticker}.latest_actual"

    # HTTPS URL requirement
    assert actual["source_url"].startswith("https://"), f"{ticker} source_url must be HTTPS"

    # Valid page number or label
    assert (isinstance(actual["page"], int) and actual["page"] > 0) or (
        isinstance(actual["page"], str) and actual["page"].strip()
    )

    # Date ordering
    period_end = date.fromisoformat(actual["period_end"])
    published_at = date.fromisoformat(actual["published_at"])
    as_of = date.fromisoformat(REPORT_AS_OF)

    assert period_end <= published_at, f"{ticker}: period_end ({period_end}) must be <= published_at ({published_at})"
    assert published_at <= as_of, f"{ticker}: published_at ({published_at}) must be <= as_of ({as_of})"


@pytest.mark.parametrize("ticker", TARGET_TICKERS)
def test_evidence_points_to_verified_document_and_exact_reported_values(ticker):
    actual = json.loads((EVIDENCE_DIR / f"{ticker}.json").read_text(encoding="utf-8"))["latest_actual"]
    expected = VERIFIED_PRIMARY[ticker]
    assert actual["source_url"] == expected["source_url"]
    for metric, exact_value in expected["metrics"].items():
        assert actual["metrics"].get(metric) == exact_value, (
            f"{ticker}.{metric}: expected {exact_value}, got {actual['metrics'].get(metric)}"
        )


@pytest.mark.parametrize("ticker", ALL_KNOWN_TICKERS)
def test_evidence_metrics_numeric_and_complete(ticker):
    file_path = EVIDENCE_DIR / f"{ticker}.json"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    actual = data.get("latest_actual", {})
    metrics = actual.get("metrics", {})

    assert isinstance(metrics, dict) and metrics, f"{ticker} metrics must be a non-empty dictionary"

    # Required financial metrics
    assert "revenue" in metrics, f"{ticker} missing 'revenue' metric"
    assert "net_profit" in metrics, f"{ticker} missing 'net_profit' metric"

    for key, val in metrics.items():
        assert isinstance(val, (int, float)) and not isinstance(val, bool), (
            f"{ticker} metric {key} must be numeric, got {type(val)}: {val}"
        )


@pytest.mark.parametrize("ticker", VERIFIED_TICKERS)
def test_evidence_loader_integration(ticker):
    loaded = issuer_evidence.load(ticker, REPORT_AS_OF)
    assert loaded is not None, f"issuer_evidence.load failed for {ticker}"
    assert loaded["ticker"] == ticker
    assert loaded["latest_actual"]["published_at"] <= REPORT_AS_OF


def test_sido_publication_date_is_a_corroborated_upper_bound():
    """The IDX filing date could not be read, so the pack dates the mirrored
    statement at the first independent report of the same figures."""
    actual = json.loads((EVIDENCE_DIR / "SIDO.json").read_text(encoding="utf-8"))["latest_actual"]
    assert actual["published_at"] == "2026-08-03"
    assert actual["corroboration_url"].startswith("https://")
    assert "batas atas" in actual["published_at_basis"]
    assert issuer_evidence.load("SIDO", REPORT_AS_OF) is not None
    assert issuer_evidence.load("SIDO", "2026-08-02") is None


def test_blocked_evidence_pack_is_not_loaded(tmp_path, monkeypatch):
    pack = json.loads((EVIDENCE_DIR / "SIDO.json").read_text(encoding="utf-8"))
    pack.update(evidence_status="blocked", evidence_status_reason="publication date unverified")
    (tmp_path / "SIDO.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(issuer_evidence, "ROOT", tmp_path)
    assert issuer_evidence.load("SIDO", REPORT_AS_OF) is None


@pytest.mark.parametrize("ticker", VERIFIED_TICKERS)
def test_intake_loads_official_evidence_for_target_tickers(ticker):
    intake_data, _ = intake.load(ticker)
    assert intake_data["official_evidence"] is not None
    assert intake_data["latest_official_actual"] is not None
    assert intake_data["latest_official_actual"]["period"] == "1H26"
    assert intake_data["latest_official_actual"]["metrics"]["revenue"] > 0
    assert intake_data["latest_official_actual"]["metrics"]["net_profit"] > 0


@pytest.mark.parametrize("ticker", VERIFIED_TICKERS)
def test_release_assessment_official_actual_blockers_cleared(ticker):
    intake_data, _ = intake.load(ticker)
    profile = intake_data["model_profile"]
    forecast = {"forecast_basis": "driver_forecast", "production_ready": True}
    sotp_result = "draft" if profile == "financial_ddm" else None

    result = assess_release(profile, intake_data, forecast, sotp_result)
    assert "latest official interim actual is missing or unverified" not in result["blockers"]
    assert "latest official interim actual has incomplete provenance" not in result["blockers"]
    assert "latest official interim revenue/net profit are missing" not in result["blockers"]
    assert "latest official interim dates are inconsistent" not in result["blockers"]


# Audited annual D&A read from the consolidated statements: the depreciation line
# of the segment note (fixed assets + investment properties + right-of-use), and
# operating profit ("Laba usaha") from the income statement, full Rupiah.
AUDITED_DEPRECIATION = {
    # Fixed-asset depreciation (Catatan 7) + right-of-use depreciation (Catatan 8).
    "INET": {
        2024: {"depreciation": 2_439_150_301 + 144_239_903, "operating_profit": 1_310_294_737},
        2025: {"depreciation": 14_309_448_849 + 172_622_362, "operating_profit": 30_322_656_374},
    },
    "SSIA": {
        2024: {"depreciation": 160_474_192_622, "operating_profit": 845_923_357_770},
        2025: {"depreciation": 175_460_879_268, "operating_profit": 215_715_597_257},
    },
    # FY2025 audited statements: laba rugi PDF p.15, segment note 35 PDF p.95
    # ("Penyusutan dan amortisasi"), fixed-asset roll-forward note 10 PDF p.61-62.
    "SIDO": {
        2024: {"depreciation": 107_597_000_000, "operating_profit": 1_471_483_000_000,
               "net_profit": 1_171_026_000_000, "revenue": 3_919_084_000_000},
        2025: {"depreciation": 125_835_000_000, "operating_profit": 1_544_117_000_000,
               "net_profit": 1_229_202_000_000, "revenue": 4_079_659_000_000},
    },
}


@pytest.mark.parametrize("ticker", sorted(AUDITED_DEPRECIATION))
def test_audited_annual_depreciation_carries_full_provenance(ticker):
    pack = json.loads((EVIDENCE_DIR / f"{ticker}.json").read_text(encoding="utf-8"))
    source = pack["annual_actuals_source"]
    for field in ("title", "url", "published_at", "pages", "unit", "status"):
        assert source.get(field), f"{ticker}.annual_actuals_source.{field} missing"
    assert source["url"].startswith("https://")
    assert "diaudit" in source["title"]
    assert source["status"] == "aktual"
    assert source["unit"].startswith("IDR")
    assert "Penyusutan" in source["pages"] and "laba rugi" in source["pages"]
    published = date.fromisoformat(source["published_at"])
    assert published <= date.fromisoformat(REPORT_AS_OF)

    rows = {row["year"]: row for row in pack["annual_actuals"]}
    for year, expected in AUDITED_DEPRECIATION[ticker].items():
        row = rows[year]
        assert date(year, 12, 31) < published, f"{ticker} FY{year} published before year end"
        for key, value in expected.items():
            assert row[key] == value, f"{ticker} FY{year} {key}: {row[key]} != {value}"
        for key in ("revenue", "operating_profit", "depreciation", "ebitda", "net_profit",
                    "net_profit_attributable"):
            assert isinstance(row[key], int) and not isinstance(row[key], bool)
        assert row["ebitda"] == row["operating_profit"] + row["depreciation"]

    # The intake takes the audited figures in place of Sectors EBITDA - EBIT, so
    # the asset-life guard never voids them.
    data, _ = intake.load(ticker)
    annuals = {a["year"]: a for a in data["annuals"]}
    for year, expected in AUDITED_DEPRECIATION[ticker].items():
        assert annuals[year]["da"] == expected["depreciation"]
        assert annuals[year]["da_source"] == "official"
        assert annuals[year]["ebit"] == expected["operating_profit"]
        assert annuals[year].get("da_implied_life") is None


def test_inet_interim_balance_sheet_and_cash_flow_tie_to_the_filing():
    """The 30 June 2026 statements the forecast opens from: every line sourced from
    the audited interim report, subtotals and cash tying as the filing prints them."""
    pack = json.loads((EVIDENCE_DIR / "INET.json").read_text(encoding="utf-8"))
    actual, balance = pack["latest_actual"], pack["balance_sheet"]
    assert balance["source_url"] == actual["source_url"]
    assert balance["source_url"].startswith("https://www.idx.co.id/")
    assert balance["published_at"] == actual["published_at"] == "2026-09-11"
    assert balance["period_end"] == actual["period_end"] == "2026-06-30"
    assert balance["status"] == "aktual" and balance["unit"].startswith("IDR")
    lines = ("cash", "trade_receivables", "inventories", "other_current_assets",
             "current_assets", "fixed_assets", "other_non_current_assets", "total_assets",
             "short_term_debt", "trade_payables", "other_current_liabilities",
             "current_liabilities", "long_term_debt", "other_non_current_liabilities",
             "non_current_liabilities", "total_liabilities", "total_debt",
             "equity_attributable", "non_controlling_interest", "total_equity", "shares_issued")
    for key in lines:
        assert isinstance(balance[key], int) and not isinstance(balance[key], bool), key
    b = balance
    assert b["total_assets"] == 6_111_011_414_909 and b["cash"] == 4_336_912_848_074
    assert b["current_assets"] == (b["cash"] + b["trade_receivables"] + b["inventories"]
                                   + b["other_current_assets"]) == 4_720_207_854_212
    assert b["total_assets"] == (b["current_assets"] + b["fixed_assets"]
                                 + b["other_non_current_assets"])
    assert b["current_liabilities"] == (b["short_term_debt"] + b["trade_payables"]
                                        + b["other_current_liabilities"]) == 1_664_779_061_414
    assert b["non_current_liabilities"] == b["long_term_debt"] + b["other_non_current_liabilities"]
    assert b["total_liabilities"] == b["current_liabilities"] + b["non_current_liabilities"]
    assert b["total_assets"] == b["total_liabilities"] + b["total_equity"]
    assert b["total_equity"] == b["equity_attributable"] + b["non_controlling_interest"]
    assert b["total_debt"] == b["short_term_debt"] + b["long_term_debt"] == 1_780_486_487_723
    assert b["shares_issued"] == pack["capital_changes_2026"]["shares_issued_2026_06_30"]
    # 1H26 cash flow: FY2025 cash + net cash flow = the 30 June cash.
    flows = actual["cash_flow"]
    assert flows["cash_begin"] + flows["net_cash_flow"] == b["cash"] == flows["cash_end"]
    assert (flows["operating_cash_flow"] + flows["investing_cash_flow"]
            + flows["financing_cash_flow"]) == flows["net_cash_flow"]
    assert flows["investing_cash_flow"] == (flows["other_investing_cash_flow"]
                                            - flows["capital_expenditure"])
    assert flows["financing_cash_flow"] == (flows["debt_raised"] + flows["equity_raised"]
                                            + flows["other_financing_cash_flow"]
                                            - flows["dividends_paid"])
    for block in flows["components"].values():
        assert all(isinstance(v, int) for v in block.values())
    assert sum(flows["components"]["utang"].values()) == flows["debt_raised"]
    assert flows["cash_begin"] == pack["annual_actuals"][1]["balance_sheet"]["cash"]
    # 1H26 D&A: fixed assets + right-of-use + intangibles (Catatan 14, 15, 36).
    metrics = actual["metrics"]
    assert metrics["depreciation"] == 17_329_773_565 + 462_835_729 + 408_004_576
    assert metrics["capital_expenditure"] == flows["capital_expenditure"]
    assert metrics["dividends_paid"] == flows["dividends_paid"]
    assert "Catatan 14" in actual["metric_sources"]["depreciation"]
    # FY2025 audited year-end balance sheet balances too.
    year = pack["annual_actuals"][1]["balance_sheet"]
    assert year["total_assets"] == year["total_liabilities"] + year["total_equity"]
    assert year["total_equity"] == year["equity_attributable"] + year["non_controlling_interest"]


def test_inet_intake_uses_the_official_depreciation_and_interim_bridge():
    data, _ = intake.load("INET")
    annuals = {a["year"]: a for a in data["annuals"]}
    # The Sectors EBITDA - EBIT (Rp1,1 miliar on Rp282 miliar of assets) is replaced.
    assert annuals[2025]["da"] == 14_482_071_211 and annuals[2025]["da_source"] == "official"
    assert annuals[2025]["ebitda"] == 44_804_727_585
    from app import scenario_value
    ratio, basis = scenario_value.da_intensity(data)
    assert ratio == pytest.approx(18_200_613_870 / 926_453_327_140)
    assert "1H26 resmi" in basis
    link = scenario_value.bridge(data)
    assert link["shares"] == 22_374_111_088
    assert link["cash"] == 4_336_912_848_074 and link["debt"] == 1_780_486_487_723
    assert link["nci"] == 152_191_722_293
    assert str(link["valuation_date"]) == "2026-06-30"
