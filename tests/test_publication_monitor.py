"""Release policy 1.2.0: materiality, OJK filing calendar, staleness and withdrawal."""
from __future__ import annotations

import pytest

from app import gallery, publication_monitor as M, release_policy as P


# --- materiality -----------------------------------------------------------

def _check(result, basis):
    return next(c for c in result["checks"] if c["basis"] == basis)


def test_materiality_is_inclusive_at_five_percent_of_earnings_and_value():
    base = {"fy1_attributable_earnings": 100.0, "value_per_share": 1000.0}
    just_below = P.materiality_assessment(
        "going_concern_fcff", base, {"fy1_attributable_earnings": 104.99, "value_per_share": 1049.9})
    assert not just_below["material"]
    at = P.materiality_assessment(
        "going_concern_fcff", base, {"fy1_attributable_earnings": 95.0, "value_per_share": 1000.0})
    assert at["material"] and _check(at, "fy1_attributable_earnings")["material"]
    assert not _check(at, "value_per_share")["material"]
    assert at["policy_version"] == P.POLICY_VERSION


def test_bank_car_uses_absolute_basis_points_and_mining_uses_nav():
    before = {"fy1_attributable_earnings": 100.0, "value_per_share": 1000.0,
              "capital_adequacy_ratio": 0.2100}
    inside = P.materiality_assessment("financial_ddm", before, {**before, "capital_adequacy_ratio": 0.2149})
    assert not inside["material"]
    at = P.materiality_assessment("financial_ddm", before, {**before, "capital_adequacy_ratio": 0.2050})
    assert at["material"] and _check(at, "capital_adequacy_ratio")["change"] == pytest.approx(-50.0)

    mine = {"fy1_attributable_earnings": 100.0, "value_per_share": 1000.0, "attributable_asset_nav": 200.0}
    moved = P.materiality_assessment("finite_life_mining", mine, {**mine, "attributable_asset_nav": 210.0})
    assert moved["material"] and _check(moved, "attributable_asset_nav")["material"]


def test_zero_baseline_and_missing_values_are_never_silently_immaterial():
    zero = P.materiality_assessment("going_concern_fcff", {"fy1_attributable_earnings": 0.0},
                                    {"fy1_attributable_earnings": 0.01})
    assert zero["material"] and _check(zero, "fy1_attributable_earnings")["change"] is None
    both_zero = P.materiality_assessment("going_concern_fcff", {"fy1_attributable_earnings": 0.0},
                                         {"fy1_attributable_earnings": 0.0})
    assert not both_zero["material"]
    missing = P.materiality_assessment("financial_ddm", {"value_per_share": 1000.0},
                                       {"value_per_share": 1000.0})
    assert set(missing["unassessed"]) == {"fy1_attributable_earnings", "capital_adequacy_ratio"}
    with pytest.raises(ValueError):
        P.materiality_assessment("unknown_profile", {}, {})


# --- OJK filing calendar -----------------------------------------------------

def test_semester_with_unknown_assurance_is_due_at_the_audited_deadline():
    assert P.latest_required_period("2026-09-29")["label"] == "Q1 2026"
    due = P.latest_required_period("2026-09-30")
    assert (due["label"], due["due"]) == ("1H26", "2026-09-30")
    reviewed = P.latest_required_period("2026-08-31", interim_assurance={"semester": "limited_review"})
    assert reviewed["label"] == "1H26"
    assert P.latest_required_period("2026-08-30",
                                    interim_assurance={"semester": "limited_review"})["label"] == "Q1 2026"


def test_quarters_annual_and_non_december_fiscal_years():
    assert P.latest_required_period("2026-10-31")["label"] == "9M26"
    # 9M26 is due only on 31 October, so the day before still requires 1H26.
    assert P.latest_required_period("2026-10-30")["label"] == "1H26"
    annual = P.latest_required_period("2027-03-31")
    assert (annual["label"], annual["period_end"]) == ("FY2026", "2026-12-31")
    # A March fiscal year: the year ending March 2027 has its semester at September 2026.
    march = P.fiscal_periods(2027, fiscal_year_end_month=3)
    assert [p["period_end"].isoformat() for p in march] == [
        "2026-06-30", "2026-09-30", "2026-12-31", "2027-03-31"]


def test_filing_overdue_compares_the_report_period_with_the_due_period():
    assert not P.filing_overdue("2026-06-30", "2026-10-30")["overdue"]
    late = P.filing_overdue("2026-06-30", "2026-10-31")
    assert late["overdue"] and late["required"]["label"] == "9M26"


# --- staleness and withdrawal ------------------------------------------------

def test_trading_days_skip_weekends():
    assert P.trading_days_after("2026-09-25", "2026-09-28") == 1   # Fri -> Mon
    assert P.trading_days_after("2026-09-25", "2026-10-09") == 10
    assert P.trading_days_after("2026-09-25", "2026-09-25") == 0


def test_publication_decision_labels_first_and_withdraws_only_measured_material_change():
    trigger = [{"kind": "new_official_actual", "date": "2026-09-25"}]
    material = {"material": True, "checks": [{"basis": "value_per_share", "material": True}]}
    immaterial = {"material": False, "checks": [{"basis": "value_per_share", "material": False}]}

    assert P.publication_decision([], "2026-10-09")["state"] == "current"
    assert P.publication_decision(trigger, "2026-12-31")["state"] == "stale"  # unmeasured
    assert P.publication_decision(trigger, "2026-10-08", material)["state"] == "stale"  # 9 days
    due = P.publication_decision(trigger, "2026-10-09", material)
    assert due["state"] == "withdrawal_due" and "value_per_share" in due["reason"]
    assert P.publication_decision(trigger, "2026-12-31", immaterial)["state"] == "stale"
    assert P.publication_decision(trigger, "2026-12-31", material,
                                  replacement_approved=True)["state"] == "stale"


def test_policy_snapshot_records_the_decisions_from_the_enforced_constants():
    policy = P.policy_snapshot()
    assert policy["version"] == "1.3.0"
    bank = policy["profiles"]["financial_ddm"]["quantitative_materiality_threshold"]
    assert bank["capital_adequacy_ratio"]["threshold"] == P.CAR_MATERIALITY_BP == 50.0
    assert policy["public_staleness"]["grace_trading_days"] == P.WITHDRAWAL_GRACE_TRADING_DAYS
    assert {d["id"] for d in policy["decisions"]} >= {
        "quantitative_materiality_cutoffs", "issuer_actual_calendar",
        "public_staleness_and_withdrawal"}
    assert not {a["id"] for a in policy["ambiguities"]} & {d["id"] for d in policy["decisions"]}


# --- monitor -----------------------------------------------------------------

def _stored(monkeypatch, *, period_end="2026-06-30", latest=None, candidate=None,
            candidate_state="pending", state="approved"):
    published = {"meta": {"model_profile": "going_concern_fcff", "tp": 1000},
                 "model_summary": {"fy1_attributable_earnings": 100.0}}
    manifest = {"publication_id": "a" * 64,
                "official_filing": {"period": "1H26", "period_end": period_end}}

    def load(kind, folder, ticker, db=None):
        if str(folder) == "candidate":
            return candidate if kind == M.outputs.REPORT else None
        return {M.outputs.REPORT: published, M.outputs.MANIFEST: manifest}.get(kind)

    monkeypatch.setattr(M.outputs, "load", load)
    monkeypatch.setattr(M.assumption_review, "status", lambda folder, t, db=None: {
        "state": candidate_state if str(folder) == "candidate" else state})
    monkeypatch.setattr(M, "_latest_official_actual", lambda t, day: latest)
    monkeypatch.setattr(M, "_calendar", lambda t: {})


def test_monitor_is_current_until_a_newer_period_is_due(monkeypatch):
    _stored(monkeypatch)
    assert M.assess("reports", "POWR", "2026-10-30")["state"] == "current"
    late = M.assess("reports", "POWR", "2026-10-31")
    assert late["state"] == "stale" and late["triggers"][0]["kind"] == "filing_due"


def test_monitor_flags_a_newer_official_actual_and_measures_the_candidate(monkeypatch):
    latest = {"period": "9M26", "period_end": "2026-09-30", "published_at": "2026-10-20"}
    candidate = {"meta": {"model_profile": "going_concern_fcff", "tp": 900},
                 "model_summary": {"fy1_attributable_earnings": 100.0}}
    _stored(monkeypatch, latest=latest, candidate=candidate)
    stale = M.assess("reports", "POWR", "2026-10-21", candidate_folder="candidate")
    assert stale["state"] == "stale" and stale["materiality"]["material"]
    due = M.assess("reports", "POWR", "2026-11-03", candidate_folder="candidate")
    assert due["state"] == "withdrawal_due"
    assert due["trading_days_elapsed"] >= P.WITHDRAWAL_GRACE_TRADING_DAYS


def test_monitor_ignores_unpublished_reports(monkeypatch):
    _stored(monkeypatch, state="pending")
    assert M.assess("reports", "POWR", "2027-01-31")["state"] == "not_published"


def test_summarize_model_keeps_missing_bases_out():
    fc = {"outyear_scenario": {"anchor": {"net_profit_attributable": 5.0}},
          "bank_model": {"rows": [{"capital_adequacy_ratio": 0.21}]}}
    assert M.summarize_model(fc, {"sotp": {"attributable_asset_nav_idr": 7.0}}) == {
        "fy1_attributable_earnings": 5.0, "capital_adequacy_ratio": 0.21,
        "attributable_asset_nav": 7.0}
    assert M.summarize_model({}, {}) == {}


def test_gallery_labels_a_stale_publication_without_hiding_it(monkeypatch):
    monkeypatch.setattr(gallery.publication_monitor, "assess", lambda folder, t: {
        "state": "stale", "reason": "Pemicu pembaruan terbuka.",
        "triggers": [{"detail": "Rilis resmi 9M26 terbit 2026-10-20."}]})
    label = gallery._freshness("reports", "POWR")
    assert label["state"] == "stale" and label["triggers"] == ["Rilis resmi 9M26 terbit 2026-10-20."]
    monkeypatch.setattr(gallery.publication_monitor, "assess", lambda folder, t: {"state": "current"})
    assert gallery._freshness("reports", "POWR") == {"state": "current"}
