"""Sourced bank driver file: official balances, 1H lines, capital requirement, drivers.

``data/bank_drivers/<TICKER>.json`` turns the Bank Driver Scenario's
screening shortcuts into sourced inputs for ``app.bank_model.project``
(plan §5.2):

- ``fy0_close`` and ``h1_close``: the last fiscal year-end and 30 June
  balances from the interim statements, in the model's field names (gross
  loans, allowance, earning assets, deposits by type, other interest-bearing
  and non-interest-bearing liabilities, equity and minorities, total capital
  and RWA), one definition for both dates;
- ``h1``: the official first-half income lines (NII, other income, operating
  expense, provisions, pre-tax profit, tax, profit and parent profit), so no
  cost split is inferred;
- ``capital_requirement``: the regulatory minimum CAR the issuer discloses
  (risk-profile minimum plus buffers), which the projection holds;
- ``cost_of_funds`` and ``payout_path`` (payout on each forecast year's
  profit), and five yearly ``drivers`` (loan growth, NIM, non-interest income
  / NII, cost-to-income, cost of credit, optional deposit growth).

Every value cites ``source_refs``; each forward driver carries ``kind``
(``company_guidance``, ``sourced`` or ``analyst_assumption``) and a rationale.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "bank_drivers"
BALANCE_KEYS = ("gross_loan", "allowance_for_loans", "non_loan_earning_assets", "total_assets",
                "total_deposit", "current_account", "savings_account", "time_deposit",
                "other_interest_bearing_liabilities", "non_interest_bearing_liabilities",
                "parent_equity", "non_controlling_interest", "total_equity",
                "total_capital", "total_risk_weighted_asset")
H1_KEYS = ("net_interest_income", "other_income", "operating_expense", "provision",
           "earnings_before_tax", "tax", "net_profit", "net_profit_attributable")
DRIVER_KEYS = ("loan_growth_pct", "nim_pct", "non_ii_to_nii_pct", "cost_to_income_pct",
               "cost_of_credit_pct")
KINDS = ("company_guidance", "sourced", "analyst_assumption")
TOLERANCE = 1.0


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def load(ticker, as_of, root=ROOT):
    path = Path(root) / f"{str(ticker).upper()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    cutoff = _day(as_of)
    dates = [_day(s.get("published_at")) for s in (data.get("sources") or {}).values()]
    if cutoff is None or any(d is None or d > cutoff for d in dates):
        return None
    return data


def validate(data) -> list[str]:
    errors = []
    if not isinstance(data, dict):
        return ["bank driver file is invalid"]
    sources = data.get("sources") or {}
    for key, s in sources.items():
        if not (isinstance(s, dict) and str(s.get("url") or "").startswith("https://")
                and s.get("title") and _day(s.get("published_at"))):
            errors.append(f"source {key!r} needs title, https url and published_at")

    def cited(record, label):
        refs = (record or {}).get("source_refs")
        if not refs or any(r not in sources for r in refs):
            errors.append(f"{label} must cite sources from the driver file")

    for block, keys in (("fy0_close", BALANCE_KEYS), ("h1_close", BALANCE_KEYS), ("h1", H1_KEYS)):
        record = data.get(block)
        if not isinstance(record, dict):
            errors.append(f"bank driver file is missing {block}")
            continue
        cited(record, block)
        missing = [k for k in keys if _num(record.get(k)) is None]
        if missing:
            errors.append(f"{block} is missing " + ", ".join(missing))
    for block in ("fy0_close", "h1_close"):
        b = data.get(block) or {}
        if all(_num(b.get(k)) is not None for k in BALANCE_KEYS):
            liabilities = (b["total_deposit"] + b["other_interest_bearing_liabilities"]
                           + b["non_interest_bearing_liabilities"])
            if abs(b["total_assets"] - liabilities - b["total_equity"]) > TOLERANCE:
                errors.append(f"{block}: total assets do not equal liabilities + equity")
            if abs(b["parent_equity"] + b["non_controlling_interest"] - b["total_equity"]) > TOLERANCE:
                errors.append(f"{block}: parent equity + minorities do not equal total equity")
            if abs(b["current_account"] + b["savings_account"] + b["time_deposit"]
                   - b["total_deposit"]) > TOLERANCE:
                errors.append(f"{block}: deposit types do not add up to total deposits")
    h1 = data.get("h1") or {}
    if all(_num(h1.get(k)) is not None for k in H1_KEYS):
        ebt = h1["net_interest_income"] + h1["other_income"] - h1["operating_expense"] - h1["provision"]
        if abs(ebt - h1["earnings_before_tax"]) > TOLERANCE:
            errors.append("h1: NII + other income - operating expense - provisions != pre-tax profit")
        if abs(h1["earnings_before_tax"] - h1["tax"] - h1["net_profit"]) > TOLERANCE:
            errors.append("h1: pre-tax profit - tax != profit")
    req = data.get("capital_requirement") or {}
    if _num(req.get("value")) is None or not 0 < req["value"] < 1:
        errors.append("capital_requirement.value must be a fraction")
    cited(req, "capital_requirement")
    for key in ("cost_of_funds",):
        record = data.get(key) or {}
        if _num(record.get("value")) is None:
            errors.append(f"{key}.value is required")
        cited(record, key)
    drivers = data.get("drivers") or []
    if len(drivers) != 5:
        errors.append("five yearly driver rows are required")
    for row in drivers:
        for key in DRIVER_KEYS:
            cell = row.get(key)
            if not isinstance(cell, dict) or _num(cell.get("value")) is None:
                errors.append(f"driver {row.get('year')} {key} needs a value")
                continue
            if cell.get("kind") not in KINDS:
                errors.append(f"driver {row.get('year')} {key} kind must be one of {KINDS}")
            if not str(cell.get("rationale") or "").strip():
                errors.append(f"driver {row.get('year')} {key} needs a rationale")
            if cell.get("kind") in ("company_guidance", "sourced"):
                cited(cell, f"driver {row.get('year')} {key}")
    payout = data.get("payout_path") or {}
    if not isinstance(payout.get("values"), list) or len(payout["values"]) != 5 or \
            any(_num(v) is None or not 0 <= v <= 1 for v in payout["values"]):
        errors.append("payout_path needs five fractions (payout on each forecast year's profit)")
    if not str(payout.get("rationale") or "").strip():
        errors.append("payout_path needs a rationale")
    return errors


def model_drivers(data):
    """Driver rows in the shape ``bank_model.project`` reads (percent values)."""
    out = []
    for row in data["drivers"]:
        item = {"year": int(row["year"])}
        for key in DRIVER_KEYS:
            item[key] = float(row[key]["value"])
        if isinstance(row.get("deposit_growth_pct"), dict):
            item["deposit_growth_pct"] = float(row["deposit_growth_pct"]["value"])
        item["rationale"] = "; ".join(f"{k}: {row[k]['rationale']}" for k in DRIVER_KEYS)
        out.append(item)
    return out


def summary(data):
    """Each forward driver with its kind and rationale, for the report and trace."""
    return [{"year": row["year"], "driver": key, "value": row[key]["value"],
             "kind": row[key]["kind"], "rationale": row[key]["rationale"]}
            for row in data["drivers"] for key in DRIVER_KEYS]
