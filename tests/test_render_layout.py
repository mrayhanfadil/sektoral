"""Exhibit layout: content-aware column widths, the house source line with a
source appendix, two-across exhibit rows, and the template header/footer."""
import re

from app import fmt, render

HOUSE = fmt.DEFAULT_SOURCE


def _widths(cols, rows, context="full"):
    widths = render._column_widths(cols, rows, context)
    assert len(widths) == len(cols)
    assert abs(sum(widths) - 100) < 0.05
    return widths


def test_long_sentences_get_the_width_not_the_short_labels():
    # AMMN Exhibit 62: short labels left, long sentences right (was 78/22).
    rows = [["Harga provisional saat penjualan",
             "Konsentrat dan katoda awalnya dicatat 100% pada harga provisional; pengakuan "
             "revenue tetap mensyaratkan delivery/title transfer."],
            ["Sebelum settlement final",
             "Harga di-mark-to-market memakai forward price untuk estimasi bulan settlement; "
             "embedded derivative masuk laba rugi."],
            ["Risiko harga",
             "Penurunan 2% dinilai tidak signifikan terhadap laba per 30 Jun; tidak ada "
             "sensitivitas dolar yang diberikan."]]
    label, text = _widths(["Pengungkapan interim", "Dampak pada forecast"], rows)
    assert text > 65 and label >= 15


def test_figure_columns_share_one_width_and_keep_values_on_one_line():
    cols = ["Rp miliar", "2024A", "2025A", "FY26F", "FY27F", "FY28F", "FY29F", "FY30F"]
    rows = [["Pendapatan", "43.036", "30.904", "84.448", "90.266", "88.632", "91.000", "95.100"],
            ["Beban pokok pendapatan", "(21.305)", "(16.919)", "NA", "NA", "NA", "NA", "NA"],
            ["Laba bersih", "10.290", "4.167", "20.474", "31.703", "29.669", "30.100", "31.000"]]
    widths = _widths(cols, rows)
    figures = widths[1:]
    assert max(figures) - min(figures) <= 0.1
    assert widths[0] > figures[0]
    # Each figure column is at least as wide as its widest value plus padding.
    need = (render._em("(21.305)") + render._CELL_PAD_EM) / render._TABLE_EM["full"] * 100
    assert min(figures) >= need
    assert render._column_kinds(cols, rows)[3] == "num"  # NA forecast columns align as figures


def test_mixed_table_gives_the_reason_column_the_room():
    cols = ["Metode", "Keputusan", "Nilai/saham", "Alasan"]
    reason = ("dek harga rata-rata 12 bulan kalender terakhir dianggap datar sepanjang umur "
              "tambang; harga cadangan JORC emiten ditampilkan sebagai sensitivitas; capex dan "
              "jadwal Elang tidak diungkapkan emiten; capex dari riset broker dan probabilitas "
              "pengembangan 50% adalah asumsi analis")
    rows = [["1. SOTP/LoM (utama)", "Terpilih", "Rp2.990", reason],
            ["2. RNAV LoM", "Tidak dijalankan", "-", "jembatan operasi fisik ke keuangan belum ada"],
            ["3. EV/EBITDA FY", "Silang cek", "Rp3.750", "multiple 8x adalah asumsi analis"]]
    method, decision, value, why = _widths(cols, rows)
    assert why > 55
    assert why > method and why > decision and why > value
    # Short labels are not crushed: each keeps its longest word.
    budget = render._TABLE_EM["full"]
    assert decision / 100 * budget >= render._em("dijalankan") + render._CELL_PAD_EM


def test_widths_are_deterministic_and_follow_the_placement():
    cols = ["Tahun buku 31 Des", "2024", "2025", "FY26F", "FY27F", "FY28F"]
    rows = [["Pertumbuhan laba bersih (%)", "-", "(60,9%)", "343,5%", "54,8%", "(6,4%)"],
            ["EV/EBITDA (x)", "-", "-", "9,6x", "7,2x", "7,5x"]]
    cover = _widths(cols, rows, "cover")
    assert cover == _widths(cols, rows, "cover")
    # In the cover column (45 em) the figures still keep one line each.
    need = (render._em("(60,9%)") + render._CELL_PAD_EM) / render._TABLE_EM["cover"] * 100
    assert min(cover[1:]) >= need and max(cover[1:]) - min(cover[1:]) <= 0.1


def test_sentence_opening_with_a_number_is_text_not_a_figure():
    cols = ["Katalis / risiko", "Waktu dan bukti"]
    rows = [["Volume", "38 Mt bijih segar pada 1Q26 dari 1 Mt; kadar tembaga naik ke 0,53%"],
            ["Harga", "12 bulan terakhir naik 29,4% (data s.d. 2026-09-24)"]]
    assert render._column_kinds(cols, rows) == ["text", "text"]


def _doc():
    table = lambda n, judul, cols, rows, note: {  # noqa: E731
        "n": n, "judul": judul, "tipe": "tabel", "data": {"cols": cols, "rows": rows},
        "catatan_sumber": note}
    small_a = table(2, "Hasil interim", ["Metrik", "1H25", "1H26"],
                    [["Pendapatan", "1.000", "1.200"], ["Laba bersih", "100", "120"]],
                    "Sumber: rilis 1H26, hlm. 3; https://issuer.example/blobs/proxy/abc/"
                    "H1%202026%20RELEASE.pdf?disposition=inline. Angka turunan, bukan final.")
    small_b = table(3, "Rasio", ["Rasio", "1H25", "1H26"],
                    [["Marjin bersih", "10,0%", "10,0%"]], "Source: Company, Sektoral Estimates")
    prose = table(4, "Ketentuan", ["Pengungkapan", "Dampak pada forecast"],
                  [["Harga provisional", "Konsentrat dan katoda awalnya dicatat pada harga "
                    "provisional; pengakuan revenue tetap mensyaratkan delivery dan title "
                    "transfer sehingga tidak dapat dipakai sebagai harga final forecast H2."]] * 3,
                  "Sumber: laporan keuangan interim, Catatan 2.s hlm. 40.")
    return {
        "meta": {"ticker": "TEST", "emiten": "PT Test Tbk", "tanggal": "2026-09-24",
                 "status": "draft_non_distributable", "harga": 100},
        "cover": {"headline": "Laba naik", "bullets": ["Satu."], "paragraf": [],
                  "data_pasar": {}},
        "exhibits": [small_a, small_b, prose],
        "bagian": [{"halaman": 3, "layout": "stack", "judul": "Hasil",
                    "paragraf": ["Teks."], "exhibit": [small_a, small_b, prose]}],
        "catatan_metodologi": ["Catatan."],
    }


def test_every_exhibit_footer_is_the_house_line_and_detail_moves_to_the_appendix(monkeypatch):
    monkeypatch.setattr(render, "SHOW_SOURCE_APPENDIX", True)
    out = render.render(_doc())
    footers = re.findall(r"<p class='src'>([^<]*)</p>", out)
    assert footers and set(footers) == {HOUSE}
    assert fmt.DEFAULT_SOURCE == HOUSE
    appendix = out[out.index("source-appendix"):]
    assert out.index("source-appendix") < out.index("<h2 class='sec'>Pengungkapan</h2>")
    assert "Exhibit 2. Hasil interim" in appendix
    assert "Rilis 1H26, hlm. 3" in appendix and "Angka turunan, bukan final." in appendix
    # URLs become links with a short label; the full URL stays in the href.
    assert ("href='https://issuer.example/blobs/proxy/abc/H1%202026%20RELEASE.pdf"
            "?disposition=inline'") in appendix
    assert ">issuer.example/…/H1 2026 RELEASE.pdf</a>." in appendix
    # An exhibit whose note is only the house line still gets an entry.
    assert "Exhibit 3. Rasio</dt><dd>Data perusahaan dan estimasi Sektoral.</dd>" in appendix


def test_provenance_detail_strips_the_house_line():
    assert fmt.provenance_detail("Source: Company, Sektoral Estimates") == ""
    assert fmt.provenance_detail("Source: Sectors, Sektoral Estimates") == "Sectors"
    assert fmt.provenance_detail("Sumber: rilis 1H26; hlm. 3") == "rilis 1H26; hlm. 3"
    assert fmt.house_source_line("Sumber: rilis 1H26") == HOUSE + "; rilis 1H26"


def test_short_tables_sit_two_across_and_prose_stays_full_width():
    doc = _doc()
    rows = render._pair_rows(doc["bagian"][0]["exhibit"])
    assert rows == [(0, 1), (2,)]
    out = render._exhibits_paired(doc["bagian"][0]["exhibit"])
    assert out.startswith("<div class='ex-pair'><div class='pair-col'>")
    # Reading order and numbering: left, right, then the next row.
    assert out.index("Exhibit 2.") < out.index("Exhibit 3.") < out.index("Exhibit 4.")
    assert out.count("<div class='ex-pair'>") == 1
    assert render._half_height(doc["exhibits"][2]) is None
    assert ".band-pair,.ex-pair{grid-template-columns:minmax(0,1fr)}" in render.CSS  # narrow screens


def test_right_column_stacks_two_short_exhibits_against_a_tall_one():
    tall = {"n": 1, "judul": "Komponen WACC", "tipe": "tabel", "catatan_sumber": "",
            "data": {"cols": ["Parameter", "Nilai"],
                     "rows": [[f"Parameter {i}", f"{i},0%"] for i in range(16)]}}
    short = lambda n: {"n": n, "judul": "Kecil", "tipe": "tabel", "catatan_sumber": "",  # noqa: E731
                       "data": {"cols": ["WACC", "g 2,5%", "g 3,5%"],
                                "rows": [["WACC 9,3%", "Rp93", "Rp111"]] * 3}}
    assert render._pair_rows([tall, short(2), short(3)]) == [(0, 1, 2)]


def test_header_and_footer_follow_the_template():
    header = render._report_header("2026-09-24", {"ticker": "AMMN", "rating": "Sell", "tp": 2840})
    assert "<div class='report-title'>AMMN IJ | SELL · TP Rp 2.840</div>" in header
    assert "<div class='report-subtitle'>Equity Research - Company Update | 24 Sep 2026</div>" in header
    draft = render._report_header("2026-09-24", {"ticker": "AMMN", "rating": "Sell", "tp": 2840,
                                                 "status": "draft_non_distributable"})
    assert "AMMN IJ | DRAFT</div>" in draft and "TP" not in draft.split("report-subtitle")[0]
    assert "report-wordmark" in header and "report-divider" in header
    assert "@bottom-left{content:'sectors.app'" in render.CSS
    assert ("@bottom-right{content:'See important disclosure at the back of this report'"
            " '\\2003' 'Page ' counter(page) ' of ' counter(pages)") in render.CSS


def test_combo_panel_legend_names_the_builders_series():
    panel = {"n": 10, "judul": "NIM dan biaya kredit (2024A-2025A, aktual)", "tipe": "combo_panel",
             "catatan_sumber": "",
             "data": {"cols": ["2024A", "2025A"],
                      "series": [{"label": "NIM (%) & biaya kredit", "bars": [7.6, 7.5],
                                  "line": [3.0, 3.2], "is_forecast": [False, False],
                                  "bar_unit": "%"}]}}
    out = render._combo_panel(panel)
    assert ">NIM aktual<" in out and ">Biaya kredit (%, sumbu kanan)<" in out
    assert "proyeksi" not in out and "garis:" not in out and "rasio" not in out
    assert ">7,6%<" in out  # bar values carry the builder's bar unit
    panel["data"]["series"][0].update(label="Ekuitas (Rp) & ROE", bars=[3.2e14, 3.3e14],
                                      is_forecast=[False, True], bar_unit=None)
    out = render._combo_panel(panel)
    assert ">Ekuitas aktual<" in out and ">Ekuitas proyeksi<" in out
    assert ">ROE (%, sumbu kanan)<" in out


def test_bar_chart_labels_use_the_stated_unit_with_one_decimal():
    chart = {"n": 5, "judul": "Perbandingan metrik 1H26", "tipe": "bar_chart", "catatan_sumber": "",
             "data": {"unit": "Rp miliar", "prior_label": "1H25", "current_label": "1H26",
                      "rows": [{"label": "Pendapatan", "prior": 102376278000000,
                                "current": 107923454000000},
                               {"label": "Laba bersih", "prior": 26533147000000,
                                "current": 31182586000000}]}}
    out = render._bar_chart(chart)
    labels = re.findall(r"font-weight='500' fill='[^']*'>([^<]*)<", out)
    # Rp107.923 miliar would need five integer digits: the axis steps up to Rp triliun.
    assert labels == ["102,4", "107,9", "26,5", "31,2"] and ">Rp triliun<" in out
    chart["data"].update(unit="US$ juta", rows=[{"label": "Pendapatan", "prior": 183000000,
                                                 "current": 2052000000}])
    out = render._bar_chart(chart)
    assert re.findall(r"font-weight='500' fill='[^']*'>([^<]*)<", out) == ["183,0", "2.052,0"]
    assert ">US$ juta<" in out


def test_negative_figures_are_bracketed_in_cells_and_captions():
    assert fmt.bracket_negatives("Rp-370,7 miliar", whole=True) == "(Rp370,7 miliar)"
    assert fmt.bracket_negatives("-4,1%", whole=True) == "(4,1%)"
    assert fmt.bracket_negatives("Net sell Rp-39,8 miliar") == "Net sell (Rp39,8 miliar)"
    for kept in ("2024-2025", "8-10x", "-", "2026-06-30"):
        assert fmt.bracket_negatives(kept, whole=True) == kept
    table = {"n": 7, "judul": "Aktivitas asing Rp-20,5 miliar", "tipe": "tabel", "catatan_sumber": "",
             "data": {"cols": ["Metrik", "Nilai"], "rows": [["Arus bersih asing", "Rp-20,5 miliar"]]}}
    out = render._table(table)
    assert "(Rp20,5 miliar)</td>" in out and "Aktivitas asing (Rp20,5 miliar)</caption>" in out


def test_peer_issuer_summary_and_sensitivity_base_are_highlighted():
    peers = {"n": 20, "judul": "Perbandingan peer Banks", "tipe": "tabel", "catatan_sumber": "",
             "data": {"cols": ["Emiten", "P/E (x)"],
                      "rows": [["BBCA", "13,1x"], ["BBRI (emiten)", "7,9x"],
                               ["Median peer (tanpa emiten)", "7,6x"],
                               ["Rata-rata peer (tanpa emiten)", "9,8x"], ["Peringkat BBRI", "5/10"]]}}
    out = render._table(peers)
    assert "<tr class='issuer-row'><td class='cell-text'>BBRI (emiten)" in out
    assert out.count("<tr class='summary-row'>") == 2
    grid = {"n": 18, "judul": "Sensitivitas nilai DDM: CoE x pertumbuhan terminal", "tipe": "tabel",
            "catatan_sumber": "",
            "data": {"cols": ["Cost of equity", "g 2,5%", "g 3,5%", "g 4,5%"],
                     "rows": [["CoE 9,9%", "Rp5.250", "Rp5.875", "Rp6.725"],
                              ["CoE 10,9% (basis)", "Rp4.630", "Rp5.075", "Rp5.700"],
                              ["CoE 11,9%", "Rp4.140", "Rp4.490", "Rp4.940"]]}}
    out = render._table(grid)
    assert "<tr class='base-row'><td class='cell-text'>CoE 10,9% (basis)" in out
    assert re.search(r"<td class='cell-num short base-cell'>Rp5\.075</td>", out)
    # A builder can point at the base directly when labels do not say it.
    grid["data"]["rows"][1][0] = "CoE 10,9%"
    grid["data"]["base"] = {"row": 1, "col": 2}
    assert "base-row" in render._table(grid)


def test_running_header_and_price_box_follow_the_template():
    css = render._running_header({"ticker": "AMMN", "tanggal": "2026-09-24"})
    assert "AMMN IJ" in css and "Equity Research - Company Update | 24 Sep 2026" in css
    assert "@top-right{content:'';" in css and "data:image/png;base64," in css  # logo
    doc = _doc()
    doc["meta"].update(rating="Buy", tp=150, upside_persen=50.456, status="distributable_assumption_led")
    assert "+50,5%</b>" in render.render(doc)


def _yoy_table(cells, note):
    return {"n": 3, "judul": "Hasil interim resmi dan perubahan yoy", "tipe": "tabel",
            "catatan_sumber": note,
            "data": {"cols": ["Metrik", "1H25", "1H26", "yoy"],
                     "rows": [["Pendapatan (US$ juta)", "183,0", "2.052,0", cells[0]],
                              ["Laba bersih (US$ juta)", "(146,0)", "504,0", cells[1]]]}}


def test_a_table_with_nm_prints_only_the_nm_reason_under_the_source_line():
    note = ("Sumber: AMMAN H1 2026 Earnings Release, hlm. 3; https://www.amman.co.id/x "
            "n.m. pada kolom yoy: perubahan dari/ke angka negatif tidak bermakna sebagai persentase.")
    out = render._table(_yoy_table([">500%", "n.m."], note))
    assert out.index(f"<p class='src'>{HOUSE}</p>") < out.index("<p class='nm-note'>")
    assert ("<p class='nm-note'>n.m. pada kolom yoy: perubahan dari/ke angka negatif tidak "
            "bermakna sebagai persentase.</p>") in out
    assert "amman.co.id" not in out
    # '>500%' is a figure: right-aligned like the rest of the column.
    assert "<td class='cell-num short'>&gt;500%</td>" in out
    assert "nm-note" not in render._table(_yoy_table([">500%", "12,0%"], note))


def test_nm_note_takes_the_nm_clause_of_a_multi_clause_sentence():
    note = ("Sumber: grup peer kurasi Sektoral; per 2026-09-25; P/E negatif tidak diperingkat; "
            "rasio di atas 500% ditulis n.m. karena basis sangat kecil. Median memakai peer valid.")
    assert render._nm_note({"catatan_sumber": note}) == (
        "<p class='nm-note'>rasio di atas 500% ditulis n.m. karena basis sangat kecil.</p>")
