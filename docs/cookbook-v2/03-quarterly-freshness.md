# Example 3: Quarterly freshness polling

> Hackathon track fit: **Automation** / AI Agents
> Endpoints exercised: `GET /v2/companies/quarterly-financial-dates/`, `GET /v2/company/get_quarterly_financial_dates/{symbol}/`, `GET /v2/financials/quarterly/{symbol}/`
> Credits per run: **1** for the universe poll + **1 per quarter fetched** for individual financials

## What this demonstrates

- The **two-tier freshness pattern**: a cheap universe-level poll (`/v2/companies/quarterly-financial-dates/?since=...`) tells you which companies published a new quarter, then a targeted `/v2/financials/quarterly/{symbol}/` call pulls the actual numbers.
- The `since=` polling parameter — its existence is the difference between 1 credit and 32 credits per cron tick.
- How `report_date` is the bridge between "discover what's available" and "fetch the actuals".
- The two-step `get_quarterly_financial_dates/{symbol}/` pattern for non-universe use cases (when you only care about one stock).

## Code

```python
"""
Quarterly freshness polling — the credit-efficient way to track IDX reporting.

Two-tier strategy:
  1. Universe-level poll (1 credit): which tickers reported a new quarter since X?
  2. Targeted fetch (1 credit/quarter): pull actuals only for those tickers.

If you don't use `since=`, the universe poll costs ~32 credits per sweep (one per page
of 30 companies, ~950 total). The `since=` filter drops that to ~1 credit per cron tick.
"""
import os
import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def latest_quarterly_dates(since: str | None = None, year: int | None = None,
                           limit: int = 30, offset: int = 0) -> dict:
    """
    Returns the latest available quarterly report date for every IDX company.
    Costs 1 credit per PAGE (limit max 30).

    Args:
        since: YYYY-MM-DD — return only companies whose latest quarter is on/after this.
               THIS IS THE INCREMENTAL POLL KEY — saves ~31 credits vs full sweep.
        year: 1900–2026 — restrict to report dates within this calendar year.
        limit/offset: standard pagination.
    """
    params: dict = {"limit": limit, "offset": offset}
    if since:
        params["since"] = since
    if year:
        params["year"] = year
    r = requests.get(
        f"{BASE}/v2/companies/quarterly-financial-dates/",
        headers=HEADERS, params=params, timeout=15,
    )
    r.raise_for_status()
    return r.json()


def company_quarterly_dates(symbol: str) -> dict:
    """
    Per-symbol helper. Returns {"YYYY": [[date, quarter_label], ...], ...}.
    Costs 1 credit per call.

    Use this BEFORE fetching quarterly financials if you don't already know
    which `report_date` value to pass.
    """
    r = requests.get(
        f"{BASE}/v2/company/get_quarterly_financial_dates/{symbol}/",
        headers=HEADERS, timeout=15,
    )
    r.raise_for_status()
    return r.json()


def quarterly_financials(symbol: str, n_quarters: int = 4,
                         report_date: str | None = None) -> list[dict]:
    """
    Pull the actual quarterly figures. Costs 1 credit per quarter returned.
    Pass `report_date` from a prior `company_quarterly_dates()` call to fetch
    a specific quarter.
    """
    params: dict = {"n_quarters": n_quarters}
    if report_date:
        params["report_date"] = report_date
    r = requests.get(
        f"{BASE}/v2/financials/quarterly/{symbol}/",
        headers=HEADERS, params=params, timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---- Pattern 1: incremental poll (1 credit) ----
# Cron job: every day at 08:00 WIB, ask "who reported a new quarter since I last checked?"
# Then store `since` somewhere (file, env, DB) so the next run knows where to resume.
print("=== Universe poll: who reported Q1 2026 since 2026-04-15? ===")
data = latest_quarterly_dates(since="2026-04-15", limit=30)
print(f"  Showing: {data['pagination']['showing']}, total universe: {data['pagination']['total_count']}")
print(f"  Page 1 first 5:")
for row in data["results"][:5]:
    print(f"    {row['symbol']:<8} latest_date={row['date']}  quarter={row['quarter']}")
print()


# ---- Pattern 2: paginate the full universe when you MUST do a cold sweep ----
# One-time use: e.g. building a baseline DB. ~32 credits.
print("=== Full cold sweep: page through entire IDX ===")
newly_reported = []
offset = 0
while True:
    page = latest_quarterly_dates(offset=offset, limit=30)
    newly_reported.extend(page["results"])
    if not page["pagination"]["has_next"]:
        break
    offset = page["pagination"]["next_offset"]
print(f"  Collected {len(newly_reported)} ticker-date records across full universe")
print()


# ---- Pattern 3: discover a symbol's available dates, then fetch specific quarter ----
print("=== BBCA: discover dates, then fetch Q1 2026 actuals ===")
dates = company_quarterly_dates("BBCA")
# dates == {"2026": [["2026-03-31", "q1"]], "2025": [["2025-09-30", "q3"], ...]}
q1_2026_date = dates["2026"][0][0]
print(f"  BBCA Q1 2026 report_date: {q1_2026_date}")

actual = quarterly_financials("BBCA", report_date=q1_2026_date, n_quarters=1)
row = actual[0]
print(f"  BBCA Q1 2026: revenue={row.get('revenue'):,}  earnings={row.get('earnings'):,}")
print(f"  (banks also expose net_interest_income={row.get('financials_sector_metrics', {}).get('net_interest_income')})")
```

## Expected output shape

Universe poll (paginated):

```json
{
  "results": [
    {"symbol": "AADI.JK", "date": "2026-03-31", "quarter": "q1"}
  ],
  "pagination": {
    "total_count": 959,
    "showing": 1,
    "limit": 30,
    "offset": 0,
    "has_next": true,
    "has_previous": false,
    "next_offset": 30,
    "previous_offset": null
  }
}
```

Per-symbol helper (dictionary keyed by year-string):

```json
{
  "2026": [["2026-03-31", "q1"]],
  "2025": [["2025-09-30", "q3"], ["2025-06-30", "q2"], ["2025-03-31", "q1"]]
}
```

Quarterly financials (array, one row per quarter):

```json
[
  {
    "symbol": "BBCA.JK",
    "date": "2026-03-31",
    "revenue": 28434118000000,
    "earnings": 14695475000000,
    "total_assets": 1640830566000000,
    "financials_sector_metrics": {
      "net_interest_income": 21108433000000,
      "gross_loan": 970701203000000,
      "total_deposit": 1276408911000000
    }
  }
]
```

## Pitfalls

- **`since=` is a discovery-only filter**, not a "give me everything published after". It returns the LATEST date per ticker that is on-or-after the `since` value. So if BBCA reported Q1 2026 in April 2026 and you poll `since=2026-04-20`, you get `{symbol: BBCA, date: 2026-03-31, quarter: q1}` — Q1 is the latest on or after 2026-04-20.
- **Universe poll is sorted by symbol** (~950 tickers, alphabetical), so pagination is deterministic. You can cache page boundaries and resume.
- **`approx=true` default**: `/v2/financials/quarterly/{symbol}/` will fuzzy-match a `report_date` if no exact match exists. If you want strict, set `approx=false`.
- **`n_quarters` cost = n_credits.** Always pass it; the default is "all available" which can be 20+ quarters for an old ticker.
- **Financial-sector extras**: banks/insurers have a nested `financials_sector_metrics` dict with `net_interest_income`, `gross_loan`, `total_deposit`, `current_account`, etc. Other sectors won't have this key — handle with `.get('financials_sector_metrics', {})`.
- **404 vs 400 in this stack**: bad `report_date` format → 400 (free). Unknown symbol → 404 (1 credit wasted). Always validate format before calling.

## Variations

- **For Automation track**: store `since` in `state/last_quarterly_poll.txt`. Each cron tick: `latest_quarterly_dates(since=last_date)` → store the max date seen as new `since` → fetch actuals only for the tickers returned. Costs ~1–5 credits per day.
- **For AI Agents**: agents can call `company_quarterly_dates(symbol)` first (1 credit) to discover "what quarters are available", then decide which to fetch. This is the right pattern for "show me BMRI's last 3 quarters" — never pre-fetch blindly.
- **For Market Intel dashboards**: pre-build a quarterly-events calendar. Run the universe poll once per quarter-end week (Apr/Jul/Oct/Jan) with `since=` set to the previous poll date. Page 1 of results is enough — you're building a table, not streaming.
- **Sector-specific gotcha**: when comparing banks, normalize by `total_assets` or `total_deposit` — `revenue` alone isn't comparable across banks of different sizes. The `financials_sector_metrics` block is the right level of detail.
