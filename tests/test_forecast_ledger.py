"""Frozen forecasts scored against declared baselines."""
import pytest

from app import forecast_ledger as L, outputs


def _intake():
    return {"as_of": "2026-09-26",
            "official_evidence": {"reporting_currency": "IDR",
                                  "annual_actuals": [{"year": 2025, "revenue": 900.0,
                                                      "net_profit_attributable": 90.0}]},
            "latest_official_actual": {"period": "1H26", "published_at": "2026-07-31",
                                       "metrics": {"revenue": 500.0, "net_profit_attributable": 50.0}}}


def _fc():
    return {"earnings_scenario": {"year": 2026, "full_year": {"revenue": 1020.0,
                                                               "net_profit_attributable": 104.0}},
            "outyear_scenario": {"rows": [{"year": 2027, "revenue": 1100.0,
                                           "net_profit_attributable": 112.0}]}}


def test_the_record_carries_the_forecast_and_both_declared_baselines():
    rec = L.record(_intake(), _fc())
    assert [y["year"] for y in rec["years"]] == [2026, 2027]
    assert rec["baselines"]["last_fy"]["net_profit_attributable"] == 90.0
    assert rec["baselines"]["run_rate"]["net_profit_attributable"] == 100.0


def test_a_material_fiscal_year_error_raises_a_review_task_and_is_compared_with_baselines():
    rec = L.record(_intake(), _fc())
    result = L.evaluate(rec, {"period": "FY2026", "revenue": 1000.0, "net_profit_attributable": 95.0})
    model = result["model"]["net_profit_attributable"]
    assert model["pct"] == pytest.approx(9 / 95)
    assert result["material"] and "melewati materialitas" in result["review_task"]
    assert result["baselines"]["run_rate"]["net_profit_attributable"]["pct"] == pytest.approx(5 / 95)
    close = L.evaluate(rec, {"period": "FY2026", "net_profit_attributable": 102.0})
    assert close["material"] is False and close["review_task"] is None


def test_an_interim_result_is_tracking_not_a_forecast_error():
    rec = L.record(_intake(), _fc())
    result = L.evaluate(rec, {"period": "9M26", "net_profit_attributable": 72.0,
                              "prior_year_share_of_fy": 0.72})
    assert result["status"] == "tracking" and result["implied_fy"] == pytest.approx(100.0)
    assert L.evaluate(rec, {"period": "FY2031", "net_profit_attributable": 1})["status"] == "outside_horizon"


def test_freeze_is_once_per_publication(tmp_path):
    outputs.save(outputs.REPORT, tmp_path, "UJIA", {"meta": {"status": "distributable"},
                                                   "forecast_record": L.record(_intake(), _fc())})
    outputs.save(outputs.MANIFEST, tmp_path, "UJIA", {"publication_id": "pub-1"})
    key = L.freeze(tmp_path, "UJIA")
    assert key == "UJIA:2026-09-26:pub-1"
    assert L.freeze(tmp_path, "UJIA") is None      # append-only: never overwritten
    assert [r["publication_id"] for r in L.frozen_records("UJIA")] == ["pub-1"]
