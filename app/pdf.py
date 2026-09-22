"""Cetak HTML ke PDF A4 via Chromium headless (Playwright sync API)."""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"


def to_pdf(ticker, outdir=OUT):
    from playwright.sync_api import sync_playwright
    t = ticker.upper()
    html = (outdir / f"{t}.html").read_text()
    pdf = outdir / f"{t}.pdf"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html, wait_until="load")
        pg.pdf(path=str(pdf), format="A4", print_background=True)
        b.close()
    return pdf
