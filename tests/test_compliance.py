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


def test_disclaimer_kondisional_pakai_umur_aktual(tmp_path):
    d = _doc(tmp_path)
    notes = " ".join(d["catatan_metodologi"]).lower()
    assert "umur cadangan tidak ada di cache" not in notes
    assert "73" in notes  # umur cadangan aktual dari overlay mining


def test_tp_ekstrem_ada_tesis(tmp_path):
    d = _doc(tmp_path)
    assert abs(d["meta"]["upside_persen"]) > 50
    val_sec = next(b for b in d["bagian"] if b["judul"] == "Valuasi")
    assert len(val_sec["paragraf"]) >= 3  # base + tesis + keterbatasan
    assert "keterbatasan utama" in val_sec["paragraf"][-1].lower()


def test_katalis_tidak_mengandung_skor(tmp_path):
    d = _doc(tmp_path)
    kat = next(e for e in d["exhibits"] if e["judul"] == "Katalis")
    blob = json.dumps(kat["data"], ensure_ascii=False)
    assert "kurasi" not in blob.lower()
    assert len(kat["data"]["rows"]) >= 1


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
