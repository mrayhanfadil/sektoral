"""The earnings-quality record: reviewed ledgers in, honest status out."""
from app import build as B, earnings_quality as Q
from tests.test_corporate_actions import SRC, _split
from tests.test_earnings_normalization import _fixture

SOURCES = {"fy25": {"title": "Laporan keuangan FY2025", "url": "https://idx.example/fy25",
                    "published_at": "2026-03-01"}}
PACK = {"filing_sources": SOURCES}


def _ledger(*actions):
    return {"register_counts": [{"date": "2025-12-31", "shares_outstanding": 100,
                                 "source_ref": "fy25"}],
            "actions": list(actions)}


def test_missing_ledgers_are_not_assessed_never_an_empty_pass():
    result = Q.assess(PACK, {"rows": []}, "2026-09-26")
    assert result["status"] == "not_assessed"
    assert "no reviewed earnings normalization ledger" in result["normalization"]["reason"]
    assert "no reviewed share ledger" in result["share_basis"]["reason"]


def test_reviewed_ledgers_are_assessed_and_reconcile_the_model_shares():
    ledger, register = _fixture()
    pack = {**PACK, "normalization_ledger": ledger, "share_ledger": _ledger(_split())}
    result = Q.assess(pack, register, "2026-09-26", model_shares=500)
    assert result["status"] == "assessed"
    assert result["normalization"]["results"][0]["normalized_attributable_earnings"] == "1270"
    assert result["share_basis"]["shares_on_report_date"] == 500
    assert result["share_basis"]["reconciles"] is True


def test_a_model_share_count_that_ignores_a_split_is_a_named_blocker():
    pack = {**PACK, "share_ledger": _ledger(_split())}
    basis = Q.assess(pack, {"rows": []}, "2026-09-26", model_shares=100)["share_basis"]
    assert basis["status"] == "incomplete" and basis["reconciles"] is False
    assert "does not match" in basis["blockers"][0]


def test_invalid_ledgers_are_incomplete_with_their_errors():
    pack = {**PACK, "share_ledger": _ledger({"action_id": "x", "kind": "split", **SRC})}
    result = Q.assess(pack, {"rows": []}, "2026-09-26")
    assert result["status"] == "incomplete"
    assert any("ratio must be a positive number" in e for e in result["share_basis"]["blockers"])


def test_build_records_earnings_quality_without_changing_release(tmp_path):
    doc = B.build("BBCA", tmp_path, as_of="2026-09-24")
    quality = doc["earnings_quality"]
    assert quality["as_of"] == "2026-09-24"
    assert quality["share_basis"]["status"] in {"assessed", "incomplete", "not_assessed"}


def _timeline():
    """One synthetic issuer: FY2025 restated in May, a split in April, a rights issue in June."""
    ledger, register = _fixture()  # FY2025 reported 1,000 (Mar) restated to 1,200 (May)
    rights = {"action_id": "rights-2026", "kind": "rights_issue", "new_shares": 125,
              "subscription_price": 120, "cum_rights_price": 200, "status": "completed",
              "announced_at": "2026-05-20", "ex_date": "2026-06-01",
              "effective_date": "2026-06-15", "shares_before": 500, **SRC}
    pack = {**PACK, "normalization_ledger": ledger, "share_ledger": _ledger(_split(), rights)}
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


def test_filing_source_keys_resolve_to_register_rows_and_give_fy1_normalized_earnings():
    from app import evidence
    filing = {"title": "Laporan keuangan 1H26", "url": "https://idx.example/1h26",
              "page": "PDF 68", "period": "1H26", "published_at": "2026-08-15",
              "currency": "IDR", "unit": "unit"}
    ledger = {
        "adjustments_assessed": True,
        "reported_results": [{"vintage_id": "1h26", "period": "1H26", "published_at": "2026-08-15",
                              "currency": "IDR", "unit": "unit",
                              "reported_attributable_earnings": 1000, "source_refs": ["1h26"]}],
        "adjustments": [
            {"vintage_id": "fx", "adjustment_id": "fx-loss", "period": "1H26",
             "published_at": "2026-08-15", "currency": "IDR", "unit": "unit",
             "classification": "one_off", "pretax_amount": 100, "tax_effect": 22,
             "minority_interest_effect": 0, "normalized_attributable_effect": 78,
             "source_refs": ["1h26"]},
            {"vintage_id": "rent", "adjustment_id": "rent", "period": "1H26",
             "published_at": "2026-08-15", "currency": "IDR", "unit": "unit",
             "classification": "recurring", "pretax_amount": -10, "tax_effect": -2,
             "minority_interest_effect": 0, "normalized_attributable_effect": 0,
             "source_refs": ["1h26"]}]}
    pack = {"filing_sources": {"1h26": filing}, "normalization_ledger": ledger,
            "latest_actual": {}}
    register = evidence.build("XXXX", "2026-09-26", {"official_evidence": pack})
    assert [r["kind"] for r in register["rows"]] == ["official_filing"]
    result = Q.assess(pack, register, "2026-09-26", fiscal_year=2026)["normalization"]
    assert result["status"] == "assessed"
    fy1 = result["fy1"]
    assert (fy1["reported"], fy1["normalized"], fy1["effect"]) == (1000, 1078, 78)
    assert [a["adjustment_id"] for a in fy1["adjustments"]] == ["fx-loss"]
    # A key that is not a filing source stays visible as unresolved and fails closed.
    ledger["adjustments"][0]["source_refs"] = ["missing"]
    broken = Q.assess(pack, register, "2026-09-26", fiscal_year=2026)["normalization"]
    assert broken["status"] == "incomplete" and broken["fy1"] is None
    assert any("unresolved:missing" in b for b in broken["blockers"])
