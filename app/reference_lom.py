"""Independent reference calculation of a finite-life LoM/SOTP value per share (plan §5.6).

A second implementation of the physical-to-financial chain from the same LoM
input set (reserves, plant and smelter capacity, recoveries, price deck,
royalty bands, unit costs, taxes, capex, development risk) and the SOTP
bridge. It imports nothing from the production LoM code. Conventions follow
the model: valuation from 30 June of the first year (its second half only,
at the FY guidance less the first-half actual), pit then stockpile then the
development deposit into a plant of fixed capacity, the smelter and refinery
take what they can and the rest is sold as concentrate when export is
allowed (else feed is limited to smelter capacity and surplus concentrate
is smelted the next year), flows at mid-year from 30 June, no terminal
value; the development asset is risked by its probability.
"""
from __future__ import annotations

TOLERANCE = 0.005
PAY_CU, PAY_AU = 0.9655, 0.97


def _royalty(table, price):
    """PP 19/2025 band rate for a reference price; bands are ``below`` or
    ``from_inclusive``/``to_exclusive`` rows in percent."""
    for band in table:
        if "below" in band:
            if price < band["below"]:
                return band["rate_pct"] / 100
            continue
        low = band.get("from_inclusive", float("-inf"))
        high = band.get("to_exclusive", float("inf"))
        if low <= price < high:
            return band["rate_pct"] / 100
    raise ValueError(f"no royalty band holds price {price}")


def _sources(inp):
    return [
        {"asset": "bh", "kind": "pit", "mt": inp["pit_mt"], "cu": inp["pit_cu_t"],
         "au": inp["pit_au_oz"], "start": inp.get("first_year", 2026)},
        {"asset": "bh", "kind": "stockpile", "mt": inp["stock_mt"], "cu": inp["stock_cu_t"],
         "au": inp["stock_au_oz"], "start": inp.get("first_year", 2026)},
        {"asset": "elang", "kind": "pit", "mt": inp["elang_mt"], "cu": inp["elang_cu_t"],
         "au": inp["elang_au_oz"], "start": inp["elang_first_ore"]}]


def _year_draws(inp, pools, year, export, carry):
    first = year == inp.get("first_year", 2026)
    share = 0.5 if first else 1.0
    cap_cu = (inp["h2_cathode_t"] if first and inp.get("h2_cathode_t")
              else inp["smelter_t"] * inp["utilization"] * share)
    draws = []
    if not export and not first and carry[0] > 0:
        draws.append((None, 0.0, carry[0] / inp["recovery_cu"], carry[1] / inp["recovery_au"]))
    if first:
        cu = (inp["fy_guidance_cu_t"] - inp["h1_cu_t"]) / inp["recovery_cu"]
        au = (inp["fy_guidance_au_oz"] - inp["h1_au_oz"]) / inp["recovery_au"]
        mt = cu * inp["recovery_cu"] / (inp["h1_grade_cu"] / 100 * inp["recovery_cu"]) / 1e6
        pit = pools[0]
        pit["mt"] -= mt
        pit["cu"] -= cu
        pit["au"] -= au
        draws.append((pit, mt, cu, au))
        return draws, share, cap_cu
    room = inp["plant_mtpa"]
    cu_room = float("inf") if export else max(
        cap_cu - sum(d[2] for d in draws) * inp["recovery_cu"], 0.0) / inp["recovery_cu"]
    for pool in pools:
        if room <= 1e-9 or cu_room <= 1e-9 or pool["mt"] <= 1e-9 or year < pool["start"]:
            continue
        per_mt = pool["cu"] / pool["mt"]
        take = min(room, pool["mt"], cu_room / per_mt if per_mt else room)
        cu, au = pool["cu"] * take / pool["mt"], pool["au"] * take / pool["mt"]
        pool["mt"] -= take
        pool["cu"] -= cu
        pool["au"] -= au
        cu_room -= take * per_mt
        room -= take
        draws.append((pool, take, cu, au))
    return draws, share, cap_cu


def _grow(inp, year, y0=2026):
    """Nominal escalation from the deck year: (1 + US inflation) ^ years after it."""
    return (1.0 + (inp.get("escalation") or 0.0)) ** max(year - y0, 0)


def flows(inp, deck_cu, deck_au, export=True):
    """(asset, year) -> {ebitda, share, kinds} and the development capex by year."""
    rates = inp["royalty"]
    pools = _sources(inp)
    carry = (0.0, 0.0)
    acc = {}
    feed_years = set()
    y0 = inp.get("first_year", 2026)
    for year in range(y0, int(inp["licence_end"]) + 1):
        draws, share, cap_cu = _year_draws(inp, pools, year, export, carry)
        if not export and year > y0:
            carry = (0.0, 0.0)
        if not draws:
            break
        g = _grow(inp, year, y0)
        cu_price, au_price = deck_cu * g, deck_au * g
        r_cath = _royalty(rates["copper_cathode_by_hma_usd_per_tonne"], cu_price)
        r_gold = _royalty(rates["primary_refined_gold_by_hma_usd_per_oz"], au_price)
        r_ccu = _royalty(rates["copper_in_concentrate_by_hma_usd_per_tonne"], cu_price)
        r_cau = _royalty(rates["gold_byproduct_in_copper_concentrate_by_hma_usd_per_oz"], au_price)
        cu_rec = sum(d[2] for d in draws) * inp["recovery_cu"]
        au_rec = sum(d[3] for d in draws) * inp["recovery_au"]
        cathode = min(cu_rec, cap_cu)
        smelted = cathode / cu_rec if cu_rec else 0.0
        cap_au = (inp.get("h2_refined_oz") or inp["pmr_oz"] * share
                  if year == y0 and inp.get("h2_cathode_t") else inp["pmr_oz"] * share)
        refined = min(au_rec * smelted, cap_au)
        if not export and year == y0:
            carry = (cu_rec - cathode, au_rec - refined)
        total_cu = sum(d[2] for d in draws)
        for pool, mt, cu, au in draws:
            asset = pool["asset"] if pool else "bh"
            kind = pool["kind"] if pool else "concentrate"
            part = cu / total_cu
            my_cu, my_au = cu * inp["recovery_cu"], au * inp["recovery_au"]
            my_cath = cathode * part
            my_ref = refined * (my_au / au_rec if au_rec else 0.0)
            conc_cu, conc_au = my_cu - my_cath, my_au - my_ref
            conc = (conc_cu * cu_price * PAY_CU + conc_au * au_price * PAY_AU) if export else 0.0
            revenue = my_cath * cu_price + my_ref * au_price + conc * (1 - inp["export_duty"])
            royalty = my_cath * cu_price * r_cath + my_ref * au_price * r_gold + (
                conc_cu * cu_price * r_ccu + conc_au * au_price * r_cau if export else 0.0)
            if year == y0:
                moved = inp["h1_material_mt"] * 1e6 * part
            else:
                moved = mt * 1e6 * (1 + inp["strip_ratio"]) if kind == "pit" else 0.0
            cost = g * (moved * inp["mining_usd_t"]
                        + (mt * 1e6 * inp["rehandle_usd_t"] if kind == "stockpile" else 0.0)
                        + mt * 1e6 * inp["processing_usd_t"] + my_cath * inp["smelting_usd_t"])
            item = acc.setdefault((asset, year), {"ebitda": 0.0, "revenue": 0.0, "share": share,
                                                  "kinds": set()})
            item["ebitda"] += revenue - royalty - cost
            item["revenue"] += revenue
            item["kinds"].add(kind)
            if asset == "elang" and mt > 0:
                feed_years.add(year)
    capex = dict(sorted(inp["elang_capex"].items()))
    if capex and feed_years:
        shift = max(0, (min(feed_years) - 1) - max(capex))
        later = (1.0 + (inp.get("escalation") or 0.0)) ** shift
        capex = {y + shift: v * later for y, v in capex.items()}
    return acc, capex


def value(inp, bridge, fx, rate=None, deck=None, risk=None, export=None):
    rate = inp["discount"] if rate is None else rate
    risk = inp["elang_risk"] if risk is None else risk
    export = inp.get("export_base", True) if export is None else export
    cu_price, au_price = deck or (inp["cu_price"], inp["au_price"])
    acc, dev = flows(inp, cu_price, au_price, export)
    y0 = inp.get("first_year", 2026)
    t = lambda y: 0.25 if y == y0 else float(y - y0)  # noqa: E731
    elang_years = sorted({y for (a, y) in acc if a == "elang"})
    dev_total = sum(dev.values())
    nav = {"bh": 0.0, "elang": 0.0}
    wc = inp.get("wc")
    wc_cash = {}
    if wc:
        # Net operating working capital in days of annual revenue, released in each
        # asset's last operating year; supplies released at mine end; the customer
        # advance delivered against on its schedule.
        net_days = wc["receivable_days"] + wc["inventory_days"] - wc["payable_days"]
        level = {"bh": wc["opening"]["receivables"] + wc["opening"]["product_inventory"]
                 - wc["opening"]["payables"], "elang": 0.0}
        ends = {}
        for asset, year in acc:
            ends[asset] = max(ends.get(asset, 0), year)
        all_years = sorted(acc, key=lambda k: (k[1], k[0]))
        final_year = max(ends.values())
        final_asset = max(ends, key=lambda a: ends[a])
        for asset, year in all_years:
            item = acc[(asset, year)]
            yearly = item["revenue"] / item["share"]
            new = 0.0 if year == ends[asset] else net_days / 365 * yearly
            out = new - level[asset]
            level[asset] = new
            if year == final_year and asset == final_asset:
                out -= wc["supplies"]
            if asset == "bh":
                out += wc["advance_unwind"].get(year, wc["advance_unwind"].get(str(year), 0.0))
            wc_cash[(asset, year)] = out
    for (asset, year), item in acc.items():
        share = item["share"]
        g = _grow(inp, year, y0)
        if asset == "bh":
            da = inp["da_usd"] * share
            if year == y0:
                capex = inp["h2_capex_usd"] or inp["h1_capex_usd"]
            elif "pit" in item["kinds"] and year <= inp["pit_end"]:
                capex = inp["h1_capex_usd"] * 2 * g
            else:
                capex = inp["h1_capex_usd"] * 2 * inp["stockpile_capex_share"] * g
        else:
            sustaining = inp["elang_sustaining_usd"] * g
            da = dev_total / len(elang_years) + sustaining
            capex = sustaining
        taxable = max(item["ebitda"] - da, 0.0)
        tax = taxable * inp["tax_rate"]
        ntgr = max(taxable - tax, 0.0) * inp["ntgr_rate"]
        nav[asset] += (item["ebitda"] - tax - ntgr - capex - wc_cash.get((asset, year), 0.0)) \
            / (1 + rate) ** t(year)
    for year, amount in dev.items():
        nav["elang"] -= amount / (1 + rate) ** t(year)
    last = max(y for (_, y) in acc)
    last = max([last] + list(dev))
    overhead = sum(inp["ga_usd"] * (0.5 if y == y0 else 1.0) * _grow(inp, y, y0)
                   / (1 + rate) ** t(y) for y in range(y0, last + 1))
    assets = nav["bh"] + nav["elang"] * risk + (0.0 if wc else (inp["inventory_usd"] or 0.0))
    equity = (assets - overhead) * fx + bridge["cash"] - bridge["debt"] - bridge["minority"]
    return {"per_share": equity / bridge["shares"], "nav_usd": nav, "overhead_usd": overhead}


def compare(inp, bridge, fx, production_per_share):
    ref = value(inp, bridge, fx)
    gap = abs(ref["per_share"] - production_per_share) / abs(production_per_share) \
        if production_per_share else None
    return {"status": "agrees" if gap is not None and gap <= TOLERANCE else "differs",
            "reference_per_share": ref["per_share"],
            "production_per_share": production_per_share, "relative_gap": gap,
            "tolerance": TOLERANCE, "reference_nav_usd": ref["nav_usd"],
            "method": "app.reference_lom: independent physical-to-NAV implementation"}
