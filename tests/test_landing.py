"""Regression tests for the Sectoral landing page contract.

Spec under test:
- Implementation contract: app.landing.render_landing() -> str
- First-child-body direction-contract comment carrying seed ae210778 + exact FINISH clause.
- Semantic document structure and accessibility basics (lang, charset, viewport, title, landmarks, alt/aria).
- Sectoral brand colors (#0928B1 primary, #333333 charcoal, #D9D9D9 rule, #B4C7FF accent/fill) and Roboto typography.
- Primary landing CTA linking to /research and secondary anchor linking to #cara-kerja (with target id="cara-kerja").
- Brand assets: logo (/assets/brand/sectoral-logo.svg) and research flow illustration (/assets/brand/research-flow.svg).
- Dated Sectors-data source caveat (no live market feed, no internal cache wording) and no-investment-advice disclaimer.
- Explicit partial-evidence handling policy (no silent guessing or synthetic fabrication).
- Negative compliance: no unsupported copy (no real-time/live market data, no trading/execution, no invented metrics/testimonials, no guaranteed outcomes).
- Responsive layout, focus affordances, and reduced-motion affordance when animations/transitions are defined.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def landing_html() -> str:
    """Invokes app.landing.render_landing() to obtain the landing page HTML."""
    try:
        from app.landing import render_landing
    except ImportError as err:
        pytest.fail(f"Failed to import render_landing from app.landing: {err}")
    html = render_landing()
    assert isinstance(html, str), f"render_landing() must return str, got {type(html).__name__}"
    assert len(html.strip()) > 0, "render_landing() returned an empty string"
    return html


# ------------------------------------------------ implementation contract


def test_render_landing_contract():
    """Verifies that app.landing.render_landing exists, is callable, and returns a string."""
    from app import landing
    assert hasattr(landing, "render_landing"), "app.landing must expose render_landing()"
    assert callable(landing.render_landing), "app.landing.render_landing must be callable"
    result = landing.render_landing()
    assert isinstance(result, str), f"Expected str return type, got {type(result).__name__}"
    assert len(result.strip()) > 0, "render_landing() returned empty string"


def test_first_child_body_direction_contract_comment(landing_html: str):
    """Verifies that the first child inside <body> is a direction-contract comment

    carrying 'seed ae210778' and the exact 'FINISH' clause.
    """
    body_match = re.search(r"<body[^>]*>", landing_html, re.IGNORECASE)
    assert body_match is not None, "HTML document must contain a <body> tag"

    body_content = landing_html[body_match.end():].lstrip()
    assert body_content.startswith("<!--"), (
        "The first child element inside <body> must be an HTML comment (<!-- ... -->)"
    )

    comment_match = re.match(r"^<!--([\s\S]*?)-->", body_content)
    assert comment_match is not None, "Failed to parse the first-child comment inside <body>"

    comment_text = comment_match.group(1).strip()
    assert "seed ae210778" in comment_text, (
        f"First-child body comment must contain 'seed ae210778', got: {comment_text!r}"
    )
    assert re.search(r"\bFINISH\b", comment_text), (
        f"First-child body comment must contain exact 'FINISH' clause, got: {comment_text!r}"
    )


# -------------------------------- semantic document & accessibility basics


def test_semantic_document_structure(landing_html: str):
    """Verifies standard HTML5 doctype, html lang attribute, charset, viewport, and title."""
    assert re.match(r"^\s*<!doctype\s+html", landing_html, re.IGNORECASE), (
        "Document must begin with standard <!DOCTYPE html> declaration"
    )
    assert re.search(r'<html\s+[^>]*lang=["\']id', landing_html, re.IGNORECASE), (
        "HTML tag must declare Bahasa Indonesia lang attribute (e.g. lang='id')"
    )
    assert re.search(r'<meta\s+[^>]*charset=["\']?utf-8', landing_html, re.IGNORECASE), (
        "Document head must declare UTF-8 character encoding"
    )
    assert re.search(
        r'<meta\s+[^>]*name=["\']viewport["\'][^>]*content=["\'][^"\']*width=device-width',
        landing_html,
        re.IGNORECASE,
    ), "Document head must contain responsive viewport meta tag with width=device-width"

    title_match = re.search(r"<title>([\s\S]*?)</title>", landing_html, re.IGNORECASE)
    assert title_match is not None, "Document must have a <title> tag"
    title_text = title_match.group(1).lower()
    assert "sectoral" in title_text or "sektoral" in title_text, (
        f"Document <title> must reference Sectoral, got: {title_match.group(1)!r}"
    )


def test_semantic_landmarks_and_hierarchy(landing_html: str):
    """Verifies presence of semantic landmarks (header, main, footer) and heading hierarchy."""
    assert re.search(r"<header[\s>]", landing_html, re.IGNORECASE), (
        "Document must contain a <header> landmark"
    )
    assert re.search(r"<main[\s>]", landing_html, re.IGNORECASE), (
        "Document must contain a <main> landmark"
    )
    assert re.search(r"<footer[\s>]", landing_html, re.IGNORECASE), (
        "Document must contain a <footer> landmark"
    )
    assert re.search(r"<h1[\s>]", landing_html, re.IGNORECASE), (
        "Document must contain an <h1> primary heading"
    )
    assert re.search(r"<h2[\s>]", landing_html, re.IGNORECASE), (
        "Document must contain <h2> section headings"
    )


def test_accessibility_affordances(landing_html: str):
    """Verifies that images have alt attributes and focus states are defined."""
    img_tags = re.findall(r"<img[^>]*>", landing_html, re.IGNORECASE)
    for img in img_tags:
        assert re.search(r'\balt=["\']', img, re.IGNORECASE), (
            f"Image tag missing alt attribute: {img}"
        )

    # Focus styles must be defined for keyboard accessibility
    assert ":focus" in landing_html or ":focus-visible" in landing_html, (
        "Styles must define visible focus indicators (:focus or :focus-visible)"
    )


# --------------------------------- brand identity: exact colors & roboto


def test_exact_sectoral_brand_colors(landing_html: str):
    """Verifies exact Sectoral Design System palette tokens are used."""
    # Primary deep blue #0928B1
    assert "#0928B1" in landing_html or "#0928b1" in landing_html, (
        "Primary brand blue #0928B1 must be used in landing page"
    )
    # Charcoal text #333333 / #333
    assert "#333333" in landing_html or "#333" in landing_html, (
        "Charcoal text color #333333 / #333 must be used for typography"
    )
    # Rule / border gray #D9D9D9
    assert "#D9D9D9" in landing_html or "#d9d9d9" in landing_html, (
        "Rule gray #D9D9D9 must be used for borders/rules"
    )

    # Verify no retired off-spec colors from earlier iterations
    retired_colors = [
        "#002060", "#0F4C9C", "#1a1a1a", "#D27A30",
        "#aebfd3", "#e4ebf3", "#d8e2ed", "#f8fafc",
    ]
    lowered = landing_html.lower()
    for retired in retired_colors:
        assert retired.lower() not in lowered, (
            f"Retired off-spec color {retired} found in landing HTML"
        )


def test_roboto_typography_only(landing_html: str):
    """Verifies Roboto is used and deprecated font families (e.g. Poppins) are excluded."""
    assert "Roboto" in landing_html, "Landing page must specify Roboto font family"
    assert "@font-face" in landing_html, "Landing page should define @font-face for typography"

    # Ensure deprecated pre-spec font families are not used
    assert "poppins" not in landing_html.lower(), (
        "Deprecated font family 'Poppins' must not appear in landing page"
    )


# ----------------------------------- cta, anchors, and asset references


def test_landing_cta_and_navigation_anchors(landing_html: str):
    """Verifies primary CTA links to /research and secondary anchor links to #cara-kerja."""
    # Primary CTA -> /research
    cta_link = re.search(r'<a\s+[^>]*href=["\']/research["\']', landing_html, re.IGNORECASE)
    cta_form = re.search(r'<form\s+[^>]*action=["\']/research["\']', landing_html, re.IGNORECASE)
    assert cta_link or cta_form, (
        "Landing page must contain a primary CTA linking or submitting to '/research'"
    )

    # Secondary anchor -> #cara-kerja
    assert re.search(r'<a\s+[^>]*href=["\']#cara-kerja["\']', landing_html, re.IGNORECASE), (
        "Landing page must contain a secondary anchor link to '#cara-kerja'"
    )

    # Target element for #cara-kerja must exist in the document
    assert re.search(r'<[a-zA-Z0-9]+\s+[^>]*id=["\']cara-kerja["\']', landing_html, re.IGNORECASE), (
        "Landing page must contain a target section/element with id='cara-kerja'"
    )


def test_brand_asset_references(landing_html: str):
    """Verifies references to brand assets: sectoral-logo.svg and research-flow.svg."""
    assert "/assets/brand/sectoral-logo.svg" in landing_html, (
        "Landing page must reference the logo asset at '/assets/brand/sectoral-logo.svg'"
    )
    assert "/assets/brand/research-flow.svg" in landing_html, (
        "Landing page must reference the workflow illustration at '/assets/brand/research-flow.svg'"
    )


# ----------------------------- caveats, disclaimers, & partial evidence


def _visible_text(html: str) -> str:
    html = re.sub(r"<!--[\s\S]*?-->", " ", html)
    html = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html, flags=re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", html).lower()


def test_dated_sectors_source_caveat(landing_html: str):
    """Verifies disclosure that market data comes from dated Sectors data, not a live feed."""
    text_content = _visible_text(landing_html)
    assert "data sectors" in text_content, (
        "Landing page must state that market data is sourced from Sectors data"
    )
    assert "tanpa panggilan data pasar langsung" in text_content, (
        "Landing page must state that research runs without live market-data calls"
    )


def test_visible_copy_avoids_cache_wording(landing_html: str):
    """Internal storage wording ("cache", database paths) stays out of product copy."""
    text_content = _visible_text(landing_html)
    alt_text = " ".join(re.findall(r'alt=["\']([^"\']*)', landing_html)).lower()
    assert "cache" not in text_content
    assert "cache" not in alt_text
    assert "sectors_cache.db" not in landing_html


def test_no_investment_advice_disclaimer(landing_html: str):
    """Verifies clear no-financial-advice / no-investment-recommendations disclaimer."""
    text_content = re.sub(r"<[^>]+>", " ", landing_html).lower()
    has_disclaimer = (
        "bukan rekomendasi investasi" in text_content
        or "bukan saran investasi" in text_content
        or "bukan nasihat investasi" in text_content
        or "tidak memberikan rekomendasi investasi" in text_content
        or "informasi dan analisis" in text_content
    )
    assert has_disclaimer, (
        "Landing page must prominently include a no-investment-advice disclaimer"
    )


def test_explicit_partial_evidence_handling(landing_html: str):
    """Verifies disclosure of explicit partial/incomplete evidence handling."""
    text_content = re.sub(r"<[^>]+>", " ", landing_html).lower()
    has_partial_handling = (
        "parsial" in text_content
        or "partial" in text_content
        or "bukti belum cukup" in text_content
        or "batas bukti" in text_content
        or "bukti tidak lengkap" in text_content
        or "bukti terbatas" in text_content
    )
    assert has_partial_handling, (
        "Landing page must explain that incomplete evidence is explicitly labeled partial"
    )


# -------------------------------- negative compliance: unsupported copy


def test_no_unsupported_market_or_trading_claims(landing_html: str):
    """Verifies that marketing copy does not claim real-time data or trade execution."""
    text_content = re.sub(r"<[^>]+>", " ", landing_html).lower()

    # Disallowed real-time / live market claims
    unsupported_realtime = [
        "real-time market", "real time market", "live market data",
        "live data feed", "harga live streaming", "live price updates",
    ]
    for claim in unsupported_realtime:
        assert claim not in text_content, (
            f"Unsupported real-time market claim found in landing copy: '{claim}'"
        )

    # Disallowed active trading / automated order execution claims
    unsupported_trading = [
        "eksekusi order otomatis", "eksekusi trading otomatis", "auto-trade",
        "beli saham otomatis", "direct brokerage connection", "live order routing",
    ]
    for claim in unsupported_trading:
        assert claim not in text_content, (
            f"Unsupported trading/brokerage execution claim found in landing copy: '{claim}'"
        )


def test_no_invented_metrics_or_guaranteed_outcomes(landing_html: str):
    """Verifies that copy contains no fabricated metrics, fake testimonials, or profit guarantees."""
    text_content = re.sub(r"<[^>]+>", " ", landing_html).lower()

    unsupported_guarantees = [
        "garansi cuan", "guaranteed profit", "pasti untung",
        "pasti profit", "100% akurat", "jaminan profit",
        "keuntungan pasti", "99.9% akurat", "10.000+ analis", "10,000+ analis",
        "50.000+ pengguna", "50,000+ pengguna",
    ]
    for claim in unsupported_guarantees:
        assert claim not in text_content, (
            f"Unsupported guarantee or fabricated metric found in landing copy: '{claim}'"
        )


# -------------------------------- responsive & reduced motion affordance


def test_responsive_and_reduced_motion_affordances(landing_html: str):
    """Verifies responsive CSS rules and reduced-motion media query when animations exist."""
    style_blocks = re.findall(r"<style[^>]*>([\s\S]*?)</style>", landing_html, re.IGNORECASE)
    combined_css = " ".join(style_blocks).lower()

    # Responsive media queries must be present
    assert "@media" in combined_css, (
        "Landing page CSS must include responsive @media queries"
    )

    # If transitions/animations are present, verify reduced-motion affordance
    has_motion = (
        "animation" in combined_css
        or "transition" in combined_css
        or "@keyframes" in combined_css
    )
    if has_motion:
        assert "prefers-reduced-motion" in combined_css, (
            "CSS with transitions/animations must support @media (prefers-reduced-motion)"
        )
