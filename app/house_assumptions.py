"""Versioned record of the discount-rate and terminal-growth house inputs.

The values below are the existing analyst policy used by the model. Recording
them centrally makes each run reproducible; it does not make them externally
sourced or validated. Dated market/survey observations are shown separately by
``app.rate_benchmarks``. Until the unresolved items are approved, this registry
is a documented baseline and cannot qualify a forecast as Production-Ready.

``parameters`` describes every model-active value (plan §5.5): currency, tenor,
nominal or real basis, whether it is a fixed policy value or a dated
observation, its rationale and the dated benchmark it is reviewed against, and
a review range. ``discount_rates`` holds the same values in the shape the model
reads; a test keeps the two identical. Terminal economics are checked per run
(``app.terminal_economics``), not asserted here. An issuer-specific deviation
from these values is not supported: a pack that carries one fails closed.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date


POLICY_VERSION = "1.2.0"
DOCUMENTED_AS_OF = "2026-09-26"

_POLICY = {
    "version": POLICY_VERSION,
    "documented_as_of": DOCUMENTED_AS_OF,
    "status": "approved_not_independently_validated",
    "effective_from": "2026-09-26",
    "effective_date_note": "Approved by the Sektoral Team on 2026-09-26 for Report Dates on or after that date; earlier runs used the same values without an approved policy.",
    "approved_by": "Sektoral Team",
    "approved_at": "2026-09-26",
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
    "parameters": [
        {"id": "IDR.risk_free", "value": 0.065, "currency": "IDR", "tenor": "10Y",
         "basis": "nominal", "kind": "policy", "review_range": [0.06, 0.075],
         "benchmark": "rate_benchmarks.rf_idr (INDOGB 10Y close)",
         "rationale": "Fixed policy rate for rupiah cash flows. The local-currency government "
                      "yield already carries the sovereign default spread, so rupiah models "
                      "add no country risk premium. The dated INDOGB close is shown beside "
                      "it; replacing the policy value with the observation is an open policy "
                      "item."},
        {"id": "IDR.equity_risk_premium", "value": 0.04, "currency": "IDR", "tenor": "long-run",
         "basis": "nominal", "kind": "policy", "review_range": [0.035, 0.06],
         "benchmark": "rate_benchmarks.erp (Damodaran implied mature-market ERP)",
         "rationale": "Mature-market equity risk premium; the January 2026 implied premium "
                      "(4.23%) lies inside the review range."},
        {"id": "IDR.country_risk_premium", "value": 0.0, "currency": "IDR", "tenor": "long-run",
         "basis": "nominal", "kind": "policy", "review_range": [0.0, 0.0],
         "benchmark": "rate_benchmarks.crp (Damodaran country default spread)",
         "rationale": "Zero for rupiah: the INDOGB-based risk-free rate embeds the sovereign "
                      "spread (2.46% for Baa2 in January 2026); adding it again would count "
                      "the same risk twice."},
        {"id": "IDR.beta", "value": 1.1, "currency": "IDR", "tenor": "n/a", "basis": "n/a",
         "kind": "policy", "review_range": [0.6, 1.6],
         "benchmark": "rate_benchmarks.beta (weekly regression on IHSG, raw and Blume-adjusted)",
         "rationale": "Uniform policy beta; issuer regression betas are shown as benchmarks, "
                      "not applied."},
        {"id": "IDR.cost_of_debt_pretax", "value": 0.09, "currency": "IDR", "tenor": "long-run",
         "basis": "nominal", "kind": "policy", "review_range": [0.07, 0.12],
         "benchmark": "issuer effective interest cost where the pack reports it",
         "rationale": "Pre-tax rupiah borrowing cost for the WACC debt weight."},
        {"id": "IDR.terminal_growth", "value": 0.035, "currency": "IDR", "tenor": "perpetuity",
         "basis": "nominal", "kind": "policy", "review_range": [0.02, 0.05],
         "benchmark": "rate_benchmarks.growth (IMF WEO long-run real growth and inflation)",
         "rationale": "Mature-phase nominal rupiah growth of roughly inflation plus one point: "
                      "below IMF 2031 nominal GDP growth (about 7.8%) and below the rupiah "
                      "risk-free rate. Each run checks it against reinvestment and returns."},
        {"id": "USD.risk_free", "value": None, "currency": "USD", "tenor": "10Y",
         "basis": "nominal", "kind": "observation",
         "benchmark": "app.rates UST 10Y close on or before the Report Date",
         "rationale": "US$ cash flows use the dated US Treasury yield; a missing yield is a "
                      "gap, never the rupiah rate."},
        {"id": "USD.country_risk_premium", "value": 0.025, "currency": "USD",
         "tenor": "long-run", "basis": "nominal", "kind": "policy",
         "review_range": [0.015, 0.035],
         "benchmark": "rate_benchmarks.crp (Damodaran, 2.46% Baa2 / 1.60% CDS, January 2026)",
         "rationale": "Indonesia country risk added to the US$ risk-free rate."},
        {"id": "USD.equity_risk_premium", "value": 0.04, "currency": "USD", "tenor": "long-run",
         "basis": "nominal", "kind": "policy", "review_range": [0.035, 0.06],
         "benchmark": "rate_benchmarks.erp", "rationale": "As for rupiah."},
        {"id": "USD.beta", "value": 1.1, "currency": "USD", "tenor": "n/a", "basis": "n/a",
         "kind": "policy", "review_range": [0.6, 1.6], "benchmark": "rate_benchmarks.beta",
         "rationale": "As for rupiah."},
        {"id": "USD.cost_of_debt_pretax", "value": None, "currency": "USD",
         "tenor": "long-run", "basis": "nominal", "kind": "derived",
         "benchmark": "UST 10Y + CRP; issuer effective cost when higher",
         "rationale": "Market-based US$ borrowing cost for an Indonesian issuer."},
        {"id": "USD.terminal_growth", "value": 0.03, "currency": "USD", "tenor": "perpetuity",
         "basis": "nominal", "kind": "policy", "review_range": [0.015, 0.04],
         "benchmark": "rate_benchmarks.growth (IMF WEO, US)",
         "rationale": "Below IMF 2031 US nominal GDP growth (about 4.0%) and the UST yield; "
                      "each run checks it against reinvestment and returns."},
    ],
    "screening": {
        "exit_ev_ebitda_multiple": 8.0,
        "exit_multiple_basis": "analyst screening parameter only; selected value requires a supported peer or issuer-history basis",
    },
    "production_validation": {
        "status": "approved",
        "approval_required": True,
        "approved_by": "Sektoral Team",
        "effective_from": "2026-09-26",
        "independent_reference_validation": "required per Model Profile",
        "terminal_economics_validation": "per_run",
        "terminal_economics_basis": "app.terminal_economics on the selected valuation of each run",
        "review_owner": "research_governance",
    },
    "terminal_restatement": "An FCFF terminal that fails the reinvestment or return-on-new-capital check is restated to NOPAT x (1 - g / RONIC) at the ceiling return (decided by the Sektoral Team on 2026-09-26); a rate or currency failure is labelled, not restated.",
    "unresolved": [
        "whether and when dated benchmark observations replace or only challenge policy inputs",
        "whether issuer-specific betas or costs of debt may deviate from the uniform policy, and who approves them",
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


def parameter(identifier: str) -> dict:
    """One parameter record (currency, tenor, basis, kind, rationale, range)."""
    for item in policy_snapshot()["parameters"]:
        if item["id"] == identifier:
            return item
    raise KeyError(identifier)


def deviation_violations(pack) -> list[str]:
    """Issuer-specific house-assumption deviations are not supported: fail closed."""
    if isinstance(pack, dict) and pack.get("house_deviations"):
        return ["issuer pack carries house-assumption deviations, which the house policy "
                "does not support; record the change in the house policy with its reason"]
    return []


def production_readiness_blockers(as_of: str | None = None, terminal: dict | None = None
                                  ) -> list[str]:
    """Missing controls that must be approved before any Production-Ready path.

    ``terminal`` is the run's ``app.terminal_economics`` record for the selected
    valuation; without a consistent (or not-applicable) record the terminal
    economics are unreconciled for that run.
    """
    validation = policy_snapshot().get("production_validation") or {}
    blockers = []
    blockers.extend(_effective_date_blockers(validation.get("effective_from"), as_of))
    if validation.get("status") != "approved" and not any(
            blocker.startswith("house discount-rate") for blocker in blockers):
        blockers.append("house discount-rate and terminal-growth assumptions are not approved")
    status = (terminal or {}).get("status")
    if status not in ("consistent", "not_applicable"):
        blockers.extend((terminal or {}).get("blockers") or
                        ["terminal growth is not reconciled to reinvestment and incremental "
                         "return on capital for this run"])
    if validation.get("independent_reference_validation") != "complete":
        blockers.append("independent reference validation is not recorded for each Model Profile")
    return blockers
