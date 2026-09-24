"""Report gallery: public summaries, confined file serving, landing integration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import gallery, landing  # noqa: E402
from test_landing_routes import Server, get  # noqa: E402


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
    assert held["held_reason"].startswith("Gate 5")


def test_artifacts_are_confined_to_the_reports_folder(tmp_path):
    _report(tmp_path, "AAAA")
    assert gallery.artifact(tmp_path, "AAAA", "pdf")[1] == "application/pdf"
    assert gallery.artifact(tmp_path, "../AAAA", "pdf") is None
    assert gallery.artifact(tmp_path, "AAAA", "json") is None
    assert gallery.artifact(tmp_path, "ZZZZ", "pdf") is None


def test_landing_features_a_real_report_and_lists_coverage(tmp_path):
    _report(tmp_path, "AAAA")
    _report(tmp_path, "BBBB", published=False)
    page = landing.render_landing(gallery.load(tmp_path))
    assert "Hasil riset nyata" in page and 'href="/laporan/AAAA/pdf"' in page
    assert "1 company update terbit, 1 ditahan untuk review." in page
    empty = landing.render_landing([])
    assert "Ilustrasi tampilan" in empty and 'id="laporan"' not in empty


def test_gallery_routes_serve_pages_and_files(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    server = Server(tmp_path)
    try:
        status, _, body = get(server.base, "/laporan")
        assert status == 200 and b"AAAA" in body
        status, headers, body = get(server.base, "/laporan/AAAA/pdf")
        assert status == 200 and headers.get_content_type() == "application/pdf"
        assert get(server.base, "/laporan/AAAA/secrets")[0] == 404
        assert get(server.base, "/laporan/..%2FAAAA/pdf")[0] == 404
    finally:
        server.close()
