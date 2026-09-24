import re
from app.build import build


def test_bank_report_with_missing_cash_remains_explicit_and_renderable(tmp_path):
    doc = build("BBRI", outdir=tmp_path)

    assert doc["meta"]["status"] == "draft_non_distributable"
    html = (tmp_path / "BBRI.html").read_text(encoding="utf-8")
    assert "Kas belum tersedia" in html
    assert "utang bersih belum dapat dihitung" in html
    # Search reader-visible markup only; embedded base64 fonts can contain any bytes.
    visible = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    assert "Rp0" not in visible


def test_segment_evidence_without_prior_period_remains_renderable(tmp_path):
    doc = build("SSIA", outdir=tmp_path)

    assert doc["meta"]["status"] == "draft_non_distributable"
    html = (tmp_path / "SSIA.html").read_text(encoding="utf-8")
    assert "reparasi dan overhaul" not in html.lower()
    assert "garuda" not in html.lower()
    assert "beban material" not in html.lower()
    # Loss reversal is stated only when the evidence shows it: SSIA's 1H25 was a
    # net loss of Rp32,3 miliar, so the sentence must carry both figures.
    assert "laba bersih 1h26 rp262,6 miliar, berbalik dari rugi rp32,3 miliar" in html.lower()
    assert "rp- miliar" not in html.lower()
