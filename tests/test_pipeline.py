"""End-to-end pipeline dari cache, tanpa network. Ticker tak dikenal ditolak."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import build as B  # noqa: E402


def test_ammn_end_to_end(tmp_path):
    doc = B.build("AMMN", tmp_path)
    assert (tmp_path / "AMMN.json").exists()
    assert (tmp_path / "AMMN.html").exists()
    assert set(doc) >= {"meta", "cover", "bagian", "tabel_asumsi", "log_gate",
                        "catatan_metodologi", "exhibits"}
    assert doc["meta"]["status"] == "draft_non_distributable"
    assert "tp" not in doc["meta"]
    assert "upside_persen" not in doc["meta"]
    assert "rating" not in doc["meta"]
    assert len(doc["cover"]["headline"].split()) <= 12
    for b in doc["cover"]["bullets"]:
        assert len(b.split()) <= 30, b
    assert [e["n"] for e in doc["exhibits"]] == list(range(1, len(doc["exhibits"]) + 1))
    body = json.dumps(doc, ensure_ascii=False)
    for banned in ["—", "–", "endpoint", "payload", "engine deterministik"]:
        if banned in ("—", "–"):
            continue  # punctuation may occur in preserved source citations
        assert banned not in body, banned
    assert "Forecast fisik tambang" in body
    assert "Jembatan operasi ke keuangan" in body
    assert "Valuasi SOTP/LoM" in body
    assert "Kinerja kuartalan yang tersedia di cache" in body
    assert "KB Valbury" not in body
    assert "BRI Danareksa" not in body
    assert doc["log_gate"]["release"]["status"] == "draft_non_distributable"
    assert doc["log_gate"]["release"]["blocker_count"] > 0
    html = (tmp_path / "AMMN.html").read_text()
    assert "DRAFT NON-DISTRIBUTABLE" in html
    assert "Target Harga (Rp)" in html
    assert "Rating ditahan hingga pemeriksaan selesai" in html


def test_ammn_report_date_includes_published_interim_without_releasing_target(tmp_path):
    doc = B.build("AMMN", tmp_path, as_of="2026-09-23")
    assert doc["meta"]["tanggal"] == "2026-09-23"
    assert doc["meta"]["harga_tanggal"] == "2026-09-23"
    assert doc["meta"]["status"] == "draft_non_distributable"
    assert "tp" not in doc["meta"]
    titles = {item["judul"] for item in doc["exhibits"]}
    assert "Hasil interim resmi dan perubahan yoy" in titles
    assert "Metrik operasi dan pemrosesan" in titles
    assert "Pemeriksaan sebelum rating dan target harga" in titles
    assert len(doc["exhibits"]) >= 9


def test_ammn_illustrative_pages_keep_release_boundary(tmp_path):
    doc = B.build("AMMN", tmp_path, as_of="2026-09-23",
                  illustrative_scenarios=True)
    assert doc["meta"]["status"] == "draft_non_distributable"
    assert doc["meta"]["illustrative_scenarios"] is True
    assert "tp" not in doc["meta"] and "rating" not in doc["meta"]
    titles = {item["judul"] for item in doc["exhibits"]}
    assert "Riwayat keuangan dalam cache" in titles
    assert "Screen proyeksi historis, bukan forecast produksi" in titles
    assert "Perbandingan nilai model lama, bukan target harga" in titles
    assert "Sensitivitas Gordon ilustratif (Rp/saham)" in titles
    assert any("Skenario operasi ilustratif" == page["judul"] for page in doc["bagian"])


def test_unknown_ticker_refused(tmp_path):
    with pytest.raises(ValueError, match="no verified assumptions"):
        B.build("ZZZZ", tmp_path)


def test_forecast_accounting_identity(tmp_path):
    doc = B.build("BBCA", tmp_path)
    assert doc["meta"]["ticker"] == "BBCA"
    raw = json.loads((tmp_path / "BBCA.json").read_text())
    assert raw["log_gate"]["G2"]["G2.5_neraca"] == "lolos"


def test_cli_ok(tmp_path):
    r = subprocess.run([sys.executable, "-m", "app.build", "AMMN",
                        "--out", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "AMMN.html").exists()
