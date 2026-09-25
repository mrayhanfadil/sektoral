"""Curated peer groups: comparable IDX businesses, not the Sectors sub-sector.

The Sectors peer table is the issuer's sub-sector, which can put toll roads
and a geothermal developer beside an aircraft maintenance company (GMFI's
"Airport Operators") or contractors beside an industrial-estate owner (SSIA).
A reviewed pack in ``data/peer_groups/<T>.json`` names the peers that share
the issuer's business model, and the ones left out, each with a reason:

    {"ticker": "JPFA", "as_of": "2026-09-25", "group": "...", "basis": "...",
     "peers": [{"symbol": "CPIN", "yahoo": "CPIN.JK", "name": "...",
                "market": "IDX", "reason": "..."}],
     "excluded": [{"symbol": "RLCO", "reason": "..."}]}

Peers are IDX (BEI) listings only: every peer and exclusion is a four-letter
IDX code, a peer's market is "IDX" and its Yahoo symbol is "<CODE>.JK";
``load`` refuses any other entry. Peers are chosen by business model, not by
multiple: a peer whose P/E or P/B is an outlier stays in the group, and the
valuation bands in app.method_chain leave that multiple out of the median.

A peer that sits in the issuer's Sectors peer table keeps that row (same
snapshot, same date). Any other peer is read from its stored Yahoo Finance
snapshot (``python -m app.peer_fundamentals --group <T>``); a peer that
reports in US dollars is valued in dollars and shown in rupiah, so its P/E,
P/B and EV/EBITDA are ratios of like with like. Every row says where it came
from. A group with fewer than three peers that have data (including a group
that finds fewer than three comparable IDX businesses) is not used: the
report keeps the Sectors peer table and says why (``unusable_note``).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import cache, peer_fundamentals

ROOT = Path(__file__).resolve().parent.parent / "data" / "peer_groups"
MARKET = "IDX"
IDX_CODE = re.compile(r"[A-Z]{4}")


def _not_idx(entry, is_peer):
    """Why a pack entry is not a plain IDX listing, or None."""
    symbol = str(entry.get("symbol") or "")
    if not IDX_CODE.fullmatch(symbol):
        return f"symbol {symbol!r} is not a four-letter IDX code"
    market = entry.get("market", None if is_peer else MARKET)
    if market != MARKET:
        return f"market {market!r} is not {MARKET!r}"
    yahoo = entry.get("yahoo")
    if yahoo is not None and yahoo != f"{symbol}.JK":
        return f"yahoo {yahoo!r} is not {symbol + '.JK'!r}"
    return None


def load(ticker) -> dict | None:
    """The reviewed pack for ``ticker``, or None; ValueError on a malformed pack
    or on any peer or exclusion that is not an IDX listing."""
    path = ROOT / f"{str(ticker).strip().upper()}.json"
    if not path.is_file():
        return None
    group = json.loads(path.read_text(encoding="utf-8"))
    if group.get("ticker") != str(ticker).strip().upper():
        raise ValueError(f"peer group ticker mismatch: {path}")
    peers = group.get("peers")
    if not isinstance(peers, list):
        raise ValueError(f"peer group needs a list of peers: {path}")
    for peer in peers + list(group.get("excluded") or []):
        if not peer.get("symbol") or not str(peer.get("reason") or "").strip():
            raise ValueError(f"every peer and exclusion needs a symbol and a reason: {path}")
    for kind, entries in (("peer", peers), ("exclusion", group.get("excluded") or [])):
        for entry in entries:
            why = _not_idx(entry, kind == "peer")
            if why:
                raise ValueError(
                    f"{kind} {entry['symbol']} is not an IDX listing ({why}); peer groups "
                    f"hold only IDX (BEI) companies: {path}")
    return group


def _num(value):
    return peer_fundamentals._num(value)


def _sectors_companies(ticker):
    """Every company row in the issuer's own (or borrowed) Sectors peer table."""
    report = cache.company_report(ticker) or {}
    rows = {}
    for group in report.get("peers") or []:
        for company in (group.get("peers_data") or {}).get("companies") or []:
            if isinstance(company, dict) and company.get("symbol"):
                rows[str(company["symbol"]).replace(".JK", "").upper()] = company
    return rows


def _from_snapshot(peer):
    """A Sectors-shaped company row from a stored Yahoo snapshot, or None."""
    snap = peer_fundamentals.load(peer["symbol"])
    if not snap:
        return None
    to_idr = _num(snap.get("fx_reporting_to_idr"))
    cap = _num(snap.get("market_cap_reporting"))
    income, equity = _num(snap.get("net_income")), _num(snap.get("equity"))
    idr = (lambda v: v * to_idr if v is not None and to_idr else None)
    return {
        "symbol": peer["symbol"], "company_name": peer.get("name") or snap.get("company_name"),
        "market_cap": idr(cap),
        "pe_ttm": cap / income if cap and income and income > 0 else None,
        "pb_mrq": cap / equity if cap and equity and equity > 0 else None,
        "net_income": idr(income), "total_revenue": idr(_num(snap.get("revenue"))),
        "total_equity": idr(equity), "total_assets": idr(_num(snap.get("total_assets"))),
        "total_liabilities": idr(_num(snap.get("total_liabilities"))),
        "year": snap.get("net_income_period") or snap.get("period_label"),
        "group": ["peer"],
        "source_kind": "yahoo",
        "source": (f"{snap.get('source')}; kapitalisasi {snap.get('trading_currency')} "
                   f"dikonversi ke {snap.get('currency')} dan Rp, diambil "
                   f"{snap.get('fetched_at')}"),
        "ev": _snapshot_ev(snap, cap),
    }


def _snapshot_ev(snap, cap):
    """EV/EBITDA in the peer's reporting currency, with the snapshot's period."""
    debt, cash, ebitda = (_num(snap.get(k)) for k in ("total_debt", "cash_and_equivalents",
                                                      "ebitda"))
    if cap is None or None in (debt, cash, ebitda):
        return {"ev_status": "balance_incomplete"}
    ev = cap + debt - cash
    ok = ev > 0 and ebitda > 0
    return {"ev": ev, "ev_year": snap.get("fiscal_year"), "ev_period": snap.get("period_label"),
            "ev_status": "ok" if ok else "not_meaningful",
            "ev_ebitda": ev / ebitda if ok else None, "ev_source_kind": "yahoo",
            "ev_source": f"{snap.get('source')} (diambil {snap.get('fetched_at')})"}


MIN_PEERS = 3


def unusable_note(ticker):
    """Why a curated group exists but cannot be used, or None."""
    group = load(ticker)
    if not group:
        return None
    named = [p["symbol"] for p in group["peers"]]
    if len(named) < MIN_PEERS:
        found = (f"hanya menemukan {len(named)} emiten BEI yang sebanding ({', '.join(named)}; "
                 f"minimal {MIN_PEERS})" if named else "tidak menemukan emiten BEI yang sebanding")
        return f"grup peer kurasi {ticker} {found}, sehingga tabel peer Sectors dipakai"
    rows, missing = _rows(ticker, group)
    if len(rows) >= MIN_PEERS:
        return None
    return (f"grup peer kurasi {ticker} baru punya data untuk {len(rows)} dari "
            f"{len(group['peers'])} peer (tanpa snapshot: {', '.join(missing)}; jalankan "
            f"python -m app.peer_fundamentals --group {ticker}), sehingga tabel peer Sectors "
            "dipakai")


def companies(ticker):
    """(self row, peer rows, missing symbols, group) for a curated group, or None.

    Rows use the Sectors peer-table shape so the valuation and the peer
    exhibits read one set; ``source_kind`` is "sectors" or "yahoo". A group
    with fewer than three peers that have data is not used (see
    ``unusable_note``): the report then says so and keeps the Sectors table.
    """
    group = load(ticker)
    if not group:
        return None
    t = str(ticker).strip().upper()
    table = _sectors_companies(t)
    own = table.get(t)
    if own is None:
        # The issuer is not in its own table: build its row from its report.
        report = cache.company_report(t) or {}
        ov = report.get("overview") or {}
        fin = max(((report.get("financials") or {}).get("historical_financials") or []),
                  key=lambda r: r.get("year") or 0, default={})
        val = max(((report.get("valuation") or {}).get("historical_valuation") or []),
                  key=lambda r: r.get("year") or 0, default={})
        own = {"symbol": t, "company_name": report.get("company_name"),
               "market_cap": ov.get("market_cap"), "pe_ttm": val.get("pe"),
               "pb_mrq": val.get("pb"), "net_income": fin.get("earnings"),
               "total_revenue": fin.get("revenue"), "total_equity": fin.get("total_equity"),
               "total_assets": fin.get("total_assets"),
               "total_liabilities": fin.get("total_liabilities"), "year": fin.get("year")}
    own = {**own, "group": ["self"], "source_kind": "sectors"}
    rows, missing = _rows(t, group, table)
    if len(rows) < MIN_PEERS:
        return None
    return own, rows, missing, group


def _rows(ticker, group, table=None):
    """(peer rows with data, symbols without data) for a curated group."""
    table = _sectors_companies(ticker) if table is None else table
    rows, missing = [], []
    for peer in group["peers"]:
        symbol = str(peer["symbol"]).replace(".JK", "").upper()
        if symbol in table:
            rows.append({**table[symbol], "group": ["peer"], "source_kind": "sectors",
                         "source": f"tabel peer Sectors {ticker}"})
            continue
        row = _from_snapshot({**peer, "symbol": symbol})
        if row is None:
            missing.append(symbol)
        else:
            rows.append(row)
    return rows, missing
