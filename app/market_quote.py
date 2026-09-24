"""Dated market-close overrides for report runs with stale cache snapshots.

A pack is a reviewed JSON file in ``data/market_quotes``. Writing one from
Yahoo Finance is an explicit command that needs the network; the report build
only reads the files:

    python -m app.market_quote --as-of 2026-09-24 AMMN BBRI
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent / "data" / "market_quotes"


def load(ticker, as_of, cache_date, max_age_days=5):
    path = ROOT / f"{ticker.upper()}.json"
    if not path.is_file():
        return None
    row = json.loads(path.read_text(encoding="utf-8"))
    # A pack may carry recent closes; the Report Date picks the latest one on
    # or before it, so an earlier Report Date is not left on a stale price.
    closes = [c for c in row.get("closes") or []
              if isinstance(c, dict) and str(c.get("date")) <= str(as_of)[:10]]
    if closes:
        latest = max(closes, key=lambda c: c["date"])
        row = {**row, "price": latest.get("price"), "date": latest["date"]}
    if row.get("ticker") != ticker.upper() or row.get("currency") != "IDR":
        raise ValueError(f"invalid market quote identity: {path}")
    quote_date = date.fromisoformat(row["date"])
    report_date = date.fromisoformat(str(as_of)[:10])
    cached_date = date.fromisoformat(str(cache_date)[:10])
    source = urlsplit(str(row.get("source_url") or ""))
    price = row.get("price")
    if (not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0
            or source.scheme != "https" or not source.hostname
            or not isinstance(row.get("source_title"), str)
            or not row["source_title"].strip()):
        raise ValueError(f"incomplete dated market quote: {path}")
    if quote_date <= cached_date or quote_date > report_date:
        return None
    if (report_date - quote_date).days > max_age_days:
        return None
    return row


def fetch_close(ticker, as_of, ticker_factory=None):
    """Latest completed Yahoo daily close on or before the Report Date."""
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker
    symbol = f"{ticker.upper()}.JK"
    history = ticker_factory(symbol).history(period="1mo", auto_adjust=False)
    if history is None or history.empty or "Close" not in history:
        raise ValueError(f"Yahoo Finance returned no closes for {symbol}")
    report_day, today = str(as_of)[:10], date.today().isoformat()
    closes = [(stamp.date().isoformat() if hasattr(stamp, "date") else str(stamp)[:10], float(v))
              for stamp, v in history["Close"].dropna().items()]
    # A bar dated today is still trading unless the Report Date is in the past.
    closes = [(d, v) for d, v in closes if d <= report_day and (d < today or report_day < today)]
    if not closes:
        raise ValueError(f"Yahoo Finance has no {symbol} close on or before {report_day}")
    day, price = closes[-1]
    return {"ticker": ticker.upper(), "currency": "IDR", "price": round(price),
            "date": day, "source_title": f"Yahoo Finance {symbol} daily close",
            "source_url": f"https://finance.yahoo.com/quote/{symbol}/history/",
            "closes": [{"date": d, "price": round(v)} for d, v in closes[-10:]]}


def write(row, root=None):
    path = (root or ROOT) / f"{row['ticker']}.json"
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write dated Yahoo closing-price packs.")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--as-of", required=True, help="Report Date (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    failed = 0
    for ticker in args.tickers:
        try:
            row = fetch_close(ticker, args.as_of)
        except Exception as error:  # one ticker must not stop the batch
            print(f"{ticker}: FAILED {type(error).__name__}: {error}", file=sys.stderr)
            failed += 1
            continue
        print(f"{row['ticker']}: Rp{row['price']:,} ({row['date']}) -> {write(row)}")
    return 1 if failed == len(args.tickers) else 0


if __name__ == "__main__":
    sys.exit(main())
