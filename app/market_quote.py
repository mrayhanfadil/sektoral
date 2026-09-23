"""Dated market-close overrides for report runs with stale cache snapshots."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent / "data" / "market_quotes"


def load(ticker, as_of, cache_date, max_age_days=5):
    path = ROOT / f"{ticker.upper()}.json"
    if not path.is_file():
        return None
    row = json.loads(path.read_text(encoding="utf-8"))
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
