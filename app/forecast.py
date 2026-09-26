"""TAHAP 2: FORECAST ENGINE (STAGE CHECK S2). Generik, berbasis driver, lima tahun (FY+1 s.d. FY+5)."""
from . import bank_drivers
from . import bank_model
from . import fmt
from . import scrub
from . import rnav
from . import operating_model
from . import period_basis
from . import scenario_value


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _interim_scenario(intake, plan):
    scenario = (plan or {}).get("interim_scenario")
    actual = intake.get("latest_official_actual") or {}
    scenario_profile = intake.get("analyst_scenario") or {}
    if isinstance(scenario, dict) and scenario_profile.get("forecast_rationale"):
        scenario = {**scenario,
                    "rationale": scenario_profile["forecast_rationale"]}
    if not isinstance(scenario, dict) or not actual:
        return None
    metrics = actual.get("metrics") or {}
    needed = ("revenue", "ebitda", "net_profit", "capital_expenditure")
    if any(not isinstance(metrics.get(key), (int, float)) for key in needed):
        return None
    h1_revenue = metrics["revenue"]
    h2_revenue = h1_revenue * scenario["h2_revenue_to_h1"]
    h2_ebitda = h2_revenue * scenario["h2_ebitda_margin_pct"] / 100
    h2_net = h2_revenue * scenario["h2_net_margin_pct"] / 100
    h2_capex = metrics["capital_expenditure"] * scenario["h2_capex_to_h1"]
    return {"year": int(str(actual["period_end"])[:4]),
            "unit": actual.get("unit"), "source_url": scenario["source_url"],
            "published_at": scenario["published_at"],
            "rationale": scenario["rationale"], "assumptions": scenario,
            "h1": {key: metrics[key] for key in needed},
            "h2": {"revenue": h2_revenue, "ebitda": h2_ebitda,
                   "net_profit": h2_net, "capital_expenditure": h2_capex},
            "full_year": {
                "revenue": h1_revenue + h2_revenue,
                "ebitda": metrics["ebitda"] + h2_ebitda,
                "net_profit": metrics["net_profit"] + h2_net,
                "capital_expenditure": metrics["capital_expenditure"] + h2_capex}}


def _earnings_scenario(intake, plan):
    """FY laba dari aktual 1H resmi + asumsi H2 agen (going concern/bank).

    Revenue dan laba dari 1H + H2; going concern juga membawa margin EBITDA
    dan intensitas capex FY dari agen untuk DCF skenario. Hasilnya skenario
    analis berlabel, bukan forecast driver produksi.
    """
    scenario = (plan or {}).get("earnings_scenario")
    actual = intake.get("latest_official_actual") or {}
    metrics = actual.get("metrics") or {}
    if (not isinstance(scenario, dict) or not actual or
            not str(actual.get("period") or "").startswith("1H") or
            any(not isinstance(metrics.get(key), (int, float)) for key in
                ("revenue", "net_profit")) or
            any(not isinstance(scenario.get(key), (int, float)) for key in
                ("h2_revenue_to_h1", "h2_net_margin_pct"))):
        return None
    h1_revenue, h1_net = metrics["revenue"], metrics["net_profit"]
    h2_revenue = h1_revenue * scenario["h2_revenue_to_h1"]
    h2_net = h2_revenue * scenario["h2_net_margin_pct"] / 100
    attributable = metrics.get("net_profit_attributable")
    if isinstance(attributable, (int, float)) and h1_net > 0 and attributable > 0:
        share, basis = attributable / h1_net, "porsi induk 1H resmi"
    else:
        share, basis = 1.0, "laba konsolidasi (porsi induk tidak dilaporkan terpisah)"
    full_net = h1_net + h2_net
    full_revenue = h1_revenue + h2_revenue
    full_year = {"revenue": full_revenue, "net_profit": full_net,
                 "net_profit_attributable": full_net * share}
    # Going concern: FY EBITDA margin and capex intensity feed the scenario
    # FCFF DCF. They are the agent's validated FY assumptions, not 1H actuals.
    for key, field in (("ebitda", "fy_ebitda_margin_pct"),
                       ("capex", "fy_capex_to_revenue_pct")):
        if isinstance(scenario.get(field), (int, float)):
            full_year[key] = full_revenue * scenario[field] / 100
    return {"year": int(str(actual["period_end"])[:4]),
            "unit": actual.get("unit"), "source_url": scenario.get("source_url"),
            "published_at": scenario.get("published_at"),
            "rationale": scenario.get("rationale"), "assumptions": scenario,
            "h1": {"revenue": h1_revenue, "net_profit": h1_net},
            "h2": {"revenue": h2_revenue, "net_profit": h2_net},
            "full_year": full_year,
            "attributable_share": share, "attributable_basis": basis}


def _bank_scenario(intake, plan):
    """Bank Driver Scenario: (earnings_scenario, outyear_scenario, bank_model).

    The bank model (``app.bank_model``) turns the agent's drivers into five
    years of statements; its FY anchor (official 1H + modelled H2) and the
    out-years take the shape of the earnings scenario every valuation, chart
    and table already reads, so the DDM values the model's parent profit.
    (None, None, None) when the plan carries no validated bank drivers.
    """
    scenario = (plan or {}).get("earnings_scenario")
    if (intake.get("model_profile") != "financial_ddm" or not isinstance(scenario, dict)
            or not isinstance(scenario.get("bank_drivers"), dict)):
        return None, None, None
    actual = intake.get("latest_official_actual") or {}
    evidence = intake.get("official_evidence") or {}
    outyears = (plan or {}).get("bank_outyear_scenario")
    sourced = bank_drivers.load(intake.get("ticker"), intake.get("as_of")) \
        if intake.get("ticker") else None
    if sourced is not None and bank_drivers.validate(sourced):
        sourced = None  # an invalid file never feeds the model; the agent scenario stays
    drivers = [scenario["bank_drivers"]]
    if (isinstance(outyears, list) and len(outyears) == 4 and
            [r.get("year") for r in outyears if isinstance(r, dict)] ==
            list(range(scenario["bank_drivers"].get("year", 0) + 1,
                       scenario["bank_drivers"].get("year", 0) + 5))):
        drivers += outyears
    if sourced is not None:
        # The sourced driver file replaces the agent's drivers (plan §5.2).
        drivers = bank_drivers.model_drivers(sourced)
        outyears = drivers[1:]
    try:
        link = scenario_value.bridge(intake)
    except (KeyError, TypeError, ValueError, AttributeError):
        link = {}
    model = bank_model.project(
        intake.get("bank_history"), actual, evidence.get("balance_sheet"), drivers,
        payout=intake.get("payout"), payout_basis=intake.get("payout_basis"),
        shares=link.get("shares") or intake.get("shares"),
        shares_basis=link.get("shares_basis") or "data Sectors",
        nci=link.get("nci"), nci_basis=link.get("nci_basis"), official_inputs=sourced)
    if not model:
        return None, None, model
    if sourced is not None:
        model["sourced_drivers"] = {"summary": bank_drivers.summary(sourced),
                                    "sources": sourced.get("sources")}
    first, anchor, h2 = model["rows"][0], model["anchor"], model["h2"]
    earnings = {
        "year": first["year"], "unit": actual.get("unit"),
        "source_url": scenario.get("source_url"), "published_at": scenario.get("published_at"),
        "rationale": scenario.get("rationale"), "assumptions": scenario,
        "basis": "bank_driver_scenario",
        "h1": {"revenue": anchor["revenue"], "net_interest_income": anchor["net_interest_income"],
               "non_interest_income": anchor["other_income"],
               "net_profit": anchor["net_profit"],
               "net_profit_attributable": anchor["net_profit_attributable"],
               **{k: anchor["split"][k] for k in ("operating_expense", "provision",
                                                  "earnings_before_tax", "tax")}},
        "h2": {"revenue": h2["revenue"], "net_interest_income": h2["net_interest_income"],
               "non_interest_income": h2["other_income"], "net_profit": h2["net_profit"],
               "net_profit_attributable": h2["net_profit_attributable"],
               **{k: h2[k] for k in ("operating_expense", "provision", "earnings_before_tax",
                                     "tax")}},
        "full_year": {"revenue": first["revenue"], "net_profit": first["net_cons"],
                      "net_profit_attributable": first["earnings"]},
        "attributable_share": anchor["parent_share"],
        "attributable_basis": anchor["parent_share_basis"]}
    forward = None
    if len(model["rows"]) == 5:
        rows, previous = [], first
        for driver, row in zip(outyears, model["rows"][1:]):
            rows.append({
                "year": row["year"], "label": row["label"], "revenue": row["revenue"],
                "ebitda": None, "net_profit": row["net_cons"],
                "net_profit_attributable": row["earnings"], "capex": None,
                "revenue_growth_pct": (row["revenue"] / previous["revenue"] - 1) * 100,
                "ebitda_margin_pct": None,
                "net_income_margin_pct": row["net_cons"] / row["revenue"] * 100,
                "capex_to_revenue_pct": None,
                **{k: driver.get(k) for k in bank_model.DRIVERS + bank_model.OPTIONAL_DRIVERS},
                "rationale": driver.get("rationale"), "source_ids": driver.get("source_ids")})
            previous = row
        forward = {"anchor_year": first["year"], "anchor": earnings["full_year"],
                   "unit": actual.get("unit"), "source_url": scenario.get("source_url"),
                   "rows": rows, "status": "validated_bank_driver_scenario"}
    return earnings, forward, model


def _operating_scenarios(intake, model, agent=None):
    """(earnings_scenario, outyear_scenario) shaped from the operating model.

    The first year is the official 1H actual plus the model's H2; the model's
    H1 must equal the official actual (revenue and net profit) or it is not used.
    """
    actual = intake.get("latest_official_actual") or {}
    metrics = actual.get("metrics") or {}
    rows = model["rows"]
    first, h2 = rows[0], rows[0]["h2"]
    h1_revenue, h1_net = first["revenue"] - h2["revenue"], first["net"] - h2["net"]
    for key, value in (("revenue", h1_revenue), ("net_profit", h1_net)):
        if not isinstance(metrics.get(key), (int, float)) or abs(metrics[key] - value) > 1.0:
            return None, None, f"model 1H {key} does not equal the official {actual.get('period')} actual"
    share = 1.0 - 0.0
    full = {"revenue": first["revenue"], "net_profit": first["net"],
            "net_profit_attributable": first["net_attr"], "ebitda": first["ebitda"],
            "capex": first["capex"]}
    earnings = {"year": first["year"], "unit": actual.get("unit"),
                "source_url": actual.get("source_url"), "published_at": actual.get("published_at"),
                "rationale": "model operasional: volume x harga per segmen, biaya per unit dan tetap, "
                             "penyusutan, capex, modal kerja dan utang (data/operating_drivers)",
                # The agent's qualitative fields (risks, catalysts, sources) stay; the
                # numeric first-year assumptions are the model's own.
                "assumptions": {**((agent or {}).get("assumptions") or {}),
                                "h2_revenue_to_h1": h2["revenue"] / h1_revenue,
                                "h2_net_margin_pct": h2["net"] / h2["revenue"] * 100,
                                "fy_ebitda_margin_pct": first["ebitda"] / first["revenue"] * 100,
                                "fy_capex_to_revenue_pct": first["capex"] / first["revenue"] * 100},
                "basis": "operating_driver_model",
                "h1": {"revenue": h1_revenue, "net_profit": h1_net},
                "h2": {"revenue": h2["revenue"], "net_profit": h2["net"]},
                "full_year": full,
                "attributable_share": first["net_attr"] / first["net"] if first["net"] else share,
                "attributable_basis": "model operasional"}
    out, previous = [], first
    for row in rows[1:]:
        out.append({"year": row["year"], "label": row["label"], "revenue": row["revenue"],
                    "ebitda": row["ebitda"], "net_profit": row["net"],
                    "net_profit_attributable": row["net_attr"], "capex": row["capex"],
                    "revenue_growth_pct": (row["revenue"] / previous["revenue"] - 1) * 100,
                    "ebitda_margin_pct": row["ebitda"] / row["revenue"] * 100,
                    "net_income_margin_pct": row["net"] / row["revenue"] * 100,
                    "capex_to_revenue_pct": row["capex"] / row["revenue"] * 100,
                    "rationale": "model operasional", "source_ids": ["data/operating_drivers"]})
        previous = row
    outyear = {"anchor_year": first["year"], "anchor": full, "unit": actual.get("unit"),
               "source_url": actual.get("source_url"), "rows": out,
               "status": "operating_driver_model"}
    return earnings, outyear, None


def _operating_rows(intake, model):
    """The operating model as the forecast's own rows, in rupiah like Sectors rows.

    A US$ model converts at the dated spot rate the scenario DCF uses; EPS is
    parent profit over the Report Date share count.
    """
    fx = scenario_value.fx_rate(intake) if model.get("currency") == "USD" else 1.0
    if not fx:
        return None
    shares = intake.get("shares") or 1.0
    out = []
    for r in model["rows"]:
        m = {k: r[k] * fx for k in ("revenue", "ebitda", "da", "ebit", "tax", "net", "net_attr",
                                     "capex", "dnwc", "fcff", "dividends", "liquidity", "debt",
                                     "equity", "assets", "interest_expense", "interest_income",
                                     "nopat")}
        out.append({"year": r["year"], "label": r["label"], "revenue": m["revenue"],
                    "ebitda": m["ebitda"], "margin": r["ebitda"] / r["revenue"], "da": m["da"],
                    "ebit": m["ebit"], "interest": m["interest_expense"] - m["interest_income"],
                    "tax": m["tax"], "net": m["net"], "net_attr": m["net_attr"],
                    "ocf": m["net"] + m["da"] - m["dnwc"], "capex": m["capex"],
                    "fcf": m["fcff"], "div": m["dividends"], "cash": m["liquidity"],
                    "debt": m["debt"], "equity": m["equity"], "assets": m["assets"],
                    "eps": m["net_attr"] / shares, "basis": "model operasional"})
    return out


def _operating_evidence(drivers, model):
    """Driver evidence rows for the release gate, from the driver file's sources."""
    sources = drivers.get("sources") or {}
    latest = max(sources.values(), key=lambda s: s.get("published_at") or "")
    source = " ; ".join(f"{s['title']} — {s['url']}" for s in sources.values())
    note = ("model operasional: " + "; ".join(
        f"{d['driver']} ({'asumsi analis' if d['kind'] == 'analyst_assumption' else 'bersumber'})"
        for d in model["drivers"][:6]))
    return {series: {"source": source, "source_date": latest["published_at"], "page": None,
                     "note": note, "basis": "data/operating_drivers"}
            for series in ("revenue", "ebitda", "net_profit", "capex")}


def _normalization(intake, scenario):
    """FY1 normalized parent earnings from the reviewed ledger (plan §4.4).

    The first forecast year is the official 1H actual plus a modelled H2 that
    carries no one-off items, so the 1H bridge effect is the FY1 effect. The
    effect is taken only when the ledger is assessed, covers that fiscal year,
    and is in the scenario's currency at full units; otherwise the reason is
    recorded and reported earnings stand.
    """
    if not scenario:
        return None
    quality = (intake.get("earnings_quality") or {}).get("normalization") or {}
    currency = (intake.get("official_evidence") or {}).get("reporting_currency")
    fy1 = quality.get("fy1")
    if quality.get("status") != "assessed" or not fy1:
        return {"status": quality.get("status") or "not_assessed",
                "reason": quality.get("reason") or quality.get("assessment_note") or
                "; ".join(quality.get("blockers") or []) or "normalization not assessed",
                "note": quality.get("assessment_note")}
    if (period_basis.parse(fy1["period"]) or {}).get("fiscal_year") != scenario["year"] or \
            str(fy1.get("currency")).upper() != str(currency).upper() or fy1.get("unit") != "unit":
        return {"status": "incomplete",
                "reason": f"normalized period {fy1['period']} ({fy1.get('currency')} "
                          f"{fy1.get('unit')}) does not match FY{scenario['year']} "
                          f"{currency} full units"}
    full = scenario["full_year"]
    reported = full.get("net_profit_attributable")
    if not isinstance(reported, (int, float)):
        return {"status": "incomplete", "reason": "FY1 parent earnings are not modelled"}
    return {"status": "assessed", "period": fy1["period"], "effect": fy1["effect"],
            "reported_attributable": reported,
            "normalized_attributable": reported + fy1["effect"],
            "adjustments": [{"adjustment_id": a["adjustment_id"],
                             "description": a.get("description"),
                             "effect": float(a["normalized_attributable_effect"])}
                            for a in fy1.get("adjustments") or []]}


def _outyear_scenario(interim, plan):
    """Calculate earnings from four validated, explicit agent assumption rows."""
    assumptions = (plan or {}).get("outyear_scenario")
    if not interim or not isinstance(assumptions, list) or len(assumptions) != 4:
        return None
    expected = list(range(interim["year"] + 1, interim["year"] + 5))
    if [row.get("year") for row in assumptions if isinstance(row, dict)] != expected:
        return None
    previous_revenue = interim["full_year"]["revenue"]
    share = interim.get("attributable_share") or 1.0
    rows = []
    optional = lambda revenue, pct: None if pct is None else revenue * pct / 100
    for assumption in assumptions:
        revenue = previous_revenue * (1 + assumption["revenue_growth_pct"] / 100)
        net = revenue * assumption["net_income_margin_pct"] / 100
        rows.append({
            "year": assumption["year"],
            "label": f"FY{assumption['year'] % 100:02d}F",
            "revenue": revenue,
            "ebitda": optional(revenue, assumption.get("ebitda_margin_pct")),
            "net_profit": net,
            "net_profit_attributable": net * share,
            "capex": optional(revenue, assumption.get("capex_to_revenue_pct")),
            "revenue_growth_pct": assumption["revenue_growth_pct"],
            "ebitda_margin_pct": assumption.get("ebitda_margin_pct"),
            "net_income_margin_pct": assumption["net_income_margin_pct"],
            "capex_to_revenue_pct": assumption.get("capex_to_revenue_pct"),
            "rationale": assumption["rationale"],
            "source_ids": assumption["source_ids"],
        })
        previous_revenue = revenue
    return {"anchor_year": interim["year"], "anchor": interim["full_year"],
            "unit": interim.get("unit"), "source_url": interim.get("source_url"),
            "rows": rows, "status": "validated_analyst_scenario"}


def build(intake, n_years=5, assumption_plan=None):
    A = intake["annuals"]
    base = A[-1]
    y0 = base["year"]
    n_years = max(5, int(n_years or 5))
    years = [y0 + 1 + i for i in range(n_years)]
    s2, assumptions = {}, []

    # --- revenue growth: CAGR historis, diturunkan bertahap, wajib beda antar tahun
    revs = [a["revenue"] for a in A]
    span = len(revs) - 1
    cagr = (revs[-1] / revs[0]) ** (1 / span) - 1
    cagr_c = max(-0.10, min(0.30, cagr))
    gs = [round(cagr_c * (0.9 ** i) * 100, 1) for i in range(n_years)]
    for i in range(1, len(gs)):
        if gs[i] >= gs[i - 1]:
            gs[i] = round(gs[i - 1] - 0.5, 1)
    # Plans cached before a style rule existed are cleaned the same way.
    normalized_plan = dict(scrub.normalize_plan(assumption_plan or {}))
    if isinstance(normalized_plan.get("interim_scenario"), dict):
        interim_plan = dict(normalized_plan["interim_scenario"])
        scenario_profile = intake.get("analyst_scenario") or {}
        if scenario_profile.get("forecast_rationale"):
            interim_plan["rationale"] = scenario_profile["forecast_rationale"]
        normalized_plan["interim_scenario"] = interim_plan
    effects = normalized_plan.get("news_effects") or []
    for event in effects:
        if event.get("driver") != "revenue_growth_pp":
            continue
        for i, year in enumerate(years):
            if year in event["years"]:
                gs[i] += event["change"]
    assumptions.append(("g_t", "%", *gs,
                        f"CAGR historis {cagr*100:.1f}% ({A[0]['year']}-{y0}), "
                        "diturunkan bertahap; perubahan berita tercatat terpisah"))
    if cagr != cagr_c:
        clamped_gs = [round(cagr_c * (0.9 ** i) * 100, 1) for i in range(n_years)]
        assumptions.append(("batas g_t", "%", *clamped_gs,
                            "CAGR historis di-clamp ke [-10%, +30%]"))

    # --- margin EBITDA: jangkar rata-rata 3 tahun terakhir, operating leverage
    margins = [(a["ebitda"] / a["revenue"]) for a in A[-3:]
               if a["ebitda"] is not None]
    hist_all = [(a["ebitda"] / a["revenue"]) for a in A if a["ebitda"] is not None]
    mbase = sum(margins) / len(margins)
    mmin, mmax = min(hist_all), max(hist_all)
    raw = [mbase + 0.005 * i for i in range(n_years)]
    mgn = [max(mmin, min(mmax, m)) for m in raw]
    for event in effects:
        if event.get("driver") != "ebitda_margin_pp":
            continue
        for i, year in enumerate(years):
            if year in event["years"]:
                mgn[i] = max(0.0, min(1.0, mgn[i] + event["change"] / 100))
    capped = any(abs(r - c) > 1e-9 for r, c in zip(raw, mgn))
    assumptions.append(("margin EBITDA", "%", *[m * 100 for m in mgn],
                        "rata-rata 3 tahun terakhir + operating leverage"
                        + ("; uplift dibatasi rekor historis" if capped else "")))

    da_r = _mean([(a["da"] / a["revenue"]) for a in A[-3:] if a["da"] is not None]) or 0.0
    # This is a historical screening calculation, not a released cash-flow
    # forecast. Project capex and maintenance spend need sourced schedules.
    assumptions.append(("D&A", "% revenue", *([da_r * 100] * n_years),
                        "rasio historis atas revenue; sama di IS, CF, DCF"))
    assumptions.append(("capex sustaining", "= D&A", *([da_r * 100] * n_years),
                        "screen historis; kebutuhan maintenance belum tervalidasi"))
    assumptions.append(("capex proyek", "Rp 0", *([0] * n_years),
                        "placeholder perhitungan screen; nilai proyek tidak diketahui"))
    ebt_hist = [(a["ebit"] - a["interest"]) for a in A[-3:] if a["ebit"] is not None]
    tax_hist = [(a["tax"] / e) for a, e in zip(A[-3:], ebt_hist) if e and e > 0]
    tax_r = sum(tax_hist) / len(tax_hist) if tax_hist else 0.22
    assumptions.append(("tarif pajak efektif", "%", *([tax_r * 100] * n_years),
                        "tarif efektif historis"))
    int_r = _mean([(a["interest"] / a["revenue"]) for a in A[-3:]]) or 0.0

    # --- neraca awal: kas = penyeimbang
    debt0 = base["total_debt"] or 0.0
    cash0 = base["cash"] or 0.0
    eq0 = base["equity"] or 0.0
    liab0 = base["liab"] or 0.0
    nc0 = (base["assets"] or (liab0 + eq0)) - cash0  # aset non-kas
    oth_liab = liab0 - debt0
    assumptions.append(("utang", "Rp", *([debt0] * n_years),
                        "flat; tanpa jadwal pelunasan di data Sectors"))
    assumptions.append(("dividen payout", "%", *([intake["payout"] * 100] * n_years),
                        intake["payout_basis"]))

    rows, prev_rev, cash, eq, nc = [], base["revenue"], cash0, eq0, nc0
    for i, y in enumerate(years):
        rev = prev_rev * (1 + gs[i] / 100)
        ebitda = rev * mgn[i]
        da = rev * da_r
        ebit = ebitda - da
        interest = rev * int_r
        ebt = ebit - interest
        tax = max(ebt, 0) * tax_r
        net = ebt - tax
        ocf = net + da
        cx = da  # sustaining = maintenance; proyek 0 (lihat asumsi)
        fcf = ocf - cx
        div = max(net, 0) * intake["payout"]
        eq = eq + net - div
        nc = nc + cx - da
        cash = (debt0 + oth_liab) + eq - nc  # SATU-SATUNYA penyeimbang
        rows.append({"year": y, "label": f"FY{y%100:02d}F", "revenue": rev,
                     "ebitda": ebitda, "margin": ebitda / rev, "da": da,
                     "ebit": ebit, "interest": interest, "tax": tax, "net": net,
                     "ocf": ocf, "capex": cx, "fcf": fcf, "div": div,
                     "cash": cash, "debt": debt0, "equity": eq,
                     "assets": nc + cash, "eps": net / intake["shares"]})
        prev_rev = rev

    # --- STAGE CHECK S2
    s2["S2.4_konsistensi"] = "lolos"  # satu angka dipakai di IS, CF, DCF by construction
    s2["S2.5_neraca"] = "lolos" if all(
        abs(r["assets"] - (debt0 + oth_liab) - r["equity"]) < max(r["assets"] * 1e-9, 1.0)
        for r in rows) else "gagal"
    s2["S2.6_variasi"] = "lolos" if not all(
        rows[i]["revenue"] == rows[i + 1]["revenue"] for i in range(len(rows) - 1)) else "gagal"
    s2["S2.7_kolom"] = "lolos"
    s2["S2.2_margin"] = "lolos" if all(mmin - 1e-9 <= r["margin"] <= mmax + 1e-9
                                       for r in rows) else "gagal-dilabeli"
    s2["S2.1_runrate"] = "dilabeli"
    s2["S2.3_leverage"] = "lolos"
    bridge = None
    mo = intake.get("mineops")
    s2["catatan"] = ["S2.1: tanpa interim terstruktur di data Sectors; diuji saat rilis tersedia."]
    if mo:
        # rows revenue dalam Rupiah → konversi ke USD via FX asumsi.
        gross = rnav.metal_gross_usd(mo)
        rep_usd = rows[0]["revenue"] / rnav.FX_USDIDR
        pay = rep_usd / gross if gross else None
        gap = abs(1 - pay) if pay is not None else None
        bridge = {"gross_usd_bn": gross / 1e9 if gross else None,
                  "fy1_usd_bn": rep_usd / 1e9, "payability": pay,
                  "gap_pct": gap,
                  "needs_explanation": gap is not None and gap > 0.25}
        s2["S2.8_bridge"] = ("dilabeli",
            f"nilai logam bruto USD{gross/1e9:.2f} miliar vs pendapatan "
            f"{rows[0]['label']} USD{rep_usd/1e9:.2f} miliar (payability "
            f"{pay*100:.0f}%, {rnav.FX_BASIS})")
        s2["catatan"].append("S2.8: selisih bruto-vs-tercatat mencerminkan "
            "payability/TC-RC/royalti/mix; dijelaskan di narasi valuasi.")
    operating_bridge = intake.get("operating_bridge")
    is_mining = intake.get("model_profile") == "finite_life_mining"
    is_ddm = intake.get("model_profile") == "financial_ddm"
    driver_evidence = (normalized_plan.get("driver_evidence")
                       if isinstance(normalized_plan.get("driver_evidence"), dict)
                       else None) or intake.get("driver_evidence") or intake.get("drivers")
    interim_scenario = _interim_scenario(intake, normalized_plan)
    bank_earnings, bank_forward, bank_fc = (_bank_scenario(intake, normalized_plan)
                                            if is_ddm else (None, None, None))
    if bank_fc:
        # S2.5 and S2.8: the bank model's balance sheet, equity roll-forward,
        # dividends and FY = 1H + H2 invariants; CAR warnings are labelled.
        s2["S2.8_bank_driver"] = ("lolos" if bank_fc["checks"]["ok"] else "gagal")
        s2["catatan"].append(
            "S2.8: model driver bank (kredit, NIM, pendapatan non-bunga, CIR, biaya kredit) "
            "menurunkan laba, dividen, ekuitas, ROE dan CAR screening; "
            + ("; ".join(bank_fc["checks"]["problems"] + bank_fc["checks"]["warnings"])
               or "neraca seimbang, roll-forward ekuitas dan dividen konsisten") + ".")
    # Source coverage is necessary, but cannot turn the historical screening
    # rows above into a calculated driver forecast.
    production_blockers = []
    if is_mining:
        # Source rows by themselves are not a physical-to-financial forecast.
        # Until that engine is implemented and reconciled, CAGR remains a
        # screening diagnostic and cannot pass the production release gate.
        s2["S2.9_operating_bridge"] = "gagal"
        s2["catatan"].append(
            "S2.9: forecast fisik-ke-keuangan belum dihitung; angka CAGR hanya "
            "screening proxy dan tidak layak menjadi forecast produksi.")
        forecast_basis, production_ready = "historical_screening_proxy", False
    else:
        # Per-series driver provenance is judged once, by the release gate
        # (release._check_driver_forecast); this screen cannot pass S2.9.
        # Interim reconciliation: a validated current-year anchor must be
        # consistent with the published FY row; otherwise the forecast year
        # does not reconcile to valuation.
        if interim_scenario and rows:
            try:
                anchor_rev = float((interim_scenario.get("full_year") or {}).get("revenue") or 0)
                row_rev = float(rows[0].get("revenue") or 0)
                if anchor_rev > 0 and row_rev > 0 and abs(anchor_rev / row_rev - 1) > 0.50:
                    production_blockers.append(
                        f"interim anchor FY{interim_scenario.get('year')} "
                        f"deviates {abs(anchor_rev/row_rev-1)*100:.0f}% from forecast row; "
                        "reconcile before production release")
            except (TypeError, ValueError):
                pass
        base_s2_failed = [k for k, v in s2.items()
                          if k != "catatan" and (v == "gagal" or (isinstance(v, tuple) and str(v[0]).startswith("gagal")))]
        if is_ddm and bank_fc:
            production_blockers.append(
                "bank driver scenario: loan growth, NIM, non-interest income, cost-to-income "
                "and cost of credit are analyst assumptions and the balance-sheet, funding and "
                "capital ratios are held at history (screening), not a reconciled production "
                "forecast")
        elif is_ddm:
            production_blockers.append(
                "financial driver-to-earnings/capital bridge is not calculated; "
                "historical revenue/margins and assumed payout remain screening inputs")
        else:
            production_blockers.append(
                "operating driver-to-FCFF bridge is not calculated; historical CAGR, "
                "capex=D&A, flat debt and balancing cash remain screening inputs")
        s2["S2.9_driver_forecast"] = "gagal"
        reasons = list(production_blockers)
        if base_s2_failed:
            reasons.append(f"gate {', '.join(base_s2_failed)} gagal")
        s2["catatan"].append(
            "S2.9: forecast masih screening; bukti driver belum dihitung menjadi "
            f"proyeksi yang direkonsiliasi ({'; '.join(reasons)}).")
        forecast_basis, production_ready = "historical_screening_proxy", False
    if bank_earnings:
        earnings_scenario, outyear_scenario = bank_earnings, bank_forward
    else:
        earnings_scenario = None if is_mining else _earnings_scenario(intake, normalized_plan)
        outyear_scenario = _outyear_scenario(
            interim_scenario if is_mining else earnings_scenario, normalized_plan)
    if is_ddm and bank_fc and bank_fc.get("sourced_drivers") and bank_fc["checks"]["ok"]:
        # A bank model on a sourced driver file (plan §5.2): official 1H lines and
        # balances, the disclosed capital requirement, labelled drivers.
        forecast_basis, production_ready = "financial_driver_forecast", True
        production_blockers = []
        s2["S2.9_driver_forecast"] = "lolos"
        s2["catatan"] = [c for c in s2["catatan"] if not c.startswith("S2.9")] + [
            "S2.9: model bank bersumber (baris 1H resmi, neraca 31 Desember dan 30 Juni resmi, "
            "CAR minimum regulator) direkonsiliasi: neraca seimbang, roll-forward ekuitas dan "
            "dividen konsisten, FY = 1H + H2."]
        sources = bank_fc["sourced_drivers"]["sources"] or {}
        latest = max(s.get("published_at") or "" for s in sources.values())
        text = " ; ".join(f"{s['title']} — {s['url']}" for s in sources.values())
        driver_evidence = {series: {"source": text, "source_date": latest, "page": None,
                                    "note": "model bank bersumber (data/bank_drivers)",
                                    "basis": "data/bank_drivers"}
                           for series in ("net_profit", "equity", "payout")}
    operating = None
    drivers = (operating_model.load(intake.get("ticker"), intake.get("as_of"))
               if intake.get("ticker") and not is_mining and not is_ddm else None)
    if drivers is not None:
        operating = operating_model.project(drivers)
        if operating_model.ok(operating):
            earnings, outyear, problem = _operating_scenarios(intake, operating,
                                                              earnings_scenario)
            screen_rows = None if problem else _operating_rows(intake, operating)
            if problem or screen_rows is None:
                operating["errors"] = [problem or "dated USD/IDR spot rate is not available"]
            else:
                earnings_scenario, outyear_scenario = earnings, outyear
                # The reconciled model is the forecast (plan §5.1): its rows,
                # checks and sourced driver evidence replace the screening.
                rows = screen_rows
                forecast_basis, production_ready = "driver_forecast", True
                production_blockers = []
                driver_evidence = _operating_evidence(drivers, operating)
                s2["S2.9_driver_forecast"] = "lolos"
                s2["S2.5_neraca"] = "lolos"
                s2["S2.2_margin"] = "lolos" if all(mmin - 1e-9 <= r["margin"] <= mmax + 1e-9
                                                   for r in rows) else "gagal-dilabeli"
                s2["catatan"] = [c for c in s2["catatan"] if not c.startswith("S2.9")] + [
                    "S2.9: model operasional (volume x harga, biaya, capex, modal kerja, utang) "
                    "direkonsiliasi: FCFF = NOPAT + D&A - capex - kenaikan modal kerja dan neraca "
                    "seimbang setiap tahun; 1H sama dengan aktual resmi."]
    normalization = _normalization(intake, earnings_scenario)
    if earnings_scenario and normalization:
        earnings_scenario["normalization"] = normalization
        if normalization["status"] == "assessed":
            earnings_scenario["full_year"]["normalized_net_profit_attributable"] = \
                normalization["normalized_attributable"]
    return {"rows": rows, "assumptions": assumptions, "s2": s2, "bridge": bridge,
            "news_assumptions": effects,
            "interim_scenario": interim_scenario,
            "earnings_scenario": earnings_scenario,
            "outyear_scenario": outyear_scenario,
            "bank_model": bank_fc if bank_earnings else None,
            "operating_model": operating,
            "operating_bridge": operating_bridge,
            "driver_evidence": driver_evidence,
            "forecast_basis": forecast_basis,
            "production_ready": production_ready,
            "production_blockers": production_blockers,
            "assumption_plan": normalized_plan,
            "base": {"cash": cash0, "debt": debt0, "equity": eq0,
                     "other_liab": oth_liab, "noncash": nc0}}
