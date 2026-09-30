"""Report prose in two languages (app.prose_lang)."""
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
