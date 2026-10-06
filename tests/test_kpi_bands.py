"""Test selective depth, KPI bands, number formatting guards, and exhibit provenance.

Adapts rules from:
- sectors-hackathon: docs/rules/house-report-format.md
- sectors-hackathon: credit-calculator.md
- docs/plans/2026-09-23-sectors-hackathon-adoption.md (Task 4.1)

Guards tested:
1. P/E ratio <= 0 or > 200 must format as "n.m." (not meaningful).
2. Revenue/margins formatted with standard Indonesian notation (dot thousands, comma decimals).
3. Source citation lines always conform to "Source: Company, Sektoral Estimates" or verified provenance.
4. Zero em-dash (U+2014, U+2015) in any formatted outputs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import fmt  # noqa: E402


class TestPERatioGuards:
    """P/E ratio <= 0 or > 200 must format as 'n.m.' (not meaningful)."""

    @pytest.mark.parametrize(
        "pe_val",
        [
            0,
            0.0,
            -0.001,
            -1.0,
            -5.5,
            -15.2,
            -100.0,
            -9999.0,
        ],
    )
    def test_pe_zero_or_negative_formats_as_not_meaningful(self, pe_val):
        assert fmt.pe(pe_val) == "n.m."
        assert fmt.fmt_pe(pe_val) == "n.m."

    @pytest.mark.parametrize(
        "pe_val",
        [
            200.001,
            200.1,
            201,
            250.0,
            500.0,
            1200.0,
            99999.0,
        ],
    )
    def test_pe_greater_than_200_formats_as_not_meaningful(self, pe_val):
        assert fmt.pe(pe_val) == "n.m."
        assert fmt.fmt_pe(pe_val) == "n.m."

    @pytest.mark.parametrize(
        ("pe_val", "expected"),
        [
            (0.1, "0,1x"),
            (1.0, "1,0x"),
            (8.5, "8,5x"),
            (15.2, "15,2x"),
            (28.42, "28,4x"),
            (199.9, "199,9x"),
            (200.0, "200,0x"),
        ],
    )
    def test_pe_in_valid_range_formats_correctly(self, pe_val, expected):
        assert fmt.pe(pe_val) == expected
        assert fmt.fmt_pe(pe_val) == expected

    def test_pe_invalid_or_none_returns_not_available(self):
        assert fmt.pe(None) == "n.a."
        assert fmt.pe("not_a_number") == "n.a."
        assert fmt.fmt_pe(None) == "n.a."


class TestIndonesianNotationGuards:
    """Revenue and margins must format with standard Indonesian notation:
    - Dot (.) for thousands grouping
    - Comma (,) for decimal separation
    - No em-dash (U+2014, U+2015)
    """

    def test_rp_per_share_without_decimals(self):
        assert fmt.rp(1000) == "1.000"
        assert fmt.rp(1250) == "1.250"
        assert fmt.rp(1250000) == "1.250.000"
        assert fmt.rp(500) == "500"

    def test_miliar_large_values_with_comma_decimal(self):
        assert fmt.miliar(15_000_000_000) == "15,0"
        assert fmt.miliar(1_500_000_000) == "1,5"
        assert fmt.miliar(1_234_500_000_000) == "1.234,5"
        assert fmt.miliar(500_000_000) == "0,5"

    def test_revenue_idr_helper(self):
        assert fmt.revenue_idr(25_000_000_000) == "25,0"
        assert fmt.revenue_idr(10_500_000_000) == "10,5"
        assert fmt.revenue_idr(1250000, in_miliar=False) == "1.250.000,0"
        assert fmt.revenue_idr(None) == "n.a."

    def test_percentage_with_comma_decimal(self):
        assert fmt.pct(0.125) == "12,5%"
        assert fmt.pct(0.245) == "24,5%"
        assert fmt.pct(0.0) == "0,0%"
        assert fmt.pct(-0.045) == "-4,5%"
        assert fmt.pct(1.0) == "100,0%"

    def test_margin_helper(self):
        assert fmt.margin(0.245) == "24,5%"
        assert fmt.margin(0.108) == "10,8%"
        assert fmt.margin(-0.052) == "-5,2%"
        assert fmt.margin(None) == "n.a."

    def test_mult_multiple_formatting(self):
        assert fmt.mult(1.8) == "1,8x"
        assert fmt.mult(15.2) == "15,2x"
        assert fmt.mult(2.45, dec=2) == "2,45x"

    def test_no_em_dash_in_any_formatted_string(self):
        samples = [
            fmt.rp(5000),
            fmt.miliar(15e9),
            fmt.pct(0.15),
            fmt.mult(2.5),
            fmt.pe(15.2),
            fmt.pe(-5),
            fmt.pe(250),
            fmt.margin(0.2),
            fmt.revenue_idr(10e9),
            fmt.source_citation(),
        ]
        for s in samples:
            assert "\u2014" not in s, f"Em-dash U+2014 found in: {s!r}"
            assert "\u2015" not in s, f"Horizontal bar U+2015 found in: {s!r}"


class TestSourceCitationProvenanceGuards:
    """Source citation lines must always conform to 'Source: Company, Sektoral Estimates'
    or verified provenance.
    """

    def test_default_source_citation_constant(self):
        assert fmt.DEFAULT_SOURCE == "Source: Sectors (market and financial data), issuer disclosures; Sektoral analysis and estimates."

    def test_source_citation_empty_defaults_to_house_standard(self):
        assert fmt.source_citation("") == fmt.DEFAULT_SOURCE
        assert fmt.source_citation("   ") == fmt.DEFAULT_SOURCE
        assert fmt.source_citation(None) == fmt.DEFAULT_SOURCE

    def test_source_citation_normalizes_missing_source_prefix(self):
        res = fmt.source_citation("Company, Sektoral Estimates")
        assert res == "Source: Company, Sektoral Estimates"

        res_custom = fmt.source_citation("Sectors mining data, Sektoral Estimates")
        assert res_custom == "Source: Sectors mining data, Sektoral Estimates"

    def test_source_citation_preserves_verified_provenance(self):
        verified = "Source: Sectors mining data, Sektoral Estimates; Rf = INDOGB 10Y"
        assert fmt.source_citation(verified) == verified

    def test_is_valid_source_citation_validator(self):
        assert fmt.is_valid_source_citation("Source: Company, Sektoral Estimates") is True
        assert fmt.is_valid_source_citation("Source: Sectors mining data, Sektoral Estimates") is True
        assert fmt.is_valid_source_citation("Source: Sektoral Estimates; sel base (*) = skenario dasar") is True

        # Invalid citations
        assert fmt.is_valid_source_citation("Company, Sektoral Estimates") is False
        assert fmt.is_valid_source_citation("Random notes without source prefix") is False
        assert fmt.is_valid_source_citation("Source:") is False
        assert fmt.is_valid_source_citation("Source: ") is False
        assert fmt.is_valid_source_citation("") is False
        assert fmt.is_valid_source_citation(None) is False

    def test_valtables_default_exhibit_source(self):
        from app import valtables

        ex = valtables._exhibit("Test Exhibit", ["Col1"], [["Val1"]])
        assert "catatan_sumber" in ex
        assert fmt.is_valid_source_citation(ex["catatan_sumber"])
        assert ex["catatan_sumber"] == "Source: Company, Sektoral Estimates"


class TestSelectiveDepthAndKPIBands:
    """Selective depth & KPI band guards:
    - Multiple / band values format using Indonesian conventions.
    - Tenancy and infrastructure metrics format with comma decimal.
    """

    def test_kpi_multiple_bands_formatting(self):
        # 3Y PBV / EV band checks (AVG ± STD)
        avg_multiple = 2.45
        std_multiple = 0.35

        band_upper = avg_multiple + std_multiple  # 2.80
        band_lower = avg_multiple - std_multiple  # 2.10

        assert fmt.mult(avg_multiple, dec=2) == "2,45x"
        assert fmt.mult(band_upper, dec=2) == "2,80x"
        assert fmt.mult(band_lower, dec=2) == "2,10x"

    def test_subsector_hero_metrics(self):
        # Tenancy ratio (tenants / tower)
        tenancy_ratio = 1.84
        assert fmt.mult(tenancy_ratio, dec=2) == "1,84x"

        # Fiber length in thousand km
        fiber_km = 45200
        assert fmt.rp(fiber_km) == "45.200"

    def test_english_decimals_rejected_in_formatted_metrics(self):
        sample_metrics = [
            fmt.pe(18.5),
            fmt.margin(0.321),
            fmt.mult(4.2),
            fmt.revenue_idr(12.8e9),
        ]
        for m in sample_metrics:
            # Should not contain period followed by 1 or 2 digits and 'x' or '%'
            assert not re.search(r"\d+\.\d+(x|%)?", m), (
                f"English decimal format detected in metric {m!r}"
            )
