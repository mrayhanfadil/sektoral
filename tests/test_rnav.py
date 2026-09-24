"""Batch D: LoM RNAV + revenue bridge nyambung ke forecast."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import mineops, rnav  # noqa: E402


def test_nav_stream_anuitas_tanpa_terminal():
    s = rnav.nav_stream(100.0, 1000.0, 10.0, 0.5, 0.10)
    assert s["life"] == 10.0
    assert s["annual_cf"] == 100 * 10 * 0.5
    exp = 500 * (1 - 1.1 ** -10) / 0.10
    assert abs(s["pv"] - exp) < 1e-6
    # Terbukti tanpa terminal: PV < CF flat 10 thn + 1 thn penuh sekalipun.
    assert s["pv"] < 500 * 10


def test_nav_stream_tanpa_produksi():
    assert rnav.nav_stream(0, 1000.0, 10.0, 0.5, 0.10)["pv"] is None


def test_ammn_dua_aliran_material():
    mo = mineops.load("AMMN")
    r = rnav.build(mo, 0.52, 0.105, 20000, 60000, 36200)
    assert len(r["streams"]) == 2
    assert all(s["nav_rpbn"] > 10000 for s in r["streams"])
    assert r["total_nav_rpbn"] == sum(s["nav_rpbn"] for s in r["streams"])
    assert "Yahoo Finance IDR=X" in r["fx_basis"] or "asumsi analis Rp16.000/USD" in r["fx_basis"]


def test_bridge_flag_ammn():
    mo = mineops.load("AMMN")
    r = rnav.build(mo, 0.52, 0.105, 20000, 60000, 36200)
    b = r["bridge"]
    assert 0.4 < b["payability"] < 0.8  # payability parsial, bukan 100%
    assert b["needs_explanation"] is True


def test_forecast_g28_hanya_tambang():
    from app import forecast, intake
    fam, _ = intake.load("AMMN")
    f = forecast.build(fam)
    assert f["bridge"] is not None
    assert f["g2"]["G2.8_bridge"][0] == "dilabeli"
    fbb, _ = intake.load("BBCA")
    fb = forecast.build(fbb)
    assert fb["bridge"] is None
    assert "G2.8_bridge" not in fb["g2"]


def test_method_select_ddm_bbca(tmp_path):
    from app import build as B
    d = B.build("BBCA", tmp_path, method="ddm")
    assert d["method_select"] == "ddm"
    assert d["method"] == "DDM (dividen, Rp)"
    assert any("dipilih analis" in n for n in d["catatan_metodologi"])


def test_method_select_ditolak_jujur(tmp_path):
    import pytest
    from app import build as B
    with pytest.raises(ValueError):
        B.build("BBCA", tmp_path, method="rnav")
    with pytest.raises(ValueError):
        B.build("AMMN", tmp_path, method="bogus")


def test_bridge_minority_row(tmp_path):
    from app import build as B
    d = B.build("AMMN", tmp_path)
    fx = next(e for e in d["exhibits"]
              if e["judul"] == "Input SOTP yang belum lengkap")
    paths = {row[0] for row in fx["data"]["rows"]}
    assert "Kepentingan nonpengendali" in paths
    assert "tp" not in d["meta"]


def test_bank_ddm_full_path(tmp_path):
    from app import build as B
    d = B.build("BBCA", tmp_path)
    titles = [e["judul"] for e in d["exhibits"]]
    assert "Komponen Cost of Equity" in titles
    assert "Sensitivitas DDM (CoE x g)" in titles
    assert "Sensitivitas Inverse CoE (CoE x ROE)" in titles
    val_sec = next(b for b in d["bagian"] if b["judul"] == "Skenario nilai")
    assert any("lintasan ROE" in p for p in val_sec["paragraf"])
    blob = json.dumps(d, ensure_ascii=False).lower()
    assert "tanpa histori coe di data sectors" in blob  # band jujur absen


def test_rnav_discount_sens(tmp_path):
    from app import build as B
    d = B.build("AMMN", tmp_path)
    titles = [e["judul"] for e in d["exhibits"]]
    assert "Discount Rate per Aset" not in titles
    assert "Sensitivitas RNAV (diskon x harga)" not in titles
    assert "tp" not in d["meta"]
    assert any("SOTP/LoM belum dapat direkonsiliasi" in p["isi"]
               for p in d["cover"]["paragraf"])
