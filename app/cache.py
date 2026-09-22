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
    rows = payloads(endpoint)
    return rows[0][1] if rows else None


def endpoints():
    con = connect()
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT endpoint FROM sectors_cache ORDER BY 1")]
    finally:
        con.close()
