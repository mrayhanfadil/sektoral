"""Template harness: spec/Struktur-Template.md as named, machine-checked rules.

Every rule of the report template that can be read off the report document is
a check with an id (``T1.numbering``, ``T7.tieouts`` ...), a fixed severity and
an owner. The mapping from template rule to check, the severity policy and the
decisions that settle template-vs-spec conflicts are in
``docs/harness-template-rules.md``; checks on the rendered HTML/PDF text live in
``app/harness/render_check.py``.

Severity: ``blocker`` when the failure misleads a reader or breaks a tie-out
(blank forecast cells, broken tie-outs, a balance sheet that does not balance,
numbering, a missing mandatory valuation exhibit, non-IDX peers, TP or method
that differ between the cover and the valuation page); ``warning`` for
presentation rules that do not change meaning. ``run_all`` adds every failed
blocker as ``T.<id>`` and so forces ``draft_non_distributable``.

Standalone::

    python -m app.harness.template out/demo-reports [TICKERS] [--render] [--json]

prints one table per ticker (check id, severity, result, detail) and exits 1
when any blocker fails. ``--render`` also renders each report with
``app.render`` and runs ``render_check`` on it, and on ``<folder>/<T>.pdf`` when
the file exists and ``pypdf`` is installed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.harness.profiles import normalize as _normalize_profile  # noqa: E402
from app.fmt import DEFAULT_SOURCE  # noqa: E402

# Switch: template checks run inside run_all (fail closed). One place to turn
# them off, e.g. while bisecting a build: SEKTORAL_TEMPLATE_HARNESS=0.
import os  # noqa: E402

ENABLED = os.environ.get("SEKTORAL_TEMPLATE_HARNESS", "1") != "0"

BLOCKER, WARNING = "blocker", "warning"
PASS, FAIL, NA = "lolos", "gagal", "tidak_berlaku"
HOUSE_SOURCE = DEFAULT_SOURCE

# id -> (severity, owner, rule). Owners: present (report_extras/narrative),
# layout (render/fmt), model (forecast_statements/valuation), peers.
CHECKS: dict[str, tuple[str, str, str]] = {
    "T1.exhibit_label": (WARNING, "present", "judul exhibit deskriptif, bukan generik"),
    "T1.numbering": (BLOCKER, "present", "nomor exhibit global 1..N sesuai urutan baca"),
    "T1.title_period_range": (BLOCKER, "present", "rentang periode di judul = kolom yang tampil"),
    "TF.forecast_cells": (BLOCKER, "model", "semua sel proyeksi terisi (angka atau n.m.)"),
    "TF.nm_reason": (BLOCKER, "present", "sel n.m. punya alasan di catatan exhibit"),
    "TF.actual_cells": (WARNING, "present", "sel aktual tanpa NA/kosong/- telanjang"),
    "TF.display_horizon": (BLOCKER, "present", "laba rugi/neraca/arus kas/rasio/grafik: 2A+3F"),
    "TF.chart_history": (WARNING, "present", "grafik Slide 3 tanpa tahun di luar 2A+3F"),
    "TF.chart_forecast_nm": (WARNING, "present", "grafik keempat hanya aktual, alasan tertulis"),
    "TF.valuation_horizon": (BLOCKER, "model", "tabel valuasi lima tahun proyeksi berurutan"),
    "TF.period_labels": (WARNING, "present", "label periode 2024A / FY26F"),
    "T2.cover_rating_block": (BLOCKER, "present", "label skenario nilai informasional di cover"),
    "T2.rating_status": (WARNING, "present", "status skenario nilai indikatif atau dalam peninjauan"),
    "T2.price_box": (BLOCKER, "present", "harga, nilai model, selisih = nilai model/harga - 1"),
    "T2.stats_block": (WARNING, "present", "saham, kap. pasar Rp/US$, ADTV Rp/US$, free float, pemegang saham"),
    "T2.relative_chart": (WARNING, "present", "exhibit harga relatif terhadap IHSG di cover"),
    "T2.thesis_subtitle": (WARNING, "present", "subjudul tesis, bukan judul generik"),
    "T2.cover_bullets": (WARNING, "present", "tiga bullet satu kalimat; bullet 3 nilai model per saham"),
    "T2.cover_paragraphs": (WARNING, "present", "tiga paragraf dengan subjudul"),
    "T2.valuation_paragraph": (WARNING, "present", "paragraf valuasi: metode + parameter, CAGR FY26-28F, multiple pada nilai model"),
    "T2.cover_tp_method": (BLOCKER, "present", "nilai model dan metode sama di cover dan halaman valuasi"),
    "T2.key_financials_rows": (BLOCKER, "present", "baris Key Financials per profile"),
    "T2.key_financials_order": (WARNING, "present", "urutan baris Key Financials"),
    "T2.key_financials_cols": (BLOCKER, "present", "kolom Key Financials 2A+3F"),
    "TN.one_decimal": (WARNING, "present", "multiple dan persentase satu desimal"),
    "T3.combo_charts": (BLOCKER, "present", "grafik pendapatan, EBITDA, laba bersih (bar + garis)"),
    "T3.chart_style": (WARNING, "present", "bar + garis, aktual vs proyeksi, narasi grafik"),
    "T3.chart4_by_profile": (WARNING, "present", "grafik keempat sesuai profile"),
    "T3.tieout_key_financials": (BLOCKER, "present", "angka Slide 3 = Key Financials"),
    "T3.currency_consistency": (BLOCKER, "model", "satu mata uang di Key Financials, laporan keuangan, grafik"),
    "T4.valuation_option_exhibits": (BLOCKER, "present", "exhibit wajib opsi valuasi aktif"),
    "T4.fcff_blocks": (BLOCKER, "present", "FCFF: blok eksplisit, terminal, bridge"),
    "T4.fcff_rows": (WARNING, "present", "baris FCFF lengkap per template"),
    "T4.wacc_components": (BLOCKER, "present", "WACC: Rf, beta, ERP, CoE, WACC"),
    "T4.wacc_rows": (WARNING, "present", "WACC: CoD, pajak, bobot; WACC baris terakhir"),
    "T4.sensitivity_grid_base_highlight": (BLOCKER, "model", "sel basis sensitivitas = nilai wajar/TP"),
    "T4.sensitivity_grid_shape": (WARNING, "model", "grid lima langkah diskonto x >= 3 kolom"),
    "T4.ddm_blocks": (BLOCKER, "present", "DDM: blok dividen dan terminal, CoE bukan WACC"),
    "T4.ddm_rows": (WARNING, "present", "baris DDM lengkap per template"),
    "T4.coe_components": (BLOCKER, "present", "CoE: Rf, beta, ERP, CoE"),
    "T4.rnav_bridge": (BLOCKER, "present", "RNAV/SOTP: NAV aset + bridge ke per saham"),
    "T4.rnav_rows": (WARNING, "present", "RNAV: kepemilikan, jumlah NAV, overhead, diskon RNAV"),
    "T4.discount_rate_per_asset": (WARNING, "present", "tingkat diskonto per aset"),
    "T4.rf_beta_erp_sources": (WARNING, "present", "sumber Rf, beta, ERP dicatat"),
    "T4.discount_rate_currency": (BLOCKER, "model", "Rf sesuai mata uang model; tanpa CRP ganda"),
    "T4.terminal_growth_cap": (BLOCKER, "model", "g terminal <= risk-free rate"),
    "T4.fcf_vs_fcff": (WARNING, "model", "FCF arus kas dan FCFF dalam rentang wajar"),
    "T5.peer_table_median_average_highlight_asof_criteria": (
        WARNING, "present", "tabel peer: median, rata-rata, baris emiten, kriteria, tanggal"),
    "T5.peers_idx_only": (BLOCKER, "peers", "peer hanya emiten BEI (IDX)"),
    "T5.peer_crosscheck_consistency": (BLOCKER, "present",
                                       "nilai/median peer sesuai rantai metode dan >= 3 multiple valid"),
    "T5.hist_bands_mean_median_marker": (WARNING, "present", "band P/E dan P/BV 1 tahun: mean, median, posisi kini"),
    "T5.implied_price_mean_median_two_multiples": (WARNING, "present", "harga implisit mean dan median, >= 2 multiple"),
    "T5.disclaimer": (WARNING, "present", "disclaimer: cross-check, bukan TP, driver tetap"),
    "T5.peer_narrative": (WARNING, "present", "narasi posisi terhadap median/rata-rata peer"),
    "T6.income_statement_lines": (BLOCKER, "present", "baris laba rugi per template"),
    "T6.income_statement_order": (WARNING, "present", "urutan baris laba rugi"),
    "T6.balance_sheet_lines_and_balance": (BLOCKER, "model", "baris neraca; total aset = liabilitas + ekuitas"),
    "T6.balance_sheet_subtotals": (WARNING, "model", "subtotal neraca sama dengan jumlah barisnya"),
    "T6.balancing_debt_share": (WARNING, "model",
                                "pinjaman penyeimbang kas forecast <= 25% dari total ekuitas"),
    "T7.cash_flow_sections_and_tieout": (BLOCKER, "model", "arus kas: tiga blok, rekonsiliasi kas proyeksi"),
    "T7.cash_flow_actual_reconciliation": (WARNING, "present", "rekonsiliasi kas tahun aktual (efek kurs)"),
    "T7.key_ratio_sections_format": (BLOCKER, "present", "baris rasio utama per template"),
    "T7.key_ratio_format": (WARNING, "present", "blok rasio dan satu desimal"),
    "T7.tieouts": (BLOCKER, "model", "laba bersih LR = KF = awal AK; kas akhir AK = kas neraca"),
}

# ----------------------------------------------------------------- parsing

_WS = re.compile(r"\s+")
_NUM_RE = re.compile(
    r"^(?P<open>\()?\s*(?P<cur>Rp|US\$|USD)?\s*(?P<sign>[-−+])?\s*(?:Rp|US\$)?\s*"
    r"(?P<int>\d{1,3}(?:\.\d{3})+|\d+)(?:,(?P<dec>\d+))?\s*(?P<unit>%|x|pp)?\s*(?P<close>\))?$")
_BLANK_TOKENS = {"", "-", "--", "–", "—", "na", "n/a", "n.a.", "n.a", "none", "null", "nan",
                 "tidak tersedia", "tidak ada"}
# "n.m." and spec §4.5's "belum dimodelkan": allowed only with the reason in
# the exhibit note (TF.nm_reason); bare NA, n.a., "-" and blanks never.
_NM = re.compile(r"^(n\.\s?m\.?(?=\s|$|\(|:|;|,)|(belum|tidak) dimodelkan\b)", re.I)


def _clean(text) -> str:
    return _WS.sub(" ", str(text if text is not None else "")).strip()


def parse_num(cell):
    """Indonesian display number -> (value, decimals, unit) or None.

    ``3.520,0`` -> 3520.0; ``(139,1)`` and ``-139,1`` -> -139.1; ``12,4x``;
    ``-31,1%``; ``Rp5.925``; ``(Rp234)``. Words or a second number -> None.
    """
    if isinstance(cell, bool) or cell is None:
        return None
    if isinstance(cell, (int, float)):
        return None if (isinstance(cell, float) and math.isnan(cell)) else (float(cell), 0, "")
    m = _NUM_RE.match(_clean(cell))
    if not m or bool(m.group("open")) != bool(m.group("close")):
        return None
    value = float(m.group("int").replace(".", "") + ("." + m.group("dec") if m.group("dec") else ""))
    if m.group("open") or m.group("sign") in ("-", "−"):
        value = -value
    return value, len(m.group("dec") or ""), m.group("unit") or ""


def num(cell):
    parsed = parse_num(cell)
    return parsed[0] if parsed else None


def classify_cell(cell) -> str:
    """``num``, ``nm`` (not meaningful, allowed with a reason), ``blank``
    (NA, n.a., -, empty, null, "belum dimodelkan") or ``text``."""
    if cell is None:
        return "blank"
    if isinstance(cell, bool):
        return "text"
    if isinstance(cell, (int, float)):
        return "blank" if isinstance(cell, float) and math.isnan(cell) else "num"
    s = _clean(cell)
    if s.lower() in _BLANK_TOKENS:
        return "blank"
    if _NM.match(s):
        return "nm"
    if parse_num(s) is not None:
        return "num"
    # A capped growth rate: '>500%'.
    if re.fullmatch(r"[<>]\s?\d[\d.,]*%", s):
        return "num"
    # A figure with a short unit or qualifier: 'Rp860 miliar', '13,5x (p28)', '1.683 ha'.
    if re.match(r"^\(?[-−+]?\s?(?:Rp|US\$)?\s?[-−]?\d", s) and len(s.split()) <= 4:
        return "num"
    return "text"


def _descriptive_row(row) -> bool:
    """An annotation row ('Asumsi | - | H2/H1 1,40x; margin 25% | -'): words,
    no figures. Its empty cells are not missing data."""
    kinds = [classify_cell(c) for c in row[1:]]
    return "text" in kinds and "num" not in kinds


_PERIOD_RE = re.compile(r"^(FY\s?)?(\d{4}|\d{2})\s?([AFE])?$", re.I)


def parse_period(label):
    """Annual period label -> (year, kind) with kind 'A', 'F' or None
    (unsuffixed, read as actual). ``2024``, ``2024A``, ``FY26F``, ``2026F``,
    ``FY2025``. Interim labels (``1H26``) and anything else -> None."""
    m = _PERIOD_RE.match(_clean(label))
    if not m:
        return None
    digits, kind = m.group(2), (m.group(3) or "").upper() or None
    if len(digits) == 2:
        if not (m.group(1) or kind):
            return None
        year = 2000 + int(digits)
    else:
        year = int(digits)
        if not 1990 <= year <= 2100:
            return None
    return year, ("F" if kind == "E" else kind)


def _is_forecast(period) -> bool:
    return bool(period) and period[1] == "F"


def _norm_label(label) -> str:
    """Lower-case label without trailing unit parentheses and sign prefixes:
    'Pendapatan (Rp miliar)' -> 'pendapatan'; '(-) Capex' -> 'capex'."""
    s = _clean(label).lower()
    s = re.sub(r"^(\((?:[+\-=x]|-/\+|\+/-)\)\s*)+", "", s)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()
    return s.rstrip(":").strip()


def _unit(label):
    """(currency, scale) from a unit label: 'Rp miliar' -> ('IDR', 1e9)."""
    s = _clean(label).lower()
    currency = "USD" if re.search(r"us\$|\busd\b", s) else (
        "IDR" if re.search(r"\brp\b|rupiah", s) else None)
    if currency is None:
        return None, None
    scale = 1.0
    for word, size in (("triliun", 1e12), ("miliar", 1e9), (" bn", 1e9), ("juta", 1e6),
                       (" mn", 1e6), ("ribu", 1e3), ("sen", 0.01)):
        if word in s:
            scale = size
            break
    return currency, scale


def _tick(value) -> float:
    for bound, size in ((200, 1), (500, 2), (2000, 5), (5000, 10)):
        if abs(value) < bound:
            return size
    return 25


# --------------------------------------------------------------- exhibits

def exhibits_of(doc) -> list[dict]:
    """Canonical exhibit list: ``doc['exhibits']`` (deduplicated by number)
    or, when absent, the exhibits placed in ``bagian``."""
    top = [e for e in (doc.get("exhibits") or []) if isinstance(e, dict)]
    if top:
        seen, out = set(), []
        for e in top:
            key = (e.get("n"), _clean(e.get("judul")))
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out
    return [e for page in doc.get("bagian") or [] if isinstance(page, dict)
            for e in page.get("exhibit") or [] if isinstance(e, dict)]


def _data(e) -> dict:
    return e.get("data") if isinstance(e.get("data"), dict) else {}


def _cols(e) -> list:
    return list(_data(e).get("cols") or [])


def _rows(e) -> list[list]:
    return [r for r in (_data(e).get("rows") or []) if isinstance(r, list)]


def _title(e) -> str:
    return re.sub(r"^exhibit\s+\d+\.\s*", "", _clean(e.get("judul")), flags=re.I)


def _base_title(e) -> str:
    """Title without a trailing parenthetical (period range, 'bukan target harga')."""
    return _norm_label(_title(e))


def _note(e) -> str:
    parts = [e.get(k) for k in ("catatan_sumber", "source", "catatan", "footnote", "note", "notes")]
    out = []
    for part in parts:
        if isinstance(part, list):
            out.extend(str(p) for p in part)
        elif part:
            out.append(str(part))
    return " ".join(out)


def _period_cols(e):
    """[(index, (year, kind))] of annual period columns (index >= 1)."""
    out = []
    for i, c in enumerate(_cols(e)):
        if i == 0 and e.get("tipe") not in ("combo_panel", "combo_chart"):
            continue
        p = parse_period(c)
        if p:
            out.append((i, p))
    return out


def _is_section_row(row) -> bool:
    label = _clean(row[0]) if row else ""
    rest = [c for c in row[1:] if _clean(c)]
    return bool(label) and not rest and (label.lower().startswith("blok ") or label.endswith(":"))


_STATEMENT_TITLES = {
    "kf": ("key financials",),
    "is": ("laba rugi", "laba rugi bank", "income statement"),
    "bs": ("neraca", "neraca bank", "balance sheet"),
    "cf": ("arus kas", "arus kas bank", "cash flow", "cash flow statement"),
    "ratio": ("rasio utama", "rasio utama bank", "key ratio", "key ratios"),
}


def _find(exs, kind) -> dict | None:
    names = _STATEMENT_TITLES[kind]
    return next((e for e in exs if _base_title(e) in names and e.get("tipe") != "price_chart"), None)


def _combo_series(exs):
    """[(exhibit, series, concept)] for Slide-3 combo charts."""
    out = []
    for e in exs:
        if e.get("tipe") not in ("combo_panel", "combo_chart"):
            continue
        for s in _data(e).get("series") or []:
            if not isinstance(s, dict):
                continue
            label = _clean(s.get("label") or _title(e)).lower()
            title = _title(e).lower()
            concept = "other"
            for key, pat in (("revenue", r"^(pendapatan|revenue|penjualan|sales)\b"),
                             ("ebitda", r"^ebitda\b"),
                             ("net_profit", r"^(laba bersih|net profit|eps)\b")):
                if re.search(pat, label) or (e.get("tipe") == "combo_panel" and re.search(pat, title)):
                    concept = key
                    break
            out.append((e, s, concept))
    return out


# Row concepts: (key, pattern on the normalized label). First match wins;
# each concept takes the first row it matches.
_REVENUE = r"^(pendapatan|penjualan|revenue|sales)( usaha| bersih)?$"
_NET = r"^(laba bersih|net profit|net income)( pemilik induk| yang dapat diatribusikan.*| attributable.*)?$"
KF_ROWS = {
    "nonbank": [("revenue", _REVENUE), ("ebitda", r"^ebitda$"),
                ("ebitda_growth", r"^(pertumbuhan ebitda|ebitda growth)$"),
                ("net_profit", _NET), ("eps", r"^eps$"),
                ("eps_growth", r"^(pertumbuhan eps|eps growth)$"),
                ("per", r"^(per|p/e|pe)$"), ("pbv", r"^(pbv|p/bv|p/b|pb)$"),
                ("ev_ebitda", r"^ev/ebitda$")],
    "bank": [("revenue", _REVENUE), ("net_profit", _NET), ("eps", r"^eps$"),
             ("eps_growth", r"^(pertumbuhan eps|eps growth)$"), ("bvps", r"^bvps$"),
             ("roe", r"^(roe|roae)$"), ("dps", r"^dps$"),
             ("per", r"^(per|p/e|pe)$"), ("pbv", r"^(pbv|p/bv|p/b|pb)$")],
}
KF_EXTRA = [("revenue_growth", r"^(pertumbuhan (pendapatan|penjualan)|revenue growth|sales growth)$"),
            ("np_growth", r"^(pertumbuhan laba bersih|net profit growth)$")]

IS_ROWS = {
    "nonbank": [("revenue", _REVENUE),
                ("cogs", r"^(beban pokok (pendapatan|penjualan)|harga pokok penjualan|cost of (goods sold|revenue)|cogs)$"),
                ("gross_profit", r"^(laba kotor|gross profit)$"),
                ("opex", r"^(beban usaha|beban operasi|operating expenses|opex|sg&a)$"),
                ("ebit", r"^(laba usaha|ebit|operating profit)$"),
                ("interest_income", r"^(pendapatan bunga|pendapatan keuangan|interest income|finance income)$"),
                ("interest_expense", r"^(beban bunga|beban keuangan|interest expense|finance costs?)$"),
                ("other", r"^(pendapatan \(beban\) (lain-lain|non-operasional( lain)?)|other income.*|lain-lain)$"),
                ("pretax", r"^(laba sebelum pajak|pre-tax profit|profit before tax)$"),
                ("tax", r"^(pajak( penghasilan)?|beban pajak( penghasilan)?|income tax)$"),
                ("minority", r"^(kepentingan non-?pengendali|minority interests?|nci)$"),
                ("net_profit", _NET)],
    "bank": [("interest_income", r"^(pendapatan bunga|interest income)$"),
             ("interest_expense", r"^(beban bunga|interest expense)$"),
             ("nii", r"^(pendapatan bunga bersih|net interest income|nii)$"),
             ("non_interest_income", r"^(pendapatan non-? ?bunga|non-interest income|pendapatan operasional lain(nya)?)$"),
             ("ppop", r"^(laba sebelum provisi|ppop|pre-provision operating profit)$"),
             ("provisions", r"^(provisi( dan cadangan)?|beban (provisi|cadangan).*|provisions.*|cadangan kerugian.*)$"),
             ("net_profit", _NET)],
}
IS_NET_PARENT = r"^(laba bersih pemilik induk|laba bersih yang dapat diatribusikan.*|net profit attributable.*)$"
IS_NET_ANY = r"^(laba bersih|net profit|net income)$"

BS_ROWS = {
    "nonbank": [("cash", r"^(kas dan setara kas|kas|cash( and cash equivalents| & cash equivalents)?)$"),
                ("receivables", r"^(piutang usaha|trade receivables)$"),
                ("inventory", r"^(persediaan|inventory|inventories)$"),
                ("other_ca", r"^(aset lancar lain(nya)?|other current assets)$"),
                ("total_ca", r"^(total aset lancar|jumlah aset lancar|total current assets)$"),
                ("fixed_assets", r"^(aset tetap( bersih)?|fixed assets( \(net\))?)$"),
                ("other_nca", r"^(aset tidak lancar lain(nya)?|other non-current assets)$"),
                ("total_assets", r"^(total aset|jumlah aset|total assets)$"),
                ("st_debt", r"^(utang jangka pendek|pinjaman jangka pendek|short-term debt)$"),
                ("payables", r"^(utang usaha|trade payables)$"),
                ("other_cl", r"^(liabilitas lancar lain(nya)?|other current liabilities)$"),
                ("total_cl", r"^(total liabilitas lancar|jumlah liabilitas jangka pendek|total current liabilities)$"),
                ("lt_debt", r"^(utang jangka panjang|pinjaman jangka panjang|long-term debt)$"),
                ("other_ncl", r"^(liabilitas tidak lancar lain(nya)?|other non-current liabilities)$"),
                ("total_liabilities", r"^(total liabilitas|jumlah liabilitas|total liabilities)$"),
                ("equity", r"^(total ekuitas|ekuitas( pemegang saham)?|shareholders'? equity)$"),
                ("total_le", r"^(total liabilitas dan ekuitas|jumlah liabilitas dan ekuitas|total liabilities (and|&) equity)$")],
    "bank": [("gross_loans", r"^(kredit bruto|kredit yang diberikan bruto|gross loans)$"),
             ("loan_provisions", r"^(cadangan kerugian( penurunan nilai)?( kredit)?|provisions?|allowances?)$"),
             ("net_loans", r"^(kredit bersih|net loans)$"),
             ("govt_bonds", r"^(obligasi pemerintah|surat berharga negara|govt bonds|government bonds)$"),
             ("securities", r"^(surat berharga|efek-efek|securities)$"),
             ("earning_assets", r"^(total aset produktif|jumlah aset produktif|total earning assets)$"),
             ("total_assets", r"^(total aset|jumlah aset|total assets)$"),
             ("deposits", r"^(dana pihak ketiga|simpanan nasabah|customer deposits)$"),
             ("equity", r"^(total ekuitas|ekuitas( pemegang saham)?|shareholders'? (funds|equity))$"),
             ("total_le", r"^(total liabilitas dan ekuitas|jumlah liabilitas dan ekuitas|total liabilities (and|&) equity)$")],
}
BS_OPTIONAL_BANK = [("total_liabilities", r"^(total liabilitas|jumlah liabilitas|total liabilities)$")]

CF_ROWS = {
    "nonbank": [("net_profit", r"^(laba bersih|net profit|net income)( pemilik induk)?$"),
                ("da", r"^(depresiasi( dan amortisasi)?|penyusutan( dan amortisasi)?|d&a|depreciation.*)$"),
                ("wc", r"^(perubahan modal kerja|(kenaikan|penurunan).*modal kerja|change in working capital|working capital)$"),
                ("other_op", r"^(pos operasi lain(nya)?|other operating items)$"),
                ("cfo", r"^(jumlah arus kas operasi|arus kas operasi|arus kas bersih dari aktivitas operasi|net cash from operations)$"),
                ("capex", r"^(belanja modal|capex|capital expenditure)$"),
                ("other_inv", r"^(pos investasi lain(nya)?|other investing items)$"),
                ("cfi", r"^(jumlah arus kas investasi|arus kas investasi|arus kas bersih dari aktivitas investasi|net cash from investing)$"),
                ("debt", r"^(penarikan \(pembayaran\) utang|debt raised.*|penambahan \(pelunasan\) utang)$"),
                ("dividends", r"^(dividen dibayar|pembayaran dividen|dividends paid)$"),
                ("equity_raised", r"^(penerbitan \(pembelian kembali\) saham|equity raised.*)$"),
                ("cff", r"^(jumlah arus kas pendanaan|arus kas pendanaan|arus kas bersih dari aktivitas pendanaan|net cash from financing)$"),
                ("net_change", r"^(perubahan kas bersih|kenaikan \(penurunan\) kas bersih|net change in cash)$"),
                ("begin_cash", r"^(kas awal( tahun| periode)?|beginning cash( balance)?)$"),
                ("end_cash", r"^(kas akhir( tahun| periode)?|ending cash( balance)?)$"),
                ("fcf", r"^(arus kas bebas|free cash flow)$")],
}
CF_BANK_REQUIRED = ("net_profit", "cfo", "cfi", "cff", "net_change", "begin_cash", "end_cash")
CF_SECTIONS = (("operasi", r"operasi|operating"), ("investasi", r"investasi|investing"),
               ("pendanaan", r"pendanaan|financing"))

RATIO_ROWS = {
    "nonbank": {
        "growth": [("sales", r"^(pendapatan|penjualan|sales|revenue)$"), ("ebitda", r"^ebitda$"),
                   ("op_profit", r"^(laba usaha|operating profit|ebit)$"),
                   ("net_profit", r"^(laba bersih|net profit)( pemilik induk)?$")],
        "profitability": [("gross_margin", r"^(marjin|margin) laba kotor$|^gross margin$"),
                          ("ebitda_margin", r"^(marjin|margin) ebitda$|^ebitda margin$"),
                          ("op_margin", r"^(marjin|margin) (laba )?usaha$|^operating margin$"),
                          ("net_margin", r"^(marjin|margin) laba bersih$|^net margin$"),
                          ("roaa", r"^roaa$"), ("roae", r"^roae$")],
        "leverage": [("net_gearing", r"^net gearing$|^rasio utang bersih"),
                     ("interest_coverage", r"^(cakupan bunga|interest coverage|rasio cakupan bunga)$")],
    },
    "bank": {
        "all": [("yield_ea", r"yield|imbal hasil"), ("cof", r"biaya dana|cost of funds"),
                ("spread", r"spread|selisih bunga"),
                ("nim", r"marjin bunga bersih|margin bunga bersih|\bnim\b|net interest margin"),
                ("cir", r"biaya terhadap pendapatan|cost ?/ ?income|\bcir\b"),
                ("npl", r"\bnpl\b(?!.*(cakupan|coverage))|kredit bermasalah"),
                ("coverage", r"cakupan|coverage"),
                ("coc", r"biaya kredit|cost of credit"),
                ("ldr", r"\bldr\b|kredit terhadap simpanan|loan to deposit"),
                ("casa", r"\bcasa\b"), ("roae", r"^roae$"), ("roaa", r"^roaa$"),
                ("car", r"\bcar\b|kecukupan modal")],
    },
}


def _match_rows(rows, concepts, full=False):
    """{concept: row} using the first matching row per concept. ``full``
    matches against the whole lower-case label (for parenthesised acronyms)."""
    found: dict[str, list] = {}
    for row in rows:
        if not row or _is_section_row(row):
            continue
        label = _clean(row[0]).lower() if full else _norm_label(row[0])
        for key, pat in concepts:
            if key not in found and re.search(pat, label):
                found[key] = row
                break
    return found


# ----------------------------------------------------------------- context

class _Ctx:
    def __init__(self, doc, profile=None, method_key=None, currency=None):
        self.doc = doc if isinstance(doc, dict) else {}
        self.meta = self.doc.get("meta") if isinstance(self.doc.get("meta"), dict) else {}
        self.cover = self.doc.get("cover") if isinstance(self.doc.get("cover"), dict) else {}
        self.pages = [p for p in self.doc.get("bagian") or [] if isinstance(p, dict)]
        self.exs = exhibits_of(self.doc)
        self.profile = _normalize_profile(profile or self.meta.get("model_profile"))
        self.bank = self.profile == "financial_ddm"
        status = str(self.meta.get("status") or "")
        self.published = bool(status) and status != "draft_non_distributable"
        self.kf = _find(self.exs, "kf")
        self.is_ = _find(self.exs, "is")
        self.bs = _find(self.exs, "bs")
        self.cf = _find(self.exs, "cf")
        self.ratio = _find(self.exs, "ratio")
        self.combos = _combo_series(self.exs)
        self.method_key = method_key or self._method_key()
        self.option = _option(self.method_key)
        self.currency = self._currency(currency)
        self.tp = num(self.meta.get("tp"))
        self.price = num(self.meta.get("harga"))
        self.last_actual = self._last_actual()

    def _method_key(self):
        release = (((self.doc.get("harness") or {}).get("log_gate") or {}).get("release") or {})
        if release.get("method_key"):
            return release["method_key"]
        chain = self.find_title(r"^rantai metode")
        if chain:
            row = _chain_selected_row(chain)
            if row:
                key = _key_from_text(_clean(row[0]))
                if key:
                    return key
        return _key_from_text(_clean(self.doc.get("method")))

    def _currency(self, given):
        if given:
            g = str(given).strip().upper()
            return "USD" if g in ("USD", "US$") else "IDR"
        if self.kf:
            for row in _rows(self.kf):
                cur, scale = _unit(row[0]) if row else (None, None)
                if cur == "USD" and scale and scale >= 1e6:
                    return cur
        # A USD reporter shown in rupiah says so in its notes ("berpelaporan
        # USD", "laba US$ aktual resmi dikonversi", "US$ juta, mata uang pelaporan").
        notes = " ".join(_note(e) for e in (self.kf, self.is_, self.bs, self.cf) if e)
        if re.search(r"berpelaporan usd|pelapor(an)? usd|mata uang pelaporan usd|"
                     r"us\$ juta, mata uang pelaporan|laba us\$ aktual", notes, re.I):
            return "USD"
        return "IDR"

    def _last_actual(self):
        for e in (self.kf, self.is_, self.bs, self.cf):
            if e:
                years = [p[0] for _, p in _period_cols(e) if not _is_forecast(p)]
                if years:
                    return max(years)
        try:
            return date.fromisoformat(str(self.meta.get("tanggal"))[:10]).year - 1
        except ValueError:
            return None

    def find_title(self, pattern, *, exclude=None):
        for e in self.exs:
            t = _title(e).lower()
            if re.search(pattern, t) and not (exclude and re.search(exclude, t)):
                return e
        return None

    def find_all(self, pattern, *, exclude=None):
        return [e for e in self.exs if re.search(pattern, _title(e).lower())
                and not (exclude and re.search(exclude, _title(e).lower()))]

    def page_of(self, exhibit):
        key = (exhibit.get("n"), _clean(exhibit.get("judul")))
        return next((p for p in self.pages
                     if any((e.get("n"), _clean(e.get("judul"))) == key for e in p.get("exhibit") or [])),
                    None)


_OPTION = {"fcff_dcf": "A", "dcf_reference": "A", "ddm": "B",
           "sotp_lom": "C", "rnav_lom": "C", "property_nav": "C"}
_FAMILY = {
    "fcff_dcf": r"\bDCF\b", "dcf_reference": r"\bDCF\b", "ddm": r"\bDDM\b",
    "sotp_lom": r"\bSOTP\b|\bLoM\b", "rnav_lom": r"\bRNAV\b", "holding_sotp": r"\bSOTP\b",
    "property_nav": r"\bNAV\b", "ev_ebitda_peer": r"EV/EBITDA", "ev_ebitda_fy": r"EV/EBITDA",
    "ev_sales_peer": r"EV/Sales", "ps_peer": r"\bP/S\b",
    "pbv_relative": r"P/BV|\bPBV\b", "pbv_roe": r"P/BV|\bPBV\b", "pbv_roe_fy": r"P/BV|\bPBV\b",
    "pbv_book": r"P/BV|\bPBV\b", "relative_pe": r"\bPER\b|\bP/E\b", "pe_fy_scenario": r"\bPER\b|\bP/E\b",
}
_FAMILIES = sorted(set(_FAMILY.values()))


def _option(key):
    if not key:
        return None
    return _OPTION.get(key, "X")


def _key_from_text(text):
    t = text or ""
    for pat, key in ((r"holding sotp", "holding_sotp"), (r"sotp/lom|\blom\b.*sotp|sotp.*\blom\b", "sotp_lom"),
                     (r"\brnav\b", "rnav_lom"), (r"property nav", "property_nav"),
                     (r"\bddm\b", "ddm"), (r"dcf (fcff|skenario)|fcff dcf|dcf fcff", "fcff_dcf"),
                     (r"dcf (konsolidasi|referensi)", "dcf_reference"),
                     (r"ev/ebitda (median )?peer|ev/ebitda peer", "ev_ebitda_peer"),
                     (r"ev/ebitda", "ev_ebitda_fy"), (r"ev/sales", "ev_sales_peer"),
                     (r"p/bv[- ]roe fy", "pbv_roe_fy"), (r"p/bv[- ]roe|inverse coe", "pbv_roe"),
                     (r"p/bv buku", "pbv_book"), (r"p/bv relatif", "pbv_relative"),
                     (r"per (fy )?skenario|per median peer x eps skenario", "pe_fy_scenario"),
                     (r"per relatif|relatif per", "relative_pe"), (r"\bp/s\b", "ps_peer")):
        if re.search(pat, t, re.I):
            return key
    return None


def _chain_selected_row(chain):
    cols = [_clean(c).lower() for c in _cols(chain)]
    dec = next((i for i, c in enumerate(cols) if c.startswith("keputusan") or c == "decision"), 1)
    return next((r for r in _rows(chain) if len(r) > dec and
                 re.match(r"^(terpilih|selected|dipakai)", _clean(r[dec]).lower())), None)


# ------------------------------------------------------------------ result

class _Results:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, cid, ok, message, *, na=False):
        severity, owner, _ = CHECKS[cid]
        status = NA if na else (PASS if ok else FAIL)
        self.items.append({"check": cid, "severity": severity, "status": status,
                           "blocker": status == FAIL and severity == BLOCKER,
                           "owner": owner, "message": message})

    def na(self, cid, message):
        self.add(cid, True, message, na=True)


_REGISTRY: list[tuple] = []


def _check(*ids):
    def deco(fn):
        _REGISTRY.append((fn, ids))
        return fn
    return deco


def _short(items, limit=6) -> str:
    items = list(items)
    text = "; ".join(str(i) for i in items[:limit])
    return text + (f"; +{len(items) - limit} lagi" if len(items) > limit else "")


# =================================================================== T1

_GENERIC_TITLES = {"chart", "grafik", "tabel", "table", "exhibit", "figure", "gambar",
                   "data", "lainnya", "lain-lain", "untitled", "tanpa judul"}


@_check("T1.exhibit_label")
def _t1_label(ctx, r):
    bad = []
    for e in ctx.exs:
        t = _title(e)
        if not t or re.sub(r"[\d\s.]+$", "", t).strip().lower() in _GENERIC_TITLES:
            bad.append(f"Exhibit {e.get('n')}: '{t or '(kosong)'}'")
    r.add("T1.exhibit_label", not bad, "semua judul deskriptif" if not bad
          else f"judul generik/kosong: {_short(bad)}")


def reading_order(doc) -> list[dict]:
    """Exhibits in the order a reader meets them: the cover's price chart and
    Key Financials, then each page's exhibits."""
    exs = exhibits_of(doc)
    placed_keys = set()
    ordered = []

    def key(e):
        return (e.get("n"), _clean(e.get("judul")))
    for page in doc.get("bagian") or []:
        for e in (page or {}).get("exhibit") or []:
            placed_keys.add(key(e))
    chart = next((e for e in exs if e.get("tipe") == "price_chart"), None)
    cover = [e for e in exs if e is not chart and key(e) not in placed_keys]
    kf = next((e for e in cover if _base_title(e) == "key financials"), cover[0] if cover else None)
    for e in (chart, kf):
        if e is not None:
            ordered.append(e)
    seen = {key(e) for e in ordered}
    for page in doc.get("bagian") or []:
        for e in (page or {}).get("exhibit") or []:
            if isinstance(e, dict) and key(e) not in seen:
                seen.add(key(e))
                ordered.append(e)
    return ordered


@_check("T1.numbering")
def _t1_numbering(ctx, r):
    if not ctx.exs:
        r.na("T1.numbering", "tanpa exhibit")
        return
    order = reading_order(ctx.doc)
    numbers = []
    for e in order:
        try:
            numbers.append(int(e.get("n")))
        except (TypeError, ValueError):
            numbers.append(None)
    problems = []
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(f"urutan baca {numbers[:12]}{'...' if len(numbers) > 12 else ''} "
                        f"bukan 1..{len(numbers)}")
    keys = {(e.get("n"), _clean(e.get("judul"))) for e in order}
    orphan = [f"Exhibit {e.get('n')} '{_title(e)[:40]}'" for e in ctx.exs
              if (e.get("n"), _clean(e.get("judul"))) not in keys]
    if orphan:
        problems.append(f"tidak ditempatkan di halaman mana pun: {_short(orphan, 3)}")
    r.add("T1.numbering", not problems, "nomor exhibit 1..N sesuai urutan baca"
          if not problems else "; ".join(problems))


_RANGE = re.compile(r"(?<![\w.])((?:FY)?\d{4}[AFE]?|FY\d{2}[AFE]?|\d{2}[AFE])\s*[-–]\s*"
                    r"((?:FY)?\d{4}[AFE]?|FY\d{2}[AFE]?|\d{2}[AFE])(?![\w.])")


def _title_range(title):
    m = _RANGE.search(title or "")
    if not m:
        return None
    a, b = parse_period(m.group(1)), parse_period(m.group(2))
    if not a or not b or a[0] > b[0]:
        return None
    return m.group(0), a, b


def _shown_periods(e):
    periods = [p for _, p in _period_cols(e)]
    if periods:
        return periods
    rows = [parse_period(r[0]) for r in _rows(e) if r]
    rows = [p for p in rows if p]
    return rows if len(rows) >= 2 else []


@_check("T1.title_period_range")
def _t1_range(ctx, r):
    bad, checked = [], 0
    for e in ctx.exs:
        rng = _title_range(_title(e))
        if not rng:
            continue
        shown = _shown_periods(e)
        if not shown:
            continue
        checked += 1
        text, start, end = rng
        first, last = shown[0], shown[-1]
        same = (start[0] == first[0] and end[0] == last[0] and
                (start[1] is None or first[1] is None or start[1] == first[1] or
                 {start[1], first[1]} <= {"A", None}) and
                (end[1] is None or last[1] is None or end[1] == last[1] or
                 {end[1], last[1]} <= {"A", None}))
        if not same:
            bad.append(f"Exhibit {e.get('n')} '{_title(e)[:50]}': judul {text}, kolom "
                       f"{first[0]}{first[1] or ''}-{last[0]}{last[1] or ''}")
    if not checked:
        r.na("T1.title_period_range", "tanpa judul berentang periode")
    else:
        r.add("T1.title_period_range", not bad, f"{checked} judul berentang cocok dengan kolom"
              if not bad else _short(bad, 4))


# =================================================================== TF

def _display_tables(ctx):
    return [e for e in (ctx.kf, ctx.is_, ctx.bs, ctx.cf, ctx.ratio) if e]


def _explains_nm(note) -> bool:
    return bool(re.search(r"n\.\s?m\.|tidak bermakna|not meaningful|(belum|tidak) dimodelkan",
                          note or "", re.I))


@_check("TF.forecast_cells", "TF.nm_reason", "TF.actual_cells")
def _tf_cells(ctx, r):
    blank_fc, text_fc, nm_no_reason, blank_act = [], [], [], []
    tables = 0
    for e in ctx.exs:
        if e.get("tipe") in ("combo_panel", "combo_chart", "band_chart", "price_chart", "bar_chart"):
            continue
        pcols = _period_cols(e)
        nm_cells = sum(1 for row in _rows(e) for c in row[1:] if classify_cell(c) == "nm")
        if nm_cells and not _explains_nm(_note(e)):
            nm_no_reason.append(f"Exhibit {e.get('n')} '{_title(e)[:40]}' ({nm_cells} sel n.m.)")
        if not pcols:
            continue
        tables += 1
        display = e in _display_tables(ctx)
        for row in _rows(e):
            if not row or _is_section_row(row) or (not display and _descriptive_row(row)):
                continue
            for i, period in pcols:
                cell = row[i] if i < len(row) else None
                kind = classify_cell(cell)
                where = f"Exhibit {e.get('n')} '{_title(e)[:30]}' / {_clean(row[0])[:40]}"
                if _is_forecast(period):
                    if kind == "blank":
                        blank_fc.append(f"{where} ({_clean(cell) or 'kosong'})")
                    elif kind == "text":
                        text_fc.append(f"{where} ('{_clean(cell)[:20]}')")
                elif display and kind == "blank":
                    blank_act.append(f"{where} ({_clean(cell) or 'kosong'})")
    # Slide-3 charts: a forecast point without a value is an empty cell.
    for e, s, _ in ctx.combos:
        cols = list(_data(e).get("cols") or [])
        flags = s.get("is_forecast") or []
        explained = _explains_nm(_note(e) + " " + _clean(e.get("narasi")))
        for part in ("bars", "line"):
            values = s.get(part) or []
            for i, col in enumerate(cols):
                period = parse_period(col)
                forecast = (flags[i] if i < len(flags) else False) or _is_forecast(period)
                value = values[i] if i < len(values) else None
                missing = value is None or (isinstance(value, float) and math.isnan(value))
                where = f"Exhibit {e.get('n')} '{_title(e)[:30]}' / {part} {col}"
                if missing and forecast and not explained:
                    blank_fc.append(where)
                elif missing and not forecast and not explained and period and part == "bars" and \
                        ctx.last_actual and \
                        period[0] >= ctx.last_actual - 1:
                    blank_act.append(where)
    fc_bad = _collapse(blank_fc + text_fc)
    r.add("TF.forecast_cells", not fc_bad,
          f"{tables} tabel berperiode: semua sel proyeksi terisi" if not fc_bad
          else f"{len(blank_fc) + len(text_fc)} sel proyeksi kosong/NA/-: {_short(fc_bad, 5)}")
    r.add("TF.nm_reason", not nm_no_reason, "setiap sel n.m. dijelaskan di catatan"
          if not nm_no_reason else f"n.m. tanpa alasan di catatan: {_short(nm_no_reason, 4)}")
    act_bad = _collapse(blank_act)
    r.add("TF.actual_cells", not act_bad, "sel aktual terisi" if not act_bad
          else f"{len(blank_act)} sel aktual NA/kosong/-: {_short(act_bad, 4)}")


def _collapse(items):
    """Group 'Exhibit n 'x' / row (cell)' entries by exhibit and row."""
    groups: dict[str, int] = {}
    for item in items:
        head = re.sub(r"\s*\((?:[^()]*)\)$", "", item)
        head = re.sub(r" (bars|line) \S+$", r" \1", head)
        groups[head] = groups.get(head, 0) + 1
    return [f"{k} x{v}" if v > 1 else k for k, v in groups.items()]


def _horizon_problem(periods, last_actual):
    """None when periods are exactly 2 actual + 3 forecast consecutive years."""
    if not periods:
        return "tanpa kolom periode"
    years = [p[0] for p in periods]
    kinds = ["F" if _is_forecast(p) else "A" for p in periods]
    if kinds != ["A", "A", "F", "F", "F"]:
        return f"{len(kinds) - kinds.count('F')}A+{kinds.count('F')}F ({_fmt_periods(periods)})"
    if years != list(range(years[0], years[0] + 5)):
        return f"tahun tidak berurutan ({_fmt_periods(periods)})"
    if last_actual and years[1] != last_actual:
        return f"aktual terakhir {years[1]}, bukan {last_actual}"
    return None


def _fmt_periods(periods):
    return ", ".join(f"{y}{k or ''}" for y, k in periods)


@_check("T2.key_financials_cols")
def _t2_kf_cols(ctx, r):
    if not ctx.kf:
        r.add("T2.key_financials_cols", False, "exhibit Key Financials tidak ada")
        return
    problem = _horizon_problem([p for _, p in _period_cols(ctx.kf)], None)
    r.add("T2.key_financials_cols", problem is None, "Key Financials 2A+3F" if problem is None
          else f"Key Financials {problem}")


_ACTUAL_ONLY = re.compile(r"hanya aktual|actual only|tanpa (tahun )?proyeksi|tidak dimodelkan|"
                          r"n\.\s?m\.|tidak bermakna|\baktual\)", re.I)


@_check("TF.display_horizon", "TF.chart_history", "TF.chart_forecast_nm")
def _tf_horizon(ctx, r):
    kf_periods = [p[0] for _, p in _period_cols(ctx.kf)] if ctx.kf else []
    bad, checked = [], 0
    for name, e in (("laba rugi", ctx.is_), ("neraca", ctx.bs), ("arus kas", ctx.cf),
                    ("rasio utama", ctx.ratio)):
        if not e:
            continue
        checked += 1
        periods = [p for _, p in _period_cols(e)]
        problem = _horizon_problem(periods, ctx.last_actual)
        if problem is None and kf_periods and [p[0] for p in periods] != kf_periods:
            problem = f"tahun {_fmt_periods(periods)} berbeda dari Key Financials"
        if problem:
            bad.append(f"{name}: {problem}")
    history, actual_only = [], []
    if ctx.last_actual:
        want_fc = {ctx.last_actual + k for k in (1, 2, 3)}
        want_act = {ctx.last_actual - 1, ctx.last_actual}
        seen = set()
        for e, _s, concept in ctx.combos:
            if id(e) in seen:
                continue
            seen.add(id(e))
            checked += 1
            periods = [parse_period(c) for c in _data(e).get("cols") or []]
            periods = [p for p in periods if p]
            fc = {p[0] for p in periods if _is_forecast(p)}
            act = {p[0] for p in periods if not _is_forecast(p)}
            missing = sorted(want_fc - fc) + sorted(want_act - act)
            reason = _ACTUAL_ONLY.search(" ".join([_title(e), _clean(e.get("narasi")), _note(e)]))
            if missing and concept == "other" and not fc and not (want_act - act) and reason:
                actual_only.append(f"Exhibit {e.get('n')} '{_title(e)[:40]}'")
            elif missing:
                bad.append(f"grafik Exhibit {e.get('n')}: tanpa tahun {missing}")
            extra = sorted((act - want_act) | (fc - want_fc))
            if extra:
                history.append(f"Exhibit {e.get('n')}: {extra}")
    if not checked:
        r.na("TF.display_horizon", "tanpa laporan keuangan atau grafik Slide 3")
    else:
        r.add("TF.display_horizon", not bad, "laporan keuangan dan grafik 2A+3F" if not bad
              else _short(bad, 6))
    if not ctx.combos:
        r.na("TF.chart_history", "tanpa grafik Slide 3")
        r.na("TF.chart_forecast_nm", "tanpa grafik Slide 3")
    else:
        r.add("TF.chart_history", not history, "grafik tanpa tahun di luar 2A+3F" if not history
              else f"tahun di luar 2A+3F: {_short(history, 4)}")
        r.add("TF.chart_forecast_nm", not actual_only, "semua grafik memuat proyeksi" if not actual_only
              else f"hanya aktual, alasan tertulis: {_short(actual_only, 3)}")


@_check("TF.period_labels")
def _tf_labels(ctx, r):
    bad = []
    for e in _display_tables(ctx):
        for i, p in _period_cols(e):
            label = _clean(_cols(e)[i])
            if p[1] is None:
                bad.append(f"'{_title(e)[:20]}' {label} (tanpa A)")
            elif not re.match(r"^(\d{4}A|FY\d{2}F|\d{4}F|FY\d{2}A)$", label):
                bad.append(f"'{_title(e)[:20]}' {label}")
    if not _display_tables(ctx):
        r.na("TF.period_labels", "tanpa tabel tampilan")
    else:
        r.add("TF.period_labels", not bad, "label periode 2024A/FY26F" if not bad
              else _short(sorted(set(bad)), 6))


def _valuation_block1(ctx):
    """The explicit-period valuation table of the active option."""
    if ctx.option == "A":
        return next((e for e in ctx.find_all(r"fcff") if any(_is_forecast(p) for _, p in _period_cols(e))), None)
    if ctx.option == "B":
        return next((e for e in ctx.find_all(r"dividen|dividend|ddm")
                     if any(_is_forecast(p) for _, p in _period_cols(e))), None)
    if ctx.option == "C":
        cands = ctx.find_all(r"\blom\b|rnav|sotp|life of mine", exclude=r"sensitivitas|rantai")
        best = None
        for e in cands:
            fc = [p for p in _shown_periods(e) if _is_forecast(p)]
            if fc and (best is None or len(fc) > best[0]):
                best = (len(fc), e)
        return best[1] if best else None
    return None


@_check("TF.valuation_horizon")
def _tf_valuation_horizon(ctx, r):
    if ctx.option not in ("A", "B", "C"):
        r.na("TF.valuation_horizon", f"metode {ctx.method_key or '?'} tanpa tabel proyeksi 5 tahun")
        return
    e = _valuation_block1(ctx)
    if not e:
        if ctx.option == "C":
            r.add("TF.valuation_horizon", False,
                  "tanpa exhibit LoM tahunan FY(aktual+1)F..+5 (jadwal per fase tidak cukup)")
        else:
            r.na("TF.valuation_horizon", "tabel eksplisit tidak ada (lihat T4.valuation_option_exhibits)")
        return
    fc = [p[0] for p in _shown_periods(e) if _is_forecast(p)]
    start = (ctx.last_actual + 1) if ctx.last_actual else (fc[0] if fc else None)
    want = list(range(start, start + 5)) if start else []
    ok = fc[:5] == want and len(fc) >= 5
    r.add("TF.valuation_horizon", ok,
          f"Exhibit {e.get('n')} {len(fc)} tahun proyeksi FY{want[0] % 100}F-FY{want[-1] % 100}F"
          if ok else f"Exhibit {e.get('n')} '{_title(e)[:40]}': proyeksi {fc}, wajib {want}")


# =================================================================== T2

_MODEL_LABELS = {"di atas harga pasar", "di bawah harga pasar", "setara harga pasar", "skenario nilai"}
_RATING_STATUS = re.compile(r"^(skenario nilai indikatif|dalam peninjauan)$", re.I)


@_check("T2.cover_rating_block", "T2.rating_status")
def _t2_rating(ctx, r):
    rating = _clean(ctx.meta.get("rating"))
    status = _clean(ctx.meta.get("rating_status") or ctx.cover.get("rating_status"))
    if not ctx.published:
        r.na("T2.cover_rating_block", "draft: nilai model ditahan")
        ok = not status or status.lower().startswith("dalam peninjauan")
        r.add("T2.rating_status", ok, "draft: dalam peninjauan" if ok
              else f"draft dengan status rating '{status}'")
        return
    r.add("T2.cover_rating_block", rating.lower() in _MODEL_LABELS,
          f"skenario nilai {rating}" if rating.lower() in _MODEL_LABELS
          else f"label skenario '{rating or 'kosong'}' bukan label informasional")
    if not status:
        r.na("T2.rating_status", "status skenario nilai belum diisi")
    else:
        r.add("T2.rating_status", bool(_RATING_STATUS.match(status)), f"status '{status}'")


@_check("T2.price_box")
def _t2_price_box(ctx, r):
    if not ctx.published:
        r.na("T2.price_box", "draft: nilai model ditahan")
        return
    up = num(ctx.meta.get("upside_persen"))
    if not ctx.price or ctx.price <= 0 or ctx.tp is None or up is None:
        r.add("T2.price_box", False, f"harga {ctx.price}, nilai model {ctx.tp}, selisih {up}: wajib lengkap")
        return
    want = (ctx.tp / ctx.price - 1) * 100
    ok = abs(up - want) <= 0.05
    r.add("T2.price_box", ok, f"selisih {up:+.1f}% = nilai model/harga - 1" if ok
          else f"selisih {up:+.2f}% tetapi nilai model/harga - 1 = {want:+.2f}%")


@_check("T2.stats_block")
def _t2_stats(ctx, r):
    dp = ctx.cover.get("data_pasar") if isinstance(ctx.cover.get("data_pasar"), dict) else {}
    missing = [label for label, keys in (
        ("jumlah saham", ("saham",)), ("kap. pasar Rp", ("market_cap",)),
        ("kap. pasar US$", ("market_cap_usd",)), ("ADTV Rp", ("adtv",)),
        ("ADTV US$", ("adtv_usd",)), ("free float", ("free_float", "public_ownership")))
        if not any(classify_cell(dp.get(k)) == "num" for k in keys)]
    holders = [h for h in ctx.doc.get("holders") or []
               if isinstance(h, (list, tuple)) and len(h) >= 2 and classify_cell(h[1]) == "num"]
    if not holders:
        missing.append("pemegang saham utama (%)")
    r.add("T2.stats_block", not missing, "blok statistik lengkap" if not missing
          else f"tanpa: {', '.join(missing)}")


@_check("T2.relative_chart")
def _t2_relative(ctx, r):
    chart = next((e for e in ctx.exs if e.get("tipe") == "price_chart"), None)
    if not chart:
        r.add("T2.relative_chart", False, "exhibit harga relatif terhadap IHSG tidak ada")
        return
    order = reading_order(ctx.doc)
    first = order[0] if order else None
    ok = first is chart or (first is not None and first.get("n") == chart.get("n"))
    r.add("T2.relative_chart", ok, "chart relatif IHSG di cover" if ok
          else "chart relatif IHSG bukan exhibit pertama di cover")


_THESIS_GENERIC = re.compile(r"^(company update|laporan (perusahaan|emiten)|equity research|"
                             r"pembaruan (perusahaan|emiten))$", re.I)


@_check("T2.thesis_subtitle")
def _t2_thesis(ctx, r):
    hl = _clean(ctx.cover.get("headline"))
    problems = []
    if not hl:
        problems.append("kosong")
    else:
        if len(hl.split()) > 10:
            problems.append(f"{len(hl.split())} kata (> 10)")
        if len(re.findall(r"\d+(?:[.,]\d+)*", hl)) > 1:
            problems.append("berisi statistik")
        if _THESIS_GENERIC.match(hl) or hl.lower() == _clean(ctx.meta.get("emiten")).lower():
            problems.append("generik")
    r.add("T2.thesis_subtitle", not problems, f"'{hl}'" if not problems
          else f"subjudul '{hl}': {', '.join(problems)}")


def _sentences(text):
    return [p.strip() for p in re.split(r"[.!?]+\s+|[.!?]+\s*$", str(text or "")) if p.strip()]


@_check("T2.cover_bullets")
def _t2_bullets(ctx, r):
    bullets = [b for b in ctx.cover.get("bullets") or [] if _clean(b)]
    problems = []
    if len(bullets) != 3:
        problems.append(f"{len(bullets)} bullet (wajib 3)")
    for i, b in enumerate(bullets, 1):
        if len(str(b).split()) > 30 or len(_sentences(b)) > 1:
            problems.append(f"bullet {i} > 1 kalimat atau > 30 kata")
    if ctx.published and len(bullets) >= 3:
        last = str(bullets[2])
        rating = _clean(ctx.meta.get("rating"))
        if not re.search(r"nilai model", last, re.I):
            problems.append("bullet 3 tanpa nilai model")
        if not re.search(r"Rp\s?\d", last):
            problems.append("bullet 3 tanpa TP")
    r.add("T2.cover_bullets", not problems, "tiga bullet sesuai" if not problems
          else "; ".join(problems))


@_check("T2.cover_paragraphs")
def _t2_paragraphs(ctx, r):
    paras = [p for p in ctx.cover.get("paragraf") or [] if isinstance(p, dict)]
    problems = []
    if len(paras) != 3:
        problems.append(f"{len(paras)} paragraf (wajib 3)")
    for i, p in enumerate(paras, 1):
        if not _clean(p.get("judul")):
            problems.append(f"paragraf {i} tanpa subjudul")
        if not _clean(p.get("isi")):
            problems.append(f"paragraf {i} kosong")
    r.add("T2.cover_paragraphs", not problems, "tiga paragraf bersubjudul" if not problems
          else "; ".join(problems))


_TP_MENTION = re.compile(r"\b(?:nilai(?:\s+(?:model|skenario(?:\s+indikatif)?))?|skenario\s+nilai|"
                         r"target(?:\s+harga)?|TP)\b"
                         r"(?:\s+(?:baru|menjadi|ke|sebesar|di|kami))*"
                         r"\s*(?:menjadi\s+)?Rp\s?(\d{1,3}(?:\.\d{3})+|\d+)", re.I)


def _cover_texts(ctx):
    texts = [str(b) for b in ctx.cover.get("bullets") or []]
    texts += [str(p.get("isi") or "") for p in ctx.cover.get("paragraf") or [] if isinstance(p, dict)]
    return texts


def _valuation_paragraph(ctx):
    paras = [p for p in ctx.cover.get("paragraf") or [] if isinstance(p, dict)]
    hit = [p for p in paras if re.search(r"\b(nilai model|target|TP)\b",
                                        str(p.get("isi") or ""), re.I)]
    return hit[-1] if hit else (paras[2] if len(paras) >= 3 else None)


@_check("T2.valuation_paragraph")
def _t2_val_para(ctx, r):
    if not ctx.published:
        r.na("T2.valuation_paragraph", "draft: nilai model ditahan")
        return
    p = _valuation_paragraph(ctx)
    if not p:
        r.add("T2.valuation_paragraph", False, "paragraf valuasi tidak ada")
        return
    text = str(p.get("isi") or "")
    missing = []
    fam = _FAMILY.get(ctx.method_key or "")
    if not (_TP_MENTION.search(text) and fam and re.search(fam, text)):
        missing.append("kalimat metodologi (nilai model + metode)")
    rate = any(re.search(r"(wacc|coe|cost of equity|diskonto|diskon|discount|exit multiple|\bg\b)", s, re.I)
               and re.search(r"\d+(?:,\d+)?\s?%", s) for s in _sentences(text))
    multiple = ctx.option == "X" and any(re.search(r"(EV/EBITDA|EV/Sales|PER|P/E|P/BV|PBV)", s)
                                         and re.search(r"\d+(?:,\d+)?x", s) for s in _sentences(text))
    if not (rate or multiple):
        missing.append("parameter kunci (WACC/CoE/diskonto % atau multiple)")
    if not re.search(r"CAGR\s+(?:FY)?26F?\s*[-–]\s*(?:FY)?28F", text):
        missing.append("CAGR FY26-28F" + (" (ada CAGR periode lain)" if "CAGR" in text else ""))
    mult = [s for s in _sentences(text) if re.search(r"(PER|P/E|PBV|P/BV|EV/EBITDA)\b", s)
            and re.search(r"\d+(?:,\d+)?x", s)]
    if not mult:
        missing.append("multiple pada nilai model")
    else:
        if not any(re.search(r"historis|rata-rata|median|peer|sejarah", s, re.I) for s in mult):
            missing.append("pembanding multiple (historis/peer)")
        if not any(re.search(r"pada (nilai model|skenario nilai)|di (nilai model|skenario nilai)",
                             s, re.I) for s in mult):
            missing.append("multiple dihitung pada nilai model (bukan harga kini)")
    r.add("T2.valuation_paragraph", not missing, "empat elemen valuasi ada" if not missing
          else f"kurang: {', '.join(missing)}")


def _primary_per_share(ctx):
    """Per-share value printed on the primary valuation exhibit(s)."""
    if ctx.option == "A":
        exs = ctx.find_all(r"fcff|terminal|jembatan|bridge|\bdcf\b", exclude=r"sensitivitas|rantai|wacc")
    elif ctx.option == "B":
        exs = ctx.find_all(r"ddm|dividen|dividend|nilai wajar", exclude=r"sensitivitas|rantai")
    elif ctx.option == "C":
        exs = ctx.find_all(r"sotp|rnav|\bnav\b", exclude=r"sensitivitas|rantai|uji|asumsi|jadwal|jembatan korporat")
    else:
        exs = [e for e in ctx.exs if re.search(r"^target harga|sotp", _title(e).lower())]
    for e in exs:
        rows = _rows(e)
        cols = [_clean(c).lower() for c in _cols(e)]
        col = next((i for i, c in enumerate(cols) if i and re.search(r"per saham|per share|nilai wajar", c)), None)
        pick = [row for row in rows if re.search(r"target (harga|price)", _clean(row[0]).lower())]
        pick += [row for row in rows if re.search(
            r"(nilai wajar|fair value|nilai|rnav) per saham|per share|median \(basis\)|\(basis\)",
            _clean(row[0]).lower()) and "sensitivitas" not in " ".join(map(str, row)).lower()]
        for row in pick:
            if col is not None and col < len(row) and (num(row[col]) or 0) > 0:
                return num(row[col]), e
            rupiah = [num(c) for c in row[1:] if re.fullmatch(r"\(?Rp\s?\d[\d.]*(,\d+)?\)?", _clean(c))]
            plain = [num(c) for c in row[1:] if (parse_num(c) or (None, 0, "x"))[2] == ""]
            for v in rupiah + plain:
                if v is not None and v > 0:
                    return v, e
    return None, None


@_check("T2.cover_tp_method")
def _t2_tp_method(ctx, r):
    if not ctx.published:
        r.na("T2.cover_tp_method", "draft: TP ditahan")
        return
    problems = []
    tp = ctx.tp
    if tp is None:
        problems.append("meta.tp kosong")
    fam = _FAMILY.get(ctx.method_key or "")
    if not fam:
        problems.append(f"metode terpilih tidak dikenali ({ctx.method_key})")
    for text in _cover_texts(ctx):
        for m in _TP_MENTION.finditer(text):
            around = text[max(0, m.start() - 25):m.end() + 25].lower()
            if re.search(r"sebelum|previous|lama\b", around):
                continue
            value = num(m.group(1))
            if tp is not None and value is not None and abs(value - tp) > 0.5:
                problems.append(f"cover menyebut target Rp{m.group(1)}, TP Rp{tp:,.0f}".replace(",", "."))
        if fam:
            for s in _sentences(text):
                if not _TP_MENTION.search(s):
                    continue
                named = [f for f in _FAMILIES if re.search(f, s)]
                if named and not re.search(fam, s):
                    problems.append(f"kalimat TP menyebut metode lain: '{s[:70]}'")
    label = _clean(ctx.doc.get("method"))
    if fam and label and not re.search(fam, label):
        problems.append(f"label metode cover '{label[:50]}' bukan metode terpilih")
    chain = ctx.find_title(r"^rantai metode")
    if chain:
        row = _chain_selected_row(chain)
        if not row:
            problems.append("rantai metode tanpa baris Terpilih")
        else:
            if fam and not re.search(fam, _clean(row[0])):
                problems.append(f"rantai metode memilih '{_clean(row[0])}'")
            values = [num(c) for c in row[1:] if num(c) is not None and num(c) > 0]
            if tp is not None and values and all(abs(v - tp) > _tick(tp) for v in values):
                problems.append(f"rantai metode Rp{values[0]:,.0f} vs TP Rp{tp:,.0f}".replace(",", "."))
    else:
        problems.append("exhibit rantai metode tidak ada")
    value, e = _primary_per_share(ctx)
    if tp is not None and value is not None and abs(value - tp) > _tick(tp):
        problems.append(f"Exhibit {e.get('n')} nilai per saham {value:,.0f} vs TP {tp:,.0f}".replace(",", "."))
    r.add("T2.cover_tp_method", not problems,
          f"TP Rp{tp:,.0f} dan metode {ctx.method_key} konsisten".replace(",", ".") if not problems
          else "; ".join(problems))


def _profile_kind(ctx):
    return "bank" if ctx.bank else "nonbank"


@_check("T2.key_financials_rows", "T2.key_financials_order")
def _t2_kf_rows(ctx, r):
    if not ctx.kf:
        r.add("T2.key_financials_rows", False, "exhibit Key Financials tidak ada")
        r.na("T2.key_financials_order", "tanpa Key Financials")
        return
    concepts = KF_ROWS[_profile_kind(ctx)]
    rows = _rows(ctx.kf)
    found = _match_rows(rows, concepts)
    missing = [k for k, _ in concepts if k not in found]
    r.add("T2.key_financials_rows", not missing, f"{len(concepts)} baris template ada"
          if not missing else f"tanpa baris: {', '.join(missing)}")
    order = [k for k, _ in concepts if k in found]
    actual = sorted(order, key=lambda k: rows.index(found[k]))
    r.add("T2.key_financials_order", order == actual, "urutan sesuai template" if order == actual
          else f"urutan {actual}")


@_check("TN.one_decimal")
def _tn_decimal(ctx, r):
    bad = []

    def scan(e, row, cells):
        for cell in cells:
            p = parse_num(cell)
            if p and p[2] in ("%", "x") and p[1] != 1:
                bad.append(f"'{_title(e)[:18]}' {_clean(row[0])[:28]}: {_clean(cell)}")
    if ctx.kf:
        for row in _rows(ctx.kf):
            if re.search(r"\((%|x)\)|growth|pertumbuhan|per\b|pbv|ev/ebitda|roe", _clean(row[0]).lower()):
                scan(ctx.kf, row, row[1:])
    if ctx.ratio:
        for row in _rows(ctx.ratio):
            if not _is_section_row(row):
                scan(ctx.ratio, row, row[1:])
    peer = ctx.find_title(r"^(perbandingan peer|peer valuation|perbandingan valuasi peer)")
    if peer:
        idx = [i for i, c in enumerate(_cols(peer)) if re.search(r"p/e|p/b|ev/|per\b|pbv|\(x\)", _clean(c).lower())]
        for row in _rows(peer):
            scan(peer, row, [row[i] for i in idx if i < len(row)])
    r.add("TN.one_decimal", not bad, "multiple dan persentase satu desimal" if not bad
          else _short(bad, 5))


# =================================================================== T3

@_check("T3.combo_charts", "T3.chart_style", "T3.chart4_by_profile")
def _t3_charts(ctx, r):
    concepts = {c for _, _, c in ctx.combos}
    need = ["revenue", "net_profit"] + ([] if ctx.bank else ["ebitda"])
    missing = [c for c in need if c not in concepts]
    r.add("T3.combo_charts", not missing, "grafik pendapatan, EBITDA, laba bersih ada" if not missing
          else f"grafik Slide 3 tidak ada: {', '.join(missing)}")
    style = []
    for e, s, c in ctx.combos:
        cols = list(_data(e).get("cols") or [])
        bars, line, flags = s.get("bars") or [], s.get("line") or [], s.get("is_forecast") or []
        if len(bars) != len(cols) or len(line) != len(cols):
            style.append(f"Exhibit {e.get('n')}: bar/garis tidak selaras dengan {len(cols)} periode")
        if flags and len(flags) == len(cols):
            wrong = [cols[i] for i, f in enumerate(flags) if bool(f) != _is_forecast(parse_period(cols[i]))]
            if wrong:
                style.append(f"Exhibit {e.get('n')}: penanda proyeksi salah di {wrong}")
        elif not flags:
            style.append(f"Exhibit {e.get('n')}: tanpa penanda aktual/proyeksi")
        if e.get("tipe") == "combo_panel" and not _clean(e.get("narasi")):
            style.append(f"Exhibit {e.get('n')}: tanpa narasi")
    if not ctx.combos:
        r.na("T3.chart_style", "tanpa grafik Slide 3")
    else:
        r.add("T3.chart_style", not style, "bar + garis, aktual vs proyeksi, narasi" if not style
              else _short(style, 4))
    others = [(e, s) for e, s, c in ctx.combos if c == "other"]
    want = {"going_concern_fcff": (r"\bder\b|debt.to.equity|leverage", "DER vs ROE"),
            "financial_ddm": (r"\bnim\b|biaya kredit|cost of credit|\bnpl\b|\blar\b", "NIM dan biaya kredit/NPL"),
            "finite_life_mining": (r"produksi|volume|output|biaya (unit|tunai)|cash cost|lifting", "volume dan biaya unit")
            }.get(ctx.profile)
    if not want:
        r.na("T3.chart4_by_profile", f"profile {ctx.profile}")
    elif not others:
        r.add("T3.chart4_by_profile", False, f"grafik keempat ({want[1]}) tidak ada")
    else:
        label = " ".join(_clean(s.get("label") or _title(e)) for e, s in others).lower()
        ok = bool(re.search(want[0], label))
        r.add("T3.chart4_by_profile", ok, f"grafik keempat: {want[1]}" if ok
              else f"grafik keempat '{label[:40]}', template: {want[1]}")


def _kf_series(ctx, concept):
    """{year: (value in currency units, tolerance)} for a Key Financials money row."""
    if not ctx.kf:
        return {}, None
    extra = dict(KF_ROWS["nonbank"] + KF_ROWS["bank"] + KF_EXTRA)
    row = _match_rows(_rows(ctx.kf), [(concept, extra[concept])]).get(concept)
    if not row:
        return {}, None
    cur, scale = _unit(row[0])
    out = {}
    for i, p in _period_cols(ctx.kf):
        parsed = parse_num(row[i]) if i < len(row) else None
        if parsed:
            factor = scale or 1.0
            out[p[0]] = (parsed[0] * factor, 0.5 * 10 ** -parsed[1] * factor)
    return out, cur


def _chart_values(e, s, part):
    cols = list(_data(e).get("cols") or [])
    values = s.get(part) or []
    out = {}
    for i, c in enumerate(cols):
        p = parse_period(c)
        v = values[i] if i < len(values) else None
        if p and isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
            out[p[0]] = float(v)
    return out


def _chart_unit(e, s):
    for text in (s.get("unit"), _data(e).get("unit"), s.get("bar_unit"), s.get("label"), _title(e)):
        if text and str(text).strip() != "%":
            cur, scale = _unit(text)
            if cur:
                return cur, scale
    return None, None


def _close(a, b, tol=0.0) -> bool:
    return abs(a - b) <= max(0.001 * max(abs(a), abs(b)), tol)


def tieout_key_financials(ctx_or_doc) -> tuple[list[str], int]:
    """Mismatches between Slide-3 charts and Key Financials, and how many
    values were compared. Shared with narrative_tool's N.tieout."""
    ctx = ctx_or_doc if isinstance(ctx_or_doc, _Ctx) else _Ctx(ctx_or_doc)
    bad, compared = [], 0
    kf_growth_rows = {"revenue": "revenue_growth", "ebitda": "ebitda_growth", "net_profit": "eps_growth"}
    for e, s, concept in ctx.combos:
        if concept == "other":
            continue
        kf_vals, kf_cur = _kf_series(ctx, concept)
        bars = _chart_values(e, s, "bars")
        cur, scale = _chart_unit(e, s)
        if cur and kf_cur and cur != kf_cur:
            continue  # different currencies: T3.currency_consistency, not a value tie-out
        if kf_vals and bars and cur and kf_cur:
            for year, value in bars.items():
                if year in kf_vals:
                    compared += 1
                    kv, tol = kf_vals[year]
                    cv = value * (scale or 1.0)
                    if not _close(kv, cv, tol):
                        bad.append(f"Exhibit {e.get('n')} {concept} {year}: grafik {cv / (scale or 1):,.1f} "
                                   f"vs KF {kv / (scale or 1):,.1f}")
        # Lines: growth vs Key Financials growth rows (unit-free).
        line = _chart_values(e, s, "line")
        if concept == "ebitda":
            rev, _ = _kf_series(ctx, "revenue")
            ebitda = kf_vals
            for year, value in line.items():
                if year in rev and year in ebitda and rev[year][0]:
                    compared += 1
                    (a, ta), (b, tb) = ebitda[year], rev[year]
                    margin = a / b * 100
                    if abs(margin - value) > 100 * abs(a / b) * (ta / abs(a or 1) + tb / abs(b)) + 0.1:
                        bad.append(f"Exhibit {e.get('n')} margin EBITDA {year}: grafik {value:.1f}% "
                                   f"vs KF {margin:.1f}%")
            continue
        growth_key = kf_growth_rows[concept]
        label = _clean(s.get("label")).lower()
        if concept == "net_profit" and "eps" not in label:
            growth_key = "np_growth"
        extra = dict(KF_ROWS["nonbank"] + KF_ROWS["bank"] + KF_EXTRA)
        grow_row = _match_rows(_rows(ctx.kf), [(growth_key, extra[growth_key])]).get(growth_key) \
            if ctx.kf else None
        for year, value in line.items():
            shown, tol = None, 0.0
            if grow_row:
                idx = next((i for i, p in _period_cols(ctx.kf) if p[0] == year), None)
                shown = num(grow_row[idx]) if idx is not None and idx < len(grow_row) else None
                tol = 0.1 + 0.001 * abs(shown) if shown is not None else 0.0
            if shown is None and year in kf_vals and (year - 1) in kf_vals and kf_vals[year - 1][0]:
                (a, ta), (b, tb) = kf_vals[year], kf_vals[year - 1]
                shown = (a / b - 1) * 100
                tol = 100 * abs(a / b) * (ta / abs(a or 1) + tb / abs(b)) + 0.1
            if shown is not None and not (concept == "net_profit" and growth_key == "eps_growth"
                                          and "eps" not in label):
                compared += 1
                if abs(shown - value) > tol:
                    bad.append(f"Exhibit {e.get('n')} pertumbuhan {concept} {year}: grafik {value:.1f}% "
                               f"vs KF {shown:.1f}%")
    return bad, compared


@_check("T3.tieout_key_financials")
def _t3_tieout(ctx, r):
    if not ctx.kf or not ctx.combos:
        r.na("T3.tieout_key_financials", "Key Financials atau grafik Slide 3 tidak ada")
        return
    bad, compared = tieout_key_financials(ctx)
    if not compared:
        r.na("T3.tieout_key_financials", "tidak ada nilai yang dapat dibandingkan "
             "(mata uang berbeda, lihat T3.currency_consistency)")
        return
    r.add("T3.tieout_key_financials", not bad, f"{compared} nilai grafik = Key Financials"
          if not bad else _short(bad, 5))


def _statement_currency(e):
    if not e:
        return None
    cur, _ = _unit(_cols(e)[0] if _cols(e) else "")
    return cur


@_check("T3.currency_consistency")
def _t3_currency(ctx, r):
    seen = {}
    if ctx.kf:
        for row in _rows(ctx.kf):
            cur, scale = _unit(row[0]) if row else (None, None)
            if cur and scale and scale >= 1e6:
                seen.setdefault(cur, []).append("Key Financials")
                break
    for name, e in (("laba rugi", ctx.is_), ("neraca", ctx.bs), ("arus kas", ctx.cf)):
        cur = _statement_currency(e)
        if cur:
            seen.setdefault(cur, []).append(name)
    for e, s, c in ctx.combos:
        if c == "other":
            continue
        cur, _ = _chart_unit(e, s)
        if cur:
            seen.setdefault(cur, []).append(f"grafik Exhibit {e.get('n')}")
    if not seen:
        r.na("T3.currency_consistency", "tanpa satuan mata uang")
        return
    ok = len(seen) == 1
    r.add("T3.currency_consistency", ok, f"satu mata uang ({next(iter(seen))})" if ok
          else "; ".join(f"{k}: {', '.join(v)}" for k, v in seen.items()))


# =================================================================== T4

def _rows_of(exs):
    return [row for e in exs for row in _rows(e) if row]


def _has(rows, pattern, *, full=True):
    for row in rows:
        label = _clean(row[0]).lower() if full else _norm_label(row[0])
        if re.search(pattern, label):
            return row
    return None


def _sensitivity(ctx):
    pats = {"A": r"wacc|dcf", "B": r"coe|ddm|cost of equity", "C": r"sotp|lom|rnav|diskonto|discount"}
    sens = ctx.find_all(r"^sensitivitas|^sensitivity")
    pat = pats.get(ctx.option)
    if pat:
        pick = [e for e in sens if re.search(pat, _title(e).lower())]
        if pick:
            return pick[0]
    return sens[0] if sens else None


@_check("T4.valuation_option_exhibits")
def _t4_option(ctx, r):
    if not ctx.published:
        r.na("T4.valuation_option_exhibits", "draft: exhibit valuasi tidak wajib")
        return
    if not ctx.option:
        r.add("T4.valuation_option_exhibits", False, "metode terpilih tidak dapat ditentukan")
        return
    missing = []
    if not ctx.find_title(r"^rantai metode"):
        missing.append("rantai metode valuasi")
    if ctx.option == "A":
        if not ctx.find_title(r"fcff"):
            missing.append("FCFF Forecast and Terminal Value")
        if not ctx.find_title(r"wacc", exclude=r"sensitivitas|sensitivity"):
            missing.append("WACC Components")
    elif ctx.option == "B":
        if not ctx.find_title(r"dividen|dividend"):
            missing.append("Dividend Forecast and Terminal Value")
        if not ctx.find_title(r"cost of equity|komponen coe"):
            missing.append("Cost of Equity Components")
    elif ctx.option == "C":
        if not ctx.find_title(r"sotp|rnav|\bnav\b", exclude=r"sensitivitas|rantai|uji|asumsi"):
            missing.append("Asset Breakdown and RNAV Bridge")
    else:
        value, _e = _primary_per_share(ctx)
        if value is None:
            missing.append("tabel perhitungan TP")
    has_sens = _sensitivity(ctx) is not None or any(
        len([row for row in _rows(e) if re.search(r"kuartil|quartile|diskon holding", _clean(row[0]).lower())]) >= 2
        for e in ctx.exs)
    if not has_sens:
        missing.append("Sensitivity Analysis")
    r.add("T4.valuation_option_exhibits", not missing,
          f"opsi {ctx.option} ({ctx.method_key}): exhibit wajib lengkap" if not missing
          else f"opsi {ctx.option} ({ctx.method_key}) tanpa: {', '.join(missing)}")


_FCFF_CONCEPTS = [
    ("revenue", r"^(pendapatan|revenue|penjualan)\b"), ("ebit", r"^(ebit(?!da)|laba usaha)\b"),
    ("tax_on_ebit", r"pajak atas ebit|tax on ebit"), ("nopat", r"\bnopat\b"),
    ("da", r"d&a|depresiasi|penyusutan|depreciation"), ("capex", r"capex|belanja modal|capital expenditure"),
    ("nwc", r"modal kerja|working capital|\bnwc\b"), ("fcff", r"^fcff$"),
    ("fcff_growth", r"pertumbuhan fcff|fcff growth"),
    ("discount_factor", r"^(faktor diskonto|discount factor)(?!.*terminal)"),
    ("pv_fcff", r"^(pv fcff|pv of fcff|nilai kini fcff)"),
    ("terminal_fcff", r"fcff terminal|terminal fcff"),
    ("terminal_growth", r"pertumbuhan terminal|terminal growth|^g\b"),
    ("terminal_value", r"^(nilai terminal|terminal value)"),
    ("terminal_df", r"(faktor diskonto|discount factor).*terminal|terminal.*(faktor diskonto|discount factor)"),
    ("pv_tv", r"pv (nilai terminal|of terminal value|terminal)"),
    ("sum_pv", r"(jumlah|sum|total) pv"), ("ev", r"^(enterprise value|nilai perusahaan)\b|^ev$"),
    ("net_debt", r"utang bersih|net debt|kas bersih|net cash"), ("cash", r"\bkas\b|\bcash\b"),
    ("debt", r"\butang\b|\bdebt\b|pinjaman"), ("minority", r"minoritas|non-?pengendali|minority|porsi induk"),
    ("equity_value", r"nilai ekuitas|equity value"),
    ("fv", r"nilai wajar per saham|fair value per share|nilai per saham")]


def _concepts_found(rows, concepts):
    found = {}
    for row in rows:
        label = _norm_label(row[0])
        full = _clean(row[0]).lower()
        for key, pat in concepts:
            if key not in found and (re.search(pat, label) or re.search(pat, full)):
                found[key] = row
    return found


@_check("T4.fcff_blocks", "T4.fcff_rows")
def _t4_fcff(ctx, r):
    exs = ctx.find_all(r"fcff|terminal|jembatan|bridge|\bdcf\b", exclude=r"sensitivitas|rantai|wacc")
    if ctx.option != "A" or not exs:
        why = "opsi bukan DCF FCFF" if ctx.option != "A" else "tanpa exhibit FCFF (lihat T4.valuation_option_exhibits)"
        r.na("T4.fcff_blocks", why)
        r.na("T4.fcff_rows", why)
        return
    found = _concepts_found(_rows_of(exs), _FCFF_CONCEPTS)
    headers = " ".join(_clean(c) for e in exs for c in _cols(e)).lower()
    if "terminal_growth" not in found and re.search(r"\bg\s*\d", headers):
        found["terminal_growth"] = ["(header)"]
    blocks = {"eksplisit": ("fcff", "discount_factor", "pv_fcff"),
              "terminal": ("terminal_value", "pv_tv"),
              "bridge": ("ev", "equity_value", "fv")}
    missing_blocks = [f"{name} ({', '.join(k for k in keys if k not in found)})"
                      for name, keys in blocks.items() if any(k not in found for k in keys)]
    if not ("net_debt" in found or ("cash" in found and "debt" in found)):
        missing_blocks.append("bridge (utang bersih)")
    r.add("T4.fcff_blocks", not missing_blocks, "tiga blok FCFF ada" if not missing_blocks
          else f"blok tidak lengkap: {'; '.join(missing_blocks)}")
    rows_needed = ("revenue", "ebit", "tax_on_ebit", "nopat", "da", "capex", "nwc", "fcff_growth",
                   "terminal_fcff", "terminal_growth", "terminal_df", "sum_pv", "minority")
    missing = [k for k in rows_needed if k not in found]
    r.add("T4.fcff_rows", not missing, "semua baris template FCFF ada" if not missing
          else f"tanpa baris: {', '.join(missing)}")


_RF, _BETA, _ERP = r"risk-?free|\brf\b|bebas risiko", r"\bbeta\b", r"equity risk premium|\berp\b|premi risiko ekuitas"
_COE = r"cost of equity|\bcoe\b|biaya ekuitas"


@_check("T4.wacc_components", "T4.wacc_rows")
def _t4_wacc(ctx, r):
    e = ctx.find_title(r"wacc", exclude=r"sensitivitas|sensitivity")
    if ctx.option != "A":
        r.na("T4.wacc_components", "opsi bukan DCF FCFF")
        r.na("T4.wacc_rows", "opsi bukan DCF FCFF")
        return
    if not e:
        r.add("T4.wacc_components", not ctx.published, "exhibit WACC Components tidak ada")
        r.na("T4.wacc_rows", "tanpa exhibit WACC")
        return
    rows = _rows(e)
    core = {"Rf": _RF, "beta": _BETA, "ERP": _ERP, "CoE": _COE, "WACC": r"^wacc$"}
    missing = [k for k, pat in core.items()
               if not any(re.search(pat, _norm_label(row[0]) if k == "WACC" else _clean(row[0]).lower())
                          for row in rows)]
    r.add("T4.wacc_components", not missing, "Rf, beta, ERP, CoE, WACC ada" if not missing
          else f"tanpa: {', '.join(missing)}")
    extra = {"CoD sebelum pajak": r"cost of debt.*(sebelum|pre)|pre-tax cost of debt|biaya utang sebelum",
             "tarif pajak": r"pajak|tax rate", "CoD setelah pajak": r"(setelah|after).*(pajak|tax)",
             "bobot utang": r"bobot utang|weight of debt|d/\(d\+e\)",
             "bobot ekuitas": r"bobot ekuitas|weight of equity|e/\(d\+e\)"}
    missing = [k for k, pat in extra.items() if not any(re.search(pat, _clean(row[0]).lower()) for row in rows)]
    wacc_idx = next((i for i, row in enumerate(rows) if re.search(r"^wacc$", _norm_label(row[0]))), None)
    after = [_clean(row[0]) for row in rows[wacc_idx + 1:]] if wacc_idx is not None else []
    problems = ([f"tanpa: {', '.join(missing)}"] if missing else []) + \
        ([f"baris sesudah WACC: {_short(after, 3)}"] if after else [])
    r.add("T4.wacc_rows", not problems, "komponen WACC lengkap, WACC di baris terakhir" if not problems
          else "; ".join(problems))


def _pct_in(text):
    m = re.search(r"(-?\d+(?:,\d+)?)\s?%", text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def _base_col(cols, base_g=None):
    for i, c in enumerate(cols[1:], 1):
        if re.search(r"basis|base|dasar", _clean(c).lower()):
            return i
    if base_g is not None:
        for i, c in enumerate(cols[1:], 1):
            v = _pct_in(_clean(c))
            if v is not None and abs(v - base_g) < 0.05:
                return i
    n = len(cols) - 1
    return (n + 1) // 2 if n % 2 == 1 and n >= 3 else None


def _terminal_growth(ctx):
    for e in ctx.exs:
        for c in _cols(e):
            m = re.search(r"\bg\s*(\d+(?:,\d+)?)\s?%\s*\(basis\)", _clean(c))
            if m:
                return float(m.group(1).replace(",", "."))
        for row in _rows(e):
            if re.search(r"pertumbuhan terminal|terminal growth|^g$", _norm_label(row[0])) and len(row) > 1:
                v = _pct_in(_clean(row[1]))
                if v is not None:
                    return v
    return None


@_check("T4.sensitivity_grid_base_highlight", "T4.sensitivity_grid_shape")
def _t4_sensitivity(ctx, r):
    if not ctx.published:
        r.na("T4.sensitivity_grid_base_highlight", "draft: TP ditahan")
        r.na("T4.sensitivity_grid_shape", "draft")
        return
    e = _sensitivity(ctx)
    if not e or ctx.option not in ("A", "B", "C") or ctx.method_key == "holding_sotp":
        why = "tanpa grid sensitivitas opsi A/B/C" if not e else f"metode {ctx.method_key}"
        # Quartile tables of multiple-based methods: basis row = TP.
        quart = next((x for x in ctx.exs if any(re.search(r"\(basis\)", _clean(row[0]).lower())
                                               for row in _rows(x))
                      and any(re.search(r"kuartil|quartile", _clean(row[0]).lower()) for row in _rows(x))), None)
        if quart and ctx.tp is not None:
            row = next(row for row in _rows(quart) if "(basis)" in _clean(row[0]).lower())
            values = [num(c) for c in row[1:] if num(c) is not None and num(c) > 50]
            ok = any(abs(v - ctx.tp) <= _tick(ctx.tp) for v in values)
            r.add("T4.sensitivity_grid_base_highlight", ok,
                  f"baris basis Exhibit {quart.get('n')} = TP" if ok
                  else f"baris basis Exhibit {quart.get('n')} {values} vs TP {ctx.tp:,.0f}")
        else:
            r.na("T4.sensitivity_grid_base_highlight", why)
        r.na("T4.sensitivity_grid_shape", why)
        return
    rows, cols = _rows(e), _cols(e)
    base_row = next((row for row in rows if re.search(r"\(basis\)|\bbasis\b|\bbase\b", _clean(row[0]).lower())), None)
    j = _base_col(cols, _terminal_growth(ctx))
    shape = []
    if len(rows) != 5:
        shape.append(f"{len(rows)} baris tingkat diskonto (template: 5)")
    if len(cols) - 1 < 3:
        shape.append(f"{len(cols) - 1} kolom (template: >= 3)")
    if base_row is None or j is None:
        shape.append("sel basis tidak dapat ditentukan")
    r.add("T4.sensitivity_grid_shape", not shape, f"Exhibit {e.get('n')} grid {len(rows)}x{len(cols) - 1}"
          if not shape else f"Exhibit {e.get('n')}: {'; '.join(shape)}")
    if base_row is None or j is None:
        r.na("T4.sensitivity_grid_base_highlight", "sel basis tidak dapat ditentukan (lihat shape)")
        return
    base = num(base_row[j]) if j < len(base_row) else None
    fv, _src = _primary_per_share(ctx)
    ref = fv if fv is not None else ctx.tp
    if base is None or ref is None:
        r.add("T4.sensitivity_grid_base_highlight", False, f"sel basis '{_clean(base_row[j])}' tidak terbaca")
        return
    ok = abs(base - ref) <= _tick(ref)
    r.add("T4.sensitivity_grid_base_highlight", ok,
          f"sel basis Exhibit {e.get('n')} Rp{base:,.0f} = nilai wajar".replace(",", ".") if ok
          else f"sel basis Exhibit {e.get('n')} Rp{base:,.0f} vs nilai wajar Rp{ref:,.0f}".replace(",", "."))


_DDM_CONCEPTS = [
    ("net_profit", r"^laba( bersih)?( pemilik induk)?\b|net profit"), ("payout", r"payout"),
    ("dps", r"^dps\b(?!.*terminal)"), ("dps_growth", r"pertumbuhan dps|dps growth"),
    ("discount_factor", r"faktor diskonto|discount factor"), ("pv_dps", r"^pv (of )?dps"),
    ("terminal_dps", r"dps terminal|terminal dps"),
    ("terminal_growth", r"pertumbuhan terminal|terminal growth|long-term growth|^g\b"),
    ("terminal_value", r"^(nilai terminal|terminal value)"),
    ("pv_tv", r"pv (nilai terminal|of terminal value|terminal)"),
    ("fv", r"nilai wajar per saham|fair value per share|fair value")]


@_check("T4.ddm_blocks", "T4.ddm_rows")
def _t4_ddm(ctx, r):
    if not ctx.published:
        r.na("T4.ddm_blocks", "nilai DDM ditahan karena laporan masih draft")
        r.na("T4.ddm_rows", "nilai DDM ditahan karena laporan masih draft")
        return
    exs = ctx.find_all(r"dividen|dividend|ddm", exclude=r"sensitivitas|rantai")
    if ctx.option != "B" or not exs:
        why = "opsi bukan DDM" if ctx.option != "B" else "tanpa exhibit DDM (lihat T4.valuation_option_exhibits)"
        r.na("T4.ddm_blocks", why)
        r.na("T4.ddm_rows", why)
        return
    found = _concepts_found(_rows_of(exs), _DDM_CONCEPTS)
    problems = []
    b1 = [k for k in ("dps", "discount_factor", "pv_dps") if k not in found]
    b2 = [k for k in ("terminal_value", "pv_tv", "fv") if k not in found]
    if b1:
        problems.append(f"blok dividen tanpa {', '.join(b1)}")
    if b2:
        problems.append(f"blok terminal tanpa {', '.join(b2)}")
    text = " ".join([_title(e) for e in exs] + [_clean(c) for e in exs for c in _cols(e)] +
                    [_clean(row[0]) for row in _rows_of(exs)])
    if re.search(r"\bwacc\b", text, re.I) and not re.search(r"bukan wacc|not wacc", text, re.I):
        problems.append("DDM memakai WACC (wajib Cost of Equity)")
    r.add("T4.ddm_blocks", not problems, "blok dividen dan terminal ada, diskonto CoE" if not problems
          else "; ".join(problems))
    missing = [k for k in ("net_profit", "payout", "dps_growth", "terminal_dps", "terminal_growth")
               if k not in found]
    r.add("T4.ddm_rows", not missing, "semua baris template DDM ada" if not missing
          else f"tanpa baris: {', '.join(missing)}")


@_check("T4.coe_components")
def _t4_coe(ctx, r):
    if ctx.option != "B":
        r.na("T4.coe_components", "opsi bukan DDM")
        return
    e = ctx.find_title(r"cost of equity|komponen coe", exclude=r"sensitivitas|sensitivity")
    if not e:
        r.add("T4.coe_components", not ctx.published, "exhibit Cost of Equity Components tidak ada")
        return
    rows = _rows(e)
    core = {"Rf": _RF, "beta": _BETA, "ERP": _ERP, "CoE": _COE}
    missing = [k for k, pat in core.items() if not any(re.search(pat, _clean(row[0]).lower()) for row in rows)]
    r.add("T4.coe_components", not missing, "Rf, beta, ERP, CoE ada" if not missing
          else f"tanpa: {', '.join(missing)}")


@_check("T4.rnav_bridge", "T4.rnav_rows", "T4.discount_rate_per_asset")
def _t4_rnav(ctx, r):
    if ctx.option != "C":
        for cid in ("T4.rnav_bridge", "T4.rnav_rows", "T4.discount_rate_per_asset"):
            r.na(cid, "opsi bukan RNAV/LoM-SOTP")
        return
    exs = ctx.find_all(r"sotp|rnav|\bnav\b", exclude=r"sensitivitas|rantai|uji|asumsi|jadwal")
    if not exs:
        r.add("T4.rnav_bridge", not ctx.published, "exhibit Asset Breakdown and RNAV Bridge tidak ada")
        r.na("T4.rnav_rows", "tanpa exhibit RNAV")
        r.na("T4.discount_rate_per_asset", "tanpa exhibit RNAV")
        return
    rows = _rows_of(exs)
    lab = lambda row: _clean(row[0]).lower()  # noqa: E731
    assets = [row for row in rows if re.search(r"\bnav\b|nilai aset|aset|tambang|proyek|landbank", lab(row))
              and not re.search(r"jumlah|total|per saham", lab(row))]
    needs = {"NAV per aset": bool(assets),
             "kas": any(re.search(r"\bkas\b|\bcash\b", lab(row)) for row in rows),
             "utang": any(re.search(r"\butang\b|\bdebt\b|pinjaman", lab(row)) for row in rows),
             "RNAV/ekuitas": any(re.search(r"rnav|nilai ekuitas|equity value|total nilai", lab(row)) for row in rows),
             "per saham": any(re.search(r"per saham|per share", lab(row)) for row in rows)}
    missing = [k for k, ok in needs.items() if not ok]
    r.add("T4.rnav_bridge", not missing, "NAV aset dan bridge ke per saham ada" if not missing
          else f"tanpa: {', '.join(missing)}")
    text = " ".join(lab(row) for row in rows) + " " + " ".join(_clean(c).lower() for e in exs for c in _cols(e))
    extra = {"% kepemilikan": r"kepemilikan|ownership|porsi|%\s*milik",
             "jumlah NAV": r"(jumlah|sum|total) (of )?nav",
             "overhead korporat": r"overhead|biaya korporat",
             "diskon RNAV": r"diskon (terhadap )?rnav|discount to rnav|diskon holding"}
    miss = [k for k, pat in extra.items() if not re.search(pat, text)]
    r.add("T4.rnav_rows", not miss, "baris RNAV lengkap" if not miss else f"tanpa: {', '.join(miss)}")
    per_asset = ctx.find_title(r"(diskonto|discount rate).*(aset|asset)|per aset|per asset") or next(
        (e for e in exs if any(re.search(r"diskonto|discount|wacc", _clean(c).lower()) for c in _cols(e)[1:])), None)
    basis_rates = [row for row in rows if len(row) > 3 and re.search(r"\d+(,\d+)?%", _clean(row[-1]))
                   and re.search(r"dcf|diskonto|discount", _clean(row[-1]).lower())]
    ok = per_asset is not None or bool(basis_rates)
    r.add("T4.discount_rate_per_asset", ok, "tingkat diskonto per aset tampil" if ok
          else "tanpa exhibit/kolom tingkat diskonto per aset")


def _rate_rows(ctx):
    exs = ctx.find_all(r"wacc|cost of equity|komponen coe|asumsi analis", exclude=r"sensitivitas")
    return exs, _rows_of(exs)


@_check("T4.rf_beta_erp_sources", "T4.discount_rate_currency", "T4.terminal_growth_cap")
def _t4_rates(ctx, r):
    exs, rows = _rate_rows(ctx)
    if ctx.option not in ("A", "B", "C") or not rows:
        why = f"metode {ctx.method_key or '?'} tanpa komponen tingkat diskonto"
        for cid in ("T4.rf_beta_erp_sources", "T4.discount_rate_currency", "T4.terminal_growth_cap"):
            r.na(cid, why)
        return
    visible = " ".join(" ".join(_clean(c) for c in row) for row in rows).lower()
    notes = " ".join(_note(e) for e in exs).lower()
    text = visible + " " + notes
    missing = []
    if not re.search(r"indogb|\bust\b|us treasury|treasury|sbn", text):
        missing.append("sumber Rf (INDOGB/UST)")
    if not re.search(r"bloomberg|kebijakan analis|regresi|regression|relever|peer", text):
        missing.append("sumber beta")
    if not re.search(r"damodaran|kebijakan analis|policy", text):
        missing.append("sumber ERP")
    r.add("T4.rf_beta_erp_sources", not missing, "sumber Rf, beta, ERP dicatat" if not missing
          else f"tanpa {', '.join(missing)}")
    rf_row = next((row for row in rows if re.search(_RF, _clean(row[0]).lower())), None)
    rf_text = " ".join(_clean(c) for c in rf_row).lower() if rf_row else ""
    problems = []
    if ctx.currency == "USD":
        usd_rate = re.search(r"\bust\b|us treasury|treasury|diskonto usd|tingkat diskonto usd|arus kas usd", text)
        if (rf_row and not re.search(r"\bust\b|treasury", rf_text)) or (not rf_row and not usd_rate):
            problems.append(f"pelapor USD dengan Rf '{rf_text or 'tanpa baris Rf'}' (wajib UST)")
    else:
        if re.search(r"\bcrp\b|country risk|premi risiko negara", visible):
            problems.append("model rupiah menambah CRP di atas INDOGB")
    r.add("T4.discount_rate_currency", not problems, f"tingkat diskonto sesuai mata uang {ctx.currency}"
          if not problems else "; ".join(problems))
    g = _terminal_growth(ctx)
    rf = _pct_in(rf_text.split(" ", 1)[-1]) if rf_row else None
    if rf_row:
        rf = next((v for v in (_pct_in(_clean(c)) for c in rf_row[1:]) if v is not None), rf)
    if ctx.option == "C" or g is None or rf is None:
        r.na("T4.terminal_growth_cap", "tanpa terminal perpetual" if ctx.option == "C"
             else "g atau Rf tidak terbaca")
    else:
        r.add("T4.terminal_growth_cap", g <= rf + 1e-9, f"g {g:.1f}% <= Rf {rf:.1f}%" if g <= rf
              else f"g {g:.1f}% > Rf {rf:.1f}%")


@_check("T4.fcf_vs_fcff")
def _t4_fcf(ctx, r):
    fcff_e = next((e for e in ctx.find_all(r"fcff") if any(_is_forecast(p) for _, p in _period_cols(e))), None)
    if ctx.option != "A" or not fcff_e or not ctx.cf:
        r.na("T4.fcf_vs_fcff", "tanpa FCFF dan arus kas")
        return
    fcff_row = _has(_rows(fcff_e), r"^fcff$", full=False)
    fcf_row = _match_rows(_rows(ctx.cf), [("fcf", r"^(arus kas bebas|free cash flow)$")]).get("fcf")
    if not fcff_row or not fcf_row:
        r.na("T4.fcf_vs_fcff", "baris FCFF atau arus kas bebas tidak ada")
        return
    if _statement_currency(ctx.cf) != _statement_currency(fcff_e):
        r.na("T4.fcf_vs_fcff", "mata uang berbeda")
        return
    _c1, s1 = _unit(_cols(fcff_e)[0])
    _c2, s2 = _unit(_cols(ctx.cf)[0])
    a = {p[0]: num(fcff_row[i]) for i, p in _period_cols(fcff_e) if i < len(fcff_row)}
    b = {p[0]: num(fcf_row[i]) for i, p in _period_cols(ctx.cf) if i < len(fcf_row) and _is_forecast(p)}
    bad, compared = [], 0
    for year, fcf in b.items():
        fcff = a.get(year)
        if fcf is None or fcff is None:
            continue
        compared += 1
        x, y = fcff * (s1 or 1), fcf * (s2 or 1)
        if (x > 0) != (y > 0) or not (0.5 <= abs(y) / abs(x) <= 2 if x else False):
            bad.append(f"FY{year % 100}F FCF {fcf:,.1f} vs FCFF {fcff:,.1f}")
    if not compared:
        r.na("T4.fcf_vs_fcff", "tanpa tahun yang sama")
    else:
        r.add("T4.fcf_vs_fcff", not bad, f"{compared} tahun FCF dalam 0,5-2x FCFF" if not bad
              else _short(bad, 3))


# =================================================================== T5

def _peer_table(ctx):
    return ctx.find_title(r"^(perbandingan peer|peer valuation|perbandingan valuasi peer|valuasi peer)")


def _is_summary_row(label):
    return bool(re.search(r"^(median|rata-rata|average|mean|peringkat|rank)", label.lower()))


@_check("T5.peer_table_median_average_highlight_asof_criteria", "T5.peers_idx_only", "T5.peer_narrative")
def _t5_peers(ctx, r):
    cid = "T5.peer_table_median_average_highlight_asof_criteria"
    peer = _peer_table(ctx)
    select = ctx.find_title(r"^grup peer|^peer group|alasan pemilihan")
    if not peer:
        r.add(cid, False, "tabel peer tidak ada")
    else:
        rows = _rows(peer)
        labels = [_clean(row[0]) for row in rows if row]
        cols = [_clean(c).lower() for c in _cols(peer)]
        ticker = _clean(ctx.meta.get("ticker")).upper()
        problems = []
        if not any(re.match(r"^median", lab, re.I) for lab in labels):
            problems.append("tanpa baris Median")
        if not any(re.match(r"^(rata-rata|average|mean)", lab, re.I) for lab in labels):
            problems.append("tanpa baris Average")
        if not any("(emiten)" in lab.lower() or (ticker and lab.upper().startswith(ticker)) for lab in labels):
            problems.append("baris emiten tidak ditandai")
        need_cols = {"P/E": r"p/e|\bper\b", "PBV": r"p/b|pbv"}
        if not ctx.bank:
            need_cols["EV/EBITDA"] = r"ev/ebitda"
        miss_cols = [k for k, pat in need_cols.items() if not any(re.search(pat, c) for c in cols)]
        if miss_cols:
            problems.append(f"tanpa kolom {', '.join(miss_cols)}")
        peers = [lab for lab in labels if not _is_summary_row(lab) and "(emiten)" not in lab.lower()]
        if peers and all(re.fullmatch(r"[A-Z0-9.]{2,8}", p) for p in peers):
            problems.append("hanya ticker, tanpa nama perusahaan")
        note = (_note(peer) + " " + _title(peer)).lower()
        if not re.search(r"kriteria|criteria|model bisnis", note):
            problems.append("kriteria pemilihan tidak dicantumkan")
        if not re.search(r"(per|as of|tanggal)\s+\d{4}-\d{2}-\d{2}|\d{1,2} \w+ \d{4}", note):
            problems.append("tanggal harga (as of) tidak dicantumkan")
        r.add(cid, not problems, "median, rata-rata, baris emiten, kriteria, as-of ada" if not problems
              else "; ".join(problems))
    # IDX only.
    bad = []
    if select:
        cols = [_clean(c).lower() for c in _cols(select)]
        ex_i = next((i for i, c in enumerate(cols) if re.search(r"bursa|exchange|market|pasar", c)), None)
        st_i = next((i for i, c in enumerate(cols) if re.search(r"status", c)), None)
        for row in _rows(select):
            if ex_i is None or ex_i >= len(row):
                continue
            used = st_i is None or re.search(r"dipakai|used|ya|yes", _clean(row[st_i]).lower() if st_i < len(row) else "")
            exch = _clean(row[ex_i]).upper()
            if used and exch not in ("IDX", "BEI", "IDX (BEI)", "BEI (IDX)"):
                bad.append(f"{_clean(row[0])} ({exch})")
    if peer:
        for row in _rows(peer):
            lab = _clean(row[0]) if row else ""
            if not lab or _is_summary_row(lab) or "(emiten)" in lab.lower():
                continue
            code = lab.split()[0]
            code = code.strip("()")
            symbol = re.search(r"\(([A-Z]{4})(?:\.JK)?\)", lab)
            if symbol:
                code = symbol.group(1)
            if not re.fullmatch(r"[A-Z]{4}", code) and not re.search(r"\(([A-Z]{4})\)", lab):
                bad.append(f"{lab} (bukan kode BEI)")
    if not peer and not select:
        r.na("T5.peers_idx_only", "tanpa peer")
    else:
        r.add("T5.peers_idx_only", not bad, "semua peer tercatat di BEI" if not bad
              else f"peer bukan BEI: {_short(sorted(set(bad)), 8)}")
    # Narrative.
    page = ctx.page_of(peer) if peer else None
    if not page:
        r.na("T5.peer_narrative", "tanpa halaman peer")
    else:
        text = " ".join(str(p) for p in page.get("paragraf") or [])
        ok = bool(re.search(r"median|rata-rata|average", text, re.I) and re.search(r"\d+(?:,\d+)?x", text))
        r.add("T5.peer_narrative", ok, "narasi menyebut posisi vs median/rata-rata peer" if ok
              else "narasi peer tanpa posisi terhadap median/rata-rata (multiple x)")


# Validity bands of peer multiples, as in app.method_chain (PEER_PE_BAND,
# PEER_PB_BAND, PEER_EV_BAND): a median needs three peers inside the band.
_PEER_MULTIPLES = (("EV/EBITDA", r"EV/EBITDA", 50.0), ("P/E", r"\bP/E\b|\bPER\b", 50.0),
                   ("P/B", r"P/BV|P/B\b|\bPBV\b", 10.0))
_TOO_FEW = re.compile(r"peer[^;.]*kurang dari (tiga|3)|kurang dari (tiga|3) peer|fewer than (three|3)|"
                      r"peer valid (kurang|<)", re.I)
MIN_VALID_PEERS = 3


def _multiple_key(text):
    for key, pat, _cap in _PEER_MULTIPLES:
        if re.search(pat, text or ""):
            return key
    return None


def _cap(key):
    return next(cap for k, _p, cap in _PEER_MULTIPLES if k == key)


def _valid_in_column(peer, key):
    """Valid multiples of ``key`` among the peer rows of the comparison table."""
    pat = next(p for k, p, _c in _PEER_MULTIPLES if k == key)
    cols = [_clean(c) for c in _cols(peer)]
    idx = next((i for i, c in enumerate(cols) if i and re.search(pat, c, re.I)), None)
    if idx is None:
        return None
    values = []
    for row in _rows(peer):
        lab = _clean(row[0]) if row else ""
        if not lab or _is_summary_row(lab) or "(emiten)" in lab.lower() or idx >= len(row):
            continue
        v = num(row[idx])
        if v is not None:
            values.append(v)
    return sum(1 for v in values if 0 < v <= _cap(key))


def _valid_in_text(text, key):
    """Valid multiples listed in a note ('TLKM 3,7x, ISAT 4,3x')."""
    values = [float(m.group(1).replace(".", "").replace(",", "."))
              for m in re.finditer(r"\b[A-Z][A-Z0-9.]{2,7}\s+(\d+(?:,\d+)?)x", text or "")]
    return sum(1 for v in values if 0 < v <= _cap(key)) if values else None


def _chain_rows(chain):
    if not chain:
        return []
    cols = [_clean(c).lower() for c in _cols(chain)]
    find = lambda pat, default: next((i for i, c in enumerate(cols) if re.search(pat, c)), default)  # noqa: E731
    d_i, v_i, a_i = find(r"keputusan|decision", 1), find(r"nilai|value", 2), find(r"alasan|reason", 3)
    out = []
    for row in _rows(chain):
        get = lambda i: _clean(row[i]) if i is not None and i < len(row) else ""  # noqa: E731
        out.append({"label": get(0), "decision": get(d_i).lower(), "value": num(get(v_i)),
                    "reason": get(a_i), "key": _multiple_key(get(0))})
    return out


@_check("T5.peer_crosscheck_consistency")
def _t5_peer_consistency(ctx, r):
    peer = _peer_table(ctx)
    chain = _chain_rows(ctx.find_title(r"^rantai metode"))
    bad, checked = [], 0
    # Medians and averages printed in the peer table.
    if peer:
        for key, _pat, _cap_v in _PEER_MULTIPLES:
            valid = _valid_in_column(peer, key)
            if valid is None:
                continue
            pat = next(p for k, p, _c in _PEER_MULTIPLES if k == key)
            idx = next(i for i, c in enumerate(_cols(peer)) if i and re.search(pat, _clean(c), re.I))
            for row in _rows(peer):
                lab = _clean(row[0]) if row else ""
                if re.match(r"^(median|rata-rata|average|mean)", lab, re.I) and idx < len(row) \
                        and num(row[idx]) is not None:
                    checked += 1
                    if valid < MIN_VALID_PEERS:
                        bad.append(f"Exhibit {peer.get('n')} {lab[:24]} {key} {_clean(row[idx])} dari "
                                   f"{valid} multiple valid (< {MIN_VALID_PEERS})")
    # Per-share values derived from peer multiples.
    for e in ctx.exs:
        title = _title(e)
        if e is peer or re.search(r"^rantai metode|^grup peer|alasan pemilihan|^band historis|^kondisi", title, re.I):
            continue
        for row in _rows(e):
            lab = _clean(row[0]) if row else ""
            context = f"{lab} {title}"
            if not re.search(r"peer", context, re.I) or re.search(r"target harga metode utama", lab, re.I):
                continue
            values = [num(c) for c in row[1:] if re.match(r"^\(?Rp", _clean(c)) and num(c) is not None]
            key = _multiple_key(lab) or _multiple_key(title)
            if not values or not key:
                continue
            checked += 1
            where = f"Exhibit {e.get('n')} '{lab[:40]}' Rp{values[0]:,.0f}".replace(",", ".")
            rows_k = [c for c in chain if c["key"] == key]
            run = [c for c in rows_k if re.match(r"(terpilih|silang cek|selected|cross)", c["decision"])]
            skipped = [c for c in rows_k if re.match(r"(tidak dijalankan|not run)", c["decision"])]
            if rows_k and not run and any(_TOO_FEW.search(c["reason"]) for c in skipped):
                bad.append(f"{where}: rantai metode tidak menjalankan {key} (peer valid < 3)")
                continue
            if run and re.search(r"median|\(basis\)", lab, re.I) and not re.search(r"kuartil|quartile", lab, re.I):
                if not any(c["value"] is not None and abs(c["value"] - values[0]) <= _tick(values[0])
                           for c in run):
                    bad.append(f"{where}: berbeda dari rantai metode "
                               f"({', '.join(str(c['value']) for c in run)})")
            valid = _valid_in_column(peer, key) if peer else None
            if valid is None:
                valid = _valid_in_text(_note(e), key)
            if valid is not None and valid < MIN_VALID_PEERS:
                bad.append(f"{where}: {valid} multiple {key} valid (< {MIN_VALID_PEERS})")
    if not checked:
        r.na("T5.peer_crosscheck_consistency", "tanpa nilai atau median turunan peer")
    else:
        r.add("T5.peer_crosscheck_consistency", not bad,
              f"{checked} nilai/median peer konsisten dengan rantai metode" if not bad else _short(bad, 5))


_BAND_TEMPLATE = ("P/E", "P/BV")
_BAND_SUBSTITUTE = re.compile(r"^(EV/EBITDA|EV/SALES|EV/EBIT|EV/REVENUE|P/S)$")
_BAND_SWAP = re.compile(r"(\S+) menggantikan (?:band )?(P/E|P/BV|P/B)\b[^.]*?\bkarena \S"
                        r"|(\S+) replaces (?:the )?(P/E|P/BV|P/B)\b[^.]*?\bbecause \S", re.I)


def _band_label(e):
    label = _clean(_data(e).get("label")).upper().replace(" ", "")
    return "P/BV" if label == "P/B" else label


def _band_swaps(text):
    """{template multiple: substitute} stated as '<X> menggantikan band <P/E|P/BV> karena ...'."""
    out = {}
    for m in _BAND_SWAP.finditer(_clean(text)):
        sub, orig = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        orig = "P/BV" if orig.upper() == "P/B" else orig.upper()
        out[orig] = sub.upper()
    return out


@_check("T5.hist_bands_mean_median_marker")
def _t5_bands(ctx, r):
    """P/E and P/BV bands over a year with mean, median and the current marker.
    Where P/E or P/BV is not meaningful the template allows another multiple
    (EV/EBITDA, EV/Sales): a substitute chart counts for the multiple it
    replaces only when its note states the swap and why."""
    bands = [e for e in ctx.exs if e.get("tipe") == "band_chart"]
    if not bands:
        r.add("T5.hist_bands_mean_median_marker", False, "grafik band P/E dan P/BV tidak ada")
        return
    covered, problems, swaps = set(), [], []
    for e in bands:
        label = _band_label(e)
        if label in _BAND_TEMPLATE:
            covered.add(label)
        elif _BAND_SUBSTITUTE.match(label):
            stated = {orig for orig, sub in _band_swaps(_note(e)).items() if sub == label}
            if not stated:
                problems.append(f"Exhibit {e.get('n')}: band {label} tanpa alasan pengganti P/E atau P/BV")
            covered |= stated
            swaps += [f"{_clean(_data(e).get('label'))} menggantikan {orig}" for orig in sorted(stated)]
    problems = [f"tanpa band {m} (atau pengganti yang dinyatakan)" for m in _BAND_TEMPLATE
                if m not in covered] + problems
    for e in bands:
        d = _data(e)
        values = [v for v in d.get("values") or [] if isinstance(v, (int, float))]
        if any(not isinstance(d.get(k), (int, float)) for k in ("mean", "median", "current")):
            problems.append(f"Exhibit {e.get('n')}: mean/median/posisi kini tidak lengkap")
            continue
        dates = d.get("dates") or []
        try:
            span = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days
        except (ValueError, IndexError, TypeError):
            span = 0
        if span < 330:
            problems.append(f"Exhibit {e.get('n')}: jendela {span} hari (template 1 tahun)")
        if values and not min(values) <= d["mean"] <= max(values):
            problems.append(f"Exhibit {e.get('n')}: mean di luar band")
    r.add("T5.hist_bands_mean_median_marker", not problems,
          ("band P/E dan P/BV 1 tahun lengkap" + (f" ({'; '.join(swaps)}, alasan dinyatakan)"
                                                   if swaps else ""))
          if not problems else "; ".join(problems))


@_check("T5.implied_price_mean_median_two_multiples", "T5.disclaimer")
def _t5_implied(ctx, r):
    table = ctx.find_title(r"^band historis|^historical band|^relative valuation")
    if not table:
        r.add("T5.implied_price_mean_median_two_multiples", False, "tabel harga implisit band tidak ada")
    else:
        cols = [_clean(c).lower() for c in _cols(table)]
        idx = next((i for i, c in enumerate(cols) if re.search(r"implisit|implied", c)), None)
        # A substitute multiple's row counts only when the table note states
        # which multiple it replaces and why.
        stated = set(_band_swaps(_note(table)).values())
        good, unstated = [], []
        for row in _rows(table):
            if idx is None or idx >= len(row):
                continue
            values = re.findall(r"Rp\s?\d[\d.]*", _clean(row[idx]))
            if len(values) < 2:
                continue
            label = _clean(row[0])
            key = "P/BV" if label.upper().replace(" ", "") == "P/B" else label.upper().replace(" ", "")
            if key in _BAND_TEMPLATE or not _BAND_SUBSTITUTE.match(key) or key in stated:
                good.append(label)
            else:
                unstated.append(label)
        ok = len(good) >= 2
        r.add("T5.implied_price_mean_median_two_multiples", ok,
              f"harga implisit mean/median: {', '.join(good)}" if ok
              else f"harga implisit mean dan median hanya untuk {good or 'tidak ada'}"
              + (f"; pengganti tanpa alasan: {', '.join(unstated)}" if unstated else ""))
    anchor = table or next((e for e in ctx.exs if e.get("tipe") == "band_chart"), None)
    page = ctx.page_of(anchor) if anchor else None
    if not page:
        r.na("T5.disclaimer", "tanpa halaman band historis")
        return
    visible = " ".join([str(p) for p in page.get("paragraf") or []] +
                       [_title(e) + " " + _clean(e.get("narasi")) for e in page.get("exhibit") or []])
    missing = []
    if not re.search(r"bukan (?:target harga|nilai model)|bukan tp\b|not (the |a )?target price",
                     visible, re.I):
        missing.append("bukan nilai model resmi")
    if not re.search(r"driver (fundamental )?(tetap|konstan)|konstan|constant|tetap di level", visible, re.I):
        missing.append("asumsi driver konstan")
    r.add("T5.disclaimer", not missing, "disclaimer lengkap" if not missing
          else f"disclaimer tanpa: {', '.join(missing)}")


# =================================================================== T6/T7

def _row_values(e, row):
    """{year: (value, tolerance, kind)} of a statement row in currency units."""
    _cur, scale = _unit(_cols(e)[0] if _cols(e) else "")
    scale = scale or 1.0
    out = {}
    for i, p in _period_cols(e):
        cell = row[i] if i < len(row) else None
        parsed = parse_num(cell)
        if parsed:
            out[p[0]] = (parsed[0] * scale, 0.5 * 10 ** -parsed[1] * scale, "F" if _is_forecast(p) else "A")
    return out


def _lines_check(ctx, e, concepts, required, name):
    found = _match_rows(_rows(e), concepts)
    missing = [k for k in required if k not in found]
    order = [k for k, _ in concepts if k in found]
    rows = _rows(e)
    actual = sorted(order, key=lambda k: rows.index(found[k]))
    return found, missing, order == actual, actual


@_check("T6.income_statement_lines", "T6.income_statement_order")
def _t6_is(ctx, r):
    if not ctx.is_:
        r.add("T6.income_statement_lines", False, "exhibit laba rugi tidak ada")
        r.na("T6.income_statement_order", "tanpa laba rugi")
        return
    concepts = IS_ROWS[_profile_kind(ctx)]
    _found, missing, in_order, actual = _lines_check(ctx, ctx.is_, concepts, [k for k, _ in concepts], "laba rugi")
    r.add("T6.income_statement_lines", not missing, f"{len(concepts)} baris template ada" if not missing
          else f"tanpa baris: {', '.join(missing)}")
    r.add("T6.income_statement_order", in_order, "urutan sesuai template" if in_order
          else f"urutan {actual}")


@_check("T6.balance_sheet_lines_and_balance", "T6.balance_sheet_subtotals")
def _t6_bs(ctx, r):
    if not ctx.bs:
        r.add("T6.balance_sheet_lines_and_balance", False, "exhibit neraca tidak ada")
        r.na("T6.balance_sheet_subtotals", "tanpa neraca")
        return
    kind = _profile_kind(ctx)
    concepts = BS_ROWS[kind] + (BS_OPTIONAL_BANK if ctx.bank else [])
    found = _match_rows(_rows(ctx.bs), concepts)
    missing = [k for k, _ in BS_ROWS[kind] if k not in found]
    problems = [f"tanpa baris: {', '.join(missing)}"] if missing else []
    ta = _row_values(ctx.bs, found["total_assets"]) if "total_assets" in found else {}
    tle = _row_values(ctx.bs, found["total_le"]) if "total_le" in found else {}
    unbalanced = [f"{y}: aset {_display(ta[y][0], ctx.bs)} vs L+E {_display(tle[y][0], ctx.bs)}"
                  for y in sorted(set(ta) & set(tle)) if not _close(ta[y][0], tle[y][0], ta[y][1] + tle[y][1])]
    if unbalanced:
        problems.append("tidak seimbang " + _short(unbalanced, 3))
    r.add("T6.balance_sheet_lines_and_balance", not problems,
          f"baris lengkap; seimbang {len(set(ta) & set(tle))} kolom" if not problems else "; ".join(problems))
    sums = {"total_ca": ("cash", "receivables", "inventory", "other_ca"),
            "total_assets": ("total_ca", "fixed_assets", "other_nca"),
            "total_cl": ("st_debt", "payables", "other_cl"),
            "total_liabilities": ("total_cl", "lt_debt", "other_ncl"),
            "total_le": ("total_liabilities", "equity")} if not ctx.bank else {}
    bad, checked = [], 0
    for total, parts in sums.items():
        if total not in found or any(p not in found for p in parts):
            continue
        tv = _row_values(ctx.bs, found[total])
        pv = [_row_values(ctx.bs, found[p]) for p in parts]
        for year, (value, tol, _k) in tv.items():
            if all(year in v for v in pv):
                checked += 1
                s = sum(v[year][0] for v in pv)
                t = tol + sum(v[year][1] for v in pv)
                if not _close(value, s, t):
                    bad.append(f"{total} {year}")
    if not checked:
        r.na("T6.balance_sheet_subtotals", "subtotal tidak dapat dijumlah (baris n.m. atau tidak ada)")
    else:
        r.add("T6.balance_sheet_subtotals", not bad, f"{checked} subtotal cocok" if not bad
              else f"subtotal tidak sama dengan jumlah: {_short(bad, 4)}")


# The short-term debt the statements draw to keep cash at its minimum
# (report_extras.REVOLVER_LINE) is a screening plug; above this share of total
# equity the forecast leans on financing nobody has arranged.
BALANCING_DEBT_EQUITY_MAX = 0.25
_REVOLVER_LABEL = re.compile(r"pinjaman penyeimbang kas|balancing (cash )?(debt|borrowing)", re.I)


@_check("T6.balancing_debt_share")
def _t6_revolver(ctx, r):
    if not ctx.bs or ctx.bank:
        r.na("T6.balancing_debt_share", "tanpa neraca" if not ctx.bs else "bank: tanpa utang penyeimbang")
        return
    rows = _rows(ctx.bs)
    memo = next((row for row in rows if row and _REVOLVER_LABEL.search(_clean(row[0]))), None)
    if memo is None:
        r.add("T6.balancing_debt_share", True, "tanpa pinjaman penyeimbang kas")
        return
    equity = _match_rows(rows, [c for c in BS_ROWS[_profile_kind(ctx)] if c[0] == "equity"]).get("equity")
    debt = {y: v for y, v in _row_values(ctx.bs, memo).items() if v[2] == "F"}
    eq = _row_values(ctx.bs, equity) if equity else {}
    heavy = [f"{y}F {debt[y][0] / eq[y][0]:.0%}" for y in sorted(debt)
             if y in eq and eq[y][0] > 0 and debt[y][0] / eq[y][0] > BALANCING_DEBT_EQUITY_MAX]
    r.add("T6.balancing_debt_share", not heavy,
          (f"pinjaman penyeimbang kas <= {BALANCING_DEBT_EQUITY_MAX:.0%} ekuitas" if not heavy else
           f"pinjaman penyeimbang kas > {BALANCING_DEBT_EQUITY_MAX:.0%} ekuitas: "
           + ", ".join(heavy) + "; pendanaan capex/dividen belum dimodelkan"))


def _cf_sections(e):
    labels = [_clean(row[0]).lower() for row in _rows(e) if row and _is_section_row(row)]
    return [name for name, pat in CF_SECTIONS if any(re.search(pat, lab) for lab in labels)]


@_check("T7.cash_flow_sections_and_tieout", "T7.cash_flow_actual_reconciliation")
def _t7_cf(ctx, r):
    if not ctx.cf:
        r.add("T7.cash_flow_sections_and_tieout", False, "exhibit arus kas tidak ada")
        r.na("T7.cash_flow_actual_reconciliation", "tanpa arus kas")
        return
    concepts = CF_ROWS["nonbank"]
    found = _match_rows(_rows(ctx.cf), concepts)
    required = CF_BANK_REQUIRED if ctx.bank else [k for k, _ in concepts]
    problems = []
    missing = [k for k in required if k not in found]
    if missing:
        problems.append(f"tanpa baris: {', '.join(missing)}")
    sections = _cf_sections(ctx.cf)
    if not ctx.bank and len(sections) < 3:
        problems.append(f"blok {', '.join(n for n, _ in CF_SECTIONS if n not in sections)} tidak ada")
    vals = {k: _row_values(ctx.cf, found[k]) for k in ("begin_cash", "net_change", "end_cash", "cfo", "cfi", "cff")
            if k in found}
    # Explicit, labelled source-data reconciling lines (actual columns only):
    # 'cash' sits between begin and end cash, 'flows' between CFO+CFI+CFF and
    # the net change. They count on actual columns; a forecast cell must read
    # 0 or n.m. (a filled one would be a plug and fails the blocker).
    gaps = _cf_gap_rows(ctx.cf)
    gap_vals = {k: _row_values(ctx.cf, row) for k, row in gaps.items()}
    fc_bad, act_bad, bridged = [], [], set()
    for key, row in gaps.items():
        for year, (value, tol, kind) in gap_vals[key].items():
            if kind == "F" and not _close(value, 0.0, tol):
                fc_bad.append(f"baris selisih data sumber '{_clean(row[0])}' terisi pada {year}F")

    def gap(key, year, kind):
        if kind == "F" or year not in gap_vals.get(key, {}):
            return 0.0, 0.0
        value, tol, _k = gap_vals[key][year]
        if value:
            bridged.add(f"{year}A")
        return value, tol

    def recon(name, year, lhs, rhs, tol, kind):
        if not _close(lhs, rhs, tol):
            (fc_bad if kind == "F" else act_bad).append(
                f"{name} {year}: {_display(lhs, ctx.cf)} vs {_display(rhs, ctx.cf)}")
    if {"begin_cash", "net_change", "end_cash"} <= set(vals):
        for year, (end, tol, kind) in vals["end_cash"].items():
            if year in vals["begin_cash"] and year in vals["net_change"]:
                b, n = vals["begin_cash"][year], vals["net_change"][year]
                g, g_tol = gap("cash", year, kind)
                tol_all = tol + b[1] + n[1] + g_tol
                recon("awal + perubahan = akhir", year, b[0] + n[0] + g, end,
                      tol_all if kind == "F" else max(tol_all, 0.01 * abs(end)), kind)
    if {"cfo", "cfi", "cff", "net_change"} <= set(vals):
        for year, (chg, tol, kind) in vals["net_change"].items():
            if all(year in vals[k] for k in ("cfo", "cfi", "cff")):
                g, g_tol = gap("flows", year, kind)
                s = sum(vals[k][year][0] for k in ("cfo", "cfi", "cff")) + g
                t = tol + sum(vals[k][year][1] for k in ("cfo", "cfi", "cff")) + g_tol
                recon("CFO + CFI + CFF = perubahan", year, s, chg,
                      t if kind == "F" else max(t, 0.01 * max(abs(chg), abs(s))), kind)
    if fc_bad:
        problems.append("rekonsiliasi proyeksi: " + _short(fc_bad, 3))
    r.add("T7.cash_flow_sections_and_tieout", not problems, "blok dan rekonsiliasi kas lengkap"
          if not problems else "; ".join(problems))
    r.add("T7.cash_flow_actual_reconciliation", not act_bad,
          (f"rekonsiliasi kas aktual lengkap dengan baris selisih data sumber eksplisit "
           f"({', '.join(sorted(bridged))})" if bridged else "rekonsiliasi kas aktual dalam 1%")
          if not act_bad else _short(act_bad, 3))


_CF_GAP_LABEL = re.compile(r"\((data sumber|source data)\)\s*$", re.I)


def _cf_gap_rows(e):
    """{'cash' | 'flows': row} of explicitly labelled source-data reconciling
    lines: the label ends '(data sumber)'/'(source data)' and names an FX or
    cash-definition effect ('cash') or a cash-flow-component gap ('flows')."""
    out = {}
    for row in _rows(e):
        label = _clean(row[0]) if row else ""
        if not _CF_GAP_LABEL.search(label):
            continue
        low = label.lower()
        if re.search(r"komponen arus kas|cash flow components?", low):
            out.setdefault("flows", row)
        elif re.search(r"efek kurs|selisih definisi kas|fx effect|cash definition", low):
            out.setdefault("cash", row)
    return out


@_check("T7.key_ratio_sections_format", "T7.key_ratio_format")
def _t7_ratio(ctx, r):
    if not ctx.ratio:
        r.add("T7.key_ratio_sections_format", False, "exhibit rasio utama tidak ada")
        r.na("T7.key_ratio_format", "tanpa rasio utama")
        return
    rows = _rows(ctx.ratio)
    missing, sections = [], {}
    current = None
    for row in rows:
        if _is_section_row(row):
            lab = _clean(row[0]).lower()
            current = ("growth" if re.search(r"pertumbuhan|growth", lab) else
                       "profitability" if re.search(r"profitabilitas|profitability", lab) else
                       "leverage" if re.search(r"leverage|solvabilitas", lab) else lab)
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(row)
    if ctx.bank:
        found = _match_rows(rows, RATIO_ROWS["bank"]["all"], full=True)
        missing = [k for k, _ in RATIO_ROWS["bank"]["all"] if k not in found]
    else:
        for sec, concepts in RATIO_ROWS["nonbank"].items():
            found = _match_rows(sections.get(sec) or [], concepts)
            missing += [f"{sec}.{k}" for k, _ in concepts if k not in found]
    r.add("T7.key_ratio_sections_format", not missing, "baris rasio template ada" if not missing
          else f"tanpa baris: {', '.join(missing)}")
    fmt = []
    if not ctx.bank and not {"growth", "profitability", "leverage"} <= set(sections):
        fmt.append("blok Growth/Profitability/Leverage tidak lengkap")
    for row in rows:
        if _is_section_row(row):
            continue
        for cell in row[1:]:
            p = parse_num(cell)
            if p and p[1] != 1:
                fmt.append(f"{_clean(row[0])[:24]}: {_clean(cell)}")
                break
    r.add("T7.key_ratio_format", not fmt, "blok dan satu desimal" if not fmt else _short(fmt, 5))


def _display(value, e):
    """A currency-unit value in the exhibit's own display unit: '1.104,2 US$ juta'."""
    label = _clean(_cols(e)[0]) if e and _cols(e) else ""
    _cur, scale = _unit(label)
    text = f"{value / (scale or 1):,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text} {label}".strip()


@_check("T7.tieouts")
def _t7_tieouts(ctx, r):
    checks, bad = 0, []
    unit_e = ctx.is_ or ctx.cf or ctx.bs

    def compare(name, a, b):
        nonlocal checks
        for year in sorted(set(a) & set(b)):
            checks += 1
            if not _close(a[year][0], b[year][0], a[year][1] + b[year][1]):
                bad.append(f"{name} {year}: {_display(a[year][0], unit_e)} vs {_display(b[year][0], unit_e)}")
    is_rows = _rows(ctx.is_) if ctx.is_ else []
    parent = _has(is_rows, IS_NET_PARENT, full=False)
    anynet = _has(is_rows, IS_NET_ANY, full=False)
    is_np = _row_values(ctx.is_, parent or anynet) if (parent or anynet) else {}
    is_any = _row_values(ctx.is_, anynet) if anynet else {}
    kf_np, kf_cur = _kf_series(ctx, "net_profit")
    kf_np = {y: (v, t, "") for y, (v, t) in kf_np.items()}
    if is_np and kf_np:
        if kf_cur and _statement_currency(ctx.is_) and kf_cur != _statement_currency(ctx.is_):
            pass  # reported by T3.currency_consistency
        else:
            compare("laba bersih LR vs KF", is_np, kf_np)
    cf_found = _match_rows(_rows(ctx.cf), CF_ROWS["nonbank"]) if ctx.cf else {}
    if is_np and "net_profit" in cf_found:
        cf_np = _row_values(ctx.cf, cf_found["net_profit"])
        for year in sorted(set(cf_np) & (set(is_np) | set(is_any))):
            checks += 1
            v, t, _k = cf_np[year]
            options = [x for x in (is_np.get(year), is_any.get(year)) if x]
            if not any(_close(v, o[0], t + o[1]) for o in options):
                bad.append(f"laba bersih AK vs LR {year}: {_display(v, ctx.cf)} vs {_display(options[0][0], ctx.cf)}")
    bs_found = _match_rows(_rows(ctx.bs), BS_ROWS["nonbank"][:1]) if ctx.bs else {}
    if "end_cash" in cf_found and "cash" in bs_found:
        compare("kas akhir AK vs kas neraca", _row_values(ctx.cf, cf_found["end_cash"]),
                _row_values(ctx.bs, bs_found["cash"]))
    if "end_cash" in cf_found and "begin_cash" in cf_found:
        end = _row_values(ctx.cf, cf_found["end_cash"])
        begin = _row_values(ctx.cf, cf_found["begin_cash"])
        for year in sorted(begin):
            if year - 1 in end:
                checks += 1
                if not _close(begin[year][0], end[year - 1][0], begin[year][1] + end[year - 1][1]):
                    bad.append(f"kas awal {year} vs kas akhir {year - 1}")
    if not checks:
        r.na("T7.tieouts", "tidak ada pasangan angka untuk tie-out (baris n.m./tidak ada)")
    else:
        r.add("T7.tieouts", not bad, f"{checks} tie-out cocok (< 0,1%)" if not bad else _short(bad, 5))


# ================================================================== driver

def check_template(doc: dict | None, *, profile: str | None = None, method_key: str | None = None,
                   currency: str | None = None) -> dict:
    """Run every template check on one report document."""
    ctx = _Ctx(doc or {}, profile, method_key, currency)
    results = _Results()
    for fn, ids in _REGISTRY:
        before = len(results.items)
        try:
            fn(ctx, results)
        except Exception as exc:  # fail closed: a crashing check is a failed check
            del results.items[before:]
            for cid in ids:
                results.add(cid, False, f"pemeriksaan error: {type(exc).__name__}: {exc}")
    items = results.items
    blockers = [f"{c['check']}: {c['message']}" for c in items if c["blocker"]]
    warnings = [f"{c['check']}: {c['message']}" for c in items
                if c["status"] == FAIL and c["severity"] == WARNING]
    return {"tool": "check_template", "profile": ctx.profile, "method_key": ctx.method_key,
            "option": ctx.option, "published": ctx.published,
            "status": "lolos" if not blockers else "gagal",
            "checks": items, "blockers": blockers, "warnings": warnings}


# --------------------------------------------------------------------- CLI

def _pdf_pages(path: Path):
    """Page texts of a PDF, or (None, reason)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            return None, "pypdf/pdfplumber tidak terpasang; cek PDF dilewati"
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages], None
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages], None


def run_folder(folder, tickers=None, *, render=False) -> dict:
    from app import outputs
    folder = Path(folder)
    wanted = [t.upper() for t in tickers or []] or outputs.tickers(outputs.REPORT, folder)
    report = {}
    for t in wanted:
        doc = outputs.load(outputs.REPORT, folder, t)
        if not isinstance(doc, dict):
            report[t] = {"error": f"laporan {t} tidak ada di {folder}"}
            continue
        result = check_template(doc)
        checks = list(result["checks"])
        notes = []
        if render:
            from app.harness import render_check
            try:
                from app import render as render_mod
                html = render_mod.render(doc)
                checks += render_check.check_rendered(html, doc)["checks"]
            except Exception as exc:
                checks.append(render_check.error_result(exc))
            pdf = folder / f"{t}.pdf"
            if pdf.is_file():
                pages, why = _pdf_pages(pdf)
                if pages is None:
                    notes.append(why)
                else:
                    checks += render_check.check_pdf_text(pages, doc)["checks"]
            else:
                notes.append(f"{pdf.name} tidak ada; cek PDF dilewati")
        blockers = [c for c in checks if c["blocker"]]
        report[t] = {"status": "lolos" if not blockers else "gagal", "profile": result["profile"],
                     "method_key": result["method_key"], "published": result["published"],
                     "checks": checks, "notes": notes,
                     "blockers": len(blockers),
                     "warnings": sum(1 for c in checks if c["status"] == FAIL and c["severity"] == WARNING)}
    return report


def _print_table(report, out=sys.stdout):
    for t, res in report.items():
        if "error" in res:
            print(f"== {t}: {res['error']}", file=out)
            continue
        print(f"== {t} ({res['profile']}, {res['method_key']}, "
              f"{'published' if res['published'] else 'draft'}): "
              f"{res['blockers']} blocker gagal, {res['warnings']} warning gagal", file=out)
        for note in res["notes"]:
            print(f"   catatan: {note}", file=out)
        print(f"   {'check':<56} {'severity':<8} {'result':<14} detail", file=out)
        for c in res["checks"]:
            detail = c["message"] if len(c["message"]) <= 200 else c["message"][:197] + "..."
            print(f"   {c['check']:<56} {c['severity']:<8} {c['status']:<14} {detail}", file=out)
    total_b = sum(r.get("blockers", 0) for r in report.values())
    total_w = sum(r.get("warnings", 0) for r in report.values())
    print(f"TOTAL: {len(report)} laporan, {total_b} blocker gagal, {total_w} warning gagal", file=out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Template harness (spec/Struktur-Template.md)")
    parser.add_argument("folder", help="run folder, e.g. out/demo-reports")
    parser.add_argument("tickers", nargs="*")
    parser.add_argument("--render", action="store_true", help="also check rendered HTML and PDF text")
    parser.add_argument("--json", action="store_true", help="print JSON instead of tables")
    args = parser.parse_args(argv)
    report = run_folder(args.folder, args.tickers, render=args.render)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        _print_table(report)
    failed = any("error" in r or r.get("blockers") for r in report.values())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
