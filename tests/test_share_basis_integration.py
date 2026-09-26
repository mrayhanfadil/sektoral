"""The reviewed share ledger drives every per-share figure of a build."""
from app import intake, scenario_value, share_basis


def test_intake_uses_the_ledger_count_net_of_treasury_shares():
    doc, _ = intake.load("SIDO", as_of="2026-09-26")
    assert doc["share_basis"]["status"] == "assessed"
    # 30.000.000.000 issued less treasury shares (Catatan 1c), not the issued count.
    assert doc["shares"] == 29520300000
    assert doc["market_cap"] == doc["price"] * 29520300000
    assert scenario_value.bridge(doc)["shares"] == 29520300000
    assert share_basis.report_date_shares(doc)[0] == 29520300000


def test_a_rights_issue_moves_the_model_count_off_the_stale_cache():
    doc, _ = intake.load("INET", as_of="2026-09-26")
    assert doc["shares"] == 22374111088
    weighted = doc["share_basis"]["fy_weighted_average"]
    assert weighted["h1_basis"] == "derived_from_dated_actions"
    assert doc["share_basis"]["dilution_at_price"]["incremental_shares"] > 0
