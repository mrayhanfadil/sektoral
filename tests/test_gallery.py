"""Report gallery: public summaries and confined file serving."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import gallery  # noqa: E402


def _report(folder: Path, ticker: str, published: bool = True, chain=True):
    doc = {"meta": {"ticker": ticker, "emiten": f"PT {ticker} Tbk", "tanggal": "2026-09-24",
                    "harga": 1000.0, "status": ("distributable_assumption_led" if published
                                                else "draft_non_distributable"),
                    "rating": "Hold" if published else None, "tp": 1100 if published else None,
                    "upside_persen": 10.0 if published else None,
                    "model_profile": "going_concern_fcff"},
           "method": "FY26F PER median peer x EPS skenario analis [fallback: DCF]",
           "cover": {"headline": "Laba naik"},
           "harness": {"blockers": [] if published else ["release.extreme pe target"]},
           "exhibits": ([{"judul": "Rantai metode valuasi", "data": {"rows": [
               ["1. DCF FCFF (utama)", "Dilewati", "-", "forecast"],
               ["2. PER FY skenario", "Terpilih", "Rp1.100", "ok"],
               ["3. P/BV buku", "Silang cek", "Rp900", "ok"]]}}] if chain else [])}
    (folder / f"{ticker}.json").write_text(json.dumps(doc))
    (folder / f"{ticker}.pdf").write_bytes(b"%PDF-1.4 test")
    (folder / f"{ticker}-trace.html").write_text("<html>trace</html>")


def test_summaries_hold_drafts_and_read_the_method_chain(tmp_path):
    _report(tmp_path, "AAAA")
    _report(tmp_path, "BBBB", published=False)
    (tmp_path / "notes.json").write_text("{}")
    items = gallery.load(tmp_path)
    assert [i["ticker"] for i in items] == ["AAAA", "BBBB"]
    first, held = items
    assert first["rating"] == "Hold" and first["method"] == "FY26F PER median peer x EPS skenario analis"
    assert [s["decision"] for s in first["chain"]] == ["Dilewati", "Terpilih", "Silang cek"]
    assert first["chain"][0]["step"] == "DCF FCFF"
    assert held["rating"] is None and held["tp"] is None
    assert held["held_reason"].startswith("Method Gate 5")


def test_artifacts_are_confined_to_the_reports_folder(tmp_path):
    _report(tmp_path, "AAAA")
    assert gallery.artifact(tmp_path, "AAAA", "pdf")[1] == "application/pdf"
    assert gallery.artifact(tmp_path, "../AAAA", "pdf") is None
    assert gallery.artifact(tmp_path, "AAAA", "json") is None
    assert gallery.artifact(tmp_path, "ZZZZ", "pdf") is None


def test_draft_profile_falls_back_to_the_run_manifest(tmp_path):
    _report(tmp_path, "BBBB", published=False)
    doc = json.loads((tmp_path / "BBBB.json").read_text())
    del doc["meta"]["model_profile"]
    doc["run_manifest"] = {"profile": "financial_ddm"}
    (tmp_path / "BBBB.json").write_text(json.dumps(doc))
    assert gallery.load(tmp_path)[0]["profile"] == "Bank"
