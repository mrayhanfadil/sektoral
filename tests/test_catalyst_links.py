"""Checkpoint 4: catalysts name a model driver and a thesis-change threshold;
unanswered business-quality dimensions carry a reason."""
from app import driver_value, investability, report_extras as RX


def _driver(name, base, low_effect, high_effect, unit="±1 pp"):
    return {"driver": name, "base": base, "low": "turun", "high": "naik", "unit": unit,
            "value_effect_low": low_effect, "value_effect_high": high_effect}


def _doc(drivers, rating="Buy", tp=1300):
    return {"meta": {"rating": rating, "tp": tp},
            "driver_value": {"rows": drivers, "cases": {"base": {"per_share": tp}}},
            "bagian": [{"judul": "Katalis", "exhibit": [{
                "judul": RX.CATALYST_TITLE, "catatan_sumber": "Sumber: rilis.",
                "data": {"cols": ["Katalis", "Waktu", "Jalur", "Arah"], "rows": [
                    ["Biaya kredit naik ke 3,1%", "H2, rilis data center", "Provisi naik -> laba turun", "Negatif"],
                    ["Net sell asing", "Sep", "Sentimen pasar", "Negatif"]]}}]}]}


def test_a_catalyst_names_its_driver_and_the_move_that_changes_the_rating():
    doc = _doc([{**_driver("Biaya kredit", "3,1%", -100, 100, "±20 bp"), "low": "naik",
                 "high": "turun"},
                _driver("Pertumbuhan kredit", "9%", -50, 50)])
    RX.link_catalysts(doc, {"price": 1000.0})
    ex = doc["bagian"][0]["exhibit"][0]
    assert ex["data"]["cols"][-2:] == ["Driver model", "Ambang perubahan tesis"]
    credit, flows = ex["data"]["rows"]
    assert credit[4].startswith("Biaya kredit") and "rating menjadi Hold" in credit[5]
    assert flows[4].startswith("tidak terhubung") and "di bawah Rp1.150 menjadi Hold" in flows[5]


def test_an_assumption_led_report_states_its_value_band():
    doc = _doc([], rating="Sell", tp=800)
    doc["driver_value"] = None
    RX.link_catalysts(doc, {"price": 1000.0})
    row = doc["bagian"][0]["exhibit"][0]["data"]["rows"][0]
    assert row[4].startswith("laporan tanpa tabel") and "di atas Rp900 menjadi Hold" in row[5]


def test_the_holding_driver_table_moves_prices_and_land():
    land = {"inputs": {"gross_ha": 100.0, "net_ratio": 0.65, "pace_ha": 20.0, "asp": 2e6,
                       "asp_growth": 0.02, "cash_margin": 0.5, "carrying_idr": 5e11,
                       "stake": 0.635}, "rate": 0.109}
    detail = {"components": [{"ticker": "NRCA", "stake": 0.64, "market_cap": 1.3e12,
                              "book_equity": 1.36e12}],
              "parent_equity": 5.78e12, "shares": 4.7e9, "landbank": land}
    table = driver_value.holding(detail)
    names = [r["driver"] for r in table["rows"]]
    assert any(n.startswith("Harga saham anak usaha") for n in names) and len(names) == 5
    cases = table["cases"]
    assert cases["downside"]["per_share"] < cases["base"]["per_share"] < cases["upside"]["per_share"]


def test_unanswered_dimensions_carry_a_reason(tmp_path):
    rows = investability.business_quality("UJIA", "2026-09-26", root=tmp_path)
    governance = next(r for r in rows if r["dimension"] == "governance")
    assert "D8" in governance["reason"]
    assert all(r["reason"] for r in rows if r["status"] == "unanswered")


def test_a_move_far_outside_the_tested_range_does_not_count():
    from app import decision_summary as D
    row = _driver("Probabilitas pengembangan", "65%", -100, 100, "±25 pp")
    assert D._move_to(row, 1500, 1000) == (5.0, "naik")
    assert D._move_to(row, 1600, 1000) is None  # 6 steps: a probability past 100%


def test_a_bounded_driver_cannot_pass_its_range():
    from app import decision_summary as D
    row = {**_driver("Utilisasi", "93%", -100, 100, "±5 pp"), "max_steps_high": 1.4}
    assert D._move_to(row, 1100, 1000) is not None
    assert D._move_to(row, 1200, 1000) is None  # 2 steps = 103%
