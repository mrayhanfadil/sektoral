"""Rating history store data/rating_history/<TICKER>.json for cover status."""
from __future__ import annotations

import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "rating_history"

ORDER = {"Sell": 0, "Hold": 1, "Buy": 2}


def load(ticker: str) -> list[dict]:
    if not ticker:
        return []
    path = DIR / f"{str(ticker).upper()}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    hist = data.get("history") if isinstance(data, dict) else None
    if not isinstance(hist, list):
        return []
    out = []
    for row in hist:
        if isinstance(row, dict) and row.get("rating") in ORDER and row.get("date"):
            out.append({"date": str(row["date"]), "rating": row["rating"],
                        "tp": row.get("tp")})
    return sorted(out, key=lambda r: r["date"])


def cover_status(ticker: str, current_rating: str | None) -> str:
    """Inisiasi / Dipertahankan / Naik dari X / Turun dari X."""
    hist = load(ticker)
    if not hist or not current_rating or current_rating not in ORDER:
        return "Inisiasi" if not hist else "Dipertahankan"
    last = hist[-1]["rating"]
    if last == current_rating:
        return "Dipertahankan"
    if ORDER[current_rating] > ORDER[last]:
        return f"Naik dari {last}"
    return f"Turun dari {last}"
