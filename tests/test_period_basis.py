"""Cumulative interim periods versus standalone quarters and halves."""
import pytest

from app import period_basis as P, scenario_value


def _fig(value, scope="consolidated", unit="million", currency="IDR"):
    return {"value": value, "currency": currency, "unit": unit, "scope": scope}


@pytest.mark.parametrize("label,months,basis,quarter", [
    ("1H26", 6, "cumulative", 2), ("H1 2026", 6, "cumulative", 2),
    ("9M26", 9, "cumulative", 3), ("Q1 2026", 3, "cumulative", 1),
    ("FY2025", 12, "cumulative", 4), ("Q2 2026 (derived)", 3, "standalone", 2),
    ("3Q26", 3, "standalone", 3), ("H2 2025", 6, "standalone", 4),
])
def test_labels_carry_months_and_basis(label, months, basis, quarter):
    parsed = P.parse(label)
    assert (parsed["months"], parsed["basis"], parsed["quarter"]) == (months, basis, quarter)


def test_non_financial_period_labels_are_not_guessed():
    assert P.parse("June 2026") is None and P.parse("2026-06-P1") is None


def test_scenario_value_keeps_cumulative_months_only():
    assert scenario_value._period_months("1H26") == 6
    assert scenario_value._period_months("Q1 2026") == 3
    assert scenario_value._period_months("Q2 2026") is None
    assert scenario_value._period_months("H2 2025") is None


def test_standalone_quarters_subtract_the_preceding_cumulative_period():
    figures = {"Q1 2026": _fig(100.0), "1H26": _fig(250.0), "9M26": _fig(390.0),
               "FY2026": _fig(560.0)}
    assert P.standalone_quarter(figures, 1, 2026)["value"] == 100.0
    q2 = P.standalone_quarter(figures, 2, 2026)
    assert q2["value"] == 150.0 and q2["derivation"] == "1H26 minus Q1 2026"
    assert P.standalone_quarter(figures, 3, 2026)["value"] == 140.0
    assert P.standalone_quarter(figures, 4, 2026)["value"] == 170.0
    assert P.second_half(figures, 2026)["value"] == 310.0


def test_other_fiscal_years_are_ignored_and_missing_periods_fail():
    figures = {"Q1 2025": _fig(90.0), "1H26": _fig(250.0)}
    with pytest.raises(ValueError, match="3-month"):
        P.standalone_quarter(figures, 2, 2026)


def test_scope_currency_or_unit_mismatch_never_subtracts():
    with pytest.raises(ValueError, match="scope"):
        P.standalone_quarter({"Q1 2026": _fig(100.0, scope="parent"), "1H26": _fig(250.0)}, 2, 2026)
    with pytest.raises(ValueError, match="unit"):
        P.second_half({"1H26": _fig(250.0, unit="billion"), "FY2026": _fig(560.0)}, 2026)
    with pytest.raises(ValueError, match="scope must be"):
        P.standalone_quarter({"Q1 2026": _fig(100.0, scope="group")}, 1, 2026)


def test_growth_compares_like_with_like_only():
    assert P.comparable_growth("1H26", _fig(110.0), "1H25", _fig(100.0)) == pytest.approx(0.10)
    assert P.comparable_growth("1H26", _fig(-50.0), "1H25", _fig(-100.0)) == pytest.approx(0.5)
    assert P.comparable_growth("1H26", _fig(5.0), "1H25", _fig(0.0)) is None
    with pytest.raises(ValueError, match="different periods"):
        P.comparable_growth("1H26", _fig(110.0), "Q1 2025", _fig(100.0))
    with pytest.raises(ValueError, match="different periods"):
        P.comparable_growth("Q2 2026", _fig(110.0), "Q1 2026", _fig(100.0))
    with pytest.raises(ValueError, match="scope"):
        P.comparable_growth("1H26", _fig(110.0, scope="parent"), "1H25", _fig(100.0))
