"""Point-in-time, source-linked earnings normalization ledger.

This module is an auditable calculation only. It does not alter forecasts or
Release Status. Monetary amounts are signed in the stated currency and unit.
For a one-off item, ``pretax_amount`` is the signed change to normalized
pretax earnings (an expense add-back is positive); ``tax_effect`` is the
signed change to tax expense; and ``minority_interest_effect`` is the signed
change to profit attributable to non-controlling interests. The parent bridge
is therefore ``pretax_amount - tax_effect - minority_interest_effect``.

The input is append-only by convention: corrected reports and revised
adjustments are new vintages, never edits to prior vintages. At a report date,
the latest eligible vintage for each period/item is selected and the prior
vintages remain visible in the returned audit history.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


_SCALE = {
    "unit": Decimal("1"), "units": Decimal("1"), "one": Decimal("1"),
    "ones": Decimal("1"), "thousand": Decimal("1000"),
    "thousands": Decimal("1000"), "million": Decimal("1000000"),
    "millions": Decimal("1000000"), "billion": Decimal("1000000000"),
    "billions": Decimal("1000000000"),
}


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _unit_scale(value: Any) -> Decimal | None:
    """Accept explicit base/scale names, optionally prefixed by currency."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.strip().lower().replace("_", " ").split())
    pieces = normalized.split()
    if len(pieces) == 1:
        return _SCALE.get(pieces[0])
    # Allow the unambiguous forms "IDR million" and "million IDR".
    if len(pieces) == 2:
        return _SCALE.get(pieces[0]) or _SCALE.get(pieces[1])
    return None


def _iso_day(value: Any, label: str, errors: list[str]) -> date | None:
    parsed = _day(value)
    if parsed is None:
        errors.append(f"{label} is missing or invalid")
    return parsed


def _source_rows(ids: Any, rows_by_id: dict[str, dict], *, label: str,
                 period: str, currency: str | None, unit_scale: Decimal,
                 cutoff: date, errors: list[str], shares: bool = False) -> None:
    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) or not item for item in ids):
        errors.append(f"{label} must cite one or more Evidence Register row IDs")
        return
    if len(set(ids)) != len(ids):
        errors.append(f"{label} contains duplicate Evidence Register row IDs")
        return
    for row_id in ids:
        row = rows_by_id.get(row_id)
        if row is None:
            errors.append(f"{label} cites unknown Evidence Register row ID {row_id!r}")
            continue
        if (row.get("period") or row.get("effective_years") or row.get("fiscal_years")) != period:
            errors.append(f"{label} source {row_id!r} does not match period {period!r}")
        row_currency = str(row.get("currency") or "").upper().strip()
        if currency is not None and row_currency != currency:
            errors.append(f"{label} source {row_id!r} currency does not reconcile")
        if shares:
            row_scale = _unit_scale(row.get("shares_unit") or row.get("unit"))
        else:
            row_scale = _unit_scale(row.get("unit"))
        if row_scale is None or row_scale != unit_scale:
            errors.append(f"{label} source {row_id!r} unit does not reconcile")
        published = _day(row.get("published_at"))
        available = _day(row.get("available_at") or row.get("published_at"))
        if published is None or available is None:
            errors.append(f"{label} source {row_id!r} has no valid publication/availability date")
        elif published > cutoff or available > cutoff:
            errors.append(f"{label} source {row_id!r} was not available by the report date")
        elif available < published:
            errors.append(f"{label} source {row_id!r} is available before publication")


def calculate(ledger: Any, evidence_register: Any, as_of: str) -> dict[str, Any]:
    """Calculate normalized attributable earnings without changing release state.

    Required ledger keys are ``reported_results`` (append-only report
    vintages), ``adjustments`` (append-only item vintages), and
    ``adjustments_assessed`` (affirmative review that the adjustment list is
    complete, including when no adjustments were found). Both record types
    require ``vintage_id``, ``period``, ``published_at``, ``available_at``,
    ``currency``, ``unit`` and ``source_row_ids``. Reported results also need
    ``reported_attributable_earnings``. Adjustment records additionally need
    ``adjustment_id``, ``classification`` (``one_off`` or ``recurring``),
    ``pretax_amount``, ``tax_effect``, ``minority_interest_effect`` and a
    reviewed ``normalized_attributable_effect``. That after-tax, after-minority
    amount must equal the independently calculated bridge effect (zero for a
    recurring item).

    Shares are optional. When supplied, ``shares_unit`` and
    ``shares_source_row_ids`` are required and EPS is returned in currency per
    share. Every error fails closed: results are empty and the calculation is
    explicitly marked Draft/incomplete.
    """
    errors: list[str] = []
    cutoff = _iso_day(as_of, "report date", errors)
    if not isinstance(ledger, dict):
        errors.append("normalization ledger is missing or invalid")
        ledger = {}
    if not isinstance(evidence_register, dict) or not isinstance(evidence_register.get("rows"), list):
        errors.append("Evidence Register is missing or invalid")
        evidence_register = {}
        evidence_rows: list[dict] = []
    else:
        evidence_rows = [row for row in evidence_register["rows"] if isinstance(row, dict)]

    rows_by_id: dict[str, dict] = {}
    for row in evidence_rows:
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or not row_id:
            errors.append("Evidence Register contains a row without a canonical row_id")
            continue
        if row_id in rows_by_id:
            errors.append(f"Evidence Register row_id {row_id!r} is not unique")
        rows_by_id[row_id] = row

    reports = ledger.get("reported_results")
    adjustments = ledger.get("adjustments")
    if not isinstance(reports, list) or not reports:
        errors.append("reported result vintages are missing")
        reports = []
    if not isinstance(adjustments, list):
        errors.append("adjustment vintages are missing or invalid")
        adjustments = []
    if ledger.get("adjustments_assessed") is not True:
        errors.append("adjustments have not been affirmatively assessed as complete")

    eligible_reports: list[dict] = []
    eligible_adjustments: list[dict] = []
    future: list[dict] = []
    vintage_errors: list[str] = []

    def prepare(records: list, kind: str, output: list) -> None:
        seen_ids: set[str] = set()
        for index, raw in enumerate(records):
            label = f"{kind}[{index}]"
            if not isinstance(raw, dict):
                vintage_errors.append(f"{label} is invalid")
                continue
            vintage_id = raw.get("vintage_id")
            if not isinstance(vintage_id, str) or not vintage_id.strip():
                vintage_errors.append(f"{label} has no vintage_id")
            elif vintage_id in seen_ids:
                vintage_errors.append(f"duplicate {kind} vintage_id {vintage_id!r}")
            else:
                seen_ids.add(vintage_id)
            published = _day(raw.get("published_at"))
            available = _day(raw.get("available_at") or raw.get("published_at"))
            if published is None or available is None:
                vintage_errors.append(f"{label} has invalid publication/availability dates")
                continue
            if available < published:
                vintage_errors.append(f"{label} is available before publication")
                continue
            if cutoff is None:
                continue
            if published > cutoff or available > cutoff:
                future.append({"kind": kind, "vintage_id": vintage_id,
                               "period": raw.get("period"), "published_at": raw.get("published_at"),
                               "available_at": raw.get("available_at") or raw.get("published_at"),
                               "selection": "excluded_future"})
                continue
            output.append(dict(raw))

    prepare(reports, "reported_result", eligible_reports)
    prepare(adjustments, "adjustment", eligible_adjustments)
    errors.extend(vintage_errors)

    def validate_record(record: dict, label: str, *, is_adjustment: bool) -> tuple[Decimal | None, Decimal | None]:
        period = record.get("period")
        if not isinstance(period, str) or not period.strip():
            errors.append(f"{label} period is missing")
            period = ""
        currency = str(record.get("currency") or "").upper().strip()
        if not currency:
            errors.append(f"{label} currency is missing")
        scale = _unit_scale(record.get("unit"))
        if scale is None:
            errors.append(f"{label} unit is missing or unsupported")
        if cutoff is not None and period and not is_adjustment:
            _source_rows(record.get("source_row_ids"), rows_by_id, label=label,
                         period=period, currency=currency or None,
                         unit_scale=scale or Decimal("-1"), cutoff=cutoff, errors=errors)
        if is_adjustment:
            for field in ("adjustment_id",):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    errors.append(f"{label} {field} is missing")
            if record.get("classification") not in {"one_off", "recurring"}:
                errors.append(f"{label} classification must be one_off or recurring")
            pretax = _number(record.get("pretax_amount"))
            tax = _number(record.get("tax_effect"))
            minority = _number(record.get("minority_interest_effect"))
            stated_effect = _number(record.get("normalized_attributable_effect"))
            for field, value in (("pretax_amount", pretax), ("tax_effect", tax),
                                 ("minority_interest_effect", minority),
                                 ("normalized_attributable_effect", stated_effect)):
                if value is None:
                    errors.append(f"{label} {field} is missing or non-finite")
            if pretax is not None and tax is not None and minority is not None and stated_effect is not None:
                calculated_effect = (pretax - tax - minority
                                     if record.get("classification") == "one_off" else Decimal(0))
                if stated_effect != calculated_effect:
                    errors.append(f"{label} normalized_attributable_effect does not reconcile")
            if scale is not None:
                _source_rows(record.get("source_row_ids"), rows_by_id, label=label,
                             period=period, currency=currency or None,
                             unit_scale=scale, cutoff=cutoff, errors=errors)
            return pretax, ((tax or Decimal(0)) + (minority or Decimal(0)))

        reported = _number(record.get("reported_attributable_earnings"))
        if reported is None:
            errors.append(f"{label} reported_attributable_earnings is missing or non-finite")
        shares = None
        if record.get("shares_outstanding") is not None:
            shares = _number(record.get("shares_outstanding"))
            if shares is None or shares <= 0:
                errors.append(f"{label} shares_outstanding must be a positive finite number")
            shares_scale = _unit_scale(record.get("shares_unit"))
            if shares_scale is None:
                errors.append(f"{label} shares_unit is missing or unsupported")
            elif cutoff is not None and period:
                _source_rows(record.get("shares_source_row_ids"), rows_by_id, label=f"{label} shares",
                             period=period, currency=None, unit_scale=shares_scale,
                             cutoff=cutoff, errors=errors, shares=True)
        return reported, shares

    report_values: dict[str, list[tuple[dict, Decimal | None, Decimal | None]]] = {}
    for index, record in enumerate(eligible_reports):
        label = f"reported_result[{record.get('vintage_id') or index}]"
        amount, shares = validate_record(record, label, is_adjustment=False)
        report_values.setdefault(str(record.get("period") or ""), []).append((record, amount, shares))

    adjustment_values: dict[tuple[str, str], list[tuple[dict, Decimal | None, Decimal | None]]] = {}
    for index, record in enumerate(eligible_adjustments):
        label = f"adjustment[{record.get('vintage_id') or index}]"
        pretax, tax_plus_minority = validate_record(record, label, is_adjustment=True)
        key = (str(record.get("period") or ""), str(record.get("adjustment_id") or ""))
        # Keep the separately named effects for output and arithmetic.
        tax = _number(record.get("tax_effect"))
        minority = _number(record.get("minority_interest_effect"))
        delta = (pretax - tax - minority) if pretax is not None and tax is not None and minority is not None else None
        adjustment_values.setdefault(key, []).append((record, delta, tax_plus_minority))

    def choose(vintages: list[tuple[dict, Decimal | None, Decimal | None]], label: str):
        ordered = sorted(vintages, key=lambda item: str(item[0].get("available_at") or item[0].get("published_at")))
        if not ordered:
            return None
        latest_date = ordered[-1][0].get("available_at") or ordered[-1][0].get("published_at")
        tied = [item for item in ordered if (item[0].get("available_at") or item[0].get("published_at")) == latest_date]
        if len(tied) > 1:
            errors.append(f"{label} has multiple vintages available on {latest_date}")
            return None
        return ordered[-1]

    selected_reports: dict[str, tuple[dict, Decimal | None, Decimal | None]] = {}
    for period, vintages in report_values.items():
        selected = choose(vintages, f"reported result {period!r}")
        if selected:
            selected_reports[period] = selected

    selected_adjustments: dict[tuple[str, str], tuple[dict, Decimal | None, Decimal | None]] = {}
    for key, vintages in adjustment_values.items():
        selected = choose(vintages, f"adjustment {key[1]!r} for {key[0]!r}")
        if selected:
            selected_adjustments[key] = selected

    # Enforce exact currency and monetary scale equality across every selected
    # period bridge before doing arithmetic.
    for period, (report, _, _) in selected_reports.items():
        for (adjustment_period, _), (adjustment, _, _) in selected_adjustments.items():
            if period != adjustment_period:
                continue
            if str(report.get("currency") or "").upper().strip() != str(adjustment.get("currency") or "").upper().strip():
                errors.append(f"period {period!r} currency does not reconcile across earnings bridge")
            if _unit_scale(report.get("unit")) != _unit_scale(adjustment.get("unit")):
                errors.append(f"period {period!r} monetary units do not reconcile across earnings bridge")

    if not selected_reports:
        errors.append("no reported result vintage is available by the report date")
    for period, _ in selected_adjustments:
        if period not in selected_reports:
            errors.append(f"adjustment period {period!r} has no eligible reported result")

    history: list[dict] = []
    for kind, records, selected_ids in (
        ("reported_result", eligible_reports,
         {item[0].get("vintage_id") for item in selected_reports.values()}),
        ("adjustment", eligible_adjustments,
         {item[0].get("vintage_id") for item in selected_adjustments.values()}),
    ):
        history.extend({"kind": kind, "vintage_id": record.get("vintage_id"),
                        "period": record.get("period"),
                        "available_at": record.get("available_at") or record.get("published_at"),
                        "source_row_ids": list(record.get("source_row_ids") or []),
                        "selection": "selected" if record.get("vintage_id") in selected_ids else "superseded"}
                       for record in records)
    history.extend(future)

    results = []
    if not errors and cutoff is not None:
        for period in sorted(selected_reports):
            report, reported, shares = selected_reports[period]
            assert reported is not None
            bridge_rows = []
            normalized = reported
            for (adjustment_period, adjustment_id), (record, delta, _) in sorted(selected_adjustments.items()):
                if adjustment_period != period:
                    continue
                included = record.get("classification") == "one_off"
                applied = delta if included else Decimal(0)
                assert applied is not None
                normalized += applied
                bridge_rows.append({
                    "adjustment_id": adjustment_id,
                    "vintage_id": record.get("vintage_id"),
                    "classification": record.get("classification"),
                    "description": record.get("description"),
                    "published_at": record.get("published_at"),
                    "available_at": record.get("available_at") or record.get("published_at"),
                    "currency": record.get("currency"), "unit": record.get("unit"),
                    "pretax_amount": _decimal_text(_number(record.get("pretax_amount"))),
                    "tax_effect": _decimal_text(_number(record.get("tax_effect"))),
                    "minority_interest_effect": _decimal_text(_number(record.get("minority_interest_effect"))),
                    "normalized_attributable_effect": _decimal_text(applied),
                    "included_in_normalization": included,
                    "source_row_ids": list(record.get("source_row_ids") or []),
                })
            scale = _unit_scale(report.get("unit"))
            eps = None
            if shares is not None:
                shares_scale = _unit_scale(report.get("shares_unit"))
                assert scale is not None and shares_scale is not None
                eps = normalized * scale / (shares * shares_scale)
            results.append({
                "period": period,
                "reported_result": {
                    "vintage_id": report.get("vintage_id"),
                    "published_at": report.get("published_at"),
                    "available_at": report.get("available_at") or report.get("published_at"),
                    "reported_attributable_earnings": _decimal_text(reported),
                    "currency": report.get("currency"), "unit": report.get("unit"),
                    "source_row_ids": list(report.get("source_row_ids") or []),
                },
                "adjustments": bridge_rows,
                "normalized_attributable_earnings": _decimal_text(normalized),
                "currency": report.get("currency"), "unit": report.get("unit"),
                "shares_outstanding": _decimal_text(shares) if shares is not None else None,
                "shares_unit": report.get("shares_unit") if shares is not None else None,
                "eps": _decimal_text(eps) if eps is not None else None,
            })

    return {
        "status": "Draft",
        "completeness": "incomplete" if errors else "complete",
        "as_of": as_of,
        "calculation_only": True,
        "results": results,
        "vintage_history": sorted(history, key=lambda item: (item.get("period") or "", item.get("kind") or "", item.get("available_at") or "", item.get("vintage_id") or "")),
        "blockers": list(dict.fromkeys(errors)),
    }


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rendered = format(value.normalize(), "f")
    return "0" if rendered in {"-0", ""} else rendered
