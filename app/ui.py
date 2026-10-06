"""Brand tokens and embedded Roboto for the standalone trace HTML.

The web app itself is the React frontend in ``web/`` (its Tailwind theme
carries the same tokens). The audit trace written next to each report is a
self-contained HTML file, so it embeds the fonts as data URIs.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"


def _embedded_font(filename: str) -> str:
    try:
        encoded = base64.b64encode((_ASSETS / "fonts" / filename).read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:font/ttf;base64,{encoded}"


@lru_cache(maxsize=1)
def font_faces() -> str:
    faces = []
    for filename, weight, style in (
        ("Roboto-Regular.ttf", "400", "normal"),
        ("Roboto-Bold.ttf", "500 900", "normal"),
        ("Roboto-Italic.ttf", "400", "italic"),
    ):
        src = _embedded_font(filename)
        if src:
            faces.append(
                f"@font-face{{font-family:Roboto;src:url('{src}') format('truetype');"
                f"font-weight:{weight};font-style:{style};font-display:swap}}"
            )
    return "\n".join(faces)


# Sektoral Design System: primary #0928B1, charcoal #333333, rule #D9D9D9,
# table tint #B4C7FF, accents #1DCD9F / #3ED628.
TOKENS = """
:root{
  --blue:#0928B1;--blue-hover:#071F8A;--blue-50:#F2F5FF;--blue-100:#E3E9FF;--tint:#B4C7FF;
  --ink:#333333;--ink-soft:#5B5F6B;--rule:#D9D9D9;--rule-soft:#ECEEF2;
  --surface:#FFFFFF;--canvas:#F7F8FA;
  --teal:#1DCD9F;--green:#3ED628;
  --ok-bg:#E8FAF4;--ok-ink:#0B6B50;--warn-bg:#FFF6E0;--warn-ink:#7A4B00;--warn-rule:#F0B429;
  --err-bg:#FDECEC;--err-ink:#9B1C1C;
  --radius:12px;--radius-sm:8px;
  --font:Roboto,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  --mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  --shadow:0 1px 2px rgba(16,24,40,.05),0 8px 24px -12px rgba(16,24,40,.12);
}
"""
