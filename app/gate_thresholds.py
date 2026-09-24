"""Single source of truth for Gate 5 output-sanity thresholds.

Framework (Gates 0-5, A. M. Armand):
- Review Required when upside > +100% or downside < -50%.
- Terminal value > 80% of EV: flagged with implied exit check, not blocking.
- Implied exit EV/EBITDA outside peer/history range: flag, require cross-check.

Used by app.method_chain, app.model_profiles, app.harness.g3,
app.valuation and spec §4.4/§4.6. Tests assert they agree.
"""
from __future__ import annotations


EXTREME_UPSIDE_PCT = 100.0
EXTREME_DOWNSIDE_PCT = -50.0
TV_SHARE_PCT = 80.0
SCALE_BAND = (0.2, 3.0)


def _upside_pct(upside) -> float | None:
    """Normalize upside to percent. Accepts ratio (0.2) or percent (20.0)."""
    if upside is None or isinstance(upside, bool):
        return None
    try:
        u = float(upside)
    except (TypeError, ValueError):
        return None
    # Heuristic from model_profiles: |u|<=2 is a ratio, else percent.
    # Keep int-percent edge: 1 -> 1%, not 100%.
    if abs(u) <= 2.0 and not (u > 1.0 and u == int(u)):
        return u * 100.0
    return u


def is_extreme_ratio(upside_ratio) -> bool:
    """Chain upside is a ratio (per_share/price-1): extreme if >+100% or <-50%."""
    if upside_ratio is None or isinstance(upside_ratio, bool):
        return False
    try:
        u = float(upside_ratio)
    except (TypeError, ValueError):
        return False
    return u > 1.0 or u < -0.5


def is_extreme_pct(upside_pct) -> bool:
    """Gate upside already in percent: extreme if >+100 or <-50."""
    if upside_pct is None or isinstance(upside_pct, bool):
        return False
    try:
        p = float(upside_pct)
    except (TypeError, ValueError):
        return False
    # If a ratio slipped in (|p|<=2), convert to percent first.
    if abs(p) <= 2.0 and not (p > 1.0 and p == int(p)):
        p = p * 100.0
    return p > EXTREME_UPSIDE_PCT or p < EXTREME_DOWNSIDE_PCT


def is_extreme(upside) -> bool:
    """Backward-compat: handles ratio (chain) and percent (gates).

    Ratios >2 (e.g. 49.4 = 4940%) are always extreme; percents in (2,100]
    are not extreme on the upside. To disambiguate, treat |u|>2 and |u|<=100
    as percent (conservative), but |u|>100 as extreme either way.
    Chain callers should prefer is_extreme_ratio for correctness.
    """
    if upside is None or isinstance(upside, bool):
        return False
    try:
        u = float(upside)
    except (TypeError, ValueError):
        return False
    if abs(u) <= 2.0:
        # Ratio domain: convert, but keep int-percent edge.
        if u > 1.0 and u == int(u):
            pct = u
        else:
            pct = u * 100.0
        return pct > EXTREME_UPSIDE_PCT or pct < EXTREME_DOWNSIDE_PCT
    if abs(u) > 100.0:
        return True
    # (2,100]: ambiguous; treat as percent (not extreme unless >100/<-50).
    return u > EXTREME_UPSIDE_PCT or u < EXTREME_DOWNSIDE_PCT


def tv_flagged(tv_share) -> bool:
    """True when terminal share exceeds 80% of EV (flag, not blocker)."""
    if tv_share is None or isinstance(tv_share, bool):
        return False
    try:
        v = float(tv_share)
    except (TypeError, ValueError):
        return False
    pct = v * 100.0 if v <= 1.0 else v
    return pct > TV_SHARE_PCT
