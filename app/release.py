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
# Financial DDM never inherits FCFF/capex/NWC/EV/WACC as a release
# requirement (§3.1, §4.5). Its production bridge is profit/equity/payout.
_REQUIRED_DRIVER_SERIES_DDM = ("net_profit", "equity", "payout")
_DDM_PROFIT_ALIASES = {"net_profit", "profit"}
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
    # Evidence often keeps the document title alongside its direct URL.
    # Accept that traceable form as well as a bare URL and cache provenance.
    match = re.search(r"https://[^\s<>\"']+", value.strip(), flags=re.IGNORECASE)
    candidate = match.group(0).rstrip(".,;)") if match else value.strip()
    try:
        parsed = urlsplit(candidate)
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
                not _verified_source_reference(bridge[stage].get("source")):
            blockers.append(f"operating bridge {stage}: source must identify verified provenance (HTTPS or sectors_cache)")
    return blockers


def _check_driver_forecast(forecast: object, intake: object,
                           profile: object = None) -> list[str]:
    if not isinstance(forecast, Mapping):
        return ["sourced operating and cash-flow forecast is incomplete"]
    blockers = []
    normalized = str(profile or "").strip().lower() if isinstance(profile, str) else ""
    if not normalized and isinstance(intake, Mapping):
        normalized = str(intake.get("model_profile") or "").strip().lower()
    is_ddm = normalized == "financial_ddm"
    required_series = _REQUIRED_DRIVER_SERIES_DDM if is_ddm else _REQUIRED_DRIVER_SERIES
    expected_basis = "driver_forecast"
    if forecast.get("forecast_basis") != expected_basis:
        if is_ddm and forecast.get("forecast_basis") == "financial_driver_forecast":
            pass
        else:
            blockers.append("sourced operating and cash-flow forecast is incomplete")
    if forecast.get("production_ready") is not True:
        blockers.append("forecast is not verified as production-ready")
    for reason in forecast.get("production_blockers") or []:
        if isinstance(reason, str) and reason.strip():
            blockers.append(f"forecast: {reason}")

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
    for series in required_series:
        # DDM profit alias: net_profit satisfies profit and vice versa.
        lookup = series
        if is_ddm and series == "net_profit" and series not in driver_evidence:
            if "profit" in driver_evidence:
                lookup = "profit"
        if lookup not in driver_evidence:
            if is_ddm and series in _DDM_PROFIT_ALIASES:
                sibling = "profit" if series == "net_profit" else "net_profit"
                if sibling in driver_evidence:
                    lookup = sibling
                else:
                    blockers.append(f"driver forecast missing required series: {series}")
                    continue
            else:
                blockers.append(f"driver forecast missing required series: {series}")
                continue
        row = driver_evidence[lookup]
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
            if _text(asset.get("source")) and not _verified_source_reference(asset.get("source")):
                blockers.append(f"{prefix}.source must identify verified provenance (HTTPS or sectors_cache)")
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
            elif not _verified_source_reference(evidence.get("source")):
                blockers.append(f"{prefix}.source must identify verified provenance (HTTPS or sectors_cache)")
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


def common_blockers(profile, intake, forecast):
    """Data/forecast blockers shared by every valuation method of a profile.

    Method-specific completeness (SOTP bridge, DDM result) is checked
    separately so the method chain can fall back without losing these.
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
        blockers.extend(_check_driver_forecast(forecast, intake, normalized_profile))
    return blockers


def _check_ddm_present(result):
    has_ddm = (
        isinstance(result, Mapping)
        and (
            result.get("status") in {"complete", "draft"}
            or "tp_gordon" in result
            or result.get("method") == "ddm"
        )
    ) or result == "draft"
    return [] if has_ddm else [
        "financial DDM/residual-income primary valuation is not implemented"]


def assess_chain(profile, intake, forecast, chain):
    """Release for the method selected by :mod:`app.method_chain`.

    Common data blockers always apply; the skipped methods' own gaps stay in
    the chain trace instead of blocking the selected fallback.
    """
    from . import method_chain
    blockers = common_blockers(profile, intake, forecast)
    chain_blocker = method_chain.summary_blocker(chain or {})
    if chain_blocker:
        blockers.append(chain_blocker)
    return {"status": "draft_non_distributable" if blockers else "distributable",
            "blockers": blockers, "route": (chain or {}).get("route"),
            "method_key": (chain or {}).get("selected")}


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
    normalized_profile = profile.strip().lower() if isinstance(profile, str) else ""
    blockers = common_blockers(profile, intake, forecast)
    if normalized_profile == "finite_life_mining":
        blockers.extend(_check_sotp(sotp_result, intake))
    elif normalized_profile == "financial_ddm":
        blockers.extend(_check_ddm_present(sotp_result))
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


def assess_assumption_led(intake, forecast, valuation, assumption_status,
                          underlying_release):
    """Opt-in FY forecast/multiple release, independent of the LoM/SOTP gate."""
    blockers = []
    report_day = _date(intake.get("as_of"))
    actual = intake.get("latest_official_actual") or {}
    quote = intake.get("market_quote") or {}
    scenario = forecast.get("interim_scenario") or {}
    fx = intake.get("fx_spot") or {}
    if intake.get("model_profile") != "finite_life_mining":
        blockers.append("assumption-led method requires finite_life_mining profile")
    blockers.extend(_check_latest_interim_actuals(intake))
    if assumption_status != "validated":
        blockers.append("forecast agent scenario has not passed validation")
    if not scenario or not _verified_source_reference(scenario.get("source_url")):
        blockers.append("source-backed interim scenario is missing")
    elif (scenario.get("source_url") != actual.get("source_url") or
          scenario.get("published_at") != actual.get("published_at")):
        blockers.append("interim scenario does not match the official actual release")
    else:
        for key in _FINANCIAL_METRICS:
            field = "capital_expenditure" if key == "capex" else key
            if not _number((scenario.get("h1") or {}).get(field)) or not _number(
                    (scenario.get("full_year") or {}).get(field)):
                blockers.append(f"interim scenario missing {field}")
            elif abs(scenario["h1"][field] - actual["metrics"][field]) > 1:
                blockers.append(f"interim scenario {field} differs from official actual")
    publication = _date(actual.get("published_at"))
    quote_day = _date(quote.get("date"))
    if (not report_day or not publication or not quote_day or
            not publication <= quote_day <= report_day or
            (report_day - quote_day).days > 5 or
            not _verified_source_reference(quote.get("source_url")) or
            quote.get("price") != intake.get("price")):
        blockers.append("fresh sourced close after latest release is required")
    fx_day = _date(fx.get("date"))
    if (not report_day or not fx_day or fx_day > report_day or
            (report_day - fx_day).days > 7 or
            not _text(fx.get("source")) or
            not _number(fx.get("rate")) or fx["rate"] <= 0):
        blockers.append("fresh sourced USD/IDR quote is required")
    balance = (intake.get("official_evidence") or {}).get("balance_sheet") or {}
    if (not _verified_source_reference(balance.get("source_url")) or
            any(not _number(balance.get(key)) or balance[key] <= 0 for key in
                ("cash", "total_debt", "shares_outstanding")) or
            not _number(balance.get("non_controlling_interest")) or
            balance["non_controlling_interest"] < 0):
        blockers.append("official cash/debt/minority/share bridge is incomplete")
    values = valuation.get("values") if isinstance(valuation, Mapping) else None
    if not isinstance(values, list) or [v.get("multiple") for v in values] != [6.0, 8.0, 10.0] or any(
            not _number(v.get("per_share_idr")) or v["per_share_idr"] <= 0
            for v in values):
        blockers.append("6x/8x/10x EV/EBITDA sensitivity is incomplete")
    elif not values[0]["per_share_idr"] < values[1]["per_share_idr"] < values[2]["per_share_idr"]:
        blockers.append("EV/EBITDA sensitivity is not monotonic")
    return {
        "status": "draft_non_distributable" if blockers else "distributable_assumption_led",
        "method": "FY26F EV/EBITDA 8x",
        "blockers": blockers,
        "underlying_sotp": underlying_release,
        "limitations": ["8x is an analyst assumption, not a verified peer multiple",
                        "asset-level LoM/SOTP and later cash/debt movements are not modeled"],
    }
