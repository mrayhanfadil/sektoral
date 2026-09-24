"""Spec §5 layout rules for sections added from local Sectors data."""
from __future__ import annotations

import re

from app import build as B, narrative, render, report_extras as X


def _doc(tmp_path):
    return B.build("AMMN", tmp_path, as_of="2026-09-24")


def test_pages_follow_spec_order_and_exhibits_are_numbered_in_reading_order(tmp_path):
    doc = _doc(tmp_path)
    titles = [page["judul"] for page in doc["bagian"]]
    for earlier, later in (("Operasi", "Industri"), ("Industri", "Katalis"),
                           ("Katalis", "Perbandingan peer"), ("Perbandingan peer", "Data keuangan")):
        first = next(i for i, t in enumerate(titles) if t.startswith(earlier))
        second = next(i for i, t in enumerate(titles) if t.startswith(later))
        assert first < second, (earlier, later, titles)
    # The cover holds Exhibit 1 (price vs IHSG) and Exhibit 2 (Key Financials).
    reading = [1, 2] + [e["n"] for page in doc["bagian"] for e in page["exhibit"]]
    assert reading == list(range(1, len(reading) + 1))
    assert [e["n"] for e in doc["exhibits"]] == reading


def test_industry_peer_ownership_and_financial_pages_come_from_local_data(tmp_path):
    doc = _doc(tmp_path)
    titles = {e["judul"] for e in doc["exhibits"]}
    assert "Harga komoditas utama emiten" in titles
    assert any(t.startswith("Valuasi dan pertumbuhan sub-sektor") for t in titles)
    assert any(t.startswith("Perbandingan peer") for t in titles)
    assert {"Pemegang saham utama", "Aktivitas investor asing", "Laba rugi historis",
            "Neraca historis"} <= titles
    commodity = next(e for e in doc["exhibits"] if e["judul"] == "Harga komoditas utama emiten")
    assert len(commodity["data"]["cols"]) == len(set(commodity["data"]["cols"]))


def test_cover_shows_two_actual_three_forecast_periods_and_market_data(tmp_path):
    doc = _doc(tmp_path)
    assert doc["exhibits"][0]["tipe"] == "price_chart"
    assert doc["exhibits"][1]["judul"] == "Key Financials"
    cols = doc["exhibits"][1]["data"]["cols"]
    assert len(cols) == 6 and cols[-1].endswith("F") and not cols[2].endswith("F")
    market = doc["cover"]["data_pasar"]
    assert market["adtv"] != "-" and market["free_float"] != "-"
    assert doc["holders"] and doc["holders"][0][1].endswith("%")


def test_catalysts_carry_timing_driver_and_direction(tmp_path):
    doc = _doc(tmp_path)
    table = next(e for e in doc["exhibits"] if e["judul"] == "Katalis, risiko, dan indikator pemantauan")
    assert table["data"]["cols"] == ["Katalis / risiko", "Waktu dan bukti",
                                     "Driver dan jalur dampak", "Arah"]
    assert all(row[3] for row in table["data"]["rows"])
    assert not any("Penjualan Penjualan" in cell for row in table["data"]["rows"] for cell in row)


def test_guidance_attainment_matches_products_across_units(tmp_path):
    doc = _doc(tmp_path)
    table = next(e for e in doc["exhibits"] if e["judul"] == "Realisasi 1H26 terhadap panduan FY2026")
    rows = {row[0]: row for row in table["data"]["rows"]}
    assert rows["Katoda tembaga (kt)"][1] == "48,8" and rows["Katoda tembaga (kt)"][2] == "130"


def test_cover_sentences_keep_at_most_three_figures(tmp_path):
    doc = _doc(tmp_path)
    for paragraph in doc["cover"]["paragraf"][:1]:
        for sentence in re.split(r"(?<=\.)\s+", paragraph["isi"]):
            figures = re.findall(r"(?<![\w/])\d[\d.,]*(?:%| juta| miliar)", sentence)
            assert len(figures) <= 3, sentence
    assert "1.021" not in doc["cover"]["bullets"][0]
    assert "dari basis rendah" in doc["cover"]["bullets"][0]


def test_change_sentence_describes_base_effects_and_loss_reversals():
    money = lambda v: f"US${v}"
    assert "dari basis rendah" in narrative._change_sentence("pendapatan", 2052, 183, "1H26", "1H25", money)
    assert "berbalik dari rugi US$146" in narrative._change_sentence("laba bersih", 504, -146, "1H26", "1H25", money)
    assert "naik 10,0% yoy" in narrative._change_sentence("EBITDA", 110, 100, "1H26", "1H25", money)


def test_assumption_headline_is_a_short_forward_thesis():
    for rating in ("Buy", "Hold", "Sell"):
        headline = narrative._assumption_headline(rating, "FY26F")
        assert len(headline.split()) <= 10
        assert not re.search(r"\d+x", headline)


def test_negative_figures_render_in_brackets_and_header_repeats_on_pages():
    table = {"n": 2, "judul": "T", "catatan_sumber": "S",
             "data": {"cols": ["Metrik", "2025"], "rows": [["Pertumbuhan", "-30,7%"],
                                                          ["Tanggal", "2026-06-30"]]}}
    html = render._table(table)
    assert "(30,7%)" in html and "2026-06-30" in html
    css = render._running_header({"ticker": "AMMN", "rating": "Sell", "tp": 3910,
                                  "tanggal": "2026-09-24"})
    assert '@top-left{content:"AMMN IJ | SELL · TP Rp 3.910"' in css
    assert "@page:first" in css


def test_renumber_keeps_key_financials_first():
    key = {"judul": "Key Financials", "n": 9}
    other = {"judul": "B", "n": 1}
    doc = {"exhibits": [other, key], "bagian": [{"exhibit": [other]}]}
    X.renumber(doc)
    assert (key["n"], other["n"]) == (1, 2)


def test_draft_report_carries_quantified_fallback_risks(tmp_path):
    doc = _doc(tmp_path)
    assert 1 <= len(doc["risks"]) <= 5
    assert all(r["kategori"] and any(ch.isdigit() for ch in r["isi"]) for r in doc["risks"])
    page = next(p for p in doc["bagian"] if p["judul"] == "Katalis, risiko, dan kepemilikan")
    assert page["risks"] == doc["risks"]
    assert "Risiko utama:" in doc["cover"]["paragraf"][-1]["isi"]


def test_published_report_without_risks_is_blocked():
    from app.harness.narrative_tool import check_narrative
    doc = {"meta": {"status": "distributable_assumption_led"},
           "cover": {"headline": "Laba naik", "paragraf": [{"judul": "Valuasi", "isi": "Target."}]},
           "risks": []}
    assert any(b.startswith("N.risiko") for b in check_narrative(doc)["blockers"])
    doc["meta"]["status"] = "draft_non_distributable"
    assert not any(b.startswith("N.risiko") for b in check_narrative(doc)["blockers"])


def test_peer_median_and_average_use_the_valuation_band():
    rows = [{"is_self": False, "metrics": {"pe": pe, "pb": pb}} for pe, pb in
            ((6.8, 1.5), (646.0, 40.5), (131.9, 8.5), (9.2, 0.7), (3.2, 0.5), (-4.0, 17.9))]
    rows.append({"is_self": True, "metrics": {"pe": 5.1, "pb": 1.3}})
    stats = X._peer_stats(rows)
    assert stats["pe"] == (6.8, (6.8 + 9.2 + 3.2) / 3)
    assert stats["pb"][0] == 1.1  # 0.5, 0.7, 1.5, 8.5 inside 0-10x


def test_band_and_statements_use_indonesian_format_and_hide_zero_ebitda(tmp_path):
    doc = B.build("JPFA", tmp_path, as_of="2026-09-24")
    html_out = render.render(doc)
    cells = re.findall(r"<td class='[^']*'>([^<]*)</td>", html_out)
    assert not [c for c in cells if re.search(r"\d\.\dx", c)]
    income = next(e for e in doc["exhibits"] if e["judul"] == "Laba rugi historis")
    ebitda = next(r for r in income["data"]["rows"] if r[0] == "EBITDA")
    assert "0" not in ebitda[1:]
