"""Version comparison and its exact value bridge."""
import copy

import pytest

from app import reference_fcff, revision
from tests.test_operating_model import _drivers

VAL = {"wacc": 0.10, "g": 0.03, "valuation_date": "2026-06-30", "terminal_ronic": 0.15,
       "cash": 100.0, "debt": 100.0, "nci": None, "distributions": 0.0, "shares": 10.0,
       "to_idr": 1.0, "parent_share": 1.0}


def _doc(drivers, val, tp):
    return {"meta": {"status": "distributable", "rating": "Buy", "tp": tp},
            "model_inputs": {"kind": "operating", "drivers": drivers, "valuation": val},
            "run_manifest": {"as_of": "2026-09-26"}}


def test_the_value_bridge_attributes_every_rupiah_to_an_input_group():
    before = _doc(_drivers(), dict(VAL), 100)
    later = _drivers()
    later["segments"][0]["volume_growth_pct"]["values"] = [12, 12, 12, 12]   # assumption
    # Actual: a higher 1H realized price (1H capex is already in the 30 June PP&E).
    later["segments"][0]["h1_revenue"] = 110.0
    after = _doc(later, {**VAL, "wacc": 0.105, "shares": 11.0}, 90)
    result = revision.compare(before, after)
    assert {c["field"] for c in result["changes"]} == {"tp"}
    bridge = result["value_bridge"]
    assert bridge["status"] == "decomposed"
    groups = {s["group"]: s["change"] for s in bridge["steps"]}
    assert groups["Tingkat diskonto dan terminal"] < 0
    assert groups["Jumlah saham"] < 0
    assert groups["Asumsi driver ke depan"] > 0
    assert groups["Aktual resmi dan saldo awal"] > 0
    assert groups["Kurs"] == 0 and groups["Jembatan neraca"] == 0
    assert bridge["start"] == pytest.approx(reference_fcff.value(_drivers(), **VAL)["per_share"])
    assert bridge["start"] + sum(groups.values()) == pytest.approx(bridge["end"])
    assert bridge["residual"] == pytest.approx(0.0, abs=1e-9)


def test_versions_without_comparable_inputs_are_listed_not_decomposed():
    result = revision.compare({"meta": {"tp": 1}}, {"meta": {"tp": 2}})
    assert result["value_bridge"]["status"] == "not_decomposed"
    assert result["changes"] == [{"field": "tp", "previous": 1, "current": 2}]
