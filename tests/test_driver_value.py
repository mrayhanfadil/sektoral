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


def test_decision_summary_reads_the_price_and_the_rating_band_from_the_tested_range():
    from app import decision_summary as S
    row = {"driver": "Volume", "unit": "±1 pp per tahun", "low": "turun", "high": "naik",
           "value_effect_low": -100.0, "value_effect_high": 100.0}
    fraction, word = S._move_to(row, 700.0, 1000.0)
    assert (fraction, word) == (3.0, "turun")
    assert S._step_text(row, (fraction, word)) == "Volume turun 3,0 pp per tahun"
    cost = {**row, "driver": "Biaya", "unit": "±2% level biaya", "low": "naik", "high": "turun"}
    assert S._step_text(cost, S._move_to(cost, 800.0, 1000.0)) == "Biaya naik 4,0% level biaya"
    # 9M26 is the next filing once 1H26 is out; its OJK deadline is a month after quarter end.
    assert S.next_filing("2026-09-26", "2026-06-30") == {
        "label": "9M26", "period_end": "2026-09-30", "deadline": "2026-10-31"}


def test_driver_figures_are_written_in_the_reports_indonesian_form():
    """The Indonesian document carries 8,5 and US$13.002; the English edition
    localizes them (fmt.localize), so neither language shows the other's form."""
    from app import fmt
    assert DV._path([8.5, 8.5, 8.0, 8.0]) == "8,5/8,5/8/8%"
    assert DV._path([3.1, 3.0, 2.25]) == "3,1/3/2,25%"
    assert fmt.localize(DV._path([5, 4.5, 4, 3.5]), "en") == "5/4.5/4/3.5%"


def test_the_mining_deck_and_discount_rate_use_the_report_format(monkeypatch):
    from app import fmt, reference_lom
    monkeypatch.setattr(reference_lom, "value", lambda *a, **k: {"per_share": 1000.0})
    inp = {"cu_price": 13002.4, "au_price": 4455.0, "discount": 0.107, "elang_risk": 0.65,
           "utilization": 0.9}
    base = {r["driver"]: r["base"] for r in DV.mining(inp, {}, 17837.3)["rows"]}
    assert base["Harga tembaga"] == "US$13.002/t" and base["Harga emas"] == "US$4.455/oz"
    assert base["Tingkat diskonto US$"] == "10,7%"
    assert fmt.localize(base["Harga tembaga"], "en") == "US$13,002/t"
    assert fmt.localize(base["Tingkat diskonto US$"], "en") == "10.7%"


def test_the_case_table_rounds_to_the_tick_like_the_target_price():
    """The base case reads as the cover: AMMN's model value Rp3.487,8 is the
    Rp3.490 target, -26,2% against Rp4.730, not Rp3.488 and -26,3%."""
    from app import report_extras as RX
    row = {"driver": "Harga tembaga", "basis": "asumsi analis", "years": "LoM",
           "base": "US$13.002/t", "unit": "±10%", "fy1_profit_low": None,
           "value_effect_low": -418.0, "value_effect_high": 418.0}
    doc = {"driver_value": {"rows": [row], "method": "LoM", "cases": {
        "downside": {"per_share": 2211.4}, "base": {"per_share": 3487.8},
        "upside": {"per_share": 5168.1}}}}
    page = RX.driver_value_page(doc, {"price": 4730.0})
    cases = page["exhibit"][1]["data"]["rows"]
    assert [r[:3] for r in cases] == [["Turun", "Rp2.210", "-53,3%"],
                                      ["Dasar", "Rp3.490", "-26,2%"],
                                      ["Naik", "Rp5.175", "+9,4%"]]
    assert "dibulatkan ke fraksi harga seperti target" in page["exhibit"][1]["catatan_sumber"]
