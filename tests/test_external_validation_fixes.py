"""Fixes from validating the 9-ticker e2e run against external sources
(docs/e2e-self-review-2026-09-25.md, "Validasi eksternal")."""
from datetime import date, timedelta
import json

import pandas as pd

from app import fx, intake, market_quote, peer_fundamentals, scenario_value


def _annual(year, revenue, ebitda, ebit, fixed_assets):
    return {"year": year, "revenue": revenue, "ebitda": ebitda, "ebit": ebit,
            "da": ebitda - ebit, "fixed_assets": fixed_assets}


# --- D&A: Sectors EBITDA - EBIT is not depreciation for most issuers --------

def test_depreciation_implying_an_eighty_year_asset_life_is_voided():
    # JPFA FY2025 in Sectors: D&A Rp236 miliar on Rp18.684 miliar of fixed assets.
    annuals = [_annual(2025, 60_716e9, 6_525e9, 6_289e9, 18_684e9)]
    notes = intake._implausible_depreciation(annuals)
    assert annuals[0]["da"] is None
    assert "79 tahun" in notes[0] and "di atas 40 tahun" in notes[0]


def test_credible_depreciation_is_kept():
    # POWR: about 13 years.
    annuals = [_annual(2025, 9_264e9, 2_980e9, 2_008e9, 12_762e9)]
    assert intake._implausible_depreciation(annuals) == []
    assert annuals[0]["da"] == 972e9


def test_audited_annual_depreciation_replaces_sectors_ebitda():
    annuals = [_annual(2025, 60_716e9, 6_525e9, 6_289e9, 18_684e9)]
    evidence = {"reporting_currency": "IDR",
                "annual_actuals_source": {"title": "laporan audit FY2025"},
                "annual_actuals": [{"year": 2025, "operating_profit": 6_183_584e6,
                                    "depreciation": 1_265_023e6}]}
    notes = intake._official_annual_depreciation(annuals, evidence)
    assert annuals[0]["da"] == 1_265_023e6
    assert annuals[0]["ebitda"] == 6_183_584e6 + 1_265_023e6
    assert annuals[0]["da_source"] == "official"
    # The audited figure survives the plausibility guard (life ~15 years).
    assert intake._implausible_depreciation(annuals) == []
    assert "laporan audit FY2025" in notes[0]
    ratio, basis = scenario_value.da_intensity({"annuals": annuals})
    assert abs(ratio - 1_265_023e6 / 60_716e9) < 1e-12 and "audit" in basis


def test_jpfa_intake_uses_the_audited_depreciation():
    data, log = intake.load("JPFA", "2026-09-24")
    fy25 = next(a for a in data["annuals"] if a["year"] == 2025)
    assert fy25["da"] == 1_265_023_000_000 and fy25["da_source"] == "official"
    assert any("laporan audit" in n or "Laporan Keuangan Konsolidasian" in n
               for n in log["catatan"])


def test_dcf_without_credible_depreciation_is_not_adequate():
    ratio, basis = scenario_value.da_intensity({"annuals": []})
    assert ratio is None and "D&A tidak tersedia" in basis


# --- Dividends paid after the bridge's balance-sheet date -------------------

def test_dividend_after_the_balance_sheet_date_leaves_the_equity():
    out = scenario_value._distributions(
        {"as_of": "2026-09-24",
         "dividend_events": [{"date": "2025-06-10", "dps": 30.0},
                             {"date": "2026-05-11", "dps": 140.0},
                             {"date": "2026-10-01", "dps": 50.0}]},
        date(2025, 12, 31), 1_000)
    assert out["distributions"] == 140.0 * 1_000
    assert "2026-05-11" in out["distributions_basis"]


def test_no_dividend_after_the_anchor_means_no_deduction():
    out = scenario_value._distributions(
        {"as_of": "2026-09-24", "dividend_events": [{"date": "2026-04-21", "dps": 346.0}]},
        date(2026, 6, 30), 1_000)
    assert out == {"distributions": 0.0}


# --- Payout: last twelve months of dividends over the last fiscal year's EPS -

def test_bbri_payout_is_the_share_of_fy2025_profit_actually_paid():
    data, _ = intake.load("BBRI", "2026-09-24")
    assert 0.91 < data["payout"] < 0.93          # Sectors payout_ratio says 83,2%
    assert data["payout_basis"].startswith("DPS 12 bulan terakhir Rp346")


# --- The discount rate the price implies ------------------------------------

def test_implied_rate_recovers_the_gordon_rate():
    dps, g = 100.0, 0.03
    per_share = lambda rate: dps / (rate - g)
    assert abs(scenario_value.implied_rate(per_share, dps / (0.12 - g), g) - 0.12) < 1e-6
    assert scenario_value.implied_rate(per_share, 0, g) is None


# --- Dated closes -----------------------------------------------------------

def test_quote_pack_serves_the_latest_close_on_or_before_the_report_date(tmp_path, monkeypatch):
    pack = {"ticker": "SSIA", "currency": "IDR", "price": 1750, "date": "2026-09-24",
            "source_title": "Yahoo Finance SSIA.JK daily close",
            "source_url": "https://finance.yahoo.com/quote/SSIA.JK/history/",
            "closes": [{"date": "2026-09-22", "price": 1600},
                       {"date": "2026-09-23", "price": 1715},
                       {"date": "2026-09-24", "price": 1750}]}
    (tmp_path / "SSIA.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(market_quote, "ROOT", tmp_path)
    assert market_quote.load("SSIA", "2026-09-24", "2026-09-22")["price"] == 1750
    assert market_quote.load("SSIA", "2026-09-23", "2026-09-22")["price"] == 1715
    assert market_quote.load("SSIA", "2026-09-22", "2026-09-22") is None   # not newer than cache


class _History:
    def __init__(self, closes):
        self._frame = pd.DataFrame({"Close": list(closes.values())},
                                   index=pd.to_datetime(list(closes)))

    def history(self, **_kwargs):
        return self._frame


def test_fx_ignores_todays_live_bar():
    today = date.today()
    closes = {(today - timedelta(days=1)).isoformat(): 17_805.0, today.isoformat(): 17_878.0}
    quote = fx.fetch_usd_idr(lambda _symbol: _History(closes))
    assert quote["rate"] == 17_805.0 and quote["date"] == (today - timedelta(days=1)).isoformat()


# --- Peer EV/EBITDA on the latest twelve months -----------------------------

class _Peer:
    def __init__(self):
        quarters = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"])
        self.quarterly_income_stmt = pd.DataFrame(
            [[160.0, 150.0, 170.0, 165.0], [400.0, 390.0, 410.0, 405.0]],
            index=["EBITDA", "Total Revenue"], columns=quarters)
        self.quarterly_balance_sheet = pd.DataFrame(
            [[800.0], [200.0]], index=["Total Debt", "Cash And Cash Equivalents"],
            columns=quarters[:1])
        self.info = {"financialCurrency": "IDR"}


def test_peer_snapshot_sums_the_last_four_quarters():
    snap = peer_fundamentals.fetch("LINK", lambda _symbol: _Peer())
    assert snap["period"] == "TTM" and snap["ebitda"] == 645.0
    assert snap["total_debt"] == 800.0 and snap["period_end"] == "2026-06-30"
    assert snap["period_label"] == "12 bulan s.d. 2026-06-30"
