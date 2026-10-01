"""Explicitly refreshed USD/IDR cache sourced from Yahoo Finance.

The normal report build is offline and deterministic: it reads the stored quote
(``fx`` collection of the app database) and it changes only when the caller
explicitly refreshes it. A missing/stale cache is never silently
replaced with a fixed or network-derived rate.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Callable

from . import store

COLLECTION, KEY = "fx", "USD/IDR"
YAHOO_SYMBOL = "IDR=X"  # Yahoo quote convention: IDR per USD


def fetch_usd_idr(ticker_factory: Callable | None = None) -> dict:
    """Fetch the latest available daily close (IDR per USD) from Yahoo Finance."""
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker

    history = ticker_factory(YAHOO_SYMBOL).history(period="5d", auto_adjust=False)
    if history is None or history.empty or "Close" not in history:
        raise ValueError("Yahoo Finance returned no USD/IDR close")
    close = history["Close"].dropna()
    # FX trades around the clock: today's bar is a live quote, not a close
    # (the 23 Sep 2026 bar fetched intraday read 17.878; its close was 17.805).
    today = date.today().isoformat()
    close = close[[(s.date().isoformat() if hasattr(s, "date") else str(s)[:10]) < today
                   for s in close.index]]
    if close.empty:
        raise ValueError("Yahoo Finance returned no valid USD/IDR close")
    rate = float(close.iloc[-1])
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("Yahoo Finance returned an invalid USD/IDR rate")
    observed = close.index[-1]
    observed_date = observed.date().isoformat() if hasattr(observed, "date") else str(observed)[:10]
    return {
        "pair": "USD/IDR",
        "rate": rate,
        "date": observed_date,
        "source": "Yahoo Finance IDR=X daily close",
    }


def load_cached_rate(db=None) -> dict | None:
    """Read a valid cached quote; return None on missing, malformed, or invalid data."""
    try:
        data = store.get(COLLECTION, KEY, db)
        rate = data.get("rate")
        if (data.get("pair") != "USD/IDR" or not isinstance(rate, (int, float))
                or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0):
            return None
        date.fromisoformat(data["date"])
        if not isinstance(data.get("source"), str) or not data["source"]:
            return None
        return data
    except (AttributeError, ValueError, TypeError, KeyError):
        return None


def refresh_usd_idr(db=None, fetcher: Callable[[], dict] = fetch_usd_idr) -> dict:
    """Fetch and atomically persist a valid quote; leave old cache intact on errors."""
    data = fetcher()
    if not isinstance(data, dict):
        raise ValueError("fetcher must return a valid USD/IDR quote")
    rate = data.get("rate")
    if (data.get("pair") != "USD/IDR" or not isinstance(rate, (int, float))
            or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0):
        raise ValueError("fetcher did not return a valid USD/IDR rate")
    try:
        date.fromisoformat(data["date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("fetcher did not return a valid USD/IDR date") from exc
    if not isinstance(data.get("source"), str) or not data["source"]:
        raise ValueError("fetcher did not return USD/IDR source provenance")
    store.put(COLLECTION, KEY, data, db)
    return data


# A rebuild whose source report converted at a rate no stored quote matches
# recovers that rate from the source report (app.rebuild). It is not a Yahoo
# Finance close, so it carries its own source and every label says so.
IMPLIED_SOURCE = "tersirat dari report sumber (app.rebuild)"


def implied_quote(rate: float, day: str) -> dict:
    """A USD/IDR rate recovered from a source report, dated with its price date."""
    return {"pair": "USD/IDR", "rate": float(rate), "date": str(day)[:10],
            "source": IMPLIED_SOURCE}


def is_implied(quote) -> bool:
    return isinstance(quote, dict) and quote.get("source") == IMPLIED_SOURCE


def basis(quote, english: bool = False) -> str:
    """Where the quote comes from, as the report names it."""
    if is_implied(quote):
        return ("rate implied from the source report" if english
                else "kurs tersirat dari report sumber")
    return "Yahoo Finance IDR=X"


def dated(quote, english: bool = False) -> str | None:
    """The quote's date as the report prints it beside the rate; an implied
    rate says so instead of passing for that day's close."""
    if not isinstance(quote, dict) or not quote.get("date"):
        return None
    if is_implied(quote):
        return (f"implied from the source report, price {quote['date']}" if english
                else f"tersirat dari report sumber, harga {quote['date']}")
    return str(quote["date"])
