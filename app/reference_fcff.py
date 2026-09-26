"""Independent reference calculation of a going-concern FCFF value per share (plan §5.6).

A second, deliberately plain implementation that reads only the operating
driver file and the valuation's bridge inputs (rates, cash, debt, minorities,
distributions, shares, spot rate, valuation date). It imports nothing from the
production forecast or valuation code, so an error in either path shows up as
a difference. It follows the same documented conventions: FY1 = official H1 +
modelled H2; operating flows at mid-period; the H2 flow alone is valued from a
30 June valuation date; the terminal is the last year without contracts that
end before the first terminal year closes, capitalised by Gordon, restated to
NOPAT x (1 - g / RONIC) when a return on new capital is given.
"""
from __future__ import annotations

from datetime import date

TOLERANCE = 0.005  # relative gap to the production value per share


def _years(later, earlier):
    return (later - earlier).days / 365.25


def _flows(d):
    """Annual (and FY1 second-half) operating flows from the driver file alone."""
    h1 = d["anchor"]["h1"]
    year0 = int(d["anchor"]["year"])
    tax = d["tax"]["rate"]["values"][0]
    dep_rate = d["depreciation"]["rate_on_opening_net_ppe"]["values"][0]
    dep_h2 = d["depreciation"]["h2_to_h1"]["values"][0]
    wc = d["working_capital"]
    rd = wc["receivable_days_on_revenue"]["values"][0]
    idays = wc["inventory_days_on_variable_cost"]["values"][0]
    pdays = wc["payable_days_on_variable_cost"]["values"][0]
    total_h1_units = sum(s["h1_volume"] for s in d["segments"])
    var = d.get("variable_costs") or []

    def active(seg, year, full):
        end = seg.get("contract_end")
        if not end:
            return full
        end = date.fromisoformat(end)
        return full if end.year > year else 0.0 if end.year < year else full * end.month / 12

    units, prices = {}, {}
    for s in d["segments"]:
        full = s["h1_volume"] * (1 + s["h2_volume_to_h1"]["values"][0])
        price = s["h1_revenue"] / s["h1_volume"] * (1 + s["price_growth_pct"]["values"][0] / 100)
        units[s["id"]], prices[s["id"]] = [full], [price]
        for i in range(4):
            units[s["id"]].append(units[s["id"]][-1] * (1 + s["volume_growth_pct"]["values"][i] / 100))
            prices[s["id"]].append(prices[s["id"]][-1] * (1 + s["price_growth_pct"]["values"][i + 1] / 100))
    unit_cost = {}
    for v in var:
        c = v["h1_amount"] / total_h1_units
        unit_cost[v["id"]] = []
        for g in v["unit_cost_growth_pct"]["values"]:
            c *= 1 + g / 100
            unit_cost[v["id"]].append(c)
    fixed = []
    for f in d["fixed_costs"]:
        path = [f["h1_amount"] * (1 + f["h2_to_h1"]["values"][0])]
        for g in f["growth_pct"]["values"]:
            path.append(path[-1] * (1 + g / 100))
        fixed.append((f["h1_amount"] * f["h2_to_h1"]["values"][0], path))
    capex_out = d["capex"]["sustaining_outyears"]["values"]
    committed = (d["capex"].get("committed_outyears") or {}).get("values") or [0.0] * 4
    op = d["opening"]
    nwc_prev = op["fy0_close"]["receivables"] + op["fy0_close"]["inventories"] - op["fy0_close"]["payables"]
    nwc_h1 = op["h1_close"]["receivables"] + op["h1_close"]["inventories"] - op["h1_close"]["payables"]
    ppe = op["h1_close"]["ppe"]

    years, h2 = [], None
    for i in range(5):
        year = year0 + i
        seg_units = {s["id"]: active(s, year, units[s["id"]][i]) for s in d["segments"]}
        if i == 0:
            h2_units = {s["id"]: max(seg_units[s["id"]] - s["h1_volume"], 0.0) for s in d["segments"]}
            h2_rev = sum(h2_units[k] * prices[k][0] for k in h2_units)
            h2_var = sum(unit_cost[v["id"]][0] * sum(h2_units.values()) for v in var)
            h2_fix = sum(f[0] for f in fixed)
            h2_da = h1["depreciation"] * dep_h2
            revenue = h1["revenue"] + h2_rev
            var_total = h1["variable_costs"] + h2_var
            ebitda = revenue - var_total - h1["fixed_costs"] - h2_fix
            da = h1["depreciation"] + h2_da
            capex = h1["capex"] + sum(x["amount"] for x in d["capex"]["h2_items"])
            ppe = ppe + (capex - h1["capex"]) - h2_da
            h2_ebit = h2_rev - h2_var - h2_fix - h2_da
        else:
            revenue = sum(seg_units[k] * prices[k][i] for k in seg_units)
            var_total = sum(unit_cost[v["id"]][i] * sum(seg_units.values()) for v in var)
            ebitda = revenue - var_total - sum(f[1][i] for f in fixed)
            da = dep_rate * ppe
            capex = capex_out[i - 1] + committed[i - 1]
            ppe = ppe + capex - da
        nwc = rd / 365 * revenue + idays / 365 * var_total - pdays / 365 * var_total
        ebit = ebitda - da
        fcff = ebit * (1 - tax) + da - capex - (nwc - nwc_prev)
        if i == 0:
            h2 = h2_ebit * (1 - tax) + h2_da - (capex - h1["capex"]) - (nwc - nwc_h1)
        years.append({"year": year, "revenue": revenue, "var": var_total, "ebit": ebit,
                      "nopat": ebit * (1 - tax), "da": da, "capex": capex,
                      "dnwc": nwc - nwc_prev, "fcff": fcff, "units": seg_units})
        nwc_prev = nwc
    # Terminal base: drop contracts ending before the first terminal year closes.
    last = years[-1]
    first_terminal = year0 + 5
    lost_rev = lost_units = 0.0
    for s in d["segments"]:
        end = s.get("contract_end")
        if end and date.fromisoformat(end) <= date(first_terminal, 12, 31):
            lost_rev += last["units"][s["id"]] * prices[s["id"]][4]
            lost_units += last["units"][s["id"]]
    lost_var = sum(unit_cost[v["id"]][4] * lost_units for v in var)
    t_ebit = last["ebit"] - lost_rev + lost_var
    terminal = {"nopat": t_ebit * (1 - tax), "da": last["da"], "capex": last["capex"],
                "dnwc": last["dnwc"]}
    terminal["fcff"] = terminal["nopat"] + terminal["da"] - terminal["capex"] - terminal["dnwc"]
    return years, h2, terminal


def value(drivers, *, wacc, g, valuation_date, cash, debt, nci, distributions, shares,
          to_idr=1.0, parent_share=1.0, terminal_ronic=None):
    """Rupiah value per share from the driver file and bridge inputs."""
    years, h2_fcff, terminal = _flows(drivers)
    vd = valuation_date if isinstance(valuation_date, date) else date.fromisoformat(str(valuation_date))
    pv = 0.0
    for row in years:
        start, end = date(row["year"], 1, 1), date(row["year"], 12, 31)
        if end <= vd:
            continue
        if start > vd:
            flow, begin = row["fcff"], start
        elif vd == date(row["year"], 6, 30):
            flow, begin = h2_fcff, vd
        else:
            flow = row["fcff"] * _years(end, vd) / _years(end, start)
            begin = vd
        t = _years(begin, vd) + _years(end, begin) / 2
        pv += flow / (1 + wacc) ** t
    if terminal_ronic:
        t_flow = terminal["nopat"] * (1 + g) * (1 - g / terminal_ronic)
    else:
        t_flow = (terminal["fcff"] + terminal["capex"] - max(terminal["capex"], terminal["da"])) * (1 + g)
    end_last = _years(date(years[-1]["year"], 12, 31), vd)
    ev = pv + t_flow / (wacc - g) / (1 + wacc) ** end_last
    equity = ev + cash - debt
    equity = equity - nci - distributions if nci is not None else equity * parent_share - distributions
    return {"per_share": equity / shares * to_idr, "ev": ev, "pv_explicit": pv,
            "terminal_flow": t_flow, "h2_fcff": h2_fcff,
            "fcff": [r["fcff"] for r in years]}


def compare(drivers, detail) -> dict:
    """Reference vs production value per share for a scenario DCF detail."""
    view = detail.get("native") or detail
    to_idr = detail.get("fx") or 1.0
    ref = value(drivers, wacc=detail["wacc"], g=detail["g"],
                valuation_date=detail["valuation_date"], cash=view["cash"], debt=view["debt"],
                nci=view.get("nci"), distributions=view.get("distributions") or 0.0,
                shares=detail["shares"], to_idr=to_idr,
                parent_share=detail.get("attributable_share") or 1.0,
                terminal_ronic=detail.get("terminal_ronic"))
    production = detail["per_share"]
    gap = abs(ref["per_share"] - production) / abs(production) if production else None
    return {"status": "agrees" if gap is not None and gap <= TOLERANCE else "differs",
            "reference_per_share": ref["per_share"], "production_per_share": production,
            "relative_gap": gap, "tolerance": TOLERANCE,
            "reference_fcff": ref["fcff"],
            "method": "app.reference_fcff: independent implementation from the driver file"}
