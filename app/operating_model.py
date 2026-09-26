"""Going-concern operating model: segment volume x price to FCFF and three statements.

Plan §5.1: revenue from issuer drivers (volume, realized price, contract end),
variable costs per unit of volume, fixed costs, D&A on the opening asset base,
sustaining and committed capex, operating working capital in days, fixed-rate
debt, interest income on liquidity, tax, dividends and minorities. The first
forecast year is the official first-half actual plus a modelled second half;
the next four years roll from it. Every row reconciles:

- FCFF = NOPAT + D&A - capex - increase in operating working capital;
- assets = liabilities + equity, with liquidity (cash and investments) moving
  only through the cash-flow statement;
- the first half's segment revenue equals the official reported revenue.

The terminal line is the last forecast year without segments whose contract
ends before the first terminal year closes: a perpetuity does not keep revenue
the issuer has no right to.

The driver file (``data/operating_drivers/<TICKER>.json``) holds the sourced
first-half actuals and opening balances (``source_refs`` into its ``sources``)
and each forward driver as ``{"values", "kind", "rationale"}`` where ``kind``
is ``sourced`` or ``analyst_assumption``. Shared code holds no issuer values.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "operating_drivers"
HORIZON = 5
TOLERANCE = 1.0          # currency units; the model is exact up to float rounding
DAYS = 365.0


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def load(ticker, as_of, root=ROOT):
    """The driver file known by ``as_of``, else None (missing or not yet published)."""
    path = Path(root) / f"{str(ticker).upper()}.json"
    if not path.exists():
        return None
    drivers = json.loads(path.read_text(encoding="utf-8"))
    cutoff = _day(as_of)
    published = [_day(s.get("published_at")) for s in (drivers.get("sources") or {}).values()
                 if isinstance(s, dict)]
    if cutoff is None or any(p is None or p > cutoff for p in published):
        return None
    return drivers


def _path(driver, n, label, errors):
    """``n`` forward values of a driver record, with its kind and rationale checked."""
    if not isinstance(driver, dict):
        errors.append(f"{label} must be a driver record")
        return [0.0] * n
    values = driver.get("values")
    if not isinstance(values, list) or len(values) != n or any(_num(v) is None for v in values):
        errors.append(f"{label} needs {n} numeric values")
        return [0.0] * n
    if driver.get("kind") not in ("sourced", "analyst_assumption"):
        errors.append(f"{label} kind must be sourced or analyst_assumption")
    if not str(driver.get("rationale") or "").strip():
        errors.append(f"{label} needs a rationale")
    if driver.get("kind") == "sourced" and not driver.get("source_refs"):
        errors.append(f"{label} is sourced but cites no source")
    return [float(v) for v in values]


def _scalar(driver, label, errors):
    return _path(driver, 1, label, errors)[0]


def _cited(record, sources, label, errors):
    refs = record.get("source_refs") if isinstance(record, dict) else None
    if not refs or any(ref not in sources for ref in refs):
        errors.append(f"{label} must cite sources from the driver file")


def validate(drivers) -> list[str]:
    """Named errors; an empty list means the file can be projected."""
    errors = []
    if not isinstance(drivers, dict):
        return ["operating driver file is invalid"]
    sources = drivers.get("sources") or {}
    for key, source in sources.items():
        if not (isinstance(source, dict) and str(source.get("url") or "").startswith("https://")
                and source.get("title") and _day(source.get("published_at"))):
            errors.append(f"source {key!r} needs title, https url and published_at")
    for key in ("anchor", "segments", "fixed_costs", "depreciation", "capex",
                "working_capital", "debt", "liquidity", "tax", "distribution", "opening"):
        if key not in drivers:
            errors.append(f"driver file is missing {key}")
    if errors:
        return errors
    _cited(drivers["anchor"], sources, "anchor", errors)
    _cited(drivers["opening"], sources, "opening balances", errors)
    if not drivers["segments"]:
        errors.append("at least one revenue segment is required")
    for seg in drivers["segments"]:
        label = f"segment {seg.get('id')!r}"
        _cited(seg, sources, label, errors)
        for key in ("h1_volume", "h1_revenue"):
            if not (_num(seg.get(key)) and seg[key] > 0):
                errors.append(f"{label} {key} must be positive")
        if seg.get("contract_end") is not None and _day(seg["contract_end"]) is None:
            errors.append(f"{label} contract_end must be an ISO date")
    for item in drivers.get("variable_costs") or []:
        _cited(item, sources, f"variable cost {item.get('id')!r}", errors)
    for item in drivers["fixed_costs"]:
        _cited(item, sources, f"fixed cost {item.get('id')!r}", errors)
    capex = drivers["capex"]
    if not capex.get("h2_items"):
        errors.append("capex needs second-half items (committed projects and sustaining)")
    for item in capex.get("h2_items") or []:
        _cited(item, sources, f"capex item {item.get('id')!r}", errors)
    return errors


def _segment_volume(seg, year, full_year_volume):
    """Volume in ``year`` after a contract end: the months it still runs."""
    end = _day(seg.get("contract_end"))
    if end is None or end.year > year:
        return full_year_volume
    if end.year < year:
        return 0.0
    return full_year_volume * end.month / 12.0


def project(drivers) -> dict:
    """Five forecast years, their reconciliations and a terminal line (model currency)."""
    errors = validate(drivers)
    if errors:
        return {"status": "invalid", "errors": errors}
    n_out = HORIZON - 1
    a = drivers["anchor"]
    year0 = int(a["year"])
    years = [year0 + i for i in range(HORIZON)]
    h1 = a["h1"]
    op = drivers["opening"]

    # --- revenue by segment
    seg_rows = []
    for seg in drivers["segments"]:
        label = f"segment {seg['id']!r}"
        h2_ratio = _scalar(seg["h2_volume_to_h1"], f"{label} h2_volume_to_h1", errors)
        growth = _path(seg["volume_growth_pct"], n_out, f"{label} volume_growth_pct", errors)
        price_growth = _path(seg["price_growth_pct"], HORIZON,
                             f"{label} price_growth_pct", errors)
        price_h1 = seg["h1_revenue"] / seg["h1_volume"]
        volumes, prices = [], []
        base_full = seg["h1_volume"] * (1 + h2_ratio)
        for i, year in enumerate(years):
            full = base_full if i == 0 else volumes_full[-1] * (1 + growth[i - 1] / 100)
            volumes_full = (volumes_full if i else []) + [full]
            price = price_h1 * (1 + price_growth[0] / 100) if i == 0 else \
                prices[-1] * (1 + price_growth[i] / 100)
            prices.append(price)
            if i == 0:
                h2_volume = _segment_volume(seg, year, base_full) - seg["h1_volume"]
                volumes.append({"h2": max(h2_volume, 0.0),
                                "year": seg["h1_volume"] + max(h2_volume, 0.0)})
            else:
                volumes.append({"year": _segment_volume(seg, year, full)})
        seg_rows.append({"seg": seg, "price_h1": price_h1, "prices": prices,
                         "volumes": volumes, "volumes_full": volumes_full})
    if errors:
        return {"status": "invalid", "errors": errors}

    def segment_revenue(i, part="year"):
        out = {}
        for s in seg_rows:
            if i == 0 and part == "h2":
                out[s["seg"]["id"]] = s["volumes"][0]["h2"] * s["prices"][0]
            elif i == 0:
                out[s["seg"]["id"]] = s["seg"]["h1_revenue"] + s["volumes"][0]["h2"] * s["prices"][0]
            else:
                out[s["seg"]["id"]] = s["volumes"][i]["year"] * s["prices"][i]
        return out

    def total_volume(i, part="year"):
        if i == 0 and part == "h2":
            return sum(s["volumes"][0]["h2"] for s in seg_rows)
        return sum(s["volumes"][i]["year"] for s in seg_rows)

    h1_volume = sum(s["seg"]["h1_volume"] for s in seg_rows)

    # --- costs
    var_costs = []
    for item in drivers.get("variable_costs") or []:
        growth = _path(item["unit_cost_growth_pct"], HORIZON,
                       f"variable cost {item['id']!r} unit_cost_growth_pct", errors)
        unit = item["h1_amount"] / h1_volume
        units = []
        for i in range(HORIZON):
            unit = unit * (1 + growth[i] / 100)
            units.append(unit)
        var_costs.append({"item": item, "units": units})
    fixed = []
    for item in drivers["fixed_costs"]:
        h2_ratio = _scalar(item["h2_to_h1"], f"fixed cost {item['id']!r} h2_to_h1", errors)
        growth = _path(item["growth_pct"], n_out, f"fixed cost {item['id']!r} growth_pct", errors)
        amounts = [item["h1_amount"] * (1 + h2_ratio)]
        for g in growth:
            amounts.append(amounts[-1] * (1 + g / 100))
        fixed.append({"item": item, "h2": item["h1_amount"] * h2_ratio, "amounts": amounts})
    dep = drivers["depreciation"]
    dep_rate = _scalar(dep["rate_on_opening_net_ppe"], "depreciation rate", errors)
    h2_dep_ratio = _scalar(dep["h2_to_h1"], "depreciation h2_to_h1", errors)
    capex_d = drivers["capex"]
    capex_out = _path(capex_d["sustaining_outyears"], n_out, "capex sustaining_outyears", errors)
    committed_out = capex_d.get("committed_outyears")
    committed_out = (_path(committed_out, n_out, "capex committed_outyears", errors)
                     if committed_out else [0.0] * n_out)
    wc = drivers["working_capital"]
    recv_days = _scalar(wc["receivable_days_on_revenue"], "receivable days", errors)
    inv_days = _scalar(wc["inventory_days_on_variable_cost"], "inventory days", errors)
    pay_days = _scalar(wc["payable_days_on_variable_cost"], "payable days", errors)
    tax_d = drivers["tax"]
    tax_rate = _scalar(tax_d["rate"], "tax rate", errors)
    final_tax = _scalar(tax_d["interest_income_final_tax"], "interest income final tax", errors)
    liq_yield = _scalar(drivers["liquidity"]["yield"], "liquidity yield", errors)
    dist = drivers["distribution"]
    payout = _scalar(dist["payout_of_prior_year_profit"], "payout", errors)
    minority = (_scalar(dist["minority_share"], "minority share", errors)
                if dist.get("minority_share") else 0.0)
    if errors:
        return {"status": "invalid", "errors": errors}
    debt = [d for d in drivers["debt"] if isinstance(d, dict)]

    def interest_expense(year, months=12):
        total = 0.0
        for d in debt:
            maturity = _day(d.get("maturity"))
            if maturity and maturity.year < year:
                continue
            total += d["principal"] * d["coupon"] * months / 12.0 + d.get("other_annual", 0.0) * months / 12.0
        return total

    # --- roll the years
    rows = []
    ppe, liquidity = op["h1_close"]["ppe"], op["h1_close"]["liquidity"]
    equity = op["h1_close"]["equity"]
    nwc_fy0 = op["fy0_close"]["receivables"] + op["fy0_close"]["inventories"] - \
        op["fy0_close"]["payables"]
    prior_profit = op["fy0_profit"]
    other_assets = op["h1_close"]["other_assets"]
    other_liabs = op["h1_close"]["other_liabilities"]
    debt_book = op["h1_close"]["debt"]
    opening_nwc = nwc_fy0
    for i, year in enumerate(years):
        rev_by_seg = segment_revenue(i)
        revenue = sum(rev_by_seg.values())
        if i == 0:
            h2_rev = sum(segment_revenue(0, "h2").values())
            h2_var = sum(v["units"][0] * total_volume(0, "h2") for v in var_costs)
            h2_fixed = sum(f["h2"] for f in fixed)
            h2_ebitda = h2_rev - h2_var - h2_fixed
            h2_da = h1["depreciation"] * h2_dep_ratio
            var_total = h1["variable_costs"] + h2_var
            fixed_total = h1["fixed_costs"] + h2_fixed
            ebitda = revenue - var_total - fixed_total
            da = h1["depreciation"] + h2_da
            h2_interest = interest_expense(year, 6)
            h2_income = liquidity * liq_yield / 2
            h2_ebt = h2_ebitda - h2_da - h2_interest + h2_income
            h2_tax = tax_rate * (h2_ebt - h2_income) + final_tax * h2_income
            interest_exp = h1["interest_expense"] + h2_interest
            interest_inc = h1["interest_income"] + h2_income
            tax = h1["tax"] + h2_tax
            net = h1["net_profit"] + h2_ebt - h2_tax
            capex = h1["capex"] + sum(item["amount"] for item in capex_d["h2_items"])
            h2_capex = capex - h1["capex"]
            dividends = h1["dividends"] + max(payout * prior_profit - h1["dividends"], 0.0)
            h2_dividends = dividends - h1["dividends"]
            # H2 cash: from the official 30 June balances.
            receivables = recv_days / DAYS * revenue
            inventories = inv_days / DAYS * var_total
            payables = pay_days / DAYS * var_total
            nwc_close = receivables + inventories - payables
            h1_nwc = op["h1_close"]["receivables"] + op["h1_close"]["inventories"] - \
                op["h1_close"]["payables"]
            h2_dnwc = nwc_close - h1_nwc
            h2_net = h2_ebt - h2_tax
            liquidity_close = liquidity + h2_net + h2_da - h2_dnwc - h2_capex - h2_dividends
            ppe_close = ppe + h2_capex - h2_da
            equity_close = equity + h2_net - h2_dividends
            h2 = {"revenue": h2_rev, "ebitda": h2_ebitda, "da": h2_da, "capex": h2_capex,
                  "dnwc": h2_dnwc, "net": h2_net,
                  "fcff": (h2_ebitda - h2_da) * (1 - tax_rate) + h2_da - h2_capex - h2_dnwc}
        else:
            var_total = sum(v["units"][i] * total_volume(i) for v in var_costs)
            fixed_total = sum(f["amounts"][i] for f in fixed)
            ebitda = revenue - var_total - fixed_total
            da = dep_rate * ppe
            interest_exp = interest_expense(year)
            interest_inc = liquidity * liq_yield
            ebt = ebitda - da - interest_exp + interest_inc
            tax = tax_rate * (ebt - interest_inc) + final_tax * interest_inc
            net = ebt - tax
            capex = capex_out[i - 1] + committed_out[i - 1]
            dividends = payout * prior_profit
            receivables = recv_days / DAYS * revenue
            inventories = inv_days / DAYS * var_total
            payables = pay_days / DAYS * var_total
            nwc_close = receivables + inventories - payables
            liquidity_close = liquidity + net + da - (nwc_close - opening_nwc) - capex - dividends
            ppe_close = ppe + capex - da
            equity_close = equity + net - dividends
        dnwc = nwc_close - opening_nwc
        ebit = ebitda - da
        nopat = ebit * (1 - tax_rate)
        fcff = nopat + da - capex - dnwc
        assets = liquidity_close + receivables + inventories + ppe_close + other_assets
        liabilities = payables + debt_book + other_liabs
        rows.append({
            "year": year, "label": f"FY{year % 100:02d}F", "revenue": revenue,
            "segment_revenue": rev_by_seg,
            "segment_volume": {s["seg"]["id"]: s["volumes"][i]["year"] for s in seg_rows},
            "variable_costs": var_total, "fixed_costs": fixed_total, "ebitda": ebitda,
            "da": da, "ebit": ebit, "interest_expense": interest_exp,
            "interest_income": interest_inc, "tax": tax, "net": net,
            "net_attr": net * (1 - minority), "capex": capex, "dnwc": dnwc,
            "nopat": nopat, "fcff": fcff, "dividends": dividends,
            "receivables": receivables, "inventories": inventories, "payables": payables,
            "liquidity": liquidity_close, "ppe": ppe_close, "equity": equity_close,
            "debt": debt_book, "assets": assets, "liabilities": liabilities,
            "balance_gap": assets - liabilities - equity_close,
        })
        if i == 0:
            rows[0]["h2"] = h2
        opening_nwc, ppe, liquidity, equity = nwc_close, ppe_close, liquidity_close, equity_close
        prior_profit = net

    # --- terminal line: the last year without contracts that end before the
    # first terminal year closes.
    last = rows[-1]
    first_terminal = years[-1] + 1
    ended = [s for s in seg_rows if _day(s["seg"].get("contract_end")) and
             _day(s["seg"]["contract_end"]) <= date(first_terminal, 12, 31)]
    lost_revenue = sum(last["segment_revenue"][s["seg"]["id"]] for s in ended)
    lost_volume = sum(last["segment_volume"][s["seg"]["id"]] for s in ended)
    lost_var = sum(v["units"][-1] * lost_volume for v in var_costs)
    t_ebitda = last["ebitda"] - lost_revenue + lost_var
    t_ebit = t_ebitda - last["da"]
    terminal = {"year": years[-1], "excluded_segments": [s["seg"]["id"] for s in ended],
                "revenue": last["revenue"] - lost_revenue, "ebitda": t_ebitda, "da": last["da"],
                "ebit": t_ebit, "nopat": t_ebit * (1 - tax_rate), "capex": last["capex"],
                "dnwc": last["dnwc"],
                "fcff": t_ebit * (1 - tax_rate) + last["da"] - last["capex"] - last["dnwc"]}

    checks = _checks(rows, drivers, h1)
    return {"status": "projected", "currency": drivers.get("currency"), "rows": rows,
            "terminal": terminal, "checks": checks, "tax_rate": tax_rate,
            "invested_capital_opening": op["h1_close"]["ppe"] + (
                op["h1_close"]["receivables"] + op["h1_close"]["inventories"]
                - op["h1_close"]["payables"]),
            "drivers": _driver_summary(drivers)}


def _checks(rows, drivers, h1):
    out = []
    seg_sum = sum(s["h1_revenue"] for s in drivers["segments"])
    out.append({"name": "h1_segment_revenue_equals_reported",
                "ok": abs(seg_sum - h1["revenue"]) <= TOLERANCE,
                "value": seg_sum, "bound": h1["revenue"]})
    h1_ebitda = h1["revenue"] - h1["variable_costs"] - h1["fixed_costs"]
    out.append({"name": "h1_ebitda_components", "ok": abs(h1_ebitda - h1["ebitda"]) <= TOLERANCE,
                "value": h1_ebitda, "bound": h1["ebitda"]})
    for r in rows:
        identity = r["nopat"] + r["da"] - r["capex"] - r["dnwc"]
        out.append({"name": f"fcff_identity_{r['year']}", "ok": abs(identity - r["fcff"]) <= TOLERANCE,
                    "value": r["fcff"], "bound": identity})
        out.append({"name": f"balance_{r['year']}", "ok": abs(r["balance_gap"]) <= TOLERANCE,
                    "value": r["balance_gap"], "bound": 0.0})
    return out


def _driver_summary(drivers):
    """Every forward driver with its kind and rationale, for the Audit Trace and report."""
    out = []
    for seg in drivers["segments"]:
        for key in ("h2_volume_to_h1", "volume_growth_pct", "price_growth_pct"):
            record = seg[key]
            out.append({"driver": f"{seg['name']}: {key}", "values": record["values"],
                        "kind": record["kind"], "rationale": record["rationale"]})
    for item in drivers.get("variable_costs") or []:
        record = item["unit_cost_growth_pct"]
        out.append({"driver": f"{item['name']}: unit_cost_growth_pct", "values": record["values"],
                    "kind": record["kind"], "rationale": record["rationale"]})
    for item in drivers["fixed_costs"]:
        record = item["growth_pct"]
        out.append({"driver": f"{item['name']}: growth_pct", "values": record["values"],
                    "kind": record["kind"], "rationale": record["rationale"]})
    for key, record in (("capex sustaining_outyears", drivers["capex"]["sustaining_outyears"]),
                        ("depreciation rate", drivers["depreciation"]["rate_on_opening_net_ppe"]),
                        ("tax rate", drivers["tax"]["rate"]),
                        ("liquidity yield", drivers["liquidity"]["yield"]),
                        ("payout", drivers["distribution"]["payout_of_prior_year_profit"])):
        out.append({"driver": key, "values": record["values"], "kind": record["kind"],
                    "rationale": record["rationale"]})
    return out


def ok(model) -> bool:
    return isinstance(model, dict) and model.get("status") == "projected" and \
        all(c["ok"] for c in model.get("checks") or [])
