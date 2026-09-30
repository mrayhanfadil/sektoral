"""Number formats per report language: Indonesian 1.234,5, English 1,234.5."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import fmt  # noqa: E402


def test_indonesian_is_the_default_and_unchanged():
    assert fmt.num(1234.5) == fmt._id(1234.5) == "1.234,5"
    assert fmt.rp(17893.2) == "17.893"
    assert fmt.miliar(39_800_000_000) == "39,8"
    assert fmt.pct(0.1234) == "12,3%"
    assert fmt.mult(12.84) == "12,8x"
    assert fmt.pe(250) == "n.m."


def test_english_swaps_the_separators():
    assert fmt.num(1234.5, lang="en") == "1,234.5"
    assert fmt.num(-1234567.891, 2, lang="en") == "-1,234,567.89"
    assert fmt.rp(17893.2, lang="en") == "17,893"
    assert fmt.miliar(39_800_000_000, lang="en") == "39.8"
    assert fmt.pct(0.1234, lang="en") == "12.3%"
    assert fmt.mult(12.84, lang="en") == "12.8x"
    assert fmt.pe(9.14, lang="en") == "9.1x"
    assert fmt.margin(0.055, lang="en") == "5.5%"
    assert fmt.revenue_idr(1_234_500_000_000, lang="en") == "1,234.5"


def test_conventions_hold_in_both_languages():
    for lang in fmt.LANGS:
        assert fmt.num(None, lang=lang) == "n.a."
        assert fmt.rp("x", lang=lang) == "n.a."
        assert fmt.mult(150, cap=100, lang=lang) == "n.m."
        # A value that rounds to zero is 0, not -0.
        assert fmt.num(-0.04, lang=lang) == {"id": "0,0", "en": "0.0"}[lang]


def test_localize_rewrites_indonesian_figures_only():
    assert fmt.localize("Rp1.036,5 miliar; 12,4%; 0,9x", "en") == "Rp1,036.5 miliar; 12.4%; 0.9x"
    assert fmt.localize("Rp17.893/US$ pada 2026-09-24", "en") == "Rp17,893/US$ pada 2026-09-24"
    # Stage Check ids, versions, ranges and years are not figures to rewrite.
    for text in ("S2.9", "policy 1.3.0", "2024-2025", "FY2025", "8-10x", "11.7%"):
        assert fmt.localize(text, "en") == text
    assert fmt.localize("1.234,5", "id") == "1.234,5"
    assert fmt.localize(None, "en") is None


def test_bracket_negatives_reads_english_scale_suffixes():
    assert fmt.bracket_negatives("Rp-39.8bn", lang="en") == "(Rp39.8bn)"
    assert fmt.bracket_negatives("-4.1%", whole=True, lang="en") == "(4.1%)"
    assert fmt.bracket_negatives("Rp-39,8 miliar") == "(Rp39,8 miliar)"
