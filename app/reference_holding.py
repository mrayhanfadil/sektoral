"""Independent recomputation of the holding SOTP value (plan §5.6).

It rebuilds value per share from the raw components, without the production
code in ``app.method_chain.holding_sotp`` or ``app.landbank.nav``:

- each listed subsidiary: shares held / shares issued x market capitalisation;
- the rest of the group: parent equity less the stake's share of each listed
  subsidiary's book equity (so no asset is counted twice);
- the landbank: the net saleable area sold at the stated pace in whole and
  partial years, at the starting price growing at its rate, times the cash
  margin, discounted mid-year; only the owner's stake of the excess over book
  is added.

``compare`` reports agreement within the release tolerance.
"""
from __future__ import annotations

import math

TOLERANCE = 0.005
M2_PER_HA = 10_000


def _landbank_nav(inp, rate):
    net_ha = inp["gross_ha"] * inp["net_ratio"]
    full_years = math.floor(net_ha / inp["pace_ha"] + 1e-12)
    tail = net_ha - full_years * inp["pace_ha"]
    sold = [inp["pace_ha"]] * full_years + ([tail] if tail > 1e-9 else [])
    unit = M2_PER_HA * inp["asp"] * inp["cash_margin"]
    return sum(ha * unit * (1 + inp["asp_growth"]) ** t / (1 + rate) ** (t + 0.5)
               for t, ha in enumerate(sold))


def value(listed, parent_equity, shares, landbank=None):
    market = sum(row["stake"] * row["market_cap"] for row in listed)
    book_share = sum(row["stake"] * row["book_equity"] for row in listed)
    uplift = 0.0
    if landbank:
        inp = landbank["inputs"]
        uplift = (_landbank_nav(inp, landbank["rate"]) - inp["carrying_idr"]) * inp["stake"]
    total = market + (parent_equity - book_share) + uplift
    return {"per_share": total / shares, "total": total, "listed_market": market,
            "remainder_book": parent_equity - book_share, "landbank_uplift": uplift}


def compare(listed, parent_equity, shares, landbank, production_per_share):
    try:
        ref = value(listed, parent_equity, shares, landbank)
    except (KeyError, TypeError, ZeroDivisionError) as error:
        return {"status": "differs", "reason": f"reference could not be computed: {error}",
                "tolerance": TOLERANCE, "method": "app.reference_holding"}
    gap = (abs(ref["per_share"] - production_per_share) / abs(production_per_share)
           if production_per_share else None)
    return {"status": "agrees" if gap is not None and gap <= TOLERANCE else "differs",
            "reference_per_share": ref["per_share"],
            "production_per_share": production_per_share, "relative_gap": gap,
            "tolerance": TOLERANCE, "reference_components": ref,
            "method": "app.reference_holding: independent holding SOTP recomputation"}
