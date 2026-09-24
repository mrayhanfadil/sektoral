"""Primary methods on the validated scenario: bank DDM, going-concern FCFF DCF,
holding SOTP under Method Gate 0, and the agent's soft DCF drivers."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.forecast_assumptions import run as agent  # noqa: E402
from app import method_chain as MC, model_profiles as MP, release  # noqa: E402
from app import scenario_value as SV  # noqa: E402


def _fc(net=50.0, growth=0.1, ebitda=None, capex=None):
    full = {"revenue": 100.0, "net_profit": net, "net_profit_attributable": net}
    if ebitda is not None:
        full.update(ebitda=100.0 * ebitda, capex=100.0 * capex)
    rows, revenue = [], 100.0
    for i in range(4):
        revenue *= 1 + growth
        row = {"year": 2027 + i, "label": f"FY{27 + i}F", "revenue": revenue,
               "net_profit": revenue * net / 100, "net_profit_attributable": revenue * net / 100}
        if ebitda is not None:
            row.update(ebitda=revenue * ebitda, capex=revenue * capex)
        rows.append(row)
    return {"earnings_scenario": {"year": 2026, "full_year": full,
                                  "h1": {"revenue": 50.0, "net_profit": net / 2},
                                  "h2": {"revenue": 50.0, "net_profit": net / 2},
                                  "attributable_share": 1.0, "assumptions": {}},
            "outyear_scenario": {"rows": rows}}


def _bank(**extra):
    base = {"model_profile": "financial_ddm", "price": 40.0, "payout": 0.5,
            "payout_basis": "payout ratio historis di data Sectors", "dps_hist": [1, 2, 3],
            "official_evidence": {"balance_sheet": {
                "period_end": "2026-06-30", "shares_outstanding": 10.0,
                "equity_attributable": 200.0}},
            "annuals": [{"year": 2025, "revenue": 90.0}]}
    base.update(extra)
    return base


def test_scenario_ddm_discounts_dividends_at_cost_of_equity():
    detail, reasons = SV.ddm(_bank(), _fc(), 0.109, 0.035)
    assert reasons == [] and detail["basis"] == "scenario"
    first = detail["lines"][0]
    assert abs(first["dps"] - 50.0 * 0.5 / 10) < 1e-9
    assert abs(first["t"] - (0.5 + 0.25)) < 0.01      # paid a quarter after FY26 closes
    assert detail["per_share"] > 0 and detail["per_share_down"] < detail["per_share"]
    grid = detail["grid"]
    assert grid[(-0.01, 0.035)] > grid[(0.0, 0.035)] > grid[(0.01, 0.035)]
    assert grid[(0.0, 0.045)] > grid[(0.0, 0.025)]


def test_scenario_ddm_needs_a_sourced_payout_and_five_years():
    _, reasons = SV.ddm(_bank(payout_basis="asumsi analis 25%"), _fc(), 0.109, 0.035)
    assert any("payout" in r for r in reasons)
    short = _fc()
    short["outyear_scenario"]["rows"] = short["outyear_scenario"]["rows"][:2]
    assert SV.ddm(_bank(), short, 0.109, 0.035)[0] is None


def test_ddm_release_gate_checks_dividend_evidence():
    gate = release.assess_ddm_scenario(_bank(dps_hist=[1]), _fc(), {"detail": {
        "payout": 0.5, "coe": 0.03, "g": 0.035, "lines": [{"dps": 1.0}] * 5}}, "validated")
    assert any("dividend history" in b for b in gate["blockers"])
    assert any("cost of equity must exceed" in b for b in gate["blockers"])
    assert not any(b.startswith("peer PER") for b in gate["blockers"])


def _going_concern(**extra):
    base = {"model_profile": "going_concern_fcff", "price": 40.0, "as_of": "2026-09-24",
            "official_evidence": {"balance_sheet": {"period_end": "2026-06-30",
                                                    "cash": 30.0, "shares_issued": 10.0}},
            "quarterly_actuals": [
                {"date": "2026-03-31", "total_debt": 80.0, "cash_only": 20.0},
                {"date": "2026-06-30", "total_debt": 60.0, "cash_and_short_term_investments": 45.0,
                 "cash_only": 30.0, "total_equity": 300.0, "stockholders_equity": 280.0}],
            "annuals": [{"year": 2025, "revenue": 90.0, "ebitda": 20.0, "da": 5.0, "ebit": 15.0,
                         "interest": 1.0, "tax": 3.5, "cash": 10.0, "total_debt": 70.0,
                         "current_assets": 40.0, "current_liabilities": 30.0,
                         "short_term_debt": 10.0}],
            "historical_ev_ebitda": [{"value": 6.0}, {"value": 7.0}, {"value": 8.0}]}
    base.update(extra)
    return base


def test_bridge_takes_cash_and_debt_from_one_balance_sheet():
    # Share count unchanged since FY25: fiscal year-end, so seasonal
    # working capital in an interim balance sheet cannot distort net debt.
    link = SV.bridge(_going_concern(shares=10.0))
    assert (link["cash"], link["debt"]) == (10.0, 70.0)
    assert str(link["valuation_date"]) == "2025-12-31"
    # Shares moved > 5% since year-end (rights issue): latest interim. The
    # official pack has cash but no debt, so both come from the Sectors quarter.
    link = SV.bridge(_going_concern(shares=5.0))
    assert (link["cash"], link["debt"]) == (45.0, 60.0)
    assert str(link["valuation_date"]) == "2026-06-30"
    assert link["nci"] == 20.0 and "2026-06-30" in link["nci_basis"]
    # Official cash and debt together win over the quarter.
    official = _going_concern(shares=5.0)
    official["official_evidence"]["balance_sheet"]["total_debt"] = 55.0
    link = SV.bridge(official)
    assert (link["cash"], link["debt"]) == (30.0, 55.0)


def test_scenario_dcf_keeps_terminal_capex_at_least_depreciation():
    intake = _going_concern(shares=5.0)
    detail, reasons = SV.fcff(intake, _fc(net=8.0, ebitda=0.25, capex=0.02), 0.065, 0.04, 1.1,
                              0.035)
    assert reasons == []
    last = detail["lines"][-1]
    assert last["capex"] < last["da"]               # scenario capex below D&A...
    assert abs(detail["terminal_base"] - (last["fcff"] + last["capex"] - last["da"])) < 1e-9
    assert detail["terminal_fcff"] < last["fcff"] * 1.035   # ...is not capitalised
    assert detail["per_share_down"] < detail["per_share"]
    assert detail["exit_multiple"] == 7.0 and detail["per_share_exit"] is not None
    assert detail["lines"][0]["share"] == 0.5        # H2 only after the 1H balance sheet


def test_scenario_dcf_without_ebitda_or_capex_names_the_gap():
    detail, reasons = SV.fcff(_going_concern(), _fc(), 0.065, 0.04, 1.1, 0.035)
    assert detail is None and "margin EBITDA dan capex" in reasons[0]


def test_method_gate0_holding_primary_survives_the_ramping_gate():
    verdict = MP.evaluate({"domain": "holding_dissimilar", "segments_count": 3,
                           "has_steady_state_3y": False, "life_cycle_stage": "mature"})
    assert verdict.primary == "SOTP"
    assert MC.chain_for(verdict, "going_concern_fcff")[0] == "holding_sotp"
    ramping = MP.evaluate({"domain": "going_concern_fcff", "has_steady_state_3y": False})
    assert ramping.primary == "Relative Valuation"


def test_agent_dcf_drivers_are_soft_for_going_concerns_only():
    source = {"model_profile": "going_concern_fcff",
              "official": {"metrics": {"revenue": 100.0, "net_profit": 5.0}}}
    problems = agent._dcf_field_problems({"h2_revenue_to_h1": 1.0, "h2_net_margin_pct": 5.0},
                                         source)
    assert problems and all(p.endswith(agent.DCF_SOFT) for p in problems)
    below = agent._dcf_field_problems({"h2_revenue_to_h1": 1.0, "h2_net_margin_pct": 5.0,
                                       "fy_ebitda_margin_pct": 2.0,
                                       "fy_capex_to_revenue_pct": 5.0}, source)
    assert any("below the FY net margin" in p for p in below)
    assert agent._dcf_field_problems({}, {"model_profile": "financial_ddm"}) == []
    fragment = {"earnings_scenario": {"h2_revenue_to_h1": 1.0, "fy_ebitda_margin_pct": 90.0,
                                      "fy_capex_to_revenue_pct": 5.0}}
    agent._drop_dcf_fields("earnings", fragment, ["x (dcf)"])
    scenario = fragment["earnings_scenario"]
    assert "fy_ebitda_margin_pct" not in scenario and scenario["h2_revenue_to_h1"] == 1.0
    rows = [{"year": 2027, "ebitda_margin_pct": 3.0, "net_income_margin_pct": 6.0,
             "capex_to_revenue_pct": 5.0}]
    assert any("below the net margin" in p for p in agent._outyear_dcf_problems(rows, source))


def _ammn_lom():
    import glob
    import json
    import os
    from app import forecast, intake, lom
    doc_in, _ = intake.load("AMMN", as_of="2026-09-24")
    plans = sorted(glob.glob(str(ROOT / "data" / "forecast_plans" / "AMMN-*.json")),
                   key=os.path.getmtime)
    plan = json.load(open(plans[-1]))["plan"] if plans else None
    fc = forecast.build(doc_in, assumption_plan=plan)
    return doc_in, fc, lom.build(doc_in, fc)


def test_lom_stays_inside_official_reserves_and_capacities():
    import pytest
    doc_in, _, (res, gaps) = _ammn_lom()
    if res is None:
        pytest.skip(f"AMMN LoM inputs unavailable: {gaps}")
    inp, rows = res["inputs"], res["base"]["rows"]
    bh_mt = sum(r["feed_mt"] for r in rows if r["asset"] == "bh")
    assert bh_mt <= inp["pit_mt"] + inp["stock_mt"] + 1e-6
    assert sum(r["feed_mt"] for r in rows if r["asset"] == "elang") <= inp["elang_mt"]
    for year in {r["year"] for r in rows}:
        cathode = sum(r["cathode_t"] for r in rows if r["year"] == year)
        share = 0.5 if year == 2026 else 1.0
        assert cathode <= inp["smelter_t"] * inp["utilization"] * share + 1e-6
        assert year <= inp["licence_end"]
    assert 0.8 < inp["recovery_cu"] < 1.0 and 0.6 < inp["recovery_au"] < 1.0


def test_lom_value_ties_to_the_sotp_bridge_and_moves_the_right_way():
    import pytest
    from app import lom
    doc_in, _, (res, gaps) = _ammn_lom()
    if res is None:
        pytest.skip(f"AMMN LoM inputs unavailable: {gaps}")
    sotp = lom.sotp_result(doc_in, res)
    assert sotp["status"] == "complete"
    assert abs(sotp["target_price_idr"] - res["per_share"]) < 1e-6
    grid, rate = res["grid"], res["inputs"]["discount"]
    assert grid[(round(rate - 0.02, 3), "base")] > grid[(rate, "base")] > \
        grid[(round(rate + 0.02, 3), "base")]
    assert grid[(rate, "reserve")] < grid[(rate, "down20")] < grid[(rate, "base")] < \
        grid[(rate, "up20")]
    assert res["no_export"] < res["per_share"]
    assert res["per_share_down"] < res["per_share"]
    bridge = lom.operating_bridge(doc_in, res)
    assert not release._check_operating_bridge({"operating_bridge": bridge})


def test_lom_gate_needs_sourced_analyst_assumptions():
    import pytest
    doc_in, fc, (res, gaps) = _ammn_lom()
    if res is None:
        pytest.skip(f"AMMN LoM inputs unavailable: {gaps}")
    stripped = dict(doc_in, analyst_scenario={
        **(doc_in.get("analyst_scenario") or {}),
        "lom_assumptions": {**doc_in["analyst_scenario"]["lom_assumptions"],
                            "broker_source_url": None}})
    gate = release.assess_sotp_lom_scenario(stripped, fc, {"detail": {}}, "validated")
    assert any("dated, traceable source" in b for b in gate["blockers"])


def _ev_peers(*mults):
    return [{"symbol": f"P{i}.JK", "ev_ebitda": m, "ev_status": "ok", "ev_year": 2025,
             "ev_source_kind": "sectors"} for i, m in enumerate(mults)]


def test_scenario_ev_ebitda_peer_bridges_the_median_multiple_to_equity():
    detail, reasons = SV.ev_ebitda_peer(_going_concern(shares=10.0), _fc(ebitda=0.25, capex=0.1),
                                        _ev_peers(6.0, 8.0, 10.0))
    assert reasons == [] and detail["basis"] == "scenario"
    assert detail["peer_source"] == "data Sectors"
    # FY26 EBITDA 25 x median 8 = EV 200; FY25 year-end bridge cash 10, debt 70.
    assert detail["ebitda"] == 25.0 and detail["ev"] == 200.0
    assert (detail["cash"], detail["debt"], detail["nci"]) == (10.0, 70.0, 0.0)
    assert detail["equity"] == 140.0 and detail["per_share"] == 14.0
    assert detail["per_share_down"] == (7.0 * 25.0 + 10.0 - 70.0) / 10.0
    assert detail["per_share_up"] > detail["per_share"] > detail["per_share_down"]
    assert detail["valuation_date"] == "2025-12-31" and detail["grid"] == {}
    assert [p["symbol"] for p in detail["peers"]] == ["P0", "P1", "P2"]


def test_scenario_ev_ebitda_peer_names_each_missing_input():
    _, reasons = SV.ev_ebitda_peer(_going_concern(shares=10.0), _fc(), _ev_peers(6.0, 8.0, 10.0))
    assert reasons == ["margin EBITDA FY skenario belum tersedia dari agen"]
    _, reasons = SV.ev_ebitda_peer(_going_concern(shares=10.0), _fc(ebitda=0.25, capex=0.1),
                                   [{"ev_status": "report_not_cached"}] * 4)
    assert reasons == ["peer EV/EBITDA belum tersedia di cache Sectors "
                       "(0 < 3; laporan Sectors atau snapshot Yahoo 4/4 peer belum tersedia); "
                       "belum dimodelkan"]
    assert SV.ev_ebitda_peer(_going_concern(), {}, _ev_peers(6.0, 8.0, 10.0))[0] is None


def test_ev_ebitda_release_gate_needs_ebitda_three_peers_and_a_bridge():
    detail, _ = SV.ev_ebitda_peer(_going_concern(shares=10.0), _fc(ebitda=0.25, capex=0.1),
                                  _ev_peers(6.0, 8.0, 10.0))
    gate = release.assess_ev_ebitda_scenario(_going_concern(shares=10.0), _fc(ebitda=0.25, capex=0.1),
                                             {"detail": detail}, "validated")
    # Only the earnings-led evidence (official actual, fresh close) is missing here.
    assert not any(b.startswith(("peer PER", "FY earnings", "peer EV/EBITDA", "FY EBITDA",
                                 "enterprise-to-equity", "equity value")) for b in gate["blockers"])
    assert not any("out-year" in b for b in gate["blockers"])   # one forward year suffices
    bad = release.assess_ev_ebitda_scenario(
        {"model_profile": "financial_ddm"}, {}, {"detail": {"ebitda": -1.0, "peer_count": 2,
                                                            "q1_ev_ebitda": 9.0, "median_ev_ebitda": 8.0,
                                                            "q3_ev_ebitda": 10.0, "shares": 10.0,
                                                            "equity": -5.0}}, "validated")
    for text in ("going-concern method", "FY EBITDA scenario is missing or not positive",
                 "peer EV/EBITDA set has fewer than three", "sensitivity is not ordered",
                 "bridge is missing cash", "bridge is missing debt", "equity value is not positive"):
        assert any(text in b for b in bad["blockers"]), text
    assert release.SCENARIO_ASSESSORS["ev_ebitda_peer"] is release.assess_ev_ebitda_scenario
    assert MC.reader_reason("peer EV/EBITDA set has fewer than three valid peers") == \
        "peer EV/EBITDA valid kurang dari tiga"
