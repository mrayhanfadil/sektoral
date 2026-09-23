"""Regression tests for Sectoral branding invariants (spec-to-repo audit).

Spec under test (Sectoral Design System):
- Primary deep blue #0928B1, paper white #FFFFFF, text #333333,
  rules #D9D9D9, table even-row fill #B4C7FF.
- Roboto only (no Poppins or other foreign families in report CSS).
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import render, web  # noqa: E402

SPEC_SERIES = ["#0928B1", "#B4C7FF", "#3ED628", "#1DCD9F", "#0047AB", "#7596FF"]

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def _norm(hexcode: str) -> str:
    return hexcode.upper()


# ---------------------------------------------------------------- palette

def test_palette_constants_match_spec():
    assert render.PRIMARY == "#0928B1"
    assert _norm(render.PAPER) == "#FFFFFF"
    assert _norm(render.INK) == "#333333"
    assert _norm(render.RULE) == "#D9D9D9"
    assert _norm(render.EVEN_ROW) == "#B4C7FF"


def test_chart_series_palette_exact_order():
    assert list(render.SERIES) == SPEC_SERIES


def test_issuer_and_index_chart_colors_come_from_series():
    assert render.ISSUER_COLOR == render.SERIES[0] == "#0928B1"
    assert render.INDEX_COLOR in render.SERIES


def test_report_css_uses_spec_colors():
    css = render.CSS
    assert "#0928B1" in css  # primary: topbar, headings, thead
    assert "#333333" in css  # body text
    assert "#D9D9D9" in css  # table/panel rules
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
            + render.EVEN_ROW in css)


# ------------------------------------------------------------------- font

def test_report_css_is_roboto_only():
    css = render.CSS
    assert "Roboto" in css
    lowered = css.lower()
    for foreign in ("poppins", "arial", "helvetica", "system-ui",
                    "segoe", "inter", "georgia", "times"):
        assert foreign not in lowered, foreign
    assert "@font-face" in css
    assert "font-family:'Roboto'" in css


def test_roboto_font_files_exist_and_embed():
    assert render._ROB_REG, "Roboto-Regular.ttf missing or unreadable"
    assert render._ROB_BOLD, "Roboto-Bold.ttf missing or unreadable"
    assert render._ROB_ITA, "Roboto-Italic.ttf missing or unreadable"
    fonts_dir = Path(render.__file__).resolve().parent / "assets" / "fonts"
    for name in ("Roboto-Regular.ttf", "Roboto-Bold.ttf", "Roboto-Italic.ttf"):
        assert (fonts_dir / name).is_file(), name


def test_web_shell_uses_roboto_and_spec_tokens_not_poppins():
    page = web._page().decode("utf-8")
    assert "Roboto" in page
    assert "Poppins" not in page
    assert "Arial" not in page
    assert "system-ui" not in page
    assert "@font-face{font-family:Roboto" in page
    assert "data:font/ttf;base64," in page
    assert "#0928B1" in page
    assert "#D9D9D9" in page
    assert "#333333" in page


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
    assert "stroke='#000000'" in chart  # baseline (100) line
    assert "stroke-width='1.2'" in chart
    assert "stroke='#E6E6E6'" in chart  # subtle grid
    assert "stroke-width='0.5'" in chart


def test_chart_uses_only_series_plus_neutral_colors(monkeypatch):
    chart = _chart(monkeypatch)
    allowed = {_norm(c) for c in SPEC_SERIES}
    allowed |= {"#000000", "#E6E6E6", "#555555", "#333333"}
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
    canonical = (Path(__file__).resolve().parents[2]
                / "sectors-hackathon" / "assets" / "brand" / "sectoral-logo.svg").read_text(encoding="utf-8")
    assert asset.is_file(), str(asset)
    assert asset.read_text(encoding="utf-8") == canonical
    assert render.LOGO_SVG == canonical
    assert 'aria-label="Sectoral"' in render.LOGO_SVG
    assert 'fill="#0928B1"' in render.LOGO_SVG
    assert 'fill="#1DCD9F"' in render.LOGO_SVG
    assert 'fill="#3ED628"' in render.LOGO_SVG


def test_web_header_shows_logo_wordmark_and_title():
    page = web._page().decode("utf-8")
    assert "<title>Sectoral | Company update</title>" in page
    assert "CTORAL" in page
    assert "#0928B1" in web._LOGO_SVG
    assert "#1DCD9F" in web._LOGO_SVG
    assert "#3ED628" in web._LOGO_SVG
    assert "Sectoral" in page
