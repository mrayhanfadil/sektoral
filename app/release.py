"""Profile-aware production release gate.

The mining contract is intentionally explicit so callers cannot interpret an
absent value as zero:

Interim actuals may use ``sectors_cache`` provenance or a dated official issuer
release. That evidence alone does not approve a production forecast or valuation.

* ``intake["latest_interim_actuals"]`` contains period, actual status, source,
  publication date, page, and metrics for revenue, EBITDA, net profit and capex.
  Each metric has a numeric ``value`` and non-empty ``unit``.
* ``forecast["operating_bridge"]`` maps each stage in
  :data:`OPERATING_BRIDGE_STAGES` to a source-backed evidence row with
  claim/value/unit/period/status/source/source_date/page. A stage irrelevant
  to the issuer may be explicitly marked ``not_applicable`` with an explanation
  in its value and source.
* ``sotp_result`` is the result from ``app.sotp.calculate_sotp``.

Only the explicit ``finite_life_mining`` profile applies the physical-chain
checks. Other profiles have their own interim and forecast requirements.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from math import isfinite
from numbers import Real
import re
from urllib.parse import urlsplit


OPERATING_BRIDGE_STAGES = (
    "ore_access",
    "throughput",
    "grade",
    "recovery",
    "payable_production",
    "downstream_capacity",
    "downstream_utilization",
    "product_sales_mix",
    "realized_price_netback",
    "revenue",
    "unit_cost_royalty",
    "ebitda",
    "capex",
    "nwc",
    "tax",
    "debt",
    "fcff",
)

_ACTUAL_STATUSES = {"actual", "reported actual", "actual reported"}
_ALLOWED_SOURCE_TYPES = {"sectors_cache", "official_issuer"}
_INTERIM_PERIOD = re.compile(
    r"^(?:1Q|2Q|3Q|1H|2H|9M)[ -]?(?:\d{2}|\d{4})$", re.IGNORECASE
)


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


_FINANCIAL_METRICS = ("revenue", "ebitda", "net_profit", "capex")
_REQUIRED_DRIVER_SERIES = ("revenue", "ebitda", "net_profit", "capex")
_EVIDENCE_FIELDS = (
    "claim", "value", "unit", "period", "status", "source",
    "source_date", "page",
)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _cache_provenance(value: object) -> bool:
    if not _text(value):
        return False
    normalized = value.lower()
    return ("sectors_cache" in normalized or "sectors cache" in normalized) and not re.search(
        r"https?://", value, flags=re.IGNORECASE)


def _verified_source_reference(value: object) -> bool:
    if _cache_provenance(value):
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
        return (parsed.scheme.lower() == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def _number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        return False
    try:
        return isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _value(value: object) -> bool:
    return _number(value) or _text(value)


def _source_date(value: object) -> bool:
    if not _text(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _page(value: object) -> bool:
    # Null explicitly represents a source with no page numbering, such as API.
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return _text(value)


def _evidence_row(row: object) -> list[str]:
    """Return missing/invalid evidence fields for a bridge stage row."""
    errors = []
    if not isinstance(row, Mapping):
        return ["must be a source-backed evidence object"]

    for field in _EVIDENCE_FIELDS:
        if field not in row:
            errors.append(f"missing {field}")

    for field in ("claim", "unit", "period", "status", "source"):
        if field in row and not _text(row[field]):
            errors.append(f"{field} must be non-empty text")
    if "value" in row and not _value(row["value"]):
        errors.append("value must be a finite number or non-empty text")
    if "source_date" in row and not _source_date(row["source_date"]):
        errors.append("source_date must be YYYY-MM-DD")
    if "page" in row and not _page(row["page"]):
        errors.append("page must be a positive page label/number or null")
    if str(row.get("status", "")).strip().lower().replace("-", "_") == "not_applicable":
        if not _text(row.get("value")):
            errors.append("not_applicable requires an explanatory text value")
    return errors


def _check_latest_interim_actuals(intake: object) -> list[str]:
    blockers = []
    if not isinstance(intake, Mapping):
        return ["latest interim actuals: intake must be an object"]
    actuals = intake.get("latest_interim_actuals")
    if not isinstance(actuals, Mapping):
        return ["latest interim actuals missing: intake.latest_interim_actuals"]

    period = actuals.get("period")
    if not _text(period) or not _INTERIM_PERIOD.fullmatch(period.strip()):
        blockers.append("latest interim actuals require an interim period (for example 1Q26 or 1H26)")
    status = str(actuals.get("status", "")).strip().lower().replace("_", " ")
    if status not in _ACTUAL_STATUSES:
        blockers.append("latest interim actuals must be explicitly labeled actual")
    source_type = str(actuals.get("source_type", "")).strip().lower()
    if source_type not in _ALLOWED_SOURCE_TYPES:
        blockers.append("latest interim actuals require a verified source type")
    if not _text(actuals.get("source")):
        blockers.append("latest interim actuals require a source")
    elif source_type == "sectors_cache" and not _cache_provenance(actuals.get("source")):
        blockers.append("latest interim actuals source must identify sectors_cache provenance")
    elif source_type == "official_issuer" and not str(actuals.get("source")).startswith("https://"):
        blockers.append("latest interim official source must use HTTPS")
    if not _source_date(actuals.get("source_date")):
        blockers.append("latest interim actuals require source_date in YYYY-MM-DD format")
    if "page" not in actuals or not _page(actuals.get("page")):
        blockers.append("latest interim actuals require a valid page label/number (or null for non-paginated sources)")
    as_of = intake.get("as_of") or intake.get("price_date")
    if not _source_date(as_of):
        blockers.append("report as-of date is required to check interim source freshness")
    elif _source_date(actuals.get("source_date")) and actuals["source_date"] > as_of:
        blockers.append("latest interim actuals were published after the report as-of date")
    if actuals.get("is_latest") is not True:
        blockers.append("interim actuals must be identified as the latest available release")

    metrics = actuals.get("metrics")
    if not isinstance(metrics, Mapping):
        blockers.append("latest interim actuals require metrics for revenue, EBITDA, net profit and capex")
    else:
        for metric in _FINANCIAL_METRICS:
            item = metrics.get(metric)
            if not isinstance(item, Mapping):
                blockers.append(f"latest interim actuals missing metric: {metric}")
                continue
            if not _number(item.get("value")):
                blockers.append(f"latest interim actuals {metric}.value must be a finite reported number")
            if not _text(item.get("unit")):
                blockers.append(f"latest interim actuals {metric}.unit is required")
    if actuals.get("is_latest") is False:
        blockers.append("interim actuals are not identified as the latest available release")
    return blockers


def _check_operating_bridge(forecast: object) -> list[str]:
    if not isinstance(forecast, Mapping):
        return ["operating bridge missing: forecast must be an object"]
    bridge = forecast.get("operating_bridge")
    if not isinstance(bridge, Mapping):
        return ["operating bridge missing: forecast.operating_bridge"]

    blockers = []
    for stage in OPERATING_BRIDGE_STAGES:
        if stage not in bridge:
            blockers.append(f"operating bridge missing stage: {stage}")
            continue
        errors = _evidence_row(bridge[stage])
        blockers.extend(f"operating bridge {stage}: {error}" for error in errors)
        if isinstance(bridge[stage], Mapping) and _text(bridge[stage].get("source")) and \
                not _cache_provenance(bridge[stage].get("source")):
            blockers.append(f"operating bridge {stage}: source must be sectors_cache-only")
    return blockers


def _check_driver_forecast(forecast: object, intake: object) -> list[str]:
    if not isinstance(forecast, Mapping):
        return ["sourced operating and cash-flow forecast is incomplete"]
    blockers = []
    if forecast.get("forecast_basis") != "driver_forecast":
        blockers.append("sourced operating and cash-flow forecast is incomplete")
    if forecast.get("production_ready") is not True:
        blockers.append("forecast is not verified as production-ready")

    g2 = forecast.get("g2")
    if isinstance(g2, Mapping):
        if g2.get("G2.9_driver_forecast") == "gagal" or g2.get("G2.9_operating_bridge") == "gagal":
            blockers.append("forecast gate failed: G2.9 driver forecast is not reconciled")
        for k, v in g2.items():
            if k != "catatan" and (v == "gagal" or (isinstance(v, tuple) and v[0].startswith("gagal"))):
                if "G2.9" not in k:
                    blockers.append(f"forecast gate check failed: {k}")

    driver_evidence = forecast.get("driver_evidence")
    if driver_evidence is None and isinstance(intake, Mapping):
        driver_evidence = intake.get("driver_evidence") or intake.get("drivers")
    if not isinstance(driver_evidence, Mapping):
        blockers.append("driver forecast missing driver evidence for required series")
        return blockers

    as_of = intake.get("as_of") or intake.get("price_date") if isinstance(intake, Mapping) else None
    for series in _REQUIRED_DRIVER_SERIES:
        if series not in driver_evidence:
            blockers.append(f"driver forecast missing required series: {series}")
            continue
        row = driver_evidence[series]
        prefix = f"driver forecast {series}"
        if not isinstance(row, Mapping):
            blockers.append(f"{prefix}: must be a driver evidence object")
            continue
        source = row.get("source")
        if not _text(source):
            blockers.append(f"{prefix}: source is required and must identify verified provenance")
        elif not _verified_source_reference(source):
            blockers.append(f"{prefix}: source must identify verified provenance (HTTPS or sectors_cache)")
        s_date = row.get("source_date")
        if not _source_date(s_date):
            blockers.append(f"{prefix}: source_date is required in YYYY-MM-DD format")
        elif _source_date(as_of) and s_date > str(as_of)[:10]:
            blockers.append(f"{prefix}: source_date is after report as-of date")
        if "page" in row and not _page(row.get("page")):
            blockers.append(f"{prefix}: page must be a positive page label/number or null")
        if not _text(row.get("note") or row.get("claim") or row.get("status") or row.get("basis")):
            blockers.append(f"{prefix}: explanatory note or claim is required")
    return blockers


def _check_sotp(result: object, intake: object) -> list[str]:
    if not isinstance(result, Mapping):
        return ["SOTP missing: no SOTP result"]
    blockers = []
    if result.get("status") != "complete":
        blockers.append("SOTP incomplete: status must be complete")
    gaps = result.get("gaps")
    if not isinstance(gaps, list) or gaps:
        blockers.append("SOTP incomplete: gaps must be an empty list")
    assets = result.get("assets")
    as_of = intake.get("as_of") or intake.get("price_date") \
        if isinstance(intake, Mapping) else None
    if not isinstance(assets, list) or not assets:
        blockers.append("SOTP incomplete: at least one valued asset is required")
    else:
        for i, asset in enumerate(assets):
            prefix = f"SOTP incomplete: assets[{i}]"
            if not isinstance(asset, Mapping):
                blockers.append(f"{prefix} must be a valued asset object")
                continue
            for field in ("name", "stage", "method", "source", "provenance"):
                if not _text(asset.get(field)):
                    blockers.append(f"{prefix}.{field} is required")
            if _text(asset.get("source")) and not _cache_provenance(asset.get("source")):
                blockers.append(f"{prefix}.source must identify sectors_cache provenance")
            for field in ("nav_idr", "ownership_pct", "attributable_nav_idr"):
                if not _number(asset.get(field)):
                    blockers.append(f"{prefix}.{field} must be finite and present")
            if not _source_date(asset.get("source_date")):
                blockers.append(f"{prefix}.source_date is required in YYYY-MM-DD format")
            elif _source_date(as_of) and asset["source_date"] > as_of:
                blockers.append(f"{prefix}.source_date is after report as-of date")
            if not _page(asset.get("page")):
                blockers.append(f"{prefix}.page is required")
    for field in ("attributable_asset_nav_idr", "pre_discount_equity_value_idr",
                  "equity_value_idr"):
        if not _number(result.get(field)):
            blockers.append(f"SOTP incomplete: {field} must be finite and present")
    for field in ("cash_idr", "debt_idr", "minority_interest_idr",
                  "corporate_overhead_idr", "shares", "target_price_idr"):
        if not _number(result.get(field)):
            blockers.append(f"SOTP incomplete: {field} must be finite and present")
    bridge_evidence = result.get("bridge_evidence")
    bridge_fields = ("cash_idr", "debt_idr", "minority_interest_idr",
                     "corporate_overhead_idr", "shares")
    if not isinstance(bridge_evidence, Mapping):
        blockers.append("SOTP incomplete: bridge evidence is required")
    else:
        for field in bridge_fields:
            evidence = bridge_evidence.get(field)
            prefix = f"SOTP incomplete: {field} evidence"
            if not isinstance(evidence, Mapping):
                blockers.append(f"{prefix} is missing")
                continue
            for required in ("source", "source_date", "page", "unit"):
                if required not in evidence:
                    blockers.append(f"{prefix}.{required} is required")
            if not _text(evidence.get("source")):
                blockers.append(f"{prefix}.source must be non-empty")
            elif not _cache_provenance(evidence.get("source")):
                blockers.append(f"{prefix}.source must identify sectors_cache provenance")
            if not _source_date(evidence.get("source_date")):
                blockers.append(f"{prefix}.source_date must be YYYY-MM-DD")
            elif _source_date(as_of) and evidence["source_date"] > as_of:
                blockers.append(f"{prefix}.source_date is after report as-of date")
            if not _page(evidence.get("page")):
                blockers.append(f"{prefix}.page must be a positive page label/number")
            allowed_units = {"shares"} if field == "shares" else {"IDR", "raw IDR"}
            if evidence.get("unit") not in allowed_units:
                blockers.append(f"{prefix}.unit must be one of {sorted(allowed_units)}")
    return blockers


def assess_release(profile, intake, forecast, sotp_result):
    """Assess whether a model may be published as a production report.

    Args:
        profile: Explicit model profile string. Only ``finite_life_mining``
            activates the three mining-specific checks below.
        intake: For mining, contains ``latest_interim_actuals`` with an interim
            period, reported-actual status, source/date/page, and numeric
            revenue/EBITDA/net-profit/capex metrics, each with a unit.
        forecast: For mining, contains ``operating_bridge`` keyed by every
            stage in :data:`OPERATING_BRIDGE_STAGES`; each stage is a sourced
            evidence row. Use a sourced ``not_applicable`` row for stages that
            do not apply to the issuer.
        sotp_result: For mining, complete result from ``calculate_sotp``.

    Returns ``{"status": ..., "blockers": [...]}``. Non-mining profiles do
    not inherit any of these mining-only requirements.
    """
    blockers = []
    normalized_profile = profile.strip().lower() if isinstance(profile, str) else ""
    supported_profiles = {"finite_life_mining", "going_concern_fcff", "financial_ddm"}
    if normalized_profile not in supported_profiles:
        blockers.append(f"unsupported model profile: {profile or 'missing'}")
    if normalized_profile == "finite_life_mining":
        blockers.extend(_check_latest_interim_actuals(intake))
        blockers.extend(_check_operating_bridge(forecast))
        if (not isinstance(forecast, Mapping) or
                forecast.get("forecast_basis") != "physical_driver_forecast" or
                forecast.get("production_ready") is not True):
            blockers.append(
                "mining forecast is not a verified physical-driver production forecast")
        g2 = (forecast or {}).get("g2") if isinstance(forecast, Mapping) else None
        if isinstance(g2, Mapping) and g2.get("G2.9_operating_bridge") == "gagal":
            blockers.append("forecast gate failed: G2.9 physical-to-financial operating bridge is not reconciled")
        blockers.extend(_check_sotp(sotp_result, intake))
    elif normalized_profile in {"going_concern_fcff", "financial_ddm"}:
        actual = intake.get("latest_official_actual") if isinstance(intake, Mapping) else None
        if not isinstance(actual, Mapping):
            blockers.append("latest official interim actual is missing or unverified")
        elif not all(actual.get(key) for key in
                     ("period", "period_end", "published_at", "source_url", "metrics")):
            blockers.append("latest official interim actual has incomplete provenance")
        else:
            report_date = _date((intake or {}).get("as_of"))
            publication = _date(actual.get("published_at"))
            period_end = _date(actual.get("period_end"))
            if not publication or not period_end or period_end > publication or (
                    report_date and publication > report_date):
                blockers.append("latest official interim dates are inconsistent")
            metrics = actual.get("metrics")
            if (not isinstance(metrics, Mapping) or
                    any(not isinstance(metrics.get(key), (int, float)) for key in
                        ("revenue", "net_profit"))):
                blockers.append("latest official interim revenue/net profit are missing")
        blockers.extend(_check_driver_forecast(forecast, intake))
        if normalized_profile == "financial_ddm":
            has_ddm = (
                isinstance(sotp_result, Mapping)
                and (
                    sotp_result.get("status") in {"complete", "draft"}
                    or "tp_gordon" in sotp_result
                    or sotp_result.get("method") == "ddm"
                )
            ) or sotp_result == "draft"
            if not has_ddm:
                blockers.append("financial DDM/residual-income primary valuation is not implemented")
    thin_data = False
    if isinstance(sotp_result, Mapping):
        gv = sotp_result.get("gate_verdict")
        if isinstance(gv, Mapping):
            if gv.get("rating_override") == "Review Required":
                blockers.append("valuation sanity check failed: extreme upside/downside requires review")
            if gv.get("thin_data"):
                thin_data = True
    result = {
        "status": "draft_non_distributable" if blockers else "distributable",
        "blockers": blockers,
    }
    if thin_data:
        result["thin_data"] = True
    return result
