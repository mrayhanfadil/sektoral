"""Driver-to-value table and investability, on synthetic and real inputs."""
import copy
from datetime import date

import pytest

from app import driver_value as DV, investability as INV
from tests.test_operating_model import _drivers

DETAIL = {"wacc": 0.10, "g": 0.03, "valuation_date": date(2026, 6, 30), "cash": 100.0,
          "debt": 100.0, "nci": None, "distributions": 0.0, "shares": 10.0, "fx": 1.0,
          "attributable_share": 1.0, "terminal_ronic": 0.15}


def test_each_driver_moves_value_in_its_stated_direction_and_cases_bracket_the_base():
    result = DV.operating(_drivers(), DETAIL)
    by_name = {r["driver"]: r for r in result["rows"]}
    volume = by_name["A: pertumbuhan volume"]
    assert volume["value_effect_low"] < 0 < volume["value_effect_high"]
    assert volume["fy1_profit_low"] == pytest.approx(0.0)  # growth starts in FY2
    fuel = by_name["Bahan bakar: biaya per unit"]
    assert fuel["value_effect_low"] < 0 < fuel["value_effect_high"]
    cases = result["cases"]
    assert cases["downside"]["per_share"] < cases["base"]["per_share"] < cases["upside"]["per_share"]
    # Rows are ordered by their largest value effect.
    effects = [max(abs(r["value_effect_low"]), abs(r["value_effect_high"])) for r in result["rows"]]
    assert effects == sorted(effects, reverse=True)


def test_a_passed_through_cost_is_offset_by_the_linked_tariff():
    plain = DV.operating(_drivers(), DETAIL)
    linked = _drivers()
    linked["pass_through"] = [{"cost": "fuel", "segments": ["a", "b"], "share": 1.0}]
    offset = DV.operating(linked, DETAIL)
    fuel = lambda r: next(x for x in r["rows"] if x["driver"].startswith("Bahan bakar"))  # noqa: E731
    assert abs(fuel(offset)["value_effect_low"]) < abs(fuel(plain)["value_effect_low"]) / 10


def test_liquidity_states_its_window_and_position_assumptions(monkeypatch):
    rows = [{"date": f"2026-07-{d:02d}", "close": 1000, "volume": 1_000_000} for d in range(1, 31)]
    monkeypatch.setattr(INV.cache, "first", lambda key: {"data": rows})
    liq = INV.liquidity("XXXX", "2026-07-20")
    assert liq["sessions"] == 20 and liq["end"] == "2026-07-20"   # nothing after the Report Date
    assert liq["median_value"] == 1e9
    first = liq["positions"][0]
    assert first["days"] == pytest.approx(10e9 / (0.2 * 1e9))
    assert INV.liquidity("XXXX", "2026-07-10")["status"] == "unavailable"


def test_business_quality_answers_only_dated_evidence(tmp_path):
    import json
    (tmp_path / "XXXX.json").write_text(json.dumps({"dimensions": {
        "pricing_power": {"assessment": "Formula tarif meneruskan biaya.", "model_effect": "x",
                          "evidence": [{"title": "t", "url": "https://x.example/a",
                                        "published_at": "2026-07-31", "page": "1"}]},
        "governance": {"assessment": "Tanpa bukti.", "evidence": []}}}))
    result = {i["dimension"]: i for i in INV.business_quality("XXXX", "2026-09-26", root=tmp_path)}
    assert result["pricing_power"]["status"] == "answered"
    assert result["governance"]["status"] == "unanswered"
    assert result["competitive_position"]["status"] == "unanswered"
    # Evidence published after the Report Date does not answer the dimension.
    later = INV.business_quality("XXXX", "2026-07-01", root=tmp_path)
    assert all(i["status"] == "unanswered" for i in later)
