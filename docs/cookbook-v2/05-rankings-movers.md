# Example 5: Top movers + most-traded

> Hackathon track fit: **Market Intel** / AI Agents
> Endpoints exercised: `GET /v2/companies/top-changes/`, `GET /v2/most-traded/`
> Credits per run: **2** (trimmed top-changes 1×1 + 1 most-traded 2 credits) — up to **12** if you take defaults

## What this demonstrates

- The **classifications × periods credit grid**: top-changes costs 1 credit per (classification × period) combo. Default = 10 credits (2 classifications × 5 periods). Trim ruthlessly.
- Top movers and most-traded as the **two cheapest "daily pulse"** queries — under 5 credits gets you the full daily heatmap.
- Filtering by `sub_sector` to focus on a single industry (e.g. just banks).
- `adjusted=true` for most-traded, which ranks by `volume × close` (turnover IDR) instead of raw share count — better signal for institutional flow.

## Code

```python
"""
Top movers + most-traded — the daily pulse, trimmed to ~2-3 credits.

Credit math (IMPORTANT):
  - top-changes:  1 credit per (classification × period) combo
                   default 2×5 = 10 credits. Trim by passing ONLY what you need.
  - most-traded:  2 credits flat, regardless of params.

The pattern below:
  - Top 5 gainers + top 5 losers over 1d AND 7d = 2×2 = 4 credits  ← still too much
  - Drop to just 1d gainers+losers = 2×1 = 2 credits              ← better
  - + most-traded = 2 credits
  - TOTAL = 4 credits for a "daily movers + volume" snapshot
"""
import os
import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def top_changes(classifications: list[str] | None = None,
                periods: list[str] | None = None,
                sub_sector: str | None = None,
                n_stock: int = 5,
                min_mcap_billion: int = 5000) -> dict:
    """
    Top gainers and/or losers across periods. Cost = len(classifications) × len(periods).

    Defaults if not passed: classifications=['top_gainers','top_losers'],
    periods=['1d','7d','14d','30d','365d'] → 10 credits.

    ALWAYS trim. The 7d/30d/365d windows are useful for narrative pieces, not
    daily monitoring — most Market Intel products only need 1d.
    """
    params: dict = {
        "n_stock": n_stock,
        "min_mcap_billion": min_mcap_billion,
    }
    if classifications is not None:
        params["classifications"] = ",".join(classifications)
    if periods is not None:
        params["periods"] = ",".join(periods)
    if sub_sector is not None:
        params["sub_sector"] = sub_sector
    r = requests.get(
        f"{BASE}/v2/companies/top-changes/",
        headers=HEADERS, params=params, timeout=15,
    )
    r.raise_for_status()
    return r.json()


def most_traded(start: str, end: str,
                sub_sector: str | None = None,
                n_stock: int = 5,
                adjusted: bool = False) -> dict:
    """
    Most traded by volume over the date range (max 90 days). 2 credits flat.

    Set adjusted=true to rank by turnover (volume × close) instead of raw share
    count — better proxy for institutional flow.

    Response is a dict keyed by date.
    """
    params: dict = {
        "start": start, "end": end,
        "n_stock": n_stock,
        "adjusted": "true" if adjusted else "false",
    }
    if sub_sector:
        params["sub_sector"] = sub_sector
    r = requests.get(
        f"{BASE}/v2/most-traded/",
        headers=HEADERS, params=params, timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---- 1d gainers only (1 credit) ----
print("=== Top 5 gainers, 1d, IDX-wide ===")
data = top_changes(
    classifications=["top_gainers"],
    periods=["1d"],
    n_stock=5,
    min_mcap_billion=1000,  # include mid-caps
)
for row in data["top_gainers"]["1d"]:
    pct = row["price_change"] * 100
    print(f"  +{pct:6.2f}%  {row['symbol']:<10} Rp {row['last_close_price']:,}  ({row['name'][:35]})")
print()


# ---- 1d gainers AND losers (2 credits) ----
print("=== Top 5 gainers + losers, 1d ===")
data = top_changes(
    classifications=["top_gainers", "top_losers"],
    periods=["1d"],
    n_stock=5,
)
print("  Gainers:")
for row in data["top_gainers"]["1d"]:
    print(f"    +{row['price_change']*100:6.2f}%  {row['symbol']:<10} Rp {row['last_close_price']:,}")
print("  Losers:")
for row in data["top_losers"]["1d"]:
    print(f"    {row['price_change']*100:6.2f}%  {row['symbol']:<10} Rp {row['last_close_price']:,}")
print()


# ---- Sub-sector focus: banks 1d ----
print("=== Top movers, banks subsector, 1d ===")
data = top_changes(
    classifications=["top_gainers", "top_losers"],
    periods=["1d"],
    sub_sector="banks",
    n_stock=5,
)
for row in data["top_gainers"]["1d"]:
    print(f"    +{row['price_change']*100:6.2f}%  {row['symbol']}")
print()


# ---- Most-traded, 1d, with adjusted (turnover) ranking (2 credits) ----
print("=== Most traded, 2026-06-09, adjusted by turnover ===")
data = most_traded(start="2026-06-09", end="2026-06-09", n_stock=5, adjusted=True)
for date, rows in data.items():
    print(f"  {date}:")
    for row in rows:
        # turnover = volume × close (in IDR, not normalized)
        turnover = row["volume"] * row["price"]
        print(f"    {row['symbol']:<10} vol={row['volume']:>12,}  close=Rp {row['price']:,}  "
              f"turnover=Rp {turnover:>16,}")
print()


# ---- Combined "daily pulse" = 4 credits total ----
# (top-changes 1d gainers+losers = 2 credits) + (most-traded adjusted = 2 credits)
# This is the canonical "morning brief" recipe.
print("=== Daily pulse: 4 credits ===")
print("  Already shown above — combine the top_changes(periods=['1d']) + most_traded() calls.")
```

## Expected output shape

`/v2/companies/top-changes/` response (nested dict: classification → period → array):

```json
{
  "top_gainers": {
    "1d": [
      {
        "name": "PT Nitrasanata Dharma Tbk",
        "symbol": "JECX.JK",
        "price_change": 0.25,
        "last_close_price": 1950,
        "latest_close_date": "2026-07-08"
      }
    ],
    "7d": [...],
    "14d": [...],
    "30d": [...],
    "365d": [...]
  },
  "top_losers": {
    "1d": [...],
    "7d": [...],
    ...
  }
}
```

Only requested classifications × periods appear in the response — empty combos are omitted.

`/v2/most-traded/` response (dict keyed by date):

```json
{
  "2025-05-02": [
    {"symbol": "GOTO.JK",  "company_name": "PT GoTo Gojek Tokopedia Tbk", "volume": 2627450200, "price": 82},
    {"symbol": "DEWA.JK",  "company_name": "Darma Henwa Tbk",              "volume": 1563426700, "price": 138},
    {"symbol": "BUMI.JK",  "company_name": "Bumi Resources Tbk",           "volume": 1012962400, "price": 112}
  ]
}
```

## Pitfalls

- **`price_change` is a decimal, not a percentage.** `0.25` means +25%. Multiply by 100 for display.
- **`min_mcap_billion` default is 5000** (5 trillion IDR). That filters out small caps. For hackathon dashboards you usually want a lower threshold — pass `min_mcap_billion=1000` (1 trillion) to capture more names.
- **`n_stock` max is 10.** Don't pass higher values.
- **`sub_sector` must be kebab-case**: `banks`, `consumer-non-cyclicals`, `energy`. Use `/v2/subsectors/` to discover (1 credit, cache the result forever).
- **`most-traded` ignores limit/offset** — only `n_stock` controls output size, and the date range is the actual paging dimension.
- **`adjusted=true` flips the ranking semantic**: with raw volume, a sub-Rp100 penny stock with 100B shares trades "wins"; with adjusted (turnover), institutional-grade names surface. Always use `adjusted=true` for "real money flow" framing.
- **Date range defaults to last 30 days.** If you want a single day, pass `start=end`. Multi-day responses grow the dict; budget for that in your UI.

## Variations

- **For Market Intel "morning brief"** — 4 credits total:
  1. `top_changes(periods=['1d'], classifications=['top_gainers','top_losers'])` → 2 credits
  2. `most_traded(start=yesterday, end=yesterday, adjusted=true)` → 2 credits
  That's the whole snapshot.
- **For AI Agents** — surface these as tools. Agent decides whether to fetch `top_changes(periods=['1d','7d'])` (2 credits) or `top_changes(periods=['1d'])` (1 credit) based on the question. Always trim periods.
- **For Automation cron** — run at 08:00 WIB Mon-Fri. Store results in a per-day JSON file keyed by date. Don't re-pull — top movers for a closed day never change.
- **Narrative piece** (1-off) — take the default `top_changes()` (10 credits) to get the full matrix for a "year in review" style article. This is the one case where the default makes sense.
- **Sector focus** — for the hackathon's Indonesian context, common sub_sector slugs: `banks`, `consumer-non-cyclicals`, `energy`, `basic-materials`, `industrial`, `infrastructure`, `technology`, `healthcare`. Get the full list once, cache it.
