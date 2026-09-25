"""Explicitly refreshed US Treasury 10-year yield series from Yahoo Finance.

A model built in US dollars (a US$ reporter, spec §2 and §4.2) is discounted
at a US$ rate: risk-free = UST 10Y, plus the Indonesia country risk premium,
plus beta x the mature-market ERP. The rupiah model keeps INDOGB 10Y. The UST
yield is market data, so it is dated: the report reads the last close on or
before its Report Date.

Like the USD/IDR quote and the commodity series, the report build is offline
and reads only the stored series; refreshing is an explicit command that
needs the network:

    python -m app.rates
"""
from __future__ import annotations

import math
import sys
from datetime import date
from typing import Callable

from . import store

COLLECTION = "rates"
UST10Y = "UST10Y"
# name -> (Yahoo symbol, market label). ^TNX is the CBOE 10-year Treasury
# yield index; Yahoo quotes it as the yield in percent (4.15 = 4,15%).
SERIES = {UST10Y: ("^TNX", "imbal hasil US Treasury 10 tahun, indeks CBOE")}
SOURCE = "Yahoo Finance"
# A close older than this before the Report Date is stale (as the FX quote).
MAX_AGE_DAYS = 7


def fetch(name: str = UST10Y, ticker_factory: Callable | None = None) -> dict:
    """Two years of daily closes, yield in percent, completed sessions only."""
    symbol, market = SERIES[name]
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker
    history = ticker_factory(symbol).history(period="2y", auto_adjust=False)
    if history is None or history.empty or "Close" not in history:
        raise ValueError(f"{SOURCE} returned no {symbol} closes")
    today = date.today().isoformat()
    rows = []
    for stamp, close in history["Close"].dropna().items():
        day = stamp.date().isoformat() if hasattr(stamp, "date") else str(stamp)[:10]
        value = float(close)
        # Today's bar is still trading; only completed sessions are stored.
        if day < today and math.isfinite(value) and 0 < value < 20:
            rows.append({"date": day, "yield_pct": round(value, 4)})
    if not rows:
        raise ValueError(f"{SOURCE} returned no completed {symbol} sessions")
    return {"name": name, "symbol": symbol, "unit": "percent", "market": market,
            "source": f"{SOURCE} {symbol} daily close ({market})",
            "fetched_at": today, "rows": rows}


def load(name: str = UST10Y, db=None) -> dict | None:
    """Stored series, or None when missing or malformed."""
    data = store.get(COLLECTION, name, db)
    if not isinstance(data, dict) or not str(data.get("source") or "").startswith(SOURCE):
        return None
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    try:
        for row in rows:
            date.fromisoformat(row["date"])
            value = row["yield_pct"]
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not 0 < value < 20):
                return None
    except (KeyError, TypeError, ValueError):
        return None
    return data


def on_or_before(as_of, name: str = UST10Y, db=None) -> dict | None:
    """The last close on or before ``as_of`` as a decimal rate, dated and sourced.

    None when the series is missing or its last close before ``as_of`` is
    more than MAX_AGE_DAYS old: a stale yield is never used silently.
    """
    data = load(name, db)
    try:
        day = date.fromisoformat(str(as_of)[:10])
    except (TypeError, ValueError):
        return None
    if not data:
        return None
    rows = [r for r in data["rows"] if date.fromisoformat(r["date"]) <= day]
    if not rows:
        return None
    row = max(rows, key=lambda r: r["date"])
    if (day - date.fromisoformat(row["date"])).days > MAX_AGE_DAYS:
        return None
    return {"name": name, "rate": row["yield_pct"] / 100, "date": row["date"],
            "symbol": data.get("symbol"), "source": data["source"]}


def refresh(names=tuple(SERIES), db=None, fetcher: Callable = fetch) -> dict:
    """Fetch and persist each series; a failure leaves the stored one intact."""
    done, failed = {}, {}
    for name in names:
        try:
            data = fetcher(name)
        except Exception as error:  # a Yahoo failure must not wipe the stored series
            failed[name] = f"{type(error).__name__}: {error}"
            continue
        store.put(COLLECTION, name, data, db)
        done[name] = data
    return {"stored": done, "failed": failed}


def main(argv=None) -> int:
    result = refresh()
    for name, data in result["stored"].items():
        last = data["rows"][-1]
        print(f"{name}: {len(data['rows'])} closes to {last['date']}, "
              f"last {last['yield_pct']:.3f}% [{data['source']}]")
    for name, why in result["failed"].items():
        print(f"{name}: FAILED {why}", file=sys.stderr)
    return 1 if result["failed"] and not result["stored"] else 0


if __name__ == "__main__":
    sys.exit(main())
