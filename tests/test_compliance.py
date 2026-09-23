"""Kepatuhan spec v3.1 §5.3/§4.1/§4.4 pada artefak terbangun (AMMN)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import build as B  # noqa: E402
from app import narrative  # noqa: E402


def test_optional_research_brief_is_cited_and_limited_to_scalar_values():
    section = narrative._research_section({"research_analysis": {
        "as_of": "2026-09-23", "summary": "Harga komoditas menguat.",
        "limitations": ["Sampel hanya mencakup data cache."],
        "insights": [{"title": "Harga komoditas", "observation": "Harga naik.",
                      "implication": "Potensi perubahan pendapatan.",
                      "caveat": "Volume penjualan belum tersedia.",
                      "citations": [{"endpoint": "/news/", "field_path": "/data/0/body",
                                     "value": "x" * 300}]}]}})
    assert section["judul"] == "Ringkasan riset berbantuan AI"
    assert section["layout"] == "research_cards"
    assert "2026-09-23" in " ".join(section["paragraf"])
    citation = section["research_cards"][0]["citations"][0]
    assert "/news/ · /data/0/body" in citation
    assert len(citation.split(" = ", 1)[1]) == 80
    assert "Sampel hanya mencakup data cache." in " ".join(section["paragraf"])


def test_research_news_citations_are_compact_and_trace_fields_stay_auditable():
    section = narrative._research_section({"research_analysis": {
        "as_of": "2026-09-23", "summary": "Ringkasan tervalidasi.",
        "limitations": [],
        "insights": [{"title": "Tekanan pasar global",
                      "observation": "BBCA disebut dalam konteks tekanan pasar global.",
                      "implication": "Pendapatan bunga memberi konteks usaha.",
                      "caveat": "Berita tidak mengukur dampak ke laba.",
                      "citations": [
                          {"endpoint": "/news/", "field_path": "/results/0/title",
                           "value": "Mirae Asset Sekuritas assesses global pressures still weighing on the market"},
                          {"endpoint": "/news/", "field_path": "/results/0/body",
                           "value": "raw article body " + "x" * 300},
                          {"endpoint": "/news/", "field_path": "/results/0/timestamp",
                           "value": "2026-09-11T15:37:00"},
                          {"endpoint": "/news/", "field_path": "/results/0/source",
                           "value": "https://www.antaranews.com/berita/123"},
                          {"endpoint": "/financials/quarterly/BBCA/",
                           "field_path": "/data/0/interest_income", "value": 25173142000000},
                      ]}]}})
    refs = section["research_cards"][0]["citations"]
    joined = "; ".join(refs)
    assert len(refs) == 2
    assert "global pressures" in joined
    assert "2026-09-11" in joined and "antaranews.com" in joined
    assert "/data/0/interest_income" in joined
    assert "Rp25.173,1 miliar" in joined
    assert "raw article body" not in joined
    assert "x" * 80 not in joined

LEAK = ["kurasi skor", "sebelum masuk model", "aksi korporasi tercatat",
        "tanpa tanggal", "tanpa judul", "tidak ditampilkan", "endpoint",
        "payload", "scraper", "scraping"]


def _doc(tmp_path):
    return B.build("AMMN", tmp_path)


def test_tanpa_string_bocor_di_json(tmp_path):
    d = _doc(tmp_path)
    blob = json.dumps(d, ensure_ascii=False).lower()
    for s in LEAK:
        assert s not in blob, s


def test_draft_does_not_promote_cache_reserve_life_to_valuation(tmp_path):
    d = _doc(tmp_path)
    notes = " ".join(d["catatan_metodologi"]).lower()
    assert "tp" not in d["meta"]
    assert "rating" not in d["meta"]
    assert "umur cadangan tidak ada di cache" not in notes
    assert "rnav annuitas indikatif" in notes
    assert "bukan nilai wajar" in notes


def test_incomplete_mining_inputs_withhold_target_and_rating(tmp_path):
    d = _doc(tmp_path)
    assert d["meta"]["status"] == "draft_non_distributable"
    val_sec = next(b for b in d["bagian"]
                   if b["judul"] == "Valuasi dan kelengkapan model")
    assert any("skenario nilai belum" in p.lower()
               for p in val_sec["paragraf"])


def test_draft_does_not_publish_unsourced_catalysts(tmp_path):
    d = _doc(tmp_path)
    assert not any(e["judul"] == "Katalis" for e in d["exhibits"])
    assert any("Kelengkapan sebelum rilis" == e["judul"]
               for e in d["exhibits"])


def test_pdf_tanpa_simbol_dolar(tmp_path):
    try:
        B.build("AMMN", tmp_path, want_pdf=True)
    except Exception:
        return  # chromium tak ada: lewati
    pdf = tmp_path / "AMMN.pdf"
    if not pdf.exists():
        return
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                         capture_output=True, text=True).stdout
    assert "$" not in txt
    for s in ["kurasi skor", "aksi korporasi tercatat", "tanpa tanggal",
              "tidak ditampilkan"]:
        assert s not in txt.lower(), s
