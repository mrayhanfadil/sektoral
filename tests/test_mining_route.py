"""Published mining route (FY EV/EBITDA on the validated interim scenario).

The fixture is AMMN's validated live plan of 2026-09-24. Before this test the
route had no coverage and crashed on an undefined name once a scenario
validated.
"""
import json
import re
from pathlib import Path

from app import build, commodity, fmt, fx, prose_lang, rates, server, store

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
    assert doc["meta"]["model_profile"] == "finite_life_mining"
    assert doc["harness"]["blockers"] == []
    assert doc["meta"]["rating"] in {"Buy", "Hold", "Sell"} and doc["meta"]["tp"]
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


_URL = re.compile(r"https?://\S+")


def test_ammn_audit_appendix_has_english_for_its_template_text(tmp_path):
    """The trace page's audit appendix (the FY26 H2 reconstruction): every
    paragraph and source note has an English twin with no Indonesian clause,
    every table cell an English label; document names and page numbers are
    kept ("hlm." becomes "p.")."""
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    pages = server._audit_appendix(doc)
    exhibits = [e for page in pages for e in page["exhibits"]]
    assert len([e for e in exhibits if e["note"]]) >= 20
    for page in pages:
        for indonesian, english in zip(page["paragraphs"], page["paragraphs_en"]):
            assert english, indonesian[:120]
            assert not prose_lang.indonesian_words(_URL.sub("", english)), english
    for exhibit in exhibits:
        if exhibit["note"]:
            assert exhibit["note_en"], exhibit["note"][:120]
            assert not prose_lang.indonesian_words(_URL.sub("", exhibit["note_en"])), \
                exhibit["note_en"]
            assert "hlm." not in exhibit["note_en"]
        for row in exhibit["rows_en"]:
            for cell in row:
                assert not prose_lang.indonesian_words(cell), cell
    notes = " ".join(e["note_en"] for e in exhibits if e["note_en"])
    assert "AMMAN H1 2026 Earnings Release, pp. 3-4" in notes
    assert "Note 2.s p. 40 and Note 30.a.ii p. 113" in notes
    cells = {cell for e in exhibits for row in e["rows_en"] for cell in row}
    assert "Q1 to H1 difference; both source figures rounded to US$ mn" in cells
    assert any(cell.startswith("Detailed financial statement figure; it includes the US$")
               for cell in cells)
    assert any(cell.startswith("Against detailed long-term principal repayments of US$")
               for cell in cells)


# Two sentences run together: a full stop straight into the next sentence.
_RUN_ON = re.compile(r"[a-z)]\.[A-Z][a-z]")


def test_ammn_prose_describes_the_escalated_deck_the_lom_runs(tmp_path):
    """Since the LoM escalates the deck, costs and capex with US inflation, the
    target-price paragraph and the methodology note say so, at the model's own
    rate, in both languages; nothing says the deck is held flat (#50)."""
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    inputs = doc["model_inputs"]["inputs"]
    assert inputs["escalation"] > 0
    rate = fmt.pct(inputs["escalation"])
    paragraph = next(p for p in doc["cover"]["paragraf"] if "memakai SOTP/LoM" in p["isi"])
    note = next(n for n in doc["catatan_metodologi"] if n.startswith("Dek harga"))
    for text in (paragraph["isi"], note):
        assert f"menjadi dek 2026 dan sesudahnya dieskalasi {inputs['escalation_basis']}" in text
        assert "bersama biaya dan capex" in text and "datar" not in text
    english = [paragraph["isi_en"], doc["catatan_metodologi_en"][
        doc["catatan_metodologi"].index(note)]]
    for text in english:
        assert (f"escalated after that by long-run US inflation of {rate} a year "
                "(IMF WEO Apr 2026), as are costs and capex") in text
        assert "held flat" not in text


def test_ammn_h2_bridge_sentences_are_spaced(tmp_path):
    """The H2 revenue bridge appends its gold and conditional-concentrate
    sentences separately; each starts after a space in both languages."""
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=PLAN,
                      assumption_status="validated")
    pages = [p for p in (doc.get("bagian") or []) + (doc.get("lampiran_audit") or [])
             if p.get("judul") == "Jembatan revenue H2 menurut produk"]
    assert pages
    for page in pages:
        for text in page["paragraf"] + (page.get("paragraf_en") or []):
            assert "Sebagai uji bersyarat" in text or "As a conditional test" in text
            assert not _RUN_ON.search(_URL.sub("", text)), _RUN_ON.search(text)
