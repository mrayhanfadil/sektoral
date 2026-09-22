"""Catatan metodologi kondisional (spesifikasi Instruksi-Report-v3.md 3.1, 4.1, 4.4).

Aturan: setiap kalimat keterbatasan harus mencerminkan data yang
benar-benar dipakai laporan ini. Kalimat "tidak ada di cache" dilarang
muncul untuk data yang sudah ditampilkan di exhibit.
"""

from . import fmt


def _is_miner(intake):
    sub = (intake.get("sub_sector") or "").lower()
    ind = (intake.get("industry") or "").lower()
    return sub.startswith("metal") or ind.startswith("metal")


def _is_bank(intake):
    hay = ((intake.get("sub_sector") or "") + " " +
           (intake.get("industry") or "")).lower()
    return "bank" in hay


def _fmt_tahun(x):
    return ("%.1f" % x).replace(".", ",")


def methodology_notes(intake, fc, val, mineops_or_none):
    """Catatan metodologi kondisional: miner, bank, FX."""
    notes = list(val.get("notes") or []) if isinstance(val, dict) else []
    out = [n for n in notes
           if "umur cadangan tidak ada di cache" not in n]
    if _is_miner(intake):
        life = None
        basis = None
        if isinstance(mineops_or_none, dict):
            life = mineops_or_none.get("reserve_life_cu_yr")
            basis = mineops_or_none.get("reserve_life_basis")
        if life:
            s = ("keterbatasan model: emiten tambang idealnya DCF sampai "
                 "akhir umur aset tanpa terminal perpetual; umur cadangan "
                 "tembaga terhitung %s tahun (%s) dan ditampilkan di exhibit, "
                 "sehingga Gordon + exit multiple dipakai sebagai proksi "
                 "karena profil produksi tahunan tidak ada di cache."
                 % (_fmt_tahun(life), basis or "basis cadangan"))
            out.append(s)
        else:
            out.append("keterbatasan model: emiten tambang idealnya DCF "
                       "sampai akhir umur aset tanpa terminal perpetual; "
                       "umur cadangan tidak ada di cache sehingga dipakai "
                       "Gordon + exit multiple sebagai proksi.")
    if _is_bank(intake) and not any("bank idealnya" in n for n in out):
        out.append("keterbatasan model: bank idealnya pendekatan GGM ekuitas "
                   "atau residual income dengan silang cek P/BV vs ROE; "
                   "proksi FCFF dipakai karena kerangka ringan generic.")
    if not any(n.startswith("model dibangun") for n in out):
        out.append("model dibangun di mata uang pelaporan (Rp); FX = 1.")
    return out[:5]


def extreme_tp_lines(upside, tp, price, driver_sentence, limitation_sentence):
    """Dua baris TP ekstrem per spesifikasi 4.4, kosong bila |upside|<=50%."""
    if abs(upside) <= 0.5:
        return []
    arah = "di atas" if upside > 0 else "di bawah"
    tesis = ("TP Rp%s (%s%s %s harga Rp%s) didukung %s."
             % (fmt.rp(tp), "+" if upside > 0 else "",
                fmt.pct(upside), arah, fmt.rp(price), driver_sentence))
    batas = "Keterbatasan utama: %s." % limitation_sentence.rstrip(".")
    return [tesis, batas]


def capex_impact_line(has_project_capex, missing_what):
    """Kalimat dampak tangga fallback capex proyek level 4 (spesifikasi 3.1)."""
    if has_project_capex:
        return ("capex proyek mengikuti guidance/timeline yang tersedia "
                "di cache dan tercermin di FCFF.")
    return ("capex proyek Rp0 karena %s tidak ada di cache; bila proyek "
            "berjalan, FCFF overstated sebesar belanja yang hilang."
            % (missing_what or "guidance/timeline"))


def revenue_bridge(fy1_revenue_bn, volume_total, ref_price):
    """Revenue bridge tambang: realized price tersirat vs harga acuan.

    implied_price = revenue FY1 / total volume; gap_pct dihitung relatif
    ke harga acuan; selisih > 25% wajib dijelaskan (spesifikasi 3.1).
    """
    if not volume_total or not ref_price:
        return {"implied_price": None, "gap_pct": None,
                "needs_explanation": False}
    implied = fy1_revenue_bn / volume_total
    gap = implied / ref_price - 1
    return {"implied_price": implied, "gap_pct": gap,
            "needs_explanation": abs(gap) > 0.25}
