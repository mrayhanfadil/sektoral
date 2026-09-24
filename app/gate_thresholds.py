"""Single source of truth for Method Gate 5 output-sanity thresholds.

Framework (Method Gates 0-5, A. M. Armand):
- Review Required when upside > +100% or downside < -50%.
- Terminal value > 80% of EV: flagged with implied exit check, not blocking.
- Implied exit EV/EBITDA outside peer/history range: flag, require cross-check.

Used by app.method_chain, app.model_profiles, app.harness.s3,
app.valuation and spec §4.4/§4.6. Tests assert they agree.
"""
from __future__ import annotations


EXTREME_UPSIDE_PCT = 100.0
EXTREME_DOWNSIDE_PCT = -50.0
TV_SHARE_PCT = 80.0
SCALE_BAND = (0.2, 3.0)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def gate_upside_pct(inputs: dict):
    """Upside in percent from gate inputs, with explicit units.

    ``upside_pct`` is always percent (1.5 means +1,5%); ``upside`` is always a
    ratio (0.015 means +1,5%). Magnitude is never used to guess the unit:
    that heuristic read +1,5% as +150%.
    """
    pct = _number(inputs.get("upside_pct"))
    if pct is not None:
        return pct
    ratio = _number(inputs.get("upside"))
    return ratio * 100.0 if ratio is not None else None


def is_extreme_ratio(upside_ratio) -> bool:
    """Chain upside is a ratio (per_share/price-1): extreme if >+100% or <-50%."""
    u = _number(upside_ratio)
    return u is not None and (u * 100.0 > EXTREME_UPSIDE_PCT or u * 100.0 < EXTREME_DOWNSIDE_PCT)


def is_extreme_pct(upside_pct) -> bool:
    """Upside in percent: extreme if >+100 or <-50. No ratio guessing."""
    p = _number(upside_pct)
    return p is not None and (p > EXTREME_UPSIDE_PCT or p < EXTREME_DOWNSIDE_PCT)


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
