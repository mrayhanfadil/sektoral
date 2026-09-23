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
    assert "latest interim actuals require a verified source type" in result["blockers"]
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


def test_non_mining_profile_requires_official_actual_and_driver_forecast():
    result = assess_release("going_concern_fcff", None, None, None)

    assert result["status"] == "draft_non_distributable"
    assert "latest official interim actual is missing or unverified" in result["blockers"]
    assert "sourced operating and cash-flow forecast is incomplete" in result["blockers"]


def _driver_evidence():
    return {
        series: {
            "source": "https://issuer.example/guidance_2026.pdf",
            "source_date": "2026-09-18",
            "page": 10,
            "note": f"Sourced {series} operating trajectory from official guidance",
            "path": [100, 115, 130],
        }
        for series in ("revenue", "ebitda", "net_profit", "capex")
    }


def test_sourced_going_concern_can_clear_non_mining_release_gate():
    intake = {"as_of": "2026-09-22", "latest_official_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
        "metrics": {"revenue": 100, "net_profit": 8}}}
    forecast = {
        "forecast_basis": "driver_forecast",
        "production_ready": True,
        "driver_evidence": _driver_evidence(),
    }

    assert assess_release("going_concern_fcff", intake, forecast, None) == {
        "status": "distributable", "blockers": []}
    assert assess_release("financial_ddm", intake, forecast, None)["status"] == \
        "draft_non_distributable"


def test_driver_forecast_missing_driver_evidence_is_blocked():
    intake = {"as_of": "2026-09-22", "latest_official_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
        "metrics": {"revenue": 100, "net_profit": 8}}}
    forecast = {"forecast_basis": "driver_forecast", "production_ready": True}

    result = assess_release("going_concern_fcff", intake, forecast, None)
    assert result["status"] == "draft_non_distributable"
    assert "driver forecast missing driver evidence for required series" in result["blockers"]


def test_driver_forecast_missing_required_series_is_blocked():
    intake = {"as_of": "2026-09-22", "latest_official_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
        "metrics": {"revenue": 100, "net_profit": 8}}}
    drv = _driver_evidence()
    del drv["capex"]
    forecast = {
        "forecast_basis": "driver_forecast",
        "production_ready": True,
        "driver_evidence": drv,
    }

    result = assess_release("going_concern_fcff", intake, forecast, None)
    assert result["status"] == "draft_non_distributable"
    assert "driver forecast missing required series: capex" in result["blockers"]


def test_driver_forecast_unsourced_series_is_blocked():
    intake = {"as_of": "2026-09-22", "latest_official_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
        "metrics": {"revenue": 100, "net_profit": 8}}}
    drv = _driver_evidence()
    drv["revenue"]["source"] = ""
    forecast = {
        "forecast_basis": "driver_forecast",
        "production_ready": True,
        "driver_evidence": drv,
    }

    result = assess_release("going_concern_fcff", intake, forecast, None)
    assert result["status"] == "draft_non_distributable"
    assert "driver forecast revenue: source is required and must identify verified provenance" in result["blockers"]


def test_driver_forecast_rejects_non_https_or_malformed_source_urls():
    for source in ("http://issuer.example/guidance.pdf",
                   "not a URL, but contains http in prose",
                   "https://", "https://user:pass@issuer.example/guidance.pdf"):
        intake = {"as_of": "2026-09-22", "latest_official_actual": {
            "period": "1H26", "period_end": "2026-06-30",
            "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
            "metrics": {"revenue": 100, "net_profit": 8}}}
        drv = _driver_evidence()
        drv["revenue"]["source"] = source
        forecast = {
            "forecast_basis": "driver_forecast",
            "production_ready": True,
            "driver_evidence": drv,
        }

        result = assess_release("going_concern_fcff", intake, forecast, None)
        assert result["status"] == "draft_non_distributable", source
        assert any("source must identify verified provenance" in blocker
                   for blocker in result["blockers"]), source


def test_driver_forecast_future_source_date_is_blocked():
    intake = {"as_of": "2026-09-22", "latest_official_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
        "metrics": {"revenue": 100, "net_profit": 8}}}
    drv = _driver_evidence()
    drv["ebitda"]["source_date"] = "2026-09-25"
    forecast = {
        "forecast_basis": "driver_forecast",
        "production_ready": True,
        "driver_evidence": drv,
    }

    result = assess_release("going_concern_fcff", intake, forecast, None)
    assert result["status"] == "draft_non_distributable"
    assert "driver forecast ebitda: source_date is after report as-of date" in result["blockers"]


def test_driver_forecast_failed_g2_is_blocked():
    intake = {"as_of": "2026-09-22", "latest_official_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "2026-09-18", "source_url": "https://issuer.example/1h26.pdf",
        "metrics": {"revenue": 100, "net_profit": 8}}}
    forecast = {
        "forecast_basis": "driver_forecast",
        "production_ready": True,
        "driver_evidence": _driver_evidence(),
        "g2": {"G2.9_driver_forecast": "gagal"},
    }

    result = assess_release("going_concern_fcff", intake, forecast, None)
    assert result["status"] == "draft_non_distributable"
    assert "forecast gate failed: G2.9 driver forecast is not reconciled" in result["blockers"]


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
