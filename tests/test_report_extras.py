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
    assert {"Pemegang saham utama", "Aktivitas investor asing", "Laba rugi",
            "Neraca", "Rasio utama"} <= titles
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
    # Struktur-Template running header: report type over the publication date.
    assert ('@top-left{content:"Equity Research - Company Update" \'\\A \' '
            '"Kamis, 24 September 2026"') in css
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


def test_peer_medians_need_three_valid_peers_like_the_method_chain():
    rows = [{"is_self": False, "metrics": {"pe": pe, "pb": pb}} for pe, pb in
            ((8.0, 2.2), (8.1, 2.3), (None, None), (None, None))]
    rows.append({"is_self": True, "metrics": {"pe": 11.5, "pb": 2.7}})
    stats = X._peer_stats(rows)
    assert stats["pe"] == (None, None) and stats["pb"] == (None, None)
    assert stats["counts"]["pe"] == 2
    assert "kurang dari tiga peer valid (P/E 2 peer, P/B 2 peer" in X._thin_peer_note(stats)


def test_band_and_statements_use_indonesian_format_and_hide_zero_ebitda(tmp_path):
    doc = B.build("JPFA", tmp_path, as_of="2026-09-24")
    html_out = render.render(doc)
    cells = re.findall(r"<td class='[^']*'>([^<]*)</td>", html_out)
    assert not [c for c in cells if re.search(r"\d\.\dx", c)]
    income = next(e for e in doc["exhibits"] if e["judul"] == "Laba rugi")
    # Template Exhibit 14 has no EBITDA line; EBITDA lives in Key Financials and ratios.
    assert "EBITDA" not in [r[0] for r in income["data"]["rows"]]
    ratios = next(e for e in doc["exhibits"] if e["judul"] == "Rasio utama")
    margin = next(r for r in ratios["data"]["rows"] if r[0] == "Marjin EBITDA")
    assert "0,0%" not in margin[1:]


INCOME_LINES = ["Pendapatan", "Beban pokok pendapatan", "Laba kotor", "Beban usaha",
                "Laba usaha (EBIT)", "Pendapatan bunga", "Beban bunga",
                "Pendapatan (beban) lain-lain", "Laba sebelum pajak", "Pajak penghasilan",
                "Kepentingan non-pengendali", "Laba bersih"]
BALANCE_LINES = ["Kas dan setara kas", "Piutang usaha", "Persediaan", "Aset lancar lainnya",
                 "Total aset lancar", "Aset tetap bersih", "Aset tidak lancar lainnya",
                 "Total aset", "Utang jangka pendek", "Utang usaha", "Liabilitas lancar lainnya",
                 "Total liabilitas lancar", "Utang jangka panjang",
                 "Liabilitas tidak lancar lainnya", "Total liabilitas", "Total ekuitas",
                 "Total liabilitas dan ekuitas"]
CASH_LINES = ["Blok Arus kas operasi", "Laba bersih", "Depresiasi dan amortisasi",
              "Perubahan modal kerja", "Pos operasi lainnya", "Jumlah arus kas operasi",
              "Blok Arus kas investasi", "Belanja modal", "Pos investasi lainnya",
              "Jumlah arus kas investasi", "Blok Arus kas pendanaan",
              "Penarikan (pembayaran) utang", "Dividen dibayar",
              "Penerbitan (pembelian kembali) saham", "Pos pendanaan lainnya",
              "Jumlah arus kas pendanaan", "Blok Saldo kas", "Perubahan kas bersih", "Kas awal",
              "Kas akhir", "Arus kas bebas (operasi - capex, memo)"]
DISPLAY = ["2024A", "2025A", "FY26F", "FY27F", "FY28F"]


def _table(doc, title):
    return next(e for e in doc["exhibits"] if e["judul"] == title)


def _cells(table):
    return [c for r in table["data"]["rows"] if not r[0].startswith("Blok ") for c in r[1:]]


def test_statements_follow_struktur_with_two_actual_and_three_forecast_years(tmp_path):
    doc = _doc(tmp_path)  # AMMN draft: no validated scenario, forecast columns n.m.
    income = _table(doc, "Laba rugi")
    assert income["data"]["cols"] == ["Rp miliar"] + DISPLAY
    assert [r[0] for r in income["data"]["rows"]] == INCOME_LINES
    assert [r[0] for r in _table(doc, "Neraca")["data"]["rows"]] == BALANCE_LINES
    assert [r[0] for r in _table(doc, "Arus kas")["data"]["rows"]] == CASH_LINES
    rows = {r[0]: r for r in _table(doc, "Neraca")["data"]["rows"]}
    assert rows["Total aset"][1:3] == rows["Total liabilitas dan ekuitas"][1:3]
    ratios = _table(doc, "Rasio utama")
    assert [r[0] for r in ratios["data"]["rows"] if r[0].startswith("Blok ")] == [
        "Blok Pertumbuhan (%)", "Blok Profitabilitas (%)", "Blok Leverage (x)"]
    # Spec §3.1: no NA or blank; a cell that cannot be derived is n.m. with a reason.
    for title in ("Laba rugi", "Neraca", "Arus kas", "Rasio utama"):
        table = _table(doc, title)
        assert not set(_cells(table)) & {"NA", "", "-"}, title
        assert all(r[3:] == ["n.m."] * 3 for r in table["data"]["rows"]
                   if not r[0].startswith("Blok ")), title
        assert "belum tervalidasi" in table["catatan_sumber"], title
    assert "Sectors tidak memisahkan piutang usaha" in _table(doc, "Neraca")["catatan_sumber"]


def test_bank_statements_switch_to_bank_layout(tmp_path):
    doc = B.build("BBRI", tmp_path, as_of="2026-09-24")
    titles = {e["judul"] for e in doc["exhibits"]}
    assert {"Laba rugi bank", "Neraca bank"} <= titles
    income = next(e for e in doc["exhibits"] if e["judul"] == "Laba rugi bank")
    assert "Laba sebelum provisi (PPOP)" in [r[0] for r in income["data"]["rows"]]
    ratios = next(e for e in doc["exhibits"] if e["judul"] == "Rasio utama")
    labels = [r[0] for r in ratios["data"]["rows"]]
    assert {"Marjin bunga bersih (NIM)", "Kredit terhadap simpanan (LDR)",
            "Rasio kecukupan modal (CAR)"} <= set(labels)


def test_non_mining_issuer_gets_an_industry_and_sentiment_page(tmp_path):
    doc = B.build("JPFA", tmp_path, as_of="2026-09-24")
    page = next(p for p in doc["bagian"] if p["judul"] == "Industri dan sentimen")
    table = page["exhibit"][0]
    # JPFA has a curated peer group, so the table reads the group, not the sub-sector.
    assert table["judul"].startswith("Kondisi grup peer Integrator pakan dan unggas")
    assert [r[0] for r in table["data"]["rows"]][:2] == [
        "Kapitalisasi pasar (Rp triliun)", "Perubahan kapitalisasi pasar 1 tahun"]
    text = " ".join(page["paragraf"])
    assert "IHSG" in text and "-" not in re.findall(r"(?:naik|turun) (\S+)", text)[0]
    titles = [p["judul"] for p in doc["bagian"]]
    assert titles.index("Industri dan sentimen") < titles.index("Katalis, risiko, dan kepemilikan")


def test_band_reports_its_real_window_and_implied_prices(tmp_path):
    doc = B.build("JPFA", tmp_path, as_of="2026-09-24")
    table = next(e for e in doc["exhibits"] if e["judul"].startswith("Band historis"))
    assert "1 tahun" not in table["judul"] and "bulan" in table["judul"]
    pe = next(r for r in table["data"]["rows"] if r[0] == "P/E")
    assert re.fullmatch(r"Rp[\d.]+ / Rp[\d.]+", pe[4])
    charts = [e for e in doc["exhibits"] if e.get("tipe") == "band_chart"]
    assert [c["data"]["label"] for c in charts] == ["P/E", "P/BV"]
    html_out = render.render(doc)
    assert "class='band-pair'" in html_out and "class='band-chart'" in html_out


def test_performance_charts_are_four_narrated_exhibits(tmp_path):
    doc = B.build("JPFA", tmp_path, as_of="2026-09-24")
    panels = [e for e in doc["exhibits"] if e.get("tipe") == "combo_panel"]
    assert [p["judul"].split(" (")[0] for p in panels] == [
        "Pendapatan dan pertumbuhan", "EBITDA dan margin", "Laba bersih dan pertumbuhan EPS",
        "DER dan ROE"]
    assert all(p["narasi"] and any(ch.isdigit() for ch in p["narasi"]) for p in panels)
    assert [p["n"] for p in panels] == list(range(panels[0]["n"], panels[0]["n"] + 4))
    # Draft: no validated scenario, so the charts carry the two actual years only
    # for DER/ROE and no forecast bars anywhere.
    assert all(p["data"]["cols"][:2] == ["2024A", "2025A"] for p in panels)
    assert panels[3]["judul"] == "DER dan ROE (2024A-2025A)"
    assert not any(v is not None for p in panels
                   for v, fc in zip(p["data"]["series"][0]["bars"],
                                    p["data"]["series"][0]["is_forecast"]) if fc)
    bank = B.build("BBRI", tmp_path / "bank", as_of="2026-09-24")
    bank_panels = [e for e in bank["exhibits"] if e.get("tipe") == "combo_panel"]
    # EBITDA means nothing for a bank: equity and ROE take its place.
    assert [p["judul"].split(" (")[0] for p in bank_panels] == [
        "Pendapatan dan pertumbuhan", "Laba bersih dan pertumbuhan EPS", "Ekuitas dan ROE",
        "NIM dan biaya kredit"]
    nim = bank_panels[3]
    assert nim["judul"] == "NIM dan biaya kredit (2024A-2025A, aktual)"
    assert nim["data"]["cols"] == ["2024A", "2025A"]
    assert "Rp-" not in " ".join(p for page in doc["bagian"] for p in page["paragraf"])


# ------------------------------------------------ forecast statements and charts

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
KF_ROWS = ["Pendapatan (Rp miliar)", "EBITDA (Rp miliar)", "Pertumbuhan EBITDA (%)",
           "Laba bersih (Rp miliar)", "EPS (Rp)", "Pertumbuhan EPS (%)", "PER (x)", "PBV (x)",
           "EV/EBITDA (x)"]
KF_BANK_ROWS = ["Pendapatan (Rp miliar)", "Laba bersih (Rp miliar)", "EPS (Rp)",
                "Pertumbuhan EPS (%)", "BVPS (Rp)", "ROE (%)", "DPS (Rp)", "PER (x)", "PBV (x)"]


def _scenario_doc(ticker, tmp_path):
    """The stored run's validated analyst scenario (FY26F-FY30F), rebuilt offline."""
    stored = json.loads((FIXTURES / f"{ticker.lower()}_scenario_plan.json").read_text())
    return B.build(ticker, tmp_path / ticker, as_of="2026-09-24",
                   assumption_plan=stored["plan"], assumption_status=stored["status"])


def _number(cell):
    cell = cell.replace(".", "").replace(",", ".").rstrip("%x")
    return -float(cell.strip("()")) if cell.startswith("(") else float(cell)


def _row(table, label):
    rows = table["data"]["rows"]
    row = next((r for r in rows if r[0] == label), None) or next(
        r for r in rows if r[0].startswith(label + " ("))
    return dict(zip(table["data"]["cols"], row))


def test_chart_rows_carry_the_five_year_scenario():
    from app import forecast, intake
    doc_in, _ = intake.load("JPFA", as_of="2026-09-24")
    stored = json.loads((FIXTURES / "jpfa_scenario_plan.json").read_text())
    fc = forecast.build(doc_in, assumption_plan=stored["plan"])
    rows = X.chart_forecast_rows(doc_in, fc)
    assert [r["label"] for r in rows] == ["FY26F", "FY27F", "FY28F", "FY29F", "FY30F"]
    assert [r["revenue"] for r in rows[1:]] == [r["revenue"] for r in fc["outyear_scenario"]["rows"]]
    assert [r["year"] for r in rows] == [2026, 2027, 2028, 2029, 2030]


def test_scenario_statements_fill_three_forecast_years_from_the_model(tmp_path):
    doc = _scenario_doc("JPFA", tmp_path)
    assert doc["meta"]["status"] == "distributable_assumption_led"
    key_fin = _table(doc, "Key Financials")
    assert key_fin["data"]["cols"][1:] == DISPLAY
    assert [r[0] for r in key_fin["data"]["rows"]] == KF_ROWS
    assert not set(_cells(key_fin)) & {"NA", "", "-"}
    assert all(c != "n.m." for r in key_fin["data"]["rows"] for c in r[3:])
    income, balance, cash = (_table(doc, t) for t in ("Laba rugi", "Neraca", "Arus kas"))
    for table in (income, balance, cash, _table(doc, "Rasio utama")):
        assert table["data"]["cols"][1:] == DISPLAY
        assert not set(_cells(table)) & {"NA", "", "-"}
    # A forecast n.m. is named in the note with its reason.
    for table in (income, balance, cash):
        for row in table["data"]["rows"]:
            if "n.m." in row[3:]:
                assert re.search(re.escape(row[0]) + r"[^;]*\(kolom FY26F-FY28F\): \w",
                                 table["catatan_sumber"]), row[0]
    # Struktur tie-outs: net profit (Key Financials = income statement = cash flow start),
    # balance sheet balances, ending cash = balance-sheet cash, cash rolls year to year.
    kf_net, is_net = _row(key_fin, "Laba bersih"), _row(income, "Laba bersih")
    cf_net = _row(cash, "Laba bersih")
    for label in DISPLAY:
        assert abs(_number(kf_net[label]) - _number(is_net[label])) <= 1, label
        assert is_net[label] == cf_net[label]
    assets, total = _row(balance, "Total aset"), _row(balance, "Total liabilitas dan ekuitas")
    ending, bs_cash = _row(cash, "Kas akhir"), _row(balance, "Kas dan setara kas")
    opening = _row(cash, "Kas awal")
    for label in DISPLAY[2:]:
        assert abs(_number(assets[label]) - _number(total[label])) <= 1, label
        assert ending[label] == bs_cash[label]
    assert opening["FY27F"] == ending["FY26F"] and opening["FY28F"] == ending["FY27F"]
    # Ratios are computed for forecast years wherever the inputs exist.
    ratios = _table(doc, "Rasio utama")
    for label in ("EBITDA", "Marjin EBITDA", "ROAE", "Net gearing (utang bersih / ekuitas)"):
        assert "n.m." not in [_row(ratios, label)[c] for c in DISPLAY[2:]], label
    assumptions = _table(doc, "Asumsi proyeksi laporan keuangan")
    assert len(assumptions["data"]["rows"]) >= 3
    # Slide 3: every chart on 2024A-FY28F, DER/ROE with forecast values from the model.
    panels = [e for e in doc["exhibits"] if e.get("tipe") == "combo_panel"]
    assert all(p["data"]["cols"] == DISPLAY for p in panels)
    assert panels[3]["judul"] == "DER dan ROE (2024A-FY28F)"
    assert all(v is not None for v in panels[3]["data"]["series"][0]["bars"][2:])
    # Revenue bars tie out with Key Financials for the same periods.
    revenue = _row(key_fin, "Pendapatan")
    bars = panels[0]["data"]["series"][0]["bars"]
    assert [round(v / 1e9, 1) for v in bars] == [_number(revenue[c]) for c in DISPLAY]


def test_bank_scenario_drops_ebitda_and_shows_ddm_lines(tmp_path):
    doc = _scenario_doc("BBRI", tmp_path)
    assert doc["meta"]["status"] == "distributable_assumption_led"
    key_fin = _table(doc, "Key Financials")
    assert [r[0] for r in key_fin["data"]["rows"]] == KF_BANK_ROWS
    assert not set(_cells(key_fin)) & {"NA", "", "-"}
    # DPS is the DDM exhibit's line; ROE is the ratio table's ROAE.
    ddm = next(e for e in doc["exhibits"] if e["judul"].startswith("Proyeksi dividen"))
    assert [_row(key_fin, "DPS")[c] for c in DISPLAY[2:]] == \
        [_row(ddm, "DPS")[c] for c in DISPLAY[2:]]
    ratios = _table(doc, "Rasio utama")
    assert [_row(key_fin, "ROE")[c] for c in DISPLAY] == [_row(ratios, "ROAE")[c] for c in DISPLAY]
    income = _table(doc, "Laba rugi bank")
    net = _row(income, "Laba bersih")
    assert all(net[c] != "n.m." for c in DISPLAY)
    assert "Skenario laba bank tidak memodelkan" in income["catatan_sumber"]
    cash = _table(doc, "Arus kas")
    assert "Belanja modal" not in [r[0] for r in cash["data"]["rows"]]
    assert all(_row(cash, "Dividen dibayar")[c] != "n.m." for c in DISPLAY[2:])
    panels = [e for e in doc["exhibits"] if e.get("tipe") == "combo_panel"]
    equity = next(p for p in panels if p["judul"].startswith("Ekuitas dan ROE"))
    assert equity["judul"] == "Ekuitas dan ROE (2024A-FY28F)"
    assert all(v is not None for v in equity["data"]["series"][0]["bars"])
    assert not any(p["judul"].startswith("EBITDA") for p in panels)


def test_usd_reporter_statements_are_in_usd_and_tie_to_key_financials(tmp_path):
    """Spec §2: a US$ reporter's model is in US$; its statements read the same
    US$ figures as Key Financials and the charts (AMMN's validated plan)."""
    from app import commodity, fx, store
    fixtures = FIXTURES
    store.put(commodity.COLLECTION, "Copper",
              json.loads((fixtures / "commodity_prices.json").read_text())["Copper"])
    store.put(fx.COLLECTION, fx.KEY, {"pair": "USD/IDR", "rate": 17805.0, "date": "2026-09-23",
                                      "source": "Yahoo Finance IDR=X daily close"})
    plan = json.loads((fixtures / "ammn_interim_plan.json").read_text())
    doc = B.build("AMMN", tmp_path, as_of="2026-09-24", assumption_plan=plan,
                  assumption_status="validated")
    key_fin, income = _table(doc, "Key Financials"), _table(doc, "Laba rugi")
    assert income["data"]["cols"][0] == "US$ juta"
    for label in ("Pendapatan", "Laba bersih"):
        kf, stmt = _row(key_fin, label), _row(income, label)
        for period in DISPLAY:
            assert abs(_number(kf[period]) - _number(stmt[period])) <= 0.1, (label, period)
    # Actual lines the official US$ release does not carry are n.m. with the reason.
    assert _row(income, "Laba kotor")["2025A"] == "n.m."
    assert "rilis tahunan resmi US$" in income["catatan_sumber"]
    assert "kurs yang sama dengan model" in income["catatan_sumber"]
    panels = [e for e in doc["exhibits"] if e.get("tipe") == "combo_panel"]
    assert panels[0]["data"]["series"][0]["label"].startswith("Pendapatan (US$)")


def test_bank_exhibits_carry_no_ebitda_and_growth_starts_from_fy2025(tmp_path):
    doc = _scenario_doc("BBRI", tmp_path)
    labels = [r[0] for e in doc["exhibits"] if e.get("tipe") == "tabel"
              for r in e["data"]["rows"] if isinstance(r, list) and r]
    assert not [label for label in labels if "EBITDA" in str(label)]
    ddm = next(e for e in doc["exhibits"] if e["judul"].startswith("Proyeksi dividen"))
    growth = _row(ddm, "Pertumbuhan DPS")
    assert growth["FY26F"] not in ("-", "n.m.")
    assert "DPS FY2025" in ddm["catatan_sumber"]


def test_fcff_growth_starts_from_fy2025_on_the_table_definition(tmp_path):
    doc = _scenario_doc("JPFA", tmp_path)
    fcff = next(e for e in doc["exhibits"] if e["judul"].startswith("Proyeksi FCFF"))
    cells = _row(fcff, "Pertumbuhan FCFF")
    assert "-" not in list(cells.values())[1:]
    assert cells["FY26F"] != "n.m." and "FCFF FY2025" in fcff["catatan_sumber"]
