import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.sotp import calculate_sotp  # noqa: E402


def _asset(**overrides):
    row = {
        "name": "Batu Hijau",
        "nav_idr": 1_000_000_000_000,
        "ownership_pct": 80,
        "stage": "producing",
        "method": "life-of-mine DCF",
        "source": "Technical report, p. 42",
        "provenance": "NAV from reserve schedule and stated price deck",
        "source_date": "2026-08-25",
        "page": 42,
    }
    row.update(overrides)
    return row


def test_sotp_bridges_attributable_asset_nav_and_explicit_haircut():
    result = calculate_sotp(
        [_asset(), _asset(name="Smelter", nav_idr=500_000_000_000,
                          ownership_pct=50, stage="ramp-up",
                          method="incremental DCF")],
        cash_idr=200_000_000_000,
        debt_idr=300_000_000_000,
        minority_interest_idr=50_000_000_000,
        corporate_overhead_idr=100_000_000_000,
        shares=80_000_000_000,
        discount_pct=10,
    )

    assert result["status"] == "complete"
    assert result["currency"] == "IDR"
    assert result["amount_unit"] == "raw IDR"
    assert result["attributable_asset_nav_idr"] == 1_050_000_000_000
    assert result["pre_discount_equity_value_idr"] == 800_000_000_000
    assert result["equity_value_idr"] == 720_000_000_000
    assert result["target_price_idr"] == 9
    assert result["assets"][0]["attributable_nav_idr"] == 800_000_000_000
    assert result["gaps"] == []


def test_sotp_without_optional_discount_does_not_apply_a_haircut():
    result = calculate_sotp(
        [_asset(nav_idr=1000, ownership_pct=50)],
        cash_idr=100,
        debt_idr=20,
        minority_interest_idr=10,
        corporate_overhead_idr=10,
        shares=100,
    )

    assert result["status"] == "complete"
    assert result["discount_pct"] is None
    assert result["pre_discount_equity_value_idr"] == 560
    assert result["equity_value_idr"] == 560
    assert result["target_price_idr"] == 5.6


def test_missing_critical_inputs_returns_gaps_and_no_target_price():
    result = calculate_sotp(
        [_asset(nav_idr=None, source="", provenance=None)],
        cash_idr=None,
        debt_idr=10,
        minority_interest_idr=0,
        corporate_overhead_idr=0,
        shares=100,
    )

    assert result["status"] == "incomplete"
    assert result["target_price_idr"] is None
    assert result["pre_discount_equity_value_idr"] is None
    assert result["attributable_asset_nav_idr"] is None
    paths = {item["path"] for item in result["gaps"]}
    assert {
        "assets[0].nav_idr",
        "assets[0].source",
        "assets[0].provenance",
        "cash_idr",
    } <= paths


def test_sotp_asset_requires_dated_page_level_provenance():
    result = calculate_sotp(
        [_asset(source_date="2026-02-30", page=None)],
        cash_idr=100,
        debt_idr=20,
        minority_interest_idr=10,
        corporate_overhead_idr=10,
        shares=100,
    )

    assert result["status"] == "incomplete"
    assert result["target_price_idr"] is None
    paths = {item["path"] for item in result["gaps"]}
    assert {"assets[0].source_date", "assets[0].page"} <= paths


def test_invalid_ownership_and_bridge_values_are_not_coerced_to_zero():
    result = calculate_sotp(
        [_asset(ownership_pct=101)],
        cash_idr="0",
        debt_idr=0,
        minority_interest_idr=0,
        corporate_overhead_idr=0,
        shares=0,
        discount_pct=101,
    )

    assert result["status"] == "incomplete"
    assert result["target_price_idr"] is None
    paths = {item["path"] for item in result["gaps"]}
    assert {"assets[0].ownership_pct", "cash_idr", "shares", "discount_pct"} <= paths


def test_empty_asset_list_is_incomplete():
    result = calculate_sotp(
        [],
        cash_idr=0,
        debt_idr=0,
        minority_interest_idr=0,
        corporate_overhead_idr=0,
        shares=1,
    )

    assert result["status"] == "incomplete"
    assert result["target_price_idr"] is None
    assert result["gaps"] == [{"path": "assets", "reason": "must contain at least one asset"}]
