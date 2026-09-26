"""Interim period basis: cumulative year-to-date periods versus standalone quarters.

Issuers report cumulative interim periods (Q1/3M, 1H/6M, 9M, FY); a standalone
quarter other than Q1 is derived by subtracting the preceding cumulative period.
Growth, margins and normalization compare like with like only: the same months
covered, the same basis and the same accounting scope (consolidated or parent).
"""
from __future__ import annotations

import re

_CUMULATIVE = ((r"^(?:1H|H1|6M)\s*'?(\d{2,4})?$", 6), (r"^9M\s*'?(\d{2,4})?$", 9),
               (r"^(?:3M|1Q|Q1)\s*'?(\d{2,4})?$", 3), (r"^(?:FY|12M)\s*'?(\d{2,4})?$", 12))
_STANDALONE = re.compile(r"^(?:([2-4])Q|Q([2-4]))\s*'?(\d{2,4})?$")
_SECOND_HALF = re.compile(r"^(?:2H|H2)\s*'?(\d{2,4})?$")
_NOTE = re.compile(r"\s*\([^)]*\)\s*$")  # "Q2 2026 (derived)"
SCOPES = {"consolidated", "parent"}


def _year(text):
    if not text:
        return None
    return int(text) + 2000 if len(text) == 2 else int(text)


def parse(label) -> dict | None:
    """``{"months", "basis", "quarter", "fiscal_year"}`` for a period label, or None.

    ``basis`` is ``cumulative`` (year to date, Q1 included) or ``standalone``
    (a single later quarter, or the second half H2 = FY minus 1H, whose
    ``quarter`` is 4). A trailing note in parentheses is ignored.
    ``fiscal_year`` is None when the label omits it.
    """
    text = " ".join(_NOTE.sub("", str(label or "")).upper().split())
    for pattern, months in _CUMULATIVE:
        match = re.match(pattern, text)
        if match:
            return {"months": months, "basis": "cumulative", "quarter": months // 3,
                    "fiscal_year": _year(match.group(1))}
    match = _STANDALONE.match(text)
    if match:
        quarter = int(match.group(1) or match.group(2))
        return {"months": 3, "basis": "standalone", "quarter": quarter,
                "fiscal_year": _year(match.group(3))}
    match = _SECOND_HALF.match(text)
    if match:
        return {"months": 6, "basis": "standalone", "quarter": 4,
                "fiscal_year": _year(match.group(1))}
    return None


def cumulative_months(label) -> int | None:
    """Months covered by a cumulative period; None for a standalone quarter or unknown label."""
    parsed = parse(label)
    return parsed["months"] if parsed and parsed["basis"] == "cumulative" else None


def _figure(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: a figure needs value, currency, unit and scope")
    missing = [k for k in ("value", "currency", "unit", "scope") if value.get(k) in (None, "")]
    if missing:
        raise ValueError(f"{label}: missing {', '.join(missing)}")
    if value["scope"] not in SCOPES:
        raise ValueError(f"{label}: scope must be consolidated or parent")
    if isinstance(value["value"], bool) or not isinstance(value["value"], (int, float)):
        raise ValueError(f"{label}: value is not numeric")
    return value


def _same_basis(a, b, a_label, b_label):
    for key in ("currency", "unit", "scope"):
        if a[key] != b[key]:
            raise ValueError(f"{a_label} and {b_label} differ in {key}: {a[key]} vs {b[key]}")


def standalone_quarter(figures: dict, quarter: int, fiscal_year: int) -> dict:
    """Derive one standalone quarter from cumulative figures of the same fiscal year.

    ``figures`` maps cumulative labels (``Q1 2026``, ``1H26``, ``9M26``, ``FY2026``)
    to ``{"value", "currency", "unit", "scope"}``. Q1 is already standalone; Q2 is
    1H minus Q1, Q3 is 9M minus 1H and Q4 is FY minus 9M. Mismatched currency,
    unit or scope is an error, never a silent subtraction.
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1 to 4")
    by_months = {}
    for label, value in figures.items():
        parsed = parse(label)
        if not parsed or parsed["basis"] != "cumulative":
            continue
        if parsed["fiscal_year"] not in (None, fiscal_year):
            continue
        by_months[parsed["months"]] = (label, _figure(value, label))
    months = quarter * 3
    if months not in by_months:
        raise ValueError(f"cumulative {months}-month figure for FY{fiscal_year} is missing")
    current_label, current = by_months[months]
    if quarter == 1:
        return {"quarter": 1, "fiscal_year": fiscal_year, "value": current["value"],
                "currency": current["currency"], "unit": current["unit"],
                "scope": current["scope"], "derivation": f"{current_label} as reported"}
    if months - 3 not in by_months:
        raise ValueError(f"cumulative {months - 3}-month figure for FY{fiscal_year} is missing")
    prior_label, prior = by_months[months - 3]
    _same_basis(current, prior, current_label, prior_label)
    return {"quarter": quarter, "fiscal_year": fiscal_year,
            "value": current["value"] - prior["value"], "currency": current["currency"],
            "unit": current["unit"], "scope": current["scope"],
            "derivation": f"{current_label} minus {prior_label}"}


def second_half(figures: dict, fiscal_year: int) -> dict:
    """H2 as FY minus 1H of the same fiscal year, currency, unit and scope."""
    by_months = {}
    for label, value in figures.items():
        parsed = parse(label)
        if parsed and parsed["basis"] == "cumulative" and \
                parsed["fiscal_year"] in (None, fiscal_year):
            by_months[parsed["months"]] = (label, _figure(value, label))
    if 12 not in by_months or 6 not in by_months:
        raise ValueError(f"FY and 1H figures for FY{fiscal_year} are both required")
    (fy_label, fy), (h1_label, h1) = by_months[12], by_months[6]
    _same_basis(fy, h1, fy_label, h1_label)
    return {"half": 2, "fiscal_year": fiscal_year, "value": fy["value"] - h1["value"],
            "currency": fy["currency"], "unit": fy["unit"], "scope": fy["scope"],
            "derivation": f"{fy_label} minus {h1_label}"}


def comparable_growth(current_label, current, prior_label, prior) -> float | None:
    """Growth between two periods of the same length, basis and scope.

    Raises when the periods cannot be compared (a 6-month figure against a
    3-month one, a standalone quarter against a cumulative period, or a parent
    figure against a consolidated one). Returns None for a zero base.
    """
    a, b = parse(current_label), parse(prior_label)
    if not a or not b:
        raise ValueError(f"unrecognized period: {current_label if not a else prior_label}")
    if (a["months"], a["basis"]) != (b["months"], b["basis"]):
        raise ValueError(f"{current_label} and {prior_label} cover different periods")
    current, prior = _figure(current, current_label), _figure(prior, prior_label)
    _same_basis(current, prior, current_label, prior_label)
    if prior["value"] == 0:
        return None
    return (current["value"] - prior["value"]) / abs(prior["value"])
