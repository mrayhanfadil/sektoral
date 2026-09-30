"""Catatan metodologi kondisional (spesifikasi Instruksi-Report-v3.md 3.1, 4.1, 4.4).

Aturan: setiap kalimat keterbatasan harus mencerminkan data yang
benar-benar dipakai laporan ini. Kalimat "tidak ada di data Sectors" dilarang
muncul untuk data yang sudah ditampilkan di exhibit.

Each sentence has an English form beside the Indonesian one; the producers
take ``lang`` ("id" default), and ``localize_note`` turns a stored Indonesian
note into English for the English Company Update.
"""
import re

from . import fmt

# (Indonesian, English) per sentence; %s slots are filled in the same order.
_TEXT = {
    "miner_life": (
        "keterbatasan model: emiten tambang idealnya DCF sampai "
        "akhir umur aset tanpa terminal perpetual; umur cadangan "
        "tembaga terhitung %s tahun (%s) dan ditampilkan di exhibit, "
        "sehingga Gordon + exit multiple dipakai sebagai proksi "
        "karena profil produksi tahunan tidak ada di data Sectors.",
        "model limitation: a miner is ideally valued by DCF to the end of asset life with no "
        "perpetual terminal; copper reserve life is %s years (%s) and shown in the exhibits, "
        "so Gordon + exit multiple serve as a proxy because the annual production profile is "
        "not in Sectors data."),
    "miner_no_life": (
        "keterbatasan model: emiten tambang idealnya DCF "
        "sampai akhir umur aset tanpa terminal perpetual; "
        "umur cadangan tidak ada di data Sectors sehingga dipakai "
        "Gordon + exit multiple sebagai proksi.",
        "model limitation: a miner is ideally valued by DCF to the end of asset life with no "
        "perpetual terminal; reserve life is not in Sectors data, so Gordon + exit multiple "
        "serve as a proxy."),
    "bank": (
        "keterbatasan model: bank idealnya pendekatan GGM ekuitas "
        "atau residual income dengan silang cek P/BV vs ROE; "
        "proksi FCFF dipakai karena kerangka ringan generic.",
        "model limitation: a bank is ideally valued by an equity GGM or residual income with a "
        "P/BV vs ROE cross-check; an FCFF proxy is used because the light framework is generic."),
    "currency": ("model dibangun di mata uang pelaporan (Rp); FX = 1.",
                 "the model is built in the reporting currency (Rp); FX = 1."),
    "explicit_period": ("periode eksplisit 3 tahun (template ringan), bukan 5 tahun standar.",
                        "3-year explicit period (light template), not the standard 5 years."),
    "capex_sourced": ("capex proyek mengikuti guidance/timeline yang tersedia "
                      "di data Sectors dan tercermin di FCFF.",
                      "project capex follows the guidance/timeline available in Sectors data "
                      "and is reflected in FCFF."),
    "capex_missing": ("capex proyek Rp0 karena %s tidak ada di data Sectors; bila proyek "
                      "berjalan, FCFF overstated sebesar belanja yang hilang.",
                      "project capex is Rp0 because %s is not in Sectors data; if the project "
                      "proceeds, FCFF is overstated by the missing spend."),
}
# What the English note says for the words a note fills in.
_FILL_EN = {"basis cadangan": "reserve basis", "guidance/timeline": "guidance/timeline",
            "volume penjualan dan jadwal investasi": "sales volume and investment schedule"}


def _say(key, lang, *fill):
    text = _TEXT[key][1 if lang == "en" else 0]
    if lang == "en":
        fill = tuple(_FILL_EN.get(f, f) for f in fill)
    return text % fill if fill else text


def _pattern(key):
    body = re.escape(_TEXT[key][0]).replace(re.escape("%s"), "(.+?)")
    return re.compile(body)


_PATTERNS = {key: _pattern(key) for key in _TEXT}


def localize_note(note, lang="id"):
    """A stored note this module wrote, in `lang`; any other text unchanged."""
    if lang == "id" or not isinstance(note, str):
        return note
    for key, pattern in _PATTERNS.items():
        found = pattern.fullmatch(note)
        if found:
            return _say(key, lang, *(fmt.localize(g, lang) for g in found.groups()))
    return note


def _is_miner(intake):
    sub = (intake.get("sub_sector") or "").lower()
    ind = (intake.get("industry") or "").lower()
    return sub.startswith("metal") or ind.startswith("metal")


def _is_bank(intake):
    hay = ((intake.get("sub_sector") or "") + " " +
           (intake.get("industry") or "")).lower()
    return "bank" in hay


def _fmt_tahun(x, lang="id"):
    text = "%.1f" % x
    return text if lang == "en" else text.replace(".", ",")


def methodology_notes(intake, fc, val, mineops_or_none, lang="id"):
    """Catatan metodologi kondisional: miner, bank, FX."""
    notes = list(val.get("notes") or []) if isinstance(val, dict) else []
    out = [n for n in notes
           if "umur cadangan tidak ada di" not in n]
    if _is_miner(intake):
        life = None
        basis = None
        if isinstance(mineops_or_none, dict):
            life = mineops_or_none.get("reserve_life_cu_yr")
            basis = mineops_or_none.get("reserve_life_basis")
        if life:
            out.append(_say("miner_life", lang, _fmt_tahun(life, lang), basis or "basis cadangan"))
        else:
            out.append(_say("miner_no_life", lang))
    if _is_bank(intake) and not any("bank idealnya" in n or "a bank is ideally" in n for n in out):
        out.append(_say("bank", lang))
    if not any(n.startswith(("model dibangun", "the model is built")) for n in out):
        out.append(_say("currency", lang))
    out.append(_say("explicit_period", lang))
    return out[:6]


def extreme_tp_lines(upside, tp, price, driver_sentence, limitation_sentence):
    """Dua baris TP ekstrem per spesifikasi 4.4, kosong bila tidak ekstrem."""
    from . import gate_thresholds as _gt
    if not _gt.is_extreme_ratio(upside):
        return []
    arah = "di atas" if upside > 0 else "di bawah"
    tesis = ("TP Rp%s (%s%s %s harga Rp%s) didukung %s."
             % (fmt.rp(tp), "+" if upside > 0 else "",
                fmt.pct(upside), arah, fmt.rp(price), driver_sentence))
    batas = "Keterbatasan utama: %s." % limitation_sentence.rstrip(".")
    return [tesis, batas]


def capex_impact_line(has_project_capex, missing_what, lang="id"):
    """Kalimat dampak tangga fallback capex proyek level 4 (spesifikasi 3.1)."""
    if has_project_capex:
        return _say("capex_sourced", lang)
    return _say("capex_missing", lang, missing_what or "guidance/timeline")


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
