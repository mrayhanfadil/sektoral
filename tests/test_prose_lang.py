"""Report prose in two languages (app.prose_lang)."""
import copy

from app import prose_lang
from app.prose_lang import attach, building, english_view, t


def _doc(para, notes=("Catatan.",), headline="Laba naik"):
    return {"cover": {"headline": headline, "bullets": ["Pendapatan Rp1.234,5 miliar."],
                      "paragraf": [{"judul": "Ringkasan", "isi": para}]},
            "bagian": [{"judul": "Operasi", "paragraf": [para],
                        "cards": [{"title": "A", "text": para}]}],
            "risks": [{"judul": "Harga", "isi": para}],
            "exhibits": [], "catatan_metodologi": list(notes)}


def test_t_builds_indonesian_unless_english_is_active():
    assert t("Laba naik", "Profit rose") == "Laba naik"
    with building("en"):
        assert t("Laba naik", "Profit rose") == "Profit rose"
    assert prose_lang.lang() == "id"


def test_attach_adds_english_siblings_with_the_same_figures():
    doc = _doc("Laba naik 12,4% ke Rp1.234,5 miliar pada 1H26.")
    en = _doc("Profit rose 12,4% to Rp1.234,5 miliar in 1H26.", headline="Profit rose")
    en["cover"]["bullets"] = ["Revenue Rp1.234,5 miliar."]
    attach(doc, en)
    assert doc["cover"]["headline_en"] == "Profit rose"
    assert doc["cover"]["bullets_en"] == ["Revenue Rp1.234,5 miliar."]
    assert doc["cover"]["paragraf"][0]["isi_en"].startswith("Profit rose")
    assert doc["bagian"][0]["paragraf_en"][0].startswith("Profit rose")
    assert doc["bagian"][0]["cards"][0]["text_en"].startswith("Profit rose")
    assert doc["risks"][0]["isi_en"].startswith("Profit rose")
    # The Indonesian fields are untouched.
    assert doc["cover"]["headline"] == "Laba naik"


def test_attach_refuses_english_whose_figures_differ():
    doc = _doc("Laba naik 12,4% pada 1H26.")
    en = _doc("Profit rose 12,5% in 1H26.")
    attach(doc, en)
    assert "paragraf_en" not in doc["bagian"][0]
    assert "isi_en" not in doc["risks"][0]


def test_attach_skips_untranslated_text_and_mismatched_structure():
    doc = _doc("Laba naik.")
    same = _doc("Laba naik.")
    attach(doc, same)
    assert "paragraf_en" not in doc["bagian"][0]
    doc = _doc("Laba naik.")
    other = _doc("Profit rose.")
    other["bagian"][0]["judul"] = "Lain"
    attach(doc, other)
    assert "paragraf_en" not in doc["bagian"][0]


def test_english_view_swaps_prose_formats_figures_and_counts_fallback():
    doc = _doc("Laba naik 12,4% ke Rp1.234,5 miliar.")
    en = _doc("Profit rose 12,4% to Rp1.234,5 miliar.")
    en["cover"]["headline"] = "Laba naik"  # not translated: falls back
    attach(doc, en)
    view, fallback = english_view(doc)
    assert view["bagian"][0]["paragraf"][0] == "Profit rose 12.4% to Rp1,234.5bn."
    assert isinstance(view["bagian"][0]["paragraf"][0], prose_lang.Translated)
    assert view["cover"]["headline"] == "Laba naik"
    assert fallback >= 1
    assert not any(k.endswith("_en") for k in view["cover"])
    # The stored document keeps its siblings.
    assert "headline_en" not in doc["cover"] and "paragraf_en" in doc["bagian"][0]


def test_english_view_does_not_count_notes_the_renderer_translates():
    note = "Tanda '-' berarti angka tidak tersedia, bukan nol."
    doc = _doc("Laba naik.", notes=(note,))
    en = _doc("Profit rose.", notes=(note,))
    en["cover"]["headline"] = "Profit rose"
    en["cover"]["bullets"] = ["Revenue Rp1.234,5 miliar."]
    en["bagian"][0]["cards"][0]["title"] = "Card"
    en["risks"][0]["judul"] = "Price"
    attach(doc, en)
    _, fallback = english_view(doc)
    assert fallback == 0


def test_source_text_without_english_makes_its_field_fall_back():
    assert prose_lang.source("Presentasi H1 menyebut rekor.") == "Presentasi H1 menyebut rekor."
    with building("en"):
        assert prose_lang.source("Presentasi H1.", "The 1H deck.") == "The 1H deck."
        quoted = "Profit rose, " + prose_lang.source("presentasi menyebut rekor") + "."
    doc = _doc("Laba naik, presentasi menyebut rekor.")
    en = _doc(quoted)
    attach(doc, en)
    assert "paragraf_en" not in doc["bagian"][0]


def test_source_text_takes_english_from_the_source_dictionary(monkeypatch):
    monkeypatch.setattr(prose_lang, "_source_text", lambda: {"Rekor Juli.": "A July record."})
    with building("en"):
        assert prose_lang.source("Rekor Juli.") == "A July record."


def test_attach_refuses_english_that_still_reads_indonesian():
    doc = _doc("Pendapatan 1H26 naik ke Rp1.234,5 miliar dari Rp1.000,0 miliar.")
    en = _doc("Revenue 1H26 naik ke Rp1.234,5 miliar dari Rp1.000,0 miliar.")
    attach(doc, en)
    assert "paragraf_en" not in doc["bagian"][0]
    assert not prose_lang.mixed("Revenue rose 12,4% from a low base in 1H25.")


def _research_page(**twins):
    """The research page as `narrative` builds it in the language active."""
    from app import narrative
    insight = {"title": "Pendapatan kuartal",
               "observation": "Cache mencatat pendapatan perusahaan pada catatan terbaru.",
               "implication": "Catatan ini memberi konteks untuk memahami aktivitas usaha.",
               "caveat": "Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.",
               "citations": [{"endpoint": "/financials/quarterly/UJI/",
                              "field_path": "/revenue", "value": 1250}], **twins}
    brief = {"as_of": "2026-09-23", "insights": [insight],
             "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
             "limitations": ["Angka kuartalan historis tidak membuktikan hubungan sebab-akibat "
                             "atau kinerja mendatang.",
                             "The quarterly cross-reference was withheld because its citation "
                             "did not pass validation."]}
    return {"bagian": [narrative._research_section({"research_analysis": brief})]}


_RESEARCH_EN = {"title_en": "Quarterly revenue",
                "observation_en": "The cache records the company's revenue in its latest record.",
                "implication_en": "This record gives context for understanding business activity.",
                "caveat_en": "A single record does not explain the effect on earnings or cash flow."}


def test_research_cards_attach_the_agent_english_and_english_view_swaps_it():
    doc = _research_page(**_RESEARCH_EN)
    with building("en"):
        doc_en = _research_page(**_RESEARCH_EN)
    indonesian = copy.deepcopy(doc)
    attach(doc, doc_en)
    page = doc["bagian"][0]
    card = page["research_cards"][0]
    for key, english in _RESEARCH_EN.items():
        assert card[key] == english
    # Host summary and limitations come from data/source_text_en/research.json.
    assert page["paragraf_en"][0] == "This brief summarizes the cache findings that passed validation."
    assert page["paragraf_en"][2].startswith("Limitations: Historical quarterly figures")
    assert page["paragraf_en"][2].endswith("did not pass validation.")
    # The Indonesian page is untouched apart from the siblings.
    for key in _RESEARCH_EN:
        card.pop(key)
    page.pop("paragraf_en")
    assert doc == indonesian

    attach(doc, doc_en)
    view, fallback = english_view(doc)
    assert fallback == 0
    shown = view["bagian"][0]["research_cards"][0]
    assert shown["observation"] == _RESEARCH_EN["observation_en"]
    assert "observation_en" not in shown
    assert doc["bagian"][0]["research_cards"][0]["observation"].startswith("Cache mencatat")


def test_research_cards_without_english_fall_back_to_indonesian():
    doc = _research_page()
    with building("en"):
        doc_en = _research_page()
    attach(doc, doc_en)
    card = doc["bagian"][0]["research_cards"][0]
    assert not [key for key in card if key.endswith("_en")]
    missing = []
    view, fallback = english_view(doc, missing)
    assert fallback == 4
    assert view["bagian"][0]["research_cards"][0]["caveat"] == card["caveat"]
    assert card["observation"] in missing
