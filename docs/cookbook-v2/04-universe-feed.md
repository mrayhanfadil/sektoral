# Example 4: Universe feed — full-IDX daily close + total market cap

> Hackathon track fit: **Market Intel** / Automation
> Endpoints exercised: `GET /v2/close/`, `GET /v2/idx-total/`
> Credits per run: **~33 credits** for full universe close (32 pages × 1 + 1 for idx-total). Use `?date=` to fetch historical days.

## What this demonstrates

- The **paged universe feed** pattern: get closing prices for **every IDX ticker** on a single day in one paginated call series. Beats per-symbol `/v2/daily/{symbol}/` calls by ~30× on credits.
- `limit` cap of 30 per page (max), so full IDX universe (~950 tickers) is ~32 pages = ~32 credits per day.
- Pairing with `/v2/idx-total/` for total-IDX market cap to anchor a "% of IDX" view.
- Why this is the **canonical "every morning at 08:00 WIB" cron job** for Market Intel track.

## Code

```python
"""
Universe feed: pull every-IDX close for one day + IDX total market cap.

Total cost for one full pull: ~33 credits
  - /v2/close/: 32 pages × 1 credit  (~950 tickers, 30 per page)
  - /v2/idx-total/: 1 credit

For a daily cron at 08:00 WIB this is the core "market state" snapshot.
"""
import os
import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def fetch_close(date: str | None = None, limit: int = 30) -> list[dict]:
    """
    Returns the close for every IDX ticker on `date` (YYYY-MM-DD), defaulting
    to the most recent trading day. Page through with the returned pagination
    cursor — `next_offset` is null when there are no more pages.

    Costs 1 credit per page. limit max 30.
    """
    out: list[dict] = []
    offset = 0
    while True:
        params = {"limit": limit, "offset": offset}
        if date:
            params["date"] = date
        r = requests.get(f"{BASE}/v2/close/", headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        page = r.json()
        out.extend(page["results"])
        if not page["pagination"]["has_next"]:
            break
        offset = page["pagination"]["next_offset"]
    return out


def fetch_idx_total(start: str, end: str) -> list[dict]:
    """
    Total IDX market cap over a date range (max 90 days). 1 credit per call.
    Earliest valid start: 2021-01-01.
    """
    r = requests.get(
        f"{BASE}/v2/idx-total/",
        headers=HEADERS,
        params={"start": start, "end": end},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---- Full pull for a specific date ----
print("=== Full IDX close, 2026-06-09 ===")
closes = fetch_close(date="2026-06-09")
print(f"  Got {len(closes)} tickers")
# Show top 5 by close (rough proxy for high-priced names)
top5 = sorted(closes, key=lambda r: r["close"], reverse=True)[:5]
for row in top5:
    print(f"  {row['symbol']:<10} close=Rp {row['close']:>6,}")
print()


# ---- Latest trading day (no date param) ----
print("=== Latest trading day (most recent) ===")
latest = fetch_close()
print(f"  {len(latest)} tickers; sample first 3:")
for row in latest[:3]:
    print(f"  {row}")
print()


# ---- IDX total market cap (90-day window) ----
print("=== IDX total market cap, last 30 days ===")
mcap = fetch_idx_total(start="2026-05-10", end="2026-06-09")
print(f"  {len(mcap)} daily points; latest: Rp {mcap[-1]['idx_total_market_cap']:,}")
print()


# ---- Combine: "what % of IDX is this ticker?" ----
# Useful framing for Market Intel dashboards ("BBCA = 11% of IDX by market cap")
print("=== BBCA as % of IDX, on 2026-06-09 ===")
day_close = next((r for r in closes if r["symbol"] == "BBCA.JK"), None)
if day_close and mcap:
    # NOTE: /v2/close/ only gives price, not market cap per ticker.
    # Use /v2/daily/{symbol}/ for per-symbol market cap, OR pull BBCA from
    # /v2/companies/ (market_cap field) — that's 1 extra credit but no date pin.
    print(f"  BBCA close: Rp {day_close['close']:,}")
    print(f"  IDX total mcap (same day): Rp {mcap[-1]['idx_total_market_cap']:,}")
    print(f"  (To compute BBCA's %, fetch its market_cap from /v2/companies/ — 1 extra credit)")
```

## Expected output shape

`/v2/close/` page response (one of N):

```json
{
  "results": [
    {"symbol": "AADI.JK", "date": "2025-05-02", "close": 7150}
  ],
  "pagination": {
    "total_count": 942,
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

`/v2/idx-total/` response (flat array, one row per trading day in the window):

```json
[
  {"date": "2026-06-09", "idx_total_market_cap": 10095511071726246}
]
```

## Pitfalls

- **Tickers with no recorded close for the day are omitted** from `/v2/close/`. If a ticker was suspended or had no trades, it won't appear. Don't assume `len(closes) == ~950` — expect 800–950 depending on the day.
- **`.JK` suffix in response**: `/v2/close/` returns symbols with `.JK` suffix (`"symbol": "BBCA.JK"`), unlike the screener which sometimes strips it. If you mix them in your code, normalize to bare form.
- **Limit hard cap is 30**, not 50 like the screener. Don't try `limit=100`.
- **`date` defaults to most recent trading day.** If you want a specific day and the market was closed, you'll get 400 (free, no credit).
- **Future dates return 400** — common bug when a cron job's clock is in the wrong timezone. Pin `date=` to yesterday's date, not today's.
- **No volume data here**: `/v2/close/` is close-only. For close + volume + market cap, use `/v2/daily/{symbol}/` per ticker (1 credit each), or look up `market_cap` from `/v2/companies/`.
- **Earliest `/v2/idx-total/` is 2021-01-01.** Going earlier returns 400.
- **Idempotent paginate**: `pagination.next_offset` is what you pass back as `offset`. `has_next` is the loop terminator. Don't track page count manually.

## Variations

- **For Market Intel dashboards**: the canonical "every morning 08:00 WIB" job — fetch yesterday's `/v2/close/` (32 credits), fetch the matching `/v2/idx-total/` row (1 credit). Store as JSON for the day. After 30 trading days you've spent ~990 credits — about your whole budget. **Cache aggressively**; do NOT re-pull closed days.
- **For Automation track**: combine with example 03 (quarterly freshness) — only fetch `/v2/close/` for tickers that just reported a new quarter. ~30 credits/day drops to ~5 if 80% of the universe hasn't reported.
- **For AI Agents**: don't call this in the hot path. Pre-fetch at session start and serve from a local cache. `/v2/close/` is a bulk tool, not a per-question lookup.
- **Pair with example 05** (top-changes) for a "market snapshot" UI: today's close + 1d gainers/losers in ~43 credits.
- **Framing**: for "% of IDX" calculations, use BBCA's `market_cap` from `/v2/companies/` (1 credit) divided by `idx_total_market_cap` from `/v2/idx-total/`. Don't try to back-compute market cap from `/v2/close/` — it doesn't have share count.
