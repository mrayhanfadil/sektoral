"""Versioned record of the discount-rate and terminal-growth house inputs.

The values below are the existing analyst policy used by the model. Recording
them centrally makes each run reproducible; it does not make them externally
sourced or validated. Dated market/survey observations are shown separately by
``app.rate_benchmarks``. Until the unresolved items are approved, this registry
is a documented baseline and cannot qualify a forecast as Production-Ready.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date


POLICY_VERSION = "1.0.0"
DOCUMENTED_AS_OF = "2026-09-26"

_POLICY = {
    "version": POLICY_VERSION,
    "documented_as_of": DOCUMENTED_AS_OF,
    "status": "used_by_model_not_independently_validated",
    "effective_from": None,
    "effective_date_note": "The prior code constants did not record an effective date; this is an inventory date, not an asserted start date.",
    "discount_rates": {
        "IDR": {
            "risk_free": 0.065,
            "risk_free_basis": "fixed analyst policy parameter; dated INDOGB observation is a separate benchmark",
            "country_risk_premium": 0.0,
            "beta": 1.1,
            "equity_risk_premium": 0.04,
            "cost_of_debt_pretax": 0.09,
            "terminal_growth": 0.035,
            "growth_sensitivity": [0.025, 0.035, 0.045],
            "rate_sensitivity": [-0.01, 0.0, 0.01],
            "scenario_rate_sensitivity": [-0.01, -0.005, 0.0, 0.005, 0.01],
            "screen_rate_sensitivity": [-0.01, 0.0, 0.01],
            "screen_growth_sensitivity": [-0.01, 0.0, 0.01],
        },
        "USD": {
            "risk_free": None,
            "risk_free_basis": "latest dated UST 10Y close on or before Report Date; required",
            "country_risk_premium": 0.025,
            "beta": 1.1,
            "equity_risk_premium": 0.04,
            "cost_of_debt_pretax": None,
            "cost_of_debt_basis": "max(dated UST 10Y + Indonesia CRP, sourced issuer effective cost when available)",
            "terminal_growth": 0.03,
            "growth_sensitivity": [0.02, 0.03, 0.04],
            "rate_sensitivity": [-0.01, 0.0, 0.01],
            "scenario_rate_sensitivity": [-0.01, -0.005, 0.0, 0.005, 0.01],
            "screen_rate_sensitivity": [-0.01, 0.0, 0.01],
            "screen_growth_sensitivity": [-0.01, 0.0, 0.01],
        },
    },
    "screening": {
        "exit_ev_ebitda_multiple": 8.0,
        "exit_multiple_basis": "analyst screening parameter only; selected value requires a supported peer or issuer-history basis",
    },
    "production_validation": {
        "status": "not_approved",
        "approval_required": True,
        "effective_from": None,
        "independent_reference_validation": "required per Model Profile",
        "terminal_economics_validation": "reinvestment and incremental-return relationship is not supplied",
        "review_owner": "research_governance",
    },
    "unresolved": [
        "approval and effective date of the fixed IDR risk-free, ERP, beta, CRP, cost-of-debt, and terminal-growth policy values",
        "terminal growth consistency with reinvestment and incremental returns on capital for FCFF methods",
        "terminal growth consistency with sustainable payout and returns on equity for equity methods",
        "dated issuer-specific deviations from the house policy",
        "whether and when dated benchmark observations replace or only challenge policy inputs",
    ],
}


def policy_snapshot() -> dict:
    """A detached JSON-compatible baseline for embedding in run manifests."""
    return json.loads(json.dumps(_POLICY, sort_keys=True))


def policy_sha256(policy: dict | None = None) -> str:
    body = policy_snapshot() if policy is None else policy
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def versioned_snapshot() -> dict:
    body = policy_snapshot()
    return {"policy": body, "sha256": policy_sha256(body)}


def discount_inputs(currency: str) -> dict:
    """Return the model inputs for a currency without caller mutation."""
    code = str(currency or "").upper()
    selected = policy_snapshot()["discount_rates"].get(code)
    if selected is None:
        raise ValueError(f"unsupported house-assumption currency: {currency}")
    return selected


def _effective_date_blockers(effective_from, as_of) -> list[str]:
    if not effective_from:
        return ["house discount-rate and terminal-growth assumptions lack an approved effective date"]
    try:
        effective = date.fromisoformat(str(effective_from)[:10])
    except (TypeError, ValueError):
        return ["house-assumption effective date must be a valid ISO date"]
    try:
        report_date = date.fromisoformat(str(as_of)[:10]) if as_of else None
    except (TypeError, ValueError):
        report_date = None
    if report_date is None:
        return ["report date is required to validate the house-assumption policy vintage"]
    if effective > report_date:
        return ["house-assumption policy became effective after the Report Date"]
    return []


def production_readiness_blockers(as_of: str | None = None) -> list[str]:
    """Missing controls that must be approved before any Production-Ready path."""
    validation = policy_snapshot().get("production_validation") or {}
    blockers = []
    blockers.extend(_effective_date_blockers(validation.get("effective_from"), as_of))
    if validation.get("status") != "approved" and not any(
            blocker.startswith("house discount-rate") for blocker in blockers):
        blockers.append("house discount-rate and terminal-growth assumptions are not approved")
    if validation.get("terminal_economics_validation") != "complete":
        blockers.append("terminal growth is not reconciled to reinvestment and incremental return on capital")
    if validation.get("independent_reference_validation") != "complete":
        blockers.append("independent reference validation is not recorded for each Model Profile")
    return blockers
