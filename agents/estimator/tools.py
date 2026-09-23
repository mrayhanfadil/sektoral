"""Tools estimator agent. Semua read-only kecuali tulis file drivers.

- Cache SQLite: baca saja, tidak pernah hit upstream (0 kredit).
- Web publik: filings/paparan emiten + berita; UA browser-like eksplisit
  (pelajaran WAF: urllib default diblok).
- Tulis: hanya data/drivers/{T}.json, dan hanya via validate gate.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DB = ROOT / "data" / "sectors_cache.db"
DRIVERS_DIR = ROOT / "data" / "drivers"

UA = {"User-Agent": "sektoral-estimator/1.0 (+cache-first research snapshot)",
      "Accept": "text/html,application/json"}


def _like(ticker):
    return f"%/{ticker.upper()}/%"


def cache_endpoints(ticker):
    """Daftar endpoint unik yang ada di cache untuk ticker ini."""
    con = sqlite3.connect(f"file:{CACHE_DB}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT endpoint FROM sectors_cache WHERE endpoint LIKE ?",
            (_like(ticker),)).fetchall()
    finally:
        con.close()
    return sorted(r[0] for r in rows)


def cache_get(ticker, endpoint):
    """Ambil payload cache (dict) atau None bila miss. Tidak pernah upstream."""
    con = sqlite3.connect(f"file:{CACHE_DB}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT payload_json FROM sectors_cache WHERE endpoint=? "
            "AND endpoint LIKE ? ORDER BY fetched_at DESC LIMIT 1",
            (endpoint, _like(ticker))).fetchone()
    finally:
        con.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return None


def fetch_public(url, timeout=25, char_limit=12000):
    """Ambil halaman publik (filings/paparan/berita). Kembalikan teks."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(char_limit * 4)
    try:
        text = raw.decode("utf-8", "replace")
    except Exception:
        text = ""
    return text[:char_limit]


def write_drivers(ticker, doc):
    """Tulis drivers JSON setelah lolos gate. Kembalikan path."""
    from .validate import gate
    problems = gate(doc)
    if problems:
        raise ValueError("gate menolak drivers: " + "; ".join(problems))
    DRIVERS_DIR.mkdir(parents=True, exist_ok=True)
    p = DRIVERS_DIR / f"{ticker.upper()}.json"
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    return p


TOOLS = {
    "cache_endpoints": "daftar endpoint cache per ticker (gratis)",
    "cache_get": "baca payload satu endpoint (gratis, miss -> None)",
    "fetch_public": "ambil halaman publik: filings/paparan/berita",
    "write_drivers": "tulis drivers JSON (hanya lolos gate)",
}
