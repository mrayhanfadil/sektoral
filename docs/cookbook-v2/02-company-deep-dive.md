# Example 2: Company deep-dive with section selection

> Hackathon track fit: **AI Agents** / Market Intel
> Endpoints exercised: `GET /v2/company/report/{symbol}/`
> Credits per run: **1 per section requested** (default all 8 = 8 credits)

## What this demonstrates

- The single biggest credit-saver in the Sectors API: **select sections** instead of fetching the full report.
- All 8 available sections and what each gives you.
- The `sections=` query parameter syntax and the credit math.
- How to layer this into an agent loop: fetch `overview` first, then conditionally pull `financials` only if you need numbers.

## Code

```python
"""
Company deep-dive with section selection.

Rule of thumb: only fetch the sections you actually need to render / reason about.
Default behavior fetches all 8 and costs 8 credits. The example below shows a
3-section fetch for a quick valuation summary = 3 credits.
"""
import os
import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def company_report(symbol: str, sections: list[str] | None = None) -> dict:
    """
    Fetch a company report.

    Args:
        symbol: IDX ticker, bare form (e.g. 'BBCA'). API tolerates 'BBCA.JK' too.
        sections: list of section names to fetch, or None for all (8 credits).
                  Valid: overview, valuation, future, peers, financials,
                         dividend, management, ownership.

    Credit cost = len(sections) if sections else 8.
    """
    params = {}
    if sections is not None:
        params["sections"] = ",".join(sections)
    r = requests.get(
        f"{BASE}/v2/company/report/{symbol}/",
        headers=HEADERS,
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---- Cheap "is this stock worth a deeper look?" check (2 credits) ----
print("=== BBCA quick valuation (overview + valuation only) ===")
report = company_report("BBCA", sections=["overview", "valuation"])
overview = report["overview"]
valuation = report["valuation"]
print(f"  Name      : {overview.get('company_name')}")
print(f"  Market cap: Rp {overview.get('market_cap', 0):,}")
print(f"  Forward PE: {valuation.get('forward_pe')}")
print(f"  Last close: Rp {valuation.get('last_close_price'):,}")
print(f"  Intrinsic : Rp {valuation.get('intrinsic_value'):,}")
print()


# ---- Medium "agent reasoning" fetch (4 credits) ----
print("=== BMRI agent briefing (overview + valuation + peers + dividend) ===")
report = company_report("BMRI", sections=["overview", "valuation", "peers", "dividend"])
print(f"  Peer count : {len(report.get('peers', []))}")
print(f"  Dividend yield TTM: {report.get('dividend', {}).get('dividend_yield_ttm')}")
print(f"  Payout ratio      : {report.get('dividend', {}).get('payout_ratio')}")
print()


# ---- Full report (8 credits — only do this when you're building a profile page) ----
print("=== TLKM full report (all 8 sections, 8 credits) ===")
report = company_report("TLKM")
print(f"  Sections returned: {sorted(report.keys())}")
```

## Expected output shape

Each section is a top-level key in the response. The shape of each section varies; `overview` is mostly identity + market cap + tags, `valuation` is price-history + per-year ratios, `peers` is an array of {symbol, company_name, market_cap, ...}, etc.

```json
{
  "overview": {
    "symbol": "BBCA.JK",
    "company_name": "Bank Central Asia Tbk",
    "market_cap": 1095329638012500,
    "listing_date": "2000-05-31",
    "indices": ["LQ45", "IDX30"],
    "tags": ["blue-chip", "dividend"],
    "esg_score": 78.4
  },
  "valuation": {
    "symbol": "BBCA.JK",
    "last_close_price": 8975,
    "forward_pe": 21.5,
    "intrinsic_value": 10200,
    "pb_history": {"2020": 4.1, "2021": 4.5, "2022": 4.3, "2023": 4.7, "2024": 4.4},
    "pe_history":  {"2020": 28.1, "2021": 30.2, "2022": 27.8, "2023": 25.4, "2024": 22.6}
  },
  "peers": [...],
  "dividend": {...}
}
```

## Pitfalls

- **No partial sections / free preview.** Every section costs 1 credit. No way to get just the `symbol` for free.
- **404 still costs 1 credit.** A typo like `BBA` (instead of `BBCA`) returns 404 — and you got billed for the lookup. Validate ticker against example 01 (`/v2/companies/` screener) before calling.
- **`.JK` suffix**: works either way. Bare form is what MCP tools expect, so use it everywhere for consistency.
- **`valuation` is per-year ratios**: `pe_history`, `pb_history` are dicts keyed by year-string (`"2024"`). Don't index with integers — `pe_history["2024"]` works, `pe_history[2024]` doesn't.
- **`peers` is the company's own subsector peers**, not custom — if you want to compare across subsectors, fetch each ticker individually or call `/v2/subsector/report/{sub_sector}/` for an aggregated peer view.
- **`ownership` and `management` sections can be heavy** (lists of shareholders / directors). Skip them in agent loops unless the agent's reasoning specifically needs them.

## Variations

- **For AI Agents**: pattern is "fetch overview → if user asks for numbers, fetch valuation → if user asks for comparison, fetch peers". Each step gates the next, so a single Q&A costs 1–3 credits, not 8.
- **For Market Intel dashboard**: pre-fetch all 8 sections once for a "stock detail page" the first time a user opens it, then cache the JSON for 24h. This is the only case where the full 8-section fetch is justified.
- **For Automation (cron-watchers)**: section selection lets you run a "dividend aristocrat screener" cheaply — `sections=dividend,overview` for the entire LQ45 universe = 2 × 45 = 90 credits (vs 8 × 45 = 360 with full reports).
- **Cross-reference**: `/v2/company/segments/{symbol}/{financial_year}/` (Sankey-ready revenue + cost breakdown) is a SEPARATE endpoint, costs 1 credit per (symbol, year). Useful when `financials` section alone isn't enough.
