"""Exhibit valuasi per Opsi A/B/C (Instruksi-Report-v3, seksi 4.5).

Setiap builder mengembalikan SATU exhibit dict (penomoran "n" = None,
diisi orkestrator mengikuti urutan global laporan):

    {"n": None, "judul": ..., "tipe": "tabel",
     "data": {"cols": [...], "rows": [...]},
     "catatan_sumber": ...}

Semua uang diformat via app.fmt. Label Bahasa Indonesia, tanpa emoji. Each
exhibit carries a stable ``exhibit_id``; its English title and fixed labels
(``TITLES_EN``, ``LABELS_EN``) sit below, for the English Company Update
(app.report_lang).
"""

from . import fmt
from . import valuation as _valuation


def _exhibit(judul, cols, rows, note="Source: Company, Sektoral Estimates", exhibit_id=None):
    return {"n": None, "judul": judul, "tipe": "tabel",
            "data": {"cols": cols, "rows": rows},
            "catatan_sumber": note, "exhibit_id": exhibit_id}


TITLES_EN = {
    "fcff_bridge": "FCFF projection, terminal value and value-scenario bridge",
    "wacc_components": "WACC components",
    "value_sensitivity": "Scenario value per share sensitivity (Rp)",
    "ddm_bridge": "Dividend forecast, terminal value and inverse CoE",
    "rnav_bridge": "Asset breakdown and RNAV bridge",
}

LABELS_EN = {
    "Terminal / Total": "Terminal / Total",
    "Blok 1: FCFF eksplisit (Rp miliar)": "Block 1: explicit FCFF (Rp bn)",
    "Blok 2: Nilai terminal Gordon": "Block 2: Gordon terminal value",
    "Blok 3: Jembatan ke nilai skenario": "Block 3: bridge to scenario value",
    "(-/+) Delta NWC (plug penyeimbang)": "(-/+) Delta NWC (balancing plug)",
    "Faktor diskonto (mid-year)": "Discount factor (mid-year)",
    "FCFF terminal (= FCFF terakhir x (1+g))": "Terminal FCFF (= last FCFF x (1+g))",
    "Pertumbuhan terminal g (di bawah risk-free)": "Terminal growth g (below risk-free)",
    "Terminal Value (undiscounted)": "Terminal value (undiscounted)",
    "PV Terminal Value": "PV of terminal value",
    "Jumlah PV FCFF (Rp miliar)": "Sum of PV of FCFF (Rp bn)",
    "(+) PV Terminal Value (Rp miliar)": "(+) PV of terminal value (Rp bn)",
    "(=) Enterprise Value (Rp miliar)": "(=) Enterprise value (Rp bn)",
    "(-) Utang bersih tanggal valuasi (Rp miliar)": "(-) Net debt at valuation date (Rp bn)",
    "(+/-) Minority Interest / Aset non-operasi (Rp miliar)":
        "(+/-) Minority interest / non-operating assets (Rp bn)",
    "0 (tidak ada di data Sectors)": "0 (not in Sectors data)",
    "(=) Nilai Ekuitas Gordon (Rp miliar)": "(=) Gordon equity value (Rp bn)",
    "(/) Saham beredar (saham)": "(/) Shares outstanding (shares)",
    "(=) Nilai skenario per Saham Gordon (Rp)": "(=) Gordon scenario value per share (Rp)",
    "Nilai per saham exit (Rp)": "Exit value per share (Rp)",
    "Nilai skenario gabungan per saham Gordon+exit (Rp)": "Combined Gordon + exit scenario value per share (Rp)",
    "Risk-free rate IDR (house policy)": "IDR risk-free rate (house policy)",
    "Equity Risk Premium": "Equity risk premium",
    "(=) Cost of Equity (Rf + Beta x ERP)": "(=) Cost of Equity (Rf + Beta x ERP)",
    "Cost of Debt pra-pajak": "Pre-tax cost of debt",
    "(=) Cost of Debt setelah pajak": "(=) After-tax cost of debt",
    "WACC / g terminal": "WACC / terminal g",
    "Blok 1: Dividen Gordon (diskonto CoE, valuasi ekuitas langsung)":
        "Block 1: Gordon dividends (CoE discounting, direct equity valuation)",
    "BVPS forward (Rp)": "Forward BVPS (Rp)",
    "ROAE forward": "Forward ROAE",
    "EPS forward (= ROAE x BVPS, Rp)": "Forward EPS (= ROAE x BVPS, Rp)",
    "DPS forward (= EPS x payout, Rp)": "Forward DPS (= EPS x payout, Rp)",
    "DPS terminal (= DPS x (1+g), Rp)": "Terminal DPS (= DPS x (1+g), Rp)",
    "Terminal Value (= DPS terminal/(CoE-g), Rp)": "Terminal value (= terminal DPS/(CoE-g), Rp)",
    "Faktor diskonto (1/(1+CoE))": "Discount factor (1/(1+CoE))",
    "Nilai skenario per Saham Gordon (Rp)": "Gordon scenario value per share (Rp)",
    "Blok 2: Inverse Cost of Equity": "Block 2: inverse Cost of Equity",
    "Nilai skenario (= P/BV x BVPS, Rp)": "Scenario value (= P/BV x BVPS, Rp)",
    "Blok 1: NAV per aset (Rp miliar)": "Block 1: NAV by asset (Rp bn)",
    "Jumlah NAV atribuibel (Rp miliar)": "Sum of attributable NAV (Rp bn)",
    "Blok 2: Jembatan RNAV ke skenario nilai": "Block 2: RNAV bridge to scenario value",
    "(+) Kas dan setara kas (Rp miliar)": "(+) Cash and equivalents (Rp bn)",
    "(-) Total utang (Rp miliar)": "(-) Total debt (Rp bn)",
    "(-) Overhead korporat, PV biaya tak teratribusi (Rp miliar)":
        "(-) Corporate overhead, PV of unallocated costs (Rp bn)",
    "(=) Total RNAV (Rp miliar)": "(=) Total RNAV (Rp bn)",
    "(=) RNAV per saham (Rp)": "(=) RNAV per share (Rp)",
    "(=) Nilai skenario (= RNAVps x (1-diskon), Rp)": "(=) Scenario value (= RNAVps x (1-discount), Rp)",
}


def _teff(fc):
    """Tarif pajak efektif, rumus SAMA dengan app.valuation.build."""
    r0 = fc["rows"][0]
    t = r0["tax"] / max(r0["ebit"] - r0["interest"], 1)
    return max(0.0, min(0.35, t))


def _df4(x):
    return f"{x:.4f}".replace(".", ",")


def fcff_exhibit(intake, fc, val):
    """Opsi A, tabel 1: tiga blok (eksplisit, terminal Gordon, jembatan)."""
    rows3 = fc["rows"]
    labels = [r["label"] for r in rows3]
    wacc = val["wacc"]
    g = val["wacc_inputs"]["g"]
    exit_mult = val["wacc_inputs"]["exit_mult"]
    shares = intake["shares"]
    net_debt = val["net_debt"]
    teff = _teff(fc)

    per, prev = [], None
    for i, r in enumerate(rows3):
        tax_ebit = r["ebit"] * teff
        nopat = r["ebit"] - tax_ebit
        # Delta NWC = plug penyeimbang: kas satu-satunya penyeimbang di
        # forecast, sehingga FCFF tampil = fcf forecast (basis skenario nilai).
        dnwc = nopat + r["da"] - r["capex"] - r["fcf"]
        df = 1 / (1 + wacc) ** (i + 0.5)
        growth = None if prev is None or prev == 0 else r["fcf"] / prev - 1
        per.append({"tax_ebit": tax_ebit, "nopat": nopat, "dnwc": dnwc,
                    "df": df, "pv": r["fcf"] * df, "growth": growth})
        prev = r["fcf"]

    f_last = rows3[-1]
    term_fcf = f_last["fcf"] * (1 + g)
    tv = term_fcf / (wacc - g)
    df_t = 1 / (1 + wacc) ** (len(rows3) - 0.5)
    pv_tv = tv * df_t

    # Blok 3 memakai angka val agar jembatan terikat persis pada hasil model.
    ev = val["ev_gordon"]
    eq = ev - net_debt
    ev_x = f_last["ebitda"] * exit_mult
    ps_x = (ev_x - net_debt) / ((1 + wacc) ** len(rows3) * shares)

    cols = ["Uraian"] + labels + ["Terminal / Total"]
    n_pad = len(labels)
    B = lambda t: [t] + [""] * (n_pad + 1)  # noqa: E731
    R = []
    R.append(B("Blok 1: FCFF eksplisit (Rp miliar)"))
    R.append(["Pendapatan"] + [fmt.miliar(r["revenue"]) for r in rows3] + [""])
    R.append(["EBIT"] + [fmt.miliar(r["ebit"]) for r in rows3] + [""])
    R.append([f"Pajak atas EBIT (tarif efektif {fmt.pct(teff)})"]
             + [fmt.miliar(p["tax_ebit"]) for p in per] + [""])
    R.append(["NOPAT"] + [fmt.miliar(p["nopat"]) for p in per] + [""])
    R.append(["(+) D&A"] + [fmt.miliar(r["da"]) for r in rows3] + [""])
    R.append(["(-) Capex"] + [fmt.miliar(r["capex"]) for r in rows3] + [""])
    R.append(["(-/+) Delta NWC (plug penyeimbang)"]
             + [fmt.miliar(p["dnwc"]) for p in per] + [""])
    R.append(["FCFF"] + [fmt.miliar(r["fcf"]) for r in rows3] + [""])
    R.append(["Pertumbuhan FCFF"]
             + [("n.a." if p["growth"] is None else fmt.pct(p["growth"]))
                for p in per] + [""])
    R.append(["Faktor diskonto (mid-year)"]
             + [_df4(p["df"]) for p in per] + [""])
    R.append(["PV FCFF"] + [fmt.miliar(p["pv"]) for p in per] + [""])
    R.append(B("Blok 2: Nilai terminal Gordon"))
    R.append(["FCFF terminal (= FCFF terakhir x (1+g))"] + [""] * n_pad +
              [fmt.miliar(term_fcf)])
    R.append(["Pertumbuhan terminal g (di bawah risk-free)"] + [""] * n_pad +
              [fmt.pct(g)])
    R.append(["Terminal Value (undiscounted)"] + [""] * n_pad + [fmt.miliar(tv)])
    R.append(["Faktor diskonto terminal"] + [""] * n_pad + [_df4(df_t)])
    R.append(["PV Terminal Value"] + [""] * n_pad + [fmt.miliar(pv_tv)])
    R.append(B("Blok 3: Jembatan ke nilai skenario"))
    R.append(["Jumlah PV FCFF (Rp miliar)"] + [""] * n_pad +
              [fmt.miliar(val["pv_explicit"])])
    R.append(["(+) PV Terminal Value (Rp miliar)"] + [""] * n_pad +
              [fmt.miliar(val["pv_terminal"])])
    R.append(["(=) Enterprise Value (Rp miliar)"] + [""] * n_pad + [fmt.miliar(ev)])
    R.append(["(-) Utang bersih tanggal valuasi (Rp miliar)"] + [""] * n_pad +
              [fmt.miliar(net_debt)])
    R.append(["(+/-) Minority Interest / Aset non-operasi (Rp miliar)"] + [""] * n_pad +
              ["0 (tidak ada di data Sectors)"])
    R.append(["(=) Nilai Ekuitas Gordon (Rp miliar)"] + [""] * n_pad + [fmt.miliar(eq)])
    R.append(["(/) Saham beredar (saham)"] + [""] * n_pad + [fmt.rp(shares)])
    R.append(["(=) Nilai skenario per Saham Gordon (Rp)"] + [""] * n_pad +
              [fmt.rp(val["ps_gordon"])])
    R.append([f"Silang cek: EV exit (EBITDA x {fmt.mult(exit_mult)}) "
              "(Rp miliar)"] + [""] * n_pad + [fmt.miliar(ev_x)])
    R.append(["Nilai per saham exit (Rp)"] + [""] * n_pad + [fmt.rp(ps_x)])
    R.append(["Nilai skenario gabungan per saham Gordon+exit (Rp)"] + [""] * n_pad +
              [fmt.rp(val.get("dcf_blend", val["tp"]))])
    return _exhibit("Proyeksi FCFF, Nilai Terminal, dan Jembatan Nilai Skenario",
                    cols, R,
                    "Source: Company, Sektoral Estimates; Delta NWC = plug "
                    "penyeimbang; konvensi diskonto mid-year; silang cek "
                    "Gordon vs exit multiple tampil berdampingan", "fcff_bridge")


def wacc_exhibit(intake, fc, val):
    """Opsi A, tabel 2: komponen WACC via CAPM, struktur modal market-value."""
    wi = val["wacc_inputs"]
    teff = _teff(fc)
    rd_after = wi["rd_after_tax"]
    rd_pre = rd_after / (1 - teff) if teff < 1 else rd_after
    D = fc["base"]["debt"] + fc["base"]["other_liab"]
    E = intake["market_cap"]
    wD, wE = D / max(D + E, 1), E / max(D + E, 1)
    rows = [
        ["Risk-free rate IDR (house policy)", fmt.pct(wi["rf"])],
        ["Beta", fmt.mult(wi["beta"])],
        ["Equity Risk Premium", fmt.pct(wi["erp"])],
        ["(=) Cost of Equity (Rf + Beta x ERP)", fmt.pct(wi["re"])],
        ["Cost of Debt pra-pajak", fmt.pct(rd_pre)],
        ["Tarif pajak efektif", fmt.pct(teff)],
        ["(=) Cost of Debt setelah pajak", fmt.pct(rd_after)],
        [f"Bobot utang (D Rp{fmt.miliar(D)} miliar, market value)",
         fmt.pct(wD)],
        [f"Bobot ekuitas (E Rp{fmt.miliar(E)} miliar, market value)",
         fmt.pct(wE)],
        ["WACC", fmt.pct(val["wacc"])],
    ]
    return _exhibit("Komponen WACC", ["Komponen", "Nilai"], rows,
                    "Source: Company, Sektoral Estimates; Rf = house policy parameter, compared with dated INDOGB 10Y in the policy benchmark table; "
                    "ERP = Damodaran, Beta = Bloomberg; tanpa CRP ganda", "wacc_components")


def sens_matrix_5x3(intake, fc, val):
    """Opsi A, tabel 3: WACC base+-1pp/0,5pp x g terminal, sel base bertanda."""
    w0 = val["wacc"]
    g0 = val["wacc_inputs"]["g"]
    m = val["wacc_inputs"]["exit_mult"]
    nd = val["net_debt"]
    sh = intake["shares"]
    dws = (-0.01, -0.005, 0.0, 0.005, 0.01)
    ggs = (g0 - 0.01, g0, g0 + 0.01)

    def _tp(dw, gg):
        c = _valuation._core(fc, sh, w0 + dw, gg, m, nd)
        return fmt.tick((c["ps_g"] + c["ps_x"]) / 2)

    cols = ["WACC / g terminal"] + [
        f"g {fmt.pct(gg)}" + (" (base)" if gg == g0 else "") for gg in ggs]
    rows = []
    for dw in dws:
        lab = f"WACC {fmt.pct(w0 + dw)}" + (" (base)" if dw == 0 else "")
        cells = [fmt.rp(_tp(dw, gg)) + (" *" if dw == 0 and gg == g0 else "")
                 for gg in ggs]
        rows.append([lab] + cells)
    return _exhibit("Sensitivitas Nilai Skenario per Saham (Rp)", cols, rows,
                    "Source: Sektoral Estimates; sel base (*) = skenario dasar; "
                    "rerata Gordon + exit, basis skenario sama", "value_sensitivity")


def ddm_exhibits(payout, roae_fwd, bvps, coe, g=0.035):
    """Opsi B: blok dividen Gordon + baris Inverse CoE dalam satu exhibit."""
    eps = roae_fwd * bvps
    dps = eps * payout
    dps_t = dps * (1 + g)
    tv = dps_t / (coe - g)
    df = 1 / (1 + coe)
    fv_gordon = tv * df
    pbv = (roae_fwd - g) / (coe - g)
    fv_pbv = pbv * bvps
    rows = [
        ["Blok 1: Dividen Gordon (diskonto CoE, valuasi ekuitas langsung)", ""],
        ["BVPS forward (Rp)", fmt.rp(bvps)],
        ["ROAE forward", fmt.pct(roae_fwd)],
        ["EPS forward (= ROAE x BVPS, Rp)", fmt.rp(eps)],
        ["Payout ratio", fmt.pct(payout)],
        ["DPS forward (= EPS x payout, Rp)", fmt.rp(dps)],
        ["DPS terminal (= DPS x (1+g), Rp)", fmt.rp(dps_t)],
        ["Pertumbuhan terminal g", fmt.pct(g)],
        ["Cost of Equity", fmt.pct(coe)],
        ["Terminal Value (= DPS terminal/(CoE-g), Rp)", fmt.rp(tv)],
        ["Faktor diskonto (1/(1+CoE))", _df4(df)],
        ["Nilai skenario per Saham Gordon (Rp)", fmt.rp(fv_gordon)],
        ["Blok 2: Inverse Cost of Equity", ""],
        ["ROAE forward", fmt.pct(roae_fwd)],
        ["Fair P/BV (= (ROAE-g)/(CoE-g))", fmt.mult(pbv, dec=2)],
        ["BVPS forward (Rp)", fmt.rp(bvps)],
        ["Nilai skenario (= P/BV x BVPS, Rp)", fmt.rp(fv_pbv)],
    ]
    return _exhibit("Prakiraan Dividen, Nilai Terminal, dan Inverse CoE",
                    ["Uraian", "Nilai"], rows,
                    "Source: Company, Sektoral Estimates; DDM = valuasi "
                    "ekuitas langsung, bukan WACC", "ddm_bridge")


def rnav_exhibits(assets, cash, debt, overhead, shares, discount):
    """Opsi C: blok NAV per aset + jembatan skenario = RNAVps x (1-diskon).

    assets: list {"nama", "nav", "kepemilikan" (0-1), opsional "ukuran"}.
    """
    attr = [a["nav"] * a["kepemilikan"] for a in assets]
    total_nav = sum(attr)
    rnav = total_nav + cash - debt - overhead
    rnavps = rnav / shares
    tp = rnavps * (1 - discount)
    rows = [["Blok 1: NAV per aset (Rp miliar)", ""]]
    for a, at in zip(assets, attr):
        ukuran = f"; {a['ukuran']}" if a.get("ukuran") else ""
        rows.append([f"{a['nama']} (NAV Rp{fmt.miliar(a['nav'])} miliar x "
                     f"{fmt.pct(a['kepemilikan'])} kepemilikan{ukuran})",
                     fmt.miliar(at)])
    rows.append(["Jumlah NAV atribuibel (Rp miliar)", fmt.miliar(total_nav)])
    rows += [
        ["Blok 2: Jembatan RNAV ke skenario nilai", ""],
        ["(+) Kas dan setara kas (Rp miliar)", fmt.miliar(cash)],
        ["(-) Total utang (Rp miliar)", fmt.miliar(debt)],
        ["(-) Overhead korporat, PV biaya tak teratribusi (Rp miliar)",
         fmt.miliar(overhead)],
        ["(=) Total RNAV (Rp miliar)", fmt.miliar(rnav)],
        ["(/) Saham beredar (saham)", fmt.rp(shares)],
        ["(=) RNAV per saham (Rp)", fmt.rp(rnavps)],
        [f"(-) Diskon RNAV {fmt.pct(discount)} (judgment analis)", ""],
        ["(=) Nilai skenario (= RNAVps x (1-diskon), Rp)", fmt.rp(tp)],
    ]
    return _exhibit("Rincian Aset dan Jembatan RNAV", ["Uraian", "Nilai"],
                    rows,
                    "Source: Company, Sektoral Estimates; diskon RNAV = "
                    "judgment analis", "rnav_bridge")
