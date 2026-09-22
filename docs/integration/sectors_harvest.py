"""Bulk Sectors harvest - pull once, store in the lake, reuse everywhere.

Lake layout (.cache/sectors/):
  manifest.json                  - harvest id, timestamp, credit estimate/actual
  universe/close-{date}.json     - full-universe close (1 call, not per-ticker)
  {TICKER}/report-{sections}.json, daily-90d.json, quarterly-8.json,
    news.json, filings.json, actions.json, flow-90d.json, brokertop.json,
    suspensions.json, listing.json

Credit math (see docs/sectors-swap.md Pricing):
  per ticker ~17 (report 5 sections + daily + dates/quarterly + segments +
    shareholders + news + filings + actions + flow + brokertop +
    suspensions + listing)
  shared ~12 (universe + idx-mcap + jci + 4 subsectors x2 + screener)
  full quintet harvest ~= 5*17 + 12 = 97 credits.
  Daily refresh ~= 5*(daily+news) + universe = 11 credits.

Usage:
  python scripts/sectors_harvest.py --dry-run            # no key, no network
  python scripts/sectors_harvest.py --execute            # needs SECTORS_API_KEY
  python scripts/sectors_harvest.py --execute --daily    # cheap refresh only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TICKERS = ["RATU", "CDIA", "MTEL", "BBCA", "ADRO"]
SUBSECTORS = ["banks", "energy", "telecommunication-service", "basic-materials"]
LAKE = Path(os.getenv("SECTORS_LAKE_DIR", ".cache/sectors-lake"))

# (helper-name, per-ticker?, credit-cost, refresh-cadence)
PLAN_SHARED = [
    ("universe_close", False, 1, "daily"),
    ("idx_market_cap", False, 1, "daily"),
    ("index_daily:JCI", False, 1, "daily"),
    ("screener:breadth", False, 1, "weekly"),
    ("subsector_report", False, 2 * len(SUBSECTORS), "weekly"),
]
PLAN_PER_TICKER = [
    ("report:overview,financials,dividend,peers,future", 5, "weekly"),
    ("daily:90d", 1, "daily"),
    ("quarterly_dates+quarterly:8", 2, "on-filing"),
    ("segments", 1, "yearly"),
    ("shareholders_composition", 1, "weekly"),
    ("news", 1, "daily"),
    ("filings", 1, "weekly"),
    ("corporate_actions", 1, "weekly"),
    ("foreign_flow:90d", 1, "weekly"),
    ("broker_top", 1, "weekly"),
    ("suspensions", 1, "weekly"),
    ("listing_performance", 1, "once"),
]


def build_plan(daily_only: bool = False):
    shared = [p for p in PLAN_SHARED if not daily_only or p[3] == "daily"]
    per = [p for p in PLAN_PER_TICKER if not daily_only or p[2] == "daily"]
    per_creds = sum(p[1] for p in per) * len(TICKERS)
    shared_creds = sum(p[2] for p in shared)
    return {
        "tickers": TICKERS,
        "per_ticker": [{"call": p[0], "credits": p[1]} for p in per],
        "shared": [{"call": p[0], "credits": p[2]} for p in shared],
        "credit_estimate": per_creds + shared_creds,
    }


def execute(plan: dict) -> dict:
    from server import sectors as S

    end = date.today().isoformat()
    start90 = (date.today() - timedelta(days=90)).isoformat()
    LAKE.mkdir(parents=True, exist_ok=True)
    spent, errors = 0, []
    (LAKE / "universe").mkdir(exist_ok=True)
    try:
        uni = S.universe_close(end)
        (LAKE / "universe" / f"close-{end}.json").write_text(json.dumps(uni)[:2_000_000])
        spent += 1
    except Exception as e:
        errors.append(f"universe: {type(e).__name__}")
    for t in plan["tickers"]:
        d = LAKE / t
        d.mkdir(exist_ok=True)
        calls = [
            ("report-opfvd.json", S.company_report, (t, "overview,peers,future,valuation,dividend")),
            ("daily-90d.json", S.daily, (t, start90, end)),
            ("quarterly-8.json", S.quarterly, (t, 8)),
            ("segments.json", S.segments, (t,)),
            ("shareholders.json", S.shareholders_composition, (t,)),
            ("news.json", S.news, (t,)),
            ("filings.json", S.filings, (t,)),
            ("actions.json", S.corporate_actions, (t,)),
            ("flow-90d.json", S.foreign_flow, (t, start90, end)),
            ("brokertop.json", S.broker_top, (t, start90, end)),
            ("suspensions.json", S.suspensions, (t,)),
            ("listing.json", S.listing_performance, (t,)),
        ]
        for fname, fn, args in calls:
            try:
                (d / fname).write_text(json.dumps(fn(*args))[:2_000_000])
                spent += 1
            except Exception as e:
                errors.append(f"{t}/{fname}: {type(e).__name__}")
    manifest = {"date": end, "credits_spent": spent, "errors": errors}
    (LAKE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--daily", action="store_true")
    a = ap.parse_args()
    plan = build_plan(daily_only=a.daily)
    if a.dry_run or not a.execute:
        print(json.dumps(plan, indent=2))
        return 0
    if not os.environ.get("SECTORS_API_KEY"):
        print("SECTORS_API_KEY missing - refusing to burn blind. Run --dry-run.")
        return 2
    print(json.dumps(execute(plan), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
