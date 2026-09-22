"""Cache-only reader for data/sectors_cache.db. Local SQLite, no network, no credits.

Stale rows are served (expired flag reported) — matches the old
SECTORS_STALE_OK=1 discipline. Never calls upstream.
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "sectors_cache.db"


def conn():
    if not DB.exists():
        sys.exit(f"missing {DB}")
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def list_endpoints():
    c = conn()
    for ep, n in c.execute(
        "SELECT endpoint, COUNT(*) FROM sectors_cache GROUP BY endpoint ORDER BY 2 DESC"
    ):
        print(f"{n:4d}  {ep}")


def list_keys(endpoint, limit):
    c = conn()
    q = "SELECT cache_key, fetched_at, expires_at FROM sectors_cache"
    args: list = []
    if endpoint:
        q += " WHERE endpoint = ?"
        args.append(endpoint)
    q += " LIMIT ?"
    args.append(limit)
    now = time.time()
    for r in c.execute(q, args):
        flag = "EXPIRED" if r["expires_at"] < now else "live"
        print(f"[{flag}] {r['cache_key']} fetched={r['fetched_at']:.0f}")


def get(key):
    c = conn()
    r = c.execute(
        "SELECT endpoint, fetched_at, expires_at, payload_json"
        " FROM sectors_cache WHERE cache_key = ?",
        (key,),
    ).fetchone()
    if not r:
        sys.exit("miss: no such cache_key")
    print(json.dumps(
        {
            "cache_key": key,
            "endpoint": r["endpoint"],
            "fetched_at": r["fetched_at"],
            "expires_at": r["expires_at"],
            "expired": r["expires_at"] < time.time(),
            "payload": json.loads(r["payload_json"]),
        },
        indent=1,
    )[:4000])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list-endpoints", action="store_true")
    p.add_argument("--endpoint", default="")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--get", default="")
    a = p.parse_args()
    if a.list_endpoints:
        return list_endpoints()
    if a.get:
        return get(a.get)
    return list_keys(a.endpoint or None, a.limit)


if __name__ == "__main__":
    main()
