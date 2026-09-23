"""Profile routing from configured or verified business metadata.

Profiles describe business economics and applicable methods; ticker symbols
never select an engine.
"""
from __future__ import annotations


SUPPORTED_PROFILES = {
    "finite_life_mining": "LoM/SOTP",
    "going_concern_fcff": "FCFF DCF",
    "financial_ddm": "DDM/residual income",
}


def resolve(metadata: dict) -> tuple[str, str]:
    """Return ``(profile, selection_basis)`` for issuer metadata.

    A configured profile takes precedence. Otherwise, verified industry labels
    map to a supported business archetype; unknown metadata fails closed.
    """
    explicit = metadata.get("model_profile")
    if explicit:
        profile = str(explicit).strip().lower()
        if profile in SUPPORTED_PROFILES:
            return profile, "configured issuer model profile"
        return "unsupported", f"unsupported configured model profile: {explicit}"

    industry_text = " ".join(str(metadata.get(key) or "") for key in
                             ("industry", "sub_sector", "sector")).lower()
    if not industry_text.strip():
        return "unsupported", "industry metadata is missing"

    if any(term in industry_text for term in
           ("mining", "minerals", "metal", "coal")):
        return "finite_life_mining", "verified extractive industry metadata"
    if any(term in industry_text for term in
           ("bank", "insurance", "financial")):
        return "financial_ddm", "verified financial industry metadata"
    return "going_concern_fcff", "verified non-financial industry metadata"
