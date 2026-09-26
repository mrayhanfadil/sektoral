"""Earnings quality record for one build: normalization bridge and share basis.

Collects the source pack's reviewed ledgers into one Audit Trace block. A
missing ledger is reported as ``not_assessed`` with its reason, never as an
empty pass, and a ledger error is listed rather than silently skipped. The
record never changes Release Status; the forecast and valuation read its
assessed results (``fy1`` normalized earnings, the Report Date share count).

Source pack keys (all optional):

- ``filing_sources``: ``{key: {title, url, page, period, published_at, currency,
  unit}}``; each becomes an ``official_filing`` Evidence Register row.
- ``normalization_ledger``: input to :func:`app.earnings_normalization.calculate`
  whose records cite ``source_refs`` (filing-source keys) in place of
  ``source_row_ids``; the keys are resolved to the register's row IDs here.
- ``share_ledger``: see :mod:`app.share_basis`.
"""
from __future__ import annotations

from . import earnings_normalization, evidence, period_basis, share_basis

SHARE_RECONCILIATION_TOLERANCE = 1e-6  # relative; share counts are exact integers


def _resolved(ledger, register):
    """The ledger with each record's ``source_refs`` mapped to register row IDs."""
    ids = evidence.row_ids_by_name(register)
    out = dict(ledger)
    for key in ("reported_results", "adjustments"):
        records = []
        for record in ledger.get(key) or []:
            if isinstance(record, dict) and "source_refs" in record:
                refs = record.get("source_refs") or []
                record = {**record, "source_row_ids": [ids.get(ref, f"unresolved:{ref}")
                                                       for ref in refs]}
            records.append(record)
        out[key] = records
    return out


def fy1(result, fiscal_year):
    """Latest cumulative normalized period of ``fiscal_year``: reported, normalized, effect."""
    best = None
    for row in (result or {}).get("results") or []:
        parsed = period_basis.parse(row.get("period"))
        if not parsed or parsed["basis"] != "cumulative" or parsed["fiscal_year"] != fiscal_year:
            continue
        if best is None or parsed["months"] > best[0]:
            best = (parsed["months"], row)
    if best is None:
        return None
    row = best[1]
    reported = float(row["reported_result"]["reported_attributable_earnings"])
    normalized = float(row["normalized_attributable_earnings"])
    return {"period": row["period"], "months": best[0], "currency": row.get("currency"),
            "unit": row.get("unit"), "reported": reported, "normalized": normalized,
            "effect": normalized - reported,
            "adjustments": [a for a in row.get("adjustments") or []
                            if a.get("included_in_normalization")]}


def _normalization(pack, register, as_of, fiscal_year):
    ledger = pack.get("normalization_ledger")
    if ledger is None:
        return {"status": "not_assessed",
                "reason": "Source pack has no reviewed earnings normalization ledger; "
                          "reported attributable earnings are used as reported."}
    if not isinstance(ledger, dict):
        return {"status": "incomplete", "blockers": ["normalization ledger is invalid"]}
    result = dict(earnings_normalization.calculate(_resolved(ledger, register), register, as_of))
    # The calculation reports itself as a Draft; keep that label separately so it
    # cannot overwrite whether the ledger was assessed.
    result["calculation_status"] = result.pop("status", None)
    if ledger.get("assessment_note"):
        result["assessment_note"] = ledger["assessment_note"]
    complete = result["completeness"] == "complete"
    return {**result, "status": "assessed" if complete else "incomplete",
            "fy1": fy1(result, fiscal_year) if complete else None}


def _share_basis(pack, as_of, model_shares, price, fiscal_year):
    record = share_basis.assess(pack, as_of, price=price, fiscal_year=fiscal_year)
    if record["status"] != "assessed":
        return record
    current = record["shares_on_report_date"]
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


def assess(pack, evidence_register, as_of, model_shares=None, price=None,
           fiscal_year=None) -> dict:
    """Normalization bridge and share basis for one issuer at one Report Date."""
    pack = pack if isinstance(pack, dict) else {}
    normalization = _normalization(pack, evidence_register, as_of, fiscal_year)
    shares = _share_basis(pack, as_of, model_shares, price, fiscal_year)
    statuses = {normalization["status"], shares["status"]}
    overall = ("assessed" if statuses == {"assessed"} else
               "incomplete" if "incomplete" in statuses else "not_assessed")
    return {"status": overall, "as_of": as_of, "fiscal_year": fiscal_year,
            "normalization": normalization, "share_basis": shares}
