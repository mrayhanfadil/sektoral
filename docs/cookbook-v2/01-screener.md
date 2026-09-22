# Example 1: Screener with `where` + bracket notation

> Hackathon track fit: **All** (Market Intel most natural fit, AI Agents for the NL-query path)
> Endpoints exercised: `GET /v2/companies/`
> Credits per run: **1** (structured `where+order_by`) — **3** if you use `?q=` natural-language

## What this demonstrates

- The SQL-like `where` + `order_by` screener contract on `/v2/companies/`.
- Three filter idioms every recipe will use:
  - **Bracket notation** for yearly fields (`revenue[2024] > 100_000_000_000`).
  - **`in` operator** for array fields (`indices in ['LQ45','IDX30']`).
  - **Arithmetic in `where`** (e.g. `roe[2024] / roe[2023] > 1.2`).
- The two mutually-exclusive query modes (`where+order_by` vs `q=`) and when to use each.
- The `pagination{}` shape every list endpoint returns.

## Code

```python
"""
Sectors screener demo.

Three queries, each costs 1 credit (structured mode):
  1. Big banks with strong ROE
  2. LQ45 constituents that grew revenue YoY
  3. 'q=' natural-language fallback (costs 3 credits)

Drop your key in SECTORS_API_KEY env var.
"""
import os
import requests
from urllib.parse import urlencode

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def screen(where: str | None = None, order_by: str | None = None,
           q: str | None = None, limit: int = 10) -> dict:
    """Wrapper around /v2/companies/. Pass EITHER (where, order_by) OR q, never both."""
    params = {"limit": limit}
    if q is not None:
        # natural-language mode. NOTE: 'q' overrides where/order_by on the server side.
        params["q"] = q
    else:
        if where is not None:
            params["where"] = where
        if order_by is not None:
            params["order_by"] = order_by
    r = requests.get(f"{BASE}/v2/companies/", headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# ---- Query 1: Banks with ROE > 15% AND PE < 15 (bracket-free, simple fields) ----
print("=== Banks: ROE > 15% AND PE_ttm < 15, top 10 by market cap ===")
data = screen(
    where="sub_sector = 'banks' and roe_ttm > 0.15 and pe_ttm < 15",
    order_by="-market_cap",
    limit=10,
)
for row in data["results"][:5]:
    print(f"  {row['symbol']:<8} {row['company_name'][:35]:<35} "
          f"ROE={row.get('roe_ttm')} PE={row.get('pe_ttm')} mcap_rank={row.get('market_cap_rank')}")
print(f"  total matched: {data['pagination']['total_count']}\n")


# ---- Query 2: LQ45 names that GREW revenue 2023 -> 2024 by >= 20% ----
# This is the canonical use of bracket notation + arithmetic in a single condition.
print("=== LQ45 with revenue[2024] >= 1.2 * revenue[2023] (>=20% YoY) ===")
data = screen(
    where="indices in ['LQ45'] and revenue[2024] >= revenue[2023] * 1.2",
    order_by="-yoy_quarter_revenue_growth",
    limit=10,
)
for row in data["results"][:5]:
    print(f"  {row['symbol']:<8} {row['company_name'][:35]:<35} "
          f"q_yoy={row.get('yoy_quarter_revenue_growth')}")
print(f"  total matched: {data['pagination']['total_count']}\n")


# ---- Query 3: Natural-language fallback ----
# Use this when you don't know the exact field name. Costs 3 credits, server-side LLM
# translation is returned in data["llm_translation"] so you can SEE what it picked.
print("=== NL: 'top 5 banks by market cap in 2024' (q= path, 3 credits) ===")
data = screen(q="top 5 banks by market cap in 2024", limit=5)
for row in data["results"]:
    print(f"  {row['symbol']:<8} {row['company_name']}")
print(f"  llm translated to: where={data.get('llm_translation', {}).get('translated_params', {}).get('where')}")
```

## Expected output shape

The full response is `{results: [...], pagination: {...}, llm_translation?: {...}}`. For `q=` calls, `llm_translation.translated_params` shows you the structured query the LLM picked — useful for debugging "why did my NL query return zero results?".

```json
{
  "results": [
    {
      "symbol": "BBCA.JK",
      "company_name": "Bank Central Asia Tbk"
    }
  ],
  "pagination": {
    "total_count": 2,
    "showing": 2,
    "limit": 50,
    "offset": 0,
    "has_next": false,
    "has_previous": false,
    "next_offset": null,
    "previous_offset": null
  },
  "llm_translation": {
    "natural_query": "top 2 banks by market cap in 2024",
    "translated_params": {
      "where": "sub_sector = 'banks'",
      "order_by": "-market_cap",
      "limit": 2,
      "offset": 0
    },
    "message": "Used sub_sector = 'banks' to filter for banking companies."
  }
}
```

## Pitfalls

- **`q` overrides `where`/`order_by` server-side.** Don't mix them in one call — silently the `q` wins. Pick a mode deliberately.
- **Smart FY handling**: between Jan and Apr, "latest year" queries default to the **previous** audited year (e.g. early 2026 uses 2024 data). If you need current-year data, use `revenue[2026]` directly.
- **Field names are case-sensitive.** `roe_ttm` works, `ROE_TTM` doesn't. Bracket fields too: `revenue[2024]` works, `Revenue[2024]` doesn't.
- **`limit` cap is 200, default is 50.** Set it explicitly if you need fewer — saves parsing work, same credit cost.
- **String values** must use single or double quotes — `sector = 'Financials'` not `sector = Financials`.
- **404 vs 200-empty**: an unmatched `where` returns `200` with `results: []` and still bills 1 credit. A bad column name returns `400` (free, no credit) — different from "no matches". Use the status code, not the array length, to distinguish.

## Variations

- **For Market Intel track** (e.g. "IDX Energy Pulse"): combine `sub_sector = 'oil-gas-energy'` with `revenue[2024] / revenue[2023] > 1.1` and `order_by=-forward_pe` to surface undervalued energy growers.
- **For AI Agents track**: drive the `where` clause from an LLM's structured output. Cap fields with a whitelist — the screener accepts arbitrary fields but you should sandbox what the agent can ask for.
- **For Automation track**: pair with `/v2/companies/quarterly-financial-dates/` (example 03) — only re-screen when a company publishes a new quarter. Cron at 08:00 WIB with `since=`-style freshness check saves 30+ credits/day vs full re-screening.
- **Currency fields are all IDR integers**, not float. `market_cap=1095329638012500` means Rp 1,095,329,638,012,500. Don't divide by 1e9 thinking it's millions.
