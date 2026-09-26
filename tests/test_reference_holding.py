"""Holding SOTP: independent reference and the production gate (decision D7)."""
import pytest

from app import landbank, method_chain, reference_holding, release


def _land():
    inp = {"gross_ha": 100.0, "net_ratio": 0.65, "pace_ha": 20.0, "asp": 2_000_000.0,
           "asp_growth": 0.02, "cash_margin": 0.5, "carrying_idr": 5e11, "stake": 0.635}
    nav, years = landbank.nav(inp, 0.109)
    return {"inputs": inp, "rate": 0.109, "nav": nav, "years": years,
            "uplift_attributable": (nav - inp["carrying_idr"]) * inp["stake"]}


LISTED = [{"ticker": "NRCA", "stake": 0.6394, "market_cap": 1.3e12, "book_equity": 1.36e12,
           "market_date": "2026-09-24", "book_date": "2026-06-30",
           "stake_source": "IDX register", "market_source": "Yahoo close"}]


def test_the_reference_rebuilds_the_holding_value():
    land = _land()
    production = method_chain.holding_sotp(LISTED, 5.78e12, 4.7e9, landbank=land)["per_share"]
    check = reference_holding.compare(LISTED, 5.78e12, 4.7e9, land, production)
    assert check["status"] == "agrees"
    assert check["reference_per_share"] == pytest.approx(production, rel=1e-9)
    assert reference_holding.compare(LISTED, 5.78e12, 4.7e9, land, production * 1.02)[
        "status"] == "differs"


def test_undated_or_stale_components_block_production():
    detail = {"balance_period": "2026-06-30", "landbank": _land(),
              "terminal_economics": {"status": "not_applicable"},
              "reference_validation": {"status": "agrees"}}
    intake = {"as_of": "2026-09-26"}
    assert release._holding_production_blockers(intake, detail, LISTED) == []
    stale = [{**LISTED[0], "market_date": "2026-09-10", "book_date": "2025-12-31"}]
    out = release._holding_production_blockers(intake, detail, stale)
    assert any("outside the 5-day window" in b for b in out)
    assert any("book equity is not dated" in b for b in out)
