"""Independent reference calculation of a bank DDM value per share (plan §5.6).

Reads only the bank driver file, the first-year dividend already declared
(historical payout x prior-year parent profit) and the valuation's inputs
(Cost of Equity, g, valuation date, share count). It imports nothing from
the production bank model or valuation: the balance sheet is solved in
closed form (earning assets are linear in themselves through NII and equity)
instead of by the production fixed point. Conventions follow the model:
FY1 = official H1 + H2 on the 30 June and year-end balances; later years on
opening and closing averages; deposits = net loans / 30 June LDR; dividends
paid in year t = payout x parent profit of t-1; the DDM discounts each DPS a
quarter after its fiscal year-end; the terminal pays the sustainable payout
1 - g / ROE capped at the policy payout. Capital-floor adjustments are not
reproduced: a model that applied one is reported as not comparable.
"""
from __future__ import annotations

from datetime import date

TOLERANCE = 0.005


def _years(later, earlier):
    return (later - earlier).days / 365.25


def path(d, prior_profit, first_payout):
    """Parent profit, payout and equity per forecast year from the driver file alone."""
    mid, fy0, h1 = d["h1_close"], d["fy0_close"], d["h1"]
    cov = mid["allowance_for_loans"] / mid["gross_loan"]
    ldr = (mid["gross_loan"] - mid["allowance_for_loans"]) / mid["total_deposit"]
    other_liab = (mid["other_interest_bearing_liabilities"]
                  + mid["non_interest_bearing_liabilities"]) / mid["total_deposit"]
    ne = (mid["total_assets"] - mid["non_loan_earning_assets"] + mid["allowance_for_loans"]) \
        / mid["total_assets"]
    tax = h1["tax"] / h1["earnings_before_tax"]
    share = h1["net_profit_attributable"] / h1["net_profit"]
    payouts = d["payout_path"]["values"]
    gl_prev, ea_prev = fy0["gross_loan"], fy0["non_loan_earning_assets"]
    parent_eq, nci = fy0["parent_equity"], fy0["non_controlling_interest"]
    prev_parent, rate_paid = prior_profit, first_payout
    rows = []
    for i, row in enumerate(d["drivers"]):
        v = {k: row[k]["value"] / 100 for k in ("loan_growth_pct", "nim_pct", "non_ii_to_nii_pct",
                                                 "cost_to_income_pct", "cost_of_credit_pct")}
        gl = gl_prev * (1 + v["loan_growth_pct"])
        allowance = cov * gl
        dep = (gl - allowance) / ldr
        liabilities = dep * (1 + other_liab)
        paid = rate_paid * max(prev_parent, 0.0)
        margin = (1 + v["non_ii_to_nii_pct"]) * (1 - v["cost_to_income_pct"]) * v["nim_pct"] * (1 - tax)
        if i == 0:
            ea_mid, loans_mid = mid["non_loan_earning_assets"], mid["gross_loan"]
            # H2 net profit = margin x (ea_mid + ea) / 4 - (1 - tax) x coc x (loans_mid + gl) / 4
            k = margin / 4
            c = margin * ea_mid / 4 - (1 - tax) * v["cost_of_credit_pct"] * (loans_mid + gl) / 4
            base_net = h1["net_profit"]
            base_parent = h1["net_profit_attributable"]
        else:
            k = margin / 2
            c = margin * ea_prev / 2 - (1 - tax) * v["cost_of_credit_pct"] * (gl_prev + gl) / 2
            base_net = base_parent = 0.0
        equity_prev = parent_eq + nci
        # ea = (L + equity_prev + base_net + k ea + c - paid)(1 - ne) + allowance
        ea = ((liabilities + equity_prev + base_net + c - paid) * (1 - ne) + allowance) \
            / (1 - k * (1 - ne))
        net_new = k * ea + c
        net = base_net + net_new
        parent = base_parent + net_new * share
        parent_eq_new = parent_eq + parent - paid
        nci += net - parent
        rows.append({"year": int(row["year"]), "parent": parent, "net": net,
                     "payout": payouts[i], "paid": paid,
                     "roe": parent / ((parent_eq + parent_eq_new) / 2)})
        parent_eq = parent_eq_new
        gl_prev, ea_prev, prev_parent, rate_paid = gl, ea, parent, payouts[i]
    return rows


def value(d, *, prior_profit, first_payout, coe, g, valuation_date, shares, to_idr=1.0):
    rows = path(d, prior_profit, first_payout)
    vd = valuation_date if isinstance(valuation_date, date) else date.fromisoformat(str(valuation_date))
    pv, last_factor, last_eps = 0.0, None, None
    for r in rows:
        end = date(r["year"], 12, 31)
        if end <= vd:
            continue
        t = _years(end, vd) + 0.25
        eps = max(r["parent"], 0.0) * to_idr / shares
        factor = 1 / (1 + coe) ** t
        pv += eps * r["payout"] * factor
        last_factor, last_eps = factor, eps
    cap = d["payout_path"]["values"][-1]
    terminal_payout = min(max(1 - g / rows[-1]["roe"], 0.0), cap)
    tv = last_eps * (1 + g) * terminal_payout / (coe - g)
    return {"per_share": pv + tv * last_factor, "rows": rows, "terminal_payout": terminal_payout}


def compare(d, detail, model, prior_profit, first_payout):
    """Reference vs production DDM value per share."""
    if (model or {}).get("constraints", {}).get("applied"):
        return {"status": "not_comparable",
                "reason": "the production model applied a capital or funding constraint"}
    ref = value(d, prior_profit=prior_profit, first_payout=first_payout, coe=detail["coe"],
                g=detail["g"], valuation_date=detail["valuation_date"], shares=detail["shares"],
                to_idr=detail.get("fx") or 1.0)
    production = detail["per_share"]
    gap = abs(ref["per_share"] - production) / abs(production) if production else None
    return {"status": "agrees" if gap is not None and gap <= TOLERANCE else "differs",
            "reference_per_share": ref["per_share"], "production_per_share": production,
            "relative_gap": gap, "tolerance": TOLERANCE,
            "reference_parent_profit": [r["parent"] for r in ref["rows"]],
            "method": "app.reference_ddm: closed-form balance sheet from the driver file"}
