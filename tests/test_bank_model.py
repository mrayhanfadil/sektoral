"""Bank driver model (app.bank_model): history ratios, the 1H anchor and the
five-year projection's invariants, and how the forecast, DDM, statements and
release gate read it (spec §3.1 Institusi keuangan, S2.5, S2.8)."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import bank_model as B  # noqa: E402
from app import forecast, forecast_statements, release, scenario_value  # noqa: E402

T = 1e12  # Rp triliun


def _year(year, gl, ea, nii, ebt, opex, prov, tax, earn, dep, ca, sa, oibl, nibl, te, ta,
          rwa, cap, allowance, ii, ie):
    return {"year": year, "gross_loan": gl * T, "non_loan_earning_assets": ea * T,
            "net_interest_income": nii * T, "earnings_before_tax": ebt * T,
            "operating_expense": opex * T, "provision": prov * T, "tax": tax * T,
            "earnings": earn * T, "total_deposit": dep * T, "current_account": ca * T,
            "savings_account": sa * T, "time_deposit": (dep - ca - sa) * T,
            "other_interest_bearing_liabilities": oibl * T,
            "non_interest_bearing_liabilities": nibl * T, "total_equity": te * T,
            "total_assets": ta * T, "total_liabilities": (dep + oibl + nibl) * T,
            "total_risk_weighted_asset": rwa * T, "total_capital": cap * T,
            "allowance_for_loans": -allowance * T, "net_loan": (gl - allowance) * T,
            "interest_income": ii * T, "interest_expense": ie * T,
            "non_interest_income": (ebt - nii + opex + prov) * T, "revenue": None}


# A BBCA-like bank, FY2022-FY2025 (Sectors signs: allowance negative).
HISTORY = [
    _year(2022, 700, 1170, 64.0, 50.5, 32.5, 4.5, 9.7, 40.7, 1040, 324, 524, 9.8, 44.0, 221.0,
          1315.0, 822, 220.6, 34.0, 72.2, 8.25),
    _year(2023, 792, 1266, 75.1, 60.2, 37.5, 2.3, 11.5, 48.6, 1102, 348, 536, 12.2, 51.7, 242.5,
          1408.4, 826, 242.7, 33.3, 87.4, 12.3),
    _year(2024, 901, 1354, 82.3, 68.2, 38.1, 2.0, 13.4, 54.8, 1120.6, 359.4, 559.6, 16.7, 40.1,
          271.9, 1449.3, 910, 265.2, 32.6, 94.8, 12.5),
    _year(2025, 970, 1509, 85.5, 71.3, 36.7, 4.0, 13.7, 57.5, 1238.5, 431.0, 612.9, 21.4, 45.2,
          281.7, 1586.8, 936.4, 284.4, 29.8, 98.9, 13.4),
]
OFFICIAL = {"period": "1H26", "period_end": "2026-06-30", "published_at": "2026-07-28",
            "source_url": "https://issuer.example/1h26.xlsx", "unit": "IDR",
            "metrics": {"revenue": 57.1 * T, "net_interest_income": 42.5 * T,
                        "net_profit": 29.5 * T, "net_profit_attributable": 29.49 * T}}
BALANCE = {"period_end": "2026-06-30", "total_assets": 1660.6 * T, "loans": 982.0 * T,
           "deposits": 1279.0 * T, "shares_outstanding": 122.84e9,
           "non_controlling_interest": 0.23 * T}


def _drivers(first=(5.0, 5.6, 33.0, 33.0, 0.4), later=(6.0, 5.7, 32.0, 33.0, 0.4), **extra):
    rows = []
    for i, values in enumerate([first] + [later] * 4):
        rows.append({"year": 2026 + i, **dict(zip(B.DRIVERS, values)), **extra})
    return rows


def _project(drivers=None, history=HISTORY, payout=0.8, **kw):
    return B.project(history, OFFICIAL, BALANCE, drivers or _drivers(), payout=payout,
                     payout_basis="payout ratio historis di data Sectors",
                     shares=BALANCE["shares_outstanding"], shares_basis="neraca interim resmi",
                     nci=BALANCE["non_controlling_interest"], nci_basis="neraca interim resmi",
                     **kw)


def test_history_ratios_use_average_balances_and_the_income_identity():
    y = {r["year"]: r for r in B.history(HISTORY)}[2025]
    r = y["ratios"]
    assert r["nim"] == pytest.approx(85.5 / ((1354 + 1509) / 2))
    assert r["cost_of_credit"] == pytest.approx(4.0 / ((901 + 970) / 2))
    # Non-interest income = pre-tax profit - NII + opex + provisions: every
    # income line between NII and pre-tax profit, whatever Sectors called it.
    assert y["other_income"] == pytest.approx((71.3 - 85.5 + 36.7 + 4.0) * T)
    assert r["cost_to_income"] == pytest.approx(36.7 / (85.5 + 26.5))
    assert r["coverage"] == pytest.approx(29.8 / 970)       # allowance sign flipped
    assert r["ldr"] == pytest.approx((970 - 29.8) / 1238.5)  # net loans / deposits (Sectors)
    assert r["car"] == pytest.approx(284.4 / 936.4)
    flipped = copy.deepcopy(HISTORY)
    flipped[-1]["provision"] = -4.0 * T
    assert {r["year"]: r for r in B.history(flipped)}[2025]["ratios"]["cost_of_credit"] == \
        pytest.approx(r["cost_of_credit"])


def test_eligibility_names_what_is_missing():
    assert B.eligible(HISTORY, OFFICIAL, BALANCE) == []
    no_nii = dict(OFFICIAL, metrics={k: v for k, v in OFFICIAL["metrics"].items()
                                     if k != "net_interest_income"})
    assert any("net_interest_income" in r for r in B.eligible(HISTORY, no_nii, BALANCE))
    assert any("1H" in r for r in B.eligible(HISTORY, dict(OFFICIAL, period="FY25"), BALANCE))
    thin = copy.deepcopy(HISTORY)
    thin[-1]["gross_loan"] = None
    assert any("gross_loan" in r for r in B.eligible(thin, OFFICIAL, BALANCE))
    assert B.project(thin, OFFICIAL, BALANCE, _drivers(), payout=0.8, payout_basis="x") is None


def test_reference_holds_three_year_average_and_annualised_interim():
    ref = B.reference(HISTORY, OFFICIAL, BALANCE)
    years = {r["year"]: r for r in B.history(HISTORY)}
    nims = [years[y]["ratios"]["nim"] * 100 for y in (2023, 2024, 2025)]
    assert [row["year"] for row in ref["history"]] == [2023, 2024, 2025]
    assert ref["three_year_average"]["nim_pct"] == pytest.approx(sum(nims) / 3, abs=0.01)
    ea_mid = 1660.6 * 1509 / 1586.8
    assert ref["interim"]["nim_pct"] == pytest.approx(42.5 * 2 / ((1509 + ea_mid) / 2) * 100,
                                                      abs=0.01)
    assert ref["interim"]["loan_growth_pct"] == pytest.approx(((982 / 970) ** 2 - 1) * 100,
                                                              abs=0.01)
    assert ref["interim_year"] == 2026 and ref["base_year"] == 2025


def test_a_driver_is_far_only_when_it_misses_both_references():
    ref = B.reference(HISTORY, OFFICIAL, BALANCE)
    near = {"loan_growth_pct": ref["three_year_average"]["loan_growth_pct"] + 4.0,
            "nim_pct": ref["interim"]["nim_pct"] + 0.4, "non_ii_to_nii_pct": 33.0,
            "cost_to_income_pct": 33.0, "cost_of_credit_pct": 0.4}
    assert B.departures(near, ref) == []
    far = dict(near, nim_pct=max(ref["interim"]["nim_pct"],
                                 ref["three_year_average"]["nim_pct"]) + 0.6)
    assert B.departures(far, ref) == ["nim_pct"]


def test_projection_balances_and_rolls_equity_forward():
    result = _project()
    rows, payout = result["rows"], 0.8
    assert result["checks"]["ok"] and len(rows) == 5
    prev_equity, prev_parent = 281.7 * T, 57.5 * T
    for r in rows:
        assert r["total_assets"] == pytest.approx(r["total_liabilities"] + r["total_equity"])
        assert r["total_assets"] == pytest.approx(
            r["net_loan"] + (r["non_loan_earning_assets"] - r["gross_loan"])
            + r["non_earning_assets"])
        # Dividends paid in year t = payout x parent profit of t-1 (final
        # dividend after the AGM), the DDM's DPS convention a year earlier.
        assert r["dividends_paid"] == pytest.approx(payout * prev_parent)
        assert r["total_equity"] - prev_equity == pytest.approx(
            r["net_cons"] - r["dividends_paid"])
        assert r["dps"] * BALANCE["shares_outstanding"] == pytest.approx(payout * r["earnings"])
        assert r["bvps"] * BALANCE["shares_outstanding"] == pytest.approx(r["stockholders_equity"])
        assert r["total_deposit"] == pytest.approx(r["net_loan"] / result["parameters"]["ldr"])
        # Non-earning assets keep the base year's share; securities balance.
        assert r["non_earning_assets"] == pytest.approx(
            r["total_assets"] * result["parameters"]["non_earning_share"])
        assert r["capital_adequacy_ratio"] == pytest.approx(
            r["total_equity"] * result["parameters"]["capital_to_equity"]
            / (r["total_assets"] * result["parameters"]["rwa_density"]))
        prev_equity, prev_parent = r["total_equity"], r["earnings"]
    assert rows[1]["gross_loan"] == pytest.approx(rows[0]["gross_loan"] * 1.06)
    assert rows[1]["net_interest_margin"] == pytest.approx(0.057)
    assert rows[1]["cost_of_credit"] == pytest.approx(0.004)
    assert rows[1]["cost_to_income"] == pytest.approx(0.33)


def test_interim_year_is_official_1h_plus_modelled_h2():
    result = _project()
    first, h2, anchor = result["rows"][0], result["h2"], result["anchor"]
    assert first["net_cons"] == pytest.approx(29.5 * T + h2["net_profit"])
    assert first["earnings"] == pytest.approx(29.49 * T + h2["net_profit_attributable"])
    assert first["net_interest_income"] == pytest.approx(42.5 * T + h2["net_interest_income"])
    assert first["revenue"] == pytest.approx(57.1 * T + h2["revenue"])
    # H2 NII = NIM x half-year average earning assets (30 June from official assets).
    ea_mid = 1660.6 * T * 1509 / 1586.8
    assert h2["net_interest_income"] == pytest.approx(
        0.056 * (ea_mid + first["non_loan_earning_assets"]) / 2 / 2)
    assert h2["provision"] == pytest.approx(0.004 * (982 * T + first["gross_loan"]) / 2 / 2)
    # The 1H cost split is screening and adds up to the official profit.
    split = anchor["split"]
    assert 57.1 * T - split["operating_expense"] - split["provision"] - split["tax"] == \
        pytest.approx(29.5 * T)


def test_deposit_growth_overrides_the_historical_ldr():
    result = _project(_drivers(deposit_growth_pct=12.0))
    rows = result["rows"]
    assert rows[0]["total_deposit"] == pytest.approx(1238.5 * T * 1.12)
    assert rows[1]["total_deposit"] == pytest.approx(rows[0]["total_deposit"] * 1.12)
    assert result["checks"]["ok"]


def test_capital_warning_when_payout_outruns_retained_earnings():
    fast = _project(_drivers(first=(12.0, 5.6, 33.0, 33.0, 0.4),
                             later=(12.0, 5.6, 33.0, 33.0, 0.4)), payout=1.0)
    assert fast["checks"]["ok"]
    assert any("CAR screening" in w for w in fast["checks"]["warnings"])
    assert fast["rows"][-1]["capital_adequacy_ratio"] < fast["rows"][0]["capital_adequacy_ratio"]


def test_funding_that_cannot_carry_the_loan_book_is_a_problem():
    # Loans +25% a year while deposits grow 2%: placements and securities (the
    # balancing item) run out and the model says so instead of inventing
    # funding; before that, the LDR climbs past its record with a warning.
    broken = _project(_drivers(first=(25.0, 5.6, 33.0, 33.0, 0.4),
                               later=(25.0, 5.6, 33.0, 33.0, 0.4), deposit_growth_pct=2.0))
    assert not broken["checks"]["ok"]
    assert any("selain kredit" in p and "negatif" in p for p in broken["checks"]["problems"])
    assert any(w.startswith("LDR di atas rekor") for w in broken["checks"]["warnings"])


def test_missing_capital_history_leaves_car_out_with_a_reason():
    history = copy.deepcopy(HISTORY)
    history[-1]["total_capital"] = None
    result = _project(history=history)
    assert "capital_adequacy_ratio" not in result["rows"][0]
    assert "ATMR" in result["notes"]["capital_adequacy_ratio"]


def test_assumptions_label_every_rule():
    text = " ".join(_project()["assumptions"])
    for phrase in ("Skenario analis (Bank Driver Scenario)", "Asumsi screening: rilis 1H26",
                   "LDR FY2025", "cakupan cadangan", "biaya dana FY2025", "CAR = ekuitas",
                   "pos penyeimbang", "payout x laba induk tahun t-1"):
        assert phrase in text, phrase


def test_drivers_must_start_at_the_interim_year():
    with pytest.raises(ValueError):
        _project([dict(r, year=r["year"] + 1) for r in _drivers()])


# ------------------------------------------------------------ integration

def _annual(row):
    return {"year": row["year"], "revenue": 110 * T, "ebitda": 75 * T, "ebit": 72 * T,
            "da": 2 * T, "interest": 0.0, "tax": row["tax"], "earnings": row["earnings"],
            "total_debt": 2 * T, "cash": 25 * T, "equity": row["total_equity"],
            "assets": row["total_assets"], "liab": row["total_liabilities"],
            "shares": 122.84e9, "ebt": row["earnings_before_tax"]}


def _intake():
    return {"ticker": "UJIB", "as_of": "2026-09-24", "model_profile": "financial_ddm",
            "price": 6225.0, "shares": 122.84e9, "market_cap": 6225.0 * 122.84e9,
            "payout": 0.8, "payout_basis": "payout ratio historis di data Sectors",
            "dps_hist": [200, 250, 300, 350], "annuals": [_annual(r) for r in HISTORY],
            "bank_history": copy.deepcopy(HISTORY),
            "latest_official_actual": copy.deepcopy(OFFICIAL),
            "official_evidence": {"latest_actual": copy.deepcopy(OFFICIAL),
                                  "balance_sheet": copy.deepcopy(BALANCE)}}


def _plan():
    rows = _drivers(rationale="Driver mengikuti rekam jejak tiga tahun dan hasil 1H26 resmi.",
                    source_ids=["official"])
    return {"news_effects": [], "interim_scenario": None, "outyear_scenario": None,
            "earnings_scenario": {"bank_drivers": rows[0], "rationale": "x" * 50,
                                  "source_ids": ["official"],
                                  "source_url": OFFICIAL["source_url"],
                                  "published_at": OFFICIAL["published_at"]},
            "bank_outyear_scenario": rows[1:]}


def test_forecast_values_the_bank_on_the_model():
    intake = _intake()
    fc = forecast.build(intake, 5, _plan())
    model = fc["bank_model"]
    assert model and model["checks"]["ok"]
    assert fc["earnings_scenario"]["full_year"]["net_profit_attributable"] == \
        pytest.approx(model["rows"][0]["earnings"])
    assert [r["net_profit_attributable"] for r in fc["outyear_scenario"]["rows"]] == \
        pytest.approx([r["earnings"] for r in model["rows"][1:]])
    assert fc["s2"]["S2.8_bank_driver"] == "lolos"
    detail, reasons = scenario_value.ddm(intake, fc, 0.109, 0.035)
    assert reasons == []
    assert [x["net_attr"] for x in detail["lines"]] == pytest.approx(
        [r["earnings"] for r in model["rows"]])
    assert detail["roe_fwd"] == pytest.approx(model["rows"][0]["roe"])
    assert detail["per_share_inverse"] == pytest.approx(
        (detail["roe_fwd"] - 0.035) / (0.109 - 0.035) * model["rows"][0]["bvps"])
    statements = forecast_statements.forecast_rows(intake, fc, None)
    assert statements["mode"] == forecast_statements.MODE_BANK_DRIVER
    assert [r["earnings"] for r in statements["rows"]] == pytest.approx(
        [r["earnings"] for r in model["rows"]])
    assert "net_interest_margin" in statements["rows"][0]
    assert "npl" in statements["notes"] and "government_bonds" in statements["notes"]
    gate = release.assess_ddm_scenario(intake, fc, {"detail": detail}, "validated")
    assert not any(b.startswith("bank driver model") for b in gate["blockers"])
    assert any("model driver bank" in x for x in gate["limitations"])


def test_a_broken_bank_model_blocks_the_ddm():
    intake = _intake()
    fc = forecast.build(intake, 5, _plan())
    fc["bank_model"]["checks"] = {"ok": False, "problems": ["FY26F: roll-forward ekuitas tidak cocok"],
                                  "warnings": []}
    detail, _ = scenario_value.ddm(intake, fc, 0.109, 0.035)
    gate = release.assess_ddm_scenario(intake, fc, {"detail": detail}, "validated")
    assert "bank driver model: FY26F: roll-forward ekuitas tidak cocok" in gate["blockers"]


def test_a_legacy_bank_plan_keeps_the_earnings_scenario():
    intake = _intake()
    plan = {"earnings_scenario": {"h2_revenue_to_h1": 1.0, "h2_net_margin_pct": 50.0,
                                  "source_url": OFFICIAL["source_url"],
                                  "published_at": OFFICIAL["published_at"]}}
    fc = forecast.build(intake, 5, plan)
    assert fc["bank_model"] is None
    assert fc["earnings_scenario"]["full_year"]["net_profit"] == pytest.approx(
        29.5 * T + 57.1 * T * 0.5)
