# Sectors API & MCP — quick reference for the build

> Sources (verified 29 Aug 2026):
> - https://sectors.app/api (product page)
> - https://docs.sectors.app (full docs)
> - https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide (MCP guide)
> - https://docs.sectors.app/get-started/v2/migration-guide (v1→v2)
> - https://docs.sectors.app/llms.txt (full docs index)
> - https://sectors.app/pricing (plans + 1,000 hackathon credits context)

This file summarizes what we actually need to know before we touch code. Endpoints we don't use, we ignore.

---

## TL;DR — two ways to talk to Sectors

| | **REST API** | **MCP server** |
|---|---|---|
| **Base URL** | `https://api.sectors.app/v2/...` | `https://sectors-mcp.supertype.ai/mcp` |
| **Auth header** | `Authorization: <api-key>` (raw key) | `Authorization: Bearer <api-key>` |
| **Client** | any HTTP — Python, Node, R, cURL | MCP-compatible client (Claude Code, Cursor, VS Code Copilot, Windsurf, JetBrains, custom Streamable HTTP client) |
| **Coverage** | full IDX + SGX + KLSE + mining + brokers + filings + news | same — **65+ tools** covering IDX, SGX, KLSE, Indonesian mining |
| **Hosting** | cloud (Supertype) | **cloud-hosted on Cloudflare Workers** — no local install |
| **When to use** | cron / automation / REST-of-the-world integrations | AI agent / Claude / Cursor / VS Code workflows |

Both qualify as a "core data source" per hackathon rules §06. **Any track may use either or both.** Pick by stack, not by track.

---

## Two things that matter most

### 1. **The hackathon's "1,000 Sectors API credits" is the Insider plan's API quota**

Pricing reference (https://sectors.app/pricing):
- **Forever Free** — no API access
- **Standard** — $49/mo, AI Chat but **no API**
- **Insider** — $53/mo → **5,000 Sectors API credits/month** + Sectors Workflow + Screener/Query Builder + free workshops
- Hackathon team bonus: **1,000 credits** (one-time, valid during build period, expires at event end — rules §04)

So:
- The 1,000 hackathon credits **are** the same Insider-plan credit pool — they just gate on **hackathon onboarding** instead of $53/mo subscription.
- Onboarding at sectors.app unlocks both (a) API key generation and (b) the 1,000-credit grant once the team claims it (rules §03 + §04).

### 2. **v1 is dead. Use v2.**

v1 discontinued **2026-05-11**. `/v1/*` → HTTP 410 Gone. Always use `/v2/`.

Migration was straightforward (mostly just change `/v1/` → `/v2/`), except 3 endpoints that were redesigned for v2:
1. Companies by Index → use `where` or `q` on `/v2/companies/`
2. Top Companies Ranked → use `order_by` with arbitrary field (e.g. `-revenue[2023]`)
3. Top Companies by Growth → use `order_by=-yoy_quarter_revenue_growth` or natural-language `q`

---

## Auth — concrete

### REST
```python
import requests
url = "https://api.sectors.app/v2/companies/"
headers = {"Authorization": "<api-key>"}   # raw key, no Bearer prefix
r = requests.get(url, headers=headers)
r.raise_for_status()
```

### MCP (Streamable HTTP)
```bash
claude mcp add -t http sectors https://sectors-mcp.supertype.ai/mcp \
  -H "Authorization: Bearer YOUR_API_KEY_HERE"
```

Auth gotchas:
- REST uses raw key (`Authorization: <key>`)
- MCP uses Bearer (`Authorization: Bearer <key>`)
- Either way the **same** Sectors API key, generated from sectors.app/api page after Insider plan (or hackathon onboarding)

---

## Ticker conventions (read this — getting it wrong wastes credits)

- **IDX**: 4-letter code, **omit `.JK`** → `BBCA`, `BMRI`, `TLKM`. The API handles `.JK` internally.
- **SGX**: 3 chars (letters or digits) → `D05`, `U11`, `Z74`. Optional `.si`.
- **KLSE**: 4-digit numeric → `1155`, `4197`, `5225`.
- Subsectors are **kebab-case slugs**: `banks`, `software-it-services`. Use `get-subsectors` (MCP) or `fetch-subsectors` (REST) to get the exact list — don't guess.

---

## REST endpoint catalog (the ones we care about for this hackathon)

REST base: `https://api.sectors.app/v2/`. All require `Authorization: <key>` header.

### Companies & screener
- `GET /v2/companies/` — paginated screener. **SQL-like** `where` + flexible `order_by`, or **natural-language** `q` (LLM translates). Returns `results[]`, `pagination{}`, `llm_translation{}`. `where` supports `=`, `!=`, `>`, `>=`, `<`, `<=`, `like`, `in`, `and`/`or`, bracket notation for yearly fields (`revenue[2024]`), arithmetic (`revenue[2024] / total_assets[2024] > 0.5`). `limit` 1–200, default 50.
- `GET /v2/companies/?where=free_float>0.5` → free float filter (`/screener/free-float`)
- `GET /v2/companies/?sub_sector=...&year=...` → various helper lists

### Per-company reports (the agent-track gold)
- `GET /v2/company/report/{symbol}/?sections=overview,valuation,future,peers,financials,dividend,management,ownership` — full company report, sections are selectable so you don't over-fetch credits.
- `GET /v2/company/segments/{symbol}/{financial_year}/` — Sankey-graph-ready revenue + cost segment breakdown.
- `GET /v2/company/corporate-actions/{symbol}/` — splits, rights, warrants, bonus, AGM, dividend history.
- `GET /v2/company/shareholders-composition/{symbol}/{year}/` — local vs foreign monthly composition.
- `GET /v2/ipo/listing-performance/{symbol}/` — 7d / 30d / 90d / 365d price changes since listing.

### Time-series & financials
- `GET /v2/company/quarterly-financials/{symbol}/?n_quarters=4[&report_date=YYYY-Qn]` — quarterly income + balance sheet. **Banks/insurance have extra fields**: `net_interest_income`, `gross_loan`, `total_deposit`, etc.
- `GET /v2/company/quarterly-financial-dates/{symbol}/` — available report dates (call first, then `report_date=...` for the next call).
- `GET /v2/companies/quarterly-financial-dates/?since=YYYY-MM-DD` — **universe-wide** latest dates, one paginated feed (freshness polling).

### Daily transaction / market
- `GET /v2/transaction/close/{date}/` — daily close for **every** IDX ticker on one date (paginated universe feed — saves credits vs per-symbol calls).
- `GET /v2/transaction/daily/{symbol}/?start=YYYY-MM-DD&end=YYYY-MM-DD` — daily close, volume, market cap for one symbol, **range up to 90 days**.
- `GET /v2/transaction/idx-total/?start=...&end=...` — total IDX market cap history.
- `GET /v2/transaction/index-daily/{index_code}/?start=...&end=...` — index daily close.

### Rankings / movers / most-traded
- `GET /v2/ranking/top-changes/?classifications=top_gainers,top_losers&periods=1d,7d,14d,30d,365d[&sub_sector=...]&n_stock=10`
- `GET /v2/ranking/most-traded/?start=...&end=...&n_stock=20[&sub_sector=...]`

### Foreign flow / brokers
- `GET /v2/brokers/foreign-flow/{symbol}/?start=...&end=...` — daily net foreign-broker inflow, **up to 90 days**.
- `GET /v2/brokers/registry/?origin=foreign&cohort=institutional` — broker registry.
- `GET /v2/brokers/top/?date=YYYY-MM-DD&metric=gross_value|n_abs_net_flow&n_brokers=20`
- `GET /v2/brokers/broker-summary/{broker_code}/{symbol}/?start=...&end=...` — per-broker activity for one stock, **up to 14 days**.
- `GET /v2/brokers/broker-summary/top/{symbol}/?start=...&end=...&n_brokers=20` — top accumulators/distributors for one stock.
- `GET /v2/brokers/broker-activity/{broker_code}/?start=...&end=...` — all stocks that broker touched, **up to 14 days**.
- `GET /v2/brokers/broker-activity/top/{broker_code}/?start=...&end=...` — top accumulations/distributions by one broker.

### Sector / subsector taxonomy
- `GET /v2/subsectors/` — all sector/subsector kebab-slugs (discovery)
- `GET /v2/industries/`, `/v2/subindustries/` — finer taxonomy
- `GET /v2/subsector/report/{sub_sector}/?sections=overview,financials,...` — aggregated subsector report

### News, filings, events
- `GET /v2/news/news/?extension=idx|mining[&sector=...&symbols=...&tags=...&start=...&end=...]` — paginated news
- `GET /v2/news/filings/?symbol=...&transaction_type=buy|sell&holder_type=...&sector=...&start=...&end=...` — insider filings
- `GET /v2/news/suspensions/?symbol=...&start=...&end=...` — stock suspensions with official IDX PDF links
- `GET /v2/tags/` — valid tag slugs for news/filings filter

### SGX (Singapore)
- `GET /v2/sgx/sectors/`, `/v2/sgx/subsectors/`, `/v2/sgx/companies-by-sector/?sector=...`
- `GET /v2/sgx/report/{symbol}/?sections=...`
- `GET /v2/sgx/ranking/top-companies/?classifications=dividend_yield,market_cap&sector=...`
- `GET /v2/sgx/transaction/daily/{symbol}/`, `/v2/sgx/transaction/short-sell/`, `/v2/sgx/transaction/share-buybacks/`
- `GET /v2/sgx/news/news/`, `/v2/sgx/news/filings/`

### KLSE (Malaysia) — thin
- `GET /v2/klse/sectors/`, `/v2/klse/companies/?sector=...`
- `GET /v2/klse/report/{symbol}/`, `/v2/klse/top-companies/`

### Mining (Indonesia) — full
- `GET /v2/mining/companies/?keyword=...&commodity_type=...&company_type=...`
- `GET /v2/mining/companies/{slug}/` — operational detail
- `GET /v2/mining/companies/{slug}/financials/?year=YYYY` — USD millions
- `GET /v2/mining/companies/{slug}/ownership/` — corporate tree
- `GET /v2/mining/companies/{slug}/performance/?commodity_type=...&year=YYYY`
- `GET /v2/mining/sites/?commodity_type=...&province=...&year=...&min_production=...`
- `GET /v2/mining/sites/{slug}/` — site detail with lat/long
- `GET /v2/mining/commodities/`, `/v2/mining/commodities/price/{commodity}/?start_year=...&end_year=...` (monthly, max 3yr)
- `GET /v2/mining/commodities/{commodity}/global/?country=...` — production/reserves/trade
- `GET /v2/mining/commodities/{commodity}/exports/?year=YYYY` — top export destinations
- `GET /v2/mining/licenses/?commodity_type=...&province=...&license_type=...&expiring_soon=true`
- `GET /v2/mining/license-auctions/?status=open|closed`, `/v2/mining/license-auctions/{wiup_code}/`
- `GET /v2/mining/contracts/?mine_owner=...&contractor=...`

---

## MCP tool catalog (if we go MCP instead of REST)

65+ tools, organized by domain. **Tool name = function name, kebab-cased.** Below is the cheat sheet — full table at https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide#tools-reference.

### Company analysis
- `fetch-company-report(symbol, sections)` — sections: overview, valuation, future, peers, financials, dividend, management, ownership
- `fetch-company-segments(symbol, financial_year)` — Sankey-ready segments
- `fetch-listing-performance(symbol)` — 7d/30d/90d/365d since listing
- `fetch-corporate-actions(symbol)` — splits, rights, warrants, AGM, dividend
- `fetch-shareholders-composition(symbol, year)` — local vs foreign monthly

### Market screening & rankings
- `fetch-companies-by-subsector(q?, where?, order_by?, limit?)` — structured or NL
- `fetch-companies-top-changes(classifications, periods, sub_sector?, n_stock?)` — gainers/losers × 1d/7d/14d/30d/365d
- `fetch-most-traded-stocks(start, end, n_stock, sub_sector?)`
- `fetch-close(date)` — every ticker on a date

### Financial data
- `fetch-quarterly-financials(symbol, n_quarters, report_date?)`
- `fetch-quarterly-financial-dates(symbol)`
- `fetch-companies-quarterly-financial-dates(since?, year?)` — universe freshness feed

### Market indices & daily data
- `fetch-index-daily(index_code, start, end)`, `fetch-idx-market-cap(start, end)`, `fetch-daily-transaction(symbol, start, end)`, `fetch-foreign-flow(symbol, start, end)`, `fetch-free-float(sector?, sub_sector?, industry?)`

### Sector taxonomy
- `get-subsectors()`, `fetch-industries()`, `fetch-subindustries()`, `fetch-subsector-report(sub_sector, sections)`, `fetch-companies-with-segments()`

### News, filings, events
- `fetch-news(extension, sector?, sub_sector?, symbols?, keyword?, tags?, start?, end?)`
- `fetch-filings(symbol?, transaction_type?, holder_type?, sector?, start?, end?)`
- `fetch-suspensions(symbol?, start?, end?)`
- `fetch-tags()`

### Brokers
- `fetch-brokers(origin?, cohort?)`, `fetch-top-brokers(date, metric, n_brokers?, origin?, cohort?)`, `fetch-broker-summary(symbol, broker_code, start, end)`, `fetch-broker-summary-top(symbol, start, end, n_brokers?)`, `fetch-broker-activity(broker_code, symbol?, start, end)`, `fetch-broker-activity-top(broker_code, start, end)`

### SGX
- `fetch-sgx-sectors()`, `fetch-sgx-subsectors()`, `fetch-sgx-company-report(symbol, sections)`, `fetch-sgx-companies-by-sector(sector)`, `fetch-sgx-top-companies(classifications, sector?)`, `fetch-sgx-daily-transaction(symbol, start, end)`, `fetch-sgx-filings(symbol?, ...start/end)`, `fetch-sgx-news(sector?, symbols?, tags?, start?, end?)`, `fetch-sgx-buybacks(symbol?, start?, end?)`, `fetch-sgx-short-sell(symbol?, start?, end?)`, `fetch-sgx-tags()`

### KLSE
- `fetch-klse-sectors()`, `fetch-klse-companies-by-sector(sector)`, `fetch-klse-company-report(symbol)`, `fetch-klse-top-companies(classifications, sector?)`

### Mining (Indonesia)
- `fetch-mining-commodities()`, `fetch-mining-commodity-price(commodity_name, start_year, end_year)`, `fetch-mining-global-commodity(commodity_type?, country?)`
- `fetch-mining-companies(keyword?, commodity_type?, company_type?)`, `fetch-mining-company-detail(slug)`, `fetch-mining-company-financials(slug, year?)`, `fetch-mining-company-ownership(slug)`, `fetch-mining-company-performance(slug, commodity_type?, year?)`
- `fetch-mining-sites(commodity_type?, province?, year?, min_production?)`, `fetch-mining-site-detail(slug)`
- `fetch-mining-total-production(commodity_type)`, `fetch-mining-exports(commodity_type, year)`, `fetch-mining-sales-destination(slug, year?)`
- `fetch-mining-contracts(mine_owner?, contractor?)`, `fetch-mining-licenses(commodity_type?, province?, license_type?, expiring_soon?)`, `fetch-mining-license-auctions(commodity_type?, province?, status?)`, `fetch-mining-license-auction-detail(wiup_code)`, `fetch-mining-resources-reserves()`, `fetch-mining-resources-reserves-detail(province, commodity_type, year)`

---

## Data freshness

> "Market prices and daily transaction data are updated at end-of-day. Quarterly financials are updated as companies file their reports. Dividend data is updated when announcements are made."

(From the MCP guide.)

**Implication for Automation track**: cron at 08:00 WIB will see yesterday's EOD data, not today's intraday. If we want intraday we'd have to scrape IDX directly — outside Sectors. Worth noting in the problem statement ("previous-day close + sector flow analysis"), not promising real-time.

---

## Cost / credit budget

- 1,000 credits for the build period (Aug 19 – Sep 30, ~42 days)
- No published per-endpoint credit cost in the public docs I could find
- Proxy: Insider plan gives 5,000/mo → so a single project lifecycle gets ~20% of a monthly subscription worth of calls
- **Implication**: cache aggressively, prefer **universe feeds** (`/v2/transaction/close/{date}/`, `/v2/companies/quarterly-financial-dates/`) over per-symbol calls when we need breadth. Always request `sections=` only when we need them.

---

## What we don't have (gaps to flag)

- No WebSocket / streaming API — everything is request/response. Real-time tick data is out of scope.
- No published per-endpoint credit cost — we'll discover it empirically.
- No explicit rate-limit headers in the docs I read — assume standard (be polite, cache).
- v1 is gone; don't waste time on it.

---

## Hackathon-specific gotchas

1. **Ticker format trap**: don't pass `BBCA.JK` to MCP tools — they want bare `BBCA`. REST tolerates both per docs, MCP doesn't. Pick one and be consistent.
2. **Section selector**: `fetch-company-report(symbol, sections='overview,valuation,dividend')` saves credits vs default full report. Use it.
3. **Universe feeds beat per-symbol loops**: `fetch-close(date)` returns every IDX ticker in one paginated call. Better than 900 separate `/v2/companies/{symbol}/...` calls.
4. **Bracket notation for time-series**: `revenue[2024]` works in `where` for screener. Use it.
5. **News `extension` is required** for `fetch-news` / `/v2/news/news/` — pick `idx` or `mining`.
6. **Free float in API**: `/v2/companies/?where=free_float>0.5` works on `/v2/companies/`; standalone `/v2/screener/free-float/` is also valid.
