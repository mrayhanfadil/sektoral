"""Test minimal 5-year forecast horizon across intake, forecast, valuation, narrative, and valtables."""
import pytest
from pathlib import Path
from app import intake, forecast, valuation, valtables

ROOT = Path(__file__).resolve().parent.parent


def test_forecast_horizon_is_minimal_5y():
    doc_in, g1 = intake.load("BBCA")
    fc = forecast.build(doc_in)
    rows = fc["rows"]
    assert len(rows) >= 5, f"Expected at least 5 forecast years, got {len(rows)}"
    
    # Assert sequential labels
    base_year = doc_in["annuals"][-1]["year"]
    expected_years = [base_year + 1 + i for i in range(len(rows))]
    actual_years = [r["year"] for r in rows]
    assert actual_years == expected_years
    
    # Assert accounting identities hold across all years
    assert fc["g2"]["G2.5_neraca"] == "lolos"
    assert fc["g2"]["G2.6_variasi"] == "lolos"
    assert fc["g2"]["G2.4_konsistensi"] == "lolos"
    
    # Revenue should grow or differ across consecutive years
    for i in range(len(rows) - 1):
        assert rows[i]["revenue"] != rows[i + 1]["revenue"]


def test_forecast_explicit_n_years_arg():
    doc_in, _ = intake.load("BBCA")
    # n_years < 5 should clamp to minimal 5
    fc3 = forecast.build(doc_in, n_years=3)
    assert len(fc3["rows"]) == 5
    
    # n_years >= 5 should be respected
    fc7 = forecast.build(doc_in, n_years=7)
    assert len(fc7["rows"]) == 7


def test_valuation_core_5y_discounting():
    doc_in, _ = intake.load("BBCA")
    fc = forecast.build(doc_in)
    val = valuation.build(doc_in, fc)
    assert "5 tahun" in val["method"] or f"{len(fc['rows'])} tahun" in val["method"]
    assert val["pv_explicit"] > 0
    assert val["pv_terminal"] > 0


def test_fcff_exhibit_has_5_forecast_columns():
    doc_in, _ = intake.load("BBCA")
    fc = forecast.build(doc_in)
    val = valuation.build(doc_in, fc)
    ex = valtables.fcff_exhibit(doc_in, fc, val)
    cols = ex["data"]["cols"]
    # cols = ["Uraian"] + 5 forecast year labels + ["Terminal / Total"] = 7 columns
    assert len(cols) == len(fc["rows"]) + 2
    for r in ex["data"]["rows"]:
        assert len(r) == len(cols)


def test_forecast_and_exhibits_carry_5y_horizon():
    doc_in, _ = intake.load("BBCA")
    fc = forecast.build(doc_in)
    val = valuation.build(doc_in, fc)
    ex = valtables.fcff_exhibit(doc_in, fc, val)
    cols = ex["data"]["cols"]
    f_cols = [c for c in cols if str(c).endswith("F")]
    assert len(f_cols) >= 5, f"Expected at least 5 forecast columns, got {f_cols}"
