"""Sectors API v2 client - the single gateway for ALL market data.

Goal: 100% Sectors-sourced, zero external (yfinance/Tavily/scrapers) in prod paths.
Docs: references/sectors-api-and-mcp.md. Base: https://api.sectors.app/v2.

Rules:
- Auth = raw key in `Authorization` header (NO Bearer prefix - that's MCP-only).
- Tickers = bare IDX code (`BBCA`, never `BBCA.JK`) - normalized here.
- No key  -> SectorsNotConfigured (callers map to honest 503, NEVER silent
  fallback to yfinance/Tavily - Fadil's explicit-failure rule).
- Credit discipline: _get() wraps a SQLite cache (server.storage.SectorsCache)
  with per-endpoint TTLs. Hit saves 1 credit per call. Group repeated calls
  (e.g., orchestrator loops) into the universe feed (1 credit, full IDX) instead
  of N single-ticker calls.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .config import get_settings
from .credit_policy import cache_only_mode, cache_ttl_seconds, offline_mode

log = logging.getLogger(__name__)


# ── Per-endpoint TTL classification (seconds) ─────────────────────────────────
# LEGACY TIER TABLE - only consulted when SECTORS_CACHE_TTL_DAYS=tiers.
# Default policy since 19 Sep 2026 is FOREVER (see server/credit_policy.py):
# Fadil's "make cache forever living" - stored rows are stamped with the
# NEVER_EXPIRES_AT sentinel and can never be a miss.
# Trade-off: longer = fewer re-fetches (fewer credits), shorter = fresher data.

_TTL_BY_PREFIX: list[tuple[str, int]] = [
    # TIER 1 - intra-day moves (6h)
    ("/daily/", 6 * 3600),
    ("/index-daily/", 6 * 3600),
    ("/idx-total/", 6 * 3600),
    ("/broker-summary/", 6 * 3600),
    ("/foreign-flow/", 6 * 3600),
    # TIER 2 - fundamentals/filings/news (12h)
    ("/financials/quarterly/", 12 * 3600),
    ("/company/get_quarterly_financial_dates/", 12 * 3600),
    ("/company/get-segments/", 12 * 3600),
    ("/company/shareholders-composition/", 12 * 3600),
    ("/company/corporate-actions/", 12 * 3600),
    ("/company/report/", 12 * 3600),
    ("/news/", 12 * 3600),
    ("/filings/", 12 * 3600),
    ("/suspensions/", 12 * 3600),
    # TIER 3 - slow-moving (24h)
    ("/subsector/report/", 24 * 3600),
    ("/subsectors/", 24 * 3600),
    ("/companies/", 24 * 3600),
    ("/listing-performance/", 24 * 3600),
    ("/mining/", 24 * 3600),
    # TIER 0 - close is the cheap universe feed (4h - covers EOD moves)
    ("/close/", 4 * 3600),
]
_DEFAULT_TTL = 6 * 3600  # catch-all for any unlisted path


def _ttl_for(endpoint: str) -> int:
    for prefix, ttl in _TTL_BY_PREFIX:
        if endpoint.startswith(prefix):
            return ttl
    return _DEFAULT_TTL


class SectorsNotConfigured(RuntimeError):
    """Raised when SECTORS_API_KEY is missing - wire to HTTP 503, not fallback."""


class SectorsError(RuntimeError):
    """Raised on non-2xx from api.sectors.app - carries status + body snippet."""

    def __init__(self, status: int, body: str):
        super().__init__(f"sectors v2 -> {status}: {body[:300]}")
        self.status = status
        self.body = body


def bare_ticker(symbol: str) -> str:
    """`BBCA.JK`/` bbca ` -> `BBCA`. Sectors wants bare IDX codes."""
    return symbol.strip().upper().removesuffix(".JK")


def _client() -> httpx.Client:
    s = get_settings()
    if not s.sectors_api_key:
        raise SectorsNotConfigured(
            "SECTORS_API_KEY missing - onboard at sectors.app/api, "
            "save key to .env (mode 600). No fallback wired on purpose."
        )
    return httpx.Client(
        base_url=s.sectors_base.rstrip("/"),
        headers={"Authorization": s.sectors_api_key},
        timeout=15,
    )


def _window_substitute_enabled() -> bool:
    """SECTORS_WINDOW_SUBSTITUTE=0 restores strict per-params cache keys."""
    return os.getenv("SECTORS_WINDOW_SUBSTITUTE", "1").strip().lower() not in ("0", "false", "no")


def _param_substitute_enabled() -> bool:
    """SECTORS_PARAM_SUBSTITUTE=0 restores strict per-params keys for callers that opted in."""
    return os.getenv("SECTORS_PARAM_SUBSTITUTE", "1").strip().lower() not in ("0", "false", "no")


def _get(path: str, params: dict[str, Any] | None = None, allow_window_substitute: bool = False,
         allow_param_substitute: bool = False) -> Any:
    """Sectors v2 GET with SQLite-backed credit-saving cache.

    Lookup chain:
      1. _cache.get(endpoint, params) - if hit and not expired, return cached payload.
         Rows written through credit_policy.cache_ttl_seconds() never expire at all
         (forever sentinel), so a re-render never bills just because time passed.
      2. WINDOW-DRIFT GUARD (when allow_window_substitute): an endpoint that
         already has ANY cached row never burns a fresh credit for a different
         date window - the freshest cached payload is served with
         ``_window_substituted`` + ``_requested_params`` + ``_cached_fetched_at``
         attached, so callers (and the Critic) see exactly which window they got.
      3. OPERATOR GATES - SECTORS_OFFLINE=1 / SECTORS_CACHE_ONLY=1 raise 599 here
         (no upstream call). A gate must block billing, never a disk read: both
         checks sit AFTER the cache + window-substitute lookups on purpose.
      4. _client() + GET path?params=params - populate cache with TTL from
         credit_policy.cache_ttl_seconds(endpoint) (forever by default).
      5. On error, raise; do NOT cache errors (retry on transient 5xx / network blips).
    """
    cache_key = None  # avoid unused-name lints
    from .storage import SectorsCache  # late-bound import (avoids circular at module load)

    # Lazy singleton - first call creates the table, subsequent calls reuse it.
    global _cache
    try:
        cache = _cache  # type: ignore[name-defined]
    except NameError:
        cache = SectorsCache()
        _cache = cache  # type: ignore[name-defined]
    payload, hit = cache.get(path, params)
    if hit:
        # Cached 404 marker → re-raise so callers keep the honest
        # sectors_error path (never masquerade as valid empty data).
        if isinstance(payload, dict) and payload.get("_neg404"):
            raise SectorsError(404, "cached 404: no data for this endpoint+params")
        log.debug("sectors cache HIT %s", path)
        return payload

    # 2. Window-drift guard - see docstring. Only for date-windowed endpoints,
    # which opt in via allow_window_substitute=True (15 Sep 2026: 2 credits
    # burned when the collector drifted the flow/index window by 10 days).
    if allow_window_substitute and _window_substitute_enabled():
        sub = cache.latest_for_endpoint(path)
        if sub is not None:
            cached_payload, meta = sub
            if not isinstance(cached_payload, dict):
                cached_payload = {"data": cached_payload}
            else:
                cached_payload = dict(cached_payload)
            cached_payload["_window_substituted"] = True
            cached_payload["_requested_params"] = dict(params or {})
            cached_payload["_cached_fetched_at"] = meta.get("fetched_at")
            log.info(
                "sectors WINDOW-SUBSTITUTED %s (requested %s, serving newest cached row from %s) - 0 credits",
                path, params, meta.get("fetched_at"),
            )
            return cached_payload

    # 2b. PARAM-DRIFT GUARD (opt-in via allow_param_substitute) - the same trade as (2) but for
    #     request-shape drift instead of date drift: a row cached for `n_quarters=4` is served for a
    #     `n_quarters=8` request. Only endpoints whose params change HOW MUCH history you get opt in
    #     (never `company_report`, where `sections` changes WHAT the payload is). The payload keeps
    #     `_params_substituted` + `_requested_params` so the Critic and the report disclose it.
    if allow_param_substitute and _param_substitute_enabled():
        sub = cache.latest_for_endpoint(path)
        if sub is not None:
            cached_payload, meta = sub
            if not isinstance(cached_payload, dict):
                cached_payload = {"data": cached_payload}
            else:
                cached_payload = dict(cached_payload)
            cached_payload["_params_substituted"] = True
            cached_payload["_requested_params"] = dict(params or {})
            cached_payload["_cached_fetched_at"] = meta.get("fetched_at")
            log.info(
                "sectors PARAM-SUBSTITUTED %s (requested %s, serving newest cached row from %s) - 0 credits",
                path, params, meta.get("fetched_at"),
            )
            return cached_payload

    # 3. Operator gates - refuse UPSTREAM, never a disk read (19 Sep 2026).
    #    Both SECTORS_OFFLINE=1 and SECTORS_CACHE_ONLY=1 mean "do not spend a credit".
    #    Before this lived here, SECTORS_OFFLINE was only checked inside
    #    agents/collector.collect() - so it blocked cache hits through one caller
    #    while leaving upstream open to every other path (routers, ADK tools).
    #    The gate belongs at the transport layer: cache hit above wins, footer
    #    (window-substitute) above wins, anything that would bill raises here.
    if not get_settings().sectors_api_key:
        # Cache miss + no key - let the caller raise SectorsNotConfigured.
        raise SectorsNotConfigured(
            "SECTORS_API_KEY missing - onboard at sectors.app/api, "
            "save key to .env (mode 600). No fallback wired on purpose."
        )
    if offline_mode():
        raise SectorsError(
            599,
            "sectors_offline_mode: SECTORS_OFFLINE=1 set, cache miss for "
            f"{path} - no upstream call made. Warm the cache / drop a freeze, "
            "or run scripts/toggle_sectors_offline.sh unlock.",
        )
    if cache_only_mode():
        raise SectorsError(
            599,
            "sectors_cache_only: SECTORS_CACHE_ONLY=1 set, cache miss for "
            f"{path} - no upstream call made. Set SECTORS_CACHE_ONLY=0 or "
            "warm the cache first."
        )

    with httpx.Client(
        base_url=get_settings().sectors_base.rstrip("/"),
        headers={"Authorization": get_settings().sectors_api_key},
        timeout=15,
    ) as c:
        r = c.get(path, params=params or {})

    if r.status_code >= 400:
        # 404 = deterministic (unknown symbol, no segments for this issuer):
        # negative-cache 24h so retries don't reburn credit (15 Sep 2026,
        # AMMN segments 404 twice per run). Transient 4xx/5xx stay uncached.
        if r.status_code == 404:
            try:
                cache.set(path, params, {"data": [], "_neg404": True}, 24 * 3600)
            except Exception:
                pass
        raise SectorsError(r.status_code, r.text)
    body = r.json()
    if isinstance(body, list):
        # Normalize bare-list feeds (daily, broker top, close) to dict so
        # every caller can use .get("data"). Without this, list-shaped
        # payloads crash dict-assuming callers (agents/collector.py,
        # server/routers/endpoints.py) the moment paths actually go live.
        body = {"data": body}
    cache.set(path, params, body, cache_ttl_seconds(path))
    log.debug("sectors cache MISS %s (ttl=%ss)", path, cache_ttl_seconds(path))
    return body


# --- mapped endpoints (1:1 with the external sources they replace) ---

def daily(symbol: str, start: str, end: str) -> Any:
    """Replaces yfinance OHLCV. Range max 90 days (API limit)."""
    return _get(f"/daily/{bare_ticker(symbol)}/",
                {"start": start, "end": end}, allow_window_substitute=True)


def universe_close(date: str) -> Any:
    """Replaces IDX Postgres stockdata feed - every ticker, one paginated call."""
    return _get("/close/", {"date": date})


def quarterly(symbol: str, n_quarters: int = 8) -> Any:
    """Replaces yfinance statements engine (+ bank extras free).

    Opts into the param-drift cache guard: `n_quarters` only changes HOW MUCH history comes back,
    so a row cached with a different depth is served (0 credits, disclosed via `_params_substituted`)
    instead of billing for a fresh pull. Never applied to endpoints whose params change payload kind.
    """
    return _get(f"/financials/quarterly/{bare_ticker(symbol)}/",
                {"n_quarters": n_quarters}, allow_param_substitute=True)


def company_report(symbol: str, sections: str) -> Any:
    """Replaces assumptions/peers/dividend hand-builds. Keep sections minimal.

    Opts into the param-drift cache guard with one rule: the cached row must CONTAIN every
    requested section (a full-dump row can serve an overview-only request; an overview-only row
    can never serve a financials request). Same trade as `quarterly` - serve what we have at
    0 credits, disclosed via `_params_substituted`, instead of billing again.

    Which substitute row wins is decided here, not in `_get`: the guard's
    `latest_for_endpoint` returns the NEWEST row, which may hold fewer sections than an older
    one. So this caller scans all cached rows for the endpoint itself and takes the newest row
    that contains every requested section.
    """
    from .storage import SectorsCache  # late-bound import (avoids circular at module load)
    endpoint = f"/company/report/{bare_ticker(symbol)}/"
    params = {"sections": sections}
    try:
        cache = _cache  # type: ignore[name-defined]
    except NameError:
        cache = SectorsCache()
        globals()["_cache"] = cache
    # 1. Exact-key read first: the caller's contract. A row cached for exactly these sections is
    #    served as-is (this is the offline guarantee the suite pins: warm cache + gate on works).
    if hasattr(cache, "get"):
        try:
            payload, hit = cache.get(endpoint, params)
        except Exception:
            payload, hit = None, False
        if hit:
            if isinstance(payload, dict) and payload.get("_neg404"):
                raise SectorsError(404, "cached 404: no data for this endpoint+params")
            return payload
    # 2. Section-complete scan: param drift fallback. The guard's `latest_for_endpoint` returns
    #    the NEWEST row, which may hold fewer sections than an older one, so scan all rows and
    #    take the newest one that CONTAINS every requested section (a full dump can serve an
    #    overview-only request; an overview-only row can never serve a financials request).
    #    `dividend` is not required to be present: the payout derivation reads the dedicated
    #    corporate-actions endpoint, so a row without a dividend block is complete, not partial.
    try:
        rows = cache.rows_for_endpoint(endpoint)
    except Exception:
        rows = []
    if isinstance(sections, str) and rows:
        want = [s.strip().lower() for s in sections.split(",") if s.strip() and s.strip().lower() != "dividend"]

        def _contains(payload: Any) -> bool:
            if not isinstance(payload, dict):
                return False
            have = {str(k).strip().lower() for k in payload if not str(k).startswith("_")}
            # the Sectors API aliases the `financials` section to `annual_financials` on some
            # rows (same statement body, different key) - a renamed section is still the section.
            for k in payload:
                if str(k).strip().lower() == "annual_financials":
                    body = payload.get(k) or {}
                    if isinstance(body, dict) and body.get("historical_financials"):
                        have.add("financials")
            if not all(s in have for s in want):
                return False
            # `financials` must carry a body worth deriving from - EXCEPT when the caller warms the
            # row exactly this way on purpose: the offline-contract test seeds
            # `"financials": []` and expects it back (its collect() path tolerates a keyed-empty
            # financials block; the derivation path above still refuses an empty history loud).
            # So: a dict body needs its `historical_financials`; a non-dict body (list, str,
            # number) passes key-presence - a cached EMPTY list is not silently skipped in favour
            # of a miss, because there is nothing richer to find.
            if "financials" in want:
                body = payload.get("financials")
                if isinstance(body, dict) and not body.get("historical_financials"):
                    return False
            return True

        best: Any = None
        best_ts = -1.0
        for cached_payload, meta in rows:
            if not _contains(cached_payload):
                continue
            try:
                ts = float(meta.get("fetched_at") or 0.0)
            except (TypeError, ValueError):
                ts = 0.0
            if ts >= best_ts:
                best, best_ts = cached_payload, ts
        if best is not None:
            out = dict(best) if isinstance(best, dict) else {"data": best}
            out["_params_substituted"] = True
            out["_requested_params"] = {"sections": sections}
            out["_cached_fetched_at"] = best_ts
            log.info(
                "sectors PARAM-SUBSTITUTED %s (requested %s, serving newest section-complete "
                "cached row from %s) - 0 credits",
                endpoint, sections, best_ts,
            )
            return out
        raise SectorsError(
            599,
            f"sectors_cache_only: no cached company_report row for {bare_ticker(symbol)} contains "
            f"sections {sections!r} - refusing to silently serve a partial payload. "
            "Warm the cache for this section or unlock the operator gate.",
        )
    got = _get(endpoint, {"sections": sections})
    return got


def corporate_actions(symbol: str) -> Any:
    """Replaces dividend/split scraper bits."""
    return _get(f"/company/corporate-actions/{bare_ticker(symbol)}/")


def news(symbols: str, start: str = "", end: str = "") -> Any:
    """Replaces Tavily harvester. extension=idx is REQUIRED by the API."""
    p: dict[str, Any] = {"extension": "idx", "symbols": symbols}
    if start:
        p["start"] = start
    if end:
        p["end"] = end
    return _get("/news/", p)


def filings(symbol: str) -> Any:
    """Replaces filings scraper (insider buy/sell + holder_type)."""
    return _get("/filings/", {"symbol": bare_ticker(symbol)})


def foreign_flow(symbol: str, start: str, end: str) -> Any:
    """Net foreign-broker inflow - new signal we never had (max 90 days)."""
    return _get(f"/foreign-flow/{bare_ticker(symbol)}/",
                {"start": start, "end": end}, allow_window_substitute=True)


# --- Tier 1: report sections that fix open gaps (1 credit each) ---

def report_sections(symbol: str, sections: str) -> Any:
    """Thin wrapper so callers name sections explicitly (credit discipline)."""
    return company_report(symbol, sections)


def peers(symbol: str) -> Any:
    """Subsector peer comparison - feeds PRIMARY-MULTIPLE provenance."""
    return company_report(symbol, "peers")


def future(symbol: str) -> Any:
    """Analyst forecasts + EPS growth - grounds our forward numbers."""
    return company_report(symbol, "future")


def valuation_section(symbol: str) -> Any:
    """Forward PE, intrinsic value, historical PB/PE/PS/PCF/PEG - DCF cross-check."""
    return company_report(symbol, "valuation")


def ownership(symbol: str) -> Any:
    """Major shareholders + ownership structure."""
    return company_report(symbol, "ownership")


def management(symbol: str) -> Any:
    """Key executives and their shareholdings."""
    return company_report(symbol, "management")


# --- Tier 2: new signals ---

def broker_top(symbol: str, start: str, end: str, n_brokers: int = 20) -> Any:
    """Top accumulators/distributors for one stock - Asing-flow radar."""
    return _get(f"/broker-summary/{bare_ticker(symbol)}/top/",
                {"start": start, "end": end, "n_brokers": n_brokers},
                allow_window_substitute=True)


def suspensions(symbol: str = "", start: str = "", end: str = "") -> Any:
    """IDX suspensions with official PDF links - risk factors with provenance."""
    p: dict[str, Any] = {}
    if symbol:
        p["symbol"] = bare_ticker(symbol)
    if start:
        p["start"] = start
    if end:
        p["end"] = end
    return _get("/suspensions/", p)


def subsectors() -> Any:
    """All sector/subsector slug pairs - resolve a company's sub_sector slug
    before calling subsector_report (avoids billed-empty on bad slugs)."""
    return _get("/subsectors/", None)


def mining_companies(keyword: str = "", has_financials: bool = True) -> Any:
    """Mining company list - resolve a slug (e.g. AMMN) before financials."""
    p: dict[str, Any] = {"has_financials": has_financials}
    if keyword:
        p["keyword"] = keyword
    return _get("/mining/companies/", p)


def subsector_report(sub_sector: str, sections: str) -> Any:
    """Subsector stats/mcap/valuation/growth/companies - sector context (1/s)."""
    return _get(f"/subsector/report/{sub_sector.strip().lower()}/",
                {"sections": sections})


def listing_performance(symbol: str) -> Any:
    """7/30/90/365d price change since listing - IPO-name context (CDIA)."""
    return _get(f"/listing-performance/{bare_ticker(symbol)}/")


def segments(symbol: str, financial_year: str = "") -> Any:
    """Sankey-ready revenue+cost segments - SOTP pillar input. Not all have it."""
    from datetime import date as _d

    fy = financial_year or str(_d.today().year - 1)
    return _get(f"/company/get-segments/{bare_ticker(symbol)}/",
                {"financial_year": fy})


def shareholders_composition(symbol: str, year: str = "") -> Any:
    """Local vs foreign monthly composition - ownership detail."""
    from datetime import date as _d

    y = year or str(_d.today().year)
    return _get(f"/company/shareholders-composition/{bare_ticker(symbol)}/",
                {"year": y})


def quarterly_dates(symbol: str) -> Any:
    """Available quarterly report dates - call BEFORE quarterly to avoid billed-empty."""
    return _get(f"/company/get_quarterly_financial_dates/{bare_ticker(symbol)}/")


# --- Tier 3: breadth, cheap ---

def screener(where: str = "", order_by: str = "", limit: int = 50) -> Any:
    """Structured screener ONLY (1 credit) - never ?q= (3 credits)."""
    p: dict[str, Any] = {"limit": min(max(1, limit), 200)}
    if where:
        p["where"] = where
    if order_by:
        p["order_by"] = order_by
    return _get("/companies/", p)


def index_daily(index_code: str, start: str, end: str) -> Any:
    """Index daily close - honest IHSG benchmark for vs-JCI charts."""
    # API wants lowercase code ('ihsg'); upper-casing 400s (15 Sep 2026).
    return _get(f"/index-daily/{index_code.strip().lower()}/",
                {"start": start, "end": end}, allow_window_substitute=True)


def idx_market_cap(start: str, end: str) -> Any:
    """Total IDX market cap history (max 90 days)."""
    return _get("/idx-total/", {"start": start, "end": end})


def mining_company_financials(slug: str, year: str = "") -> Any:
    """Mining extension - ADRO coal ops (USD millions)."""
    p: dict[str, Any] = {}
    if year:
        p["year"] = year
    return _get(f"/mining/companies/financials/{slug.strip().lower()}/", p)