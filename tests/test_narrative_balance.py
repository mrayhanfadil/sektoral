from app.build import build


def test_bank_report_with_missing_cash_remains_explicit_and_renderable(tmp_path):
    doc = build("BBRI", outdir=tmp_path)

    assert doc["meta"]["status"] == "draft_non_distributable"
    html = (tmp_path / "BBRI.html").read_text(encoding="utf-8")
    assert "Kas belum tersedia" in html
    assert "utang bersih belum dapat dihitung" in html
    assert "Rp0" not in html


def test_segment_evidence_without_prior_period_remains_renderable(tmp_path):
    doc = build("SSIA", outdir=tmp_path)

    assert doc["meta"]["status"] == "draft_non_distributable"
    html = (tmp_path / "SSIA.html").read_text(encoding="utf-8")
    assert "reparasi dan overhaul" not in html.lower()
    assert "garuda" not in html.lower()
    assert "beban material" not in html.lower()
    assert "berbalik dari rugi" not in html.lower()
    assert "rp- miliar" not in html.lower()
