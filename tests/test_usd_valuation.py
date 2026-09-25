"""A US$ reporter's scenario DCF is built and discounted in US$ (spec §2, §4.2).

The flows, balance sheet, EV and equity stay in US$; the WACC is UST 10Y +
the Indonesia CRP + beta x the mature-market ERP with a market-based US$ cost
of debt; the value per share converts to rupiah once, at the dated spot rate.
A rupiah reporter's DCF is the same as before (INDOGB, no CRP).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import fmt, narrative, scenario_value as SV, valuation  # noqa: E402
from app import forecast_statements as fs  # noqa: E402
from test_forecast_statements import (BASE_2025, dcf_va, going_concern,  # noqa: E402,F401
                                      history, scenario)
from test_primary_methods import _fc, _going_concern  # noqa: E402

FX = 16000.0
UST = {"name": "UST10Y", "rate": 0.05, "date": "2026-09-24", "symbol": "^TNX",
       "source": "Yahoo Finance ^TNX daily close"}
M = 1e6


def _usd(fx=FX, debt=100 * M, finance_cost=None, ust=UST):
    """A US$ reporter: official 1H26 release and balance sheet in US$; Sectors
    history in rupiah at Sectors' own rate (16.700)."""
    metrics = {"revenue": 50 * M, "net_profit": 4 * M, "depreciation": 2.5 * M}
    if finance_cost is not None:
        metrics["finance_cost"] = finance_cost
    sectors = 16700.0
    return {
        "model_profile": "going_concern_fcff", "price": 300.0, "price_date": "2026-09-24",
        "as_of": "2026-09-24", "shares": 1e9,
        "official_evidence": {
            "reporting_currency": "USD",
            "balance_sheet": {"period_end": "2026-06-30", "cash": 40 * M,
                              "short_term_investments": 10 * M, "total_debt": debt,
                              "shares_issued": 1e9},
            "annual_actuals": [{"year": 2025, "revenue": 90 * M, "equity": 200 * M}]},
        "latest_official_actual": {"period": "1H26", "period_end": "2026-06-30",
                                   "metrics": metrics},
        "fx_spot": {"pair": "USD/IDR", "rate": fx, "date": "2026-09-24"},
        "ust_10y": ust,
        "annuals": [{"year": 2025, "revenue": 90 * M * sectors, "ebit": 15 * M * sectors,
                     "interest": 1 * M * sectors, "tax": 3.5 * M * sectors,
                     "cash": 10 * M * sectors, "total_debt": 70 * M * sectors,
                     "current_assets": 40 * M * sectors, "current_liabilities": 30 * M * sectors,
                     "short_term_debt": 10 * M * sectors}],
        "historical_ev_ebitda": [{"value": 6.0}, {"value": 7.0}, {"value": 8.0}],
        "quarterly_actuals": [], "dividend_events": []}


def _fc_usd():
    """Earnings scenario (1H + H2) and four out-years in US$."""
    fc = _fc(net=8.0, ebitda=0.25, capex=0.05)
    anchor = fc["earnings_scenario"]
    for part in ("full_year", "h1", "h2"):
        anchor[part] = {k: v * M for k, v in anchor[part].items()}
    for row in fc["outyear_scenario"]["rows"]:
        for key in ("revenue", "net_profit", "net_profit_attributable", "ebitda", "capex"):
            row[key] *= M
    return fc


def _dcf(intake, fc=None):
    rates, gaps = SV.discount_rates(intake, 0.065, 0.035)
    assert not gaps, gaps
    detail, reasons = SV.fcff(intake, fc or _fc_usd(), 0.065, 0.04, 1.1, 0.035, rates=rates)
    assert detail, reasons
    return detail


# --- the US$ discount rate --------------------------------------------------

def test_usd_wacc_is_ust_plus_crp_plus_beta_times_mature_erp():
    d = _dcf(_usd())
    assert d["currency"] == "USD" and d["rf_label"] == "UST 10Y" and d["rf_date"] == "2026-09-24"
    assert d["rf"] == 0.05 and d["crp"] == SV.CRP_INDONESIA == 0.025
    assert d["coe"] == pytest.approx(0.05 + 0.025 + 1.1 * 0.04)
    assert d["g"] == SV.TERMINAL_GROWTH_USD < d["rf"] < d["wacc"]
    # No sourced finance cost: the market US$ rate UST + CRP, stated as policy.
    assert d["kd_pretax"] == pytest.approx(0.075) and "UST 10Y + CRP" in d["kd_basis"]
    wd = d["weight_debt"]
    assert wd == pytest.approx(100 * M / (100 * M + 300.0 * 1e9 / FX))
    assert d["wacc"] == pytest.approx(d["coe"] * (1 - wd) + d["kd_after"] * wd)
    assert sorted({g for _, g in d["grid"]}) == list(SV.GRID_GROWTH_USD)
    assert d["per_share_down"] == d["grid"][(0.01, 0.02)]


def test_usd_cost_of_debt_is_the_issuers_own_only_when_not_below_market():
    # 1H26 finance cost 3m on 100m debt = 6% a year, below UST + CRP 7,5%: not market.
    low = _dcf(_usd(finance_cost=3 * M))
    assert low["kd_pretax"] == pytest.approx(0.075)
    assert low["kd_effective"] == pytest.approx(0.06) and "tidak dipakai" in low["kd_basis"]
    # 5m in 1H = 10% a year: the issuer's own rate.
    high = _dcf(_usd(finance_cost=5 * M))
    assert high["kd_pretax"] == pytest.approx(0.10) and "bunga efektif emiten" in high["kd_basis"]


def test_a_usd_model_without_a_dated_ust_yield_is_not_discounted_at_a_rupiah_rate():
    rates, gaps = SV.discount_rates(_usd(ust=None), 0.065, 0.035)
    assert rates is None and "UST 10Y" in gaps[0]
    candidate = valuation._fcff_scenario_candidate(_usd(ust=None), _fc_usd(), "validated",
                                                   0.065, 0.04, 1.1, 0.035, 0.0)
    assert candidate["per_share"] is None and "UST 10Y" in candidate["reasons"][0]


# --- US$ model, one conversion ------------------------------------------------

def test_usd_reporter_is_valued_in_usd_and_converted_once_at_the_per_share_step():
    d = _dcf(_usd())
    native = d["native"]
    fc = _fc_usd()
    # Flows are the scenario in US$, not converted.
    assert native["lines"][0]["revenue"] == fc["earnings_scenario"]["full_year"]["revenue"]
    assert native["lines"][1]["revenue"] == fc["outyear_scenario"]["rows"][0]["revenue"]
    # Working capital grows from the official US$ FY25 revenue.
    assert native["prior_revenue"] == 90 * M
    # Bridge: the official US$ balance sheet, cash with short-term investments.
    assert (native["cash"], native["debt"]) == (50 * M, 100 * M)
    assert d["valuation_date"] == "2026-06-30" and native["lines"][0]["share"] == 0.5
    # Equity per share in US$, then the one conversion.
    assert native["per_share"] == pytest.approx(native["equity"] / 1e9)
    assert d["per_share"] == pytest.approx(native["per_share"] * FX)
    # Rupiah mirrors carry the same one rate.
    assert d["ev"] == pytest.approx(native["ev"] * FX)
    for line, own in zip(d["lines"], native["lines"]):
        assert line["fcff"] == pytest.approx(own["fcff"] * FX)
        assert line["factor"] == own["factor"]


def test_the_rate_moves_only_the_rupiah_value_per_share():
    # Without debt the WACC is the cost of equity, so nothing in US$ depends on the rate.
    a, b = _dcf(_usd(debt=0.0)), _dcf(_usd(fx=18000.0, debt=0.0))
    assert a["wacc"] == b["wacc"] and a["native"]["ev"] == b["native"]["ev"]
    assert b["per_share"] / a["per_share"] == pytest.approx(18000.0 / FX)
    assert b["grid"][(0.0, 0.03)] / a["grid"][(0.0, 0.03)] == pytest.approx(18000.0 / FX)


def test_the_price_implied_rate_is_a_usd_wacc():
    # Without debt the price does not move the weights, so the WACC is fixed.
    intake = _usd(debt=0.0)
    d = _dcf(intake)
    rates, _ = SV.discount_rates(intake, 0.065, 0.035)
    at_implied, _ = SV.fcff({**intake, "price": d["per_share"]}, _fc_usd(), 0.065, 0.04, 1.1,
                            0.035, rates=rates)
    # At a price equal to the value, the implied WACC is the model's own.
    assert at_implied["implied_wacc"] == pytest.approx(at_implied["wacc"], abs=1e-6)


# --- rupiah reporters are unchanged ---------------------------------------------

@pytest.mark.parametrize("shares, pinned", [
    (10.0, {"per_share": 20.69637127226141, "wacc": 0.10281914893617022,
            "ev": 266.9637127226141, "per_share_down": 15.51575562109424,
            "implied_wacc": 0.07362807777856087}),
    (5.0, {"per_share": 23.360968206416942, "wacc": 0.10358695652173913,
           "ev": 268.6096820641694, "per_share_down": 18.13337463770054,
           "implied_wacc": 0.07662410497947217})])
def test_rupiah_reporter_dcf_is_unchanged(shares, pinned):
    """Values pinned from the DCF before the US$ change (INDOGB 6,5%, no CRP, g 3,5%)."""
    intake, fc = _going_concern(shares=shares), _fc(net=8.0, ebitda=0.25, capex=0.02)
    rates, gaps = SV.discount_rates(intake, 0.065, 0.035)
    assert gaps == [] and rates["currency"] == "IDR" and rates["crp"] == 0.0
    with_rates, _ = SV.fcff(intake, fc, 0.065, 0.04, 1.1, 0.035, rates=rates)
    plain, _ = SV.fcff(intake, fc, 0.065, 0.04, 1.1, 0.035)
    assert with_rates["rf_label"] == "INDOGB 10Y" and with_rates["crp"] == 0.0
    for detail in (with_rates, plain):
        assert detail["native"] is None and detail["fx"] is None
        assert detail["coe"] == pytest.approx(0.065 + 1.1 * 0.04, rel=1e-15)
        for key, value in pinned.items():
            assert detail[key] == pytest.approx(value, rel=1e-12), key
    assert SV.native_view(plain) is plain


# --- exhibits -------------------------------------------------------------------

def _exhibits(intake, detail):
    fcff, bridge, wacc, grid = narrative._dcf_scenario_exhibits(intake, detail, "FY26F", [])
    return fcff, bridge, wacc, grid


def test_usd_exhibits_show_usd_figures_and_one_conversion():
    intake = _usd()
    d = _dcf(intake)
    fcff, bridge, wacc, grid = _exhibits(intake, d)
    assert fcff["data"]["cols"][0] == "US$ juta" and bridge["data"]["cols"][0] == "US$ juta"
    revenue = next(r for r in fcff["data"]["rows"] if r[0] == "Pendapatan")
    assert revenue[1] == fmt._id(d["native"]["lines"][0]["revenue"] / M, 1)
    rows = {r[0]: r[1] for r in bridge["data"]["rows"]}
    assert rows["Enterprise value"] == fmt._id(d["native"]["ev"] / M, 1)
    assert rows["Ekuitas per saham (US$)"] == narrative._usd_per_share(d["native"]["per_share"])
    assert rows["Kurs Rp/US$ (Yahoo Finance IDR=X, 2026-09-24)"] == fmt._id(FX, 0)
    assert rows["Nilai wajar per saham (Rp)"] == fmt.rp(fmt.tick(d["per_share"]))
    labels = [r[0] for r in bridge["data"]["rows"]]
    # The rupiah value per share closes the bridge; nothing before it is in rupiah.
    assert labels[-1] == "Nilai wajar per saham (Rp)" and labels[-2].startswith("Kurs")
    params = {r[0]: r[1] for r in wacc["data"]["rows"]}
    assert params["Risk-free (UST 10Y, 2026-09-24)"] == "5,0%"
    assert params["Country risk premium Indonesia (parameter kebijakan analis)"] == "2,5%"
    assert not any("INDOGB" in label for label in params)
    assert list(params)[-1] == "WACC"
    assert "kebijakan analis" in wacc["catatan_sumber"] and "UST 10Y" in wacc["catatan_sumber"]
    assert grid["data"]["cols"] == ["WACC", "g 2,0%", "g 3,0%", "g 4,0%"]
    base = next(r for r in grid["data"]["rows"] if "(basis)" in r[0])
    assert base[2] == f"Rp{fmt.rp(fmt.tick(d['per_share']))}"


def test_rupiah_exhibits_keep_indogb_and_no_crp():
    intake = {**_going_concern(shares=10.0), "price_date": "2026-09-24"}
    d, _ = SV.fcff(intake, _fc(net=8.0, ebitda=0.25, capex=0.02), 0.065, 0.04, 1.1, 0.035,
                   rates=SV.discount_rates(intake, 0.065, 0.035)[0])
    fcff, bridge, wacc, grid = _exhibits(intake, d)
    assert fcff["data"]["cols"][0] == "Rp miliar" and wacc["judul"] == "Komponen WACC"
    labels = [r[0] for r in wacc["data"]["rows"]]
    assert labels[0] == "Risk-free (INDOGB 10Y)"
    assert not any("risk premium Indonesia" in label for label in labels)
    assert not any(r[0].startswith("Kurs") for r in bridge["data"]["rows"])
    assert grid["data"]["cols"] == ["WACC", "g 2,5%", "g 3,5%", "g 4,5%"]


# --- statements follow the same US$ base ----------------------------------------

def test_usd_statements_open_from_the_official_usd_equity(history):
    history["TEST"] = [BASE_2025]
    fx = 16000.0
    intake, fc = going_concern(fx), scenario(fx)
    sectors_rate = 16700.0
    evidence = intake["official_evidence"]
    evidence["annual_actuals"] = [{"year": 2025, "revenue": BASE_2025["revenue"] / sectors_rate,
                                   "equity": BASE_2025["total_equity"] / sectors_rate,
                                   "equity_attributable": 660e9 / sectors_rate,
                                   "net_profit_attributable": BASE_2025["earnings"] / sectors_rate}]
    va = dcf_va(intake, fc)
    out = fs.forecast_rows(intake, fc, va)
    factor = fx / sectors_rate
    rows = out["rows"]
    first = rows[0]
    # Opening equity = official US$ x the rows' rate; FY26F rolls from it.
    opening = BASE_2025["total_equity"] / sectors_rate * fx
    assert first["total_equity"] == pytest.approx(
        opening + first["net_cons"] - first["dividends_paid"])
    assert first["dividends_paid"] == pytest.approx(0.4 * BASE_2025["earnings"] * factor)
    # Every Sectors opening amount moves to the same rate; the sheet still balances.
    assert first["total_debt"] == pytest.approx(BASE_2025["total_debt"] * factor)
    assert first["cash_begin"] == pytest.approx(BASE_2025["cash_and_equivalents"] * factor)
    for row in rows:
        assert row["total_assets"] == pytest.approx(
            row["total_liabilities"] + row["total_equity"], rel=1e-12)
    assert any("neraca awal FY2025 dari ekuitas US$" in a for a in out["assumptions"])
    # The FCFF identity with the US$ DCF (rupiah mirror) still holds.
    lines = va["method_chain"]["trace"][0]["detail"]["lines"]
    for row, line in zip(rows, lines):
        assert row["fcff"] == pytest.approx(line["fcff"], rel=1e-9)


def test_official_interim_finance_cost_becomes_the_interest_line(history):
    history["TEST"] = [BASE_2025]
    fx = 16000.0
    intake, fc = going_concern(fx), scenario(fx)
    intake["latest_official_actual"]["metrics"]["finance_cost"] = 8e9 / fx  # 1H26, US$
    out = fs.forecast_rows(intake, fc, dcf_va(intake, fc))
    for row in out["rows"]:
        assert row["interest_expense_non_operating"] == pytest.approx(16e9)
        assert row["other_non_operating"] == pytest.approx(
            row["earnings_before_tax"] - row["operating_pnl"] + 16e9)
        assert row["interest_coverage"] == pytest.approx(row["operating_pnl"] / 16e9)
    assert "interest_expense_non_operating" not in out["notes"]


# --- mining: the LoM discounts at the same US$ build, one USD/IDR rate ----------

def _mine(finance_costs=None, ust=UST, fx=FX):
    income = {"profit_before_tax": 100.0, "income_tax": -20.0,
              "profit_before_non_tax_revenue": 80.0, "non_tax_government_revenue": -8.0}
    if finance_costs is not None:
        income["finance_costs"] = finance_costs            # US$ thousand, 1H
    return {"price": 4000.0, "ust_10y": ust,
            "fx_spot": {"pair": "USD/IDR", "rate": fx, "date": "2026-09-24"},
            "official_evidence": {"reporting_currency": "USD", "latest_actual": {
                "period": "1H26", "financial_statements_usd_thousand": {"income_statement": income}}},
            "sotp_bridge": {"debt_idr": {"value": 5000 * M * fx}, "shares": {"value": 72e9}}}


def test_lom_discount_rate_is_the_us_dollar_wacc_built_from_ust_and_crp():
    from app import lom
    build, gaps = lom.discount_rate(_mine())
    assert gaps == []
    assert build["coe"] == pytest.approx(0.05 + SV.CRP_INDONESIA + lom.BETA * lom.ERP)
    assert build["kd_pretax"] == pytest.approx(0.075)            # market: UST + CRP
    shield = 1 - (1 - 0.2) * (1 - 0.1)                           # income tax and PNBP
    wd = 5000 * M / (5000 * M + 4000.0 * 72e9 / FX)
    assert build["weight_debt"] == pytest.approx(wd)
    wacc = build["coe"] * (1 - wd) + 0.075 * (1 - shield) * wd
    assert build["wacc"] == pytest.approx(wacc) and build["rate"] == round(wacc, 3)
    # The issuer's own finance cost counts when not below market: 250m x2 / 5bn = 10%.
    assert lom.discount_rate(_mine(finance_costs=-250_000))[0]["kd_pretax"] == pytest.approx(0.10)
    # No dated UST yield: no rate, the LoM names the gap.
    assert lom.discount_rate(_mine(ust=None)) == (None, ["ust_10y"])


def test_sotp_bridge_translates_at_the_reports_one_usd_idr_close():
    from app import intake as intake_mod
    evidence = {"reporting_currency": "USD",
                "valuation_fx_reference": {"rate": 17803.0, "date": "2026-09-23",
                                           "source_url": "https://www.bi.go.id/jisdor"},
                "balance_sheet": {"period_end": "2026-06-30", "cash": 800 * M,
                                  "non_controlling_interest": 95 * M,
                                  "source_title": "FS", "source_url": "https://example.test/fs"},
                "latest_actual": {"published_at": "2026-09-21"},
                "debt_and_contract_evidence": {"shares_outstanding": 72e9}}
    spot = {"pair": "USD/IDR", "rate": FX, "date": "2026-09-24"}
    bridge = intake_mod._sotp_bridge_inputs(evidence, "2026-09-24", spot)
    assert bridge["cash_idr"]["value"] == pytest.approx(800 * M * FX)
    assert bridge["cash_idr"]["fx_rate"] == FX and "IDR=X" in bridge["cash_idr"]["source"]
    # Without the stored close the pack's dated reference is the fallback.
    assert intake_mod._sotp_bridge_inputs(evidence, "2026-09-24")["cash_idr"]["fx_rate"] == 17803.0
