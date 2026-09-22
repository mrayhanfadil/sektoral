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
    assert len(doc["cover"]["headline"].split()) <= 10
    for b in doc["cover"]["bullets"]:
        assert len(b.split()) <= 30, b
    for p in doc["cover"]["paragraf"]:
        n = len(p["isi"].split())
        assert 90 <= n <= 160, (p["judul"], n)
    assert [e["n"] for e in doc["exhibits"]] == list(range(1, len(doc["exhibits"]) + 1))
    body = " ".join([doc["cover"]["headline"]] +
                    [p["isi"] for p in doc["cover"]["paragraf"]])
    for banned in ["—", "–", "endpoint", "payload", "engine deterministik"]:
        assert banned not in body, banned
    assert doc["meta"]["tp"] > 0 and doc["log_gate"]["G3"]["G3.4_downside"] == "lolos"


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
