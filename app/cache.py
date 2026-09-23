"""Read-only access to data/sectors_cache.db. No network, no key, no credits."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sectors_cache.db"


def connect():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"cache DB missing: {DB_PATH}")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def payloads(endpoint):
    """All (cache_key, payload) rows for one endpoint, oldest fetch first."""
    con = connect()
    try:
        rows = con.execute(
            "SELECT cache_key, payload_json FROM sectors_cache"
            " WHERE endpoint = ? ORDER BY fetched_at",
            (endpoint,),
        ).fetchall()
        return [(r["cache_key"], json.loads(r["payload_json"])) for r in rows]
    finally:
        con.close()


def first(endpoint):
    """Return the most recently fetched snapshot for an endpoint."""
    rows = payloads(endpoint)
    return rows[-1][1] if rows else None


def company_report(ticker):
    """Return the newest report snapshot with the inputs needed by the model.

    Sectors may cache partial responses for the same endpoint/parameters. Do
    not let a newer overview-only response hide an older full company report.
    """
    rows = payloads(f"/company/report/{str(ticker).strip().upper()}/")
    if not rows:
        return None
    for _, payload in reversed(rows):
        if not isinstance(payload, dict):
            continue
        overview = payload.get("overview") or {}
        valuation = payload.get("valuation") or {}
        try:
            price = float(overview.get("last_close_price") or
                          valuation.get("last_close_price"))
        except (TypeError, ValueError):
            continue
        history = ((payload.get("financials") or {}).get("historical_financials") or [])
        usable = [row for row in history if isinstance(row, dict) and
                  isinstance(row.get("year"), (int, float)) and
                  _positive_number(row.get("revenue"))]
        if price > 0 and len(usable) >= 3:
            return payload
    return rows[-1][1]


def _positive_number(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def endpoints():
    con = connect()
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT endpoint FROM sectors_cache ORDER BY 1")]
    finally:
        con.close()
