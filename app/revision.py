"""Version comparison: what changed between two Company Updates and how it moved value (plan §8).

``compare(previous, current)`` lists the changed facts, methods, market inputs
and status of two stored reports. When both carry ``model_inputs`` of the same
kind (a Production-Ready operating, bank or mining model), the change in value
per share is decomposed exactly by sequential substitution through the
profile's independent reference calculation: starting from the previous
version, each input group is replaced by the current version's in a fixed
order, and each step's change is attributed to that group:

- operating: discount rate and terminal (WACC, g, RONIC) -> balance-sheet
  bridge (cash, debt, minorities, distributions) -> share count -> spot rate ->
  official actuals and opening balances -> forward driver assumptions;
- bank: Cost of Equity and g -> share count -> spot rate -> official actuals,
  balances and capital requirement -> forward drivers and payout policy;
- mining: discount rate -> bridge and share count -> spot rate -> price deck ->
  physical and cost inputs.

The steps sum to the total change by construction; the order is stated
because substitution effects depend on it. Without comparable model inputs
the change is listed but not decomposed.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from . import outputs, reference_ddm, reference_fcff, reference_lom

_OPERATING_ACTUALS = ("anchor", "opening", "segments_h1")
_META_KEYS = ("status", "rating", "tp", "upside_persen", "model_profile")


def _operating_value(drivers, val):
    return reference_fcff.value(drivers, **val)["per_share"]


def _bank_value(drivers, val):
    return reference_ddm.value(drivers, **val)["per_share"]


def _lom_inputs(inp):
    out = dict(inp)
    out["elang_capex"] = {int(k): v for k, v in (inp.get("elang_capex") or {}).items()}
    return out


def _lom_value(inp, bridge, fx):
    return reference_lom.value(_lom_inputs(inp), bridge, fx)["per_share"]


def _steps_operating(a, b):
    va, vb = dict(a["valuation"]), dict(b["valuation"])
    da, db = copy.deepcopy(a["drivers"]), copy.deepcopy(b["drivers"])
    groups = [("Tingkat diskonto dan terminal", ("wacc", "g", "terminal_ronic", "valuation_date")),
              ("Jembatan neraca", ("cash", "debt", "nci", "distributions", "parent_share")),
              ("Jumlah saham", ("shares",)), ("Kurs", ("to_idr",))]
    steps, val, drivers = [], dict(va), da
    current = _operating_value(drivers, val)
    start = current
    for label, keys in groups:
        for k in keys:
            val[k] = vb[k]
        value = _operating_value(drivers, val)
        steps.append((label, value - current))
        current = value
    # Official actuals and opening balances (the 1H lines, segment 1H volumes and revenue).
    drivers = copy.deepcopy(drivers)
    drivers["anchor"], drivers["opening"] = copy.deepcopy(db["anchor"]), copy.deepcopy(db["opening"])
    for seg_a, seg_b in zip(drivers["segments"], db["segments"]):
        for k in ("h1_volume", "h1_revenue"):
            seg_a[k] = seg_b[k]
    for item_a, item_b in zip(drivers.get("variable_costs") or [], db.get("variable_costs") or []):
        item_a["h1_amount"] = item_b["h1_amount"]
    for item_a, item_b in zip(drivers["fixed_costs"], db["fixed_costs"]):
        item_a["h1_amount"] = item_b["h1_amount"]
    value = _operating_value(drivers, val)
    steps.append(("Aktual resmi dan saldo awal", value - current))
    current = value
    value = _operating_value(db, val)
    steps.append(("Asumsi driver ke depan", value - current))
    return start, value, steps


def _steps_bank(a, b):
    va, vb = dict(a["valuation"]), dict(b["valuation"])
    da, db = copy.deepcopy(a["drivers"]), copy.deepcopy(b["drivers"])
    steps, val, drivers = [], dict(va), da
    current = start = _bank_value(drivers, val)
    for label, keys in (("Cost of Equity dan g", ("coe", "g", "valuation_date")),
                        ("Jumlah saham", ("shares",)), ("Kurs", ("to_idr",)),
                        ("Laba tahun dasar dan payout terumumkan", ("prior_profit", "first_payout"))):
        for k in keys:
            val[k] = vb[k]
        value = _bank_value(drivers, val)
        steps.append((label, value - current))
        current = value
    drivers = copy.deepcopy(drivers)
    for k in ("h1", "h1_close", "fy0_close", "capital_requirement", "cost_of_funds"):
        drivers[k] = copy.deepcopy(db[k])
    value = _bank_value(drivers, val)
    steps.append(("Aktual resmi, neraca dan persyaratan modal", value - current))
    current = value
    value = _bank_value(db, val)
    steps.append(("Driver ke depan dan kebijakan payout", value - current))
    return start, value, steps


def _steps_mining(a, b):
    ia, ib = _lom_inputs(a["inputs"]), _lom_inputs(b["inputs"])
    inp, bridge, fx = dict(ia), dict(a["bridge"]), a["fx"]
    current = start = reference_lom.value(inp, bridge, fx)["per_share"]
    steps = []
    for label, change in (
            ("Tingkat diskonto", lambda: inp.update(discount=ib["discount"])),
            ("Jembatan korporat dan jumlah saham", lambda: bridge.update(b["bridge"])),
            ("Kurs", None),
            ("Dek harga", lambda: inp.update(cu_price=ib["cu_price"], au_price=ib["au_price"]))):
        if change:
            change()
        else:
            fx = b["fx"]
        value = reference_lom.value(inp, bridge, fx)["per_share"]
        steps.append((label, value - current))
        current = value
    value = reference_lom.value(ib, bridge, fx)["per_share"]
    steps.append(("Input fisik, biaya dan asumsi LoM", value - current))
    return start, value, steps


def decompose(previous, current):
    a, b = previous.get("model_inputs"), current.get("model_inputs")
    if not a or not b or a.get("kind") != b.get("kind"):
        return {"status": "not_decomposed",
                "reason": "kedua versi tidak memuat input model referensi yang sebanding"}
    start, end, steps = {"operating": _steps_operating, "bank": _steps_bank,
                         "mining": _steps_mining}[a["kind"]](a, b)
    return {"status": "decomposed", "kind": a["kind"], "start": start, "end": end,
            "steps": [{"group": g, "change": c} for g, c in steps],
            "residual": end - start - sum(c for _, c in steps),
            "order": "berurutan sesuai daftar; efek substitusi bergantung pada urutan"}


def compare(previous, current):
    pm, cm = previous.get("meta") or {}, current.get("meta") or {}
    changes = [{"field": k, "previous": pm.get(k), "current": cm.get(k)}
               for k in _META_KEYS if pm.get(k) != cm.get(k)]
    for k, label in (("method", "method"),):
        if previous.get(k) != current.get(k):
            changes.append({"field": label, "previous": previous.get(k), "current": current.get(k)})
    pman, cman = previous.get("run_manifest") or {}, current.get("run_manifest") or {}
    for k in ("as_of", "code_revision"):
        if pman.get(k) != cman.get(k):
            changes.append({"field": k, "previous": pman.get(k), "current": cman.get(k)})
    return {"changes": changes, "value_bridge": decompose(previous, current)}


def compare_folders(previous_folder, current_folder, db=None):
    out = []
    current = set(outputs.tickers(outputs.REPORT, current_folder, db))
    for ticker in sorted(current & set(outputs.tickers(outputs.REPORT, previous_folder, db))):
        a = outputs.load(outputs.REPORT, previous_folder, ticker, db) or {}
        b = outputs.load(outputs.REPORT, current_folder, ticker, db) or {}
        out.append({"ticker": ticker, **compare(a, b)})
    return out


def markdown(rows, previous_folder, current_folder):
    lines = [f"# Revisi: {previous_folder} -> {current_folder}", ""]
    for r in rows:
        lines.append(f"## {r['ticker']}")
        for c in r["changes"]:
            lines.append(f"- {c['field']}: {c['previous']} -> {c['current']}")
        bridge = r["value_bridge"]
        if bridge["status"] == "decomposed":
            rp = lambda v: f"{v:,.0f}".replace(",", ".")  # noqa: E731
            lines.append(f"- Jembatan nilai per saham ({bridge['kind']}): Rp{rp(bridge['start'])} -> "
                         f"Rp{rp(bridge['end'])}")
            for s in bridge["steps"]:
                sign = "+" if s["change"] >= 0 else "-"
                lines.append(f"  - {s['group']}: {sign}Rp{rp(abs(s['change']))}")
        else:
            lines.append(f"- Jembatan nilai: {bridge['reason']}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--markdown")
    args = parser.parse_args(argv)
    rows = compare_folders(args.previous, args.current)
    text = markdown(rows, args.previous, args.current)
    if args.markdown:
        Path(args.markdown).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
