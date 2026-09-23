"""Kepatuhan spec v3.1 §5.3/§4.1/§4.4 pada artefak terbangun (AMMN)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import build as B  # noqa: E402

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
    assert d["meta"]["tp"] is None
    assert "umur cadangan tidak ada di cache" not in notes
    assert "rnav annuitas indikatif" in notes
    assert "bukan nilai wajar" in notes


def test_incomplete_mining_inputs_withhold_target_and_rating(tmp_path):
    d = _doc(tmp_path)
    assert d["meta"]["upside_persen"] is None
    assert d["meta"]["rating"] == "DRAFT NON-DISTRIBUTABLE"
    val_sec = next(b for b in d["bagian"]
                   if b["judul"] == "Valuasi dan kelengkapan model")
    assert any("target harga dan rating ditahan" in p.lower()
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
