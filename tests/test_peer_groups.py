"""Curated peer groups (data/peer_groups): comparable IDX businesses, one row set."""
from datetime import date, timedelta
import json

import pandas as pd
import pytest

from app import intake, method_chain, peer_fundamentals, peer_groups, store
from agents.analyst import tools

TICKERS = ("AMMN", "GMFI", "INET", "JPFA", "POWR", "SIDO", "SSIA")


@pytest.mark.parametrize("ticker", TICKERS)
def test_every_pack_names_idx_peers_and_exclusions_with_reasons(ticker):
    group = peer_groups.load(ticker)
    assert group["ticker"] == ticker and group["group"] and group["basis"]
    for peer in group["peers"]:
        assert peer_groups.IDX_CODE.fullmatch(peer["symbol"]) and peer["market"] == "IDX"
        assert peer["yahoo"] == f"{peer['symbol']}.JK" and peer["reason"].strip()
    for gone in group.get("excluded") or []:
        assert peer_groups.IDX_CODE.fullmatch(gone["symbol"]) and gone["reason"].strip()
    kept = {p["symbol"] for p in group["peers"]}
    assert not kept & {x["symbol"] for x in group.get("excluded") or []}
    if len(kept) < peer_groups.MIN_PEERS:          # too few IDX comparables: says so
        assert "tabel peer Sectors" in group["basis"]


def _pack(tmp_path, monkeypatch, peer=None, excluded=None):
    """A JPFA pack in a temporary directory with one extra peer or exclusion."""
    pack = json.loads((peer_groups.ROOT / "JPFA.json").read_text(encoding="utf-8"))
    if peer:
        pack["peers"].append({"name": "x", "reason": "x", **peer})
    if excluded:
        pack["excluded"].append({"reason": "x", **excluded})
    (tmp_path / "JPFA.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(peer_groups, "ROOT", tmp_path)


@pytest.mark.parametrize("peer", [
    {"symbol": "CPF", "market": "SET", "yahoo": "CPF.BK"},       # a Thai listing
    {"symbol": "CPF", "market": "IDX", "yahoo": "CPF.BK"},       # labelled IDX, still foreign
    {"symbol": "S59.SI", "market": "IDX", "yahoo": "S59.SI"},    # not an IDX code
    {"symbol": "CPFX", "market": "SET", "yahoo": "CPFX.JK"},     # market says it is foreign
    {"symbol": "CPFX", "yahoo": "CPFX.JK"},                      # market not stated
])
def test_a_foreign_peer_is_refused(tmp_path, monkeypatch, peer):
    _pack(tmp_path, monkeypatch, peer=peer)
    with pytest.raises(ValueError, match="is not an IDX listing"):
        peer_groups.load("JPFA")


def test_a_foreign_exclusion_is_refused(tmp_path, monkeypatch):
    # The peer page lists exclusions as BEI companies, so they must be IDX codes too.
    _pack(tmp_path, monkeypatch, excluded={"symbol": "FCX"})
    with pytest.raises(ValueError, match="exclusion FCX is not an IDX listing"):
        peer_groups.load("JPFA")


def test_an_idx_peer_passes(tmp_path, monkeypatch):
    _pack(tmp_path, monkeypatch, peer={"symbol": "WMUX", "market": "IDX", "yahoo": "WMUX.JK"})
    assert peer_groups.load("JPFA")["peers"][-1]["symbol"] == "WMUX"


def test_packs_hold_no_foreign_peer():
    foreign = {"S59.SI", "S63.SI", "AIR", "VSEC", "CPF", "BGRIM", "GPSC", "RATCH", "EGCO",
               "GULF", "FCX", "SCCO", "ANTO", "LUN", "HBM", "ZIJIN", "MMG", "CMOC", "SFR"}
    for ticker in TICKERS:
        group = peer_groups.load(ticker)
        named = {p["symbol"] for p in group["peers"] + (group.get("excluded") or [])}
        assert not named & foreign, ticker


def _snapshot(symbol, cap, income, equity, reporting="USD", to_idr=17_800.0):
    return {"symbol": symbol, "yahoo_symbol": f"{symbol}.JK", "fiscal_year": 2026,
            "period_end": "2026-06-30", "period": "TTM", "period_label": "12 bulan s.d. 2026-06-30",
            "currency": reporting, "total_debt": 100.0, "cash_and_equivalents": 50.0,
            "ebitda": 200.0, "revenue": 1_000.0, "net_income": income,
            "net_income_period": "12 bulan s.d. 2026-06-30", "equity": equity,
            "total_assets": 3_000.0, "total_liabilities": 1_000.0,
            "market_cap_reporting": cap, "trading_currency": "IDR",
            "fx_reporting_to_idr": to_idr,
            "source": f"Yahoo Finance {symbol}.JK quarterly statements", "fetched_at": "2026-09-25"}


def test_dollar_reporting_idx_peers_are_valued_in_dollars_and_shown_in_rupiah():
    # AMMN: ARCI and PSAB are IDX gold producers outside AMMN's Sectors table.
    for symbol, cap, income in (("ARCI", 1_860.0, 136.0), ("PSAB", 801.0, 197.0)):
        store.put(peer_fundamentals.COLLECTION, symbol, _snapshot(symbol, cap, income, 400.0))
    own, rows, missing, group = peer_groups.companies("AMMN")
    assert own["symbol"].startswith("AMMN") and missing == []
    arci = next(r for r in rows if r["symbol"] == "ARCI")
    assert arci["source_kind"] == "yahoo"
    assert arci["pe_ttm"] == pytest.approx(1_860.0 / 136.0)
    assert arci["market_cap"] == pytest.approx(1_860.0 * 17_800.0)
    assert arci["ev"]["ev_ebitda"] == pytest.approx((1_860.0 + 100.0 - 50.0) / 200.0)
    data, _ = intake.load("AMMN", "2026-09-24")
    assert data["peer_basis"].startswith("grup peer kurasi")
    assert {p["symbol"].replace(".JK", "") for p in data["peers"]} == {
        "MDKA", "ANTM", "ARCI", "PSAB", "BRMS"}
    found = tools.find_peers("AMMN")
    assert found["group"] == group["group"] and "Yahoo" in found["source"]
    assert sum(r["is_self"] for r in found["rows"]) == 1 and len(found["rows"]) == 6


def test_gmfi_widened_aviation_group_replaces_the_airport_operators_table():
    # No other aircraft MRO is listed on IDX: the pack widens to IDX aviation
    # businesses. Loss-making airlines stay in the group without a P/E or P/B.
    group = peer_groups.load("GMFI")
    assert [p["symbol"] for p in group["peers"]] == ["CASS", "GIAA", "CMPP", "HELI"]
    assert {"JSMR", "PORT", "BREN"} <= {x["symbol"] for x in group["excluded"]}
    for symbol, cap, income, equity in (("GIAA", 1_347.0, -330.0, -40.0),
                                        ("CMPP", 737e9, -1_957e9, -12_189e9),
                                        ("HELI", 211.5e9, 26.1e9, 91.1e9)):
        idr = symbol != "GIAA"
        store.put(peer_fundamentals.COLLECTION, symbol,
                  _snapshot(symbol, cap, income, equity, reporting="IDR" if idr else "USD",
                            to_idr=1.0 if idr else 17_800.0))
    data, _ = intake.load("GMFI", "2026-09-24")
    assert data["peer_basis"].startswith("grup peer kurasi")
    by_symbol = {p["symbol"].replace(".JK", ""): p for p in data["peers"]}
    assert set(by_symbol) == {"CASS", "GIAA", "CMPP", "HELI"}
    for airline in ("GIAA", "CMPP"):
        assert by_symbol[airline]["pe"] is None and by_symbol[airline]["pb"] is None
    # Two valid P/E and P/B: the methods that need three do not run.
    assert len(method_chain.peer_pes(data["peers"])) == 2
    assert len(method_chain.peer_pbvs(data["peers"])) == 2
    found = tools.find_peers("GMFI")
    flagged = [r["symbol"] for r in found["rows"] if r["metrics"]["pe"] is None]
    assert flagged == ["GIAA", "CMPP"]                   # the peer page's outliers


def test_a_group_with_too_few_idx_comparables_keeps_the_sectors_table_and_says_so(
        tmp_path, monkeypatch):
    pack = json.loads((peer_groups.ROOT / "GMFI.json").read_text(encoding="utf-8"))
    pack["peers"] = pack["peers"][:1]                    # CASS alone
    (tmp_path / "GMFI.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(peer_groups, "ROOT", tmp_path)
    assert peer_groups.companies("GMFI") is None
    data, _ = intake.load("GMFI", "2026-09-24")
    assert data["peer_basis"] == (
        "tabel peer Sectors; grup peer kurasi GMFI hanya menemukan 1 emiten BEI yang "
        "sebanding (CASS; minimal 3), sehingga tabel peer Sectors dipakai")
    assert any(p["symbol"].startswith("JSMR") for p in data["peers"])
    found = tools.find_peers("GMFI")
    assert "grup peer kurasi GMFI hanya menemukan 1 emiten BEI" in found["basis"]


def test_a_group_without_snapshots_keeps_the_sectors_table_and_says_so():
    # SSIA: DMAS, BEST and KIJA sit outside SSIA's Sectors table and need snapshots.
    assert peer_groups.companies("SSIA") is None           # no snapshots in this database
    note = peer_groups.unusable_note("SSIA")
    assert note.startswith("grup peer kurasi SSIA baru punya data untuk 2 dari 5 peer")
    assert "--group SSIA" in note


class _Ticker:
    """An IDX peer reporting in dollars whose quarterly statements Yahoo lacks:
    EBITDA and net income only in the annual statements."""

    def __init__(self):
        year = pd.to_datetime(["2025-12-31"])
        self.balance_sheet = pd.DataFrame(
            [[100.0], [40.0], [900.0], [2_000.0], [700.0]],
            index=["Total Debt", "Cash And Cash Equivalents", "Stockholders Equity",
                   "Total Assets", "Total Liabilities Net Minority Interest"], columns=year)
        self.income_stmt = pd.DataFrame([[150.0], [1_200.0], [90.0]],
                                        index=["EBITDA", "Total Revenue",
                                               "Net Income Common Stockholders"], columns=year)
        self.quarterly_income_stmt = pd.DataFrame()
        self.quarterly_balance_sheet = pd.DataFrame()
        self.info = {"currency": "IDR", "financialCurrency": "USD",
                     "marketCap": 1_800.0 * 17_800.0, "longName": "Dollar Geothermal"}


class _Fx:
    def __init__(self, rate):
        yesterday = date.today() - timedelta(days=1)
        self._frame = pd.DataFrame({"Close": [rate]}, index=pd.to_datetime([yesterday]))

    def history(self, **_kwargs):
        return self._frame


def test_annual_reporter_uses_its_fiscal_year_net_income():
    rates = {"IDRUSD=X": 1 / 17_800.0, "USDIDR=X": 17_800.0}
    factory = lambda s: _Fx(rates[s]) if s.endswith("=X") else _Ticker()
    snap = peer_fundamentals.fetch("PGEO", factory, yahoo_symbol="PGEO.JK")
    assert snap["period"] == "FY" and snap["net_income"] == 90.0
    assert snap["net_income_period"] == "FY s.d. 2025-12-31"
    assert snap["equity"] == 900.0 and snap["market_cap_reporting"] == pytest.approx(1_800.0)
    assert snap["fx_reporting_to_idr"] == 17_800.0 and snap["symbol"] == "PGEO"
    json.dumps(snap)                                      # storable as a document


def test_regional_references_stay_out_of_the_valuation_peers(tmp_path, monkeypatch):
    # GMFI keeps foreign MRO listings in a separate context list: they are
    # never peers, never in companies() and must name their non-IDX market.
    group = peer_groups.load("GMFI")
    regional = {e["symbol"] for e in group.get("regional_reference") or []}
    assert regional and not regional & {p["symbol"] for p in group["peers"]}
    for entry in group["regional_reference"]:
        assert entry["market"] != "IDX" and entry["reason"].strip() and entry["yahoo"]
    pack = json.loads((peer_groups.ROOT / "GMFI.json").read_text(encoding="utf-8"))
    pack["regional_reference"][0]["market"] = "IDX"
    (tmp_path / "GMFI.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(peer_groups, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="non-IDX market"):
        peer_groups.regional("GMFI")


def test_regional_rows_come_from_their_snapshots_with_market_and_reason():
    store.put(peer_fundamentals.COLLECTION, "AIR", {
        **_snapshot("AIR", 4_800.0, 190.0, 1_700.0), "yahoo_symbol": "AIR",
        "source": "Yahoo Finance AIR quarterly statements"})
    rows, missing, basis = peer_groups.regional("GMFI")
    air = next(r for r in rows if r["symbol"] == "AIR")
    assert air["market"] == "NYSE" and air["group"] == ["regional_reference"]
    assert air["pe_ttm"] == pytest.approx(4_800.0 / 190.0)
    assert "IDX-only" in basis
