"""Cetak HTML ke PDF A4 via Chromium headless (Playwright sync API)."""
import base64
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"

# A4 content width with the design's 8.5 mm side margins (render.PAGE_NUM).
CONTENT_WIDTH_MM = 210 - 2 * 8.5
PX_PER_MM = 96 / 25.4
HEADER_GAP_MM = 4.0


def _repeat_cover_header(pg):
    """Print the page-1 header (two type styles, logo, blue/lime divider) on
    every later sheet.

    CSS page-margin boxes hold one text style and cannot show the logo, and
    Chromium drops text/images inside an SVG margin background. So the real
    HTML header is captured at 3x and placed as the margin-box background;
    render._running_header's text header remains the fallback.
    """
    header = pg.locator(".report-header").first
    if not header.count():
        return
    box = header.bounding_box()
    if not box or box["height"] <= 0:
        return
    png = base64.b64encode(header.screenshot(type="png")).decode("ascii")
    height_mm = box["height"] / PX_PER_MM
    pg.add_style_tag(content=(
        f"@page{{margin-top:{height_mm + HEADER_GAP_MM + 3:.1f}mm;"
        "@top-left{content:none;border:0}@top-right{content:none;border:0}"
        f"@top-center{{content:'';width:{CONTENT_WIDTH_MM}mm;"
        f"background:url('data:image/png;base64,{png}') left 0 bottom {HEADER_GAP_MM}mm"
        f"/{CONTENT_WIDTH_MM}mm {height_mm:.2f}mm no-repeat}}}}"
        "@page:first{@top-center{content:none;background:none}}"))


def to_pdf(ticker, outdir=OUT):
    from playwright.sync_api import sync_playwright
    t = ticker.upper()
    html = (outdir / f"{t}.html").read_text()
    pdf = outdir / f"{t}.pdf"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": round(CONTENT_WIDTH_MM * PX_PER_MM), "height": 1123},
                        device_scale_factor=3)
        pg.set_content(html, wait_until="load")
        pg.emulate_media(media="print")
        _repeat_cover_header(pg)
        pg.pdf(path=str(pdf), format="A4", print_background=True)
        b.close()
    return pdf
