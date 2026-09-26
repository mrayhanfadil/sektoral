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
