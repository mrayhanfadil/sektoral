"""Exhibit valuasi per Opsi A/B/C (Instruksi-Report-v3, seksi 4.5).

Setiap builder mengembalikan SATU exhibit dict (penomoran "n" = None,
diisi orkestrator mengikuti urutan global laporan):

    {"n": None, "judul": ..., "tipe": "tabel",
     "data": {"cols": [...], "rows": [...]},
     "catatan_sumber": ...}

Semua uang diformat via app.fmt. Label Bahasa Indonesia, tanpa emoji.
"""

from . import fmt
from . import valuation as _valuation


def _exhibit(judul, cols, rows, note="Source: Company, Sektoral Estimates"):
    return {"n": None, "judul": judul, "tipe": "tabel",
            "data": {"cols": cols, "rows": rows},
            "catatan_sumber": note}


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
        # forecast, sehingga FCFF tampil = fcf forecast (sumber TP).
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

    # Blok 3 memakai angka val (sumber kebenaran TP) agar terikat persis.
    ev = val["ev_gordon"]
    eq = ev - net_debt
    ev_x = f_last["ebitda"] * exit_mult
    ps_x = (ev_x - net_debt) / ((1 + wacc) ** len(rows3) * shares)

    cols = ["Uraian"] + labels + ["Terminal / Total"]
    B = lambda t: [t, "", "", "", ""]  # noqa: E731
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
    R.append(["FCFF terminal (= FCFF terakhir x (1+g))", "", "", "",
              fmt.miliar(term_fcf)])
    R.append(["Pertumbuhan terminal g (di bawah risk-free)", "", "", "",
              fmt.pct(g)])
    R.append(["Terminal Value (undiscounted)", "", "", "", fmt.miliar(tv)])
    R.append(["Faktor diskonto terminal", "", "", "", _df4(df_t)])
    R.append(["PV Terminal Value", "", "", "", fmt.miliar(pv_tv)])
    R.append(B("Blok 3: Jembatan ke nilai wajar"))
    R.append(["Jumlah PV FCFF (Rp miliar)", "", "", "",
              fmt.miliar(val["pv_explicit"])])
    R.append(["(+) PV Terminal Value (Rp miliar)", "", "", "",
              fmt.miliar(val["pv_terminal"])])
    R.append(["(=) Enterprise Value (Rp miliar)", "", "", "", fmt.miliar(ev)])
    R.append(["(-) Utang bersih tanggal valuasi (Rp miliar)", "", "", "",
              fmt.miliar(net_debt)])
    R.append(["(=) Nilai Ekuitas Gordon (Rp miliar)", "", "", "",
              fmt.miliar(eq)])
    R.append(["(/) Saham beredar (saham)", "", "", "", fmt.rp(shares)])
    R.append(["(=) Nilai Wajar per Saham Gordon (Rp)", "", "", "",
              fmt.rp(val["ps_gordon"])])
    R.append([f"Silang cek: EV exit (EBITDA x {fmt.mult(exit_mult)}) "
              "(Rp miliar)", "", "", "", fmt.miliar(ev_x)])
    R.append(["Nilai per saham exit (Rp)", "", "", "", fmt.rp(ps_x)])
    R.append(["Nilai Wajar per Saham rata-rata Gordon+exit (Rp)", "", "", "",
              fmt.rp(val["tp"])])
    return _exhibit("Prakiraan FCFF, Nilai Terminal, dan Jembatan Nilai Wajar",
                    cols, R,
                    "Source: Company, Sektoral Estimates; Delta NWC = plug "
                    "penyeimbang; konvensi diskonto mid-year; silang cek "
                    "Gordon vs exit multiple tampil berdampingan")


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
        ["Risk-free rate (INDOGB 10Y)", fmt.pct(wi["rf"])],
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
                    "Source: Company, Sektoral Estimates; Rf = INDOGB 10Y, "
                    "ERP = Damodaran, Beta = Bloomberg; tanpa CRP ganda")


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
        return round((c["ps_g"] + c["ps_x"]) / 2 / 10) * 10

    cols = ["WACC / g terminal"] + [
        f"g {fmt.pct(gg)}" + (" (base)" if gg == g0 else "") for gg in ggs]
    rows = []
    for dw in dws:
        lab = f"WACC {fmt.pct(w0 + dw)}" + (" (base)" if dw == 0 else "")
        cells = [fmt.rp(_tp(dw, gg)) + (" *" if dw == 0 and gg == g0 else "")
                 for gg in ggs]
        rows.append([lab] + cells)
    return _exhibit("Sensitivitas Nilai Wajar per Saham (Rp)", cols, rows,
                    "Source: Sektoral Estimates; sel base (*) = TP base; "
                    "rerata Gordon + exit, basis sama dengan TP")


def ddm_exhibits(payout, roae_fwd, bvps, coe, g=0.025):
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
        ["Nilai Wajar per Saham Gordon (Rp)", fmt.rp(fv_gordon)],
        ["Blok 2: Inverse Cost of Equity", ""],
        ["ROAE forward", fmt.pct(roae_fwd)],
        ["Fair P/BV (= (ROAE-g)/(CoE-g))", fmt.mult(pbv, dec=2)],
        ["BVPS forward (Rp)", fmt.rp(bvps)],
        ["Nilai Wajar (= P/BV x BVPS, Rp)", fmt.rp(fv_pbv)],
    ]
    return _exhibit("Prakiraan Dividen, Nilai Terminal, dan Inverse CoE",
                    ["Uraian", "Nilai"], rows,
                    "Source: Company, Sektoral Estimates; DDM = valuasi "
                    "ekuitas langsung, bukan WACC")


def rnav_exhibits(assets, cash, debt, overhead, shares, discount):
    """Opsi C: blok NAV per aset + jembatan ke TP = RNAVps x (1-diskon).

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
        ["Blok 2: Jembatan RNAV ke target price", ""],
        ["(+) Kas dan setara kas (Rp miliar)", fmt.miliar(cash)],
        ["(-) Total utang (Rp miliar)", fmt.miliar(debt)],
        ["(-) Overhead korporat, PV biaya tak teratribusi (Rp miliar)",
         fmt.miliar(overhead)],
        ["(=) Total RNAV (Rp miliar)", fmt.miliar(rnav)],
        ["(/) Saham beredar (saham)", fmt.rp(shares)],
        ["(=) RNAV per saham (Rp)", fmt.rp(rnavps)],
        [f"(-) Diskon RNAV {fmt.pct(discount)} (judgment analis)", ""],
        ["(=) Target Price (= RNAVps x (1-diskon), Rp)", fmt.rp(tp)],
    ]
    return _exhibit("Rincian Aset dan Jembatan RNAV", ["Uraian", "Nilai"],
                    rows,
                    "Source: Company, Sektoral Estimates; diskon RNAV = "
                    "judgment analis")
