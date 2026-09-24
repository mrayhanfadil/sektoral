"""Explicitly refreshed peer fundamentals from Yahoo Finance.

Peer EV/EBITDA needs each peer's debt, cash and EBITDA. Those come from the
peer's own Sectors company report when it is cached; when it is not, this
snapshot fills the gap. Every value keeps its Yahoo provenance: it is never
written into the Sectors cache and never labelled as Sectors data.

Like the USD/IDR quote, the report build is offline and reads only stored
snapshots; refreshing is an explicit command that needs the network:

    python -m app.peer_fundamentals MORA LINK          # symbols
    python -m app.peer_fundamentals --peers-of INET    # every peer in a table
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import date
from typing import Callable

from . import store

# Snapshots live in the app database, keyed by IDX symbol.
COLLECTION = "yahoo_fundamentals"
SOURCE = "Yahoo Finance"
# Yahoo statement rows -> snapshot fields (annual statements, reporting currency).
ROWS = {"total_debt": "Total Debt", "cash_and_equivalents": "Cash And Cash Equivalents",
        "ebitda": "EBITDA", "revenue": "Total Revenue"}


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def fetch(symbol: str, ticker_factory: Callable | None = None) -> dict:
    """Latest fiscal-year debt, cash, EBITDA and revenue for one Yahoo symbol.

    The year is the latest statement column that carries all of debt, cash
    and EBITDA; a later year missing one of them is not used, and no value
    is taken from a different year than the others.
    """
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker
    yahoo = str(symbol).strip().upper()
    if not yahoo.endswith(".JK"):
        yahoo += ".JK"
    ticker = ticker_factory(yahoo)
    balance, income = ticker.balance_sheet, ticker.income_stmt
    if balance is None or income is None or balance.empty or income.empty:
        raise ValueError(f"{SOURCE} returned no annual statements for {yahoo}")
    years = sorted({c for c in balance.columns} & {c for c in income.columns}, reverse=True)
    for column in years:
        values = {}
        for field, row in ROWS.items():
            frame = income if field in ("ebitda", "revenue") else balance
            values[field] = _num(frame.loc[row, column]) if row in frame.index else None
        if None in (values["total_debt"], values["cash_and_equivalents"], values["ebitda"]):
            continue
        info = {}
        try:
            info = ticker.info or {}
        except Exception:  # info is optional context; statements are the data
            info = {}
        year = column.year if hasattr(column, "year") else int(str(column)[:4])
        return {
            "symbol": yahoo.replace(".JK", ""), "yahoo_symbol": yahoo,
            "fiscal_year": year, "period_end": str(column)[:10],
            "currency": info.get("financialCurrency") or info.get("currency"),
            "market_cap": _num(info.get("marketCap")),
            **values,
            "source": f"{SOURCE} {yahoo} annual statements FY{year}",
            "fetched_at": date.today().isoformat(),
        }
    raise ValueError(f"{SOURCE} has no fiscal year with debt, cash and EBITDA for {yahoo}")


def load(symbol: str, db=None) -> dict | None:
    """Stored snapshot for a symbol, or None when missing or malformed."""
    data = store.get(COLLECTION, str(symbol).replace(".JK", "").strip().upper(), db)
    if not isinstance(data, dict) or not str(data.get("source") or "").startswith(SOURCE):
        return None
    if any(_num(data.get(k)) is None for k in ("total_debt", "cash_and_equivalents", "ebitda")):
        return None
    if not isinstance(data.get("fiscal_year"), int):
        return None
    return data


def refresh(symbols, db=None, fetcher: Callable = fetch, pause: float = 1.0) -> dict:
    """Fetch and persist one snapshot per symbol; failures are reported, not stored."""
    done, failed = {}, {}
    for i, symbol in enumerate(symbols):
        if i and pause:
            time.sleep(pause)
        try:
            data = fetcher(symbol)
        except Exception as error:  # one bad symbol must not stop the batch
            failed[symbol] = f"{type(error).__name__}: {error}"
            continue
        store.put(COLLECTION, data["symbol"], data, db)
        done[data["symbol"]] = data
    return {"stored": done, "failed": failed}


def peers_of(ticker: str) -> list[str]:
    """Peer symbols in the issuer's cached Sectors peer table."""
    from . import cache
    report = cache.company_report(ticker) or {}
    return [str(c.get("symbol") or "").replace(".JK", "")
            for g in report.get("peers") or []
            for c in (g.get("peers_data") or {}).get("companies") or []
            if isinstance(c, dict) and c.get("symbol") and (c.get("group") or []) != ["self"]]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("symbols", nargs="*", help="IDX symbols (with or without .JK)")
    parser.add_argument("--peers-of", action="append", default=[],
                        help="fetch every peer in this issuer's cached Sectors peer table")
    args = parser.parse_args(argv)
    symbols = list(args.symbols)
    for ticker in args.peers_of:
        symbols.extend(p for p in peers_of(ticker) if p not in symbols)
    if not symbols:
        parser.error("no symbols given")
    result = refresh(symbols)
    for symbol, data in result["stored"].items():
        print(f"{symbol}: FY{data['fiscal_year']} EBITDA {data['ebitda']:.3e} "
              f"debt {data['total_debt']:.3e} cash {data['cash_and_equivalents']:.3e} "
              f"[{data['source']}]")
    for symbol, why in result["failed"].items():
        print(f"{symbol}: FAILED {why}", file=sys.stderr)
    return 1 if result["failed"] and not result["stored"] else 0


if __name__ == "__main__":
    sys.exit(main())
