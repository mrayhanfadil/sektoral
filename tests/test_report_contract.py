"""Tests for report data contract validation rules (Phase 2)."""

import pytest

from app.report_contract import (
    ReportContractError,
    ValidationError,
    check_rule_1_blended_weights,
    check_rule_2_exhibit_provenance_and_numbering,
    check_rule_3_segments_share,
    check_rule_4_upside_recompute,
    check_rule_5_news_and_sentiment,
    check_rule_6_esg,
    validate,
    validate_or_raise,
)


@pytest.fixture
def valid_doc():
    """A fully compliant sample report document."""
    return {
        "meta": {
            "ticker": "MTEL",
            "company_name": "Mitratel",
            "tp": 635,
            "price": 460,
            "upside_pct": 38.0,
        },
        "cover": {
            "rating_box": {
                "action": "BUY",
                "tp": 635,
                "price": 460,
                "upside_pct": 38.0,
            },
            "esg": {
                "found": True,
                "scores": {"e": 2.23, "s": 3.03, "g": 5.08},
                "source": "Sectors cache /esg/MTEL/",
                "date": "2026-08-31",
            },
        },
        "segments": [
            {"name": "Tower Leasing", "revenue": 3833, "share_pct": 49.2},
            {"name": "Fiber", "revenue": 3950, "share_pct": 50.8},
        ],
        "valuation": {
            "methods": [
                {"method": "DCF", "fv": 630},
                {"method": "EV/EBITDA", "fv": 640},
            ],
            "blended": {
                "weights": {"DCF": 60, "EV/EBITDA": 40},
                "fv": 635,
            },
        },
        "exhibits": [
            {
                "n": 1,
                "title": "Revenue and Growth",
                "source": "Company data, IDX",
            },
            {
                "n": 2,
                "title": "EBITDA Bridge",
                "catatan_sumber": "Sectors cache, financial reports",
            },
        ],
        "news": [
            {
                "title": "Mitratel expands fiber footprint",
                "url": "https://example.com/news/1",
                "date": "2026-08-28",
            }
        ],
        "sentiment": {
            "gauge": 62,
            "score": 62,
        },
    }


# ============================================================================
# General / Baseline Tests
# ============================================================================


def test_valid_doc_passes(valid_doc):
    errors = validate(valid_doc)
    assert errors == []
    # validate_or_raise should not raise
    validate_or_raise(valid_doc)


def test_validate_or_raise_raises_on_invalid():
    bad_doc = {
        "cover": {"rating_box": {"tp": 1000, "price": 500, "upside_pct": 50.0}},  # should be 100.0%
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_or_raise(bad_doc)
    assert isinstance(exc_info.value, ReportContractError)
    assert isinstance(exc_info.value, ValueError)
    assert len(exc_info.value.errors) > 0
    assert "Upside recompute mismatch" in str(exc_info.value)


def test_invalid_doc_type():
    errors = validate("not-a-dict")
    assert any("must be a dictionary" in e for e in errors)


# ============================================================================
# Rule 1: Blended Weights & Divergence
# ============================================================================


def test_rule_1_valid_weights_dict(valid_doc):
    valid_doc["valuation"]["blended"]["weights"] = {"DCF": 50, "DDM": 50}
    assert check_rule_1_blended_weights(valid_doc) == []


def test_rule_1_valid_weights_list(valid_doc):
    valid_doc["valuation"]["blended"]["weights"] = [70, 30]
    assert check_rule_1_blended_weights(valid_doc) == []


def test_rule_1_fail_weights_not_100(valid_doc):
    valid_doc["valuation"]["blended"]["weights"] = {"DCF": 60, "EV/EBITDA": 30}  # sum = 90
    errors = check_rule_1_blended_weights(valid_doc)
    assert any("must sum to 100" in e for e in errors)


def test_rule_1_fail_divergence_without_thesis(valid_doc):
    # DCF 600 vs EV/EBITDA 900 -> gap = 300 / 900 = 33.3% > 30%
    valid_doc["valuation"]["methods"] = [
        {"method": "DCF", "fv": 600},
        {"method": "EV/EBITDA", "fv": 900},
    ]
    errors = check_rule_1_blended_weights(valid_doc)
    assert any("exceeds 30% without explicit thesis" in e for e in errors)


def test_rule_1_pass_divergence_with_thesis(valid_doc):
    valid_doc["valuation"]["methods"] = [
        {"method": "DCF", "fv": 600},
        {"method": "EV/EBITDA", "fv": 900},
    ]
    valid_doc["valuation"]["blended"]["thesis"] = (
        "EV/EBITDA reflects near-term market multiples while DCF captures long-term contracts."
    )
    assert check_rule_1_blended_weights(valid_doc) == []


def test_rule_1_fail_explicit_divergence_attribute(valid_doc):
    valid_doc["valuation"]["blended"]["divergence"] = 0.35  # 35% > 30%
    errors = check_rule_1_blended_weights(valid_doc)
    assert any("exceeds 30% without explicit thesis" in e for e in errors)


# ============================================================================
# Rule 2: Exhibit Provenance and Sequential Numbering
# ============================================================================


def test_rule_2_valid_exhibits(valid_doc):
    assert check_rule_2_exhibit_provenance_and_numbering(valid_doc) == []


def test_rule_2_valid_exhibits_in_bagian():
    doc = {
        "bagian": [
            {"halaman": 2, "exhibit": [{"n": 1, "source": "Company data"}]},
            {"halaman": 3, "exhibit": [{"n": 2, "catatan_sumber": "IDX reports"}]},
        ]
    }
    assert check_rule_2_exhibit_provenance_and_numbering(doc) == []


def test_rule_2_valid_exhibits_with_title_numbering():
    doc = {
        "exhibits": [
            {"title": "Exhibit 1: Historic Revenue", "source": "Company"},
            {"title": "Exhibit 2: Future Capex", "source": "Estimates"},
        ]
    }
    assert check_rule_2_exhibit_provenance_and_numbering(doc) == []


def test_rule_2_fail_missing_source(valid_doc):
    valid_doc["exhibits"][0]["source"] = ""
    valid_doc["exhibits"][0].pop("catatan_sumber", None)
    errors = check_rule_2_exhibit_provenance_and_numbering(valid_doc)
    assert any("missing non-empty source/catatan_sumber" in e for e in errors)


def test_rule_2_fail_duplicate_numbering(valid_doc):
    valid_doc["exhibits"] = [
        {"n": 1, "source": "Company"},
        {"n": 1, "source": "IDX"},
    ]
    errors = check_rule_2_exhibit_provenance_and_numbering(valid_doc)
    assert any("Duplicate exhibit number 1" in e for e in errors)


def test_rule_2_fail_out_of_order_numbering(valid_doc):
    valid_doc["exhibits"] = [
        {"n": 2, "source": "Company"},
        {"n": 1, "source": "IDX"},
    ]
    errors = check_rule_2_exhibit_provenance_and_numbering(valid_doc)
    assert any("Out-of-order" in e or "Non-sequential" in e for e in errors)


def test_rule_2_fail_non_sequential_gap(valid_doc):
    valid_doc["exhibits"] = [
        {"n": 1, "source": "Company"},
        {"n": 3, "source": "IDX"},  # expected 2
    ]
    errors = check_rule_2_exhibit_provenance_and_numbering(valid_doc)
    assert any("Non-sequential exhibit number 3" in e for e in errors)


def test_rule_2_fail_missing_numbering(valid_doc):
    valid_doc["exhibits"] = [
        {"title": "Revenue Growth", "source": "Company"},
    ]
    errors = check_rule_2_exhibit_provenance_and_numbering(valid_doc)
    assert any("missing global sequential numbering" in e for e in errors)


# ============================================================================
# Rule 3: Segments share_pct sum == 100 ± 0.5
# ============================================================================


def test_rule_3_valid_single_segment():
    doc = {"segments": [{"name": "Only Segment", "share_pct": 100.0}]}
    assert check_rule_3_segments_share(doc) == []


def test_rule_3_valid_multiple_segments_exact_100(valid_doc):
    valid_doc["segments"] = [
        {"name": "Seg A", "share_pct": 60.0},
        {"name": "Seg B", "share_pct": 40.0},
    ]
    assert check_rule_3_segments_share(valid_doc) == []


def test_rule_3_valid_within_tolerance(valid_doc):
    # 50.2 + 50.1 = 100.3 (within 100 ± 0.5)
    valid_doc["segments"] = [
        {"name": "Seg A", "share_pct": 50.2},
        {"name": "Seg B", "share_pct": 50.1},
    ]
    assert check_rule_3_segments_share(valid_doc) == []


def test_rule_3_fail_sum_outside_tolerance(valid_doc):
    # 60.0 + 30.0 = 90.0 (outside 100 ± 0.5)
    valid_doc["segments"] = [
        {"name": "Seg A", "share_pct": 60.0},
        {"name": "Seg B", "share_pct": 30.0},
    ]
    errors = check_rule_3_segments_share(valid_doc)
    assert any("must sum to 100 ± 0.5" in e for e in errors)


def test_rule_3_fail_missing_share_pct(valid_doc):
    valid_doc["segments"] = [
        {"name": "Seg A", "share_pct": 60.0},
        {"name": "Seg B"},
    ]
    errors = check_rule_3_segments_share(valid_doc)
    assert any("missing numeric share_pct" in e for e in errors)


# ============================================================================
# Rule 4: Upside Recompute
# ============================================================================


def test_rule_4_valid_recompute_hackathon_format(valid_doc):
    valid_doc["cover"]["rating_box"] = {"tp": 635, "price": 460, "upside_pct": 38.0}
    assert check_rule_4_upside_recompute(valid_doc) == []


def test_rule_4_valid_recompute_sektoral_format():
    doc = {
        "meta": {"tp": 6710, "harga": 6325.0, "upside_persen": 6.1}
    }
    assert check_rule_4_upside_recompute(doc) == []


def test_rule_4_skip_when_tp_or_price_missing():
    # Draft reports withhold TP
    doc = {"meta": {"tp": None, "harga": 4860.0}}
    assert check_rule_4_upside_recompute(doc) == []


def test_rule_4_fail_upside_mismatch(valid_doc):
    # tp=1000, price=800 -> upside should be 25.0%
    valid_doc["cover"]["rating_box"] = {"tp": 1000, "price": 800, "upside_pct": 20.0}
    errors = check_rule_4_upside_recompute(valid_doc)
    assert any("Upside recompute mismatch: expected 25.0%, got 20.0%" in e for e in errors)


def test_rule_4_fail_upside_missing_when_tp_and_price_present():
    doc = {"meta": {"tp": 1000, "harga": 800}}
    errors = check_rule_4_upside_recompute(doc)
    assert any("Upside percentage missing" in e for e in errors)


def test_rule_4_fail_non_positive_price():
    doc = {"meta": {"tp": 1000, "harga": 0, "upside_persen": 0.0}}
    errors = check_rule_4_upside_recompute(doc)
    assert any("Price must be positive" in e for e in errors)


# ============================================================================
# Rule 5: News date/timestamp and Sentiment Score
# ============================================================================


def test_rule_5_valid_news_and_sentiment(valid_doc):
    assert check_rule_5_news_and_sentiment(valid_doc) == []


def test_rule_5_valid_sentiment_boundary():
    doc = {
        "sentiment": {"gauge": 0, "score": 100},
        "news": [{"title": "News 1", "timestamp": "2026-09-01T12:00:00"}],
    }
    assert check_rule_5_news_and_sentiment(doc) == []


def test_rule_5_fail_news_missing_date(valid_doc):
    valid_doc["news"] = [{"title": "News without date", "url": "https://example.com"}]
    errors = check_rule_5_news_and_sentiment(valid_doc)
    assert any("missing non-empty date/timestamp" in e for e in errors)


def test_rule_5_fail_news_empty_date(valid_doc):
    valid_doc["news"] = [{"title": "News with empty date", "date": "   "}]
    errors = check_rule_5_news_and_sentiment(valid_doc)
    assert any("missing non-empty date/timestamp" in e for e in errors)


def test_rule_5_fail_sentiment_gauge_above_100(valid_doc):
    valid_doc["sentiment"]["gauge"] = 105
    errors = check_rule_5_news_and_sentiment(valid_doc)
    assert any("must be in [0, 100], got 105" in e for e in errors)


def test_rule_5_fail_sentiment_gauge_below_0(valid_doc):
    valid_doc["sentiment"]["gauge"] = -5
    errors = check_rule_5_news_and_sentiment(valid_doc)
    assert any("must be in [0, 100], got -5" in e for e in errors)


# ============================================================================
# Rule 6: ESG Check (found == False -> Hide Box, No Fabricated Scores)
# ============================================================================


def test_rule_6_valid_found_true(valid_doc):
    valid_doc["cover"]["esg"] = {
        "found": True,
        "scores": {"e": 2.23, "s": 3.03, "g": 5.08},
    }
    assert check_rule_6_esg(valid_doc) == []


def test_rule_6_valid_found_false_box_hidden(valid_doc):
    valid_doc["cover"]["esg"] = {
        "found": False,
        "hide_box": True,
    }
    assert check_rule_6_esg(valid_doc) == []


def test_rule_6_valid_esg_empty_and_not_shown():
    doc = {"cover": {}}
    assert check_rule_6_esg(doc) == []


def test_rule_6_fail_fabricated_scores_when_found_false(valid_doc):
    valid_doc["cover"]["esg"] = {
        "found": False,
        "scores": {"e": 2.5, "s": 3.1, "g": 4.0},  # fabricated scores!
    }
    errors = check_rule_6_esg(valid_doc)
    assert any("Fabricated ESG scores present when found is False" in e for e in errors)


def test_rule_6_fail_box_visible_when_found_false(valid_doc):
    valid_doc["cover"]["esg"] = {
        "found": False,
        "visible": True,
    }
    errors = check_rule_6_esg(valid_doc)
    assert any("ESG box must be hidden when found is False" in e for e in errors)


def test_rule_6_fail_box_visible_when_missing_esg():
    doc = {"cover": {}, "show_esg": True}
    errors = check_rule_6_esg(doc)
    assert any("ESG box must be hidden when ESG data is missing or empty" in e for e in errors)
