"""Explicitly refreshed USD/IDR cache sourced from Yahoo Finance.

The normal report build is offline and deterministic: it reads this artifact only
when the caller explicitly refreshes it. A missing/stale cache is never silently
replaced with a fixed or network-derived rate.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Callable

DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "fx_usdidr.json"
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


def load_cached_rate(cache_path: Path = DEFAULT_CACHE_PATH) -> dict | None:
    """Read a valid cached quote; return None on missing, malformed, or invalid data."""
    try:
        data = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        rate = data.get("rate")
        if (data.get("pair") != "USD/IDR" or not isinstance(rate, (int, float))
                or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0):
            return None
        date.fromisoformat(data["date"])
        if not isinstance(data.get("source"), str) or not data["source"]:
            return None
        return data
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def refresh_usd_idr(
    cache_path: Path = DEFAULT_CACHE_PATH,
    fetcher: Callable[[], dict] = fetch_usd_idr,
) -> dict:
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
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return data
