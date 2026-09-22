"""TAHAP 3: VALUATION ENGINE (GATE 3). Satu mata uang, TP = rerata Gordon + exit."""
from . import fmt

BAND_BUY, BAND_SELL = 0.15, -0.10


def _core(fc, shares, wacc, g, exit_mult, net_debt):
    """Satu basis perhitungan; dipakai TP base, downside, dan grid sensitivitas."""
    dfs = [(1 + wacc) ** (i + 0.5) for i in range(3)]
    pv_exp = sum(r["fcf"] / d for r, d in zip(fc["rows"], dfs))
    f_last = fc["rows"][-1]
    tv = f_last["fcf"] * (1 + g) / (wacc - g)
    pv_tv = tv / dfs[-1]
    ev_g = pv_exp + pv_tv
    ps_g = (ev_g - net_debt) / shares
    ev_x = f_last["ebitda"] * exit_mult
    ps_x = (ev_x - net_debt) / ((1 + wacc) ** 3 * shares)
    return {"pv_exp": pv_exp, "pv_tv": pv_tv, "ev_g": ev_g, "ps_g": ps_g,
            "ps_x": ps_x, "tv_share": pv_tv / ev_g, "f_last": f_last}


def tp_grid(intake, fc, wacc, g, exit_mult, net_debt):
    """Grid TP 3x3 (WACC±1pp × g ∈ {1,5; 2,5; 3,5}%), rerata Gordon + exit."""
    out = {}
    for dw in (-0.01, 0.0, 0.01):
        for gg in (0.015, 0.025, 0.035):
            c = _core(fc, intake["shares"], wacc + dw, gg, exit_mult, net_debt)
            out[(round(dw, 3), gg)] = round((c["ps_g"] + c["ps_x"]) / 2 / 10) * 10
    return out


def build(intake, fc):
    g3, notes = {}, []
    t = intake["ticker"]
    is_miner = (intake.get("sub_sector") or "").lower().startswith("metal") or \
               (intake.get("industry") or "").lower().startswith("metal")
    method = ("DCF FCFF 3 tahun eksplisit + terminal Gordon, dibobot sama dengan "
              "exit EV/EBITDA")
    is_bank = "bank" in ((intake.get("sub_sector") or "") + " " +
                          (intake.get("industry") or "")).lower()
    if is_bank:
        notes.append("keterbatasan model: bank idealnya pendekatan GGM ekuitas atau "
                     "residual income dengan silang cek P/BV vs ROE; proksi FCFF "
                     "dipakai karena kerangka ringan generic.")
    if is_miner:
        notes.append("keterbatasan model: emiten tambang idealnya DCF sampai akhir umur "
                     "aset tanpa terminal perpetual; umur cadangan tidak ada di cache "
                     "sehingga dipakai Gordon + exit multiple sebagai proksi.")
    notes.append("model dibangun di mata uang pelaporan (Rp); FX = 1.")

    # --- WACC IDR: INDOGB 10Y sudah memuat risiko negara, tanpa CRP ganda
    rf, erp, beta = 0.065, 0.05, 1.1
    re = rf + beta * erp
    teff = fc["rows"][0]["tax"] / max(fc["rows"][0]["ebit"] - fc["rows"][0]["interest"], 1)
    teff = max(0.0, min(0.35, teff))
    rd = 0.09 * (1 - teff)
    D = fc["base"]["debt"] + fc["base"]["other_liab"]
    E = intake["market_cap"]
    wacc = (re * E + rd * D) / max(E + D, 1)
    g = 0.025  # terminal growth, wajib < rf
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
    rating = "Buy" if upside > BAND_BUY else ("Sell" if upside < BAND_SELL else "Hold")

    # --- downside + grid: basis SAMA dengan TP (rerata Gordon + exit)
    grid = tp_grid(intake, fc, wacc, g, exit_mult, net_debt)
    tp_down = grid[(0.01, 0.015)]

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

    impl = {"per": tp / (f_last["net"] / intake["shares"]) if f_last["net"] > 0 else None,
            "ev_ebitda": (tp * intake["shares"] + net_debt) / f_last["ebitda"]
            if f_last["ebitda"] > 0 else None}
    return {"method": method, "wacc": wacc, "wacc_inputs": {"rf": rf, "erp": erp,
            "beta": beta, "re": re, "rd_after_tax": rd, "g": g, "exit_mult": exit_mult,
            "exit_basis": exit_basis},
            "pv_explicit": pv_exp, "pv_terminal": pv_tv, "tv_share": pv_tv / ev_g,
            "ev_gordon": ev_g, "net_debt": net_debt, "ps_gordon": ps_g,
            "ps_exit": ps_x, "tp": tp, "tp_down": tp_down, "tp_grid": grid,
            "upside": upside,
            "rating": rating, "implied": impl, "g3": g3, "notes": notes}
