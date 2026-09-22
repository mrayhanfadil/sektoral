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

Both gates are read live from the environment on every call (no import-time
snapshot) so a container bounce is not required to flip them mid-session.
"""
from __future__ import annotations

import os

from .storage import NEVER_EXPIRES_AT

_TRUTHY = ("1", "true", "yes", "on")
_FOREVER = ("", "0", "forever", "inf", "infinite", "none")

__all__ = [
    "NEVER_EXPIRES_AT",
    "cache_only_mode",
    "offline_mode",
    "upstream_gated",
    "cache_ttl_seconds",
    "freeze_max_age_seconds",
]


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
        from .sectors import _ttl_for  # late import: policy -> client, never the reverse
        return float(_ttl_for(endpoint or ""))
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


def _now() -> float:
    import time
    return time.time()
