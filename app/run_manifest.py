"""Immutable run manifest: compare a new PDF with an archived one.

One manifest per ticker run records code revision, as_of, latest market
close, cache snapshot IDs, official filings + publication dates, Tavily
query + retrieval status, selected news URLs, assumption-plan hash,
profile, release status, and blockers. Changed data/methods never look
like a gate regression.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git_revision():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT), stderr=subprocess.DEVNULL,
            timeout=5).decode().strip()
    except Exception:
        return "unknown"


def assumption_plan_hash(plan):
    try:
        blob = json.dumps(plan or {}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]
    except Exception:
        return "unhashable"


def cache_snapshot_ids(tickers=()):
    """Lightweight cache identity: endpoint + newest cache_key per feed."""
    try:
        from . import cache as cache_mod
        snapshot = {}
        for endpoint in sorted(set(list(tickers) or cache_mod.endpoints())):
            try:
                rows = cache_mod.payloads(endpoint)
            except Exception:
                continue
            if rows:
                snapshot[endpoint] = rows[-1][0]
        return snapshot
    except Exception:
        return {}


def build_manifest(*, ticker, as_of, intake=None, forecast=None,
                   valuation=None, news_evidence=None, assumption_plan=None,
                   release=None, spec_sha=None):
    intake = intake or {}
    forecast = forecast or {}
    valuation = valuation or {}
    news_evidence = news_evidence or {}
    search = news_evidence.get("search") or {}
    rows = news_evidence.get("rows") or []
    official = (intake.get("official_evidence") or {}).get("latest_actual") or {}
    market_quote = intake.get("market_quote") or {}
    release = release or (valuation.get("release") or {})

    queries = search.get("queries")
    if not queries and search.get("query"):
        queries = [{"query": search.get("query")}]
    return {
        "ticker": str(ticker or "").upper(),
        "code_revision": git_revision(),
        "as_of": str(as_of or intake.get("as_of") or "")[:10],
        "profile": intake.get("model_profile"),
        "market_close": {
            "price": intake.get("price"),
            "price_date": intake.get("price_date"),
            "source_title": market_quote.get("source_title"),
            "source_url": market_quote.get("source_url"),
        },
        "official_filing": {
            "period": official.get("period"),
            "period_end": official.get("period_end"),
            "published_at": official.get("published_at"),
            "source_title": official.get("source_title"),
            "source_url": official.get("source_url"),
        },
        "tavily": {
            "status": search.get("status"),
            "queries": queries or [],
            "window": search.get("window"),
            "fetched_at": search.get("fetched_at"),
            "error": search.get("error"),
        },
        "selected_news_urls": [str(r.get("source") or "") for r in rows
                               if isinstance(r, dict) and r.get("source")],
        "assumption_plan_hash": assumption_plan_hash(assumption_plan),
        "forecast_basis": forecast.get("forecast_basis"),
        "production_ready": forecast.get("production_ready"),
        "target_method": valuation.get("method"),
        "target_price": valuation.get("tp"),
        "release_status": release.get("status"),
        "blockers": list(release.get("blockers") or []),
        "spec_sha256": spec_sha,
        "cache_snapshot": cache_snapshot_ids(),
    }
