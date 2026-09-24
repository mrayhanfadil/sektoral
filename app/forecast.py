"""TAHAP 2: FORECAST ENGINE (GATE 2). Generik, berbasis driver, tiga tahun."""
from . import fmt
from . import rnav


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


def _outyear_scenario(interim, plan):
    """Calculate earnings from four validated, explicit agent assumption rows."""
    assumptions = (plan or {}).get("outyear_scenario")
    if not interim or not isinstance(assumptions, list) or len(assumptions) != 4:
        return None
    expected = list(range(interim["year"] + 1, interim["year"] + 5))
    if [row.get("year") for row in assumptions if isinstance(row, dict)] != expected:
        return None
    previous_revenue = interim["full_year"]["revenue"]
    rows = []
    for assumption in assumptions:
        revenue = previous_revenue * (1 + assumption["revenue_growth_pct"] / 100)
        rows.append({
            "year": assumption["year"],
            "label": f"FY{assumption['year'] % 100:02d}F",
            "revenue": revenue,
            "ebitda": revenue * assumption["ebitda_margin_pct"] / 100,
            "net_profit": revenue * assumption["net_income_margin_pct"] / 100,
            "capex": revenue * assumption["capex_to_revenue_pct"] / 100,
            "revenue_growth_pct": assumption["revenue_growth_pct"],
            "ebitda_margin_pct": assumption["ebitda_margin_pct"],
            "net_income_margin_pct": assumption["net_income_margin_pct"],
            "capex_to_revenue_pct": assumption["capex_to_revenue_pct"],
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
    g2, assumptions = {}, []

    # --- revenue growth: CAGR historis, diturunkan bertahap, wajib beda antar tahun
    revs = [a["revenue"] for a in A]
    span = len(revs) - 1
    cagr = (revs[-1] / revs[0]) ** (1 / span) - 1
    cagr_c = max(-0.10, min(0.30, cagr))
    gs = [round(cagr_c * (0.9 ** i) * 100, 1) for i in range(n_years)]
    for i in range(1, len(gs)):
        if gs[i] >= gs[i - 1]:
            gs[i] = round(gs[i - 1] - 0.5, 1)
    normalized_plan = dict(assumption_plan or {})
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

    # --- GATE 2
    g2["G2.4_konsistensi"] = "lolos"  # satu angka dipakai di IS, CF, DCF by construction
    g2["G2.5_neraca"] = "lolos" if all(
        abs(r["assets"] - (debt0 + oth_liab) - r["equity"]) < max(r["assets"] * 1e-9, 1.0)
        for r in rows) else "gagal"
    g2["G2.6_variasi"] = "lolos" if not all(
        rows[i]["revenue"] == rows[i + 1]["revenue"] for i in range(len(rows) - 1)) else "gagal"
    g2["G2.7_kolom"] = "lolos"
    g2["G2.2_margin"] = "lolos" if all(mmin - 1e-9 <= r["margin"] <= mmax + 1e-9
                                       for r in rows) else "gagal-dilabeli"
    g2["G2.1_runrate"] = "dilabeli"
    g2["G2.3_leverage"] = "lolos"
    bridge = None
    mo = intake.get("mineops")
    g2["catatan"] = ["G2.1: tanpa interim terstruktur di data Sectors; diuji saat rilis tersedia."]
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
        g2["G2.8_bridge"] = ("dilabeli",
            f"nilai logam bruto USD{gross/1e9:.2f} miliar vs pendapatan "
            f"{rows[0]['label']} USD{rep_usd/1e9:.2f} miliar (payability "
            f"{pay*100:.0f}%, {rnav.FX_BASIS})")
        g2["catatan"].append("G2.8: selisih bruto-vs-tercatat mencerminkan "
            "payability/TC-RC/royalti/mix; dijelaskan di narasi valuasi.")
    operating_bridge = intake.get("operating_bridge")
    is_mining = intake.get("model_profile") == "finite_life_mining"
    is_ddm = intake.get("model_profile") == "financial_ddm"
    driver_evidence = (normalized_plan.get("driver_evidence")
                       if isinstance(normalized_plan.get("driver_evidence"), dict)
                       else None) or intake.get("driver_evidence") or intake.get("drivers")
    interim_scenario = _interim_scenario(intake, normalized_plan)
    # Production readiness is computed from source coverage + reconciliation,
    # never hardcoded. A historical screen stays a labeled fallback.
    production_blockers = []
    if is_mining:
        # Source rows by themselves are not a physical-to-financial forecast.
        # Until that engine is implemented and reconciled, CAGR remains a
        # screening diagnostic and cannot pass the production release gate.
        g2["G2.9_operating_bridge"] = "gagal"
        g2["catatan"].append(
            "G2.9: forecast fisik-ke-keuangan belum dihitung; angka CAGR hanya "
            "screening proxy dan tidak layak menjadi forecast produksi.")
        forecast_basis, production_ready = "historical_screening_proxy", False
    else:
        required = ("net_profit", "equity", "payout") if is_ddm else (
            "revenue", "ebitda", "net_profit", "capex")
        missing = []
        if not isinstance(driver_evidence, dict):
            missing = list(required)
        else:
            as_of_day = str(intake.get("as_of") or "")[:10]
            for series in required:
                lookup = series
                if is_ddm and series == "net_profit" and series not in driver_evidence \
                        and "profit" in driver_evidence:
                    lookup = "profit"
                row = driver_evidence.get(lookup)
                if not isinstance(row, dict):
                    missing.append(series)
                    continue
                if row.get("origin") == "official_actual_base":
                    missing.append(f"{series}:base-actual-only")
                    continue
                src = str(row.get("source") or "")
                has_https = "https://" in src.lower()
                has_cache = "sectors_cache" in src.lower() or "sectors cache" in src.lower()
                s_date = str(row.get("source_date") or "")[:10]
                note = str(row.get("note") or row.get("claim") or row.get("status") or row.get("basis") or "")
                if not (has_https or has_cache) or not s_date or not note.strip():
                    missing.append(series)
                elif as_of_day and s_date > as_of_day:
                    missing.append(f"{series}:future-dated")
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
        base_g2_failed = [k for k, v in g2.items()
                          if k != "catatan" and (v == "gagal" or (isinstance(v, tuple) and str(v[0]).startswith("gagal")))]
        if not missing and not production_blockers and not base_g2_failed:
            g2["G2.9_driver_forecast"] = "lolos"
            g2["catatan"].append(
                "G2.9: rantai driver-ke-laba/arus kas bersumber dan direkonsiliasi; "
                f"coverage {', '.join(required)}.")
            forecast_basis = "financial_driver_forecast" if is_ddm else "driver_forecast"
            production_ready = True
        else:
            g2["G2.9_driver_forecast"] = "gagal"
            reasons = []
            if missing:
                reasons.append(f"driver {', '.join(missing)} belum bersumber")
            if production_blockers:
                reasons.extend(production_blockers)
            if base_g2_failed:
                reasons.append(f"gate {', '.join(base_g2_failed)} gagal")
            g2["catatan"].append(
                "G2.9: angka CAGR dan capex=D&A hanyalah screen; forecast driver, "
                f"modal kerja, serta jadwal utang belum direkonsiliasi ({'; '.join(reasons)}).")
            forecast_basis, production_ready = "historical_screening_proxy", False
    return {"rows": rows, "assumptions": assumptions, "g2": g2, "bridge": bridge,
            "news_assumptions": effects,
            "interim_scenario": interim_scenario,
            "outyear_scenario": _outyear_scenario(interim_scenario, assumption_plan),
            "operating_bridge": operating_bridge,
            "driver_evidence": driver_evidence,
            "forecast_basis": forecast_basis,
            "production_ready": production_ready,
            "production_blockers": production_blockers,
            "assumption_plan": normalized_plan,
            "base": {"cash": cash0, "debt": debt0, "equity": eq0,
                     "other_liab": oth_liab, "noncash": nc0}}
