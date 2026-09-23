"""Small, source-linked issuer facts used when the cache omits official releases.

The report may quote these actuals. A source pack does not by itself approve a
forecast, valuation, target price, or rating.
"""
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / "data" / "issuer_evidence"


def load(ticker, as_of):
    path = ROOT / f"{ticker.upper()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    actual = data.get("latest_actual") or {}
    if data.get("ticker") != ticker.upper() or data.get("schema_version") != 1:
        raise ValueError(f"invalid issuer evidence identity: {path}")
    if not all(actual.get(key) for key in
               ("period", "period_end", "published_at", "source_title", "source_url", "page")):
        raise ValueError(f"incomplete official actual provenance: {path}")
    if date.fromisoformat(actual["published_at"]) > date.fromisoformat(str(as_of)[:10]):
        return None
    if date.fromisoformat(actual["period_end"]) > date.fromisoformat(actual["published_at"]):
        raise ValueError(f"official actual period after publication: {path}")
    if not isinstance(actual.get("metrics"), dict) or not actual["metrics"]:
        raise ValueError(f"official actual metrics missing: {path}")
    for key, value in actual["metrics"].items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"official actual {key} is not numeric: {path}")
    return data
