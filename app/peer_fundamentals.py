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


def _ttm(ticker, yahoo, info_of):
    """Trailing four quarters of EBITDA and revenue with the latest quarter's
    debt and cash, or None when any of the four quarters is missing."""
    try:
        balance, income = ticker.quarterly_balance_sheet, ticker.quarterly_income_stmt
    except Exception:  # quarterly statements are optional; annual is the fallback
        return None
    if balance is None or income is None or balance.empty or income.empty:
        return None
    if ROWS["ebitda"] not in income.index:
        return None
    quarters = sorted(income.columns, reverse=True)[:4]
    ebitda = [_num(income.loc[ROWS["ebitda"], q]) for q in quarters]
    if len(quarters) < 4 or None in ebitda:
        return None
    end = quarters[0]
    if end not in balance.columns:
        return None
    debt = _num(balance.loc[ROWS["total_debt"], end]) if ROWS["total_debt"] in balance.index else None
    cash = (_num(balance.loc[ROWS["cash_and_equivalents"], end])
            if ROWS["cash_and_equivalents"] in balance.index else None)
    if debt is None or cash is None:
        return None
    revenue = ([_num(income.loc[ROWS["revenue"], q]) for q in quarters]
               if ROWS["revenue"] in income.index else [None])
    info = info_of()
    period_end = str(end)[:10]
    return {
        "symbol": yahoo.replace(".JK", ""), "yahoo_symbol": yahoo,
        "fiscal_year": int(period_end[:4]), "period_end": period_end,
        "period": "TTM", "period_label": f"12 bulan s.d. {period_end}",
        "currency": info.get("financialCurrency") or info.get("currency"),
        "market_cap": _num(info.get("marketCap")),
        "total_debt": debt, "cash_and_equivalents": cash, "ebitda": sum(ebitda),
        "revenue": sum(revenue) if None not in revenue else None,
        "source": f"{SOURCE} {yahoo} quarterly statements, 12 months to {period_end}",
        "fetched_at": date.today().isoformat(),
    }


def fetch(symbol: str, ticker_factory: Callable | None = None) -> dict:
    """Latest twelve months of EBITDA (four quarters) with the latest quarter's
    debt and cash for one Yahoo symbol; the latest fiscal year when the
    quarters are incomplete.

    The peer multiple is applied to the issuer's forward EBITDA, so the most
    recent twelve months are the closer basis: a fiscal year that ended nine
    months ago can carry one-offs the market has already looked past (LINK
    FY2025 EBITDA Rp795 miliar against Rp2,3 triliun over the last four
    quarters). In the fiscal-year fallback the year is the latest statement
    column that carries all of debt, cash and EBITDA; no value is taken from
    a different year than the others.
    """
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker
    yahoo = str(symbol).strip().upper()
    if not yahoo.endswith(".JK"):
        yahoo += ".JK"
    ticker = ticker_factory(yahoo)

    def info_of():
        try:
            return ticker.info or {}
        except Exception:  # info is optional context; statements are the data
            return {}

    trailing = _ttm(ticker, yahoo, info_of)
    if trailing:
        return trailing
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
        info = info_of()
        year = column.year if hasattr(column, "year") else int(str(column)[:4])
        return {
            "symbol": yahoo.replace(".JK", ""), "yahoo_symbol": yahoo,
            "fiscal_year": year, "period_end": str(column)[:10],
            "period": "FY", "period_label": f"FY{year}",
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
        print(f"{symbol}: {data.get('period_label') or data['fiscal_year']} EBITDA {data['ebitda']:.3e} "
              f"debt {data['total_debt']:.3e} cash {data['cash_and_equivalents']:.3e} "
              f"[{data['source']}]")
    for symbol, why in result["failed"].items():
        print(f"{symbol}: FAILED {why}", file=sys.stderr)
    return 1 if result["failed"] and not result["stored"] else 0


if __name__ == "__main__":
    sys.exit(main())
