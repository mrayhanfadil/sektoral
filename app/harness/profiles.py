"""MODEL_PROFILE registry for Instruksi-Report-v3.

Single source of truth: which drivers, methods, gates, exhibits and
metrics apply to each business archetype. Ticker symbols never select
an engine; only this registry + verified metadata does.
"""
from __future__ import annotations

PROFILES = ("going_concern_fcff", "financial_ddm", "finite_life_mining")

# Which G2 checks apply per profile. G2.9 always applies (profile-specific chain).
G2_APPLICABILITY = {
    "going_concern_fcff": ("G2.1", "G2.2", "G2.3", "G2.4", "G2.5", "G2.6", "G2.7", "G2.9"),
    "financial_ddm": ("G2.1", "G2.4", "G2.5", "G2.6", "G2.7", "G2.8", "G2.9"),
    "finite_life_mining": ("G2.1", "G2.2", "G2.3", "G2.4", "G2.5", "G2.6", "G2.7", "G2.9"),
}

# Which G3 checks apply per profile.
G3_APPLICABILITY = {
    "going_concern_fcff": ("G3.1", "G3.2", "G3.3", "G3.4", "G3.5", "G3.6", "G3.7"),
    "financial_ddm": ("G3.1", "G3.2", "G3.3", "G3.4", "G3.5", "G3.6", "G3.7"),
    "finite_life_mining": ("G3.2", "G3.3", "G3.4", "G3.5", "G3.6", "G3.7"),
}

PRIMARY_METHOD = {
    "going_concern_fcff": "FCFF DCF (explicit horizon + Gordon/exit terminal)",
    "financial_ddm": "DDM / residual income / P/BV-vs-ROE (Cost of Equity, no WACC)",
    "finite_life_mining": "LoM DCF / RNAV-SOTP to end of economic life (no perpetual terminal)",
}

# Required evidence keys for production release (§4.5).
REQUIRED_RELEASE = {
    "going_concern_fcff": (
        "latest_official_actual",
        "driver_forecast:revenue,ebitda,net_profit,capex",
        "fcff_dcf",
        "enterprise_to_equity_bridge",
    ),
    "financial_ddm": (
        "latest_official_actual",
        "driver_forecast:profit,equity,payout",
        "ddm_or_residual",
        "coe_bridge",
        "equity_value_bridge",
    ),
    "finite_life_mining": (
        "latest_interim_actuals",
        "physical_to_financial_chain",
        "lom_forecast",
        "sotp_nav_bridge",
    ),
}

# Forbidden mechanics per profile (§3.1, §4.1).
FORBIDDEN = {
    "going_concern_fcff": (),
    "financial_ddm": ("fcff", "ev_wacc", "capex_as_release_req", "nwc_as_release_req",
                      "operating_bridge_mining"),
    "finite_life_mining": ("perpetual_terminal_as_primary",),
}

# Cover metrics per profile (§5.4).
COVER_METRICS = {
    "going_concern_fcff": ("revenue", "ebitda", "net_profit", "eps", "capex", "fcff",
                           "bvps", "per", "ev_ebitda"),
    "financial_ddm": ("net_interest_or_ops", "net_profit", "eps", "roe", "equity_bvps",
                      "payout_dps", "pbv_per"),
    "finite_life_mining": ("payable_output", "realized_price", "revenue", "ebitda",
                           "net_profit", "capex", "lom_sotp_bridge"),
}


def normalize(profile: str | None) -> str:
    p = str(profile or "").strip().lower()
    return p if p in PROFILES else "unsupported"


def g2_for(profile: str) -> tuple[str, ...]:
    return G2_APPLICABILITY.get(normalize(profile), ())


def g3_for(profile: str) -> tuple[str, ...]:
    return G3_APPLICABILITY.get(normalize(profile), ())


def describe(profile: str) -> dict:
    p = normalize(profile)
    return {
        "profile": p,
        "primary_method": PRIMARY_METHOD.get(p, "unsupported"),
        "g2": list(g2_for(p)),
        "g3": list(g3_for(p)),
        "required_release": list(REQUIRED_RELEASE.get(p, ())),
        "forbidden": list(FORBIDDEN.get(p, ())),
        "cover_metrics": list(COVER_METRICS.get(p, ())),
    }
