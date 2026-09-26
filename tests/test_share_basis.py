"""Synthetic share ledgers; no issuer data is implied."""
import pytest

from app import share_basis as SB

SOURCES = {
    "fy25": {"title": "Laporan keuangan FY2025", "url": "https://idx.example/fy25",
             "published_at": "2026-03-31", "page": "PDF 60"},
    "1h26": {"title": "Laporan keuangan 1H26", "url": "https://idx.example/1h26",
             "published_at": "2026-08-15", "page": "PDF 70"},
    "profile": {"title": "Profil emiten", "url": "https://idx.example/profile",
                "published_at": "2026-09-20"},
}


def _rights(**kw):
    return {"action_id": "rights", "kind": "rights_issue", "status": "completed",
            "new_shares": 1000, "subscription_price": 250, "cum_rights_price": 750,
            "shares_before": 1000, "announced_at": "2025-12-01", "ex_date": "2026-01-05",
            "effective_date": "2026-01-22", "source_ref": "1h26", **kw}


def _pack(**ledger):
    base = {"register_counts": [
        {"date": "2025-12-31", "shares_outstanding": 1000, "source_ref": "fy25"},
        {"date": "2026-06-30", "shares_outstanding": 2000, "source_ref": "1h26"}],
        "actions": [_rights()], "reviewed_through": "2026-09-26"}
    base.update(ledger)
    return {"filing_sources": SOURCES, "share_ledger": base}


def test_register_counts_reconcile_through_dated_actions():
    record = SB.assess(_pack(), "2026-09-26", price=500)
    assert record["status"] == "assessed"
    assert record["shares_on_report_date"] == 2000
    assert record["reconciliation"][0]["reconciles"] is True
    assert record["basis"]["source_ref"] == "1h26"


def test_a_missing_action_blocks_the_ledger():
    record = SB.assess(_pack(actions=[]), "2026-09-26")
    assert record["status"] == "incomplete"
    assert "an action is missing" in record["blockers"][0]
    assert SB.model_shares(record) is None


def test_counts_published_after_the_report_date_are_not_known():
    record = SB.assess(_pack(), "2026-08-01")
    assert record["basis"]["date"] == "2025-12-31"
    assert record["shares_on_report_date"] == 2000  # the dated rights issue was known


def test_a_reported_weighted_average_that_ignores_dated_actions_is_replaced():
    # TERP = (1000 x 750 + 1000 x 250) / 2000 = 500, bonus factor 1.5; the new
    # shares count from 22 Jan: 1000 x 1.5 x 21 days + 2000 x 160 days.
    derived = (1500 * 21 + 2000 * 160) / 181
    reported = [{"start": "2026-01-01", "end": "2026-06-30", "shares": 1100, "source_ref": "1h26"}]
    record = SB.assess(_pack(reported_weighted_average=reported), "2026-09-26")
    weighted = record["fy_weighted_average"]
    assert weighted["derived"] == pytest.approx(derived)
    assert weighted["h1_basis"] == "derived_from_dated_actions"
    assert "does not reconcile" in record["warnings"][0]
    assert weighted["shares"] == pytest.approx((derived * 181 + 2000 * 184) / 365)


def test_a_reconciling_reported_weighted_average_is_kept():
    derived = (1500 * 21 + 2000 * 160) / 181
    reported = [{"start": "2026-01-01", "end": "2026-06-30", "shares": round(derived),
                 "source_ref": "1h26"}]
    record = SB.assess(_pack(reported_weighted_average=reported), "2026-09-26")
    assert record["fy_weighted_average"]["h1_basis"] == "issuer_reported"
    assert record["warnings"] == []


def test_aggregate_changes_reconcile_but_keep_the_issuer_weighted_average():
    buyback = {"action_id": "bb-h2", "kind": "buyback", "status": "completed", "shares": 10,
               "cash_paid": 5000, "timing": "aggregate", "announced_at": "2026-06-01",
               "effective_date": "2026-09-20", "source_ref": "profile"}
    counts = [{"date": "2026-06-30", "shares_outstanding": 2000, "source_ref": "1h26"},
              {"date": "2026-09-20", "shares_outstanding": 1990, "source_ref": "profile"}]
    reported = [{"start": "2026-01-01", "end": "2026-06-30", "shares": 1950, "source_ref": "1h26"}]
    record = SB.assess(_pack(register_counts=counts, actions=[buyback],
                             reported_weighted_average=reported), "2026-09-26")
    assert record["status"] == "assessed"
    assert record["shares_on_report_date"] == 1990
    weighted = record["fy_weighted_average"]
    assert weighted["h1_basis"] == "issuer_reported" and weighted["derived"] is None
    h2 = (2000 * 81 + 1990 * 103) / 184  # 1 Jul - 19 Sep, then 20 Sep - 31 Dec
    assert weighted["h2_shares"] == pytest.approx(h2)


def test_warrants_dilute_eps_at_price_and_value_only_when_in_the_money():
    warrant = {"instrument_id": "w2", "kind": "warrant", "shares": 200, "exercise_price": 300,
               "exercisable_from": "2026-07-13", "expires_at": "2028-07-11", "source_ref": "1h26"}
    record = SB.assess(_pack(dilutive_instruments=[warrant]), "2026-09-26", price=400)
    assert record["dilution_at_price"]["incremental_shares"] == pytest.approx(200 * (1 - 300 / 400))
    below = SB.dilute_at_value(250, 2000, record["instruments"])
    assert below["per_share"] == 250 and below["excluded"] == ["w2"]
    above = SB.dilute_at_value(500, 2000, record["instruments"])
    assert above["per_share"] == pytest.approx((500 * 2000 + 200 * 300) / 2200)


def test_report_date_shares_falls_back_to_outstanding_then_issued():
    intake = {"as_of": "2026-09-26", "share_basis": SB.assess(_pack(), "2026-09-26")}
    assert SB.report_date_shares(intake)[0] == 2000
    balance = {"period_end": "2026-06-30", "shares_issued": 2100, "shares_outstanding": 2050}
    assert SB.report_date_shares({"official_evidence": {"balance_sheet": balance}})[0] == 2050
    del balance["shares_outstanding"]
    assert SB.report_date_shares({"official_evidence": {"balance_sheet": balance}})[0] == 2100
    assert SB.assess({}, "2026-09-26")["status"] == "not_assessed"
