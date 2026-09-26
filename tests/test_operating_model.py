"""Synthetic operating-driver fixtures; no issuer data is implied (plus one real-file check)."""
import copy

import pytest

from app import forecast, operating_model as M, scenario_value

SRC = {"fs": {"title": "Laporan 1H", "url": "https://issuer.example/1h.pdf",
              "published_at": "2026-07-31"}}


def A(values):
    return {"values": values, "kind": "analyst_assumption", "rationale": "uji"}


def _drivers():
    return {
        "currency": "USD", "sources": SRC,
        "anchor": {"year": 2026, "source_refs": ["fs"],
                   "h1": {"revenue": 150.0, "variable_costs": 60.0, "fixed_costs": 30.0,
                          "ebitda": 60.0, "depreciation": 10.0, "interest_expense": 2.0,
                          "interest_income": 1.0, "tax": 12.0, "net_profit": 37.0,
                          "capex": 8.0, "dividends": 20.0}},
        "segments": [
            {"id": "a", "name": "A", "h1_volume": 100.0, "h1_revenue": 100.0, "source_refs": ["fs"],
             "h2_volume_to_h1": A([1.0]), "volume_growth_pct": A([10, 10, 10, 10]),
             "price_growth_pct": A([0, 0, 0, 0, 0])},
            {"id": "b", "name": "B", "h1_volume": 50.0, "h1_revenue": 50.0, "source_refs": ["fs"],
             "contract_end": "2031-05-31", "h2_volume_to_h1": A([1.0]),
             "volume_growth_pct": A([0, 0, 0, 0]), "price_growth_pct": A([0, 0, 0, 0, 0])}],
        "variable_costs": [{"id": "fuel", "name": "Bahan bakar", "h1_amount": 60.0,
                            "source_refs": ["fs"], "unit_cost_growth_pct": A([0, 0, 0, 0, 0])}],
        "fixed_costs": [{"id": "staff", "name": "Pegawai", "h1_amount": 30.0, "source_refs": ["fs"],
                         "h2_to_h1": A([1.0]), "growth_pct": A([0, 0, 0, 0])}],
        "depreciation": {"h2_to_h1": A([1.0]), "rate_on_opening_net_ppe": A([0.1])},
        "capex": {"h2_items": [{"id": "sust", "amount": 12.0, "source_refs": ["fs"]}],
                  "sustaining_outyears": A([20.0, 20.0, 20.0, 20.0])},
        "working_capital": {"receivable_days_on_revenue": A([36.5]),
                            "inventory_days_on_variable_cost": A([0.0]),
                            "payable_days_on_variable_cost": A([0.0])},
        "debt": [{"id": "notes", "principal": 100.0, "coupon": 0.05, "maturity": "2035-01-01"}],
        "liquidity": {"yield": A([0.02])},
        "tax": {"rate": A([0.25]), "interest_income_final_tax": A([0.2])},
        "distribution": {"payout_of_prior_year_profit": A([0.5])},
        "opening": {"source_refs": ["fs"], "fy0_profit": 60.0,
                    "fy0_close": {"receivables": 25.0, "inventories": 0.0, "payables": 0.0},
                    "h1_close": {"liquidity": 100.0, "receivables": 30.0, "inventories": 0.0,
                                 "payables": 0.0, "ppe": 200.0, "other_assets": 10.0,
                                 "debt": 100.0, "other_liabilities": 40.0, "equity": 200.0}},
    }


def test_a_complete_model_reconciles_every_year():
    model = M.project(_drivers())
    assert M.ok(model)
    first = model["rows"][0]
    # FY1 = official H1 plus H2 at the H1 run-rate: revenue 150 + 150.
    assert first["revenue"] == pytest.approx(300.0)
    assert first["ebitda"] == pytest.approx(120.0)
    # Year 2: segment A +10% -> 220, B flat 100 -> revenue 320; fuel 0.4/unit on 320 units.
    second = model["rows"][1]
    assert second["revenue"] == pytest.approx(320.0)
    assert second["variable_costs"] == pytest.approx(0.4 * 320)
    for row in model["rows"]:
        assert row["fcff"] == pytest.approx(row["nopat"] + row["da"] - row["capex"] - row["dnwc"])
        assert abs(row["balance_gap"]) < 1e-6


def test_a_contract_ending_inside_the_horizon_or_terminal_is_removed():
    drivers = _drivers()
    drivers["segments"][1]["contract_end"] = "2029-03-31"
    model = M.project(drivers)
    by_year = {r["year"]: r["segment_volume"]["b"] for r in model["rows"]}
    assert by_year[2028] == pytest.approx(100.0)
    assert by_year[2029] == pytest.approx(100.0 * 3 / 12)
    assert by_year[2030] == 0.0
    # The original 2031 end is after the horizon: kept in the rows, dropped in the terminal.
    base = M.project(_drivers())
    assert base["rows"][-1]["segment_volume"]["b"] == pytest.approx(100.0)
    assert base["terminal"]["excluded_segments"] == ["b"]
    assert base["terminal"]["revenue"] == pytest.approx(base["rows"][-1]["revenue"] - 100.0)
    # Its contribution (revenue less variable cost 0.4/unit) leaves the terminal EBITDA.
    assert base["terminal"]["ebitda"] == pytest.approx(base["rows"][-1]["ebitda"] - 60.0)


def test_missing_sources_or_assumption_rationale_fail_closed():
    drivers = _drivers()
    drivers["capex"]["h2_items"] = []
    assert "capex needs second-half items" in M.project(drivers)["errors"][0]
    drivers = _drivers()
    drivers["segments"][0]["volume_growth_pct"]["rationale"] = ""
    assert any("needs a rationale" in e for e in M.project(drivers)["errors"])
    drivers = _drivers()
    drivers["segments"][0]["source_refs"] = ["missing"]
    assert any("must cite sources" in e for e in M.validate(drivers))


def test_a_driver_file_published_after_the_report_date_is_not_known(tmp_path):
    import json
    (tmp_path / "XXXX.json").write_text(json.dumps(_drivers()))
    assert M.load("XXXX", "2026-09-26", root=tmp_path) is not None
    assert M.load("XXXX", "2026-07-30", root=tmp_path) is None


def test_the_forecast_uses_the_model_only_when_its_h1_equals_the_official_actual():
    model = M.project(_drivers())
    intake = {"latest_official_actual": {"period": "1H26", "unit": "USD",
                                         "metrics": {"revenue": 150.0, "net_profit": 37.0}}}
    earnings, outyear, problem = forecast._operating_scenarios(intake, model)
    assert problem is None and earnings["basis"] == "operating_driver_model"
    assert earnings["full_year"]["revenue"] == pytest.approx(300.0)
    assert [r["year"] for r in outyear["rows"]] == [2027, 2028, 2029, 2030]
    wrong = copy.deepcopy(intake)
    wrong["latest_official_actual"]["metrics"]["net_profit"] = 40.0
    assert "does not equal the official" in forecast._operating_scenarios(wrong, model)[2]
    lines, tax, terminal, h2_share = scenario_value.operating_lines(
        {"operating_model": model, "earnings_scenario": earnings})
    assert [l["fcff"] for l in lines] == [r["fcff"] for r in model["rows"]]
    assert terminal["revenue"] < lines[-1]["revenue"] and tax == 0.25
    assert h2_share == pytest.approx(model["rows"][0]["h2"]["fcff"] / model["rows"][0]["fcff"])


def test_the_powr_driver_file_reconciles_to_its_official_first_half():
    drivers = M.load("POWR", "2026-09-26")
    model = M.project(drivers)
    assert M.ok(model), [c for c in model.get("checks", []) if not c["ok"]] or model.get("errors")
    first = model["rows"][0]
    assert first["revenue"] - first["h2"]["revenue"] == pytest.approx(274783475)
    assert model["terminal"]["excluded_segments"] == ["pln"]
