"""Dated analyst-only inputs kept separate from issuer evidence."""
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / "data" / "analyst_scenarios"


def load(ticker, as_of):
    path = ROOT / f"{str(ticker).strip().upper()}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("ticker") != str(ticker).strip().upper():
        raise ValueError(f"analyst scenario ticker mismatch: {path}")
    scenario_date = date.fromisoformat(doc["as_of"])
    if scenario_date > date.fromisoformat(str(as_of)[:10]):
        return None
    return doc
