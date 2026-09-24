"""Daily closes from IDX (Indonesia Stock Exchange) trading summaries.

data/idx_history/{T}.json holds issuer closes from the IDX company trading
summary and IHSG.json the COMPOSITE index summary, each with its source and
retrieval date. The Sectors cache keeps about three months of daily data; the
IDX series give the 18-24 month price history struktur asks for. Charts that
use them name IDX as the source.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "idx_history"
MAX_GAP_DAYS = 16  # Lebaran closes the market ~11 days; longer gaps break the series


def load(symbol, as_of=None):
    """Source metadata and closes strictly before ``as_of`` (the last close
    before publication), trimmed to the continuous tail of the series."""
    path = ROOT / f"{str(symbol).upper()}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    cutoff = date.fromisoformat(str(as_of)[:10]) if as_of else None
    points = []
    for row in doc.get("observations") or []:
        try:
            day, close = date.fromisoformat(row["date"]), float(row["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if close > 0 and (cutoff is None or day < cutoff):
            points.append((day, close))
    points.sort()
    start = 0
    for i in range(1, len(points)):
        if (points[i][0] - points[i - 1][0]).days > MAX_GAP_DAYS:
            start = i
    points = points[start:]
    if len(points) < 2:
        return None
    return {"symbol": doc.get("ticker"), "source_title": doc.get("source_title"),
            "source_url": doc.get("source_url"), "retrieved_at": doc.get("retrieved_at"),
            "points": points}
