"""
Sectors backfill - scripts/sectors_backfill.py (replaces yfinance_fallback.py, Lane E).

Sectors v2 is the single gateway: daily bars + quarterly fundamentals.
Keyless -> honest empty rows + error 'sectors_missing_key' (never a silent
third-party fallback). Cache 4h, disclose source per exhibit.

Env:
  SECTORS_CACHE_DIR  default .cache/sectors
  SECTORS_TTL_SECONDS default 14400 (4h)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CACHE_DIR = Path(os.getenv("SECTORS_CACHE_DIR", ".cache/sectors"))
TTL_SECONDS = int(os.getenv("SECTORS_TTL_SECONDS", "14400"))
JKT = timezone(timedelta(hours=7))


def _cache_path(ticker: str, kind: str) -> Path:
    safe = ticker.strip().upper().replace("/", "_")
    h = hashlib.sha256(f"{safe}:{kind}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"{safe}__{kind}__{h}.json"


def _read_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > TTL_SECONDS:
            return None
        return json.loads(path.read_text())
    except Exception:
        return None


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["_cached_at"] = datetime.now(JKT).isoformat()
    payload["_ttl_seconds"] = TTL_SECONDS
    path.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2))


def _honest_empty(base: str, extra: dict | None = None) -> dict:
    payload = {
        "ticker": base,
        "source": "sectors_missing_key",
        "rows": [],
        "row_count": 0,
        "fetched_at": datetime.now(JKT).isoformat(),
        "cache_hit": False,
        "error": "SECTORS_API_KEY missing - onboard at sectors.app/api, save key to .env. No fallback wired on purpose.",
    }
    if extra:
        payload.update(extra)
    return payload


def get_sectors_prices(ticker: str, days: int = 90, force_refresh: bool = False) -> dict:
    """
    Daily bars via Sectors daily (range max 90 days per call).

    Returns dict:
      { ticker, source: 'sectors'|'sectors_missing_key', rows: [...], fetched_at, cache_hit, error? }
    rows: [{time, open, high, low, close, volume}] ASC.
    Keyless returns cached rows if present, else honest empty + error.
    Disclosure: caller must label exhibit source as 'sectors'.
    """
    base = ticker.strip().upper().removesuffix(".JK")
    cache_path = _cache_path(base, f"prices_{days}d")
    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

    try:
        from server.sectors import daily as _daily
    except Exception as e:
        return _honest_empty(base, {"error": f"sectors client unavailable: {e}"})

    try:
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=min(max(1, days), 90))).isoformat()
        raw = _daily(base, start, end) or {}
        items = raw.get("data") or raw.get("results") or []
        rows = []
        for b in items:
            if not isinstance(b, dict):
                continue
            ts = str(b.get("date") or b.get("time") or "")[:10]
            close = b.get("close") if b.get("close") is not None else b.get("closing_price")
            rows.append({
                "time": ts,
                "open": b.get("open"),
                "high": b.get("high"),
                "low": b.get("low"),
                "close": close,
                "volume": b.get("volume"),
            })
        payload = {
            "ticker": base,
            "source": "sectors",
            "rows": rows,
            "row_count": len(rows),
            "fetched_at": datetime.now(JKT).isoformat(),
            "cache_hit": False,
        }
        if rows:
            _write_cache(cache_path, payload)
        return payload
    except Exception as e:
        # SectorsNotConfigured or transport error - try stale cache, else honest empty
        if "SectorsNotConfigured" in type(e).__name__:
            if cache_path.exists():
                try:
                    stale = json.loads(cache_path.read_text())
                    stale["cache_hit"] = True
                    stale["stale"] = True
                    stale["error"] = str(e)
                    return stale
                except Exception:
                    pass
            return _honest_empty(base)
        if cache_path.exists():
            try:
                stale = json.loads(cache_path.read_text())
                stale["cache_hit"] = True
                stale["stale"] = True
                stale["error"] = str(e)
                return stale
            except Exception:
                pass
        return _honest_empty(base, {"error": str(e)})


def get_sectors_fundamentals(ticker: str, force_refresh: bool = False) -> dict:
    """
    Fundamentals via Sectors company report + quarterly financials.

    Returns {ticker, source:'sectors'|'sectors_missing_key', overview, quarterly,
    dividends, fetched_at, warnings}. Keyless -> honest empty + warnings.
    """
    base = ticker.strip().upper().removesuffix(".JK")
    cache_path = _cache_path(base, "fundamentals")
    if not force_refresh:
        cached = _read_cache(cache_path)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

    warnings: list[str] = []
    try:
        from server.sectors import (
            company_report as _rep,
            corporate_actions as _acts,
            quarterly as _quart,
        )
    except Exception as e:
        return {
            "ticker": base,
            "source": "sectors_missing_key",
            "overview": {},
            "quarterly": [],
            "dividends": [],
            "fetched_at": datetime.now(JKT).isoformat(),
            "cache_hit": False,
            "error": str(e),
            "warnings": ["sectors client unavailable"],
        }

    try:
        rep = _rep(base, "overview,financials,dividend") or {}
        fin = _quart(base, 8) or {}
        acts = _acts(base) or {}
        quarterly = (fin or {}).get("data") or (fin or {}).get("results") or []
        if not quarterly:
            warnings.append("sectors quarterly empty for ticker")
        payload = {
            "ticker": base,
            "source": "sectors",
            "overview": rep.get("overview") if isinstance(rep.get("overview"), dict) else rep,
            "quarterly": quarterly,
            "dividends": (acts or {}).get("dividend") or (acts or {}).get("dividends") or [],
            "fetched_at": datetime.now(JKT).isoformat(),
            "cache_hit": False,
            "warnings": warnings,
        }
        _write_cache(cache_path, payload)
        return payload
    except Exception as e:
        if "SectorsNotConfigured" in type(e).__name__:
            return {
                "ticker": base,
                "source": "sectors_missing_key",
                "overview": {},
                "quarterly": [],
                "dividends": [],
                "fetched_at": datetime.now(JKT).isoformat(),
                "cache_hit": False,
                "error": str(e),
                "warnings": warnings + ["SECTORS_API_KEY missing - no fallback wired"],
            }
        return {
            "ticker": base,
            "source": "sectors",
            "overview": {},
            "quarterly": [],
            "dividends": [],
            "fetched_at": datetime.now(JKT).isoformat(),
            "cache_hit": False,
            "error": str(e),
            "warnings": warnings + [str(e)],
        }


# ---- coverage note helper ----
SECTORS_COVERAGE = {
    "note": "Sectors v2 is the single gateway (IDX full coverage: daily, quarterly, news, filings, corporate actions, foreign flow). Keyless runs return honest empty with source=sectors_missing_key.",
    "keyed": {
        "RATU": "full - IPO 2025 covered via quarterly + daily",
        "CDIA": "full - 2025 listing covered via quarterly + daily",
        "MTEL": "full - infra KPIs via company report sections",
        "BBCA": "full - bank extras (net interest income, CASA) free in quarterly",
        "ADRO": "full - cross-check vs foreign-flow endpoint",
    },
}


def gap_summary() -> dict:
    return SECTORS_COVERAGE


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    print(json.dumps(get_sectors_prices(ticker, days=5), indent=2, ensure_ascii=False))
    print("--- fundamentals --")
    print(json.dumps(get_sectors_fundamentals(ticker), indent=2, ensure_ascii=False))
