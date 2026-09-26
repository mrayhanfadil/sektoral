"""Focused checks for the versioned release policy: enforced tolerances and documented rules."""
from __future__ import annotations

import json
from inspect import signature

from app import (gate_thresholds, market_quote, mineops, model_profiles, rates, release,
                 report_contract)
from app.harness import s1, template
from app import release_policy


def test_policy_snapshot_is_detached_serializable_and_deterministically_hashed():
    snapshot = release_policy.policy_snapshot()
    json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
    assert snapshot["version"] == release_policy.POLICY_VERSION == "1.3.0"
    assert snapshot["effective_date"] == release_policy.EFFECTIVE_DATE == "2026-09-26"
    assert release_policy.policy_sha256(snapshot) == release_policy.policy_sha256()
    assert release_policy.policy_sha256(dict(reversed(list(snapshot.items())))) == (
        release_policy.policy_sha256(snapshot))

    snapshot["version"] = "edited-copy"
    assert release_policy.policy_snapshot()["version"] == "1.3.0"
    assert release_policy.policy_sha256(snapshot) != release_policy.policy_sha256()
    package = release_policy.versioned_snapshot()
    assert package["sha256"] == release_policy.policy_sha256(package["policy"])


def test_method_gate_thresholds_are_preserved_from_the_existing_rules():
    policy = release_policy.policy_snapshot()
    gates = policy["method_gates"]
    gate5 = gates["gate_5_output_sanity"]
    assert gate5["extreme_upside_pct_strictly_above"] == gate_thresholds.EXTREME_UPSIDE_PCT
    assert gate5["extreme_downside_pct_strictly_below"] == gate_thresholds.EXTREME_DOWNSIDE_PCT
    assert gate5["terminal_value_share_flag_pct_strictly_above"] == gate_thresholds.TV_SHARE_PCT
    assert gates["method_chain_scale_sanity"]["implied_equity_to_market_cap_ratio_inclusive"] == (
        list(gate_thresholds.SCALE_BAND))

    assert gates["gate_1a_filing_history"]["minimum_years"] == 4
    assert gates["gate_1b_profitability"]["minimum_positive_ebit_years"] == 2
    assert gates["gate_1b_profitability"]["window_years"] == 3
    assert gates["gate_1c_capital_structure"]["max_debt_to_debt_plus_equity"] == 0.80
    assert gates["gate_1c_capital_structure"]["max_net_debt_to_ebitda"] == 6.0
    assert gates["gate_1c_capital_structure"]["minimum_interest_coverage"] == 1.0
    assert gates["gate_2_non_controlling_interest"]["sotp_cross_check_max_pct_inclusive"] == 40.0
    assert gates["gate_3_cyclicality_and_operating_stage"]["steady_state_window_years"] == 3


def test_freshness_policy_uses_existing_windows_and_calendar_based_actuals():
    policy = release_policy.policy_snapshot()["freshness"]
    assert signature(market_quote.load).parameters["max_age_days"].default == 5
    assert policy["market_close"]["max_age_days"] == 5
    assert rates.MAX_AGE_DAYS == policy["ust_10y"]["max_age_days"] == 7
    assert mineops.DECK_MAX_AGE_DAYS == policy["commodity_deck"]["max_age_days"] == 45
    assert policy["usd_idr"]["max_age_days"] == 7
    assert policy["financial_actuals"]["max_age_days"] is None
    assert "verified fiscal calendar" in policy["financial_actuals"]["basis"]
    assert policy["indogb_rate_benchmark"]["max_age_days"] == 7
    assert policy["rate_benchmarks"]["max_age_days"] == release_policy.BENCHMARK_MAX_AGE_DAYS
    assert policy["sectors_snapshot"]["max_age_days"] is None


def test_release_quote_and_usd_fx_boundary_checks_match_the_registry():
    actual = {
        "period": "1H2026", "period_end": "2026-06-30",
        "published_at": "2026-09-19", "source_url": "https://issuer.example/report.pdf",
        "metrics": {"revenue": 100.0, "net_profit": 10.0},
    }

    def assess(quote_day, fx_day):
        intake = {
            "as_of": "2026-09-26", "model_profile": "financial_ddm",
            "latest_official_actual": actual,
            "official_evidence": {"reporting_currency": "USD"},
            "price": 1000.0, "price_date": quote_day,
            "price_provenance": {"verified": True, "date": quote_day,
                                 "source": "https://finance.yahoo.com/quote/BBCA.JK/history/"},
            "fx_spot": {"rate": 16000.0, "date": fx_day, "source": "Yahoo Finance"},
        }
        forecast = {"earnings_scenario": {"source_url": actual["source_url"],
                                          "published_at": actual["published_at"]}}
        valuation = {"detail": {"shares": 100.0, "peer_count": 3, "eps_idr": 10.0,
                                "q1_pe": 9.0, "median_pe": 10.0, "q3_pe": 11.0}}
        return release.assess_earnings_led(intake, forecast, valuation, "validated")["blockers"]

    assert not any("fresh sourced close" in p for p in
                   assess("2026-09-21", "2026-09-19"))  # close age 5, FX age 7
    assert any("fresh sourced close" in p for p in
               assess("2026-09-20", "2026-09-19"))  # close age 6
    assert any("fresh sourced USD/IDR" in p for p in
               assess("2026-09-21", "2026-09-18"))  # FX age 8


def test_profile_materiality_bases_and_critical_risks_cover_supported_profiles():
    policy = release_policy.policy_snapshot()
    profiles = policy["profiles"]
    assert set(profiles) == set(model_profiles.SUPPORTED_PROFILES)
    for profile in profiles.values():
        assert profile["materiality_bases"]
        assert profile["qualitative_critical_risks"]
        threshold = profile["quantitative_materiality_threshold"]
        assert threshold["fy1_attributable_earnings"]["threshold"] == 5.0
        assert threshold["value_per_share"]["threshold"] == 5.0
        assert all(rule["inclusive"] for rule in threshold.values())
        assert profile["enforcement_status"] == "enforced_by_publication_monitor"
        assert profile["severity_if_material_and_unresolved"] == "blocker"
        assert profile["review_owner"] in policy["review_owner_roles"]


def test_established_tolerance_fields_and_policy_ambiguities_are_explicit():
    policy = release_policy.policy_snapshot()
    tolerances = policy["tolerances"]
    assert tolerances["report_value_tieout"]["relative_tolerance"] == 0.001
    assert tolerances["report_value_tieout"]["absolute_tolerance"] is None
    assert tolerances["report_value_tieout"]["absolute_tolerance_basis"]
    assert tolerances["growth_chart_tieout"]["absolute_tolerance"] == 0.1
    assert tolerances["growth_chart_tieout"]["relative_tolerance"] == 0.001
    assert tolerances["forecast_statement_identity"]["absolute_tolerance"] == 1.0
    assert tolerances["forecast_statement_identity"]["relative_tolerance"] == 1e-9
    assert tolerances["historical_cash_flow_reconciliation"]["relative_tolerance"] == 0.01
    assert tolerances["segment_share_sum"]["absolute_tolerance"] == 0.5
    assert {item["enforcement_status"] for item in tolerances.values()} == {"enforced"}
    assert all(item["enforced_by"] for item in tolerances.values())
    assert policy["enforcement_summary"]["profile_materiality"].startswith(
        "enforced_by_publication_monitor")

    # Policy 1.2.0 resolved materiality, the filing calendar and public
    # staleness; 1.3.0 the tie-out formulas, stale commodity fallback,
    # benchmark age and review roles. No ambiguity stays open.
    assert policy["ambiguities"] == []
    assert {d["id"] for d in policy["decisions"]} == {
        "issuer_actual_calendar", "quantitative_materiality_cutoffs",
        "public_staleness_and_withdrawal", "display_tieout_tolerance",
        "commodity_fallback_status", "indogb_benchmark_freshness", "review_role_authorization",
        "publication_tiers",
    }


def test_review_roles_and_permissions():
    may = release_policy.role_may
    assert not may("analyst", "approve") and may("analyst", "view_review")
    assert may("reviewer", "approve") and may("compliance", "withdraw")
    assert not may("guest", "view_review")
    roles = release_policy.policy_snapshot()["review_roles"]
    assert roles["policy_owner"] == "Sektoral Team"
    assert roles["permissions"]["reviewer"] == ["approve", "view_review", "withdraw"]


def test_benchmarks_older_than_their_policy_age_are_not_shown():
    from app import rate_benchmarks
    rf = {"as_of": "2026-09-23"}
    assert rate_benchmarks._dated(rf, "2026-09-26", "rf_idr") is rf
    assert rate_benchmarks._dated(rf, "2026-10-01", "rf_idr") is None
    assert rate_benchmarks._dated(rf, "2026-09-22", "rf_idr") is None  # no look-ahead
    erp = {"as_of": "2026-01-05"}
    assert rate_benchmarks._dated(erp, "2026-09-26", "erp") is erp
    assert rate_benchmarks._dated(erp, "2027-03-01", "erp") is None


def test_a_deck_still_stale_after_the_fallback_blocks_a_mining_report():
    from app import release
    fresh = {"mineops": {"cu_price": {"stale": False}, "au_price": {"stale": False}}}
    assert release._stale_deck_blockers(fresh) == []
    stale = {"mineops": {"cu_price": {"stale": True, "age_days": 60, "date": "2026-07-28"}}}
    (blocker,) = release._stale_deck_blockers(stale)
    assert "copper price deck is 60 days old" in blocker
    assert blocker in release.common_blockers("finite_life_mining", stale, None)


def test_active_tolerance_checks_cover_inside_outside_and_near_zero_boundaries():
    # Report value tie-out: 0.1% relative, with an explicit display-rounding floor.
    assert template._close(100.0, 100.10009)
    assert not template._close(100.0, 100.10011)
    assert template._close(0.0, 0.0049, 0.005)
    assert not template._close(0.0, 0.0051, 0.005)
    assert not template._close(0.0, 1e-8)

    # Growth chart: near-zero uses the 0.1pp floor; a displayed 100% uses 0.2pp.
    assert release_policy.growth_chart_tieout_matches(0.0999, 0.0)
    assert not release_policy.growth_chart_tieout_matches(0.1001, 0.0)
    assert release_policy.growth_chart_tieout_matches(100.1999, 100.0)
    assert not release_policy.growth_chart_tieout_matches(100.2001, 100.0)
    assert release_policy.derived_growth_chart_tieout_matches(50.0999, 150.0, 100.0, 0, 0)
    assert not release_policy.derived_growth_chart_tieout_matches(50.1001, 150.0, 100.0, 0, 0)
    # EBITDA margin from two rows is a ratio, not a growth rate: 30/100 is 30%, not -70%.
    assert release_policy.derived_margin_chart_tieout_matches(30.0999, 30.0, 100.0, 0, 0)
    assert not release_policy.derived_margin_chart_tieout_matches(30.1001, 30.0, 100.0, 0, 0)

    # Interim identity: the absolute one-unit floor governs near zero.
    assert release_policy.forecast_statement_identity_matches(0.999, 0.0, 0.0)
    assert not release_policy.forecast_statement_identity_matches(1.001, 0.0, 0.0)
    assert release_policy.forecast_statement_identity_matches(1e12 + 999.9, 1e12, 1e12)
    assert not release_policy.forecast_statement_identity_matches(1e12 + 1000.1, 1e12, 1e12)

    # Historical cash: its 0.01-unit floor governs near-zero FCF.
    assert release_policy.historical_cash_flow_reconciles(0.0099, 0.0, 0.0)
    assert not release_policy.historical_cash_flow_reconciles(0.0101, 0.0, 0.0)
    assert release_policy.historical_cash_flow_reconciles(100.999, 0.0, 100.0)
    assert not release_policy.historical_cash_flow_reconciles(101.001, 0.0, 100.0)

    # Existing check entry points still consume the policy helpers.
    assert not report_contract.check_rule_3_segments_share({
        "segments": [{"share_pct": 50.25}, {"share_pct": 50.25}]})
    assert report_contract.check_rule_3_segments_share({
        "segments": [{"share_pct": 50.2501}, {"share_pct": 50.2501}]})
    kas = s1.check_s1({"annuals": [{"ocf": 0.0099, "capex_out": 0.0, "fcf": 0.0}]})
    assert next(c for c in kas["checks"] if c["check"] == "S1.kas")["status"] == "lolos"
    kas = s1.check_s1({"annuals": [{"ocf": 0.0101, "capex_out": 0.0, "fcf": 0.0}]})
    assert next(c for c in kas["checks"] if c["check"] == "S1.kas")["status"] == "gagal-dilabeli"


def test_update_triggers_have_severity_and_assigned_review_owners():
    policy = release_policy.policy_snapshot()
    allowed_severity = set(policy["severity_levels"])
    for trigger in policy["update_triggers"]:
        assert trigger["trigger"]
        assert trigger["severity"] in allowed_severity
        assert trigger["review_owner"] in policy["review_owner_roles"]
