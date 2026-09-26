"""Synthetic corporate-action fixtures; no issuer data is implied."""
import pytest

from app import corporate_actions as C

SRC = {"source_title": "Keterbukaan informasi sintetis", "source_url": "https://idx.example/ca"}


def _split(**kw):
    return {"action_id": "split-1to5", "kind": "split", "ratio": 5, "status": "completed",
            "announced_at": "2026-03-01", "ex_date": "2026-04-01", "effective_date": "2026-04-01",
            **SRC, **kw}


def _rights(**kw):
    # 100 old shares at a cum-rights close of 1,000; 25 new shares at 600.
    return {"action_id": "rights-2026", "kind": "rights_issue", "new_shares": 25,
            "subscription_price": 600, "cum_rights_price": 1000, "status": "completed",
            "announced_at": "2026-05-01", "ex_date": "2026-06-01", "effective_date": "2026-06-15",
            **SRC, **kw}


def test_validation_names_every_missing_date_term_source_and_condition():
    bad = [{"action_id": "x", "kind": "split", "ratio": 0.5, "status": "completed",
            "announced_at": "2026-03-01"},
           {"action_id": "x", "kind": "rights_issue", "status": "pending", "announced_at": "bad"},
           {"action_id": "y", "kind": "merger"}]
    errors = C.validate(bad)
    assert any("without a valid effective_date" in e for e in errors)
    assert any("split ratio must be above 1" in e for e in errors)
    assert any("source_title and source_url" in e for e in errors)
    assert any("duplicate action_id 'x'" in e for e in errors)
    assert any("pending without its conditions" in e for e in errors)
    assert any("kind 'merger'" in e for e in errors)
    assert C.validate([_split(), _rights()]) == []
    assert C.validate([_split(effective_date="2026-02-01")])  # before announcement


def test_split_moves_the_share_count_only_after_it_takes_effect_and_is_known():
    ledger = [_split()]
    assert C.shares_on(100, "2025-12-31", ledger, "2026-03-31", "2026-09-26") == 100
    assert C.shares_on(100, "2025-12-31", ledger, "2026-06-30", "2026-09-26") == 500
    # A Report Date before the announcement cannot know the split.
    assert C.shares_on(100, "2025-12-31", ledger, "2026-06-30", "2026-02-15") == 100


def test_pending_and_cancelled_actions_never_change_actual_shares():
    pending = _rights(status="pending", effective_date=None,
                      conditions="Menunggu persetujuan RUPSLB dan pernyataan efektif OJK.")
    cancelled = _split(action_id="split-cancelled", status="cancelled")
    assert C.shares_on(100, "2025-12-31", [pending, cancelled], "2026-12-31", "2026-09-26") == 100
    scenarios = C.conditional_scenarios([pending, cancelled], "2026-09-26")
    assert [s["action_id"] for s in scenarios] == ["rights-2026"]
    assert "RUPSLB" in scenarios[0]["conditions"]


def test_price_factor_restates_history_for_splits_and_the_rights_bonus_element():
    assert C.price_adjustment_factor([_split()], "2026-01-02", "2026-09-26", "2026-09-26") == 0.2
    assert C.price_adjustment_factor([_split()], "2026-05-01", "2026-09-26", "2026-09-26") == 1.0
    rights = _rights()
    # TERP = (100 x 1,000 + 25 x 600) / 125 = 920, so the factor is 0.92.
    assert C.terp(100, rights) == pytest.approx(920.0)
    factor = C.price_adjustment_factor([rights], "2026-05-15", "2026-09-26", "2026-09-26",
                                       shares_before_rights={"rights-2026": 100})
    assert factor == pytest.approx(0.92)
    with pytest.raises(ValueError, match="share count before it"):
        C.price_adjustment_factor([rights], "2026-05-15", "2026-09-26", "2026-09-26")


def test_reverse_split_buyback_and_conversion_move_the_count_in_order():
    ledger = [
        _split(action_id="reverse", kind="reverse_split", ratio=0.2,
               ex_date="2026-02-01", effective_date="2026-02-01", announced_at="2026-01-10"),
        {"action_id": "buyback", "kind": "buyback", "shares": 5, "cash_paid": 50_000,
         "status": "completed", "announced_at": "2026-02-10", "effective_date": "2026-03-01", **SRC},
        {"action_id": "cb", "kind": "conversion", "new_shares": 10, "debt_converted": 90_000,
         "status": "completed", "announced_at": "2026-03-10", "effective_date": "2026-04-01", **SRC},
    ]
    # 1,000 -> reverse 1:5 = 200 -> buyback 5 = 195 -> conversion 10 = 205.
    assert C.shares_on(1000, "2025-12-31", ledger, "2026-06-30", "2026-09-26") == 205
    assert C.price_adjustment_factor(ledger, "2026-01-02", "2026-06-30", "2026-09-26") == 5.0


def test_invalid_ledger_or_share_base_fails_closed():
    with pytest.raises(ValueError):
        C.shares_on(100, "2025-12-31", [{"action_id": "x"}], "2026-06-30", "2026-09-26")
    with pytest.raises(ValueError, match="positive"):
        C.shares_on(0, "2025-12-31", [], "2026-06-30", "2026-09-26")
