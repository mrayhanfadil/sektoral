"""Prospective forecast evaluation: freeze estimates, score them against declared baselines (plan §8).

Each build records ``forecast_record``: its fiscal-year revenue and parent
profit forecasts in the reporting currency, the first-half actual it was
anchored on, and two declared baselines fixed at the same time:

- ``last_fy``: the last reported fiscal year held flat (random walk);
- ``run_rate``: twice the first-half actual (the forecast year's own H1).

``freeze`` stores the record of a published Company Update once, keyed by its
publication, before the next official result; it is append-only. ``evaluate``
scores a later official fiscal-year actual against the model and each
baseline: absolute and percentage errors with the unit, and whether the
model's error is material under release policy 1.2.0 (5% of FY1 parent
profit), which raises a review task. A cumulative interim actual (9M) is
tracked against the forecast with the prior year's seasonality and stated as
tracking, not as a forecast error.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import outputs, period_basis, release_policy, store

COLLECTION = "forecast_ledger"


def record(intake, fc):
    """The build's forecast and baselines, or None without a fiscal-year path."""
    evidence = intake.get("official_evidence") or {}
    currency = evidence.get("reporting_currency") or "IDR"
    actual = intake.get("latest_official_actual") or {}
    scenario = (fc or {}).get("earnings_scenario") or (fc or {}).get("interim_scenario") or {}
    full = scenario.get("full_year") or {}
    years = []
    if scenario.get("year") and full:
        years.append({"year": scenario["year"], "revenue": full.get("revenue"),
                      "net_profit_attributable": full.get("net_profit_attributable",
                                                          full.get("net_profit"))})
    for r in ((fc or {}).get("outyear_scenario") or {}).get("rows") or []:
        years.append({"year": r.get("year"), "revenue": r.get("revenue"),
                      "net_profit_attributable": r.get("net_profit_attributable", r.get("net_profit"))})
    if not years:
        return None
    # A scenario without its own parent split (the mining interim anchor) takes
    # the official prior-year parent share, as Key Financials and the statements do.
    from . import forecast_statements
    parent = forecast_statements.parent_share(intake, scenario) if scenario else None
    if parent:
        share = parent[0]
        consolidated = [full.get("net_profit")] + [
            r.get("net_profit") for r in ((fc or {}).get("outyear_scenario") or {}).get("rows") or []]
        for item, net in zip(years, consolidated):
            if net is not None:
                item["net_profit_attributable"] = net * share
    metrics = actual.get("metrics") or {}
    h1_net = metrics.get("net_profit_attributable", metrics.get("net_profit"))
    annual = [a for a in evidence.get("annual_actuals") or [] if isinstance(a, dict)]
    last = max(annual, key=lambda a: a.get("year", 0)) if annual else None
    if last is None and intake.get("annuals"):
        a = intake["annuals"][-1]
        last = {"year": a.get("year"), "revenue": a.get("revenue"),
                "net_profit_attributable": a.get("earnings")}
        if currency == "USD":
            last = None  # Sectors annuals are rupiah; no like-for-like US$ baseline
    baselines = {}
    if last and last.get("net_profit_attributable", last.get("net_profit")) is not None:
        baselines["last_fy"] = {"year": last.get("year"), "revenue": last.get("revenue"),
                                "net_profit_attributable": last.get("net_profit_attributable",
                                                                    last.get("net_profit"))}
    if isinstance(h1_net, (int, float)) and str(actual.get("period") or "").startswith("1H"):
        baselines["run_rate"] = {"year": years[0]["year"],
                                 "revenue": 2 * metrics["revenue"] if metrics.get("revenue") else None,
                                 "net_profit_attributable": 2 * h1_net}
    return {"currency": currency, "unit": "unit", "as_of": intake.get("as_of"),
            "anchor": {"period": actual.get("period"), "net_profit_attributable": h1_net,
                       "published_at": actual.get("published_at")},
            "years": years, "baselines": baselines,
            "baseline_rules": {"last_fy": "tahun fiskal terakhir yang dilaporkan, datar",
                               "run_rate": "dua kali aktual 1H tahun forecast"}}


def freeze(folder, ticker, db=None):
    """Store a published report's forecast record once; returns the stored key or None."""
    t = str(ticker).upper()
    doc = outputs.load(outputs.REPORT, folder, t, db) or {}
    manifest = outputs.load(outputs.MANIFEST, folder, t, db) or {}
    rec = doc.get("forecast_record")
    if not rec:
        return None
    key = f"{t}:{rec['as_of']}:{manifest.get('publication_id') or 'unpublished'}"
    stored = store.insert_if_absent(COLLECTION, key, {
        "ticker": t, "folder": str(folder), "publication_id": manifest.get("publication_id"),
        "status": (doc.get("meta") or {}).get("status"), **rec}, db)
    return key if stored else None


def freeze_if_auto_published(folder, ticker, db=None):
    """Freeze the forecast of a build that publishes automatically (policy 1.3.0)."""
    doc = outputs.load(outputs.REPORT, folder, str(ticker).upper(), db) or {}
    status = (doc.get("meta") or {}).get("status")
    if not (release_policy.auto_publish_enabled() and status in release_policy.AUTO_PUBLISH_STATUSES):
        return None
    return freeze(folder, ticker, db)


def _error(forecast, actual):
    if forecast is None or actual in (None, 0):
        return None
    return {"forecast": forecast, "actual": actual, "abs": forecast - actual,
            "pct": (forecast - actual) / abs(actual)}


def evaluate(frozen, actual):
    """Score a later official actual ``{period, revenue, net_profit_attributable, ...}``."""
    parsed = period_basis.parse(actual.get("period"))
    if not parsed:
        return {"status": "unrecognized_period"}
    year = parsed["fiscal_year"]
    forecast = next((y for y in frozen["years"] if y["year"] == year), None)
    if forecast is None:
        return {"status": "outside_horizon", "year": year}
    if parsed["months"] == 12:
        net = actual.get("net_profit_attributable", actual.get("net_profit"))
        out = {"status": "evaluated", "period": actual["period"], "currency": frozen["currency"],
               "model": {"net_profit_attributable": _error(forecast["net_profit_attributable"], net),
                         "revenue": _error(forecast.get("revenue"), actual.get("revenue"))},
               "baselines": {name: {"net_profit_attributable": _error(b.get("net_profit_attributable"), net),
                                    "revenue": _error(b.get("revenue"), actual.get("revenue"))}
                             for name, b in frozen["baselines"].items()}}
        model = out["model"]["net_profit_attributable"]
        threshold = release_policy.EARNINGS_MATERIALITY_PCT / 100
        out["material"] = bool(model and abs(model["pct"]) >= threshold)
        out["review_task"] = (f"Kesalahan forecast laba induk {actual['period']} "
                              f"{model['pct'] * 100:+.1f}% melewati materialitas; tinjau asumsi "
                              "dan putuskan revisi atau pertahankan dengan alasan tercatat."
                              if out["material"] else None)
        return out
    # A cumulative interim actual is tracked with the prior year's seasonality.
    share = actual.get("prior_year_share_of_fy")
    net = actual.get("net_profit_attributable", actual.get("net_profit"))
    if share and net is not None and forecast["net_profit_attributable"]:
        implied = net / share
        return {"status": "tracking", "period": actual["period"], "implied_fy": implied,
                "forecast_fy": forecast["net_profit_attributable"],
                "gap_pct": implied / forecast["net_profit_attributable"] - 1,
                "basis": "aktual kumulatif / porsi periode yang sama tahun lalu terhadap FY"}
    return {"status": "tracking_unavailable", "period": actual["period"],
            "reason": "porsi musiman tahun lalu tidak tersedia"}


def frozen_records(ticker, db=None):
    return [doc for _, doc in store.items(COLLECTION, f"{str(ticker).upper()}:", db)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--folder", required=True)
    f.add_argument("tickers", nargs="*")
    e = sub.add_parser("evaluate")
    e.add_argument("--ticker", required=True)
    e.add_argument("--actual", required=True, help="JSON file with period and metrics")
    args = parser.parse_args(argv)
    if args.command == "freeze":
        tickers = [t.upper() for t in args.tickers] or outputs.tickers(outputs.REPORT, args.folder)
        for t in tickers:
            print(t, freeze(args.folder, t) or "sudah dibekukan atau tanpa forecast")
        return 0
    actual = json.loads(open(args.actual, encoding="utf-8").read())
    for rec in frozen_records(args.ticker):
        print(json.dumps({"publication": rec.get("publication_id"), "as_of": rec.get("as_of"),
                          **evaluate(rec, actual)}, default=str, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
