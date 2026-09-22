# Example 6: Broker & foreign-flow analysis

> Hackathon track fit: **AI Agents** / Market Intel
> Endpoints exercised: `GET /v2/brokers/top/`, `GET /v2/broker-summary/{symbol}/top/`, `GET /v2/foreign-flow/{symbol}/`
> Credits per run: **5** for the "broker-by-symbol + foreign-flow + top brokers" triad (2+2+1)

## What this demonstrates

- Three endpoints that together give you a **full broker-flow picture**: top brokers by trading value, per-symbol buyer/seller leaderboard, and net foreign-broker inflow.
- The **"closed market" identity** for foreign flow: since the IDX is a closed auction market, `foreign + domestic = 0` for any (symbol, date) pair. The API only returns the foreign side; domestic flow is implicitly `-net_foreign_inflow`.
- The `origin` + `cohort` filter pair: `origin=foreign|domestic`, `cohort=retail|mixed|institutional|unknown`. Useful for separating institutional vs retail flow.
- How to wire this into a "smart money tracker" — flag a stock when foreign brokers are accumulating AND a top-3 broker is net buying.

## Code

```python
"""
Broker & foreign-flow analysis — the "smart money" triad.

Three endpoints:
  - /v2/brokers/top/?date=...           (top brokers by gross trade value, 2 credits)
  - /v2/broker-summary/{symbol}/top/    (top buyers/sellers for ONE symbol, 2 credits)
  - /v2/foreign-flow/{symbol}/?start&end (daily net foreign-broker flow, 1 credit)

The three together = 5 credits. Use the symbol-targeted pair when you already
have a watchlist; use /v2/brokers/top/ when you're scanning the whole market.
"""
import os
import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def top_brokers(date: str | None = None,
                metric: str = "gross",
                origin: str = "all",
                cohort: str = "all",
                n_brokers: int = 10) -> dict:
    """
    Top brokers ranked for a single date.

    metric: 'gross' (total buy+sell value) | 'net' (absolute net flow)
    origin: 'foreign' | 'domestic' | 'all'
    cohort: 'institutional' | 'mixed' | 'retail' | 'unknown' | 'all'

    Costs 2 credits. Default n_brokers=None returns all ~88 IDX brokers.
    """
    params: dict = {"metric": metric, "origin": origin, "cohort": cohort}
    if date:
        params["date"] = date
    if n_brokers:
        params["n_brokers"] = n_brokers
    r = requests.get(f"{BASE}/v2/brokers/top/", headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def broker_summary_top(symbol: str, start: str, end: str,
                       origin: str = "all",
                       cohort: str = "all",
                       n_brokers: int = 10) -> dict:
    """
    Top net buyers and sellers for one symbol over a date range (max 90 days).
    Costs 2 credits.

    Response has top_buyers[] (positive net_idr first) and top_sellers[]
    (most negative net_idr first).
    """
    params: dict = {
        "start": start, "end": end,
        "origin": origin, "cohort": cohort,
        "n_brokers": n_brokers,
    }
    r = requests.get(
        f"{BASE}/v2/broker-summary/{symbol}/top/",
        headers=HEADERS, params=params, timeout=15,
    )
    r.raise_for_status()
    return r.json()


def foreign_flow(symbol: str, start: str, end: str) -> dict:
    """
    Daily net foreign-broker inflow for one symbol over up to 90 days.
    Costs 1 credit. Positive = foreign brokers net buyers that day.
    """
    r = requests.get(
        f"{BASE}/v2/foreign-flow/{symbol}/",
        headers=HEADERS, params={"start": start, "end": end}, timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---- 1. Top brokers overall, foreign origin, latest day (2 credits) ----
print("=== Top 10 foreign brokers, latest trading day, by gross value ===")
data = top_brokers(metric="gross", origin="foreign", n_brokers=10)
print(f"  Date: {data['date']}  metric={data['metric']}  origin={data['origin']}")
for row in data["results"][:5]:
    print(f"    #{row['rank']:<2} {row['broker_code']:<5} gross=Rp {row['gross']:>16,}  "
          f"net=Rp {row.get('net', 0):>16,}")
print()


# ---- 2. Per-symbol top buyers/sellers, BBCA, last 14 days (2 credits) ----
print("=== BBCA: top 5 buyers + sellers, last 14 days, all brokers ===")
data = broker_summary_top("BBCA", start="2026-05-26", end="2026-06-09", n_brokers=5)
print("  Top buyers (net buy):")
for row in data["top_buyers"][:5]:
    print(f"    #{row['rank']:<2} {row['broker_code']:<5} net=Rp {row['net_idr']:>16,}  "
          f"buy={row['buy_idr']:,}  sell={row['sell_idr']:,}")
print("  Top sellers (net sell):")
for row in data["top_sellers"][:5]:
    print(f"    #{row['rank']:<2} {row['broker_code']:<5} net=Rp {row['net_idr']:>16,}")
print()


# ---- 3. Foreign flow on BBCA, last 30 days (1 credit) ----
print("=== BBCA: foreign flow, last 30 days ===")
flow = foreign_flow("BBCA", start="2026-05-10", end="2026-06-09")
print(f"  Symbol: {flow['symbol']}  Range: {flow['start']} → {flow['end']}")
total_net = sum(p["net_foreign_inflow"] for p in flow["data"])
print(f"  {len(flow['data'])} trading days; cumulative net foreign: Rp {total_net:,}")
print(f"  Last 3 days:")
for p in flow["data"][-3:]:
    sign = "+" if p["net_foreign_inflow"] >= 0 else ""
    print(f"    {p['date']}: {sign}Rp {p['net_foreign_inflow']:,}")
print()


# ---- 4. Combined "smart money" check on GOTO (2+1 = 3 credits) ----
# Pattern: foreign buying + a top-3 broker also net buying → bull signal.
print("=== GOTO smart-money check ===")
summary = broker_summary_top("GOTO", start="2026-06-02", end="2026-06-09", n_brokers=3)
fflow = foreign_flow("GOTO", start="2026-06-02", end="2026-06-09")

foreign_7d = sum(p["net_foreign_inflow"] for p in fflow["data"])
print(f"  Foreign 7d cumulative: Rp {foreign_7d:,}")
print(f"  Top buyer: {summary['top_buyers'][0]['broker_code']}  "
      f"net=Rp {summary['top_buyers'][0]['net_idr']:,}")
print(f"  Top seller: {summary['top_sellers'][0]['broker_code']}  "
      f"net=Rp {summary['top_sellers'][0]['net_idr']:,}")
signal = "BULL" if foreign_7d > 0 and summary["top_buyers"][0]["net_idr"] > 0 else "MIXED"
print(f"  Signal: {signal}")
```

## Expected output shape

`/v2/brokers/top/` response:

```json
{
  "date": "2026-07-08",
  "metric": "gross",
  "origin": "foreign",
  "cohort": "all",
  "results": [
    {"rank": 1, "broker_code": "AK", "gross": 1984643350000, "net": -326211642600}
  ]
}
```

`/v2/broker-summary/{symbol}/top/` response:

```json
{
  "symbol": "BBCA.JK",
  "start": "2025-05-01",
  "end": "2025-05-14",
  "origin": "all",
  "cohort": "all",
  "top_buyers": [
    {"rank": 1, "broker_code": "KZ", "net_idr": 645536242500,
     "buy_idr": 1163325432500, "sell_idr": 517789190000}
  ],
  "top_sellers": [
    {"rank": 1, "broker_code": "BK", "net_idr": -318961117500,
     "buy_idr": 561727337500, "sell_idr": 880688455000}
  ]
}
```

`/v2/foreign-flow/{symbol}/` response:

```json
{
  "symbol": "BBCA.JK",
  "start": "2025-05-01",
  "end": "2025-05-05",
  "data": [
    {"date": "2025-05-02", "net_foreign_inflow": 199859810000}
  ]
}
```

## Pitfalls

- **`broker_code` is a 2-letter ID** (e.g. `"AK"`, `"KZ"`, `"BK"`), not a human name. The `/v2/brokers/registry/` endpoint (1 credit) maps codes to full names — fetch once and cache forever.
- **Closed-market identity**: for any `(symbol, date)` on IDX, `foreign + domestic net = 0`. The API only returns foreign flow, so don't double-count or fetch "domestic flow" — it doesn't exist as a separate field.
- **404 vs empty**: a ticker with no broker activity in the window returns 404 (`Symbol 'XYZA' not found in broker data`). That costs 1 credit. Verify ticker exists with example 01 before calling.
- **`cohort` enum**: `retail|mixed|institutional|unknown|all`. Lowercase. The default `all` includes "unknown" brokers (some legacy / inactive codes) — filter them out if you're showing a "smart money" narrative.
- **`net_idr` sign convention**: positive = net buyer, negative = net seller. `top_buyers` ranks by largest positive first; `top_sellers` by largest negative first.
- **`origin` and `cohort` come from the broker registry** — classifications are curated by Sectors, not user-editable. If a broker's classification seems wrong, that's a registry fact, not a query error.
- **14-day cap on broker summary** (not 90 like foreign flow). If you want a longer window, paginate by stitching overlapping windows.
- **`/v2/foreign-flow/` doesn't accept `origin` or `cohort`** — it's already foreign-only. The symbol-scoped `/v2/broker-summary/{symbol}/` is the one that takes those filters.

## Variations

- **For AI Agents** — pattern: agent holds a watchlist. When a user asks "who's buying BBCA?", agent calls `broker_summary_top("BBCA", ...)` (2 credits). When it asks "what's the broader broker scene?", agent calls `top_brokers(date=..., origin='foreign')` (2 credits). When it asks "is foreign money coming in?", agent calls `foreign_flow(symbol, ...)` (1 credit). Total per deep Q: 5 credits. Cache `broker_code → name` registry once (1 credit).
- **For Market Intel "smart money tracker"** — daily cron (08:00 WIB):
  1. `top_brokers(date=today, origin='foreign', cohort='institutional')` → 2 credits
  2. `broker_summary_top` for each ticker in your top-10 watchlist (2 × 10 = 20 credits)
  3. `foreign_flow` for the same 10 (1 × 10 = 10 credits)
  4. **Total**: 32 credits/day. Heavier than the 4-credit movers snapshot but the only way to surface real accumulation patterns.
- **For Automation anomaly alerts** — run weekly, not daily:
  - Compute `foreign_30d_cumulative` for each ticker in watchlist (1 credit × N)
  - Compare to 30-day moving average
  - Alert when current > MA × 2 or current < -MA × 2 (significant deviation)
  - Use `n_quarters`-equivalent batching: 30-day window fits in one call, no stitching.
- **Pair with example 02** — if a name has both positive foreign flow AND a high `forward_pe` from the company report, that's an institutional thesis you can narrate.
