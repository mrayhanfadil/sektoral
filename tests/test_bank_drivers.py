"""Sourced bank driver files: validation, the sourced model path and its independent reference."""
import copy

import pytest

from app import bank_drivers as BD, bank_model, intake, reference_ddm


def _bbri():
    data = BD.load("BBRI", "2026-09-26")
    assert data is not None
    return data


def _project(data, **kw):
    doc, _ = intake.load("BBRI", as_of="2026-09-26")
    return doc, bank_model.project(
        doc["bank_history"], doc["latest_official_actual"],
        doc["official_evidence"]["balance_sheet"], BD.model_drivers(data), payout=doc["payout"],
        payout_basis=doc["payout_basis"], shares=doc["shares"], official_inputs=data, **kw)


def test_the_bbri_file_is_complete_and_its_balances_tie():
    assert BD.validate(_bbri()) == []


def test_broken_balances_unsourced_guidance_or_missing_requirement_fail_closed():
    data = _bbri()
    broken = copy.deepcopy(data)
    broken["h1_close"]["current_account"] += 1e9
    assert any("deposit types do not add up" in e for e in BD.validate(broken))
    broken = copy.deepcopy(data)
    broken["drivers"][0]["nim_pct"]["source_refs"] = []
    assert any("must cite sources" in e for e in BD.validate(broken))
    broken = copy.deepcopy(data)
    broken["drivers"][2]["cost_of_credit_pct"]["rationale"] = ""
    assert any("needs a rationale" in e for e in BD.validate(broken))
    broken = copy.deepcopy(data)
    del broken["capital_requirement"]["value"]
    assert any("capital_requirement" in e for e in BD.validate(broken))
    broken = copy.deepcopy(data)
    broken["h1"]["tax"] += 1e9
    assert any("pre-tax profit - tax" in e for e in BD.validate(broken))


def test_the_sourced_model_uses_official_lines_and_the_regulatory_floor():
    data = _bbri()
    _, model = _project(data)
    assert model["checks"]["ok"]
    assert model["anchor"]["split"]["operating_expense"] == data["h1"]["operating_expense"]
    assert model["constraints"]["car_floor"] == pytest.approx(0.14)
    first = model["rows"][0]
    # FY = official 1H + modelled H2, and every year holds the regulatory floor.
    assert first["earnings"] == pytest.approx(
        data["h1"]["net_profit_attributable"] + model["h2"]["net_profit_attributable"])
    assert all(r["capital_adequacy_ratio"] >= 0.14 for r in model["rows"])
    assert [r["payout"] for r in model["rows"]] == data["payout_path"]["values"]


def test_the_closed_form_reference_rebuilds_the_production_profit_path():
    data = _bbri()
    _, model = _project(data)
    rows = reference_ddm.path(data, model["prior_parent_profit"], model["first_payout"])
    for ref, prod in zip(rows, model["rows"]):
        assert ref["parent"] == pytest.approx(prod["earnings"], rel=1e-9)
        assert ref["roe"] == pytest.approx(prod["roe"], rel=1e-9)


def test_a_binding_capital_floor_is_not_compared_silently():
    data = copy.deepcopy(_bbri())
    data["capital_requirement"]["value"] = 0.199  # above the projected CAR
    _, model = _project(data)
    assert model["constraints"]["applied"]
    result = reference_ddm.compare(data, {"coe": 0.11, "g": 0.035, "valuation_date": "2026-06-30",
                                          "shares": 1.0, "per_share": 1.0}, model, 1.0, 0.5)
    assert result["status"] == "not_comparable"


def test_a_file_published_after_the_report_date_is_not_known():
    assert BD.load("BBRI", "2026-08-30") is None
