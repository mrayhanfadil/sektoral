"""Earnings quality record for one build: normalization bridge and share basis.

Collects the source pack's optional reviewed ledgers into one Audit Trace
block. It never changes the forecast or Release Status: a missing ledger is
reported as ``not_assessed`` with its reason, never as an empty pass, and a
ledger error is listed rather than silently skipped.

Source pack keys (both optional):

- ``normalization_ledger``: input to :func:`app.earnings_normalization.calculate`.
- ``corporate_actions``: records for :mod:`app.corporate_actions`, applied to the
  pack's ``balance_sheet.shares_outstanding`` at ``balance_sheet.period_end``.
"""
from __future__ import annotations

from . import corporate_actions, earnings_normalization

SHARE_RECONCILIATION_TOLERANCE = 1e-6  # relative; share counts are exact integers


def _normalization(pack, register, as_of):
    ledger = pack.get("normalization_ledger")
    if ledger is None:
        return {"status": "not_assessed",
                "reason": "Source pack has no reviewed earnings normalization ledger; "
                          "reported attributable earnings are used as reported."}
    result = dict(earnings_normalization.calculate(ledger, register, as_of))
    # The calculation reports itself as a Draft; keep that label separately so it
    # cannot overwrite whether the ledger was assessed.
    result["calculation_status"] = result.pop("status", None)
    return {**result,
            "status": "assessed" if result["completeness"] == "complete" else "incomplete"}


def _share_basis(pack, as_of, model_shares):
    actions = pack.get("corporate_actions")
    balance = pack.get("balance_sheet") or {}
    base, base_date = balance.get("shares_outstanding"), balance.get("period_end")
    if actions is None:
        return {"status": "not_assessed",
                "reason": "Source pack has no corporate-action ledger; the share count is the "
                          "latest balance-sheet figure without later actions."}
    errors = corporate_actions.validate(actions)
    if errors:
        return {"status": "incomplete", "blockers": errors}
    if not base or not base_date:
        return {"status": "incomplete",
                "blockers": ["balance_sheet.shares_outstanding and period_end are required"]}
    current = corporate_actions.shares_on(base, base_date, actions, as_of, as_of)
    record = {"status": "assessed", "base_shares": base, "base_date": base_date,
              "shares_on_report_date": current,
              "conditional_scenarios": corporate_actions.conditional_scenarios(actions, as_of),
              "blockers": []}
    if isinstance(model_shares, (int, float)) and model_shares > 0:
        gap = abs(model_shares - current) / current
        record["model_shares"] = model_shares
        record["reconciles"] = gap <= SHARE_RECONCILIATION_TOLERANCE
        if not record["reconciles"]:
            record["status"] = "incomplete"
            record["blockers"].append(
                f"model share count {model_shares:,.0f} does not match {current:,.0f} "
                f"after corporate actions to {as_of}")
    return record


def assess(pack, evidence_register, as_of, model_shares=None) -> dict:
    """Normalization bridge and share basis for one issuer at one Report Date."""
    pack = pack if isinstance(pack, dict) else {}
    normalization = _normalization(pack, evidence_register, as_of)
    share_basis = _share_basis(pack, as_of, model_shares)
    statuses = {normalization["status"], share_basis["status"]}
    overall = ("assessed" if statuses == {"assessed"} else
               "incomplete" if "incomplete" in statuses else "not_assessed")
    return {"status": overall, "as_of": as_of, "calculation_only": True,
            "normalization": normalization, "share_basis": share_basis}
