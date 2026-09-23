"""Credit/lifetime policy knobs for the Sectors data plane - ONE home (19 Sep 2026).

Fadil's rule, verbatim: *"make cache forever living"*. Consequences encoded here:

1. **Cache lifetime is forever by default.** Every row in `sectors_cache` never
   expires, so a re-render can never bill a credit just because a clock moved.
   `SECTORS_CACHE_TTL_DAYS=0` (or unset) = forever; `N` = N days;
   `tiers` = the legacy per-endpoint table in `server/sectors.py`.
2. **File freezes are forever by default too.** `FREEZE_TTL_DAYS=0` (or unset)
   means a pre-populated freeze under `output/cache/ticker_fill/` (legacy alias
   `ammn_fill/`) is always served, no matter its mtime. Set `N` to restore a
   recency gate. Age is ALWAYS surfaced (`freeze_age_s` / the source string) so
   freshness stays visible even when the gate is off.
3. **A gate blocks upstream, never disk.** `SECTORS_OFFLINE=1` and
   `SECTORS_CACHE_ONLY=1` both mean "do not spend a credit"; neither may refuse
   a cache hit or a freeze read. Before this module existed, `SECTORS_OFFLINE`
   was checked inside `collect()` *before* the Sectors path was tried, so a warm
   cache looked empty; and `_get()` did not honour `SECTORS_OFFLINE` at all, so
   the gate blocked disk reads while leaving upstream open to every caller that
   bypassed `collect()` (routers, ADK tools, backfill scripts).

Credit Budget Rules (adapted from credit-calculator.md):
- 1,000 API credits total budget; budget them like cash.
- 1 credit per endpoint / section.
- Never natural language queries (?q= costs 3 credits; structured where= costs 1 credit).
- Validate ticker existence before dispatch (404s still incur API credit penalty).
- Check quarterly-financial-dates before pulling full quarterly statements.
- Prefer minimal sections= parameter over bloated payloads (default max 5 sections).
- Assert total dry-run budget for a quintet harvest remains < 100 credits.

Both gates are read live from the environment on every call (no import-time
snapshot) so a container bounce is not required to flip them mid-session.
"""
from __future__ import annotations

import os
import re
import warnings
from typing import Any

try:
    from .storage import NEVER_EXPIRES_AT
except (ImportError, ModuleNotFoundError):
    NEVER_EXPIRES_AT = 4102444800.0  # 2100-01-01T00:00:00Z

_TRUTHY = ("1", "true", "yes", "on")
_FOREVER = ("", "0", "forever", "inf", "infinite", "none")

# ── Credit Cost Constants (from credit-calculator.md) ─────────────────────────
COST_PER_ENDPOINT = 1
COST_PER_SECTION = 1
COST_NL_QUERY = 3          # Screener GET /v2/companies/?q=natural_language (spikes on LLM execution)
COST_STRUCTURED_QUERY = 1  # Screener GET /v2/companies/?where=
COST_404_LOOKUP = 1        # Billed for the lookup, not the result
COST_CLIENT_ERROR = 0      # 400, 401/403, 429, 5xx free early rejection
BUDGET_QUINTET_HARVEST_MAX = 100
MAX_RECOMMENDED_SECTIONS = 5

ALLOWED_SECTIONS = {
    "overview",
    "valuation",
    "future",
    "peers",
    "financials",
    "dividend",
    "ownership",
    "management",
    "corporate_actions",
}

__all__ = [
    "ALLOWED_SECTIONS",
    "BUDGET_QUINTET_HARVEST_MAX",
    "COST_404_LOOKUP",
    "COST_CLIENT_ERROR",
    "COST_NL_QUERY",
    "COST_PER_ENDPOINT",
    "COST_PER_SECTION",
    "COST_STRUCTURED_QUERY",
    "MAX_RECOMMENDED_SECTIONS",
    "NEVER_EXPIRES_AT",
    "NLQueryWarning",
    "assert_quintet_budget",
    "cache_only_mode",
    "cache_ttl_seconds",
    "calculate_quintet_budget",
    "check_quarterly_dates_first",
    "check_query_params",
    "freeze_max_age_seconds",
    "offline_mode",
    "upstream_gated",
    "validate_minimal_sections",
    "validate_ticker",
]


class NLQueryWarning(UserWarning):
    """Warns against 3-credit natural language queries (?q=)."""


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


def offline_mode() -> bool:
    """`SECTORS_OFFLINE=1` - upstream is closed; disk (cache + freeze) still serves."""
    return _flag("SECTORS_OFFLINE")


def cache_only_mode() -> bool:
    """`SECTORS_CACHE_ONLY=1` - cache-or-nothing; a miss raises instead of billing."""
    return _flag("SECTORS_CACHE_ONLY")


def upstream_gated() -> bool:
    """True when ANY operator gate forbids a fresh upstream call."""
    return offline_mode() or cache_only_mode()


def cache_ttl_seconds(endpoint: str | None = None) -> float:
    """Lifetime for a freshly written `sectors_cache` row, in seconds.

    Default = forever (row stamped with `NEVER_EXPIRES_AT`). `SECTORS_CACHE_TTL_DAYS=N`
    pins N days; `SECTORS_CACHE_TTL_DAYS=tiers` falls back to the legacy
    per-endpoint table (`server.sectors._ttl_for`).

    Returned as a RELATIVE delta because `SectorsCache.set()` stores
    `now + ttl_seconds`.
    """
    raw = os.getenv("SECTORS_CACHE_TTL_DAYS", "").strip().lower()
    if raw in _FOREVER:
        return NEVER_EXPIRES_AT - _now()
    if raw in ("tiers", "legacy", "tier"):
        try:
            from .sectors import _ttl_for  # late import: policy -> client, never the reverse
            return float(_ttl_for(endpoint or ""))
        except (ImportError, ModuleNotFoundError):
            return 6 * 3600.0
    try:
        days = float(raw)
    except ValueError:
        return NEVER_EXPIRES_AT - _now()
    return days * 86400.0 if days > 0 else NEVER_EXPIRES_AT - _now()


def freeze_max_age_seconds() -> float:
    """Max age of a freeze file before it is refused, in seconds.

    Default = `inf` (forever). `FREEZE_TTL_DAYS=N` restores an N-day gate.
    A refused freeze is only ever a *degradation* (honest empty / chart off) -
    it must never be the reason a cache read is skipped.
    """
    raw = os.getenv("FREEZE_TTL_DAYS", "").strip().lower()
    if raw in _FOREVER:
        return float("inf")
    try:
        days = float(raw)
    except ValueError:
        return float("inf")
    return days * 86400.0 if days > 0 else float("inf")


def check_query_params(params: dict[str, Any] | None, strict: bool = False) -> None:
    """Reject or warn against natural language queries (?q=).

    Screener GET /v2/companies/?q= costs 3 credits because an LLM executes.
    Structured 'where=' costs only 1 credit.
    """
    if not params:
        return
    if "q" in params and params["q"]:
        msg = (
            "Natural language query '?q=' detected (costs 3 credits). "
            "Reject/warn: prefer structured 'where=' queries (1 credit) to protect budget."
        )
        if strict:
            raise ValueError(msg)
        warnings.warn(msg, NLQueryWarning, stacklevel=2)


_IDX_TICKER_RE = re.compile(r"^[A-Z0-9]{4,6}$")


def validate_ticker(symbol: str, known_universe: set[str] | list[str] | None = None) -> str:
    """Validate ticker existence and format before dispatch.

    404s still incur API credit penalty ('billed for the lookup, not the result').
    Pre-validating avoids burning credits on typos or non-existent tickers.
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError(f"Invalid ticker: {symbol!r} (must be non-empty string)")
    clean = symbol.strip().upper().removesuffix(".JK")
    if not _IDX_TICKER_RE.match(clean):
        raise ValueError(f"Invalid IDX ticker format: {symbol!r}")
    if known_universe is not None and clean not in known_universe:
        raise ValueError(
            f"Ticker {clean} not found in known universe "
            "(pre-dispatch check to avoid 404 credit penalty)"
        )
    return clean


def check_quarterly_dates_first(symbol: str, available_dates: list[Any] | None) -> bool:
    """Ensure quarterly-financial-dates is checked before pulling full quarterly statements.

    Pulling quarterly data for a ticker or period with no filings incurs 1 credit
    for empty results. Checking dates first verifies data exists before pulling full financials.
    """
    if available_dates is None:
        raise ValueError(
            f"Must check 'quarterly-financial-dates' for {symbol} before pulling full quarterly "
            "to avoid 1-credit penalty on empty reports."
        )
    return len(available_dates) > 0


def validate_minimal_sections(
    sections: str | list[str], max_sections: int = MAX_RECOMMENDED_SECTIONS
) -> list[str]:
    """Validate and normalize sections parameter to prefer minimal payloads over bloated ones.

    Each section costs 1 credit or inflates payloads; requesting only necessary
    sections prevents bloated payloads and preserves cache efficiency.
    """
    if isinstance(sections, str):
        parts = [s.strip().lower() for s in sections.split(",") if s.strip()]
    elif isinstance(sections, (list, tuple, set)):
        parts = [str(s).strip().lower() for s in sections if str(s).strip()]
    else:
        raise ValueError(f"Invalid sections argument: {sections!r}")

    if not parts:
        raise ValueError("At least one section must be specified in sections parameter")

    deduped = []
    seen = set()
    for s in parts:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    if len(deduped) > max_sections:
        warnings.warn(
            f"Requesting {len(deduped)} sections ({','.join(deduped)}) exceeds recommended "
            f"minimal limit of {max_sections}. Prefer minimal sections= parameter.",
            UserWarning,
            stacklevel=2,
        )
    return deduped


QUINTET_TICKERS = ["RATU", "CDIA", "MTEL", "BBCA", "ADRO"]
QUINTET_SUBSECTORS = ["banks", "energy", "telecommunication-service", "basic-materials"]


def calculate_quintet_budget() -> dict[str, Any]:
    """Calculate dry-run budget for a quintet harvest per docs/sectors-swap.md / credit-calculator.md.

    Credit math:
      per ticker ~17 (report 5 sections + daily + dates/quarterly + segments +
        shareholders + news + filings + actions + flow + brokertop +
        suspensions + listing)
      shared ~12 (universe + idx-mcap + jci + 4 subsectors x2 + screener)
      full quintet harvest = 5 * 17 + 12 = 97 credits.
    """
    per_ticker_calls = [
        ("report_5_sections", 5),
        ("daily_90d", 1),
        ("quarterly_dates_and_quarterly", 2),
        ("segments", 1),
        ("shareholders_composition", 1),
        ("news", 1),
        ("filings", 1),
        ("corporate_actions", 1),
        ("foreign_flow_90d", 1),
        ("broker_top", 1),
        ("suspensions", 1),
        ("listing_performance", 1),
    ]
    cost_per_ticker = sum(cost for _, cost in per_ticker_calls)  # 17
    shared_calls = [
        ("universe_close", 1),
        ("idx_market_cap", 1),
        ("index_daily_jci", 1),
        ("screener_breadth", 1),
        ("subsector_reports", 2 * len(QUINTET_SUBSECTORS)),  # 8
    ]
    cost_shared = sum(cost for _, cost in shared_calls)  # 12
    total_cost = (cost_per_ticker * len(QUINTET_TICKERS)) + cost_shared  # 5 * 17 + 12 = 97

    return {
        "tickers": QUINTET_TICKERS,
        "cost_per_ticker": cost_per_ticker,
        "cost_shared": cost_shared,
        "total_budget": total_cost,
        "budget_cap": BUDGET_QUINTET_HARVEST_MAX,
        "within_budget": total_cost < BUDGET_QUINTET_HARVEST_MAX,
    }


def assert_quintet_budget() -> int:
    """Assert that dry-run budget for quintet harvest remains strictly under 100 credits."""
    budget = calculate_quintet_budget()
    total = budget["total_budget"]
    assert total < BUDGET_QUINTET_HARVEST_MAX, (
        f"Quintet harvest dry-run budget {total} credits exceeds cap {BUDGET_QUINTET_HARVEST_MAX}"
    )
    return total


def _now() -> float:
    import time
    return time.time()
