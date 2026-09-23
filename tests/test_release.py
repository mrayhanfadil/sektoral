"""Focused tests for the profile-aware production release gate."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.release import OPERATING_BRIDGE_STAGES, assess_release  # noqa: E402
from app.sotp import calculate_sotp  # noqa: E402


def _intake():
    return {"latest_interim_actuals": {
        "period": "1H26",
        "status": "reported actual",
        "source_type": "sectors_cache",
        "source": "Sectors cache /financials/quarterly/TEST/",
        "source_date": "2026-08-25",
        "is_latest": True,
        "page": 4,
        "metrics": {
            "revenue": {"value": 1_200, "unit": "USD mn"},
            "ebitda": {"value": 650, "unit": "USD mn"},
            "net_profit": {"value": 210, "unit": "USD mn"},
            "capex": {"value": 300, "unit": "USD mn"},
        },
    }}


def _forecast():
    bridge = {}
    for stage in OPERATING_BRIDGE_STAGES:
        bridge[stage] = {
            "claim": stage.replace("_", " "),
            "value": ("no downstream asset in this issuer"
                      if stage == "downstream_utilization" else 10),
            "unit": "text" if stage == "downstream_utilization" else "USD mn",
            "period": "FY2027F",
            "status": ("not_applicable" if stage == "downstream_utilization"
                       else "analyst forecast"),
            "source": "Sectors cache /mining/companies/performance/TEST/; model calculation",
            "source_date": "2026-08-25",
            "page": 12,
        }
    return {"operating_bridge": bridge,
            "forecast_basis": "physical_driver_forecast",
            "production_ready": True}


def _sotp():
    result = calculate_sotp(
        [{"name": "Producing asset", "nav_idr": 1_000_000_000_000,
          "ownership_pct": 80, "stage": "producing", "method": "LoM DCF",
          "source": "Sectors cache /mining/companies/performance/TEST/",
          "provenance": "LoM NAV from sourced reserve and production schedule",
          "source_date": "2026-08-25", "page": 12}],
        cash_idr=100_000_000_000,
        debt_idr=200_000_000_000,
        minority_interest_idr=20_000_000_000,
        corporate_overhead_idr=10_000_000_000,
        shares=80_000_000_000,
    )
    result["bridge_evidence"] = {
        field: {"source": "Sectors cache /financials/quarterly/TEST/",
                "source_date": "2026-08-25", "page": 4,
                "unit": "shares" if field == "shares" else "IDR"}
        for field in ("cash_idr", "debt_idr", "minority_interest_idr",
                      "corporate_overhead_idr", "shares")
    }
    return result


def test_complete_finite_life_mining_inputs_are_distributable():
    intake = _intake()
    intake["as_of"] = "2026-09-11"
    result = assess_release("finite_life_mining", intake, _forecast(), _sotp())

    assert result == {"status": "distributable", "blockers": []}


def test_sectors_cache_is_an_allowed_data_source_for_release_inputs():
    intake = _intake()
    intake["as_of"] = "2026-09-11"
    actuals = intake["latest_interim_actuals"]
    actuals["source_type"] = "sectors_cache"
    actuals["source"] = "Sectors cache /financials/quarterly/TEST/"
    actuals["page"] = None

    result = assess_release("finite_life_mining", intake, _forecast(), _sotp())

    assert result == {"status": "distributable", "blockers": []}


def test_missing_latest_interim_actuals_blocks_with_explicit_gaps():
    result = assess_release("finite_life_mining", {}, _forecast(), _sotp())

    assert result["status"] == "draft_non_distributable"
    assert "latest interim actuals missing: intake.latest_interim_actuals" in result["blockers"]


def test_interim_actuals_require_actual_status_period_source_date_and_metrics():
    intake = _intake()
    actuals = intake["latest_interim_actuals"]
    actuals["period"] = "FY25"
    actuals["status"] = "management guidance"
    actuals["source_date"] = "25-08-2026"
    del actuals["metrics"]["capex"]

    result = assess_release("finite_life_mining", intake, _forecast(), _sotp())

    assert result["status"] == "draft_non_distributable"
    assert any("interim period" in blocker for blocker in result["blockers"])
    assert any("labeled actual" in blocker for blocker in result["blockers"])
    assert any("source_date" in blocker for blocker in result["blockers"])
    assert any("missing metric: capex" in blocker for blocker in result["blockers"])


def test_interim_actuals_must_be_primary_latest_and_precede_report_date():
    intake = _intake()
    intake["as_of"] = "2026-09-11"
    actuals = intake["latest_interim_actuals"]
    actuals["source_type"] = "broker_research"
    actuals["source_date"] = "2026-09-22"
    actuals["is_latest"] = False

    result = assess_release("finite_life_mining", intake, _forecast(), _sotp())

    assert result["status"] == "draft_non_distributable"
    assert "latest interim actuals require sectors_cache as the sole data source" in result["blockers"]
    assert "latest interim actuals were published after the report as-of date" in result["blockers"]
    assert "interim actuals must be identified as the latest available release" in result["blockers"]


def test_every_operating_bridge_stage_must_be_present_and_source_backed():
    forecast = _forecast()
    del forecast["operating_bridge"]["recovery"]
    forecast["operating_bridge"]["grade"]["source"] = ""

    result = assess_release("finite_life_mining", _intake(), forecast, _sotp())

    assert result["status"] == "draft_non_distributable"
    assert "operating bridge missing stage: recovery" in result["blockers"]
    assert "operating bridge grade: source must be non-empty text" in result["blockers"]


def test_incomplete_sotp_blocks_even_when_other_mining_inputs_pass():
    result = assess_release(
        "finite_life_mining", _intake(), _forecast(),
        {"status": "incomplete", "gaps": [{"path": "debt_idr"}],
         "assets": [], "target_price_idr": None},
    )

    assert result["status"] == "draft_non_distributable"
    assert "SOTP incomplete: status must be complete" in result["blockers"]
    assert "SOTP incomplete: gaps must be an empty list" in result["blockers"]
    assert "SOTP incomplete: at least one valued asset is required" in result["blockers"]
    assert "SOTP incomplete: target_price_idr must be finite and present" in result["blockers"]


def test_non_mining_profile_is_not_blocked_by_mining_only_checks():
    result = assess_release("going_concern_fcff", None, None, None)

    assert result == {"status": "distributable", "blockers": []}


def test_unknown_profile_fails_closed():
    result = assess_release("unknown", None, None, None)

    assert result["status"] == "draft_non_distributable"
    assert result["blockers"] == ["unsupported model profile: unknown"]


def test_source_bridge_cannot_pass_without_physical_forecast_engine():
    forecast = _forecast()
    forecast["forecast_basis"] = "historical_screening_proxy"
    forecast["production_ready"] = False
    intake = _intake()
    intake["as_of"] = "2026-09-11"

    result = assess_release("finite_life_mining", intake, forecast, _sotp())

    assert result["status"] == "draft_non_distributable"
    assert "mining forecast is not a verified physical-driver production forecast" in result["blockers"]


def test_sotp_corporate_bridge_requires_dated_evidence_and_units():
    intake = _intake()
    intake["as_of"] = "2026-09-11"
    sotp = _sotp()
    sotp["bridge_evidence"]["debt_idr"]["source_date"] = "2026-09-22"
    sotp["bridge_evidence"]["shares"]["unit"] = "USD"

    result = assess_release("finite_life_mining", intake, _forecast(), sotp)

    assert result["status"] == "draft_non_distributable"
    assert "SOTP incomplete: debt_idr evidence.source_date is after report as-of date" in result["blockers"]
    assert "SOTP incomplete: shares evidence.unit must be one of ['shares']" in result["blockers"]
