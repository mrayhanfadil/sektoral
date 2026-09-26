"""The mining LoM against its independent reference, and its production route."""
import pytest

from app import forecast, intake, lom, reference_lom


def _inputs():
    doc, _ = intake.load("AMMN", as_of="2026-09-26")
    inp, gaps = lom.inputs(doc, {"interim_scenario": None})
    # Dated rates and FX are pinned per run; a fixed rate is enough to compare engines.
    inp = {**inp, "discount": 0.10}
    bridge = {"cash": 2.0e13, "debt": 6.0e13, "minority": 1.0e12, "shares": 72412413856}
    return doc, inp, bridge, gaps


@pytest.mark.parametrize("kw", [{}, {"export": True}, {"export": False}, {"risk": 1.0},
                                {"rate": 0.12}])
def test_the_reference_rebuilds_the_lom_value_on_every_branch(kw):
    _, inp, bridge, _ = _inputs()
    production = lom.value(inp, bridge, 16900.0, **kw)["per_share"]
    reference = reference_lom.value(inp, bridge, 16900.0, **kw)["per_share"]
    assert reference == pytest.approx(production, rel=1e-9)


def test_a_disagreeing_reference_is_reported_as_such():
    _, inp, bridge, _ = _inputs()
    production = lom.value(inp, bridge, 16900.0)["per_share"]
    assert reference_lom.compare(inp, bridge, 16900.0, production * 1.02)["status"] == "differs"


def test_a_lom_with_input_gaps_stays_off_the_physical_forecast_route():
    doc, _, _, gaps = _inputs()
    assert gaps  # no pinned UST/FX in a bare intake: the discount rate is a gap
    fc = forecast.build(doc)
    assert fc["forecast_basis"] != "physical_driver_forecast"
    assert fc["production_ready"] is False


def test_working_capital_is_modelled_and_lowers_value_against_book_inventory():
    _, inp, bridge, _ = _inputs()
    assert inp["wc"] and inp["wc"]["advance_unwind"]
    with_wc = lom.value(inp, bridge, 16900.0)["per_share"]
    assert reference_lom.value(inp, bridge, 16900.0)["per_share"] == pytest.approx(with_wc, rel=1e-9)
    no_advance = {**inp, "wc": {**inp["wc"], "advance_unwind": {}}}
    # Settling the customer advance in product is a cash outflow the reference also carries.
    assert lom.value(no_advance, bridge, 16900.0)["per_share"] > with_wc
    assert reference_lom.value(no_advance, bridge, 16900.0)["per_share"] == pytest.approx(
        lom.value(no_advance, bridge, 16900.0)["per_share"], rel=1e-9)


def test_the_elang_probability_is_the_documented_two_gate_assumption():
    _, inp, _, _ = _inputs()
    assert inp["elang_risk"] == pytest.approx(0.65)
