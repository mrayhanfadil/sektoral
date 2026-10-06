"""Regression tests for Sectoral branding invariants (spec-to-repo audit).

Spec under test (Sectoral Design System):
- Primary deep blue #0928B1, paper white #FFFFFF, text #000000,
  grid/rules #E0E0E0, highlight #E1E9FF. The Figma report templates
  (Others, nodes 2592-2 / 2627-897) fill even table rows with the highlight
  #E1E9FF; #B4C7FF stays the second chart series.
- Roboto only, on screen and in print (Regular to Black Italic).
- Charts use the six-color series
  #0928B1 / #B4C7FF / #3ED628 / #1DCD9F / #0047AB / #7596FF,
  with a black baseline and subtle grid.
- Logo: "E" of blue/teal/green bars inside the S + E-bars + "CTORAL"
  wordmark.

These tests are read-only: they pin constants, generated CSS/SVG, the
web page shell, and on-disk brand/font assets. They must not modify
app code.
"""
from __future__ import annotations

import re
import sys

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import render  # noqa: E402

SPEC_SERIES = ["#0928B1", "#B4C7FF", "#3ED628", "#1DCD9F", "#0047AB", "#7596FF"]

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def _norm(hexcode: str) -> str:
    return hexcode.upper()


# ---------------------------------------------------------------- palette

def test_palette_constants_match_spec():
    assert render.PRIMARY == "#0928B1"
    assert _norm(render.PAPER) == "#FFFFFF"
    assert _norm(render.INK) == "#000000"
    assert _norm(render.RULE) == "#E0E0E0"
    assert _norm(render.EVEN_ROW) == "#B4C7FF"
    assert _norm(render.HIGHLIGHT) == "#E1E9FF"
    assert _norm(render.LIME) == "#3ED628"


def test_chart_series_palette_exact_order():
    assert list(render.SERIES) == SPEC_SERIES


def test_issuer_and_index_chart_colors_come_from_series():
    assert render.ISSUER_COLOR == render.SERIES[0] == "#0928B1"
    assert render.INDEX_COLOR in render.SERIES


def test_report_css_uses_spec_colors():
    css = render.CSS
    assert "#0928B1" in css  # primary: topbar, headings, thead
    assert "#000000" in css  # body text
    assert "#E0E0E0" in css  # table/grid rules
    assert "#E1E9FF" in css  # rating block and highlight callouts
    assert "#B4C7FF" in css  # even-row fill
    assert "#ffffff" in css  # paper background


def test_old_pre_spec_colors_are_gone_from_report_css():
    css = render.CSS
    for retired in ("#002060", "#0F4C9C", "#1a1a1a", "#D27A30",
                    "#aebfd3", "#e4ebf3", "#d8e2ed", "#f8fafc"):
        assert retired not in css, retired


def test_table_header_and_even_row_rules_use_spec_tokens():
    css = render.CSS
    assert ".exhibit-table thead th{background:" + render.PRIMARY in css
    assert "nth-child(even)" in css
    assert (".exhibit-table tbody tr:nth-child(even) td{background:"
            + render.HIGHLIGHT in css)


# ------------------------------------------------------------------- font

def test_report_uses_roboto_on_screen_and_in_print():
    css = render.CSS
    assert "Roboto" in css
    lowered = css.lower()
    for foreign in ("poppins", "helvetica", "system-ui", "arial",
                    "segoe", "inter", "georgia", "times"):
        assert foreign not in lowered, foreign
    assert "@font-face" in css
    assert "body{font-family:'Roboto',sans-serif" in css
    # Print keeps Roboto and bold headings; ligatures stay off for copy-safe text.
    assert "font-weight:400!important" not in css
    assert "@media print{body,body *{font-variant-ligatures:none;" in css
    for weight, style in ((400, "normal"), (400, "italic"), (500, "normal"), (700, "normal"),
                          (700, "italic"), (900, "normal"), (900, "italic")):
        assert f"font-weight:{weight};font-style:{style}" in css, (weight, style)


def test_roboto_font_files_exist_and_embed():
    assert render._ROB_REG, "Roboto-Regular.ttf missing or unreadable"
    assert render._ROB_BOLD, "Roboto-Bold.ttf missing or unreadable"
    assert render._ROB_ITA, "Roboto-Italic.ttf missing or unreadable"
    fonts_dir = Path(render.__file__).resolve().parent / "assets" / "fonts"
    for name in ("Roboto-Regular.ttf", "Roboto-Bold.ttf", "Roboto-Italic.ttf"):
        assert (fonts_dir / name).is_file(), name


def test_web_app_uses_roboto_and_spec_tokens_not_poppins():
    web = Path(render.__file__).resolve().parent.parent / "web"
    css = (web / "src" / "index.css").read_text(encoding="utf-8")
    assert "--font-sans: Roboto" in css
    assert "Poppins" not in css and "Arial" not in css and "system-ui" not in css
    assert "font-family: Roboto" in css and "app/assets/fonts/Roboto-Regular.ttf" in css
    for token in ("#0928B1", "#D9D9D9", "#333333", "#B4C7FF", "#1DCD9F", "#3ED628"):
        assert token in css, token


# ------------------------------------------------------------------ chart

def _chart(monkeypatch):
    def payloads(endpoint):
        if endpoint == "/daily/TEST/":
            return [("issuer", {"data": [
                {"date": "2026-01-02", "close": 100},
                {"date": "2026-01-04", "close": 120},
            ]})]
        if endpoint == "/index-daily/ihsg/":
            return [("index", {"data": [
                {"date": "2026-01-02", "price": 1000},
                {"date": "2026-01-04", "price": 1100},
            ]})]
        raise AssertionError(endpoint)

    monkeypatch.setattr(render.cache_mod, "payloads", payloads)
    return render._price_chart("TEST", "2026-01-04")


def test_chart_baseline_is_black_and_grid_is_subtle(monkeypatch):
    chart = _chart(monkeypatch)
    assert "stroke='#000000'" in chart  # baseline (relative zero) line
    assert "stroke-width='1.2'" in chart
    assert "stroke='#E0E0E0'" in chart  # subtle dashed grid, no frame
    assert "stroke-dasharray='3 3'" in chart
    assert "<rect x='30' y='15'" not in chart  # no chart frame


def test_chart_uses_only_series_plus_neutral_colors(monkeypatch):
    chart = _chart(monkeypatch)
    allowed = {_norm(c) for c in SPEC_SERIES}
    allowed |= {"#000000", "#E0E0E0", "#555555", "#FFFFFF"}
    found = {_norm(m) for m in HEX.findall(chart)}
    assert found, "no colors found in chart SVG"
    assert found <= allowed, f"off-spec chart colors: {sorted(found - allowed)}"


def test_chart_draws_issuer_and_index_in_series_colors(monkeypatch):
    chart = _chart(monkeypatch)
    assert f"stroke='{render.ISSUER_COLOR}'" in chart
    assert f"stroke='{render.INDEX_COLOR}'" in chart


# ------------------------------------------------------------------- logo

def test_report_topbar_uses_canonical_repo_wordmark():
    bar = render._topbar("2026-09-23")
    assert "CTORAL" in render.LOGO_SVG
    assert render.LOGO_SVG in bar
    assert "S{" not in bar
    assert "aria-label='Sectoral'" in bar


def test_report_logo_matches_canonical_asset_exactly():
    asset = (Path(render.__file__).resolve().parent
             / "assets" / "brand" / "sectoral-logo.svg")
    # The canonical asset lives in the sibling sectors-hackathon checkout; look
    # upward so the test also works from a git worktree, and skip when absent.
    relative = Path("sectors-hackathon") / "assets" / "brand" / "sectoral-logo.svg"
    source = next((parent / relative for parent in Path(__file__).resolve().parents
                   if (parent / relative).is_file()), None)
    if source is None:
        pytest.skip("sectors-hackathon checkout not found next to this repo")
    canonical = source.read_text(encoding="utf-8")
    assert asset.is_file(), str(asset)
    assert asset.read_text(encoding="utf-8") == canonical
    assert render.LOGO_SVG == canonical
    assert 'aria-label="Sectoral"' in render.LOGO_SVG
    assert 'fill="#0928B1"' in render.LOGO_SVG
    assert 'fill="#1DCD9F"' in render.LOGO_SVG
    assert 'fill="#3ED628"' in render.LOGO_SVG


def test_web_header_uses_the_canonical_logo_file():
    web = Path(render.__file__).resolve().parent.parent / "web"
    brand = (web / "src" / "components" / "Brand.tsx").read_text(encoding="utf-8")
    layout = (web / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
    assert "app/assets/brand/sectoral-logo.svg?raw" in brand
    # The home link's label is bilingual (web/src/lib/i18n.ts).
    assert 'aria-label={t({ id: "Sectoral, beranda", en: "Sectoral, home" })}' in layout
    assert "<Logo" in layout
    logo = (Path(render.__file__).resolve().parent / "assets" / "brand" / "sectoral-logo.svg").read_text()
    assert "CTORAL" in logo
    for color in ("#0928B1", "#1DCD9F", "#3ED628"):
        assert color in logo


def test_source_lines_open_with_the_house_line_and_keep_provenance():
    from app import fmt
    assert fmt.house_source_line("Source: Sectors, Sectoral Estimates") == \
        fmt.DEFAULT_SOURCE + "; Sectors"
    assert fmt.house_source_line("Sumber: PER TTM data Sectors") == \
        fmt.DEFAULT_SOURCE + "; PER TTM data Sectors"
    assert fmt.house_source_line("Source: Company, Sectoral Estimates") == \
        fmt.DEFAULT_SOURCE


def test_header_date_uses_dd_mon_yyyy():
    html_out = render._report_header("2026-09-24", {"ticker": "JPFA"})
    assert "Company Update | 24 Sep 2026" in html_out
    assert "| 03 Agu 2026" in render._report_header("2026-08-03", {"ticker": "JPFA"})
