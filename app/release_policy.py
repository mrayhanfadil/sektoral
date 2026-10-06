"""Versioned baseline policy for Company Update release controls.

This registry records current product rules, the decisions a policy owner has
approved, and the gaps that still need one. Runs snapshot its version and hash
in the Audit Trace. Tolerances are enforced at their check sites; materiality,
the filing calendar and public staleness are enforced by
``app.publication_monitor``; the remaining documented rules are not automatic
Release Gate checks. Numeric values are copied from existing
constants/checks and tested against those sources so the baseline cannot drift.
"""
from __future__ import annotations

import copy
import hashlib
import json


POLICY_VERSION = "1.3.0"
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

# Policy 1.3.0 (2026-09-26): maximum age at the Report Date of each dated
# discount-rate benchmark shown beside the policy inputs (app.rate_benchmarks).
# INDOGB 10Y is a daily market close, like UST 10Y; the Damodaran ERP/CRP and
# IMF WEO growth series are published once or twice a year.
BENCHMARK_MAX_AGE_DAYS = {"rf_idr": 7, "erp": 400, "crp": 400, "growth": 400}

# Policy 1.3.0: what each authenticated registry role may do
# (app.reviewer_auth). Building a report needs no role; the analyst role reads
# the review view only.
ROLE_PERMISSIONS = {
    "analyst": frozenset({"view_review"}),
    "reviewer": frozenset({"view_review", "approve", "withdraw"}),
    "compliance": frozenset({"view_review", "approve", "withdraw"}),
}


def role_may(role, action) -> bool:
    return action in ROLE_PERMISSIONS.get(role, frozenset())


# Policy 1.3.0: a report that clears every automatic Release Gate
# (Production-Ready or Assumption-Led) is published at once, labelled as not
# reviewed by an analyst; an analyst approval adds the "Direview analis" badge
# and an archived, hash-verified bundle. A draft is never published.
# SECTORAL_AUTO_PUBLISH=0 restores review-gated publication.
AUTO_PUBLISH_STATUSES = frozenset({"production_ready", "distributable",
                                   "distributable_assumption_led"})


def auto_publish_enabled() -> bool:
    import os
    return (os.environ.get("SECTORAL_AUTO_PUBLISH") or "1").strip().lower() not in {"0", "false", "no"}


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


# --- Materiality (policy 1.2.0, approved 2026-09-26) -------------------------
# A change is material when it reaches the threshold (inclusive). Percentages
# compare against the previously published figure; CAR compares absolute
# basis points. A zero or missing baseline cannot anchor a percentage, so any
# nonzero move from zero is material and a missing value is reported as
# unassessed rather than assumed immaterial.
MATERIALITY_DECISION_DATE = "2026-09-26"
EARNINGS_MATERIALITY_PCT = 5.0
VALUE_MATERIALITY_PCT = 5.0
CAR_MATERIALITY_BP = 50.0
NAV_MATERIALITY_PCT = 5.0
MATERIALITY = {
    "going_concern_fcff": {"fy1_attributable_earnings": ("pct", EARNINGS_MATERIALITY_PCT),
                           "value_per_share": ("pct", VALUE_MATERIALITY_PCT)},
    "financial_ddm": {"fy1_attributable_earnings": ("pct", EARNINGS_MATERIALITY_PCT),
                      "value_per_share": ("pct", VALUE_MATERIALITY_PCT),
                      "capital_adequacy_ratio": ("bp", CAR_MATERIALITY_BP)},
    "finite_life_mining": {"fy1_attributable_earnings": ("pct", EARNINGS_MATERIALITY_PCT),
                           "value_per_share": ("pct", VALUE_MATERIALITY_PCT),
                           "attributable_asset_nav": ("pct", NAV_MATERIALITY_PCT)},
}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def materiality_assessment(profile, before, after) -> dict:
    """Compare two model summaries against the profile's approved thresholds.

    ``before`` and ``after`` map basis names (``fy1_attributable_earnings``,
    ``value_per_share``, ``capital_adequacy_ratio`` as a fraction,
    ``attributable_asset_nav``) to numbers. Returns ``material`` (True when any
    assessed basis reaches its threshold), each check, and the bases that could
    not be assessed because a value was missing.
    """
    if profile not in MATERIALITY:
        raise ValueError(f"no materiality rule for Model Profile {profile!r}")
    checks, unassessed = [], []
    for basis, (unit, threshold) in MATERIALITY[profile].items():
        old, new = _number((before or {}).get(basis)), _number((after or {}).get(basis))
        if old is None or new is None:
            unassessed.append(basis)
            continue
        if unit == "bp":
            change = (new - old) * 10_000
            material = abs(change) >= threshold
        elif old == 0:
            change = None if new != 0 else 0.0
            material = new != 0
        else:
            change = (new - old) / abs(old) * 100
            material = abs(change) >= threshold
        checks.append({"basis": basis, "before": old, "after": new, "unit": unit,
                       "change": change, "threshold": threshold, "material": material})
    return {"profile": profile, "material": any(c["material"] for c in checks),
            "checks": checks, "unassessed": unassessed,
            "policy_version": POLICY_VERSION}


# --- Issuer filing calendar (OJK POJK 14/2022 statutory deadlines) ----------
# Interim reports: unaudited 1 month, limited review 2 months, audited 3 months
# after period end; annual audited reports 3 months after fiscal year end. The
# semester report's assurance level is often not recorded in the source pack,
# so an unknown level uses the latest lawful deadline (3 months) rather than
# flagging an issuer that filed an audited semester report on time.
FILING_DEADLINE_MONTHS = {
    "quarter": {"unaudited": 1, "limited_review": 2, "audited": 3, None: 1},
    "semester": {"unaudited": 1, "limited_review": 2, "audited": 3, None: 3},
    "annual": {"audited": 3, None: 3},
}


def _month_end(year, month):
    import calendar
    from datetime import date
    year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def fiscal_periods(fiscal_year, fiscal_year_end_month=12):
    """Q1, 1H, 9M and FY period ends of one fiscal year, with their report kind."""
    start = fiscal_year_end_month - 12  # months before the calendar year of FY end
    return [
        {"label": f"Q1 {fiscal_year}", "kind": "quarter",
         "period_end": _month_end(fiscal_year, start + 3)},
        {"label": f"1H{str(fiscal_year)[-2:]}", "kind": "semester",
         "period_end": _month_end(fiscal_year, start + 6)},
        {"label": f"9M{str(fiscal_year)[-2:]}", "kind": "quarter",
         "period_end": _month_end(fiscal_year, start + 9)},
        {"label": f"FY{fiscal_year}", "kind": "annual",
         "period_end": _month_end(fiscal_year, start + 12)},
    ]


def filing_deadline(period_end, kind, assurance=None):
    months = FILING_DEADLINE_MONTHS[kind].get(assurance, FILING_DEADLINE_MONTHS[kind][None])
    return _month_end(period_end.year, period_end.month + months)


def latest_required_period(as_of, fiscal_year_end_month=12, interim_assurance=None) -> dict:
    """The most recent period whose statutory filing deadline has passed by ``as_of``.

    ``interim_assurance`` may map a report kind (``quarter``/``semester``) to its
    verified assurance level for this issuer.
    """
    from datetime import date
    day = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of)[:10])
    assurance = interim_assurance or {}
    due = []
    for year in (day.year - 1, day.year, day.year + 1):
        for period in fiscal_periods(year, fiscal_year_end_month):
            deadline = filing_deadline(period["period_end"], period["kind"],
                                       assurance.get(period["kind"]))
            if deadline <= day:
                due.append({**period, "due": deadline})
    latest = max(due, key=lambda row: row["period_end"])
    return {"label": latest["label"], "kind": latest["kind"],
            "period_end": latest["period_end"].isoformat(), "due": latest["due"].isoformat()}


def filing_overdue(actual_period_end, as_of, **calendar) -> dict:
    """Whether a newer official period than ``actual_period_end`` was due by ``as_of``."""
    required = latest_required_period(as_of, **calendar)
    return {"overdue": str(actual_period_end)[:10] < required["period_end"],
            "required": required}


# --- Public staleness and withdrawal (policy 1.2.0) --------------------------
# A trigger labels a publication stale and opens a review; it stays visible.
# It is withdrawn only when a measured change is material and no approved
# replacement exists after the grace window. Trading days count Monday to
# Friday; IDX exchange holidays are not modelled, which can only shorten the
# window (withdrawal earlier, never later).
WITHDRAWAL_GRACE_TRADING_DAYS = 10


def trading_days_after(start, end) -> int:
    """Weekdays strictly after ``start`` up to and including ``end``."""
    from datetime import date, timedelta
    first = start if isinstance(start, date) else date.fromisoformat(str(start)[:10])
    last = end if isinstance(end, date) else date.fromisoformat(str(end)[:10])
    days, cursor = 0, first
    while cursor < last:
        cursor += timedelta(days=1)
        days += cursor.weekday() < 5
    return days


def publication_decision(triggers, as_of, materiality=None, replacement_approved=False) -> dict:
    """``current``, ``stale`` or ``withdrawal_due`` for one published Company Update.

    ``triggers`` are dicts with at least ``kind`` and ``date``. ``materiality`` is
    a :func:`materiality_assessment` of the published model against a rebuilt
    candidate, or None when no candidate has been measured.
    """
    if not triggers:
        return {"state": "current", "triggers": [], "reason": None}
    first = min(str(t["date"])[:10] for t in triggers)
    elapsed = trading_days_after(first, as_of)
    material = bool(materiality and materiality.get("material"))
    if material and not replacement_approved and elapsed >= WITHDRAWAL_GRACE_TRADING_DAYS:
        state = "withdrawal_due"
        reason = (f"Perubahan material ({', '.join(c['basis'] for c in materiality['checks'] if c['material'])}) "
                  f"tanpa pengganti yang disetujui dalam {WITHDRAWAL_GRACE_TRADING_DAYS} hari bursa "
                  f"sejak {first}.")
    else:
        state = "stale"
        reason = ("Pemicu pembaruan terbuka sejak " + first + "; laporan tetap tampil dengan label "
                  "stale sampai ditinjau." + ("" if materiality else
                                               " Materialitas belum diukur karena belum ada kandidat pengganti."))
    return {"state": state, "triggers": list(triggers), "first_trigger": first,
            "trading_days_elapsed": elapsed, "grace_trading_days": WITHDRAWAL_GRACE_TRADING_DAYS,
            "materiality": materiality, "replacement_approved": replacement_approved,
            "reason": reason}


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
            "max_age_days": 7,
            "as_of_rule": "benchmark publication date must be on or before Report Date",
            "stale_action": "benchmark is not shown; the policy value is unaffected",
            "review_owner": "model",
            "source": "app/rate_benchmarks.py:_dated",
            "enforcement_status": "enforced_elsewhere",
        },
        "commodity_deck": {
            "max_age_days": 45,
            "stale_action": "Sectors price is marked stale and dated Yahoo series is considered as fallback",
            "stale_severity": "production_blocker_if_still_stale_after_fallback",
            "stale_after_fallback": ("the LoM records a price input gap and leaves the physical "
                                     "route; any mining method is at most Assumption-Led"),
            "review_owner": "model",
            "source": "app/mineops.py:DECK_MAX_AGE_DAYS and _price_stats; app/release.py:common_blockers",
            "enforcement_status": "enforced_elsewhere",
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


# Policy 1.2.0 decisions (2026-09-26): quantitative materiality, the OJK filing
# calendar, and public staleness/withdrawal. The snapshot is filled from the
# same constants the checks use, so the documented rule cannot drift from the
# enforced one.
_DECISION_OWNER = "Sectoral Team"
for _name, _rules in MATERIALITY.items():
    _POLICY["profiles"][_name]["quantitative_materiality_threshold"] = {
        basis: {"unit": unit, "threshold": threshold, "inclusive": True,
                "comparison": ("absolute change in basis points" if unit == "bp"
                               else "change relative to the published value")}
        for basis, (unit, threshold) in _rules.items()}
    _POLICY["profiles"][_name]["enforcement_status"] = "enforced_by_publication_monitor"
_POLICY["freshness"]["financial_actuals"].update({
    "implementation": "app.release_policy.latest_required_period: OJK POJK 14/2022 deadlines",
    "enforcement_status": "enforced_by_publication_monitor",
    "filing_deadline_months": {kind: {str(k): v for k, v in levels.items()}
                               for kind, levels in FILING_DEADLINE_MONTHS.items()},
    "unknown_assurance": "semester reports use the 3-month audited deadline",
    "issuer_override": "source pack fiscal_calendar.fiscal_year_end_month and interim_assurance",
})
_POLICY["update_triggers"][0]["enforcement_status"] = "enforced_by_publication_monitor"
_POLICY["public_staleness"] = {
    "on_trigger": "label the publication stale and open a review; it stays visible",
    "withdraw_when": ("a rebuilt candidate shows a material change and no approved replacement "
                      "exists after the grace window"),
    "grace_trading_days": WITHDRAWAL_GRACE_TRADING_DAYS,
    "trading_day_basis": "Monday to Friday; IDX exchange holidays are not modelled",
    "unmeasured_materiality": "stays stale; never withdrawn without a measured material change",
    "actor": "an authenticated reviewer or compliance identity records every withdrawal",
    "enforcement_status": "enforced_by_publication_monitor",
}
_POLICY["enforcement_summary"].update({
    "profile_materiality": "enforced_by_publication_monitor for published-vs-candidate changes",
    "issuer_calendar_freshness": "enforced_by_publication_monitor via OJK filing deadlines",
    "public_staleness_and_withdrawal": "enforced_by_publication_monitor; withdrawal needs an authenticated actor",
})
_POLICY["freshness"]["rate_benchmarks"] = {
    "max_age_days": dict(BENCHMARK_MAX_AGE_DAYS),
    "as_of_rule": "dated on or before the Report Date and no older than its maximum age",
    "stale_action": "benchmark is not shown; the policy value is unaffected",
    "source": "app/rate_benchmarks.py:_dated",
    "enforcement_status": "enforced_elsewhere",
}
_POLICY["tieout_formulas"] = {
    "report_value": "abs(a - b) <= max(0.1% x max(|a|, |b|), half a unit of the last printed digit)",
    "growth_chart_vs_displayed": "abs(chart - displayed) <= 0.1pp + 0.1% x |displayed|",
    "derived_growth_or_margin": ("abs(model - chart) <= 100 x |c/p| x (rounding_c/|c| + "
                                 "rounding_p/|p|) + 0.1pp"),
    "forecast_statement_identity": "max(scale x 1e-9, 1.0)",
    "source": "app/release_policy.py tie-out helpers, called by app/harness/template.py",
    "enforcement_status": "enforced_elsewhere",
}
_POLICY["review_roles"] = {
    "policy_owner": _DECISION_OWNER,
    "permissions": {role: sorted(actions) for role, actions in ROLE_PERMISSIONS.items()},
    "identity": "authenticated registry token (SECTORAL_REVIEWERS); a typed name never approves",
    "segregation": ("the report is built by the pipeline; approval and withdrawal need an "
                    "authenticated reviewer or compliance identity"),
    "enforcement_status": "enforced_by_server_and_assumption_review",
}
_POLICY["publication_tiers"] = {
    "automatic": ("a report that clears every automatic Release Gate is published at once, "
                  "labelled 'dihasilkan model, belum direview analis'; its forecast is frozen "
                  "at build"),
    "analyst_reviewed": ("an authenticated reviewer approval adds the 'Direview analis' badge "
                         "and archives the hash-verified bundle"),
    "statuses": sorted(AUTO_PUBLISH_STATUSES),
    "never": "draft_non_distributable",
    "switch": "SECTORAL_AUTO_PUBLISH=0 restores review-gated publication",
    "enforcement_status": "enforced_by_gallery",
}
_RESOLVED = {"quantitative_materiality_cutoffs", "issuer_actual_calendar",
             "public_staleness_and_withdrawal", "display_tieout_tolerance",
             "commodity_fallback_status", "indogb_benchmark_freshness",
             "review_role_authorization"}
_POLICY["decisions"] = [
    {"id": "quantitative_materiality_cutoffs", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "Material at >=5% of FY1 attributable earnings or value per share; banks also "
                 ">=50bp CAR; mining also >=5% attributable asset NAV."},
    {"id": "issuer_actual_calendar", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "A period is due at its OJK POJK 14/2022 deadline; unknown semester assurance "
                 "uses the 3-month audited deadline."},
    {"id": "public_staleness_and_withdrawal", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "Label stale on a trigger; withdraw only a measured material change without an "
                 f"approved replacement after {WITHDRAWAL_GRACE_TRADING_DAYS} trading days."},
    {"id": "display_tieout_tolerance", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "Each check keeps its own formula, all defined once in release_policy "
                 "(tieout_formulas); no single universal threshold."},
    {"id": "commodity_fallback_status", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "A price deck still older than 45 days after the dated Yahoo fallback is a "
                 "production blocker for a mining report; it may be Assumption-Led at most."},
    {"id": "indogb_benchmark_freshness", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "INDOGB 10Y benchmark at most 7 days old; Damodaran ERP/CRP and IMF growth at "
                 "most 400 days; an older benchmark is not shown."},
    {"id": "publication_tiers", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "Reports that clear the automatic gates publish at once, labelled as not "
                 "analyst-reviewed; analyst approval is an optional badge on top."},
    {"id": "review_role_authorization", "decided": "2026-09-26", "owner": _DECISION_OWNER,
     "decision": "Analyst views; reviewer and compliance approve and withdraw; every approval "
                 "and withdrawal needs an authenticated registry identity."},
]
_POLICY["ambiguities"] = [a for a in _POLICY["ambiguities"] if a["id"] not in _RESOLVED]


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
