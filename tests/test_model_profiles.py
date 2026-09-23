"""Profile selection follows issuer economics and verified metadata, not tickers."""

from app.model_profiles import resolve


def test_configured_profile_takes_precedence_over_sector_label():
    assert resolve({"model_profile": "financial_ddm", "industry": "Mining"}) == (
        "financial_ddm", "configured issuer model profile")


def test_metadata_routes_business_archetypes_without_ticker_branches():
    assert resolve({"industry": "Metal Mining"})[0] == "finite_life_mining"
    assert resolve({"sub_sector": "Bank"})[0] == "financial_ddm"
    assert resolve({"sector": "Consumer Goods"})[0] == "going_concern_fcff"


def test_missing_or_unknown_profile_fails_closed():
    assert resolve({})[0] == "unsupported"
    assert resolve({"model_profile": "issuer_specific_magic"})[0] == "unsupported"
