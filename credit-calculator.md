# Sectors API credit calculator

> 1,000 API credits per team. Non-transferable. Expire at event end (rules §04). Budget them like cash.

## Why this exists as its own file

F1 audit gap **G-9**: "Credit budgeting calculator — `sectors-api-and-mcp.md` estimates '100–200 well-scoped calls' with 1,000 credits. Without a calculator, the team can't pre-budget a Track-1 agent loop vs a Track-2 cron vs a Track-3 screener."

This file is the operational budget. Use it before committing to a build plan.

## Cost matrix (from `references/sectors-api-and-mcp.md` + per-endpoint docs)

| Endpoint family | Cost / call | Notes |
|---|---|---|
| Screener `GET /v2/companies/` (structured `where`) | **1 credit** | Default. |
| Screener `GET /v2/companies/?q=natural_language` | **3 credits** | Spikes on NL queries because LLM runs. |
| Universe feed `GET /v2/transaction/close/{date}/` | 1 credit/page | Returns all IDX tickers in paginated feed — far cheaper than per-symbol loops. |
| Per-company report `GET /v2/company/report/{symbol}/?sections=...` | 1 credit (most sections) | Higher if multi-section reports. |
| `GET /v2/company/quarterly-financials/{symbol}/` | 1 credit | |
| `GET /v2/news/news/`, `/v2/news/filings/`, `/v2/news/suspensions/` | 1 credit | |
| `GET /v2/brokers/top/`, `/v2/brokers/foreign-flow/{symbol}/`, `/v2/brokers/broker-summary/{broker}/{symbol}/` | 1 credit | Foreign-flow returns 90 days of daily data — high-value per credit. |
| Mining endpoints (companies, sites, commodities, licenses, auctions) | 1 credit each | |
| 404 (addressed resource not found) | 1 credit | "You are billed for the lookup, not the result." |
| 400 (bad request), 401/403, 429, 5xx | **0 credits** | Free — early rejection. |

## Track-specific budgets (4-week build, 1,000 credits)

### Track 01 — AI Agent (Asing Radar-style or Saham Jujur-style)

**Asing Radar (recommended):** Daily cron at 08:00 WIB.

| Phase | Calls per day | Calc | Credits/day | 30-day total |
|---|---|---|---|---|
| Universe close (1 page) | 1 | Fetch IDX universe | 1 | 30 |
| Foreign-flow loop (top 50 tickers) | 50 | `?start=YYYY-MM-DD&end=YYYY-MM-DD` | 50 | 1,500 |
| Optional drill-down on `/dive <TICKER>` | ~5 (interactive) | detail + broker summary | 5 | (no fixed budget) |
| **Daily total** | ~56 | | **56** | **1,680** |

❌ **Asing Radar exceeds 1,000 credits in 18 days at this rate.** Need to either (a) cache aggressively, (b) reduce to top 20 tickers, or (c) use shorter 5-day rolling window and amortize across days.

**Better:** Cache 5-day rolling window in KV with 24h TTL → 1 universe call + 50 ticker calls = 51 credits/day, but the 50 only happens on first cron per day. Subsequent calls hit cache → **51 credits/day** = ~19 days budget. Still tight.

**Cache-optimized budget (1,000 credits, 30 days):**
- Universe close once per day: 1 × 30 = **30 credits**
- Foreign-flow loop on first cache miss per ticker per day: 50 × 30 = **1,500** (still too high — cache doesn't help within a single day's run)
- **Solution: shrink the loop to top 10 tickers only**: 10 × 30 = **300 credits**
- Drill-down `/dive` calls (interactive, user-triggered): ~5/day = **150 credits/month**
- Buffer for dev/test: **520 credits**

**Final track-02 budget (Asing Radar, optimized): ~1,000 credits across 30 days.**

### Track 01 — Saham Jujur-style agent

User asks ad-hoc ticker questions. No cron. Cost = sum of per-query tools called.

| Per-query tools | Cost |
|---|---|
| 1 overview call (most queries) | 1 credit |
| 1 detailed report with 4 sections | 1 credit (max-section report) |
| 1 quarterly financials call | 1 credit |
| 1 corporate-actions call | 1 credit |
| 1 shareholders-composition call | 1 credit |
| 1 foreign-flow 5-day call | 1 credit |
| **Total per agent answer** | **6 credits** |

**Budget:** 1,000 credits / 6 = **~167 agent answers** = ~5/day over 30 days. Comfortable.

### Track 03 — Screener / Smart-Money Score

User-driven screener, less frequency.

- 1 NL screener query: **3 credits** (LLM-side)
- 1 structured screener query: **1 credit**
- 1 most-traded pull: **1 credit**
- 1 foreign-flow per ticker: **1 credit**

**Per screener session:** ~10 credits. Budget: **~100 sessions**. Plenty.

### Track 03 — Tema Scanner (theme → ticker mapping)

Mostly static data, recomputed weekly.

- Subsector list: 1 credit (cached)
- Companies per theme (8 themes): 8 × 1 = **8 credits/week**
- Mining commodity data per theme: 4 themes × 1 = **4 credits/week**
- Cache hit on repeat queries: **0 credits**

**Budget:** ~50 credits/week × 4 weeks = **200 credits**. Very comfortable.

## Universal rules

- **Empty array results cost 1 credit** (the query ran). Build filters that fail fast.
- **Test calls in dev** count toward your 1,000-credit budget. Use free 400 errors aggressively during integration testing (send malformed params to confirm your code handles the error path — those are free).
- **Cache by ticker per EOD.** Sectors says EOD-updated. 24h TTL is safe for almost all endpoints. Universe-feed endpoints are the best cache anchor.

## Cross-track comparison

| Track | Recommended idea | Est. credits/day | Headroom |
|---|---|---|---|
| 01 — Agent | Saham Jujur | ~6 (per query) | ✅ ~167 queries |
| 02 — Automation | Asing Radar | ~50 (with cache) | 🟡 tight |
| 02 — Automation | Pre-market brief | ~80 (multiple signals) | 🟡 tight |
| 03 — Market Intel | Tema Scanner | ~7 (weekly batch) | ✅ very comfortable |
| 03 — Market Intel | Dividend Consistency | ~15 (cron) | ✅ comfortable |

## When you blow the budget

It's over. Rules §04 says credits are non-transferable and not exchangeable. There is no top-up. **Plan around the limit, not against it.**
