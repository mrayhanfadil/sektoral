"""Small, auditable sum-of-the-parts equity bridge.

All valuation amounts are raw IDR (not IDR millions/billions) and shares are
individual shares. Asset NAV is entered on a 100% basis; ownership is applied
here. ``discount_pct`` is an optional explicit haircut to bridged equity value.
If any required input is missing or invalid, the result is incomplete and has
no target price.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from math import isfinite
from numbers import Real
from typing import Any


_ASSET_TEXT_FIELDS = ("name", "stage", "method", "source", "provenance")


def _number(value: Any) -> float | None:
    """Return a finite numeric value, without treating strings/bools as numbers."""
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        return None
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_source_date(value: Any) -> bool:
    if not _non_empty_text(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _valid_page(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return _non_empty_text(value)


def calculate_sotp(
    assets: Sequence[Mapping[str, Any]] | None = None,
    *,
    cash_idr: Any = None,
    debt_idr: Any = None,
    minority_interest_idr: Any = None,
    corporate_overhead_idr: Any = None,
    shares: Any = None,
    discount_pct: Any = None,
) -> dict[str, Any]:
    """Calculate an attributable SOTP target price or return explicit gaps.

    Each asset mapping must contain:

    - ``name``: asset identifier/label
    - ``nav_idr``: 100%-basis NAV in raw IDR
    - ``ownership_pct``: attributable ownership from 0 through 100
    - ``stage`` and ``method``: asset stage and valuation method
    - ``source`` and ``provenance``: source reference and derivation note
    - ``source_date`` and ``page``: evidence date and page/table reference

    Required bridge inputs are ``cash_idr``, ``debt_idr``,
    ``minority_interest_idr``, ``corporate_overhead_idr`` (present value), and
    positive ``shares``. All four bridge amounts are raw IDR. ``discount_pct``
    is optional; when supplied it must be between 0 and 100 and is applied to
    the bridged equity value. No rounding is performed.

    The return has ``status`` equal to ``"complete"`` or ``"incomplete"``.
    Incomplete results include path-specific ``gaps`` and always set
    ``target_price_idr`` to ``None``.
    """
    gaps: list[dict[str, str]] = []

    def gap(path: str, reason: str) -> None:
        gaps.append({"path": path, "reason": reason})

    normalized_assets: list[dict[str, Any]] = []
    if assets is None:
        gap("assets", "required; provide at least one asset")
    elif isinstance(assets, (str, bytes)) or not isinstance(assets, Sequence):
        gap("assets", "must be a sequence of asset mappings")
    elif not assets:
        gap("assets", "must contain at least one asset")
    else:
        for index, asset in enumerate(assets):
            prefix = f"assets[{index}]"
            if not isinstance(asset, Mapping):
                gap(prefix, "must be an asset mapping")
                continue

            row: dict[str, Any] = {}
            row_valid = True
            for field in _ASSET_TEXT_FIELDS:
                value = asset.get(field)
                if not _non_empty_text(value):
                    gap(f"{prefix}.{field}", "required non-empty text")
                    row_valid = False
                else:
                    row[field] = value.strip()

            source_date = asset.get("source_date")
            if not _valid_source_date(source_date):
                gap(f"{prefix}.source_date", "required source date in YYYY-MM-DD format")
                row_valid = False
            else:
                row["source_date"] = source_date

            page = asset.get("page")
            if not _valid_page(page):
                gap(f"{prefix}.page", "required positive page number or label")
                row_valid = False
            else:
                row["page"] = page

            nav = _number(asset.get("nav_idr"))
            if nav is None:
                gap(f"{prefix}.nav_idr", "required finite numeric value in raw IDR")
                row_valid = False
            else:
                row["nav_idr"] = nav

            ownership = _number(asset.get("ownership_pct"))
            if ownership is None:
                gap(f"{prefix}.ownership_pct", "required finite percentage from 0 to 100")
                row_valid = False
            elif not 0 <= ownership <= 100:
                gap(f"{prefix}.ownership_pct", "must be between 0 and 100")
                row_valid = False
            else:
                row["ownership_pct"] = ownership

            if row_valid:
                row["attributable_nav_idr"] = nav * ownership / 100
                normalized_assets.append(row)

    bridge_values = {
        "cash_idr": cash_idr,
        "debt_idr": debt_idr,
        "minority_interest_idr": minority_interest_idr,
        "corporate_overhead_idr": corporate_overhead_idr,
        "shares": shares,
    }
    bridge: dict[str, float] = {}
    for field, raw_value in bridge_values.items():
        value = _number(raw_value)
        if value is None:
            gap(field, "required finite numeric value")
            continue
        if field == "shares":
            if value <= 0:
                gap(field, "must be greater than zero")
                continue
        elif value < 0:
            gap(field, "must be zero or greater; amounts are raw IDR")
            continue
        bridge[field] = value

    discount = None
    if discount_pct is not None:
        discount = _number(discount_pct)
        if discount is None:
            gap("discount_pct", "must be a finite percentage from 0 to 100")
        elif not 0 <= discount <= 100:
            gap("discount_pct", "must be between 0 and 100")

    if gaps:
        return {
            "status": "incomplete",
            "currency": "IDR",
            "amount_unit": "raw IDR",
            "shares_unit": "shares",
            "gaps": gaps,
            "assets": [],
            "cash_idr": bridge.get("cash_idr"),
            "debt_idr": bridge.get("debt_idr"),
            "minority_interest_idr": bridge.get("minority_interest_idr"),
            "corporate_overhead_idr": bridge.get("corporate_overhead_idr"),
            "shares": bridge.get("shares"),
            "attributable_asset_nav_idr": None,
            "pre_discount_equity_value_idr": None,
            "equity_value_idr": None,
            "target_price_idr": None,
            "discount_pct": discount,
        }

    attributable_nav = sum(row["attributable_nav_idr"] for row in normalized_assets)
    pre_discount_equity = (
        attributable_nav
        + bridge["cash_idr"]
        - bridge["debt_idr"]
        - bridge["minority_interest_idr"]
        - bridge["corporate_overhead_idr"]
    )
    equity_value = pre_discount_equity * (1 - (discount or 0) / 100)

    return {
        "status": "complete",
        "currency": "IDR",
        "amount_unit": "raw IDR",
        "shares_unit": "shares",
        "gaps": [],
        "assets": normalized_assets,
        "cash_idr": bridge["cash_idr"],
        "debt_idr": bridge["debt_idr"],
        "minority_interest_idr": bridge["minority_interest_idr"],
        "corporate_overhead_idr": bridge["corporate_overhead_idr"],
        "shares": bridge["shares"],
        "attributable_asset_nav_idr": attributable_nav,
        "pre_discount_equity_value_idr": pre_discount_equity,
        "equity_value_idr": equity_value,
        "target_price_idr": equity_value / bridge["shares"],
        "discount_pct": discount,
    }
