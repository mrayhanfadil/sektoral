"""Tools estimator agent. Sumber bukti dibatasi ke sectors_cache.

Cache SQLite selalu read-only dan tidak pernah hit upstream. Output estimasi
hanya disimpan setelah lolos gate; report builder tidak membaca file tersebut.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from app import cache as report_cache
from app import store

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DB = ROOT / "data" / "sectors_cache.db"
# Gated estimator output and its news narrative, in the app database.
DRIVERS_COLLECTION = "drivers"
NEWS_ANALYSIS_COLLECTION = "news_analysis"

def _like(ticker):
    return f"%/{ticker.upper()}/%"


def cache_endpoints(ticker):
    """Daftar endpoint unik yang ada di cache untuk ticker ini."""
    con = sqlite3.connect(f"file:{CACHE_DB}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT endpoint FROM sectors_cache"
            " WHERE endpoint LIKE ? OR endpoint = '/news/'",
            (_like(ticker),)).fetchall()
    finally:
        con.close()
    return sorted(r[0] for r in rows)


def cache_get(ticker, endpoint):
    """Ambil payload cache (dict) atau None bila miss. Tidak pernah upstream.

    Global cached news is narrowed to rows that explicitly name the requested
    ticker in their symbols list; the agent never receives unrelated headlines.
    """
    if endpoint == f"/company/report/{ticker.upper()}/":
        return report_cache.company_report(ticker)
    con = sqlite3.connect(f"file:{CACHE_DB}?mode=ro", uri=True)
    try:
        as_of = None
        if endpoint == "/news/":
            row = con.execute(
                "SELECT payload_json FROM sectors_cache WHERE endpoint=? "
                "ORDER BY fetched_at DESC LIMIT 1", (endpoint,)).fetchone()
            report_row = con.execute(
                "SELECT payload_json FROM sectors_cache WHERE endpoint=? "
                "ORDER BY fetched_at DESC LIMIT 1",
                (f"/company/report/{ticker.upper()}/",)).fetchone()
            if report_row:
                try:
                    report = json.loads(report_row[0])
                    as_of = ((report.get("overview") or {}).get("latest_close_date")
                             or (report.get("valuation") or {}).get("latest_close_date"))
                except (ValueError, TypeError):
                    as_of = None
        else:
            row = con.execute(
                "SELECT payload_json FROM sectors_cache WHERE endpoint=? "
                "AND endpoint LIKE ? ORDER BY fetched_at DESC LIMIT 1",
                (endpoint, _like(ticker))).fetchone()
    finally:
        con.close()
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except (ValueError, TypeError):
        return None
    if endpoint == "/news/" and isinstance(payload, dict):
        symbol = ticker.upper()
        wanted = {symbol, f"{symbol}.JK"}
        results = payload.get("results") or []
        payload = {
            **payload,
            "results": [item for item in results
                        if isinstance(item, dict) and
                        (not as_of or str(item.get("timestamp") or "")[:10] <= as_of) and
                        wanted.intersection(str(x).upper()
                                            for x in item.get("symbols", []))][:10],
        }
    return payload


def write_drivers(ticker, doc):
    """Tulis drivers JSON setelah lolos gate. Kembalikan path."""
    from .validate import gate
    problems = gate(doc)
    if problems:
        raise ValueError("gate menolak drivers: " + "; ".join(problems))
    store.put(DRIVERS_COLLECTION, ticker.upper(), doc)
    return f"{DRIVERS_COLLECTION}/{ticker.upper()}"


def write_news_analysis(ticker, doc):
    """Persist only the validated news narrative block, separate from drivers."""
    payload = {"ticker": ticker.upper(),
               "news_analysis": doc.get("news_analysis") or []}
    store.put(NEWS_ANALYSIS_COLLECTION, ticker.upper(), payload)
    return f"{NEWS_ANALYSIS_COLLECTION}/{ticker.upper()}"


TOOLS = {
    "cache_endpoints": "daftar endpoint cache per ticker (gratis)",
    "cache_get": "baca payload satu endpoint (gratis, miss -> None)",
    "write_drivers": "tulis drivers JSON (hanya lolos gate)",
    "write_news_analysis": "simpan narasi berita tervalidasi dari cache",
}
