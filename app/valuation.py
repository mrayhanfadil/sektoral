from . import cache
from . import ddm
from . import fmt
from . import gate_thresholds
from . import method_chain
from . import model_profiles
from . import rnav
from . import scenario_value
from . import release
from . import rating as rating_mod
from . import sotp as sotp_mod
from . import stage as stage_mod

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
            out[(round(dw, 3), gg)] = fmt.tick((c["ps_g"] + c["ps_x"]) / 2)
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


def _ddm_grid(nets, payout_used, dps_hist, shares, re, g, roae, bvps):
    """CoE±1pp x g {2.5,3.5,4.5}% sensitivity on the DDM Gordon TP."""
    from . import ddm as _ddm
    out = {}
    for dw in (-0.01, 0.0, 0.01):
        for gg in (0.025, 0.035, 0.045):
            try:
                coe = re + dw
                if coe <= gg:
                    out[(round(dw, 3), gg)] = None
                    continue
                r = _ddm.value_bank(nets, [payout_used], dps_hist or [],
                                    shares, coe, gg, roae, bvps)
                out[(round(dw, 3), gg)] = fmt.tick(r["tp_gordon"])
            except Exception:
                out[(round(dw, 3), gg)] = None
    return out


def _rnav_candidate(intake, fc, lom, wacc):
    """RNAV LoM anuitas sebagai fallback tambang; downside = diskonto +1pp."""
    reasons = []
    if not lom:
        return method_chain.candidate(
            "rnav_lom", reasons=["overlay cadangan/produksi/harga tidak tersedia"])
    for stream in lom.get("streams") or []:
        if not (isinstance(stream.get("life"), (int, float)) and stream["life"] > 0):
            reasons.append(f"umur cadangan {stream.get('nama', '?')} tidak terhitung")
        if stream.get("nav_usd") is None:
            reasons.append(f"NAV {stream.get('nama', '?')} tidak terhitung")
    down = None
    if not reasons:
        lom_down = rnav.build(intake["mineops"], fc["rows"][0]["margin"], wacc + 0.01,
                             fc["base"]["cash"] / 1e9, fc["base"]["debt"] / 1e9,
                             fc["rows"][0]["revenue"] / 1e9)
        down = lom_down["rnav_rpbn"] * 1e9 / intake["shares"]
    ps = lom.get("rnav_ps")
    reasons += method_chain.scale_reasons(ps, intake["shares"], intake["market_cap"])
    return method_chain.candidate(
        "rnav_lom", per_share=ps, per_share_down=down, reasons=reasons,
        labels=[lom.get("margin_basis"), "produksi flat sampai cadangan habis; "
                "diskon RNAV 0% adalah judgment tanpa basis pembanding"],
        detail={"discount": wacc})


def _earnings_candidate(intake, fc, assumption_status):
    """PER median peer x EPS FY dari skenario laba agen; gate sendiri."""
    scenario = fc.get("earnings_scenario") or {}
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    shares = balance.get("shares_outstanding") or balance.get("shares_issued")
    usd = evidence.get("reporting_currency") == "USD"
    fx = (intake.get("fx_spot") or {}).get("rate") if usd else 1.0
    pes = method_chain.peer_pes(intake.get("peers"))
    detail = {"shares": shares, "peer_count": len(pes), "fx": fx if usd else None,
              "year": scenario.get("year"),
              "attributable_basis": scenario.get("attributable_basis")}
    eps = None
    net = (scenario.get("full_year") or {}).get("net_profit_attributable")
    if isinstance(net, (int, float)) and isinstance(shares, (int, float)) and shares > 0 \
            and isinstance(fx, (int, float)) and fx > 0:
        eps = net * fx / shares
        detail["eps_idr"] = eps
    ps = down = None
    if len(pes) >= method_chain.MIN_PEERS and eps and eps > 0:
        q1, median, q3 = method_chain.pe_quartiles(pes)
        detail.update(q1_pe=q1, median_pe=median, q3_pe=q3,
                      per_share_up=q3 * eps)
        ps, down = median * eps, q1 * eps
    gate = release.assess_earnings_led(intake, fc, {"detail": detail}, assumption_status)
    label_year = f"FY{scenario['year'] % 100:02d}F" if scenario.get("year") else "FY"
    candidate = method_chain.candidate(
        "pe_fy_scenario", per_share=ps, per_share_down=down,
        reasons=gate["blockers"], labels=gate["limitations"], detail=detail)
    candidate["label"] = (f"{label_year} PER median peer x EPS skenario analis")
    candidate["gate"] = gate
    return candidate


def _pbv_roe_fy_candidate(intake, fc, assumption_status, coe, g):
    """Bank excess-return value on the validated earnings scenario:
    justified P/BV = (ROE - g) / (CoE - g) times BVPS, where ROE is FY
    parent profit over the latest parent equity. Downside: CoE +1pp."""
    scenario = fc.get("earnings_scenario") or {}
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    usd = evidence.get("reporting_currency") == "USD"
    fx = (intake.get("fx_spot") or {}).get("rate") if usd else 1.0
    shares = balance.get("shares_outstanding") or balance.get("shares_issued")
    equity, equity_source = balance.get("equity_attributable"), "neraca interim resmi"
    if equity is None and balance.get("total_equity") is not None:
        equity = balance["total_equity"] - (balance.get("non_controlling_interest") or 0)
    if equity is not None and fx:
        equity *= fx
    if equity is None:
        last = next((a for a in reversed(intake.get("annuals") or []) if a.get("equity")), None)
        if last:
            equity, equity_source = last["equity"], f"Sectors FY{last.get('year')}"
    net = (scenario.get("full_year") or {}).get("net_profit_attributable")
    net = net * fx if isinstance(net, (int, float)) and fx else None
    roe = net / equity if net is not None and equity else None
    detail = {"shares": shares, "equity": equity, "equity_source": equity_source,
              "coe": coe, "g": g, "roe": roe, "year": scenario.get("year"),
              "bvps": equity / shares if equity and shares else None}
    ps = down = None
    if roe is not None and detail["bvps"] and coe > g and roe > g:
        detail["fair_pbv"] = (roe - g) / (coe - g)
        detail["fair_pbv_down"] = (roe - g) / (coe + 0.01 - g)
        ps = detail["fair_pbv"] * detail["bvps"]
        down = detail["fair_pbv_down"] * detail["bvps"]
    gate = release.assess_pbv_roe_fy(intake, fc, {"detail": detail}, assumption_status)
    label_year = f"FY{scenario['year'] % 100:02d}F" if scenario.get("year") else "FY"
    candidate = method_chain.candidate("pbv_roe_fy", per_share=ps, per_share_down=down,
                                       reasons=gate["blockers"], labels=gate["limitations"],
                                       detail=detail)
    candidate["label"] = f"P/BV wajar dari ROE {label_year} skenario analis"
    candidate["gate"] = gate
    return candidate


# A scenario that cannot be valued carries only its own reasons.
_NO_GATE = {"status": "draft_non_distributable", "blockers": [], "limitations": []}


def _scenario_candidate(key, detail, reasons, gate, label):
    """Primary method valued on the validated scenario, with its own gate."""
    candidate = method_chain.candidate(
        key, per_share=(detail or {}).get("per_share"),
        per_share_down=(detail or {}).get("per_share_down"),
        reasons=list(reasons) + gate["blockers"], labels=gate["limitations"],
        detail=detail or {"basis": "scenario"})
    candidate["label"] = label
    candidate["gate"] = gate
    return candidate


def _ddm_scenario_candidate(intake, fc, assumption_status, coe, g):
    """Bank primary: DDM on the validated FY path (None without a scenario)."""
    if not fc.get("earnings_scenario"):
        return None
    detail, reasons = scenario_value.ddm(intake, fc, coe, g)
    gate = (release.assess_ddm_scenario(intake, fc, {"detail": detail}, assumption_status)
            if detail else _NO_GATE)
    if detail:
        reasons = reasons + method_chain.scale_reasons(
            detail["per_share"], detail["shares"], intake["price"] * detail["shares"])
    year = fc["earnings_scenario"]["year"]
    return _scenario_candidate(
        "ddm", detail, reasons, gate,
        f"DDM dividen skenario FY{year % 100:02d}F-FY{(year + 4) % 100:02d}F "
        "+ terminal Gordon (CoE, bukan WACC)")


def _fcff_scenario_candidate(intake, fc, assumption_status, rf, erp, beta, g, wacc_bps):
    """Going-concern primary: FCFF DCF on the validated FY path."""
    if not fc.get("earnings_scenario"):
        return None
    detail, reasons = scenario_value.fcff(intake, fc, rf, erp, beta, g, wacc_bps)
    gate = (release.assess_fcff_scenario(intake, fc, {"detail": detail}, assumption_status)
            if detail else _NO_GATE)
    if detail:
        reasons = reasons + method_chain.scale_reasons(
            detail["per_share"], detail["shares"], intake["price"] * detail["shares"])
    year = fc["earnings_scenario"]["year"]
    return _scenario_candidate(
        "fcff_dcf", detail, reasons, gate,
        f"DCF FCFF skenario FY{year % 100:02d}F-FY{(year + 4) % 100:02d}F + terminal Gordon; "
        "exit EV/EBITDA historis sebagai cross-check")


def _pbv_book_candidate(intake, fc, assumption_status):
    """Median peer P/B x reported BVPS (official interim), for asset-heavy
    going concerns; downside at the lower quartile."""
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    usd = evidence.get("reporting_currency") == "USD"
    fx = (intake.get("fx_spot") or {}).get("rate") if usd else 1.0
    shares = balance.get("shares_outstanding") or balance.get("shares_issued")
    equity = balance.get("equity_attributable")
    if equity is None and balance.get("total_equity") is not None:
        equity = balance["total_equity"] - (balance.get("non_controlling_interest") or 0)
    equity = equity * fx if equity is not None and fx else None
    history = ((cache.company_report(intake["ticker"]) or {}).get("financials") or {}) \
        .get("historical_financials") or []
    last = history[-1] if history else {}
    share = (last.get("fixed_assets") / last["total_assets"]
             if last.get("fixed_assets") and last.get("total_assets") else None)
    pbvs = method_chain.peer_pbvs(intake.get("peers"))
    detail = {"shares": shares, "equity": equity, "fixed_asset_share": share,
              "fixed_asset_year": last.get("year"), "peer_count": len(pbvs),
              "balance_period": balance.get("period_end"),
              "bvps": equity / shares if equity and shares else None}
    ps = down = None
    if len(pbvs) >= method_chain.MIN_PEERS and detail["bvps"]:
        q1, median, q3 = method_chain.pe_quartiles(pbvs)
        detail.update(q1_pb=q1, median_pb=median, q3_pb=q3)
        ps, down = median * detail["bvps"], q1 * detail["bvps"]
    gate = release.assess_pbv_book(intake, fc, {"detail": detail}, assumption_status)
    candidate = method_chain.candidate("pbv_book", per_share=ps, per_share_down=down,
                                       reasons=gate["blockers"], labels=gate["limitations"],
                                       detail=detail)
    candidate["label"] = "P/BV median peer x nilai buku terlapor"
    candidate["gate"] = gate
    return candidate


def _holding_sotp_candidate(intake):
    """Holding SOTP inputs: stakes from the issuer pack (IDX register), each
    listed subsidiary's market cap and book equity from the Sectors peer
    table of the parent (or the subsidiary's own cached report)."""
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    fx = ((intake.get("fx_spot") or {}).get("rate")
          if evidence.get("reporting_currency") == "USD" else 1.0) or None
    parent_report = cache.company_report(intake["ticker"]) or {}
    table = {str(c.get("symbol") or "").replace(".JK", ""): c
             for g in parent_report.get("peers") or []
             for c in (g.get("peers_data") or {}).get("companies") or [] if isinstance(c, dict)}
    listed = []
    for sub in evidence.get("listed_subsidiaries") or []:
        ticker = str(sub.get("ticker") or "").upper()
        row = table.get(ticker) or {}
        own = cache.company_report(ticker) or {}
        market_cap = (row.get("market_cap") or
                      ((own.get("overview") or {}).get("market_cap")))
        book = row.get("total_equity")
        if book is None:
            history = ((own.get("financials") or {}).get("historical_financials") or [])
            book = (history[-1] if history else {}).get("total_equity")
        held, total = sub.get("shares_held"), sub.get("shares_total")
        listed.append({"ticker": ticker, "name": sub.get("name") or ticker,
                       "segment": sub.get("segment") or "-",
                       "stake": held / total if held and total else None,
                       "market_cap": market_cap, "book_equity": book,
                       "book_year": row.get("year"), "stake_source": sub.get("source"),
                       "market_source": (f"tabel peer Sectors {intake['ticker']}" if row
                                         else f"Sectors company/report {ticker}")})
    equity = balance.get("equity_attributable")
    shares = (balance.get("shares_outstanding") or balance.get("shares_issued")
              or intake.get("shares"))
    candidate = method_chain.holding_sotp(listed, equity * fx if equity and fx else None, shares)
    candidate["detail"]["balance_period"] = balance.get("period_end")
    return candidate


def build(intake, fc, analyst_target=False, assumption_status=None,
          method_override=None, assumption_plan=None):
    g3, notes = {}, []
    t = intake["ticker"]
    profile = intake.get("model_profile", "unsupported")
    is_miner = profile == "finite_life_mining"
    n_fc = len(fc["rows"]) if fc.get("rows") else 5
    method = (f"DCF FCFF {n_fc} tahun eksplisit + terminal Gordon, dibobot sama dengan "
              "exit EV/EBITDA")
    is_bank = profile == "financial_ddm"
    if is_bank:
        method = (f"DDM {n_fc} tahun dividen eksplisit + terminal Gordon "
                  f"(CoE, bukan WACC); FCFF {n_fc} tahun hanya screen ilustratif")
        notes.append("metode utama bank: DDM ekuitas langsung (CoE, bukan WACC); "
                     "FCFF/EV/WACC hanya screen ilustratif dan bukan syarat release.")
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
    exit_basis = "asumsi analis 8,0x (tanpa EV/EBITDA peer di data Sectors)"
    if intake.get("peer_median_pe"):
        exit_basis += f"; silang cek median PER peer {intake['peer_median_pe']:.1f}x"

    # --- DCF Gordon + exit, konvensi mid-year, satu basis untuk semua TP
    net_debt = fc["base"]["debt"] - fc["base"]["cash"]
    core = _core(fc, intake["shares"], wacc, g, exit_mult, net_debt)
    pv_exp, pv_tv = core["pv_exp"], core["pv_tv"]
    ev_g, ps_g, ps_x = core["ev_g"], core["ps_g"], core["ps_x"]
    f_last = core["f_last"]
    tp = fmt.tick((ps_g + ps_x) / 2)
    upside = tp / intake["price"] - 1
    # The numeric model output is for scenario analysis; it does not classify
    # the security or imply an action for readers.
    rating = None

    # --- downside + grid: basis SAMA dengan TP (rerata Gordon + exit)
    grid = tp_grid(intake, fc, wacc, g, exit_mult, net_debt)
    tp_down = grid[(0.01, 0.025)]

    eq_dcf = ev_g - net_debt
    ratio = eq_dcf / intake["market_cap"]
    tv_flag = gate_thresholds.tv_flagged(pv_tv / ev_g if ev_g else None)
    g3["G3.1_terminal"] = ("peringatan" if tv_flag else "lolos",
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
    _extreme = gate_thresholds.is_extreme_ratio(upside)
    g3["G3.9_extreme_thesis"] = (
        "gagal" if _extreme else "lolos",
        "upside/downside ekstrem memerlukan tesis fundamental dan validasi analis"
        if _extreme else "band ekstrem tidak terpicu")

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
    nets, bvps, roae = None, 0, 0.12
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
    icr_fc = ebit_first / max(int_first, 1.0) if int_first else 10.0
    ebitda_first = r_first.get("ebitda", 1.0)
    nd_ebitda_fc = net_debt / max(ebitda_first, 1.0) if ebitda_first else 0.0

    # Gate 5 exit-multiple range: the issuer's own EV/EBITDA history (Sectors
    # peer tables carry no EV). It was the peer P/E range, a unit mismatch.
    peer_exit_low = None
    peer_exit_high = None
    own_ev = [h["value"] for h in intake.get("historical_ev_ebitda") or []]
    if len(own_ev) >= 2:
        peer_exit_low, peer_exit_high = min(own_ev), max(own_ev)

    # --- 1.1 Real gate inputs: official BS when present, else Sectors; missing stays None.
    official_ev = intake.get("official_evidence") or {}
    official_bs = official_ev.get("balance_sheet") or {}
    stage_info = stage_mod.classify(intake, assumption_plan or fc.get("assumption_plan"))
    stage_vals = stage_info.get("values") or {}

    def _off_num(*keys):
        for k in keys:
            v = official_bs.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        return None

    # Official balance sheet is in the reporting currency; gate ratios mix it
    # with Sectors/forecast figures in IDR, so convert first (USD reporters).
    usd_report = official_ev.get("reporting_currency") == "USD"
    fx_rate = (intake.get("fx_spot") or {}).get("rate") if usd_report else 1.0
    fx_ok = isinstance(fx_rate, (int, float)) and fx_rate > 0

    nci_off = _off_num("non_controlling_interest")
    total_equity_off = _off_num("total_equity")
    if total_equity_off is None:
        parent = _off_num("equity_attributable", "equity")
        if parent is not None:
            # NCI share is measured against total equity (parent + NCI).
            total_equity_off = parent + (nci_off or 0.0)
    if total_equity_off is not None and total_equity_off != 0 and nci_off is not None:
        nci_pct_val = nci_off / total_equity_off * 100.0
    else:
        nci_pct_val = None
    if total_equity_off is not None:
        equity_pos_val = total_equity_off > 0
    else:
        # Fallback to Sectors annuals equity (latest), not market cap.
        secs_equity = None
        for a in reversed(annuals):
            if isinstance(a.get("equity"), (int, float)):
                secs_equity = a["equity"]
                break
        equity_pos_val = (secs_equity > 0) if isinstance(secs_equity, (int, float)) else None

    # Financial debt only: total_debt, else loans + leases. Total liabilities
    # (payables, provisions, bank deposits) is never treated as debt.
    d_off = _off_num("total_debt")
    if d_off is None:
        parts = [_off_num(k) for k in ("loans_current", "loans_noncurrent",
                                       "lease_current", "lease_noncurrent")]
        d_off = sum(v for v in parts if v is not None) if any(v is not None for v in parts) else None
    cash_off = _off_num("cash", "cash_and_equivalents")
    if d_off is not None and total_equity_off is not None and (d_off + total_equity_off) != 0:
        d_de_val = d_off / (d_off + total_equity_off)   # same currency: ratio is FX-free
    else:
        d_de_val = D / max(E + D, 1.0) if isinstance(D, (int, float)) else None
    net_debt_off_idr = ((d_off - cash_off) * fx_rate
                        if d_off is not None and cash_off is not None and fx_ok else None)
    if net_debt_off_idr is not None and isinstance(ebitda_first, (int, float)) and ebitda_first:
        nd_ebitda_val = net_debt_off_idr / max(ebitda_first, 1.0)   # IDR / IDR
    else:
        nd_ebitda_val = nd_ebitda_fc
    # ICR needs official interest; keep forecast-based but None if no interest data.
    if isinstance(ebit_first, (int, float)) and isinstance(int_first, (int, float)):
        icr_val = icr_fc
    else:
        icr_val = None

    # Revenue drivers: profile + stage commodity flag.
    rev_drivers = list(intake.get("revenue_drivers") or [])
    if stage_vals.get("commodity_price_driven"):
        if "commodity" not in rev_drivers:
            rev_drivers = rev_drivers + ["commodity"]
    # Segments: stage dissimilar_segments or intake segments.
    segs_val = stage_vals.get("dissimilar_segments")
    if not isinstance(segs_val, int):
        segs_val = len(intake.get("segments") or []) or None
    # Steady / life-cycle from stage; unverified defaults labeled via stage_info source.
    steady_val = stage_vals.get("has_steady_state_3y")
    lc_val = stage_vals.get("life_cycle_stage")
    if stage_info.get("source") == "default_unverified":
        # Conservative defaults, gates will still record unverified via notes.
        pass

    # Gate 0 holding with dissimilar lines: a validated count of dissimilar
    # segments plus a holding signal (listed subsidiaries or NCI > 15%).
    listed_subs = (official_ev.get("listed_subsidiaries") or [])
    holding_signal = bool(listed_subs) or (nci_pct_val is not None and nci_pct_val > 15.0)
    domain = profile
    if (profile == "going_concern_fcff" and isinstance(segs_val, int) and segs_val >= 2
            and holding_signal and stage_info.get("source") in ("llm", "override")):
        domain = "holding_dissimilar"
    gate_inputs = {
        "domain": domain,
        "model_profile": profile,
        "filing_history_years": len(annuals) if annuals else None,
        "ebit_positive_count": ebit_pos if annuals else None,
        "d_de_ratio": d_de_val,
        "net_debt_to_ebitda": nd_ebitda_val,
        "icr": icr_val,
        "equity_positive": equity_pos_val,
        "nci_pct": nci_pct_val,
        "revenue_drivers": rev_drivers,
        "has_steady_state_3y": steady_val,
        "life_cycle_stage": lc_val,
        "segments_count": segs_val,
        "segments": intake.get("segments"),
        "upside_pct": upside * 100.0 if upside is not None else None,
        "terminal_value_pct_of_ev": (pv_tv / ev_g * 100.0) if ev_g else None,
        "implied_exit_ev_ebitda": impl.get("ev_ebitda"),
        "peer_exit_low": peer_exit_low,
        "peer_exit_high": peer_exit_high,
    }

    # --- Rantai metode (§4.1a v3.7): order dari verdict Gates 0-5, fixed sebelum nilai.
    # Preliminary verdict untuk order (upside DCF awal); Gate 5 final dinilai ulang
    # pada metode terpilih di bawah.
    prelim_verdict = model_profiles.evaluate(gate_inputs)
    prelim_order = method_chain.chain_for(prelim_verdict, profile)
    # Override analis: --method atau file data/method_overrides/<TICKER>.json
    override_key = method_override or stage_info.get("method_override")
    if override_key:
        override_key = str(override_key).strip()
        if override_key not in method_chain.LABELS:
            notes.append(f"override analis {override_key} tidak dikenal; diabaikan.")
            override_key = None
        else:
            notes.append(
                f"Usulan sistem: {prelim_order[0] if prelim_order else '-'}; "
                f"dipilih analis: {override_key} "
                f"({stage_info.get('method_reason') or 'alasan analis'}).")

    shares, mcap, price = intake["shares"], intake["market_cap"], intake["price"]
    candidates = {}
    # DCF candidate (going concern + reference for holding/decline)
    if profile in ("going_concern_fcff",) or "dcf_reference" in prelim_order or "fcff_dcf" in prelim_order:
        reasons = method_chain.scale_reasons(ps_g * 0.5 + ps_x * 0.5, shares, mcap)
        if method_gap > 0.30:
            reasons.append(f"divergensi Gordon vs exit {method_gap*100:.0f}% > 30%")
        tv_label = []
        if gate_thresholds.tv_flagged(pv_tv / ev_g if ev_g else None):
            tv_label = [f"porsi terminal {pv_tv/ev_g*100:.0f}% > {gate_thresholds.TV_SHARE_PCT:.0f}% dari EV"]
        candidates["fcff_dcf"] = method_chain.candidate(
            "fcff_dcf", per_share=(ps_g + ps_x) / 2, per_share_down=tp_down,
            reasons=reasons, labels=tv_label)
        if "dcf_reference" in prelim_order:
            c = candidates["fcff_dcf"]
            candidates["dcf_reference"] = method_chain.candidate(
                "dcf_reference", per_share=c["per_share"], per_share_down=c["per_share_down"],
                reasons=c["reasons"], labels=c["labels"] + ["DCF konsolidasi hanya referensi"],
                detail=c["detail"])
    if is_miner:
        # SOTP and RNAV value the physical forecast; while it is a screening
        # proxy they are insufficient, so the chain can still reach the
        # assumption-led multiple route that has its own evidence gate.
        mining_data = release.common_blockers(profile, intake, fc)
        # A development asset whose economics are not disclosed cannot be
        # valued risk-adjusted; that named gap leads the SOTP reasons.
        undisclosed = [
            f"aset pengembangan Elang: {item.get('valuation_consequence') or 'belum dinilai'}"
            for item in [official_ev.get("elang_development_economics")]
            if isinstance(item, dict) and item.get("status") == "not_disclosed"]
        candidates["sotp_lom"] = method_chain.candidate(
            "sotp_lom", per_share=sotp_result.get("target_price_idr"),
            reasons=undisclosed + release._check_sotp(sotp_result, intake) + mining_data,
            labels=["sensitivitas SOTP dilabeli"])
        candidates["rnav_lom"] = method_chain.with_reasons(
            _rnav_candidate(intake, fc, lom, wacc), mining_data)
        scenario_target = scenario_ev_ebitda_crosscheck(intake, fc)
        assumption_release = release.assess_assumption_led(
            intake, fc, scenario_target or {}, assumption_status,
            {"status": "draft_non_distributable", "blockers": []})
        values = (scenario_target or {}).get("values") or []
        candidates["ev_ebitda_fy"] = method_chain.candidate(
            "ev_ebitda_fy",
            per_share=values[1]["per_share_idr"] if len(values) > 1 else None,
            per_share_down=values[0]["per_share_idr"] if values else None,
            reasons=assumption_release["blockers"],
            labels=assumption_release.get("limitations") or [])
    else:
        scenario_target = None
        assumption_release = {"status": "draft_non_distributable", "blockers": [], "limitations": []}
    if is_bank or "ddm" in prelim_order:
        ddm_reasons = release._check_ddm_present(ddm_result)
        ddm_down, ddm_grid, pbv_down = None, {}, None
        if isinstance(ddm_result, dict):
            try:
                ddm_grid = _ddm_grid(nets, ddm_result.get("payout_used"),
                                     intake.get("dps_hist") or [], shares, re, g, roae, bvps)
                ddm_down = ddm_grid.get((0.01, 0.025))
            except Exception:
                ddm_grid = {}
        candidates["ddm"] = method_chain.candidate(
            "ddm", per_share=(ddm_result or {}).get("tp_gordon"), per_share_down=ddm_down,
            reasons=ddm_reasons + method_chain.scale_reasons(
                (ddm_result or {}).get("tp_gordon"), shares, mcap) +
            ([] if ddm_down is not None or ddm_reasons else ["grid sensitivitas DDM gagal"]))
        pbv_reasons = []
        if not isinstance(ddm_result, dict):
            pbv_reasons.append("hasil DDM/Inverse CoE tidak tersedia")
        if not fc["rows"][0].get("equity"):
            pbv_reasons.append("ROE forward tidak terhitung (ekuitas forecast kosong)")
        if not bvps or bvps <= 0:
            pbv_reasons.append("BVPS <= 0 atau tidak tersedia")
        tp_inv = (ddm_result or {}).get("tp_inverse")
        if not pbv_reasons and re + 0.01 > g:
            pbv_down = (roae - g) / (re + 0.01 - g) * bvps
        candidates["pbv_roe"] = method_chain.candidate(
            "pbv_roe", per_share=tp_inv, per_share_down=pbv_down,
            reasons=pbv_reasons + method_chain.scale_reasons(tp_inv, shares, mcap),
            detail={"fair_pbv": (ddm_result or {}).get("fair_pbv"), "roae": roae, "bvps": bvps})
    if "pbv_book" in prelim_order:
        candidates["pbv_book"] = _pbv_book_candidate(intake, fc, assumption_status)
    if "pbv_roe_fy" in prelim_order:
        candidates["pbv_roe_fy"] = _pbv_roe_fy_candidate(intake, fc, assumption_status, re, g)
    # Generic peer/NAV/SOTP placeholders for gate-driven orders (1.4)
    fwd = fc["rows"][0] if fc.get("rows") else {}
    # net_debt is the forecast base: Sectors total debt less cash, base year.
    sectors_nd_source = f"data Sectors FY{intake.get('base_year')}"
    if "relative_pe" in prelim_order or profile in ("going_concern_fcff", "financial_ddm"):
        candidates["relative_pe"] = method_chain.relative_pe(
            intake.get("peers"), fwd.get("eps"), shares, mcap)
    if "pbv_relative" in prelim_order:
        _bvps_fwd = None
        try:
            _bvps_fwd = fwd.get("equity") / shares if fwd.get("equity") and shares else bvps
        except (TypeError, ZeroDivisionError):
            _bvps_fwd = bvps
        candidates["pbv_relative"] = method_chain.pbv_relative(
            intake.get("peers"), _bvps_fwd, shares, mcap)
    if "ev_ebitda_peer" in prelim_order:
        _ebitda_fwd = fwd.get("ebitda")
        # Official net debt (converted to IDR) when available; EV and EBITDA are IDR.
        if net_debt_off_idr is not None:
            _nd, _nd_source = net_debt_off_idr, "neraca resmi"
        else:
            _nd, _nd_source = net_debt, sectors_nd_source
        candidates["ev_ebitda_peer"] = method_chain.ev_ebitda_peer(
            intake.get("peers"), _ebitda_fwd, shares, mcap, net_debt=_nd,
            net_debt_source=_nd_source)
    if "ev_sales_peer" in prelim_order:
        candidates["ev_sales_peer"] = method_chain.ev_sales_peer(
            intake.get("peers"), fwd.get("revenue"), shares, mcap, net_debt=net_debt,
            net_debt_source=sectors_nd_source)
    if "ps_peer" in prelim_order:
        # P/S needs no EV: market cap and revenue sit in the Sectors peer rows.
        candidates["ps_peer"] = method_chain.ps_peer(
            intake.get("peers"), fwd.get("revenue"), shares, mcap)
    holding = None
    if "holding_sotp" in prelim_order or (nci_pct_val is not None and 15.0 < nci_pct_val <= 40.0):
        holding = _holding_sotp_candidate(intake)
    if "holding_sotp" in prelim_order:
        # Primary for a holding with dissimilar lines: its own evidence gate
        # (official equity, listed stakes at market), not the forecast G2.9.
        gate = release.assess_holding_sotp(intake, fc, holding, assumption_status)
        holding = method_chain.with_reasons(holding, gate["blockers"])
        holding.update(gate=gate, labels=list(holding.get("labels") or []) + gate["limitations"])
        holding["detail"] = {**(holding.get("detail") or {}), "basis": "official"}
        candidates["holding_sotp"] = holding
    if "property_nav" in prelim_order:
        candidates["property_nav"] = method_chain.unavailable(
            "property_nav",
            "Property NAV memerlukan evidence pack per aset; belum tersedia")
    # Primary DDM / FCFF DCF on the validated analyst scenario (spec Opsi A/B):
    # the same method, valued on the agents' FY path instead of the screen.
    if is_bank and "ddm" in candidates:
        scenario_ddm = _ddm_scenario_candidate(intake, fc, assumption_status, re, g)
        if scenario_ddm:
            candidates["ddm"] = scenario_ddm
    if profile == "going_concern_fcff" and "fcff_dcf" in candidates:
        scenario_dcf = _fcff_scenario_candidate(intake, fc, assumption_status, rf, erp, beta,
                                                g, news_wacc_bps)
        if scenario_dcf:
            candidates["fcff_dcf"] = scenario_dcf
            if "dcf_reference" in candidates:
                # The consolidated DCF reference values the same scenario.
                candidates["dcf_reference"] = dict(
                    scenario_dcf, key="dcf_reference",
                    short=method_chain.SHORT["dcf_reference"],
                    label=scenario_dcf["label"] + " [referensi]")
    if profile in ("going_concern_fcff", "financial_ddm"):
        # DCF/DDM/P-BV/PER-forward on the screening forecast are insufficient
        # while its data gates fail, so the chain can reach a scenario-based
        # method that carries its own evidence gate.
        forecast_data = release.common_blockers(profile, intake, fc)
        if forecast_data:
            for key in ("fcff_dcf", "dcf_reference", "ddm", "pbv_roe", "relative_pe",
                        "pbv_relative", "ev_ebitda_peer", "ev_sales_peer"):
                if key in candidates and not candidates[key].get("gate"):
                    candidates[key] = method_chain.with_reasons(candidates[key], forecast_data)
        candidates["pe_fy_scenario"] = _earnings_candidate(intake, fc, assumption_status)

    chain = method_chain.run(profile, candidates, price, order=prelim_order,
                             override_key=override_key)
    selected = chain["selected"]
    sel = next((t for t in chain["trace"] if t["key"] == selected), None)

    # Gate 5 dinilai ulang pada metode terpilih, bukan DCF bila DCF di-skip.
    if sel and sel["upside"] is not None:
        gate_inputs["upside_pct"] = sel["upside"] * 100.0
    scenario_sel = bool(sel and sel.get("gate") and
                        (sel.get("detail") or {}).get("basis") == "scenario")
    if scenario_sel and selected in ("fcff_dcf", "dcf_reference"):
        gate_inputs["terminal_value_pct_of_ev"] = (sel["detail"]["tv_share"] or 0) * 100.0
        gate_inputs["implied_exit_ev_ebitda"] = sel["detail"]["implied_exit"]
    elif selected != "fcff_dcf":
        gate_inputs.pop("terminal_value_pct_of_ev", None)
        gate_inputs.pop("implied_exit_ev_ebitda", None)
    verdict = model_profiles.evaluate(gate_inputs)
    # Chain order final dari verdict final (untuk laporan); trace sudah fixed.
    final_order = method_chain.chain_for(verdict, profile)
    chain["verdict_order"] = list(final_order)
    chain["prelim_order"] = list(prelim_order)
    chain["stage"] = {"values": stage_vals, "source": stage_info.get("source"),
                      "rationale": stage_info.get("values", {}).get("rationale") if False else None}
    # 1.5 Mandatory cross-checks: DCF primary, Gate 1c breach, atau NCI 15-40%.
    try:
        _nci_for_x = float(nci_pct_val) if nci_pct_val is not None else 0.0
    except (TypeError, ValueError):
        _nci_for_x = 0.0
    needs_x = (
        (verdict.primary in ("FCFF/WACC DCF", "DCF (shortened horizon)")) or
        ("1c_capital_structure" in verdict.gates_failed and
         "1c_capital_structure" not in verdict.gates_unassessed) or
        (15.0 < _nci_for_x <= 40.0)
    )
    chain["cross_check_required"] = bool(needs_x)
    # Gate 5: an extreme result points to relative valuation as the cross-check.
    # P/S needs no earnings, so it still reads when every earnings multiple is
    # extreme (a high-growth issuer on thin current profit).
    if chain.get("extreme") and "ps_peer" not in chain["order"]:
        scenario_fy = (fc.get("earnings_scenario") or {}).get("full_year") or {}
        fx_scen = ((intake.get("fx_spot") or {}).get("rate")
                   if (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
                   else 1.0)
        revenue = (scenario_fy["revenue"] * fx_scen if scenario_fy.get("revenue") and fx_scen
                   else fwd.get("revenue"))
        ps_check = method_chain.ps_peer(intake.get("peers"), revenue, shares, mcap)
        price_now = intake.get("price")
        chain.setdefault("cross_checks", []).append({
            **ps_check, "rank": "x", "role": "cross_check",
            "decision": "cross_check" if ps_check["status"] == "sufficient" else "not_available",
            "upside": (ps_check["per_share"] / price_now - 1
                       if ps_check.get("per_share") and price_now else None),
            "why": "Gate 5: target metode terpilih ekstrem; framework menunjuk valuasi "
                   "relatif (P/S peer) sebagai cross-check"})
    if needs_x:
        x_keys = {"relative_pe", "pbv_relative", "ev_ebitda_peer", "ev_sales_peer",
                  "holding_sotp", "sotp_lom"}
        has_x = any(t["key"] in x_keys and t["status"] == "sufficient"
                    for t in chain["trace"] if t["key"] != selected)
        # Also count selected itself if it is relative/SOTP.
        if selected in x_keys:
            has_x = True
        # Gate 2 (NCI 15-40%): the holding SOTP runs beside the chain as the
        # mandatory cross-check; it never becomes the target method.
        if holding and "holding_sotp" not in chain["order"]:
            price_now = intake.get("price")
            up = (holding["per_share"] / price_now - 1
                  if holding.get("per_share") and price_now else None)
            chain["cross_checks"] = [{**holding, "rank": "x", "role": "cross_check",
                                      "decision": ("cross_check" if holding["status"] == "sufficient"
                                                   else "not_available"),
                                      "upside": up,
                                      "why": "Gate 2: kepentingan non-pengendali 15-40% dari "
                                             "ekuitas mewajibkan cross-check SOTP"}]
            has_x = has_x or holding["status"] == "sufficient"
        chain["cross_check_present"] = bool(has_x)
        if not has_x:
            has_peer_data = bool(intake.get("peers"))
            if has_peer_data:
                chain["cross_check_missing"] = True
            else:
                notes.append("keterbatasan: cross-check relatif/SOTP belum tersedia (tanpa peer); "
                             "dilabeli sebagai limitasi metodologi.")
                chain["cross_check_missing"] = False
        else:
            chain["cross_check_missing"] = False
    else:
        chain["cross_check_present"] = None
        chain["cross_check_missing"] = False

    if selected == "ev_ebitda_fy":
        release_result = dict(assumption_release)
        release_result["underlying_sotp"] = release.assess_release(
            profile, intake, fc, sotp_result)
        release_result["route"], release_result["method_key"] = chain["route"], selected
        extreme_blocker = method_chain.summary_blocker(chain)
        if extreme_blocker and release_result["status"] != "draft_non_distributable":
            release_result.update(status="draft_non_distributable",
                                  blockers=release_result["blockers"] + [extreme_blocker])
    elif sel is not None and sel.get("gate"):
        release_result = dict(sel["gate"])
        release_result["underlying_primary"] = release.common_blockers(profile, intake, fc)
        release_result["route"], release_result["method_key"] = chain["route"], selected
        extreme_blocker = method_chain.summary_blocker(chain)
        if extreme_blocker:
            release_result.update(status="draft_non_distributable",
                                  blockers=release_result["blockers"] + [extreme_blocker])
    elif profile == "unsupported":
        release_result = release.assess_release(profile, intake, fc, None)
    else:
        release_result = release.assess_chain(profile, intake, fc, chain)
        # Generic gate-driven methods: still need data-gate + extreme handling.
        if chain.get("cross_check_missing"):
            release_result["blockers"] = list(release_result.get("blockers") or []) + [
                "cross-check relatif/SOTP wajib belum tersedia padahal peer ada"]
            release_result["status"] = "draft_non_distributable"
        extreme_blocker = method_chain.summary_blocker(chain)
        if extreme_blocker and release_result["status"] != "draft_non_distributable":
            release_result.update(status="draft_non_distributable",
                                  blockers=list(release_result.get("blockers") or []) + [extreme_blocker])
        if override_key:
            release_result["override"] = {"method": override_key,
                                          "reason": stage_info.get("method_reason"),
                                          "proposed_order": chain.get("proposed_order"),
                                          "system_proposal": (chain.get("proposed_order") or [None])[0]}
    release_result["method_chain"] = {"selected": selected, "route": chain["route"]}
    release_result["gate_verdict"] = verdict.to_dict()
    release_result["stage"] = {"values": stage_vals, "source": stage_info.get("source")}
    is_draft = release_result["status"] not in {
        "distributable", "distributable_assumption_led"}

    if selected:
        # Keep DCF label for dcf_reference (reference) but show reference suffix.
        if selected in ("fcff_dcf", "ddm") and not scenario_sel:
            pass
        elif selected == "dcf_reference":
            method = sel["label"] + " [referensi]"
        else:
            method = sel["label"]
        if chain["route"] in ("fallback", "override"):
            skipped = [t for t in chain["trace"] if t["decision"] == "skipped"]
            tag = "override" if chain["route"] == "override" else "fallback"
            method += f" [{tag}: " + ", ".join(
                f"{t['short']} tidak memadai" for t in skipped) + "]"
            notes.append("rantai metode: " + "; ".join(
                f"{t['short']} dilewati ({method_chain.reader_reason(t['reasons'][0])})"
                for t in skipped)
                + f"; dasar nilai {sel['label']}.")
            if chain["route"] == "override":
                notes.append(
                    f"Usulan sistem: {(chain.get('proposed_order') or ['-'])[0]}; "
                    f"dipilih analis: {override_key} "
                    f"({stage_info.get('method_reason') or 'alasan analis'}).")
        notes.extend(sel["labels"])
    elif is_miner:
        method = method_chain.LABELS["sotp_lom"]

    dcf_grid, dcf_down = grid, tp_down
    tp_down, grid = None, {}
    if scenario_sel:
        grid = {key: fmt.tick(v) if v else None for key, v in sel["detail"]["grid"].items()}
    elif selected == "fcff_dcf":
        grid, tp_down = dcf_grid, dcf_down
    elif selected == "ddm":
        grid = ddm_grid
    if sel and not is_draft:
        tp = fmt.tick(sel["per_share"])
        upside = tp / price - 1
        if tp_down is None and sel["per_share_down"] is not None:
            tp_down = fmt.tick(sel["per_share_down"])
        rating = (rating_mod.classify(upside) if selected in ("ev_ebitda_fy", "pe_fy_scenario",
                                                              "pbv_roe_fy", "pbv_book")
                  or scenario_sel
                  else verdict.rating_override or rating_mod.classify(upside))
        if selected == "ev_ebitda_fy":
            tp_down, grid = None, {}
            notes.append("8x EV/EBITDA FY26F adalah asumsi analis; LoM/SOTP belum lengkap.")
    else:
        rating = "DRAFT NON-DISTRIBUTABLE"
        if profile != "going_concern_fcff" or selected != "fcff_dcf" or scenario_sel:
            tp, upside, tp_down, grid = None, None, None, {}

    if tp is not None and f_last["net"] > 0:
        impl["per"] = tp / (f_last["net"] / shares)
    if selected == "pe_fy_scenario" and tp is not None:
        impl["per"] = tp / sel["detail"]["eps_idr"]
    if selected == "pbv_roe_fy" and tp is not None and sel["detail"].get("bvps"):
        impl["pbv"] = tp / sel["detail"]["bvps"]
    if selected not in (None, "fcff_dcf") and tp is not None:
        impl["ev_ebitda"] = ((tp * shares + net_debt) / f_last["ebitda"]
                             if f_last["ebitda"] > 0 and not is_bank else None)
    if is_bank:
        impl.update(ev_ebitda=None,
                    pbv=(ddm_result or {}).get("fair_pbv"),
                    tp_inverse=(ddm_result or {}).get("tp_inverse"))
    if scenario_sel and tp is not None:
        # Implied multiples on the same FY path the target values.
        detail = sel["detail"]
        first = detail["lines"][0]
        eps_fy = (first["net_attr"] / detail["shares"]) if first.get("net_attr") else None
        impl["per"] = tp / eps_fy if eps_fy and eps_fy > 0 else None
        if selected == "ddm":
            impl["pbv"] = tp / detail["bvps"] if detail.get("bvps") else None
        else:
            ev_at_tp = (tp * detail["shares"] - detail["cash"] + detail["debt"]
                        + (detail.get("nci") or 0.0))
            impl["ev_ebitda"] = ev_at_tp / first["ebitda"] if first["ebitda"] > 0 else None

    if selected != "fcff_dcf" or scenario_sel:
        g3 = {
            "G3.1_method": "lolos" if selected else "gagal",
            "G3.2_skala": "lolos" if tp is not None else "dilabeli",
            "G3.3_implied": "dilabeli",
            "G3.4_downside": ("lolos" if (tp is not None and tp_down is not None and tp_down < tp)
                              else "dilabeli" if tp is None or selected in ("sotp_lom", "ev_ebitda_fy")
                              else "gagal"),
            "G3.5_keyfin": "lolos" if (f_last.get("net") and shares) else "gagal",
            "G3.6_peer": "dilabeli" if not intake["peers"] else "lolos",
            "G3.7_band": "dilabeli",
            "G3.8_method_divergence": "dilabeli",
            "G3.9_extreme_thesis": "gagal" if chain["extreme"] else "lolos",
            "G3.10_method_chain": (chain["route"] or "none") + ":" + (selected or "-"),
        }
        if is_miner:
            g3["G3.2_sotp"] = ("lolos" if sotp_result["status"] == "complete" else
                               "dilabeli" if selected else "gagal")
            g3["G3.5_release"] = release_result["status"]
        if scenario_sel:
            detail = sel["detail"]
            g3["G3.3_implied"] = "lolos" if impl.get("per") or impl.get("ev_ebitda") else "dilabeli"
            g3["G3.7_band"] = "lolos"
            if detail.get("tv_share") is not None:
                g3["G3.1_terminal"] = (
                    "peringatan" if gate_thresholds.tv_flagged(detail["tv_share"]) else "lolos",
                    f"porsi terminal {detail['tv_share'] * 100:.0f}% dari "
                    + ("nilai DDM" if selected == "ddm" else "EV"))
            if selected in ("fcff_dcf", "dcf_reference"):
                gap = detail.get("exit_gap")
                g3["G3.8_method_divergence"] = (
                    "dilabeli",
                    f"TP memakai Gordon; selisih dengan exit EV/EBITDA historis "
                    f"{gap * 100:.0f}% diungkapkan, tidak dirata-rata" if gap is not None
                    else "exit EV/EBITDA historis kurang dari tiga titik; Gordon saja")
    else:
        g3["G3.10_method_chain"] = f"{chain['route']}:{selected}"

    valuation_asset = sotp_result if is_miner else (ddm_result if is_bank else None)
    if isinstance(valuation_asset, dict):
        valuation_asset["gate_verdict"] = verdict.to_dict()
    # Terminal share of the DCF the target is built on (scenario or screen).
    tv_selected = (sel["detail"].get("tv_share") if scenario_sel else
                   pv_tv / ev_g if ev_g and selected == "fcff_dcf" else None)
    if gate_thresholds.tv_flagged(tv_selected):
        notes.append(f"peringatan terminal: porsi terminal {tv_selected*100:.0f}% > "
                     f"{gate_thresholds.TV_SHARE_PCT:.0f}% dari "
                     + ("nilai DDM" if selected == "ddm" else "EV"))
    if "5_exit_multiple_out_of_range" in verdict.gates_failed:
        notes.append("implied exit EV/EBITDA di luar rentang EV/EBITDA historis emiten; "
                     "periksa cross-check valuasi relatif")
    if stage_info.get("source") == "default_unverified":
        notes.append("klasifikasi tahap operasi belum tervalidasi (default konservatif, belum terverifikasi).")
    elif stage_info.get("source") == "override":
        notes.append("klasifikasi tahap operasi dari override analis.")

    out = {"method": method, "model_profile": profile,
            "release": release_result, "sotp": sotp_result,
            "scenario_target": (scenario_target if analyst_target or
                                selected == "ev_ebitda_fy" else None),
            "ddm": ddm_result, "gate_verdict": verdict.to_dict(),
            "stage_classification": {"values": stage_vals, "source": stage_info.get("source"),
                                     "override": stage_info.get("override")},
            "gate_inputs": gate_inputs,
            "wacc": wacc, "wacc_inputs": {"rf": rf, "erp": erp,
            "beta": beta, "re": re, "rd_after_tax": rd, "g": g, "exit_mult": exit_mult,
            "exit_basis": exit_basis, "news_wacc_bps": news_wacc_bps,
            "news_coe_bps": news_coe_bps},
            "pv_explicit": pv_exp, "pv_terminal": pv_tv, "tv_share": pv_tv / ev_g,
            "ev_gordon": ev_g, "net_debt": net_debt, "ps_gordon": ps_g,
            "ps_exit": ps_x, "dcf_blend": fmt.tick((ps_g + ps_x) / 2), "tp": tp, "tp_down": tp_down, "tp_grid": grid,
            "upside": upside, "rating": rating,
            "implied": impl, "lom": lom, "g3": g3, "notes": notes,
            "method_chain": chain}
    if scenario_sel and selected in ("fcff_dcf", "dcf_reference"):
        # The report, harness G3.1/G3.8 and Gate 5 read the DCF the target
        # was built on; the screening DCF stays in wacc_inputs/trace only.
        d = sel["detail"]
        out.update(wacc=d["wacc"], pv_explicit=d["pv_explicit"], pv_terminal=d["pv_tv"],
                   tv_share=d["tv_share"], ev_gordon=d["ev"], net_debt=d["debt"] - d["cash"],
                   ps_gordon=d["per_share"], ps_exit=d.get("per_share_exit"),
                   dcf_blend=None, dcf_basis="gordon")
    elif scenario_sel and selected == "ddm":
        out.update(ev_gordon=None, ps_gordon=None, ps_exit=None, dcf_blend=None)
    return out
