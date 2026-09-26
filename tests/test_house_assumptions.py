from app import (house_assumptions as H, lom, release, research, run_manifest,
                 scenario_value, valuation)


def test_house_assumptions_are_versioned_hashed_and_detached():
    snapshot = H.versioned_snapshot()
    assert snapshot["policy"]["version"] == H.POLICY_VERSION == "1.0.0"
    assert snapshot["policy"]["documented_as_of"] == H.DOCUMENTED_AS_OF
    assert snapshot["policy"]["effective_from"] is None
    assert snapshot["policy"]["status"] == "used_by_model_not_independently_validated"
    assert snapshot["sha256"] == H.policy_sha256(snapshot["policy"])
    snapshot["policy"]["discount_rates"]["IDR"]["risk_free"] = 99
    assert H.discount_inputs("IDR")["risk_free"] == 0.065


def test_existing_valuation_inputs_share_the_house_policy():
    idr, usd = H.discount_inputs("IDR"), H.discount_inputs("USD")
    assert scenario_value.KD_PRETAX == idr["cost_of_debt_pretax"] == 0.09
    assert scenario_value.GRID_GROWTH == tuple(idr["growth_sensitivity"])
    assert scenario_value.GRID_GROWTH_USD == tuple(usd["growth_sensitivity"])
    assert scenario_value.CRP_INDONESIA == usd["country_risk_premium"] == 0.025
    assert scenario_value.TERMINAL_GROWTH_USD == usd["terminal_growth"] == 0.03
    assert lom.BETA == usd["beta"] == 1.1
    assert lom.ERP == usd["equity_risk_premium"] == 0.04
    grid = valuation.tp_grid({"shares": 10}, {"rows": [{"fcf": 10, "ebitda": 10}]},
                             0.10, idr["terminal_growth"], 8.0, 0.0)
    assert set(grid) == {(dw, growth) for dw in idr["rate_sensitivity"]
                         for growth in idr["growth_sensitivity"]}


def test_unknown_currency_fails_closed():
    try:
        H.discount_inputs("EUR")
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unsupported currency received house assumptions")


def test_unapproved_house_policy_blocks_only_production_ready_forecasts():
    production_blockers = H.production_readiness_blockers()
    assert len(production_blockers) == 3
    production = release._check_driver_forecast(
        {"forecast_basis": "driver_forecast", "production_ready": True}, {},
        "going_concern_fcff")
    assert all(item in production for item in production_blockers)

    screening = release._check_driver_forecast(
        {"forecast_basis": "historical_screening_proxy", "production_ready": False}, {},
        "going_concern_fcff")
    assert not any(item in screening for item in production_blockers)


def test_house_policy_effective_date_is_point_in_time_checked():
    assert H._effective_date_blockers("2026-09-26", "2026-09-26") == []
    assert H._effective_date_blockers("2026-09-27", "2026-09-26") == [
        "house-assumption policy became effective after the Report Date"]
    assert H._effective_date_blockers("not-a-date", "2026-09-26") == [
        "house-assumption effective date must be a valid ISO date"]
    assert H._effective_date_blockers("2026-09-26", None) == [
        "report date is required to validate the house-assumption policy vintage"]


def test_publication_manifest_binds_the_house_assumption_snapshot(tmp_path):
    for name, content in (("TEST.html", b"html"), ("TEST.pdf", b"pdf"),
                          ("TEST-trace.html", b"trace")):
        (tmp_path / name).write_bytes(content)
    manifest = run_manifest.finalize_manifest({
        "ticker": "TEST", "as_of": "2026-09-26", "source_tree_sha256": "a" * 64,
        "spec_sha256": "b" * 64, "evidence_register_sha256": "c" * 64,
    }, tmp_path, "TEST")
    hashes = {key: value["sha256"] for key, value in manifest["artifacts"].items()}
    assert not run_manifest.publication_manifest_errors(manifest, "TEST", "2026-09-26", hashes)

    stale = {**manifest, "house_assumptions": {
        "policy": {**manifest["house_assumptions"]["policy"], "version": "0.9.0"},
        "sha256": ""}}
    stale["house_assumptions"]["sha256"] = H.policy_sha256(stale["house_assumptions"]["policy"])
    errors = run_manifest.publication_manifest_errors(stale, "TEST", "2026-09-26", hashes)
    assert "publication manifest house assumptions are stale" in errors


def test_standalone_audit_trace_shows_active_house_inputs_and_open_validation():
    html = research._trace_html("TEST", {}, "TEST.html",
                                run_manifest={"house_assumptions": H.versioned_snapshot()})
    assert "House assumptions tingkat diskonto" in html
    assert "6.5%" in html and "4.0%" in html and "3.5%" in html
    assert "used_by_model_not_independently_validated" in html
    assert "terminal growth consistency with reinvestment" in html
