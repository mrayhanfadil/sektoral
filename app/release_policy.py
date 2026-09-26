"""Versioned baseline policy for Company Update release controls.

This registry records current product rules and the gaps that still need a
policy owner. Runs snapshot its version and hash in the Audit Trace; it is not
yet enforced by the Release Gate. Numeric values are copied from existing
constants/checks and tested against those sources so the baseline cannot drift.
"""
from __future__ import annotations

import copy
import hashlib
import json


POLICY_VERSION = "1.1.0"
EFFECTIVE_DATE = "2026-09-26"

# These constants are the numeric tolerance inputs used by the existing
# deterministic checks below. Keep formulas in named helpers so the policy
# snapshot and active checks cannot drift independently.
REPORT_VALUE_RELATIVE_TOLERANCE = 0.001
GROWTH_CHART_RELATIVE_TOLERANCE = 0.001
GROWTH_CHART_ABSOLUTE_TOLERANCE_PP = 0.1
FORECAST_STATEMENT_ABSOLUTE_FLOOR = 1.0
FORECAST_STATEMENT_RELATIVE_TOLERANCE = 1e-9
HISTORICAL_CASH_ABSOLUTE_FLOOR = 0.01
HISTORICAL_CASH_RELATIVE_TOLERANCE = 0.01
SEGMENT_SHARE_ABSOLUTE_TOLERANCE_PP = 0.5


def report_value_tieout_tolerance(left, right, display_rounding_tolerance=0.0):
    """Relative 0.1% with the existing display-rounding tolerance floor."""
    return max(REPORT_VALUE_RELATIVE_TOLERANCE * max(abs(left), abs(right)),
               display_rounding_tolerance)


def report_value_tieout_matches(left, right, display_rounding_tolerance=0.0):
    return abs(left - right) <= report_value_tieout_tolerance(
        left, right, display_rounding_tolerance)


def growth_chart_tieout_tolerance(displayed_growth):
    """Tolerance when the chart growth is compared with a displayed KF row."""
    return (GROWTH_CHART_ABSOLUTE_TOLERANCE_PP
            + GROWTH_CHART_RELATIVE_TOLERANCE * abs(displayed_growth))


def growth_chart_tieout_matches(chart_growth, displayed_growth):
    return abs(chart_growth - displayed_growth) <= growth_chart_tieout_tolerance(
        displayed_growth)


def derived_growth_chart_tieout_tolerance(current, previous,
                                          current_rounding, previous_rounding):
    """Tolerance from displayed statement rows plus the existing 0.1pp floor."""
    return (100 * abs(current / previous)
            * (current_rounding / abs(current or 1)
               + previous_rounding / abs(previous))
            + GROWTH_CHART_ABSOLUTE_TOLERANCE_PP)


def derived_growth_chart_tieout_matches(chart_growth, current, previous,
                                        current_rounding, previous_rounding):
    """Chart growth vs growth derived from two displayed rows: (current / previous - 1)."""
    modeled_growth = (current / previous - 1) * 100
    return abs(modeled_growth - chart_growth) <= derived_growth_chart_tieout_tolerance(
        current, previous, current_rounding, previous_rounding)


def derived_margin_chart_tieout_matches(chart_margin, numerator, denominator,
                                        numerator_rounding, denominator_rounding):
    """Chart margin vs a ratio of two displayed rows (EBITDA / revenue). The ratio's
    rounding error is the same as the growth case, so it shares that tolerance."""
    modeled_margin = numerator / denominator * 100
    return abs(modeled_margin - chart_margin) <= derived_growth_chart_tieout_tolerance(
        numerator, denominator, numerator_rounding, denominator_rounding)


def forecast_statement_identity_tolerance(statement_scale):
    """Tolerance used for the interim balance sheet and cash-flow identities."""
    return max(statement_scale * FORECAST_STATEMENT_RELATIVE_TOLERANCE,
               FORECAST_STATEMENT_ABSOLUTE_FLOOR)


def forecast_statement_identity_matches(left, right, statement_scale):
    return abs(left - right) <= forecast_statement_identity_tolerance(statement_scale)


def historical_cash_flow_tolerance(fcf):
    """Tolerance used by the historical S1 cash-flow reconciliation."""
    return HISTORICAL_CASH_RELATIVE_TOLERANCE * max(abs(fcf), 1)


def historical_cash_flow_reconciles(ocf, capex_out, fcf):
    return abs((ocf - capex_out) - fcf) <= historical_cash_flow_tolerance(fcf)


def segment_share_sum_is_valid(total_share):
    """Existing report-contract check: segment shares total 100% +/- 0.5pp."""
    return abs(total_share - 100.0) <= SEGMENT_SHARE_ABSOLUTE_TOLERANCE_PP


_POLICY = {
    "version": POLICY_VERSION,
    "effective_date": EFFECTIVE_DATE,
    "status": "mixed_enforcement_and_documentation",
    "scope": "Company Update report preparation, analytical review, and distribution",
    "enforcement_summary": {
        "tolerances": "enforced_at_the_listed_check_sites_via_this_registry",
        "method_gates": "enforced_by_existing_gate_and_chain_modules; snapshot is a recorded mirror",
        "market_freshness": "enforced_by_existing_intake_and_release_checks; policy does not centralize those windows",
        "profile_materiality": "documented_only; numeric cutoffs are unresolved",
        "issuer_calendar_freshness": "date ordering is enforced; expected issuer-period cadence is documented_only",
        "update_triggers": "documented_only_except_existing_hard_release_blockers_and_bundle-review controls",
        "release_gate_integration": "policy snapshot is traceable; remaining documented rules are not automatic release checks",
    },
    "severity_levels": {
        "blocker": "Unresolved failure prevents distributable status.",
        "conditional_blocker": "Blocks when the affected input or approval is required by the selected release path.",
        "review_required": "A named analyst or reviewer must challenge and document disposition.",
        "warning": "Visible limitation or presentation issue; does not block by itself.",
    },
    "review_owner_roles": {
        "research_analyst": "Owns sourced claims, profile assumptions, and research updates.",
        "reviewer": "Owns challenge and approval of the exact report bundle.",
        "model": "Owns model inputs, calculations, and financial reconciliations.",
        "present": "Owns report content and exhibit data assembly.",
        "layout": "Owns HTML/PDF rendering and rendered-output checks.",
        "peers": "Owns peer selection and peer-derived inputs.",
    },
    "method_gates": {
        "gate_0_business_model": {
            "financial_institution_primary": "DDM / Excess Return",
            "finite_reserves_primary": "NAV / Reserve-based",
            "dissimilar_holding_sotp_when_segment_count_gt": 1,
            "review_owner": "research_analyst",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_1a_filing_history": {
            "minimum_years": 4,
            "review_owner": "present",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_1b_profitability": {
            "minimum_positive_ebit_years": 2,
            "window_years": 3,
            "review_owner": "model",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_1c_capital_structure": {
            "max_debt_to_debt_plus_equity": 0.80,
            "max_net_debt_to_ebitda": 6.0,
            "minimum_interest_coverage": 1.0,
            "review_owner": "model",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_1d_equity_base": {
            "positive_equity_required_for_equity_multiples": True,
            "nonpositive_equity_route": "EV-based multiples only; no P/E or P/BV",
            "review_owner": "model",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_2_non_controlling_interest": {
            "normal_band_max_pct_inclusive": 15.0,
            "sotp_cross_check_above_pct_exclusive": 15.0,
            "sotp_cross_check_max_pct_inclusive": 40.0,
            "sotp_primary_above_pct_exclusive": 40.0,
            "review_owner": "model",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_3_cyclicality_and_operating_stage": {
            "steady_state_window_years": 3,
            "extractive_commodity_uses_reserve_based_primary": True,
            "generic_non_extractive_commodity_does_not_route_to_nav": True,
            "review_owner": "research_analyst",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_4_life_cycle": {
            "decline_route": "P/BV or NAV when asset base is substantial",
            "pre_revenue_or_high_growth_route": "EV/Sales",
            "review_owner": "research_analyst",
            "severity": "review_required",
            "source": "app/model_profiles.py:evaluate",
        },
        "gate_5_output_sanity": {
            "extreme_upside_pct_strictly_above": 100.0,
            "extreme_downside_pct_strictly_below": -50.0,
            "extreme_result_action": "stop method chain; Review Required",
            "terminal_value_share_flag_pct_strictly_above": 80.0,
            "terminal_value_flag_action": "cross-check; not a blocker by itself",
            "implied_exit_multiple_action": "outside peer/history range flags and requires cross-check",
            "review_owner": "reviewer",
            "severity": "review_required",
            "source": "app/gate_thresholds.py and spec/Instruksi-Report-v3.md §4.4",
        },
        "method_chain_scale_sanity": {
            "implied_equity_to_market_cap_ratio_inclusive": [0.2, 3.0],
            "review_owner": "model",
            "severity": "review_required",
            "source": "app/gate_thresholds.py:SCALE_BAND; app/method_chain.py:scale_reasons",
        },
    },
    "freshness": {
        "financial_actuals": {
            "max_age_days": None,
            "basis": "latest actual required by the issuer's verified fiscal calendar and applicable profile",
            "cutoff": "publication_date must be on or before Report Date",
            "due_period_missing_severity": "blocker",
            "review_owner": "research_analyst",
            "source": "spec/Instruksi-Report-v3.md §3.1; input-profile calendar policy",
            "implementation": "issuer-period policy is not centralized; do not substitute a generic day window",
            "enforcement_status": "publication_date_cutoff_enforced; issuer_period_cadence_documented_only",
        },
        "market_close": {
            "max_age_days": 5,
            "additional_condition": "for assumption-led releases, quote is after the latest official release and on or before Report Date",
            "stale_or_out_of_period_severity": "conditional_blocker",
            "severity_condition": "when a fresh close is required by the selected release path",
            "review_owner": "present",
            "source": "app/market_quote.py:load; app/release.py:_fresh_close_blockers",
            "enforcement_status": "enforced_elsewhere",
        },
        "usd_idr": {
            "max_age_days": 7,
            "as_of_rule": "latest sourced close on or before Report Date",
            "stale_severity": "conditional_blocker",
            "severity_condition": "when USD/IDR is required by the selected release path",
            "review_owner": "model",
            "source": "app/intake.py; app/release.py USD model checks",
            "enforcement_status": "enforced_elsewhere",
        },
        "ust_10y": {
            "max_age_days": 7,
            "as_of_rule": "latest completed sourced close on or before Report Date",
            "stale_severity": "review_required",
            "stale_action": "input unavailable; selected-method gate decides sufficiency",
            "review_owner": "model",
            "source": "app/rates.py:MAX_AGE_DAYS and on_or_before",
            "enforcement_status": "enforced_elsewhere",
        },
        "indogb_rate_benchmark": {
            "max_age_days": None,
            "as_of_rule": "benchmark publication date must be on or before Report Date",
            "review_owner": "model",
            "source": "app/rate_benchmarks.py:_dated",
            "enforcement_status": "as_of_cutoff_enforced; maximum_age_documented_only",
        },
        "commodity_deck": {
            "max_age_days": 45,
            "stale_action": "Sectors price is marked stale and dated Yahoo series is considered as fallback",
            "stale_severity": "review_required_if_stale_price_remains_material_to_valuation",
            "review_owner": "model",
            "source": "app/mineops.py:DECK_MAX_AGE_DAYS and _price_stats",
            "enforcement_status": "stale_flag_and_fallback_enforced; release_severity_documented_only",
        },
        "sectors_snapshot": {
            "max_age_days": None,
            "refresh_rule": "local snapshot does not expire automatically; refresh is explicit and new closes remain dated overrides",
            "review_owner": "research_analyst",
            "source": "docs/adr/0001-sectors-snapshot-is-the-only-market-data-source.md",
            "enforcement_status": "documented_only",
        },
    },
    "tolerances": {
        "report_value_tieout": {
            "relative_tolerance": REPORT_VALUE_RELATIVE_TOLERANCE,
            "relative_tolerance_unit": "fraction of compared value",
            "absolute_tolerance": None,
            "absolute_tolerance_basis": "display precision / half-unit rounding tolerance derived from the printed value",
            "formula": "abs(left-right) <= max(relative_tolerance * max(abs(left), abs(right)), display_rounding_tolerance)",
            "severity": "blocker",
            "review_owner": "model",
            "source": "app/harness/template.py:_close; docs/harness-template-rules.md T6/T7",
            "enforcement_status": "enforced",
            "enforced_by": ["app/harness/template.py:_close"],
        },
        "growth_chart_tieout": {
            "absolute_tolerance": GROWTH_CHART_ABSOLUTE_TOLERANCE_PP,
            "absolute_tolerance_unit": "percentage_points, plus propagated display rounding when derived from financial rows",
            "relative_tolerance": GROWTH_CHART_RELATIVE_TOLERANCE,
            "relative_tolerance_unit": "fraction of compared growth value",
            "formula": "displayed growth: 0.1pp + 0.001 * abs(displayed_growth); derived growth: propagated display rounding + 0.1pp",
            "severity": "blocker",
            "review_owner": "present",
            "source": "app/harness/template.py:tieout_key_financials; docs/harness-template-rules.md T3",
            "enforcement_status": "enforced",
            "enforced_by": ["app/harness/template.py:tieout_key_financials"],
        },
        "forecast_statement_identity": {
            "absolute_tolerance": FORECAST_STATEMENT_ABSOLUTE_FLOOR,
            "absolute_tolerance_unit": "input currency unit",
            "relative_tolerance": FORECAST_STATEMENT_RELATIVE_TOLERANCE,
            "relative_tolerance_unit": "fraction of statement scale",
            "formula": "max(statement_scale * relative_tolerance, absolute_tolerance)",
            "application_scope": "interim opening balance-sheet and cash-flow identities only",
            "severity": "blocker",
            "review_owner": "model",
            "source": "app/forecast_statements.py:_interim_opening",
            "enforcement_status": "enforced",
            "enforced_by": ["app/forecast_statements.py:_interim_opening"],
        },
        "historical_cash_flow_reconciliation": {
            "absolute_tolerance": HISTORICAL_CASH_ABSOLUTE_FLOOR,
            "absolute_tolerance_unit": "input currency unit floor",
            "relative_tolerance": HISTORICAL_CASH_RELATIVE_TOLERANCE,
            "relative_tolerance_unit": "fraction of FCF magnitude",
            "formula": "relative_tolerance * max(abs(FCF), 1 input currency unit)",
            "severity": "warning",
            "review_owner": "model",
            "source": "app/harness/s1.py:S1.kas",
            "enforcement_status": "enforced",
            "enforced_by": ["app/harness/s1.py:check_s1"],
        },
        "segment_share_sum": {
            "absolute_tolerance": SEGMENT_SHARE_ABSOLUTE_TOLERANCE_PP,
            "absolute_tolerance_unit": "percentage_points around 100%",
            "relative_tolerance": None,
            "relative_tolerance_unit": None,
            "severity": "blocker",
            "review_owner": "present",
            "source": "app/report_contract.py:check_rule_3_segments_share",
            "enforcement_status": "enforced",
            "enforced_by": ["app/report_contract.py:check_rule_3_segments_share"],
        },
    },
    "profiles": {
        "going_concern_fcff": {
            "materiality_bases": [
                "normalized attributable earnings and EPS",
                "revenue volume, price, mix, operating margins, tax, and working capital",
                "FCFF: NOPAT + D&A - capex - change in operating working capital",
                "debt, cash, enterprise-to-equity bridge, diluted shares, and value per share",
                "terminal-value share and base/downside/upside sensitivity",
            ],
            "quantitative_materiality_threshold": None,
            "qualitative_critical_risks": [
                "going-concern or solvency concern",
                "liquidity, refinancing, or funding shortfall",
                "material customer or supplier concentration or loss of pricing power",
                "project execution, capex commitment, or working-capital risk",
                "material governance, related-party, accounting, or reporting concern",
            ],
            "review_owner": "model",
            "severity_if_material_and_unresolved": "blocker",
            "source": "docs/plans/2026-09-26-institutional-research-grade.md §5.1, §6.1",
            "enforcement_status": "documented_only",
        },
        "financial_ddm": {
            "materiality_bases": [
                "normalized earnings attributable to owners and EPS",
                "earning assets, yield, funding cost, fees, provisions, and credit losses",
                "capital adequacy, retained earnings, sustainable payout, dividends, and DPS",
                "balance-sheet and capital reconciliation, share count, and value per share",
                "base/downside/upside sensitivity to earnings, funding, capital, and payout",
            ],
            "quantitative_materiality_threshold": None,
            "qualitative_critical_risks": [
                "asset quality, concentration, or rapid credit deterioration",
                "deposit funding, liquidity, or repricing mismatch",
                "capital adequacy or regulatory constraint",
                "unsustainable payout or dividend capacity",
                "material governance, related-party, accounting, or reporting concern",
            ],
            "review_owner": "model",
            "severity_if_material_and_unresolved": "blocker",
            "source": "docs/plans/2026-09-26-institutional-research-grade.md §5.2, §6.1",
            "enforcement_status": "documented_only",
        },
        "finite_life_mining": {
            "materiality_bases": [
                "reserves, economic life, throughput, grade or quality, recovery, and payable output",
                "realized price or netback, unit costs, royalties, taxes, and asset cash flow",
                "sustaining/project capex, working capital, funding, and closure obligations",
                "asset NAV, ownership, development risk, corporate items, minorities, debt, and diluted shares",
                "base/downside/upside sensitivity to price, volume, cost, capex, and commissioning",
            ],
            "quantitative_materiality_threshold": None,
            "qualitative_critical_risks": [
                "reserve, permit, license, or economic-life uncertainty",
                "commissioning, construction, throughput, or recovery shortfall",
                "commodity price, netback, operating cost, or FX exposure",
                "funding, debt, closure, environmental, or community obligation",
                "material governance, related-party, accounting, or reporting concern",
            ],
            "review_owner": "model",
            "severity_if_material_and_unresolved": "blocker",
            "source": "docs/plans/2026-09-26-institutional-research-grade.md §5.3, §6.1",
            "enforcement_status": "documented_only",
        },
    },
    "update_triggers": [
        {
            "trigger": "A required official actual becomes due under the verified issuer fiscal calendar, or a restatement changes an applicable historical period.",
            "severity": "blocker",
            "review_owner": "research_analyst",
            "enforcement_status": "partially_enforced_elsewhere",
        },
        {
            "trigger": "New official guidance, material financing, corporate action, or evidence contradicts a material research claim or driver assumption.",
            "severity": "review_required",
            "review_owner": "research_analyst",
            "enforcement_status": "documented_only",
        },
        {
            "trigger": "A predeclared thesis-change threshold or catalyst condition is met.",
            "severity": "review_required",
            "review_owner": "research_analyst",
            "enforcement_status": "documented_only",
        },
        {
            "trigger": "A required quote, FX, rate, or commodity input breaches its established freshness window or changes materially in a new as-of snapshot.",
            "severity": "conditional_blocker",
            "condition": "when required by selected method; otherwise record the unavailable input and its effect",
            "review_owner": "model",
            "enforcement_status": "freshness_window_enforced_elsewhere; material_change_trigger_documented_only",
        },
        {
            "trigger": "Evidence, assumptions, source packs, spec, model/code, release status, disclosures, or rendered artifact bytes change after approval.",
            "severity": "blocker",
            "condition": "until the changed bundle is reviewed and approved",
            "review_owner": "reviewer",
            "enforcement_status": "partially_enforced_elsewhere",
        },
        {
            "trigger": "A material conflict, critical source failure, or unresolved statement/model reconciliation is found.",
            "severity": "blocker",
            "review_owner": "model",
            "enforcement_status": "partially_enforced_elsewhere",
        },
    ],
    "ambiguities": [
        {
            "id": "issuer_actual_calendar",
            "issue": "The report spec contains a fiscal-calendar policy placeholder and the release gate checks provenance/date consistency but does not encode expected publication cadence by issuer.",
            "safe_baseline": "Require the latest period dictated by each verified issuer calendar; max_age_days is null.",
            "resolution_needed": "Maintain verified fiscal year-end, reporting cadence, expected filing window, and profile-specific interim requirement per issuer.",
        },
        {
            "id": "quantitative_materiality_cutoffs",
            "issue": "No approved profile-specific amount or percentage threshold for a material earnings, cash-flow, capital, or value difference is present in current code/spec.",
            "safe_baseline": "Record impact on the listed profile bases and escalate material qualitative risks; keep numeric threshold unset.",
            "resolution_needed": "Policy owner to approve profile-specific quantitative materiality rules and boundary cases.",
        },
        {
            "id": "display_tieout_tolerance",
            "issue": "The report rule says 0.1% plus display rounding; some growth checks use 0.1 percentage point plus a 0.1% relative component, while monetary checks derive absolute tolerance from printed precision.",
            "safe_baseline": "Preserve each check's implemented formula and do not convert it into one universal threshold.",
            "resolution_needed": "Reconcile the shared threshold policy with all harness formulas before central enforcement.",
        },
        {
            "id": "commodity_fallback_status",
            "issue": "Mine ops flags a price deck older than 45 days and considers Yahoo fallback, but there is no uniform release status for a fallback series that is itself stale.",
            "safe_baseline": "Keep the dated source and stale flag visible; require review when the stale deck materially drives value.",
            "resolution_needed": "Define selected-method release behavior for a still-stale price deck and profile-specific use.",
        },
        {
            "id": "indogb_benchmark_freshness",
            "issue": "The dated INDOGB benchmark is filtered against Report Date but has no maximum-age rule; the 7-day window applies to UST10Y and USD/IDR paths.",
            "safe_baseline": "Do not apply the 7-day rule to INDOGB, ERP, CRP, or growth benchmark rows without a policy decision.",
            "resolution_needed": "Approve benchmark-specific age limits or accept dated-as-of evidence without a fixed window.",
        },
        {
            "id": "review_role_authorization",
            "issue": "Harness owner labels exist, and review records capture a reviewer name, but an authenticated role matrix and policy owner are not established.",
            "safe_baseline": "Use the named review-owner categories for routing only; this registry does not grant authorization or segregation of duties.",
            "resolution_needed": "Assign accountable policy owner and define author/reviewer/compliance permissions before enforcement.",
        },
        {
            "id": "public_staleness_and_withdrawal",
            "issue": "The plan requires a stale label and withdrawal policy for older public views, but current policy code does not set general report expiry or withdrawal intervals.",
            "safe_baseline": "Open a review on listed triggers; do not invent an automatic day-based public expiry.",
            "resolution_needed": "Approve when an existing publication may stay visible as stale and when a material change requires withdrawal.",
        },
    ],
}


def policy_snapshot() -> dict:
    """Return a detached, JSON-serializable copy of the versioned baseline."""
    return copy.deepcopy(_POLICY)


def policy_sha256(snapshot: dict | None = None) -> str:
    """Hash a canonical policy snapshot; mapping insertion order is irrelevant."""
    payload = policy_snapshot() if snapshot is None else snapshot
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def versioned_snapshot() -> dict:
    """Return the detached policy body and its deterministic content hash."""
    snapshot = policy_snapshot()
    return {"policy": snapshot, "sha256": policy_sha256(snapshot)}
