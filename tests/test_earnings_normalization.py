"""Deterministic synthetic examples for the Draft earnings ledger."""
import pytest

from app.earnings_normalization import calculate


def _fixture():
    # Synthetic-only Evidence Register rows; no issuer data is implied.
    rows = [
        {"row_id": "synthetic:reported:v1", "period": "FY2025", "currency": "IDR",
         "unit": "million", "published_at": "2026-03-01", "available_at": "2026-03-01"},
        {"row_id": "synthetic:shares:v1", "period": "FY2025", "unit": "million shares",
         "published_at": "2026-03-01", "available_at": "2026-03-01"},
        {"row_id": "synthetic:oneoff:v1", "period": "FY2025", "currency": "IDR",
         "unit": "million", "published_at": "2026-03-10", "available_at": "2026-03-10"},
        {"row_id": "synthetic:recurring:v1", "period": "FY2025", "currency": "IDR",
         "unit": "million", "published_at": "2026-03-11", "available_at": "2026-03-11"},
        {"row_id": "synthetic:restatement:v2", "period": "FY2025", "currency": "IDR",
         "unit": "million", "published_at": "2026-05-15", "available_at": "2026-05-15"},
    ]
    ledger = {
        "adjustments_assessed": True,
        "reported_results": [
            {"vintage_id": "reported-v1", "period": "FY2025",
             "published_at": "2026-03-01", "available_at": "2026-03-01",
             "reported_attributable_earnings": 1000, "currency": "IDR", "unit": "million",
             "source_row_ids": ["synthetic:reported:v1"],
             "shares_outstanding": 10, "shares_unit": "million",
             "shares_source_row_ids": ["synthetic:shares:v1"]},
            {"vintage_id": "reported-v2-restatement", "period": "FY2025",
             "published_at": "2026-05-15", "available_at": "2026-05-15",
             "reported_attributable_earnings": 1200, "currency": "IDR", "unit": "million",
             "source_row_ids": ["synthetic:restatement:v2"],
             "shares_outstanding": 10, "shares_unit": "million",
             "shares_source_row_ids": ["synthetic:shares:v1"]},
        ],
        "adjustments": [
            {"vintage_id": "oneoff-v1", "adjustment_id": "site-closure",
             "period": "FY2025", "classification": "one_off",
             "published_at": "2026-03-10", "available_at": "2026-03-10",
             "currency": "IDR", "unit": "million", "pretax_amount": 100,
             "tax_effect": 20, "minority_interest_effect": 10,
             "normalized_attributable_effect": 70,
             "source_row_ids": ["synthetic:oneoff:v1"]},
            {"vintage_id": "recurring-v1", "adjustment_id": "routine-maintenance",
             "period": "FY2025", "classification": "recurring",
             "published_at": "2026-03-11", "available_at": "2026-03-11",
             "currency": "IDR", "unit": "million", "pretax_amount": 50,
             "tax_effect": 10, "minority_interest_effect": 0,
             "normalized_attributable_effect": 0,
             "source_row_ids": ["synthetic:recurring:v1"]},
        ],
    }
    return ledger, {"rows": rows}


def test_one_off_flows_into_normalized_earnings_but_recurring_does_not():
    ledger, register = _fixture()
    result = calculate(ledger, register, "2026-04-01")

    assert result["status"] == "Draft"
    assert result["completeness"] == "complete"
    period = result["results"][0]
    assert period["reported_result"]["reported_attributable_earnings"] == "1000"
    assert period["normalized_attributable_earnings"] == "1070"
    assert period["eps"] == "107"
    adjustments = {row["adjustment_id"]: row for row in period["adjustments"]}
    assert adjustments["site-closure"]["normalized_attributable_effect"] == "70"
    assert adjustments["site-closure"]["included_in_normalization"] is True
    assert adjustments["routine-maintenance"]["normalized_attributable_effect"] == "0"
    assert adjustments["routine-maintenance"]["included_in_normalization"] is False


def test_report_restatement_is_a_new_vintage_selected_only_after_availability():
    ledger, register = _fixture()
    before = calculate(ledger, register, "2026-04-01")
    after = calculate(ledger, register, "2026-05-20")

    assert before["results"][0]["reported_result"]["vintage_id"] == "reported-v1"
    assert before["results"][0]["normalized_attributable_earnings"] == "1070"
    assert any(row["vintage_id"] == "reported-v2-restatement" and
               row["selection"] == "excluded_future" for row in before["vintage_history"])
    assert after["results"][0]["reported_result"]["vintage_id"] == "reported-v2-restatement"
    assert after["results"][0]["normalized_attributable_earnings"] == "1270"
    assert {row["vintage_id"] for row in after["vintage_history"]
            if row["kind"] == "reported_result"} == {"reported-v1", "reported-v2-restatement"}


def test_tax_and_minority_effects_reconcile_to_parent_attributable_bridge():
    ledger, register = _fixture()
    result = calculate(ledger, register, "2026-04-01")
    adjustment = next(row for row in result["results"][0]["adjustments"]
                      if row["adjustment_id"] == "site-closure")

    # +100 pretax add-back, less +20 tax expense and +10 NCI profit.
    assert adjustment["pretax_amount"] == "100"
    assert adjustment["tax_effect"] == "20"
    assert adjustment["minority_interest_effect"] == "10"
    assert adjustment["normalized_attributable_effect"] == "70"


@pytest.mark.parametrize("source_id", [None, "synthetic:made-up"])
def test_missing_or_fabricated_source_ids_fail_closed(source_id):
    ledger, register = _fixture()
    ledger["adjustments"][0]["source_row_ids"] = [] if source_id is None else [source_id]
    result = calculate(ledger, register, "2026-04-01")

    assert result["status"] == "Draft"
    assert result["completeness"] == "incomplete"
    assert result["results"] == []
    assert any("Evidence Register row ID" in item for item in result["blockers"])


def test_bridge_arithmetic_mismatch_and_unit_mismatch_fail_closed():
    ledger, register = _fixture()
    ledger["adjustments"][0]["normalized_attributable_effect"] = 71
    bad_math = calculate(ledger, register, "2026-04-01")
    assert bad_math["completeness"] == "incomplete"
    assert bad_math["results"] == []
    assert any("does not reconcile" in item for item in bad_math["blockers"])

    ledger, register = _fixture()
    ledger["adjustments"][0]["unit"] = "thousand"
    bad_units = calculate(ledger, register, "2026-04-01")
    assert bad_units["completeness"] == "incomplete"
    assert bad_units["results"] == []
    assert any("unit does not reconcile" in item for item in bad_units["blockers"])


def test_absent_reviewed_adjustment_data_stays_draft_incomplete():
    ledger, register = _fixture()
    ledger["adjustments_assessed"] = False
    result = calculate(ledger, register, "2026-04-01")

    assert result["status"] == "Draft"
    assert result["completeness"] == "incomplete"
    assert result["results"] == []
    assert any("not been affirmatively assessed" in item for item in result["blockers"])
