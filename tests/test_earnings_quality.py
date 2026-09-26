"""The earnings-quality record: reviewed ledgers in, honest status out."""
from app import build as B, earnings_quality as Q
from tests.test_corporate_actions import SRC, _split
from tests.test_earnings_normalization import _fixture

PACK = {"balance_sheet": {"shares_outstanding": 100, "period_end": "2025-12-31"}}


def test_missing_ledgers_are_not_assessed_never_an_empty_pass():
    result = Q.assess(PACK, {"rows": []}, "2026-09-26")
    assert result["status"] == "not_assessed"
    assert "no reviewed earnings normalization ledger" in result["normalization"]["reason"]
    assert "no corporate-action ledger" in result["share_basis"]["reason"]
    assert result["calculation_only"] is True


def test_reviewed_ledgers_are_assessed_and_reconcile_the_model_shares():
    ledger, register = _fixture()
    pack = {**PACK, "normalization_ledger": ledger, "corporate_actions": [_split()]}
    result = Q.assess(pack, register, "2026-09-26", model_shares=500)
    assert result["status"] == "assessed"
    assert result["normalization"]["results"][0]["normalized_attributable_earnings"] == "1270"
    assert result["share_basis"]["shares_on_report_date"] == 500
    assert result["share_basis"]["reconciles"] is True


def test_a_model_share_count_that_ignores_a_split_is_a_named_blocker():
    pack = {**PACK, "corporate_actions": [_split()]}
    basis = Q.assess(pack, {"rows": []}, "2026-09-26", model_shares=100)["share_basis"]
    assert basis["status"] == "incomplete" and basis["reconciles"] is False
    assert "does not match" in basis["blockers"][0]


def test_invalid_ledgers_are_incomplete_with_their_errors():
    pack = {**PACK, "corporate_actions": [{"action_id": "x", "kind": "split", **SRC}]}
    result = Q.assess(pack, {"rows": []}, "2026-09-26")
    assert result["status"] == "incomplete"
    assert any("ratio must be a positive number" in e for e in result["share_basis"]["blockers"])


def test_build_records_earnings_quality_without_changing_release(tmp_path):
    doc = B.build("BBCA", tmp_path, as_of="2026-09-24")
    quality = doc["earnings_quality"]
    # No source pack carries reviewed ledgers yet: the record says so.
    assert quality["status"] == "not_assessed" and quality["calculation_only"] is True
    assert quality["as_of"] == "2026-09-24"


def _timeline():
    """One synthetic issuer: FY2025 restated in May, a split in April, a rights issue in June."""
    ledger, register = _fixture()  # FY2025 reported 1,000 (Mar) restated to 1,200 (May)
    rights = {"action_id": "rights-2026", "kind": "rights_issue", "new_shares": 125,
              "subscription_price": 120, "cum_rights_price": 200, "status": "completed",
              "announced_at": "2026-05-20", "ex_date": "2026-06-01",
              "effective_date": "2026-06-15", **SRC}
    pack = {**PACK, "normalization_ledger": ledger, "corporate_actions": [_split(), rights]}
    return pack, register


def test_earlier_report_dates_are_not_contaminated_by_later_events():
    pack, register = _timeline()
    april = Q.assess(pack, register, "2026-04-15")
    # Original FY2025 vintage, split applied, rights issue not yet announced.
    assert april["normalization"]["results"][0]["reported_result"]["vintage_id"] == "reported-v1"
    assert april["share_basis"]["shares_on_report_date"] == 500
    assert april["share_basis"]["conditional_scenarios"] == []

    may = Q.assess(pack, register, "2026-05-25")
    # Restatement is known; the announced rights issue is only a conditional scenario.
    assert may["normalization"]["results"][0]["reported_result"]["vintage_id"] == \
        "reported-v2-restatement"
    assert may["share_basis"]["shares_on_report_date"] == 500
    assert [s["action_id"] for s in may["share_basis"]["conditional_scenarios"]] == ["rights-2026"]

    july = Q.assess(pack, register, "2026-07-01")
    assert july["share_basis"]["shares_on_report_date"] == 625
    assert july["share_basis"]["conditional_scenarios"] == []


def test_cumulative_interim_growth_uses_derived_standalone_quarters():
    from app import period_basis as P
    fig = lambda v: {"value": v, "currency": "IDR", "unit": "million", "scope": "consolidated"}
    this_year = {"Q1 2026": fig(300.0), "1H26": fig(700.0)}
    last_year = {"Q1 2025": fig(280.0), "1H25": fig(600.0)}
    q2_now = P.standalone_quarter(this_year, 2, 2026)
    q2_before = P.standalone_quarter(last_year, 2, 2025)
    growth = P.comparable_growth("Q2 2026", q2_now, "Q2 2025", q2_before)
    assert (q2_now["value"], q2_before["value"]) == (400.0, 320.0)
    assert growth == 0.25  # standalone Q2, not the 16.7% cumulative 1H growth
