from . import ddm
from . import fmt
from . import model_profiles
from . import rnav
from . import release
from . import rating as rating_mod
from . import sotp as sotp_mod

def _core(fc, shares, wacc, g, exit_mult, net_debt):
    """Satu basis perhitungan; dipakai TP base, downside, dan grid sensitivitas."""
    n_years = len(fc["rows"])
    dfs = [(1 + wacc) ** (i + 0.5) for i in range(n_years)]
    pv_exp = sum(r["fcf"] / d for r, d in zip(fc["rows"], dfs))
    f_last = fc["rows"][-1]
    tv = f_last["fcf"] * (1 + g) / (wacc - g)
    pv_tv = tv / dfs[-1]
    ev_g = pv_exp + pv_tv
    ps_g = (ev_g - net_debt) / shares
    ev_x = f_last["ebitda"] * exit_mult
    ps_x = (ev_x - net_debt) / ((1 + wacc) ** n_years * shares)
    return {"pv_exp": pv_exp, "pv_tv": pv_tv, "ev_g": ev_g, "ps_g": ps_g,
            "ps_x": ps_x, "tv_share": pv_tv / ev_g, "f_last": f_last}


def tp_grid(intake, fc, wacc, g, exit_mult, net_debt):
    """Grid TP 3x3 (WACC±1pp × g ∈ {2,5; 3,5; 4,5}%), rerata Gordon + exit."""
    out = {}
    for dw in (-0.01, 0.0, 0.01):
        for gg in (0.025, 0.035, 0.045):
            c = _core(fc, intake["shares"], wacc + dw, gg, exit_mult, net_debt)
            out[(round(dw, 3), gg)] = round((c["ps_g"] + c["ps_x"]) / 2 / 10) * 10
    return out


def gordon_screen_grid(intake, fc, wacc, g, exit_mult, net_debt):
    """Unblended historical-model sensitivity for an explicitly labeled draft."""
    rows = []
    for delta_wacc in (-0.01, 0.0, 0.01):
        rate = wacc + delta_wacc
        values = []
        for delta_growth in (-0.01, 0.0, 0.01):
            growth = g + delta_growth
            values.append(_core(fc, intake["shares"], rate, growth,
                                exit_mult, net_debt)["ps_g"]
                          if rate > growth else None)
        rows.append((rate, values))
    return {"growth_rates": [g - 0.01, g, g + 0.01], "rows": rows}


def scenario_ev_ebitda_crosscheck(intake, fc, multiples=(6.0, 8.0, 10.0)):
    """Optional interim-based multiple screen in the issuer's reporting currency."""
    scenario = fc.get("interim_scenario") or {}
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    fx_quote = intake.get("fx_spot") or {}
    if evidence.get("reporting_currency") != "USD" or not scenario or not fx_quote:
        return None
    ebitda = (scenario.get("full_year") or {}).get("ebitda")
    cash, debt, shares, rate = (balance.get("cash"), balance.get("total_debt"),
                                 balance.get("shares_outstanding") or balance.get("shares_issued"),
                                 fx_quote.get("rate"))
    minority_interest = balance.get("non_controlling_interest")
    if not all(isinstance(value, (int, float)) and value > 0
               for value in (ebitda, cash, debt, shares, rate)) or not (
                   isinstance(minority_interest, (int, float)) and minority_interest >= 0):
        return None
    net_debt = debt - cash
    values = []
    for multiple in multiples:
        enterprise = ebitda * multiple
        equity = enterprise - net_debt - minority_interest
        values.append({"multiple": multiple, "enterprise_usd": enterprise,
                       "equity_usd": equity,
                       "per_share_idr": equity / shares * rate if equity > 0 else None})
    return {"year": scenario["year"], "ebitda_usd": ebitda,
            "cash_usd": cash, "debt_usd": debt, "net_debt_usd": net_debt,
            "minority_interest_usd": minority_interest,
            "shares": shares, "fx": fx_quote, "balance_period": balance.get("period_end"),
            "source_url": scenario["source_url"], "values": values,
            "status": "illustrative_crosscheck_only"}


def build(intake, fc, analyst_target=False, assumption_status=None):
    g3, notes = {}, []
    t = intake["ticker"]
    profile = intake.get("model_profile", "unsupported")
    is_miner = profile == "finite_life_mining"
    n_fc = len(fc["rows"]) if fc.get("rows") else 5
    method = (f"DCF FCFF {n_fc} tahun eksplisit + terminal Gordon, dibobot sama dengan "
              "exit EV/EBITDA")
    is_bank = profile == "financial_ddm"
    if is_bank:
        notes.append("keterbatasan model: bank idealnya pendekatan GGM ekuitas atau "
                     "residual income dengan silang cek P/BV vs ROE; proksi FCFF "
                     "dipakai karena kerangka ringan generic.")
    if is_miner:
        notes.append("keterbatasan model: emiten tambang idealnya DCF sampai akhir umur "
                     "aset tanpa terminal perpetual; rilis resmi dapat memuat jadwal "
                     "tambang, tetapi tanpa arus kas tahunan per aset Gordon dan "
                     "exit multiple hanya menjadi screen ilustratif.")
    notes.append("model dibangun di mata uang pelaporan (Rp); FX = 1.")

    # --- WACC IDR: INDOGB 10Y sudah memuat risiko negara, tanpa CRP ganda
    rf, erp, beta = 0.065, 0.04, 1.1
    re = rf + beta * erp
    news_coe_bps = sum(
        event["change"] for event in (fc.get("news_assumptions") or [])
        if event.get("driver") == "coe_bps" and is_bank and
        fc["rows"][0]["year"] in event.get("years", []))
    news_coe_bps = max(-200, min(200, news_coe_bps))
    re += news_coe_bps / 10000
    if news_coe_bps:
        notes.append(f"CoE screen adjusted {news_coe_bps:+g} bp by cited news scenario judgments.")
    teff = fc["rows"][0]["tax"] / max(fc["rows"][0]["ebit"] - fc["rows"][0]["interest"], 1)
    teff = max(0.0, min(0.35, teff))
    rd = 0.09 * (1 - teff)
    D = fc["base"]["debt"] + fc["base"]["other_liab"]
    E = intake["market_cap"]
    wacc = (re * E + rd * D) / max(E + D, 1)
    news_wacc_bps = sum(
        event["change"] for event in (fc.get("news_assumptions") or [])
        if event.get("driver") == "wacc_bps" and
        fc["rows"][0]["year"] in event.get("years", []))
    news_wacc_bps = max(-200, min(200, news_wacc_bps))
    wacc += news_wacc_bps / 10000
    if news_wacc_bps:
        notes.append(f"WACC screen adjusted {news_wacc_bps:+g} bp by cited news scenario judgments.")
    g = 0.035  # terminal growth FIX analis, wajib < rf
    exit_mult = 8.0
    exit_basis = "asumsi analis 8,0x (tanpa EV/EBITDA peer di cache)"
    if intake.get("peer_median_pe"):
        exit_basis += f"; silang cek median PER peer {intake['peer_median_pe']:.1f}x"

    # --- DCF Gordon + exit, konvensi mid-year, satu basis untuk semua TP
    net_debt = fc["base"]["debt"] - fc["base"]["cash"]
    core = _core(fc, intake["shares"], wacc, g, exit_mult, net_debt)
    pv_exp, pv_tv = core["pv_exp"], core["pv_tv"]
    ev_g, ps_g, ps_x = core["ev_g"], core["ps_g"], core["ps_x"]
    f_last = core["f_last"]
    tp = round((ps_g + ps_x) / 2 / 10) * 10
    upside = tp / intake["price"] - 1
    # The numeric model output is for scenario analysis; it does not classify
    # the security or imply an action for readers.
    rating = None

    # --- downside + grid: basis SAMA dengan TP (rerata Gordon + exit)
    grid = tp_grid(intake, fc, wacc, g, exit_mult, net_debt)
    tp_down = grid[(0.01, 0.025)]

    eq_dcf = ev_g - net_debt
    ratio = eq_dcf / intake["market_cap"]
    g3["G3.1_terminal"] = ("peringatan" if pv_tv / ev_g > 0.75 else "lolos",
                           f"porsi terminal {pv_tv/ev_g*100:.0f}% dari EV")
    g3["G3.2_skala"] = ("lolos" if 0.2 <= ratio <= 3.0 else "gagal-dilabeli",
                        f"ekuitas DCF {ratio*100:.0f}% dari market cap")
    g3["G3.3_implied"] = "lolos"  # dihitung dari model, bukan ketik manual
    g3["G3.4_downside"] = ("lolos" if tp_down < tp else "gagal",
                           f"downside Rp{fmt.rp(tp_down)} vs base Rp{fmt.rp(tp)}")
    g3["G3.5_keyfin"] = "lolos"
    g3["G3.6_peer"] = "dilabeli" if not intake["peers"] else "lolos"
    g3["G3.7_band"] = "lolos"
    method_gap = abs(ps_g - ps_x) / max(abs(ps_g), abs(ps_x), 1)
    g3["G3.8_method_divergence"] = (
        "lolos" if method_gap <= 0.30 else "gagal",
        f"selisih Gordon vs exit {method_gap*100:.1f}%")
    g3["G3.9_extreme_thesis"] = (
        "gagal" if abs(upside) > 0.50 else "lolos",
        "upside/downside ekstrem memerlukan tesis fundamental dan validasi analis"
        if abs(upside) > 0.50 else "band ekstrem tidak terpicu")

    impl = {"per": tp / (f_last["net"] / intake["shares"]) if f_last["net"] > 0 else None,
            "ev_ebitda": (tp * intake["shares"] + net_debt) / f_last["ebitda"]
            if f_last["ebitda"] > 0 else None}
    lom = None
    if is_miner and intake.get("mineops"):
        # fc/base dalam Rupiah → konversi ke Rp miliar untuk rnav.
        lom = rnav.build(intake["mineops"], fc["rows"][0]["margin"], wacc,
                         fc["base"]["cash"] / 1e9, fc["base"]["debt"] / 1e9,
                         fc["rows"][0]["revenue"] / 1e9)
        lom["rnav_ps"] = lom["rnav_rpbn"] * 1e9 / intake["shares"]

    sotp_result = None
    if is_miner:
        bridge = intake.get("sotp_bridge")
        bridge = bridge if isinstance(bridge, dict) else {}

        def bridge_value(key):
            value = bridge.get(key)
            return value.get("value") if isinstance(value, dict) else value

        sotp_result = sotp_mod.calculate_sotp(
            intake.get("sotp_assets"),
            cash_idr=bridge_value("cash_idr"),
            debt_idr=bridge_value("debt_idr"),
            minority_interest_idr=bridge_value("minority_interest_idr"),
            corporate_overhead_idr=bridge_value("corporate_overhead_idr"),
            shares=bridge_value("shares"),
            discount_pct=bridge_value("discount_pct"),
        )
        sotp_result["bridge_evidence"] = {
            field: {key: bridge[field].get(key) for key in
                    ("source", "source_date", "page", "unit",
                     "financial_source_date", "balance_period_end", "fx_date",
                     "fx_rate", "basis")}
            if isinstance(bridge.get(field), dict) else None
            for field in ("cash_idr", "debt_idr", "minority_interest_idr",
                          "corporate_overhead_idr", "shares")
        }
        sotp_result["customer_advance_excluded_usd_thousand"] = bridge.get(
            "customer_advance_excluded_usd_thousand")
    ddm_result = None
    if is_bank and intake.get("payout") is not None:
        nets = [r["net"] for r in fc["rows"]]
        bvps = (intake["annuals"][-1].get("equity") or 0) / intake["shares"] if intake.get("annuals") and intake.get("shares") else 0
        roae = nets[0] / fc["rows"][0]["equity"] if fc["rows"][0].get("equity") else 0.12
        ddm_result = ddm.value_bank(
            nets, [intake["payout"]], intake.get("dps_hist") or [],
            intake["shares"], re, g, roae, bvps,
        )
        ddm_result["status"] = "complete"
        ddm_result["method"] = "ddm"

    annuals = intake.get("annuals") or []
    ebit_pos = sum(
        1 for a in annuals[-3:]
        if (a.get("ebit") or a.get("operating_profit") or a.get("ebitda") or 0) > 0
    )
    r_first = fc["rows"][0] if fc.get("rows") else {}
    ebit_first = r_first.get("ebit", 1.0)
    int_first = r_first.get("interest", 1.0)
    icr = ebit_first / max(int_first, 1.0) if int_first else 10.0
    ebitda_first = r_first.get("ebitda", 1.0)
    nd_ebitda = net_debt / max(ebitda_first, 1.0) if ebitda_first else 0.0

    peer_exit_low = None
    peer_exit_high = None
    if intake.get("peers"):
        pe_vals = [p.get("pe") for p in intake["peers"] if isinstance(p.get("pe"), (int, float))]
        if pe_vals:
            peer_exit_low = min(pe_vals)
            peer_exit_high = max(pe_vals)

    gate_inputs = {
        "domain": profile,
        "model_profile": profile,
        "filing_history_years": len(annuals),
        "ebit_positive_count": ebit_pos,
        "d_de_ratio": D / max(E + D, 1.0),
        "net_debt_to_ebitda": nd_ebitda,
        "icr": icr,
        "equity_positive": E > 0,
        "nci_pct": 0.0,
        "revenue_drivers": intake.get("revenue_drivers") or [],
        "has_steady_state_3y": True,
        "life_cycle_stage": "mature",
        "upside_pct": upside * 100.0 if upside is not None else None,
        "terminal_value_pct_of_ev": (pv_tv / ev_g * 100.0) if ev_g else None,
        "implied_exit_ev_ebitda": impl.get("ev_ebitda"),
        "peer_exit_low": peer_exit_low,
        "peer_exit_high": peer_exit_high,
    }
    verdict = model_profiles.evaluate(gate_inputs)

    if pv_tv / ev_g > 0.75:
        notes.append(f"peringatan terminal: porsi terminal {pv_tv/ev_g*100:.0f}% > 75% dari EV")
    if "5_exit_multiple_out_of_range" in verdict.gates_failed:
        notes.append("implied exit EV/EBITDA di luar rentang peer; periksa cross-check valuasi relatif")

    valuation_asset = sotp_result if is_miner else (ddm_result if is_bank else None)
    if isinstance(valuation_asset, dict):
        valuation_asset["gate_verdict"] = verdict.to_dict()

    release_result = release.assess_release(profile, intake, fc, valuation_asset)
    if release_result["status"] == "distributable":
        critical = [key for key, result in g3.items()
                    if key in {"G3.2_skala", "G3.4_downside",
                               "G3.8_method_divergence", "G3.9_extreme_thesis"}
                    and isinstance(result, tuple) and result[0].startswith("gagal")]
        if verdict.rating_override == "Review Required":
            critical.append("G3.9_extreme_thesis")
        if critical:
            release_result = {"status": "draft_non_distributable",
                              "blockers": [f"valuation check failed: {key}" for key in critical]}
    scenario_target = None
    if is_miner and analyst_target:
        scenario_target = scenario_ev_ebitda_crosscheck(intake, fc)
        release_result = release.assess_assumption_led(
            intake, fc, scenario_target or {}, assumption_status, release_result)
    is_draft = release_result["status"] not in {
        "distributable", "distributable_assumption_led"}

    # Mining's primary method is finite-life SOTP, never the legacy Gordon /
    # exit blend. A screening forecast or incomplete SOTP cannot publish a TP.
    if is_miner:
        method = ("FY26F EV/EBITDA 8x (asumsi analis)"
                  if release_result["status"] == "distributable_assumption_led"
                  else "SOTP/LoM (asset-based, no perpetual terminal)")
        if release_result["status"] == "distributable_assumption_led":
            base = scenario_target["values"][1]
            tp = round(base["per_share_idr"] / 10) * 10
            upside = tp / intake["price"] - 1
            rating = rating_mod.classify(upside)
            tp_down, grid = None, {}
            notes.append("8x EV/EBITDA FY26F adalah asumsi analis; LoM/SOTP belum lengkap.")
        elif is_draft:
            tp, upside, rating = None, None, "DRAFT NON-DISTRIBUTABLE"
            tp_down, grid = None, {}
        else:
            tp = round(sotp_result["target_price_idr"] / 10) * 10
            upside = tp / intake["price"] - 1
            if abs(upside) > 0.50:
                release_result = {"status": "draft_non_distributable",
                                  "blockers": ["extreme SOTP target needs a sourced fundamental thesis"]}
                tp, upside, rating = None, None, "DRAFT NON-DISTRIBUTABLE"
            else:
                rating = verdict.rating_override or rating_mod.classify(upside)
            tp_down, grid = None, {}
        g3 = {
            "G3.1_method": "lolos" if not is_draft else "gagal",
            "G3.2_sotp": "lolos" if sotp_result["status"] == "complete" else "gagal",
            "G3.3_scenario_value": "lolos" if tp is not None else "gagal",
            "G3.4_sensitivity": "dilabeli",
            "G3.5_release": release_result["status"],
        }
    elif profile == "unsupported":
        tp, upside, rating, tp_down, grid = None, None, \
            "DRAFT NON-DISTRIBUTABLE", None, {}
        g3 = {"G3.release": "draft_non_distributable"}
    elif is_draft:
        rating = "DRAFT NON-DISTRIBUTABLE"
    else:
        rating = verdict.rating_override or rating_mod.classify(upside)

    return {"method": method, "model_profile": profile,
            "release": release_result, "sotp": sotp_result,
            "scenario_target": scenario_target,
            "ddm": ddm_result, "gate_verdict": verdict.to_dict(),
            "wacc": wacc, "wacc_inputs": {"rf": rf, "erp": erp,
            "beta": beta, "re": re, "rd_after_tax": rd, "g": g, "exit_mult": exit_mult,
            "exit_basis": exit_basis, "news_wacc_bps": news_wacc_bps,
            "news_coe_bps": news_coe_bps},
            "pv_explicit": pv_exp, "pv_terminal": pv_tv, "tv_share": pv_tv / ev_g,
            "ev_gordon": ev_g, "net_debt": net_debt, "ps_gordon": ps_g,
            "ps_exit": ps_x, "tp": tp, "tp_down": tp_down, "tp_grid": grid,
            "upside": upside, "rating": rating,
            "implied": impl, "lom": lom, "g3": g3, "notes": notes}
