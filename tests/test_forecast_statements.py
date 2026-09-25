"""Five-year forecast statements (app/forecast_statements.py).

Synthetic intake/scenario dicts prove the invariants: rows follow the charted
scenario path, the balance sheet balances, cash comes from the cash-flow
statement, the rows' FCFF equals the scenario DCF, banks model only what the
DDM drives, and every line left out carries a reason. Two fixtures extracted
from the stored JPFA and BBCA reports (out/demo-reports) tie the rows to the
published FCFF, DDM and Key Financials exhibits without reading the database.
"""
import copy
import re

import pytest

from app import cache, report_extras, scenario_value
from app import forecast_statements as fs

B = 1e9
LABELS = ["FY26F", "FY27F", "FY28F", "FY29F", "FY30F"]

# Sectors historical_financials, last actual year (full Rupiah, balanced).
BASE_2025 = {"year": 2025, "revenue": 1000 * B, "earnings": 90 * B,
             "cash_and_equivalents": 200 * B, "inventories": 150 * B,
             "current_assets": 500 * B, "fixed_assets": 800 * B, "total_assets": 1300 * B,
             "short_term_debt": 100 * B, "long_term_debt": 300 * B, "total_debt": 400 * B,
             "current_liabilities": 250 * B, "non_current_liabilities": 350 * B,
             "total_liabilities": 600 * B, "total_equity": 700 * B}

ANNUALS = [
    {"year": 2023, "revenue": 800 * B, "ebitda": 160 * B, "ebit": 120 * B, "da": 40 * B,
     "tax": 22 * B, "interest": 10 * B, "ebt": 110 * B, "total_debt": 380 * B, "cash": 150 * B,
     "shares": 1e9, "earnings": 80 * B},
    {"year": 2024, "revenue": 900 * B, "ebitda": 180 * B, "ebit": 135 * B, "da": 45 * B,
     "tax": 25 * B, "interest": 10 * B, "ebt": 125 * B, "total_debt": 390 * B, "cash": 180 * B,
     "shares": 1e9, "earnings": 85 * B},
    {"year": 2025, "revenue": 1000 * B, "ebitda": 200 * B, "ebit": 150 * B, "da": 50 * B,
     "tax": 28 * B, "interest": 10 * B, "ebt": 140 * B, "total_debt": 400 * B, "cash": 200 * B,
     "current_assets": 500 * B, "current_liabilities": 250 * B, "short_term_debt": 100 * B,
     "shares": 1e9, "earnings": 90 * B},
]
SOURCED_PAYOUT = "DPS 12 bulan terakhir Rp36,0 atas EPS FY2025 Rp90,0 (data Sectors)"


@pytest.fixture
def history(monkeypatch):
    """Sectors historical_financials per ticker, without the Sectors snapshot."""
    rows = {}
    monkeypatch.setattr(cache, "company_report", lambda ticker: {
        "financials": {"historical_financials": rows.get(ticker, [])}})
    return rows


def going_concern(fx=1.0, payout=0.4, payout_basis=SOURCED_PAYOUT, depreciation=26 * B,
                  profile="going_concern_fcff"):
    """Intake for a going concern reporting in IDR (fx=1) or US$ (fx=rate)."""
    unit = 1 / fx
    metrics = {"revenue": 520 * B * unit, "net_profit": 50 * B * unit,
               "net_profit_attributable": 45 * B * unit}
    if depreciation is not None:
        metrics["depreciation"] = depreciation * unit
    return {
        "ticker": "TEST", "model_profile": profile, "as_of": "2026-09-24", "price": 1000.0,
        "shares": 1e9, "payout": payout, "payout_basis": payout_basis,
        "official_evidence": {"reporting_currency": "USD" if fx != 1.0 else "IDR",
                              "balance_sheet": {"period_end": "2026-06-30",
                                                "shares_outstanding": 1e9,
                                                "non_controlling_interest": 40 * B * unit}},
        "fx_spot": {"pair": "USD/IDR", "rate": fx, "date": "2026-09-24"},
        "latest_official_actual": {"period": "1H26", "period_end": "2026-06-30",
                                   "metrics": metrics},
        "annuals": copy.deepcopy(ANNUALS), "quarterly_actuals": [], "dividend_events": [],
    }


def scenario(fx=1.0, share=0.9, ebitda=True, capex=True):
    """Earnings scenario (1H + H2) and four out-years, in the reporting currency."""
    unit = 1 / fx
    revenue = 1092 * B * unit
    full = {"revenue": revenue, "net_profit": 107.2 * B * unit,
            "net_profit_attributable": 107.2 * B * unit * share}
    if ebitda:
        full["ebitda"] = revenue * 0.20
    if capex:
        full["capex"] = revenue * 0.06
    rows = []
    for k, (growth, margin, net, intensity) in enumerate(
            [(8, 21, 10, 6), (7, 21.5, 10.5, 5.5), (6, 22, 11, 5), (5, 22, 11, 5)]):
        revenue *= 1 + growth / 100
        rows.append({"year": 2027 + k, "label": LABELS[k + 1], "revenue": revenue,
                     "ebitda": revenue * margin / 100 if ebitda else None,
                     "net_profit": revenue * net / 100,
                     "net_profit_attributable": revenue * net / 100 * share,
                     "capex": revenue * intensity / 100 if capex else None})
    return {"production_ready": False,
            "earnings_scenario": {"year": 2026, "h1": {"revenue": 520 * B * unit,
                                                       "net_profit": 50 * B * unit},
                                  "h2": {"revenue": 572 * B * unit,
                                         "net_profit": 57.2 * B * unit},
                                  "full_year": full, "attributable_share": share,
                                  "attributable_basis": "porsi induk 1H resmi"},
            "outyear_scenario": {"rows": rows, "status": "validated_analyst_scenario"}}


def dcf_va(intake, fc):
    detail, reasons = scenario_value.fcff(intake, fc, 0.065, 0.04, 1.1, 0.035)
    assert detail, reasons
    return {"method_chain": {"selected": "fcff_dcf",
                             "trace": [{"key": "fcff_dcf", "detail": detail}]}}


def assert_ties(rows, opening_cash):
    previous = opening_cash
    for row in rows:
        assert row["total_assets"] == pytest.approx(
            row["total_liabilities"] + row["total_equity"], rel=1e-12)
        assert row["cash_begin"] == pytest.approx(previous, rel=1e-12)
        assert row["cash_begin"] + row["net_cash_flow"] == pytest.approx(
            row["cash_and_equivalents"], rel=1e-12)
        assert row["net_cash_flow"] == pytest.approx(
            row["operating_cash_flow"] + row["investing_cash_flow"]
            + row["financing_cash_flow"], rel=1e-12)
        assert row["current_assets"] == pytest.approx(
            row["cash_and_equivalents"] + row["inventories"] + row["other_current_assets"])
        assert row["total_liabilities"] == pytest.approx(
            row["current_liabilities"] + row["non_current_liabilities"])
        previous = row["cash_and_equivalents"]


@pytest.mark.parametrize("fx", [1.0, 16000.0])
def test_going_concern_statements_balance_and_cash_ties(history, fx):
    history["TEST"] = [BASE_2025]
    intake, fc = going_concern(fx), scenario(fx)
    out = fs.forecast_rows(intake, fc, dcf_va(intake, fc))

    assert out["basis"] == "skenario analis"
    assert out["mode"] == fs.MODE_FULL and out["base_year"] == 2025
    assert [r["label"] for r in out["rows"]] == LABELS
    assert_ties(out["rows"], BASE_2025["cash_and_equivalents"])
    # Debt follows the valuation's flat-debt screen; fixed assets roll with capex - D&A.
    fixed = BASE_2025["fixed_assets"]
    for row in out["rows"]:
        assert row["total_debt"] == BASE_2025["total_debt"]
        fixed += row["capital_expenditure"] - row["depreciation"]
        assert row["fixed_assets"] == pytest.approx(fixed)
        assert row["net_debt"] == pytest.approx(row["total_debt"] - row["cash_and_equivalents"])


@pytest.mark.parametrize("fx", [1.0, 16000.0])
@pytest.mark.parametrize("with_va", [True, False])
def test_fcff_implied_by_rows_equals_scenario_dcf(history, fx, with_va):
    history["TEST"] = [BASE_2025]
    intake, fc = going_concern(fx), scenario(fx)
    va = dcf_va(intake, fc)
    lines = va["method_chain"]["trace"][0]["detail"]["lines"]
    detail = va["method_chain"]["trace"][0]["detail"]
    out = fs.forecast_rows(intake, fc, va if with_va else None)

    for row, line in zip(out["rows"], lines, strict=True):
        assert row["fcff"] == pytest.approx(line["fcff"], rel=1e-9)
        # The identity from the rows alone: EBIT x (1 - t) + D&A - capex - dNWC.
        implied = (row["operating_pnl"] * (1 - detail["tax_rate"]) + row["depreciation"]
                   - row["capital_expenditure"] + row["change_in_working_capital"])
        assert implied == pytest.approx(line["fcff"], rel=1e-9)
        assert -row["change_in_working_capital"] == pytest.approx(line["dnwc"], rel=1e-9)
        assert row["depreciation"] == pytest.approx(line["da"], rel=1e-9)


def test_rows_follow_the_charted_scenario_path(history):
    history["TEST"] = [BASE_2025]
    intake, fc = going_concern(), scenario()
    rows = fs.forecast_rows(intake, fc)["rows"]
    path = scenario_value.path(fc)
    for row, step in zip(rows, path, strict=True):
        assert row["label"] == step["label"]
        assert row["revenue"] == step["revenue"]
        assert row["ebitda"] == step["ebitda"]
        assert row["net_cons"] == step["net_profit"]
        assert row["earnings"] == step["net_profit_attributable"]
        assert row["capital_expenditure"] == step["capex"]
        assert row["minority"] == pytest.approx(step["net_profit"] - step["net_profit_attributable"])
    for row, chart in zip(rows, report_extras.chart_forecast_rows(intake, fc)):
        assert (row["label"], row["revenue"], row["ebitda"], row["earnings"]) == (
            chart["label"], chart["revenue"], chart["ebitda"], chart["net_attr"])
    assert [r["label"] for r in fs.forecast_rows(intake, fc, horizon=3)["rows"]] == LABELS[:3]


def test_income_statement_reconciles_to_scenario_profit(history):
    history["TEST"] = [BASE_2025]
    intake, fc = going_concern(), scenario()
    out = fs.forecast_rows(intake, fc)
    tax = scenario_value.tax_rate(intake)[0]
    for row in out["rows"]:
        assert row["operating_pnl"] == pytest.approx(row["ebitda"] - row["depreciation"])
        assert row["earnings_before_tax"] == pytest.approx(
            row["operating_pnl"] + row["non_operating_income_or_loss"])
        assert row["tax"] == pytest.approx(row["earnings_before_tax"] * tax)
        assert row["earnings_before_tax"] - row["tax"] == pytest.approx(row["net_cons"])
        assert row["net_cons"] - row["minority"] == pytest.approx(row["earnings"])
    assert "implisit" in out["notes"]["interest_expense_non_operating"]
    assert any("implisit dari margin laba bersih" in a for a in out["assumptions"])


def test_cash_flow_starts_from_attributable_profit_with_cash_flow_signs(history):
    history["TEST"] = [BASE_2025]
    rows = fs.forecast_rows(going_concern(), scenario())["rows"]
    for row in rows:
        assert row["operating_cash_flow"] == pytest.approx(
            row["earnings"] + row["depreciation"] + row["change_in_working_capital"]
            + row["other_operating_cash_flow"])
        assert row["other_operating_cash_flow"] == pytest.approx(row["minority"])
        assert row["change_in_working_capital"] < 0  # revenue grows: working capital absorbs cash
        assert row["capital_expenditure"] > 0 and row["dividends_paid"] > 0
        assert row["investing_cash_flow"] == pytest.approx(-row["capital_expenditure"])
        assert row["financing_cash_flow"] == pytest.approx(
            row["debt_raised"] + row["equity_raised"] + row["other_financing_cash_flow"]
            - row["dividends_paid"])
        assert row["free_cash_flow"] == pytest.approx(
            row["operating_cash_flow"] - row["capital_expenditure"])
    # Working-capital items scale with revenue at the FY2025 intensity (15%).
    assert rows[-1]["working_capital"] == pytest.approx(0.15 * rows[-1]["revenue"])


def test_per_share_values_use_parent_figures_and_valuation_shares(history):
    history["TEST"] = [BASE_2025]
    intake, fc = going_concern(), scenario()
    out = fs.forecast_rows(intake, fc)
    rows = out["rows"]
    shares = scenario_value.bridge(intake)["shares"]
    for row in rows:
        assert row["eps"] == pytest.approx(row["earnings"] / shares)
        assert row["stockholders_equity"] == pytest.approx(
            row["total_equity"] - row["non_controlling_interest"])
        assert row["bvps"] == pytest.approx(row["stockholders_equity"] / shares)
        assert row["dps"] == pytest.approx(0.4 * row["eps"])
        assert row["payout"] == 0.4
    # Dividends paid in year t come from year t-1 profit (FY26F: FY2025 actual).
    assert rows[0]["dividends_paid"] == pytest.approx(0.4 * BASE_2025["earnings"])
    assert rows[1]["dividends_paid"] == pytest.approx(0.4 * rows[0]["earnings"])
    # Equity: opening + consolidated profit - dividends; NCI keeps its share.
    equity, nci = BASE_2025["total_equity"], 40 * B
    for row in rows:
        equity += row["net_cons"] - row["dividends_paid"]
        nci += row["minority"]
        assert row["total_equity"] == pytest.approx(equity)
        assert row["non_controlling_interest"] == pytest.approx(nci)


def test_every_missing_line_has_a_reason(history):
    history["TEST"] = [BASE_2025]
    out = fs.forecast_rows(going_concern(), scenario())
    for key in fs.NON_FINANCIAL_KEYS:
        present = all(key in row for row in out["rows"])
        assert present or out["notes"].get(key), key
        assert not (present and key in out["notes"]), key
    for key in ("trade_receivables", "trade_payables", "interest_income", "gross_profit",
                "cost_of_revenue", "operating_expense"):
        assert out["notes"][key]
    assert out["assumptions"] and all(isinstance(a, str) and a for a in out["assumptions"])
    assert any(a.startswith("Asumsi screening: utang awal flat") for a in out["assumptions"])


def _reader_texts(out):
    return list(out["assumptions"]) + list(out["notes"].values())


@pytest.mark.parametrize("profile", ["going_concern_fcff", "financial_ddm"])
def test_reader_text_carries_no_field_names(history, profile):
    history["TEST"] = [BASE_2025]
    fc = scenario(ebitda=profile != "financial_ddm", capex=profile != "financial_ddm")
    out = fs.forecast_rows(going_concern(profile=profile), fc)
    identifiers = set(fs.NON_FINANCIAL_KEYS + fs.BANK_KEYS)
    for text in _reader_texts(out):
        leaked = [w for w in re.findall(r"[a-z]+(?:_[a-z]+)+", text) if w in identifiers]
        assert not leaked, (leaked, text)


def test_other_non_operating_is_the_ebit_to_pretax_line(history):
    history["TEST"] = [BASE_2025]
    for row in fs.forecast_rows(going_concern(), scenario())["rows"]:
        assert row["other_non_operating"] == pytest.approx(
            row["earnings_before_tax"] - row["operating_pnl"])
        assert row["other_non_operating"] == row["non_operating_income_or_loss"]


def heavy_capex(fx=1.0):
    """FY26F-FY27F capex far above cash flow, then light capex: the revolver
    must draw first and be repaid later."""
    fc = scenario(fx)
    fc["earnings_scenario"]["full_year"]["capex"] = fc["earnings_scenario"]["full_year"][
        "revenue"] * 0.45
    for row, intensity in zip(fc["outyear_scenario"]["rows"], (0.40, 0.02, 0.02, 0.02)):
        row["capex"] = row["revenue"] * intensity
    return fc


@pytest.mark.parametrize("fx", [1.0, 16000.0])
def test_revolver_keeps_cash_at_the_minimum_then_is_repaid(history, fx):
    history["TEST"] = [BASE_2025]
    intake, fc = going_concern(fx), heavy_capex(fx)
    va = dcf_va(intake, fc)
    out = fs.forecast_rows(intake, fc, va)
    rows = out["rows"]
    ratio = BASE_2025["cash_and_equivalents"] / BASE_2025["revenue"]
    floors = [min(BASE_2025["cash_and_equivalents"], ratio * r["revenue"]) for r in rows]

    assert all(r["cash_and_equivalents"] >= 0 for r in rows)
    assert all(r["cash_and_equivalents"] >= f - 1e-3 for r, f in zip(rows, floors))
    assert rows[0]["debt_raised"] > 0 and rows[1]["debt_raised"] > 0
    assert rows[0]["cash_and_equivalents"] == pytest.approx(floors[0])
    assert any(r["debt_raised"] < 0 for r in rows[2:])            # repaid once cash recovers
    balance = 0.0
    for row in rows:
        balance += row["debt_raised"]
        assert row["revolver"] == pytest.approx(balance)
        assert row["revolver"] >= -1e-3
        assert row["short_term_debt"] == pytest.approx(BASE_2025["short_term_debt"] + balance)
        assert row["total_debt"] == pytest.approx(BASE_2025["total_debt"] + balance)
        assert row["financing_cash_flow"] == pytest.approx(
            row["debt_raised"] - row["dividends_paid"])
    assert_ties(rows, BASE_2025["cash_and_equivalents"])
    for row, line in zip(rows, va["method_chain"]["trace"][0]["detail"]["lines"], strict=True):
        assert row["fcff"] == pytest.approx(line["fcff"], rel=1e-9)
    text = next(a for a in out["assumptions"]
                if a.startswith("Asumsi screening: utang jangka pendek penyeimbang kas"))
    assert "Dipakai: FY26F tarik" in text and "lunasi" in text
    # No interest is invented for the draw: pre-tax profit still follows the scenario.
    tax = scenario_value.tax_rate(intake)[0]
    for row in rows:
        assert row["earnings_before_tax"] * (1 - tax) == pytest.approx(row["net_cons"])


def test_revolver_idle_when_cash_stays_above_the_minimum(history):
    history["TEST"] = [BASE_2025]
    out = fs.forecast_rows(going_concern(), scenario())
    assert all(r["debt_raised"] == 0 and r["revolver"] == 0 for r in out["rows"])
    assert any("Tidak terpakai" in a for a in out["assumptions"])


def test_unsourced_payout_keeps_cash_roll_but_hides_dps(history):
    history["TEST"] = [BASE_2025]
    intake = going_concern(payout=0.25,
                           payout_basis="asumsi analis 25% (tanpa payout historis di data Sectors)")
    out = fs.forecast_rows(intake, scenario())
    assert "dps" in out["notes"] and "payout" in out["notes"]
    assert all("dps" not in r and "payout" not in r for r in out["rows"])
    assert out["rows"][0]["dividends_paid"] == pytest.approx(0.25 * BASE_2025["earnings"])
    assert any(a.startswith("Asumsi analis tanpa sumber: payout") for a in out["assumptions"])
    assert_ties(out["rows"], BASE_2025["cash_and_equivalents"])


def test_missing_depreciation_models_earnings_and_equity_only(history):
    history["TEST"] = [BASE_2025]
    intake = going_concern(depreciation=None)
    for annual in intake["annuals"]:
        annual["da"] = None
    out = fs.forecast_rows(intake, scenario())
    assert out["mode"] == fs.MODE_EQUITY
    assert len(out["rows"]) == 5
    for key in ("depreciation", "operating_pnl", "fcff", "cash_and_equivalents",
                "total_assets", "operating_cash_flow"):
        assert key in out["notes"] and all(key not in r for r in out["rows"])
    assert "D&A tidak tersedia" in out["notes"]["depreciation"]
    for key in ("revenue", "ebitda", "earnings", "total_equity", "eps", "bvps", "dps",
                "earnings_before_tax", "tax"):
        assert all(key in r for r in out["rows"]), key


def test_share_count_change_rolls_equity_from_interim_balance_sheet(history):
    history["TEST"] = [BASE_2025]
    intake = going_concern()
    intake["official_evidence"]["balance_sheet"].update(shares_outstanding=2e9,
                                                          total_equity=1500 * B)
    fc = scenario()
    out = fs.forecast_rows(intake, fc)
    rows = out["rows"]
    assert out["mode"] == fs.MODE_EQUITY
    assert rows[0]["total_equity"] == pytest.approx(1500 * B + 57.2 * B)
    assert rows[0]["dividends_paid"] is None
    assert out["notes"]["dividends_paid"].startswith("FY26F")
    assert rows[1]["dividends_paid"] == pytest.approx(0.4 * rows[0]["earnings"])
    assert rows[0]["eps"] == pytest.approx(rows[0]["earnings"] / 2e9)
    assert "jumlah saham berubah" in out["notes"]["total_assets"]
    assert all("total_assets" not in r for r in rows)


def test_bank_models_only_what_the_ddm_drives(history):
    history["BANK"] = [{"year": 2025, "revenue": 1000 * B, "earnings": 300 * B,
                        "total_assets": 9000 * B, "total_liabilities": 7500 * B,
                        "total_equity": 1500 * B}]
    intake = going_concern(profile="financial_ddm")
    intake["ticker"] = "BANK"
    fc = scenario(ebitda=False, capex=False)
    detail, reasons = scenario_value.ddm(intake, fc, 0.11, 0.035)
    assert detail, reasons
    va = {"method_chain": {"trace": [{"key": "ddm", "detail": detail}]}}
    out = fs.forecast_rows(intake, fc, va)
    rows = out["rows"]

    assert out["mode"] == fs.MODE_BANK and len(rows) == 5
    assert set(rows[0]) - {"year", "label"} == set(fs.BANK_MODELLED)
    for row, line in zip(rows, detail["lines"], strict=True):
        assert row["dps"] == pytest.approx(line["dps"], rel=1e-12)
        assert row["earnings"] == pytest.approx(line["net_attr"], rel=1e-12)
        assert row["payout"] == detail["payout"]
    equity = 1500 * B
    for row in rows:
        equity += row["net_cons"] - row["dividends_paid"]
        assert row["total_equity"] == pytest.approx(equity)
    # Every line the bank statements, ratios and charts read has its own reason.
    specific = {
        "gross_loan": "penyaluran kredit", "npl": "kredit bermasalah",
        "government_bonds": "obligasi pemerintah", "securities": "surat berharga",
        "non_loan_earning_assets": "aset produktif", "total_deposit": "simpanan nasabah",
        "current_account": "simpanan nasabah", "interest_income": "pendapatan bunga",
        "net_interest_income": "pendapatan bunga bersih", "provision": "provisi",
        "depreciation": "D&A", "ebitda": "EBITDA", "capital_adequacy_ratio": "CAR",
        "net_interest_margin": "NIM", "cost_of_funds": "biaya dana",
        "cost_of_credit": "biaya kredit", "loan_to_deposit_ratio": "LDR",
        "fcff": "FCFF", "operating_cash_flow": "Arus kas"}
    for key, phrase in specific.items():
        assert phrase in out["notes"][key], key
    for key in fs.BANK_KEYS + fs.NON_FINANCIAL_KEYS:
        assert all(key in r for r in rows) or out["notes"].get(key), key


def _mining_case():
    fx = 16000.0
    tax, ntgr, interest = 0.2, 0.1, 100e6
    intake = going_concern(fx=fx, payout=0.25,
                           payout_basis="asumsi analis 25% (tanpa payout historis di data Sectors)",
                           profile="finite_life_mining")
    intake["official_evidence"]["latest_actual"] = {"financial_statements_usd_thousand": {
        "income_statement": {"finance_costs": -interest / 2 / 1000}}}
    rows, flows = [], [{"year": 2026, "da": 150e6}]
    for k, (revenue, ebitda) in enumerate([(3200e6, 2000e6), (3100e6, 1900e6),
                                           (3000e6, 1800e6), (2900e6, 1700e6)]):
        year = 2027 + k
        flows += [{"year": year, "da": 300e6}, {"year": year, "da": 100e6}]
        pre_tax = ebitda - 400e6 - interest
        net = pre_tax * (1 - tax) * (1 - ntgr)
        rows.append({"year": year, "label": LABELS[k + 1], "revenue": revenue, "ebitda": ebitda,
                     "net_profit": net, "net_profit_attributable": net, "capex": 250e6})
    fc = {"production_ready": False,
          "interim_scenario": {"year": 2026, "h2": {"net_profit": 300e6},
                               "full_year": {"revenue": 3000e6, "ebitda": 1500e6,
                                             "net_profit": 600e6,
                                             "capital_expenditure": 300e6}},
          "outyear_scenario": {"rows": rows, "status": "lom_schedule"}}
    va = {"method_chain": {"trace": [{"key": "sotp_lom", "detail": {"lom": {
        "inputs": {"da_usd": 300e6, "tax_rate": tax, "ntgr_rate": ntgr},
        "base": {"flows": flows}}}}]}}
    return intake, fc, va, fx, interest


def test_mining_follows_the_valued_lom_schedule(history):
    history["TEST"] = [BASE_2025]
    intake, fc, va, fx, interest = _mining_case()
    out = fs.forecast_rows(intake, fc, va)
    rows = out["rows"]
    assert out["mode"] == fs.MODE_FULL and [r["label"] for r in rows] == LABELS
    assert rows[0]["revenue"] == pytest.approx(3000e6 * fx)
    assert rows[0]["depreciation"] == pytest.approx(300e6 * fx)  # 1H actual + LoM H2
    for row in rows[1:]:
        # The LoM's own income statement: EBIT - interest = pre-tax; tax + PNBP.
        assert row["depreciation"] == pytest.approx(400e6 * fx)
        assert row["non_operating_income_or_loss"] == pytest.approx(-interest * fx)
        pre_tax = row["operating_pnl"] - interest * fx
        assert row["earnings_before_tax"] == pytest.approx(pre_tax)
        assert row["tax"] == pytest.approx(pre_tax - row["net_cons"])
    for row in rows:
        assert row["interest_expense_non_operating"] == pytest.approx(interest * fx)
        assert row["change_in_working_capital"] == 0.0
    assert_ties(rows, BASE_2025["cash_and_equivalents"])
    assert "dps" in out["notes"]
    assert any(a.startswith("Jadwal LoM") for a in out["assumptions"])


AMMN = {
    # Stored AMMN report (out/demo-reports): official 1H26 + H2 anchor and the
    # valued LoM out-years (US$), FY2025 official parent share 248,979/258,000,
    # and the published Key Financials EPS (US$ sen) at Rp17.893/US$.
    "fx": 17892.965093039656, "shares": 72412413856,
    "annual_actuals": [{"year": 2025, "net_profit": 258000000,
                        "net_profit_attributable": 248979000}],
    "interim": {"year": 2026, "h2": {"net_profit": 640224000.0},
                "full_year": {"revenue": 4719600000.0, "ebitda": 2541828000.0,
                              "net_profit": 1144224000.0, "capital_expenditure": 312000000.0}},
    "outyears": [(2027, 5044744972.8451, 3393334531.3846, 1771780882.1019),
                 (2028, 4953403462.7185, 3236495671.9344, 1658127624.8836),
                 (2029, 4953403462.7185, 3236495671.9344, 1658127624.8836),
                 (2030, 4953403462.7185, 3236495671.9344, 1658127624.8836)],
    "lom": {"da_usd": 436920000.0, "tax_rate": 0.20260115814840124,
            "ntgr_rate": 0.0912328688033602},
    "history": {"year": 2025, "revenue": 30904224855660, "earnings": 4167027074340,
                "cash_and_equivalents": 11327721485340, "inventories": 17505835066200,
                "current_assets": 52760066713380, "fixed_assets": 179385478712700,
                "total_assets": 232145545426080, "short_term_debt": 9405472108500,
                "long_term_debt": 98965951589700, "total_debt": 108371423698200,
                "current_liabilities": 23597354203020,
                "non_current_liabilities": 117650602479540,
                "total_liabilities": 141247956682560, "total_equity": 90897588743520},
    "eps_cents": [1.52, 2.36, 2.21],
}


def test_mining_parent_share_follows_key_financials(history):
    history["AMMN"] = [AMMN["history"]]
    fx, shares = AMMN["fx"], AMMN["shares"]
    intake = going_concern(fx=fx, payout=0.25,
                           payout_basis="asumsi analis 25% (tanpa payout historis di data Sectors)",
                           profile="finite_life_mining")
    intake["ticker"] = "AMMN"
    intake["annuals"][-1].update(shares=72377616279.0, total_debt=108371423698200.0,
                                 cash=11327721485340.0)
    intake["official_evidence"].update(
        annual_actuals=AMMN["annual_actuals"], annual_source_title="AMMAN FY 2025 Earnings Release",
        latest_actual={"financial_statements_usd_thousand": {
            "income_statement": {"finance_costs": -255699}}})
    intake["official_evidence"]["balance_sheet"].update(shares_outstanding=shares,
                                                        non_controlling_interest=95328000)
    rows = [{"year": y, "label": f"FY{y % 100}F", "revenue": rev, "ebitda": ebitda,
             "net_profit": net, "net_profit_attributable": net, "capex": 260064000.0}
            for y, rev, ebitda, net in AMMN["outyears"]]
    fc = {"production_ready": False, "interim_scenario": AMMN["interim"],
          "outyear_scenario": {"rows": rows, "status": "lom_schedule"}}
    flows = [{"year": 2026, "da": 218460000.0}] + [{"year": y, "da": 436920000.0}
                                                   for y in range(2027, 2031)]
    va = {"method_chain": {"trace": [{"key": "sotp_lom", "detail": {"lom": {
        "inputs": AMMN["lom"], "base": {"flows": flows}}}}]}}
    out = fs.forecast_rows(intake, fc, va)
    rows = out["rows"]
    share = 248979000 / 258000000

    assert out["mode"] == fs.MODE_FULL
    assert [round(r["eps"] / fx * 100, 2) for r in rows[:3]] == AMMN["eps_cents"]
    for row in rows:
        assert row["earnings"] == pytest.approx(row["net_cons"] * share, rel=1e-12)
        assert row["minority"] == pytest.approx(row["net_cons"] * (1 - share), rel=1e-12)
        assert row["eps"] == pytest.approx(row["earnings"] / shares, rel=1e-12)
        assert row["bvps"] == pytest.approx(row["stockholders_equity"] / shares, rel=1e-12)
    assert [round(r["net_cons"] / fx / 1e6, 1) for r in rows[:3]] == [1144.2, 1771.8, 1658.1]
    nci = scenario_value.bridge(intake).get("nci") or 95328000 * fx
    for row in rows:
        nci += row["minority"]
        assert row["non_controlling_interest"] == pytest.approx(nci, rel=1e-12)
    assert any("porsi induk FY2025 resmi" in a for a in out["assumptions"])
    assert_ties(rows, AMMN["history"]["cash_and_equivalents"])


def test_production_forecast_uses_its_own_depreciation(history):
    history["TEST"] = [BASE_2025]
    rows = [{"year": 2026 + k, "label": LABELS[k], "revenue": (1100 + 100 * k) * B,
             "ebitda": (220 + 20 * k) * B, "da": (55 + 5 * k) * B, "net": (110 + 10 * k) * B,
             "capex": (60 + 5 * k) * B} for k in range(5)]
    out = fs.forecast_rows(going_concern(), {"production_ready": True, "rows": rows})
    assert out["basis"] == "forecast produksi"
    assert [r["depreciation"] for r in out["rows"]] == [r["da"] for r in rows]
    assert [r["earnings"] for r in out["rows"]] == [r["net"] for r in rows]
    assert_ties(out["rows"], BASE_2025["cash_and_equivalents"])


@pytest.mark.parametrize("fc", [None, {}, {"rows": [{"year": 2026}], "production_ready": False}])
@pytest.mark.parametrize("profile", ["going_concern_fcff", "financial_ddm"])
def test_no_scenario_and_no_production_forecast_gives_no_rows(history, fc, profile):
    out = fs.forecast_rows(going_concern(profile=profile), fc)
    assert out["rows"] == [] and out["basis"] is None
    universe = fs.BANK_KEYS if profile == "financial_ddm" else fs.NON_FINANCIAL_KEYS
    assert set(out["notes"]) == set(universe)
    assert all("skenario analis tervalidasi" in v for v in out["notes"].values())


# --- fixtures extracted from the stored reports (out/demo-reports, 2026-09-24)

JPFA = {
    "intake": {
        "ticker": "JPFA", "model_profile": "going_concern_fcff", "as_of": "2026-09-24",
        "price": 2180.0, "shares": 11704870701, "payout": 0.409261,
        "payout_basis": "DPS 12 bulan terakhir Rp140,0 atas EPS FY2025 Rp342,1 (data Sectors)",
        "official_evidence": {"reporting_currency": "IDR", "balance_sheet": {
            "period_end": "2026-06-30", "total_equity": 21334052000000,
            "shares_issued": 11726575201, "shares_outstanding": 11704870701}},
        "latest_official_actual": {"period": "1H26", "period_end": "2026-06-30", "metrics": {
            "revenue": 35355127000000, "net_profit": 2684344000000,
            "net_profit_attributable": 2475417000000}},
        "annuals": [
            {"year": 2023, "revenue": 51175898000000.0, "ebitda": 0.0, "ebit": 2264057000000.0,
             "tax": 315315000000.0, "interest": 988478000000.0, "ebt": 1261237000000.0,
             "total_debt": 21604000000.0, "cash": 1505310000000.0, "shares": 11627669901.0,
             "earnings": 929716000000.0},
            {"year": 2024, "revenue": 55800849000000.0, "ebitda": 6227279000000.0,
             "ebit": 5061875000000.0, "da": 1165404000000.0, "da_source": "official",
             "tax": 1029134000000.0, "interest": 870051000000.0, "ebt": 4241472000000.0,
             "total_debt": 10743624000000.0, "cash": 1356331000000.0, "shares": 11627669901.0,
             "earnings": 3018892000000.0},
            {"year": 2025, "revenue": 60715806000000.0, "ebitda": 7448607000000.0,
             "ebit": 6183584000000.0, "da": 1265023000000.0, "da_source": "official",
             "tax": 1202320000000.0, "interest": 804867000000.0, "ebt": 5483649000000.0,
             "total_debt": 11862081000000.0, "cash": 3553088000000.0,
             "current_assets": 21376175000000.0, "current_liabilities": 16517464000000.0,
             "short_term_debt": 9771736000000.0, "shares": 11726575201.0,
             "earnings": 4004000000000.0}],
        "quarterly_actuals": [
            {"date": "2025-12-31", "total_debt": 11862081000000,
             "cash_and_short_term_investments": 3553088000000, "cash_only": 3550006000000,
             "total_equity": 20018957000000, "stockholders_equity": 18663757000000}],
        "dividend_events": []},
    "fc": {"production_ready": False,
           "earnings_scenario": {
               "year": 2026, "h1": {"revenue": 35355127000000, "net_profit": 2684344000000},
               "h2": {"revenue": 31819614300000.0, "net_profit": 1845537629400.0},
               "full_year": {"revenue": 67174741300000.0, "net_profit": 4529881629400.0,
                             "net_profit_attributable": 4177313337412.962,
                             "ebitda": 8060968956000.0, "capex": 3358737065000.0},
               "attributable_share": 0.922168, "attributable_basis": "porsi induk 1H resmi"},
           "outyear_scenario": {"status": "validated_analyst_scenario", "rows": [
               {"year": 2027, "label": "FY27F", "revenue": 72548720604000.0,
                "ebitda": 8705846472480.0, "net_profit": 4715666839260.0,
                "net_profit_attributable": 4348638572493.12, "capex": 3264692427180.0},
               {"year": 2028, "label": "FY28F", "revenue": 77627131046280.0,
                "ebitda": 9160001463461.04, "net_profit": 4968136386961.92,
                "net_profit_attributable": 4581457991451.213, "capex": 3337966634990.04},
               {"year": 2029, "label": "FY29F", "revenue": 82284758909056.8,
                "ebitda": 9462747274541.531, "net_profit": 5101655052361.521,
                "net_profit_attributable": 4704584674971.465, "capex": 3291390356362.272},
               {"year": 2030, "label": "FY30F", "revenue": 86398996854509.64,
                "ebitda": 9676687647705.078, "net_profit": 5183939811270.579,
                "net_profit_attributable": 4780465072954.876, "capex": 3455959874180.3857}]}},
    "history": [{"year": 2025, "revenue": 60715806000000, "earnings": 4004000000000,
                 "cash_and_equivalents": 3553088000000, "cash_only": 3550006000000,
                 "inventories": 11726011000000, "current_assets": 21376175000000,
                 "fixed_assets": 18684255000000, "total_assets": 40060430000000,
                 "short_term_debt": 9771736000000, "long_term_debt": 2090345000000,
                 "total_debt": 11862081000000, "current_liabilities": 16517464000000,
                 "non_current_liabilities": 3524009000000,
                 "total_liabilities": 20041473000000, "total_equity": 20018957000000}],
    # Published exhibits, Rp miliar: "Proyeksi FCFF dan nilai kini (FY26F-FY30F)" and
    # Key Financials (EPS in Rp).
    "fcff": [1907.9, 2715.5, 3065.9, 3442.1, 3559.5],
    "revenue": [67174.7, 72548.7, 77627.1], "ebitda": [8061.0, 8705.8, 9160.0],
    "earnings": [4177.3, 4348.6, 4581.5], "eps": [357, 372, 391],
}

BBCA = {
    "intake": {
        "ticker": "BBCA", "model_profile": "financial_ddm", "as_of": "2026-09-24",
        "price": 6225.0, "shares": 122841751300, "payout": 0.813433,
        "payout_basis": "DPS 12 bulan terakhir Rp381,0 atas EPS FY2025 Rp468,4 (data Sectors)",
        "official_evidence": {"reporting_currency": "IDR", "balance_sheet": {
            "period_end": "2026-06-30", "cash": 21065925000000, "total_equity": 270667746000000,
            "equity_attributable": 270437543000000, "non_controlling_interest": 230203000000,
            "shares_outstanding": 122841751300}},
        "latest_official_actual": {"period": "1H26", "period_end": "2026-06-30", "metrics": {
            "revenue": 57111457000000, "net_profit": 29545621000000,
            "net_profit_attributable": 29534446000000}},
        "annuals": [
            {"year": 2024, "revenue": 108306541000000.0, "tax": 13366576000000.0,
             "ebt": 68217850000000.0, "total_debt": 3046238000000.0, "cash": 69822495000000.0,
             "shares": 123275050000.0, "earnings": 54836305000000.0},
            {"year": 2025, "revenue": 112006326000000.0, "tax": 13697783000000.0,
             "ebt": 71260876000000.0, "total_debt": 2395446000000.0, "cash": 78406483000000.0,
             "shares": 123244982342.0, "earnings": 57537287000000.0}],
        "quarterly_actuals": [], "dividend_events": []},
    "fc": {"production_ready": False,
           "earnings_scenario": {
               "year": 2026, "h1": {"revenue": 57111457000000, "net_profit": 29545621000000},
               "h2": {"revenue": 58253686140000.0, "net_profit": 30291916792800.0},
               "full_year": {"revenue": 115365143140000.0, "net_profit": 59837537792800.0,
                             "net_profit_attributable": 59814905522358.484},
               "attributable_share": 0.999622, "attributable_basis": "porsi induk 1H resmi"},
           "outyear_scenario": {"status": "validated_analyst_scenario", "rows": [
               {"year": 2027, "label": "FY27F", "revenue": 122287051728400.0,
                "net_profit": 63589266898768.0, "net_profit_attributable": 63565215616935.28},
               {"year": 2028, "label": "FY28F", "revenue": 130235710090746.0,
                "net_profit": 67983040667369.42, "net_profit_attributable": 67957327534466.99},
               {"year": 2029, "label": "FY29F", "revenue": 138049852696190.77,
                "net_profit": 71509823696626.81, "net_profit_attributable": 71482776633381.47},
               {"year": 2030, "label": "FY30F", "revenue": 145642594594481.25,
                "net_profit": 75005936216157.84,
                "net_profit_attributable": 74977566823034.73}]}},
    "history": [{"year": 2025, "revenue": 112006326000000, "earnings": 57537287000000,
                 "cash_only": 25305031000000, "total_assets": 1586830000000000,
                 "total_debt": 2395446000000, "total_liabilities": 1305140000000000,
                 "total_equity": 281687555000000}],
    # Published "Proyeksi dividen dan nilai kini (DDM, FY26F-FY30F)": parent profit
    # (Rp miliar) and DPS (Rp).
    "earnings": [59814.9, 63565.2, 67957.3, 71482.8, 74977.6],
    "dps": [396, 421, 450, 473, 496],
}


def test_jpfa_rows_tie_to_the_published_fcff_and_key_financials(history):
    history["JPFA"] = JPFA["history"]
    intake, fc = copy.deepcopy(JPFA["intake"]), copy.deepcopy(JPFA["fc"])
    out = fs.forecast_rows(intake, fc, dcf_va(intake, fc))
    rows = out["rows"]
    assert out["mode"] == fs.MODE_FULL and [r["label"] for r in rows] == LABELS
    assert [round(r["fcff"] / B, 1) for r in rows] == pytest.approx(JPFA["fcff"], abs=0.051)
    for key in ("revenue", "ebitda", "earnings"):
        assert [round(r[key] / B, 1) for r in rows[:3]] == pytest.approx(JPFA[key], abs=0.051)
    assert [round(r["eps"]) for r in rows[:3]] == JPFA["eps"]
    assert_ties(rows, JPFA["history"][0]["cash_and_equivalents"])
    # Template tie-out tolerance (below 0.1%) holds with room to spare.
    assert max(abs(r["total_assets"] - r["total_liabilities"] - r["total_equity"])
               / r["total_assets"] for r in rows) < 1e-9


def test_bbca_rows_tie_to_the_published_ddm(history):
    history["BBCA"] = BBCA["history"]
    intake, fc = copy.deepcopy(BBCA["intake"]), copy.deepcopy(BBCA["fc"])
    detail, reasons = scenario_value.ddm(intake, fc, 0.109, 0.035)
    assert detail, reasons
    out = fs.forecast_rows(intake, fc, {"method_chain": {"trace": [
        {"key": "ddm", "detail": detail}]}})
    rows = out["rows"]
    assert out["mode"] == fs.MODE_BANK and [r["label"] for r in rows] == LABELS
    assert [round(r["earnings"] / B, 1) for r in rows] == pytest.approx(BBCA["earnings"],
                                                                        abs=0.051)
    assert [round(r["dps"]) for r in rows] == BBCA["dps"]
    assert all("total_assets" not in r and "ebitda" not in r for r in rows)
    assert rows[0]["total_equity"] == pytest.approx(
        281687555000000 + rows[0]["net_cons"] - 0.813433 * 57537287000000)
