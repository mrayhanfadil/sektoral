"""RNAV of an industrial-estate landbank (spec §4.5 Opsi C, per-asset NAV).

Undeveloped land sits in the balance sheet at cost. Its value to the owner is
the cash from selling it over time: net saleable area sold at the historical
pace, at the latest marketing price growing at its historical rate, times the
cash margin, discounted at the policy Cost of Equity. The book value of the
land is replaced by that NAV, and only the owner's stake of the difference is
added to a holding SOTP (the rest belongs to minorities).

Every issuer figure comes from the evidence pack (``landbank``); what the
issuer does not disclose (the saleable share of gross land) is a labelled
analyst assumption in ``data/analyst_scenarios/<T>.json``.
"""
from __future__ import annotations

M2_PER_HA = 10_000
PACES = (25.0, 50.0, 75.0, 100.0, 135.0)
GROWTHS = (0.0, None, 0.05)          # None = the historical base growth


def _num(value):
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def _cagr(history):
    """Compound growth between the first and last year of a {year: value} map."""
    years = sorted((int(y), _num(v)) for y, v in (history or {}).items() if _num(v))
    if len(years) < 2 or years[-1][0] == years[0][0]:
        return None
    (y0, v0), (y1, v1) = years[0], years[-1]
    return (v1 / v0) ** (1 / (y1 - y0)) - 1


def inputs(intake):
    """(inputs, gaps): sourced landbank facts and labelled assumptions."""
    evidence = (intake.get("official_evidence") or {}).get("landbank") or {}
    assumptions = ((intake.get("analyst_scenario") or {}).get("landbank_assumptions") or {})
    land = evidence.get("land_for_development") or {}
    history = (evidence.get("industrial_marketing_sales_ha") or {}).get("history") or {}
    asp = (evidence.get("marketing_asp_idr_per_m2") or {}).get("history") or {}
    latest = evidence.get("marketing_sales_1h26") or {}
    segment = evidence.get("property_segment_idr_bn") or {}
    gaps = []

    revenue = segment.get("revenue") or {}
    gross = segment.get("gross_profit") or {}
    ebitda = segment.get("ebitda") or {}
    periods = [p for p in revenue if _num(revenue.get(p)) and _num(gross.get(p))
               and _num(ebitda.get(p))]
    total_rev = sum(revenue[p] for p in periods)
    gross_margin = sum(gross[p] for p in periods) / total_rev if total_rev else None
    opex_ratio = (sum(gross[p] - ebitda[p] for p in periods) / total_rev
                  if total_rev else None)
    latest_asp = (_num(latest.get("value_idr")) / (_num(latest.get("ha")) * M2_PER_HA)
                  if _num(latest.get("value_idr")) and _num(latest.get("ha")) else None)
    paces = [_num(v) for v in history.values() if _num(v) is not None]
    values = {
        "gross_ha": _num(land.get("gross_ha")),
        "carrying_idr": _num(land.get("carrying_idr")),
        "carrying_as_of": land.get("as_of"),
        "stake": _num((evidence.get("scs_ownership") or {}).get("stake")),
        "net_ratio": _num(assumptions.get("net_saleable_ratio")),
        "pace_ha": sum(paces) / len(paces) if paces else None,
        "pace_years": f"{min(history)}-{max(history)}" if history else None,
        "asp": latest_asp,
        "asp_growth": _cagr({y: v for y, v in asp.items() if y != "2024"}),
        "gross_margin": gross_margin,
        "opex_ratio": opex_ratio,
        "margin_periods": f"{periods[0]}-{periods[-1]}" if periods else None,
        "final_tax": _num(assumptions.get("final_tax_rate")),
        "evidence": evidence, "assumptions": assumptions,
    }
    for key in ("gross_ha", "carrying_idr", "stake", "net_ratio", "pace_ha", "asp",
                "asp_growth", "gross_margin", "opex_ratio", "final_tax"):
        if values[key] is None:
            gaps.append(key)
    if not gaps:
        net_m2 = values["gross_ha"] * values["net_ratio"] * M2_PER_HA
        # The book cost of the land is already inside the reported gross margin;
        # it is sunk, so the cash margin adds it back per saleable m2.
        values["land_cost_share"] = values["carrying_idr"] / net_m2 / values["asp"]
        values["cash_margin"] = (values["gross_margin"] + values["land_cost_share"]
                                 - values["opex_ratio"] - values["final_tax"])
    return values, gaps


def nav(inp, rate, pace_ha=None, growth=None):
    """Present value of selling the net saleable land; sales at mid-year from the
    valuation date, the last year partial."""
    pace = inp["pace_ha"] if pace_ha is None else pace_ha
    growth = inp["asp_growth"] if growth is None else growth
    left = inp["gross_ha"] * inp["net_ratio"]
    pv, year = 0.0, 0
    while left > 1e-9:
        ha = min(pace, left)
        left -= ha
        cash = ha * M2_PER_HA * inp["asp"] * (1 + growth) ** year * inp["cash_margin"]
        pv += cash / (1 + rate) ** (year + 0.5)
        year += 1
    return pv, year


def value(intake, rate):
    """Landbank RNAV and the owner's uplift over book, or (None, gaps)."""
    inp, gaps = inputs(intake)
    if gaps:
        return None, gaps
    base_nav, years = nav(inp, rate)
    uplift = (base_nav - inp["carrying_idr"]) * inp["stake"]
    grid = {}
    for pace in PACES:
        for growth in GROWTHS:
            g = inp["asp_growth"] if growth is None else growth
            grid[(pace, round(g, 4))] = (nav(inp, rate, pace, g)[0] - inp["carrying_idr"]) \
                * inp["stake"]
    return {"inputs": inp, "rate": rate, "nav": base_nav, "years": years,
            "uplift_attributable": uplift, "grid": grid}, []
