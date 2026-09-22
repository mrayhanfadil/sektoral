# Copyright 2026 Sectors Hackathon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Sectors financial tools - FunctionTool wrappers for read-only Sectors v2 data.

These tools are the ONLY way the Collector agent fetches fundamentals.
LLMs must call them rather than inventing financial figures in-text.

Each function delegates to server/sectors.py (sync httpx, run via
asyncio.to_thread so ADK can await them). Plain callables here -
google.adk.tools.function_tool.FunctionTool wraps them in agents/adk/app.py,
mirroring agents/adk/tools/finance_tools.py conventions.

Tools:
  sectors_quarterly, sectors_company_report, sectors_peers,
  sectors_filings, sectors_foreign_flow, sectors_segments,
  sectors_index_daily

Env:
  SECTORS_API_KEY - required for live data; missing key returns an honest
  empty result ({data: [], source: 'sectors_missing_key'}), never fabricated
  figures, never raised exceptions.

Honest provenance:
  Every result carries (ticker, source, fetched_at). The Critic agent checks
  source == 'sectors' before accepting claims.

Usage:
  from .sectors_financial_tools import SECTORS_FINANCIAL_TOOLS
  tools = [FunctionTool(fn) for fn in SECTORS_FINANCIAL_TOOLS]
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

logger = logging.getLogger(__name__)


def _bare(ticker: str) -> str:
    """`BBCA.JK`/` bbca ` -> `BBCA`. Sectors wants bare IDX codes."""
    return (ticker or "").strip().upper().removesuffix(".JK")


def _missing_key_dict(ticker: str, fetched_at: str) -> dict[str, Any] | None:
    """Return the honest keyless shape, or None when a key is configured.

    Checked FIRST so every tool honors the keyless contract regardless of
    other params: no key -> {data: [], source: 'sectors_missing_key'},
    never fabricated, never raised.

    GATES (revised 19 Sep 2026): this used to also short-circuit on
    SECTORS_CACHE_ONLY=1 / SECTORS_OFFLINE=1 and hand back empty data. That made
    a warm cache indistinguishable from a cold one - an agent got `data: []`
    while `sectors_cache` held the payload, which is exactly the "we don't use
    the cache" failure Fadil caught. Gates now live at the transport layer
    (server/sectors._get): a cache hit serves normally, a cold endpoint raises
    SectorsError(599) which `_error_dict()` labels honestly. So: return None and
    let the call run.
    """
    from server.config import get_settings

    if not get_settings().sectors_api_key.strip():
        return {
            "ticker": ticker,
            "source": "sectors_missing_key",
            "fetched_at": fetched_at,
            "data": [],
        }
    return None


def _error_dict(ticker: str, fetched_at: str, exc: BaseException) -> dict[str, Any]:
    """Honest error shape for a tool call that failed.

    A 599 from the transport gate is NOT a generic error - it means "the operator
    closed upstream and this endpoint was cold", with nothing spent. Label it
    accordingly so the pipeline (and the Critic) can tell the two apart.
    """
    msg = str(exc)[:300]
    if "sectors_offline_mode" in msg:
        return {"ticker": ticker, "source": "sectors_offline", "fetched_at": fetched_at,
                "data": [], "error": msg,
                "note": "SECTORS_OFFLINE=1 - cache miss, no upstream call made (0 credits)."}
    if "sectors_cache_only" in msg:
        return {"ticker": ticker, "source": "sectors_cache_only", "fetched_at": fetched_at,
                "data": [], "error": msg,
                "note": "SECTORS_CACHE_ONLY=1 - cache miss, no upstream call made (0 credits)."}
    return {"ticker": ticker, "source": "sectors_error", "fetched_at": fetched_at,
            "data": [], "error": msg}


def _payload(raw: Any) -> Any:
    """Unwrap the API envelope ({data: [...]} or {results: [...]}) if present."""
    if isinstance(raw, dict):
        return raw.get("data", raw.get("results", raw))
    return raw


async def sectors_quarterly(
    ticker: Annotated[str, "IDX ticker, bare (e.g. 'BBCA', never 'BBCA.JK')."],
    n_quarters: Annotated[int, "Quarters of history (default 8, max ~20)."] = 8,
) -> dict[str, Any]:
    """Quarterly fundamentals via Sectors (replaces yfinance statements).

    Args:
        ticker: Bare IDX code.
        n_quarters: Number of trailing quarters.

    Returns:
        Dict with ticker, source, fetched_at, data (quarterly financial rows).
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, quarterly as _quarterly

    t = _bare(ticker)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(t, fetched_at)) is not None:
        return miss
    try:
        raw = await asyncio.to_thread(_quarterly, t, max(1, min(n_quarters, 20)))
        return {"ticker": t, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
    except SectorsNotConfigured:
        return {"ticker": t, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_quarterly(%s) failed: %s", t, e)
        return _error_dict(t, fetched_at, e)


async def sectors_company_report(
    ticker: Annotated[str, "IDX ticker, bare (e.g. 'BBCA')."],
    sections: Annotated[str, "Report section(s), comma-separated, kept minimal for credit discipline (e.g. 'valuation', 'peers', 'future', 'ownership', 'management')."] = "valuation",
) -> dict[str, Any]:
    """Company report section(s) via Sectors (assumptions/peers/dividend input).

    Args:
        ticker: Bare IDX code.
        sections: Minimal section list - one call per section set (1 credit each).

    Returns:
        Dict with ticker, sections, source, fetched_at, data.
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, company_report as _report

    t = _bare(ticker)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(t, fetched_at)) is not None:
        return miss
    try:
        raw = await asyncio.to_thread(_report, t, sections)
        return {"ticker": t, "sections": sections, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
    except SectorsNotConfigured:
        return {"ticker": t, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_company_report(%s) failed: %s", t, e)
        return _error_dict(t, fetched_at, e)


async def sectors_peers(
    ticker: Annotated[str, "IDX ticker, bare (e.g. 'BBCA')."],
) -> dict[str, Any]:
    """Subsector peer comparison via Sectors (PRIMARY-MULTIPLE provenance).

    Args:
        ticker: Bare IDX code.

    Returns:
        Dict with ticker, source, fetched_at, data (peer rows).
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, peers as _peers

    t = _bare(ticker)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(t, fetched_at)) is not None:
        return miss
    try:
        raw = await asyncio.to_thread(_peers, t)
        return {"ticker": t, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
    except SectorsNotConfigured:
        return {"ticker": t, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_peers(%s) failed: %s", t, e)
        return _error_dict(t, fetched_at, e)


async def sectors_filings(
    ticker: Annotated[str, "IDX ticker, bare (e.g. 'BBCA')."],
) -> dict[str, Any]:
    """Filings via Sectors (insider buy/sell + holder_type).

    Args:
        ticker: Bare IDX code.

    Returns:
        Dict with ticker, source, fetched_at, data (filing rows).
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, filings as _filings

    t = _bare(ticker)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(t, fetched_at)) is not None:
        return miss
    try:
        raw = await asyncio.to_thread(_filings, t)
        return {"ticker": t, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
    except SectorsNotConfigured:
        return {"ticker": t, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_filings(%s) failed: %s", t, e)
        return _error_dict(t, fetched_at, e)


async def sectors_foreign_flow(
    ticker: Annotated[str, "IDX ticker, bare (e.g. 'BBCA')."],
    start: Annotated[str, "Window start YYYY-MM-DD (max 90d window)."] = "",
    end: Annotated[str, "Window end YYYY-MM-DD."] = "",
    top_n: Annotated[int, "Also fetch top-N accumulators/distributors (0 = skip, saves a credit)."] = 0,
) -> dict[str, Any]:
    """Net foreign-broker flow (+ optional top-broker radar) via Sectors.

    Args:
        ticker: Bare IDX code.
        start: Window start (YYYY-MM-DD). Required - returned as error dict if missing.
        end: Window end (YYYY-MM-DD). Required - returned as error dict if missing.
        top_n: When > 0, also fetch top-N brokers into 'broker_top'.

    Returns:
        Dict with ticker, source, fetched_at, data (foreign-flow rows).
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, broker_top as _broker_top, foreign_flow as _flow

    t = _bare(ticker)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(t, fetched_at)) is not None:
        return miss
    if not start or not end:
        return {"ticker": t, "source": "sectors", "fetched_at": fetched_at, "data": [],
                "error": "start and end required (YYYY-MM-DD, max 90d window)"}
    try:
        raw = await asyncio.to_thread(_flow, t, start, end)
        out: dict[str, Any] = {"ticker": t, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
        if top_n > 0:
            top_raw = await asyncio.to_thread(_broker_top, t, start, end, max(1, min(top_n, 50)))
            out["broker_top"] = _payload(top_raw)
        return out
    except SectorsNotConfigured:
        return {"ticker": t, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_foreign_flow(%s) failed: %s", t, e)
        return _error_dict(t, fetched_at, e)


async def sectors_segments(
    ticker: Annotated[str, "IDX ticker, bare (e.g. 'BBCA')."],
    financial_year: Annotated[str, "Financial year YYYY (default: last year). Not all issuers have segment data."] = "",
) -> dict[str, Any]:
    """Revenue+cost segments via Sectors (Sankey-ready SOTP pillar input).

    Args:
        ticker: Bare IDX code.
        financial_year: YYYY string; empty defaults to last year server-side.

    Returns:
        Dict with ticker, source, fetched_at, data (segment rows).
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, segments as _segments

    t = _bare(ticker)
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(t, fetched_at)) is not None:
        return miss
    try:
        raw = await asyncio.to_thread(_segments, t, financial_year)
        return {"ticker": t, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
    except SectorsNotConfigured:
        return {"ticker": t, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_segments(%s) failed: %s", t, e)
        return _error_dict(t, fetched_at, e)


async def sectors_index_daily(
    index_code: Annotated[str, "Index code lowercase, e.g. 'ihsg' for JCI benchmark (API rejects uppercase)."] = "ihsg",
    start: Annotated[str, "Window start YYYY-MM-DD (max 90d window)."] = "",
    end: Annotated[str, "Window end YYYY-MM-DD."] = "",
) -> dict[str, Any]:
    """Index daily close via Sectors (honest JCI benchmark for vs-index charts).

    Returns:
        Dict with index_code, source, fetched_at, data (index rows).
        Keyless -> {data: [], source: 'sectors_missing_key'}.
    """
    from server.sectors import SectorsNotConfigured, index_daily as _index_daily

    code = (index_code or "ihsg").strip().lower()
    fetched_at = datetime.now(timezone.utc).isoformat()
    if (miss := _missing_key_dict(code, fetched_at)) is not None:
        return miss
    if not start or not end:
        return {"ticker": code, "source": "sectors", "fetched_at": fetched_at, "data": [],
                "error": "start and end required (YYYY-MM-DD, max 90d window)"}
    try:
        raw = await asyncio.to_thread(_index_daily, code, start, end)
        return {"ticker": code, "source": "sectors", "fetched_at": fetched_at, "data": _payload(raw)}
    except SectorsNotConfigured:
        return {"ticker": code, "source": "sectors_missing_key", "fetched_at": fetched_at, "data": []}
    except Exception as e:
        logger.warning("sectors_index_daily(%s) failed: %s", code, e)
        return _error_dict(code, fetched_at, e)


# Export list for ADK registration (collector only - see agents/adk/app.py)
SECTORS_FINANCIAL_TOOLS = [
    sectors_quarterly,
    sectors_company_report,
    sectors_peers,
    sectors_filings,
    sectors_foreign_flow,
    sectors_segments,
    sectors_index_daily,
]
