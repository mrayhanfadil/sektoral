"""Published mining route (FY EV/EBITDA on the validated interim scenario).

The fixture is AMMN's validated live plan of 2026-09-24. Before this test the
route had no coverage and crashed on an undefined name once a scenario
validated.
"""
import json
from pathlib import Path

from app import build, commodity, fx, rates, store

FIXTURES = Path(__file__).parent / "fixtures"
PLAN = json.loads((FIXTURES / "ammn_interim_plan.json").read_text())
# Yahoo HG=F closes to 2026-09-24: the Sectors copper series ends 2026-02-15.
COPPER = json.loads((FIXTURES / "commodity_prices.json").read_text())["Copper"]
# The tests' own database has no USD/IDR quote; the route needs one within
# seven days of the Report Date (Yahoo IDR=X close, 23 Sep 2026).
USD_IDR = {"pair": "USD/IDR", "rate": 17805.0, "date": "2026-09-23",
           "source": "Yahoo Finance IDR=X daily close"}
# The LoM discounts in US$ at UST 10Y + CRP + beta x ERP: the dated UST close.
UST_10Y = {"name": "UST10Y", "symbol": "^TNX",
           "source": "Yahoo Finance ^TNX daily close (imbal hasil US Treasury 10 tahun)",
           "rows": [{"date": "2026-09-24", "yield_pct": 5.162}]}


def test_ammn_publishes_on_the_validated_interim_scenario(tmp_path):
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    assert doc["meta"]["status"] == "distributable_assumption_led"
    assert doc["harness"]["blockers"] == []
    assert doc["meta"]["rating"] in {"Buy", "Hold", "Sell"} and doc["meta"]["tp"]
    titles = {e["judul"] for e in doc["exhibits"]}
    # The branch that raised NameError builds this table from the sales bridge.
    assert "Volume penjualan dan net realized price per logam" in titles
    text = " ".join(p["isi"] for p in doc["cover"]["paragraf"])
    assert "Q4 2027" not in text and "Risiko utama:" in text


def test_ammn_skips_the_lom_on_a_stale_copper_deck(tmp_path):
    """Without a copper series within 45 days of the Report Date the LoM has
    no current price to value the mine at: the chain skips SOTP/LoM for the
    missing input (spec §4.1) instead of pricing the mine at February's deck."""
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    assert "SOTP/LoM tidak memadai" in doc["method"]
    assert "cu_price_stale" in json.dumps(doc, ensure_ascii=False)


def test_ammn_deck_is_the_fresh_series_average(tmp_path):
    store.put(commodity.COLLECTION, "Copper", COPPER)
    from app import mineops
    cu = mineops.load("AMMN", "2026-09-24")["cu_price"]
    assert cu["source"] == "yahoo" and cu["window"] == ["2025-10", "2026-09"]
    assert cu["replaced"]["date"] == "2026-02-15"
    assert 12_500 < cu["avg12"] < 13_500
