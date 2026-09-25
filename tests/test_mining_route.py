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
    assert doc["meta"]["rating"] in {
        "Di atas harga pasar", "Setara harga pasar", "Di bawah harga pasar"}
    assert doc["meta"]["tp"]
    # The branch that raised NameError builds this table from the sales bridge;
    # it is audit detail, kept in the report's audit appendix, not printed.
    audit = {e["judul"] for p in doc.get("lampiran_audit") or [] for e in p["exhibit"]}
    assert "Volume penjualan dan net realized price per logam" in audit
    assert "Volume penjualan dan net realized price per logam" not in {e["judul"] for e in doc["exhibits"]}
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


def test_ammn_lom_grid_has_five_rate_steps_and_chart_four_reads_the_mine_plan(tmp_path):
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    grid = next(e for e in doc["exhibits"] if e["judul"].startswith("Sensitivitas SOTP/LoM"))
    rows = grid["data"]["rows"]
    assert len(rows) == 5 and "(basis)" in rows[2][0]
    base = grid["data"]["cols"].index("Dek dasar")
    assert rows[2][base] == f"Rp{doc['meta']['tp']:,}".replace(",", ".")
    chart = next(e for e in doc["exhibits"] if e["judul"].startswith("Produksi tembaga"))
    series = chart["data"]["series"][0]
    # FY2024/FY2025 from the issuer's annual operations; FY26F = 1H actual +
    # the LoM's 2H, which equals the FY2026 guidance (485 Mlbs).
    assert series["bars"][:2] == [395.0, 209.0] and round(series["bars"][2]) == 485
    assert all(v is not None for v in series["bars"][2:])
    # The line: Adjusted C1 for actual years, the LoM cash cost after the gold
    # credit for full forecast years; FY26F is a part year in the schedule.
    assert series["line"][2] is None and all(v is not None for v in series["line"][3:])
    assert "biaya tunai setahun penuh per pon tidak dihitung" in chart["narasi"]
    assert "bukan Adjusted C1" in chart["catatan_sumber"]
