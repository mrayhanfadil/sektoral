import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pdf, render


def test_pdf_copy_text_keeps_words_intact(tmp_path):
    if not shutil.which("pdftotext"):
        pytest.skip("poppler pdftotext is unavailable")
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        pytest.skip("Playwright is unavailable")

    html = (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + render.CSS
        + "</style></head><body><div class='page'>"
        "<h3 class='sub'>Skenario nilai indikatif</h3>"
        "<p>Skenario nilai memakai DCF FCFF 3 tahun eksplisit + terminal Gordon, "
        "dibobot sama dengan exit EV/EBITDA. Nilai skenario indikatif Rp390 "
        "per saham merupakan rerata Gordon Rp643 dan exit EV/EBITDA 8,0x Rp141.</p>"
        "</div></body></html>"
    )
    (tmp_path / "SIDO.html").write_text(html, encoding="utf-8")
    out = pdf.to_pdf("SIDO", tmp_path)
    text = subprocess.run(
        ["pdftotext", "-raw", str(out), "-"],
        capture_output=True, check=True, text=True,
    ).stdout
    normalized = " ".join(text.split())
    assert "Skenario nilai indikatif" in normalized
    assert "Skenario nilai memakai DCF FCFF" in normalized
    assert "dibobot sama dengan exit EV/EBITDA" in normalized


def test_ai_research_summary_is_hidden_only_in_pdf(tmp_path):
    if not shutil.which("pdftotext"):
        pytest.skip("poppler pdftotext is unavailable")
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        pytest.skip("Playwright is unavailable")

    html = (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        + render.CSS
        + "</style></head><body>"
        "<div class='page research-summary'><h2>Ringkasan riset berbantuan AI</h2>"
        "<p>Insight ini tetap tersedia pada report HTML.</p></div>"
        "<div class='page'><h2>Bagian analisis</h2>"
        "<p>Konten utama report tetap dicetak.</p></div></body></html>"
    )
    (tmp_path / "BBRI.html").write_text(html, encoding="utf-8")
    out = pdf.to_pdf("BBRI", tmp_path)
    extracted = subprocess.run(
        ["pdftotext", "-raw", str(out), "-"],
        capture_output=True, check=True, text=True,
    ).stdout

    assert "Ringkasan riset berbantuan AI" in html
    assert "Insight ini tetap tersedia" in html
    assert "Ringkasan riset berbantuan AI" not in extracted
    assert "Bagian analisis" in extracted
    assert "Konten utama report tetap dicetak" in extracted
