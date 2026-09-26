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


def test_weighted_average_restates_a_split_for_the_whole_period():
    # 100 shares all year, split 1:5 on 1 April: 500 weighted for the full year.
    result = C.weighted_average_shares(100, "2025-12-31", "2026-01-01", "2026-12-31",
                                       [_split()], "2027-03-31")
    assert result["weighted_average_shares"] == pytest.approx(500.0)
    assert result["closing_shares"] == 500


def test_weighted_average_counts_a_placement_from_its_effective_date():
    placement = {"action_id": "pp", "kind": "private_placement", "new_shares": 50, "price": 800,
                 "status": "completed", "announced_at": "2026-06-01",
                 "effective_date": "2026-07-02", **SRC}
    # 100 shares for 182 days (1 Jan - 1 Jul), 150 for 183 days.
    result = C.weighted_average_shares(100, "2025-12-31", "2026-01-01", "2026-12-31",
                                       [placement], "2027-03-31")
    assert result["weighted_average_shares"] == pytest.approx((100 * 182 + 150 * 183) / 365)


def test_rights_issue_adds_its_bonus_element_before_and_new_shares_after():
    rights = _rights()  # bonus factor 1,000 / 920; 25 new shares from 15 June
    result = C.weighted_average_shares(100, "2025-12-31", "2026-01-01", "2026-12-31",
                                       [rights], "2027-03-31")
    before_days, after_days = 165, 200  # 1 Jan - 14 Jun, 15 Jun - 31 Dec
    expected = (100 * 1000 / 920 * before_days + 125 * after_days) / 365
    assert result["weighted_average_shares"] == pytest.approx(expected)


def test_diluted_eps_excludes_anti_dilutive_instruments():
    warrants_in = {"kind": "warrant", "shares": 20, "exercise_price": 500}
    warrants_out = {"kind": "warrant", "shares": 20, "exercise_price": 1500}
    cheap_cb = {"kind": "convertible", "shares": 10, "interest_after_tax": 50}   # 5 per share
    costly_cb = {"kind": "convertible", "shares": 10, "interest_after_tax": 400}  # 40 per share
    result = C.diluted_eps(1000, 100, [warrants_in, warrants_out, cheap_cb, costly_cb],
                           average_price=1000)
    assert result["basic_eps"] == 10
    # Warrants add 10 incremental shares; the cheap convertible dilutes further.
    assert result["diluted_eps"] == pytest.approx((1000 + 50) / (100 + 10 + 10))
    assert result["included"] == ["warrant", "convertible"]
    assert result["anti_dilutive_excluded"] == ["convertible"]


def test_financing_effects_carry_cash_and_debt_with_the_dilution():
    buyback = {"action_id": "bb", "kind": "buyback", "shares": 5, "cash_paid": 4_000,
               "status": "completed", "announced_at": "2026-02-01", "effective_date": "2026-03-01", **SRC}
    cb = {"action_id": "cb", "kind": "conversion", "new_shares": 10, "debt_converted": 9_000,
          "status": "completed", "announced_at": "2026-02-01", "effective_date": "2026-03-01", **SRC}
    effects = C.financing_effects([_rights(), buyback, cb, _split()], "2026-01-01", "2026-12-31",
                                  "2027-03-31")
    assert effects["net_cash"] == 25 * 600 - 4_000
    assert effects["net_debt_change"] == -9_000
    assert {r["action_id"] for r in effects["rows"]} == {"rights-2026", "bb", "cb"}


def test_an_aggregate_buyback_may_omit_its_undisclosed_cash():
    aggregate = {"action_id": "bb-q3", "kind": "buyback", "shares": 13, "timing": "aggregate",
                 "status": "completed", "announced_at": "2026-06-01",
                 "effective_date": "2026-09-24", **SRC}
    assert C.validate([aggregate]) == []
    assert C.validate([{**aggregate, "timing": None}])  # a dated buyback needs its cash
    assert C.shares_on(1000, "2026-06-30", [aggregate], "2026-09-26", "2026-09-26") == 987
    effects = C.financing_effects([aggregate], "2026-01-01", "2026-12-31", "2026-09-26")
    assert effects["rows"] == [] and effects["undisclosed_cash"] == ["bb-q3"]


def test_a_rights_tail_after_the_ex_date_carries_no_bonus_restatement():
    tail = _rights(bonus_restated=False, effective_date="2026-06-15")
    result = C.weighted_average_shares(100, "2025-12-31", "2026-01-01", "2026-12-31",
                                       [tail], "2027-03-31")
    assert result["weighted_average_shares"] == pytest.approx((100 * 165 + 125 * 200) / 365)
