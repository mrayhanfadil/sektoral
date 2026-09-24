"""MODEL_PROFILE registry for Instruksi-Report-v3.

Single source of truth: which drivers, methods, gates, exhibits and
metrics apply to each business archetype. Ticker symbols never select
an engine; only this registry + verified metadata does.
"""
from __future__ import annotations

PROFILES = ("going_concern_fcff", "financial_ddm", "finite_life_mining")

# Which S2 checks apply per profile. S2.9 always applies (profile-specific chain).
S2_APPLICABILITY = {
    "going_concern_fcff": ("S2.1", "S2.2", "S2.3", "S2.4", "S2.5", "S2.6", "S2.7", "S2.9"),
    "financial_ddm": ("S2.1", "S2.4", "S2.5", "S2.6", "S2.7", "S2.8", "S2.9"),
    "finite_life_mining": ("S2.1", "S2.2", "S2.3", "S2.4", "S2.5", "S2.6", "S2.7", "S2.9"),
}

# Which S3 checks apply per profile.
S3_APPLICABILITY = {
    "going_concern_fcff": ("S3.1", "S3.2", "S3.3", "S3.4", "S3.5", "S3.6", "S3.7"),
    "financial_ddm": ("S3.1", "S3.2", "S3.3", "S3.4", "S3.5", "S3.6", "S3.7"),
    "finite_life_mining": ("S3.2", "S3.3", "S3.4", "S3.5", "S3.6", "S3.7"),
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


def s2_for(profile: str) -> tuple[str, ...]:
    return S2_APPLICABILITY.get(normalize(profile), ())


def s3_for(profile: str) -> tuple[str, ...]:
    return S3_APPLICABILITY.get(normalize(profile), ())


def describe(profile: str) -> dict:
    p = normalize(profile)
    return {
        "profile": p,
        "primary_method": PRIMARY_METHOD.get(p, "unsupported"),
        "s2": list(s2_for(p)),
        "s3": list(s3_for(p)),
        "required_release": list(REQUIRED_RELEASE.get(p, ())),
        "forbidden": list(FORBIDDEN.get(p, ())),
        "cover_metrics": list(COVER_METRICS.get(p, ())),
    }
