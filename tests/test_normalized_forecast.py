"""FY1 normalized earnings reach the forecast only from an assessed ledger."""
from app import forecast, forecast_statements


def _intake(status="assessed", currency="USD", period="1H26"):
    fy1 = {"period": period, "currency": currency, "unit": "unit", "effect": 78.0,
           "adjustments": [{"adjustment_id": "fx-loss", "description": "Rugi kurs",
                            "normalized_attributable_effect": "78"}]}
    return {"official_evidence": {"reporting_currency": "USD"},
            "earnings_quality": {"normalization": {"status": status, "fy1": fy1,
                                                   "assessment_note": "pos gabungan tanpa rincian"}}}


def _scenario():
    return {"year": 2026, "full_year": {"net_profit_attributable": 1000.0}}


def test_an_assessed_bridge_adds_its_fy1_effect_to_parent_earnings():
    result = forecast._normalization(_intake(), _scenario())
    assert result["status"] == "assessed"
    assert (result["reported_attributable"], result["normalized_attributable"]) == (1000.0, 1078.0)
    assert result["adjustments"][0]["effect"] == 78.0


def test_other_years_currencies_or_unassessed_ledgers_keep_reported_earnings():
    assert forecast._normalization(_intake(period="1H25"), _scenario())["status"] == "incomplete"
    assert forecast._normalization(_intake(currency="IDR"), _scenario())["status"] == "incomplete"
    unassessed = forecast._normalization(_intake(status="incomplete"), _scenario())
    assert unassessed["status"] == "incomplete" and unassessed["note"] == "pos gabungan tanpa rincian"


def test_report_sentences_state_core_earnings_or_why_they_are_missing():
    scenario = {**_scenario(), "normalization": forecast._normalization(_intake(), _scenario())}
    text = " ".join(forecast_statements._earnings_quality_notes(
        _intake(), {"earnings_scenario": scenario}))
    assert "Laba inti FY26F" in text and "Rugi kurs" in text
    scenario["normalization"] = forecast._normalization(_intake(status="incomplete"), _scenario())
    text = " ".join(forecast_statements._earnings_quality_notes(
        _intake(), {"earnings_scenario": scenario}))
    assert "belum lengkap: pos gabungan tanpa rincian" in text
