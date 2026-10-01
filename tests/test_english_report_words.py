"""The English Company Update reads English (#41).

Builds BBRI (on a Forecast Plan with its English twins) and AMMN (the
validated interim plan) offline, renders the English edition and reads every
visible text node: none may hold an Indonesian function word
(``prose_lang.indonesian_words``) unless the text is source data the report
quotes as it is: a document or news title, a company name, a URL.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from app import build, commodity, fx, prose_lang, rates, render, report_lang, store

FIXTURES = Path(__file__).parent / "fixtures"
AS_OF = "2026-09-24"


class _Text(HTMLParser):
    """Visible text nodes of a page (no script, style or document title)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open, self.nodes = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in ("br", "wbr", "col", "img", "meta", "link", "input", "hr"):
            self.open.append(tag)

    def handle_endtag(self, tag):
        while self.open and self.open.pop() != tag:
            pass

    def handle_data(self, data):
        if data.strip() and not {"script", "style", "title"} & set(self.open):
            self.nodes.append(data.strip())


def _nodes(page):
    parser = _Text()
    parser.feed(page)
    return parser.nodes


# Source data quoted as it is: names of documents and news items, and companies.
_URL = re.compile(r"https?://\S+")
_SOURCE = [re.compile(p) for p in (
    r"PT [A-Z][\w.&()-]*(?: [A-Z(][\w.&()-]*)*(?: Tbk)?",   # company names
    r"Laporan Keuangan[\w ,()]*\d{4}(?: \(tidak diaudit\))?",  # issuer statement titles
)]


def _indonesian(text, quoted=()):
    text = _URL.sub("", text)
    for title in quoted:
        text = text.replace(title, "")
    for pattern in _SOURCE:
        text = pattern.sub("", text)
    return prose_lang.indonesian_words(text)


def _titles(doc):
    """Titles of the documents and news items the report cites: a title held
    beside the item's URL or publication date."""
    titles = set()

    def walk(value):
        if isinstance(value, dict):
            if {"url", "source_url", "published_at", "timestamp", "date"} & set(value):
                titles.update(v for k, v in value.items()
                              if k in ("title", "source_title") and isinstance(v, str))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(doc)
    return sorted((t for t in titles if len(t) > 12), key=len, reverse=True)


def _english_hits(doc):
    quoted = _titles(doc)
    return [text for text in _nodes(render.render(doc, lang="en")) if _indonesian(text, quoted)]


def test_english_bbri_report_reads_english(tmp_path):
    stored = json.loads((FIXTURES / "bbri_scenario_plan_en.json").read_text())
    doc = build.build("BBRI", tmp_path, as_of=AS_OF, assumption_plan=stored["plan"],
                      assumption_status=stored["status"])
    assert _english_hits(doc) == []
    english = _nodes(render.render(doc, lang="en"))
    # The catalyst table quotes the agent's twins; the Indonesian rows stay for
    # driver matching and the Indonesian edition.
    assert "3Q26 earnings release" in english
    assert any(n.startswith("not available: consensus retrieved 2026-09-25") for n in english)
    assert any(n.startswith("about 0.1 trading days at 20% participation") for n in english)
    assert "n.m. in DPS (Rp) (actual columns): Sectors data records dividends by ex-date, " \
           "not by financial year." in english
    indonesian = _nodes(render.render(doc))
    assert "Rilis earnings 3Q26" in indonesian
    assert any(n.startswith("sekitar 0,1 hari bursa") for n in indonesian)


def test_english_ammn_report_reads_english(tmp_path):
    from test_mining_route import COPPER, PLAN, UST_10Y, USD_IDR
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of=AS_OF, assumption_plan=PLAN,
                      assumption_status="validated")
    assert _english_hits(doc) == []
    english = _nodes(render.render(doc, lang="en"))
    assert "Batu Hijau pit, per year (2027-2033)" in english
    assert "IDX-listed copper and gold miners" in " ".join(english)    # the Peer Group name


# --- The mechanisms -----------------------------------------------------------


def _exhibit(rows, **data):
    return {"n": 1, "judul": "Ringkasan keputusan", "tipe": "tabel",
            "data": {"cols": ["Pertanyaan", "Jawaban"], "rows": rows, **data}}


def test_table_cells_carry_the_english_runs_cells_with_the_same_figures():
    doc = {"exhibits": [_exhibit([["Yang berubah", "Harga Rp3.140 setara dengan satu dari: a"],
                                  ["Status", "Tanggal laporan 2026-09-26"],
                                  ["Sama", "1H26"]])]}
    doc_en = {"exhibits": [_exhibit([["Yang berubah", "The Rp3.140 price equals any one of: a"],
                                     ["Status", "Report Date 2026-09-27"],
                                     ["Sama", "1H26"]])]}
    prose_lang.attach(doc, doc_en)
    # Same figures: attached. Another figure, or no change: left to the label.
    assert doc["exhibits"][0]["data"]["rows_en"] == [
        [None, "The Rp3.140 price equals any one of: a"], None, None]
    view, _ = prose_lang.english_view(doc)
    cell = view["exhibits"][0]["data"]["rows_en"][0][1]
    assert cell == "The Rp3,140 price equals any one of: a"
    assert isinstance(cell, prose_lang.Translated)
    # The Indonesian rows stay as built, for the renderer's layout and the Indonesian edition.
    assert view["exhibits"][0]["data"]["rows"] == doc["exhibits"][0]["data"]["rows"]


def test_a_builders_own_rows_en_overrides_its_indonesian_rows():
    """The catalyst table keeps Indonesian rows in the English run (driver
    matching) and sets rows_en itself; a cell appended later is English already."""
    doc = {"exhibits": [_exhibit([["Rilis earnings 3Q26", "Rating Buy berubah bila x"]])]}
    doc_en = {"exhibits": [_exhibit([["Rilis earnings 3Q26", "The Buy rating changes if x"]],
                                    rows_en=[["3Q26 earnings release"]])]}
    prose_lang.attach(doc, doc_en)
    assert doc["exhibits"][0]["data"]["rows_en"] == [
        ["3Q26 earnings release", "The Buy rating changes if x"]]


def test_a_quoted_title_is_not_an_untranslated_clause():
    title = "Laporan Keuangan dan Catatan yang Tidak Diaudit"
    id_text = f"Tidak ada batas kredit yang mengikat. Sumber asumsi: {title}."
    bare = f"No loan constraint binds. Assumption source: {title}."
    with prose_lang.building("en"):
        en_text = f"No loan constraint binds. Assumption source: {prose_lang.quoted(title)}."
    assert prose_lang._pair(id_text, bare) is None          # reads as mixed Indonesian
    assert prose_lang._pair(id_text, en_text) == bare       # attached, marks dropped
    assert prose_lang.quoted(title) == title                # Indonesian build: as is


def test_nm_notes_read_english_or_stay_indonesian_whole():
    parts = ["n.m. pada Dividen dibayar, Arus kas bebas (operasi - capex, memo) (kolom aktual): "
             "Sectors hanya memuat total arus kas pendanaan tanpa rincian; Marjin laba kotor "
             "(kolom FY26F-FY28F): pos ini tidak dihasilkan model forecast",
             "rasio di atas 500% ditulis n.m. karena basis pendapatan atau ekuitas sangat kecil."]
    assert report_lang.nm_note(parts, "en") == [
        "n.m. in Dividends paid, Free cash flow (operating - capex, memo) (actual columns): "
        "Sectors carries only total financing cash flow, without a breakdown; Gross margin "
        "(FY26F-FY28F columns): the forecast model does not produce this line",
        "ratios above 500% are shown as n.m. on a very small revenue or equity base"]
    # A reason or a line label without English keeps the whole note Indonesian.
    assert report_lang.nm_note(parts + ["n.m. pada Laba (kolom aktual): alasan baru"], "en") is None
    assert report_lang.nm_note(["n.m. pada Pos baru sekali (kolom aktual): pos ini tidak "
                                "dihasilkan model forecast"], "en") is None
    assert report_lang.nm_note(parts) == parts


def test_an_unknown_nm_reason_keeps_the_note_indonesian():
    ex = {"catatan_sumber": "Sumber: Sectors. n.m. pada Laba (kolom aktual): alasan baru."}
    token = render._LANG.set("en")
    try:
        note = render._nm_note(ex)
    finally:
        render._LANG.reset(token)
    assert "n.m. pada Laba (kolom aktual): alasan baru." in note


def test_driver_values_keep_their_figures_inside_english_templates():
    with prose_lang.building("en"):
        assert prose_lang.label("Biaya kredit") == "Cost of credit"
        assert prose_lang.label("US$13.002/t") == "US$13.002/t"      # a figure and its unit
        assert prose_lang.label("50,3 ha/tahun") == "50,3 ha/yr"     # figures as written
        assert prose_lang._UNTRANSLATED in prose_lang.label("alasan tanpa terjemahan")
    assert prose_lang.label("Biaya kredit") == "Biaya kredit"
