"""Driver-to-value table and base/downside/upside cases from the same model (plan §6).

For a Production-Ready model (operating model, sourced bank model or LoM) each
material driver is moved over a stated range, one at a time, and revalued by
that profile's independent reference calculation (``app.reference_fcff``,
``app.reference_ddm``, ``app.reference_lom``) with the valuation's own rates,
bridge and share count. The downside and upside cases move every driver to its
adverse or favourable end together. The ranges are sensitivity steps, not
probabilities: no case is weighted or called likely.

Each row states the driver's basis (company guidance, sourced ratio or
analyst assumption), its source keys, the forecast years it covers, the
tested range and the change in first-forecast-year parent profit (when the
model reports it) and in value per share.
"""
from __future__ import annotations

import copy

from . import fmt, operating_model, reference_ddm, reference_fcff, reference_holding, reference_lom

KIND_LABEL = {"sourced": "bersumber", "company_guidance": "panduan emiten",
              "analyst_assumption": "asumsi analis"}


def _figure(value) -> str:
    """A driver figure as written (8.5 -> "8,5", 5.0 -> "5"), in the report's
    Indonesian form; the English edition localizes it."""
    dec = next(d for d in (0, 1, 2, 3) if round(value, d) == round(value, 3))
    return fmt.num(value, dec)


def _path(values) -> str:
    """A driver's yearly values, "8,5/8,5/8/8%"."""
    return "/".join(_figure(v) for v in values) + "%"


def _row(name, basis, refs, years, base, low, high, v_low, v_high, v_base,
         p_low=None, p_high=None, p_base=None, unit=""):
    return {"driver": name, "basis": basis, "source_refs": refs or [], "years": years,
            "base": base, "low": low, "high": high, "unit": unit,
            "value_low": v_low, "value_high": v_high, "value_base": v_base,
            "value_effect_low": v_low - v_base, "value_effect_high": v_high - v_base,
            "fy1_profit_low": None if p_low is None else p_low - p_base,
            "fy1_profit_high": None if p_high is None else p_high - p_base}


# ------------------------------------------------------------ going concern

def _shift(record, step, first_only=False):
    out = copy.deepcopy(record)
    values = out["values"]
    if first_only:
        values[0] = values[0] + step
    else:
        out["values"] = [v + step for v in values]
    return out


def _operating_cases(drivers):
    """(name, basis, refs, years, base text, adverse drivers, favourable drivers, unit)."""
    cases = []
    first = int(drivers["anchor"]["year"])
    span = f"FY{(first + 1) % 100:02d}F-FY{(first + 4) % 100:02d}F"
    for i, seg in enumerate(drivers["segments"]):
        rec = seg["volume_growth_pct"]
        down, up = copy.deepcopy(drivers), copy.deepcopy(drivers)
        down["segments"][i]["volume_growth_pct"] = _shift(rec, -1.0)
        up["segments"][i]["volume_growth_pct"] = _shift(rec, 1.0)
        cases.append((f"{seg['name']}: pertumbuhan volume", rec["kind"],
                      rec.get("basis_refs") or rec.get("source_refs"), span,
                      _path(rec["values"]), down, up, "±1 pp per tahun",
                      ("turun", "naik")))
        rec = seg["price_growth_pct"]
        down, up = copy.deepcopy(drivers), copy.deepcopy(drivers)
        down["segments"][i]["price_growth_pct"] = _shift(rec, -2.0, first_only=True)
        up["segments"][i]["price_growth_pct"] = _shift(rec, 2.0, first_only=True)
        cases.append((f"{seg['name']}: harga terealisasi", rec["kind"],
                      rec.get("basis_refs") or rec.get("source_refs"), f"FY{first % 100:02d}F dst.",
                      "level 1H", down, up, "±2% level harga", ("turun", "naik")))
    for i, item in enumerate(drivers.get("variable_costs") or []):
        rec = item["unit_cost_growth_pct"]
        down, up = copy.deepcopy(drivers), copy.deepcopy(drivers)
        down["variable_costs"][i]["unit_cost_growth_pct"] = _shift(rec, 2.0, first_only=True)
        up["variable_costs"][i]["unit_cost_growth_pct"] = _shift(rec, -2.0, first_only=True)
        _pass_through(drivers, item, down, 2.0)
        _pass_through(drivers, item, up, -2.0)
        linked = any(link.get("cost") == item["id"] for link in drivers.get("pass_through") or [])
        cases.append((f"{item['name']}: biaya per unit", rec["kind"],
                      rec.get("basis_refs") or rec.get("source_refs"), f"FY{first % 100:02d}F dst.",
                      "level 1H", down, up,
                      "±2% level biaya" + (", diteruskan ke tarif" if linked else ""), ("naik", "turun")))
    rec = drivers["capex"]["sustaining_outyears"]
    down, up = copy.deepcopy(drivers), copy.deepcopy(drivers)
    down["capex"]["sustaining_outyears"]["values"] = [v * 1.1 for v in rec["values"]]
    up["capex"]["sustaining_outyears"]["values"] = [v * 0.9 for v in rec["values"]]
    cases.append(("Capex pemeliharaan", rec["kind"], rec.get("basis_refs") or rec.get("source_refs"),
                  span, "dasar", down, up, "±10%", ("naik", "turun")))
    return cases


def _pass_through(drivers, item, moved, pct):
    """A cost change the tariff formula passes on moves the linked segments' price.

    The price level moves by the cost change per unit over the segment's
    realized price (times the pass-through share), so a fuel shock is not
    counted without the tariff change that offsets it.
    """
    h1_units = sum(s["h1_volume"] for s in drivers["segments"])
    unit_cost = item["h1_amount"] / h1_units
    for link in drivers.get("pass_through") or []:
        if link.get("cost") != item["id"]:
            continue
        for j, seg in enumerate(drivers["segments"]):
            if seg["id"] not in link.get("segments", []):
                continue
            price = seg["h1_revenue"] / seg["h1_volume"]
            step = pct * unit_cost / price * link.get("share", 1.0)
            moved["segments"][j]["price_growth_pct"] = _shift(
                moved["segments"][j]["price_growth_pct"], step, first_only=True)


def operating(drivers, detail):
    """Driver table and cases for a going-concern operating model."""
    view = detail.get("native") or detail
    kw = dict(wacc=detail["wacc"], g=detail["g"], valuation_date=detail["valuation_date"],
              cash=view["cash"], debt=view["debt"], nci=view.get("nci"),
              distributions=view.get("distributions") or 0.0, shares=detail["shares"],
              to_idr=detail.get("fx") or 1.0, parent_share=detail.get("attributable_share") or 1.0,
              terminal_ronic=detail.get("terminal_ronic"))
    fx = detail.get("fx") or 1.0
    value = lambda d: reference_fcff.value(d, **kw)["per_share"]  # noqa: E731
    profit = lambda d: operating_model.project(d)["rows"][0]["net_attr"] * fx  # noqa: E731
    base_v, base_p = value(drivers), profit(drivers)
    rows, adverse, favourable = [], copy.deepcopy(drivers), copy.deepcopy(drivers)
    for name, kind, refs, years, base, down, up, unit, words in _operating_cases(drivers):
        rows.append(_row(name, KIND_LABEL.get(kind, kind), refs, years, base, words[0], words[1],
                         value(down), value(up), base_v, profit(down), profit(up), base_p, unit))
    # Combined cases: every driver at its adverse / favourable end.
    for name, kind, refs, years, base, down, up, unit, words in _operating_cases(drivers):
        _merge(adverse, down, drivers)
        _merge(favourable, up, drivers)
    return _result(rows, base_v, value(adverse), value(favourable),
                   base_p, profit(adverse), profit(favourable))


def _merge(target, moved, base):
    """Copy into ``target`` every driver record ``moved`` changed relative to ``base``."""
    for i, seg in enumerate(moved["segments"]):
        for key in ("volume_growth_pct", "price_growth_pct"):
            if seg[key] != base["segments"][i][key]:
                # Additive, so a tariff case and a passed-through fuel case combine.
                target["segments"][i][key]["values"] = [
                    t + (m - b) for t, m, b in zip(target["segments"][i][key]["values"],
                                                   seg[key]["values"],
                                                   base["segments"][i][key]["values"])]
    for i, item in enumerate(moved.get("variable_costs") or []):
        if item["unit_cost_growth_pct"] != base["variable_costs"][i]["unit_cost_growth_pct"]:
            target["variable_costs"][i]["unit_cost_growth_pct"] = copy.deepcopy(item["unit_cost_growth_pct"])
    if moved["capex"]["sustaining_outyears"] != base["capex"]["sustaining_outyears"]:
        target["capex"]["sustaining_outyears"] = copy.deepcopy(moved["capex"]["sustaining_outyears"])


# ------------------------------------------------------------------- bank

_BANK_STEPS = (("loan_growth_pct", "Pertumbuhan kredit", 1.0, -1, "±1 pp"),
               ("nim_pct", "NIM", 0.10, -1, "±10 bp"),
               ("non_ii_to_nii_pct", "Pendapatan non-bunga / NII", 2.0, -1, "±2 pp"),
               ("cost_to_income_pct", "Rasio biaya / pendapatan", 1.0, 1, "±1 pp"),
               ("cost_of_credit_pct", "Biaya kredit", 0.20, 1, "±20 bp"))


def bank(data, detail, model):
    prior, first = model["prior_parent_profit"], model["first_payout"]
    kw = dict(prior_profit=prior, first_payout=first, coe=detail["coe"], g=detail["g"],
              valuation_date=detail["valuation_date"], shares=detail["shares"],
              to_idr=detail.get("fx") or 1.0)
    run = lambda d: reference_ddm.value(d, **kw)  # noqa: E731
    base = run(data)
    base_v, base_p = base["per_share"], base["rows"][0]["parent"]
    rows = []
    adverse, favourable = copy.deepcopy(data), copy.deepcopy(data)
    for key, name, step, bad_sign, unit in _BANK_STEPS:
        moved = {}
        for sign in (-1, 1):
            d = copy.deepcopy(data)
            for row in d["drivers"]:
                row[key]["value"] += sign * step
            moved[sign] = run(d)
        low, high = moved[bad_sign], moved[-bad_sign]  # low = adverse end
        kinds = {row[key]["kind"] for row in data["drivers"]}
        rows.append(_row(name, " / ".join(KIND_LABEL.get(k, k) for k in sorted(kinds)),
                         sorted({r for row in data["drivers"] for r in row[key].get("source_refs") or []}),
                         f"FY{data['drivers'][0]['year'] % 100:02d}F-FY{data['drivers'][-1]['year'] % 100:02d}F",
                         _path(row[key]["value"] for row in data["drivers"]),
                         "turun" if bad_sign < 0 else "naik", "naik" if bad_sign < 0 else "turun",
                         low["per_share"], high["per_share"], base_v,
                         low["rows"][0]["parent"], high["rows"][0]["parent"], base_p, unit))
        for row_a, row_f in zip(adverse["drivers"], favourable["drivers"]):
            row_a[key]["value"] += bad_sign * step
            row_f[key]["value"] -= bad_sign * step
    a, f = run(adverse), run(favourable)
    return _result(rows, base_v, a["per_share"], f["per_share"],
                   base_p, a["rows"][0]["parent"], f["rows"][0]["parent"])


# ----------------------------------------------------------------- mining

def mining(inp, bridge, fx):
    base_v = reference_lom.value(inp, bridge, fx)["per_share"]
    cu, au = inp["cu_price"], inp["au_price"]
    cases = [
        ("Harga tembaga", "asumsi analis (dek 12 bulan)", "LoM", f"US${fmt.num(cu, 0)}/t",
         dict(deck=(cu * 0.9, au)), dict(deck=(cu * 1.1, au)), "±10%", ("turun", "naik")),
        ("Harga emas", "asumsi analis (dek 12 bulan)", "LoM", f"US${fmt.num(au, 0)}/oz",
         dict(deck=(cu, au * 0.9)), dict(deck=(cu, au * 1.1)), "±10%", ("turun", "naik")),
        ("Tingkat diskonto US$", "kebijakan rumah", "LoM", fmt.pct(inp["discount"]),
         dict(rate=inp["discount"] + 0.01), dict(rate=inp["discount"] - 0.01), "±1 pp",
         ("naik", "turun")),
        ("Probabilitas pengembangan Elang", "asumsi analis", "LoM",
         f"{inp['elang_risk'] * 100:.0f}%", dict(risk=max(inp["elang_risk"] - 0.25, 0.0)),
         dict(risk=min(inp["elang_risk"] + 0.25, 1.0)), "±25 pp", ("turun", "naik")),
    ]
    util = inp["utilization"]
    cases.append(("Utilisasi smelter dan PMR 2027+", "laju Juni 2026 (emiten)", "2027+",
                  f"{util * 100:.0f}%", dict(_inp={"utilization": max(util - 0.05, 0.0)}),
                  dict(_inp={"utilization": min(util + 0.05, 1.0)}), "±5 pp", ("turun", "naik")))

    def run(moves):
        moves = dict(moves)
        return reference_lom.value({**inp, **moves.pop("_inp", {})}, bridge, fx,
                                   **moves)["per_share"]
    # Probabilities and utilization cannot pass 0-100%: the room to move, in
    # tested steps, for the thresholds read off this table.
    room = {"Probabilitas pengembangan Elang": (inp["elang_risk"] / 0.25,
                                                (1 - inp["elang_risk"]) / 0.25),
            "Utilisasi smelter dan PMR 2027+": (util / 0.05, (1 - util) / 0.05)}
    rows = []
    for name, basis, years, base, down, up, unit, words in cases:
        row = _row(name, basis, [], years, base, words[0], words[1],
                   run(down), run(up), base_v, unit=unit)
        if name in room:
            row["max_steps_low"], row["max_steps_high"] = room[name]
        rows.append(row)
    adverse = reference_lom.value(inp, bridge, fx, deck=(cu * 0.9, au * 0.9),
                                  rate=inp["discount"] + 0.01,
                                  risk=max(inp["elang_risk"] - 0.25, 0.0))["per_share"]
    favourable = reference_lom.value(inp, bridge, fx, deck=(cu * 1.1, au * 1.1),
                                     rate=inp["discount"] - 0.01,
                                     risk=min(inp["elang_risk"] + 0.25, 1.0))["per_share"]
    return _result(rows, base_v, adverse, favourable)


def holding(detail):
    """Holding SOTP: listed-stake prices and the landbank drivers, one at a time,
    revalued by ``app.reference_holding``."""
    listed = detail["components"]
    equity, shares, land = detail["parent_equity"], detail["shares"], detail.get("landbank")

    def value(listed_m=1.0, **land_moves):
        rows = [{**c, "market_cap": c["market_cap"] * listed_m} for c in listed]
        moved = None
        if land:
            inp = {**land["inputs"], **{k: v for k, v in land_moves.items() if k != "rate"}}
            moved = {**land, "inputs": inp, "rate": land_moves.get("rate", land["rate"])}
        return reference_holding.value(rows, equity, shares, moved)["per_share"]

    base_v = value()
    names = ", ".join(c["ticker"] for c in listed)
    cases = [(f"Harga saham anak usaha tercatat ({names})", "harga penutupan bertanggal",
              "tanggal laporan", "harga penutupan", dict(listed_m=0.9), dict(listed_m=1.1),
              "±10%", ("turun", "naik"))]
    if land:
        li = land["inputs"]
        cases += [
            ("Laju penjualan lahan", "rata-rata marketing sales historis", "sampai lahan habis",
             f"{fmt.num(li['pace_ha'])} ha/tahun",
             dict(pace_ha=max(li["pace_ha"] - 25, 1.0)), dict(pace_ha=li["pace_ha"] + 25),
             "±25 ha/tahun", ("turun", "naik")),
            ("Pertumbuhan harga lahan", "CAGR harga marketing historis", "sampai lahan habis",
             fmt.pct(li["asp_growth"]),
             dict(asp_growth=li["asp_growth"] - 0.01), dict(asp_growth=li["asp_growth"] + 0.01),
             "±1 pp", ("turun", "naik")),
            ("Porsi lahan dapat dijual", "asumsi analis", "sampai lahan habis",
             f"{li['net_ratio'] * 100:.0f}%", dict(net_ratio=li["net_ratio"] - 0.05),
             dict(net_ratio=li["net_ratio"] + 0.05), "±5 pp", ("turun", "naik")),
            ("Tingkat diskonto landbank", "Cost of Equity kebijakan", "sampai lahan habis",
             fmt.pct(land["rate"]), dict(rate=land["rate"] + 0.01),
             dict(rate=land["rate"] - 0.01), "±1 pp", ("naik", "turun"))]
    rows = [_row(name, basis, [], years, base, words[0], words[1], value(**down), value(**up),
                 base_v, unit=unit)
            for name, basis, years, base, down, up, unit, words in cases]
    if land:
        share = land["inputs"]["net_ratio"]
        for row in rows:
            if row["driver"] == "Porsi lahan dapat dijual":
                row["max_steps_low"], row["max_steps_high"] = share / 0.05, (1 - share) / 0.05
    adverse = {k: v for _, _, _, _, down, _, _, _ in cases for k, v in down.items()}
    favourable = {k: v for _, _, _, _, _, up, _, _ in cases for k, v in up.items()}
    return _result(rows, base_v, value(**adverse), value(**favourable))


def _result(rows, base_v, down_v, up_v, base_p=None, down_p=None, up_p=None):
    rows.sort(key=lambda r: -max(abs(r["value_effect_low"]), abs(r["value_effect_high"])))
    return {"rows": rows,
            "cases": {"downside": {"per_share": down_v, "fy1_profit": down_p},
                      "base": {"per_share": base_v, "fy1_profit": base_p},
                      "upside": {"per_share": up_v, "fy1_profit": up_p}},
            "method": "satu driver digeser per baris dan dinilai ulang dengan kalkulasi "
                      "referensi independen; kasus turun/naik menggeser semua driver bersamaan; "
                      "tanpa probabilitas"}


def _jsonable(value):
    import json
    return json.loads(json.dumps(value, default=str))


def model_inputs(intake, fc, va):
    """The inputs a reference calculation needs to rebuild this version's value.

    Stored on the report so two versions can be bridged exactly (plan §8):
    the driver file (or LoM input set) plus the valuation's rates, bridge,
    share count and spot rate. None when the model has no reference.
    """
    chain = (va or {}).get("method_chain") or {}
    selected = chain.get("selected")
    detail = next((t.get("detail") for t in chain.get("trace") or [] if t.get("key") == selected),
                  None) or {}
    if selected == "fcff_dcf" and detail.get("operating_model"):
        drivers = operating_model.load(intake.get("ticker"), intake.get("as_of"))
        view = detail.get("native") or detail
        if drivers:
            return _jsonable({"kind": "operating", "drivers": drivers, "valuation": {
                "wacc": detail["wacc"], "g": detail["g"], "valuation_date": detail["valuation_date"],
                "terminal_ronic": detail.get("terminal_ronic"), "cash": view["cash"],
                "debt": view["debt"], "nci": view.get("nci"),
                "distributions": view.get("distributions") or 0.0, "shares": detail["shares"],
                "to_idr": detail.get("fx") or 1.0,
                "parent_share": detail.get("attributable_share") or 1.0}})
    if selected == "ddm" and ((fc or {}).get("bank_model") or {}).get("sourced_drivers"):
        from . import bank_drivers
        data = bank_drivers.load(intake.get("ticker"), intake.get("as_of"))
        model = fc["bank_model"]
        if data:
            return _jsonable({"kind": "bank", "drivers": data, "valuation": {
                "coe": detail["coe"], "g": detail["g"], "valuation_date": detail["valuation_date"],
                "shares": detail["shares"], "to_idr": detail.get("fx") or 1.0,
                "prior_profit": model["prior_parent_profit"], "first_payout": model["first_payout"]}})
    if selected == "sotp_lom" and detail.get("lom"):
        lom = detail["lom"]
        return _jsonable({"kind": "mining", "inputs": lom["inputs"], "bridge": lom["bridge_idr"],
                          "fx": lom["fx"]})
    return None


def _link_register(result, register):
    """Each row's Evidence Register row IDs for its source keys (plan §6 exit)."""
    from . import evidence
    ids = evidence.row_ids_by_name(register, "driver_source")
    for row in (result or {}).get("rows") or []:
        row["evidence_row_ids"] = [ids[k] for k in row.get("source_refs") or [] if k in ids]
    return result


def assess(intake, fc, va):
    """Driver table for the selected Production-Ready model, or None (register-linked)."""
    return _link_register(_assess(intake, fc, va), (intake or {}).get("evidence_register"))


def _assess(intake, fc, va):
    chain = (va or {}).get("method_chain") or {}
    selected = chain.get("selected")
    detail = next((t.get("detail") for t in chain.get("trace") or [] if t.get("key") == selected),
                  None) or {}
    try:
        if selected == "fcff_dcf" and detail.get("operating_model"):
            drivers = operating_model.load(intake.get("ticker"), intake.get("as_of"))
            return operating(drivers, detail) if drivers else None
        if selected == "ddm" and ((fc or {}).get("bank_model") or {}).get("sourced_drivers"):
            from . import bank_drivers
            data = bank_drivers.load(intake.get("ticker"), intake.get("as_of"))
            return bank(data, detail, fc["bank_model"]) if data else None
        if selected == "sotp_lom" and detail.get("lom"):
            lom = detail["lom"]
            return mining(lom["inputs"], lom["bridge_idr"], lom["fx"])
        if selected == "holding_sotp" and detail.get("components"):
            return holding(detail)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        return {"rows": [], "error": f"{type(error).__name__}: {error}"}
    return None
