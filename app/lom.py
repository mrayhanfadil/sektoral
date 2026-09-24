"""SOTP/LoM for an integrated copper-gold miner (spec §4.1 finite-life, §4.5).

Physical chain, asset by asset, from the official reserve date to the end of
the licence horizon, with no perpetual terminal value:

reserves (pit, stockpile, development deposit) -> plant feed at the official
concentrator capacity -> recovered metal (recoveries implied by the latest
official interim) -> smelter/refinery at official capacity and the latest
official utilisation, the excess sold as concentrate -> revenue at a dated
price deck -> unit costs, royalties (PP 19/2025) and export duty -> EBITDA ->
tax and non-tax government revenue at the latest official rates -> capex ->
FCFF, discounted in USD.

Every physical and cost input comes from the issuer evidence pack; what the
issuer does not disclose (development capex, discount rate, risking,
stockpile rehandling) comes from the labelled analyst assumptions in
``data/analyst_scenarios/<T>.json`` and is shown as such. The result is an
assumption-led valuation, never a production-ready forecast.
"""
from __future__ import annotations

import re

from . import commodity, fmt

OZ_PER_T = 32150.7466
G_PER_OZ = 31.1034768
LB_PER_T = 2204.62262
PAYABLE_CU, PAYABLE_AU = 0.9655, 0.97   # HPM payable rules (Kepmen ESDM 144.K/2026)
CAPACITY_PAGE = 10
# Sensitivity only: mine Elang until its reserve is exhausted, not to 2050.
LICENCE_EXTENSION_END = 2100  # H1 2026 presentation: "up to 220,000 tonnes ... and 579,000 oz"


def _num(value):
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def _band(rate_table, price):
    """Royalty rate (%) for a reference price from a PP 19/2025 band table."""
    for row in rate_table:
        low = row.get("from_inclusive", float("-inf"))
        high = row.get("to_exclusive", row.get("below", float("inf")))
        if "below" in row and price < row["below"]:
            return row["rate_pct"] / 100
        if "below" not in row and low <= price < high:
            return row["rate_pct"] / 100
    return None


def _metric(rows, name):
    return next((row for row in rows or [] if row.get("name") == name), {})


def _year(text):
    """First year of an issuer range such as '2031/2032'."""
    match = re.search(r"(20\d\d)", str(text or ""))
    return int(match.group(1)) if match else None


def inputs(intake, fc):
    """Collect sourced physical, cost and bridge inputs; (inputs, gaps)."""
    ev = intake.get("official_evidence") or {}
    scenario = intake.get("analyst_scenario") or {}
    lom = scenario.get("lom_assumptions") or {}
    gaps = []
    mlc = ev.get("mine_life_context") or {}
    om = ev.get("operating_metrics") or []
    guidance = ev.get("management_guidance") or []
    plant = ev.get("processing_plant") or {}
    capacity = ((ev.get("processing_capacity") or {}).get("products") or {})
    util = ev.get("smelter_utilization") or {}
    cost = ev.get("cost_actuals") or {}
    trend = ((cost.get("operating_cost_history") or {}).get("unit_cost_trend") or [])
    latest_half = trend[-1] if trend else {}
    royalty = ev.get("royalty_and_export_duty") or {}
    rates = royalty.get("rates_pct_of_reference_price") or {}
    actual = ev.get("latest_actual") or {}
    income = ((actual.get("financial_statements_usd_thousand") or {})
              .get("income_statement") or {})
    inventory = ev.get("inventory_and_sales_detail") or {}
    elang = ev.get("elang_development_economics") or {}
    mineops = intake.get("mineops") or {}
    permit_expired = ((ev.get("quarterly_actuals") or {}).get("q1_2026") or {}).get(
        "temporary_concentrate_export_permit_expired")

    throughput = _num(_metric(om, "Mill throughput (juta ton)").get("current"))
    cu_grade = _num(_metric(om, "Kadar tembaga (%)").get("current"))
    au_grade = _num(_metric(om, "Kadar emas (g/t)").get("current"))
    cu_conc = _num(_metric(om, "Tembaga dalam konsentrat (Mlbs)").get("current"))
    au_conc = _num(_metric(om, "Emas dalam konsentrat (oz)").get("current"))
    recovery_cu = (cu_conc * 1e6 / LB_PER_T / (throughput * 1e6 * cu_grade / 100)
                   if throughput and cu_grade and cu_conc else None)
    recovery_au = (au_conc / (throughput * 1e6 * au_grade / G_PER_OZ)
                   if throughput and au_grade and au_conc else None)
    guide_cu = _num(_metric(guidance, "Tembaga dalam konsentrat (Mlbs)").get("value"))
    guide_au = _num(_metric(guidance, "Emas dalam konsentrat (koz)").get("value"))
    ebitda = _num((actual.get("metrics") or {}).get("ebitda"))
    operating = _num(income.get("operating_profit"))
    pbt, tax = _num(income.get("profit_before_tax")), _num(income.get("income_tax"))
    pre_ntgr, ntgr = (_num(income.get("profit_before_non_tax_revenue")),
                      _num(income.get("non_tax_government_revenue")))
    inv_rows = {row.get("name"): row for row in
                inventory.get("inventory_and_stockpile_carrying_amounts") or []}
    inv_names = ("Concentrate inventory", "In-process - smelter", "Finished copper cathode",
                 "Finished refined gold")
    inventory_usd = (sum(_num(inv_rows[n].get("jun_2026")) or 0 for n in inv_names) * 1000
                     if all(n in inv_rows for n in inv_names) else None)
    pit_cu_blb = (_num(mlc.get("batu_hijau_contained_cu_blb")) or 0) - (
        _num(mlc.get("stockpile_contained_cu_blb")) or 0)
    pit_au_moz = (_num(mlc.get("batu_hijau_contained_au_moz")) or 0) - (
        _num(mlc.get("stockpile_contained_au_moz")) or 0)
    values = {
        "reserves_as_of": mlc.get("reserves_as_of"),
        "pit_mt": (_num(mlc.get("batu_hijau_reserves_mt")) or 0) - (_num(mlc.get("stockpile_mt")) or 0),
        "pit_cu_t": pit_cu_blb * 1e9 / LB_PER_T, "pit_au_oz": pit_au_moz * 1e6,
        "stock_mt": _num(mlc.get("stockpile_mt")),
        "stock_cu_t": (_num(mlc.get("stockpile_contained_cu_blb")) or 0) * 1e9 / LB_PER_T,
        "stock_au_oz": (_num(mlc.get("stockpile_contained_au_moz")) or 0) * 1e6,
        "elang_mt": _num(mlc.get("elang_reserves_mt")),
        "elang_cu_t": (_num(mlc.get("elang_contained_cu_blb")) or 0) * 1e9 / LB_PER_T,
        "elang_au_oz": (_num(mlc.get("elang_contained_au_moz")) or 0) * 1e6,
        "pit_end": _year(mlc.get("batu_hijau_mining_through")),
        "elang_first_ore": _year(mlc.get("elang_first_ore")),
        "licence_end": _num(elang.get("mining_until_at_least")),
        "plant_mtpa": _num(plant.get("design_input_mtpa")),
        "h1_grade_cu": cu_grade, "h1_grade_au": au_grade,
        "recovery_cu": recovery_cu, "recovery_au": recovery_au,
        "fy_guidance_cu_t": guide_cu * 1e6 / LB_PER_T if guide_cu else None,
        "fy_guidance_au_oz": guide_au * 1000 if guide_au else None,
        "h1_cu_t": cu_conc * 1e6 / LB_PER_T if cu_conc else None,
        "h1_au_oz": au_conc,
        "smelter_t": _num((capacity.get("cathode_copper") or {}).get("annual_design_capacity")),
        "pmr_oz": _num((capacity.get("refined_gold") or {}).get("annual_design_capacity")),
        "utilization": (_num(util.get("production_rate_pct")) or 0) / 100 or None,
        "mining_usd_t": _num(cost.get("unit_mining_cost_usd_per_tonne")),
        "processing_usd_t": _num(cost.get("unit_processing_cost_usd_per_tonne")),
        "smelting_usd_t": _num(cost.get("smelting_refining_cost_usd_per_cathode_tonne")),
        "strip_ratio": (_num(latest_half.get("waste_mined_mt")) /
                        _num(latest_half.get("ore_mined_mt"))
                        if _num(latest_half.get("waste_mined_mt")) and
                        _num(latest_half.get("ore_mined_mt")) else None),
        "h1_material_mt": ((_num(latest_half.get("waste_mined_mt")) or 0) +
                           (_num(latest_half.get("ore_mined_mt")) or 0)) or None,
        "royalty": rates, "export_duty": (_num(royalty.get("concentrate_export_duty_pct")) or 0) / 100,
        "tax_rate": -tax / pbt if tax is not None and pbt else None,
        "ntgr_rate": -ntgr / pre_ntgr if ntgr is not None and pre_ntgr else None,
        "da_usd": (ebitda - operating * 1000) * 2 if ebitda and operating else None,
        "ga_usd": -(_num(income.get("marketing_general_administrative")) or 0) * 1000 * 2 or None,
        "h1_capex_usd": (_num(((ev.get("historical_capex_reference") or {})
                               .get("h1_2026"))) or 0) * 1e6 or None,
        "h2_capex_usd": _num(((fc.get("interim_scenario") or {}).get("h2") or {})
                             .get("capital_expenditure")),
        "inventory_usd": inventory_usd,
        "cu_price": _num((mineops.get("cu_price") or {}).get("avg12")),
        "au_price": _num((mineops.get("au_price") or {}).get("avg12")),
        "cu_price_date": (mineops.get("cu_price") or {}).get("date"),
        "au_price_date": (mineops.get("au_price") or {}).get("date"),
        "deck_basis": deck_basis(mineops),
        "export_permit_expired": permit_expired,
        # No export after the temporary permit lapsed, unless evidence shows a renewal.
        "export_base": not (permit_expired and permit_expired <= str(intake.get("as_of"))[:10]),
        "deck_source": "; ".join(dict.fromkeys(
            f"https://finance.yahoo.com/quote/{commodity.SERIES[name][0]}/history/"
            if (mineops.get(metal) or {}).get("source") == "yahoo"
            else "sectors_cache /mining/commodities"
            for metal, name in (("cu_price", "Copper"), ("au_price", "Gold")))),
        "reserve_cu_price": (_num(mlc.get("reserve_cu_price_usd_per_lb")) or 0) * LB_PER_T or None,
        "reserve_au_price": _num(mlc.get("reserve_au_price_usd_per_oz")),
        "discount": _num(lom.get("discount_rate_usd")),
        "elang_risk": _num(lom.get("elang_risk_factor")),
        "elang_capex": {int(y): float(v) for y, v in
                        (lom.get("elang_development_capex_usd") or {}).items()},
        "elang_sustaining_usd": _num(lom.get("elang_sustaining_capex_usd_per_year")),
        "rehandle_usd_t": _num(lom.get("stockpile_rehandle_usd_per_t")),
        "stockpile_capex_share": _num(lom.get("stockpile_phase_sustaining_share")),
        "assumptions": lom,
    }
    for key in ("pit_mt", "stock_mt", "elang_mt", "plant_mtpa", "recovery_cu", "recovery_au",
                "fy_guidance_cu_t", "fy_guidance_au_oz", "smelter_t", "pmr_oz",
                "utilization", "mining_usd_t", "processing_usd_t", "smelting_usd_t",
                "strip_ratio", "tax_rate", "ntgr_rate", "da_usd", "ga_usd", "h1_capex_usd",
                "cu_price", "au_price", "reserve_cu_price", "reserve_au_price", "discount",
                "elang_risk", "elang_sustaining_usd", "rehandle_usd_t",
                "stockpile_capex_share", "licence_end", "pit_end", "elang_first_ore"):
        if not values.get(key):
            gaps.append(key)
    for metal in ("cu_price", "au_price"):
        if (mineops.get(metal) or {}).get("stale"):
            gaps.append(f"{metal}_stale")
    if not values["elang_capex"]:
        gaps.append("elang_capex")
    if not rates.get("copper_cathode_by_hma_usd_per_tonne"):
        gaps.append("royalty")
    return values, gaps


def deck_basis(mineops):
    """Reader label of the base deck: window and source of each metal."""
    parts = []
    for metal, name in (("cu_price", "Cu"), ("au_price", "Au")):
        stats = mineops.get(metal) or {}
        if stats.get("avg12") is None:
            continue
        window = stats.get("window") or ["?", "?"]
        text = (f"{name} rata-rata {window[0]} s.d. {window[1]}, {stats.get('source_label')}"
                f" (data terakhir {stats.get('date')})")
        replaced = stats.get("replaced")
        if replaced:
            text += (f"; seri Sectors berhenti {replaced['date']} "
                     f"({replaced['age_days']} hari sebelum tanggal laporan) sehingga tidak dipakai")
        parts.append(text)
    return "; ".join(parts)


def deck(inp, name="base"):
    """(copper USD/t, gold USD/oz) held flat over the life of mine."""
    if name == "reserve":
        return inp["reserve_cu_price"], inp["reserve_au_price"]
    scale = {"base": 1.0, "down20": 0.8, "up20": 1.2}[name]
    return inp["cu_price"] * scale, inp["au_price"] * scale


def schedule(inp, prices, export=True):
    """Annual physical and cash rows per asset (Batu Hijau / Elang), USD.

    With ``export`` the metal the smelter and refinery cannot take is sold as
    concentrate. Without it (the temporary export permit expired on 30 Apr
    2026) the plant is fed only as much ore as the smelter can smelt; ore left
    in the pit or stockpile is processed later, and concentrate produced above
    smelter capacity in 2H26 is smelted first in the next year.
    """
    cu_price, au_price = prices
    rates = inp["royalty"]
    roy_cathode = _band(rates["copper_cathode_by_hma_usd_per_tonne"], cu_price)
    roy_gold = _band(rates["primary_refined_gold_by_hma_usd_per_oz"], au_price)
    roy_conc_cu = _band(rates["copper_in_concentrate_by_hma_usd_per_tonne"], cu_price)
    roy_conc_au = _band(rates["gold_byproduct_in_copper_concentrate_by_hma_usd_per_oz"], au_price)
    pools = [
        {"asset": "bh", "kind": "pit", "mt": inp["pit_mt"], "cu": inp["pit_cu_t"],
         "au": inp["pit_au_oz"], "from": 2026},
        {"asset": "bh", "kind": "stockpile", "mt": inp["stock_mt"], "cu": inp["stock_cu_t"],
         "au": inp["stock_au_oz"], "from": 2026},
        {"asset": "elang", "kind": "pit", "mt": inp["elang_mt"], "cu": inp["elang_cu_t"],
         "au": inp["elang_au_oz"], "from": inp["elang_first_ore"]},
    ]
    rows = []
    end = int(inp["licence_end"])
    carry = {"cu": 0.0, "au": 0.0}           # recovered metal awaiting the smelter
    concentrate = {"asset": "bh", "kind": "concentrate"}
    for year in range(2026, end + 1):
        share = 0.5 if year == 2026 else 1.0          # valuation from 30 Jun 2026
        draws = []
        smelter_cap = inp["smelter_t"] * inp["utilization"] * share
        if not export and carry["cu"] > 0 and year > 2026:
            draws.append({"pool": concentrate, "mt": 0.0, "cu": carry["cu"] / inp["recovery_cu"],
                          "au": carry["au"] / inp["recovery_au"]})
            carry = {"cu": 0.0, "au": 0.0}
        if year == 2026:
            # 2H26: FY guidance less the 1H actual, from the pit at the 1H grade.
            cu_rec = inp["fy_guidance_cu_t"] - inp["h1_cu_t"]
            au_rec = inp["fy_guidance_au_oz"] - inp["h1_au_oz"]
            tonnes = cu_rec / (inp["h1_grade_cu"] / 100 * inp["recovery_cu"])
            pit = pools[0]
            cu_cont, au_cont = cu_rec / inp["recovery_cu"], au_rec / inp["recovery_au"]
            pit.update(mt=pit["mt"] - tonnes / 1e6, cu=pit["cu"] - cu_cont,
                       au=pit["au"] - au_cont)
            draws.append({"pool": pit, "mt": tonnes / 1e6, "cu": cu_cont, "au": au_cont})
        else:
            room = inp["plant_mtpa"]
            # Contained copper the smelter can still take this year (no export).
            cu_room = (max(smelter_cap - sum(d["cu"] for d in draws) * inp["recovery_cu"], 0.0)
                       / inp["recovery_cu"]) if not export else float("inf")
            for pool in pools:
                if (room <= 1e-9 or cu_room <= 1e-9 or pool["mt"] <= 1e-9
                        or year < pool["from"]):
                    continue
                grade = pool["cu"] / pool["mt"]              # contained Cu t per Mt
                take = min(room, pool["mt"], cu_room / grade if grade else room)
                cu_room -= take * grade
                frac = take / pool["mt"]
                draw = {"pool": pool, "mt": take, "cu": pool["cu"] * frac,
                        "au": pool["au"] * frac}
                pool.update(mt=pool["mt"] - take, cu=pool["cu"] - draw["cu"],
                            au=pool["au"] - draw["au"])
                draws.append(draw)
                room -= take
        if not draws:
            break
        cu_rec_total = sum(d["cu"] for d in draws) * inp["recovery_cu"]
        au_rec_total = sum(d["au"] for d in draws) * inp["recovery_au"]
        cathode = min(cu_rec_total, smelter_cap)
        smelted = cathode / cu_rec_total if cu_rec_total else 0.0
        refined = min(au_rec_total * smelted, inp["pmr_oz"] * share)
        if not export and year == 2026:
            carry = {"cu": cu_rec_total - cathode, "au": au_rec_total * (1 - smelted)}
        for d in draws:
            pool = d["pool"]
            part = d["cu"] / sum(x["cu"] for x in draws)
            cu_rec, au_rec = d["cu"] * inp["recovery_cu"], d["au"] * inp["recovery_au"]
            d_cathode = cathode * part
            d_refined = refined * (au_rec / au_rec_total if au_rec_total else 0)
            conc_cu, conc_au = cu_rec - d_cathode, au_rec - d_refined
            conc_value = conc_cu * cu_price * PAYABLE_CU + conc_au * au_price * PAYABLE_AU
            sold_conc = conc_value if export else 0.0
            revenue = (d_cathode * cu_price + d_refined * au_price
                       + sold_conc * (1 - inp["export_duty"]))
            royalties = (d_cathode * cu_price * roy_cathode + d_refined * au_price * roy_gold
                         + (conc_cu * cu_price * roy_conc_cu + conc_au * au_price * roy_conc_au
                            if export else 0.0))
            if year == 2026:
                mined = inp["h1_material_mt"] * 1e6 * part          # 2H26 at the 1H26 rate
            elif pool["kind"] == "pit":
                mined = d["mt"] * 1e6 * (1 + inp["strip_ratio"])
            else:
                mined = 0.0
            costs = {
                "mining": mined * inp["mining_usd_t"],
                "rehandle": (d["mt"] * 1e6 * inp["rehandle_usd_t"]
                             if pool["kind"] == "stockpile" else 0.0),
                "processing": d["mt"] * 1e6 * inp["processing_usd_t"],
                "smelting": d_cathode * inp["smelting_usd_t"],
            }
            ebitda = revenue - royalties - sum(costs.values())
            rows.append({"year": year, "share": share, "asset": pool["asset"],
                         "kind": pool["kind"], "feed_mt": d["mt"], "mined_t": mined,
                         "grade_cu": d["cu"] / (d["mt"] * 1e6) * 100 if d["mt"] else None,
                         "grade_au": d["au"] * G_PER_OZ / (d["mt"] * 1e6) if d["mt"] else None,
                         "cu_rec_t": cu_rec, "au_rec_oz": au_rec, "cathode_t": d_cathode,
                         "refined_oz": d_refined, "conc_cu_t": conc_cu, "conc_au_oz": conc_au,
                         "revenue": revenue, "royalties": royalties,
                         "export_duty": sold_conc * inp["export_duty"], **costs,
                         "ebitda": ebitda})
    return rows, {"cathode": roy_cathode, "gold": roy_gold, "conc_cu": roy_conc_cu,
                  "conc_au": roy_conc_au}


def elang_capex_schedule(inp, rows):
    """Elang development capex, dated to this schedule's own first Elang feed.

    The broker profile (2029-2030) belongs to a first ore in 2031. The issuer
    starts Elang after the Batu Hijau mine life, and at the plant's 85 Mtpa the
    pit and stockpile fill it until later, so the same profile is moved to end
    the year before Elang's first feed here: capex is never spent years before
    the ore it pays for.
    """
    capex = dict(sorted(inp["elang_capex"].items()))
    feed = sorted({r["year"] for r in rows if r["asset"] == "elang" and r["feed_mt"] > 0})
    if not capex or not feed:
        return capex
    shift = max(0, (feed[0] - 1) - max(capex))
    return {year + shift: amount for year, amount in capex.items()}


def cash_flows(inp, rows):
    """Per asset and year: EBITDA -> tax -> NTGR -> capex -> FCFF."""
    by = {}
    for row in rows:
        key = (row["asset"], row["year"])
        acc = by.setdefault(key, {"asset": row["asset"], "year": row["year"],
                                  "share": row["share"], "ebitda": 0.0, "revenue": 0.0,
                                  "feed_mt": 0.0, "cathode_t": 0.0, "refined_oz": 0.0,
                                  "conc_cu_t": 0.0, "conc_au_oz": 0.0, "royalties": 0.0,
                                  "costs": 0.0, "kinds": []})
        acc["ebitda"] += row["ebitda"]
        acc["revenue"] += row["revenue"]
        acc["royalties"] += row["royalties"] + row["export_duty"]
        acc["costs"] += row["mining"] + row["rehandle"] + row["processing"] + row["smelting"]
        for k in ("feed_mt", "cathode_t", "refined_oz", "conc_cu_t", "conc_au_oz"):
            acc[k] += row[k]
        if row["kind"] not in acc["kinds"]:
            acc["kinds"].append(row["kind"])
    elang_years = sorted({y for (a, y) in by if a == "elang"})
    elang_capex = elang_capex_schedule(inp, rows)
    elang_dev = sum(elang_capex.values())
    out = []
    for (asset, year), acc in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        share = acc["share"]
        if asset == "bh":
            da = inp["da_usd"] * share
            if year == 2026:
                capex = inp["h2_capex_usd"] or inp["h1_capex_usd"]
            elif "pit" in acc["kinds"] and year <= inp["pit_end"]:
                capex = inp["h1_capex_usd"] * 2
            else:
                capex = inp["h1_capex_usd"] * 2 * inp["stockpile_capex_share"]
        else:
            da = elang_dev / len(elang_years) + inp["elang_sustaining_usd"]
            capex = inp["elang_sustaining_usd"]
        taxable = max(acc["ebitda"] - da, 0.0)
        tax = taxable * inp["tax_rate"]
        ntgr = max(taxable - tax, 0.0) * inp["ntgr_rate"]
        out.append({**acc, "da": da, "tax": tax, "ntgr": ntgr, "capex": capex,
                    "fcff": acc["ebitda"] - tax - ntgr - capex})
    for year, amount in sorted(elang_capex.items()):
        out.append({"asset": "elang", "year": year, "share": 1.0, "ebitda": 0.0,
                    "revenue": 0.0, "feed_mt": 0.0, "cathode_t": 0.0, "refined_oz": 0.0,
                    "conc_cu_t": 0.0, "conc_au_oz": 0.0, "royalties": 0.0, "costs": 0.0,
                    "kinds": ["development"], "da": 0.0, "tax": 0.0, "ntgr": 0.0,
                    "capex": amount, "fcff": -amount})
    return out


def _t(year):
    """Mid-period timing in years from 30 Jun 2026 (2H26 at 0.25)."""
    return 0.25 if year == 2026 else float(year - 2026)


def navs(inp, flows, rate):
    nav = {"bh": 0.0, "elang": 0.0}
    for f in flows:
        nav[f["asset"]] += f["fcff"] / (1 + rate) ** _t(f["year"])
    last = max(f["year"] for f in flows)
    overhead = sum(inp["ga_usd"] * (0.5 if y == 2026 else 1.0) / (1 + rate) ** _t(y)
                   for y in range(2026, last + 1))
    return nav, overhead


def value(inp, bridge_idr, fx, deck_name="base", rate=None, risk=None, export=None):
    """Per-share value and its components for one scenario."""
    export = inp.get("export_base", True) if export is None else export
    rate = inp["discount"] if rate is None else rate
    risk = inp["elang_risk"] if risk is None else risk
    rows, royalty = schedule(inp, deck(inp, deck_name), export=export)
    flows = cash_flows(inp, rows)
    nav, overhead = navs(inp, flows, rate)
    assets_usd = nav["bh"] + nav["elang"] * risk + (inp["inventory_usd"] or 0.0)
    equity_idr = (assets_usd - overhead) * fx + bridge_idr["cash"] - bridge_idr["debt"] \
        - bridge_idr["minority"]
    return {"rows": rows, "flows": flows, "royalty": royalty, "nav": nav,
            "overhead_usd": overhead, "per_share": equity_idr / bridge_idr["shares"],
            "equity_idr": equity_idr, "elang_capex": elang_capex_schedule(inp, rows),
            "elang_feed_years": sorted({r["year"] for r in rows
                                        if r["asset"] == "elang" and r["feed_mt"] > 0})}


def _bridge_value(entry):
    return entry.get("value") if isinstance(entry, dict) else None


def build(intake, fc):
    """SOTP/LoM result or (None, gaps). Amounts in the SOTP are raw IDR."""
    inp, gaps = inputs(intake, fc)
    bridge = intake.get("sotp_bridge") or {}
    b = {"cash": _bridge_value(bridge.get("cash_idr")),
         "debt": _bridge_value(bridge.get("debt_idr")),
         "minority": _bridge_value(bridge.get("minority_interest_idr")),
         "shares": _bridge_value(bridge.get("shares"))}
    fx = ((bridge.get("cash_idr") or {}).get("fx_rate")
          if isinstance(bridge.get("cash_idr"), dict) else None)
    for key, v in b.items():
        if v is None:
            gaps.append(f"bridge_{key}")
    if not fx:
        gaps.append("fx")
    if gaps:
        return None, gaps
    base = value(inp, b, fx)
    grid = {}
    for rate in (inp["discount"] - 0.02, inp["discount"], inp["discount"] + 0.02):
        for name in ("reserve", "down20", "base", "up20"):
            grid[(round(rate, 3), name)] = value(inp, b, fx, name, rate)["per_share"]
    other_export = value(inp, b, fx, export=not inp.get("export_base", True))["per_share"]
    risk_range = {r: value(inp, b, fx, risk=r)["per_share"] for r in (0.0, 0.25, 0.75, 1.0)}
    # The issuer states Elang runs "at least" to 2050; the reserve lasts longer.
    extended = value({**inp, "licence_end": LICENCE_EXTENSION_END}, b, fx)
    extension = {"end": max(extended["elang_feed_years"] or [inp["licence_end"]]),
                 "per_share": extended["per_share"]}
    return {"inputs": inp, "base": base, "grid": grid, "other_export": other_export,
            "risk_range": risk_range, "licence_extension": extension, "bridge_idr": b, "fx": fx,
            "per_share": base["per_share"],
            "per_share_down": grid[(round(inp["discount"] + 0.02, 3), "base")]}, []


def forward_rows(intake, res, anchor_year, attributable_share=1.0, years=4):
    """FY rows after the interim year from the same LoM schedule as the value.

    Revenue, EBITDA and capex are the schedule's annual totals (Batu Hijau and,
    once it feeds, Elang). Net profit deducts the schedule's D&A, interest at
    twice the 1H finance cost, and tax and non-tax government revenue at the
    1H effective rates, so the Key Financials read off the valuation's own
    physical plan instead of a separate earnings scenario.
    """
    inp, base = res["inputs"], res["base"]
    actual = ((intake.get("official_evidence") or {}).get("latest_actual") or {})
    income = ((actual.get("financial_statements_usd_thousand") or {})
              .get("income_statement") or {})
    interest = -(_num(income.get("finance_costs")) or 0.0) * 1000 * 2
    by_year = {}
    for f in base["flows"]:
        acc = by_year.setdefault(f["year"], {"revenue": 0.0, "ebitda": 0.0, "da": 0.0,
                                             "capex": 0.0})
        for key in acc:
            acc[key] += f.get(key) or 0.0
    phys = {}
    for r in base["rows"]:
        acc = phys.setdefault(r["year"], {"feed": 0.0, "cathode": 0.0, "gold": 0.0,
                                          "kinds": []})
        acc["feed"] += r["feed_mt"]
        acc["cathode"] += r["cathode_t"]
        acc["gold"] += r["refined_oz"]
        label = {"pit": "pit", "stockpile": "stockpile", "concentrate": "konsentrat 2H26"}.get(
            r["kind"], r["kind"])
        name = f"{'Elang' if r['asset'] == 'elang' else 'Batu Hijau'} {label}"
        if r["feed_mt"] > 0 or r["kind"] == "concentrate":
            if name not in acc["kinds"]:
                acc["kinds"].append(name)
    rows, previous = [], None
    for year in range(anchor_year + 1, anchor_year + 1 + years):
        acc = by_year.get(year)
        if not acc or not acc["revenue"]:
            break
        pre_tax = acc["ebitda"] - acc["da"] - interest
        tax = max(pre_tax, 0.0) * inp["tax_rate"]
        ntgr = max(pre_tax - tax, 0.0) * inp["ntgr_rate"]
        net = pre_tax - tax - ntgr
        p = phys.get(year) or {}
        rows.append({
            "year": year, "label": f"FY{year % 100:02d}F", "revenue": acc["revenue"],
            "ebitda": acc["ebitda"], "net_profit": net,
            "net_profit_attributable": net * attributable_share, "capex": acc["capex"],
            "revenue_growth_pct": (acc["revenue"] / previous - 1) * 100 if previous else None,
            "ebitda_margin_pct": acc["ebitda"] / acc["revenue"] * 100,
            "net_income_margin_pct": net / acc["revenue"] * 100,
            "capex_to_revenue_pct": acc["capex"] / acc["revenue"] * 100,
            "rationale": (f"Jadwal LoM: umpan {fmt._id(p.get('feed', 0), 0)} Mt "
                          f"({', '.join(p.get('kinds') or [])}), katoda "
                          f"{fmt._id(p.get('cathode', 0) / 1000, 0)} kt, emas murni "
                          f"{fmt._id(p.get('gold', 0) / 1000, 0)} koz; dek Cu "
                          f"US${fmt._id(inp['cu_price'], 0)}/t dan Au US${fmt._id(inp['au_price'], 0)}"
                          "/oz; bunga 2x beban keuangan 1H26; pajak dan PNBP pada tarif efektif "
                          "1H26."),
            "source_ids": ["official"]})
        previous = acc["revenue"]
    return rows


def _ref(title, url):
    return f"{title}: {url}"


def sotp_result(intake, res):
    """Asset NAVs through the auditable SOTP bridge (raw IDR)."""
    from . import sotp as sotp_mod
    ev = intake.get("official_evidence") or {}
    inp, base, fx = res["inputs"], res["base"], res["fx"]
    actual = ev.get("latest_actual") or {}
    mlc = ev.get("mine_life_context") or {}
    inventory = ev.get("inventory_and_sales_detail") or {}
    lom = inp["assumptions"]
    release = actual.get("source_url")
    statements = (ev.get("balance_sheet") or {}).get("source_url")
    last_year = max(f["year"] for f in base["flows"])
    assets = [
        {"name": "Batu Hijau (pit, stockpile, pabrik, smelter dan PMR)", "stage": "operating",
         "method": f"LoM DCF USD {inp['discount'] * 100:.0f}%, tanpa terminal",
         "source": mlc.get("source_url") or release,
         "provenance": ("Cadangan 30 Jun 2026, recovery tersirat 1H26, kapasitas pabrik 85 Mtpa, "
                        "smelter 220 kt x utilisasi Juni 93%, biaya unit 1H26, royalti PP 19/2025; "
                        f"dek harga: {inp.get('deck_basis') or 'rata-rata 12 bulan'}."),
         "source_date": actual.get("published_at"), "page": "3-7",
         "nav_idr": base["nav"]["bh"] * fx, "ownership_pct": 100.0},
        {"name": "Elang (pengembangan, pra-FID)", "stage": "development",
         "method": (f"LoM DCF USD {inp['discount'] * 100:.0f}% sampai {int(inp['licence_end'])}, "
                    f"probabilitas pengembangan {inp['elang_risk'] * 100:.0f}%"),
         "source": mlc.get("source_url") or release,
         "provenance": ("Cadangan Elang resmi 30 Jun 2026; capex pengembangan dan pemeliharaan "
                        "dari " + str(lom.get("broker_source_title")) + " (" +
                        str(lom.get("broker_source_date")) + ", " +
                        str(lom.get("broker_source_page")) + "), asumsi analis, bukan data emiten."),
         "source_date": actual.get("published_at"), "page": mlc.get("source_page") or 6,
         "nav_idr": base["nav"]["elang"] * inp["elang_risk"] * fx, "ownership_pct": 100.0},
        {"name": "Persediaan logam dan konsentrat", "stage": "inventory",
         "method": "nilai buku 30 Jun 2026",
         "source": statements or release,
         "provenance": "Konsentrat, proses smelter, katoda dan emas murni pada nilai tercatat.",
         "source_date": actual.get("published_at"),
         "page": inventory.get("inventory_source_page") or 61,
         "nav_idr": (inp["inventory_usd"] or 0.0) * fx, "ownership_pct": 100.0},
    ]
    b = res["bridge_idr"]
    overhead_idr = base["overhead_usd"] * fx
    result = sotp_mod.calculate_sotp(
        assets, cash_idr=b["cash"], debt_idr=b["debt"], minority_interest_idr=b["minority"],
        corporate_overhead_idr=overhead_idr, shares=b["shares"])
    bridge = intake.get("sotp_bridge") or {}
    evidence = {field: {key: bridge[field].get(key) for key in
                        ("source", "source_date", "page", "unit", "financial_source_date",
                         "balance_period_end", "fx_date", "fx_rate", "basis")}
                for field in ("cash_idr", "debt_idr", "minority_interest_idr", "shares")
                if isinstance(bridge.get(field), dict)}
    cash_row = evidence.get("cash_idr") or {}
    evidence["corporate_overhead_idr"] = {
        "source": statements and _ref("Laporan keuangan interim 1H26", statements),
        "source_date": cash_row.get("source_date"), "page": "4-6", "unit": "raw IDR",
        "financial_source_date": actual.get("published_at"),
        "fx_date": cash_row.get("fx_date"), "fx_rate": fx,
        "basis": (f"PV beban pemasaran, umum dan administrasi 1H26 x2 (US${inp['ga_usd'] / 1e6:.1f} "
                  f"juta per tahun) sampai {last_year} pada {inp['discount'] * 100:.0f}%.")}
    result["bridge_evidence"] = evidence
    return result


def operating_bridge(intake, res):
    """Seventeen physical-to-financial stages, each tied to its source."""
    ev = intake.get("official_evidence") or {}
    inp = res["inputs"]
    actual = ev.get("latest_actual") or {}
    mlc = ev.get("mine_life_context") or {}
    plant = ev.get("processing_plant") or {}
    util = ev.get("smelter_utilization") or {}
    cap = ev.get("processing_capacity") or {}
    cost = ev.get("cost_actuals") or {}
    royalty = ev.get("royalty_and_export_duty") or {}
    debt = ev.get("debt_and_contract_evidence") or {}
    lom = inp["assumptions"]
    rel, rel_date = actual.get("source_url"), actual.get("published_at")
    fs = (ev.get("balance_sheet") or {}).get("source_url")

    def row(claim, value, unit, period, status, source, date, page):
        return {"claim": claim, "value": value, "unit": unit, "period": period,
                "status": status, "source": source, "source_date": date, "page": page}

    return {
        "ore_access": row("Akses bijih segar Phase 8 1H26", 66, "juta ton", "1H26",
                          "reported actual", rel, rel_date, 3),
        "throughput": row("Kapasitas input pabrik konsentrator", inp["plant_mtpa"],
                          "juta ton per tahun", "2026-", "issuer disclosure",
                          plant.get("source_url"), plant.get("source_date"),
                          plant.get("source_page")),
        "grade": row("Kadar cadangan Batu Hijau / Elang",
                     "BH 0,34% Cu, 0,24 g/t Au; Elang 0,32% Cu, 0,33 g/t Au", "kadar",
                     str(mlc.get("reserves_as_of")), "JORC reserve", mlc.get("source_url"),
                     rel_date, mlc.get("source_page")),
        "recovery": row("Recovery tersirat 1H26 (logam dalam konsentrat / terkandung umpan)",
                        f"Cu {inp['recovery_cu'] * 100:.1f}%, Au {inp['recovery_au'] * 100:.1f}%",
                        "%", "1H26", "derived from reported actual", rel, rel_date, 3),
        "payable_production": row("Panduan logam dalam konsentrat FY2026",
                                  f"Cu {inp['fy_guidance_cu_t'] / 1e3:.0f} kt, Au "
                                  f"{inp['fy_guidance_au_oz'] / 1e3:.0f} koz", "logam",
                                  "FY2026", "management guidance", rel, rel_date, 7),
        "downstream_capacity": row("Kapasitas smelter dan PMR",
                                   f"{inp['smelter_t'] / 1e3:.0f} kt katoda; "
                                   f"{inp['pmr_oz'] / 1e3:.0f} koz emas murni", "per tahun",
                                   "desain", "issuer disclosure", util.get("source_url"),
                                   util.get("source_date"), CAPACITY_PAGE),
        "downstream_utilization": row("Tingkat produksi smelter", util.get("production_rate_pct"),
                                      "%", str(util.get("period")), "reported actual",
                                      util.get("source_url"), util.get("source_date"),
                                      util.get("source_page")),
        "product_sales_mix": row("Pendapatan 1H26 per produk", "katoda, emas murni, konsentrat",
                                 "US$", "1H26", "reported actual", rel, rel_date, 4),
        "realized_price_netback": row(
            "Dek harga: rata-rata 12 bulan kalender, payable HPM ("
            + (inp.get("deck_basis") or "data Sectors") + ")",
            f"Cu US${inp['cu_price']:,.0f}/t; Au US${inp['au_price']:,.0f}/oz", "USD",
            "LoM", "analyst price deck", inp.get("deck_source") or "sectors_cache /mining/commodities",
            rel_date, None),
        "revenue": row("Pendapatan bersih 1H26", (actual.get("metrics") or {}).get("revenue"),
                       "USD", "1H26", "reported actual", rel, rel_date, 3),
        "unit_cost_royalty": row(
            "Biaya unit 1H26 dan royalti PP 19/2025",
            f"tambang US${inp['mining_usd_t']}/t; olah US${inp['processing_usd_t']}/t; "
            f"smelter US${inp['smelting_usd_t']:,.0f}/t katoda", "USD/t", "1H26",
            "reported actual", cost.get("source_url") or rel, rel_date,
            cost.get("source_page") or 4),
        "ebitda": row("EBITDA 1H26", (actual.get("metrics") or {}).get("ebitda"), "USD",
                      "1H26", "reported actual", rel, rel_date, 3),
        "capex": row("Capex: 1H26 resmi; Elang asumsi analis dari riset broker",
                     f"1H26 US${inp['h1_capex_usd'] / 1e6:.0f} juta; Elang "
                     f"US${sum(inp['elang_capex'].values()) / 1e9:.2f} miliar "
                     "(dijadwalkan sebelum bijih pertama Elang dalam jadwal LoM)",
                     "USD", "LoM", "analyst assumption", lom.get("broker_source_url"),
                     lom.get("broker_source_date"), lom.get("broker_source_page")),
        "nwc": row("Modal kerja", "Perubahan modal kerja tidak dimodelkan; persediaan 30 Jun "
                   "2026 dinilai pada nilai buku", "USD", "LoM", "analyst assumption", fs,
                   rel_date, 61),
        "tax": row("Tarif pajak efektif dan PNBP 1H26",
                   f"pajak {inp['tax_rate'] * 100:.1f}%; PNBP {inp['ntgr_rate'] * 100:.1f}%",
                   "%", "1H26", "reported actual", rel, rel_date, 5),
        "debt": row("Utang finansial 30 Jun 2026",
                    (ev.get("balance_sheet") or {}).get("total_debt"), "USD", "2026-06-30",
                    "reported actual", fs, rel_date, "89, 98"),
        "fcff": row("FCFF LoM per aset", "dihitung mesin dari tahap di atas", "USD", "LoM",
                    "calculated", rel, rel_date, "model"),
    }
