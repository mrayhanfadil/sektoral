"""Explicitly refreshed copper and gold price series from Yahoo Finance.

The Sectors Snapshot is the primary commodity price source. Its copper series
can stop months before the Report Date (the 22 Sep 2026 snapshot ends on
15 Feb 2026), and a mine valued at a seven-month-old deck is valued at the
wrong price. This dated Yahoo series is the fallback when the Sectors series
is stale; every figure taken from it is labelled Yahoo Finance.

Like the USD/IDR quote, the report build is offline and reads only the stored
series; refreshing is an explicit command that needs the network:

    python -m app.commodity
"""
from __future__ import annotations

import math
import sys
from datetime import date
from typing import Callable

from . import store

COLLECTION = "commodity_prices"
LB_PER_T = 2204.62262
# name -> (Yahoo symbol, factor to the Sectors unit, unit, market label)
SERIES = {
    "Copper": ("HG=F", LB_PER_T, "USD/t", "COMEX copper futures, proksi LME"),
    "Gold": ("GC=F", 1.0, "USD/oz", "COMEX gold futures"),
}
SOURCE = "Yahoo Finance"


def fetch(name: str, ticker_factory: Callable | None = None) -> dict:
    """Two years of daily closes for one commodity, in the Sectors unit."""
    symbol, factor, unit, market = SERIES[name]
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
        price = float(close) * factor
        # Today's bar is still trading; only completed sessions are stored.
        if day < today and math.isfinite(price) and price > 0:
            rows.append({"date": day, "price": round(price, 2)})
    if not rows:
        raise ValueError(f"{SOURCE} returned no completed {symbol} sessions")
    return {"name": name, "symbol": symbol, "unit": unit, "market": market,
            "source": f"{SOURCE} {symbol} daily close ({market})",
            "fetched_at": today, "rows": rows}


def load(name: str, db=None) -> dict | None:
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
            if not isinstance(row["price"], (int, float)) or row["price"] <= 0:
                return None
    except (KeyError, TypeError, ValueError):
        return None
    return data


def refresh(names=tuple(SERIES), db=None, fetcher: Callable = fetch) -> dict:
    """Fetch and persist each series; a failure leaves the stored one intact."""
    done, failed = {}, {}
    for name in names:
        try:
            data = fetcher(name)
        except Exception as error:  # one bad symbol must not stop the other
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
              f"last {last['price']:,.0f} {data['unit']} [{data['source']}]")
    for name, why in result["failed"].items():
        print(f"{name}: FAILED {why}", file=sys.stderr)
    return 1 if result["failed"] and not result["stored"] else 0


if __name__ == "__main__":
    sys.exit(main())
