"""Curated peer groups (data/peer_groups): comparable businesses, one row set."""
from datetime import date, timedelta
import json

import pandas as pd
import pytest

from app import intake, peer_fundamentals, peer_groups, store
from agents.analyst import tools

TICKERS = ("AMMN", "GMFI", "INET", "JPFA", "POWR", "SIDO", "SSIA")


@pytest.mark.parametrize("ticker", TICKERS)
def test_every_pack_names_its_peers_and_exclusions_with_reasons(ticker):
    group = peer_groups.load(ticker)
    assert group["ticker"] == ticker and len(group["peers"]) >= 3
    assert group["group"] and group["basis"]
    for peer in group["peers"]:
        assert peer["symbol"] and peer["yahoo"] and peer["reason"].strip()
    assert all(x["reason"].strip() for x in group.get("excluded") or [])
    kept = {p["symbol"] for p in group["peers"]}
    assert not kept & {x["symbol"] for x in group.get("excluded") or []}


def test_gmfi_pack_drops_the_airport_operators_table():
    group = peer_groups.load("GMFI")
    excluded = {x["symbol"] for x in group["excluded"]}
    assert {"JSMR", "PORT", "BREN"} <= excluded
    assert {"S59.SI", "AIR"} <= {p["symbol"] for p in group["peers"]}


def _snapshot(symbol, cap, income, equity, reporting="SGD", to_idr=13_900.0):
    return {"symbol": symbol, "yahoo_symbol": symbol, "fiscal_year": 2026,
            "period_end": "2026-06-30", "period": "TTM", "period_label": "12 bulan s.d. 2026-06-30",
            "currency": reporting, "total_debt": 100.0, "cash_and_equivalents": 50.0,
            "ebitda": 200.0, "revenue": 1_000.0, "net_income": income,
            "net_income_period": "12 bulan s.d. 2026-06-30", "equity": equity,
            "total_assets": 3_000.0, "total_liabilities": 1_000.0,
            "market_cap_reporting": cap, "trading_currency": reporting,
            "fx_reporting_to_idr": to_idr, "source": f"Yahoo Finance {symbol} quarterly statements",
            "fetched_at": "2026-09-25"}


def test_foreign_peers_are_valued_in_their_own_currency_and_shown_in_rupiah():
    for symbol, cap, income in (("S59.SI", 3_550.0, 169.0), ("S63.SI", 33_876.0, 463.0),
                                ("AIR", 4_854.0, 188.0), ("VSEC", 5_064.0, 75.0)):
        store.put(peer_fundamentals.COLLECTION, symbol, _snapshot(symbol, cap, income, 1_000.0))
    own, rows, missing, group = peer_groups.companies("GMFI")
    assert own["symbol"].startswith("GMFI") and missing == []
    sia = next(r for r in rows if r["symbol"] == "S59.SI")
    assert sia["pe_ttm"] == pytest.approx(3_550.0 / 169.0)
    assert sia["market_cap"] == pytest.approx(3_550.0 * 13_900.0)
    assert sia["ev"]["ev_ebitda"] == pytest.approx((3_550.0 + 100.0 - 50.0) / 200.0)
    data, _ = intake.load("GMFI", "2026-09-24")
    assert data["peer_basis"].startswith("grup peer kurasi")
    assert {p["symbol"] for p in data["peers"]} == {"S59.SI", "S63.SI", "AIR", "VSEC"}
    found = tools.find_peers("GMFI")
    assert found["group"] == group["group"] and "Yahoo" in found["source"]
    assert sum(r["is_self"] for r in found["rows"]) == 1 and len(found["rows"]) == 5


def test_a_group_without_enough_data_keeps_the_sectors_table_and_says_so():
    data, _ = intake.load("GMFI", "2026-09-24")          # no snapshots in this database
    assert data["peer_basis"].startswith("tabel peer Sectors; grup peer kurasi GMFI")
    assert "--group GMFI" in data["peer_basis"]
    assert any(p["symbol"].startswith("JSMR") for p in data["peers"])


class _Ticker:
    """A half-yearly reporter: EBITDA and net income only in the annual statements."""

    def __init__(self):
        year = pd.to_datetime(["2026-03-31"])
        self.balance_sheet = pd.DataFrame(
            [[100.0], [40.0], [900.0], [2_000.0], [700.0]],
            index=["Total Debt", "Cash And Cash Equivalents", "Stockholders Equity",
                   "Total Assets", "Total Liabilities Net Minority Interest"], columns=year)
        self.income_stmt = pd.DataFrame([[150.0], [1_200.0], [90.0]],
                                        index=["EBITDA", "Total Revenue",
                                               "Net Income Common Stockholders"], columns=year)
        self.quarterly_income_stmt = pd.DataFrame()
        self.quarterly_balance_sheet = pd.DataFrame()
        self.info = {"currency": "SGD", "financialCurrency": "SGD", "marketCap": 1_800.0,
                     "longName": "Half-yearly Engineering"}


class _Fx:
    def __init__(self, rate):
        yesterday = date.today() - timedelta(days=1)
        self._frame = pd.DataFrame({"Close": [rate]}, index=pd.to_datetime([yesterday]))

    def history(self, **_kwargs):
        return self._frame


def test_half_yearly_reporter_uses_its_fiscal_year_net_income():
    factory = lambda s: _Fx(13_900.0) if s.endswith("=X") else _Ticker()
    snap = peer_fundamentals.fetch("S59.SI", factory, yahoo_symbol="S59.SI")
    assert snap["period"] == "FY" and snap["net_income"] == 90.0
    assert snap["net_income_period"] == "FY s.d. 2026-03-31"
    assert snap["equity"] == 900.0 and snap["market_cap_reporting"] == 1_800.0
    assert snap["fx_reporting_to_idr"] == 13_900.0 and snap["symbol"] == "S59.SI"
    json.dumps(snap)                                      # storable as a document
