"""Five forecast years of income statement, balance sheet and cash flow on the
path the report already values (spec §3.1, §4.1a, §5.4; template slides 6-7).

``forecast_rows`` takes the same FY path as the charts and Key Financials (the
validated analyst scenario: official 1H actual + H2 assumption + four
out-years, or a production forecast) and completes the statements with the
driver values the valuation uses for this issuer:

* going concern: D&A intensity, effective tax rate and working-capital
  intensity from ``scenario_value`` (the scenario FCFF DCF), so the FCFF the
  rows imply equals the DCF's per-year FCFF;
* finite-life mining on the LoM schedule: per-year D&A, interest (2x 1H
  finance cost), income tax and PNBP from the valued mine plan; working
  capital is held flat because the LoM does not model it;
* financial institutions: only what the DDM drives (profit, payout,
  dividends, equity, per-share values); bank balance-sheet drivers are
  never invented and are listed in ``notes``.

Interim opening (``MODE_INTERIM``): when the issuer evidence pack carries the
full official 1H balance sheet, the 1H cash flow that ties opening to closing
cash and the 1H D&A, the first forecast year's balance sheet rolls from that
balance sheet with H2 flows only (H2 profit; FY D&A, capex and working-capital
change less the official 1H; the prior year's final dividend when 1H did not
pay it), and its cash flow is the official 1H plus the modelled H2 from the
year-end cash. This also covers a share count that moved since the year-end
(rights issue): the interim balance sheet already holds the capital raised.
Later years roll as usual. The revolver floor is capped at the lower of the
interim and the year-end cash, since interim cash can hold unspent proceeds.

Everything the scenario does not give (debt path, other non-current items,
dividend timing, NCI dividends) is a labelled screening assumption in
``assumptions``. Cash is never a plug: it is opening cash plus the cash-flow
statement, and the balance sheet balances because every line moves through
the income statement or the cash flow.

Values are full Rupiah like Sectors ``historical_financials``; US$ reporters
are converted at the same dated spot rate as ``report_extras.chart_forecast_rows``
(the rows are the rupiah mirror of a US$ model: US$ x that one rate). A US$
reporter whose official annual release carries the base year's closing equity
opens from it: the Sectors balance sheet (rupiah at Sectors' own rate) is
restated to that official US$ base at the same spot rate, and the base year's
parent profit and minorities come from the release.
Costs are positive magnitudes (cost_of_revenue, operating_expense,
depreciation, interest_expense_non_operating, tax, capital_expenditure,
dividends_paid); cash-flow lines are signed as cash moves
(operating/investing/financing/net cash flow, change_in_working_capital where
an increase in working capital is negative, other_*_cash_flow, debt_raised,
equity_raised). ``minority`` is the non-controlling share of profit.

Net profit, per share: ``earnings`` is profit attributable to the parent, the
"Laba bersih" of the income statement and Key Financials. Where the scenario
has no parent split (the mining interim anchor and its LoM out-years), the
parent share is the official prior-year ratio, the one Key Financials applies
to EPS and PER (``parent_share``). The cash flow starts
from it: operating_cash_flow = earnings + depreciation +
change_in_working_capital + other_operating_cash_flow, where
other_operating_cash_flow is the minority share (retained in the group; NCI
dividends are not modelled), so operating_cash_flow also equals consolidated
profit (net_cons) + D&A - increase in working capital. ``eps`` is parent
earnings and ``bvps`` parent equity (total equity less NCI), both over the
share count the valuation and the PER exhibit use (the scenario valuation's
``shares``, else ``scenario_value.bridge``: official interim register, else
Sectors); ``dps`` = payout x eps, the DDM's DPS line.
"""
from __future__ import annotations

import re

from . import cache, fmt, release_policy, scenario_value, share_basis

MODE_FULL = "laporan lengkap"
# Full statements opened from the official interim balance sheet (spec §4.1a):
# the first forecast year's balance sheet rolls from it with H2 flows only.
MODE_INTERIM = "laporan lengkap, neraca awal interim resmi"
MODE_EQUITY = "laba dan ekuitas"
MODE_BANK = "bank: laba, dividen dan ekuitas"

# Keys the report's statements read, per profile. Anything not produced gets
# a reason in ``notes``.
IS_KEYS = ("revenue", "cost_of_revenue", "gross_profit", "operating_expense", "operating_pnl",
           "ebitda", "depreciation", "interest_income", "interest_expense_non_operating",
           "non_operating_income_or_loss", "other_non_operating", "earnings_before_tax", "tax",
           "net_cons", "minority", "earnings")
BS_KEYS = ("cash_and_equivalents", "trade_receivables", "inventories", "other_current_assets",
           "current_assets", "fixed_assets", "other_non_current_assets", "total_assets",
           "short_term_debt", "trade_payables", "other_current_liabilities",
           "current_liabilities", "long_term_debt", "other_non_current_liabilities",
           "non_current_liabilities", "total_liabilities", "stockholders_equity",
           "non_controlling_interest", "total_equity", "total_debt", "net_debt",
           "working_capital", "revolver")
CF_KEYS = ("cash_begin", "operating_cash_flow", "change_in_working_capital",
           "other_operating_cash_flow", "capital_expenditure", "other_investing_cash_flow",
           "investing_cash_flow", "debt_raised", "dividends_paid", "equity_raised",
           "other_financing_cash_flow", "financing_cash_flow", "net_cash_flow",
           "free_cash_flow", "fcff", "revolver_flow")
PER_SHARE_KEYS = ("eps", "dps", "bvps", "payout", "roe")
RATIO_KEYS = ("interest_coverage",)
NON_FINANCIAL_KEYS = IS_KEYS + BS_KEYS + CF_KEYS + PER_SHARE_KEYS + RATIO_KEYS

BANK_MODELLED = ("revenue", "net_cons", "minority", "earnings", "stockholders_equity",
                 "non_controlling_interest", "total_equity", "dividends_paid", "eps", "dps",
                 "bvps", "payout", "roe")
_BANK_REASONS = {
    ("interest_income", "interest_expense", "net_interest_income"):
        "Skenario laba bank tidak memodelkan aset produktif, imbal hasil dan biaya dana, "
        "sehingga pendapatan bunga, beban bunga dan pendapatan bunga bersih tidak diproyeksikan.",
    ("non_interest_income", "operating_expense", "provision", "operating_pnl",
     "non_operating_income_or_loss", "other_non_operating"):
        "Skenario laba bank menetapkan pendapatan dan margin laba bersih tanpa memecahnya "
        "menjadi pendapatan non-bunga, beban operasional, provisi dan PPOP.",
    ("earnings_before_tax", "tax"):
        "Skenario laba bank menetapkan margin laba bersih; laba sebelum pajak dan pajak tidak "
        "diturunkan agar tidak menambah asumsi yang tidak dipakai DDM.",
    ("gross_loan", "allowance_for_loans", "net_loan", "npl"):
        "Skenario laba bank tidak memodelkan penyaluran kredit, cadangan kerugian dan kredit "
        "bermasalah; kredit bruto, cadangan, kredit bersih dan NPL tidak diproyeksikan.",
    ("government_bonds", "securities", "non_loan_earning_assets", "total_assets"):
        "Skenario laba bank tidak memodelkan obligasi pemerintah, surat berharga dan aset "
        "produktif lain; total aset produktif dan total aset tidak diproyeksikan.",
    ("current_account", "savings_account", "time_deposit", "total_deposit",
     "other_interest_bearing_liabilities", "total_liabilities", "short_term_debt",
     "long_term_debt", "total_debt", "net_debt", "revolver"):
        "Skenario laba bank tidak memodelkan simpanan nasabah (giro, tabungan, deposito), "
        "pinjaman dan liabilitas lain; neraca pendanaan bank tidak diproyeksikan.",
    ("cash_and_equivalents", "cash_only", "cash_begin", "operating_cash_flow",
     "investing_cash_flow", "financing_cash_flow", "net_cash_flow", "free_cash_flow",
     "other_operating_cash_flow", "other_investing_cash_flow", "debt_raised",
     "equity_raised", "other_financing_cash_flow", "revolver_flow"):
        "Arus kas dan kas bank tidak diproyeksikan; DDM menilai dividen, bukan arus kas bebas.",
    ("ebitda", "ebit", "depreciation"):
        "EBITDA, EBIT dan D&A tidak bermakna untuk bank; skenario laba bank tidak memecah "
        "beban operasional menurut jenisnya.",
    ("capital_expenditure", "fcff", "change_in_working_capital", "working_capital"):
        "Capex, modal kerja dan FCFF tidak dipakai untuk institusi keuangan.",
    ("cost_of_revenue", "gross_profit", "interest_expense_non_operating", "trade_receivables",
     "trade_payables", "inventories", "current_assets", "current_liabilities", "fixed_assets",
     "non_current_liabilities", "other_current_assets", "other_non_current_assets",
     "other_current_liabilities", "other_non_current_liabilities", "interest_coverage"):
        "Pos laporan keuangan emiten non-keuangan; tidak berlaku untuk bank.",
    ("yield_on_earning_assets", "cost_of_funds", "net_interest_margin"):
        "Skenario laba bank tidak memodelkan aset produktif dan dana berbiaya, sehingga imbal "
        "hasil aset produktif, biaya dana dan NIM tidak diproyeksikan.",
    ("cost_to_income", "cost_of_credit", "npl_coverage"):
        "Skenario laba bank tidak memodelkan beban operasional, provisi dan kredit bermasalah, "
        "sehingga rasio biaya, biaya kredit dan cakupan cadangan tidak diproyeksikan.",
    ("loan_to_deposit_ratio", "casa_ratio", "capital_adequacy_ratio", "roaa"):
        "Skenario laba bank tidak memodelkan kredit, simpanan nasabah, aset tertimbang menurut "
        "risiko dan total aset, sehingga LDR, rasio CASA, CAR dan ROAA tidak diproyeksikan.",
}
BANK_KEYS = BANK_MODELLED + tuple(k for keys in _BANK_REASONS for k in keys)

# Bank Driver Scenario (app.bank_model): what the model leaves out, and why.
MODE_BANK_DRIVER = "bank: model driver bank (laba, neraca dan modal)"
_BANK_MODEL_REASONS = {
    ("npl", "npl_coverage"):
        "Model driver bank memakai biaya kredit sebagai driver kualitas aset; data Sectors tidak "
        "memuat kredit bermasalah, sehingga NPL dan cakupan cadangan terhadap NPL tidak "
        "diproyeksikan.",
    ("government_bonds", "securities"):
        "Model driver bank memproyeksikan aset produktif selain kredit sebagai satu pos "
        "penyeimbang pendanaan tanpa memecahnya menjadi obligasi pemerintah, surat berharga dan "
        "penempatan.",
    ("non_operating_income_or_loss", "other_non_operating"):
        "Pendapatan non-bunga model mencakup seluruh pendapatan di antara NII dan laba sebelum "
        "pajak (fee, premi bersih dan pos non-operasional), sehingga pos non-operasional tidak "
        "dipisahkan.",
    ("cash_and_equivalents", "cash_only", "cash_begin", "operating_cash_flow",
     "investing_cash_flow", "financing_cash_flow", "net_cash_flow", "free_cash_flow",
     "other_operating_cash_flow", "other_investing_cash_flow", "debt_raised",
     "equity_raised", "other_financing_cash_flow", "revolver_flow"):
        "Arus kas bank tidak diproyeksikan: DDM menilai dividen, dan kas termasuk aset "
        "non-produktif yang model driver bank jaga pada porsi historisnya terhadap total aset.",
    ("short_term_debt", "long_term_debt", "total_debt", "net_debt", "revolver"):
        "Pendanaan bank dimodelkan sebagai DPK, liabilitas berbunga lain dan liabilitas tanpa "
        "bunga; utang korporasi tidak dipisahkan.",
    ("ebitda", "ebit", "depreciation"):
        "EBITDA, EBIT dan D&A tidak bermakna untuk bank; model driver bank menurunkan beban "
        "operasional dari rasio biaya terhadap pendapatan tanpa memecahnya menurut jenis.",
    ("capital_expenditure", "fcff", "change_in_working_capital", "working_capital"):
        _BANK_REASONS[("capital_expenditure", "fcff", "change_in_working_capital",
                       "working_capital")],
    ("cost_of_revenue", "gross_profit", "interest_expense_non_operating", "trade_receivables",
     "trade_payables", "inventories", "current_assets", "current_liabilities", "fixed_assets",
     "non_current_liabilities", "other_current_assets", "other_non_current_assets",
     "other_current_liabilities", "other_non_current_liabilities", "interest_coverage"):
        "Pos laporan keuangan emiten non-keuangan; tidak berlaku untuk bank.",
}
# Row keys that are the model's internals, not statement lines.
_BANK_MODEL_INTERNAL = ("drivers", "average_earning_assets", "average_gross_loan", "tax_rate")

R_GROSS = ("Skenario analis menetapkan margin EBITDA, bukan margin laba kotor; memecah EBITDA "
           "menjadi beban pokok pendapatan dan beban usaha memerlukan asumsi margin kotor yang "
           "tidak dipakai valuasi dan tidak bersumber, sehingga tidak dimodelkan.")
R_INTEREST = ("Skenario laba tidak memisahkan beban bunga dari pos non-operasional lain; "
              "totalnya, yaitu laba sebelum pajak dikurangi EBIT yang implisit dari margin laba "
              "bersih skenario, tersaji sebagai pendapatan (beban) lain-lain bersih termasuk "
              "bunga.")
R_INTEREST_INCOME = ("Data Sectors tidak memuat pendapatan bunga emiten non-keuangan; "
                     "pendapatan bunga termasuk dalam pos non-operasional bersih.")
R_TRADE = ("Data Sectors tidak memisahkan piutang usaha dan utang usaha emiten non-keuangan; "
           "keduanya termasuk dalam aset lancar lain dan liabilitas lancar lain, yang bergerak "
           "dengan modal kerja.")
R_COVERAGE = ("Beban bunga tidak dipisahkan dalam skenario, sehingga cakupan bunga (EBIT "
              "dibagi beban bunga) tidak dapat dihitung.")


def _num(value):
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def _bn(value):
    return f"Rp{fmt._id(value / 1e9, 1)} miliar"


def _source(text):
    """A source phrase for a sentence: Indonesian decimals, no nested brackets."""
    text = re.sub(r"(\d)\.(\d+%)", r"\1,\2", str(text or "sumber tidak tercatat"))
    return text.replace("(", "").replace(")", "")


def _label(year):
    return f"FY{int(year) % 100:02d}F"


def _fx(intake):
    """Reporting currency to Rupiah, as ``report_extras.chart_forecast_rows``."""
    usd = (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
    fx = (intake.get("fx_spot") or {}).get("rate") if usd else 1.0
    return fx if _num(fx) and fx > 0 else None


def scenario_path(intake, fc):
    """The FY path the charts and Key Financials show, in Rupiah.

    Returns (basis, rows, anchor, fx, reason). Rows carry year, label,
    revenue, ebitda, net_cons (consolidated), earnings (attributable), capex
    and, for a production forecast, its own D&A. The same selection and
    conversion as ``report_extras.chart_forecast_rows`` but never truncated.
    """
    fc = fc or {}
    if fc.get("production_ready") is True and \
            fc.get("forecast_basis") != "physical_driver_forecast" and \
            (fc.get("earnings_scenario") or {}).get("basis") not in (
                "operating_driver_model", "bank_driver_scenario"):
        rows = [{"year": r.get("year"), "label": r.get("label") or _label(r["year"]),
                 "revenue": _num(r.get("revenue")), "ebitda": _num(r.get("ebitda")),
                 "net_cons": _num(r.get("net")),
                 "earnings": _num(r.get("net_attr", r.get("net"))),
                 "capex": _num(r.get("capex")), "da": _num(r.get("da"))}
                for r in fc.get("rows") or [] if r.get("year")]
        return "forecast produksi", rows, None, 1.0, None
    anchor = fc.get("earnings_scenario") or fc.get("interim_scenario")
    if not anchor:
        return None, [], None, None, (
            "Belum ada skenario analis tervalidasi atau forecast produksi; tahun forecast "
            "tidak diproyeksikan (forecast screening historis tidak dipakai di laporan).")
    fx = _fx(intake)
    if not fx:
        return None, [], anchor, None, (
            "Kurs USD/IDR bertanggal tidak tersedia; skenario dalam US$ tidak dapat "
            "dikonversi ke Rupiah.")
    idr = lambda v: None if _num(v) is None else v * fx
    full = anchor.get("full_year") or {}
    parent = full.get("net_profit_attributable")
    capex = full.get("capex") if full.get("capex") is not None else full.get(
        "capital_expenditure")
    rows = [{"year": anchor["year"], "label": _label(anchor["year"]),
             "revenue": idr(full.get("revenue")), "ebitda": idr(full.get("ebitda")),
             "net_cons": idr(full.get("net_profit")),
             "earnings": idr(parent if parent is not None else full.get("net_profit")),
             "capex": idr(capex)}]
    for r in (fc.get("outyear_scenario") or {}).get("rows") or []:
        rows.append({"year": r.get("year"), "label": r.get("label") or _label(r["year"]),
                     "revenue": idr(r.get("revenue")), "ebitda": idr(r.get("ebitda")),
                     "net_cons": idr(r.get("net_profit")),
                     "earnings": idr(r.get("net_profit_attributable")),
                     "capex": idr(r.get("capex"))})
    basis = ("model operasional" if anchor.get("basis") == "operating_driver_model"
             else "skenario analis")
    return basis, rows, anchor, fx, None


def parent_share(intake, anchor):
    """(share, basis) of consolidated profit attributable to the parent when the
    scenario carries no parent split (the mining interim anchor), else None.

    Key Financials takes the official prior-year ratio for EPS and PER, so the
    statements apply the same ratio to every forecast year.
    """
    if not anchor or (anchor.get("full_year") or {}).get("net_profit_attributable") is not None:
        return None
    evidence = intake.get("official_evidence") or {}
    year = anchor["year"] - 1
    prior = next((r for r in evidence.get("annual_actuals") or [] if r.get("year") == year), {})
    net, parent = _num(prior.get("net_profit")), _num(prior.get("net_profit_attributable"))
    if not net or parent is None:
        return None
    source = evidence.get("annual_source_title") or "laporan tahunan resmi"
    return parent / net, f"porsi induk FY{year} resmi, {source}"


def _complete(rows):
    """Consecutive years with revenue and both profit lines."""
    out = []
    for row in rows:
        if (any(row.get(k) is None for k in ("revenue", "net_cons", "earnings")) or
                (out and row["year"] != out[-1]["year"] + 1)):
            break
        out.append(row)
    return out


def _history(intake):
    report = cache.company_report(intake.get("ticker")) or {}
    rows = (report.get("financials") or {}).get("historical_financials") or []
    return sorted((r for r in rows if isinstance(r, dict) and r.get("year")),
                  key=lambda r: r["year"])


def _cash(row):
    """Cash as intake reads it: cash and equivalents, else due from banks, else cash only."""
    for key in ("cash_and_equivalents", "total_cash_and_due_from_banks", "cash_only"):
        if _num(row.get(key)) is not None:
            return row[key]
    return None


def _minimum_cash(history, base_year, cash0, cap_label=None):
    """(ratio, basis): the lowest cash-to-revenue ratio of the last three actual
    years; the floor each year is the lower of that ratio x revenue and the
    last actual cash (``cap_label`` names it when it is not the base year's),
    so it never exceeds cash the issuer actually held."""
    points = []
    for row in history:
        if row["year"] > base_year or row["year"] <= base_year - 3:
            continue
        cash, revenue = _cash(row), _num(row.get("revenue"))
        if cash is not None and revenue and revenue > 0:
            points.append((cash / revenue, row["year"]))
    if not points or cash0 is None or cash0 <= 0:
        return 0.0, "kas minimum nol (rasio kas historis tidak tersedia)"
    ratio, year = min(points)
    years = sorted(y for _, y in points)
    span = f"FY{years[0]}-FY{years[-1]}" if len(years) > 1 else f"FY{years[0]}"
    return ratio, (f"yang lebih rendah dari {cap_label or f'kas FY{base_year}'} {_bn(cash0)} dan "
                   f"rasio kas terhadap pendapatan terendah {span} ({fmt.pct(ratio)}, FY{year}) x "
                   "pendapatan tahun itu")


def _trace_detail(va, keys, need):
    for step in ((va or {}).get("method_chain") or {}).get("trace") or []:
        detail = step.get("detail") or {}
        if step.get("key") in keys and all(detail.get(k) is not None for k in need):
            return detail
    return None


def _native(value, currency):
    return (f"US${fmt._id(value / 1e6, 2)} juta" if currency == "USD"
            else f"Rp{fmt._id(value / 1e9, 1)} miliar")


def _earnings_quality_notes(intake, fc):
    """Sentences for the reviewed normalization and share ledger (plan §4.4)."""
    out = []
    currency = (intake.get("official_evidence") or {}).get("reporting_currency")
    scenario = (fc or {}).get("earnings_scenario") or {}
    norm = scenario.get("normalization") or {}
    label = _label(scenario["year"]) if scenario.get("year") else "FY1"
    if norm.get("status") == "assessed" and norm.get("adjustments"):
        items = "; ".join(f"{a['description']} {_native(a['effect'], currency)}"
                          for a in norm["adjustments"])
        out.append(
            f"Laba inti {label}: {_native(norm['normalized_attributable'], currency)} "
            f"(dilaporkan {_native(norm['reported_attributable'], currency)}); penyesuaian "
            f"satu kali {norm['period']} setelah pajak dan kepentingan nonpengendali: {items}. "
            "PER dan ROE valuasi memakai laba inti; laporan laba rugi tetap angka dilaporkan.")
    elif norm.get("status") == "assessed":
        out.append(f"Normalisasi laba {norm.get('period')}: tidak ada pos satu kali; laba inti "
                   f"{label} sama dengan laba dilaporkan.")
    elif norm:
        why = norm.get("note") or ("ledger normalisasi laba yang ditinjau belum tersedia"
                                   if norm.get("status") == "not_assessed"
                                   else "ledger normalisasi laba belum lolos pemeriksaan")
        out.append(f"Normalisasi laba {label} belum lengkap: {why.rstrip('.')}; PER dan ROE "
                   "memakai laba dilaporkan.")
    record = intake.get("share_basis") or {}
    weighted = record.get("fy_weighted_average") or {}
    if record.get("status") == "assessed" and weighted.get("shares"):
        basis = ("dari aksi korporasi bertanggal" if weighted.get("h1_basis") ==
                 "derived_from_dated_actions" else "memakai angka tertimbang 1H emiten")
        out.append(
            f"Jumlah saham tertimbang FY{weighted['year'] % 100:02d} (PSAK 56) "
            f"{fmt._id(weighted['shares'] / 1e9, 2)} miliar lembar, {basis}; dicatat untuk "
            "rekonsiliasi EPS tahunan emiten, sedangkan EPS model memakai jumlah saham pada "
            "tanggal laporan.")
    if weighted.get("h1_basis") == "derived_from_dated_actions" and weighted.get("issuer_reported"):
        out.append(
            f"Catatan register saham: rata-rata tertimbang {weighted['period']} yang dilaporkan "
            f"emiten ({fmt._id(weighted['issuer_reported'] / 1e9, 2)} miliar lembar) tidak "
            f"rekonsiliasi dengan register dan aksi korporasi bertanggal "
            f"({fmt._id(weighted['derived'] / 1e9, 2)} miliar lembar); angka turunan dipakai "
            "dan angka emiten ditandai untuk ditinjau.")
    return out


def _bridge(intake):
    try:
        return scenario_value.bridge(intake)
    except (KeyError, TypeError, ValueError, AttributeError):
        return {}


def _share_move(intake):
    """(moved, official shares, year-end shares): the valuation bridge's rule for a
    capital change since the fiscal year-end (rights issue, merger)."""
    balance = (intake.get("official_evidence") or {}).get("balance_sheet") or {}
    official = share_basis.report_date_shares(intake)[0] if balance else None
    annual = next((a for a in reversed(intake.get("annuals") or [])
                   if _num(a.get("total_debt")) is not None and _num(a.get("cash")) is not None),
                  None)
    year_shares = _num((annual or {}).get("shares")) or _num(intake.get("shares"))
    moved = bool(official and year_shares and
                 abs(official / year_shares - 1) > scenario_value.SHARE_CHANGE_LIMIT)
    return moved, official, year_shares


def _lom_schedule(va, fc, fx, path):
    """Per-year D&A and interest from the valued LoM when the out-years are its
    schedule, else None. FY anchor = 1H actual D&A + the schedule's H2."""
    if ((fc or {}).get("outyear_scenario") or {}).get("status") != "lom_schedule":
        return None
    detail = _trace_detail(va, ("sotp_lom",), ("lom",))
    lom = (detail or {}).get("lom") or {}
    inputs, base = lom.get("inputs") or {}, lom.get("base") or {}
    if not inputs or not base.get("flows") or not _num(inputs.get("da_usd")):
        return None
    by_year = {}
    for flow in base["flows"]:
        by_year[flow["year"]] = by_year.get(flow["year"], 0.0) + (flow.get("da") or 0.0)
    da = []
    for i, row in enumerate(path):
        value = by_year.get(row["year"])
        if value is None:
            return None
        da.append((value + (inputs["da_usd"] / 2 if i == 0 else 0.0)) * fx)
    tax, ntgr = _num(inputs.get("tax_rate")), _num(inputs.get("ntgr_rate"))
    if tax is None or ntgr is None:
        return None
    return {"da": da, "tax": tax, "ntgr": ntgr, "inputs": inputs}


def _lom_interest(intake, fx):
    """Twice the 1H finance cost, as ``lom.forward_rows`` deducts it."""
    actual = (intake.get("official_evidence") or {}).get("latest_actual") or {}
    income = ((actual.get("financial_statements_usd_thousand") or {})
              .get("income_statement") or {})
    cost = _num(income.get("finance_costs"))
    return abs(cost) * 1000 * 2 * fx if cost is not None else None


def _official_interest(intake, fx):
    """(annual interest, period): the official interim finance cost annualised
    (2x for 1H), flat, in the rows' currency; (None, None) when the release
    does not report it."""
    actual = (intake.get("latest_official_actual") or
              (intake.get("official_evidence") or {}).get("latest_actual") or {})
    metrics = actual.get("metrics") or {}
    cost = next((_num(metrics[k]) for k in ("finance_cost", "finance_costs")
                 if _num(metrics.get(k)) is not None), None)
    months = scenario_value._period_months(actual.get("period"))
    if not cost or not months or not fx:
        return None, None
    return abs(cost) * 12 / months * fx, actual.get("period") or "interim"


def _official_interest_income(intake, fx):
    """The official interim finance income annualised, flat, like
    ``_official_interest``; None when the release does not report it."""
    actual = (intake.get("latest_official_actual") or
              (intake.get("official_evidence") or {}).get("latest_actual") or {})
    metrics = actual.get("metrics") or {}
    income = next((_num(metrics[k]) for k in ("finance_income", "interest_income")
                   if _num(metrics.get(k)) is not None), None)
    months = scenario_value._period_months(actual.get("period"))
    if income is None or income < 0 or not months or not fx:
        return None
    return income * 12 / months * fx


# Official interim lines the interim opening needs (reporting currency).
_INTERIM_BALANCE = ("cash", "current_assets", "fixed_assets", "total_assets",
                    "current_liabilities", "total_liabilities", "short_term_debt",
                    "long_term_debt", "total_equity", "non_controlling_interest")
_INTERIM_FLOWS = ("cash_begin", "operating_cash_flow", "capital_expenditure",
                  "investing_cash_flow", "debt_raised", "dividends_paid", "equity_raised",
                  "other_financing_cash_flow", "financing_cash_flow", "net_cash_flow")


def _interim_opening(intake, anchor, fx):
    """The official 1H balance sheet and cash flow the first forecast year opens
    from, in Rupiah, else None.

    Needs the full interim balance sheet (cash, current and fixed assets,
    current liabilities, short- and long-term debt, equity and minorities, and
    balancing), the interim cash flow that ties opening to closing cash, the
    interim D&A, and a 1H + H2 earnings scenario of the same year.
    """
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    actual = (intake.get("latest_official_actual") or evidence.get("latest_actual") or {})
    flows = actual.get("cash_flow") or {}
    metrics = actual.get("metrics") or {}
    h2 = (anchor or {}).get("h2") or {}
    period_end = str(balance.get("period_end") or "")
    if (not fx or not anchor or scenario_value._period_months(actual.get("period")) != 6
            or period_end != str(actual.get("period_end") or "")
            or period_end[:4] != str(anchor.get("year"))
            or _num(h2.get("revenue")) is None or _num(h2.get("net_profit")) is None
            or _num(metrics.get("depreciation")) is None
            or any(_num(balance.get(k)) is None for k in _INTERIM_BALANCE)
            or any(_num(flows.get(k)) is None for k in _INTERIM_FLOWS)):
        return None
    b = {k: _num(v) for k, v in balance.items() if _num(v) is not None}
    f = {k: _num(v) for k, v in flows.items() if _num(v) is not None}
    scale = max(abs(b["total_assets"]), 1.0)
    if (not release_policy.forecast_statement_identity_matches(
            b["total_assets"], b["total_liabilities"] + b["total_equity"], scale)
            or not release_policy.forecast_statement_identity_matches(
                f["cash_begin"] + f["net_cash_flow"], b["cash"], scale)
            or not release_policy.forecast_statement_identity_matches(
                f["operating_cash_flow"] + f["investing_cash_flow"]
                + f["financing_cash_flow"], f["net_cash_flow"], scale)):
        return None
    inv = b.get("inventories", 0.0)
    receivables = b.get("trade_receivables", 0.0)
    payables = b.get("trade_payables", 0.0)
    out = {k: v * fx for k, v in b.items()}
    out.update(
        inventories=inv * fx, trade_receivables=receivables * fx, trade_payables=payables * fx,
        other_current_assets=(b["current_assets"] - b["cash"] - inv - receivables) * fx,
        other_current_liabilities=(b["current_liabilities"] - b["short_term_debt"]
                                   - payables) * fx,
        other_non_current_assets=(b["total_assets"] - b["current_assets"]
                                  - b["fixed_assets"]) * fx,
        other_non_current_liabilities=(b["total_liabilities"] - b["current_liabilities"]
                                       - b["long_term_debt"]) * fx,
        period_end=period_end, period=actual.get("period"),
        shares=share_basis.report_date_shares(intake)[0],
        source=balance.get("source_title") or actual.get("source_title"),
        has_receivables="trade_receivables" in b, has_payables="trade_payables" in b,
        has_inventories="inventories" in b,
        net_cons_1h=_num(metrics.get("net_profit")) * fx
        if _num(metrics.get("net_profit")) is not None else None,
        da_1h=metrics["depreciation"] * fx,
        flows={k: v * fx for k, v in f.items()}, flow_pages=flows.get("pages"))
    out["flows"]["other_investing_cash_flow"] = (f["investing_cash_flow"]
                                                 + f["capital_expenditure"]) * fx
    return out if out["net_cons_1h"] is not None else None


def _official_usd_base(intake, base, fx):
    """(base, note): a US$ reporter's Sectors base-year row restated to its
    official US$ closing equity at the rows' spot rate, else (base, None).

    Sectors converts a US$ reporter's statements to rupiah at its own rate;
    that rate is read off the base year's total equity against the official
    release, and every amount of the row moves from it to the spot rate, so
    the balance sheet still balances and the opening equity is the official
    figure. Parent profit of the base year is the release's own.
    """
    evidence = intake.get("official_evidence") or {}
    if evidence.get("reporting_currency") != "USD" or not base or not fx or fx == 1.0:
        return base, None
    official = next((r for r in evidence.get("annual_actuals") or []
                     if r.get("year") == base["year"]), None) or {}
    equity_usd, sectors_equity = _num(official.get("equity")), _num(base.get("total_equity"))
    if not equity_usd or not sectors_equity or equity_usd <= 0 or sectors_equity <= 0:
        return base, None
    rate = sectors_equity / equity_usd
    if not 0.5 < rate / fx < 1.5:  # not the same balance sheet
        return base, None
    factor = fx / rate
    out = {k: (v * factor if _num(v) is not None and k not in ("year", "outstanding_shares")
               else v) for k, v in base.items()}
    out["total_equity"] = equity_usd * fx
    parent = _num(official.get("net_profit_attributable"))
    if parent is not None:
        out["earnings"] = parent * fx
    parent_equity = _num(official.get("equity_attributable"))
    source = evidence.get("annual_source_title") or "rilis tahunan resmi"
    note = (f"neraca awal FY{base['year']} dari ekuitas US${fmt._id(equity_usd / 1e6, 1)} juta "
            f"({source}); pos neraca lain data Sectors dinyatakan ulang dari kurs Sectors "
            f"Rp{fmt._id(rate, 0)}/US$ (tersirat dari ekuitas) ke kurs yang sama")
    nci = (equity_usd - parent_equity) * fx if parent_equity is not None else None
    return out, {"note": note, "nci": nci,
                 "nci_basis": f"nilai buku FY{base['year']}, {source}" if nci is not None else None}




def _scenario_sentence(basis, span, period, path, lom, bank):
    if basis == "forecast produksi":
        return (f"Forecast produksi: pendapatan, EBITDA, D&A, capex dan laba {span} dari forecast "
                "driver yang direkonsiliasi; angka yang sama dipakai Key Financials dan valuasi.")
    if len(path) == 1:
        outyears = "tanpa tahun lanjutan tervalidasi"
    elif lom:
        outyears = (f"{len(path) - 1} tahun lanjutan dari jadwal LoM yang dinilai (pendapatan, "
                    "EBITDA, capex, D&A, bunga, pajak dan PNBP)")
    elif bank:
        outyears = (f"{len(path) - 1} tahun lanjutan tervalidasi (pertumbuhan pendapatan dan "
                    "margin laba bersih)")
    else:
        outyears = (f"{len(path) - 1} tahun lanjutan tervalidasi (pertumbuhan pendapatan, margin "
                    "EBITDA, margin laba bersih dan intensitas capex)")
    lines = "pendapatan dan laba" if bank else "pendapatan, EBITDA, capex dan laba"
    return (f"Skenario analis: {span} dari aktual {period} resmi ditambah asumsi H2 dan "
            f"{outyears}; {lines} yang sama dipakai Key Financials dan valuasi.")


def forecast_rows(intake: dict, fc: dict | None, va: dict | None = None,
                  horizon: int = 5) -> dict:
    """Five forecast years shaped like Sectors historical_financials rows.

    Returns {"rows": [...], "notes": {key: reason}, "assumptions": [...],
    "basis": "skenario analis" | "forecast produksi" | None, "mode": ...,
    "base_year": last actual year the balance sheet rolls from}. Rows are
    empty without a validated scenario or production forecast. A key absent
    from every row, or None in some rows, has its reason in ``notes``.
    """
    intake = intake or {}
    profile = intake.get("model_profile")
    bank = profile == "financial_ddm"
    mining = profile == "finite_life_mining"
    model = (fc or {}).get("bank_model") if bank else None
    if isinstance(model, dict) and model.get("rows"):
        return _bank_model_rows(intake, fc, model, horizon)
    universe = BANK_KEYS if bank else NON_FINANCIAL_KEYS
    basis, path, anchor, fx, reason = scenario_path(intake, fc)
    path = _complete(path)[:max(int(horizon or 0), 0)]
    if not path:
        why = reason or ("Skenario tidak memuat pendapatan dan laba untuk tahun forecast "
                         "pertama; tahun forecast tidak diproyeksikan.")
        return {"rows": [], "notes": {k: why for k in universe}, "assumptions": [],
                "basis": None, "mode": None, "base_year": None}

    first, last = path[0], path[-1]
    span = f"{first['label']}-{last['label']}" if len(path) > 1 else first["label"]
    period = (intake.get("latest_official_actual") or {}).get("period") or "interim"
    lom = _lom_schedule(va, fc, fx, path) if mining else None
    assumptions = [_scenario_sentence(basis, span, period, path, lom, bank)]
    history = _history(intake)
    base = next((r for r in history if r["year"] == first["year"] - 1), None)
    base_year = base["year"] if base else None
    base, usd_base = _official_usd_base(intake, base, fx)
    if fx and fx != 1.0:
        spot = intake.get("fx_spot") or {}
        assumptions.append(
            f"Skenario dalam US$ dikonversi ke Rupiah pada kurs Rp{fmt._id(fx, 0)}/US$ "
            f"({spot.get('date') or 'tanggal kurs tidak tercatat'}), sama dengan Key Financials, "
            "grafik dan DCF US$; "
            + (f"{usd_base['note']}." if usd_base else
               "neraca awal dari data Sectors dalam Rupiah (rilis tahunan resmi US$ tanpa "
               "ekuitas tahun dasar)."))

    # --- share count and payout: the valuation's own
    dcf = None if bank else _trace_detail(va, ("fcff_dcf", "dcf_reference"),
                                          ("lines", "da_ratio", "tax_rate"))
    ddm = _trace_detail(va, ("ddm",), ("lines", "payout")) if bank else None
    link = _bridge(intake)
    shares, shares_basis = None, None
    for source in (dcf, ddm, link):
        if source and _num(source.get("shares")):
            shares, shares_basis = source["shares"], source.get("shares_basis")
            break
    if shares is None and _num(intake.get("shares")):
        shares, shares_basis = intake["shares"], "data Sectors"
    if shares:
        assumptions.append(
            f"Asumsi valuasi: jumlah saham {fmt._id(shares / 1e9, 2)} miliar lembar, sumber "
            f"{_source(shares_basis)}, flat; EPS memakai laba induk dan BVPS ekuitas induk atas "
            "jumlah saham yang sama dengan valuasi dan PER.")
    assumptions.extend(_earnings_quality_notes(intake, fc))
    payout = _num((ddm or {}).get("payout"))
    payout_basis = (ddm or {}).get("payout_basis")
    if payout is None:
        payout, payout_basis = _num(intake.get("payout")), intake.get("payout_basis")
    payout_basis = payout_basis or "sumber tidak tercatat"
    payout_sourced = payout is not None and not payout_basis.startswith("asumsi analis")
    share_parent = (anchor or {}).get("attributable_share") or 1.0
    attributable_basis = (anchor or {}).get("attributable_basis") or (
        "laba konsolidasi; porsi induk tidak dilaporkan terpisah")
    official_parent = parent_share(intake, anchor)
    if official_parent:
        # No parent split in the scenario: the official prior-year ratio, as
        # Key Financials applies it to EPS and PER.
        share_parent, attributable_basis = official_parent
        for row in path:
            row["earnings"] = row["net_cons"] * share_parent

    moved, official_shares, year_shares = _share_move(intake)
    balance = (intake.get("official_evidence") or {}).get("balance_sheet") or {}
    has_ebitda = all(r.get("ebitda") is not None for r in path)
    has_capex = all(r.get("capex") is not None for r in path)

    # --- operating drivers (non-financial): the valuation's values
    da_list, tax, interest, dnwc_list, interest_income = None, None, None, None, None
    interest_period = None
    da_reason, nwc_sentence = None, None
    if not bank:
        if lom:
            da_list = lom["da"]
            tax = 1 - (1 - lom["tax"]) * (1 - lom["ntgr"])
            tax_basis = (f"PPh {fmt.pct(lom['tax'])} dan PNBP {fmt.pct(lom['ntgr'])} efektif "
                         f"{period} resmi, digabung")
            interest = _lom_interest(intake, fx)
            assumptions.append(
                "Jadwal LoM: D&A per tahun dari jadwal tambang yang dinilai "
                f"({first['label']} = D&A {period} resmi + D&A H2 jadwal LoM).")
        elif basis == "forecast produksi" and all(r.get("da") is not None for r in path):
            da_list = [r["da"] for r in path]
            assumptions.append("Forecast produksi: D&A per tahun dari forecast yang sama.")
        elif (dcf or {}).get("operating_model") and len((dcf or {}).get("lines") or []) == len(path):
            # The operating model's own D&A, the lines the DCF values.
            da_list = [line["da"] for line in dcf["lines"]]
            assumptions.append("Model operasional: D&A per tahun = tarif penyusutan x aset tetap "
                               "neto awal, sama dengan DCF.")
        else:
            da_ratio = _num((dcf or {}).get("da_ratio"))
            da_basis = (dcf or {}).get("da_basis")
            if da_ratio is None:
                da_ratio, da_basis = scenario_value.da_intensity(intake)
            if da_ratio is not None:
                da_list = [r["revenue"] * da_ratio for r in path]
                assumptions.append(
                    f"Asumsi screening: D&A {fmt.pct(da_ratio)} dari pendapatan, sumber "
                    f"{_source(da_basis)}; sama dengan DCF skenario.")
            else:
                da_reason = (
                    f"{da_basis} (aturan yang sama dengan DCF skenario); tanpa penyusutan "
                    "bersumber, EBIT, aset tetap, kas dan arus kas operasi tidak dihitung agar "
                    "tidak mengarang angka.")
        if interest is None and not lom:
            interest, interest_period = _official_interest(intake, fx)
        interest_income = _official_interest_income(intake, fx) if not lom else None
        if tax is None:
            tax = _num((dcf or {}).get("tax_rate"))
            tax_basis = (dcf or {}).get("tax_basis")
            if tax is None:
                tax, tax_basis = scenario_value.tax_rate(intake)
        assumptions.append(
            ("Jadwal LoM" if lom else "Model operasional" if (dcf or {}).get("operating_model")
             else "Asumsi screening") +
            f": tarif pajak efektif {fmt.pct(tax)}, sumber {_source(tax_basis)}; sama dengan "
            "valuasi. Laba sebelum pajak = laba bersih konsolidasi skenario / (1 - tarif); "
            "pajak = selisihnya.")
        if mining:
            # The LoM (and the mining last step) do not model working capital.
            dnwc_list = [0.0] * len(path)
            nwc_sentence = (
                "Asumsi valuasi: jadwal LoM dan metode tambang tidak memodelkan perubahan modal "
                "kerja (persediaan dinilai terpisah di SOTP); modal kerja non-kas dijaga pada "
                f"saldo FY{base_year or first['year'] - 1}.")
        elif (dcf or {}).get("operating_model") and len((dcf or {}).get("lines") or []) == len(path):
            dnwc_list = [line["dnwc"] for line in dcf["lines"]]
            nwc_sentence = ("Model operasional: kenaikan modal kerja dari hari piutang atas "
                            "pendapatan serta hari persediaan dan utang usaha atas biaya variabel, "
                            "sama dengan DCF.")
        else:
            nwc_ratio = _num((dcf or {}).get("nwc_ratio"))
            nwc_basis = (dcf or {}).get("nwc_basis")
            if nwc_ratio is None:
                nwc_ratio, nwc_basis = scenario_value.nwc_intensity(intake)
            # The DCF's own base: official US$ revenue for a US$ reporter.
            prior = scenario_value.prior_revenue(intake, first["year"] - 1)
            previous = prior * fx if prior is not None and fx else None
            dnwc_list = []
            for row in path:
                dnwc_list.append(nwc_ratio * (row["revenue"] - previous) if previous else 0.0)
                previous = row["revenue"]
            nwc_sentence = (
                f"Asumsi screening: modal kerja non-kas {fmt.pct(nwc_ratio)} dari pendapatan, "
                f"sumber {_source(nwc_basis)}; kenaikan modal kerja = intensitas x kenaikan "
                "pendapatan, sama dengan DCF skenario; persediaan, aset lancar lain dan "
                "liabilitas lancar non-utang bergerak proporsional.")
            if nwc_ratio == 0 and any(term in str(nwc_basis or "").lower()
                                      for term in ("negatif", "tidak tersedia")):
                nwc_sentence += (
                    " Basis historis negatif atau tidak tersedia tidak membuktikan kebutuhan "
                    "modal kerja masa depan tetap nol; arus kas bebas dapat lebih rendah jika "
                    "pertumbuhan operasi memerlukan modal kerja positif.")
    income_ok = da_list is not None and has_ebitda
    fcff_ok = income_ok and has_capex and dnwc_list is not None
    if income_ok:
        assumptions.append(
            "Mekanika model: EBIT = EBITDA skenario - D&A; pos non-operasional bersih (beban "
            "bunga dan lain-lain bersih) = laba sebelum pajak - EBIT, implisit dari margin laba "
            "bersih skenario, bukan asumsi terpisah"
            + ("; beban bunga = 2x beban keuangan 1H resmi, sama dengan jadwal LoM"
               if interest is not None and lom else
               f"; beban bunga = beban keuangan {interest_period} resmi disetahunkan, flat, "
               "dipisahkan dari pos non-operasional lain tanpa mengubah laba sebelum pajak"
               if interest is not None else "")
            + (f"; pendapatan bunga = penghasilan keuangan {period} resmi disetahunkan, flat "
               f"({_bn(interest_income)} per tahun), dipisahkan dengan cara yang sama"
               if interest_income is not None else "") + ".")

    # --- which statements can be built
    needs_bs = ("total_assets", "total_liabilities", "total_equity", "current_assets",
                "current_liabilities", "fixed_assets")
    bs_complete = (base is not None and _cash(base) is not None and
                   all(_num(base.get(k)) is not None for k in needs_bs))
    # Interim opening: the official 1H balance sheet and cash flow, with the
    # first year's H2 flows (FY scenario less the official 1H actual).
    interim = (None if bank or not fcff_ok or payout is None
               else _interim_opening(intake, anchor, fx))
    if interim:
        h2 = anchor["h2"]
        interim["h2_cons"] = h2["net_profit"] * fx
        interim["h2_share"] = (h2["revenue"] * fx / first["revenue"]
                               if first["revenue"] else 0.5)
        interim["da_h2"] = da_list[0] - interim["da_1h"]
        interim["capex_1h"] = abs(interim["flows"]["capital_expenditure"])
        interim["capex_h2"] = first["capex"] - interim["capex_1h"]
        interim["dnwc_h2"] = dnwc_list[0] * interim["h2_share"]
        short = [name for name, key in (("D&A", "da_h2"), ("capex", "capex_h2"))
                 if interim[key] < 0]
        if short:
            assumptions.append(
                f"Mekanika model: neraca interim resmi {interim['period_end']} tidak dipakai "
                f"sebagai neraca awal karena {' dan '.join(short)} FY skenario lebih kecil dari "
                f"{period} resmi, sehingga arus H2 akan negatif.")
            interim = None
    full = (not bank and fcff_ok and payout is not None and
            (interim is not None or (not moved and bs_complete)))
    mode = (MODE_BANK if bank else MODE_INTERIM if full and interim else
            MODE_FULL if full else MODE_EQUITY)
    if fcff_ok and nwc_sentence:
        assumptions.append(nwc_sentence)

    # --- opening equity: the last fiscal year, or the latest official interim
    # balance sheet when the share count moved since (the year-end equity
    # does not hold the capital raised).
    official_equity = _num(balance.get("total_equity"))
    if official_equity is None and _num(balance.get("equity_attributable")) is not None:
        official_equity = balance["equity_attributable"] + (
            _num(balance.get("non_controlling_interest")) or 0.0)
    official_fx = _fx(intake)
    opening, equity_reason, moved_text = None, None, None
    h2_net = _num(((anchor or {}).get("h2") or {}).get("net_profit"))
    if moved:
        moved_text = (f"jumlah saham berubah {fmt.pct(official_shares / year_shares - 1)} sejak "
                      f"akhir FY{first['year'] - 1} (aksi korporasi); neraca akhir tahun tidak "
                      "lagi mewakili dan skenario tidak memuat arus dana aksi korporasi")
    if payout is None:
        equity_reason = ("Payout tidak tersedia di data Sectors maupun asumsi forecast, "
                         "sehingga dividen dan ekuitas tidak dapat diproyeksikan.")
    elif interim:
        opening = {"equity": interim["total_equity"], "when": interim["period_end"],
                   "interim": True}
    elif moved and official_equity is not None and official_fx and h2_net is not None:
        opening = {"equity": official_equity * official_fx,
                   "when": balance.get("period_end"), "interim": True}
    elif moved:
        equity_reason = (f"Mekanika model: {moved_text}, dan neraca interim resmi (ekuitas) atau "
                         "laba H2 skenario tidak tersedia; ekuitas tidak diproyeksikan.")
    elif base is not None and _num(base.get("total_equity")) is not None:
        opening = {"equity": base["total_equity"], "when": f"FY{base['year']}",
                   "interim": False}
    else:
        equity_reason = (f"Neraca aktual FY{first['year'] - 1} tidak tersedia di data Sectors; "
                         "ekuitas tidak dapat di-roll-forward.")

    nci0, nci_basis = _num(link.get("nci")), link.get("nci_basis")
    if usd_base and usd_base.get("nci") is not None and opening and not opening["interim"]:
        nci0, nci_basis = usd_base["nci"], usd_base["nci_basis"]
    if nci0 is None and _num(balance.get("non_controlling_interest")) is not None and official_fx:
        nci0 = balance["non_controlling_interest"] * official_fx
        nci_basis = f"nilai buku, neraca interim resmi {balance.get('period_end')}"
    if interim:
        nci0 = interim["non_controlling_interest"]
        nci_basis = f"nilai buku, neraca interim resmi {interim['period_end']}"
    if nci0 is None:
        nci0, nci_basis = 0.0, "tidak dilaporkan terpisah; ekuitas induk = total ekuitas"
    prior_earnings = _num((base or {}).get("earnings"))
    if interim:
        # The prior year's final dividend follows the AGM: when the interim cash
        # flow shows it paid, H2 pays nothing more (interim dividends are not
        # modelled); otherwise it is still due in H2.
        paid_1h = interim["flows"]["dividends_paid"]
        if paid_1h > 0:
            interim["div_h2"] = 0.0
            interim["div_text"] = (
                f"{first['label']}: dividen final FY{first['year'] - 1} {_bn(paid_1h)} sudah "
                f"dibayar pada {period} (arus kas resmi) dan tercermin di ekuitas neraca interim "
                f"{interim['period_end']}; dividen H2 nol karena dividen interim tidak dimodelkan")
        else:
            interim["div_h2"] = payout * max(prior_earnings or 0.0, 0.0)
            interim["div_text"] = (
                f"{first['label']}: arus kas {period} resmi tidak mencatat dividen, sehingga "
                f"dividen final FY{first['year'] - 1} = payout x laba induk FY"
                f"{first['year'] - 1} dibayar pada H2")
    if opening:
        assumptions.append(
            f"Skenario analis: porsi laba pemilik induk {fmt.pct(share_parent)}, sumber "
            f"{_source(attributable_basis)}; laba non-pengendali menambah ekuitas NCI dengan "
            f"saldo awal {_bn(nci0)}, sumber {_source(nci_basis)}; dividen ke NCI tidak "
            "dimodelkan.")
        if interim:
            timing = interim["div_text"]
        elif opening["interim"]:
            timing = (f"{first['label']}: dividen tahun berjalan sudah tercermin di ekuitas "
                      f"neraca interim {opening['when']}")
        elif prior_earnings is not None:
            timing = (f"{first['label']} memakai laba FY{base_year} aktual "
                      + ("rilis tahunan resmi US$" if usd_base else "data Sectors"))
        else:
            timing = (f"{first['label']} memakai laba tahun yang sama karena laba FY sebelumnya "
                      "tidak tersedia")
        if payout_sourced:
            assumptions.append(
                f"Asumsi screening: payout {fmt.pct(payout)}, sumber {_source(payout_basis)}, "
                "flat; DPS tahun t = payout x EPS tahun t (baris DPS DDM); dividen tunai yang "
                "dibayar tahun t = payout x laba induk tahun t-1 karena dividen final dibagi "
                f"sesudah RUPS; {timing}.")
        else:
            assumptions.append(
                f"Asumsi analis tanpa sumber: payout {fmt.pct(payout)}, {_source(payout_basis)}, "
                "hanya dipakai untuk roll-forward kas dan ekuitas, sama dengan forecast "
                f"screening; dividen tunai tahun t = payout x laba induk tahun t-1; {timing}. "
                "DPS dan payout tidak ditampilkan karena payout historis tidak tersedia "
                "di data Sectors.")
        if interim:
            assumptions.append(
                "Mekanika model: "
                + (f"jumlah saham berubah {fmt.pct(official_shares / year_shares - 1)} sejak "
                   f"akhir FY{first['year'] - 1}; perubahan modal itu sudah masuk neraca dan arus "
                   f"kas {period} resmi, sehingga " if moved else "")
                + f"ekuitas {first['label']} = ekuitas neraca interim resmi {opening['when']} "
                f"sebesar {_bn(opening['equity'])} + laba bersih konsolidasi H2 skenario "
                f"{_bn(interim['h2_cons'])} - dividen H2; tahun berikutnya = ekuitas awal + laba "
                "bersih konsolidasi - dividen; tanpa penerbitan atau pembelian kembali saham "
                "sesudah neraca interim.")
        elif opening["interim"]:
            assumptions.append(
                f"Mekanika model: {moved_text}, sehingga ekuitas {first['label']} = ekuitas "
                f"neraca interim resmi {opening['when']} sebesar {_bn(opening['equity'])} + laba "
                "H2 skenario; tahun berikutnya = ekuitas awal + laba bersih konsolidasi - "
                "dividen.")
        else:
            assumptions.append(
                f"Mekanika model: ekuitas = saldo FY{base_year} "
                + ("rilis tahunan resmi US$" if usd_base else "data Sectors")
                + " + laba bersih konsolidasi - dividen; tanpa penerbitan atau pembelian kembali "
                "saham.")

    # --- balance-sheet opening (full statements only)
    rec0 = pay0 = 0.0
    if full and interim:
        cash0, fa0 = interim["cash"], interim["fixed_assets"]
        std0, ltd0 = interim["short_term_debt"], interim["long_term_debt"]
        inv_known = interim["has_inventories"]
        inv0, rec0, pay0 = (interim["inventories"], interim["trade_receivables"],
                            interim["trade_payables"])
        oca0, ocl0 = interim["other_current_assets"], interim["other_current_liabilities"]
        onca0, oncl0 = interim["other_non_current_assets"], interim["other_non_current_liabilities"]
        nwc0 = rec0 + inv0 + oca0 - pay0 - ocl0
        when, flows = interim["period_end"], interim["flows"]
        # Interim cash can still hold unspent proceeds of a share or bond issue:
        # the floor is capped at the lower of it and the last fiscal year-end cash.
        year_cash = _cash(base) if base else None
        cash_cap = min(cash0, year_cash) if year_cash is not None and year_cash > 0 else cash0
        cash_ratio, cash_floor_basis = _minimum_cash(
            history, first["year"] - 1, cash_cap,
            f"kas neraca interim {when}" if cash_cap == cash0 else
            f"kas FY{first['year'] - 1} (kas neraca interim {when} {_bn(cash0)} masih memuat "
            "dana aksi korporasi atau penerbitan utang yang belum terpakai)")
        residual = flows["operating_cash_flow"] - interim["net_cons_1h"] - interim["da_1h"]
        later = path[1]["label"] if len(path) > 1 else "tahun berikutnya"
        assumptions.append(
            f"Mekanika model (neraca awal interim): neraca {first['label']} bergulir dari neraca "
            f"konsolidasian resmi {when} ({_source(interim['source'])}) dengan arus H2 saja: laba "
            f"bersih konsolidasi H2 skenario {_bn(interim['h2_cons'])}, D&A H2 "
            f"{_bn(interim['da_h2'])} (D&A FY {_bn(da_list[0])} - D&A {period} resmi "
            f"{_bn(interim['da_1h'])}), capex H2 {_bn(interim['capex_h2'])} (capex FY skenario "
            f"{_bn(first['capex'])} - capex {period} resmi {_bn(interim['capex_1h'])}), kenaikan "
            f"modal kerja H2 {_bn(interim['dnwc_h2'])} (kenaikan FY x porsi pendapatan H2 "
            f"{fmt.pct(interim['h2_share'])}) dan dividen H2 {_bn(interim['div_h2'])}; {later} "
            f"dan seterusnya bergulir dari neraca akhir {first['label']}.")
        assumptions.append(
            f"Mekanika model: arus kas {first['label']} = arus kas {period} aktual resmi"
            + (f" ({_source(interim['flow_pages'])})" if interim.get("flow_pages") else "")
            + f" + arus kas H2 model, dari kas awal FY{first['year'] - 1} "
            f"{_bn(flows['cash_begin'])}; arus kas operasi {period} resmi "
            f"{_bn(flows['operating_cash_flow'])}, selisihnya terhadap laba + D&A {period} "
            f"({_bn(residual)}) tersaji sebagai pos operasi lainnya; pos investasi lainnya "
            f"({_bn(flows['other_investing_cash_flow'])}), penarikan (pembayaran) utang "
            f"({_bn(flows['debt_raised'])}), penerbitan saham ({_bn(flows['equity_raised'])}) dan "
            f"pos pendanaan lainnya ({_bn(flows['other_financing_cash_flow'])}) {period} adalah "
            "angka aktual.")
        assumptions.append(
            f"Asumsi screening: utang awal flat pada saldo neraca interim resmi {when} (jangka "
            f"pendek {_bn(std0)}, jangka panjang {_bn(ltd0)}); tanpa jadwal pelunasan atau "
            "penarikan bersumber, utang yang jatuh tempo dianggap dibiayai kembali.")
        assumptions.append(
            f"Asumsi screening: aset tidak lancar lain {_bn(onca0)} dan liabilitas tidak lancar "
            f"non-utang {_bn(oncl0)} flat pada saldo {when}; sesudah {period} arus kas investasi "
            "hanya capex dan arus kas pendanaan hanya dividen dan utang jangka pendek "
            "penyeimbang kas, tanpa penerbitan saham.")
        assumptions.append(
            f"Skenario analis: capex per tahun dari skenario; aset tetap = saldo {when} "
            f"{_bn(fa0)} + capex H2 - D&A H2, lalu + capex - D&A per tahun.")
        assumptions.append(
            f"Mekanika model: kas akhir {first['label']} = kas neraca interim {when} "
            f"{_bn(cash0)} + arus kas bersih H2, sesudahnya kas awal + arus kas bersih, bukan "
            "penyeimbang; arus kas operasi = laba induk + D&A - kenaikan modal kerja + laba "
            "non-pengendali; neraca seimbang karena setiap pos bergerak lewat laba rugi atau "
            "arus kas.")
    elif full:
        cash0 = _cash(base)
        std0 = _num(base.get("short_term_debt")) or 0.0
        ltd0 = _num(base.get("long_term_debt"))
        if ltd0 is None:
            ltd0 = max((_num(base.get("total_debt")) or 0.0) - std0, 0.0)
        inv_known = _num(base.get("inventories")) is not None
        inv0 = base["inventories"] if inv_known else 0.0
        ca0, cl0, fa0 = base["current_assets"], base["current_liabilities"], base["fixed_assets"]
        ta0, te0 = base["total_assets"], base["total_equity"]
        oca0 = ca0 - cash0 - inv0
        ocl0 = cl0 - std0
        onca0 = ta0 - ca0 - fa0
        # Sectors balance sheets balance; a residual stays in other
        # non-current liabilities so the opening totals agree.
        oncl0 = ta0 - te0 - cl0 - ltd0
        gap = ta0 - te0 - base["total_liabilities"]
        nwc0 = oca0 + inv0 - ocl0
        cash_cap = cash0
        cash_ratio, cash_floor_basis = _minimum_cash(history, base_year, cash0)
        assumptions.append(
            f"Asumsi screening: utang awal flat pada saldo FY{base_year} data Sectors (jangka "
            f"pendek {_bn(std0)}, jangka panjang {_bn(ltd0)}); tanpa jadwal pelunasan atau "
            "penarikan bersumber, sama dengan forecast screening.")
        assumptions.append(
            f"Asumsi screening: aset tidak lancar lain {_bn(onca0)} dan liabilitas tidak lancar "
            f"non-utang {_bn(oncl0)} flat pada saldo FY{base_year}; arus kas investasi hanya "
            "capex dan arus kas pendanaan hanya dividen dan utang jangka pendek penyeimbang kas, "
            "tanpa penerbitan saham.")
        assumptions.append(
            ("Skenario analis dan jadwal LoM" if lom else "Skenario analis") +
            f": capex per tahun dari skenario; aset tetap = saldo FY{base_year} {_bn(fa0)} + "
            "capex - D&A"
            + (" (aset tetap data Sectors mencakup seluruh aset tidak lancar)."
               if abs(onca0) <= abs(ta0) * 0.001 else "."))
        assumptions.append(
            f"Mekanika model: kas akhir = kas awal FY{base_year} {_bn(cash0)} + arus kas bersih, "
            "bukan penyeimbang; arus kas operasi = laba induk + D&A - kenaikan modal kerja + "
            "laba non-pengendali; neraca seimbang karena setiap pos bergerak lewat laba rugi "
            "atau arus kas.")
        if abs(gap) > max(abs(ta0) * 1e-6, 1.0):
            assumptions.append(
                f"Catatan data: total aset FY{base_year} Sectors berbeda {_bn(gap)} dari "
                "liabilitas + ekuitas; selisih dibawa flat di liabilitas tidak lancar lain.")

    # --- year loop
    rows = []
    te = opening["equity"] if opening else None
    nci = nci0
    parent_prev = te - nci if te is not None else None
    earnings_prev = prior_earnings
    if full:
        cash, fa, nwc, revolver = cash0, fa0, nwc0, 0.0
    for i, p in enumerate(path):
        row = {"year": p["year"], "label": p["label"], "revenue": p["revenue"],
               "net_cons": p["net_cons"], "earnings": p["earnings"],
               "minority": p["net_cons"] - p["earnings"]}
        first_interim = interim is not None and i == 0
        if not bank:
            row.update(ebitda=p.get("ebitda"), capital_expenditure=p.get("capex"))
            ebt = p["net_cons"] / (1 - tax) if p["net_cons"] > 0 else p["net_cons"]
            row.update(earnings_before_tax=ebt, tax=ebt - p["net_cons"])
            if income_ok:
                da = da_list[i]
                ebit = p["ebitda"] - da
                row.update(depreciation=da, operating_pnl=ebit,
                           non_operating_income_or_loss=ebt - ebit,
                           other_non_operating=(ebt - ebit + (interest or 0.0)
                                                - (interest_income or 0.0)))
                if interest is not None:
                    row["interest_expense_non_operating"] = interest
                    row["interest_coverage"] = ebit / interest if interest else None
                if interest_income is not None:
                    row["interest_income"] = interest_income
            if fcff_ok:
                ebit = row["operating_pnl"]
                row["fcff"] = (ebit - max(ebit, 0.0) * tax + row["depreciation"] - p["capex"]
                               - dnwc_list[i])
        # Equity roll-forward.
        if te is not None:
            if opening["interim"] and i == 0:
                h2_cons = h2_net * fx
                if first_interim:
                    # Dividends of the year: the official 1H cash flow plus H2.
                    paid = interim["flows"]["dividends_paid"] + interim["div_h2"]
                    te += h2_cons - interim["div_h2"]
                else:
                    paid = None
                    te += h2_cons
                nci += h2_cons * (1 - share_parent)
            else:
                basis_earnings = earnings_prev if earnings_prev is not None else p["earnings"]
                paid = payout * max(basis_earnings, 0.0)
                te += p["net_cons"] - paid
                nci += row["minority"]
            parent = te - nci
            row.update(total_equity=te, non_controlling_interest=nci, stockholders_equity=parent,
                       dividends_paid=paid)
            if shares:
                row["bvps"] = parent / shares
            average = (parent_prev + parent) / 2 if parent_prev is not None else parent
            row["roe"] = p["earnings"] / average if average and average > 0 else None
            parent_prev = parent
        if shares:
            row["eps"] = p["earnings"] / shares
            if payout_sourced:
                row["dps"] = payout * max(p["earnings"], 0.0) / shares
                row["payout"] = payout
        # Full statements: working capital, fixed assets, cash. The interim
        # opening's first year moves the balance sheet by its H2 flows only.
        if full:
            if first_interim:
                cons_step, da_step = interim["h2_cons"], interim["da_h2"]
                capex_step, dnwc = interim["capex_h2"], interim["dnwc_h2"]
                paid_step = interim["div_h2"]
            else:
                cons_step, da_step, capex_step = p["net_cons"], row["depreciation"], p["capex"]
                dnwc, paid_step = dnwc_list[i], row["dividends_paid"]
            nwc_new = nwc + dnwc
            if nwc0 > 0:
                scale = nwc_new / nwc0
                inv, rec, oca = inv0 * scale, rec0 * scale, oca0 * scale
                pay, ocl = pay0 * scale, ocl0 * scale
            else:
                inv, rec, pay, ocl = inv0, rec0, pay0, ocl0
                oca = oca0 + (nwc_new - nwc0)
            cfo_step = cons_step + da_step - dnwc
            # Short-term debt balancing cash: draw what keeps cash at the
            # minimum, repay it first once cash is above it. No interest is
            # added; the scenario's net margin already sets pre-tax profit.
            before_debt = cash + cfo_step - capex_step - paid_step
            floor = min(cash_cap, cash_ratio * p["revenue"]) if cash_ratio else 0.0
            if before_debt < floor:
                drawn = floor - before_debt
            else:
                drawn = -min(revolver, before_debt - floor)
            revolver += drawn
            net_step = cfo_step + -capex_step + (drawn - paid_step)
            cash_begin, cash = cash, cash + net_step
            fa += capex_step - da_step
            nwc = nwc_new
            if first_interim:
                # The year's cash flow: official 1H actual + modelled H2.
                f = interim["flows"]
                cash_begin = f["cash_begin"]
                cfo = f["operating_cash_flow"] + cfo_step
                cfi = f["investing_cash_flow"] - capex_step
                other_investing = f["other_investing_cash_flow"]
                debt_flow, equity_flow = f["debt_raised"] + drawn, f["equity_raised"]
                other_financing = f["other_financing_cash_flow"]
                cff = f["financing_cash_flow"] + drawn - paid_step
                net_flow = f["net_cash_flow"] + net_step
                other_operating = cfo - p["earnings"] - row["depreciation"] + dnwc
            else:
                cfo, cfi, other_investing = cfo_step, -capex_step, 0.0
                debt_flow, equity_flow, other_financing = drawn, 0.0, 0.0
                cff = drawn - paid_step
                net_flow = net_step
                other_operating = row["minority"]
            ca = cash + inv + rec + oca
            std = std0 + revolver
            cl = std + pay + ocl
            ncl = ltd0 + oncl0
            row.update(
                cash_and_equivalents=cash, other_current_assets=oca, current_assets=ca,
                fixed_assets=fa, other_non_current_assets=onca0, total_assets=ca + fa + onca0,
                short_term_debt=std, other_current_liabilities=ocl, current_liabilities=cl,
                long_term_debt=ltd0, other_non_current_liabilities=oncl0,
                non_current_liabilities=ncl, total_liabilities=cl + ncl,
                total_debt=std + ltd0, net_debt=std + ltd0 - cash, working_capital=nwc,
                revolver=revolver, cash_begin=cash_begin, operating_cash_flow=cfo,
                change_in_working_capital=-dnwc, other_operating_cash_flow=other_operating,
                other_investing_cash_flow=other_investing, investing_cash_flow=cfi,
                debt_raised=debt_flow, equity_raised=equity_flow,
                other_financing_cash_flow=other_financing, financing_cash_flow=cff,
                net_cash_flow=net_flow, free_cash_flow=cfo - p["capex"], revolver_drawn=drawn)
            if inv_known:
                row["inventories"] = inv
            if interim and interim["has_receivables"]:
                row["trade_receivables"] = rec
            if interim and interim["has_payables"]:
                row["trade_payables"] = pay
        earnings_prev = p["earnings"]
        rows.append(row)
    if full:
        draws = [f"{r['label']} {'tarik' if r['revolver_drawn'] > 0 else 'lunasi'} "
                 f"{_bn(abs(r['revolver_drawn']))}" for r in rows
                 if abs(r["revolver_drawn"]) > 0.5]
        for r in rows:
            r["revolver_flow"] = r.pop("revolver_drawn", 0.0)
        assumptions.append(
            "Asumsi screening: utang jangka pendek penyeimbang kas. Kas minimum = "
            f"{cash_floor_basis}; bila kas sebelum pembiayaan di bawah minimum, kekurangannya "
            "ditarik sebagai utang jangka pendek dan dilunasi lebih dulu saat kas melebihi "
            "minimum. Bunganya tidak ditambahkan: laba sebelum pajak tetap diturunkan dari laba "
            "bersih skenario, jadi pos non-operasional bersih yang implisit menanggungnya. "
            + ("Dipakai: " + "; ".join(draws) + "." if draws else
               "Tidak terpakai pada skenario ini."))

    reasons = _reasons(bank=bank, full=full, moved_text=moved_text, da_reason=da_reason,
                       has_ebitda=has_ebitda, has_capex=has_capex, base=base,
                       first_year=first["year"], payout=payout, bs_complete=bs_complete,
                       income_ok=income_ok, equity_reason=equity_reason, shares=shares,
                       payout_sourced=payout_sourced, payout_basis=payout_basis,
                       inventories_known=(full and inv_known) or not full)
    return {"rows": rows, "notes": _notes(rows, universe, reasons, opening),
            "assumptions": assumptions, "basis": basis, "mode": mode, "base_year": base_year}


def _bank_model_rows(intake, fc, model, horizon):
    """The Bank Driver Scenario's own statements (``app.bank_model``): income
    statement, balance sheet, capital and per-share lines for each forecast
    year, the same rows the DDM values. Lines the model leaves out have their
    reason in ``notes``."""
    rows = []
    for r in model["rows"][:max(int(horizon or 0), 0)]:
        rows.append({k: v for k, v in r.items() if k not in _BANK_MODEL_INTERNAL})
    payout_basis = intake.get("payout_basis") or "sumber tidak tercatat"
    sourced = not str(payout_basis).startswith("asumsi analis")
    reasons = {}
    for keys, text in _BANK_MODEL_REASONS.items():
        reasons.update(dict.fromkeys(keys, text))
    reasons.update(model.get("notes") or {})
    if not sourced:
        for row in rows:
            row.pop("dps", None)
            row.pop("payout", None)
        reasons["dps"] = reasons["payout"] = (
            f"Payout historis tidak tersedia: {_source(payout_basis)}. DPS dan payout forecast "
            "memerlukan payout atau panduan dividen yang didukung.")
    universe = tuple(dict.fromkeys(
        BANK_MODELLED + tuple(k for keys in _BANK_MODEL_REASONS for k in keys)
        + tuple(model.get("notes") or {}) + ("dps", "payout")))
    span = (f"{rows[0]['label']}-{rows[-1]['label']}" if len(rows) > 1 else rows[0]["label"]
            ) if rows else "-"
    period = model["anchor"]["period"]
    assumptions = [
        f"Skenario analis (model driver bank): {span} dari aktual {period} resmi ditambah H2 dan "
        f"{max(len(rows) - 1, 0)} tahun lanjutan dari driver analis; laba, dividen dan ekuitas "
        "yang sama dipakai Key Financials dan DDM."] + list(model.get("assumptions") or [])
    for text in (model.get("checks") or {}).get("warnings") or []:
        assumptions.append(f"Catatan model: {text}.")
    assumptions.extend(_earnings_quality_notes(intake, fc))
    return {"rows": rows, "notes": _notes(rows, universe, reasons, None),
            "assumptions": assumptions, "basis": "skenario analis (model driver bank)",
            "mode": MODE_BANK_DRIVER, "base_year": model.get("base_year")}


def _reasons(*, bank, full, moved_text, da_reason, has_ebitda, has_capex, base, first_year,
             payout, bs_complete, income_ok, equity_reason, shares, payout_sourced,
             payout_basis, inventories_known):
    """Why each key the rows may leave out is not modelled."""
    reasons = {}
    if bank:
        for keys, text in _BANK_REASONS.items():
            reasons.update(dict.fromkeys(keys, text))
    else:
        reasons.update(dict.fromkeys(("cost_of_revenue", "gross_profit", "operating_expense"),
                                     R_GROSS))
        reasons["interest_income"] = R_INTEREST_INCOME
        reasons["trade_receivables"] = reasons["trade_payables"] = R_TRADE
        ebitda_reason = ("Skenario tidak memuat margin EBITDA untuk setiap tahun forecast."
                         if not has_ebitda else None)
        capex_reason = ("Skenario tidak memuat intensitas capex untuk setiap tahun forecast."
                        if not has_capex else None)
        if ebitda_reason:
            reasons["ebitda"] = ebitda_reason
        if capex_reason:
            reasons["capital_expenditure"] = capex_reason
        income_reason = da_reason or ebitda_reason
        for key in ("depreciation", "operating_pnl", "non_operating_income_or_loss"):
            reasons[key] = income_reason
        reasons["fcff"] = income_reason or capex_reason
        reasons["interest_expense_non_operating"] = (
            R_INTEREST if income_ok else
            "Skenario laba tidak memisahkan beban bunga dari pos non-operasional lain; "
            f"totalnya pun tidak dihitung. {income_reason}")
        reasons["interest_coverage"] = R_COVERAGE
        if not full:
            parts = []
            if moved_text:
                parts.append(f"Mekanika model: {moved_text}, sehingga neraca dan arus kas tidak "
                             "diproyeksikan.")
            for text in (da_reason, ebitda_reason, capex_reason):
                if text and text not in parts:
                    parts.append(text)
            if base is None:
                parts.append(f"Neraca aktual FY{first_year - 1} tidak tersedia di data Sectors, "
                             "sehingga neraca dan arus kas tidak dapat di-roll-forward.")
            elif not bs_complete:
                parts.append(f"Neraca FY{first_year - 1} data Sectors tidak lengkap (aset atau "
                             "liabilitas lancar, aset tetap atau kas), sehingga neraca dan arus "
                             "kas tidak di-roll-forward.")
            if payout is None:
                parts.append(equity_reason)
            why = " ".join(parts) or "Neraca dan arus kas tidak diproyeksikan."
            for key in BS_KEYS + CF_KEYS:
                reasons.setdefault(key, why)
        elif not inventories_known:
            reasons["inventories"] = (f"Persediaan tidak dilaporkan di data Sectors "
                                      f"FY{first_year - 1}; termasuk dalam aset lancar lain.")
    if equity_reason:
        reasons.update(dict.fromkeys(("total_equity", "stockholders_equity",
                                      "non_controlling_interest", "dividends_paid", "bvps",
                                      "roe"), equity_reason))
    if not shares:
        reasons.update(dict.fromkeys(("eps", "dps", "bvps"), "Jumlah saham tidak tersedia di "
                                     "neraca resmi maupun data Sectors."))
    if not payout_sourced:
        reasons["dps"] = reasons["payout"] = (
            f"Payout historis tidak tersedia: {_source(payout_basis)}. DPS dan payout forecast "
            "memerlukan payout atau panduan dividen yang didukung."
            if payout is not None else equity_reason)
    return reasons


def _notes(rows, universe, reasons, opening):
    """A reason for every key absent from all rows (dropped), and for a key
    that is None in some years (kept, with the years named)."""
    notes = {}
    for key in dict.fromkeys(tuple(universe) + tuple(k for r in rows for k in r)):
        if key in ("year", "label"):
            continue
        values = [r.get(key) for r in rows]
        if all(v is None for v in values):
            notes[key] = reasons.get(key) or "Tidak dimodelkan pada skenario ini."
            for r in rows:
                r.pop(key, None)
        elif any(v is None for v in values):
            missing = ", ".join(r["label"] for r in rows if r.get(key) is None)
            if key == "dividends_paid" and opening and opening["interim"]:
                notes[key] = (f"{missing}: dividen tahun berjalan sudah tercermin di ekuitas "
                              f"neraca interim {opening['when']}; arus kas dividen setahun penuh "
                              "tidak dimodelkan.")
            elif key == "roe":
                notes[key] = f"{missing}: ekuitas rata-rata tidak positif; ROE tidak bermakna."
            elif key == "interest_coverage":
                notes[key] = f"{missing}: beban bunga nol."
            else:
                notes[key] = f"{missing}: {reasons.get(key) or 'tidak dapat dihitung.'}"
    return notes
