"""TAHAP 2: FORECAST ENGINE (GATE 2). Generik, berbasis driver, tiga tahun."""
from . import fmt
from . import rnav


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def build(intake, n_years=5):
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
    assumptions.append(("g_t", "%", *gs,
                        f"CAGR historis {cagr*100:.1f}% ({A[0]['year']}-{y0}), "
                        "diturunkan bertahap"))
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
                        "flat; tanpa jadwal pelunasan di cache"))
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
    g2["catatan"] = ["G2.1: tanpa interim terstruktur di cache; diuji saat rilis tersedia."]
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
    if is_mining:
        # Source rows by themselves are not a physical-to-financial forecast.
        # Until that engine is implemented and reconciled, CAGR remains a
        # screening diagnostic and cannot pass the production release gate.
        g2["G2.9_operating_bridge"] = "gagal"
        g2["catatan"].append(
            "G2.9: forecast fisik-ke-keuangan belum dihitung; angka CAGR hanya "
            "screening proxy dan tidak layak menjadi forecast produksi.")
    else:
        g2["G2.9_driver_forecast"] = "gagal"
        g2["catatan"].append(
            "G2.9: angka CAGR dan capex=D&A hanyalah screen; forecast driver, "
            "modal kerja, serta jadwal utang belum direkonsiliasi.")
    return {"rows": rows, "assumptions": assumptions, "g2": g2, "bridge": bridge,
            "operating_bridge": operating_bridge,
            "driver_evidence": intake.get("driver_evidence") or intake.get("drivers"),
            "forecast_basis": "historical_screening_proxy",
            "production_ready": False,
            "base": {"cash": cash0, "debt": debt0, "equity": eq0,
                     "other_liab": oth_liab, "noncash": nc0}}
