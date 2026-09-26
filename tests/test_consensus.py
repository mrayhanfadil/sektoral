"""Dated analyst consensus (app.consensus, plan 2.2)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import consensus as C  # noqa: E402


def _write(tmp_path, **kw):
    doc = {"ticker": "UJI", "as_of": "2026-09-25", "source_title": "Agregator",
           "source_url": "https://example.com/uji", "analysts": 5, "buy": 3, "hold": 1,
           "sell": 1, "target_avg": 1200, "target_high": 1500, "target_low": 900,
           "estimates": None, "estimates_note": "estimasi tidak tersedia", **kw}
    (tmp_path / "UJI.json").write_text(json.dumps(doc))


def test_consensus_after_the_report_date_is_not_used(tmp_path):
    _write(tmp_path)
    doc, why = C.load("UJI", "2026-09-24", tmp_path)
    assert doc is None and "sesudah tanggal laporan" in why
    e = C.exhibit("UJI", "2026-09-24", 1000, "Buy", 800, tmp_path)
    assert e["data"]["rows"][1][1].startswith("tidak tersedia")


def test_consensus_on_or_before_the_report_date_is_shown_with_source(tmp_path):
    _write(tmp_path)
    e = C.exhibit("UJI", "2026-09-25", 1000, "Buy", 800, tmp_path)
    rows = dict((r[0], r[1]) for r in e["data"]["rows"])
    assert rows["Rata-rata target konsensus (5 analis)"] == "Rp1.200"
    assert rows["Target Sektoral terhadap rata-rata konsensus"] == "-16,7%"
    assert rows["Rekomendasi (beli / tahan / jual)"] == "3 / 1 / 1"
    assert rows["Estimasi konsensus pendapatan, EBITDA, laba"] == "estimasi tidak tersedia"
    assert "diambil 2026-09-25" in rows["Sumber konsensus"]


def test_missing_consensus_says_so(tmp_path):
    doc, why = C.load("NONE", "2026-09-25", tmp_path)
    assert doc is None and "belum dikumpulkan" in why


def test_every_covered_ticker_has_a_dated_sourced_consensus():
    for path in C.ROOT.glob("*.json"):
        doc = json.loads(path.read_text())
        assert doc["as_of"] and doc["source_url"].startswith("https://")
        assert doc["target_low"] <= doc["target_avg"] <= doc["target_high"]


def test_a_withheld_target_says_why_instead_of_nm(tmp_path):
    _write(tmp_path)
    e = C.exhibit("UJI", "2026-09-25", None, None, 800, tmp_path)
    cells = [c for row in e["data"]["rows"] for c in row]
    assert "n.m." not in cells
    assert "tidak dihitung: target harga Sektoral ditahan" in cells
