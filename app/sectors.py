"""Live Sectors API client + SQLite cache writer. Satu-satunya modul yang boleh network.

Disiplin:
- Kunci HANYA dari env SECTORS_API_KEY (tidak pernah dari file repo, tidak pernah di-commit).
- Cache-first: upstream hanya dipanggil saat MISS atau refresh=True eksplisit.
- Cache TIDAK PERNAH expired: baris lama tetap dilayani apa adanya.
  Kolom expires_at hanya info umur, tidak pernah memicu fetch otomatis.
- Error upstream selalu keras (exception), tidak pernah fallback diam-diam.
- Setiap panggilan upstream dicatat di credit_log.jsonl (bukti kredit).

Skema kunci: sc:{endpoint}:{md5(params-kanonis)} — bentuk sama seperti baris
lama di sectors_cache.db. Lookup pipeline tetap by endpoint (app/cache.py).
"""
import hashlib
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.sectors.app/v2"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "sectors_cache.db"
CREDIT_LOG = ROOT / "data" / "credit_log.jsonl"

# TTL per prefix, diadopsi dari sectors-hackathon server/sectors.py
TTL_BY_PREFIX = [
    ("/daily/", 6 * 3600),
    ("/index-daily/", 6 * 3600),
    ("/financials/", 6 * 3600),
    ("/company/report/", 12 * 3600),
    ("/news/", 12 * 3600),
    ("/filings/", 12 * 3600),
    ("/suspensions/", 12 * 3600),
    ("/foreign-flow/", 12 * 3600),
    ("/broker-summary/", 12 * 3600),
    ("/broker-activity/", 12 * 3600),
    ("/brokers/", 12 * 3600),
    ("/subsector/report/", 24 * 3600),
    ("/subsectors/", 24 * 3600),
    ("/companies/", 24 * 3600),
    ("/company/corporate-actions/", 24 * 3600),
    ("/company/shareholders-composition/", 24 * 3600),
    ("/company/get-segments/", 24 * 3600),
    ("/listing-performance/", 24 * 3600),
    ("/free-float/", 24 * 3600),
    ("/mining/", 24 * 3600),
    ("/close/", 4 * 3600),
]
DEFAULT_TTL = 6 * 3600


class SectorsError(RuntimeError):
    pass


def ttl_for(endpoint: str) -> int:
    for prefix, ttl in TTL_BY_PREFIX:
        if endpoint.startswith(prefix):
            return ttl
    return DEFAULT_TTL


def cache_key(endpoint: str, params: dict | None = None) -> str:
    canon = json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
    return f"sc:{endpoint}:{hashlib.md5(canon.encode()).hexdigest()[:32]}"


def _con(db: Path, readonly: bool):
    mode = "mode=ro" if readonly else "mode=rw"
    con = sqlite3.connect(f"file:{db}?{mode}", uri=True)
    con.row_factory = sqlite3.Row
    return con


def read_row(db: Path, key: str) -> dict | None:
    con = _con(db, True)
    try:
        r = con.execute(
            "SELECT endpoint, fetched_at, expires_at, payload_json"
            " FROM sectors_cache WHERE cache_key = ?", (key,)).fetchone()
        if not r:
            return None
        return {"endpoint": r["endpoint"], "fetched_at": r["fetched_at"],
                "expires_at": r["expires_at"],
                "expired": r["expires_at"] < time.time(),
                "payload": json.loads(r["payload_json"])}
    finally:
        con.close()


def write_row(db: Path, key: str, endpoint: str, payload: object, ttl: int) -> None:
    now = time.time()
    con = _con(db, False)
    try:
        con.execute(
            "INSERT OR REPLACE INTO sectors_cache"
            " (cache_key, endpoint, fetched_at, expires_at, payload_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (key, endpoint, now, now + ttl, json.dumps(payload)))
        con.commit()
    finally:
        con.close()


def _log(endpoint: str, status: str, nbytes: int = 0) -> None:
    with open(CREDIT_LOG, "a") as f:
        f.write(json.dumps({"ts": time.time(), "endpoint": endpoint,
                            "status": status, "bytes": nbytes}) + "\n")


class Client:
    """Cache-first Sectors client. Tanpa key = hanya baca cache (mode snapshot)."""

    def __init__(self, key: str | None = None, db: Path = DEFAULT_DB,
                 timeout: int = 30):
        self.key = key
        self.db = db
        self.timeout = timeout
        self.billed = 0
        self.hits = 0

    def _fetch_live(self, endpoint: str, params: dict) -> object:
        if not self.key:
            raise SectorsError("tanpa SECTORS_API_KEY: mode snapshot, upstream ditolak")
        url = BASE + endpoint
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": self.key})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            _log(endpoint, f"http_{e.code}")
            raise SectorsError(f"upstream {e.code} untuk {endpoint}: {e.reason}")
        except urllib.error.URLError as e:
            _log(endpoint, "unreachable")
            raise SectorsError(f"upstream tak terjangkau ({endpoint}): {e.reason}")
        _log(endpoint, "billed", len(body))
        self.billed += 1
        try:
            return json.loads(body)
        except ValueError:
            raise SectorsError(f"upstream {endpoint} bukan JSON ({len(body)} bytes)")

    def get(self, endpoint: str, params: dict | None = None,
            ttl: int | None = None, refresh: bool = False) -> dict:
        """Return {payload, source: live|cache, cache_key}. Error selalu keras.

        Kebijakan never-expired: baris cache selalu menang kecuali
        refresh=True eksplisit. Upstream tidak pernah dipanggil diam-diam.
        """
        params = params or {}
        key = cache_key(endpoint, params)
        if not refresh:
            row = read_row(self.db, key)
            if row:
                self.hits += 1
                return {"payload": row["payload"], "source": "cache",
                        "cache_key": key, "expired": False}
        payload = self._fetch_live(endpoint, params)
        write_row(self.db, key, endpoint, payload, ttl or ttl_for(endpoint))
        return {"payload": payload, "source": "live", "cache_key": key,
                "expired": False}
